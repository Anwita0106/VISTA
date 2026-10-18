"""FR10-FR12, FR23 complaint registration, forwarding, tracking and escalation."""
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Complaint, ComplaintUpdate, User
from ..security import get_current_user, require_roles
from ..services import (
    audit,
    iso,
    lock_for_user,
    not_found,
    notify,
    run_escalation,
    staff_for,
    user_brief,
)

router = APIRouter(prefix="/api/complaints", tags=["complaints"])

# Which staff team a complaint is forwarded to (FR11)
ROUTING = {
    "ELECTRICAL": "MAINTENANCE", "PLUMBING": "MAINTENANCE", "CARPENTRY": "MAINTENANCE",
    "WATER": "MAINTENANCE", "WASHROOM": "CLEANING", "OTHER": "MAINTENANCE",
}
# Allowed status transitions (state transition diagram)
TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "RESOLVED"},
    "IN_PROGRESS": {"RESOLVED"},
    "ESCALATED": {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED": {"CLOSED", "OPEN"},
    "CLOSED": set(),
}


class ComplaintIn(BaseModel):
    category: Literal["ELECTRICAL", "PLUMBING", "CARPENTRY", "WASHROOM", "WATER", "OTHER"]
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    location: str = Field(default="", max_length=120)
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

    @field_validator("title", "description")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class StatusIn(BaseModel):
    status: Literal["IN_PROGRESS", "RESOLVED", "CLOSED", "OPEN"]
    note: str = Field(default="", max_length=500)


class AssignIn(BaseModel):
    staff_id: int


def complaint_out(c: Complaint, detail: bool = False) -> dict:
    d = {
        "id": c.id, "code": c.code, "category": c.category, "priority": c.priority, "title": c.title,
        "description": c.description, "location": c.location, "status": c.status,
        "student": user_brief(c.student), "assigned_staff": user_brief(c.assigned_staff),
        "escalated_to": user_brief(c.escalated_to), "escalated_at": iso(c.escalated_at),
        "resolved_at": iso(c.resolved_at), "created_at": iso(c.created_at), "updated_at": iso(c.updated_at),
    }
    if detail:
        d["updates"] = [
            {"id": u.id, "from_status": u.from_status, "to_status": u.to_status, "note": u.note,
             "actor": user_brief(u.actor) if u.actor else {"full_name": "System"}, "created_at": iso(u.created_at)}
            for u in c.updates
        ]
    return d


def can_view(user: User, c: Complaint) -> bool:
    if user.role in ("ADMIN", "WARDEN", "CHIEF_WARDEN"):
        return True
    if user.role == "STUDENT":
        return c.student_id == user.id
    if user.role == "STAFF":
        return c.assigned_staff_id == user.id
    return False


@router.post("", status_code=201)
def create_complaint(body: ComplaintIn, user: User = Depends(require_roles("STUDENT")), db: Session = Depends(get_db)):
    lock_for_user(db, user.id, "complaint")
    # duplicate submission guard: same open complaint within 10 minutes
    recent = datetime.now(UTC) - timedelta(minutes=10)
    dup = db.scalar(select(Complaint).where(
        Complaint.student_id == user.id, Complaint.category == body.category,
        func.lower(Complaint.title) == body.title.lower(), Complaint.created_at > recent,
        Complaint.status.in_(("OPEN", "IN_PROGRESS")),
    ))
    if dup:
        raise HTTPException(409, f"A similar complaint ({dup.code}) was already submitted a few minutes ago")
    # FR23: washroom and water complaints always receive HIGH priority
    priority = "HIGH" if body.category in ("WASHROOM", "WATER") else body.priority
    location = body.location or (f"{user.room.block.name}-{user.room.number}" if user.room else "")
    c = Complaint(code="TMP", student_id=user.id, category=body.category, priority=priority,
                  title=body.title, description=body.description, location=location, status="OPEN")
    db.add(c)
    db.flush()
    c.code = f"CMP-{c.id:05d}"
    # FR11: forward to the least-loaded staff member of the right team
    team = staff_for(db, ROUTING[body.category])
    if team:
        loads = {s.id: db.scalar(select(func.count()).select_from(Complaint).where(
            Complaint.assigned_staff_id == s.id, Complaint.status.in_(("OPEN", "IN_PROGRESS", "ESCALATED"))))
            for s in team}
        staff = min(team, key=lambda s: (loads[s.id], s.id))
        c.assigned_staff_id = staff.id
        notify(db, staff.id, f"New complaint {c.code} assigned", c.title, f"/complaints/{c.id}", "TASK")
    db.add(ComplaintUpdate(complaint=c, actor_id=user.id, from_status=None, to_status="OPEN",
                           note="Complaint registered" + (f" and forwarded to {team and staff.full_name}" if team else "")))
    audit(db, user, "COMPLAINT_CREATED", "complaint", c.id, f"{c.code} {c.category} {priority}")
    notify(db, user.id, f"Complaint {c.code} registered", f"Priority {priority}. We will keep you updated.",
           f"/complaints/{c.id}")
    db.commit()
    db.refresh(c)
    return complaint_out(c, detail=True)


