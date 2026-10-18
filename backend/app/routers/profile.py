"""FR05 student profile management and FR09 roommate finder."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Block, Room, User
from ..security import get_current_user, hash_password, require_roles, verify_password
from ..services import audit, user_out
from .auth import validate_password

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = None
    programme: str | None = Field(default=None, max_length=60)
    pref_sleep: Literal["", "EARLY", "LATE"] | None = None
    pref_study: Literal["", "QUIET", "GROUP"] | None = None
    pref_food: Literal["", "VEG", "NON_VEG"] | None = None
    looking_for_roommate: bool | None = None

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v):
        if v is not None and not re.fullmatch(r"[6-9]\d{9}", v.strip()):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number")
        return v.strip() if v else v

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, v):
        if v is not None and not re.fullmatch(r"[A-Za-z .'-]{2,100}", v.strip()):
            raise ValueError("Name may contain only letters, spaces, dots, hyphens and apostrophes")
        return v.strip() if v else v


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(max_length=72)
    _pw = field_validator("new_password")(validate_password)


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/profile")
def update_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(user, k, v)
    audit(db, user, "PROFILE_UPDATED", "user", user.id, ", ".join(changes))
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/profile/password")
def change_password(body: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "PASSWORD_CHANGED", "user", user.id)
    db.commit()
    return {"ok": True}


@router.get("/roommates")
def roommate_finder(
    sleep: str = Query(""),
    study: str = Query(""),
    food: str = Query(""),
    user: User = Depends(require_roles("STUDENT")),
    db: Session = Depends(get_db),
):
    """Students looking for a roommate, scored by matching preferences, plus rooms with vacancies."""
    want = {"pref_sleep": sleep or user.pref_sleep, "pref_study": study or user.pref_study,
            "pref_food": food or user.pref_food}
    candidates = db.scalars(
        select(User).where(
            User.role == "STUDENT", User.looking_for_roommate.is_(True), User.id != user.id,
            User.is_active.is_(True), User.gender == user.gender,
        )
    ).all()
    matches = []
    for c in candidates:
        score = sum(1 for k, v in want.items() if v and getattr(c, k) == v)
        matches.append({
            "id": c.id, "full_name": c.full_name, "reg_no": c.reg_no, "programme": c.programme,
            "year_of_study": c.year_of_study, "pref_sleep": c.pref_sleep, "pref_study": c.pref_study,
            "pref_food": c.pref_food, "score": score, "max_score": sum(1 for v in want.values() if v),
            "room": f"{c.room.block.name}-{c.room.number}" if c.room else None,
        })
    matches.sort(key=lambda m: (-m["score"], m["full_name"]))
    rooms = []
    for r in db.scalars(select(Room).join(Block)).all():
        free = r.capacity - len(r.occupants)
        if free > 0:
            rooms.append({"id": r.id, "label": f"{r.block.hostel.name} / {r.block.name}-{r.number}",
                          "room_type": r.room_type, "free_beds": free, "hostel_gender": r.block.hostel.gender})
    gender_map = {"MALE": "BOYS", "FEMALE": "GIRLS"}
    g = gender_map.get(user.gender)
    if g:
        rooms = [r for r in rooms if r["hostel_gender"] == g]
    return {"matches": matches, "rooms_with_vacancy": rooms[:50]}
