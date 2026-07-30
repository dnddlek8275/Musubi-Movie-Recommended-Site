import { useEffect, useState } from 'react';
import {
  checkAdminAccess,
  createAdminMovie,
  deleteAdminMovie,
  registerAdminTmdbMovie,
  searchAdminTmdbMovies,
  updateAdminMovie,
  updateUserAdminRole,
} from '../../api.js';
import './adminApiPage.css';

const emptyMovie = {
  title: '', overview: '', genres: '', director: '', cast: '', keywords: '',
  year: '', language: '', audience_count: '',
};
const editableFields = ['title', 'overview', 'genres', 'director', 'cast', 'keywords', 'year', 'language', 'audience_count'];
const listFields = new Set(['genres', 'cast', 'keywords']);
const numberFields = new Set(['year', 'audience_count']);

function directMoviePayload(form) {
  const payload = { title: form.title.trim() };
  editableFields.slice(1).forEach((key) => {
    const value = form[key].trim();
    if (!value) return;
    payload[key] = listFields.has(key)
      ? value.split(',').map((item) => item.trim()).filter(Boolean)
      : numberFields.has(key) ? Number(value) : value;
  });
  return payload;
}

function editMoviePayload(form, included, cleared, isTmdbMovie) {
  const payload = {};
  editableFields.forEach((key) => {
    if (!included[key] || (key === 'cast' && isTmdbMovie)) return;
    if (cleared[key]) {
      payload[key] = listFields.has(key) ? [] : null;
      return;
    }
    const value = form[key].trim();
    if (listFields.has(key)) payload[key] = value.split(',').map((item) => item.trim()).filter(Boolean);
    else if (numberFields.has(key)) payload[key] = value === '' ? null : Number(value);
    else payload[key] = value;
  });
  return payload;
}

export default function AdminApiPage({ authUser }) {
  const [tab, setTab] = useState('tmdb');
  const [adminCheck, setAdminCheck] = useState({ status: 'checking', data: null, error: '' });
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (!authUser) { setAdminCheck({ status: 'anonymous', data: null, error: '' }); return undefined; }
    const controller = new AbortController();
    checkAdminAccess(controller.signal)
      .then((response) => setAdminCheck(response.data?.is_admin
        ? { status: 'allowed', data: response.data, error: '' }
        : { status: 'forbidden', data: response.data, error: '관리자 권한이 필요합니다.' }))
      .catch((error) => { if (error.name !== 'AbortError') setAdminCheck({ status: 'forbidden', data: null, error: error.message }); });
    return () => controller.abort();
  }, [authUser]);

  if (!authUser) return <AdminState title="관리자 로그인이 필요합니다." message="Access Token이 필요합니다." href="/login" link="로그인으로 이동" />;
  if (adminCheck.status === 'checking') return <AdminState title="관리자 권한을 확인하고 있습니다." message="GET /admin/check" />;
  if (adminCheck.status !== 'allowed') return <AdminState title="접근 권한이 없습니다." message={adminCheck.error || '관리자 권한이 필요합니다.'} href="/" link="홈으로 이동" />;

  return <main className="be2-admin">
    <header><div><p>CINEVERSE OPERATIONS · BE2</p><h1>영화 관리자</h1><span>TMDB 영화와 직접 등록 영화를 관리합니다.</span></div><div className="be2-admin-identity"><span>{adminCheck.data?.email}</span><a href="/">사용자 페이지</a></div></header>
    <nav aria-label="관리자 기능">
      <Tab id="tmdb" tab={tab} setTab={setTab}>TMDB 검색·등록</Tab>
      <Tab id="create" tab={tab} setTab={setTab}>영화 직접 등록</Tab>
      <Tab id="edit" tab={tab} setTab={setTab}>영화 수정·삭제</Tab>
      <Tab id="roles" tab={tab} setTab={setTab}>관리자 권한</Tab>
    </nav>
    {notice && <div className={`be2-notice ${notice.type}`} role="status">{notice.text}</div>}
    {tab === 'tmdb' && <TmdbPanel setNotice={setNotice} />}
    {tab === 'create' && <DirectMoviePanel setNotice={setNotice} />}
    {tab === 'edit' && <EditMoviePanel setNotice={setNotice} />}
    {tab === 'roles' && <AdminRolePanel setNotice={setNotice} />}
  </main>;
}

function Tab({ id, tab, setTab, children }) { return <button className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{children}</button>; }
function AdminState({ title, message, href, link }) { return <main className="be2-admin-state"><h1>{title}</h1><p>{message}</p>{href && <a href={href}>{link}</a>}</main>; }

