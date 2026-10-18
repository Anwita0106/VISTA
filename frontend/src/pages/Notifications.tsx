import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { NotificationItem } from "../api/types";
import { Alert, Button, Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { cx } from "../lib/cx";
import { fmtDateTime } from "../lib/format";
import { useFetch } from "../lib/hooks";

export default function Notifications() {
  const { data, loading, error, reload } = useFetch<{ unread: number; items: NotificationItem[] }>("/api/notifications");
  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle={data ? `${data.unread} unread` : undefined}
        actions={<Button variant="secondary" disabled={!data?.unread} onClick={async () => { await api.post("/api/notifications/read-all"); void reload(); }}>Mark all as read</Button>}
      />
      <Card>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? <Spinner /> : !data?.items.length ? <EmptyState title="No notifications" /> : (
          <ul className="divide-y divide-slate-100">
            {data.items.map((n) => (
              <li key={n.id} className={cx("flex items-start gap-3 py-3", !n.is_read && "bg-navy-50/40")} data-testid="notification-item">
                <span className={cx("mt-1.5 h-2 w-2 flex-none rounded-full", n.is_read ? "bg-transparent" : n.kind === "SOS" ? "bg-red-600" : "bg-navy-600")} aria-hidden />
                <div className="min-w-0 flex-1">
                  <Link to={n.link || "#"} onClick={() => !n.is_read && void api.patch(`/api/notifications/${n.id}/read`)} className="text-sm font-medium text-slate-800 hover:underline">{n.title}</Link>
                  {n.body && <p className="text-sm text-slate-600">{n.body}</p>}
                  <p className="text-xs text-slate-500">{fmtDateTime(n.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
