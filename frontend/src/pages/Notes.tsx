import { Paperclip, Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, downloadFile, qs } from "../api/client";
import type { FileRef } from "../api/types";
import { Alert, Button, Card, EmptyState, Input, Modal, PageHeader, SearchBox, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { timeAgo } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

interface Note { id: number; title: string; subject: string; content: string; file: FileRef | null; author: { id: number; full_name: string }; created_at: string }

export default function Notes() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Note[]>(`/api/notes${qs({ q: dq })}`);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ title: "", subject: "", content: "" });
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (f.title.trim().length < 3 || f.subject.trim().length < 2) return setErr("Title and subject are required");
    if (!f.content.trim() && !file) return setErr("Add some text or attach a file");
    const fd = new FormData();
    Object.entries(f).forEach(([k, v]) => fd.append(k, v));
    if (file) fd.append("file", file);
    setBusy(true);
    try {
      await api.post("/api/notes", fd);
      toast("success", "Notes shared");
      setOpen(false);
      setF({ title: "", subject: "", content: "" });
      setFile(null);
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Notes sharing" subtitle="Share study notes with friends and classmates." actions={user?.role === "STUDENT" && <Button onClick={() => { setErr(null); setOpen(true); }}><Plus className="h-4 w-4" /> Share notes</Button>} />
      <div className="mb-4"><SearchBox value={q} onChange={setQ} placeholder="Search title or subject" /></div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="No notes yet" /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((n) => (
            <Card key={n.id}>
              <article data-testid="note-card">
                <p className="text-xs font-semibold uppercase tracking-wide text-navy-600">{n.subject}</p>
                <h3 className="mt-1 font-semibold text-slate-900">{n.title}</h3>
                {n.content && <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm text-slate-600">{n.content}</p>}
                {n.file && <button className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-navy-700 underline" onClick={() => void downloadFile(n.file!.url, n.file!.name)}><Paperclip className="h-4 w-4" />{n.file.name}</button>}
                <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                  <span>{n.author.full_name} · {timeAgo(n.created_at)}</span>
                  {(user?.id === n.author.id || user?.role === "ADMIN") && <button className="text-red-700 underline" onClick={async () => { try { await api.del(`/api/notes/${n.id}`); toast("success", "Deleted"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Delete</button>}
                </div>
              </article>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Share notes" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={busy} onClick={() => void submit()}>Share</Button></>}>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Title" name="title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
            <Input label="Subject" name="subject" value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} required />
          </div>
          <Textarea label="Notes" name="content" rows={6} value={f.content} onChange={(e) => setF({ ...f, content: e.target.value })} />
          <Input label="Attachment (PDF, PNG, JPEG or TXT, max 2 MB)" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </form>
      </Modal>
    </>
  );
}
