import { useLocation } from "react-router-dom";

const titles = { "/admin": "운영 대시보드", "/admin/users": "사용자 관리", "/admin/logs": "관리자 활동 로그" };

export default function AdminHeader({ admin, onMenu, onLogout }) {
  const location = useLocation();
  return <header className="admin-header"><button className="admin-menu-button" onClick={onMenu} aria-label="관리자 메뉴 열기">☰</button><div><p>ADMINISTRATION</p><h1>{titles[location.pathname] || "관리자 기능"}</h1></div><div className="admin-profile"><button aria-label="최근 알림">알림 <span>0</span></button><div><strong>{admin.name}</strong><small>{admin.role}</small></div><button onClick={onLogout}>로그아웃</button></div></header>;
}
