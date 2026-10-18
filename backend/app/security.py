"""Password hashing, JWT tokens and role-based access dependencies."""
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import RevokedToken, User

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def hash_secret(value: str) -> str:
    """Hash for short secrets such as OTPs (bcrypt, low cost)."""
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=6)).decode()


def generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def create_token(user: User) -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expires,
        "iat": datetime.now(UTC),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_token_payload(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        return decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please log in again") from None
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token") from None


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    if db.get(RevokedToken, payload.get("jti", "")):
        raise _unauthorized("Session has been logged out")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("Account not found or disabled")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")
        return user

    return dep


def require_staff_type(*types: str):
    """Staff of the given type(s); wardens and admins are also allowed."""

    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role in ("WARDEN", "CHIEF_WARDEN", "ADMIN"):
            return user
        if user.role == "STAFF" and (user.staff_type in types):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")

    return dep
