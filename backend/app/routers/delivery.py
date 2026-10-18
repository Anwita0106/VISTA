"""FR27-FR31: P2P inter-hostel delivery (SD5-SD7), gate food booking and parcel reservation.

Payments are DEMO records only – no real money is collected (see README)."""
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import DELIVERY_FEE_INR, settings
from ..database import get_db
from ..models import DeliveryRequest, GateDelivery, HandoverVerification, Hostel, Payment, User
from ..security import generate_otp, get_current_user, hash_secret, require_roles, verify_password
from ..services import audit, aware, iso, lock_for_user, not_found, notify, notify_many, parse_date, staff_for, today, user_brief
from .community import file_out, save_upload

router = APIRouter(prefix="/api", tags=["delivery"])
STUDENT = require_roles("STUDENT")
MAX_OTP_GENERATIONS = 3

# allowed transitions of the P2P delivery state machine
TRANSITIONS = {
    "OPEN": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"PICKED_UP", "OPEN"},
    "PICKED_UP": {"DELIVERED", "FAILED"},
    "DELIVERED": set(), "CANCELLED": set(), "FAILED": set(),
}


def move(d: DeliveryRequest, to: str) -> None:
    if to not in TRANSITIONS[d.status]:
        raise HTTPException(409, f"Invalid delivery state change from {d.status} to {to}")
    d.status = to


class DeliveryIn(BaseModel):
    receiver_reg_no: str
    item_description: str = Field(min_length=3, max_length=200)
    item_type: Literal["PARCEL", "FOOD", "DOCUMENT", "OTHER"] = "PARCEL"
    pickup_point: str = Field(default="", max_length=120)
    confirm_payment: bool

    @field_validator("receiver_reg_no")
    @classmethod
    def reg(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"\d{2}[A-Z]{3}\d{4}", v):
            raise ValueError("Receiver registration number must look like 24BYB0193")
        return v


class OtpIn(BaseModel):
    otp: str = Field(pattern=r"^\d{6}$")


class FailIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


def hostel_of(u: User) -> Hostel | None:
    return u.room.block.hostel if u.room else None


def active_otp(d: DeliveryRequest) -> HandoverVerification | None:
    return next((v for v in reversed(d.verifications) if v.method == "OTP" and v.status == "PENDING"), None)


def expire_if_needed(v: HandoverVerification | None) -> None:
    if v and v.status == "PENDING" and v.expires_at and aware(v.expires_at) < datetime.now(UTC):
        v.status = "EXPIRED"
        v.otp_plain_for_receiver = ""


def delivery_out(d: DeliveryRequest, viewer: User) -> dict:
    is_receiver = viewer.id == d.receiver_id
    v = active_otp(d)
    out = {
        "id": d.id, "code": d.code, "item_description": d.item_description, "item_type": d.item_type,
        "pickup_point": d.pickup_point, "fee": d.fee, "status": d.status,
        "pickup_hostel": d.pickup_hostel.name, "drop_hostel": d.drop_hostel.name,
        "sender": user_brief(d.sender), "carrier": user_brief(d.carrier),
        "receiver": {**user_brief(d.receiver),
                     "room": f"{d.receiver.room.block.name}-{d.receiver.room.number}" if d.receiver.room else None},
        "payment": ({"amount": d.payment.amount, "status": d.payment.status, "receipt_no": d.payment.receipt_no,
                     "method": d.payment.method}
                    if d.payment and (viewer.id == d.sender_id or viewer.role == "ADMIN") else None),
        "failure_reason": d.failure_reason,
        "created_at": iso(d.created_at), "accepted_at": iso(d.accepted_at), "picked_up_at": iso(d.picked_up_at),
        "delivered_at": iso(d.delivered_at),
        "my_role": ("SENDER" if viewer.id == d.sender_id else "RECEIVER" if is_receiver
                    else "CARRIER" if viewer.id == d.carrier_id else "VIEWER"),
        "otp_active": v is not None,
        "otp_expires_at": iso(v.expires_at) if v else None,
        "otp_attempts_left": (v.max_attempts - v.attempts) if v else None,
        "verifications": [
            {"id": x.id, "method": x.method, "status": x.status, "attempts": x.attempts,
             "created_at": iso(x.created_at), "verified_at": iso(x.verified_at),
             "receiver_name": x.receiver_name, "photo": file_out(db_file(x))} for x in d.verifications],
    }
    if is_receiver:  # only the receiver ever sees the OTP and QR secret
        out["otp"] = v.otp_plain_for_receiver if v else None
        out["qr_token"] = d.qr_token if d.status == "PICKED_UP" else None
    return out


