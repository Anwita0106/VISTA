import {
  Bell, BookOpen, Building2, ClipboardList, FileLock2, Gauge, LogOut, Map, Menu, MessageSquare, Megaphone, Package,
  ScrollText, Search, ShieldAlert, ShoppingBag, Siren, Sparkles, UserCircle2, Users, UtensilsCrossed, X, BarChart3, DoorOpen,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { Role, User } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { useFetch } from "../lib/hooks";
import { ROLE_LABEL } from "../lib/format";
import { cx } from "../lib/cx";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: Role[];
  show?: (u: User) => boolean;
}
const ALL: Role[] = ["STUDENT", "WARDEN", "CHIEF_WARDEN", "STAFF", "ADMIN"];
const MGMT: Role[] = ["WARDEN", "CHIEF_WARDEN", "ADMIN"];
const isSecurity = (u: User) => u.role !== "STAFF" || u.staff_type === "SECURITY";

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: Gauge, roles: ALL },
      { to: "/notices", label: "Notice Board", icon: Megaphone, roles: ALL },
      { to: "/messages", label: "Messages", icon: MessageSquare, roles: ALL },
      { to: "/profile", label: "My Profile", icon: UserCircle2, roles: ALL },
    ],
  },
  {
    section: "Hostel Services",
    items: [
      { to: "/complaints", label: "Complaints", icon: ClipboardList, roles: ALL },
      { to: "/visitors", label: "Visitors", icon: DoorOpen, roles: ["STUDENT", ...MGMT, "STAFF"], show: isSecurity },
      { to: "/services", label: "Sick Meal & Cleaning", icon: Sparkles, roles: ["STUDENT", ...MGMT, "STAFF"], show: (u) => u.role !== "STAFF" || ["MESS", "CLEANING"].includes(u.staff_type ?? "") },
      { to: "/sos", label: "Emergency SOS", icon: Siren, roles: ["STUDENT", ...MGMT, "STAFF"], show: isSecurity },
      { to: "/mess-feedback", label: "Mess Feedback", icon: UtensilsCrossed, roles: ["STUDENT", ...MGMT, "STAFF"], show: (u) => u.role !== "STAFF" || u.staff_type === "MESS" },
    ],
  },
  {
    section: "Delivery",
    items: [
      { to: "/delivery", label: "Deliveries", icon: Package, roles: ["STUDENT", ...MGMT] },
      { to: "/gate", label: "Gate Desk", icon: ShieldAlert, roles: ["STAFF", ...MGMT], show: isSecurity },
    ],
  },
  {
    section: "Community",
    items: [
      { to: "/lost-found", label: "Lost & Found", icon: Search, roles: ALL },
      { to: "/marketplace", label: "Marketplace", icon: ShoppingBag, roles: ["STUDENT", "ADMIN"] },
      { to: "/notes", label: "Notes Sharing", icon: BookOpen, roles: ["STUDENT", "ADMIN"] },
      { to: "/vault", label: "Document Vault", icon: FileLock2, roles: ["STUDENT"] },
      { to: "/roommates", label: "Roommate Finder", icon: Users, roles: ["STUDENT"] },
      { to: "/map", label: "Hostel Map", icon: Map, roles: ALL },
    ],
  },
  {
    section: "Administration",
    items: [
      { to: "/admin/users", label: "Users", icon: Users, roles: MGMT },
      { to: "/admin/hostels", label: "Hostels & Rooms", icon: Building2, roles: MGMT },
      { to: "/admin/reports", label: "Reports", icon: BarChart3, roles: ["ADMIN", "CHIEF_WARDEN"] },
      { to: "/admin/audit", label: "Audit Log", icon: ScrollText, roles: ["ADMIN"] },
    ],
  },
];

function navFor(user: User) {
  return NAV.map((s) => ({ ...s, items: s.items.filter((i) => i.roles.includes(user.role) && (!i.show || i.show(user))) })).filter((s) => s.items.length);
}

function Sidebar({ user, onNavigate }: { user: User; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main navigation" className="flex h-full flex-col">
      <Link to="/" className="flex items-center gap-2.5 px-5 py-5" onClick={onNavigate}>
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-vista-yellow text-lg font-extrabold text-vista-ink shadow-soft" aria-hidden>V</span>
        <div>
          <p className="text-lg font-bold leading-none tracking-wide text-vista-ink">VISTA</p>
          <p className="mt-0.5 text-[11px] text-vista-muted-text">Smart Hostel Management</p>
        </div>
      </Link>
      <div className="flex-1 space-y-5 overflow-y-auto px-3 pb-6">
        {navFor(user).map((s) => (
          <div key={s.section}>
            <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-vista-muted-text">{s.section}</p>
            <ul className="space-y-0.5">
              {s.items.map((i) => (
                <li key={i.to}>
                  <NavLink
                    to={i.to}
                    end={i.to === "/"}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cx("flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors", isActive ? "bg-vista-yellow font-semibold text-vista-ink shadow-soft" : "text-vista-ink/85 hover:bg-vista-soft hover:text-vista-ink")
                    }
                  >
                    <i.icon className="h-4 w-4 flex-none opacity-80" aria-hidden />
                    {i.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  const notif = useFetch<{ unread: number }>("/api/notifications?unread_only=true");
  const reloadNotif = notif.reload;
  useEffect(() => {
    void reloadNotif();
    const t = setInterval(() => void reloadNotif(), 30000);
    return () => clearInterval(t);
  }, [loc.pathname, reloadNotif]);
  if (!user) return null;

  return (
    <div className="min-h-screen bg-vista-bg text-vista-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-vista-line bg-vista-side lg:block">
        <Sidebar user={user} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-vista-ink/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-vista-side shadow-xl">
            <button className="absolute right-3 top-5 rounded p-1 text-vista-ink hover:bg-vista-soft" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <Sidebar user={user} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-vista-line bg-vista-card/90 px-4 backdrop-blur sm:px-6">
          <button className="rounded-lg p-2 text-vista-ink hover:bg-vista-soft lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-vista-muted-text">
              {user.hostel_name ?? "VIT Hostels"}
              {user.room && ` · ${user.room.block}-${user.room.number}`}
            </p>
          </div>
          {user.role === "STUDENT" && (
            <button onClick={() => nav("/sos?raise=1")} className="inline-flex items-center gap-1.5 rounded-lg bg-vista-sos px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400" data-testid="sos-button">
              <Siren className="h-4 w-4" aria-hidden /> SOS
            </button>
          )}
          <Link to="/notifications" className="relative rounded-lg p-2 text-vista-ink/80 hover:bg-vista-soft" aria-label={`Notifications${notif.data?.unread ? `, ${notif.data.unread} unread` : ""}`}>
            <Bell className="h-5 w-5" />
            {!!notif.data?.unread && (
              <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white" data-testid="unread-count">
                {notif.data.unread > 99 ? "99+" : notif.data.unread}
              </span>
            )}
          </Link>
          <div className="hidden text-right sm:block">
            <p className="text-sm font-semibold text-vista-ink" data-testid="current-user">{user.full_name}</p>
            <p className="text-xs text-vista-muted-text" data-testid="current-role">
              {ROLE_LABEL[user.role]}
              {user.staff_type ? ` · ${user.staff_type.charAt(0)}${user.staff_type.slice(1).toLowerCase()}` : ""}
            </p>
          </div>
          <button
            onClick={async () => {
              await logout();
              nav("/login");
            }}
            className="rounded-lg p-2 text-vista-ink/80 hover:bg-vista-soft"
            aria-label="Log out"
            title="Log out"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </header>
        <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
