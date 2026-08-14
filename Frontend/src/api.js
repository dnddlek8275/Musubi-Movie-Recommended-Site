import { getInternalMovieId } from './utils/movieIdentity.js';
import { optimizeImageUrl } from './utils/imagePerformance.js';

// 기본값은 동일 출처의 /api 프록시이며, 개발 환경에서는 Vite가 백엔드로 전달한다.
const BACKEND_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || '/api'
).replace(/\/+$/, '');

const LOCAL_PROFILE_KEY = 'cineverse.localProfile';
const LOCAL_PREFERENCES_KEY = 'cineverse.localPreferences';
const AUTH_SESSION_KEY = 'cineverse.authSession';

// AI/캐릭터 채팅에서 추천받은 영화를 마이페이지 추천과 잇기 위해 저장하는 키.
const RECOMMENDED_MOVIES_KEY = 'cineverse.recommendedMovies';
const MAX_RECOMMENDED_MOVIES = 30;

// 로그아웃/다른 사용자 로그인 시 비워야 하는, 브라우저에 남는 대화 로그/캐시 키.
const CHAT_CACHE_KEYS = [
  'cineverse.autochat.conversations', // 무 자동 대화 리스트
  'cineverse.groupchat.conversations', // 배우대기실 대화 리스트
  'cineverse.chat.rooms', // (구) 1:1 채팅방 매핑
  'cineverse.chat.partners', // (구) 대화 상대 목록
  'cineverse.chat.group.members', // (구) 그룹 멤버 목록
  RECOMMENDED_MOVIES_KEY, // 채팅에서 추천받은 영화 목록
];
const ACCOUNT_CACHE_KEYS = [LOCAL_PROFILE_KEY, LOCAL_PREFERENCES_KEY];
const memoryRequestCache = new Map();

function cachedRequest(key, ttlMs, signal, loader) {
  const now = Date.now();
  let entry = memoryRequestCache.get(key);
  if (entry?.value !== undefined && entry.expiresAt > now) return Promise.resolve(entry.value);

  if (!entry?.promise) {
    const promise = Promise.resolve()
      .then(loader)
      .then((value) => {
        memoryRequestCache.set(key, { value, expiresAt: Date.now() + ttlMs });
        return value;
      })
      .catch((error) => {
        memoryRequestCache.delete(key);
        throw error;
      });
    entry = { promise, expiresAt: 0 };
    memoryRequestCache.set(key, entry);
  }

  if (!signal) return entry.promise;
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    entry.promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

function accountCacheKey(name) {
  return `${name}:${localStorage.getItem(AUTH_SESSION_KEY) || 'guest'}`;
}

function clearMemoryRequestCache(prefix = '') {
  for (const key of memoryRequestCache.keys()) {
    if (!prefix || key.startsWith(prefix)) memoryRequestCache.delete(key);
  }
}

function clearChatCaches() {
  CHAT_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
}

function clearAccountCaches() {
  ACCOUNT_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
}

// 채팅 응답의 추천 영화들을 최근순으로 누적 저장한다(중복 제거, 최대 개수 제한).
export function addRecommendedMovies(movies) {
  if (!Array.isArray(movies) || movies.length === 0) return;

  const existing = readLocalJson(RECOMMENDED_MOVIES_KEY, []);
  const byKey = new Map();

  // 새로 추천된 영화가 앞으로 오도록 new → old 순서로 넣고, 먼저 들어온 것만 유지.
  [...movies, ...(Array.isArray(existing) ? existing : [])].forEach((movie) => {
    if (!movie) return;
    const key = String(movie.movie_id ?? movie.id ?? movie.title ?? movie.name ?? '');
    if (!key || byKey.has(key)) return;
    byKey.set(key, movie);
  });

  writeLocalJson(
    RECOMMENDED_MOVIES_KEY,
    Array.from(byKey.values()).slice(0, MAX_RECOMMENDED_MOVIES)
  );
}

export function getRecommendedMovies() {
  const stored = readLocalJson(RECOMMENDED_MOVIES_KEY, []);
  return Array.isArray(stored) ? stored : [];
}

const FALLBACK_GENRES = [
  '드라마',
  '코미디',
  '스릴러',
  '액션',
  '공포',
  '로맨스',
  '범죄',
  '모험',
  '애니메이션',
  'SF',
  '가족',
  'TV 영화',
  '판타지',
  '미스터리',
  '다큐멘터리',
  '음악',
  '서부',
  '역사',
  '전쟁',
];
const TMDB_IMAGE_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

export function resolveMovieImage(path, size = 'w500') {
  const value = String(path || '').trim();

  if (!value) return '';
  if (/^(https?:|data:|blob:)/i.test(value)) return optimizeImageUrl(value, size);

  return optimizeImageUrl(
    `${TMDB_IMAGE_BASE_URL}${value.startsWith('/') ? value : `/${value}`}`,
    size,
  );
}

function readLocalJson(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    console.error('로컬 데이터 파싱 실패:', error);
    return fallback;
  }
}

function writeLocalJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function getArrayPayload(data, ...keys) {
  if (Array.isArray(data)) return data;

  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
    if (Array.isArray(data?.data?.[key])) return data.data[key];
  }

  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function mergePreferenceValues(...values) {
  return Array.from(
    new Set(
      values
        .flatMap((value) => (Array.isArray(value) ? value : []))
        .map((value) => String(value || '').trim())
        .filter(Boolean)
    )
  );
}

export function getLocalPreferences() {
  const preferences = readLocalJson(LOCAL_PREFERENCES_KEY, {});
  return {
    genres: mergePreferenceValues(preferences?.genres),
    actors: mergePreferenceValues(preferences?.actors),
    keywords: mergePreferenceValues(preferences?.keywords),
  };
}

function getErrorMessage(data, fallbackMessage) {
  const validationMessage = Array.isArray(data?.detail)
    ? data.detail.map((item) => item?.msg).filter(Boolean).join(', ')
    : '';
  const detailMessage = typeof data?.detail === 'string' ? data.detail : '';

  return (
    data?.detail?.message ||
    data?.detail?.error ||
    data?.detail?.detail ||
    validationMessage ||
    detailMessage ||
    data?.message ||
    // 백엔드 응답 필드 오타(messaage/messsage) 대응 — 프론트는 message로 통일해서 읽는다.
    data?.messaage ||
    data?.messsage ||
    data?.error ||
    fallbackMessage
  );
}

// 일부 에러 응답은 state 대신 status로 오므로 둘 다 확인한다.
function getResponseState(data) {
  return data?.detail?.state ?? data?.detail?.status ?? data?.state ?? data?.status;
}

function isFailureResponse(data) {
  return ['failure', 'fail', 'error'].includes(getResponseState(data));
}

function clampNumber(value, min, max, fallback) {
  const number = Number(value);

  if (!Number.isFinite(number)) return fallback;

  return Math.min(max, Math.max(min, number));
}

let refreshPromise = null;

