import { useEffect, useMemo, useState } from "react";
import { listAudit } from "../api/audit";

const LIMIT_OPTIONS = [10, 25, 50];

export default function AuditPage() {
  const [items, setItems] = useState([]);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    listAudit({ limit, offset, action: action.trim() || undefined })
      .then((response) => {
        if (cancelled) return;
        const data = response?.data;
        setItems(Array.isArray(data?.items) ? data.items : []);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = err?.response?.data?.detail || err?.message || "No se pudo cargar la auditoría.";
        setError(detail);
        setItems([]);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [limit, offset, action]);

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    setOffset(0);
  };

  const canGoBack = useMemo(() => offset > 0, [offset]);
  const canGoForward = useMemo(() => items.length === limit, [items.length, limit]);

  const formatDate = (value) => {
    try {
      return value ? new Date(value).toLocaleString() : "";
    } catch {
      return value || "";
    }
  };

  return (
    <main className="flex-1 px-6 py-8">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-gray-900">Auditoría</h1>
            <p className="text-sm text-gray-600">Eventos recientes de operaciones sensibles.</p>
          </div>
          <form onSubmit={handleSearchSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              value={action}
              onChange={(event) => setAction(event.target.value)}
              placeholder="Filtrar por action"
              className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <select
              value={limit}
              onChange={(event) => {
                setLimit(Number(event.target.value));
                setOffset(0);
              }}
              className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {LIMIT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option} por página
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500"
            >
              Aplicar
            </button>
          </form>
        </header>

        <section className="rounded-lg border border-gray-200 bg-white shadow">
          {loading ? (
            <div className="p-6 text-sm text-gray-600">Cargando…</div>
          ) : error ? (
            <div className="p-6 text-sm text-red-600">{error}</div>
          ) : items.length === 0 ? (
            <div className="p-6 text-sm text-gray-600">Sin resultados.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Fecha y hora</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Acción</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Actor</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Tipo de objetivo</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Identificador</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Detalle</th>
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">ID de correlación</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-4 py-2 text-gray-800">{formatDate(item.when)}</td>
                      <td className="px-4 py-2 text-gray-800">{item.action}</td>
                      <td className="px-4 py-2 text-gray-800">{item.actor_username || "—"}</td>
                      <td className="px-4 py-2 text-gray-800">{item.target_type || "—"}</td>
                      <td className="px-4 py-2 text-gray-800">{item.target_id || "—"}</td>
                      <td className="px-4 py-2 text-gray-800">
                        {item.meta ? JSON.stringify(item.meta) : "—"}
                      </td>
                      <td className="px-4 py-2 text-gray-800">{item.correlation_id || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
            disabled={!canGoBack}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 transition hover:border-gray-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Anterior
          </button>
          <span className="text-sm text-gray-600">
            Desplegando {items.length} registros (offset {offset})
          </span>
          <button
            type="button"
            onClick={() => setOffset((prev) => prev + limit)}
            disabled={!canGoForward}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 transition hover:border-gray-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Siguiente
          </button>
        </footer>
      </div>
    </main>
  );
}
