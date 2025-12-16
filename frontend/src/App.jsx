import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ChooseInventory from "./components/ChooseInventory";
import LoginForm from "./components/LoginForm";
import HyperVPage from "./components/HyperVPage";
import KVMPage from "./components/KVMPage";
import VMTable from "./components/VMTable";
import HostTable from "./components/HostTable";
import AppLayout from "./components/AppLayout";
import AccessDenied from "./components/AccessDenied";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import UserAdminPage from "./pages/UserAdminPage";
import AuditPage from "./pages/AuditPage";
import NotificationsPage from "./pages/NotificationsPage";
import HyperVHostsPage from "./components/HyperVHostsPage";
import CediaPage from "./components/CediaPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

function AppRoutes() {
  const { token, mustChangePassword, hasPermission } = useAuth();
  const isAuthenticated = Boolean(token);
  const enforcePasswordChange = isAuthenticated && mustChangePassword;
  const canViewVmware = hasPermission("vms.view");
  const canViewHyperv = hasPermission("hyperv.view");
  const canViewCedia = hasPermission("cedia.view");
  const canViewNotifications = hasPermission("notifications.view");
  const canViewAudit = hasPermission("audit.view");
  const canManageUsers = hasPermission("users.manage");

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/choose" replace />
          ) : (
            <div className="min-h-dvh">
              <LoginForm />
            </div>
          )
        }
      />

      <Route
        path="/change-password"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <AppLayout>
                <ChangePasswordPage />
              </AppLayout>
            ) : (
              <Navigate to="/choose" replace />
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/choose"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewVmware || canViewHyperv ? (
              <AppLayout mainClassName="p-0">
                <ChooseInventory />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="No tienes permisos para ver inventarios (vms.view / hyperv.view)." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/hyperv"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewHyperv ? (
              <AppLayout>
                <HyperVPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso hyperv.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/hyperv-hosts"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewHyperv ? (
              <AppLayout mainClassName="p-0">
                <HyperVHostsPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso hyperv.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/cedia"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewCedia ? (
              <AppLayout>
                <CediaPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso cedia.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/hosts"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewVmware ? (
              <AppLayout mainClassName="p-0">
                <HostTable />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso vms.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/kvm"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : (
              <AppLayout>
                <KVMPage />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/notifications"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewNotifications ? (
              <AppLayout>
                <NotificationsPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso notifications.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/audit"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewAudit ? (
              <AppLayout>
                <AuditPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso audit.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/users"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canManageUsers ? (
              <AppLayout>
                <UserAdminPage />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso users.manage para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/*"
        element={
          isAuthenticated ? (
            enforcePasswordChange ? (
              <Navigate to="/change-password" replace />
            ) : canViewVmware ? (
              <AppLayout>
                <VMTable />
              </AppLayout>
            ) : (
              <AppLayout>
                <AccessDenied description="Necesitas el permiso vms.view para acceder." />
              </AppLayout>
            )
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}
