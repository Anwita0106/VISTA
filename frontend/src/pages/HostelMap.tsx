import { useState } from "react";
import type { Hostel } from "../api/types";
import { Alert, Card, PageHeader, Spinner } from "../components/ui";
import { cx } from "../lib/cx";
import { label } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface Loc { id: number; name: string; kind: string; x: number; y: number; description: string }
const COLORS: Record<string, string> = { BLOCK: "#8F5F14", MESS: "#b45309", GATE: "#047857", SERVICE: "#7c3aed" };

export default function HostelMap() {
  const map = useFetch<Loc[]>("/api/map");
  const hostels = useFetch<Hostel[]>("/api/hostels");
  const [sel, setSel] = useState<Loc | null>(null);
  const [kind, setKind] = useState("");
  const locs = (map.data ?? []).filter((l) => !kind || l.kind === kind);
  return (
    <>
      <PageHeader title="Hostel map" subtitle="Find hostel blocks, mess halls, gates and service points. Select a marker for details." />
      {map.error && <Alert>{map.error}</Alert>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter map">
            {["", "BLOCK", "MESS", "GATE", "SERVICE"].map((k) => (
              <button key={k} onClick={() => setKind(k)} aria-pressed={kind === k} className={cx("rounded-full border px-3 py-1 text-xs font-medium", kind === k ? "border-navy-700 bg-navy-700 text-white" : "border-slate-300 text-slate-700")}>{k ? label(k) : "All"}</button>
            ))}
          </div>
          {map.loading && !map.data ? <Spinner /> : (
            <svg viewBox="0 0 100 100" className="aspect-square w-full rounded-lg border border-slate-200 bg-[#FBF3E0]" role="img" aria-label="Campus hostel map">
              <path d="M50 100 V60 H8 M50 60 H92 M50 60 V8" stroke="#E3D2B4" strokeWidth="2.2" fill="none" />
              <rect x="42" y="38" width="16" height="14" rx="2" fill="#FAEFD9" />
              {locs.map((l) => (
                <g key={l.id} onClick={() => setSel(l)} className="cursor-pointer" tabIndex={0} role="button" aria-label={l.name} onKeyDown={(e) => e.key === "Enter" && setSel(l)}>
                  {l.kind === "BLOCK" ? <rect x={l.x - 7} y={l.y - 5} width="14" height="10" rx="1.5" fill={COLORS[l.kind]} opacity={sel?.id === l.id ? 1 : 0.85} /> : <circle cx={l.x} cy={l.y} r="2.8" fill={COLORS[l.kind]} stroke="#fff" strokeWidth="0.8" />}
                  <text x={l.x} y={l.kind === "BLOCK" ? l.y + 9 : l.y - 4} fontSize="2.6" textAnchor="middle" fill="#493522">{l.name.replace(/ \(.+\)/, "")}</text>
                </g>
              ))}
            </svg>
          )}
        </Card>
        <div className="space-y-6">
          <Card title={sel ? sel.name : "Location details"}>
            {sel ? <><p className="text-xs font-semibold uppercase text-slate-500">{label(sel.kind)}</p><p className="mt-1 text-sm text-slate-700">{sel.description}</p></> : <p className="text-sm text-slate-500">Select a marker on the map.</p>}
          </Card>
          <Card title="Hostels">
            {hostels.loading && !hostels.data ? <Spinner /> : (
              <ul className="space-y-3">
                {hostels.data?.map((h) => (
                  <li key={h.id} className="text-sm">
                    <p className="font-medium text-slate-800">{h.name}</p>
                    <p className="text-xs text-slate-500">Blocks {h.blocks.map((b) => b.name).join(", ")} · {h.occupied}/{h.capacity} beds occupied</p>
                    <div className="mt-1 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-navy-600" style={{ width: `${h.capacity ? (h.occupied / h.capacity) * 100 : 0}%` }} /></div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
