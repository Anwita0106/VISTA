import { AlertTriangle, ClipboardList, DoorOpen, Package, ShieldAlert, Siren, Sparkles, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert, Card, EmptyState, PageHeader, Spinner, StatCard } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { fmtDateTime, label, ROLE_LABEL, timeAgo } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface Dash {
  role: string;
  unread_notifications: number;
  recent_notices: { id: number; title: string; category: string; created_at: string }[];
  cards: Record<string, number>;
  complaints_by_category?: Record<string, number>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, error } = useFetch<Dash>("/api/dashboard");
  const notif = useFetch<{ items: { id: number; title: string; body: string; created_at: string; link: string }[] }>("/api/notifications");
  if (!user) return null;
  const greeting = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening";
  const c = data?.cards ?? {};
  const isStudent = user.role === "STUDENT";

  return (
    <>
      <PageHeader
        title={`${greeting}, ${user.full_name.split(" ")[0]}`}
        subtitle={isStudent ? (user.room ? `${user.room.hostel} · Block ${user.room.block} · Room ${user.room.number}` : "No room allocated yet – contact the hostel office.") : `${ROLE_LABEL[user.role]} dashboard`}
      />
      {error && <Alert>{error}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : isStudent ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Open complaints" value={c.open_complaints ?? 0} icon={<ClipboardList className="h-4 w-4" />} />
          <StatCard label="Pending visitors" value={c.pending_visitors ?? 0} icon={<DoorOpen className="h-4 w-4" />} tone="amber" />
          <StatCard label="Active service requests" value={c.active_services ?? 0} icon={<Sparkles className="h-4 w-4" />} tone="violet" />
          <StatCard label="Active deliveries" value={c.active_deliveries ?? 0} icon={<Package className="h-4 w-4" />} tone="emerald" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Open complaints" value={c.open_complaints ?? 0} icon={<ClipboardList className="h-4 w-4" />} hint={user.role === "STAFF" ? "Assigned to you" : "Open or in progress"} />
          <StatCard label="Escalated" value={c.escalated_complaints ?? 0} icon={<AlertTriangle className="h-4 w-4" />} tone="amber" />
          <StatCard label="Active SOS" value={c.active_sos ?? 0} icon={<Siren className="h-4 w-4" />} tone="red" />
          <StatCard label="Pending visitors" value={c.pending_visitors ?? 0} icon={<DoorOpen className="h-4 w-4" />} tone="violet" />
          <StatCard label="Pending services" value={c.pending_services ?? 0} icon={<Sparkles className="h-4 w-4" />} />
          <StatCard label="Deliveries this week" value={c.deliveries_this_week ?? 0} icon={<Package className="h-4 w-4" />} tone="emerald" />
          <StatCard label="Gate deliveries waiting" value={c.gate_waiting ?? 0} icon={<ShieldAlert className="h-4 w-4" />} tone="violet" />
          <StatCard label="Registered students" value={c.students ?? 0} icon={<Users className="h-4 w-4" />} />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Latest notices" className="lg:col-span-2" action={<Link to="/notices" className="text-sm font-semibold text-vista-link hover:underline">View all</Link>}>
          {data?.recent_notices.length ? (
            <ul className="divide-y divide-vista-line/70">
              {data.recent_notices.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-vista-ink">{n.title}</p>
                    <p className="text-xs text-vista-muted-text">{label(n.category)} · {fmtDateTime(n.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No notices yet" />
          )}
        </Card>
        <Card title="Recent updates" action={<Link to="/notifications" className="text-sm font-semibold text-vista-link hover:underline">All</Link>}>
          {notif.data?.items.length ? (
            <ul className="space-y-3">
              {notif.data.items.slice(0, 6).map((n) => (
                <li key={n.id}>
                  <Link to={n.link || "/notifications"} className="block rounded-xl p-2 transition hover:bg-vista-soft/60">
                    <p className="text-sm font-semibold text-vista-ink">{n.title}</p>
                    <p className="text-xs text-vista-muted-text">{timeAgo(n.created_at)}</p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-vista-muted-text">You are all caught up.</p>
          )}
        </Card>
      </div>

      {data?.complaints_by_category && (
        <Card title="Complaints by category" className="mt-6">
          <div className="space-y-2.5">
            {Object.entries(data.complaints_by_category).map(([cat, n]) => {
              const max = Math.max(...Object.values(data.complaints_by_category!));
              return (
                <div key={cat} className="flex items-center gap-3 text-sm">
                  <span className="w-28 flex-none text-vista-muted-text">{label(cat)}</span>
                  <div className="h-2.5 flex-1 rounded-full bg-vista-soft/70">
                    <div className="h-2.5 rounded-full bg-vista-accent" style={{ width: `${(n / max) * 100}%` }} />
                  </div>
                  <span className="w-8 text-right font-semibold text-vista-ink">{n}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {isStudent && (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { to: "/complaints?new=1", t: "Raise a complaint", d: "Electrical, plumbing, water…" },
            { to: "/visitors", t: "Register a visitor", d: "Needs warden approval" },
            { to: "/services", t: "Sick meal / cleaning", d: "Request a hostel service" },
            { to: "/delivery", t: "Send a parcel – ₹10", d: "Peer-to-peer delivery" },
          ].map((q) => (
            <Link key={q.to} to={q.to} className="group rounded-2xl border border-vista-line bg-vista-card p-4 shadow-soft transition hover:-translate-y-0.5 hover:border-vista-yellow focus:outline-none focus-visible:ring-2 focus-visible:ring-vista-accent">
              <p className="text-sm font-semibold text-vista-ink">{q.t}</p>
              <p className="mt-0.5 text-xs text-vista-muted-text">{q.d}</p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
