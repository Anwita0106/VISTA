"""Cross-cutting helpers: audit trail, notifications, serialisers, escalation rule."""
import zlib
from datetime import UTC, date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import ESCALATION_SLA_HOURS
from .models import (
    AuditLog,
    Complaint,
    ComplaintUpdate,
    Notification,
    User,
)


def audit(db: Session, user: User | None, action: str, entity: str, entity_id="", detail: str = "") -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            detail=detail[:500],
        )
    )


def notify(db: Session, user_id: int, title: str, body: str = "", link: str = "", kind: str = "INFO") -> None:
    db.add(Notification(user_id=user_id, title=title[:150], body=body[:500], link=link, kind=kind))


def notify_many(db: Session, users: list[User], title: str, body: str = "", link: str = "", kind="INFO") -> None:
    for u in users:
        notify(db, u.id, title, body, link, kind)


def lock_for_user(db: Session, user_id: int, scope: str) -> None:
    """Serialise create-requests per user and scope (DEF-01 fix).

    Uses a PostgreSQL transaction-level advisory lock, so a duplicate check followed by an insert
    cannot interleave with an identical request running in parallel (e.g. a double-click)."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        key = zlib.crc32(scope.encode()) * 1_000_003 + user_id  # deterministic across processes
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key & 0x7FFFFFFFFFFFFFFF})


def not_found(what: str = "Record") -> HTTPException:
    return HTTPException(404, f"{what} not found")


def bad_request(msg: str) -> HTTPException:
    return HTTPException(400, msg)


def conflict(msg: str) -> HTTPException:
    return HTTPException(409, msg)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def today() -> date:
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()  # campus local date (IST)


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise HTTPException(422, f"{field} must be a valid date (YYYY-MM-DD)") from None


def user_brief(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "full_name": u.full_name, "role": u.role, "reg_no": u.reg_no}


def user_out(u: User) -> dict:
    room = u.room
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "phone": u.phone,
        "is_active": u.is_active,
        "reg_no": u.reg_no,
        "programme": u.programme,
        "year_of_study": u.year_of_study,
        "gender": u.gender,
        "staff_type": u.staff_type,
        "hostel_id": u.hostel_id if u.hostel_id else (room.block.hostel_id if room else None),
        "hostel_name": (u.hostel.name if u.hostel else (room.block.hostel.name if room else None)),
        "room": (
            {
                "id": room.id,
                "number": room.number,
                "floor": room.floor,
                "block": room.block.name,
                "block_id": room.block_id,
                "hostel": room.block.hostel.name,
                "room_type": room.room_type,
            }
            if room
            else None
        ),
        "pref_sleep": u.pref_sleep,
        "pref_study": u.pref_study,
        "pref_food": u.pref_food,
        "looking_for_roommate": u.looking_for_roommate,
        "created_at": iso(u.created_at),
    }


def staff_for(db: Session, staff_type: str) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role == "STAFF", User.staff_type == staff_type, User.is_active.is_(True))
        )
    )


def wardens(db: Session, chief_only: bool = False) -> list[User]:
    roles = ("CHIEF_WARDEN",) if chief_only else ("WARDEN", "CHIEF_WARDEN")
    return list(db.scalars(select(User).where(User.role.in_(roles), User.is_active.is_(True))))


def run_escalation(db: Session, now: datetime | None = None) -> list[Complaint]:
    """FR12: escalate complaints still unresolved after the SLA for their priority."""
    now = now or datetime.now(UTC)
    chief = next(iter(wardens(db, chief_only=True)), None)
    escalated: list[Complaint] = []
    open_items = db.scalars(select(Complaint).where(Complaint.status.in_(("OPEN", "IN_PROGRESS"))))
    for c in open_items:
        limit = timedelta(hours=ESCALATION_SLA_HOURS.get(c.priority, 48))
        if now - aware(c.created_at) >= limit:
            prev = c.status
            c.status = "ESCALATED"
            c.escalated_at = now
            c.escalated_to_id = chief.id if chief else None
            db.add(
                ComplaintUpdate(
                    complaint=c,
                    actor_id=None,
                    from_status=prev,
                    to_status="ESCALATED",
                    note=f"Auto-escalated: unresolved for more than {int(limit.total_seconds() // 3600)} h",
                )
            )
            audit(db, None, "COMPLAINT_ESCALATED", "complaint", c.id, f"{c.code} after SLA {limit}")
            if chief:
                notify(db, chief.id, f"Escalated complaint {c.code}", c.title, f"/complaints/{c.id}", "ALERT")
            notify(db, c.student_id, f"Your complaint {c.code} was escalated", "Forwarded to the chief warden.",
                   f"/complaints/{c.id}")
            escalated.append(c)
    db.commit()
    return escalated
