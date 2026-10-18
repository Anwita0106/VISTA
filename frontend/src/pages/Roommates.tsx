import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { qs } from "../api/client";
import { Alert, Button, Card, EmptyState, FilterSelect, PageHeader, Spinner, Table } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { label } from "../lib/format";
import { useFetch } from "../lib/hooks";

interface Match { id: number; full_name: string; reg_no: string; programme: string; year_of_study: number; pref_sleep: string; pref_study: string; pref_food: string; score: number; max_score: number; room: string | null }
interface Res { matches: Match[]; rooms_with_vacancy: { id: number; label: string; room_type: string; free_beds: number }[] }

export default function Roommates() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [sleep, setSleep] = useState("");
  const [study, setStudy] = useState("");
  const [food, setFood] = useState("");
  const { data, loading, error } = useFetch<Res>(`/api/roommates${qs({ sleep, study, food })}`);
  return (
    <>
      <PageHeader title="Roommate finder" subtitle="Students looking for a roommate, ranked by how well their preferences match yours." />
      {!user?.looking_for_roommate && <div className="mb-4"><Alert kind="info">You are not listed in the finder. Turn it on in <Link className="underline" to="/profile">My profile</Link> so others can find you.</Alert></div>}
      <div className="mb-4 flex flex-wrap gap-2">
        <FilterSelect ariaLabel="Sleep" value={sleep} onChange={setSleep} options={["EARLY", "LATE"]} all="Sleep: my preference" />
        <FilterSelect ariaLabel="Study" value={study} onChange={setStudy} options={["QUIET", "GROUP"]} all="Study: my preference" />
        <FilterSelect ariaLabel="Food" value={food} onChange={setFood} options={["VEG", "NON_VEG"]} all="Food: my preference" />
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card title="Matches" className="lg:col-span-2">
            {!data?.matches.length ? <EmptyState title="No students are looking for a roommate right now" /> : (
              <Table head={["Student", "Preferences", "Match", ""]}>
                {data.matches.map((m) => (
                  <tr key={m.id} data-testid="roommate-row">
                    <td className="px-5 py-3"><p className="font-medium">{m.full_name}</p><p className="text-xs text-slate-500">{m.programme} · Year {m.year_of_study} · {m.room ?? "No room"}</p></td>
                    <td className="px-5 py-3 text-xs text-slate-600">{[m.pref_sleep, m.pref_study, m.pref_food].filter(Boolean).map(label).join(" · ") || "—"}</td>
                    <td className="px-5 py-3"><span className="font-semibold text-navy-800">{m.score}/{m.max_score || 3}</span></td>
                    <td className="px-5 py-3"><Button size="sm" variant="secondary" onClick={() => nav(`/messages?u=${m.id}`)}>Message</Button></td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
          <Card title="Rooms with free beds">
            <ul className="space-y-2 text-sm">
              {data?.rooms_with_vacancy.slice(0, 12).map((r) => (
                <li key={r.id} className="flex justify-between gap-2"><span>{r.label} <span className="text-xs text-slate-500">({label(r.room_type)})</span></span><span className="font-medium text-emerald-700">{r.free_beds} free</span></li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-500">Room changes are approved by the hostel office.</p>
          </Card>
        </div>
      )}
    </>
  );
}
