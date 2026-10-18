import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import type { ServiceRequest } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, Input, PageHeader, Select, Spinner, Table, Tabs, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, fmtDateTime, label, todayISO } from "../lib/format";
import { useFetch } from "../lib/hooks";

type Kind = "SICK_MEAL" | "CLEANING";

function RequestForm({ kind, onDone }: { kind: Kind; onDone: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ preferred_date: todayISO(), preferred_slot: "", meal_type: "", diet_notes: "", notes: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (kind === "SICK_MEAL" && !f.meal_type) return setErr("Please choose which meal you need");
    if (kind === "CLEANING" && !f.preferred_slot) return setErr("Please choose a preferred cleaning slot");
    setBusy(true);
    setErr(null);
    try {
      await api.post("/api/service-requests", { kind, ...f });
      toast("success", kind === "SICK_MEAL" ? "Sick-meal request sent to the mess" : "Room-cleaning request submitted");
      setF({ ...f, preferred_slot: "", meal_type: "", diet_notes: "", notes: "" });
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
      <Input label="Date" type="date" name="preferred_date" min={todayISO()} max={todayISO(7)} value={f.preferred_date} onChange={(e) => setF({ ...f, preferred_date: e.target.value })} />
      {kind === "SICK_MEAL" ? (
        <>
          <Select label="Meal" name="meal_type" required value={f.meal_type} onChange={(e) => setF({ ...f, meal_type: e.target.value })} options={["BREAKFAST", "LUNCH", "DINNER"]} placeholder="Select meal" />
          <Textarea label="Diet notes" name="diet_notes" value={f.diet_notes} onChange={(e) => setF({ ...f, diet_notes: e.target.value })} placeholder="e.g. light food, no spice" />
        </>
      ) : (
        <>
          <Select label="Preferred slot" name="preferred_slot" required value={f.preferred_slot} onChange={(e) => setF({ ...f, preferred_slot: e.target.value })} options={["MORNING", "AFTERNOON", "EVENING"]} placeholder="Select slot" />
          <Textarea label="Notes" name="notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Anything the cleaning staff should know" />
        </>
      )}
      <Button type="submit" loading={busy} className="w-full">
        {kind === "SICK_MEAL" ? "Request sick meal" : "Request room cleaning"}
      </Button>
    </form>
  );
}

export default function Services() {
  const { user } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<Kind>(user?.staff_type === "CLEANING" ? "CLEANING" : "SICK_MEAL");
  const [status, setStatus] = useState("");
  const isStudent = user?.role === "STUDENT";
  const isStaff = user?.role === "STAFF";
  const { data, loading, error, reload } = useFetch<ServiceRequest[]>(`/api/service-requests${qs({ kind: isStaff ? undefined : tab, status })}`);
  if (!user) return null;

  async function update(id: number, s: string) {
    try {
      await api.patch(`/api/service-requests/${id}/status`, { status: s });
      toast("success", `Request ${label(s).toLowerCase()}`);
      void reload();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }

  const list = (
    <Card title={isStudent ? "My requests" : "Requests queue"} action={<FilterSelect ariaLabel="Filter by status" value={status} onChange={setStatus} options={["PENDING", "ACCEPTED", "COMPLETED", "CANCELLED"]} />}>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState title="No requests" />
      ) : (
        <Table head={isStudent ? ["Type", "For", "Details", "Status", ""] : ["Student", "Type", "For", "Details", "Status", "Action"]}>
          {data.map((r) => (
            <tr key={r.id} data-testid="service-row">
              {!isStudent && (
                <td className="px-5 py-3">
                  <p className="font-medium">{r.student.full_name}</p>
                  <p className="text-xs text-slate-500">{r.student.room}</p>
                </td>
              )}
              <td className="whitespace-nowrap px-5 py-3">{r.kind === "SICK_MEAL" ? "Sick meal" : "Room cleaning"}</td>
              <td className="whitespace-nowrap px-5 py-3 text-slate-600">{fmtDate(r.preferred_date)}<br /><span className="text-xs">{label(r.meal_type || r.preferred_slot)}</span></td>
              <td className="max-w-xs px-5 py-3 text-slate-600">{r.diet_notes || r.notes || "—"}<p className="text-xs text-slate-400">Requested {fmtDateTime(r.created_at)}</p></td>
              <td className="px-5 py-3"><Badge value={r.status} /></td>
              <td className="whitespace-nowrap px-5 py-3">
                {isStudent && r.status === "PENDING" && <Button size="sm" variant="secondary" onClick={() => update(r.id, "CANCELLED")}>Cancel</Button>}
                {!isStudent && r.status === "PENDING" && <Button size="sm" onClick={() => update(r.id, "ACCEPTED")}>Accept</Button>}
                {!isStudent && r.status === "ACCEPTED" && <Button size="sm" variant="success" onClick={() => update(r.id, "COMPLETED")}>Mark completed</Button>}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );

  return (
    <>
      <PageHeader title="Sick meal & room cleaning" subtitle={isStudent ? "Request a meal delivered to your room when you are unwell, or book room cleaning." : "Accept and complete service requests."} />
      {!isStaff && (
        <Tabs<Kind> value={tab} onChange={setTab} tabs={[{ value: "SICK_MEAL", label: "Sick meal" }, { value: "CLEANING", label: "Room cleaning" }]} />
      )}
      {isStudent ? (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card title={tab === "SICK_MEAL" ? "Request a sick meal" : "Request room cleaning"} className="lg:col-span-2">
            <RequestForm key={tab} kind={tab} onDone={() => void reload()} />
          </Card>
          <div className="lg:col-span-3">{list}</div>
        </div>
      ) : (
        list
      )}
    </>
  );
}
