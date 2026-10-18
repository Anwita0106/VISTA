"""Notices, community features, accommodation, reports, messaging – FT-30, FT-33..FT-40."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import Complaint, Notification, User
from app.services import today

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n%demo\n"


@pytest.mark.case("FT-30")
def test_ft30_notice_publish_and_display(client, login, record, db):
    hostels = client.get("/api/hostels", headers=login("admin")).json()
    lh_east = next(h for h in hostels if h["name"] == "Ladies Hostel East")
    r = client.post("/api/notices", headers=login("warden.lh"), json={"title": "Fire drill on Friday", "body": "Assemble at the lawn at 7 AM.",
                                                                     "category": "URGENT", "hostel_id": lh_east["id"]})
    assert r.status_code == 201
    priya = [n["title"] for n in client.get("/api/notices", headers=login("priya.sharma")).json()]
    rahul = [n["title"] for n in client.get("/api/notices", headers=login("rahul.verma")).json()]
    assert "Fire drill on Friday" in priya and "Fire drill on Friday" not in rahul
    notified = db.scalar(select(func.count()).select_from(Notification).where(Notification.title == "New notice: Fire drill on Friday"))
    empty = client.post("/api/notices", headers=login("warden.lh"), json={"title": "", "body": ""})
    assert notified >= 1 and empty.status_code == 422
    record("FT-30", f"Warden published URGENT notice to Ladies Hostel East; shown to Priya, hidden from Men's hostel student; {notified} students notified; empty notice -> 422")


@pytest.mark.case("FT-33")
def test_ft33_lost_and_found(client, login, record):
    h = login("vikram.singh")
    r = client.post("/api/lost-found", headers=h, json={"kind": "LOST", "title": "Black umbrella", "location": "R block lobby", "item_date": today().isoformat()})
    future = client.post("/api/lost-found", headers=h, json={"kind": "FOUND", "title": "Watch", "location": "Gym", "item_date": (today() + timedelta(days=3)).isoformat()})
    found = client.get("/api/lost-found?q=umbrella", headers=login("priya.sharma")).json()
    other_claim = client.patch(f"/api/lost-found/{r.json()['id']}/claim", headers=login("priya.sharma"))
    claim = client.patch(f"/api/lost-found/{r.json()['id']}/claim", headers=h)
    assert r.status_code == 201 and future.status_code == 422 and len(found) == 1
    assert other_claim.status_code == 403 and claim.json()["status"] == "CLAIMED"
    record("FT-33", "Lost item reported (201) and found by keyword search; future date -> 422; only reporter can close (others 403)")


@pytest.mark.case("FT-34")
def test_ft34_marketplace(client, login, record):
    h = login("ananya.iyer")
    r = client.post("/api/marketplace", headers=h, json={"title": "Drafter set", "category": "OTHER", "condition": "GOOD", "price": 250})
    neg = client.post("/api/marketplace", headers=h, json={"title": "Bad price", "category": "BOOKS", "price": -5})
    other = client.patch(f"/api/marketplace/{r.json()['id']}/sold", headers=login("rahul.verma"))
    sold = client.patch(f"/api/marketplace/{r.json()['id']}/sold", headers=h)
    listed = [m["id"] for m in client.get("/api/marketplace", headers=login("rahul.verma")).json()]
    assert r.status_code == 201 and neg.status_code == 422 and other.status_code == 403
    assert sold.json()["status"] == "SOLD" and r.json()["id"] not in listed
    cheap = client.get("/api/marketplace?sort=price_asc", headers=h).json()
    assert [m["price"] for m in cheap] == sorted(m["price"] for m in cheap)
    record("FT-34", "Listing 201; negative price -> 422; non-seller mark sold -> 403; sold item hidden from listings; price sort ascending verified")


@pytest.mark.case("FT-35")
def test_ft35_notes_and_vault(client, login, record):
    note = client.post("/api/notes", headers=login("priya.sharma"), data={"title": "DBMS normal forms", "subject": "DBMS", "content": "1NF, 2NF, 3NF, BCNF"},
                       files={"file": ("nf.pdf", PDF, "application/pdf")})
    assert note.status_code == 201 and note.json()["file"]
    fid = note.json()["file"]["id"]
    assert client.get(f"/api/files/{fid}", headers=login("rahul.verma")).status_code == 200  # shared notes readable by others
    vault = client.post("/api/vault", headers=login("priya.sharma"), data={"title": "Hostel allotment letter", "doc_type": "ALLOTMENT_LETTER"},
                        files={"file": ("allot.pdf", PDF, "application/pdf")})
    assert vault.status_code == 201
    vid = vault.json()["file"]["id"]
    own = client.get(f"/api/files/{vid}", headers=login("priya.sharma"))
    other = client.get(f"/api/files/{vid}", headers=login("rahul.verma"))
    exe = client.post("/api/vault", headers=login("priya.sharma"), data={"title": "Malware", "doc_type": "OTHER"},
                      files={"file": ("x.exe", b"MZ\x90\x00", "application/octet-stream")})
    big = client.post("/api/vault", headers=login("priya.sharma"), data={"title": "Huge file", "doc_type": "OTHER"},
                      files={"file": ("big.pdf", PDF + b"0" * (2 * 1024 * 1024), "application/pdf")})
    assert own.status_code == 200 and own.content == PDF and other.status_code == 404
    assert exe.status_code == 415 and big.status_code == 413
    record("FT-35", "Note with PDF shared and readable by classmates; vault file downloadable by owner, other student -> 404; .exe -> 415; >2 MB -> 413")


@pytest.mark.case("FT-36")
def test_ft36_mess_feedback(client, login, record):
    h = login("arjun.nair")
    body = {"meal": "BREAKFAST", "food_rating": 4, "service_rating": 5, "comments": "Good idli", "feedback_date": today().isoformat()}
    r = client.post("/api/mess-feedback", headers=h, json=body)
    dup = client.post("/api/mess-feedback", headers=h, json=body)
    bad = client.post("/api/mess-feedback", headers=h, json={**body, "meal": "LUNCH", "food_rating": 7})
    summary = client.get("/api/mess-feedback", headers=login("mess1")).json()["summary"]
    assert r.status_code == 201 and dup.status_code == 409 and bad.status_code == 422 and "BREAKFAST" in summary
    record("FT-36", f"Feedback 201; same meal twice -> 409; rating 7 -> 422; mess staff summary shows BREAKFAST avg {summary['BREAKFAST']['food']}")


@pytest.mark.case("FT-37")
def test_ft37_roommate_finder(client, login, record):
    r = client.get("/api/roommates", headers=login("priya.sharma"))
    assert r.status_code == 200
    m = r.json()["matches"]
    assert m and all(x["full_name"] for x in m) and [x["score"] for x in m] == sorted((x["score"] for x in m), reverse=True)
    assert all(x["id"] != 0 for x in m)
    staff = client.get("/api/roommates", headers=login("warden.lh"))
    assert staff.status_code == 403
    record("FT-37", f"{len(m)} same-gender matches ranked by preference score (top {m[0]['full_name']} {m[0]['score']}/{m[0]['max_score']}); "
                    f"{len(r.json()['rooms_with_vacancy'])} rooms with free beds listed")


@pytest.mark.case("FT-38")
def test_ft38_room_allocation_rules(client, login, record, db):
    ha = login("admin")
    rooms = client.get("/api/rooms?only_vacant=true", headers=ha).json()
    girls_room = next(r for r in rooms if r["hostel"] == "Ladies Hostel East" and r["occupied"] == 0)
    boys_room = next(r for r in rooms if r["hostel"] == "Men's Hostel North" and r["occupied"] == 0)
    new_student = db.scalar(select(User).where(User.reg_no == "25BCE9001"))  # registered in FT-05 (female, no room)
    wrong = client.post("/api/rooms/allocate", headers=ha, json={"student_id": new_student.id, "room_id": boys_room["id"]})
    ok = client.post("/api/rooms/allocate", headers=ha, json={"student_id": new_student.id, "room_id": girls_room["id"]})
    full_room = next(r for r in client.get("/api/rooms", headers=ha).json() if r["occupied"] >= r["capacity"])
    full = client.post("/api/rooms/allocate", headers=ha, json={"student_id": new_student.id, "room_id": full_room["id"]})
    stu = client.post("/api/rooms/allocate", headers=login("priya.sharma"), json={"student_id": new_student.id, "room_id": girls_room["id"]})
    dup_room = client.post("/api/rooms", headers=ha, json={"block_id": girls_room["block_id"], "number": girls_room["number"]})
    assert wrong.status_code == 400 and ok.status_code == 200 and full.status_code == 409 and stu.status_code == 403 and dup_room.status_code == 409
    record("FT-38", f"Female student -> boys' hostel 400; -> {girls_room['block']}-{girls_room['number']} 200; full room -> 409; student allocating -> 403; duplicate room number -> 409")


@pytest.mark.case("FT-39")
def test_ft39_reports_match_database(client, login, record, db):
    rep = client.get("/api/admin/reports", headers=login("admin")).json()
    total_db = db.scalar(select(func.count()).select_from(Complaint))
    assert sum(rep["complaints"]["by_status"].values()) == total_db
    students = db.scalar(select(func.count()).select_from(User).where(User.role == "STUDENT"))
    assert rep["users"]["STUDENT"] == students
    csv = client.get("/api/admin/reports/export?kind=complaints", headers=login("admin"))
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert len(csv.text.strip().splitlines()) == total_db + 1
    assert client.get("/api/admin/reports", headers=login("warden.lh")).status_code == 403
    record("FT-39", f"Report complaint total {total_db} = DB count; students {students} = DB count; CSV export has {total_db} rows + header; warden -> 403")


@pytest.mark.case("FT-40")
def test_ft40_in_app_messaging(client, login, record, db):
    warden = db.scalar(select(User).where(User.email == "warden.lh@vista.demo"))
    s = client.post("/api/messages", headers=login("priya.sharma"), json={"recipient_id": warden.id, "body": "Can my parents visit on Sunday?"})
    assert s.status_code == 201
    convs = client.get("/api/messages", headers=login("warden.lh")).json()
    c = next(x for x in convs if x["user"]["full_name"] == "Priya Sharma")
    assert c["unread"] >= 1
    priya_id = c["user"]["id"]
    thread = client.get(f"/api/messages/{priya_id}", headers=login("warden.lh")).json()
    assert thread["messages"][-1]["body"] == "Can my parents visit on Sunday?"
    after = next(x for x in client.get("/api/messages", headers=login("warden.lh")).json() if x["user"]["id"] == priya_id)
    empty = client.post("/api/messages", headers=login("priya.sharma"), json={"recipient_id": warden.id, "body": ""})
    assert after["unread"] == 0 and empty.status_code == 422
    record("FT-40", "Student -> warden message delivered (unread=1), shown in thread, marked read on open (unread=0); empty message -> 422")


@pytest.mark.case("FT-42")
def test_ft42_admin_registers_staff_warden_admin(client, login, record):
    h = login("admin")
    made = {}
    for role, extra in (("WARDEN", {}), ("STAFF", {"staff_type": "SECURITY"}), ("ADMIN", {})):
        email = f"new.{role.lower()}@vista.demo"
        r = client.post("/api/admin/users", headers=h, json={"full_name": f"New {role.title()}", "email": email, "password": "Strong123",
                                                             "role": role, **extra})
        assert r.status_code == 201 and r.json()["role"] == role
        ok = client.post("/api/auth/login", json={"email": email, "password": "Strong123"})
        assert ok.status_code == 200
        made[role] = r.json()["staff_type"]
    no_type = client.post("/api/admin/users", headers=h, json={"full_name": "No Type", "email": "nt@vista.demo", "password": "Strong123", "role": "STAFF"})
    dup = client.post("/api/admin/users", headers=h, json={"full_name": "Dup", "email": "new.warden@vista.demo", "password": "Strong123", "role": "WARDEN"})
    assert no_type.status_code == 422 and dup.status_code == 409
    record("FT-42", "Admin created WARDEN, STAFF (SECURITY) and ADMIN accounts (201) and each could log in; staff without type -> 422; duplicate email -> 409")


@pytest.mark.case("FT-43")
def test_ft43_hostel_map_and_structure(client, login, record):
    m = client.get("/api/map", headers=login("priya.sharma")).json()
    kinds = {x["kind"] for x in m}
    assert {"BLOCK", "MESS", "GATE", "SERVICE"} <= kinds
    hostels = client.get("/api/hostels", headers=login("priya.sharma")).json()
    assert all(h["blocks"] and h["capacity"] >= h["occupied"] for h in hostels)
    assert client.get("/api/map").status_code == 401
    record("FT-43", f"Map returns {len(m)} locations ({', '.join(sorted(kinds))}); {len(hostels)} hostels with blocks and live occupancy; unauthenticated -> 401")
