"""Application settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader so local runs work without extra dependencies."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break


_load_dotenv()


class Settings:
    def __init__(self) -> None:
        # Default: a local SQLite file next to the backend (zero-setup demo). Set DATABASE_URL for PostgreSQL.
        default_db = "sqlite:///" + (Path(__file__).resolve().parents[1] / "vista.db").as_posix()
        self.database_url: str = os.getenv("DATABASE_URL", default_db)
        if self.database_url.startswith("postgres://"):  # Render / Heroku style URL
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.jwt_secret: str = os.getenv("JWT_SECRET", "")
        self.jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "120"))
        self.cors_origins: list[str] = [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        ]
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads")))
        self.max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024)))
        self.login_max_failures: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
        self.login_lockout_minutes: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
        self.otp_expiry_minutes: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
        self.otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))
        self.escalation_check_seconds: int = int(os.getenv("ESCALATION_CHECK_SECONDS", "300"))
        self.frontend_dist: Path = Path(
            os.getenv("FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
        )
        if not self.jwt_secret:
            if self.environment == "production":
                raise RuntimeError("JWT_SECRET must be set in production")
            self.jwt_secret = "dev-only-insecure-secret-change-me-0123456789"


settings = Settings()

# Complaint escalation rule (FR12): unresolved complaints are escalated to the
# chief warden once they have been open longer than this many hours.
ESCALATION_SLA_HOURS = {"HIGH": 24, "MEDIUM": 48, "LOW": 72}
DELIVERY_FEE_INR = 10
