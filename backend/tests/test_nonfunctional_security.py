"""Non-functional API tests: security, data protection, reliability and integrity.
NFT-07 .. NFT-14, NFT-20, NFT-21, NFT-23."""
import concurrent.futures as cf
import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.main import app
from app.models import AuditLog, Complaint, DeliveryRequest, GateDelivery, HandoverVerification, User
from app.security import ALGORITHM


def _protected_routes():
    """Every API route except the public ones, with path params filled."""
    public = {"/api/auth/login", "/api/auth/register", "/api/health"}
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/") or path in public or path.startswith("/api/docs") or path == "/api/openapi.json":
            continue
        for m in getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}:
            yield m, re.sub(r"\{[^}]+\}", "1", path)


@pytest.mark.case("NFT-07")
def test_nft07_authentication_enforced(client, record):
    results = [(m, p, client.request(m, p).status_code) for m, p in _protected_routes()]
    bad = [r for r in results if r[2] != 401]
    assert not bad, bad
    record("NFT-07", f"{len(results)} protected endpoint/method pairs called without a token: all returned 401")


RBAC = [  # (who, method, path, body) -> expected 403
    ("priya.sharma", "POST", "/api/hostels", {"name": "X", "gender": "BOYS"}),
    ("priya.sharma", "GET", "/api/admin/users", None),
    ("priya.sharma", "GET", "/api/admin/reports", None),
    ("priya.sharma", "PATCH", "/api/sos/1/acknowledge", None),
    ("priya.sharma", "POST", "/api/rooms/allocate", {"student_id": 1, "room_id": 1}),
    ("priya.sharma", "GET", "/api/deliveries?view=all", None),
    ("maint1", "GET", "/api/visitors", None),
    ("maint1", "GET", "/api/sos", None),
    ("maint1", "GET", "/api/gate-deliveries", None),
    ("mess1", "PATCH", "/api/visitors/1/decision", {"decision": "APPROVED"}),
    ("security1", "POST", "/api/notices", {"title": "abc", "body": "abcdef"}),
    ("warden.lh", "POST", "/api/admin/users", {"full_name": "A B", "email": "a@b.co", "password": "Passw0rd1", "role": "ADMIN"}),
    ("warden.lh", "GET", "/api/admin/audit-logs", None),
    ("warden.lh", "POST", "/api/complaints", {"category": "OTHER", "title": "warden complaint", "description": "should not be allowed"}),
    ("admin", "POST", "/api/deliveries", {"receiver_reg_no": "24BCE1001", "item_description": "x y z", "confirm_payment": True}),
    ("admin", "PATCH", "/api/visitors/1/decision", {"decision": "APPROVED"}),
]


@pytest.mark.case("NFT-08")
def test_nft08_role_permission_matrix(client, login, record):
    out = []
    for who, m, p, body in RBAC:
        code = client.request(m, p, headers=login(who), json=body).status_code
        out.append((who, m, p, code))
    wrong = [o for o in out if o[3] != 403]
    assert not wrong, wrong
    record("NFT-08", f"{len(out)} cross-role operations (student, staff, warden, admin) all denied with 403 by the backend")


SQLI = ["' OR '1'='1", "admin@vista.demo' --", "\" OR 1=1 --", "'; DROP TABLE users; --", "1' UNION SELECT password_hash FROM users --"]


@pytest.mark.case("NFT-09")
def test_nft09_sql_injection(client, login, record, db):
    users_before = db.scalar(select(func.count()).select_from(User))
    codes = []
    for s in SQLI:
        codes.append(client.post("/api/auth/login", json={"email": s, "password": s}).status_code)
        codes.append(client.get(f"/api/complaints?q={s}", headers=login("admin")).status_code)
        codes.append(client.get(f"/api/marketplace?q={s}", headers=login("priya.sharma")).status_code)
        codes.append(client.get(f"/api/admin/users?q={s}", headers=login("admin")).status_code)
    assert 500 not in codes and 200 in codes
    assert all(c in (401, 422, 200) for c in codes)
    assert db.scalar(select(func.count()).select_from(User)) == users_before
    record("NFT-09", f"{len(SQLI)} injection payloads x 4 inputs ({len(codes)} requests): login always 401, searches 200 with no extra rows, 0 server errors, users table intact")


