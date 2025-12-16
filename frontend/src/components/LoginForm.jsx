import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";

/**
 * LoginRedesign.jsx
 * Login oscuro con acentos por proveedor.
 * Redirige a /choose cuando las credenciales son correctas.
 */

const PROVIDERS = [
  {
    key: "vcenter",
    label: "VMware vCenter",
    tone: "bg-emerald-600",
    ring: "ring-emerald-500",
    text: "text-emerald-400",
    colors: ["#064e3b", "#059669", "#34d399"],
  },
  {
    key: "hyperv",
    label: "Microsoft Hyper-V",
    tone: "bg-blue-600",
    ring: "ring-blue-500",
    text: "text-blue-400",
    colors: ["#1d4ed8", "#2563eb", "#60a5fa"],
  },
  {
    key: "kvm",
    label: "KVM / Libvirt",
    tone: "bg-neutral-800",
    ring: "ring-neutral-500",
    text: "text-neutral-300",
    colors: ["#0f172a", "#1f2937", "#9ca3af"],
  },
];

const DEFAULT_COLORS = ["#0f172a", "#1f2937", "#4b5563"];

function DynamicGradientBackground({ colors, pointer }) {
  const palette = colors?.length ? colors : DEFAULT_COLORS;
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    setPhase(0);
    const ticker = window.setInterval(() => {
      setPhase((prev) => (prev + 1) % palette.length);
    }, 6500);
    return () => window.clearInterval(ticker);
  }, [palette]);

  const colorA = palette[phase % palette.length];
  const colorB = palette[(phase + 1) % palette.length];
  const colorC = palette[(phase + 2) % palette.length];

  const backgroundStyle = {
    background: `radial-gradient(circle at ${pointer.x}% ${pointer.y}%, ${colorA} 0%, ${colorB} 45%, ${colorC} 100%)`,
  };

  return (
    <div
      className="pointer-events-none fixed inset-0 transition-all duration-500 ease-linear"
      style={backgroundStyle}
      aria-hidden
    />
  );
}

