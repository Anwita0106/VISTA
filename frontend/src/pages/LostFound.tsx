import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, Input, Modal, PageHeader, SearchBox, Select, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, todayISO } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

interface Item { id: number; kind: string; title: string; description: string; location: string; item_date: string; contact: string; status: string; reporter: { id: number; full_name: string }; created_at: string }

export default function LostFound() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("OPEN");
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Item[]>(`/api/lost-found${qs({ q: dq, kind, status })}`);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ kind: "LOST", title: "", description: "", location: "", item_date: todayISO(), contact: "" });
  const [err, setErr] = useState<string | null>(null);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (f.title.trim().length < 3 || f.location.trim().length < 2) return setErr("Item name and location are required");
    try {
      await api.post("/api/lost-found", f);
      toast("success", "Item reported");
      setOpen(false);
      setF({ kind: "LOST", title: "", description: "", location: "", item_date: todayISO(), contact: "" });
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Lost & found" subtitle="Report lost or found items and search what others have reported." actions={<Button onClick={() => { setErr(null); setOpen(true); }}><Plus className="h-4 w-4" /> Report item</Button>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Search items or places" />
        <FilterSelect ariaLabel="Lost or found" value={kind} onChange={setKind} options={["LOST", "FOUND"]} all="Lost & found" />
        <FilterSelect ariaLabel="Status" value={status} onChange={setStatus} options={["OPEN", "CLAIMED"]} all="Any status" />
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="No items match" /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((i) => (
            <Card key={i.id}>
              <div data-testid="lf-card">
                <div className="flex items-center justify-between gap-2"><Badge value={i.kind} /><Badge value={i.status} /></div>
                <h3 className="mt-3 font-semibold text-slate-900">{i.title}</h3>
                {i.description && <p className="mt-1 text-sm text-slate-600">{i.description}</p>}
                <p className="mt-2 text-xs text-slate-500">{i.location} · {fmtDate(i.item_date)}</p>
                <p className="text-xs text-slate-500">Contact: {i.contact || i.reporter.full_name}</p>
                {i.status === "OPEN" && (user?.id === i.reporter.id || ["WARDEN", "CHIEF_WARDEN", "ADMIN"].includes(user?.role ?? "")) && (
                  <Button size="sm" variant="secondary" className="mt-3" onClick={async () => { try { await api.patch(`/api/lost-found/${i.id}/claim`); toast("success", "Marked as returned"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Mark returned</Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Report an item" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => void submit()}>Submit</Button></>}>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          <Select label="I have…" name="kind" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} options={[{ value: "LOST", label: "Lost something" }, { value: "FOUND", label: "Found something" }]} />
          <Input label="Item" name="title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
          <Textarea label="Description" name="description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Where" name="location" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} required />
            <Input label="When" type="date" name="item_date" max={todayISO()} value={f.item_date} onChange={(e) => setF({ ...f, item_date: e.target.value })} />
          </div>
          <Input label="Contact" name="contact" value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} hint="e.g. your room number" />
        </form>
      </Modal>
    </>
  );
}