export async function fetchWithAuth(url, options = {}, allowRefreshRetry = true) {
  const token = localStorage.getItem('access_token');
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    // /auth, /chat, /user 응답은 캐시하지 않는다(백엔드 no-store 헤더와 맞춤). 호출부가 지정하면 그 값 우선.
    cache: 'no-store',
    credentials: 'include',
    ...options,
    headers,
  });

  // 명세의 ACCESS_TOKEN_EXPIRED인 401에서만 재발급 후 원 요청을 1회 재시도한다.
  if (response.status === 401 && token) {
    const errorBody = await response.clone().json().catch(() => null);
    const errorCode = errorBody?.detail?.code ?? errorBody?.code;

    if (errorCode !== 'ACCESS_TOKEN_EXPIRED' || !allowRefreshRetry) {
      if (
        [
          'INVALID_ACCESS_TOKEN',
          'INVALID_TOKEN_TYPE',
          'INVALID_TOKEN_PAYLOAD',
          'INVALID_AUTH_SCHEME',
        ].includes(errorCode)
      ) {
        // 무효 토큰(재발급 대상 아님) → 자동 로그아웃.
        handleSessionExpired();
      }
      return response;
    }

    try {
      await refreshAccessToken();
    } catch (refreshError) {
      // 만료 토큰인데 재발급까지 실패 → 자동 로그아웃(handleSessionExpired가 이미 정리·이동).
      return response;
    }

    return fetchWithAuth(url, options, false);
  }

  return response;
}

// 브라우저에서 녹음한 음성을 텍스트로 변환한다.
// FormData boundary는 브라우저가 생성해야 하므로 Content-Type을 지정하지 않는다.
export async function transcribeAudio(audioBlob, signal) {
  if (!(audioBlob instanceof Blob) || audioBlob.size === 0) {
    throw new Error('녹음된 음성이 없습니다. 다시 녹음해주세요.');
  }
  if (audioBlob.size > 20 * 1024 * 1024) {
    throw new Error('음성 파일은 최대 20MB까지 업로드할 수 있습니다.');
  }

  const mimeType = String(audioBlob.type || 'audio/webm').split(';')[0];
  const extensions = {
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
    'audio/mpeg': 'mp3',
    'audio/mp4': 'm4a',
    'audio/x-m4a': 'm4a',
    'audio/ogg': 'ogg',
    'audio/webm': 'webm',
  };
  const formData = new FormData();
  // STT 계약상 audio 외에 room_id, character, 캐릭터 목록은 보내지 않는다.
  // 캐릭터명·별칭·조사·문장부호 보정은 백엔드가 처리한다.
  formData.append('audio', audioBlob, `recording.${extensions[mimeType] || 'webm'}`);

  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/audio/transcribe`, {
    method: 'POST',
    body: formData,
    signal,
  });
  const data = await response.json().catch(() => null);
  const safeMessage =
    data?.detail?.message || data?.message || '음성 변환 요청에 실패했습니다.';

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(safeMessage);
  }

  // 바깥쪽 공백만 정리하고 백엔드가 보정한 쉼표와 문장 부호는 그대로 유지한다.
  const text = String(data?.data?.text || '').trim();
  if (!text) throw new Error('음성에서 대화 내용을 인식하지 못했습니다.');
  return text;
}

async function performAccessTokenRefresh() {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    handleSessionExpired();
    throw new Error(getErrorMessage(data, `토큰 재발급 실패 (${response.status})`));
  }

  const authData = data?.data || {};

  if (!authData.access_token) {
    handleSessionExpired();
    throw new Error('토큰 재발급 응답에 access_token이 없습니다.');
  }

  localStorage.setItem('access_token', authData.access_token);

  const storedUser = getStoredAuthUser() || {};
  const user = {
    ...storedUser,
    email: authData.email || storedUser.email || '',
    nickname:
      authData.nickname ||
      storedUser.nickname ||
      authData.email ||
      storedUser.email ||
      '',
    tokenType: authData.token_type || storedUser.tokenType || 'bearer',
  };

  localStorage.setItem('auth_user', JSON.stringify(user));

  scheduleAutoLogout();

  return user;
}

// 동시에 여러 요청이 만료되어도 refresh 요청은 하나만 수행한다.
export async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = performAccessTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

export function getStoredAuthUser() {
  try {
    const rawUser = localStorage.getItem('auth_user');

    if (!rawUser) return null;

    const user = JSON.parse(rawUser);
    const tokenPayload = decodeJwtPayload(localStorage.getItem('access_token'));
    const role = tokenPayload?.role || tokenPayload?.authority || tokenPayload?.user_role;
    return role ? { ...user, role } : user;
  } catch (error) {
    console.error('저장된 로그인 정보 파싱 실패:', error);
    return null;
  }
}

export function clearStoredAuth() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem(AUTH_SESSION_KEY);
  // 로그아웃 시 브라우저에 남는 대화 로그/캐시도 함께 삭제한다.
  clearChatCaches();
  clearAccountCaches();
  clearMemoryRequestCache();
}

// 이미 로그인/회원가입/비밀번호 관련 화면이면 리다이렉트하지 않는다(루프 방지).
function redirectToLogin() {
  if (typeof window === 'undefined') return;

  const path = window.location.pathname || '';
  const skip = ['/login', '/signup', '/reset-password', '/password-reset'];
  if (skip.some((prefix) => path.startsWith(prefix))) return;

  window.location.href = '/login';
}

// 토큰 만료(재발급 실패) 또는 무효 토큰 → 자동 로그아웃: 세션 정리 후 로그인 화면으로 이동.
function handleSessionExpired() {
  clearStoredAuth();
  redirectToLogin();
}

// JWT payload에서 만료 시각(exp, 초)을 읽는다.
function decodeJwtPayload(token) {
  try {
    const part = String(token || '').split('.')[1];
    if (!part) return null;

    let base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padding = base64.length % 4;
    if (padding) base64 += '='.repeat(4 - padding);

    return JSON.parse(atob(base64));
  } catch (error) {
    return null;
  }
}

function decodeJwtExp(token) {
  const payload = decodeJwtPayload(token);
  return typeof payload?.exp === 'number' ? payload.exp : null;
}

let autoLogoutTimer = null;

// 액세스 토큰 만료 시각에 맞춰, 만료 직전 재발급을 시도하고 실패하면 즉시 자동 로그아웃한다.
// (아무 동작을 하지 않아도 만료 시점에 로그아웃되도록 하는 프로액티브 처리)
export function scheduleAutoLogout() {
  if (typeof window === 'undefined') return;

  if (autoLogoutTimer) {
    clearTimeout(autoLogoutTimer);
    autoLogoutTimer = null;
  }

  const token = localStorage.getItem('access_token');
  if (!token) return;

  const exp = decodeJwtExp(token);
  if (!exp) return;

  const run = async () => {
    try {
      // 만료 직전 재발급 성공 → 새 토큰 기준으로 다시 예약(세션 유지).
      await refreshAccessToken();
      scheduleAutoLogout();
    } catch (error) {
      // 재발급 실패(HTTP 실패/네트워크 오류 등 무엇이든) → 자동 로그아웃.
      handleSessionExpired();
    }
  };

  // 만료 5초 전에 재발급을 시도한다(네트워크 지연 여유). 이미 지났으면 즉시 실행.
  const delay = exp * 1000 - Date.now() - 5000;
  if (delay <= 0) {
    run();
    return;
  }

  // setTimeout 최대 지연(약 24.8일)을 넘지 않도록 클램프.
  autoLogoutTimer = setTimeout(run, Math.min(delay, 2_000_000_000));
}

function storeAuthSession({ accessToken, email, nickname, tokenType, onboardingCompleted }) {
  // 다른 사용자가 로그인하면 이전 사용자의 로컬 대화 캐시를 비운다(이전 채팅 노출 방지).
  const previousUser = getStoredAuthUser();
  if (!previousUser || previousUser.email !== email) {
    clearChatCaches();
    clearAccountCaches();
  }

  const user = {
    email,
    nickname: nickname || email,
    tokenType: tokenType || 'bearer',
    onboardingCompleted: Boolean(onboardingCompleted),
  };

  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('auth_user', JSON.stringify(user));
  localStorage.setItem(AUTH_SESSION_KEY, crypto.randomUUID());

  scheduleAutoLogout();

  return user;
}

export async function loginWithEmail({ email, password }, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `로그인 실패 (${response.status})`));
  }

  const authData = data?.data || {};

  if (!authData.access_token) {
    throw new Error('로그인 응답에 access_token이 없습니다.');
  }

  return storeAuthSession({
    accessToken: authData.access_token,
    email: authData.email || email,
    nickname: authData.nickname || authData.email || email,
    tokenType: authData.token_type,
    onboardingCompleted: authData.onboarding_completed,
  });
}

export async function requestEmailVerification(email, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/email-verification/request`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `인증번호 전송 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function confirmEmailVerification(email, verificationCode, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/email-verification/confirm`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, verification_code: verificationCode }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `이메일 인증 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function checkNicknameAvailability(nickname, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/nickname-check`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `닉네임 중복 확인 실패 (${response.status})`));
  }

  return {
    available: Boolean(data?.data?.available),
    message: data?.message || '',
  };
}

