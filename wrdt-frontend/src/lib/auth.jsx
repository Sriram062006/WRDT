/**
 * Authentication context.
 *
 * Holds the signed-in user, their role and their permissions, and
 * exposes `can()` so screens gate on the server's own permission bag
 * rather than re-deriving rules in the UI. This is convenience only --
 * every rule is enforced server-side too; hiding a button the API would
 * reject just avoids a pointless round trip and a confusing error.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, onUnauthorized, tokens } from "./api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);
  const [permissions, setPermissions] = useState({});
  const [assignedGroupIds, setAssignedGroupIds] = useState([]);
  const [booting, setBooting] = useState(true);

  const applyMe = useCallback((me) => {
    setUser(me.user);
    setRole(me.role);
    setPermissions(me.permissions || {});
    setAssignedGroupIds(me.assigned_group_ids || []);
  }, []);

  const clear = useCallback(() => {
    setUser(null);
    setRole(null);
    setPermissions({});
    setAssignedGroupIds([]);
  }, []);

  // Restore the session on reload so a refresh mid-meeting does not
  // bounce the supervisor back to the login screen.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!tokens.access) {
        setBooting(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) applyMe(me);
      } catch {
        tokens.clear();
      } finally {
        if (!cancelled) setBooting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyMe]);

  useEffect(() => onUnauthorized(clear), [clear]);

  const login = useCallback(
    async (email, password) => {
      await api.login(email, password);
      applyMe(await api.me());
    },
    [applyMe]
  );

  const logout = useCallback(async () => {
    await api.logout();
    clear();
  }, [clear]);

  const value = useMemo(
    () => ({
      user,
      role,
      permissions,
      assignedGroupIds,
      booting,
      isOwner: role === "owner",
      can: (key) => Boolean(permissions[key]),
      login,
      logout,
      refreshMe: async () => applyMe(await api.me()),
    }),
    [user, role, permissions, assignedGroupIds, booting, login, logout, applyMe]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
