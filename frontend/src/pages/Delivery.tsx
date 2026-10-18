import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Delivery as D, GateDelivery } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Table, Tabs } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, fmtDateTime, inr, label, todayISO } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { REG_NO_RE } from "../lib/validation";

type TabKey = "mine" | "available" | "carrying" | "gate" | "all";
const FEE = 10;

function NewDelivery({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ receiver_reg_no: "", item_description: "", item_type: "PARCEL", pickup_point: "" });
  const [agree, setAgree] = useState(false);
  const [err, setErr] = useState<Record<string, string>>({});
  const [apiErr, setApiErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const er: Record<string, string> = {};
    if (!REG_NO_RE.test(f.receiver_reg_no.trim().toUpperCase())) er.receiver_reg_no = "Enter a valid registration number (e.g. 24BCE1001)";
    if (f.item_description.trim().length < 3) er.item_description = "Describe the item";
    if (!agree) er.agree = `Confirm the ${inr(FEE)} delivery fee`;
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    setApiErr(null);
    try {
      const d = await api.post<D>("/api/deliveries", { ...f, receiver_reg_no: f.receiver_reg_no.trim().toUpperCase(), confirm_payment: true });
      toast("success", `${d.code} posted. Demo receipt ${d.payment?.receipt_no}`);
      onClose();
      nav(`/delivery/${d.id}`);
    } catch (e2) {
      setApiErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open={open} onClose={onClose} title="Send an item to another hostel" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={() => void submit()} loading={busy} data-testid="post-delivery">Pay {inr(FEE)} &amp; post request</Button></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {apiErr && <Alert>{apiErr}</Alert>}
        <Input label="Receiver registration number" name="receiver_reg_no" value={f.receiver_reg_no} onChange={(e) => setF({ ...f, receiver_reg_no: e.target.value })} error={err.receiver_reg_no} placeholder="24BCE1001" required />
        <Input label="Item description" name="item_description" value={f.item_description} onChange={(e) => setF({ ...f, item_description: e.target.value })} error={err.item_description} placeholder="e.g. Lab record notebook" required />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Item type" name="item_type" value={f.item_type} onChange={(e) => setF({ ...f, item_type: e.target.value })} options={["PARCEL", "FOOD", "DOCUMENT", "OTHER"]} />
          <Input label="Pickup point" name="pickup_point" value={f.pickup_point} onChange={(e) => setF({ ...f, pickup_point: e.target.value })} hint="Default: your room" />
        </div>
        <div className="rounded-lg border border-navy-100 bg-navy-50 p-3 text-sm text-navy-900">
          <div className="flex justify-between font-medium"><span>Delivery fee (fixed)</span><span data-testid="delivery-fee">{inr(FEE)}</span></div>
          <p className="mt-1 text-xs text-navy-700">Demo payment only – no real money is charged. In production this would go through a payment gateway.</p>
        </div>
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" name="agree" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 h-4 w-4 rounded border-slate-300" />
          I confirm the {inr(FEE)} delivery fee (demo wallet).
        </label>
        {err.agree && <p className="text-xs text-red-700" role="alert">{err.agree}</p>}
      </form>
    </Modal>
  );
}

function GateBooking({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ kind: "FOOD", vendor: "", courier_name: "", courier_phone: "", order_ref: "", expected_date: todayISO(), expected_time: "19:30", gate: "Main Gate" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (f.vendor.trim().length < 2 || f.courier_name.trim().length < 2) return setErr("Vendor and courier / delivery-partner name are required");
    setBusy(true);
    setErr(null);
    try {
      const g = await api.post<GateDelivery>("/api/gate-deliveries", f);
      toast("success", `${g.code} booked. Your gate OTP is ${g.otp}`);
      setF({ ...f, vendor: "", courier_name: "", courier_phone: "", order_ref: "" });
      onDone();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      {err && <Alert>{err}</Alert>}
      <Select label="Type" name="kind" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} options={[{ value: "FOOD", label: "Food delivery" }, { value: "PARCEL", label: "Parcel / courier" }]} />
      <Input label="Vendor / platform" name="vendor" value={f.vendor} onChange={(e) => setF({ ...f, vendor: e.target.value })} placeholder="e.g. Campus Bakery" required />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Courier / delivery partner name" name="courier_name" value={f.courier_name} onChange={(e) => setF({ ...f, courier_name: e.target.value })} required />
        <Input label="Courier mobile" name="courier_phone" value={f.courier_phone} onChange={(e) => setF({ ...f, courier_phone: e.target.value })} />
      </div>
      <Input label="Order reference" name="order_ref" value={f.order_ref} onChange={(e) => setF({ ...f, order_ref: e.target.value })} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Input label="Date" type="date" name="expected_date" min={todayISO()} max={todayISO(7)} value={f.expected_date} onChange={(e) => setF({ ...f, expected_date: e.target.value })} />
        <Input label="Time" type="time" name="expected_time" value={f.expected_time} onChange={(e) => setF({ ...f, expected_time: e.target.value })} />
        <Select label="Gate" name="gate" value={f.gate} onChange={(e) => setF({ ...f, gate: e.target.value })} options={[{ value: "Main Gate", label: "Main Gate" }, { value: "Ladies Hostel Gate", label: "Ladies Hostel Gate" }, { value: "Men's Hostel Gate", label: "Men's Hostel Gate" }]} />
      </div>
      <Button type="submit" loading={busy} className="w-full">Book gate delivery</Button>
    </form>
  );
}

