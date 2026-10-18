"""FR13-FR14 visitor registration and warden approval (SD4)."""
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, VisitorRequest
from ..security import get_current_user, require_roles
from ..services import audit, iso, lock_for_user, not_found, notify, notify_many, parse_date, today, user_brief, wardens

router = APIRouter(prefix="/api/visitors", tags=["visitors"])
MAX_DAYS_AHEAD = 30


class VisitorIn(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=100)
    relation: Literal["PARENT", "GUARDIAN", "SIBLING", "RELATIVE", "FRIEND", "OTHER"]
    visitor_phone: str
    visit_date: str
    time_from: str
    time_to: str
    purpose: str = Field(default="", max_length=300)

    @field_validator("visitor_name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z .'-]{2,100}", v):
            raise ValueError("Visitor name may contain only letters and spaces")
        return v

    @field_validator("visitor_phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        if not re.fullmatch(r"[6-9]\d{9}", v.strip()):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number")
        return v.strip()

    @field_validator("time_from", "time_to")
    @classmethod
    def time_ok(cls, v: str) -> str:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("Time must be HH:MM (24-hour)")
        return v

    @model_validator(mode="after")
    def window_ok(self):
        if self.time_from >= self.time_to:
            raise ValueError("Visit end time must be after the start time")
        if self.time_from < "08:00" or self.time_to > "20:00":
            raise ValueError("Visiting hours are 08:00 to 20:00")
        return self


class DecisionIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    remark: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def remark_needed(self):
        if self.decision == "REJECTED" and len(self.remark.strip()) < 3:
            raise ValueError("Please give a reason when rejecting a visitor request")
        return self


def visitor_out(v: VisitorRequest) -> dict:
    s = v.student
    return {
        "id": v.id, "visitor_name": v.visitor_name, "relation": v.relation, "visitor_phone": v.visitor_phone,
        "visit_date": v.visit_date, "time_from": v.time_from, "time_to": v.time_to, "purpose": v.purpose,
        "status": v.status, "decision_remark": v.decision_remark, "decided_by": user_brief(v.decided_by),
        "decided_at": iso(v.decided_at), "created_at": iso(v.created_at),
        "student": {**user_brief(s), "room": f"{s.room.block.name}-{s.room.number}" if s.room else None},
    }


@router.post("", status_code=201)
def create_visitor(body: VisitorIn, user: User = Depends(require_roles("STUDENT")), db: Session = Depends(get_db)):
    d = parse_date(body.visit_date, "Visit date")
    if d < today():
        raise HTTPException(422, "Visit date cannot be in the past")
    if d > today() + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(422, f"Visits can be requested at most {MAX_DAYS_AHEAD} days in advance")
    lock_for_user(db, user.id, "visitor")
    dup = db.scalar(select(VisitorRequest).where(
        VisitorRequest.student_id == user.id, VisitorRequest.visit_date == body.visit_date,
        VisitorRequest.visitor_phone == body.visitor_phone, VisitorRequest.status.in_(("PENDING", "APPROVED"))))
    if dup:
        raise HTTPException(409, "A request for this visitor on this date already exists")
    v = VisitorRequest(student_id=user.id, **body.model_dump())
    db.add(v)
    db.flush()
    audit(db, user, "VISITOR_REQUESTED", "visitor", v.id, f"{body.visitor_name} on {body.visit_date}")
    notify_many(db, wardens(db), "New visitor request", f"{user.full_name}: {body.visitor_name} on {body.visit_date}",
                "/visitors", "TASK")
    db.commit()
    db.refresh(v)
    return visitor_out(v)


@router.get("")
def list_visitors(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(VisitorRequest).order_by(VisitorRequest.created_at.desc())
    if user.role == "STUDENT":
        stmt = stmt.where(VisitorRequest.student_id == user.id)
    elif user.role == "STAFF" and user.staff_type != "SECURITY":
        raise HTTPException(403, "You do not have permission for this action")
    if status:
        stmt = stmt.where(VisitorRequest.status == status)
    return [visitor_out(v) for v in db.scalars(stmt.limit(200))]


@router.patch("/{visitor_id}/decision")
def decide(visitor_id: int, body: DecisionIn, user: User = Depends(require_roles("WARDEN", "CHIEF_WARDEN")),
           db: Session = Depends(get_db)):
    v = db.get(VisitorRequest, visitor_id)
    if not v:
        raise not_found("Visitor request")
    if v.status != "PENDING":
        raise HTTPException(409, f"This request was already {v.status.lower()}")
    v.status = body.decision
    v.decision_remark = body.remark.strip()
    v.decided_by_id = user.id
    v.decided_at = datetime.now(UTC)
    audit(db, user, f"VISITOR_{body.decision}", "visitor", v.id, body.remark)
    notify(db, v.student_id, f"Visitor request {body.decision.lower()}",
           f"{v.visitor_name} on {v.visit_date}" + (f" – {body.remark}" if body.remark else ""), "/visitors",
           "SUCCESS" if body.decision == "APPROVED" else "WARNING")
    db.commit()
    db.refresh(v)
    return visitor_out(v)


@router.patch("/{visitor_id}/cancel")
def cancel(visitor_id: int, user: User = Depends(require_roles("STUDENT")), db: Session = Depends(get_db)):
    v = db.get(VisitorRequest, visitor_id)
    if not v or v.student_id != user.id:
        raise not_found("Visitor request")
    if v.status != "PENDING":
        raise HTTPException(409, "Only pending requests can be cancelled")
    v.status = "CANCELLED"
    audit(db, user, "VISITOR_CANCELLED", "visitor", v.id)
    db.commit()
    db.refresh(v)
    return visitor_out(v)
