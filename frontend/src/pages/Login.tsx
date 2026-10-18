import { ArrowRight, Building2, DoorOpen, Package, Siren } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, Input } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const DEMO = [
  { label: "Student", email: "priya.sharma@vista.demo", password: "Student@123" },
  { label: "Warden", email: "warden.lh@vista.demo", password: "Warden@123" },
  { label: "Chief Warden", email: "chief.warden@vista.demo", password: "Warden@123" },
  { label: "Maintenance staff", email: "maint1@vista.demo", password: "Staff@123" },
  { label: "Security staff", email: "security1@vista.demo", password: "Staff@123" },
  { label: "Administrator", email: "admin@vista.demo", password: "Admin@123" },
];

function Mark({ className = "h-10 w-10 text-xl" }: { className?: string }) {
  return (
    <span className={`flex items-center justify-center rounded-xl bg-vista-yellow font-extrabold text-vista-ink shadow-soft ${className}`} aria-hidden>
      V
    </span>
  );
}

/** Decorative hostel skyline drawn with simple shapes (no images). */
function Skyline() {
  return (
    <svg viewBox="0 0 400 180" className="w-full" aria-hidden>
      <rect x="20" y="70" width="90" height="110" rx="10" fill="#FFFEFA" opacity="0.55" />
      <rect x="125" y="30" width="110" height="150" rx="12" fill="#FFFEFA" opacity="0.8" />
      <rect x="250" y="85" width="130" height="95" rx="10" fill="#FFFEFA" opacity="0.55" />
      {[0, 1, 2, 3].map((r) =>
        [0, 1, 2].map((c) => <rect key={`${r}${c}`} x={142 + c * 30} y={50 + r * 28} width="16" height="14" rx="3" fill="#E9A23B" opacity={(r + c) % 3 === 0 ? 0.9 : 0.45} />),
      )}
      {[0, 1].map((r) => [0, 1].map((c) => <rect key={`a${r}${c}`} x={38 + c * 32} y={90 + r * 30} width="16" height="13" rx="3" fill="#E9A23B" opacity="0.45" />))}
      {[0, 1].map((r) => [0, 1, 2].map((c) => <rect key={`b${r}${c}`} x={270 + c * 36} y={105 + r * 30} width="18" height="13" rx="3" fill="#E9A23B" opacity="0.45" />))}
      <rect x="168" y="150" width="24" height="30" rx="4" fill="#493522" opacity="0.85" />
    </svg>
  );
}

export function AuthShell({ children, title, subtitle }: { children: ReactNode; title: string; subtitle: string }) {
  const features = [
    { icon: Building2, t: "Rooms & complaints" },
    { icon: DoorOpen, t: "Visitor approvals" },
    { icon: Siren, t: "Emergency SOS" },
    { icon: Package, t: "₹10 peer delivery" },
  ];
  return (
    <div className="relative min-h-screen overflow-hidden bg-vista-bg">
      <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-vista-yellow/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-vista-accent/15 blur-3xl" />
      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-2 lg:gap-16">
        <section className="hidden flex-col justify-between rounded-[2rem] bg-gradient-to-br from-vista-yellow to-vista-accent p-10 text-vista-ink shadow-soft lg:flex lg:min-h-[600px]">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-vista-card text-xl font-extrabold text-vista-ink" aria-hidden>
              V
            </span>
            <span className="text-xl font-extrabold tracking-wide">VISTA</span>
          </div>
          <div>
            <h2 className="text-4xl font-extrabold leading-tight">Hostel life,<br />simplified.</h2>
            <p className="mt-3 max-w-sm text-base font-medium text-vista-ink/80">Everything your hostel needs, in one place.</p>
            <ul className="mt-8 grid grid-cols-2 gap-3">
              {features.map((f) => (
                <li key={f.t} className="flex items-center gap-2.5 rounded-2xl bg-vista-card/70 px-3.5 py-3 text-sm font-semibold backdrop-blur">
                  <f.icon className="h-4 w-4 flex-none" aria-hidden />
                  {f.t}
                </li>
              ))}
            </ul>
          </div>
          <Skyline />
        </section>

        <section className="mx-auto w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Mark />
            <span className="text-xl font-extrabold tracking-wide text-vista-ink">VISTA</span>
          </div>
          <div className="rounded-[1.75rem] border border-vista-line bg-vista-card p-7 shadow-soft sm:p-9">
            <h1 className="text-2xl font-extrabold text-vista-ink sm:text-3xl">{title}</h1>
            <p className="mt-1.5 text-sm text-vista-muted-text">{subtitle}</p>
            <div className="mt-7">{children}</div>
          </div>
          <p className="mt-6 text-center text-xs text-vista-muted-text">VISTA · VIT Hostels · Academic demo with fictional data</p>
        </section>
      </div>
    </div>
  );
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string; registered?: boolean } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErr, setFieldErr] = useState<{ email?: string; password?: string }>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const fe: typeof fieldErr = {};
    if (!email.trim()) fe.email = "Email is required";
    if (!password) fe.password = "Password is required";
    setFieldErr(fe);
    if (Object.keys(fe).length) return;
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      nav(loc.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your VISTA account">
      {loc.state?.registered && <div className="mb-4"><Alert kind="success">Registration successful. You can sign in now.</Alert></div>}
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <Input label="Email" type="email" autoComplete="username" placeholder="you@vista.demo" value={email} onChange={(e) => setEmail(e.target.value)} error={fieldErr.email} name="email" />
        <Input label="Password" type="password" autoComplete="current-password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} error={fieldErr.password} name="password" />
        <Button type="submit" className="w-full py-3 text-[15px]" loading={busy}>
          Sign in <ArrowRight className="h-4 w-4" aria-hidden />
        </Button>
      </form>

      <div className="mt-6 flex items-center gap-3 text-xs text-vista-muted-text">
        <span className="h-px flex-1 bg-vista-line" />
        or try a demo account
        <span className="h-px flex-1 bg-vista-line" />
      </div>
      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {DEMO.map((d) => (
          <button
            key={d.email}
            type="button"
            title={d.email}
            onClick={() => {
              setEmail(d.email);
              setPassword(d.password);
              setFieldErr({});
            }}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${email === d.email ? "border-vista-accent bg-vista-soft text-vista-ink" : "border-vista-line bg-vista-bg text-vista-ink/80 hover:border-vista-yellow hover:bg-vista-soft"}`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <p className="mt-7 text-center text-sm text-vista-muted-text">
        New student?{" "}
        <Link to="/register" className="font-semibold text-vista-link hover:underline">
          Create an account
        </Link>
      </p>
    </AuthShell>
  );
}
