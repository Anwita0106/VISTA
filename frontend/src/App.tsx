import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { Role } from "./api/types";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./context/AuthContext";
import AdminAudit from "./pages/AdminAudit";
import AdminHostels from "./pages/AdminHostels";
import AdminReports from "./pages/AdminReports";
import AdminUsers from "./pages/AdminUsers";
import ComplaintDetail from "./pages/ComplaintDetail";
import Complaints from "./pages/Complaints";
import Dashboard from "./pages/Dashboard";
import Delivery from "./pages/Delivery";
import DeliveryDetail from "./pages/DeliveryDetail";
import GateDesk from "./pages/GateDesk";
import HostelMap from "./pages/HostelMap";
import Login from "./pages/Login";
import LostFound from "./pages/LostFound";
import Marketplace from "./pages/Marketplace";
import MessFeedback from "./pages/MessFeedback";
import Messages from "./pages/Messages";
import Notes from "./pages/Notes";
import Notices from "./pages/Notices";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import Roommates from "./pages/Roommates";
import Services from "./pages/Services";
import Sos from "./pages/Sos";
import Vault from "./pages/Vault";
import Visitors from "./pages/Visitors";

function Protected({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  if (roles && !roles.includes(user.role)) return <Forbidden />;
  return <>{children}</>;
}

function Forbidden() {
  return (
    <div className="mx-auto max-w-md py-16 text-center" data-testid="forbidden">
      <p className="text-5xl font-bold text-navy-800">403</p>
      <h1 className="mt-2 text-lg font-semibold">Access denied</h1>
      <p className="mt-1 text-sm text-slate-600">Your role does not have permission to open this page.</p>
    </div>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="text-5xl font-bold text-navy-800">404</p>
      <h1 className="mt-2 text-lg font-semibold">Page not found</h1>
      <a href="/" className="mt-4 inline-block text-sm font-medium text-navy-700 underline">
        Back to dashboard
      </a>
    </div>
  );
}

const MGMT: Role[] = ["WARDEN", "CHIEF_WARDEN", "ADMIN"];

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <Register />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        <Route path="notices" element={<Notices />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="messages" element={<Messages />} />
        <Route path="complaints" element={<Complaints />} />
        <Route path="complaints/:id" element={<ComplaintDetail />} />
        <Route path="visitors" element={<Visitors />} />
        <Route path="services" element={<Services />} />
        <Route path="sos" element={<Sos />} />
        <Route path="mess-feedback" element={<MessFeedback />} />
        <Route path="delivery" element={<Protected roles={["STUDENT", ...MGMT]}><Delivery /></Protected>} />
        <Route path="delivery/:id" element={<Protected roles={["STUDENT", ...MGMT]}><DeliveryDetail /></Protected>} />
        <Route path="gate" element={<Protected roles={["STAFF", ...MGMT]}><GateDesk /></Protected>} />
        <Route path="lost-found" element={<LostFound />} />
        <Route path="marketplace" element={<Marketplace />} />
        <Route path="notes" element={<Notes />} />
        <Route path="vault" element={<Protected roles={["STUDENT"]}><Vault /></Protected>} />
        <Route path="roommates" element={<Protected roles={["STUDENT"]}><Roommates /></Protected>} />
        <Route path="map" element={<HostelMap />} />
        <Route path="admin/users" element={<Protected roles={MGMT}><AdminUsers /></Protected>} />
        <Route path="admin/hostels" element={<Protected roles={MGMT}><AdminHostels /></Protected>} />
        <Route path="admin/reports" element={<Protected roles={["ADMIN", "CHIEF_WARDEN"]}><AdminReports /></Protected>} />
        <Route path="admin/audit" element={<Protected roles={["ADMIN"]}><AdminAudit /></Protected>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
