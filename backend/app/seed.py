"""Reproducible database initialisation and fictional demo data.

Usage:  python -m app.seed            # create tables (if missing) and seed if empty
        python -m app.seed --reset    # DROP all tables, recreate and seed
"""
import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import (
    AuditLog,
    Block,
    Complaint,
    ComplaintUpdate,
    DeliveryRequest,
    HandoverVerification,
    Hostel,
    LostFoundItem,
    MapLocation,
    MarketplaceItem,
    MessFeedback,
    Notice,
    Notification,
    Payment,
    Room,
    ServiceRequest,
    SharedNote,
    User,
    VisitorRequest,
)
from .security import hash_password
from .services import today

DEMO_PASSWORDS = {"ADMIN": "Admin@123", "WARDEN": "Warden@123", "CHIEF_WARDEN": "Warden@123",
                  "STAFF": "Staff@123", "STUDENT": "Student@123"}

HOSTELS = [
    ("Men's Hostel North", "BOYS", ["Q", "R"], "Blocks Q and R near the north gate"),
    ("Men's Hostel South", "BOYS", ["K", "L"], "Blocks K and L beside the sports complex"),
    ("Ladies Hostel East", "GIRLS", ["G", "H"], "Blocks G and H facing the central lawn"),
    ("Ladies Hostel West", "GIRLS", ["C", "D"], "Blocks C and D next to the West mess"),
]

STUDENTS = [  # name, email, reg_no, gender, hostel index, block, room, programme, prefs
    ("Priya Sharma", "priya.sharma", "24BCE1001", "FEMALE", 2, "G", "101", "B.Tech CSE", ("EARLY", "QUIET", "VEG")),
    ("Ananya Iyer", "ananya.iyer", "24BCE1002", "FEMALE", 3, "C", "204", "B.Tech CSE", ("LATE", "GROUP", "NON_VEG")),
    ("Rahul Verma", "rahul.verma", "24BEC1003", "MALE", 0, "Q", "101", "B.Tech ECE", ("LATE", "QUIET", "NON_VEG")),
    ("Arjun Nair", "arjun.nair", "24BME1004", "MALE", 1, "K", "102", "B.Tech Mech", ("EARLY", "GROUP", "VEG")),
    ("Kavya Reddy", "kavya.reddy", "24BIT1005", "FEMALE", 2, "H", "203", "B.Tech IT", ("EARLY", "QUIET", "VEG")),
    ("Sneha Das", "sneha.das", "24BCE1006", "FEMALE", 3, "D", "302", "B.Tech CSE", ("EARLY", "QUIET", "VEG")),
    ("Vikram Singh", "vikram.singh", "24BCE1007", "MALE", 0, "R", "201", "B.Tech CSE", ("LATE", "GROUP", "NON_VEG")),
    ("Meera Pillai", "meera.pillai", "24BBT1008", "FEMALE", 2, "G", "102", "B.Tech Biotech", ("LATE", "QUIET", "VEG")),
]

FIRST_M = ["Aditya", "Karthik", "Siddharth", "Nikhil", "Rohan", "Varun", "Harsh", "Akash", "Pranav", "Dev"]
FIRST_F = ["Ishita", "Diya", "Riya", "Pooja", "Nandini", "Shreya", "Aditi", "Tanvi", "Lavanya", "Harini"]
LAST = ["Kumar", "Gupta", "Menon", "Rao", "Joshi", "Patel", "Bose", "Kulkarni", "Chatterjee", "Saxena"]


