import { Star } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api } from "../api/client";
import { Alert, Button, Card, EmptyState, Input, PageHeader, Select, Spinner, Table, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, label, todayISO } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface FB { summary: Record<string, { food: number; service: number; count: number }>; items: { id: number; meal: string; food_rating: number; service_rating: number; comments: string; feedback_date: string; student: { full_name: string } | null }[] }

function Stars({ value, onChange, name }: { value: number; onChange: (v: number) => void; name: string }) {
  return (
    <div role="radiogroup" aria-label={name} className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button type="button" key={n} role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`} onClick={() => onChange(n)} className="rounded p-0.5 focus-visible:ring-2 focus-visible:ring-navy-400">
          <Star className={`h-6 w-6 ${n <= value ? "fill-amber-400 text-amber-400" : "text-slate-300"}`} />
        </button>
      ))}
    </div>
  );
}

export default function MessFeedback() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch<FB>("/api/mess-feedback");
  const [f, setF] = useState({ meal: "", food_rating: 0, service_rating: 0, comments: "", feedback_date: todayISO() });
  const [err, setErr] = useState<string | null>(null);
  const isStudent = user?.role === "STUDENT";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!f.meal || !f.food_rating || !f.service_rating) return setErr("Choose the meal and give both ratings");
    try {
      await api.post("/api/mess-feedback", f);
      toast("success", "Thanks for your feedback");
      setF({ ...f, meal: "", food_rating: 0, service_rating: 0, comments: "" });
      setErr(null);
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Mess feedback" subtitle="Rate food quality and service so the mess committee can act on it." />
      {data && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {["BREAKFAST", "LUNCH", "SNACKS", "DINNER"].map((m) => (
            <div key={m} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-sm font-medium text-slate-600">{label(m)}</p>
              <p className="mt-1 text-xl font-semibold text-slate-900">{data.summary[m] ? `${data.summary[m].food.toFixed(1)} ★` : "—"}</p>
              <p className="text-xs text-slate-500">{data.summary[m] ? `Service ${data.summary[m].service.toFixed(1)} · ${data.summary[m].count} ratings` : "No ratings"}</p>
            </div>
          ))}
        </div>
      )}
      <div className={isStudent ? "grid gap-6 lg:grid-cols-5" : ""}>
        {isStudent && (
          <Card title="Give feedback" className="lg:col-span-2">
            <form onSubmit={submit} className="space-y-4" noValidate>
              {err && <Alert>{err}</Alert>}
              <div className="grid gap-4 sm:grid-cols-2">
                <Select label="Meal" name="meal" value={f.meal} onChange={(e) => setF({ ...f, meal: e.target.value })} options={["BREAKFAST", "LUNCH", "SNACKS", "DINNER"]} placeholder="Select" />
                <Input label="Date" type="date" name="feedback_date" max={todayISO()} min={todayISO(-3)} value={f.feedback_date} onChange={(e) => setF({ ...f, feedback_date: e.target.value })} />
              </div>
              <div><p className="mb-1 text-sm font-medium text-slate-700">Food quality</p><Stars name="Food quality" value={f.food_rating} onChange={(v) => setF({ ...f, food_rating: v })} /></div>
              <div><p className="mb-1 text-sm font-medium text-slate-700">Service</p><Stars name="Service" value={f.service_rating} onChange={(v) => setF({ ...f, service_rating: v })} /></div>
              <Textarea label="Comments" name="comments" value={f.comments} onChange={(e) => setF({ ...f, comments: e.target.value })} />
              <Button type="submit" className="w-full">Submit feedback</Button>
            </form>
          </Card>
        )}
        <Card title={isStudent ? "My feedback" : "Recent feedback"} className={isStudent ? "lg:col-span-3" : ""}>
          {error && <Alert>{error}</Alert>}
          {loading && !data ? <Spinner /> : !data?.items.length ? <EmptyState title="No feedback yet" /> : (
            <Table head={isStudent ? ["Date", "Meal", "Food", "Service", "Comments"] : ["Date", "Meal", "Food", "Service", "Comments", "Student"]}>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td className="whitespace-nowrap px-5 py-3">{fmtDate(i.feedback_date)}</td>
                  <td className="px-5 py-3">{label(i.meal)}</td>
                  <td className="px-5 py-3">{i.food_rating} ★</td>
                  <td className="px-5 py-3">{i.service_rating} ★</td>
                  <td className="px-5 py-3 text-slate-600">{i.comments || "—"}</td>
                  {!isStudent && <td className="px-5 py-3 text-slate-600">{i.student?.full_name ?? "Anonymous"}</td>}
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>
    </>
  );
}