export async function registerWithEmail(
  { email, password, nickname, verificationCode, verification_code },
  signal
) {
  const code = verificationCode ?? verification_code;
  const response = await fetch(`${BACKEND_BASE_URL}/auth/register`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      nickname,
      verification_code: code,
    }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `회원가입 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function requestPasswordReset(email, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/password-reset/request`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `비밀번호 재설정 요청 실패 (${response.status})`));
  }

  return data || {};
}

export async function confirmPasswordReset(token, newPassword, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/password-reset/confirm`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `비밀번호 변경 실패 (${response.status})`));
  }

  return data || {};
}

export async function logoutUser(signal) {
  try {
    const response = await fetchWithAuth(`${BACKEND_BASE_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      signal,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok || getResponseState(data) !== 'success') {
      throw new Error(getErrorMessage(data, `로그아웃 실패 (${response.status})`));
    }

    return data;
  } finally {
    // 서버 로그아웃 성공 여부와 무관하게 프론트 access token과 사용자 캐시는 제거한다.
    clearStoredAuth();
  }
}

export async function checkBackendHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `백엔드 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkApiStatus(signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/`, {
    credentials: 'include',
    cache: 'no-store',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `API 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkAiHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/ai-health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `AI 서버 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkDbHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/db-test`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `DB 연결 실패 (${response.status})`));
  }

  return data;
}

function normalizeChatResponse(json, request) {
  const payload = json?.state === 'success' && json?.data ? json.data : json || {};
  const roomId = payload.room_id ?? payload.roomId ?? payload.conversationId;
  // 백엔드 응답 키가 rounds/rouds/roud 로 제각각이라 모두 확인한다(실제 응답은 roud 사용).
  const rounds = payload.rounds ?? payload.rouds ?? payload.roud ?? [];
  const movies = payload.movies ?? payload.movie ?? payload.recommended_movies ?? [];
  const sources = payload.sources ?? payload.web_sources ?? [];

  return {
    conversationId:
      roomId === undefined || roomId === null ? '' : String(roomId),
    answer:
      payload.answer ||
      payload.message?.content ||
      payload.content ||
      '',
    character: payload.character || request.character,
    intent: payload.intent || payload.meta?.intent || 'character_chat',
    emotion: payload.emotion || payload.meta?.emotion || 'default',
    rounds: Array.isArray(rounds) ? rounds : [],
    movies: Array.isArray(movies) ? movies : [],
    sources: Array.isArray(sources) ? sources : [],
    webSearchQuota: payload.web_search_quota || payload.webSearchQuota || {},
    guestRemaining: payload.guest_remaining,
    saved: payload.saved,
    raw: json,
  };
}

const RECOVERY_LOADING_MIN_MS = 600;

function waitWithSignal(delayMs, signal) {
  if (delayMs <= 0) return Promise.resolve();

  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('응답 대기가 중단되었습니다.', 'AbortError'));
      return;
    }

    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, delayMs);
    const abort = () => {
      window.clearTimeout(timer);
      reject(new DOMException('응답 대기가 중단되었습니다.', 'AbortError'));
    };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

async function keepRecoveryLoadingVisible(startedAt, intent, signal) {
  if (intent !== 'input_recovery') return;
  const remaining = RECOVERY_LOADING_MIN_MS - (Date.now() - startedAt);
  await waitWithSignal(remaining, signal);
}

export async function fetchCharacterGreeting(character, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/greeting`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ character }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `캐릭터 첫인사 요청 실패 (${response.status})`));
  }

  const payload = data?.state === 'success' && data?.data ? data.data : data || {};
  return {
    answer: String(payload.answer || '').trim(),
    character: payload.character || character,
    emotion: payload.emotion || 'default',
  };
}

export async function sendChat(request, signal, onChunk) {
  const requestStartedAt = Date.now();
  const isGroup = request.mode === 'group';
  const isAuto = !isGroup && !request.character;

  if (!isGroup && !isAuto) {
    return sendCharacterChatStream(request, signal, onChunk);
  }

  let url = `${BACKEND_BASE_URL}/chat`;
  let body = {
    message: request.message,
    character: request.character ?? null,
    history: request.history || [],
  };

  if (isGroup) {
    url = `${BACKEND_BASE_URL}/chat/group`;
    body = {
      characters: request.characters,
      message: request.message,
      history: request.history || [],
    };
  } else if (isAuto) {
    url = `${BACKEND_BASE_URL}/chat/auto`;
    body = {
      message: request.message,
      character: request.character ?? null,
      history: request.history || [],
    };
  }

  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `채팅 요청 실패 (${response.status})`));
  }

  const normalized = normalizeChatResponse(data, request);
  await keepRecoveryLoadingVisible(requestStartedAt, normalized.intent, signal);
  return normalized;
}

export async function generateChatTitle(message, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `대화 제목 생성 실패 (${response.status})`));
  }

  return String(data?.data?.title || '').trim();
}

function getStreamText(payload) {
  if (typeof payload === 'string') return payload;

  return (
    payload?.delta ??
    payload?.token ??
    payload?.text ??
    payload?.answer ??
    payload?.content ??
    payload?.message?.content ??
    payload?.data?.delta ??
    payload?.data?.token ??
    payload?.data?.text ??
    payload?.data?.answer ??
    payload?.data?.content ??
    ''
  );
}

function parseStreamPayload(raw) {
  try {
    return JSON.parse(raw);
  } catch (error) {
    return raw;
  }
}

