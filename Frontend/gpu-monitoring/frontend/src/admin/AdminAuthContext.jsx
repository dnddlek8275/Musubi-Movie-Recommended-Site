import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getAdminMe, loginAdmin, logoutAdmin, tokens } from "./api/adminApi";

const AdminAuthContext = createContext(null);

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [checking, setChecking] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    if (!tokens.access() && !tokens.refresh()) { setChecking(false); return () => controller.abort(); }
    getAdminMe(controller.signal).then((response) => setAdmin(response.data)).catch(() => tokens.clear()).finally(() => setChecking(false));
    return () => controller.abort();
  }, []);
  const value = useMemo(() => ({
    admin, checking,
    login: async (identifier, password, signal) => { const user = await loginAdmin(identifier, password, signal); setAdmin(user); },
    logout: async () => { try { await logoutAdmin(); } finally { tokens.clear(); setAdmin(null); } },
  }), [admin, checking]);
  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export const useAdminAuth = () => useContext(AdminAuthContext);
