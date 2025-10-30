import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createUser, deleteUser, listUsers, resetUserPassword, updateUserRole } from "../api/users";
import { useAuth } from "../context/AuthContext";

const PAGE_SIZE = 10;
const ROLE_OPTIONS = ["USER", "ADMIN", "SUPERADMIN"];

function Toast({ toast, onClose }) {
  if (!toast) return null;
  const tone = toast.type === "error"
    ? "bg-red-100 text-red-700 border-red-200"
    : "bg-emerald-100 text-emerald-700 border-emerald-200";
  return (
    <div className={`fixed right-4 top-4 z-50 max-w-sm rounded-lg border px-4 py-3 shadow ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <span>{toast.message}</span>
        <button
          type="button"
          onClick={onClose}
          className="text-sm font-semibold text-current opacity-70 transition hover:opacity-100"
          aria-label="Cerrar"
        >
          x
        </button>
      </div>
    </div>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 transition hover:text-gray-800"
            aria-label="Cerrar"
          >
            x
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function UserAdminPage() {
  const { isSuperadmin, user: currentUser } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState({ type: null, user: null });
  const [createForm, setCreateForm] = useState({ username: "", password: "", role: "USER" });
  const [roleForm, setRoleForm] = useState({ role: "USER" });
  const [passwordForm, setPasswordForm] = useState({ password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef();

  const showToast = useCallback((message, type = "success") => {
    setToast({ message, type });
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }, []);

  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
  }, []);

  const fetchUsers = useCallback(() => {
    if (!isSuperadmin) {
      setUsers([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    listUsers()
      .then((response) => {
        const payload = Array.isArray(response.data) ? response.data : [];
        const normalized = payload.map((u) => {
          const role = typeof u.role === "string"
            ? u.role.toUpperCase()
            : typeof u.role?.value === "string"
            ? u.role.value.toUpperCase()
            : "";
          return { ...u, role };
        });
        setUsers(normalized);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail || err?.message || "No se pudo cargar la lista de usuarios.";
        setError(detail);
      })
      .finally(() => setLoading(false));
  }, [isSuperadmin]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return users;
    return users.filter((u) => u.username.toLowerCase().includes(term));
  }, [users, search]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const paginatedUsers = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredUsers.slice(start, start + PAGE_SIZE);
  }, [filteredUsers, page]);

  const superadminCount = useMemo(
    () => users.filter((u) => u.role === "SUPERADMIN").length,
    [users]
  );

  const closeModal = () => {
    setModal({ type: null, user: null });
    setCreateForm({ username: "", password: "", role: "USER" });
    setRoleForm({ role: "USER" });
    setPasswordForm({ password: "" });
    setSubmitting(false);
  };

  const guardLastSuperadmin = (targetUserId) => {
    const target = users.find((u) => u.id === targetUserId);
    if (!target || target.role !== "SUPERADMIN") return false;
    if (superadminCount <= 1) return true;
    if (currentUser && targetUserId === currentUser.id && superadminCount <= 1) return true;
    return false;
  };

  const handleCreateSubmit = async (event) => {
    event.preventDefault();
    if (!createForm.username.trim() || !createForm.password.trim()) {
      showToast("Username y password son obligatorios.", "error");
      return;
    }
    setSubmitting(true);
    try {
      await createUser({
        username: createForm.username.trim(),
        password: createForm.password,
        role: createForm.role,
      });
      showToast("Usuario creado correctamente.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo crear el usuario.";
      showToast(detail, "error");
      setSubmitting(false);
    }
  };

  const handleRoleSubmit = async (event) => {
    event.preventDefault();
    if (!modal.user) return;
    if (modal.user.role === roleForm.role) {
      showToast("El usuario ya tiene ese rol.", "error");
      return;
    }
    if (
      modal.user.role === "SUPERADMIN" &&
      roleForm.role !== "SUPERADMIN" &&
      guardLastSuperadmin(modal.user.id)
    ) {
      showToast("No se puede degradar al ultimo SUPERADMIN.", "error");
      return;
    }
    setSubmitting(true);
    try {
      await updateUserRole(modal.user.id, { role: roleForm.role });
      showToast("Rol actualizado.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo actualizar el rol.";
      showToast(detail, "error");
      setSubmitting(false);
    }
  };

  const handlePasswordSubmit = async (event) => {
    event.preventDefault();
    if (!modal.user) return;
    if (!passwordForm.password.trim()) {
      showToast("La nueva password es obligatoria.", "error");
      return;
    }
    setSubmitting(true);
    try {
      await resetUserPassword(modal.user.id, passwordForm.password);
      showToast("Password actualizada.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo actualizar la password.";
      showToast(detail, "error");
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!modal.user) return;
    if (guardLastSuperadmin(modal.user.id)) {
      showToast("No se puede eliminar al ultimo SUPERADMIN.", "error");
      return;
    }
    setSubmitting(true);
    try {
      await deleteUser(modal.user.id);
      showToast("Usuario eliminado.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo eliminar el usuario.";
      showToast(detail, "error");
      setSubmitting(false);
    }
  };

  if (!isSuperadmin) {
    return (
      <main className="flex-1 px-6 py-10">
        <Toast toast={toast} onClose={() => setToast(null)} />
        <h1 className="text-2xl font-semibold text-gray-800">Administracion de usuarios</h1>
        <p className="mt-4 text-sm text-gray-600">
          Acceso denegado. Solo el rol <strong>SUPERADMIN</strong> puede ver esta seccion.
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 px-6 py-10">
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-800">Administracion de usuarios</h1>
          <p className="text-sm text-gray-600">Gestiona cuentas, roles y passwords para el inventario.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setCreateForm({ username: "", password: "", role: "USER" });
            setModal({ type: "create", user: null });
          }}
          className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-emerald-500"
        >
          Crear usuario
        </button>
      </div>

      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <input
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por username"
          className="w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <div className="text-sm text-gray-500">
          Total usuarios: <span className="font-semibold text-gray-700">{users.length}</span>
        </div>
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
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">ID</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Usuario</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Rol</th>
                  <th className="px-4 py-2 text-right font-medium text-gray-600">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {paginatedUsers.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-4 text-center text-gray-500">
                      Sin resultados.
                    </td>
                  </tr>
                ) : (
                  paginatedUsers.map((user) => (
                    <tr key={user.id ?? user.username}>
                      <td className="px-4 py-2 text-gray-800">{user.id}</td>
                      <td className="px-4 py-2 text-gray-800">{user.username}</td>
                      <td className="px-4 py-2 text-gray-800">
                        <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold uppercase text-gray-700">
                          {user.role}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center justify-end gap-2 text-xs">
                          <button
                            type="button"
                            onClick={() => {
                              setRoleForm({ role: user.role });
                              setModal({ type: "role", user });
                            }}
                            className="rounded border border-gray-300 px-3 py-1 text-gray-700 transition hover:border-blue-500 hover:text-blue-600"
                          >
                            Cambiar rol
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setPasswordForm({ password: "" });
                              setModal({ type: "password", user });
                            }}
                            className="rounded border border-gray-300 px-3 py-1 text-gray-700 transition hover:border-blue-500 hover:text-blue-600"
                          >
                            Reset password
                          </button>
                          <button
                            type="button"
                            onClick={() => setModal({ type: "delete", user })}
                            className="rounded border border-gray-300 px-3 py-1 text-red-600 transition hover:border-red-500 hover:bg-red-50"
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-col items-center justify-between gap-3 text-sm text-gray-600 md:flex-row">
            <span>
              Mostrando {paginatedUsers.length} de {filteredUsers.length} usuarios
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page === 1}
                className="rounded border border-gray-300 px-3 py-1 transition hover:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Anterior
              </button>
              <span>
                Pagina {page} de {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page >= totalPages}
                className="rounded border border-gray-300 px-3 py-1 transition hover:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}

      {modal.type === "create" && (
        <Modal title="Crear usuario" onClose={closeModal}>
          <form className="space-y-4" onSubmit={handleCreateSubmit}>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Username</label>
              <input
                type="text"
                value={createForm.username}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Password</label>
              <input
                type="password"
                value={createForm.password}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Rol</label>
              <select
                value={createForm.role}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, role: event.target.value }))}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:border-gray-400"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modal.type === "role" && modal.user && (
        <Modal title={`Cambiar rol de ${modal.user.username}`} onClose={closeModal}>
          <form className="space-y-4" onSubmit={handleRoleSubmit}>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Nuevo rol</label>
              <select
                value={roleForm.role}
                onChange={(event) => setRoleForm({ role: event.target.value })}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:border-gray-400"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Guardando..." : "Actualizar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modal.type === "password" && modal.user && (
        <Modal title={`Reset password de ${modal.user.username}`} onClose={closeModal}>
          <form className="space-y-4" onSubmit={handlePasswordSubmit}>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Nueva password</label>
              <input
                type="password"
                value={passwordForm.password}
                onChange={(event) => setPasswordForm({ password: event.target.value })}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:border-gray-400"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Guardando..." : "Actualizar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modal.type === "delete" && modal.user && (
        <Modal title="Eliminar usuario" onClose={closeModal}>
          <div className="space-y-4 text-sm text-gray-700">
            <p>
              Estas seguro de eliminar la cuenta <strong>{modal.user.username}</strong>? Esta accion no se puede deshacer.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:border-gray-400"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={submitting}
                className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Eliminando..." : "Eliminar"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </main>
  );
}