def create_schema(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        print("Database already contains data – skipping seed (use --reset to start over).")
        return
    random.seed(42)
    now = datetime.now(UTC)
    hashes = {role: hash_password(pw) for role, pw in DEMO_PASSWORDS.items()}

    hostels: list[Hostel] = []
    blocks: dict[tuple[int, str], Block] = {}
    rooms: dict[tuple[int, str, str], Room] = {}
    for hi, (name, gender, block_names, desc) in enumerate(HOSTELS):
        h = Hostel(name=name, gender=gender, description=desc)
        db.add(h)
        hostels.append(h)
        for bn in block_names:
            b = Block(hostel=h, name=bn, floors=3)
            db.add(b)
            blocks[(hi, bn)] = b
            for floor in (1, 2, 3):
                for n in range(1, 5):
                    num = f"{floor}{n:02d}"
                    r = Room(block=b, number=num, floor=floor, capacity=2 if n <= 2 else 3,
                             room_type="AC" if n % 2 else "NON_AC")
                    db.add(r)
                    rooms[(hi, bn, num)] = r
    db.flush()

    def staff(name, email, role, staff_type=None, hostel=None, phone="9876500000"):
        u = User(full_name=name, email=f"{email}@vista.demo", password_hash=hashes[role], role=role,
                 staff_type=staff_type, hostel_id=hostel.id if hostel else None, phone=phone)
        db.add(u)
        return u

    admin = staff("Sanjana Krishnan", "admin", "ADMIN", phone="9876500001")
    chief = staff("Dr. Lakshmi Narayanan", "chief.warden", "CHIEF_WARDEN", phone="9876500002")
    warden_lh = staff("Mrs. Revathi Subramanian", "warden.lh", "WARDEN", hostel=hostels[2], phone="9876500003")
    warden_mh = staff("Mr. Suresh Babu", "warden.mh", "WARDEN", hostel=hostels[0], phone="9876500004")
    maint1 = staff("Ramesh Electricals", "maint1", "STAFF", "MAINTENANCE", phone="9876500005")
    maint2 = staff("Ganesh Plumbing", "maint2", "STAFF", "MAINTENANCE", phone="9876500006")
    cleaning = staff("Lakshmi Housekeeping", "cleaning1", "STAFF", "CLEANING", phone="9876500007")
    mess = staff("Murugan Mess Supervisor", "mess1", "STAFF", "MESS", phone="9876500008")
    staff("Joseph Security Desk", "security1", "STAFF", "SECURITY", phone="9876500009")
    db.flush()

    students: list[User] = []
    for i, (name, email, reg, gender, hi, bn, num, prog, prefs) in enumerate(STUDENTS):
        u = User(full_name=name, email=f"{email}@vista.demo", password_hash=hashes["STUDENT"], role="STUDENT",
                 reg_no=reg, gender=gender, programme=prog, year_of_study=2 + (i % 2), phone=f"98450{10000 + i}",
                 room=rooms[(hi, bn, num)], pref_sleep=prefs[0], pref_study=prefs[1], pref_food=prefs[2],
                 looking_for_roommate=(i in (5, 6, 7)))
        db.add(u)
        students.append(u)
    # additional fictional residents so dashboards show realistic occupancy
    serial = 2000
    for hi, (_, gender, block_names, _) in enumerate(HOSTELS):
        g = "MALE" if gender == "BOYS" else "FEMALE"
        firsts = FIRST_M if g == "MALE" else FIRST_F
        for k in range(12):
            serial += 1
            bn = block_names[k % 2]
            num = f"{(k % 3) + 1}{(k % 4) + 1:02d}"
            room = rooms[(hi, bn, num)]
            if len([s for s in students if s.room is room]) >= room.capacity:
                continue
            nm = f"{firsts[k % 10]} {LAST[(k + hi) % 10]}"
            u = User(full_name=nm, email=f"student{serial}@vista.demo", password_hash=hashes["STUDENT"], role="STUDENT",
                     reg_no=f"23BCE{serial}", gender=g, programme="B.Tech CSE", year_of_study=3,
                     phone=f"97{serial:08d}", room=room, looking_for_roommate=(k % 5 == 0),
                     pref_sleep=random.choice(["EARLY", "LATE"]), pref_study=random.choice(["QUIET", "GROUP"]),
                     pref_food=random.choice(["VEG", "NON_VEG"]))
            db.add(u)
            students.append(u)
    db.flush()
    priya, ananya, rahul, arjun, kavya, sneha, vikram, meera = students[:8]

    # ---------------- complaints
    def complaint(stu, cat, prio, title, desc, status, staff_u, age_h, notes=()):
        c = Complaint(code="TMP", student=stu, category=cat, priority=prio, title=title, description=desc,
                      location=f"{stu.room.block.name}-{stu.room.number}", status=status, assigned_staff=staff_u,
                      created_at=now - timedelta(hours=age_h))
        db.add(c)
        db.flush()
        c.code = f"CMP-{c.id:05d}"
        db.add(ComplaintUpdate(complaint=c, actor_id=stu.id, to_status="OPEN", note="Complaint registered",
                               created_at=c.created_at))
        for frm, to, note, actor in notes:
            db.add(ComplaintUpdate(complaint=c, actor_id=actor.id if actor else None, from_status=frm, to_status=to,
                                   note=note, created_at=c.created_at + timedelta(hours=2)))
        if status in ("RESOLVED", "CLOSED"):
            c.resolved_at = c.created_at + timedelta(hours=6)
        if status == "ESCALATED":
            c.escalated_to = chief
            c.escalated_at = c.created_at + timedelta(hours=24)
        return c

    complaint(priya, "ELECTRICAL", "MEDIUM", "Ceiling fan not working", "The ceiling fan in my room stopped working since last night.",
              "IN_PROGRESS", maint1, 5, [("OPEN", "IN_PROGRESS", "Electrician will visit by 5 PM", maint1)])
    complaint(priya, "WATER", "HIGH", "No hot water in G block bathroom", "The geyser on the first floor is not heating water.",
              "OPEN", maint2, 2)
    complaint(rahul, "PLUMBING", "MEDIUM", "Leaking tap in washroom", "Tap near the wash basin leaks continuously.",
              "RESOLVED", maint2, 30, [("OPEN", "RESOLVED", "Washer replaced", maint2)])
    complaint(arjun, "CARPENTRY", "LOW", "Broken cupboard hinge", "The left door of the wardrobe has a broken hinge.",
              "CLOSED", maint1, 80, [("OPEN", "RESOLVED", "Hinge replaced", maint1), ("RESOLVED", "CLOSED", "Confirmed", arjun)])
    complaint(ananya, "WASHROOM", "HIGH", "Washroom drain blocked", "The common washroom drain on the second floor is blocked.",
              "ESCALATED", cleaning, 30, [("OPEN", "ESCALATED", "Auto-escalated: unresolved for more than 24 h", None)])
    complaint(kavya, "ELECTRICAL", "HIGH", "Power socket sparking", "The socket near the study table sparks when a charger is plugged in.",
              "OPEN", maint1, 1)
    complaint(vikram, "OTHER", "LOW", "Window mesh torn", "Mosquito mesh on the window is torn.", "OPEN", maint2, 10)

    # ---------------- visitors
    d0 = today()
    for stu, vname, rel, phone, days, status, remark in [
        (priya, "Rajesh Sharma", "PARENT", "9811122233", 2, "PENDING", ""),
        (rahul, "Sunita Verma", "PARENT", "9822233344", 1, "APPROVED", "Approved – carry ID proof"),
        (ananya, "Karan Iyer", "SIBLING", "9833344455", 3, "PENDING", ""),
        (arjun, "Ravi Teja", "FRIEND", "9844455566", 1, "REJECTED", "Friends allowed only on weekends"),
    ]:
        v = VisitorRequest(student=stu, visitor_name=vname, relation=rel, visitor_phone=phone,
                           visit_date=(d0 + timedelta(days=days)).isoformat(), time_from="10:00", time_to="12:00",
                           purpose="Family visit" if rel != "FRIEND" else "Project discussion", status=status,
                           decision_remark=remark)
        if status != "PENDING":
            v.decided_by = warden_mh if stu.gender == "MALE" else warden_lh
            v.decided_at = now - timedelta(hours=3)
        db.add(v)

    # ---------------- service requests
    db.add(ServiceRequest(kind="SICK_MEAL", student=kavya, preferred_date=d0.isoformat(), meal_type="LUNCH",
                          diet_notes="Light food – fever", status="ACCEPTED", assigned_staff=mess))
    db.add(ServiceRequest(kind="CLEANING", student=priya, preferred_date=(d0 + timedelta(days=1)).isoformat(),
                          preferred_slot="MORNING", status="PENDING"))
    db.add(ServiceRequest(kind="CLEANING", student=rahul, preferred_date=d0.isoformat(), preferred_slot="AFTERNOON",
                          status="COMPLETED", assigned_staff=cleaning))

    # ---------------- notices
    for title, body, cat, h, author, age in [
        ("Water supply interruption – Sunday", "Water supply in Ladies Hostel East will be off from 10 AM to 1 PM on Sunday for tank cleaning.",
         "MAINTENANCE", hostels[2], warden_lh, 20),
        ("Mess menu revision", "The revised mess menu for this month is now available at the mess counters.", "MESS", None, chief, 48),
        ("Hostel day celebrations", "Hostel day will be celebrated on the 25th. Volunteers can register with the block representatives.",
         "EVENT", None, admin, 72),
        ("Night entry timings", "Students must return to their hostels by 9:30 PM. Late entries need prior approval.", "GENERAL",
         None, chief, 120),
    ]:
        db.add(Notice(title=title, body=body, category=cat, hostel=h, author=author, created_at=now - timedelta(hours=age)))

    # ---------------- community
    db.add(LostFoundItem(kind="LOST", title="Blue water bottle", description="Milton steel bottle with stickers",
                         location="Central library, 2nd floor", item_date=(d0 - timedelta(days=1)).isoformat(),
                         contact="Room G-101", reporter=priya))
    db.add(LostFoundItem(kind="FOUND", title="Scientific calculator", description="Casio fx-991EX found in the lab",
                         location="SJT 3rd floor lab", item_date=d0.isoformat(), contact="Room Q-101", reporter=rahul))
    db.add(LostFoundItem(kind="FOUND", title="ID card holder", description="Black lanyard with no card",
                         location="Mess entrance", item_date=(d0 - timedelta(days=3)).isoformat(), contact="Security desk",
                         reporter=arjun, status="CLAIMED"))
    for seller, title, cat, cond, price in [
        (rahul, "Engineering Mathematics – B.S. Grewal", "BOOKS", "GOOD", 350),
        (ananya, "Study table lamp", "ELECTRONICS", "LIKE_NEW", 400),
        (arjun, "Cycle lock", "OTHER", "FAIR", 100),
        (meera, "Data Structures notes binder", "BOOKS", "GOOD", 0),
    ]:
        db.add(MarketplaceItem(seller=seller, title=title, description=f"{title}. Contact via VISTA messages.",
                               category=cat, condition=cond, price=price))
    db.add(SharedNote(author=priya, title="Operating Systems – Unit 3 summary", subject="Operating Systems",
                      content="Process scheduling: FCFS, SJF, Round Robin, Priority. Key formulas: turnaround = completion - arrival; waiting = turnaround - burst."))
    db.add(SharedNote(author=rahul, title="Software Engineering – testing types", subject="Software Engineering",
                      content="Unit, integration, system and acceptance testing. Functional vs non-functional. Black-box vs white-box."))
    for stu, meal, f, s in [(priya, "LUNCH", 4, 4), (rahul, "DINNER", 3, 4), (ananya, "BREAKFAST", 2, 3), (arjun, "LUNCH", 5, 4)]:
        db.add(MessFeedback(student=stu, meal=meal, food_rating=f, service_rating=s, comments="",
                            feedback_date=(d0 - timedelta(days=1)).isoformat()))

    # ---------------- a completed historic P2P delivery
    d = DeliveryRequest(code="TMP", sender=rahul, receiver=priya, carrier=arjun, item_description="Lab record notebook",
                        item_type="DOCUMENT", pickup_hostel=hostels[0], drop_hostel=hostels[2], pickup_point="Q-101",
                        fee=10, status="DELIVERED", qr_token="seeded-historic-token-not-usable",
                        created_at=now - timedelta(days=2), accepted_at=now - timedelta(days=2, hours=-1),
                        picked_up_at=now - timedelta(days=2, hours=-2), delivered_at=now - timedelta(days=2, hours=-3))
    db.add(d)
    db.flush()
    d.code = f"DLV-{d.id:05d}"
    db.add(Payment(delivery=d, amount=10, receipt_no=f"RCPT-DEMO-{d.id:06d}"))
    db.add(HandoverVerification(delivery=d, method="OTP", otp_hash="", status="VERIFIED", attempts=1,
                                verified_at=d.delivered_at))

    # ---------------- map
    for name, kind, x, y, desc in [
        ("Men's Hostel North (Q, R)", "BLOCK", 20, 18, "Boys' hostel blocks Q and R"),
        ("Men's Hostel South (K, L)", "BLOCK", 22, 70, "Boys' hostel blocks K and L"),
        ("Ladies Hostel East (G, H)", "BLOCK", 78, 30, "Girls' hostel blocks G and H"),
        ("Ladies Hostel West (C, D)", "BLOCK", 70, 75, "Girls' hostel blocks C and D"),
        ("Central Mess", "MESS", 48, 45, "Breakfast 7–9, lunch 12–2, dinner 7:30–9:30"),
        ("West Mess", "MESS", 58, 85, "Serves Ladies Hostel West"),
        ("Main Gate", "GATE", 50, 96, "Visitor entry and food delivery pickup"),
        ("Men's Hostel Gate", "GATE", 6, 45, "Security desk 24x7"),
        ("Ladies Hostel Gate", "GATE", 93, 52, "Security desk 24x7"),
        ("Health Centre", "SERVICE", 38, 25, "Open 24x7 – emergency care"),
        ("Laundry", "SERVICE", 40, 72, "Drop-off 8 AM – 6 PM"),
        ("Maintenance Office", "SERVICE", 60, 15, "Electrical, plumbing and carpentry"),
    ]:
        db.add(MapLocation(name=name, kind=kind, x=x, y=y, description=desc))

    db.add(Notification(user_id=priya.id, title="Welcome to VISTA", body="Explore services from the sidebar.", link="/"))
    db.add(AuditLog(user_id=admin.id, action="SEED", entity="system", detail="Demo data loaded"))
    db.commit()
    print(f"Seeded {len(students)} students, 9 staff/admin users, {len(rooms)} rooms in {len(hostels)} hostels.")


def main() -> None:
    reset = "--reset" in sys.argv
    create_schema(reset=reset)
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
