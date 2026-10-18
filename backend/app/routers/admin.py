"""FR02-FR03 staff/admin registration, FR19 admin dashboard, FR35 reports, audit log, role dashboards."""
import csv
import io
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AuditLog,
    Block,
    Complaint,
    DeliveryRequest,
    GateDelivery,
    Hostel,
    MessFeedback,
    Notice,
    Notification,
    Room,
    ServiceRequest,
    SOSAlert,
    User,
    VisitorRequest,
)
from ..security import get_current_user, hash_password, require_roles
from ..services import audit, iso, not_found, user_brief, user_out
from .auth import validate_password

router = APIRouter(prefix="/api", tags=["admin"])
ADMIN = require_roles("ADMIN")


class StaffIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(max_length=72)
    role: Literal["WARDEN", "CHIEF_WARDEN", "STAFF", "ADMIN"]
    staff_type: Literal["MAINTENANCE", "CLEANING", "MESS", "SECURITY"] | None = None
    phone: str = ""
    hostel_id: int | None = None
    _pw = field_validator("password")(validate_password)

    @model_validator(mode="after")
    def staff_type_needed(self):
        if self.role == "STAFF" and not self.staff_type:
            raise ValueError("Staff members need a staff type")
        if self.role != "STAFF":
            self.staff_type = None
        if self.phone and not re.fullmatch(r"[6-9]\d{9}", self.phone):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number")
        return self


class ActiveIn(BaseModel):
    is_active: bool


@router.get("/admin/users")
def list_users(role: str | None = None, q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), _: User = Depends(require_roles("ADMIN", "WARDEN", "CHIEF_WARDEN")),
               db: Session = Depends(get_db)):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like),
                              func.lower(func.coalesce(User.reg_no, "")).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    users = db.scalars(stmt.order_by(User.role, User.full_name).offset((page - 1) * page_size).limit(page_size))
    return {"items": [user_out(u) for u in users], "total": total, "page": page, "page_size": page_size}


@router.post("/admin/users", status_code=201)
def create_user(body: StaffIn, admin: User = Depends(ADMIN), db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    if body.hostel_id is not None and not db.get(Hostel, body.hostel_id):
        raise not_found("Hostel")
    u = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name, role=body.role,
             staff_type=body.staff_type, phone=body.phone, hostel_id=body.hostel_id)
    db.add(u)
    db.flush()
    audit(db, admin, "USER_CREATED", "user", u.id, f"{body.role} {email}")
    db.commit()
    db.refresh(u)
    return user_out(u)


@router.patch("/admin/users/{user_id}/active")
def set_active(user_id: int, body: ActiveIn, admin: User = Depends(ADMIN), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise not_found("User")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    u.is_active = body.is_active
    audit(db, admin, "USER_ACTIVATED" if body.is_active else "USER_DEACTIVATED", "user", u.id)
    db.commit()
    db.refresh(u)
    return user_out(u)


@router.get("/admin/audit-logs")
def audit_logs(action: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
               _: User = Depends(ADMIN), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action.upper()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": a.id, "action": a.action, "entity": a.entity, "entity_id": a.entity_id, "detail": a.detail,
         "user": user_brief(a.user) if a.user else {"full_name": "System"}, "created_at": iso(a.created_at)}
        for a in rows]}


def _counts(db: Session, model, col) -> dict:
    return {k: v for k, v in db.execute(select(col, func.count()).select_from(model).group_by(col))}


def build_report(db: Session) -> dict:
    rooms = db.scalars(select(Room)).all()
    cap = sum(r.capacity for r in rooms)
    occ = db.scalar(select(func.count()).select_from(User).where(User.room_id.is_not(None)))
    hostels = []
    for h in db.scalars(select(Hostel).order_by(Hostel.name)):
        hr = [r for b in h.blocks for r in b.rooms]
        hc = sum(r.capacity for r in hr)
        ho = sum(len(r.occupants) for r in hr)
        hostels.append({"name": h.name, "capacity": hc, "occupied": ho,
                        "occupancy_pct": round(100 * ho / hc, 1) if hc else 0.0})
    resolved = db.scalars(select(Complaint).where(Complaint.resolved_at.is_not(None))).all()
    avg_hours = (sum(((c.resolved_at.replace(tzinfo=UTC) if c.resolved_at.tzinfo is None else c.resolved_at) -
                      (c.created_at.replace(tzinfo=UTC) if c.created_at.tzinfo is None else c.created_at)).total_seconds()
                     for c in resolved) / 3600 / len(resolved)) if resolved else None
    fb = db.execute(select(func.avg(MessFeedback.food_rating), func.avg(MessFeedback.service_rating), func.count())).one()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "occupancy": {"capacity": cap, "occupied": occ, "occupancy_pct": round(100 * occ / cap, 1) if cap else 0.0,
                      "hostels": hostels},
        "complaints": {"by_status": _counts(db, Complaint, Complaint.status),
                       "by_category": _counts(db, Complaint, Complaint.category),
                       "by_priority": _counts(db, Complaint, Complaint.priority),
                       "avg_resolution_hours": round(avg_hours, 1) if avg_hours is not None else None},
        "visitors": _counts(db, VisitorRequest, VisitorRequest.status),
        "service_requests": _counts(db, ServiceRequest, ServiceRequest.status),
        "sos": _counts(db, SOSAlert, SOSAlert.status),
        "deliveries": {"by_status": _counts(db, DeliveryRequest, DeliveryRequest.status),
                       "demo_fees_collected": db.scalar(select(func.coalesce(func.sum(DeliveryRequest.fee), 0))
                                                        .where(DeliveryRequest.status == "DELIVERED"))},
        "gate_deliveries": _counts(db, GateDelivery, GateDelivery.status),
        "mess_feedback": {"avg_food": round(float(fb[0]), 2) if fb[0] is not None else None,
                          "avg_service": round(float(fb[1]), 2) if fb[1] is not None else None, "count": fb[2]},
        "users": _counts(db, User, User.role),
    }


