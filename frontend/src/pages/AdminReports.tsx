import { Download } from "lucide-react";
import { downloadFile } from "../api/client";
import { Alert, Button, Card, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, inr, label } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface Report {
  generated_at: string;
  occupancy: { capacity: number; occupied: number; occupancy_pct: number; hostels: { name: string; capacity: number; occupied: number; occupancy_pct: number }[] };
  complaints: { by_status: Record<string, number>; by_category: Record<string, number>; by_priority: Record<string, number>; avg_resolution_hours: number | null };
  visitors: Record<string, number>;
  service_requests: Record<string, number>;
  sos: Record<string, number>;
  deliveries: { by_status: Record<string, number>; demo_fees_collected: number };
  gate_deliveries: Record<string, number>;
  mess_feedback: { avg_food: number | null; avg_service: number | null; count: number };
  users: Record<string, number>;
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (!entries.length) return <p className="text-sm text-slate-500">No data yet.</p>;
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-2">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-3 text-sm">
          <span className="w-28 flex-none truncate text-slate-600">{label(k)}</span>
          <div className="h-2.5 flex-1 rounded-full bg-slate-100"><div className="h-2.5 rounded-full bg-navy-600" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="w-8 text-right font-medium">{v}</span>
        </div>
      ))}
    </div>
  );
}

export default function AdminReports() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, loading, error } = useFetch<Report>("/api/admin/reports");
  const sum = (o: Record<string, number>) => Object.values(o).reduce((a, b) => a + b, 0);
  return (
    <>
      <PageHeader
        title="Reports"
        subtitle={data ? `Live figures from the database · generated ${fmtDateTime(data.generated_at)}` : undefined}
        actions={user?.role === "ADMIN" && (["complaints", "deliveries", "visitors", "occupancy"] as const).map((k) => (
          <Button key={k} size="sm" variant="secondary" onClick={() => downloadFile(`/api/admin/reports/export?kind=${k}`, `vista_${k}_report.csv`).catch((e) => toast("error", (e as Error).message))}><Download className="h-4 w-4" /> {label(k)} CSV</Button>
        ))}
      />
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title={`Occupancy · ${data.occupancy.occupied}/${data.occupancy.capacity} beds (${data.occupancy.occupancy_pct}%)`}>
            <div className="space-y-3">
              {data.occupancy.hostels.map((h) => (
                <div key={h.name}>
                  <div className="flex justify-between text-sm"><span>{h.name}</span><span className="font-medium">{h.occupied}/{h.capacity} · {h.occupancy_pct}%</span></div>
                  <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-navy-600" style={{ width: `${h.occupancy_pct}%` }} /></div>
                </div>
              ))}
            </div>
          </Card>
          <Card title={`Complaints · ${sum(data.complaints.by_status)} total`}>
            <Bars data={data.complaints.by_category} />
            <p className="mt-4 text-sm text-slate-600">Average resolution time: <strong>{data.complaints.avg_resolution_hours ?? "—"} h</strong></p>
            <div className="mt-3"><Bars data={data.complaints.by_status} /></div>
          </Card>
          <Card title={`P2P deliveries · demo fees ${inr(data.deliveries.demo_fees_collected)}`}><Bars data={data.deliveries.by_status} /></Card>
          <Card title="Visitor requests"><Bars data={data.visitors} /></Card>
          <Card title="Service requests"><Bars data={data.service_requests} /></Card>
          <Card title="SOS alerts"><Bars data={data.sos} /></Card>
          <Card title="Mess feedback">
            <p className="text-sm">Average food rating <strong>{data.mess_feedback.avg_food ?? "—"}</strong> · service <strong>{data.mess_feedback.avg_service ?? "—"}</strong> · {data.mess_feedback.count} responses</p>
          </Card>
          <Card title="Users by role"><Bars data={data.users} /></Card>
        </div>
      )}
    </>
  );
}
