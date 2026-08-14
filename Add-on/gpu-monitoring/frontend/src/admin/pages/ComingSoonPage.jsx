import { Link, useLocation } from "react-router-dom";
const names = { admins: "관리자 관리", servers: "서버 관리", alerts: "경고 관리", notices: "공지사항", inquiries: "문의 및 신고", settings: "시스템 설정" };
export default function ComingSoonPage() { const key = useLocation().pathname.split("/").pop(); return <section className="admin-section admin-coming"><p>다음 구현 단계</p><h2>{names[key] || "관리자 기능"}</h2><span>이 화면은 2·3차 구현 범위입니다. 존재하지 않는 API나 데이터를 구현된 것처럼 표시하지 않습니다.</span><Link to="/admin">대시보드로 돌아가기</Link></section>; }