// POST /chat과 POST /chat/rooms/{id}/messages는 성공 시 SSE, 실패 시 JSON을 반환한다.
export async function sendCharacterChatStream(request, signal, onChunk) {
  const requestStartedAt = Date.now();
  const isExistingRoom = request.roomId !== undefined && request.roomId !== null && request.roomId !== '';
  const url = isExistingRoom
    ? `${BACKEND_BASE_URL}/chat/rooms/${request.roomId}/messages`
    : `${BACKEND_BASE_URL}/chat`;
  const body = isExistingRoom
    ? {
        content: request.message,
        character: request.character ?? null,
      }
    : {
        message: request.message,
        character: request.character,
        history: request.history || [],
      };
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream, application/json',
    },
    body: JSON.stringify(body),
    signal,
  });

  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const data = await response.json().catch(() => null);

    if (!response.ok || isFailureResponse(data)) {
      throw new Error(getErrorMessage(data, `스트림 채팅 요청 실패 (${response.status})`));
    }

    const normalized = normalizeChatResponse(data, request);
    await keepRecoveryLoadingVisible(requestStartedAt, normalized.intent, signal);
    return normalized;
  }

  if (!response.ok) {
    const message = await response.text().catch(() => '');
    throw new Error(message || `스트림 채팅 요청 실패 (${response.status})`);
  }

  if (!response.body) {
    throw new Error('채팅 스트림 본문이 없습니다.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let finalPayload = null;

  const consumeEvent = (rawEvent) => {
    const dataLines = rawEvent
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim());

    for (const raw of dataLines) {
      if (!raw) continue;
      if (raw === '[DONE]') return true;

      const payload = parseStreamPayload(raw);
      if (isFailureResponse(payload)) {
        throw new Error(getErrorMessage(payload, 'AI 스트리밍 응답에 실패했습니다.'));
      }
      finalPayload = payload;
      const chunk = String(getStreamText(payload) || '');
      if (!chunk) continue;

      // AI 서버가 누적 답변을 보내는 경우와 토큰만 보내는 경우를 모두 지원한다.
      answer = chunk.startsWith(answer) ? chunk : answer + chunk;
      if (payload?.intent !== 'input_recovery') {
        onChunk?.(answer, payload);
      }
    }

    return false;
  };

  let streamDone = false;
  while (true) {
    // eslint-disable-next-line no-await-in-loop
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || '';

    for (const event of events) {
      if (consumeEvent(event)) {
        streamDone = true;
        break;
      }
    }

    if (streamDone || done) break;
  }

  if (!streamDone && buffer.trim()) consumeEvent(buffer);

  const normalized = normalizeChatResponse(finalPayload, request);
  await keepRecoveryLoadingVisible(requestStartedAt, normalized.intent, signal);
  if (normalized.intent === 'input_recovery' && answer) {
    onChunk?.(answer, finalPayload);
  }
  let conversationId = normalized.conversationId;

  // 신규 1:1 SSE에는 room_id가 없으므로 종료 후 최신 캐릭터 방을 다시 조회한다.
  if (!request.guest && !isExistingRoom && !conversationId) {
    try {
      const rooms = await fetchChatRooms(signal);
      const latestRoom = rooms.find(
        (room) =>
          room?.room_type === 'character' &&
          room?.characters?.some((name) => name === request.character)
      ) || rooms.find((room) => room?.room_type === 'character');
      conversationId =
        latestRoom?.room_id === undefined || latestRoom?.room_id === null
          ? ''
          : String(latestRoom.room_id);
    } catch (error) {
      // 방 ID 보조 조회가 실패해도 이미 완료된 스트림 답변은 유지한다.
    }
  }

  return {
    ...normalized,
    conversationId,
    answer: answer || normalized.answer,
  };
}

export async function sendRoomMessage(roomId, request, signal, onChunk) {
  return sendCharacterChatStream(
    { ...request, roomId, character: request.character ?? null },
    signal,
    onChunk
  );
}

export async function fetchChatRoomMessages(roomId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms/${roomId}/messages`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `채팅 메시지 목록 요청 실패 (${response.status})`));
  }

  return data?.data || [];
}

export async function resolveChatMovieId(movie, signal) {
  const explicitMovieId = Number(movie?.movie_id);
  if (Number.isInteger(explicitMovieId) && explicitMovieId > 0) return explicitMovieId;

  const params = new URLSearchParams();
  const tmdbId = Number(movie?.tmdb_id);
  const title = String(movie?.title || movie?.name || movie?.movie || '').trim();
  const year = Number(movie?.year);

  if (Number.isInteger(tmdbId) && tmdbId > 0) params.set('tmdb_id', String(tmdbId));
  if (title) params.set('title', title);
  if (Number.isInteger(year) && year >= 1880 && year <= 2200) params.set('year', String(year));
  if (!params.size) throw new Error('영화 식별 정보가 없습니다.');

  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/resolve?${params}`, { signal });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, '영화 상세 정보를 찾지 못했습니다.'));
  }

  const resolvedId = Number(data?.data?.movie_id);
  if (!Number.isInteger(resolvedId) || resolvedId <= 0) {
    throw new Error('영화 상세 정보를 찾지 못했습니다.');
  }
  return resolvedId;
}

export async function fetchChatRooms(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `대화 목록 요청 실패 (${response.status})`));
  }

  // 방이 없으면(failure) 빈 목록. 성공이면 data 배열을 그대로 사용한다.
  if (getResponseState(data) === 'failure' || getResponseState(data) === 'fail') {
    return [];
  }

  return getArrayPayload(data, 'rooms');
}

export async function updateChatRoomTitle(roomId, title, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms/${roomId}/title`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `대화 제목 저장 실패 (${response.status})`));
  }

  return data?.data || {};
}

// 채팅방 삭제 (DELETE /chat/rooms/{room_id}) — 인증 필요, 본인 방만.
export async function deleteChatRoom(roomId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/chat/rooms/${roomId}`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'fail' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `채팅방 삭제 실패 (${response.status})`));
  }

  return data || {};
}

async function loadCharacters() {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/characters`);
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `캐릭터 목록 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'characters')
    .map((character) => ({
      ...character,
      image:
        character.image ||
        character.image_url ||
        character.profile_image ||
        character.avatar_url ||
        '',
      image_url:
        character.image_url ||
        character.profile_image ||
        character.image ||
        character.avatar_url ||
        '',
    }));
}

export function fetchCharacters(signal) {
  return cachedRequest('characters', 5 * 60 * 1000, signal, loadCharacters);
}

// 캐릭터 단건 조회 (GET /chatcharacter/{character_name}) — 인증 없음.
// 라우터 prefix와 앞쪽 슬래시가 없는 하위 경로가 붙은 실제 OpenAPI 경로를 사용한다.
// 응답 data: { id, name, profile_image }
export async function fetchCharacter(characterName, signal) {
  const response = await fetch(
    `${BACKEND_BASE_URL}/chatcharacter/${encodeURIComponent(characterName)}`,
    { signal, cache: 'no-store' }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `캐릭터 정보 조회 실패 (${response.status})`));
  }

  const character = data?.data || {};
  return {
    id: character.id === undefined || character.id === null ? '' : String(character.id),
    name: character.name || characterName,
    image: character.profile_image || '',
    image_url: character.profile_image || '',
  };
}

// 배우 목록 조회 API (GET /movies/actors).
// 명세서: { state, message, data: [{ actor_id, actor_name, profile_path }] }
export async function fetchActors(signal, { query = '', page = 1, limit = 50, onboarding = false } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });
  const normalizedQuery = String(query || '').trim();
  if (normalizedQuery) params.set('q', normalizedQuery);
  if (onboarding && !normalizedQuery) params.set('onboarding', 'true');

  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/actors?${params.toString()}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, `배우 목록 요청 실패 (${response.status})`));
  }

  // 서버 에러(state: 'error')는 실패로 처리하고, 배우가 없는 경우(failure)는 빈 목록으로 본다.
  if (getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, '배우 조회 API 에러'));
  }

  return getArrayPayload(data, 'actors').map((actor) => {
    const path = actor?.profile_path || '';
    const image = path
      ? path.startsWith('http')
        ? path
        : resolveMovieImage(path)
      : '';

    return {
      id: String(actor?.actor_id ?? actor?.id ?? actor?.actor_name ?? ''),
      name: actor?.actor_name || actor?.name || '',
      image_url: image,
      profile_path: path,
    };
  });
}

