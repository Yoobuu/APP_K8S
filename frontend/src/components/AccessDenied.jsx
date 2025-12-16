import { useNavigate } from "react-router-dom";

export default function AccessDenied({ title = "Acceso denegado", description }) {
  const navigate = useNavigate();

  return (
    <div className="flex flex-1 items-center justify-center px-6 py-16">
      <div className="max-w-md rounded-xl border border-neutral-200 bg-white p-8 text-center shadow">
        <h2 className="text-lg font-semibold text-neutral-900">{title}</h2>
        <p className="mt-2 text-sm text-neutral-600">
          {description ??
            "No tienes permisos para acceder a esta sección. Solicita acceso al administrador del sistema."}
        </p>
        <button
          type="button"
          onClick={() => navigate("/choose")}
          className="mt-6 inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500"
        >
          Volver al portal
        </button>
      </div>
    </div>
  );
}
