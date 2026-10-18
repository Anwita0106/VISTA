import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Alert, Button, Input, Select } from "../components/ui";
import { validateRegistration, type RegistrationForm } from "../lib/validation";
import { AuthShell } from "./Login";

const EMPTY: RegistrationForm = { full_name: "", email: "", password: "", confirm: "", reg_no: "", phone: "", programme: "", year_of_study: "1", gender: "" };

export default function Register() {
  const nav = useNavigate();
  const [f, setF] = useState<RegistrationForm>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof RegistrationForm, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof RegistrationForm) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs = validateRegistration(f);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      const { confirm: _c, ...body } = f;
      void _c;
      await api.post("/api/auth/register", { ...body, year_of_study: Number(f.year_of_study) });
      nav("/login", { state: { registered: true } });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Student registration · rooms are allotted by the hostel office">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <Input label="Full name" value={f.full_name} onChange={set("full_name")} error={errors.full_name} name="full_name" required />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Registration number" placeholder="24BCE1234" value={f.reg_no} onChange={set("reg_no")} error={errors.reg_no} name="reg_no" required />
          <Input label="Mobile number" inputMode="numeric" value={f.phone} onChange={set("phone")} error={errors.phone} name="phone" required />
        </div>
        <Input label="Email" type="email" value={f.email} onChange={set("email")} error={errors.email} name="email" required />
        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Programme" value={f.programme} onChange={set("programme")} name="programme" placeholder="B.Tech CSE" />
          <Select label="Year" value={f.year_of_study} onChange={set("year_of_study")} options={["1", "2", "3", "4", "5"].map((v) => ({ value: v, label: `Year ${v}` }))} name="year_of_study" />
          <Select label="Gender" value={f.gender} onChange={set("gender")} error={errors.gender} options={["FEMALE", "MALE", "OTHER"]} placeholder="Select" name="gender" required />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Password" type="password" autoComplete="new-password" value={f.password} onChange={set("password")} error={errors.password} hint="8+ characters with letters and digits" name="password" required />
          <Input label="Confirm password" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} error={errors.confirm} name="confirm" required />
        </div>
        <Button type="submit" className="w-full" loading={busy}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        Already registered?{" "}
        <Link to="/login" className="font-medium text-navy-700 underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
