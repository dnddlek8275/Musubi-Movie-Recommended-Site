import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAdminAuth } from "../AdminAuthContext";

export default function AdminLoginPage() {
  const [identifier, setIdentifier] = useState(""); const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false); const [error, setError] = useState(""); const [submitting, setSubmitting] = useState(false);
  const { admin, login } = useAdminAuth(); const navigate = useNavigate(); const location = useLocation();
  useEffect(() => { if (admin) navigate("/admin", { replace: true }); }, [admin, navigate]);
  const submit = async (event) => { event.preventDefault(); setSubmitting(true); setError(""); const controller = new AbortController(); try { await login(identifier, password, controller.signal); navigate(location.state?.from?.pathname || "/admin", { replace: true }); } catch (requestError) { setError(requestError.message); } finally { setSubmitting(false); } };
  return <main className="admin-login"><section><div className="admin-login-intro"><p>GPU OPERATIONS</p><h1>관리자 콘솔</h1><span>GPU 모니터링 서비스의 운영 현황을 안전하게 관리합니다.</span></div><form onSubmit={submit}><h2>관리자 로그인</h2>{error && <div className="admin-login-error" role="alert">{error}</div>}<label>이메일 또는 아이디<input required autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} /></label><label>비밀번호<div className="password-field"><input required minLength="8" type={visible ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /><button type="button" onClick={() => setVisible((value) => !value)} aria-label={visible ? "비밀번호 숨기기" : "비밀번호 표시"}>{visible ? "숨김" : "표시"}</button></div></label><button className="admin-primary" disabled={submitting}>{submitting ? "로그인 중…" : "로그인"}</button><a href="/">GPU 모니터링 페이지로 돌아가기</a></form></section></main>;
}