// 선호 배우 저장 (POST /movies/actor/{actor_id}) — 인증 필요.
// 응답 data: { user_email, user_preferred_actors: [이름들] }
export async function savePreferredActor(actorId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/actor/${actorId}`,
    { method: 'POST', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `선호 배우 저장 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function fetchGenres(signal) {
  try {
    const movies = await fetchMovies(signal);
    const names = movies.flatMap((movie) => {
      if (Array.isArray(movie.genres)) return movie.genres;
      return String(movie.genres || movie.genre || '')
        .split(',')
        .map((genre) => genre.trim())
        .filter(Boolean);
    });

    // 장르 카드는 한 줄(5개)까지만 노출한다. 그 이상은 박스가 넘쳐서 잘린다.
    const uniqueNames = Array.from(new Set(names)).slice(0, 5);
    const genreNames = uniqueNames.length > 0 ? uniqueNames : FALLBACK_GENRES.slice(0, 5);

    return genreNames.map((name, index) => ({
      name,
      tone: (index % 8) + 1,
    }));
  } catch (error) {
    if (error.name === 'AbortError') throw error;

    return FALLBACK_GENRES.slice(0, 5).map((name, index) => ({
      name,
      tone: (index % 8) + 1,
    }));
  }
}

export async function getRecommendMovies(limit = 12, signal, preferences = null) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 30, 12)),
  });
  const hasPreferences = preferences && ['genres', 'actors', 'keywords']
    .some((key) => Array.isArray(preferences[key]) && preferences[key].length > 0);
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/recommend?${params}`, {
    method: 'POST',
    headers: hasPreferences ? { 'Content-Type': 'application/json' } : undefined,
    body: hasPreferences ? JSON.stringify(preferences) : undefined,
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.state === 'error') {
    throw new Error(getErrorMessage(data, `추천 영화 요청 실패 (${response.status})`));
  }

  if (data?.state === 'failure') {
    return {
      ...data,
      data: [],
    };
  }

  return data || { state: 'success', message: '', data: [] };
}

export async function fetchRecommendedMovies(signal, limit = 12, preferences = null) {
  const data = await getRecommendMovies(limit, signal, preferences);

  return data?.state === 'success' ? getArrayPayload(data) : [];
}

export async function fetchMovies(
  signal,
  keyword = '',
  { page = 1, limit, preferences = null, searchType = '' } = {},
) {
  const searchKeyword = String(keyword ?? '').trim();

  if (!searchKeyword) {
    return fetchRecommendedMovies(signal, limit ?? 12, preferences);
  }

  const params = new URLSearchParams({
    keyword: searchKeyword,
    page: String(clampNumber(page, 1, Number.MAX_SAFE_INTEGER, 1)),
    limit: String(clampNumber(limit, 1, 100, 80)),
  });
  if (searchType) params.set('type', searchType);
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/search?${params}`, {
    method: 'GET',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (getResponseState(data) === 'failure') {
    return [];
  }

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `영화 목록 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies', 'results', 'items');
}

export async function fetchSearchSections(
  signal,
  keyword,
  { limit = 20, searchType = '', category = '', page = 1, excludeIds = [] } = {},
) {
  const searchKeyword = String(keyword ?? '').trim();
  if (!searchKeyword) return [];

  const params = new URLSearchParams({
    keyword: searchKeyword,
    limit: String(clampNumber(limit, 1, 40, 20)),
    page: String(Math.max(Number(page) || 1, 1)),
  });
  if (searchType) params.set('type', searchType);
  if (category) params.set('category', category);
  excludeIds.forEach((id) => {
    const numericId = Number(id);
    if (Number.isInteger(numericId) && numericId > 0) params.append('exclude_ids', String(numericId));
  });
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/search/grouped?${params}`, {
    method: 'GET',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (getResponseState(data) === 'failure') return [];
  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `카테고리별 영화 검색 요청 실패 (${response.status})`));
  }

  const sections = data?.data?.sections || data?.sections || [];
  return Array.isArray(sections)
    ? sections.filter((section) => Array.isArray(section?.movies) && section.movies.length > 0)
    : [];
}