function TmdbPanel({ setNotice }) {
  const [query, setQuery] = useState(''); const [page, setPage] = useState(1);
  const [result, setResult] = useState(null); const [busy, setBusy] = useState(false); const [registering, setRegistering] = useState(null);
  const search = async (nextPage = 1) => { setBusy(true); setNotice(null); try { const response = await searchAdminTmdbMovies(query, nextPage); setResult(response.data); setPage(response.data.page); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  const register = async (movie) => { setRegistering(movie.tmdb_id); setNotice(null); try { const response = await registerAdminTmdbMovie(movie.tmdb_id); setNotice({ type: 'success', text: response.message }); setResult((previous) => ({ ...previous, movies: previous.movies.map((item) => item.tmdb_id === movie.tmdb_id ? { ...item, is_registered: true } : item) })); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setRegistering(null); } };
  return <section className="be2-panel"><div className="be2-panel-title"><div><small>GET /admin/tmdb-movies-search</small><h2>TMDB 영화 검색</h2></div></div>
    <form className="be2-search" onSubmit={(event) => { event.preventDefault(); search(1); }}><label htmlFor="tmdb-query">영화 제목</label><div><input id="tmdb-query" required minLength="1" maxLength="100" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="예: 해리포터" /><button className="primary" disabled={busy}>{busy ? '검색 중…' : '검색'}</button></div></form>
    {result && <><div className="be2-result-meta">검색 결과 {result.total_results}개 · {result.page}/{result.total_pages} 페이지</div><div className="be2-movie-results">{result.movies.map((movie) => <article key={movie.tmdb_id}>{movie.poster_path ? <img src={movie.poster_path} alt="" /> : <div className="be2-no-poster">NO IMAGE</div>}<div><small>TMDB #{movie.tmdb_id}</small><h3>{movie.title}</h3><p>{movie.original_title}</p><span>{movie.release_date || '개봉일 미상'} · 평점 {movie.vote_average ?? '—'}</span><p className="overview">{movie.overview || '줄거리 정보가 없습니다.'}</p><button className="primary" disabled={movie.is_registered || registering === movie.tmdb_id} onClick={() => register(movie)}>{movie.is_registered ? '등록됨' : registering === movie.tmdb_id ? '등록 중…' : '이 영화 등록'}</button></div></article>)}</div><div className="be2-pagination"><button disabled={page <= 1 || busy} onClick={() => search(page - 1)}>이전</button><span>{page} / {result.total_pages}</span><button disabled={page >= result.total_pages || busy} onClick={() => search(page + 1)}>다음</button></div></>}
  </section>;
}

function DirectMoviePanel({ setNotice }) {
  const [form, setForm] = useState(emptyMovie); const [busy, setBusy] = useState(false);
  const submit = async (event) => { event.preventDefault(); setBusy(true); setNotice(null); try { const response = await createAdminMovie(directMoviePayload(form)); setNotice({ type: 'success', text: `${response.message} (movie_id: ${response.data.movie_id})` }); setForm(emptyMovie); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  return <section className="be2-panel"><PanelTitle api="POST /admin/movie" title="영화 직접 등록" /><form className="be2-form" onSubmit={submit}><MovieFields form={form} setForm={setForm} /><div className="be2-actions"><button disabled={busy} className="primary">{busy ? '등록 중…' : '영화 등록'}</button><button type="button" onClick={() => setForm(emptyMovie)}>초기화</button></div></form></section>;
}

function EditMoviePanel({ setNotice }) {
  const [movieId, setMovieId] = useState(''); const [form, setForm] = useState(emptyMovie);
  const [included, setIncluded] = useState({}); const [cleared, setCleared] = useState({}); const [isTmdbMovie, setIsTmdbMovie] = useState(false); const [busy, setBusy] = useState(false);
  const toggle = (key) => setIncluded((current) => ({ ...current, [key]: !current[key] }));
  const submit = async (event) => { event.preventDefault(); const payload = editMoviePayload(form, included, cleared, isTmdbMovie); if (!Object.keys(payload).length) { setNotice({ type: 'error', text: '수정할 필드를 하나 이상 선택하세요.' }); return; } setBusy(true); setNotice(null); try { const response = await updateAdminMovie(movieId, payload); setNotice({ type: 'success', text: response.message }); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  const remove = async () => { if (!window.confirm(`내부 영화 #${movieId}을 삭제하시겠습니까? 관련 장르·통계·배우 연결 데이터도 함께 삭제됩니다.`)) return; setBusy(true); setNotice(null); try { const response = await deleteAdminMovie(movieId); setNotice({ type: 'success', text: response.message }); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  return <section className="be2-panel"><PanelTitle api="PATCH · DELETE /admin/movie/{movie_id}" title="영화 부분 수정·삭제" /><form className="be2-form be2-edit-form" onSubmit={submit}><label className="wide">내부 movie_id<input required type="number" min="1" value={movieId} onChange={(event) => setMovieId(event.target.value)} placeholder="tmdb_id가 아닌 movies.id" /></label><label className="wide be2-inline-check"><input type="checkbox" checked={isTmdbMovie} onChange={(event) => setIsTmdbMovie(event.target.checked)} /> TMDB로 등록한 영화입니다 (배우 수정 비활성화)</label>{editableFields.map((key) => <EditField key={key} fieldKey={key} form={form} setForm={setForm} included={included} cleared={cleared} setCleared={setCleared} toggle={toggle} disabled={key === 'cast' && isTmdbMovie} />)}<div className="be2-actions"><button disabled={busy} className="primary">{busy ? '처리 중…' : '선택한 필드 수정'}</button><button type="button" className="danger" disabled={busy || !movieId} onClick={remove}>영화 삭제</button></div></form></section>;
}

function EditField({ fieldKey, form, setForm, included, cleared, setCleared, toggle, disabled }) {
  const labels = { title: '제목', overview: '줄거리', genres: '장르', director: '감독', cast: '배우', keywords: '키워드', year: '연도', language: '언어', audience_count: '관객 수' };
  const canClear = fieldKey !== 'title';
  return <div className={`be2-edit-field ${['overview', 'genres', 'cast', 'keywords'].includes(fieldKey) ? 'wide' : ''}`}><label className="be2-inline-check"><input type="checkbox" checked={Boolean(included[fieldKey])} disabled={disabled} onChange={() => toggle(fieldKey)} /> {labels[fieldKey]} 변경</label><input disabled={!included[fieldKey] || cleared[fieldKey] || disabled} value={form[fieldKey]} onChange={(event) => setForm({ ...form, [fieldKey]: event.target.value })} placeholder={listFields.has(fieldKey) ? '쉼표로 구분; 빈 값은 [] 전송' : ''} />{canClear && <label className="be2-inline-check clear"><input type="checkbox" disabled={!included[fieldKey] || disabled} checked={Boolean(cleared[fieldKey])} onChange={(event) => setCleared((current) => ({ ...current, [fieldKey]: event.target.checked }))} /> {listFields.has(fieldKey) ? '전체 제거([])' : '값 제거(null)'}</label>}</div>;
}

function MovieFields({ form, setForm }) { const field = (key) => ({ value: form[key], onChange: (event) => setForm({ ...form, [key]: event.target.value }) }); return <><label>영화 제목<input {...field('title')} required minLength="1" maxLength="300" /></label><label>연도<input {...field('year')} type="number" min="1800" max="2100" /></label><label>감독<input {...field('director')} maxLength="200" /></label><label>언어<input {...field('language')} maxLength="10" placeholder="ko" /></label><label>관객 수<input {...field('audience_count')} type="number" min="0" /></label><label>장르<input {...field('genres')} placeholder="독립, 드라마 (최대 10개)" /></label><label className="wide">배우<input {...field('cast')} placeholder="배우 A, 배우 B (최대 30명)" /></label><label className="wide">키워드<input {...field('keywords')} placeholder="독립영화, 성장 (최대 30개)" /></label><label className="wide">줄거리<textarea {...field('overview')} maxLength="10000" rows="5" /></label></>; }
function PanelTitle({ api, title }) { return <div className="be2-panel-title"><div><small>{api}</small><h2>{title}</h2></div></div>; }

function AdminRolePanel({ setNotice }) {
  const [email, setEmail] = useState(''); const [isAdmin, setIsAdmin] = useState(true); const [busy, setBusy] = useState(false); const [result, setResult] = useState(null);
  const submit = async (event) => { event.preventDefault(); setBusy(true); setNotice(null); setResult(null); try { const response = await updateUserAdminRole(email, isAdmin); setResult(response.data); setNotice({ type: 'success', text: response.message }); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  return <section className="be2-panel"><PanelTitle api="PATCH /admin/users/admin-role" title="사용자 관리자 권한 변경" /><form className="be2-form be2-role-form" onSubmit={submit}><label className="wide">사용자 이메일<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="user@example.com" /></label><fieldset className="wide"><legend>변경할 권한</legend><label><input type="radio" name="admin-role" checked={isAdmin} onChange={() => setIsAdmin(true)} /> 관리자 권한 부여</label><label><input type="radio" name="admin-role" checked={!isAdmin} onChange={() => setIsAdmin(false)} /> 관리자 권한 회수</label></fieldset><p className="wide be2-role-warning">자신의 권한 회수, 존재하지 않는 사용자, 동일 권한 요청은 서버에서 거부됩니다.</p><div className="be2-actions"><button disabled={busy} className={isAdmin ? 'primary' : 'danger'}>{busy ? '처리 중…' : isAdmin ? '관리자 권한 부여' : '관리자 권한 회수'}</button></div></form>{result && <div className="be2-role-result"><strong>{result.nickname || result.email}</strong><span>{result.email}</span><b>{result.is_admin ? '관리자' : '일반 사용자'}</b></div>}</section>;
}
