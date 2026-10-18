import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import type { Visitor } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, Input, Modal, PageHeader, Select, Spinner, Table, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, fmtDateTime, label, todayISO } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { validateVisitor } from "../lib/validation";

const EMPTY = { visitor_name: "", relation: "", visitor_phone: "", visit_date: "", time_from: "10:00", time_to: "12:00", purpose: "" };

export default function Visitors() {
  const { user } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState(user?.role === "STUDENT" ? "" : "PENDING");
  const { data, loading, error, reload } = useFetch<Visitor[]>(`/api/visitors${qs({ status })}`);
  const [f, setF] = useState(EMPTY);
  const [err, setErr] = useState<Record<string, string>>({});
  const [apiErr, setApiErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [deciding, setDeciding] = useState<{ v: Visitor; decision: "APPROVED" | "REJECTED" } | null>(null);
  const [remark, setRemark] = useState("");
  const [remarkErr, setRemarkErr] = useState<string | null>(null);
  if (!user) return null;
  const isStudent = user.role === "STUDENT";
  const canDecide = user.role === "WARDEN" || user.role === "CHIEF_WARDEN";

  async function submit(e: FormEvent) {
    e.preventDefault();
    const er = validateVisitor(f, todayISO());
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    setApiErr(null);
    try {
      await api.post("/api/visitors", f);
      setF(EMPTY);
      toast("success", "Visitor request submitted for warden approval");
      void reload();
    } catch (e2) {
      setApiErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function decide() {
    if (!deciding) return;
    if (deciding.decision === "REJECTED" && remark.trim().length < 3) {
      setRemarkErr("Please give a reason for rejecting");
      return;
    }
    try {
      await api.patch(`/api/visitors/${deciding.v.id}/decision`, { decision: deciding.decision, remark });
      toast("success", `Visitor request ${deciding.decision.toLowerCase()}`);
      setDeciding(null);
      setRemark("");
      void reload();
    } catch (e) {
      setRemarkErr((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Visitor management" subtitle={isStudent ? "Register visitors for warden approval. Visiting hours are 08:00–20:00." : "Review visitor requests from students."} />
      <div className={isStudent ? "grid gap-6 lg:grid-cols-5" : ""}>
        {isStudent && (
          <Card title="Register a visitor" className="lg:col-span-2">
            <form onSubmit={submit} className="space-y-4" noValidate>
              {apiErr && <Alert>{apiErr}</Alert>}
              <Input label="Visitor name" name="visitor_name" required value={f.visitor_name} onChange={(e) => setF({ ...f, visitor_name: e.target.value })} error={err.visitor_name} />
              <div className="grid gap-4 sm:grid-cols-2">
                <Select label="Relation" name="relation" required value={f.relation} onChange={(e) => setF({ ...f, relation: e.target.value })} options={["PARENT", "GUARDIAN", "SIBLING", "RELATIVE", "FRIEND", "OTHER"]} placeholder="Select" error={err.relation} />
                <Input label="Visitor mobile" name="visitor_phone" required inputMode="numeric" value={f.visitor_phone} onChange={(e) => setF({ ...f, visitor_phone: e.target.value })} error={err.visitor_phone} />
              </div>
              <Input label="Visit date" name="visit_date" type="date" required min={todayISO()} value={f.visit_date} onChange={(e) => setF({ ...f, visit_date: e.target.value })} error={err.visit_date} />
              <div className="grid grid-cols-2 gap-4">
                <Input label="From" name="time_from" type="time" value={f.time_from} onChange={(e) => setF({ ...f, time_from: e.target.value })} />
                <Input label="To" name="time_to" type="time" value={f.time_to} onChange={(e) => setF({ ...f, time_to: e.target.value })} error={err.time_to} />
              </div>
              <Textarea label="Purpose" name="purpose" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} />
              <Button type="submit" loading={busy} className="w-full">
                Submit request
              </Button>
            </form>
          </Card>
        )}
        <Card title={isStudent ? "My visitor requests" : "Visitor requests"} className={isStudent ? "lg:col-span-3" : ""} action={<FilterSelect ariaLabel="Filter by status" value={status} onChange={setStatus} options={["PENDING", "APPROVED", "REJECTED", "CANCELLED"]} all="All" />}>
          {error && <Alert>{error}</Alert>}
          {loading && !data ? (
            <Spinner />
          ) : !data?.length ? (
            <EmptyState title="No visitor requests" message={isStudent ? "Requests you submit will appear here." : "Nothing waiting for review."} />
          ) : (
            <Table head={isStudent ? ["Visitor", "Date & time", "Status", "Warden remark"] : ["Student", "Visitor", "Date & time", "Status", "Action"]}>
              {data.map((v) => (
                <tr key={v.id} data-testid="visitor-row">
                  {!isStudent && (
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-800">{v.student.full_name}</p>
                      <p className="text-xs text-slate-500">{v.student.reg_no} · {v.student.room ?? "No room"}</p>
                    </td>
                  )}
                  <td className="px-5 py-3">
                    <p className="font-medium text-slate-800">{v.visitor_name}</p>
                    <p className="text-xs text-slate-500">{label(v.relation)} · {v.visitor_phone}</p>
                  </td>
                  <td className="whitespace-nowrap px-5 py-3 text-slate-600">{fmtDate(v.visit_date)}<br /><span className="text-xs">{v.time_from}–{v.time_to}</span></td>
                  <td className="px-5 py-3"><Badge value={v.status} /></td>
                  {isStudent ? (
                    <td className="px-5 py-3 text-slate-600">
                      {v.decision_remark || "—"}
                      {v.status === "PENDING" && (
                        <button
                          className="ml-2 text-xs font-medium text-red-700 underline"
                          onClick={async () => {
                            try {
                              await api.patch(`/api/visitors/${v.id}/cancel`);
                              toast("success", "Request cancelled");
                              void reload();
                            } catch (e) {
                              toast("error", (e as Error).message);
                            }
                          }}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  ) : (
                    <td className="whitespace-nowrap px-5 py-3">
                      {v.status === "PENDING" && canDecide ? (
                        <div className="flex gap-2">
                          <Button size="sm" variant="success" onClick={() => { setDeciding({ v, decision: "APPROVED" }); setRemark(""); setRemarkErr(null); }}>Approve</Button>
                          <Button size="sm" variant="danger" onClick={() => { setDeciding({ v, decision: "REJECTED" }); setRemark(""); setRemarkErr(null); }}>Reject</Button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">{v.decided_by ? `${v.decided_by.full_name}, ${fmtDateTime(v.decided_at)}` : canDecide ? "—" : "View only"}</span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>
      <Modal
        open={!!deciding}
        onClose={() => setDeciding(null)}
        title={deciding?.decision === "APPROVED" ? "Approve visitor" : "Reject visitor"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeciding(null)}>Cancel</Button>
            <Button variant={deciding?.decision === "APPROVED" ? "success" : "danger"} onClick={() => void decide()} data-testid="confirm-decision">
              Confirm {deciding?.decision === "APPROVED" ? "approval" : "rejection"}
            </Button>
          </>
        }
      >
        {deciding && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              {deciding.v.visitor_name} ({label(deciding.v.relation)}) visiting {deciding.v.student.full_name} on {fmtDate(deciding.v.visit_date)}, {deciding.v.time_from}–{deciding.v.time_to}.
            </p>
            <Textarea label={deciding.decision === "REJECTED" ? "Reason (required)" : "Remark (optional)"} name="remark" value={remark} onChange={(e) => setRemark(e.target.value)} error={remarkErr ?? undefined} />
          </div>
        )}
      </Modal>
    </>
  );
}
