import { FileText, Lock } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, downloadFile } from "../api/client";
import type { FileRef } from "../api/types";
import { Alert, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, label } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface Doc { id: number; title: string; doc_type: string; file: FileRef; created_at: string }
const TYPES = ["ID_PROOF", "ALLOTMENT_LETTER", "FEE_RECEIPT", "MEDICAL", "UNDERTAKING", "OTHER"];

export default function Vault() {
  const toast = useToast();
  const { data, loading, error, reload } = useFetch<Doc[]>("/api/vault");
  const [title, setTitle] = useState("");
  const [type, setType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [inputKey, setInputKey] = useState(0);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (title.trim().length < 3 || !type || !file) return setErr("Title, document type and a file are required");
    if (file.size > 2 * 1024 * 1024) return setErr("File is larger than 2 MB");
    const fd = new FormData();
    fd.append("title", title);
    fd.append("doc_type", type);
    fd.append("file", file);
    setBusy(true);
    setErr(null);
    try {
      await api.post("/api/vault", fd);
      toast("success", "Document stored in your vault");
      setTitle("");
      setType("");
      setFile(null);
      setInputKey((k) => k + 1);
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Document vault" subtitle="Keep hostel documents in one private place. Only you and the hostel office can open them." />
      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="Upload a document" className="lg:col-span-2">
          <form onSubmit={upload} className="space-y-4" noValidate>
            {err && <Alert>{err}</Alert>}
            <Input label="Title" name="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            <Select label="Document type" name="doc_type" value={type} onChange={(e) => setType(e.target.value)} options={TYPES} placeholder="Select type" required />
            <Input key={inputKey} label="File (PDF, PNG or JPEG, max 2 MB)" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
            <Button type="submit" loading={busy} className="w-full"><Lock className="h-4 w-4" /> Upload securely</Button>
          </form>
        </Card>
        <Card title="My documents" className="lg:col-span-3">
          {error && <Alert>{error}</Alert>}
          {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="Your vault is empty" /> : (
            <ul className="divide-y divide-slate-100">
              {data.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 py-3" data-testid="vault-item">
                  <div className="flex min-w-0 items-center gap-3">
                    <FileText className="h-5 w-5 flex-none text-navy-600" />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-800">{d.title}</p>
                      <p className="text-xs text-slate-500">{label(d.doc_type)} · {(d.file.size / 1024).toFixed(0)} KB · {fmtDateTime(d.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex flex-none gap-2">
                    <Button size="sm" variant="secondary" onClick={() => void downloadFile(d.file.url, d.file.name)}>Download</Button>
                    <Button size="sm" variant="ghost" onClick={async () => { try { await api.del(`/api/vault/${d.id}`); toast("success", "Document deleted"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Delete</Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
