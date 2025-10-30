import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LoginForm from "./components/LoginForm";
import Navbar from "./components/Navbar";
import VMTable from "./components/VMTable";
import ChooseInventory from "./components/ChooseInventory";
import HyperVPage from "./components/HyperVPage";
import KVMPage from "./components/KVMPage";
import { AuthProvider, useAuth } from "./context/AuthContext";
import UserAdminPage from "./pages/UserAdminPage";

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
  const { token } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={
          token ? (
            <Navigate to="/choose" replace />
          ) : (
            <div className="min-h-dvh">
              <LoginForm />
            </div>
          )
        }
      />

      <Route
        path="/choose"
        element={token ? <ChooseInventory /> : <Navigate to="/login" replace />}
      />

      <Route
        path="/hyperv"
        element={
          token ? (
            <div className="min-h-screen bg-gray-50 flex flex-col">
              <Navbar />
              <HyperVPage />
            </div>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/kvm"
        element={
          token ? (
            <div className="min-h-screen bg-gray-50 flex flex-col">
              <Navbar />
              <KVMPage />
            </div>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/users"
        element={
          token ? (
            <div className="min-h-screen bg-gray-50 flex flex-col">
              <Navbar />
              <UserAdminPage />
            </div>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route
        path="/*"
        element={
          token ? (
            <div className="min-h-screen bg-gray-50 flex flex-col">
              <Navbar />
              <VMTable />
            </div>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}
