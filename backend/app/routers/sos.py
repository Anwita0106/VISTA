"""FR22 Emergency SOS (SD3). DEMO ONLY – not connected to real emergency services."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SOSAlert, User
from ..security import get_current_user, require_roles
from ..services import audit, aware, iso, lock_for_user, not_found, notify, notify_many, staff_for, user_brief, wardens

router = APIRouter(prefix="/api/sos", tags=["sos"])
RESPONDERS = require_roles("WARDEN", "CHIEF_WARDEN", "STAFF", "ADMIN")


class SOSIn(BaseModel):
    message: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=150)
    confirm: bool


class ResolveIn(BaseModel):
    note: str = Field(default="", max_length=300)


def sos_out(a: SOSAlert) -> dict:
    s = a.student
    delivery_ms = None
    if a.notified_at:
        delivery_ms = round((aware(a.notified_at) - aware(a.created_at)).total_seconds() * 1000, 1)
    return {
        "id": a.id, "message": a.message, "location": a.location, "status": a.status,
        "student": {**user_brief(s), "phone": s.phone,
                    "room": f"{s.room.block.hostel.name} {s.room.block.name}-{s.room.number}" if s.room else None},
        "created_at": iso(a.created_at), "notified_at": iso(a.notified_at), "notification_delay_ms": delivery_ms,
        "acknowledged_by": user_brief(a.acknowledged_by), "acknowledged_at": iso(a.acknowledged_at),
        "resolved_by": user_brief(a.resolved_by), "resolved_at": iso(a.resolved_at),
        "resolution_note": a.resolution_note,
    }


def is_responder(user: User) -> bool:
    return user.role in ("WARDEN", "CHIEF_WARDEN", "ADMIN") or (user.role == "STAFF" and user.staff_type == "SECURITY")


@router.post("", status_code=201)
def raise_sos(body: SOSIn, user: User = Depends(require_roles("STUDENT")), db: Session = Depends(get_db)):
    if not body.confirm:
        raise HTTPException(400, "SOS must be confirmed before it is sent")
    lock_for_user(db, user.id, "sos")
    # duplicate guard: an active alert raised in the last 2 minutes is returned instead of a new one
    recent = datetime.now(UTC) - timedelta(minutes=2)
    existing = db.scalar(select(SOSAlert).where(SOSAlert.student_id == user.id, SOSAlert.status == "RAISED",
                                                SOSAlert.created_at > recent))
    if existing:
        return sos_out(existing)
    location = body.location or (f"{user.room.block.hostel.name} {user.room.block.name}-{user.room.number}"
                                 if user.room else "Location not provided")
    a = SOSAlert(student_id=user.id, message=body.message, location=location, status="RAISED")
    db.add(a)
    db.flush()
    # par: warden(s) and security notified together, in the same transaction
    recipients = wardens(db) + staff_for(db, "SECURITY")
    notify_many(db, recipients, f"SOS ALERT – {user.full_name}", f"{location}. {body.message}".strip(),
                "/sos", "SOS")
    a.notified_at = datetime.now(UTC)
    audit(db, user, "SOS_RAISED", "sos", a.id, location)
    db.commit()
    db.refresh(a)
    return sos_out(a)


@router.get("")
def list_alerts(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(SOSAlert).order_by(SOSAlert.created_at.desc())
    if user.role == "STUDENT":
        stmt = stmt.where(SOSAlert.student_id == user.id)
    elif not is_responder(user):
        raise HTTPException(403, "You do not have permission for this action")
    if status:
        stmt = stmt.where(SOSAlert.status == status)
    return [sos_out(a) for a in db.scalars(stmt.limit(100))]


@router.patch("/{alert_id}/acknowledge")
def acknowledge(alert_id: int, user: User = Depends(RESPONDERS), db: Session = Depends(get_db)):
    if not is_responder(user):
        raise HTTPException(403, "You do not have permission for this action")
    a = db.get(SOSAlert, alert_id)
    if not a:
        raise not_found("SOS alert")
    if a.status != "RAISED":
        raise HTTPException(409, f"Alert is already {a.status.lower()}")
    a.status = "ACKNOWLEDGED"
    a.acknowledged_by_id = user.id
    a.acknowledged_at = datetime.now(UTC)
    audit(db, user, "SOS_ACKNOWLEDGED", "sos", a.id)
    notify(db, a.student_id, "Help is on the way", f"{user.full_name} acknowledged your SOS alert.", "/sos", "SUCCESS")
    db.commit()
    db.refresh(a)
    return sos_out(a)


@router.patch("/{alert_id}/resolve")
def resolve(alert_id: int, body: ResolveIn, user: User = Depends(RESPONDERS), db: Session = Depends(get_db)):
    if not is_responder(user):
        raise HTTPException(403, "You do not have permission for this action")
    a = db.get(SOSAlert, alert_id)
    if not a:
        raise not_found("SOS alert")
    if a.status == "RESOLVED":
        raise HTTPException(409, "Alert is already resolved")
    if a.status == "RAISED":
        raise HTTPException(409, "Acknowledge the alert before resolving it")
    a.status = "RESOLVED"
    a.resolved_by_id = user.id
    a.resolved_at = datetime.now(UTC)
    a.resolution_note = body.note
    audit(db, user, "SOS_RESOLVED", "sos", a.id, body.note)
    notify(db, a.student_id, "SOS alert resolved", body.note, "/sos")
    db.commit()
    db.refresh(a)
    return sos_out(a)
