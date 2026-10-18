import { useState } from "react";
import { qs } from "../api/client";
import { Alert, Card, PageHeader, Pagination, SearchBox, Spinner, Table } from "../components/ui";
import { fmtDateTime } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

interface Log { id: number; action: string; entity: string; entity_id: string; detail: string; user: { full_name: string }; created_at: string }

export default function AdminAudit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const da = useDebounced(action);
  const { data, loading, error } = useFetch<{ total: number; items: Log[] }>(`/api/admin/audit-logs${qs({ action: da, page, page_size: 25 })}`);
  return (
    <>
      <PageHeader title="Audit log" subtitle="Every critical action is recorded with time, user and details (NFR12)." />
      <Card>
        <div className="mb-4"><SearchBox value={action} onChange={(v) => { setAction(v); setPage(1); }} placeholder="Filter by action, e.g. SOS, LOGIN" /></div>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? <Spinner /> : (
          <>
            <Table head={["Time", "User", "Action", "Entity", "Details"]} empty={!data?.items.length}>
              {data?.items.map((l) => (
                <tr key={l.id} data-testid="audit-row">
                  <td className="whitespace-nowrap px-5 py-2.5 text-slate-500">{fmtDateTime(l.created_at)}</td>
                  <td className="whitespace-nowrap px-5 py-2.5">{l.user.full_name}</td>
                  <td className="px-5 py-2.5 font-mono text-xs font-semibold text-navy-800">{l.action}</td>
                  <td className="px-5 py-2.5 text-slate-600">{l.entity}{l.entity_id && ` #${l.entity_id}`}</td>
                  <td className="max-w-md px-5 py-2.5 text-slate-600">{l.detail}</td>
                </tr>
              ))}
            </Table>
            {data && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
          </>
        )}
      </Card>
    </>
  );
}
