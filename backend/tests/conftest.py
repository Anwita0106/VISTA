"""Shared pytest fixtures. Tests run against a dedicated database (TEST_DATABASE_URL),
which is dropped, recreated and seeded with the demo data at the start of the session."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://vista:vista_dev_pw@localhost:5432/vista_test")
os.environ["ESCALATION_CHECK_SECONDS"] = "0"
os.environ.setdefault("UPLOAD_DIR", str(ROOT / "backend" / ".test-uploads"))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import create_schema, seed  # noqa: E402

ACTUALS: dict[str, list[str]] = {}
PASSWORDS = {"admin": "Admin@123", "chief.warden": "Warden@123", "warden.lh": "Warden@123", "warden.mh": "Warden@123"}


def pytest_configure(config):
    config.addinivalue_line("markers", "case(id): links a test to a functional / non-functional test case ID")


@pytest.fixture(scope="session", autouse=True)
def database():
    create_schema(reset=True)
    with SessionLocal() as db:
        seed(db)
    yield
    out = ROOT / "test-results" / "pytest-actuals.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(ACTUALS, indent=2))


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


_tokens: dict[str, str] = {}


@pytest.fixture(scope="session")
def login(client):
    def _login(who: str, fresh: bool = False) -> dict:
        email = who if "@" in who else f"{who}@vista.demo"
        if fresh or email not in _tokens:
            local = email.split("@")[0]
            pw = PASSWORDS.get(local) or ("Staff@123" if local[:-1] in ("maint", "cleaning", "mess", "security") else "Student@123")
            r = client.post("/api/auth/login", json={"email": email, "password": pw})
            assert r.status_code == 200, r.text
            _tokens[email] = r.json()["access_token"]
        return {"Authorization": f"Bearer {_tokens[email]}"}

    return _login


@pytest.fixture
def record(request):
    """Record an observed result for the report: record('FT-01', '200 OK, role STUDENT')."""

    def _rec(case_id: str, text: str) -> None:
        ACTUALS.setdefault(case_id, []).append(text)

    return _rec


# ---- machine-readable per-test results (used by scripts/collect_results.py) ----
_RESULTS: list[dict] = []


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _RESULTS.append({
            "nodeid": report.nodeid,
            "cases": [m.args[0] for m in getattr(report, "_case_markers", [])],
            "outcome": report.outcome,
            "duration_s": round(report.duration, 3),
            "message": (report.longreprtext.splitlines()[-1][:500] if report.outcome == "failed" and report.longreprtext else ""),
        })


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    outcome.get_result()._case_markers = list(item.iter_markers("case"))


def pytest_sessionfinish(session, exitstatus):
    out = ROOT / "test-results" / "pytest-results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"tool": "pytest", "results": _RESULTS}, indent=2))
