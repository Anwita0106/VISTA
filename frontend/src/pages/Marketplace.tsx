import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, qs } from "../api/client";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, Input, Modal, PageHeader, SearchBox, Select, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { inr, label, timeAgo } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

interface Item { id: number; title: string; description: string; category: string; condition: string; price: number; status: string; seller: { id: number; full_name: string }; created_at: string }
const CATS = ["BOOKS", "ELECTRONICS", "FURNITURE", "CLOTHING", "OTHER"];

export default function Marketplace() {
  const { user } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [sort, setSort] = useState("newest");
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Item[]>(`/api/marketplace${qs({ q: dq, category: cat, sort })}`);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ title: "", description: "", category: "BOOKS", condition: "GOOD", price: "" });
  const [err, setErr] = useState<string | null>(null);
  const isStudent = user?.role === "STUDENT";

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const price = Number(f.price);
    if (f.title.trim().length < 3) return setErr("Title must be at least 3 characters");
    if (f.price === "" || !Number.isInteger(price) || price < 0) return setErr("Enter a price in whole rupees (0 for exchange / free)");
    try {
      await api.post("/api/marketplace", { ...f, price });
      toast("success", "Listing published");
      setOpen(false);
      setF({ title: "", description: "", category: "BOOKS", condition: "GOOD", price: "" });
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Community marketplace" subtitle="Buy, sell or exchange books and items within the hostel community. Payment is arranged between students." actions={isStudent && <Button onClick={() => { setErr(null); setOpen(true); }}><Plus className="h-4 w-4" /> List an item</Button>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Search listings" />
        <FilterSelect ariaLabel="Category" value={cat} onChange={setCat} options={CATS} all="All categories" />
        <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="newest">Newest</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option>
        </select>
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="No listings" /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((m) => (
            <Card key={m.id}>
              <div data-testid="market-card">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-slate-900">{m.title}</h3>
                  <span className="whitespace-nowrap text-lg font-semibold text-navy-800">{m.price === 0 ? "Free / swap" : inr(m.price)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-slate-600">{m.description}</p>
                <div className="mt-3 flex flex-wrap gap-1.5"><Badge value={m.category} /><span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">{label(m.condition)}</span></div>
                <p className="mt-3 text-xs text-slate-500">{m.seller.full_name} · {timeAgo(m.created_at)}</p>
                <div className="mt-3 flex gap-2">
                  {user?.id === m.seller.id ? (
                    <>
                      <Button size="sm" variant="secondary" onClick={async () => { try { await api.patch(`/api/marketplace/${m.id}/sold`); toast("success", "Marked as sold"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Mark sold</Button>
                      <Button size="sm" variant="ghost" onClick={async () => { try { await api.del(`/api/marketplace/${m.id}`); toast("success", "Listing removed"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Remove</Button>
                    </>
                  ) : isStudent ? (
                    <Button size="sm" variant="secondary" onClick={() => nav(`/messages?u=${m.seller.id}`)}>Message seller</Button>
                  ) : user?.role === "ADMIN" ? (
                    <Button size="sm" variant="ghost" onClick={async () => { try { await api.del(`/api/marketplace/${m.id}`); toast("success", "Listing removed"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>Remove listing</Button>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="List an item" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => void submit()}>Publish listing</Button></>}>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          <Input label="Title" name="title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
          <Textarea label="Description" name="description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Select label="Category" name="category" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} options={CATS} />
            <Select label="Condition" name="condition" value={f.condition} onChange={(e) => setF({ ...f, condition: e.target.value })} options={["NEW", "LIKE_NEW", "GOOD", "FAIR"]} />
            <Input label="Price (₹)" name="price" type="number" min={0} value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} required />
          </div>
        </form>
      </Modal>
    </>
  );
}