def db_file(v: HandoverVerification):
    from sqlalchemy.orm import object_session

    from ..models import StoredFile
    s = object_session(v)
    return s.get(StoredFile, v.photo_file_id) if (s and v.photo_file_id) else None


def get_delivery(db: Session, delivery_id: int, user: User, lock: bool = False) -> DeliveryRequest:
    stmt = select(DeliveryRequest).where(DeliveryRequest.id == delivery_id)
    if lock and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    d = db.scalar(stmt)
    if not d:
        raise not_found("Delivery")
    return d


def issue_otp(db: Session, d: DeliveryRequest) -> None:
    count = sum(1 for v in d.verifications if v.method == "OTP")
    if count >= MAX_OTP_GENERATIONS:
        raise HTTPException(429, "OTP limit reached for this delivery. Report a handover failure instead.")
    otp = generate_otp()
    v = HandoverVerification(delivery=d, method="OTP", otp_hash=hash_secret(otp), otp_plain_for_receiver=otp,
                             expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_expiry_minutes),
                             max_attempts=settings.otp_max_attempts, status="PENDING")
    db.add(v)
    notify(db, d.receiver_id, f"Delivery {d.code}: your handover OTP",
           f"Share this OTP with the carrier only when you receive the item: {otp}. "
           f"Valid for {settings.otp_expiry_minutes} minutes.", f"/delivery/{d.id}", "OTP")


