import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion as Motion } from "framer-motion";
import { IoPowerSharp, IoPowerOutline, IoRefreshSharp } from "react-icons/io5";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";

const ACTION_THEMES = {
  start: {
    base: "bg-green-500 hover:bg-green-600 focus-visible:ring-green-300",
  },
  stop: {
    base: "bg-red-500 hover:bg-red-600 focus-visible:ring-red-300",
  },
  reset: {
    base: "bg-yellow-500 hover:bg-yellow-600 focus-visible:ring-yellow-300",
  },
};

const SKELETON_WIDTHS = ["w-2/3", "w-1/2", "w-5/6", "w-3/4", "w-1/3", "w-2/5"];

const renderDisksWithBars = (disks) => {
  if (!Array.isArray(disks) || disks.length === 0) {
    return "\u2014";
  }

  const items = disks
    .map((disk) => {
      if (!disk) return null;
      if (typeof disk === "object" && ("text" in disk || "pct" in disk)) {
        const textValue = disk.text ?? "";
        if (!textValue) return null;
        const pctValue =
          disk.pct != null && Number.isFinite(Number(disk.pct)) ? Number(disk.pct) : null;
        return { text: textValue, pct: pctValue };
      }
      if (typeof disk === "string") {
        const match = /([\d.,]+)%/.exec(disk);
        const pctValue = match ? Number(match[1].replace(",", ".")) : null;
        return { text: disk, pct: Number.isFinite(pctValue) ? pctValue : null };
      }
      return { text: String(disk), pct: null };
    })
    .filter((disk) => disk && disk.text);

  if (!items.length) {
    return "\u2014";
  }

  return (
    <div className="flex flex-col gap-2">
      {items.map((disk, index) => {
        const hasPct = Number.isFinite(disk.pct);
        const pctNumber = hasPct ? disk.pct : 0;
        const width = hasPct ? Math.min(Math.max(pctNumber, 0), 100) : 0;
        const barColor =
          hasPct && pctNumber < 50 ? "bg-green-500" : hasPct && pctNumber < 80 ? "bg-yellow-500" : "bg-red-500";
        return (
          <div key={index} className="flex flex-col gap-1">
            <span className="text-sm text-gray-700">{disk.text}</span>
            {hasPct && (
              <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default function VMDetailModal({ vmId, onClose, onAction }) {
  const modalRef = useRef(null);
  const { canManagePower } = useAuth();

  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(null);
  const [pending, setPending] = useState(null);
  const [successMsg, setSuccessMsg] = useState("");

  const powerDisabled = !canManagePower;
  const powerDisabledMessage = "No tienes permisos para controlar energia. Pide acceso a un admin.";

  useEffect(() => {
    if (!vmId) {
      setDetail(null);
      return;
    }

    setLoading(true);
    setError("");

    api
      .get(`/vms/${vmId}`)
      .then((res) => setDetail(res.data))
      .catch(() => setError("No se pudo cargar el detalle."))
      .finally(() => setLoading(false));
  }, [vmId]);

  useEffect(() => {
    if (!vmId) return undefined;
    modalRef.current?.focus();
    const onKey = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [vmId, onClose]);

  if (!vmId) return null;

  const handlePowerExecution = async (apiPath) => {
    const actionLabel = apiPath === "start" ? "encender" : apiPath === "stop" ? "apagar" : "resetear";
    if (powerDisabled) {
      alert("Acceso denegado (403).");
      setPending(null);
      return;
    }
    setActionLoading(apiPath);
    let ok = false;
    try {
      await api.post(`/vms/${vmId}/power/${apiPath}`);
      ok = true;
    } catch (err) {
      if (err?.response?.status === 403) {
        alert("Acceso denegado (403).");
      } else {
        alert(`Error al intentar ${actionLabel}.`);
      }
    } finally {
      setActionLoading(null);
      setPending(null);
    }

    if (ok) {
      setSuccessMsg(`VM ${detail?.name ?? ""} ${actionLabel} exitosamente.`);
      onAction?.(apiPath);
    }
  };

  const actionButton = (text, themeKey, apiPath, Icon) => {
    const isLoading = actionLoading === apiPath;
    const disabled = powerDisabled || isLoading;
    const theme = ACTION_THEMES[themeKey] ?? ACTION_THEMES.start;

    const baseClass =
      "flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white shadow transition disabled:cursor-not-allowed disabled:opacity-60";

    const handleClick = () => {
      if (disabled) return;
      setPending({ text, apiPath });
    };

    return (
      <Motion.button
        type="button"
        disabled={disabled}
        title={powerDisabled ? powerDisabledMessage : undefined}
        className={`${baseClass} ${theme.base}`}
        onClick={handleClick}
        whileTap={disabled ? undefined : { scale: 0.97 }}
      >
        {isLoading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/60 border-t-transparent" />
        ) : (
          <Icon />
        )}
        <span>{text}</span>
      </Motion.button>
    );
  };

  const content = (
    <AnimatePresence>
      {vmId && (
        <Motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-8"
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <Motion.div
            ref={modalRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="vm-detail-title"
            className="relative w-full max-w-md rounded-2xl bg-white p-6 text-gray-800 shadow-xl focus:outline-none"
            variants={{
              hidden: { opacity: 0, scale: 0.95 },
              visible: { opacity: 1, scale: 1 },
            }}
            initial="hidden"
            animate="visible"
            exit="hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              onClick={onClose}
              aria-label="Cerrar detalle de VM"
              className="absolute right-4 top-4 text-xl text-gray-600 transition hover:text-gray-900"
            >
              &times;
            </button>

            <h3 id="vm-detail-title" className="mb-4 text-2xl font-semibold">
              Detalle VM {vmId}
            </h3>

            {successMsg && (
              <div className="mb-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                {successMsg}
              </div>
            )}

            {loading && (
              <div className="mb-6 space-y-3 px-4">
                {SKELETON_WIDTHS.map((widthClass, index) => (
                  <div key={index} className={`h-4 animate-pulse rounded bg-gray-200 ${widthClass}`} />
                ))}
              </div>
            )}

            {error && !loading && (
              <p className="mb-4 text-center text-sm text-red-600">{error}</p>
            )}

            {pending && (
              <div className="mb-4 rounded border border-gray-300 bg-gray-100 p-4">
                <p className="text-sm text-gray-800">
                  ÂSeguro que deseas <strong>{pending.text.toLowerCase()}</strong> la VM {detail?.name ?? vmId}?
                </p>
                <div className="mt-3 flex justify-end gap-2">
                  <button
                    className="rounded bg-green-500 px-3 py-1 text-sm text-white hover:bg-green-600"
                    onClick={() => handlePowerExecution(pending.apiPath)}
                  >
                    SÃ­
                  </button>
                  <button
                    className="rounded bg-gray-300 px-3 py-1 text-sm text-gray-800 hover:bg-gray-400"
                    onClick={() => setPending(null)}
                  >
                    No
                  </button>
                </div>
              </div>
            )}

            {!loading && detail && (
              <dl className="mb-6 grid grid-cols-2 gap-x-6 gap-y-2 px-4 text-sm">
                {[
                  ["Nombre", detail.name],
                  ["Estado", detail.power_state === "POWERED_ON" ? "Encendida" : detail.power_state === "POWERED_OFF" ? "Apagada" : detail.power_state],
                  ["CPU", detail.cpu_count],
                  ["RAM", `${detail.memory_size_MiB} MiB`],
                  ["OS", detail.guest_os],
                  ["IPs", detail.ip_addresses?.length ? detail.ip_addresses.join(", ") : "-"],
                  ["Discos", renderDisksWithBars(detail.disks)],
                  ["NICs", detail.nics?.length ? detail.nics.join(", ") : "-"],
                  ["Host", detail.host || "-"],
                  ["Cluster", detail.cluster || "-"],
                  ["VLAN(s)", detail.networks?.length ? detail.networks.join(", ") : "-"],
                ].map(([label, value]) => (
                  <div key={label} className="col-span-1 flex">
                    <dt className="w-1/2 font-medium text-gray-700">{label}:</dt>
                    <dd className="flex-1 break-words text-gray-800">{value ?? "\u2014"}</dd>
                  </div>
                ))}
              </dl>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {actionButton("Encender", "start", "start", IoPowerSharp)}
              {actionButton("Apagar", "stop", "stop", IoPowerOutline)}
              {actionButton("Reset", "reset", "reset", IoRefreshSharp)}
            </div>

            {powerDisabled && (
              <p className="mt-3 text-xs text-red-500">{powerDisabledMessage}</p>
            )}
          </Motion.div>
        </Motion.div>
      )}
    </AnimatePresence>
  );

  return createPortal(content, document.body);
}