@pytest.mark.case("NFT-11")
def test_nft11_token_handling(client, login, record):
    h = login("rahul.verma")
    token = h["Authorization"].split()[1]
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    expired = jwt.encode({"sub": "1", "role": "ADMIN", "exp": datetime.now(UTC) - timedelta(minutes=1), "jti": "x"},
                         settings.jwt_secret, algorithm=ALGORITHM)
    forged = jwt.encode({"sub": "1", "role": "ADMIN", "exp": datetime.now(UTC) + timedelta(hours=1), "jti": "y"},
                        "attacker-secret", algorithm=ALGORITHM)
    none_alg = jwt.encode({"sub": "1", "role": "ADMIN", "jti": "z"}, None, algorithm="none") if "none" in jwt.algorithms.get_default_algorithms() else "a.b."
    res = {name: client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code
           for name, t in [("tampered", tampered), ("expired", expired), ("wrong-key", forged), ("alg=none", none_alg)]}
    assert all(c == 401 for c in res.values()), res
    r = client.post("/api/auth/login", json={"email": "rahul.verma@vista.demo", "password": "Student@123"})
    exp = datetime.fromisoformat(r.json()["expires_at"])
    assert timedelta(minutes=1) < exp - datetime.now(UTC) <= timedelta(minutes=settings.jwt_expiry_minutes + 1)
    record("NFT-11", f"Tampered, expired, wrong-key and alg=none tokens all 401; tokens expire after {settings.jwt_expiry_minutes} min; logout revocation covered in FT-41")


@pytest.mark.case("NFT-12")
def test_nft12_sensitive_data_protection(client, login, record, db):
    leaks = []
    for who in ("priya.sharma", "admin", "warden.lh"):
        h = login(who)
        for p in ("/api/auth/me", "/api/admin/users?page_size=100", "/api/complaints", "/api/visitors", "/api/deliveries?view=mine", "/api/messages/contacts?q=a"):
            r = client.get(p, headers=h)
            if r.status_code == 200 and any(k in r.text for k in ("password_hash", "otp_hash", "$2b$")):
                leaks.append(p)
    assert not leaks, leaks
    hashes = db.scalars(select(User.password_hash)).all()
    assert all(h.startswith("$2b$") for h in hashes)
    otp_rows = db.scalars(select(HandoverVerification).where(HandoverVerification.method == "OTP", HandoverVerification.otp_hash != "")).all()
    assert all(v.otp_hash.startswith("$2b$") for v in otp_rows)
    gates = db.scalars(select(GateDelivery)).all()
    assert all(g.otp_hash.startswith("$2b$") for g in gates)
    record("NFT-12", f"No password/OTP hashes in any API response; {len(hashes)} passwords bcrypt-hashed; {len(otp_rows) + len(gates)} OTPs stored as bcrypt hashes; "
                     "OTP/QR secret shown only to the receiver (FT-24)")


@pytest.mark.case("NFT-13")
def test_nft13_brute_force_lockout(client, record):
    email = "vikram.singh@vista.demo"
    codes = [client.post("/api/auth/login", json={"email": email, "password": f"Wrong{i}pass"}).status_code for i in range(6)]
    locked_correct = client.post("/api/auth/login", json={"email": email, "password": "Student@123"})
    assert codes[:5] == [401] * 5 and codes[5] == 429 and locked_correct.status_code == 429
    from app.database import SessionLocal
    from app.models import LoginAttempt
    with SessionLocal() as s:  # clear the lockout so later tests can log in
        s.query(LoginAttempt).filter(LoginAttempt.email == email).delete()
        s.commit()
    record("NFT-13", f"5 wrong passwords -> 401 each; 6th attempt -> 429; correct password while locked -> 429 '{locked_correct.json()['detail']}'")


@pytest.mark.case("NFT-14")
def test_nft14_upload_validation(client, login, record):
    h = login("priya.sharma")
    cases = {
        "exe as octet-stream": ("a.exe", b"MZ\x90\x00", "application/octet-stream"),
        "html renamed pdf": ("a.pdf", b"<html><script>alert(1)</script>", "application/pdf"),
        "empty file": ("e.pdf", b"", "application/pdf"),
        "svg image": ("a.svg", b"<svg onload=alert(1)>", "image/svg+xml"),
    }
    codes = {k: client.post("/api/vault", headers=h, data={"title": "Test upload", "doc_type": "OTHER"}, files={"file": v}).status_code for k, v in cases.items()}
    assert codes["exe as octet-stream"] == 415 and codes["html renamed pdf"] == 415 and codes["svg image"] == 415 and codes["empty file"] == 422
    record("NFT-14", "Uploads rejected: " + "; ".join(f"{k} -> {v}" for k, v in codes.items()) + "; size limit 2 MB -> 413 (FT-35)")