@router.get("/admin/reports")
def reports(_: User = Depends(require_roles("ADMIN", "CHIEF_WARDEN")), db: Session = Depends(get_db)):
    return build_report(db)


@router.get("/admin/reports/export")
def export_report(kind: Literal["complaints", "deliveries", "visitors", "occupancy"] = "complaints",
                  admin: User = Depends(ADMIN), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "complaints":
        w.writerow(["Code", "Category", "Priority", "Status", "Title", "Student", "Assigned staff", "Created", "Resolved"])
        for c in db.scalars(select(Complaint).order_by(Complaint.id)):
            w.writerow([c.code, c.category, c.priority, c.status, c.title, c.student.full_name,
                        c.assigned_staff.full_name if c.assigned_staff else "", iso(c.created_at), iso(c.resolved_at) or ""])
    elif kind == "deliveries":
        w.writerow(["Code", "Status", "Item", "Sender", "Receiver", "Carrier", "From", "To", "Fee (demo)", "Created"])
        for d in db.scalars(select(DeliveryRequest).order_by(DeliveryRequest.id)):
            w.writerow([d.code, d.status, d.item_description, d.sender.full_name, d.receiver.full_name,
                        d.carrier.full_name if d.carrier else "", d.pickup_hostel.name, d.drop_hostel.name, d.fee,
                        iso(d.created_at)])
    elif kind == "visitors":
        w.writerow(["ID", "Student", "Visitor", "Relation", "Date", "From", "To", "Status", "Decided by"])
        for v in db.scalars(select(VisitorRequest).order_by(VisitorRequest.id)):
            w.writerow([v.id, v.student.full_name, v.visitor_name, v.relation, v.visit_date, v.time_from, v.time_to,
                        v.status, v.decided_by.full_name if v.decided_by else ""])
    else:
        w.writerow(["Hostel", "Block", "Room", "Type", "Capacity", "Occupied"])
        for r in db.scalars(select(Room).join(Block).order_by(Block.hostel_id, Block.name, Room.number)):
            w.writerow([r.block.hostel.name, r.block.name, r.number, r.room_type, r.capacity, len(r.occupants)])
    audit(db, admin, "REPORT_EXPORTED", "report", kind)
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="vista_{kind}_report.csv"'})


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Role-specific summary cards, computed from stored data."""
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.is_read.is_(False)))
    notices = [{"id": n.id, "title": n.title, "category": n.category, "created_at": iso(n.created_at)}
               for n in db.scalars(select(Notice).order_by(Notice.created_at.desc()).limit(5))]
    out: dict = {"role": user.role, "unread_notifications": unread, "recent_notices": notices}
    if user.role == "STUDENT":
        def cnt(model, *conds):
            return db.scalar(select(func.count()).select_from(model).where(*conds))
        out["cards"] = {
            "open_complaints": cnt(Complaint, Complaint.student_id == user.id,
                                   Complaint.status.in_(("OPEN", "IN_PROGRESS", "ESCALATED"))),
            "pending_visitors": cnt(VisitorRequest, VisitorRequest.student_id == user.id, VisitorRequest.status == "PENDING"),
            "active_services": cnt(ServiceRequest, ServiceRequest.student_id == user.id,
                                   ServiceRequest.status.in_(("PENDING", "ACCEPTED"))),
            "active_deliveries": cnt(DeliveryRequest, or_(DeliveryRequest.sender_id == user.id,
                                                          DeliveryRequest.receiver_id == user.id,
                                                          DeliveryRequest.carrier_id == user.id),
                                     DeliveryRequest.status.in_(("OPEN", "ACCEPTED", "PICKED_UP"))),
        }
    else:
        week = datetime.now(UTC) - timedelta(days=7)
        out["cards"] = {
            "open_complaints": db.scalar(select(func.count()).select_from(Complaint).where(
                Complaint.status.in_(("OPEN", "IN_PROGRESS")),
                *( [Complaint.assigned_staff_id == user.id] if user.role == "STAFF" else []))),
            "escalated_complaints": db.scalar(select(func.count()).select_from(Complaint).where(Complaint.status == "ESCALATED")),
            "pending_visitors": db.scalar(select(func.count()).select_from(VisitorRequest).where(VisitorRequest.status == "PENDING")),
            "active_sos": db.scalar(select(func.count()).select_from(SOSAlert).where(SOSAlert.status != "RESOLVED")),
            "pending_services": db.scalar(select(func.count()).select_from(ServiceRequest).where(ServiceRequest.status == "PENDING")),
            "deliveries_this_week": db.scalar(select(func.count()).select_from(DeliveryRequest).where(DeliveryRequest.created_at > week)),
            "students": db.scalar(select(func.count()).select_from(User).where(User.role == "STUDENT")),
            "gate_waiting": db.scalar(select(func.count()).select_from(GateDelivery).where(GateDelivery.status.in_(("BOOKED", "AT_GATE")))),
        }
        out["complaints_by_category"] = _counts(db, Complaint, Complaint.category)
    return out
