"""SQLAlchemy data model for VISTA (follows the Class Model in the Lab VI report)."""
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every database.

    PostgreSQL keeps the time zone, but SQLite returns naive values; this normalises both,
    so comparisons with datetime.now(UTC) never fail (fixes login error on SQLite)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


TS = UTCDateTime()

# ---------------------------------------------------------------- Roles
ROLE_STUDENT = "STUDENT"
ROLE_WARDEN = "WARDEN"
ROLE_CHIEF_WARDEN = "CHIEF_WARDEN"
ROLE_STAFF = "STAFF"
ROLE_ADMIN = "ADMIN"
ALL_ROLES = (ROLE_STUDENT, ROLE_WARDEN, ROLE_CHIEF_WARDEN, ROLE_STAFF, ROLE_ADMIN)
WARDEN_ROLES = (ROLE_WARDEN, ROLE_CHIEF_WARDEN)

STAFF_TYPES = ("MAINTENANCE", "CLEANING", "MESS", "SECURITY")


# ---------------------------------------------------------------- Users & accommodation
class Hostel(Base):
    __tablename__ = "hostels"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    gender: Mapped[str] = mapped_column(String(10))  # BOYS / GIRLS
    description: Mapped[str] = mapped_column(String(300), default="")
    blocks: Mapped[list["Block"]] = relationship(back_populates="hostel", cascade="all, delete-orphan")


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("hostel_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(40))
    floors: Mapped[int] = mapped_column(Integer, default=4)
    hostel: Mapped[Hostel] = relationship(back_populates="blocks")
    rooms: Mapped[list["Room"]] = relationship(back_populates="block", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("block_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id", ondelete="CASCADE"))
    number: Mapped[str] = mapped_column(String(10))
    floor: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=2)
    room_type: Mapped[str] = mapped_column(String(20), default="AC")  # AC / NON_AC
    block: Mapped[Block] = relationship(back_populates="rooms")
    occupants: Mapped[list["User"]] = relationship(back_populates="room")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), index=True)
    phone: Mapped[str] = mapped_column(String(15), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # student fields
    reg_no: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    programme: Mapped[str] = mapped_column(String(60), default="")
    year_of_study: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(10), default="")
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    # roommate preferences (FR09)
    pref_sleep: Mapped[str] = mapped_column(String(20), default="")  # EARLY / LATE
    pref_study: Mapped[str] = mapped_column(String(20), default="")  # QUIET / GROUP
    pref_food: Mapped[str] = mapped_column(String(20), default="")  # VEG / NON_VEG
    looking_for_roommate: Mapped[bool] = mapped_column(Boolean, default=False)
    # staff / warden fields
    staff_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hostel_id: Mapped[int | None] = mapped_column(ForeignKey("hostels.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    room: Mapped[Room | None] = relationship(back_populates="occupants")
    hostel: Mapped[Hostel | None] = relationship(foreign_keys=[hostel_id])


class LoginAttempt(Base):
    """Used for brute-force protection (lockout after repeated failures)."""

    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


# ---------------------------------------------------------------- Complaints & visitors
COMPLAINT_CATEGORIES = ("ELECTRICAL", "PLUMBING", "CARPENTRY", "WASHROOM", "WATER", "OTHER")
COMPLAINT_STATUSES = ("OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED", "CLOSED")
PRIORITIES = ("LOW", "MEDIUM", "HIGH")


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    escalated_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    assigned_staff: Mapped[User | None] = relationship(foreign_keys=[assigned_staff_id])
    escalated_to: Mapped[User | None] = relationship(foreign_keys=[escalated_to_id])
    updates: Mapped[list["ComplaintUpdate"]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintUpdate.id"
    )


class ComplaintUpdate(Base):
    __tablename__ = "complaint_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    complaint: Mapped[Complaint] = relationship(back_populates="updates")
    actor: Mapped[User | None] = relationship()


class VisitorRequest(Base):
    __tablename__ = "visitor_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    visitor_name: Mapped[str] = mapped_column(String(100))
    relation: Mapped[str] = mapped_column(String(40))
    visitor_phone: Mapped[str] = mapped_column(String(15))
    visit_date: Mapped[str] = mapped_column(String(10))  # ISO date
    time_from: Mapped[str] = mapped_column(String(5))
    time_to: Mapped[str] = mapped_column(String(5))
    purpose: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_remark: Mapped[str] = mapped_column(String(300), default="")
    decided_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id])


