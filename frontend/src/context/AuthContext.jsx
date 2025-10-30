import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api from "../api/axios";

const AuthContext = createContext(null);

const normalizeUser = (rawUser) => {
  if (!rawUser) return null;
  const roleValue = (() => {
    if (typeof rawUser.role === "string") {
      const upper = rawUser.role.toUpperCase();
      return upper.startsWith("USERROLE.") ? upper.replace("USERROLE.", "") : upper;
    }
    if (rawUser.role && typeof rawUser.role.value === "string") {
      const upper = rawUser.role.value.toUpperCase();
      return upper.startsWith("USERROLE.") ? upper.replace("USERROLE.", "") : upper;
    }
    return "";
  })();
  return { ...rawUser, role: roleValue };
};

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(!!localStorage.getItem("token"));

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(
    ({ token: nextToken, user: nextUser }) => {
      if (nextToken) {
        localStorage.setItem("token", nextToken);
        setToken(nextToken);
      }
      setUser(nextUser ? normalizeUser(nextUser) : null);
    },
    []
  );

  const refreshMe = useCallback(async () => {
    if (!token) {
      setUser(null);
      return null;
    }
    try {
      const { data } = await api.get("/auth/me");
      const normalized = normalizeUser(data);
      setUser(normalized);
      return normalized;
    } catch (error) {
      logout();
      throw error;
    }
  }, [token, logout]);

  useEffect(() => {
    let cancelled = false;

    if (!token) {
      setInitializing(false);
      setUser(null);
      return undefined;
    }

    setInitializing(true);
    refreshMe()
      .catch(() => null)
      .finally(() => {
        if (!cancelled) {
          setInitializing(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, refreshMe]);

  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === "token") {
        setToken(event.newValue);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    const handleForcedLogout = () => logout();
    window.addEventListener("auth:logout", handleForcedLogout);
    return () => window.removeEventListener("auth:logout", handleForcedLogout);
  }, [logout]);

  const canManagePower = useMemo(() => {
    const role = user?.role;
    if (!role) return false;
    return role === "ADMIN" || role === "SUPERADMIN";
  }, [user]);

  const isSuperadmin = useMemo(() => user?.role === "SUPERADMIN", [user]);

  const value = useMemo(
    () => ({
      token,
      user,
      login,
      logout,
      refreshMe,
      canManagePower,
      isSuperadmin,
      initializing,
    }),
    [token, user, login, logout, refreshMe, canManagePower, isSuperadmin, initializing]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
