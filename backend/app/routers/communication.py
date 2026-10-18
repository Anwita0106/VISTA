"""FR17 dashboard notices, FR32 in-app messaging, FR33 notifications, FR34 notice publishing."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Hostel, Message, Notice, Notification, User
from ..security import get_current_user, require_roles
from ..services import audit, iso, not_found, notify, user_brief

router = APIRouter(prefix="/api", tags=["communication"])
PUBLISHERS = require_roles("WARDEN", "CHIEF_WARDEN", "ADMIN")


class NoticeIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=5, max_length=5000)
    category: Literal["GENERAL", "MESS", "MAINTENANCE", "EVENT", "URGENT"] = "GENERAL"
    hostel_id: int | None = None


class MessageIn(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=1000)


def notice_out(n: Notice) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "category": n.category,
            "hostel": n.hostel.name if n.hostel else "All hostels", "hostel_id": n.hostel_id,
            "author": user_brief(n.author), "created_at": iso(n.created_at)}


def user_hostel_id(user: User) -> int | None:
    if user.hostel_id:
        return user.hostel_id
    return user.room.block.hostel_id if user.room else None


@router.get("/notices")
def list_notices(q: str | None = Query(None, max_length=100), category: str | None = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Notice).order_by(Notice.created_at.desc())
    if user.role == "STUDENT":
        hid = user_hostel_id(user)
        stmt = stmt.where(or_(Notice.hostel_id.is_(None), Notice.hostel_id == hid))
    if category:
        stmt = stmt.where(Notice.category == category)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Notice.title).like(like), func.lower(Notice.body).like(like)))
    return [notice_out(n) for n in db.scalars(stmt.limit(100))]


@router.post("/notices", status_code=201)
def create_notice(body: NoticeIn, user: User = Depends(PUBLISHERS), db: Session = Depends(get_db)):
    if body.hostel_id is not None and not db.get(Hostel, body.hostel_id):
        raise not_found("Hostel")
    n = Notice(author_id=user.id, **body.model_dump())
    db.add(n)
    db.flush()
    students = select(User).where(User.role == "STUDENT", User.is_active.is_(True))
    for s in db.scalars(students):
        if body.hostel_id is None or user_hostel_id(s) == body.hostel_id:
            notify(db, s.id, f"New notice: {body.title}", body.body[:200], "/notices",
                   "ALERT" if body.category == "URGENT" else "INFO")
    audit(db, user, "NOTICE_PUBLISHED", "notice", n.id, body.title)
    db.commit()
    db.refresh(n)
    return notice_out(n)


@router.delete("/notices/{notice_id}")
def delete_notice(notice_id: int, user: User = Depends(PUBLISHERS), db: Session = Depends(get_db)):
    n = db.get(Notice, notice_id)
    if not n:
        raise not_found("Notice")
    if user.role != "ADMIN" and n.author_id != user.id:
        raise HTTPException(403, "You can only delete notices you published")
    db.delete(n)
    audit(db, user, "NOTICE_DELETED", "notice", notice_id)
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def list_notifications(unread_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    items = db.scalars(stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(50)).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.is_read.is_(False)))
    return {"unread": unread, "items": [
        {"id": n.id, "title": n.title, "body": n.body, "link": n.link, "kind": n.kind, "is_read": n.is_read,
         "created_at": iso(n.created_at)} for n in items]}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    db.commit()
    return {"ok": True}


@router.patch("/notifications/{notification_id}/read")
def read_one(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise not_found("Notification")
    n.is_read = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- messaging
@router.get("/messages/contacts")
def contacts(q: str = Query("", max_length=60), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Students can message wardens, staff and other students; search by name or reg no."""
    stmt = select(User).where(User.id != user.id, User.is_active.is_(True))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(func.coalesce(User.reg_no, "")).like(like)))
    return [user_brief(u) | {"staff_type": u.staff_type} for u in db.scalars(stmt.order_by(User.full_name).limit(20))]


@router.get("/messages")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msgs = db.scalars(select(Message).where(or_(Message.sender_id == user.id, Message.recipient_id == user.id))
                      .order_by(Message.created_at.desc()).limit(500)).all()
    convs: dict[int, dict] = {}
    for m in msgs:
        other = m.recipient if m.sender_id == user.id else m.sender
        c = convs.setdefault(other.id, {"user": user_brief(other), "last": m.body, "last_at": iso(m.created_at), "unread": 0})
        if m.recipient_id == user.id and not m.is_read:
            c["unread"] += 1
    return list(convs.values())


@router.get("/messages/{other_id}")
def thread(other_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    other = db.get(User, other_id)
    if not other:
        raise not_found("User")
    msgs = db.scalars(select(Message).where(or_(
        and_(Message.sender_id == user.id, Message.recipient_id == other_id),
        and_(Message.sender_id == other_id, Message.recipient_id == user.id))).order_by(Message.created_at)).all()
    db.execute(update(Message).where(Message.sender_id == other_id, Message.recipient_id == user.id)
               .values(is_read=True))
    db.commit()
    return {"user": user_brief(other), "messages": [
        {"id": m.id, "body": m.body, "mine": m.sender_id == user.id, "created_at": iso(m.created_at)} for m in msgs]}


@router.post("/messages", status_code=201)
def send(body: MessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    other = db.get(User, body.recipient_id)
    if not other or not other.is_active:
        raise not_found("Recipient")
    if other.id == user.id:
        raise HTTPException(400, "You cannot message yourself")
    m = Message(sender_id=user.id, recipient_id=other.id, body=body.body.strip())
    db.add(m)
    notify(db, other.id, f"New message from {user.full_name}", body.body[:120], f"/messages?u={user.id}", "MESSAGE")
    db.commit()
    return {"id": m.id, "body": m.body, "mine": True, "created_at": iso(m.created_at)}
