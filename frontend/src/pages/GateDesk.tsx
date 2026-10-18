import { useState } from "react";
import { api, qs } from "../api/client";
import type { GateDelivery } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, FilterSelect, PageHeader, Spinner, Table } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { fmtDate, label } from "../lib/format";
import { useFetch } from "../lib/hooks";

export default function GateDesk() {
  const toast = useToast();
  const [status, setStatus] = useState("BOOKED");
  const { data, loading, error, reload } = useFetch<GateDelivery[]>(`/api/gate-deliveries${qs({ status })}`);
  const [otp, setOtp] = useState<Record<number, string>>({});
  const [errs, setErrs] = useState<Record<number, string>>({});

  async function arrived(id: number) {
    try {
      await api.patch(`/api/gate-deliveries/${id}/arrived`);
      toast("success", "Student notified that the delivery is at the gate");
      void reload();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }
  async function collect(id: number) {
    try {
      await api.post(`/api/gate-deliveries/${id}/collect`, { otp: otp[id] ?? "" });
      toast("success", "OTP verified – handed over");
      setErrs({ ...errs, [id]: "" });
      void reload();
    } catch (e) {
      setErrs({ ...errs, [id]: (e as Error).message });
    }
  }

  return (
    <>
      <PageHeader title="Gate desk" subtitle="Food deliveries and parcels booked by students. Verify the student's OTP before handing over." />
      <Card action={<FilterSelect ariaLabel="Filter by status" value={status} onChange={setStatus} options={["BOOKED", "AT_GATE", "COLLECTED", "CANCELLED"]} />} title="Gate deliveries">
        {error && <Alert>{error}</Alert>}
        {loading && !data ? <Spinner /> : !data?.length ? <EmptyState title="Nothing here" /> : (
          <Table head={["Code", "Student", "Vendor / courier", "Expected", "Status", "Action"]}>
            {data.map((g) => (
              <tr key={g.id} data-testid="gate-desk-row">
                <td className="px-5 py-3 font-mono text-xs font-semibold">{g.code}</td>
                <td className="px-5 py-3"><p className="font-medium">{g.student.full_name}</p><p className="text-xs text-slate-500">{g.student.reg_no} · {g.student.room}</p></td>
                <td className="px-5 py-3"><p>{g.vendor} <span className="text-xs text-slate-500">({label(g.kind)})</span></p><p className="text-xs text-slate-500">{g.courier_name} {g.courier_phone}</p></td>
                <td className="whitespace-nowrap px-5 py-3 text-slate-600">{fmtDate(g.expected_date)} {g.expected_time}<br /><span className="text-xs">{g.gate}</span></td>
                <td className="px-5 py-3"><Badge value={g.status} /></td>
                <td className="px-5 py-3">
                  {g.status === "BOOKED" && <Button size="sm" onClick={() => arrived(g.id)}>Mark arrived</Button>}
                  {g.status === "AT_GATE" && (
                    <div className="flex flex-col gap-1.5">
                      <div className="flex gap-2">
                        <input aria-label={`OTP for ${g.code}`} inputMode="numeric" maxLength={6} placeholder="OTP" className="w-24 rounded-lg border border-slate-300 px-2 py-1.5 font-mono text-sm" value={otp[g.id] ?? ""} onChange={(e) => setOtp({ ...otp, [g.id]: e.target.value.replace(/\D/g, "") })} />
                        <Button size="sm" variant="success" onClick={() => collect(g.id)}>Verify</Button>
                      </div>
                      {errs[g.id] && <p className="text-xs text-red-700" role="alert">{errs[g.id]}</p>}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  );
}
