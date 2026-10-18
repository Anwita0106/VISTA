import { Siren } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { SOSAlert } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, timeAgo } from "../lib/format";
import { useFetch } from "../lib/hooks";

const DISCLAIMER = "Demonstration system: VISTA SOS alerts reach hostel wardens and security inside this app only. It is NOT connected to police, ambulance or any real emergency service. In a real emergency call 112.";

export default function Sos() {
  const { user } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const { data, loading, error, reload } = useFetch<SOSAlert[]>("/api/sos");
  const [confirming, setConfirming] = useState(params.get("raise") === "1");
  const [msg, setMsg] = useState("");
  const [loc, setLoc] = useState("");
  const [busy, setBusy] = useState(false);
  const [resolveNote, setResolveNote] = useState<Record<number, string>>({});
  const isStudent = user?.role === "STUDENT";

  useEffect(() => {
    if (params.get("raise") === "1") setConfirming(true);
  }, [params]);
  useEffect(() => {
    if (isStudent) return;
    const t = setInterval(() => void reload(), 10000);
    return () => clearInterval(t);
  }, [isStudent, reload]);
  if (!user) return null;

  async function send() {
    setBusy(true);
    try {
      const a = await api.post<SOSAlert>("/api/sos", { message: msg, location: loc, confirm: true });
      toast("success", `SOS sent to wardens and security (${a.notification_delay_ms ?? 0} ms)`);
      setConfirming(false);
      setParams({});
      setMsg("");
      void reload();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function act(id: number, action: "acknowledge" | "resolve") {
    try {
      await api.patch(`/api/sos/${id}/${action}`, action === "resolve" ? { note: resolveNote[id] ?? "" } : {});
      toast("success", action === "acknowledge" ? "Alert acknowledged – student notified" : "Alert resolved");
      void reload();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }

  return (
    <>
      <PageHeader title={isStudent ? "Emergency SOS" : "SOS alerts"} subtitle={isStudent ? "Send an immediate alert to your warden and hostel security." : "Respond to student emergency alerts. This page refreshes every 10 seconds."} />
      <div className="mb-6"><Alert kind="warning">{DISCLAIMER}</Alert></div>
      {isStudent && (
        <Card className="mb-6">
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <button onClick={() => setConfirming(true)} className="flex h-36 w-36 flex-col items-center justify-center rounded-full bg-red-600 text-white shadow-lg ring-8 ring-red-100 transition hover:bg-red-700 focus:outline-none focus-visible:ring-red-300" data-testid="sos-big-button">
              <Siren className="h-10 w-10" aria-hidden />
              <span className="mt-1 text-xl font-bold">SOS</span>
            </button>
            <p className="max-w-md text-sm text-slate-600">You will be asked to confirm before the alert is sent. Your name, phone number and room are shared with the responders.</p>
          </div>
        </Card>
      )}
      <Card title={isStudent ? "My alerts" : "Alerts"}>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? (
          <Spinner />
        ) : !data?.length ? (
          <EmptyState title="No SOS alerts" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.map((a) => (
              <li key={a.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between" data-testid="sos-row">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge value={a.status} />
                    <span className="text-xs text-slate-500">#{a.id} · {timeAgo(a.created_at)}</span>
                  </div>
                  <p className="mt-1.5 font-medium text-slate-800">{isStudent ? a.location : `${a.student.full_name} (${a.student.reg_no}) · ${a.student.phone}`}</p>
                  {!isStudent && <p className="text-sm text-slate-600">{a.location}</p>}
                  {a.message && <p className="text-sm text-slate-600">“{a.message}”</p>}
                  <p className="mt-1 text-xs text-slate-500">
                    Raised {fmtDateTime(a.created_at)} · responders notified in {a.notification_delay_ms ?? "—"} ms
                    {a.acknowledged_by && ` · acknowledged by ${a.acknowledged_by.full_name} at ${fmtDateTime(a.acknowledged_at)}`}
                    {a.resolved_by && ` · resolved by ${a.resolved_by.full_name} at ${fmtDateTime(a.resolved_at)}`}
                  </p>
                  {a.resolution_note && <p className="text-xs text-slate-600">Resolution: {a.resolution_note}</p>}
                </div>
                {!isStudent && a.status !== "RESOLVED" && (
                  <div className="flex flex-none flex-col gap-2 sm:w-64">
                    {a.status === "RAISED" ? (
                      <Button variant="danger" size="sm" onClick={() => act(a.id, "acknowledge")}>Acknowledge</Button>
                    ) : (
                      <>
                        <input aria-label="Resolution note" placeholder="Resolution note" className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm" value={resolveNote[a.id] ?? ""} onChange={(e) => setResolveNote({ ...resolveNote, [a.id]: e.target.value })} />
                        <Button variant="success" size="sm" onClick={() => act(a.id, "resolve")}>Mark resolved</Button>
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Modal
        open={confirming && isStudent}
        onClose={() => { setConfirming(false); setParams({}); }}
        title="Send SOS alert?"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setConfirming(false); setParams({}); }}>Cancel</Button>
            <Button variant="danger" loading={busy} onClick={send} data-testid="confirm-sos">Yes, send SOS now</Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-700">This immediately alerts the wardens and hostel security on duty.</p>
          <Input label="Where are you? (optional)" name="location" value={loc} onChange={(e) => setLoc(e.target.value)} hint={user.room ? `Leave blank to use ${user.room.hostel} ${user.room.block}-${user.room.number}` : undefined} />
          <Textarea label="What is happening? (optional)" name="message" value={msg} onChange={(e) => setMsg(e.target.value)} />
          <p className="text-xs text-slate-500">{DISCLAIMER}</p>
        </div>
      </Modal>
    </>
  );
}
