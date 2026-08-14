const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const ACCESS_KEY = "gpu_admin_access_token";
const REFRESH_KEY = "gpu_admin_refresh_token";

export const tokens = {
  access: () => sessionStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set: (data) => {
    if (data.access_token) sessionStorage.setItem(ACCESS_KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
  },
  clear: () => { sessionStorage.removeItem(ACCESS_KEY); localStorage.removeItem(REFRESH_KEY); },
};

async function parse(response) {
  const body = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
  if (!response.ok) {
    const error = new Error(body.message || "요청에 실패했습니다.");
    error.status = response.status;
    throw error;
  }
  return body;
}

async function refreshAccess() {
  const refreshToken = tokens.refresh();
  if (!refreshToken) throw new Error("로그인이 필요합니다.");
  const response = await fetch(`${BASE_URL}/api/admin/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refreshToken }) });
  const body = await parse(response);
  tokens.set(body.data);
  return body.data.access_token;
}

export async function adminRequest(path, options = {}, retry = true) {
  const headers = { ...options.headers, Authorization: `Bearer ${tokens.access() || ""}` };
  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (response.status === 401 && retry && tokens.refresh()) {
    const access = await refreshAccess();
    return adminRequest(path, { ...options, headers: { ...options.headers, Authorization: `Bearer ${access}` } }, false);
  }
  return parse(response);
}

export async function loginAdmin(identifier, password, signal) {
  const response = await fetch(`${BASE_URL}/api/admin/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identifier, password }), signal });
  const body = await parse(response);
  tokens.set(body.data);
  return body.data.user;
}

export const getAdminMe = (signal) => adminRequest("/api/admin/auth/me", { signal });
export const logoutAdmin = () => adminRequest("/api/admin/auth/logout", { method: "POST" });
export const getDashboard = (signal) => Promise.all([
  adminRequest("/api/admin/dashboard/summary", { signal }), adminRequest("/api/admin/dashboard/gpu-summary", { signal }),
  adminRequest("/api/admin/dashboard/recent-users", { signal }), adminRequest("/api/admin/dashboard/recent-alerts", { signal }),
  adminRequest("/api/admin/dashboard/recent-logs", { signal }),
]);
export const getAdminUsers = (params, signal) => adminRequest(`/api/admin/users?${new URLSearchParams(params)}`, { signal });
export const getAdminLogs = (params, signal) => adminRequest(`/api/admin/logs?${new URLSearchParams(params)}`, { signal });
