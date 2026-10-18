import { Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, qs } from "../api/client";
import type { Hostel, Paged, User } from "../api/types";
import { Alert, Badge, Button, Card, FilterSelect, Input, Modal, PageHeader, Pagination, SearchBox, Select, Spinner, Table } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { label, ROLE_LABEL } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";
import { passwordProblem } from "../lib/validation";

export default function AdminUsers() {
  const { user } = useAuth();
  const toast = useToast();
  const [role, setRole] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, loading, error, reload } = useFetch<Paged<User>>(`/api/admin/users${qs({ role, q: dq, page, page_size: 20 })}`);
  const isAdmin = user?.role === "ADMIN";
  const hostels = useFetch<Hostel[]>(isAdmin ? "/api/hostels" : null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ full_name: "", email: "", password: "", role: "STAFF", staff_type: "MAINTENANCE", phone: "", hostel_id: "" });
  const [err, setErr] = useState<string | null>(null);

  async function create(e?: FormEvent) {
    e?.preventDefault();
    const pw = passwordProblem(f.password);
    if (f.full_name.trim().length < 2 || !f.email.includes("@")) return setErr("Name and a valid email are required");
    if (pw) return setErr(pw);
    try {
      await api.post("/api/admin/users", { ...f, staff_type: f.role === "STAFF" ? f.staff_type : null, hostel_id: f.hostel_id ? Number(f.hostel_id) : null });
      toast("success", `${ROLE_LABEL[f.role]} account created`);
      setOpen(false);
      setF({ full_name: "", email: "", password: "", role: "STAFF", staff_type: "MAINTENANCE", phone: "", hostel_id: "" });
      void reload();
    } catch (e2) {
      setErr((e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Users" subtitle={isAdmin ? "Register wardens, staff and administrators, and activate or deactivate accounts." : "Directory of students and staff."} actions={isAdmin && <Button onClick={() => { setErr(null); setOpen(true); }}><Plus className="h-4 w-4" /> Add staff / warden</Button>} />
      <Card>
        <div className="mb-4 flex flex-wrap gap-2">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search name, email or reg. no." />
          <FilterSelect ariaLabel="Role" value={role} onChange={(v) => { setRole(v); setPage(1); }} options={["STUDENT", "WARDEN", "CHIEF_WARDEN", "STAFF", "ADMIN"]} all="All roles" />
        </div>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? <Spinner /> : (
          <>
            <Table head={["Name", "Role", "Email / phone", "Hostel / room", "Status", ...(isAdmin ? ["Action"] : [])]} empty={!data?.items.length}>
              {data?.items.map((u) => (
                <tr key={u.id} data-testid="user-row">
                  <td className="px-5 py-3"><p className="font-medium text-slate-800">{u.full_name}</p>{u.reg_no && <p className="font-mono text-xs text-slate-500">{u.reg_no}</p>}</td>
                  <td className="whitespace-nowrap px-5 py-3 text-slate-700">{ROLE_LABEL[u.role]}{u.staff_type && <span className="text-xs text-slate-500"> · {label(u.staff_type)}</span>}</td>
                  <td className="px-5 py-3 text-slate-600">{u.email}<br /><span className="text-xs">{u.phone}</span></td>
                  <td className="px-5 py-3 text-slate-600">{u.room ? `${u.room.hostel} ${u.room.block}-${u.room.number}` : u.hostel_name ?? "—"}</td>
                  <td className="px-5 py-3"><Badge value={u.is_active ? "AVAILABLE" : "CANCELLED"} className="!capitalize" /><span className="sr-only">{u.is_active ? "Active" : "Inactive"}</span></td>
                  {isAdmin && (
                    <td className="px-5 py-3">
                      {u.id !== user?.id && (
                        <Button size="sm" variant={u.is_active ? "secondary" : "success"} onClick={async () => { try { await api.patch(`/api/admin/users/${u.id}/active`, { is_active: !u.is_active }); toast("success", u.is_active ? "Account deactivated" : "Account activated"); void reload(); } catch (e) { toast("error", (e as Error).message); } }}>
                          {u.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </Table>
            {data && <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />}
          </>
        )}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Register staff, warden or administrator" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => void create()}>Create account</Button></>}>
        <form onSubmit={create} className="space-y-4" noValidate>
          {err && <Alert>{err}</Alert>}
          <Input label="Full name" name="full_name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Email" type="email" name="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
            <Input label="Mobile" name="phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Role" name="role" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} options={["STAFF", "WARDEN", "CHIEF_WARDEN", "ADMIN"].map((r) => ({ value: r, label: ROLE_LABEL[r] }))} />
            {f.role === "STAFF" && <Select label="Staff team" name="staff_type" value={f.staff_type} onChange={(e) => setF({ ...f, staff_type: e.target.value })} options={["MAINTENANCE", "CLEANING", "MESS", "SECURITY"]} />}
          </div>
          <Select label="Hostel" name="hostel_id" value={f.hostel_id} onChange={(e) => setF({ ...f, hostel_id: e.target.value })} placeholder="All hostels" options={(hostels.data ?? []).map((h) => ({ value: String(h.id), label: h.name }))} />
          <Input label="Initial password" type="password" name="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} hint="8+ characters with letters and digits" required />
        </form>
      </Modal>
    </>
  );
}