export async function fetchSearchSuggestions(signal, keyword, limit = 8) {
  const searchKeyword = String(keyword ?? '').trim();
  if (!searchKeyword) return [];

  const params = new URLSearchParams({
    keyword: searchKeyword,
    limit: String(clampNumber(limit, 1, 12, 8)),
  });
  const response = await fetch(`${BACKEND_BASE_URL}/movies/search/suggestions?${params}`, {
    method: 'GET',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `검색어 자동완성 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'suggestions', 'results', 'items')
    .map((item) => (typeof item === 'string' ? { text: item, type: '' } : item))
    .filter((item) => item?.text);
}

export async function fetchMovieRanking(signal, limit = 10) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 100, 10)),
  });
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/ranking?${params}`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `실시간 랭킹 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'rankings').map((movie, index) => ({
    ...movie,
    id: getInternalMovieId(movie),
    rank: index + 1,
    genre: Array.isArray(movie.genres)
      ? movie.genres.join(', ')
      : movie.genre || movie.genres || '',
    rating: movie.vote_average ?? movie.rating ?? movie.ranking_score ?? '',
    rankChange: Number.isFinite(Number(movie.rank_change)) && movie.rank_change !== null
      ? Number(movie.rank_change)
      : null,
    isNew: Boolean(movie.is_new),
  }));
}

export async function fetchDiscoverySections(signal, preferences = null, limit = 25) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 25, 25)),
  });
  const hasPreferences = preferences && ['genres', 'actors', 'keywords']
    .some((key) => Array.isArray(preferences[key]) && preferences[key].length > 0);
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/discovery-sections?${params}`,
    {
      method: 'POST',
      headers: hasPreferences ? { 'Content-Type': 'application/json' } : undefined,
      body: hasPreferences ? JSON.stringify(preferences) : undefined,
      signal,
    }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `영화 탐색 섹션 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'sections');
}

// 영화 상세 조회 (GET /movies/{movie_id}?source=direct).
// 로그인 상태면 조회 이력이 저장되어 "최근 본 영화"에 반영된다. source='search'면 검색 클릭으로 기록.
export async function fetchMovieDetail(movieId, source = 'direct', signal) {
  const params = new URLSearchParams({ source: source || 'direct' });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/${movieId}?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `영화 상세 조회 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function fetchPersonFilmography(role, identifier, signal) {
  const normalizedRole = role === 'director' ? 'director' : 'actor';
  const normalizedIdentifier = String(identifier || '').trim();
  if (!normalizedIdentifier) throw new Error('인물 정보가 올바르지 않습니다.');

  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/people/${normalizedRole}/${encodeURIComponent(normalizedIdentifier)}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `필모그래피 조회 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function togglePersonLike(role, identifier, signal) {
  const normalizedRole = role === 'director' ? 'director' : 'actor';
  const normalizedIdentifier = String(identifier || '').trim();
  if (!normalizedIdentifier) throw new Error('인물 정보가 올바르지 않습니다.');

  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/people/${normalizedRole}/${encodeURIComponent(normalizedIdentifier)}/like`,
    { method: 'POST', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `인물 좋아요 요청 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function fetchSimilarMovies(movieId, signal, limit = 6) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 6, 6)),
  });
  const response = await fetch(
    `${BACKEND_BASE_URL}/movies/${movieId}/similar?${params}`,
    { credentials: 'include', cache: 'no-store', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `유사 영화를 불러오지 못했습니다. (${response.status})`));
  }

  return getArrayPayload(data, 'movies');
}

export async function rateMovie(
  movieId,
  score,
  comment = '',
  {
    expectedMovieId = movieId,
    expectedTmdbId = null,
    expectedTitle = '',
    isSpoiler = false,
    signal,
  } = {}
) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/rating`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      score: Math.round(clampNumber(score, 0.5, 5, 0.5) * 2) / 2,
      comment,
      is_spoiler: Boolean(isSpoiler),
      expected_movie_id: expectedMovieId,
      expected_tmdb_id: expectedTmdbId,
      expected_title: expectedTitle || null,
    }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `영화 평가 저장 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function deleteMovieRating(
  movieId,
  {
    expectedMovieId = movieId,
    expectedTmdbId = null,
    expectedTitle = '',
    signal,
  } = {}
) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/rating`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      expected_movie_id: expectedMovieId,
      expected_tmdb_id: expectedTmdbId,
      expected_title: expectedTitle || null,
    }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `영화 평가 삭제 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function fetchMoviesByGenre(
  genre,
  signal,
  { page = 1, limit = 20, sort = 'relevance' } = {}
) {
  const params = new URLSearchParams({
    page: String(clampNumber(page, 1, Number.MAX_SAFE_INTEGER, 1)),
    limit: String(clampNumber(limit, 1, 50, 20)),
    sort: sort === 'latest' ? 'latest' : 'relevance',
  });
  const response = await fetch(
    `${BACKEND_BASE_URL}/movies/genre/${encodeURIComponent(genre)}?${params}`,
    { credentials: 'include', cache: 'no-store', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `장르별 영화 조회 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies');
}

export async function fetchMoviesByCountry(
  countryCode,
  signal,
  { page = 1, limit = 20 } = {}
) {
  const params = new URLSearchParams({
    page: String(clampNumber(page, 1, Number.MAX_SAFE_INTEGER, 1)),
    limit: String(clampNumber(limit, 1, 50, 20)),
  });
  const response = await fetch(
    `${BACKEND_BASE_URL}/movies/country/${encodeURIComponent(countryCode)}?${params}`,
    { credentials: 'include', cache: 'no-store', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `제작국가별 영화 조회 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies');
}

export async function requestAiMovieRecommendation(
  { userId, user_id, prompt = null, genres = [] },
  signal
) {
  const response = await fetch(`${BACKEND_BASE_URL}/movies/ai-recommend`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId ?? user_id,
      prompt,
      genres,
    }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `AI 영화 추천 실패 (${response.status})`));
  }

  return data?.data || {};
}


function toLikedMoviePayload(movie) {
  return {
    title: movie.title,
    genre: movie.genre || '',
    rating: movie.rating || '',
  };
}

async function requestLikedMovie(method, movie) {
  const movieId = movie?.movie_id ?? movie?.id;

  if (movieId !== undefined && movieId !== null) {
    return likeMovie(movieId);
  }

  throw new Error(`${toLikedMoviePayload(movie).title || '영화'}는 서버 movie_id가 없어 좋아요를 변경할 수 없습니다.`);
}

export function addLikedMovie(movie) {
  return requestLikedMovie('POST', movie);
}

export function removeLikedMovie(movie, signal) {
  const movieId = movie?.movie_id ?? movie?.id;

  if (movieId === undefined || movieId === null) {
    throw new Error(
      `${toLikedMoviePayload(movie).title || '영화'}는 서버 movie_id가 없어 좋아요를 삭제할 수 없습니다.`
    );
  }

  return deleteLikedMovie(movieId, signal);
}

// 좋아요 누른 영화 삭제 (DELETE /user/movie-like/{movie_id}) — 인증 필요.
// failure(이미 삭제됨)는 UI만 동기화하면 되므로 성공처럼 취급, error/네트워크 오류만 던진다.
export async function deleteLikedMovie(movieId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/movie-like/${movieId}`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `좋아요 삭제 실패 (${response.status})`));
  }

  return data || {};
}

// 선호값(장르/배우/키워드) 하나 삭제 (DELETE /user/preference/delete, body 사용) — 인증 필요.
// 응답 data의 preferred_* 배열을 { genres, actors, keywords } 로 정리해서 돌려준다.
export async function deletePreference(preferenceType, preferenceValue, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/preference/delete`,
    {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        preference_type: preferenceType,
        preference_value: preferenceValue,
      }),
      signal,
    }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `선호값 삭제 실패 (${response.status})`));
  }

  const result = data?.data || {};
  return {
    genres: result.preferred_genres || [],
    actors: result.preferred_actors || [],
    keywords: result.preferred_keywords || [],
  };
}

// 취향 종류 전체 삭제 (DELETE /user/preferences/{preference_type}) — 인증 필요.
// 서버 삭제 후 로컬 병합 데이터에서도 같은 종류를 제거해 이전 값이 다시 보이지 않게 한다.
export async function deletePreferenceType(preferenceType, signal) {
  const categoryMap = {
    genre: 'genres',
    actor: 'actors',
    keyword: 'keywords',
  };
  const category = categoryMap[preferenceType];

  if (!category) {
    throw new Error('허용되지 않는 취향 타입입니다.');
  }

  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/preferences/${encodeURIComponent(preferenceType)}`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  // 비즈니스 실패도 HTTP 200으로 올 수 있으므로 state가 success인지 반드시 확인한다.
  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `취향 전체 삭제 실패 (${response.status})`));
  }

  const localPreferences = readLocalJson(LOCAL_PREFERENCES_KEY, {});
  const nextLocalPreferences = {
    ...(localPreferences || {}),
    [category]: [],
  };

  writeLocalJson(LOCAL_PREFERENCES_KEY, nextLocalPreferences);

  return data || {};
}


export async function likeMovie(movieId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/like`, {
    method: 'POST',
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `좋아요 요청 실패 (${response.status})`));
  }

  return data;
}

async function loadUserPreferences() {
  const localPreferences = readLocalJson(LOCAL_PREFERENCES_KEY, null);
  // 실제 경로는 /user/preferences (기존 /users/me/preferences 아님)
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/preferences`);

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(
      getErrorMessage(data, `취향 정보 요청 실패 (${response.status})`)
    );
  }

  // 명세의 explicit_preferences를 현재 UI가 쓰는 preferences 형태로 함께 노출한다.
  const serverData = data?.data || data || {};
  const explicitPreferences = serverData.explicit_preferences || {};
  const combinedPreferences = serverData.combined_preferences || {};
  const serverPreferences = {
    genres:
      explicitPreferences.genres || serverData.preferred_genres || serverData.genres || [],
    actors:
      explicitPreferences.actors || serverData.preferred_actors || serverData.actors || [],
    keywords:
      explicitPreferences.keywords || serverData.preferred_keywords || serverData.keywords || [],
    directors:
      explicitPreferences.directors || serverData.preferred_directors || serverData.directors || [],
  };

  return {
    ...serverData,
    // 캐릭터 추천처럼 활동 학습까지 반영해야 하는 UI에서 사용한다.
    // combined가 아직 없는 계정은 직접 선택 취향으로 안전하게 대체한다.
    recommendationPreferences: {
      genres: [
        ...(combinedPreferences.genres?.length ? combinedPreferences.genres : serverPreferences.genres),
        ...(localPreferences?.genres || []),
      ],
      actors: [
        ...(combinedPreferences.actors?.length ? combinedPreferences.actors : serverPreferences.actors),
        ...(localPreferences?.actors || []),
      ],
      keywords: [
        ...(combinedPreferences.keywords?.length ? combinedPreferences.keywords : serverPreferences.keywords),
        ...(localPreferences?.keywords || []),
      ],
    },
    preferences: {
      genres: mergePreferenceValues(
        serverPreferences.genres,
        localPreferences?.genres
      ),
      actors: mergePreferenceValues(
        serverPreferences.actors,
        localPreferences?.actors
      ),
      keywords: mergePreferenceValues(
        serverPreferences.keywords,
        localPreferences?.keywords,
        localPreferences?.directors
      ),
    },
  };
}

