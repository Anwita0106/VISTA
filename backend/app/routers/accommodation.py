"""FR06-FR08 hostel/block/room management and allocation, FR20 hostel map."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Block, Hostel, MapLocation, Room, User
from ..security import get_current_user, require_roles
from ..services import audit, not_found, notify

router = APIRouter(prefix="/api", tags=["accommodation"])
ADMIN = require_roles("ADMIN")
ALLOCATORS = require_roles("ADMIN", "WARDEN", "CHIEF_WARDEN")


class HostelIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    gender: Literal["BOYS", "GIRLS"]
    description: str = Field(default="", max_length=300)


class BlockIn(BaseModel):
    hostel_id: int
    name: str = Field(min_length=1, max_length=40)
    floors: int = Field(default=4, ge=1, le=30)


class RoomIn(BaseModel):
    block_id: int
    number: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    floor: int = Field(default=0, ge=0, le=30)
    capacity: int = Field(default=2, ge=1, le=6)
    room_type: Literal["AC", "NON_AC"] = "AC"


class AllocateIn(BaseModel):
    student_id: int
    room_id: int | None  # None = vacate


def room_out(r: Room) -> dict:
    return {
        "id": r.id, "number": r.number, "floor": r.floor, "capacity": r.capacity, "room_type": r.room_type,
        "block_id": r.block_id, "block": r.block.name, "hostel": r.block.hostel.name,
        "hostel_id": r.block.hostel_id, "occupied": len(r.occupants),
        "occupants": [{"id": o.id, "full_name": o.full_name, "reg_no": o.reg_no} for o in r.occupants],
    }


@router.get("/hostels")
def list_hostels(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for h in db.scalars(select(Hostel).order_by(Hostel.name)):
        rooms = [r for b in h.blocks for r in b.rooms]
        cap = sum(r.capacity for r in rooms)
        occ = sum(len(r.occupants) for r in rooms)
        out.append({
            "id": h.id, "name": h.name, "gender": h.gender, "description": h.description,
            "blocks": [{"id": b.id, "name": b.name, "floors": b.floors, "rooms": len(b.rooms)} for b in h.blocks],
            "capacity": cap, "occupied": occ,
        })
    return out


@router.post("/hostels", status_code=201)
def create_hostel(body: HostelIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    if db.scalar(select(Hostel).where(Hostel.name == body.name)):
        raise HTTPException(409, "A hostel with this name already exists")
    h = Hostel(**body.model_dump())
    db.add(h)
    db.flush()
    audit(db, user, "HOSTEL_CREATED", "hostel", h.id, h.name)
    db.commit()
    return {"id": h.id, **body.model_dump()}


@router.put("/hostels/{hostel_id}")
def update_hostel(hostel_id: int, body: HostelIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    h = db.get(Hostel, hostel_id)
    if not h:
        raise not_found("Hostel")
    for k, v in body.model_dump().items():
        setattr(h, k, v)
    audit(db, user, "HOSTEL_UPDATED", "hostel", h.id, h.name)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A hostel with this name already exists") from None
    return {"id": h.id, **body.model_dump()}


@router.post("/blocks", status_code=201)
def create_block(body: BlockIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    if not db.get(Hostel, body.hostel_id):
        raise not_found("Hostel")
    b = Block(**body.model_dump())
    db.add(b)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This block already exists in the hostel") from None
    audit(db, user, "BLOCK_CREATED", "block", b.id, b.name)
    db.commit()
    return {"id": b.id, **body.model_dump()}


@router.delete("/blocks/{block_id}")
def delete_block(block_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    b = db.get(Block, block_id)
    if not b:
        raise not_found("Block")
    if any(r.occupants for r in b.rooms):
        raise HTTPException(409, "Cannot delete a block that still has occupied rooms")
    db.delete(b)
    audit(db, user, "BLOCK_DELETED", "block", block_id, b.name)
    db.commit()
    return {"ok": True}


@router.get("/rooms")
def list_rooms(hostel_id: int | None = None, block_id: int | None = None, only_vacant: bool = False,
               _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Room).join(Block)
    if hostel_id:
        q = q.where(Block.hostel_id == hostel_id)
    if block_id:
        q = q.where(Room.block_id == block_id)
    rooms = [room_out(r) for r in db.scalars(q.order_by(Block.name, Room.number))]
    if only_vacant:
        rooms = [r for r in rooms if r["occupied"] < r["capacity"]]
    return rooms


@router.post("/rooms", status_code=201)
def create_room(body: RoomIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    if not db.get(Block, body.block_id):
        raise not_found("Block")
    r = Room(**body.model_dump())
    db.add(r)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This room number already exists in the block") from None
    audit(db, user, "ROOM_CREATED", "room", r.id, r.number)
    db.commit()
    db.refresh(r)
    return room_out(r)


@router.put("/rooms/{room_id}")
def update_room(room_id: int, body: RoomIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    r = db.get(Room, room_id)
    if not r:
        raise not_found("Room")
    if body.capacity < len(r.occupants):
        raise HTTPException(409, "Capacity cannot be lower than the current number of occupants")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit(db, user, "ROOM_UPDATED", "room", r.id, r.number)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This room number already exists in the block") from None
    db.refresh(r)
    return room_out(r)


@router.post("/rooms/allocate")
def allocate(body: AllocateIn, user: User = Depends(ALLOCATORS), db: Session = Depends(get_db)):
    student = db.get(User, body.student_id)
    if not student or student.role != "STUDENT":
        raise not_found("Student")
    if body.room_id is None:
        student.room_id = None
        audit(db, user, "ROOM_VACATED", "user", student.id)
        notify(db, student.id, "Room vacated", "Your room allocation was removed by the hostel office.")
        db.commit()
        return {"ok": True}
    room = db.scalar(select(Room).where(Room.id == body.room_id).with_for_update()) if db.bind.dialect.name == "postgresql" else db.get(Room, body.room_id)
    if not room:
        raise not_found("Room")
    if student.room_id == room.id:
        raise HTTPException(409, "Student is already allocated to this room")
    if len(room.occupants) >= room.capacity:
        raise HTTPException(409, "Room is full")
    gender_ok = {"BOYS": "MALE", "GIRLS": "FEMALE"}.get(room.block.hostel.gender)
    if student.gender and gender_ok and student.gender != gender_ok:
        raise HTTPException(400, "Student cannot be allocated to this hostel")
    student.room_id = room.id
    audit(db, user, "ROOM_ALLOCATED", "user", student.id, f"{room.block.hostel.name}/{room.block.name}-{room.number}")
    notify(db, student.id, "Room allocated",
           f"You have been allocated {room.block.hostel.name}, {room.block.name}-{room.number}.", "/profile")
    db.commit()
    db.refresh(room)
    return room_out(room)


@router.get("/map")
def hostel_map(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {"id": m.id, "name": m.name, "kind": m.kind, "x": m.x, "y": m.y, "description": m.description}
        for m in db.scalars(select(MapLocation).order_by(MapLocation.kind, MapLocation.name))
    ]
