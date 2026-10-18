"""P2P inter-hostel delivery and gate deliveries – FT-22..FT-29."""
from datetime import UTC, datetime, timedelta

import pytest

from app.models import HandoverVerification
from app.services import today

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def create(client, login, sender="rahul.verma", receiver="24BCE1001", **kw):
    body = {"receiver_reg_no": receiver, "item_description": "Calculator and lab manual", "item_type": "PARCEL", "confirm_payment": True, **kw}
    return client.post("/api/deliveries", headers=login(sender), json=body)


def to_picked_up(client, login, carrier="arjun.nair", **kw):
    d = create(client, login, **kw).json()
    assert client.post(f"/api/deliveries/{d['id']}/accept", headers=login(carrier)).status_code == 200
    r = client.post(f"/api/deliveries/{d['id']}/pickup", headers=login(carrier))
    assert r.status_code == 200
    return r.json()


@pytest.mark.case("FT-22")
def test_ft22_create_delivery_request(client, login, record):
    r = create(client, login)
    assert r.status_code == 201
    d = r.json()
    assert d["fee"] == 10 and d["status"] == "OPEN" and d["payment"]["status"] == "PAID_DEMO"
    assert d["pickup_hostel"] != d["drop_hostel"]
    same_hostel = create(client, login, receiver="24BCE1007")  # Vikram is in the same hostel as Rahul
    no_pay = create(client, login, confirm_payment=False)
    unknown = create(client, login, receiver="99XYZ9999")
    assert same_hostel.status_code == 400 and no_pay.status_code == 400 and unknown.status_code == 404
    record("FT-22", f"201 {d['code']} OPEN, fee ₹{d['fee']}, demo receipt {d['payment']['receipt_no']}, {d['pickup_hostel']} -> {d['drop_hostel']}; "
                    f"same-hostel receiver -> 400; fee not confirmed -> 400; unknown receiver -> 404")


@pytest.mark.case("FT-23")
def test_ft23_carrier_acceptance(client, login, record):
    d = create(client, login).json()
    available = client.get("/api/deliveries?view=available", headers=login("vikram.singh")).json()
    assert any(x["id"] == d["id"] for x in available)
    own = client.post(f"/api/deliveries/{d['id']}/accept", headers=login("rahul.verma"))
    recv = client.post(f"/api/deliveries/{d['id']}/accept", headers=login("priya.sharma"))
    ok = client.post(f"/api/deliveries/{d['id']}/accept", headers=login("vikram.singh"))
    second = client.post(f"/api/deliveries/{d['id']}/accept", headers=login("meera.pillai"))
    assert own.status_code == 400 and recv.status_code == 400
    assert ok.status_code == 200 and ok.json()["status"] == "ACCEPTED" and ok.json()["carrier"]["full_name"] == "Vikram Singh"
    assert second.status_code == 409
    record("FT-23", f"Listed as available; sender/receiver accept -> 400; Vikram accepts -> ACCEPTED; second carrier -> 409 '{second.json()['detail']}'")


@pytest.mark.case("FT-24")
def test_ft24_valid_otp_completes_delivery(client, login, record):
    d = to_picked_up(client, login)
    as_carrier = client.get(f"/api/deliveries/{d['id']}", headers=login("arjun.nair")).json()
    as_receiver = client.get(f"/api/deliveries/{d['id']}", headers=login("priya.sharma")).json()
    assert "otp" not in as_carrier and "qr_token" not in as_carrier
    otp = as_receiver["otp"]
    assert otp and len(otp) == 6
    r = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("arjun.nair"), json={"otp": otp})
    assert r.status_code == 200 and r.json()["status"] == "DELIVERED" and r.json()["delivered_at"]
    after = client.get(f"/api/deliveries/{d['id']}", headers=login("priya.sharma")).json()
    assert after["otp"] is None
    record("FT-24", "OTP visible only to receiver (hidden from carrier); carrier entered it -> 200 DELIVERED; OTP cleared after use")


@pytest.mark.case("FT-25")
def test_ft25_invalid_otp(client, login, record):
    d = to_picked_up(client, login, carrier="vikram.singh", receiver="24BCE1002")
    real = client.get(f"/api/deliveries/{d['id']}", headers=login("ananya.iyer")).json()["otp"]
    wrong = "000000" if real != "000000" else "111111"
    r = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("vikram.singh"), json={"otp": wrong})
    fmt = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("vikram.singh"), json={"otp": "12ab"})
    not_carrier = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("rahul.verma"), json={"otp": real})
    assert r.status_code == 400 and "2 attempt(s) left" in r.json()["detail"]
    assert fmt.status_code == 422 and not_carrier.status_code == 403
    state = client.get(f"/api/deliveries/{d['id']}", headers=login("vikram.singh")).json()
    assert state["status"] == "PICKED_UP"
    record("FT-25", f"Wrong OTP -> 400 '{r.json()['detail']}'; non-numeric -> 422; sender entering OTP -> 403; status stays PICKED_UP")