export default function LoginRedesign() {
  const [provider, setProvider] = useState("vcenter");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [caps, setCaps] = useState(false);
  const [pointer, setPointer] = useState({ x: 50, y: 50 });
  const manualRef = useRef(false);
  const idleTimeoutRef = useRef(null);
  const rafRef = useRef(null);

  const navigate = useNavigate();
  const { login } = useAuth();
  const theme = useMemo(() => PROVIDERS.find((p) => p.key === provider) || PROVIDERS[0], [provider]);

  useEffect(() => {
    const onKey = (e) => setCaps(e.getModifierState && e.getModifierState("CapsLock"));
    window.addEventListener("keyup", onKey);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keyup", onKey);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    let start = performance.now();
    const animate = (now) => {
      const elapsed = (now - start) / 1000;
      if (!manualRef.current) {
        const nextX = 50 + Math.sin(elapsed * 0.35) * 22;
        const nextY = 50 + Math.cos(elapsed * 0.45 + Math.PI / 4) * 18;
        setPointer((prev) => {
          if (Math.abs(prev.x - nextX) > 0.1 || Math.abs(prev.y - nextY) > 0.1) {
            return { x: nextX, y: nextY };
          }
          return prev;
        });
      }
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  useEffect(() => {
    return () => {
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
      }
      manualRef.current = false;
    };
  }, []);

  const handlePointerMove = (event) => {
    manualRef.current = true;
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
    }

    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * 100;
    const y = ((event.clientY - bounds.top) / bounds.height) * 100;
    setPointer({
      x: Math.min(100, Math.max(0, x)),
      y: Math.min(100, Math.max(0, y)),
    });

    idleTimeoutRef.current = window.setTimeout(() => {
      manualRef.current = false;
    }, 1600);
  };

  const handlePointerLeave = () => {
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
      idleTimeoutRef.current = null;
    }
    manualRef.current = false;
    setPointer({ x: 50, y: 50 });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { username, password, provider });
      const {
        access_token: accessToken,
        user,
        require_password_change: requirePasswordChange,
        permissions,
      } = res?.data || {};

      if (accessToken) {
        login({ token: accessToken, user, permissions, requirePasswordChange });
      }

      if (remember) {
        localStorage.setItem("provider", provider);
        localStorage.setItem("last_username", username);
      } else {
        localStorage.removeItem("provider");
        localStorage.removeItem("last_username");
      }

      navigate(requirePasswordChange ? "/change-password" : "/choose", { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Error de autenticación";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const savedProvider = localStorage.getItem("provider");
    const savedUser = localStorage.getItem("last_username");
    if (savedProvider) setProvider(savedProvider);
    if (savedUser) setUsername(savedUser);
  }, []);

  const accentBtn = `${theme.tone} hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 ${theme.ring} text-white`;
  const accentSoft = `ring-1 ${theme.ring} ${theme.text}`;

  return (
    <div
      className="min-h-dvh w-full bg-gray-950 text-white relative overflow-hidden"
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <DynamicGradientBackground colors={theme.colors} pointer={pointer} />

      {/* Fondo en cuadrícula */}
      <div className="pointer-events-none fixed inset-0 opacity-20" aria-hidden>
        <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
              <path d="M 32 0 L 0 0 0 32" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      {/* Card centrada */}
      <div className="relative z-10 flex min-h-dvh items-center justify-center px-4 sm:px-6">
        <div className="w-full max-w-xl rounded-3xl border border-white/10 bg-neutral-900/60 p-6 shadow-2xl backdrop-blur">
          {/* Header */}
          <div className="mb-6 flex items-center gap-3">
            <div className={`h-9 w-9 rounded-xl ${theme.tone}`} />
            <div>
              <h1 className="text-xl font-semibold leading-5">Accede al inventario</h1>
              <div className="text-sm text-neutral-400">Introduce tus credenciales para continuar</div>
            </div>
          </div>

          {/* Selector proveedor */}
          <div className="mb-5 flex flex-wrap gap-2">
            {PROVIDERS.map((p) => (
              <button
                key={p.key}
                onClick={() => setProvider(p.key)}
                className={`rounded-full px-3 py-1.5 text-xs ring-1 transition ${
                  provider === p.key
                    ? `${p.tone} text-white ring-transparent`
                    : `bg-neutral-800 hover:bg-neutral-700 ${p.ring} text-neutral-200`
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-neutral-300">Usuario</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="w-full rounded-xl border border-white/10 bg-neutral-800 px-3 py-2 text-sm text-white placeholder-neutral-400 outline-none focus:ring-2 focus:ring-white/20"
                placeholder="usuario o dominio\\usuario"
                required
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className="block text-sm text-neutral-300">Contraseña</label>
                {caps && <span className="text-xs text-yellow-400">Caps Lock activo</span>}
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type={showPwd ? "text" : "password"}
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-white/10 bg-neutral-800 px-3 py-2 text-sm text-white placeholder-neutral-400 outline-none focus:ring-2 focus:ring-white/20"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="rounded-xl border border-white/10 bg-neutral-800 px-3 py-2 text-xs text-neutral-300 hover:bg-neutral-700"
                >
                  {showPwd ? "Ocultar" : "Mostrar"}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-neutral-400">
              <label className="inline-flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-white/10 bg-neutral-800"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                Recordarme en este equipo
              </label>
              <div className={`text-right ${accentSoft}`}>
                <p className="leading-snug">
                  ¿Olvidaste tu contraseña? <br className="hidden sm:block" />
                  Contacta al encargado del sistema para restablecerla.
                </p>
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={`group relative flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium shadow ${accentBtn} disabled:cursor-not-allowed disabled:opacity-60`}
            >
              {loading && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-transparent" />
              )}
              <span>Entrar</span>
              <span className="pointer-events-none absolute inset-x-0 -bottom-1 mx-auto h-px w-10 bg-white/50 opacity-0 transition group-hover:opacity-100" />
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 flex items-center justify-between text-xs text-neutral-500">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>vCenter</span>
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              <span>Hyper-V</span>
              <span className="h-2 w-2 rounded-full bg-neutral-700" />
              <span>KVM</span>
            </div>
            <div>Inventario DC · Seguridad primero</div>
          </div>
        </div>
      </div>
    </div>
  );
}
