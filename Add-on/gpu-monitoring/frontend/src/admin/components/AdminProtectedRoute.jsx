import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAdminAuth } from "../AdminAuthContext";

export default function AdminProtectedRoute() {
  const { admin, checking } = useAdminAuth();
  const location = useLocation();
  if (checking) return <div className="admin-full-state">관리자 인증을 확인하는 중입니다…</div>;
  if (!admin) return <Navigate to="/admin/login" replace state={{ from: location }} />;
  if (!["ADMIN", "SUPER_ADMIN"].includes(admin.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}