@router.get("")
def list_complaints(
    status: str | None = None, category: str | None = None, priority: str | None = None,
    q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    sort: Literal["newest", "oldest", "priority"] = "newest",
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = select(Complaint)
    if user.role == "STUDENT":
        stmt = stmt.where(Complaint.student_id == user.id)
    elif user.role == "STAFF":
        stmt = stmt.where(Complaint.assigned_staff_id == user.id)
    if status:
        stmt = stmt.where(Complaint.status == status)
    if category:
        stmt = stmt.where(Complaint.category == category)
    if priority:
        stmt = stmt.where(Complaint.priority == priority)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Complaint.title).like(like), func.lower(Complaint.code).like(like),
                              func.lower(Complaint.description).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    if sort == "oldest":
        stmt = stmt.order_by(Complaint.created_at.asc())
    elif sort == "priority":
        from sqlalchemy import case
        stmt = stmt.order_by(case({"HIGH": 0, "MEDIUM": 1, "LOW": 2}, value=Complaint.priority), Complaint.created_at.desc())
    else:
        stmt = stmt.order_by(Complaint.created_at.desc())
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [complaint_out(c) for c in items], "total": total, "page": page, "page_size": page_size}


@router.get("/{complaint_id}")
def get_complaint(complaint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if not c or not can_view(user, c):
        raise not_found("Complaint")
    return complaint_out(c, detail=True)


@router.patch("/{complaint_id}/status")
def update_status(complaint_id: int, body: StatusIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if not c or not can_view(user, c):
        raise not_found("Complaint")
    # students may only close or reopen their own resolved complaint
    if user.role == "STUDENT" and body.status not in ("CLOSED", "OPEN"):
        raise HTTPException(403, "Students can only close or reopen a resolved complaint")
    if user.role == "STAFF" and body.status in ("CLOSED", "OPEN"):
        raise HTTPException(403, "Only the student or a warden can close or reopen a complaint")
    if body.status not in TRANSITIONS.get(c.status, set()):
        raise HTTPException(409, f"Invalid status change from {c.status} to {body.status}")
    prev = c.status
    c.status = body.status
    if body.status == "RESOLVED":
        c.resolved_at = datetime.now(UTC)
    if body.status == "OPEN":
        c.resolved_at = None
        c.created_at = datetime.now(UTC)  # restart SLA clock on reopen
    db.add(ComplaintUpdate(complaint=c, actor_id=user.id, from_status=prev, to_status=body.status, note=body.note))
    audit(db, user, "COMPLAINT_STATUS", "complaint", c.id, f"{c.code}: {prev} -> {body.status}")
    if user.id != c.student_id:
        notify(db, c.student_id, f"Complaint {c.code} is now {body.status.replace('_', ' ').lower()}",
               body.note, f"/complaints/{c.id}")
    db.commit()
    db.refresh(c)
    return complaint_out(c, detail=True)


@router.patch("/{complaint_id}/assign")
def assign(complaint_id: int, body: AssignIn, user: User = Depends(require_roles("WARDEN", "CHIEF_WARDEN", "ADMIN")),
           db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if not c:
        raise not_found("Complaint")
    staff = db.get(User, body.staff_id)
    if not staff or staff.role != "STAFF":
        raise not_found("Staff member")
    c.assigned_staff_id = staff.id
    db.add(ComplaintUpdate(complaint=c, actor_id=user.id, from_status=c.status, to_status=c.status,
                           note=f"Reassigned to {staff.full_name}"))
    notify(db, staff.id, f"Complaint {c.code} assigned to you", c.title, f"/complaints/{c.id}", "TASK")
    audit(db, user, "COMPLAINT_ASSIGNED", "complaint", c.id, f"to staff {staff.id}")
    db.commit()
    db.refresh(c)
    return complaint_out(c, detail=True)


@router.post("/escalation/run")
def trigger_escalation(user: User = Depends(require_roles("WARDEN", "CHIEF_WARDEN", "ADMIN")),
                       db: Session = Depends(get_db)):
    escalated = run_escalation(db)
    audit(db, user, "ESCALATION_RUN", "complaint", "", f"{len(escalated)} escalated")
    db.commit()
    return {"escalated": [c.code for c in escalated]}