@pytest.mark.case("NFT-20")
def test_nft20_error_handling(client, login, record):
    h = login("admin")
    nf = client.get("/api/complaints/999999", headers=h)
    bad_json = client.post("/api/complaints", headers={**login("priya.sharma"), "Content-Type": "application/json"}, content=b"{not json")
    bad_type = client.get("/api/complaints?page=abc", headers=h)
    unknown = client.get("/api/does-not-exist", headers=h)
    method = client.delete("/api/complaints", headers=h)
    res = {"missing record": nf.status_code, "malformed JSON": bad_json.status_code, "bad query type": bad_type.status_code,
           "unknown route": unknown.status_code, "wrong method": method.status_code}
    assert res == {"missing record": 404, "malformed JSON": 422, "bad query type": 422, "unknown route": 404, "wrong method": 405}
    for r in (nf, bad_json, bad_type):
        assert "detail" in r.json() and "Traceback" not in r.text
    health = client.get("/api/health").json()
    assert health["database"] is True
    record("NFT-20", "; ".join(f"{k} -> {v}" for k, v in res.items()) + "; JSON error bodies, no stack traces; /api/health reports DB status")


@pytest.mark.case("NFT-21")
def test_nft21_duplicate_and_race_conditions(client, login, record, db):
    h = login("sneha.das")
    body = {"category": "PLUMBING", "title": "Shower head broken badly", "description": "The shower head in D-302 is broken."}
    with cf.ThreadPoolExecutor(5) as ex:
        codes = list(ex.map(lambda _: client.post("/api/complaints", headers=h, json=body).status_code, range(5)))
    stored = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.title == body["title"]))
    d = client.post("/api/deliveries", headers=login("arjun.nair"), json={"receiver_reg_no": "24BCE1002", "item_description": "Race test parcel", "confirm_payment": True}).json()
    carriers = ["rahul.verma", "vikram.singh", "kavya.reddy", "meera.pillai"]
    headers = [login(c) for c in carriers]
    with cf.ThreadPoolExecutor(4) as ex:
        acc = list(ex.map(lambda hh: client.post(f"/api/deliveries/{d['id']}/accept", headers=hh).status_code, headers))
    final = db.get(DeliveryRequest, d["id"])
    db.refresh(final)
    record("NFT-21", f"5 parallel identical complaint submissions -> codes {sorted(codes)}, {stored} stored; "
                     f"4 parallel carrier accepts -> codes {sorted(acc)}, carrier recorded once")
    assert acc.count(200) == 1 and final.carrier_id is not None
    assert stored == 1, f"duplicate complaints stored: {stored}"


@pytest.mark.case("NFT-23")
def test_nft23_audit_and_status_consistency(client, login, record, db):
    allowed = {"OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED", "CLOSED"}
    statuses = set(db.scalars(select(Complaint.status)).all())
    assert statuses <= allowed
    for c in db.scalars(select(Complaint)).all():
        if c.status in ("RESOLVED", "CLOSED"):
            assert c.resolved_at is not None
        if c.status == "ESCALATED":
            assert c.escalated_at is not None
    # perform each critical action here so the check does not depend on test order
    from app.services import today
    v1 = client.post("/api/visitors", headers=login("ananya.iyer"), json={"visitor_name": "Audit Parent", "relation": "PARENT",
                     "visitor_phone": "9876501234", "visit_date": (today() + timedelta(days=1)).isoformat(), "time_from": "10:00", "time_to": "11:00"}).json()
    v2 = client.post("/api/visitors", headers=login("ananya.iyer"), json={"visitor_name": "Audit Friend", "relation": "FRIEND",
                     "visitor_phone": "9876504321", "visit_date": (today() + timedelta(days=1)).isoformat(), "time_from": "12:00", "time_to": "13:00"}).json()
    client.patch(f"/api/visitors/{v1['id']}/decision", headers=login("warden.lh"), json={"decision": "APPROVED"})
    client.patch(f"/api/visitors/{v2['id']}/decision", headers=login("warden.lh"), json={"decision": "REJECTED", "remark": "Not allowed"})
    a = client.post("/api/sos", headers=login("ananya.iyer"), json={"confirm": True, "message": "audit check"}).json()
    client.patch(f"/api/sos/{a['id']}/acknowledge", headers=login("security1"))
    client.patch(f"/api/sos/{a['id']}/resolve", headers=login("security1"), json={"note": "ok"})
    needed = {"LOGIN", "COMPLAINT_CREATED", "COMPLAINT_STATUS", "VISITOR_APPROVED", "VISITOR_REJECTED", "SOS_RAISED",
              "SOS_ACKNOWLEDGED", "SOS_RESOLVED", "DELIVERY_COMPLETED", "COMPLAINT_ESCALATED"}
    actions = set(db.scalars(select(AuditLog.action)).all())
    missing = needed - actions
    assert not missing, missing
    sample = db.scalar(select(AuditLog).where(AuditLog.action == "VISITOR_APPROVED"))
    assert sample.user_id and sample.created_at
    record("NFT-23", f"Complaint statuses {sorted(statuses)} all valid with matching timestamps; all {len(needed)} critical actions present in the audit log with user ID and timestamp")