# ---------------------------------------------------------------- Service requests & SOS
class ServiceRequest(Base):
    """Single-table inheritance: SICK_MEAL and CLEANING requests (class model generalisation)."""

    __tablename__ = "service_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # SICK_MEAL / CLEANING
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    preferred_date: Mapped[str] = mapped_column(String(10))
    preferred_slot: Mapped[str] = mapped_column(String(20), default="")
    meal_type: Mapped[str] = mapped_column(String(20), default="")  # BREAKFAST/LUNCH/DINNER
    diet_notes: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    assigned_staff: Mapped[User | None] = relationship(foreign_keys=[assigned_staff_id])


class SOSAlert(Base):
    __tablename__ = "sos_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(300), default="")
    location: Mapped[str] = mapped_column(String(150), default="")
    status: Mapped[str] = mapped_column(String(20), default="RAISED", index=True)  # RAISED/ACKNOWLEDGED/RESOLVED
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    acknowledged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    resolution_note: Mapped[str] = mapped_column(String(300), default="")
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    acknowledged_by: Mapped[User | None] = relationship(foreign_keys=[acknowledged_by_id])
    resolved_by: Mapped[User | None] = relationship(foreign_keys=[resolved_by_id])


# ---------------------------------------------------------------- Communication & audit
class Notice(Base):
    __tablename__ = "notices"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), default="GENERAL")
    hostel_id: Mapped[int | None] = mapped_column(ForeignKey("hostels.id"), nullable=True)  # None = all hostels
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    author: Mapped[User] = relationship()
    hostel: Mapped[Hostel | None] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(String(500), default="")
    link: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(20), default="INFO")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(String(1000))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    user: Mapped[User | None] = relationship()


# ---------------------------------------------------------------- Community
class LostFoundItem(Base):
    __tablename__ = "lost_found_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # LOST / FOUND
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    item_date: Mapped[str] = mapped_column(String(10))
    contact: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN / CLAIMED
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    reporter: Mapped[User] = relationship()


class MessFeedback(Base):
    __tablename__ = "mess_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    meal: Mapped[str] = mapped_column(String(20))
    food_rating: Mapped[int] = mapped_column(Integer)
    service_rating: Mapped[int] = mapped_column(Integer)
    comments: Mapped[str] = mapped_column(String(500), default="")
    feedback_date: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    student: Mapped[User] = relationship()


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(20))  # BOOKS / ELECTRONICS / FURNITURE / OTHER
    condition: Mapped[str] = mapped_column(String(20), default="GOOD")
    price: Mapped[int] = mapped_column(Integer)  # rupees; 0 = exchange / free
    status: Mapped[str] = mapped_column(String(10), default="AVAILABLE")  # AVAILABLE / SOLD
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    seller: Mapped[User] = relationship()


class StoredFile(Base):
    """Files uploaded for the document vault, shared notes and delivery photos."""

    __tablename__ = "stored_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_name: Mapped[str] = mapped_column(String(200))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(20))  # VAULT / NOTE / DELIVERY_PHOTO
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class VaultDocument(Base):
    __tablename__ = "vault_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    doc_type: Mapped[str] = mapped_column(String(30))
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    file: Mapped[StoredFile] = relationship()


class SharedNote(Base):
    __tablename__ = "shared_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(60))
    content: Mapped[str] = mapped_column(Text, default="")
    file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    author: Mapped[User] = relationship()
    file: Mapped[StoredFile | None] = relationship()


