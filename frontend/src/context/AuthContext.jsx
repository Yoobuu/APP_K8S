/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api from "../api/axios";

const AuthContext = createContext(null);
const MUST_CHANGE_STORAGE_KEY = "mustChangePassword";

const normalizeUser = (rawUser) => (rawUser ? { ...rawUser } : null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(null);
  const [permissions, setPermissions] = useState([]);
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
    ({ token: nextToken, user: nextUser, permissions: nextPermissions, requirePasswordChange }) => {
      if (typeof nextToken === "string" && nextToken.length > 0) {
        persistToken(nextToken);
      } else if (nextToken === null) {
        persistToken(null);
      }
      setUser(nextUser ? normalizeUser(nextUser) : null);
      setPermissions(Array.isArray(nextPermissions) ? nextPermissions : []);
      if (requirePasswordChange !== undefined) {
        persistMustChange(Boolean(requirePasswordChange));
      }
    },
    [persistToken, persistMustChange]
  );

  const logout = useCallback(() => {
    persistToken(null);
    setUser(null);
    setPermissions([]);
    persistMustChange(false);
  }, [persistToken, persistMustChange]);

  const login = useCallback(
    ({ token: nextToken, user: nextUser, permissions: nextPermissions, requirePasswordChange }) => {
      applySession({
        token: nextToken,
        user: nextUser,
        permissions: nextPermissions,
        requirePasswordChange: Boolean(requirePasswordChange),
      });
    },
    [applySession]
  );

  const applyNewToken = useCallback(
    (nextToken, nextUser, nextPermissions = [], requirePasswordChange = false) => {
      applySession({
        token: nextToken,
        user: nextUser,
        permissions: nextPermissions,
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
      setPermissions(Array.isArray(data?.permissions) ? data.permissions : []);
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

  const permissionSet = useMemo(() => new Set(permissions || []), [permissions]);

  const hasPermission = useCallback(
    (code) => {
      const value = typeof code === "string" ? code : code?.value;
      if (!value) return false;
      return permissionSet.has(value);
    },
    [permissionSet],
  );

  const canManagePower = useMemo(
    () => hasPermission("vms.power") || hasPermission("hyperv.power"),
    [hasPermission],
  );

  const value = useMemo(
    () => ({
      token,
      user,
      permissions,
      mustChangePassword,
      login,
      logout,
      applyNewToken,
      refreshMe,
      hasPermission,
      canManagePower,
      initializing,
    }),
    [
      token,
      user,
      permissions,
      mustChangePassword,
      login,
      logout,
      applyNewToken,
      refreshMe,
      hasPermission,
      canManagePower,
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
