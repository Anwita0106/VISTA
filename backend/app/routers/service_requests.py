"""FR15 sick-meal and FR16 room-cleaning requests."""
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ServiceRequest, User
from ..security import get_current_user, require_roles
from ..services import audit, iso, lock_for_user, not_found, notify, notify_many, parse_date, staff_for, today, user_brief

router = APIRouter(prefix="/api/service-requests", tags=["service requests"])

TEAM = {"SICK_MEAL": "MESS", "CLEANING": "CLEANING"}
TRANSITIONS = {"PENDING": {"ACCEPTED", "CANCELLED"}, "ACCEPTED": {"COMPLETED"}, "COMPLETED": set(), "CANCELLED": set()}


class ServiceIn(BaseModel):
    kind: Literal["SICK_MEAL", "CLEANING"]
    preferred_date: str
    preferred_slot: Literal["", "MORNING", "AFTERNOON", "EVENING"] = ""
    meal_type: Literal["", "BREAKFAST", "LUNCH", "DINNER"] = ""
    diet_notes: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def kind_fields(self):
        if self.kind == "SICK_MEAL" and not self.meal_type:
            raise ValueError("Please choose which meal you need")
        if self.kind == "CLEANING" and not self.preferred_slot:
            raise ValueError("Please choose a preferred cleaning slot")
        return self


class StatusIn(BaseModel):
    status: Literal["ACCEPTED", "COMPLETED", "CANCELLED"]


def sr_out(r: ServiceRequest) -> dict:
    s = r.student
    return {
        "id": r.id, "kind": r.kind, "preferred_date": r.preferred_date, "preferred_slot": r.preferred_slot,
        "meal_type": r.meal_type, "diet_notes": r.diet_notes, "notes": r.notes, "status": r.status,
        "assigned_staff": user_brief(r.assigned_staff), "created_at": iso(r.created_at), "updated_at": iso(r.updated_at),
        "student": {**user_brief(s), "room": f"{s.room.block.hostel.name} {s.room.block.name}-{s.room.number}" if s.room else None},
    }


@router.post("", status_code=201)
def create(body: ServiceIn, user: User = Depends(require_roles("STUDENT")), db: Session = Depends(get_db)):
    d = parse_date(body.preferred_date, "Preferred date")
    if d < today() or d > today() + timedelta(days=7):
        raise HTTPException(422, "Preferred date must be between today and 7 days from now")
    if user.room_id is None:
        raise HTTPException(400, "You need an allocated room before requesting room services")
    lock_for_user(db, user.id, "service")
    dup = db.scalar(select(ServiceRequest).where(
        ServiceRequest.student_id == user.id, ServiceRequest.kind == body.kind,
        ServiceRequest.preferred_date == body.preferred_date, ServiceRequest.status.in_(("PENDING", "ACCEPTED")),
        ServiceRequest.meal_type == body.meal_type))
    if dup:
        raise HTTPException(409, "You already have an active request of this type for that date")
    r = ServiceRequest(student_id=user.id, **body.model_dump())
    db.add(r)
    db.flush()
    label = "Sick-meal" if body.kind == "SICK_MEAL" else "Room-cleaning"
    audit(db, user, f"{body.kind}_REQUESTED", "service_request", r.id, body.preferred_date)
    notify_many(db, staff_for(db, TEAM[body.kind]), f"New {label.lower()} request",
                f"{user.full_name} for {body.preferred_date}", "/services", "TASK")
    db.commit()
    db.refresh(r)
    return sr_out(r)


@router.get("")
def list_requests(kind: str | None = None, status: str | None = None, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    stmt = select(ServiceRequest).order_by(ServiceRequest.created_at.desc())
    if user.role == "STUDENT":
        stmt = stmt.where(ServiceRequest.student_id == user.id)
    elif user.role == "STAFF":
        kinds = [k for k, t in TEAM.items() if t == user.staff_type]
        if not kinds:
            raise HTTPException(403, "You do not have permission for this action")
        stmt = stmt.where(ServiceRequest.kind.in_(kinds))
    if kind:
        stmt = stmt.where(ServiceRequest.kind == kind)
    if status:
        stmt = stmt.where(ServiceRequest.status == status)
    return [sr_out(r) for r in db.scalars(stmt.limit(200))]


@router.patch("/{request_id}/status")
def update_status(request_id: int, body: StatusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(ServiceRequest, request_id)
    if not r:
        raise not_found("Request")
    if user.role == "STUDENT":
        if r.student_id != user.id:
            raise not_found("Request")
        if body.status != "CANCELLED":
            raise HTTPException(403, "Students can only cancel their own request")
    elif user.role == "STAFF":
        if TEAM[r.kind] != user.staff_type:
            raise HTTPException(403, "You do not have permission for this action")
    elif user.role not in ("WARDEN", "CHIEF_WARDEN", "ADMIN"):
        raise HTTPException(403, "You do not have permission for this action")
    if body.status not in TRANSITIONS[r.status]:
        raise HTTPException(409, f"Invalid status change from {r.status} to {body.status}")
    r.status = body.status
    if body.status == "ACCEPTED" and user.role == "STAFF":
        r.assigned_staff_id = user.id
    audit(db, user, "SERVICE_STATUS", "service_request", r.id, body.status)
    if user.id != r.student_id:
        label = "Sick-meal" if r.kind == "SICK_MEAL" else "Room-cleaning"
        notify(db, r.student_id, f"{label} request {body.status.lower()}", f"For {r.preferred_date}", "/services")
    db.commit()
    db.refresh(r)
    return sr_out(r)
