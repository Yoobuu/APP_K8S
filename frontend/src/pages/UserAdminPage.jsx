import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createUser, deleteUser, listUsers, resetUserPassword } from "../api/users";
import { getUserPermissions, listPermissionCatalog, updateUserPermissions } from "../api/permissions";
import { useAuth } from "../context/AuthContext";

const PAGE_SIZE = 10;

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

function Modal({ title, children, onClose, size = "md" }) {
  const widthClass =
    size === "xl" ? "max-w-5xl" : size === "lg" ? "max-w-3xl" : "max-w-md";
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center bg-black/50 px-4 py-10">
      <div className={`w-full ${widthClass} rounded-lg bg-white p-6 shadow-xl`}>
        <div className="flex items-start justify-between gap-4">
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
        <div className="mt-4 max-h-[75vh] overflow-y-auto pr-1">{children}</div>
      </div>
    </div>
  );
}

export default function UserAdminPage() {
  const { hasPermission } = useAuth();
  const canManageUsers = hasPermission("users.manage");

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState({ type: null, user: null });
  const [createForm, setCreateForm] = useState({ username: "", password: "" });
  const [passwordForm, setPasswordForm] = useState({ password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [formError, setFormError] = useState("");
  const [permissionCatalog, setPermissionCatalog] = useState([]);
  const [permissionsState, setPermissionsState] = useState({ loading: false, overridesDraft: {}, summary: null });
  const [permissionsError, setPermissionsError] = useState("");
  const [permissionsSaving, setPermissionsSaving] = useState(false);
  const [fullAccessUsers, setFullAccessUsers] = useState(0);
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
    if (!canManageUsers) {
      setUsers([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    listUsers()
      .then((response) => {
        const payload = Array.isArray(response.data) ? response.data : [];
        setUsers(payload);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail || err?.message || "No se pudo cargar la lista de usuarios.";
        setError(detail);
      })
      .finally(() => setLoading(false));
  }, [canManageUsers]);

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return users;
    return users.filter((u) => u.username.toLowerCase().includes(term));
  }, [users, search]);

  const permissionsByCategory = useMemo(() => {
    const grouped = {};
    (permissionCatalog || []).forEach((perm) => {
      const cat = perm.category || "otros";
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(perm);
    });
    Object.values(grouped).forEach((arr) => arr.sort((a, b) => (a.name || "").localeCompare(b.name || "")));
    return grouped;
  }, [permissionCatalog]);

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

  const closeModal = () => {
    setModal({ type: null, user: null });
    setCreateForm({ username: "", password: "" });
    setPasswordForm({ password: "" });
    setSubmitting(false);
    setFormError("");
    setPermissionsState({ loading: false, overridesDraft: {}, summary: null });
    setPermissionsError("");
    setPermissionsSaving(false);
  };

  const allPermissionCodes = useMemo(
    () => new Set((permissionCatalog || []).map((p) => p.code)),
    [permissionCatalog],
  );

  const computeFullAccessUsers = useCallback(async () => {
    if (!permissionCatalog.length || !users.length) return 0;
    const allCodes = allPermissionCodes;
    const tasks = users.map((u) =>
      getUserPermissions(u.id)
        .then(({ data }) => {
          const effective = new Set(data?.effective || []);
          return [...allCodes].every((code) => effective.has(code));
        })
        .catch(() => false)
    );
    const results = await Promise.all(tasks);
    return results.filter(Boolean).length;
  }, [allPermissionCodes, permissionCatalog.length, users]);

  const ensurePermissionData = useCallback(async () => {
    try {
      if (!permissionCatalog.length) {
        const { data } = await listPermissionCatalog();
        setPermissionCatalog(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo cargar el catálogo de permisos.";
      setPermissionsError(detail);
      throw err;
    }
    try {
      const fullCount = await computeFullAccessUsers();
      setFullAccessUsers(fullCount);
    } catch {
      // no-op; el contador se actualizará en próximas acciones
    }
  }, [permissionCatalog.length, computeFullAccessUsers]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    ensurePermissionData().catch(() => null);
  }, [ensurePermissionData]);

  useEffect(() => {
    if (!users.length || !permissionCatalog.length) return;
    computeFullAccessUsers()
      .then((count) => setFullAccessUsers(count))
      .catch(() => null);
  }, [users, permissionCatalog.length, computeFullAccessUsers]);

  const handleCreateSubmit = async (event) => {
    event.preventDefault();
    if (!createForm.username.trim() || !createForm.password.trim()) {
      setFormError("Debes ingresar un usuario y una contraseña válidos.");
      return;
    }
    setFormError("");
    setSubmitting(true);
    try {
      await createUser({
        username: createForm.username.trim(),
        password: createForm.password,
      });
      showToast("Usuario creado correctamente.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo crear el usuario.";
      showToast(detail, "error");
      setSubmitting(false);
      setFormError(detail);
    }
  };

  const openPermissionsModal = async (user) => {
    if (!user?.id) return;
    setModal({ type: "permissions", user });
    setPermissionsState({ loading: true, overridesDraft: {}, summary: null });
    setPermissionsError("");
    try {
      await ensurePermissionData();
      const { data } = await getUserPermissions(user.id);
      const draft = {};
      if (Array.isArray(data?.overrides)) {
        data.overrides.forEach((item) => {
          if (!item?.code) return;
          draft[item.code] = item.granted ? "grant" : "deny";
        });
      }
      setPermissionsState({ loading: false, overridesDraft: draft, summary: data });
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudieron cargar los permisos del usuario.";
      setPermissionsError(detail);
      setPermissionsState((prev) => ({ ...prev, loading: false }));
    }
  };

  const updateOverrideChoice = (code, choice) => {
    setPermissionsState((prev) => {
      const nextOverrides = { ...(prev.overridesDraft || {}) };
      if (choice === "inherit") {
        delete nextOverrides[code];
      } else {
        nextOverrides[code] = choice;
      }
      return { ...prev, overridesDraft: nextOverrides };
    });
  };

  const handlePermissionsSubmit = async (event) => {
    event.preventDefault();
    if (!modal.user) return;
    setPermissionsSaving(true);
    setPermissionsError("");
    const overridesPayload = Object.entries(permissionsState.overridesDraft || {})
      .filter(([, mode]) => mode === "grant" || mode === "deny")
      .map(([code, mode]) => ({ code, granted: mode === "grant" }));

    const currentEffective = new Set(permissionsState.summary?.effective || []);
    const proposedEffective = new Set(
      overridesPayload.filter((item) => item.granted).map((item) => item.code)
    );
    const removingFullAccess =
      currentEffective.size === allPermissionCodes.size &&
      [...allPermissionCodes].every((code) => currentEffective.has(code)) &&
      ![...allPermissionCodes].every((code) => proposedEffective.has(code));

    if (removingFullAccess) {
      try {
        const othersFull = await computeFullAccessUsers();
        const othersExcludingCurrent = modal.user ? othersFull - 1 : othersFull;
        if (othersExcludingCurrent <= 0) {
          setPermissionsError("No puedes quitar permisos: este usuario es el único con acceso total.");
          setPermissionsSaving(false);
          return;
        }
      } catch {
        // si falla el conteo, seguimos y dejamos que el backend valide
      }
    }

    try {
      const { data } = await updateUserPermissions(modal.user.id, overridesPayload);
      const draft = {};
      if (Array.isArray(data?.overrides)) {
        data.overrides.forEach((item) => {
          if (!item?.code) return;
          draft[item.code] = item.granted ? "grant" : "deny";
        });
      }
      setPermissionsState({ loading: false, overridesDraft: draft, summary: data });
      showToast("Permisos actualizados.");
      fetchUsers();
      const fullCount = await computeFullAccessUsers();
      setFullAccessUsers(fullCount);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudieron actualizar los permisos.";
      setPermissionsError(detail);
    } finally {
      setPermissionsSaving(false);
    }
  };

  const handlePasswordSubmit = async (event) => {
    event.preventDefault();
    if (!modal.user) return;
    if (!passwordForm.password.trim()) {
      setFormError("La nueva contraseña es obligatoria.");
      return;
    }
    setFormError("");
    setSubmitting(true);
    try {
      await resetUserPassword(modal.user.id, passwordForm.password);
      showToast("Contraseña actualizada.");
      closeModal();
      fetchUsers();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo actualizar la contraseña.";
      showToast(detail, "error");
      setSubmitting(false);
      setFormError(detail);
    }
  };

  const handleDelete = async () => {
    if (!modal.user) return;
    setSubmitting(true);
    try {
      const { data } = await getUserPermissions(modal.user.id);
      const effective = new Set(data?.effective || []);
      const hasAll = allPermissionCodes.size > 0 && [...allPermissionCodes].every((code) => effective.has(code));
      if (hasAll) {
        const othersFull = await computeFullAccessUsers();
        const othersExcludingCurrent = othersFull - 1;
        if (othersExcludingCurrent <= 0) {
          showToast("No puedes eliminar al último usuario con todos los permisos.", "error");
          setSubmitting(false);
          return;
        }
      }
    } catch {
      // si falla la validación seguimos intentando borrar y delegamos en backend
    }

    try {
      await deleteUser(modal.user.id);
      showToast("Usuario eliminado.");
      closeModal();
      fetchUsers();
      const fullCount = await computeFullAccessUsers();
      setFullAccessUsers(fullCount);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "No se pudo eliminar el usuario.";
      showToast(detail, "error");
      setSubmitting(false);
    }
  };

  if (!canManageUsers) {
    return (
      <main className="flex-1 px-6 py-10">
        <Toast toast={toast} onClose={() => setToast(null)} />
        <h1 className="text-2xl font-semibold text-gray-800">Administración de usuarios</h1>
        <p className="mt-4 text-sm text-gray-600">
          Acceso denegado. Necesitas el permiso <strong>users.manage</strong> para ver esta sección.
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 px-6 py-10">
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-800">Administración de usuarios</h1>
          <p className="text-sm text-gray-600">Gestiona cuentas, contraseñas y permisos atómicos.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setCreateForm({ username: "", password: "" });
            setModal({ type: "create", user: null });
            setFormError("");
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
          placeholder="Buscar por usuario"
          className="w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <div className="text-sm text-gray-500">
          Total usuarios: <span className="font-semibold text-gray-700">{users.length}</span>
          {permissionCatalog.length > 0 && (
            <span className="ml-3 text-xs text-gray-500">
              Con acceso total: {fullAccessUsers}
            </span>
          )}
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
                      <td className="px-4 py-2">
                        <div className="flex items-center justify-end gap-2 text-xs">
                          <button
                            type="button"
                            onClick={() => {
                              openPermissionsModal(user);
                              setFormError("");
                            }}
                            className="rounded border border-gray-300 px-3 py-1 text-gray-700 transition hover:border-blue-500 hover:text-blue-600"
                          >
                            Permisos
                          </button>
                          <button
                            type="button"
                          onClick={() => {
                            setPasswordForm({ password: "" });
                            setModal({ type: "password", user });
                            setFormError("");
                          }}
                            className="rounded border border-gray-300 px-3 py-1 text-gray-700 transition hover:border-blue-500 hover:text-blue-600"
                          >
                            Restablecer contraseña
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setFormError("");
                              setModal({ type: "delete", user });
                            }}
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
                Página {page} de {totalPages}
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
            {formError && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {formError}
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Usuario</label>
              <input
                type="text"
                value={createForm.username}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Contraseña</label>
              <input
                type="password"
                value={createForm.password}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))}
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
                className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modal.type === "password" && modal.user && (
        <Modal title={`Restablecer contraseña de ${modal.user.username}`} onClose={closeModal}>
          <form className="space-y-4" onSubmit={handlePasswordSubmit}>
            {formError && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {formError}
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Nueva contraseña</label>
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

      {modal.type === "permissions" && modal.user && (
        <Modal title={`Permisos de ${modal.user.username}`} onClose={closeModal} size="xl">
          {permissionsError && (
            <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {permissionsError}
            </div>
          )}
          {permissionsState.loading ? (
            <div className="rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">Cargando permisos...</div>
          ) : !permissionCatalog.length ? (
            <div className="rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
              No hay catálogo de permisos disponible.
            </div>
          ) : (
            <form className="space-y-4" onSubmit={handlePermissionsSubmit}>
              <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <p className="text-xs text-gray-600">
                  Selecciona <em>Permitir</em> o <em>Denegar</em>. <em>Sin override</em> elimina la entrada y el permiso queda denegado.
                </p>
              </div>

              <div className="space-y-4 rounded border border-gray-200 bg-white p-3">
                {Object.keys(permissionsByCategory).sort().map((category) => {
                  const items = permissionsByCategory[category] || [];
                  const effectiveSet = new Set(permissionsState.summary?.effective || []);
                  return (
                    <div key={category} className="space-y-2">
                      <div className="flex items-center justify-between border-b border-gray-100 pb-1">
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-600">{category}</h3>
                        <span className="text-[11px] text-gray-400">{items.length} permisos</span>
                      </div>
                      <div className="space-y-3 rounded border border-gray-100 bg-gray-50 p-2">
                        {items.map((perm) => {
                          const override = permissionsState.overridesDraft?.[perm.code] ?? "inherit";
                          const effective = effectiveSet.has(perm.code);
                          const statusLabel =
                            override === "inherit"
                              ? effective
                                ? "Acceso actual: Permitido (sin override)"
                                : "Acceso actual: Denegado (sin override)"
                              : override === "grant"
                              ? "Override aplicado: Permitido"
                              : "Override aplicado: Denegado";
                          return (
                            <div
                              key={perm.code}
                              className="grid grid-cols-1 gap-3 rounded-md bg-white p-3 shadow-sm ring-1 ring-gray-100 md:grid-cols-12 md:items-center"
                            >
                              <div className="md:col-span-3">
                                <div className="break-words text-sm font-semibold text-gray-900">{perm.name}</div>
                                <div className="break-all text-xs text-gray-500">{perm.code}</div>
                              </div>
                              <div className="md:col-span-5 break-words text-sm text-gray-700">{perm.description || "—"}</div>
                              <div className="md:col-span-2 text-xs font-medium text-gray-600">{statusLabel}</div>
                              <div className="md:col-span-2">
                                <select
                                  value={override}
                                  onChange={(event) => updateOverrideChoice(perm.code, event.target.value)}
                                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                >
                                  <option value="inherit">Sin override (queda denegado)</option>
                                  <option value="grant">Permitir</option>
                                  <option value="deny">Denegar</option>
                                </select>
                              </div>
                              <div className="md:col-span-6 text-xs font-semibold text-gray-600">
                                Acceso actual: {effective ? "Permitido" : "Denegado"}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:border-gray-400"
                >
                  Cerrar
                </button>
                <button
                  type="submit"
                  disabled={permissionsSaving}
                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {permissionsSaving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </form>
          )}
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