@pytest.mark.case("FT-26")
def test_ft26_otp_lockout_and_expiry(client, login, record, db):
    d = to_picked_up(client, login, carrier="meera.pillai", sender="arjun.nair", receiver="24BCE1006")
    real = client.get(f"/api/deliveries/{d['id']}", headers=login("sneha.das")).json()["otp"]
    wrong = "000000" if real != "000000" else "111111"
    codes = [client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("meera.pillai"), json={"otp": wrong}).status_code for _ in range(3)]
    locked = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("meera.pillai"), json={"otp": real})
    assert codes == [400, 400, 423] and locked.status_code == 410
    # new OTP, then force expiry
    assert client.post(f"/api/deliveries/{d['id']}/otp/resend", headers=login("meera.pillai")).status_code == 200
    v = db.query(HandoverVerification).filter_by(delivery_id=d["id"], status="PENDING").one()
    new_otp = v.otp_plain_for_receiver
    v.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    expired = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("meera.pillai"), json={"otp": new_otp})
    assert expired.status_code == 410
    client.post(f"/api/deliveries/{d['id']}/otp/resend", headers=login("meera.pillai"))
    limit = client.post(f"/api/deliveries/{d['id']}/otp/resend", headers=login("meera.pillai"))
    assert limit.status_code in (409, 429)
    record("FT-26", f"3 wrong OTPs -> 400, 400, 423 (locked); correct OTP after lock -> 410; expired OTP -> 410 '{expired.json()['detail']}'; "
                    f"OTP re-issue capped at 3 (4th -> {limit.status_code})")


@pytest.mark.case("FT-27")
def test_ft27_invalid_delivery_transitions(client, login, record):
    d = create(client, login, sender="kavya.reddy", receiver="24BEC1003").json()
    early_otp = client.post(f"/api/deliveries/{d['id']}/verify-otp", headers=login("arjun.nair"), json={"otp": "123456"})
    early_pickup = client.post(f"/api/deliveries/{d['id']}/pickup", headers=login("arjun.nair"))
    client.post(f"/api/deliveries/{d['id']}/accept", headers=login("arjun.nair"))
    cancel_after_accept = client.post(f"/api/deliveries/{d['id']}/cancel", headers=login("kavya.reddy"))
    fail_before_pickup = client.post(f"/api/deliveries/{d['id']}/fail", headers=login("arjun.nair"), json={"reason": "Receiver not found"})
    assert early_otp.status_code == 403 and early_pickup.status_code == 403
    assert cancel_after_accept.status_code == 409 and fail_before_pickup.status_code == 409
    record("FT-27", f"Non-carrier verify/pickup -> 403; cancel after ACCEPTED -> 409 '{cancel_after_accept.json()['detail']}'; fail before pickup -> 409")


@pytest.mark.case("FT-28")
def test_ft28_qr_photo_verification(client, login, record):
    d = to_picked_up(client, login, carrier="vikram.singh", sender="arjun.nair", receiver="24BIT1005")
    token = client.get(f"/api/deliveries/{d['id']}", headers=login("kavya.reddy")).json()["qr_token"]
    good = {"qr_token": token, "receiver_name": "Kavya Reddy", "receiver_reg_no": "24BIT1005", "receiver_room": "203", "receiver_block": "H"}
    bad = client.post(f"/api/deliveries/{d['id']}/verify-qr", headers=login("vikram.singh"), data={**good, "receiver_room": "999"},
                      files={"photo": ("parcel.png", PNG, "image/png")})
    fake = client.post(f"/api/deliveries/{d['id']}/verify-qr", headers=login("vikram.singh"), data={**good, "qr_token": "forged"},
                       files={"photo": ("parcel.png", PNG, "image/png")})
    not_img = client.post(f"/api/deliveries/{d['id']}/verify-qr", headers=login("vikram.singh"), data=good,
                          files={"photo": ("parcel.png", b"not an image", "image/png")})
    ok = client.post(f"/api/deliveries/{d['id']}/verify-qr", headers=login("vikram.singh"), data=good,
                     files={"photo": ("parcel.png", PNG, "image/png")})
    assert bad.status_code == 400 and "room number" in bad.json()["detail"]
    assert fake.status_code == 400 and "QR code" in fake.json()["detail"] and not_img.status_code == 415
    assert ok.status_code == 200 and ok.json()["status"] == "DELIVERED"
    assert ok.json()["verifications"][-1]["photo"] is not None
    record("FT-28", f"Wrong room -> 400 '{bad.json()['detail']}'; forged QR -> 400; fake image -> 415; correct QR + photo + details -> DELIVERED with photo stored")


@pytest.mark.case("FT-29")
def test_ft29_gate_parcel_reservation(client, login, record):
    h = login("priya.sharma")
    body = {"kind": "PARCEL", "vendor": "BlueDart", "courier_name": "Ravi Kumar", "courier_phone": "9812345678", "order_ref": "BD123",
            "expected_date": today().isoformat(), "expected_time": "18:00", "gate": "Ladies Hostel Gate"}
    no_courier = client.post("/api/gate-deliveries", headers=h, json={**body, "courier_name": ""})
    r = client.post("/api/gate-deliveries", headers=h, json=body)
    assert no_courier.status_code == 422 and r.status_code == 201
    g = r.json()
    otp = g["otp"]
    hs = login("security1")
    early = client.post(f"/api/gate-deliveries/{g['id']}/collect", headers=hs, json={"otp": otp})
    arrived = client.patch(f"/api/gate-deliveries/{g['id']}/arrived", headers=hs)
    wrong = client.post(f"/api/gate-deliveries/{g['id']}/collect", headers=hs, json={"otp": "000000" if otp != "000000" else "111111"})
    maint = client.post(f"/api/gate-deliveries/{g['id']}/collect", headers=login("maint1"), json={"otp": otp})
    ok = client.post(f"/api/gate-deliveries/{g['id']}/collect", headers=hs, json={"otp": otp})
    assert early.status_code == 409 and arrived.json()["status"] == "AT_GATE" and wrong.status_code == 400 and maint.status_code == 403
    assert ok.status_code == 200 and ok.json()["status"] == "COLLECTED" and "otp" not in ok.json()
    record("FT-29", f"Missing courier name -> 422; {g['code']} BOOKED with courier '{g['courier_name']}'; collect before arrival -> 409; "
                    "security marks AT_GATE; wrong OTP -> 400; maintenance staff -> 403; correct OTP -> COLLECTED")
