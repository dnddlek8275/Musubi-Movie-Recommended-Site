import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { useAdminAuth } from "../AdminAuthContext";
import AdminHeader from "./AdminHeader";
import AdminSidebar from "./AdminSidebar";

export default function AdminLayout() {
  const [open, setOpen] = useState(false);
  const { admin, logout } = useAdminAuth();
  const navigate = useNavigate();
  const handleLogout = async () => { await logout(); navigate("/admin/login", { replace: true }); };
  return <div className="admin-shell"><AdminSidebar open={open} onClose={() => setOpen(false)} onLogout={handleLogout} /><div className="admin-workspace"><AdminHeader admin={admin} onMenu={() => setOpen(true)} onLogout={handleLogout} /><div className="admin-content"><Outlet /></div></div></div>;
}
