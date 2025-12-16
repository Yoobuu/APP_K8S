import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const { applyNewToken, user } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (!oldPassword.trim() || !newPassword.trim()) {
      setError("Debes completar todos los campos.");
      return;
    }
    if (newPassword !== confirm) {
      setError("La confirmación no coincide con la nueva contraseña.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      applyNewToken(data?.access_token, data?.user, data?.permissions, data?.require_password_change);
      navigate("/choose", { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo cambiar la contraseña.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex-1 px-6 py-10">
      <div className="mx-auto w-full max-w-lg rounded-2xl border border-neutral-200 bg-white p-8 shadow">
        <h1 className="text-2xl font-semibold text-neutral-900">Debes actualizar tu contraseña</h1>
        <p className="mt-2 text-sm text-neutral-600">
          {user?.username ? (
            <>
              Hola <strong>{user.username}</strong>, ingresa tu contraseña actual y define una nueva para continuar.
            </>
          ) : (
            "Ingresa tu contraseña actual y define una nueva para continuar."
          )}
        </p>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium text-neutral-700">Contraseña actual</label>
            <input
              type="password"
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoComplete="current-password"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700">Nueva contraseña</label>
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoComplete="new-password"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700">Confirmar nueva contraseña</label>
            <input
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoComplete="new-password"
              required
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Guardando..." : "Actualizar contraseña"}
          </button>
        </form>
      </div>
    </main>
  );
}