@router.post("/deliveries", status_code=201)
def create_delivery(body: DeliveryIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    if not body.confirm_payment:
        raise HTTPException(400, f"Please confirm the ₹{DELIVERY_FEE_INR} delivery fee")
    receiver = db.scalar(select(User).where(User.reg_no == body.receiver_reg_no, User.role == "STUDENT",
                                            User.is_active.is_(True)))
    if not receiver:
        raise HTTPException(404, "No active student found with that registration number")
    if receiver.id == user.id:
        raise HTTPException(400, "You cannot send a delivery to yourself")
    pickup, drop = hostel_of(user), hostel_of(receiver)
    if not pickup:
        raise HTTPException(400, "You need an allocated hostel room to send deliveries")
    if not drop:
        raise HTTPException(400, "The receiver does not have an allocated hostel room")
    if pickup.id == drop.id:
        raise HTTPException(400, "Inter-hostel delivery is only for a receiver in a different hostel")
    lock_for_user(db, user.id, "delivery")
    d = DeliveryRequest(code="TMP", sender_id=user.id, receiver_id=receiver.id, item_description=body.item_description,
                        item_type=body.item_type, pickup_hostel_id=pickup.id, drop_hostel_id=drop.id,
                        pickup_point=body.pickup_point or f"{user.room.block.name}-{user.room.number}",
                        fee=DELIVERY_FEE_INR, status="OPEN", qr_token=secrets.token_urlsafe(24))
    db.add(d)
    db.flush()
    d.code = f"DLV-{d.id:05d}"
    pay = Payment(delivery_id=d.id, amount=DELIVERY_FEE_INR, method="DEMO_WALLET", status="PAID_DEMO",
                  receipt_no=f"RCPT-DEMO-{d.id:06d}")
    db.add(pay)
    audit(db, user, "DELIVERY_CREATED", "delivery", d.id, f"{d.code} to {receiver.reg_no}; demo fee ₹{DELIVERY_FEE_INR}")
    notify(db, receiver.id, f"Incoming delivery {d.code}", f"{user.full_name} is sending you: {body.item_description}",
           f"/delivery/{d.id}")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.get("/deliveries")
def list_deliveries(view: Literal["mine", "available", "carrying", "all"] = "mine",
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(DeliveryRequest).order_by(DeliveryRequest.created_at.desc())
    if view == "all":
        if user.role not in ("ADMIN", "WARDEN", "CHIEF_WARDEN"):
            raise HTTPException(403, "You do not have permission for this action")
    elif user.role != "STUDENT":
        raise HTTPException(403, "Only students take part in P2P deliveries")
    elif view == "mine":
        stmt = stmt.where(or_(DeliveryRequest.sender_id == user.id, DeliveryRequest.receiver_id == user.id))
    elif view == "available":
        stmt = stmt.where(DeliveryRequest.status == "OPEN", DeliveryRequest.sender_id != user.id,
                          DeliveryRequest.receiver_id != user.id)
    else:
        stmt = stmt.where(DeliveryRequest.carrier_id == user.id)
    items = db.scalars(stmt.limit(200)).all()
    for d in items:
        expire_if_needed(active_otp(d))
    db.commit()
    return [delivery_out(d, user) for d in items]


@router.get("/deliveries/{delivery_id}")
def get_one(delivery_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user)
    participant = user.id in (d.sender_id, d.receiver_id, d.carrier_id)
    if not participant and user.role not in ("ADMIN", "WARDEN", "CHIEF_WARDEN") and not (
            user.role == "STUDENT" and d.status == "OPEN"):
        raise not_found("Delivery")
    expire_if_needed(active_otp(d))
    db.commit()
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/accept")
def accept(delivery_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if user.id in (d.sender_id, d.receiver_id):
        raise HTTPException(400, "The sender or receiver cannot be the carrier")
    if d.status != "OPEN":
        raise HTTPException(409, "This delivery has already been taken by another carrier" if d.status == "ACCEPTED"
                            else f"Invalid delivery state change from {d.status} to ACCEPTED")
    active = db.scalar(select(func.count()).select_from(DeliveryRequest).where(
        DeliveryRequest.carrier_id == user.id, DeliveryRequest.status.in_(("ACCEPTED", "PICKED_UP"))))
    if active >= 3:
        raise HTTPException(409, "You can carry at most 3 deliveries at a time")
    move(d, "ACCEPTED")
    d.carrier_id = user.id
    d.accepted_at = datetime.now(UTC)
    audit(db, user, "DELIVERY_ACCEPTED", "delivery", d.id, d.code)
    notify_many(db, [d.sender, d.receiver], f"Delivery {d.code} accepted", f"{user.full_name} will carry your item.",
                f"/delivery/{d.id}")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/pickup")
def pickup(delivery_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.carrier_id != user.id:
        raise HTTPException(403, "Only the assigned carrier can do this")
    move(d, "PICKED_UP")
    d.picked_up_at = datetime.now(UTC)
    issue_otp(db, d)
    audit(db, user, "DELIVERY_PICKED_UP", "delivery", d.id, d.code)
    notify(db, d.sender_id, f"Delivery {d.code} picked up", f"{user.full_name} has collected the item.", f"/delivery/{d.id}")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/release")
def release(delivery_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    """Carrier backs out before pickup – the request becomes available again."""
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.carrier_id != user.id:
        raise HTTPException(403, "Only the assigned carrier can do this")
    move(d, "OPEN")
    d.carrier_id = None
    d.accepted_at = None
    audit(db, user, "DELIVERY_RELEASED", "delivery", d.id, d.code)
    notify(db, d.sender_id, f"Delivery {d.code} is open again", "The carrier could not take it.", f"/delivery/{d.id}")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/otp/resend")
def resend_otp(delivery_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if user.id not in (d.carrier_id, d.receiver_id):
        raise HTTPException(403, "Only the carrier or receiver can request a new OTP")
    if d.status != "PICKED_UP":
        raise HTTPException(409, "An OTP can only be issued while the item is in transit")
    current = active_otp(d)
    expire_if_needed(current)
    if current and current.status == "PENDING":
        raise HTTPException(409, "The current OTP is still valid")
    issue_otp(db, d)
    audit(db, user, "DELIVERY_OTP_REISSUED", "delivery", d.id, d.code)
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/verify-otp")
def verify_otp(delivery_id: int, body: OtpIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.carrier_id != user.id:
        raise HTTPException(403, "Only the assigned carrier can confirm the handover")
    if d.status != "PICKED_UP":
        raise HTTPException(409, f"Invalid delivery state change from {d.status} to DELIVERED")
    v = active_otp(d)
    expire_if_needed(v)
    if v is None or v.status == "EXPIRED":
        db.commit()
        raise HTTPException(410, "OTP has expired or is not active. Ask for a new OTP.")
    if not verify_password(body.otp, v.otp_hash):
        v.attempts += 1
        left = v.max_attempts - v.attempts
        if left <= 0:
            v.status = "LOCKED"
            v.otp_plain_for_receiver = ""
            audit(db, user, "DELIVERY_OTP_LOCKED", "delivery", d.id, d.code)
            notify_many(db, [d.sender, d.receiver], f"Delivery {d.code}: OTP locked",
                        "Too many wrong OTP attempts. A new OTP is needed.", f"/delivery/{d.id}", "WARNING")
            db.commit()
            raise HTTPException(423, "Too many wrong attempts. This OTP is now locked.")
        audit(db, user, "DELIVERY_OTP_FAILED", "delivery", d.id, f"{d.code} attempts={v.attempts}")
        db.commit()
        raise HTTPException(400, f"Incorrect OTP. {left} attempt(s) left.")
    v.status = "VERIFIED"
    v.verified_at = datetime.now(UTC)
    v.otp_plain_for_receiver = ""
    move(d, "DELIVERED")
    d.delivered_at = v.verified_at
    audit(db, user, "DELIVERY_COMPLETED", "delivery", d.id, f"{d.code} via OTP")
    notify_many(db, [d.sender, d.receiver], f"Delivery {d.code} completed", "Handover verified by OTP.",
                f"/delivery/{d.id}", "SUCCESS")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/verify-qr")
async def verify_qr(delivery_id: int, qr_token: str = Form(..., max_length=100),
                    receiver_name: str = Form(..., min_length=2, max_length=100),
                    receiver_reg_no: str = Form(..., max_length=20), receiver_room: str = Form(..., max_length=10),
                    receiver_block: str = Form(..., max_length=40), photo: UploadFile = File(...),
                    user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.carrier_id != user.id:
        raise HTTPException(403, "Only the assigned carrier can confirm the handover")
    if d.status != "PICKED_UP":
        raise HTTPException(409, f"Invalid delivery state change from {d.status} to DELIVERED")
    r = d.receiver
    sf = await save_upload(db, photo, user, "DELIVERY_PHOTO", ("image/png", "image/jpeg"))
    checks = {
        "QR code": secrets.compare_digest(qr_token.strip(), d.qr_token),
        "receiver name": receiver_name.strip().lower() == r.full_name.lower(),
        "registration number": receiver_reg_no.strip().upper() == (r.reg_no or ""),
        "room number": bool(r.room) and receiver_room.strip().upper() == r.room.number.upper(),
        "hostel block": bool(r.room) and receiver_block.strip().lower() == r.room.block.name.lower(),
    }
    failed = [k for k, ok in checks.items() if not ok]
    v = HandoverVerification(delivery=d, method="QR", receiver_name=receiver_name.strip(),
                             receiver_reg_no=receiver_reg_no.strip().upper(), receiver_room=receiver_room.strip(),
                             receiver_block=receiver_block.strip(), photo_file_id=sf.id,
                             status="FAILED" if failed else "VERIFIED",
                             verified_at=None if failed else datetime.now(UTC), attempts=1, max_attempts=1)
    db.add(v)
    if failed:
        audit(db, user, "DELIVERY_QR_FAILED", "delivery", d.id, ", ".join(failed))
        db.commit()
        raise HTTPException(400, "Verification failed: " + ", ".join(failed) + " did not match")
    pend = active_otp(d)
    if pend:
        pend.status = "EXPIRED"
        pend.otp_plain_for_receiver = ""
    move(d, "DELIVERED")
    d.delivered_at = v.verified_at
    audit(db, user, "DELIVERY_COMPLETED", "delivery", d.id, f"{d.code} via QR + photo")
    notify_many(db, [d.sender, d.receiver], f"Delivery {d.code} completed", "Handover verified by QR code and photo.",
                f"/delivery/{d.id}", "SUCCESS")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/fail")
def report_failure(delivery_id: int, body: FailIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.carrier_id != user.id:
        raise HTTPException(403, "Only the assigned carrier can report a handover failure")
    move(d, "FAILED")
    d.failure_reason = body.reason
    for v in d.verifications:
        if v.status == "PENDING":
            v.status = "FAILED"
            v.otp_plain_for_receiver = ""
    if d.payment:
        d.payment.status = "REFUNDED_DEMO"
    audit(db, user, "DELIVERY_FAILED", "delivery", d.id, body.reason)
    notify_many(db, [d.sender, d.receiver], f"Delivery {d.code} failed", body.reason, f"/delivery/{d.id}", "WARNING")
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


@router.post("/deliveries/{delivery_id}/cancel")
def cancel(delivery_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = get_delivery(db, delivery_id, user, lock=True)
    if d.sender_id != user.id:
        raise HTTPException(403, "Only the sender can cancel this delivery")
    move(d, "CANCELLED")
    if d.payment:
        d.payment.status = "REFUNDED_DEMO"
    audit(db, user, "DELIVERY_CANCELLED", "delivery", d.id, d.code)
    db.commit()
    db.refresh(d)
    return delivery_out(d, user)


# =============================================================== gate deliveries
class GateIn(BaseModel):
    kind: Literal["FOOD", "PARCEL"]
    vendor: str = Field(min_length=2, max_length=80)
    courier_name: str = Field(min_length=2, max_length=80)
    courier_phone: str = Field(default="", max_length=15)
    order_ref: str = Field(default="", max_length=40)
    expected_date: str
    expected_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    gate: Literal["Main Gate", "Ladies Hostel Gate", "Men's Hostel Gate"] = "Main Gate"

    @field_validator("courier_phone")
    @classmethod
    def phone(cls, v: str) -> str:
        if v and not re.fullmatch(r"[6-9]\d{9}", v.strip()):
            raise ValueError("Courier phone must be a valid 10-digit mobile number")
        return v.strip()


GATE_STAFF = require_roles("STAFF", "WARDEN", "CHIEF_WARDEN", "ADMIN")


def gate_out(g: GateDelivery, viewer: User) -> dict:
    s = g.student
    out = {"id": g.id, "code": g.code, "kind": g.kind, "vendor": g.vendor, "courier_name": g.courier_name,
           "courier_phone": g.courier_phone, "order_ref": g.order_ref, "expected_date": g.expected_date,
           "expected_time": g.expected_time, "gate": g.gate, "status": g.status, "created_at": iso(g.created_at),
           "collected_at": iso(g.collected_at), "otp_attempts": g.otp_attempts,
           "student": {**user_brief(s), "room": f"{s.room.block.name}-{s.room.number}" if s.room else None}}
    if viewer.id == g.student_id:
        out["otp"] = g.otp_plain_for_student or None
    return out


def ensure_gate_staff(user: User) -> None:
    if user.role == "STAFF" and user.staff_type != "SECURITY":
        raise HTTPException(403, "Only gate security can do this")


@router.post("/gate-deliveries", status_code=201)
def book_gate(body: GateIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = parse_date(body.expected_date, "Expected date")
    if d < today() or d > today() + timedelta(days=7):
        raise HTTPException(422, "Expected date must be within the next 7 days")
    otp = generate_otp()
    g = GateDelivery(code="TMP", student_id=user.id, otp_hash=hash_secret(otp), otp_plain_for_student=otp,
                     status="BOOKED", **body.model_dump())
    db.add(g)
    db.flush()
    g.code = f"GATE-{g.id:05d}"
    audit(db, user, f"GATE_{body.kind}_BOOKED", "gate_delivery", g.id, f"{body.vendor} via {body.courier_name}")
    notify_many(db, staff_for(db, "SECURITY"), f"Expected {body.kind.lower()} delivery {g.code}",
                f"For {user.full_name} at {body.gate}, {body.expected_date} {body.expected_time}", "/gate", "TASK")
    db.commit()
    db.refresh(g)
    return gate_out(g, user)


@router.get("/gate-deliveries")
def list_gate(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(GateDelivery).order_by(GateDelivery.created_at.desc())
    if user.role == "STUDENT":
        stmt = stmt.where(GateDelivery.student_id == user.id)
    else:
        ensure_gate_staff(user)
    if status:
        stmt = stmt.where(GateDelivery.status == status)
    return [gate_out(g, user) for g in db.scalars(stmt.limit(200))]


@router.patch("/gate-deliveries/{gate_id}/arrived")
def arrived(gate_id: int, user: User = Depends(GATE_STAFF), db: Session = Depends(get_db)):
    ensure_gate_staff(user)
    g = db.get(GateDelivery, gate_id)
    if not g:
        raise not_found("Gate delivery")
    if g.status != "BOOKED":
        raise HTTPException(409, f"Invalid status change from {g.status} to AT_GATE")
    g.status = "AT_GATE"
    g.handled_by_id = user.id
    audit(db, user, "GATE_ARRIVED", "gate_delivery", g.id)
    notify(db, g.student_id, f"Your {g.kind.lower()} is at {g.gate}",
           f"Show your OTP to security to collect it ({g.courier_name}).", "/delivery", "ALERT")
    db.commit()
    db.refresh(g)
    return gate_out(g, user)


@router.post("/gate-deliveries/{gate_id}/collect")
def collect(gate_id: int, body: OtpIn, user: User = Depends(GATE_STAFF), db: Session = Depends(get_db)):
    ensure_gate_staff(user)
    g = db.get(GateDelivery, gate_id)
    if not g:
        raise not_found("Gate delivery")
    if g.status != "AT_GATE":
        raise HTTPException(409, f"Invalid status change from {g.status} to COLLECTED")
    if g.otp_attempts >= settings.otp_max_attempts:
        raise HTTPException(423, "Too many wrong attempts. The student must contact the warden.")
    if not verify_password(body.otp, g.otp_hash):
        g.otp_attempts += 1
        db.commit()
        left = settings.otp_max_attempts - g.otp_attempts
        if left <= 0:
            raise HTTPException(423, "Too many wrong attempts. The student must contact the warden.")
        raise HTTPException(400, f"Incorrect OTP. {left} attempt(s) left.")
    g.status = "COLLECTED"
    g.collected_at = datetime.now(UTC)
    g.otp_plain_for_student = ""
    audit(db, user, "GATE_COLLECTED", "gate_delivery", g.id)
    notify(db, g.student_id, f"{g.code} collected", "Handover verified with OTP.", "/delivery", "SUCCESS")
    db.commit()
    db.refresh(g)
    return gate_out(g, user)


@router.patch("/gate-deliveries/{gate_id}/cancel")
def cancel_gate(gate_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    g = db.get(GateDelivery, gate_id)
    if not g or g.student_id != user.id:
        raise not_found("Gate delivery")
    if g.status != "BOOKED":
        raise HTTPException(409, "Only bookings that have not arrived can be cancelled")
    g.status = "CANCELLED"
    g.otp_plain_for_student = ""
    audit(db, user, "GATE_CANCELLED", "gate_delivery", g.id)
    db.commit()
    db.refresh(g)
    return gate_out(g, user)