export function fetchUserPreferences(signal) {
  return cachedRequest(
    accountCacheKey('user-preferences'),
    30 * 1000,
    signal,
    loadUserPreferences,
  );
}

export async function fetchPreferenceInsights(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/preferences/insights`, { signal });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `취향 분석 문장 요청 실패 (${response.status})`));
  }
  const insights = data?.data?.insights || {};
  return {
    genres: insights.genre || insights.genres || {},
    actors: insights.actor || insights.actors || {},
    keywords: insights.keyword || insights.keywords || {},
  };
}

export async function resetLearnedPreferences(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/preferences/learned`, {
    method: 'DELETE',
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `학습 취향 초기화 실패 (${response.status})`));
  }
  clearMemoryRequestCache('user-preferences:');
  return data?.data || {};
}

export async function fetchOnboardingOptions(signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/movies/preference-options`, {
    signal,
    cache: 'no-store',
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `취향 선택지 요청 실패 (${response.status})`));
  }

  return {
    genres: Array.isArray(data?.data?.genres) ? data.data.genres : FALLBACK_GENRES,
    keywords: Array.isArray(data?.data?.keywords) ? data.data.keywords : [],
  };
}

export async function saveOnboardingPreferences(preferences, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/preferences`, {
    method: 'PATCH',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      genres: preferences.genres || [],
      actors: preferences.actors || [],
      keywords: preferences.keywords || [],
      onboarding_completed: true,
    }),
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `초기 취향 저장 실패 (${response.status})`));
  }

  writeLocalJson(LOCAL_PREFERENCES_KEY, preferences);
  return data?.data || {};
}

export async function fetchUserProfile(signal) {
  const localProfile = readLocalJson(LOCAL_PROFILE_KEY, null);
  // 실제 경로는 /user (기존 /users/me 아님)
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `프로필 정보를 불러오지 못했습니다. (${response.status})`));
  }

  // 서버 프로필을 마지막에 병합해 오래된 브라우저 캐시가 새 프로필 이미지를
  // 덮어쓰지 않도록 한다.
  return {
    ...(localProfile || {}),
    ...(data?.data || data || {}),
  };
}

export async function updateUserProfile(profile, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  writeLocalJson(LOCAL_PROFILE_KEY, profile);

  return profile;
}

export async function requestAccountEmailVerification(email, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/email-verification/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `인증번호 전송 실패 (${response.status})`));
  }
  return data?.data || {};
}

export async function confirmAccountEmailVerification(email, verificationCode, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/email-verification/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, verification_code: verificationCode }),
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `이메일 인증 실패 (${response.status})`));
  }
  return data?.data || {};
}

export async function checkAccountNicknameAvailability(nickname, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/nickname-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname }),
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `닉네임 중복 확인 실패 (${response.status})`));
  }
  return {
    available: Boolean(data?.data?.available),
    message: data?.message || '',
  };
}

export async function updateAccountProfile({ nickname, email, verificationCode, personalContext }, signal) {
  const payload = { nickname, personal_context: personalContext ?? '' };
  if (email) payload.email = email;
  if (verificationCode) payload.verification_code = verificationCode;
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `계정 정보 수정 실패 (${response.status})`));
  }

  const updated = data?.data || {};
  const stored = getStoredAuthUser() || {};
  localStorage.setItem('auth_user', JSON.stringify({
    ...stored,
    email: updated.email || email || stored.email || '',
    nickname: updated.nickname || nickname || stored.nickname || '',
    personal_context: updated.personal_context ?? personalContext ?? stored.personal_context ?? '',
  }));
  writeLocalJson(LOCAL_PROFILE_KEY, updated);
  return updated;
}

export async function deleteMyAccount(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user`, {
    method: 'DELETE',
    credentials: 'include',
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `계정 탈퇴 실패 (${response.status})`));
  }
  clearStoredAuth();
  return data;
}

// 프로필 이미지 수정 (PATCH /user/profile_image, multipart/form-data) — 인증 필요.
// Content-Type은 브라우저가 boundary와 함께 자동 설정하도록 직접 지정하지 않는다.
export async function updateProfileImage(file, signal) {
  const form = new FormData();
  form.append('image', file);

  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/profile_image`, {
    method: 'PATCH',
    body: form,
    signal,
  });
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `이미지 수정 실패 (${response.status})`));
  }

  const updated = data?.data || {};
  const profileImage = updated.user_profile || updated.profile_image || '';
  const stored = getStoredAuthUser() || {};
  localStorage.setItem('auth_user', JSON.stringify({ ...stored, profile_image: profileImage }));
  writeLocalJson(LOCAL_PROFILE_KEY, {
    ...(readLocalJson(LOCAL_PROFILE_KEY, {}) || {}),
    profile_image: profileImage,
  });
  return updated;
}

// 프로필 이미지 삭제 (DELETE /user/delete/profile_image) — 인증 필요.
export async function deleteProfileImage(signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/delete/profile_image`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `이미지 삭제 실패 (${response.status})`));
  }

  const stored = getStoredAuthUser() || {};
  localStorage.setItem('auth_user', JSON.stringify({ ...stored, profile_image: '' }));
  writeLocalJson(LOCAL_PROFILE_KEY, {
    ...(readLocalJson(LOCAL_PROFILE_KEY, {}) || {}),
    profile_image: '',
  });
  return data || {};
}

export async function updateUserPreferences(preferences, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  writeLocalJson(LOCAL_PREFERENCES_KEY, preferences);
  clearMemoryRequestCache('user-preferences:');

  // 비회원은 브라우저에만 저장하고, 로그인 회원은 서버 추천 프로필도 함께
  // 갱신한다. 기존 구현은 로컬 저장만 해 회원 추천에 변경값이 반영되지 않았다.
  if (localStorage.getItem('access_token')) {
    const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/preferences`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        genres: preferences.genres || [],
        actors: preferences.actors || [],
        keywords: preferences.keywords || [],
        onboarding_completed: true,
      }),
      signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || ['failure', 'error'].includes(getResponseState(data))) {
      throw new Error(getErrorMessage(data, `취향 저장 실패 (${response.status})`));
    }
    return data?.data || { preferences };
  }

  return { preferences };
}

export async function fetchLikedMovies(signal) {
  // 실제 경로는 /user/movies-like (기존 /users/me/movies-like 아님)
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/movies-like`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `좋아요한 영화를 불러오지 못했습니다. (${response.status})`));
  }

  return getArrayPayload(data, 'movies', 'liked_movies');
}

// 로그인 사용자가 남긴 별점·리뷰 목록을 최신 수정순으로 조회한다.
export async function fetchMyReviews(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/reviews`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `내 리뷰를 불러오지 못했습니다. (${response.status})`));
  }

  return getArrayPayload(data, 'reviews');
}

export async function fetchWishlistMovies(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/wishlist`, { signal });
  const data = await response.json().catch(() => null);
  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `찜한 영화를 불러오지 못했습니다. (${response.status})`));
  }
  return getArrayPayload(data, 'movies', 'wishlist');
}

export async function addWishlistMovie(movieId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/wishlist`, {
    method: 'POST',
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `영화 찜 저장 실패 (${response.status})`));
  }
  return data?.data || {};
}

