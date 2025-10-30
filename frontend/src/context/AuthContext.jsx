import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api from "../api/axios";

const AuthContext = createContext(null);
const MUST_CHANGE_STORAGE_KEY = "mustChangePassword";

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
  const [mustChangePassword, setMustChangePassword] = useState(
    () => localStorage.getItem(MUST_CHANGE_STORAGE_KEY) === "true"
  );
  const [initializing, setInitializing] = useState(!!localStorage.getItem("token"));

  const persistToken = useCallback((value) => {
    if (value) {
      localStorage.setItem("token", value);
    } else {
      localStorage.removeItem("token");
    }
    setToken(value || null);
  }, []);

  const persistMustChange = useCallback((value) => {
    if (value) {
      localStorage.setItem(MUST_CHANGE_STORAGE_KEY, "true");
      setMustChangePassword(true);
    } else {
      localStorage.removeItem(MUST_CHANGE_STORAGE_KEY);
      setMustChangePassword(false);
    }
  }, []);

  const applySession = useCallback(
    ({ token: nextToken, user: nextUser, requirePasswordChange }) => {
      if (typeof nextToken === "string" && nextToken.length > 0) {
        persistToken(nextToken);
      } else if (nextToken === null) {
        persistToken(null);
      }
      setUser(nextUser ? normalizeUser(nextUser) : null);
      if (requirePasswordChange !== undefined) {
        persistMustChange(Boolean(requirePasswordChange));
      }
    },
    [persistToken, persistMustChange]
  );

  const logout = useCallback(() => {
    persistToken(null);
    setUser(null);
    persistMustChange(false);
  }, [persistToken, persistMustChange]);

  const login = useCallback(
    ({ token: nextToken, user: nextUser, requirePasswordChange }) => {
      applySession({
        token: nextToken,
        user: nextUser,
        requirePasswordChange: Boolean(requirePasswordChange),
      });
    },
    [applySession]
  );

  const applyNewToken = useCallback(
    (nextToken, nextUser, requirePasswordChange = false) => {
      applySession({
        token: nextToken,
        user: nextUser,
        requirePasswordChange,
      });
    },
    [applySession]
  );

  const refreshMe = useCallback(async () => {
    if (!token) {
      setUser(null);
      persistMustChange(false);
      return null;
    }
    try {
      const { data } = await api.get("/auth/me");
      const normalized = normalizeUser(data);
      setUser(normalized);
      persistMustChange(Boolean(data?.must_change_password));
      return normalized;
    } catch (error) {
      logout();
      throw error;
    }
  }, [token, persistMustChange, logout]);

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
      if (event.key === MUST_CHANGE_STORAGE_KEY) {
        setMustChangePassword(event.newValue === "true");
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
      mustChangePassword,
      login,
      logout,
      applyNewToken,
      refreshMe,
      canManagePower,
      isSuperadmin,
      initializing,
    }),
    [
      token,
      user,
      mustChangePassword,
      login,
      logout,
      applyNewToken,
      refreshMe,
      canManagePower,
      isSuperadmin,
      initializing,
    ]
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
