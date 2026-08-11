import { useEffect, useMemo, useState } from 'react';
import {
  checkAdminAccess, createAdminMovie, deleteAdminMovie, deleteAdminUser, fetchAdminAuditLogs, fetchAdminInquiries, fetchAdminMovies,
  fetchAdminOverview, fetchAdminUsers, registerAdminTmdbMovie,
  refreshAdminTmdbMovie, replyAdminInquiry, retryAdminMovieVectorSync, searchAdminTmdbMovies, updateAdminMovie, updateUserAdminRole,
  updateAdminInquiryStatus, updateAdminUserSuspension,
} from '../../api.js';
import Logo from '../HeaderFooter/Logo.jsx';
import ThemeToggle from '../HeaderFooter/ThemeToggle.jsx';
import { PanelSkeleton } from '../common/LoadingSkeleton.jsx';
import './adminApiPage.css';

const emptyMovie = { title: '', overview: '', genres: '', director: '', cast: '', keywords: '', year: '', release_date: '', runtime: '', production_countries: '', certification: '', certification_country: '', language: '', audience_count: '' };
const editableFields = Object.keys(emptyMovie);
const listFields = new Set(['genres', 'cast', 'keywords', 'production_countries']);
const numberFields = new Set(['year', 'runtime', 'audience_count']);
const navigation = [
  ['overview', '운영 현황', '서비스 핵심 지표'],
  ['catalog', '영화 관리', '내부 콘텐츠 탐색·수정'],
  ['register', '콘텐츠 등록', 'TMDB·직접 등록'],
  ['inquiries', '문의 관리', '회원·비회원 문의함'],
  ['users', '사용자 관리', '회원·권한 관리'],
  ['audit', '감사 로그', '관리자 작업 전체 기록'],
];
const allNavigation = navigation;

const formatNumber = (value) => Number(value || 0).toLocaleString('ko-KR');
const formatDate = (value) => value ? new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';
const formatDateOnly = (value) => value ? new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value)) : '—';
const actionLabels = { CREATE_MOVIE: '영화 등록', UPDATE_MOVIE: '영화 수정', DELETE_MOVIE: '영화 삭제', REFRESH_TMDB_MOVIE: 'TMDB 정보 동기화', RETRY_VECTOR_SYNC: '벡터 동기화 재시도', GRANT_ADMIN: '관리자 권한 부여', REVOKE_ADMIN: '관리자 권한 회수', SUSPEND_USER: '계정 정지', UNSUSPEND_USER: '계정 정지 해제', DELETE_USER: '계정 삭제', UPDATE_INQUIRY_STATUS: '문의 상태 변경', REPLY_INQUIRY: '문의 답변 발송' };

function directMoviePayload(form) {
  const payload = { title: form.title.trim() };
  editableFields.slice(1).forEach((key) => {
    const value = String(form[key] ?? '').trim();
    if (!value) return;
    payload[key] = listFields.has(key) ? value.split(',').map((item) => item.trim()).filter(Boolean) : numberFields.has(key) ? Number(value) : value;
  });
  return payload;
}

export default function AdminApiPage({ authUser }) {
  const [tab, setTab] = useState('overview');
  const [adminCheck, setAdminCheck] = useState({ status: 'checking', data: null, error: '' });
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (!authUser) { setAdminCheck({ status: 'anonymous', data: null, error: '' }); return undefined; }
    const controller = new AbortController();
    checkAdminAccess(controller.signal)
      .then((response) => setAdminCheck(response.data?.is_admin ? { status: 'allowed', data: response.data, error: '' } : { status: 'forbidden', data: response.data, error: '관리자 권한이 필요합니다.' }))
      .catch((error) => { if (error.name !== 'AbortError') setAdminCheck({ status: 'forbidden', data: null, error: error.message }); });
    return () => controller.abort();
  }, [authUser]);

  if (!authUser) return <AdminState title="관리자 로그인이 필요합니다." message="관리자 계정으로 로그인한 뒤 다시 접속해 주세요." href="/login" link="로그인" />;
  if (adminCheck.status === 'checking') return <main className="admin-loading"><PanelSkeleton lines={5} /></main>;
  if (adminCheck.status !== 'allowed') return <AdminState title="접근 권한이 없습니다." message={adminCheck.error} href="/home" link="홈으로 이동" />;

  return <div className="musubi-admin">
    <header className="admin-topbar">
      <a href="/home" className="admin-logo" aria-label="Musubi 홈"><Logo /></a>
      <div className="admin-topbar__title"><b>ADMIN CONSOLE</b><span>운영자 전용</span></div>
      <div className="admin-topbar__actions"><span>{adminCheck.data?.email}</span><a href="/home">서비스 화면</a><ThemeToggle /></div>
    </header>
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-sidebar__intro"><small>MUSUBI OPERATIONS</small><h1>서비스 운영</h1><p>영화와 사람을 잇는 서비스의 콘텐츠, 사용자, 활동 상태를 관리합니다.</p></div>
        <nav aria-label="관리자 메뉴">{navigation.map(([id, label, caption]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => { setTab(id); setNotice(null); }}><span>{label}</span><small>{caption}</small></button>)}</nav>
      </aside>
      <main className="admin-content">
        <div className="admin-page-heading"><div><small>{allNavigation.find(([id]) => id === tab)?.[2]}</small><h2>{allNavigation.find(([id]) => id === tab)?.[1]}</h2></div><span className="admin-status"><i /> 관리자 인증됨</span></div>
        {notice && <div className={`admin-notice ${notice.type}`} role="status">{notice.text}<button onClick={() => setNotice(null)}>×</button></div>}
        {tab === 'overview' && <OverviewPanel setTab={setTab} />}
        {tab === 'catalog' && <CatalogPanel setNotice={setNotice} />}
        {tab === 'register' && <RegisterPanel setNotice={setNotice} />}
        {tab === 'inquiries' && <InquiryPanel setNotice={setNotice} />}
        {tab === 'users' && <UsersPanel currentEmail={adminCheck.data?.email} setNotice={setNotice} />}
        {tab === 'audit' && <AuditPanel setNotice={setNotice} />}
      </main>
    </div>
  </div>;
}

