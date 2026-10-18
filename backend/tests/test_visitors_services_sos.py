"""Visitors (FT-14..FT-17), sick meal & cleaning (FT-18, FT-19), SOS (FT-20, FT-21)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Notification, SOSAlert, User
from app.services import today


def visitor(**kw):
    return {"visitor_name": "Anil Kapoor", "relation": "PARENT", "visitor_phone": "9876512345",
            "visit_date": (today() + timedelta(days=2)).isoformat(), "time_from": "10:00", "time_to": "11:30",
            "purpose": "Family visit", **kw}


@pytest.mark.case("FT-14")
def test_ft14_visitor_registration(client, login, record, db):
    r = client.post("/api/visitors", headers=login("kavya.reddy"), json=visitor())
    assert r.status_code == 201 and r.json()["status"] == "PENDING"
    n = db.scalars(select(Notification).where(Notification.title == "New visitor request")).all()
    assert len(n) >= 3  # chief warden + both wardens
    dup = client.post("/api/visitors", headers=login("kavya.reddy"), json=visitor())
    assert dup.status_code == 409
    record("FT-14", f"201 PENDING; {len(n)} warden notifications; duplicate same visitor/date -> 409")


@pytest.mark.case("FT-15")
def test_ft15_warden_approves(client, login, record, db):
    v = client.post("/api/visitors", headers=login("sneha.das"), json=visitor(visitor_name="Leela Das", visitor_phone="9876500111")).json()
    r = client.patch(f"/api/visitors/{v['id']}/decision", headers=login("warden.lh"), json={"decision": "APPROVED", "remark": "Carry ID"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    mine = client.get("/api/visitors", headers=login("sneha.das")).json()
    assert any(x["id"] == v["id"] and x["status"] == "APPROVED" for x in mine)
    student = db.scalar(select(User).where(User.email == "sneha.das@vista.demo"))
    assert db.scalar(select(Notification).where(Notification.user_id == student.id, Notification.title == "Visitor request approved"))
    again = client.patch(f"/api/visitors/{v['id']}/decision", headers=login("warden.lh"), json={"decision": "REJECTED", "remark": "changed mind"})
    assert again.status_code == 409
    record("FT-15", "Warden approval -> 200 APPROVED; student sees APPROVED and gets notification; deciding again -> 409")


@pytest.mark.case("FT-16")
def test_ft16_warden_rejects(client, login, record):
    v = client.post("/api/visitors", headers=login("vikram.singh"), json=visitor(visitor_name="Mohan Lal", relation="FRIEND", visitor_phone="9876500222")).json()
    no_reason = client.patch(f"/api/visitors/{v['id']}/decision", headers=login("warden.mh"), json={"decision": "REJECTED"})
    assert no_reason.status_code == 422
    r = client.patch(f"/api/visitors/{v['id']}/decision", headers=login("warden.mh"), json={"decision": "REJECTED", "remark": "Friends only on weekends"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED" and r.json()["decision_remark"] == "Friends only on weekends"
    record("FT-16", f"Reject without reason -> 422 '{no_reason.json()['detail']}'; with reason -> REJECTED, remark shown to student")


@pytest.mark.case("FT-17")
@pytest.mark.parametrize("label,data,expected", [
    ("past date", {"visit_date": "2020-01-01"}, 422),
    ("more than 30 days ahead", {"visit_date": (today() + timedelta(days=45)).isoformat()}, 422),
    ("malformed date", {"visit_date": "13/45/2026"}, 422),
    ("end before start", {"time_from": "15:00", "time_to": "14:00"}, 422),
    ("outside visiting hours", {"time_from": "21:00", "time_to": "22:00"}, 422),
    ("missing phone", {"visitor_phone": ""}, 422),
])
def test_ft17_invalid_visitor_dates(client, login, record, label, data, expected):
    r = client.post("/api/visitors", headers=login("kavya.reddy"), json=visitor(**data))
    assert r.status_code == expected
    record("FT-17", f"{label} -> {r.status_code} '{r.json()['detail'][:60]}'")


@pytest.mark.case("FT-18")
def test_ft18_sick_meal_request(client, login, record):
    h = login("priya.sharma")
    r = client.post("/api/service-requests", headers=h, json={"kind": "SICK_MEAL", "preferred_date": today().isoformat(), "meal_type": "DINNER", "diet_notes": "Soft food"})
    assert r.status_code == 201 and r.json()["status"] == "PENDING"
    hm = login("mess1")
    queue = client.get("/api/service-requests", headers=hm).json()
    assert any(x["id"] == r.json()["id"] for x in queue)
    acc = client.patch(f"/api/service-requests/{r.json()['id']}/status", headers=hm, json={"status": "ACCEPTED"})
    done = client.patch(f"/api/service-requests/{r.json()['id']}/status", headers=hm, json={"status": "COMPLETED"})
    cleaning_staff = client.patch(f"/api/service-requests/{r.json()['id']}/status", headers=login("cleaning1"), json={"status": "COMPLETED"})
    assert acc.status_code == 200 and done.json()["status"] == "COMPLETED" and cleaning_staff.status_code == 403
    record("FT-18", "Sick meal 201 PENDING -> in mess queue -> ACCEPTED -> COMPLETED by mess staff; cleaning staff -> 403")


@pytest.mark.case("FT-19")
def test_ft19_room_cleaning_request(client, login, record):
    h = login("ananya.iyer")
    body = {"kind": "CLEANING", "preferred_date": (today() + timedelta(days=1)).isoformat(), "preferred_slot": "MORNING"}
    r = client.post("/api/service-requests", headers=h, json=body)
    assert r.status_code == 201
    dup = client.post("/api/service-requests", headers=h, json=body)
    no_slot = client.post("/api/service-requests", headers=h, json={**body, "preferred_slot": ""})
    too_far = client.post("/api/service-requests", headers=h, json={**body, "preferred_date": (today() + timedelta(days=20)).isoformat()})
    assert (dup.status_code, no_slot.status_code, too_far.status_code) == (409, 422, 422)
    hc = login("cleaning1")
    assert any(x["id"] == r.json()["id"] for x in client.get("/api/service-requests", headers=hc).json())
    record("FT-19", "Cleaning 201 PENDING visible to cleaning staff; duplicate -> 409; missing slot -> 422; date > 7 days -> 422")


@pytest.mark.case("FT-20")
def test_ft20_sos_raise_ack_resolve(client, login, record, db):
    t0 = datetime.now()
    r = client.post("/api/sos", headers=login("kavya.reddy"), json={"message": "Feeling faint", "location": "H block corridor", "confirm": True})
    elapsed_ms = (datetime.now() - t0).total_seconds() * 1000
    assert r.status_code == 201
    a = r.json()
    assert a["status"] == "RAISED" and a["notification_delay_ms"] < 5000
    recipients = db.scalars(select(Notification).where(Notification.kind == "SOS", Notification.body.contains("H block corridor"))).all()
    roles = {db.get(User, n.user_id).role for n in recipients}
    assert {"WARDEN", "CHIEF_WARDEN", "STAFF"} <= roles
    hw = login("warden.lh")
    assert any(x["id"] == a["id"] for x in client.get("/api/sos", headers=hw).json())
    resolve_first = client.patch(f"/api/sos/{a['id']}/resolve", headers=hw, json={"note": "x"})
    ack = client.patch(f"/api/sos/{a['id']}/acknowledge", headers=hw)
    res = client.patch(f"/api/sos/{a['id']}/resolve", headers=hw, json={"note": "Taken to health centre"})
    assert resolve_first.status_code == 409 and ack.json()["status"] == "ACKNOWLEDGED" and res.json()["status"] == "RESOLVED"
    final = res.json()
    assert final["acknowledged_at"] and final["resolved_at"]
    record("FT-20", f"SOS RAISED, {len(recipients)} responders (warden, chief, security) notified in {a['notification_delay_ms']} ms "
                    f"(API round trip {elapsed_ms:.0f} ms); resolve-before-ack -> 409; ACKNOWLEDGED -> RESOLVED with timestamps")


@pytest.mark.case("FT-21")
def test_ft21_sos_requires_confirmation_and_role(client, login, record, db):
    before = db.query(SOSAlert).count()
    r = client.post("/api/sos", headers=login("arjun.nair"), json={"message": "", "confirm": False})
    staff_raise = client.post("/api/sos", headers=login("maint1"), json={"confirm": True})
    maint_ack = client.patch("/api/sos/1/acknowledge", headers=login("maint1"))
    assert r.status_code == 400 and staff_raise.status_code == 403 and maint_ack.status_code == 403
    assert db.query(SOSAlert).count() == before
    record("FT-21", f"Unconfirmed SOS -> 400 '{r.json()['detail']}', no alert stored; maintenance staff cannot acknowledge (403)")
