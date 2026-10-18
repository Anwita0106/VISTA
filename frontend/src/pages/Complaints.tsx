import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, qs } from "../api/client";
import type { Complaint, Paged } from "../api/types";
import { Alert, Badge, Button, Card, FilterSelect, Input, Modal, PageHeader, Pagination, SearchBox, Select, Spinner, Table, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, label } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";
import { validateComplaint } from "../lib/validation";

const CATEGORIES = ["ELECTRICAL", "PLUMBING", "CARPENTRY", "WASHROOM", "WATER", "OTHER"];
const STATUSES = ["OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED", "CLOSED"];

export function NewComplaintModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (c: Complaint) => void }) {
  const [f, setF] = useState({ category: "", title: "", description: "", location: "", priority: "MEDIUM" });
  const [err, setErr] = useState<Record<string, string>>({});
  const [apiErr, setApiErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const forcedHigh = f.category === "WASHROOM" || f.category === "WATER";

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const er = validateComplaint(f);
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    setApiErr(null);
    try {
      const c = await api.post<Complaint>("/api/complaints", f);
      setF({ category: "", title: "", description: "", location: "", priority: "MEDIUM" });
      onCreated(c);
    } catch (e2) {
      setApiErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Raise a complaint"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy} data-testid="submit-complaint">
            Submit complaint
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {apiErr && <Alert>{apiErr}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Category" name="category" required value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} options={CATEGORIES} placeholder="Select category" error={err.category} />
          <Select label="Priority" name="priority" value={forcedHigh ? "HIGH" : f.priority} disabled={forcedHigh} onChange={(e) => setF({ ...f, priority: e.target.value })} options={["LOW", "MEDIUM", "HIGH"]} />
        </div>
        {forcedHigh && <Alert kind="info">Washroom and water complaints are always given HIGH priority.</Alert>}
        <Input label="Title" name="title" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} error={err.title} placeholder="e.g. Ceiling fan not working" />
        <Textarea label="Description" name="description" required value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} error={err.description} />
        <Input label="Location" name="location" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} hint="Leave blank to use your room" />
      </form>
    </Modal>
  );
}

export default function Complaints() {
  const { user } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("newest");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Paged<Complaint>>(`/api/complaints${qs({ status, category, q: dq, page, page_size: 10, sort })}`);
  const [running, setRunning] = useState(false);
  if (!user) return null;
  const isStudent = user.role === "STUDENT";
  const canEscalate = ["WARDEN", "CHIEF_WARDEN", "ADMIN"].includes(user.role);
  const showNew = params.get("new") === "1";

  return (
    <>
      <PageHeader
        title="Complaints"
        subtitle={isStudent ? "Raise and track maintenance issues in your room or block." : user.role === "STAFF" ? "Complaints assigned to you." : "All hostel complaints with status and escalation."}
        actions={
          <>
            {canEscalate && (
              <Button
                variant="secondary"
                loading={running}
                onClick={async () => {
                  setRunning(true);
                  try {
                    const r = await api.post<{ escalated: string[] }>("/api/complaints/escalation/run");
                    toast("success", r.escalated.length ? `Escalated ${r.escalated.join(", ")}` : "No complaints are past their time limit");
                    void reload();
                  } catch (e) {
                    toast("error", (e as Error).message);
                  } finally {
                    setRunning(false);
                  }
                }}
              >
                Run escalation check
              </Button>
            )}
            {isStudent && (
              <Button onClick={() => setParams({ new: "1" })}>
                <Plus className="h-4 w-4" /> New complaint
              </Button>
            )}
          </>
        }
      />
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search title or code" />
          <FilterSelect ariaLabel="Filter by status" value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={STATUSES} all="All statuses" />
          <FilterSelect ariaLabel="Filter by category" value={category} onChange={(v) => { setCategory(v); setPage(1); }} options={CATEGORIES} all="All categories" />
          <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="priority">Highest priority</option>
          </select>
        </div>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? (
          <Spinner />
        ) : (
          <>
            <Table head={["Code", "Title", "Category", "Priority", "Status", isStudent ? "Assigned to" : "Student", "Raised"]} empty={!data?.items.length}>
              {data?.items.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50" data-testid="complaint-row">
                  <td className="whitespace-nowrap px-5 py-3 font-mono text-xs">
                    <Link to={`/complaints/${c.id}`} className="font-semibold text-navy-700 hover:underline">
                      {c.code}
                    </Link>
                  </td>
                  <td className="max-w-xs px-5 py-3">
                    <Link to={`/complaints/${c.id}`} className="line-clamp-2 font-medium text-slate-800 hover:underline">
                      {c.title}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-slate-600">{label(c.category)}</td>
                  <td className="px-5 py-3"><Badge value={c.priority} /></td>
                  <td className="px-5 py-3"><Badge value={c.status} /></td>
                  <td className="whitespace-nowrap px-5 py-3 text-slate-600">{isStudent ? c.assigned_staff?.full_name ?? "Unassigned" : c.student.full_name}</td>
                  <td className="whitespace-nowrap px-5 py-3 text-slate-500">{fmtDateTime(c.created_at)}</td>
                </tr>
              ))}
            </Table>
            {data && <Pagination page={page} pageSize={10} total={data.total} onPage={setPage} />}
          </>
        )}
      </Card>
      {isStudent && (
        <NewComplaintModal
          open={showNew}
          onClose={() => setParams({})}
          onCreated={(c) => {
            setParams({});
            toast("success", `Complaint ${c.code} registered with ${c.priority} priority`);
            void reload();
          }}
        />
      )}
    </>
  );
}
