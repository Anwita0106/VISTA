import { AlertCircle, CheckCircle2, Inbox, Loader2, X } from "lucide-react";
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useEffect,
  useId,
  useRef,
} from "react";
import { cx } from "../lib/cx";
import { label as fmtLabel } from "../lib/format";


type Variant = "primary" | "secondary" | "danger" | "ghost" | "success";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-vista-accent text-vista-ink hover:bg-vista-accent-hover focus-visible:ring-vista-accent",
  secondary: "bg-white text-navy-800 border border-slate-300 hover:bg-slate-50 focus-visible:ring-navy-400",
  danger: "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
  success: "bg-emerald-600 text-white hover:bg-emerald-700 focus-visible:ring-emerald-500",
  ghost: "text-navy-700 hover:bg-navy-50 focus-visible:ring-navy-400",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-sm",
        VARIANTS[variant],
        className,
      )}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Card({ className, children, title, action }: { className?: string; children: ReactNode; title?: ReactNode; action?: ReactNode }) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-vista-line bg-vista-card shadow-soft", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-vista-line/70 px-5 py-3.5">
          <h2 className="text-[15px] font-semibold text-vista-ink">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-vista-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-vista-muted-text">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  OPEN: "bg-[#FFF4D6] text-[#7A4E0F] ring-[#F2D9A0]",
  PENDING: "bg-amber-50 text-amber-800 ring-amber-200",
  BOOKED: "bg-[#FFF4D6] text-[#7A4E0F] ring-[#F2D9A0]",
  IN_PROGRESS: "bg-[#FDEBDD] text-[#8A3F0E] ring-[#F5CDB0]",
  ACCEPTED: "bg-[#FDEBDD] text-[#8A3F0E] ring-[#F5CDB0]",
  PICKED_UP: "bg-[#FDEBDD] text-[#8A3F0E] ring-[#F5CDB0]",
  AT_GATE: "bg-[#FDEBDD] text-[#8A3F0E] ring-[#F5CDB0]",
  ACKNOWLEDGED: "bg-[#FDEBDD] text-[#8A3F0E] ring-[#F5CDB0]",
  ESCALATED: "bg-orange-50 text-orange-800 ring-orange-200",
  RAISED: "bg-red-50 text-red-800 ring-red-200",
  RESOLVED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  COMPLETED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  APPROVED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  DELIVERED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  COLLECTED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  VERIFIED: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  AVAILABLE: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  CLOSED: "bg-slate-100 text-slate-700 ring-slate-200",
  CLAIMED: "bg-slate-100 text-slate-700 ring-slate-200",
  SOLD: "bg-slate-100 text-slate-700 ring-slate-200",
  CANCELLED: "bg-slate-100 text-slate-700 ring-slate-200",
  EXPIRED: "bg-slate-100 text-slate-700 ring-slate-200",
  REJECTED: "bg-red-50 text-red-800 ring-red-200",
  FAILED: "bg-red-50 text-red-800 ring-red-200",
  LOCKED: "bg-red-50 text-red-800 ring-red-200",
  HIGH: "bg-red-50 text-red-800 ring-red-200",
  MEDIUM: "bg-amber-50 text-amber-800 ring-amber-200",
  LOW: "bg-slate-100 text-slate-700 ring-slate-200",
  LOST: "bg-orange-50 text-orange-800 ring-orange-200",
  FOUND: "bg-emerald-50 text-emerald-800 ring-emerald-200",
};

export function Badge({ value, className }: { value: string; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        STATUS_STYLE[value] ?? "bg-slate-100 text-slate-700 ring-slate-200",
        className,
      )}
      data-status={value}
    >
      {fmtLabel(value)}
    </span>
  );
}

