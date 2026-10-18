import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Complaint, Paged, User } from "../api/types";
import { Alert, Badge, Button, Card, PageHeader, Select, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, label } from "../lib/format";
import { useFetch } from "../lib/hooks";

const NEXT: Record<string, string[]> = { OPEN: ["IN_PROGRESS", "RESOLVED"], IN_PROGRESS: ["RESOLVED"], ESCALATED: ["IN_PROGRESS", "RESOLVED"], RESOLVED: [], CLOSED: [] };

export default function ComplaintDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { data: c, loading, error, setData } = useFetch<Complaint>(`/api/complaints/${id}`);
  const isMgmt = !!user && ["WARDEN", "CHIEF_WARDEN", "ADMIN"].includes(user.role);
  const staffList = useFetch<Paged<User>>(isMgmt ? "/api/admin/users?role=STAFF&page_size=100" : null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [assignTo, setAssignTo] = useState("");

  if (loading && !c) return <Spinner />;
  if (error || !c || !user) return <Alert>{error ?? "Complaint not found"}</Alert>;

  async function setStatus(status: string) {
    setBusy(status);
    try {
      setData(await api.patch<Complaint>(`/api/complaints/${id}/status`, { status, note }));
      setNote("");
      toast("success", `Status changed to ${label(status)}`);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const isOwner = user.id === c.student.id;
  const staffActions = user.role !== "STUDENT" ? NEXT[c.status] ?? [] : [];

  return (
    <>
      <Link to="/complaints" className="mb-3 inline-flex items-center gap-1 text-sm text-navy-700 hover:underline">
        <ArrowLeft className="h-4 w-4" /> Back to complaints
      </Link>
      <PageHeader title={`${c.code} · ${c.title}`} subtitle={`${label(c.category)} complaint raised by ${c.student.full_name} on ${fmtDateTime(c.created_at)}`} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Details">
            <div className="mb-4 flex flex-wrap gap-2">
              <span data-testid="complaint-status"><Badge value={c.status} /></span>
              <Badge value={c.priority} />
            </div>
            <p className="whitespace-pre-wrap text-sm text-slate-700" data-testid="complaint-description">{c.description}</p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Location</dt><dd className="font-medium">{c.location || "—"}</dd></div>
              <div><dt className="text-slate-500">Assigned staff</dt><dd className="font-medium">{c.assigned_staff?.full_name ?? "Unassigned"}</dd></div>
              <div><dt className="text-slate-500">Escalated to</dt><dd className="font-medium">{c.escalated_to?.full_name ?? "—"}</dd></div>
              <div><dt className="text-slate-500">Resolved at</dt><dd className="font-medium">{fmtDateTime(c.resolved_at)}</dd></div>
            </dl>
          </Card>
          <Card title="History">
            <ol className="relative space-y-4 border-l border-slate-200 pl-5" data-testid="complaint-history">
              {c.updates?.map((u) => (
                <li key={u.id}>
                  <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-navy-600" />
                  <p className="text-sm font-medium text-slate-800">
                    {u.from_status ? `${label(u.from_status)} → ${label(u.to_status)}` : label(u.to_status)}
                  </p>
                  {u.note && <p className="text-sm text-slate-600">{u.note}</p>}
                  <p className="text-xs text-slate-500">{u.actor?.full_name ?? "System"} · {fmtDateTime(u.created_at)}</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
        <div className="space-y-6">
          {(staffActions.length > 0 || (isOwner && c.status === "RESOLVED") || (isMgmt && c.status === "RESOLVED")) && (
            <Card title="Update status">
              <Textarea label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} name="note" />
              <div className="mt-3 flex flex-wrap gap-2">
                {staffActions.map((s) => (
                  <Button key={s} variant={s === "RESOLVED" ? "success" : "primary"} size="sm" loading={busy === s} onClick={() => setStatus(s)}>
                    Mark {label(s).toLowerCase()}
                  </Button>
                ))}
                {c.status === "RESOLVED" && (isOwner || isMgmt) && (
                  <>
                    <Button size="sm" variant="success" loading={busy === "CLOSED"} onClick={() => setStatus("CLOSED")}>Confirm &amp; close</Button>
                    <Button size="sm" variant="secondary" loading={busy === "OPEN"} onClick={() => setStatus("OPEN")}>Reopen</Button>
                  </>
                )}
              </div>
            </Card>
          )}
          {isMgmt && staffList.data && !["RESOLVED", "CLOSED"].includes(c.status) && (
            <Card title="Reassign">
              <Select label="Staff member" value={assignTo} onChange={(e) => setAssignTo(e.target.value)} placeholder="Select staff" options={staffList.data.items.map((s) => ({ value: String(s.id), label: `${s.full_name} (${label(s.staff_type)})` }))} />
              <Button
                className="mt-3"
                size="sm"
                disabled={!assignTo}
                onClick={async () => {
                  try {
                    setData(await api.patch<Complaint>(`/api/complaints/${id}/assign`, { staff_id: Number(assignTo) }));
                    toast("success", "Complaint reassigned");
                  } catch (e) {
                    toast("error", (e as Error).message);
                  }
                }}
              >
                Reassign
              </Button>
            </Card>
          )}
          <Card title="Escalation rule">
            <p className="text-sm text-slate-600">Complaints not resolved within <strong>24 h (High)</strong>, <strong>48 h (Medium)</strong> or <strong>72 h (Low)</strong> are escalated automatically to the chief warden.</p>
          </Card>
        </div>
      </div>
    </>
  );
}
