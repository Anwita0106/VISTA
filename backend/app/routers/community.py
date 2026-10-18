"""FR18 lost & found, FR21 mess feedback, FR24 document vault, FR25 notes, FR26 marketplace."""
import secrets
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import (
    DeliveryRequest,
    HandoverVerification,
    LostFoundItem,
    MarketplaceItem,
    MessFeedback,
    SharedNote,
    StoredFile,
    User,
    VaultDocument,
)
from ..security import get_current_user, require_roles
from ..services import audit, iso, lock_for_user, not_found, parse_date, today, user_brief

router = APIRouter(prefix="/api", tags=["community"])
STUDENT = require_roles("STUDENT")

ALLOWED_TYPES = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "text/plain": (),
}


async def save_upload(db: Session, file: UploadFile, owner: User, purpose: str,
                      allowed: tuple[str, ...] = tuple(ALLOWED_TYPES)) -> StoredFile:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File is larger than {settings.max_upload_bytes // (1024 * 1024)} MB")
    if not data:
        raise HTTPException(422, "File is empty")
    ctype = (file.content_type or "").lower()
    if ctype not in allowed:
        raise HTTPException(415, "Only PDF, PNG, JPEG or plain-text files are allowed")
    magic = ALLOWED_TYPES[ctype]
    if magic and not any(data.startswith(m) for m in magic):
        raise HTTPException(415, "File content does not match its type")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = secrets.token_hex(16)
    (settings.upload_dir / stored).write_bytes(data)
    sf = StoredFile(owner_id=owner.id, original_name=(file.filename or "file")[:200], stored_name=stored,
                    content_type=ctype, size_bytes=len(data), purpose=purpose)
    db.add(sf)
    db.flush()
    return sf


def file_out(f: StoredFile | None) -> dict | None:
    if f is None:
        return None
    return {"id": f.id, "name": f.original_name, "size": f.size_bytes, "content_type": f.content_type,
            "url": f"/api/files/{f.id}"}


@router.get("/files/{file_id}")
def download(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(StoredFile, file_id)
    if not f:
        raise not_found("File")
    allowed = user.id == f.owner_id or user.role == "ADMIN"
    if f.purpose == "NOTE":
        allowed = True
    elif f.purpose == "VAULT":
        allowed = allowed or user.role in ("WARDEN", "CHIEF_WARDEN")
    elif f.purpose == "DELIVERY_PHOTO":
        v = db.scalar(select(HandoverVerification).where(HandoverVerification.photo_file_id == f.id))
        d = db.get(DeliveryRequest, v.delivery_id) if v else None
        allowed = allowed or bool(d and user.id in (d.sender_id, d.receiver_id, d.carrier_id))
    if not allowed:
        raise not_found("File")
    path = settings.upload_dir / f.stored_name
    if not path.is_file():
        raise not_found("File")
    return FileResponse(path, media_type=f.content_type, filename=f.original_name)


# ------------------------------------------------------------- lost & found
class LostFoundIn(BaseModel):
    kind: Literal["LOST", "FOUND"]
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    location: str = Field(min_length=2, max_length=120)
    item_date: str
    contact: str = Field(default="", max_length=60)


def lf_out(i: LostFoundItem) -> dict:
    return {"id": i.id, "kind": i.kind, "title": i.title, "description": i.description, "location": i.location,
            "item_date": i.item_date, "contact": i.contact, "status": i.status, "reporter": user_brief(i.reporter),
            "created_at": iso(i.created_at)}


@router.get("/lost-found")
def list_lost_found(q: str | None = Query(None, max_length=100), kind: str | None = None, status: str | None = None,
                    _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(LostFoundItem).order_by(LostFoundItem.created_at.desc())
    if kind:
        stmt = stmt.where(LostFoundItem.kind == kind)
    if status:
        stmt = stmt.where(LostFoundItem.status == status)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(LostFoundItem.title).like(like), func.lower(LostFoundItem.description).like(like),
                              func.lower(LostFoundItem.location).like(like)))
    return [lf_out(i) for i in db.scalars(stmt.limit(200))]


@router.post("/lost-found", status_code=201)
def report_item(body: LostFoundIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = parse_date(body.item_date, "Date")
    if d > today():
        raise HTTPException(422, "Date cannot be in the future")
    i = LostFoundItem(reporter_id=user.id, **body.model_dump())
    db.add(i)
    db.flush()
    audit(db, user, f"ITEM_{body.kind}", "lost_found", i.id, body.title)
    db.commit()
    db.refresh(i)
    return lf_out(i)


@router.patch("/lost-found/{item_id}/claim")
def claim(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    i = db.get(LostFoundItem, item_id)
    if not i:
        raise not_found("Item")
    if i.reporter_id != user.id and user.role not in ("WARDEN", "CHIEF_WARDEN", "ADMIN"):
        raise HTTPException(403, "Only the reporter or a warden can close this item")
    if i.status == "CLAIMED":
        raise HTTPException(409, "Item is already marked as returned")
    i.status = "CLAIMED"
    audit(db, user, "ITEM_CLAIMED", "lost_found", i.id)
    db.commit()
    db.refresh(i)
    return lf_out(i)


# ------------------------------------------------------------- mess feedback
class FeedbackIn(BaseModel):
    meal: Literal["BREAKFAST", "LUNCH", "SNACKS", "DINNER"]
    food_rating: int = Field(ge=1, le=5)
    service_rating: int = Field(ge=1, le=5)
    comments: str = Field(default="", max_length=500)
    feedback_date: str


@router.post("/mess-feedback", status_code=201)
def submit_feedback(body: FeedbackIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = parse_date(body.feedback_date, "Date")
    if d > today() or d < today() - timedelta(days=3):
        raise HTTPException(422, "Feedback can be given for meals in the last 3 days only")
    lock_for_user(db, user.id, "mess")
    if db.scalar(select(MessFeedback).where(MessFeedback.student_id == user.id, MessFeedback.meal == body.meal,
                                            MessFeedback.feedback_date == body.feedback_date)):
        raise HTTPException(409, "You have already given feedback for this meal")
    f = MessFeedback(student_id=user.id, **body.model_dump())
    db.add(f)
    audit(db, user, "MESS_FEEDBACK", "mess_feedback", "", f"{body.meal} {body.food_rating}/{body.service_rating}")
    db.commit()
    return {"id": f.id, **body.model_dump(), "created_at": iso(f.created_at)}


@router.get("/mess-feedback")
def list_feedback(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(MessFeedback).order_by(MessFeedback.created_at.desc())
    if user.role == "STUDENT":
        stmt = stmt.where(MessFeedback.student_id == user.id)
    elif not (user.role in ("WARDEN", "CHIEF_WARDEN", "ADMIN") or user.staff_type == "MESS"):
        raise HTTPException(403, "You do not have permission for this action")
    items = db.scalars(stmt.limit(200)).all()
    summary = {}
    for meal, food, svc, n in db.execute(select(MessFeedback.meal, func.avg(MessFeedback.food_rating),
                                                func.avg(MessFeedback.service_rating), func.count())
                                         .group_by(MessFeedback.meal)):
        summary[meal] = {"food": round(float(food), 2), "service": round(float(svc), 2), "count": n}
    return {"summary": summary, "items": [
        {"id": f.id, "meal": f.meal, "food_rating": f.food_rating, "service_rating": f.service_rating,
         "comments": f.comments, "feedback_date": f.feedback_date,
         "student": user_brief(f.student) if user.role != "STAFF" else None, "created_at": iso(f.created_at)}
        for f in items]}


# ------------------------------------------------------------- marketplace
class MarketIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    category: Literal["BOOKS", "ELECTRONICS", "FURNITURE", "CLOTHING", "OTHER"]
    condition: Literal["NEW", "LIKE_NEW", "GOOD", "FAIR"] = "GOOD"
    price: int = Field(ge=0, le=100000)


def mk_out(m: MarketplaceItem) -> dict:
    return {"id": m.id, "title": m.title, "description": m.description, "category": m.category,
            "condition": m.condition, "price": m.price, "status": m.status, "seller": user_brief(m.seller),
            "created_at": iso(m.created_at)}


@router.get("/marketplace")
def list_market(q: str | None = Query(None, max_length=100), category: str | None = None,
                sort: Literal["newest", "price_asc", "price_desc"] = "newest", include_sold: bool = False,
                _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(MarketplaceItem)
    if not include_sold:
        stmt = stmt.where(MarketplaceItem.status == "AVAILABLE")
    if category:
        stmt = stmt.where(MarketplaceItem.category == category)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(MarketplaceItem.title).like(like), func.lower(MarketplaceItem.description).like(like)))
    order = {"newest": MarketplaceItem.created_at.desc(), "price_asc": MarketplaceItem.price.asc(),
             "price_desc": MarketplaceItem.price.desc()}[sort]
    return [mk_out(m) for m in db.scalars(stmt.order_by(order).limit(200))]


@router.post("/marketplace", status_code=201)
def create_listing(body: MarketIn, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    m = MarketplaceItem(seller_id=user.id, **body.model_dump())
    db.add(m)
    db.flush()
    audit(db, user, "LISTING_CREATED", "marketplace", m.id, body.title)
    db.commit()
    db.refresh(m)
    return mk_out(m)


@router.patch("/marketplace/{item_id}/sold")
def mark_sold(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(MarketplaceItem, item_id)
    if not m:
        raise not_found("Listing")
    if m.seller_id != user.id:
        raise HTTPException(403, "Only the seller can mark this item as sold")
    if m.status == "SOLD":
        raise HTTPException(409, "Item is already marked as sold")
    m.status = "SOLD"
    audit(db, user, "LISTING_SOLD", "marketplace", m.id)
    db.commit()
    db.refresh(m)
    return mk_out(m)


@router.delete("/marketplace/{item_id}")
def delete_listing(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(MarketplaceItem, item_id)
    if not m:
        raise not_found("Listing")
    if m.seller_id != user.id and user.role != "ADMIN":
        raise HTTPException(403, "Only the seller or an administrator can remove this listing")
    db.delete(m)
    audit(db, user, "LISTING_DELETED", "marketplace", item_id)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- notes sharing
@router.get("/notes")
def list_notes(q: str | None = Query(None, max_length=100), subject: str | None = None,
               _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(SharedNote).order_by(SharedNote.created_at.desc())
    if subject:
        stmt = stmt.where(SharedNote.subject == subject)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(SharedNote.title).like(like), func.lower(SharedNote.subject).like(like)))
    return [{"id": n.id, "title": n.title, "subject": n.subject, "content": n.content, "file": file_out(n.file),
             "author": user_brief(n.author), "created_at": iso(n.created_at)} for n in db.scalars(stmt.limit(200))]


@router.post("/notes", status_code=201)
async def share_note(title: str = Form(..., min_length=3, max_length=120), subject: str = Form(..., min_length=2, max_length=60),
                     content: str = Form("", max_length=10000), file: UploadFile | None = File(None),
                     user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    if not content.strip() and file is None:
        raise HTTPException(422, "Add some text or attach a file")
    sf = await save_upload(db, file, user, "NOTE") if file is not None and file.filename else None
    n = SharedNote(author_id=user.id, title=title.strip(), subject=subject.strip(), content=content.strip(),
                   file_id=sf.id if sf else None)
    db.add(n)
    db.flush()
    audit(db, user, "NOTE_SHARED", "note", n.id, title)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "title": n.title, "subject": n.subject, "content": n.content, "file": file_out(n.file),
            "author": user_brief(n.author), "created_at": iso(n.created_at)}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(SharedNote, note_id)
    if not n:
        raise not_found("Note")
    if n.author_id != user.id and user.role != "ADMIN":
        raise HTTPException(403, "Only the author or an administrator can delete this note")
    db.delete(n)
    audit(db, user, "NOTE_DELETED", "note", note_id)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- document vault
@router.get("/vault")
def list_vault(user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    docs = db.scalars(select(VaultDocument).where(VaultDocument.student_id == user.id)
                      .order_by(VaultDocument.created_at.desc())).all()
    return [{"id": d.id, "title": d.title, "doc_type": d.doc_type, "file": file_out(d.file),
             "created_at": iso(d.created_at)} for d in docs]


@router.post("/vault", status_code=201)
async def upload_vault(title: str = Form(..., min_length=3, max_length=120),
                       doc_type: Literal["ID_PROOF", "ALLOTMENT_LETTER", "FEE_RECEIPT", "MEDICAL", "UNDERTAKING", "OTHER"] = Form(...),
                       file: UploadFile = File(...), user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    sf = await save_upload(db, file, user, "VAULT", ("application/pdf", "image/png", "image/jpeg"))
    d = VaultDocument(student_id=user.id, title=title.strip(), doc_type=doc_type, file_id=sf.id)
    db.add(d)
    db.flush()
    audit(db, user, "VAULT_UPLOAD", "vault", d.id, title)
    db.commit()
    db.refresh(d)
    return {"id": d.id, "title": d.title, "doc_type": d.doc_type, "file": file_out(d.file), "created_at": iso(d.created_at)}


@router.delete("/vault/{doc_id}")
def delete_vault(doc_id: int, user: User = Depends(STUDENT), db: Session = Depends(get_db)):
    d = db.get(VaultDocument, doc_id)
    if not d or d.student_id != user.id:
        raise not_found("Document")
    f = d.file
    db.delete(d)
    path = settings.upload_dir / f.stored_name
    db.delete(f)
    audit(db, user, "VAULT_DELETE", "vault", doc_id)
    db.commit()
    path.unlink(missing_ok=True)
    return {"ok": True}