export async function removeWishlistMovie(movieId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/wishlist`, {
    method: 'DELETE',
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `영화 찜 삭제 실패 (${response.status})`));
  }
  return data?.data || {};
}

export async function fetchPublicUserActivity(userId, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/user/public/${encodeURIComponent(userId)}/activity`, {
    credentials: 'include',
    cache: 'no-store',
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `회원 활동을 불러오지 못했습니다. (${response.status})`));
  }
  return data?.data || { user: {}, liked_movies: [], wishlisted_movies: [], reviews: [] };
}

// 최근 본 영화 조회 (GET /user/recently-viewed?limit=5) — 인증 필요.
export async function fetchRecentMovies(signal, limit = 5) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 50, 5)),
  });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/recently-viewed?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `최근 본 영화를 불러오지 못했습니다. (${response.status})`));
  }

  // 배우가 없는 경우 등 failure는 빈 목록으로 처리
  if (getResponseState(data) === 'failure') return [];

  return getArrayPayload(data, 'movies', 'recently_viewed');
}

// 채팅 AI가 추천했던 영화 조회 (GET /user/chatai-recommended-movies?limit=10).
// 응답 data: [{ tmdb_id, title, poster_url }]
export async function fetchChatRecommendedMovies(signal, limit = 10) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 50, 10)),
  });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/chatai-recommended-movies?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `채팅 추천 영화 조회 실패 (${response.status})`));
  }

  if (getResponseState(data) === 'failure') return [];

  return getArrayPayload(data, 'movies');
}

export async function removeRecentMovie(movieId, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  return { state: 'success', movieId };
}

export async function fetchAiRecommendation(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/today/recommend`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `AI 추천 요청 실패 (${response.status})`));
  }

  const payload = data?.data;
  const copy = Array.isArray(payload)
    ? payload[0]
    : payload?.answer || payload?.copy || payload?.recommendation || '';
  const movies = Array.isArray(payload)
    ? payload[1]
    : payload?.movies || payload?.movie || [];

  // AI 추천은 한 번에 최대 3개의 슬라이스를 받아와서 프론트에서 슬라이딩으로 보여준다.
  const movieList = (Array.isArray(movies) ? movies : [])
    .slice(0, 3)
    .map((movie) => ({
      movie_id: movie?.movie_id || movie?.id || null,
      movie: movie?.title || '',
      poster_path: movie?.poster_url || movie?.poster_path || movie?.poster || '',
      description:
        movie?.overview ||
        (Array.isArray(movie?.genres)
          ? movie.genres.join(', ')
          : movie?.genres || movie?.genre || ''),
    }));

  return {
    title: 'AI의 추천 한 줄',
    copy: copy || '',
    movies: movieList,
  };
}

// 관리자 API(BE2 명세). 기존 인증 토큰/refresh 처리를 그대로 재사용한다.
async function requestAdminApi(path, { method = 'GET', body, signal } = {}) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}${path}`, {
    method,
    signal,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401) throw new Error('로그인이 필요하거나 인증이 만료되었습니다.');
    if (response.status === 403) throw new Error('관리자 권한이 필요합니다.');
    throw new Error(getErrorMessage(data, `관리자 API 요청 실패 (${response.status})`));
  }

  // 권한 변경 제한 오류는 HTTP 200으로 오므로 반드시 응답 state를 검사한다.
  if (data?.state !== 'success') {
    throw new Error(data?.error || data?.message || '관리자 요청 처리에 실패했습니다.');
  }
  return data;
}

export const checkAdminAccess = (signal) => requestAdminApi('/admin/check', { signal });
export const fetchAdminOverview = (signal) => requestAdminApi('/admin/overview', { signal });
export const fetchAdminMovies = (query = '', page = 1, filters = {}, signal) => {
  const params = new URLSearchParams({
    query: query.trim(),
    page: String(page),
    limit: '20',
    source: filters.source || 'all',
    poster: filters.poster || 'all',
    sync_status: filters.syncStatus || 'all',
    sort: filters.sort || 'updated_desc',
  });
  return requestAdminApi(`/admin/movies?${params}`, { signal });
};
export const fetchAdminUsers = (query = '', page = 1, signal) => {
  const params = new URLSearchParams({ query: query.trim(), page: String(page), limit: '20' });
  return requestAdminApi(`/admin/users?${params}`, { signal });
};
export const fetchAdminAuditLogs = (query = '', action = 'all', page = 1, signal) => {
  const params = new URLSearchParams({ query: query.trim(), action, page: String(page), limit: '30' });
  return requestAdminApi(`/admin/audit-logs?${params}`, { signal });
};
export const fetchAdminInquiries = (query = '', status = 'all', page = 1, signal) => {
  const params = new URLSearchParams({ query: query.trim(), status, page: String(page), limit: '20' });
  return requestAdminApi(`/admin/inquiries?${params}`, { signal });
};
export const updateAdminInquiryStatus = (inquiryId, status, signal) => {
  const params = new URLSearchParams({ status });
  return requestAdminApi(`/admin/inquiries/${encodeURIComponent(inquiryId)}/status?${params}`, {
    method: 'PATCH', signal,
  });
};
export const replyAdminInquiry = (inquiryId, body, signal) =>
  requestAdminApi(`/admin/inquiries/${encodeURIComponent(inquiryId)}/reply`, {
    method: 'POST', body: { body }, signal,
  });
export const updateUserAdminRole = (email, isAdmin, signal) =>
  requestAdminApi('/admin/users/admin-role', {
    method: 'PATCH',
    body: { email: email.trim(), is_admin: isAdmin },
    signal,
  });
export const updateAdminUserSuspension = (userId, isSuspended, reason = '', signal) =>
  requestAdminApi(`/admin/users/${encodeURIComponent(userId)}/suspension`, {
    method: 'PATCH',
    body: { is_suspended: isSuspended, reason: isSuspended ? reason.trim() : null },
    signal,
  });
export const deleteAdminUser = (userId, signal) =>
  requestAdminApi(`/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE', signal,
  });

export const searchAdminTmdbMovies = (query, page = 1, signal) => {
  const params = new URLSearchParams({ query: query.trim(), page: String(page) });
  return requestAdminApi(`/admin/tmdb-movies-search?${params}`, { signal });
};
export const registerAdminTmdbMovie = (tmdbId, signal) =>
  requestAdminApi(`/admin/tmdb-movies-register/${encodeURIComponent(tmdbId)}`, {
    method: 'POST',
    signal,
  });
export const createAdminMovie = (payload, signal) =>
  requestAdminApi('/admin/movie', { method: 'POST', body: payload, signal });
export const updateAdminMovie = (movieId, payload, signal) =>
  requestAdminApi(`/admin/movie/${encodeURIComponent(movieId)}`, {
    method: 'PATCH',
    body: payload,
    signal,
  });
export const deleteAdminMovie = (movieId, signal) =>
  requestAdminApi(`/admin/movie/${encodeURIComponent(movieId)}`, {
    method: 'DELETE',
    signal,
  });
export const refreshAdminTmdbMovie = (movieId, signal) =>
  requestAdminApi(`/admin/movie/${encodeURIComponent(movieId)}/tmdb-refresh`, {
    method: 'POST', signal,
  });
export const retryAdminMovieVectorSync = (movieId, signal) =>
  requestAdminApi(`/admin/movie/${encodeURIComponent(movieId)}/vector-sync-retry`, {
    method: 'POST', signal,
  });

export async function submitContactInquiry(payload, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/contact`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `문의 접수에 실패했습니다. (${response.status})`));
  }

  return {
    message: data?.message || '문의가 접수되었습니다.',
    inquiryId: data?.data?.inquiry_id || null,
  };
}
