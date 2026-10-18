import { ArrowLeft, Camera, KeyRound, QrCode } from "lucide-react";
import QRCode from "qrcode";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../api/client";
import type { Delivery } from "../api/types";
import { Alert, Badge, Button, Card, Input, PageHeader, Spinner, Tabs, Textarea } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { fmtDateTime, inr, label } from "../lib/format";
import { useFetch } from "../lib/hooks";

const STEPS = ["OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED"];

function Progress({ status }: { status: string }) {
  const idx = STEPS.indexOf(status);
  if (idx < 0) return <Badge value={status} />;
  return (
    <ol className="flex items-center gap-2 text-xs" aria-label="Delivery progress">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold ${i <= idx ? "bg-navy-700 text-white" : "bg-slate-200 text-slate-500"}`}>{i + 1}</span>
          <span className={i <= idx ? "font-medium text-slate-800" : "text-slate-500"}>{label(s)}</span>
          {i < STEPS.length - 1 && <span className="hidden h-px w-6 bg-slate-300 sm:block" />}
        </li>
      ))}
    </ol>
  );
}

type Detector = { detect: (src: CanvasImageSource) => Promise<{ rawValue: string }[]> };

function QrScanner({ onResult }: { onResult: (v: string) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [active, setActive] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const supported = typeof window !== "undefined" && "BarcodeDetector" in window;
  useEffect(() => {
    if (!active) return;
    let stream: MediaStream | null = null;
    let stop = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        const Ctor = (window as unknown as { BarcodeDetector: new (o: object) => Detector }).BarcodeDetector;
        const det = new Ctor({ formats: ["qr_code"] });
        while (!stop && videoRef.current) {
          const codes = await det.detect(videoRef.current);
          if (codes[0]?.rawValue) {
            onResult(codes[0].rawValue);
            setActive(false);
            break;
          }
          await new Promise((r) => setTimeout(r, 300));
        }
      } catch {
        setMsg("Camera not available. Enter the code shown under the receiver's QR instead.");
        setActive(false);
      }
    })();
    return () => {
      stop = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [active, onResult]);
  if (!supported) return <p className="text-xs text-slate-500">Camera QR scanning is not supported in this browser – type or paste the code shown under the receiver's QR.</p>;
  return (
    <div className="space-y-2">
      {active ? <video ref={videoRef} className="w-full rounded-lg bg-black" muted playsInline /> : <Button type="button" size="sm" variant="secondary" onClick={() => setActive(true)}><Camera className="h-4 w-4" /> Scan with camera</Button>}
      {msg && <p className="text-xs text-amber-700">{msg}</p>}
    </div>
  );
}

export default function DeliveryDetail() {
  const { id } = useParams();
  const toast = useToast();
  const { data: d, loading, error, setData, reload } = useFetch<Delivery>(`/api/deliveries/${id}`);
  const [busy, setBusy] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [otpErr, setOtpErr] = useState<string | null>(null);
  const [method, setMethod] = useState<"OTP" | "QR">("OTP");
  const [qr, setQr] = useState({ qr_token: "", receiver_name: "", receiver_reg_no: "", receiver_room: "", receiver_block: "" });
  const [photo, setPhoto] = useState<File | null>(null);
  const [qrErr, setQrErr] = useState<string | null>(null);
  const [qrImg, setQrImg] = useState<string | null>(null);
  const [failReason, setFailReason] = useState("");

  useEffect(() => {
    if (d?.qr_token) void QRCode.toDataURL(`VISTA:${d.code}:${d.qr_token}`, { width: 220, margin: 1 }).then(setQrImg);
    else setQrImg(null);
  }, [d?.qr_token, d?.code]);
  useEffect(() => {
    const t = setInterval(() => void reload(), 15000);
    return () => clearInterval(t);
  }, [reload]);

  if (loading && !d) return <Spinner />;
  if (error || !d) return <Alert>{error ?? "Delivery not found"}</Alert>;

  async function action(path: string, body?: Record<string, unknown>, okMsg?: string) {
    setBusy(path);
    try {
      setData(await api.post<Delivery>(`/api/deliveries/${id}/${path}`, body));
      if (okMsg) toast("success", okMsg);
      return true;
    } catch (e) {
      toast("error", (e as Error).message);
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function submitOtp(e: FormEvent) {
    e.preventDefault();
    if (!/^\d{6}$/.test(otp)) return setOtpErr("Enter the 6-digit OTP");
    setBusy("otp");
    setOtpErr(null);
    try {
      setData(await api.post<Delivery>(`/api/deliveries/${id}/verify-otp`, { otp }));
      toast("success", "Handover verified – delivery completed");
    } catch (e2) {
      setOtpErr((e2 as Error).message);
      void reload();
    } finally {
      setBusy(null);
      setOtp("");
    }
  }

  async function submitQr(e: FormEvent) {
    e.preventDefault();
    if (!photo) return setQrErr("Upload a photo of the parcel");
    const token = qr.qr_token.trim().replace(/^VISTA:[^:]+:/, "");
    const fd = new FormData();
    Object.entries({ ...qr, qr_token: token }).forEach(([k, v]) => fd.append(k, v));
    fd.append("photo", photo);
    setBusy("qr");
    setQrErr(null);
    try {
      setData(await api.post<Delivery>(`/api/deliveries/${id}/verify-qr`, fd));
      toast("success", "QR + photo verified – delivery completed");
    } catch (e2) {
      setQrErr((e2 as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const role = d.my_role;
  return (
    <>
      <Link to="/delivery" className="mb-3 inline-flex items-center gap-1 text-sm text-navy-700 hover:underline"><ArrowLeft className="h-4 w-4" /> Back to deliveries</Link>
      <PageHeader title={`${d.code} · ${d.item_description}`} subtitle={`${d.pickup_hostel} → ${d.drop_hostel} · fixed fee ${inr(d.fee)}`} />
      <Card className="mb-6"><div className="flex flex-wrap items-center justify-between gap-3"><Progress status={d.status} /><span data-testid="delivery-status"><Badge value={d.status} /></span></div></Card>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {role === "VIEWER" && d.status === "OPEN" && (
            <Card title="Carry this item">
              <p className="text-sm text-slate-600">Heading to {d.drop_hostel}? Accept this request, collect the item from {d.sender.full_name} at {d.pickup_point}, and hand it over to {d.receiver.full_name}.</p>
              <Button className="mt-4" loading={busy === "accept"} onClick={() => action("accept", undefined, "You accepted the delivery")} data-testid="accept-delivery">Accept delivery</Button>
            </Card>
          )}
          {role === "CARRIER" && d.status === "ACCEPTED" && (
            <Card title="Next step: collect the item">
              <p className="text-sm text-slate-600">Collect the item from {d.sender.full_name} at <strong>{d.pickup_point}</strong>. Marking it picked up sends a one-time password to the receiver.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button loading={busy === "pickup"} onClick={() => action("pickup", undefined, "Picked up – OTP sent to receiver")} data-testid="pickup-delivery">Mark picked up</Button>
                <Button variant="secondary" loading={busy === "release"} onClick={() => action("release", undefined, "Delivery released")}>I can't carry it</Button>
              </div>
            </Card>
          )}
          {role === "CARRIER" && d.status === "PICKED_UP" && (
            <Card title="Confirm handover">
              <Tabs value={method} onChange={setMethod} tabs={[{ value: "OTP", label: "OTP from receiver" }, { value: "QR", label: "QR code + photo" }]} />
              {method === "OTP" ? (
                <form onSubmit={submitOtp} className="space-y-3" noValidate>
                  <p className="text-sm text-slate-600">Ask {d.receiver.full_name} for the 6-digit OTP shown in their VISTA app.</p>
                  {d.otp_active ? (
                    <p className="text-xs text-slate-500" data-testid="otp-meta">OTP valid until {fmtDateTime(d.otp_expires_at)} · {d.otp_attempts_left} attempt(s) left</p>
                  ) : (
                    <Alert kind="warning">No active OTP (expired or locked after 3 wrong attempts). Request a new one below.</Alert>
                  )}
                  {otpErr && <Alert>{otpErr}</Alert>}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <div className="sm:w-48"><Input label="OTP" name="otp" inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} autoComplete="one-time-code" /></div>
                    <Button type="submit" loading={busy === "otp"} disabled={!d.otp_active}><KeyRound className="h-4 w-4" /> Verify OTP</Button>
                    {!d.otp_active && <Button type="button" variant="secondary" loading={busy === "otp/resend"} onClick={() => action("otp/resend", undefined, "New OTP sent to the receiver")}>Send new OTP</Button>}
                  </div>
                </form>
              ) : (
                <form onSubmit={submitQr} className="space-y-3" noValidate>
                  <p className="text-sm text-slate-600">Scan the QR on the receiver's phone, photograph the parcel and enter the receiver's details from their ID card.</p>
                  {qrErr && <Alert>{qrErr}</Alert>}
                  <QrScanner onResult={(v) => setQr((q) => ({ ...q, qr_token: v }))} />
                  <Input label="QR code value" name="qr_token" value={qr.qr_token} onChange={(e) => setQr({ ...qr, qr_token: e.target.value })} />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input label="Receiver name" name="receiver_name" value={qr.receiver_name} onChange={(e) => setQr({ ...qr, receiver_name: e.target.value })} />
                    <Input label="Registration no." name="receiver_reg_no" value={qr.receiver_reg_no} onChange={(e) => setQr({ ...qr, receiver_reg_no: e.target.value })} />
                    <Input label="Room no." name="receiver_room" value={qr.receiver_room} onChange={(e) => setQr({ ...qr, receiver_room: e.target.value })} />
                    <Input label="Hostel block" name="receiver_block" value={qr.receiver_block} onChange={(e) => setQr({ ...qr, receiver_block: e.target.value })} />
                  </div>
                  <Input label="Parcel photo (JPEG/PNG, max 2 MB)" name="photo" type="file" accept="image/png,image/jpeg" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
                  <Button type="submit" loading={busy === "qr"}><QrCode className="h-4 w-4" /> Verify &amp; complete</Button>
                </form>
              )}
              <details className="mt-6 rounded-lg border border-slate-200 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">Report a handover problem</summary>
                <div className="mt-3 space-y-2">
                  <Textarea label="What went wrong?" name="reason" value={failReason} onChange={(e) => setFailReason(e.target.value)} />
                  <Button variant="danger" size="sm" disabled={failReason.trim().length < 5} loading={busy === "fail"} onClick={() => action("fail", { reason: failReason }, "Handover failure reported")}>Report failure</Button>
                </div>
              </details>
            </Card>
          )}
          {role === "RECEIVER" && d.status === "PICKED_UP" && (
            <Card title="Receive your item">
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <p className="text-sm font-medium text-slate-700">Option 1 – tell the carrier this OTP</p>
                  {d.otp ? (
                    <>
                      <p className="mt-2 font-mono text-3xl font-bold tracking-[0.3em] text-navy-800" data-testid="receiver-otp">{d.otp}</p>
                      <p className="mt-1 text-xs text-slate-500">Valid until {fmtDateTime(d.otp_expires_at)}. Share it only when you have the item in hand.</p>
                    </>
                  ) : (
                    <div className="mt-2 space-y-2">
                      <p className="text-sm text-slate-500">No active OTP.</p>
                      <Button size="sm" variant="secondary" loading={busy === "otp/resend"} onClick={() => action("otp/resend", undefined, "New OTP generated")}>Get a new OTP</Button>
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">Option 2 – let the carrier scan this QR</p>
                  {qrImg && <img src={qrImg} alt="Handover QR code" className="mt-2 h-44 w-44 rounded border border-slate-200" data-testid="receiver-qr" />}
                  <p className="mt-1 break-all font-mono text-[11px] text-slate-500" data-testid="receiver-qr-text">{d.qr_token}</p>
                </div>
              </div>
            </Card>
          )}
          {role === "SENDER" && d.status === "OPEN" && (
            <Card title="Waiting for a carrier">
              <p className="text-sm text-slate-600">Students travelling to {d.drop_hostel} can see and accept your request.</p>
              <Button className="mt-4" variant="secondary" loading={busy === "cancel"} onClick={() => action("cancel", undefined, "Delivery cancelled – demo fee refunded")}>Cancel request</Button>
            </Card>
          )}
          {d.status === "DELIVERED" && <Alert kind="success">Delivered on {fmtDateTime(d.delivered_at)}. Handover verified.</Alert>}
          {d.status === "FAILED" && <Alert>Handover failed: {d.failure_reason}. The demo fee was refunded.</Alert>}
          <Card title="Verification log">
            {d.verifications.length ? (
              <ul className="space-y-2 text-sm" data-testid="verification-log">
                {d.verifications.map((v) => (
                  <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2 last:border-0">
                    <span>{v.method === "OTP" ? "OTP" : "QR + photo"} · {fmtDateTime(v.created_at)} {v.attempts > 0 && `· ${v.attempts} attempt(s)`}</span>
                    <span className="flex items-center gap-2">
                      {v.photo && <button className="text-xs text-navy-700 underline" onClick={() => void downloadFile(v.photo!.url, v.photo!.name)}>Photo</button>}
                      <Badge value={v.status} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-500">No handover attempts yet.</p>}
          </Card>
        </div>
        <Card title="Details">
          <dl className="space-y-3 text-sm">
            <div><dt className="text-slate-500">Sender</dt><dd className="font-medium">{d.sender.full_name} ({d.sender.reg_no})</dd></div>
            <div><dt className="text-slate-500">Receiver</dt><dd className="font-medium">{d.receiver.full_name} · {d.drop_hostel}</dd></div>
            <div><dt className="text-slate-500">Carrier</dt><dd className="font-medium">{d.carrier?.full_name ?? "Not yet assigned"}</dd></div>
            <div><dt className="text-slate-500">Pickup point</dt><dd className="font-medium">{d.pickup_point}</dd></div>
            {d.payment && <div><dt className="text-slate-500">Payment (demo)</dt><dd className="font-medium">{inr(d.payment.amount)} · {label(d.payment.status)}<br /><span className="font-mono text-xs">{d.payment.receipt_no}</span></dd></div>}
            <div><dt className="text-slate-500">Timeline</dt><dd className="text-xs text-slate-600">Posted {fmtDateTime(d.created_at)}<br />Accepted {fmtDateTime(d.accepted_at)}<br />Picked up {fmtDateTime(d.picked_up_at)}<br />Delivered {fmtDateTime(d.delivered_at)}</dd></div>
          </dl>
        </Card>
      </div>
    </>
  );
}