function AdminState({ title, message, href, link }) { return <main className="admin-state"><Logo /><h1>{title}</h1><p>{message}</p><a href={href}>{link}</a></main>; }

function OverviewPanel({ setTab }) {
  const [state, setState] = useState({ loading: true, data: null, error: '' });
  useEffect(() => { const controller = new AbortController(); fetchAdminOverview(controller.signal).then((response) => setState({ loading: false, data: response.data, error: '' })).catch((error) => { if (error.name !== 'AbortError') setState({ loading: false, data: null, error: error.message }); }); return () => controller.abort(); }, []);
  if (state.loading) return <PanelSkeleton lines={8} />;
  if (state.error) return <EmptyState title="운영 현황을 불러오지 못했습니다." text={state.error} />;
  const { users, movies, activity, vector_sync: vectorSync, top_movies: topMovies, recent_audits: audits } = state.data;
  const cards = [
    ['등록 사용자', users.total, `최근 7일 +${formatNumber(users.new_7d)}`, 'users'],
    ['보유 영화', movies.total, `TMDB ${formatNumber(movies.tmdb)} · 직접 ${formatNumber(movies.manual)}`, 'catalog'],
    ['누적 대화', activity.chat_rooms, `메시지 ${formatNumber(activity.chat_messages)}개`, null],
    ['처리할 문의', activity.open_inquiries, `전체 ${formatNumber(activity.inquiries)}건`, 'inquiries'],
  ];
  return <div className="admin-dashboard">
    <section className="admin-kpis">{cards.map(([label, value, meta, target]) => <button key={label} disabled={!target} onClick={() => target && setTab(target)}><small>{label}</small><strong>{formatNumber(value)}</strong><span>{meta}</span></button>)}</section>
    <section className="admin-health-strip"><div><span>온보딩 완료</span><strong>{users.total ? Math.round((users.onboarded / users.total) * 100) : 0}%</strong></div><div><span>관리자 계정</span><strong>{formatNumber(users.admins)}</strong></div><div><span>영화 좋아요</span><strong>{formatNumber(activity.likes)}</strong></div><div><span>리뷰·평가</span><strong>{formatNumber(activity.ratings)}</strong></div><div><span>포스터 누락</span><strong className={movies.missing_poster ? 'warn' : ''}>{formatNumber(movies.missing_poster)}</strong></div></section>
    <section className="admin-sync-strip" aria-label="PostgreSQL과 Milvus 영화 동기화 현황"><div><span>벡터 동기화 완료</span><strong>{formatNumber(vectorSync?.completed)}</strong></div><div><span>대기·처리 중</span><strong className={vectorSync?.pending || vectorSync?.processing ? 'warn' : ''}>{formatNumber((vectorSync?.pending || 0) + (vectorSync?.processing || 0))}</strong></div><div><span>동기화 실패</span><strong className={vectorSync?.failed ? 'danger' : ''}>{formatNumber(vectorSync?.failed)}</strong></div><small>실패한 영화는 영화 관리에서 상태 필터 후 개별 재시도할 수 있습니다.</small></section>
    <div className="admin-dashboard-grid">
      <section className="admin-card"><CardHeader eyebrow="CONTENT PULSE" title="현재 주목받는 영화" action="영화 관리" onClick={() => setTab('catalog')} /><div className="admin-top-movies">{topMovies.map((movie, index) => <a href={`/movies/${movie.id}`} key={movie.id}><b>{String(index + 1).padStart(2, '0')}</b>{movie.poster_path ? <img src={movie.poster_path} alt="" /> : <span className="admin-poster-empty">NO IMAGE</span>}<div><strong>{movie.title}</strong><small>{movie.year || '연도 미상'} · 조회 {formatNumber(movie.view_count)} · 좋아요 {formatNumber(movie.like_count)}</small></div></a>)}</div></section>
      <section className="admin-card"><CardHeader eyebrow="AUDIT LOG" title="최근 관리자 작업" /><div className="admin-audit-list">{audits.length ? audits.map((item) => <article key={item.id}><i /><div><strong>{actionLabels[item.action] || item.action}</strong><span>{item.target_table} #{item.target_id || '—'}</span></div><div><b>{item.admin}</b><time>{formatDate(item.created_at)}</time></div></article>) : <EmptyState title="기록된 작업이 없습니다." />}</div></section>
    </div>
  </div>;
}

function CardHeader({ eyebrow, title, action, onClick }) { return <header className="admin-card__header"><div><small>{eyebrow}</small><h3>{title}</h3></div>{action && <button onClick={onClick}>{action} ›</button>}</header>; }
function EmptyState({ title, text }) { return <div className="admin-empty"><b>{title}</b>{text && <p>{text}</p>}</div>; }

function CatalogPanel({ setNotice }) {
  const [query, setQuery] = useState(''); const [submitted, setSubmitted] = useState(''); const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ source: 'all', poster: 'all', syncStatus: 'all', sort: 'updated_desc' });
  const [result, setResult] = useState(null); const [loading, setLoading] = useState(true); const [selected, setSelected] = useState(null);
  const load = (nextPage = page, nextQuery = submitted, nextFilters = filters) => { setLoading(true); fetchAdminMovies(nextQuery, nextPage, nextFilters).then((response) => { setResult(response.data); setPage(response.data.page); }).catch((error) => setNotice({ type: 'error', text: error.message })).finally(() => setLoading(false)); };
  useEffect(() => { load(1, ''); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const search = (event) => { event.preventDefault(); setSubmitted(query); load(1, query); };
  const changeFilter = (key, value) => { const next = { ...filters, [key]: value }; setFilters(next); load(1, submitted, next); };
  return <section className="admin-card admin-catalog"><CardHeader eyebrow="CONTENT LIBRARY" title="내부 영화 데이터" />
    <form className="admin-toolbar" onSubmit={search}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="영화 제목, 내부 ID 또는 TMDB ID" /><button>검색</button></form>
    <div className="admin-catalog-filters">
      <select aria-label="등록 출처" value={filters.source} onChange={(event) => changeFilter('source', event.target.value)}><option value="all">전체 출처</option><option value="tmdb">TMDB</option><option value="manual">직접 등록</option></select>
      <select aria-label="포스터 상태" value={filters.poster} onChange={(event) => changeFilter('poster', event.target.value)}><option value="all">전체 포스터</option><option value="present">포스터 있음</option><option value="missing">포스터 누락</option></select>
      <select aria-label="벡터 동기화 상태" value={filters.syncStatus} onChange={(event) => changeFilter('syncStatus', event.target.value)}><option value="all">전체 벡터 상태</option><option value="pending">대기</option><option value="processing">처리 중</option><option value="completed">완료</option><option value="failed">실패</option><option value="unknown">작업 없음</option><option value="not_applicable">대상 아님</option></select>
      <select aria-label="정렬" value={filters.sort} onChange={(event) => changeFilter('sort', event.target.value)}><option value="updated_desc">최근 수정순</option><option value="release_desc">최근 개봉순</option><option value="views_desc">조회순</option><option value="likes_desc">좋아요순</option><option value="title_asc">제목순</option></select>
    </div>
    <div className="admin-table-meta"><span>총 {formatNumber(result?.total)}편</span><small>영화를 선택하면 세부 정보를 수정할 수 있습니다.</small></div>
    {loading ? <PanelSkeleton lines={6} /> : <div className="admin-movie-table">{result?.items.map((movie) => <button key={movie.movie_id} onClick={() => setSelected(movie)}>{movie.poster_path ? <img src={movie.poster_path} alt="" /> : <span className="admin-poster-empty">NO IMAGE</span>}<div><strong>{movie.title}</strong><small>#{movie.movie_id} · {movie.tmdb_id ? `TMDB ${movie.tmdb_id}` : '직접 등록'} · {movie.release_date || movie.year || '개봉일 미상'}</small><span>{(movie.genres || []).slice(0, 3).join(' · ') || '장르 미입력'} · 벡터 {movie.vector_sync?.status || '알 수 없음'}</span></div><div className="admin-row-stats"><span>조회 {formatNumber(movie.view_count)}</span><span>좋아요 {formatNumber(movie.like_count)}</span><b>관리 ›</b></div></button>)}</div>}
    {result && <Pagination page={page} total={result.total_pages} onChange={(next) => load(next)} />}
    {selected && <MovieEditor movie={selected} onClose={() => setSelected(null)} onSaved={() => load(page)} setNotice={setNotice} />}
  </section>;
}

function MovieEditor({ movie, onClose, onSaved, setNotice }) {
  const initial = useMemo(() => Object.fromEntries(editableFields.map((key) => [key, listFields.has(key) ? (movie[key] || []).join(', ') : String(movie[key] ?? '')])), [movie]);
  const [form, setForm] = useState(initial); const [busy, setBusy] = useState(false); const [confirmDelete, setConfirmDelete] = useState(false); const [deleteText, setDeleteText] = useState('');
  const submit = async (event) => { event.preventDefault(); setBusy(true); const payload = {}; editableFields.forEach((key) => { if (key === 'cast' && movie.tmdb_id) return; const value = form[key].trim(); payload[key] = listFields.has(key) ? value.split(',').map((item) => item.trim()).filter(Boolean) : numberFields.has(key) ? (value ? Number(value) : null) : (value || null); }); try { const response = await updateAdminMovie(movie.movie_id, payload); setNotice({ type: 'success', text: response.message }); onSaved(); onClose(); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  const remove = async () => { if (deleteText !== movie.title) return; setBusy(true); try { const response = await deleteAdminMovie(movie.movie_id); setNotice({ type: 'success', text: response.message }); onSaved(); onClose(); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  const runSync = async (type) => { setBusy(true); try { const response = type === 'tmdb' ? await refreshAdminTmdbMovie(movie.movie_id) : await retryAdminMovieVectorSync(movie.movie_id); setNotice({ type: 'success', text: response.message }); onSaved(); if (type === 'tmdb') onClose(); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  return <div className="admin-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="admin-modal"><header><div><small>INTERNAL MOVIE #{movie.movie_id}</small><h3>{movie.title}</h3></div><button onClick={onClose}>×</button></header><form className="admin-form" onSubmit={submit}><div className="admin-movie-meta"><span>TMDB 평점 <b>{movie.vote_average ?? '—'}</b> ({formatNumber(movie.vote_count)}표)</span><span>마지막 TMDB 동기화 <b>{formatDate(movie.last_synced_at)}</b></span><span>벡터 상태 <b className={`sync-${movie.vector_sync?.status}`}>{movie.vector_sync?.status || '알 수 없음'}</b></span></div><MovieFields form={form} setForm={setForm} tmdbLocked={Boolean(movie.tmdb_id)} />{movie.tmdb_id && <div className="admin-sync-actions"><button type="button" onClick={() => runSync('tmdb')} disabled={busy}>TMDB 최신 정보 가져오기</button><button type="button" onClick={() => runSync('vector')} disabled={busy}>벡터 동기화 재시도</button></div>}{confirmDelete && <div className="admin-delete-confirm"><b>삭제하면 관련 추천·활동 데이터에 영향을 줄 수 있습니다.</b><label>확인을 위해 영화 제목을 입력하세요.<input value={deleteText} onChange={(event) => setDeleteText(event.target.value)} placeholder={movie.title} /></label><button type="button" onClick={remove} disabled={busy || deleteText !== movie.title}>영구 삭제</button></div>}<div className="admin-form-actions"><button type="button" className="danger" onClick={() => setConfirmDelete((value) => !value)} disabled={busy}>삭제</button><span /><button type="button" onClick={onClose}>취소</button><button className="primary" disabled={busy}>{busy ? '처리 중…' : '변경 저장'}</button></div></form></section></div>;
}

function RegisterPanel({ setNotice }) {
  const [mode, setMode] = useState('tmdb');
  return <section className="admin-card"><CardHeader eyebrow="CONTENT INGEST" title="영화 등록" /><div className="admin-segment"><button className={mode === 'tmdb' ? 'active' : ''} onClick={() => setMode('tmdb')}>TMDB에서 가져오기</button><button className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>직접 입력</button></div>{mode === 'tmdb' ? <TmdbPanel setNotice={setNotice} /> : <DirectMoviePanel setNotice={setNotice} />}</section>;
}
function TmdbPanel({ setNotice }) {
  const [query, setQuery] = useState(''); const [result, setResult] = useState(null); const [busy, setBusy] = useState(false); const [registering, setRegistering] = useState(null);
  const search = async (event) => { event?.preventDefault(); setBusy(true); try { const response = await searchAdminTmdbMovies(query, 1); setResult(response.data); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  const register = async (movie) => { setRegistering(movie.tmdb_id); try { const response = await registerAdminTmdbMovie(movie.tmdb_id); setNotice({ type: 'success', text: response.message }); setResult((previous) => ({ ...previous, movies: previous.movies.map((item) => item.tmdb_id === movie.tmdb_id ? { ...item, is_registered: true } : item) })); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setRegistering(null); } };
  return <div className="admin-register-body"><form className="admin-toolbar" onSubmit={search}><input required value={query} onChange={(event) => setQuery(event.target.value)} placeholder="TMDB에서 영화 제목 검색" /><button disabled={busy}>{busy ? '검색 중…' : '검색'}</button></form>{result ? <div className="admin-tmdb-grid">{result.movies.map((movie) => <article key={movie.tmdb_id}>{movie.poster_path ? <img src={movie.poster_path} alt="" /> : <span className="admin-poster-empty">NO IMAGE</span>}<div><small>TMDB #{movie.tmdb_id}</small><h4>{movie.title}</h4><p>{movie.release_date || '개봉일 미상'} · 평점 {movie.vote_average ?? '—'}</p><button disabled={movie.is_registered || registering === movie.tmdb_id} onClick={() => register(movie)}>{movie.is_registered ? '등록됨' : registering === movie.tmdb_id ? '등록 중…' : '등록'}</button></div></article>)}</div> : <EmptyState title="TMDB 영화 데이터를 검색해 보세요." text="선택한 영화의 상세 정보·배우·키워드를 함께 가져옵니다." />}</div>;
}

function DirectMoviePanel({ setNotice }) {
  const [form, setForm] = useState(emptyMovie); const [busy, setBusy] = useState(false);
  const submit = async (event) => { event.preventDefault(); setBusy(true); try { const response = await createAdminMovie(directMoviePayload(form)); setNotice({ type: 'success', text: response.message }); setForm(emptyMovie); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  return <form className="admin-form admin-register-body" onSubmit={submit}><MovieFields form={form} setForm={setForm} /><div className="admin-form-actions"><span /><button type="button" onClick={() => setForm(emptyMovie)}>초기화</button><button className="primary" disabled={busy}>{busy ? '등록 중…' : '직접 등록'}</button></div></form>;
}

function MovieFields({ form, setForm, tmdbLocked = false }) {
  const field = (key) => ({ value: form[key], onChange: (event) => setForm({ ...form, [key]: event.target.value }) });
  return <div className="admin-fields"><label className="wide">영화 제목<input {...field('title')} required /></label><label>개봉일<input {...field('release_date')} type="date" /></label><label>연도<input {...field('year')} type="number" /></label><label>상영시간(분)<input {...field('runtime')} type="number" min="1" max="1440" /></label><label>감독<input {...field('director')} /></label><label>언어<input {...field('language')} placeholder="ko" /></label><label>관객 수<input {...field('audience_count')} type="number" min="0" /></label><label>관람등급<input {...field('certification')} placeholder="예: 15" /></label><label>등급 국가<input {...field('certification_country')} maxLength="2" placeholder="KR" /></label><label className="wide">제작 국가<input {...field('production_countries')} placeholder="ISO 코드, 쉼표로 구분 (예: KR, US)" /></label><label className="wide">장르<input {...field('genres')} placeholder="쉼표로 구분" /></label><label className="wide">배우<input {...field('cast')} disabled={tmdbLocked} placeholder={tmdbLocked ? 'TMDB 등록 영화는 배우 정보를 직접 수정할 수 없습니다.' : '쉼표로 구분'} /></label><label className="wide">키워드<input {...field('keywords')} placeholder="쉼표로 구분" /></label><label className="wide">줄거리<textarea {...field('overview')} rows="5" /></label></div>;
}

const inquiryCategoryLabels = { service: '서비스 이용', movie_data: '영화 정보', ai: 'AI 추천·대화', account: '계정·로그인', other: '기타' };
const inquiryStatusLabels = { received: '접수', in_progress: '확인 중', replied: '답변 완료', closed: '종료' };

function InquiryPanel({ setNotice }) {
  const [query, setQuery] = useState(''); const [status, setStatus] = useState('all'); const [page, setPage] = useState(1);
  const [result, setResult] = useState(null); const [loading, setLoading] = useState(true); const [selected, setSelected] = useState(null);
  const [replyBody, setReplyBody] = useState(''); const [replying, setReplying] = useState(false);
  const load = (nextPage = 1, nextQuery = query, nextStatus = status) => { setLoading(true); fetchAdminInquiries(nextQuery, nextStatus, nextPage).then((response) => { setResult(response.data); setPage(response.data.page); setSelected((current) => current ? response.data.items.find((item) => item.id === current.id) || null : null); }).catch((error) => setNotice({ type: 'error', text: error.message })).finally(() => setLoading(false)); };
  useEffect(() => { load(1, '', 'all'); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const changeStatus = async (item, nextStatus) => { try { const response = await updateAdminInquiryStatus(item.id, nextStatus); setNotice({ type: 'success', text: response.message }); load(page); } catch (error) { setNotice({ type: 'error', text: error.message }); } };
  const selectInquiry = (item) => { setSelected(item); setReplyBody(item.reply_body || ''); };
  const sendReply = async () => { if (!selected || replyBody.trim().length < 2) return; setReplying(true); try { const response = await replyAdminInquiry(selected.id, replyBody.trim()); setNotice({ type: 'success', text: response.message }); load(page); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setReplying(false); } };
  return <section className="admin-card"><CardHeader eyebrow="CUSTOMER SUPPORT" title="문의함" />
    <div className="admin-inquiry-tools"><form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); load(1); }}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="이메일, 제목 또는 문의 내용 검색" /><button>검색</button></form><select value={status} onChange={(event) => { const next = event.target.value; setStatus(next); load(1, query, next); }}><option value="all">전체 상태</option>{Object.entries(inquiryStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
    <div className="admin-table-meta"><span>총 {formatNumber(result?.total)}건</span><small>회원과 비회원 모두 접수 이메일로 회신합니다.</small></div>
    {loading ? <PanelSkeleton lines={6} /> : result?.items.length ? <div className="admin-inquiry-layout"><div className="admin-inquiry-list">{result.items.map((item) => <button className={selected?.id === item.id ? 'active' : ''} key={item.id} onClick={() => selectInquiry(item)}><span className={`inquiry-status ${item.status}`}>{inquiryStatusLabels[item.status] || item.status}</span><div><strong>{item.subject}</strong><small>#{item.id} · {item.member ? item.nickname || '회원' : '비회원'} · {formatDate(item.created_at)}</small></div><b>{inquiryCategoryLabels[item.category] || item.category}</b></button>)}</div>{selected ? <article className="admin-inquiry-detail"><header><div><small>INQUIRY #{selected.id}</small><h3>{selected.subject}</h3></div><button onClick={() => setSelected(null)}>×</button></header><dl><div><dt>문의 유형</dt><dd>{inquiryCategoryLabels[selected.category] || selected.category}</dd></div><div><dt>접수자</dt><dd>{selected.member ? `${selected.nickname || '회원'} · 회원` : '비회원'}</dd></div><div><dt>회신 이메일</dt><dd>{selected.email}</dd></div><div><dt>접수 시각</dt><dd>{formatDate(selected.created_at)}</dd></div></dl><div className="admin-inquiry-message">{selected.message}</div><label className="admin-inquiry-reply">답변 내용<textarea value={replyBody} onChange={(event) => setReplyBody(event.target.value)} rows="7" placeholder="사용자에게 전송할 답변을 입력해 주세요." maxLength="10000" /><small>{replyBody.length.toLocaleString('ko-KR')} / 10,000{selected.replied_at ? ` · 마지막 발송 ${formatDate(selected.replied_at)}` : ''}</small></label><footer><select value={selected.status} onChange={(event) => changeStatus(selected, event.target.value)}>{Object.entries(inquiryStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button type="button" onClick={sendReply} disabled={replying || replyBody.trim().length < 2}>{replying ? '전송 중…' : selected.replied_at ? '답변 다시 보내기' : '답변 메일 보내기'}</button></footer><p>전송 성공 시 답변 내용과 담당 관리자, 발송 시각이 기록되고 상태가 ‘답변 완료’로 변경됩니다.</p></article> : <div className="admin-inquiry-placeholder"><b>문의를 선택해 주세요.</b><span>문의 원문과 회신 이메일을 확인할 수 있습니다.</span></div>}</div> : <EmptyState title="조건에 맞는 문의가 없습니다." />}
    {result && <Pagination page={page} total={result.total_pages} onChange={(next) => load(next)} />}
  </section>;
}

function prettyAuditData(value) {
  if (!value) return '기록 없음';
  try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
}

function AuditPanel({ setNotice }) {
  const [query, setQuery] = useState(''); const [action, setAction] = useState('all'); const [page, setPage] = useState(1);
  const [result, setResult] = useState(null); const [loading, setLoading] = useState(true); const [selected, setSelected] = useState(null);
  const load = (nextPage = 1, nextQuery = query, nextAction = action) => { setLoading(true); fetchAdminAuditLogs(nextQuery, nextAction, nextPage).then((response) => { setResult(response.data); setPage(response.data.page); }).catch((error) => setNotice({ type: 'error', text: error.message })).finally(() => setLoading(false)); };
  useEffect(() => { load(1, '', 'all'); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="admin-card"><CardHeader eyebrow="AUDIT TRAIL" title="관리자 작업 기록" /><div className="admin-audit-tools"><form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); load(1); }}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="작업, 대상, 관리자 또는 ID 검색" /><button>검색</button></form><select aria-label="작업 종류" value={action} onChange={(event) => { setAction(event.target.value); load(1, query, event.target.value); }}><option value="all">전체 작업</option>{result?.actions?.map((item) => <option key={item} value={item}>{actionLabels[item] || item}</option>)}</select></div><div className="admin-table-meta"><span>총 {formatNumber(result?.total)}건</span><small>변경 전·후 데이터와 수행 관리자를 확인할 수 있습니다.</small></div>{loading ? <PanelSkeleton lines={7} /> : result?.items?.length ? <div className="admin-audit-table">{result.items.map((item) => <button key={item.id} onClick={() => setSelected(item)}><span className="admin-audit-table__dot" /><div><b>{actionLabels[item.action] || item.action}</b><small>{item.target_table} #{item.target_id || '—'} · 로그 #{item.id}</small></div><div><strong>{item.admin_nickname}</strong><small>{item.admin_email || '삭제된 계정'} · {formatDate(item.created_at)}</small></div><span>상세 ›</span></button>)}</div> : <EmptyState title="조건에 맞는 감사 로그가 없습니다." />}{result && <Pagination page={page} total={result.total_pages} onChange={(next) => load(next)} />}{selected && <div className="admin-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><section className="admin-modal admin-audit-modal"><header><div><small>AUDIT LOG #{selected.id}</small><h3>{actionLabels[selected.action] || selected.action}</h3></div><button onClick={() => setSelected(null)}>×</button></header><div className="admin-audit-detail"><dl><div><dt>수행 관리자</dt><dd>{selected.admin_nickname} · {selected.admin_email || '삭제된 계정'}</dd></div><div><dt>대상</dt><dd>{selected.target_table} #{selected.target_id || '—'}</dd></div><div><dt>작업 시각</dt><dd>{formatDate(selected.created_at)}</dd></div><div><dt>작업 코드</dt><dd>{selected.action}</dd></div></dl><section><h4>변경 전</h4><pre>{prettyAuditData(selected.before_data)}</pre></section><section><h4>변경 후</h4><pre>{prettyAuditData(selected.after_data)}</pre></section></div></section></div>}</section>;
}

function UsersPanel({ currentEmail, setNotice }) {
  const [query, setQuery] = useState(''); const [result, setResult] = useState(null); const [page, setPage] = useState(1); const [loading, setLoading] = useState(true);
  const [menuUserId, setMenuUserId] = useState(null); const [actionTarget, setActionTarget] = useState(null); const [reason, setReason] = useState(''); const [confirmText, setConfirmText] = useState(''); const [busy, setBusy] = useState(false);
  const load = (nextPage = 1, nextQuery = query) => { setLoading(true); fetchAdminUsers(nextQuery, nextPage).then((response) => { setResult(response.data); setPage(response.data.page); }).catch((error) => setNotice({ type: 'error', text: error.message })).finally(() => setLoading(false)); };
  useEffect(() => { load(1, ''); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const close = () => setMenuUserId(null); document.addEventListener('pointerdown', close); return () => document.removeEventListener('pointerdown', close); }, []);
  const openAction = (user, type) => { setMenuUserId(null); setActionTarget({ user, type }); setReason(''); setConfirmText(''); };
  const closeAction = () => { if (!busy) setActionTarget(null); };
  const executeAction = async () => {
    if (!actionTarget) return;
    const { user, type } = actionTarget;
    setBusy(true);
    try {
      let response;
      if (type === 'suspension') response = await updateAdminUserSuspension(user.id, !user.is_suspended, reason);
      else if (type === 'delete') response = await deleteAdminUser(user.id);
      else response = await updateUserAdminRole(user.email, !user.is_admin);
      setNotice({ type: 'success', text: response.message });
      setActionTarget(null);
      load(page);
    } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); }
  };
  const actionReady = actionTarget?.type === 'delete' ? confirmText === actionTarget.user.email : actionTarget?.type === 'suspension' && !actionTarget.user.is_suspended ? reason.trim().length >= 2 : true;
  return <section className="admin-card admin-users-card"><CardHeader eyebrow="MEMBER DIRECTORY" title="사용자와 관리자 권한" /><form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); load(1); }}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="이메일 또는 닉네임 검색" /><button>검색</button></form><div className="admin-table-meta"><span>총 {formatNumber(result?.total)}명</span><small>계정 및 권한 변경은 즉시 적용되고 감사 로그에 기록됩니다.</small></div>{loading ? <PanelSkeleton lines={6} /> : <div className="admin-user-table"><div className="admin-user-table__head"><span>사용자</span><span>계정 상태</span><span>온보딩</span><span>가입일</span><span>작업</span></div>{result?.items.map((user) => <article key={user.id}><div><b>{user.nickname}{user.is_admin && <em>관리자</em>}</b><small>{user.email}</small></div><span className={`admin-account-status${user.is_suspended ? ' suspended' : ''}`}>{user.is_suspended ? '정지' : '정상'}</span><span>{user.onboarding_completed ? '완료' : '미완료'}</span><time>{formatDateOnly(user.created_at)}</time><div className="admin-user-actions" onPointerDown={(event) => event.stopPropagation()}><button className="admin-user-more" aria-label={`${user.nickname} 계정 작업`} aria-expanded={menuUserId === user.id} onClick={() => setMenuUserId((current) => current === user.id ? null : user.id)}>⋮</button>{menuUserId === user.id && <div className="admin-user-menu"><button disabled={user.email === currentEmail} onClick={() => openAction(user, 'suspension')}>{user.is_suspended ? '계정 정지 해제' : '계정 정지'}</button><button className="danger" disabled={user.email === currentEmail} onClick={() => openAction(user, 'delete')}>계정 삭제</button><button disabled={user.email === currentEmail} onClick={() => openAction(user, 'role')}>{user.is_admin ? '권한 회수' : '권한 부여'}</button></div>}</div></article>)}</div>}{result && <Pagination page={page} total={result.total_pages} onChange={(next) => load(next)} />}{actionTarget && <div className="admin-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closeAction()}><section className="admin-modal admin-user-action-modal"><header><div><small>USER #{actionTarget.user.id}</small><h3>{actionTarget.type === 'delete' ? '계정 삭제' : actionTarget.type === 'role' ? actionTarget.user.is_admin ? '관리자 권한 회수' : '관리자 권한 부여' : actionTarget.user.is_suspended ? '계정 정지 해제' : '계정 정지'}</h3></div><button onClick={closeAction}>×</button></header><div className="admin-user-action-body"><div className="admin-user-action-target"><b>{actionTarget.user.nickname}</b><span>{actionTarget.user.email}</span></div>{actionTarget.type === 'suspension' && !actionTarget.user.is_suspended && <label>정지 사유<textarea value={reason} onChange={(event) => setReason(event.target.value)} rows="4" maxLength="500" placeholder="사용자에게 안내할 수 있도록 정지 사유를 입력해 주세요." /></label>}{actionTarget.type === 'suspension' && actionTarget.user.is_suspended && <p>정지를 해제하면 이 계정은 다시 로그인하고 서비스를 이용할 수 있습니다.</p>}{actionTarget.type === 'role' && <p>{actionTarget.user.is_admin ? '관리자 페이지 접근 권한을 회수합니다.' : '영화·사용자·문의 관리 권한을 부여합니다.'}</p>}{actionTarget.type === 'delete' && <><p className="danger">계정과 채팅, 취향, 좋아요 등 관련 사용자 데이터가 삭제되며 되돌릴 수 없습니다.</p><label>확인을 위해 이메일을 입력하세요.<input value={confirmText} onChange={(event) => setConfirmText(event.target.value)} placeholder={actionTarget.user.email} /></label></>}<footer><button type="button" onClick={closeAction}>취소</button><button type="button" className={actionTarget.type === 'delete' ? 'danger' : 'primary'} disabled={busy || !actionReady} onClick={executeAction}>{busy ? '처리 중…' : '확인'}</button></footer></div></section></div>}</section>;
}

function Pagination({ page, total, onChange }) {
  const [draft, setDraft] = useState(String(page));
  useEffect(() => setDraft(String(page)), [page]);
  const jump = (event) => { event.preventDefault(); const next = Math.min(total, Math.max(1, Number(draft) || 1)); setDraft(String(next)); onChange(next); };
  return <form className="admin-pagination" onSubmit={jump}><button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹</button><label><span className="sr-only">이동할 페이지</span><input type="number" min="1" max={total} value={draft} onChange={(event) => setDraft(event.target.value)} /></label><span>/ {total}</span><button type="submit">이동</button><button type="button" disabled={page >= total} onClick={() => onChange(page + 1)}>›</button></form>;
}
