import { type FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../api/types";
import { Alert, Button, Card, Input, PageHeader, Select } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { label, ROLE_LABEL } from "../lib/format";
import { NAME_RE, PHONE_RE, passwordProblem } from "../lib/validation";

function Row({ k, v }: { k: string; v: string | number | null | undefined }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-0">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v || "—"}</dd>
    </div>
  );
}

export default function Profile() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ full_name: "", phone: "", programme: "", pref_sleep: "", pref_study: "", pref_food: "", looking_for_roommate: false });
  const [err, setErr] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [pwErr, setPwErr] = useState<string | null>(null);

  useEffect(() => {
    if (user)
      setF({ full_name: user.full_name, phone: user.phone, programme: user.programme, pref_sleep: user.pref_sleep, pref_study: user.pref_study, pref_food: user.pref_food, looking_for_roommate: user.looking_for_roommate });
  }, [user]);
  if (!user) return null;
  const isStudent = user.role === "STUDENT";

  async function save(e: FormEvent) {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (!NAME_RE.test(f.full_name.trim())) er.full_name = "Enter a valid name";
    if (!PHONE_RE.test(f.phone.trim())) er.phone = "Enter a valid 10-digit mobile number";
    setErr(er);
    if (Object.keys(er).length) return;
    setSaving(true);
    try {
      await api.put<User>("/api/profile", isStudent ? f : { full_name: f.full_name, phone: f.phone });
      await refresh();
      toast("success", "Profile updated");
    } catch (e2) {
      toast("error", (e2 as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function changePw(e: FormEvent) {
    e.preventDefault();
    const p = passwordProblem(pw.new_password);
    if (p) return setPwErr(p);
    setPwErr(null);
    try {
      await api.post("/api/profile/password", pw);
      setPw({ current_password: "", new_password: "" });
      toast("success", "Password changed");
    } catch (e2) {
      setPwErr((e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="My profile" subtitle="View and update your personal details." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Account" className="lg:col-span-1">
          <dl>
            <Row k="Role" v={ROLE_LABEL[user.role]} />
            <Row k="Email" v={user.email} />
            {isStudent && <Row k="Registration no." v={user.reg_no} />}
            {isStudent && <Row k="Year" v={user.year_of_study} />}
            {user.staff_type && <Row k="Team" v={label(user.staff_type)} />}
            <Row k="Hostel" v={user.room?.hostel ?? user.hostel_name} />
            {user.room && <Row k="Block / Room" v={`${user.room.block}-${user.room.number} (floor ${user.room.floor}, ${label(user.room.room_type)})`} />}
          </dl>
        </Card>
        <Card title="Edit details" className="lg:col-span-2">
          <form onSubmit={save} className="space-y-4" noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Full name" name="full_name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} error={err.full_name} />
              <Input label="Mobile number" name="phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} error={err.phone} />
            </div>
            {isStudent && (
              <>
                <Input label="Programme" name="programme" value={f.programme} onChange={(e) => setF({ ...f, programme: e.target.value })} />
                <p className="pt-2 text-sm font-semibold text-slate-700">Roommate preferences</p>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Select label="Sleep schedule" value={f.pref_sleep} onChange={(e) => setF({ ...f, pref_sleep: e.target.value })} options={["EARLY", "LATE"]} placeholder="No preference" />
                  <Select label="Study style" value={f.pref_study} onChange={(e) => setF({ ...f, pref_study: e.target.value })} options={["QUIET", "GROUP"]} placeholder="No preference" />
                  <Select label="Food" value={f.pref_food} onChange={(e) => setF({ ...f, pref_food: e.target.value })} options={["VEG", "NON_VEG"]} placeholder="No preference" />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={f.looking_for_roommate} onChange={(e) => setF({ ...f, looking_for_roommate: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
                  Show me in the roommate finder
                </label>
              </>
            )}
            <Button type="submit" loading={saving}>
              Save changes
            </Button>
          </form>
        </Card>
        <Card title="Change password" className="lg:col-span-3">
          <form onSubmit={changePw} className="grid gap-4 sm:grid-cols-3 sm:items-end" noValidate>
            <Input label="Current password" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" />
            <Input label="New password" type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" />
            <Button type="submit" variant="secondary">
              Update password
            </Button>
          </form>
          {pwErr && <div className="mt-3"><Alert>{pwErr}</Alert></div>}
        </Card>
      </div>
    </>
  );
}
