"""Authentication, registration, RBAC and profile – FT-01..FT-07, FT-31, FT-41."""
import pytest


@pytest.mark.case("FT-01")
def test_ft01_valid_login(client, record):
    r = client.post("/api/auth/login", json={"email": "priya.sharma@vista.demo", "password": "Student@123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["role"] == "STUDENT"
    assert "password_hash" not in body["user"]
    record("FT-01", f"HTTP {r.status_code}; JWT issued; role={body['user']['role']}; room={body['user']['room']['block']}-{body['user']['room']['number']}")


@pytest.mark.case("FT-02")
def test_ft02_invalid_login(client, record):
    r = client.post("/api/auth/login", json={"email": "rahul.verma@vista.demo", "password": "WrongPass1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"
    r2 = client.post("/api/auth/login", json={"email": "nobody@vista.demo", "password": "Whatever1"})
    assert r2.status_code == 401 and r2.json()["detail"] == r.json()["detail"]  # no user enumeration
    record("FT-02", f"HTTP 401 '{r.json()['detail']}' for wrong password and for unknown email (same message)")


@pytest.mark.case("FT-03")
def test_ft03_role_based_dashboard(client, login, record):
    s = client.get("/api/dashboard", headers=login("priya.sharma")).json()
    w = client.get("/api/dashboard", headers=login("warden.lh")).json()
    assert s["role"] == "STUDENT" and set(s["cards"]) == {"open_complaints", "pending_visitors", "active_services", "active_deliveries"}
    assert w["role"] == "WARDEN" and "active_sos" in w["cards"] and "complaints_by_category" in w
    record("FT-03", f"Student dashboard cards={sorted(s['cards'])}; warden dashboard has {len(w['cards'])} management cards incl. active_sos")


@pytest.mark.case("FT-04")
def test_ft04_student_blocked_from_admin(client, login, record):
    h = login("priya.sharma")
    codes = {
        "POST /api/admin/users": client.post("/api/admin/users", headers=h, json={"full_name": "X Y", "email": "x@y.com", "password": "Passw0rd1", "role": "ADMIN"}).status_code,
        "GET /api/admin/audit-logs": client.get("/api/admin/audit-logs", headers=h).status_code,
        "PATCH /api/visitors/1/decision": client.patch("/api/visitors/1/decision", headers=h, json={"decision": "APPROVED"}).status_code,
        "POST /api/notices": client.post("/api/notices", headers=h, json={"title": "Hack", "body": "Not allowed"}).status_code,
    }
    assert all(c == 403 for c in codes.values()), codes
    record("FT-04", "Student received 403 Forbidden on " + ", ".join(codes))


@pytest.mark.case("FT-05")
def test_ft05_student_registration(client, record):
    body = {"full_name": "Test Student", "email": "new.student@vista.demo", "password": "Newpass123", "reg_no": "25BCE9001",
            "phone": "9123456780", "programme": "B.Tech CSE", "year_of_study": 1, "gender": "FEMALE"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201 and r.json()["role"] == "STUDENT"
    dup = client.post("/api/auth/register", json={**body, "email": "other@vista.demo"})
    assert dup.status_code == 409
    ok = client.post("/api/auth/login", json={"email": "new.student@vista.demo", "password": "Newpass123"})
    assert ok.status_code == 200
    record("FT-05", f"201 Created (role STUDENT); duplicate reg no -> 409 '{dup.json()['detail']}'; new account can log in")


@pytest.mark.case("FT-06")
@pytest.mark.parametrize("field,value", [("reg_no", "ABC123"), ("phone", "12345"), ("password", "short"), ("email", "not-an-email"), ("full_name", "<script>")])
def test_ft06_registration_validation(client, record, field, value):
    body = {"full_name": "Valid Name", "email": "v@vista.demo", "password": "Valid1234", "reg_no": "25BCE9002",
            "phone": "9123456781", "year_of_study": 1, "gender": "MALE", field: value}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 422
    record("FT-06", f"{field}='{value}' -> 422 '{r.json()['detail'][:70]}'")


@pytest.mark.case("FT-07")
def test_ft07_profile_update_persists(client, login, record):
    h = login("kavya.reddy")
    r = client.put("/api/profile", headers=h, json={"phone": "9000011111", "pref_sleep": "LATE", "looking_for_roommate": True})
    assert r.status_code == 200
    again = client.get("/api/profile", headers=h).json()
    assert again["phone"] == "9000011111" and again["pref_sleep"] == "LATE" and again["looking_for_roommate"] is True
    bad = client.put("/api/profile", headers=h, json={"phone": "123"})
    assert bad.status_code == 422
    record("FT-07", "Profile saved and re-read: phone=9000011111, pref_sleep=LATE; invalid phone -> 422")


@pytest.mark.case("FT-31")
def test_ft31_unauthorized_admin_actions(client, login, record):
    w = login("warden.lh")
    s = login("security1")
    res = {
        "warden deactivates user": client.patch("/api/admin/users/5/active", headers=w, json={"is_active": False}).status_code,
        "warden creates hostel": client.post("/api/hostels", headers=w, json={"name": "Rogue", "gender": "BOYS"}).status_code,
        "security approves visitor": client.patch("/api/visitors/1/decision", headers=s, json={"decision": "APPROVED"}).status_code,
        "maintenance views audit log": client.get("/api/admin/audit-logs", headers=login("maint1")).status_code,
    }
    assert all(v == 403 for v in res.values()), res
    record("FT-31", "403 for: " + "; ".join(res))


@pytest.mark.case("FT-41")
def test_ft41_logout_revokes_token(client, login, record):
    h = login("meera.pillai", fresh=True)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    after = client.get("/api/auth/me", headers=h)
    assert after.status_code == 401
    login("meera.pillai", fresh=True)
    record("FT-41", f"Logout 200; reusing the same token -> {after.status_code} '{after.json()['detail']}'")
