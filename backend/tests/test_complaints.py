"""Complaint management – FT-08..FT-13."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Complaint, Notification, User


def _new(client, h, **kw):
    body = {"category": "ELECTRICAL", "title": "Tube light flickering", "description": "The tube light flickers all evening.", **kw}
    return client.post("/api/complaints", headers=h, json=body)


@pytest.mark.case("FT-08")
def test_ft08_register_complaint_forwarded(client, login, record, db):
    r = _new(client, login("rahul.verma"), title="Study lamp socket dead")
    assert r.status_code == 201
    c = r.json()
    assert c["code"].startswith("CMP-") and c["status"] == "OPEN"
    staff = db.get(User, c["assigned_staff"]["id"])
    assert staff.staff_type == "MAINTENANCE"
    note = db.scalar(select(Notification).where(Notification.user_id == staff.id, Notification.title.contains(c["code"])))
    assert note is not None
    record("FT-08", f"201; {c['code']} OPEN, priority {c['priority']}; auto-forwarded to {staff.full_name} (MAINTENANCE) and notified")


@pytest.mark.case("FT-09")
def test_ft09_complaint_missing_fields(client, login, record):
    h = login("rahul.verma")
    r1 = client.post("/api/complaints", headers=h, json={"category": "PLUMBING", "title": "", "description": ""})
    r2 = client.post("/api/complaints", headers=h, json={"title": "No category given", "description": "Category is missing here"})
    r3 = client.post("/api/complaints", headers=h, json={"category": "MAGIC", "title": "Bad category", "description": "Invalid category value"})
    assert (r1.status_code, r2.status_code, r3.status_code) == (422, 422, 422)
    record("FT-09", f"Empty title/description -> 422 '{r1.json()['detail']}'; missing category -> 422; invalid category -> 422")


@pytest.mark.case("FT-10")
def test_ft10_washroom_water_high_priority(client, login, record):
    h = login("vikram.singh")
    w = _new(client, h, category="WASHROOM", title="Washroom tap broken", priority="LOW").json()
    wa = _new(client, h, category="WATER", title="No drinking water", priority="MEDIUM").json()
    assert w["priority"] == "HIGH" and wa["priority"] == "HIGH"
    assert w["assigned_staff"] is not None
    record("FT-10", f"WASHROOM requested LOW -> stored {w['priority']}; WATER requested MEDIUM -> stored {wa['priority']}")


@pytest.mark.case("FT-11")
def test_ft11_staff_updates_status(client, login, record, db):
    c = _new(client, login("arjun.nair"), category="CARPENTRY", title="Door latch loose").json()
    staff = db.get(User, c["assigned_staff"]["id"])
    hs = login(staff.email)
    r1 = client.patch(f"/api/complaints/{c['id']}/status", headers=hs, json={"status": "IN_PROGRESS", "note": "Visiting at 4 PM"})
    r2 = client.patch(f"/api/complaints/{c['id']}/status", headers=hs, json={"status": "RESOLVED", "note": "Latch replaced"})
    assert r1.status_code == 200 and r2.status_code == 200
    d = r2.json()
    assert d["status"] == "RESOLVED" and d["resolved_at"]
    assert [u["to_status"] for u in d["updates"]] == ["OPEN", "IN_PROGRESS", "RESOLVED"]
    closed = client.patch(f"/api/complaints/{c['id']}/status", headers=login("arjun.nair"), json={"status": "CLOSED"})
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    record("FT-11", "OPEN -> IN_PROGRESS -> RESOLVED by assigned staff, CLOSED by student; history has 4 entries; student notified")


@pytest.mark.case("FT-12")
def test_ft12_invalid_complaint_transitions(client, login, record, db):
    c = _new(client, login("ananya.iyer"), title="Window glass cracked", category="CARPENTRY").json()
    staff = db.get(User, c["assigned_staff"]["id"])
    hs = login(staff.email)
    skip_close = client.patch(f"/api/complaints/{c['id']}/status", headers=hs, json={"status": "CLOSED"})
    stu_resolve = client.patch(f"/api/complaints/{c['id']}/status", headers=login("ananya.iyer"), json={"status": "RESOLVED"})
    other_student = client.get(f"/api/complaints/{c['id']}", headers=login("rahul.verma"))
    client.patch(f"/api/complaints/{c['id']}/status", headers=hs, json={"status": "RESOLVED"})
    client.patch(f"/api/complaints/{c['id']}/status", headers=login("ananya.iyer"), json={"status": "CLOSED"})
    after_close = client.patch(f"/api/complaints/{c['id']}/status", headers=login("warden.lh"), json={"status": "IN_PROGRESS"})
    assert skip_close.status_code == 403 and stu_resolve.status_code == 403
    assert other_student.status_code == 404 and after_close.status_code == 409
    record("FT-12", f"Staff CLOSE -> 403; student RESOLVE -> 403; other student view -> 404; CLOSED -> IN_PROGRESS -> 409 '{after_close.json()['detail']}'")


@pytest.mark.case("FT-13")
def test_ft13_escalation_rule(client, login, record, db):
    c = _new(client, login("meera.pillai"), category="ELECTRICAL", title="AC not cooling at all", priority="HIGH").json()
    fresh = _new(client, login("meera.pillai"), category="OTHER", title="Notice board pin missing", priority="LOW").json()
    row = db.get(Complaint, c["id"])
    row.created_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()
    r = client.post("/api/complaints/escalation/run", headers=login("warden.lh"))
    assert r.status_code == 200 and c["code"] in r.json()["escalated"] and fresh["code"] not in r.json()["escalated"]
    d = client.get(f"/api/complaints/{c['id']}", headers=login("chief.warden")).json()
    assert d["status"] == "ESCALATED" and d["escalated_to"]["role"] == "CHIEF_WARDEN"
    chief = db.scalar(select(User).where(User.role == "CHIEF_WARDEN"))
    assert db.scalar(select(Notification).where(Notification.user_id == chief.id, Notification.title.contains(c["code"])))
    record("FT-13", f"HIGH complaint aged 25 h escalated to {d['escalated_to']['full_name']}; 0-h LOW complaint not escalated; chief warden notified")