function DeliveryTable({ items, view }: { items: D[]; view: TabKey }) {
  if (!items.length) return <EmptyState title={view === "available" ? "No open requests right now" : "No deliveries yet"} message={view === "available" ? "Check back when you are heading to another hostel." : undefined} />;
  return (
    <Table head={["Code", "Item", "Route", view === "mine" ? "Your role" : "Sender", "Status", "Posted"]}>
      {items.map((d) => (
        <tr key={d.id} className="hover:bg-slate-50" data-testid="delivery-row">
          <td className="whitespace-nowrap px-5 py-3 font-mono text-xs"><Link className="font-semibold text-navy-700 hover:underline" to={`/delivery/${d.id}`}>{d.code}</Link></td>
          <td className="px-5 py-3"><p className="font-medium text-slate-800">{d.item_description}</p><p className="text-xs text-slate-500">{label(d.item_type)} · {inr(d.fee)}</p></td>
          <td className="px-5 py-3 text-slate-600">{d.pickup_hostel} → {d.drop_hostel}</td>
          <td className="px-5 py-3 text-slate-600">{view === "mine" ? label(d.my_role) : d.sender.full_name}</td>
          <td className="px-5 py-3"><Badge value={d.status} /></td>
          <td className="whitespace-nowrap px-5 py-3 text-slate-500">{fmtDateTime(d.created_at)}</td>
        </tr>
      ))}
    </Table>
  );
}

export default function Delivery() {
  const { user } = useAuth();
  const toast = useToast();
  const isStudent = user?.role === "STUDENT";
  const [tab, setTab] = useState<TabKey>(isStudent ? "mine" : "all");
  const [newOpen, setNewOpen] = useState(false);
  const p2p = useFetch<D[]>(tab !== "gate" ? `/api/deliveries?view=${tab}` : null);
  const gate = useFetch<GateDelivery[]>(tab === "gate" ? "/api/gate-deliveries" : null);
  if (!user) return null;
  const tabs: { value: TabKey; label: string }[] = isStudent
    ? [{ value: "mine", label: "My deliveries" }, { value: "available", label: "Available to carry" }, { value: "carrying", label: "I'm carrying" }, { value: "gate", label: "Gate food & parcels" }]
    : [{ value: "all", label: "All P2P deliveries" }];

  return (
    <>
      <PageHeader
        title="Deliveries"
        subtitle="Peer-to-peer inter-hostel delivery for a fixed ₹10, with OTP or QR + photo handover."
        actions={isStudent && <Button onClick={() => setNewOpen(true)}><Plus className="h-4 w-4" /> Send an item</Button>}
      />
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      {tab === "gate" ? (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card title="Book a gate delivery" className="lg:col-span-2"><GateBooking onDone={() => void gate.reload()} /></Card>
          <Card title="My gate bookings" className="lg:col-span-3">
            {gate.loading && !gate.data ? <Spinner /> : !gate.data?.length ? <EmptyState title="No bookings" /> : (
              <ul className="divide-y divide-slate-100">
                {gate.data.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-start justify-between gap-3 py-3" data-testid="gate-row">
                    <div>
                      <p className="font-medium text-slate-800">{g.code} · {g.vendor} <span className="text-xs text-slate-500">({label(g.kind)})</span></p>
                      <p className="text-xs text-slate-500">Courier {g.courier_name} · {g.gate} · {fmtDate(g.expected_date)} {g.expected_time}</p>
                      {g.otp && <p className="mt-1 text-sm">Gate OTP: <span className="rounded bg-navy-50 px-2 py-0.5 font-mono font-semibold tracking-widest text-navy-800" data-testid="gate-otp">{g.otp}</span></p>}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge value={g.status} />
                      {g.status === "BOOKED" && (
                        <Button size="sm" variant="secondary" onClick={async () => { try { await api.patch(`/api/gate-deliveries/${g.id}/cancel`); toast("success", "Booking cancelled"); void gate.reload(); } catch (e) { toast("error", (e as Error).message); } }}>Cancel</Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      ) : (
        <Card>
          {p2p.error && <Alert>{p2p.error}</Alert>}
          {p2p.loading && !p2p.data ? <Spinner /> : <DeliveryTable items={p2p.data ?? []} view={tab} />}
        </Card>
      )}
      {isStudent && <NewDelivery open={newOpen} onClose={() => setNewOpen(false)} />}
    </>
  );
}
