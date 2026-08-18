import { NavLink } from "react-router-dom";

const menus = [
  ["/admin", "대시보드", true], ["/admin/users", "사용자 관리"], ["/admin/admins", "관리자 관리"],
  ["/admin/servers", "서버 관리"], ["/admin/alerts", "경고 관리"], ["/admin/notices", "공지사항"],
  ["/admin/inquiries", "문의 및 신고"], ["/admin/logs", "관리자 로그"], ["/admin/settings", "시스템 설정"],
];

export default function AdminSidebar({ open, onClose, onLogout }) {
  return <><button className={`admin-backdrop ${open ? "show" : ""}`} aria-label="사이드바 닫기" onClick={onClose} /><aside className={`admin-sidebar ${open ? "open" : ""}`}>
    <div className="admin-brand"><span>GPU OPS</span><strong>Admin Console</strong></div>
    <nav aria-label="관리자 메뉴">{menus.map(([path, label, end]) => <NavLink key={path} to={path} end={end} onClick={onClose}>{label}</NavLink>)}</nav>
    <div className="admin-side-footer"><NavLink to="/" onClick={onClose}>사용자 페이지로 이동</NavLink><button type="button" onClick={onLogout}>로그아웃</button></div>
  </aside></>;
}
