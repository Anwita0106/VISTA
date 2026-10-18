import { Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import type { Hostel, Notice } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, Input, Modal, PageHeader, SearchBox, Select, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, label } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

const CATS = ["GENERAL", "MESS", "MAINTENANCE", "EVENT", "URGENT"];

export default function Notices() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Notice[]>(`/api/notices${qs({ q: dq, category: cat })}`);
  const canPublish = !!user && ["WARDEN", "CHIEF_WARDEN", "ADMIN"].includes(user.role);
  const hostels = useFetch<Hostel[]>(canPublish ? "/api/hostels" : null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ title: "", body: "", category: "GENERAL", hostel_id: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function publish(e?: FormEvent) {
    e?.preventDefault();
    if (f.title.trim().length < 3 || f.body.trim().length < 5) return setErr("Title (3+ characters) and message (5+ characters) are required");
    setBusy(true);
    setErr(null);
    try {
      await api.post("/api/notices", { ...f, hostel_id: f.hostel_id ? Number(f.hostel_id) : null });
      toast("success", "Notice published and students notified");
      setOpen(false);
      setF({ title: "", body: "", category: "GENERAL", hostel_id: "" });
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Notice board" subtitle="Announcements from wardens and the hostel office." actions={canPublish && <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Publish notice</Button>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Search notices" />
        <FilterSelect ariaLabel="Filter by category" value={cat} onChange={setCat} options={CATS} all="All categories" />
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="No notices found" /> : (
        <div className="space-y-4">
          {data.map((n) => (
            <Card key={n.id}>
              <article data-testid="notice-card">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">{n.title}</h2>
                    <p className="mt-0.5 text-xs text-slate-500">{n.author.full_name} · {n.hostel} · {fmtDateTime(n.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge value={n.category} className={n.category === "URGENT" ? "!bg-red-50 !text-red-800" : ""} />
                    {canPublish && (user?.role === "ADMIN" || user?.id === n.author.id) && (
                      <button aria-label={`Delete notice ${n.title}`} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-red-600" onClick={async () => { try { await api.del(`/api/notices/${n.id}`); toast("success", "Notice deleted"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{n.body}</p>
              </article>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Publish a notice" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={busy} onClick={() => void publish()} data-testid="publish-notice">Publish</Button></>}>
        <form onSubmit={publish} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          <Input label="Title" name="title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
          <Textarea label="Message" name="body" rows={5} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} required />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Category" name="category" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} options={CATS} />
            <Select label="Audience" name="hostel_id" value={f.hostel_id} onChange={(e) => setF({ ...f, hostel_id: e.target.value })} placeholder="All hostels" options={(hostels.data ?? []).map((h) => ({ value: String(h.id), label: h.name }))} />
          </div>
          <p className="text-xs text-slate-500">Category: {label(f.category)}. Every student in the audience receives a notification.</p>
        </form>
      </Modal>
    </>
  );
}
