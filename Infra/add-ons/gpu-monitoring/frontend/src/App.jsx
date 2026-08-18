import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AdminAuthProvider } from "./admin/AdminAuthContext";
import AdminLayout from "./admin/components/AdminLayout";
import AdminProtectedRoute from "./admin/components/AdminProtectedRoute";
import AdminDashboardPage from "./admin/pages/AdminDashboardPage";
import AdminLogPage from "./admin/pages/AdminLogPage";
import AdminLoginPage from "./admin/pages/AdminLoginPage";
import ComingSoonPage from "./admin/pages/ComingSoonPage";
import UserManagementPage from "./admin/pages/UserManagementPage";
import DashboardPage from "./pages/DashboardPage";
import "./admin/styles/admin.css";

export default function App() {
  return <BrowserRouter><AdminAuthProvider><Routes>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/admin/login" element={<AdminLoginPage />} />
    <Route element={<AdminProtectedRoute />}><Route element={<AdminLayout />}>
      <Route path="/admin" element={<AdminDashboardPage />} />
      <Route path="/admin/users" element={<UserManagementPage />} />
      <Route path="/admin/logs" element={<AdminLogPage />} />
      <Route path="/admin/:section" element={<ComingSoonPage />} />
    </Route></Route>
  </Routes></AdminAuthProvider></BrowserRouter>;
}