export function Field({ label, error, hint, children, htmlFor, required }: { label: string; error?: string; hint?: string; children: ReactNode; htmlFor: string; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-600" aria-hidden>*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      {error && (
        <p className="text-xs text-red-700" role="alert" id={`${htmlFor}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}

const inputCls =
  "block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 transition focus:border-vista-accent focus:outline-none focus:ring-4 focus:ring-vista-yellow/30 disabled:bg-slate-100";

export function Input({ label, error, hint, id, required, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={fid} required={required}>
      <input id={fid} required={required} aria-invalid={!!error} aria-describedby={error ? `${fid}-error` : undefined} className={cx(inputCls, error && "border-red-400", className)} {...rest} />
    </Field>
  );
}

export function Textarea({ label, error, hint, id, required, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string; hint?: string }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={fid} required={required}>
      <textarea id={fid} required={required} aria-invalid={!!error} rows={3} className={cx(inputCls, error && "border-red-400")} {...rest} />
    </Field>
  );
}

export function Select({ label, error, id, options, required, placeholder, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; error?: string; options: (string | { value: string; label: string })[]; placeholder?: string }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Field label={label} error={error} htmlFor={fid} required={required}>
      <select id={fid} required={required} aria-invalid={!!error} className={cx(inputCls, error && "border-red-400")} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) =>
          typeof o === "string" ? (
            <option key={o} value={o}>
              {fmtLabel(o)}
            </option>
          ) : (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ),
        )}
      </select>
    </Field>
  );
}

export function FilterSelect({ value, onChange, options, ariaLabel, all = "All" }: { value: string; onChange: (v: string) => void; options: string[]; ariaLabel: string; all?: string }) {
  return (
    <select aria-label={ariaLabel} value={value} onChange={(e) => onChange(e.target.value)} className="w-auto rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus:border-navy-500 focus:outline-none focus:ring-2 focus:ring-navy-200">
      <option value="">{all}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {fmtLabel(o)}
        </option>
      ))}
    </select>
  );
}

export function SearchBox({ value, onChange, placeholder = "Search…" }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input type="search" aria-label={placeholder} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={cx(inputCls, "w-full py-1.5 sm:w-64")} />;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500" role="status">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> {label}
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 px-6 py-10 text-center">
      <Inbox className="h-8 w-8 text-slate-400" aria-hidden />
      <p className="mt-3 font-medium text-slate-700">{title}</p>
      {message && <p className="mt-1 max-w-sm text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  const style = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-navy-200 bg-navy-50 text-navy-800",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[kind];
  const Icon = kind === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div className={cx("flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm", style)} role={kind === "error" ? "alert" : "status"}>
      <Icon className="mt-0.5 h-4 w-4 flex-none" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("input, select, textarea, button:not([data-close])");
    first?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-vista-ink/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} className={cx("max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white shadow-xl sm:rounded-2xl", wide ? "sm:max-w-2xl" : "sm:max-w-lg")}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <button data-close onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100" aria-label="Close dialog">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <nav className="mt-4 flex items-center justify-between text-sm text-slate-600" aria-label="Pagination">
      <span>
        Page {page} of {pages} · {total} records
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}

export function StatCard({ label, value, icon, tone = "navy", hint }: { label: string; value: ReactNode; icon: ReactNode; tone?: "navy" | "amber" | "red" | "emerald" | "violet"; hint?: string }) {
  // muted yellow icon chips; red is kept only where it carries meaning (SOS)
  const chip = tone === "red" ? "bg-red-50 text-red-700" : "bg-vista-soft text-vista-link";
  return (
    <div className="rounded-2xl border border-vista-line bg-vista-card p-4 shadow-soft">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-vista-muted-text">{label}</p>
        <span className={cx("rounded-xl p-2", chip)}>{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-bold text-vista-ink" data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-vista-muted-text">{hint}</p>}
    </div>
  );
}

export function Table({ head, children, empty }: { head: string[]; children: ReactNode; empty?: boolean }) {
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
            {head.map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap px-5 py-2.5">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {empty && <p className="px-5 py-8 text-center text-sm text-slate-500">No records to show.</p>}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { value: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cx(
            "-mb-px whitespace-nowrap border-b-2 px-3.5 py-2 text-sm font-medium",
            value === t.value ? "border-navy-700 text-navy-800" : "border-transparent text-slate-600 hover:text-slate-900",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
