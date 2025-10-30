import { useEffect, useState } from "react";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";

export default function UserAdminPage() {
  const { isSuperadmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isSuperadmin) {
      setUsers([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    api
      .get("/users/")
      .then((response) => {
        if (!cancelled) {
          const payload = Array.isArray(response.data) ? response.data : [];
          const normalized = payload.map((u) => {
            const role =
              typeof u.role === "string"
                ? u.role.toUpperCase()
                : typeof u.role?.value === "string"
                ? u.role.value.toUpperCase()
                : "";
            return { ...u, role };
          });
          setUsers(normalized);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const detail = err?.response?.data?.detail || err?.message || "No se pudo cargar la lista de usuarios.";
          setError(detail);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isSuperadmin]);

  if (!isSuperadmin) {
    return (
      <main className="flex-1 px-6 py-10">
        <h1 className="text-2xl font-semibold text-gray-800">Administración de usuarios</h1>
        <p className="mt-4 text-sm text-gray-600">
          Acceso denegado. Solo el rol <strong>SUPERADMIN</strong> puede ver esta sección.
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 px-6 py-10">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold text-gray-800">Administración de usuarios</h1>
        <p className="mt-2 text-sm text-gray-600">Consulta básica de usuarios. Las acciones se agregarán más adelante.</p>
      </div>

      {loading && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow">
          Cargando usuarios...
        </div>
      )}

      {error && !loading && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600 shadow">
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">ID</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Usuario</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Rol</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-4 text-center text-gray-500">
                    No hay usuarios registrados.
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr key={u.id ?? u.username}>
                  <td className="px-4 py-2 text-gray-800">{u.id}</td>
                  <td className="px-4 py-2 text-gray-800">{u.username}</td>
                  <td className="px-4 py-2 text-gray-800">{u.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