class MapLocation(Base):
    """Points of interest drawn on the hostel map (FR20)."""

    __tablename__ = "map_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))  # BLOCK / MESS / GATE / SERVICE
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(200), default="")


# ---------------------------------------------------------------- Delivery
DELIVERY_STATUSES = ("OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED", "CANCELLED", "FAILED")


class DeliveryRequest(Base):
    """Peer-to-peer inter-hostel delivery (FR28-FR30)."""

    __tablename__ = "delivery_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    carrier_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    item_description: Mapped[str] = mapped_column(String(200))
    item_type: Mapped[str] = mapped_column(String(20), default="PARCEL")  # PARCEL / FOOD / DOCUMENT
    pickup_hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    drop_hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    pickup_point: Mapped[str] = mapped_column(String(120), default="")
    fee: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    qr_token: Mapped[str] = mapped_column(String(64))
    failure_reason: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    receiver: Mapped[User] = relationship(foreign_keys=[receiver_id])
    carrier: Mapped[User | None] = relationship(foreign_keys=[carrier_id])
    pickup_hostel: Mapped[Hostel] = relationship(foreign_keys=[pickup_hostel_id])
    drop_hostel: Mapped[Hostel] = relationship(foreign_keys=[drop_hostel_id])
    payment: Mapped["Payment | None"] = relationship(back_populates="delivery", uselist=False)
    verifications: Mapped[list["HandoverVerification"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan", order_by="HandoverVerification.id"
    )


class Payment(Base):
    """Demo payment record. No real money is moved – see README."""

    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery_requests.id", ondelete="CASCADE"), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20), default="DEMO_WALLET")
    status: Mapped[str] = mapped_column(String(20), default="PAID_DEMO")  # PAID_DEMO / REFUNDED_DEMO
    receipt_no: Mapped[str] = mapped_column(String(30), unique=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    delivery: Mapped[DeliveryRequest] = relationship(back_populates="payment")


class HandoverVerification(Base):
    """OTP or QR+photo verification attempt for a delivery (generalisation in class model)."""

    __tablename__ = "handover_verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery_requests.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(10))  # OTP / QR
    otp_hash: Mapped[str] = mapped_column(String(128), default="")
    otp_plain_for_receiver: Mapped[str] = mapped_column(String(6), default="")  # visible only to receiver
    expires_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING/VERIFIED/LOCKED/EXPIRED/FAILED
    receiver_name: Mapped[str] = mapped_column(String(100), default="")
    receiver_reg_no: Mapped[str] = mapped_column(String(20), default="")
    receiver_room: Mapped[str] = mapped_column(String(10), default="")
    receiver_block: Mapped[str] = mapped_column(String(40), default="")
    photo_file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    delivery: Mapped[DeliveryRequest] = relationship(back_populates="verifications")


class GateDelivery(Base):
    """Food-delivery booking to the hostel gate (FR27) and parcel reservation (FR31)."""

    __tablename__ = "gate_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # FOOD / PARCEL
    vendor: Mapped[str] = mapped_column(String(80))
    courier_name: Mapped[str] = mapped_column(String(80))
    courier_phone: Mapped[str] = mapped_column(String(15), default="")
    order_ref: Mapped[str] = mapped_column(String(40), default="")
    expected_date: Mapped[str] = mapped_column(String(10))
    expected_time: Mapped[str] = mapped_column(String(5))
    gate: Mapped[str] = mapped_column(String(40), default="Main Gate")
    otp_hash: Mapped[str] = mapped_column(String(128))
    otp_plain_for_student: Mapped[str] = mapped_column(String(6), default="")  # cleared after collection
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="BOOKED")  # BOOKED/AT_GATE/COLLECTED/CANCELLED
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    collected_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    student: Mapped[User] = relationship(foreign_keys=[student_id])
