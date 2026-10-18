import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import type { Hostel, Paged, Room, User } from "../api/types";
import { Alert, Button, Card, Input, Modal, PageHeader, Select, Spinner, Table } from "../components/ui";
import { cx } from "../lib/cx";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { label } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

export default function AdminHostels() {
  const { user } = useAuth();
  const toast = useToast();
  const isAdmin = user?.role === "ADMIN";
  const hostels = useFetch<Hostel[]>("/api/hostels");
  const [hostelId, setHostelId] = useState<number | null>(null);
  const [blockId, setBlockId] = useState<number | "">("");
  const activeHostel = hostelId ?? hostels.data?.[0]?.id ?? null;
  const rooms = useFetch<Room[]>(activeHostel ? `/api/rooms${qs({ hostel_id: activeHostel, block_id: blockId || undefined })}` : null);
  const [modal, setModal] = useState<null | "hostel" | "block" | "room">(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [allocRoom, setAllocRoom] = useState<Room | null>(null);
  const [stuQ, setStuQ] = useState("");
  const dq = useDebounced(stuQ);
  const students = useFetch<Paged<User>>(allocRoom && dq.length >= 2 ? `/api/admin/users${qs({ role: "STUDENT", q: dq, page_size: 8 })}` : null);

  const current = hostels.data?.find((h) => h.id === activeHostel);

  async function save(e?: FormEvent) {
    e?.preventDefault();
    setErr(null);
    try {
      if (modal === "hostel") await api.post("/api/hostels", { name: form.name, gender: form.gender || "BOYS", description: form.description ?? "" });
      if (modal === "block") await api.post("/api/blocks", { hostel_id: activeHostel, name: form.name, floors: Number(form.floors || 4) });
      if (modal === "room") await api.post("/api/rooms", { block_id: Number(form.block_id), number: form.number, floor: Number(form.floor || 0), capacity: Number(form.capacity || 2), room_type: form.room_type || "AC" });
      toast("success", `${label(modal ?? "")} created`);
      setModal(null);
      setForm({});
      void hostels.reload();
      void rooms.reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  async function allocate(studentId: number | null, room: Room, vacateId?: number) {
    try {
      await api.post("/api/rooms/allocate", { student_id: vacateId ?? studentId, room_id: vacateId ? null : room.id });
      toast("success", vacateId ? "Student removed from room" : "Room allocated");
      setAllocRoom(null);
      setStuQ("");
      void rooms.reload();
      void hostels.reload();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Hostels & rooms"
        subtitle="Manage hostels, blocks and rooms, and allocate students to rooms."
        actions={isAdmin && (
          <>
            <Button variant="secondary" onClick={() => { setErr(null); setForm({}); setModal("hostel"); }}><Plus className="h-4 w-4" /> Hostel</Button>
            <Button variant="secondary" onClick={() => { setErr(null); setForm({}); setModal("block"); }} disabled={!activeHostel}><Plus className="h-4 w-4" /> Block</Button>
            <Button onClick={() => { setErr(null); setForm({ block_id: String(current?.blocks[0]?.id ?? "") }); setModal("room"); }} disabled={!current?.blocks.length}><Plus className="h-4 w-4" /> Room</Button>
          </>
        )}
      />
      {hostels.error && <Alert>{hostels.error}</Alert>}
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {hostels.data?.map((h) => (
          <button key={h.id} onClick={() => { setHostelId(h.id); setBlockId(""); }} className={cx("rounded-xl border bg-white p-4 text-left shadow-sm", h.id === activeHostel ? "border-navy-600 ring-2 ring-navy-100" : "border-slate-200 hover:border-navy-300")}>
            <p className="font-semibold text-slate-900">{h.name}</p>
            <p className="text-xs text-slate-500">{label(h.gender)} · {h.blocks.length} blocks</p>
            <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">{h.occupied}</span> / {h.capacity} beds</p>
          </button>
        ))}
      </div>
      <Card title={current ? `${current.name} – rooms` : "Rooms"} action={current && (
        <select aria-label="Block" value={blockId} onChange={(e) => setBlockId(e.target.value ? Number(e.target.value) : "")} className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All blocks</option>
          {current.blocks.map((b) => <option key={b.id} value={b.id}>Block {b.name}</option>)}
        </select>
      )}>
        {rooms.loading && !rooms.data ? <Spinner /> : (
          <Table head={["Room", "Type", "Occupancy", "Occupants", "Action"]} empty={!rooms.data?.length}>
            {rooms.data?.map((r) => (
              <tr key={r.id} data-testid="room-row">
                <td className="whitespace-nowrap px-5 py-3 font-medium">{r.block}-{r.number}<span className="block text-xs font-normal text-slate-500">Floor {r.floor}</span></td>
                <td className="px-5 py-3 text-slate-600">{label(r.room_type)}</td>
                <td className="px-5 py-3"><span className={r.occupied >= r.capacity ? "font-semibold text-red-700" : "text-emerald-700"}>{r.occupied}/{r.capacity}</span></td>
                <td className="px-5 py-3 text-slate-600">
                  {r.occupants.length ? r.occupants.map((o) => (
                    <span key={o.id} className="mr-2 inline-flex items-center gap-1 text-xs">{o.full_name}<button className="text-red-600" aria-label={`Remove ${o.full_name}`} onClick={() => void allocate(null, r, o.id)}>×</button></span>
                  )) : "—"}
                </td>
                <td className="px-5 py-3">{r.occupied < r.capacity && <Button size="sm" variant="secondary" onClick={() => { setAllocRoom(r); setStuQ(""); }}>Allocate</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Modal open={!!modal} onClose={() => setModal(null)} title={`Add ${modal ?? ""}`} footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={() => void save()}>Save</Button></>}>
        <form onSubmit={save} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          {modal === "hostel" && (<>
            <Input label="Hostel name" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Select label="Type" value={form.gender ?? "BOYS"} onChange={(e) => setForm({ ...form, gender: e.target.value })} options={["BOYS", "GIRLS"]} />
            <Input label="Description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </>)}
          {modal === "block" && (<>
            <p className="text-sm text-slate-600">Adding to {current?.name}</p>
            <Input label="Block name" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input label="Floors" type="number" value={form.floors ?? "4"} onChange={(e) => setForm({ ...form, floors: e.target.value })} />
          </>)}
          {modal === "room" && (<>
            <Select label="Block" value={form.block_id ?? ""} onChange={(e) => setForm({ ...form, block_id: e.target.value })} options={(current?.blocks ?? []).map((b) => ({ value: String(b.id), label: `Block ${b.name}` }))} />
            <div className="grid grid-cols-2 gap-4">
              <Input label="Room number" value={form.number ?? ""} onChange={(e) => setForm({ ...form, number: e.target.value })} />
              <Input label="Floor" type="number" value={form.floor ?? "1"} onChange={(e) => setForm({ ...form, floor: e.target.value })} />
              <Input label="Capacity" type="number" min={1} max={6} value={form.capacity ?? "2"} onChange={(e) => setForm({ ...form, capacity: e.target.value })} />
              <Select label="Type" value={form.room_type ?? "AC"} onChange={(e) => setForm({ ...form, room_type: e.target.value })} options={["AC", "NON_AC"]} />
            </div>
          </>)}
        </form>
      </Modal>
      <Modal open={!!allocRoom} onClose={() => setAllocRoom(null)} title={`Allocate ${allocRoom?.block}-${allocRoom?.number}`}>
        <Input label="Find student (name or reg. no.)" value={stuQ} onChange={(e) => setStuQ(e.target.value)} />
        <ul className="mt-3 divide-y divide-slate-100">
          {students.data?.items.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2 text-sm">
              <span>{s.full_name} <span className="text-xs text-slate-500">{s.reg_no} · {s.room ? `${s.room.block}-${s.room.number}` : "No room"}</span></span>
              <Button size="sm" onClick={() => allocRoom && void allocate(s.id, allocRoom)}>Allocate</Button>
            </li>
          ))}
        </ul>
      </Modal>
    </>
  );
}
