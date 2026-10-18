"""FR01, FR04: registration, secure login with RBAC, logout, profile (FR05)."""
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import LoginAttempt, RevokedToken, User
from ..security import create_token, get_current_user, get_token_payload, hash_password, verify_password
from ..services import audit, user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])

REG_NO_RE = re.compile(r"^\d{2}[A-Z]{3}\d{4}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")


def validate_password(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters and contain letters and digits")
    return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(max_length=72)
    reg_no: str
    phone: str
    programme: str = Field(default="", max_length=60)
    year_of_study: int = Field(ge=1, le=5)
    gender: Literal["MALE", "FEMALE", "OTHER"]

    _pw = field_validator("password")(validate_password)

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z .'-]{2,100}", v):
            raise ValueError("Name may contain only letters, spaces, dots, hyphens and apostrophes")
        return v

    @field_validator("reg_no")
    @classmethod
    def reg_ok(cls, v: str) -> str:
        v = v.strip().upper()
        if not REG_NO_RE.fullmatch(v):
            raise ValueError("Registration number must look like 24BYB0193")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        v = v.strip()
        if not PHONE_RE.fullmatch(v):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number")
        return v


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    if db.scalar(select(User).where(User.reg_no == body.reg_no)):
        raise HTTPException(409, "An account with this registration number already exists")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="STUDENT",
        phone=body.phone,
        reg_no=body.reg_no,
        programme=body.programme,
        year_of_study=body.year_of_study,
        gender=body.gender,
    )
    db.add(user)
    db.flush()
    audit(db, user, "USER_REGISTERED", "user", user.id, f"Student self-registration {body.reg_no}")
    db.commit()
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    window_start = datetime.now(UTC) - timedelta(minutes=settings.login_lockout_minutes)
    last_success = db.scalar(
        select(func.max(LoginAttempt.created_at)).where(LoginAttempt.email == email, LoginAttempt.success.is_(True))
    )
    since = max(window_start, last_success) if last_success else window_start
    failures = db.scalar(
        select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.email == email, LoginAttempt.success.is_(False), LoginAttempt.created_at > since
        )
    )
    if failures >= settings.login_max_failures:
        raise HTTPException(
            429, f"Too many failed attempts. Try again in {settings.login_lockout_minutes} minutes."
        )
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        db.add(LoginAttempt(email=email, success=False))
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated. Contact the hostel office.")
    db.add(LoginAttempt(email=email, success=True))
    audit(db, user, "LOGIN", "user", user.id, f"from {request.client.host if request.client else '?'}")
    db.commit()
    token, expires = create_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_at": expires.isoformat(), "user": user_out(user)}


@router.post("/logout")
def logout(payload: dict = Depends(get_token_payload), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    db.merge(RevokedToken(jti=payload["jti"]))
    audit(db, user, "LOGOUT", "user", user.id)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
