import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import {
  addRecommendedMovies,
  deleteChatRoom,
  fetchChatRooms,
  fetchChatRoomMessages,
  fetchCharacters,
  fetchUserPreferences,
  getLocalPreferences,
  sendChat,
  sendRoomMessage,
} from '../../api.js';
import { navigateTo } from '../../navigation.js';

import './chat.css';
import GuestChatNotice from './GuestChatNotice.jsx';
import ChatMovieRecommendations from './ChatMovieRecommendations.jsx';
import { rankCharactersForRecommendation } from '../../utils/characterRecommendation.js';
import { optimizeImageUrl } from '../../utils/imagePerformance.js';
import '../homeVariants/homeVariants.css';

// 배우대기실(menu2). /chat 과 /chat/group 을 한 페이지에서 다룬다.
// "멤버 추가하기" + 로 캐릭터를 고르고 — 1명이면 1:1(/chat), 2명 이상이면 그룹(/chat/group).
// 페이지 이동(새로고침) 없이 컴포넌트 상태로만 전환한다.
// 사이드바 아래 대화 내역은 대화한 캐릭터들의 이름을 제목으로 보여준다.
const STORAGE_KEY = 'cineverse.groupchat.conversations';
const AUTH_SESSION_KEY = 'cineverse.authSession';
const MUMU_DEFAULT_IMAGE = '/images/character/mu/upper-body/mu-upper-default-v1.webp';

// 장르별 캐릭터는 한 캐릭터가 한 줄에만 노출되도록 영화의 대표 장르 하나로 정규화한다.
// 복수 장르 성격이 강한 작품은 KOFIC·DC·Disney의 작품 분류를 확인해 대표 축을 정했다.
const REPRESENTATIVE_GENRE_BY_MOVIE = [
  ['범죄도시', '범죄·느와르'],
  ['베테랑', '액션·수사'],
  ['아저씨', '액션·수사'],
  ['타짜', '범죄·느와르'],
  ['신과함께', '재난·오컬트'],
  ['내부자들', '범죄·느와르'],
  ['암살', '역사·전쟁'],
  ['부산행', '재난·오컬트'],
  ['파묘', '재난·오컬트'],
  ['명량', '역사·전쟁'],
  ['아이언맨', '슈퍼히어로'],
  ['캡틴 아메리카', '역사·전쟁'],
  ['스파이더맨', '슈퍼히어로'],
  ['토르', '슈퍼히어로'],
  ['닥터 스트레인지', '마법 판타지'],
  ['어벤져스: 인피니티 워', '다크 히어로·빌런'],
  ['어벤져스', '슈퍼히어로'],
  ['가디언즈 오브 갤럭시', '슈퍼히어로'],
  ['데드풀', '다크 히어로·빌런'],
  ['다크 나이트', '다크 히어로·빌런'],
  ['조커', '다크 히어로·빌런'],
  ['수어사이드 스쿼드', '다크 히어로·빌런'],
  ['맨 오브 스틸', '슈퍼히어로'],
  ['원더우먼', '슈퍼히어로'],
  ['해리 포터', '마법 판타지'],
  ['반지의 제왕', '판타지 모험'],
  ['매트릭스', 'SF'],
  ['인터스텔라', 'SF'],
  ['인셉션', 'SF'],
  ['듄', 'SF'],
  ['오펜하이머', '역사·전쟁'],
  ['존 윅', '액션·수사'],
  ['미션 임파서블', '액션·수사'],
  ['탑건', '역사·전쟁'],
  ['캐리비안의 해적', '판타지 모험'],
  ['겨울왕국', '애니메이션'],
  ['슈렉', '애니메이션'],
  ['토이 스토리', '애니메이션'],
];

const REPRESENTATIVE_GENRE_ORDER = [
  '범죄·느와르',
  '액션·수사',
  '역사·전쟁',
  '재난·오컬트',
  '슈퍼히어로',
  '다크 히어로·빌런',
  'SF',
  '마법 판타지',
  '판타지 모험',
  '애니메이션',
  '기타',
];

function normalizeGenre(value) {
  const genre = String(value || '').trim().toLocaleLowerCase('ko-KR');
  if (!genre) return '';
  if (/animation|애니/.test(genre)) return '애니메이션';
  if (/science fiction|sci-fi|sf/.test(genre)) return 'SF';
  if (/fantasy|판타지/.test(genre)) return '판타지';
  if (/horror|공포|mystery|미스터리|thriller|스릴러/.test(genre)) return '재난·오컬트';
  if (/crime|범죄/.test(genre)) return '범죄·느와르';
  if (/history|historical|war|전쟁|역사|사극/.test(genre)) return '역사·전쟁';
  if (/adventure|모험/.test(genre)) return '판타지 모험';
  if (/action|액션/.test(genre)) return '액션·수사';
  if (/drama|드라마/.test(genre)) return '기타';
  return '';
}

function normalizeCharacterSearchText(value) {
  return String(value || '').replace(/\s+/g, '').toLocaleLowerCase('ko-KR');
}

function withObjectParticle(value) {
  const text = String(value || '').trim();
  const lastCharacter = text.at(-1) || '';
  const code = lastCharacter.charCodeAt(0);
  const isHangulSyllable = code >= 0xac00 && code <= 0xd7a3;
  const hasFinalConsonant = isHangulSyllable && (code - 0xac00) % 28 !== 0;
  return `${text}${hasFinalConsonant ? '을' : '를'}`;
}

function withSubjectParticle(value) {
  const text = String(value || '').trim();
  const lastCharacter = text.at(-1) || '';
  const code = lastCharacter.charCodeAt(0);
  const isHangulSyllable = code >= 0xac00 && code <= 0xd7a3;
  const hasFinalConsonant = isHangulSyllable && (code - 0xac00) % 28 !== 0;
  return `${text}${hasFinalConsonant ? '이' : '가'}`;
}

function getEditDistance(leftValue, rightValue) {
  const left = Array.from(normalizeCharacterSearchText(leftValue));
  const right = Array.from(normalizeCharacterSearchText(rightValue));
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);

  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex];
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = Math.min(
        current[rightIndex - 1] + 1,
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1)
      );
    }
    previous.splice(0, previous.length, ...current);
  }

  return previous[right.length];
}

function getRepresentativeGenre(character) {
  const movieTitle = String(character.movieTitle || '').replace(/\s+/g, '').toLocaleLowerCase('ko-KR');
  const researchedGenre = REPRESENTATIVE_GENRE_BY_MOVIE.find(([title]) => (
    movieTitle.includes(title.replace(/\s+/g, '').toLocaleLowerCase('ko-KR'))
  ))?.[1];
  if (researchedGenre) return researchedGenre;

  const normalizedDbGenres = character.genres.map(normalizeGenre).filter(Boolean);
  return REPRESENTATIVE_GENRE_ORDER.find((genre) => normalizedDbGenres.includes(genre)) || '기타';
}

// 그룹채팅 순차 타이핑용 유틸 ---------------------------------------------
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// 글자당 타이핑 지연(ms). 문장부호에는 추가 지연을 준다.
function getTypingDelay(character) {
  if ([',', '，'].includes(character)) return 100;
  if (['.', '!', '?', '。', '！', '？'].includes(character)) return 200;
  if (character === '…') return 250;
  return 40;
}

// crypto.randomUUID가 없는 환경을 위한 안전한 고유 id 생성기
const createId = () =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
// -----------------------------------------------------------------------

function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function readSessionConversations() {
  const stored = readJson(STORAGE_KEY, null);
  return Array.isArray(stored?.conversations) ? stored.conversations : [];
}

function formatConversationStartedAt(conversation) {
  const value = conversation?.createdAt || conversation?.messages?.[0]?.createdAt;
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return '채팅 시작 시간 정보 없음';

  const formatted = new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);

  return `${formatted}`;
}

function orbGradient(seed) {
  const text = String(seed || 'AI');
  let hue = 0;
  for (let i = 0; i < text.length; i += 1) {
    hue = (hue * 31 + text.charCodeAt(i)) % 360;
  }
  return `radial-gradient(circle at 34% 28%, hsl(${hue} 70% 78%) 0%, hsl(${hue} 55% 48%) 24%, hsl(${hue} 60% 28%) 52%, hsl(${hue} 65% 12%) 100%)`;
}

function normalizeName(value) {
  return String(value || '').trim();
}

function getCharacterFromList(name, characters) {
  const normalized = normalizeName(name);
  return characters.find((character) => normalizeName(character.name) === normalized) || null;
}

function createMember(name, characters = []) {
  const normalized = normalizeName(name);
  const character = getCharacterFromList(normalized, characters);

  return {
    id: character?.id || normalized,
    name: normalized,
    image: character?.image || '',
  };
}

function hydrateMembers(members, characters) {
  return (members || [])
    .map((member) => createMember(member?.name || member, characters))
    .filter((member) => member.name);
}

function getMessageMovies(message) {
  const movies = message?.recommended_movies ?? message?.movies ?? message?.movie ?? [];
  return Array.isArray(movies) ? movies : [];
}

// 서버 방(room) 메시지를 이 페이지의 메시지 형태로 변환한다.
function mapRoomMessages(roomId, roomMessages) {
  return (roomMessages || []).map((message, index) => ({
    id: `room-${roomId}-${index}`,
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content || message.answer || '',
    character: message.role === 'assistant' ? message.character || 'AI' : '',
    createdAt: message.created_at || message.createdAt || new Date().toISOString(),
    movies: getMessageMovies(message),
  }));
}

function normalizeCharacter(rawCharacter, index) {
  const name = String(rawCharacter?.name || rawCharacter?.character || '').trim();
  if (!name) return null;

  return {
    id: String(rawCharacter?.id ?? rawCharacter?.character_id ?? name ?? index),
    name,
    actor: String(rawCharacter?.actor || '').trim(),
    genres: Array.isArray(rawCharacter?.genres) ? rawCharacter.genres : [],
    keywords: Array.isArray(rawCharacter?.keywords) ? rawCharacter.keywords : [],
    movieTitle: String(rawCharacter?.movie_title || rawCharacter?.movieTitle || '').trim(),
    greetingMessage: String(rawCharacter?.greeting_message || rawCharacter?.greetingMessage || '').trim(),
    image: optimizeImageUrl(
      rawCharacter?.image ||
      rawCharacter?.image_url ||
      rawCharacter?.avatar_url ||
      rawCharacter?.profile_image ||
      '',
    ),
  };
}

function CharacterDiscoveryRow({ title, description, characters, onSelect }) {
  if (!characters.length) return null;

  return (
    <section className="group-character-row" aria-label={title}>
      <header>
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
      </header>
      <div className="group-character-row__track">
        {characters.map((character) => (
          <button type="button" key={character.id} onClick={() => onSelect(character)}>
            <span className="group-character-row__image">
              {character.image ? <img src={character.image} alt="" decoding="async" loading="lazy" /> : null}
            </span>
            <strong>{character.name}</strong>
            <small>{character.movieTitle || '출연 영화 정보 없음'}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function GroupChatPage({ authUser, onLogout }) {
  const [characters, setCharacters] = useState([]);
  const [characterLoadError, setCharacterLoadError] = useState('');
  const [charactersLoading, setCharactersLoading] = useState(true);
  const [preferences, setPreferences] = useState(() => getLocalPreferences());

  // 대화 내역: 각 대화는 멤버(캐릭터들)를 갖고, 제목은 멤버 이름들이다.
  const [conversations, setConversations] = useState(() =>
    authUser ? readSessionConversations() : []
  );
  const [linkedConversations, setLinkedConversations] = useState([]);
  const [activeId, setActiveId] = useState('');

  const [isPickerOpen, setPickerOpen] = useState(false);
  const [pickerMode, setPickerMode] = useState('new');
  const [pickerQuery, setPickerQuery] = useState('');
  const [pickedIds, setPickedIds] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyMenuId, setHistoryMenuId] = useState('');
  const [historyMenuPosition, setHistoryMenuPosition] = useState({ top: 0, left: 0 });
  const [promptMenuOpen, setPromptMenuOpen] = useState(false);
  const [photoName, setPhotoName] = useState('');
  const [characterSearchMessages, setCharacterSearchMessages] = useState([]);
  const [characterSearchPending, setCharacterSearchPending] = useState(false);
  const [searchChatActive, setSearchChatActive] = useState(false);

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // 그룹 응답을 하나씩 타이핑 재생하는 동안 "입력 중"인 캐릭터와 재생 진행 여부
  const [typingCharacter, setTypingCharacter] = useState(null);

  const messagesRef = useRef(null);
  const searchMessagesRef = useRef(null);
  const chatStageRef = useRef(null);
  const promptAreaRef = useRef(null);
  const promptStartRectRef = useRef(null);
  const chatActivatedRef = useRef(false);
  const restorePromptFocusRef = useRef(false);
  const photoInputRef = useRef(null);
  const promptAddButtonRef = useRef(null);
  const promptMenuRef = useRef(null);
  const historyPanelRef = useRef(null);
  const historyMoreMenuRef = useRef(null);
  const characterPickerRef = useRef(null);
  const abortRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const loadedRoomIdsRef = useRef(new Set());
  // 순차 재생 취소용 토큰: 값이 바뀌면 실행 중인 재생 루프가 스스로 멈춘다.
  const playbackIdRef = useRef(0);
  const characterSearchRequestRef = useRef(0);
  const scrollHideTimerRef = useRef(0);
  const visibleScrollbarRef = useRef(null);
  const initialRoomParamRef = useRef(
    new URLSearchParams(window.location.search).get('room') || '',
  );
  const roomEntryHandledRef = useRef(false);

  const showScrollbarWhileScrolling = (event) => {
    const element = event.currentTarget;
    if (visibleScrollbarRef.current && visibleScrollbarRef.current !== element) {
      visibleScrollbarRef.current.classList.remove('is-scrolling');
    }
    visibleScrollbarRef.current = element;
    element.classList.add('is-scrolling');
    window.clearTimeout(scrollHideTimerRef.current);
    scrollHideTimerRef.current = window.setTimeout(() => {
      element.classList.remove('is-scrolling');
      if (visibleScrollbarRef.current === element) visibleScrollbarRef.current = null;
    }, 700);
  };

  useEffect(() => {
    const controller = new AbortController();
    setCharactersLoading(true);

    fetchCharacters(controller.signal)
      .then((data) => {
        const list = Array.isArray(data)
          ? data
          : Array.isArray(data?.data)
            ? data.data
            : Array.isArray(data?.characters)
              ? data.characters
              : [];

        const dbCharacters = list.map(normalizeCharacter).filter(Boolean);
        setCharacters(dbCharacters);
        setCharacterLoadError(dbCharacters.length === 0 ? 'DB에 캐릭터 데이터가 없습니다.' : '');
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        setCharacterLoadError(fetchError.message);
        setCharacters([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setCharactersLoading(false);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!authUser) {
      setPreferences(getLocalPreferences());
      return undefined;
    }

    const controller = new AbortController();
    fetchUserPreferences(controller.signal)
      .then((result) => setPreferences(
        result?.recommendationPreferences || result?.preferences || getLocalPreferences()
      ))
      .catch((fetchError) => {
        if (fetchError.name !== 'AbortError') setPreferences(getLocalPreferences());
      });
    return () => controller.abort();
  }, [authUser]);

  useEffect(() => {
    if (!promptMenuOpen && !historyOpen && !isPickerOpen && !historyMenuId) return undefined;

    const closeFloatingPanels = (event) => {
      if (
        promptAddButtonRef.current?.contains(event.target)
        || promptMenuRef.current?.contains(event.target)
        || historyPanelRef.current?.contains(event.target)
        || historyMoreMenuRef.current?.contains(event.target)
        || characterPickerRef.current?.contains(event.target)
      ) return;

      setPromptMenuOpen(false);
      setHistoryOpen(false);
      setHistoryMenuId('');
      setPickerOpen(false);
      setPickedIds([]);
    };

    document.addEventListener('pointerdown', closeFloatingPanels);
    return () => document.removeEventListener('pointerdown', closeFloatingPanels);
  }, [promptMenuOpen, historyOpen, isPickerOpen, historyMenuId]);

  useEffect(() => {
    if (!authUser) return;
    const sessionId = window.localStorage.getItem(AUTH_SESSION_KEY);
    if (!sessionId) return;

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ sessionId, conversations })
    );
  }, [authUser, conversations]);

  useEffect(() => {
    if (!authUser) return undefined;

    const controller = new AbortController();
    fetchChatRooms(controller.signal)
      .then((rooms) => {
        const generalRooms = (rooms || [])
          .filter((room) => String(room?.room_type || room?.roomType || 'general') === 'general')
          .map((room) => {
            const roomId = String(room.room_id ?? room.roomId ?? '');
            return {
              id: `linked-general-${roomId}`,
              roomId,
              roomType: 'general',
              title: String(room.title || '').trim()
                || String(room.title_seed || room.titleSeed || '').trim().slice(0, 30)
                || '무무와 영화 이야기',
              createdAt: room.created_at || room.createdAt || new Date().toISOString(),
              updatedAt: room.updated_at || room.updatedAt || room.created_at || room.createdAt || new Date().toISOString(),
              href: `/home?room=${encodeURIComponent(roomId)}`,
              linked: true,
            };
          });
        setLinkedConversations(generalRooms);

        const characterRooms = (rooms || []).filter((room) => {
          const type = String(room?.room_type || room?.roomType || '');
          return type === 'character' || type === 'group';
        });

        setConversations((current) => {
          const localByRoomId = new Map(
            current
              .filter((conversation) => conversation.roomId)
              .map((conversation) => [String(conversation.roomId), conversation]),
          );
          const serverRoomIds = new Set(characterRooms.map((room) => String(room.room_id ?? room.roomId ?? '')));
          const hydrated = characterRooms.map((room) => {
            const roomId = String(room.room_id ?? room.roomId ?? '');
            const local = localByRoomId.get(roomId);
            const memberNames = Array.isArray(room.characters) ? room.characters.filter(Boolean) : [];
            return {
              id: local?.id || `server-room-${roomId}`,
              title: local?.title || memberNames.join(', ') || '캐릭터 대화',
              members: local?.members?.length
                ? local.members
                : memberNames.map((name) => createMember(name)),
              roomId,
              createdAt: local?.createdAt || room.created_at || room.createdAt || new Date().toISOString(),
              updatedAt: room.updated_at || room.updatedAt || local?.updatedAt || new Date().toISOString(),
              messages: Array.isArray(local?.messages) ? local.messages : [],
              pinned: Boolean(local?.pinned),
              manualTitle: Boolean(local?.manualTitle),
            };
          });
          const localOnly = current.filter((conversation) => (
            !conversation.roomId || !serverRoomIds.has(String(conversation.roomId))
          ));
          return [...hydrated, ...localOnly];
        });
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') {
          setLinkedConversations([]);
          setCharacterLoadError(loadError.message);
        }
      });

    return () => controller.abort();
  }, [authUser]);

  useEffect(() => {
    if (characters.length === 0) return;

    setConversations((current) =>
      current.map((conversation) => ({
        ...conversation,
        members: hydrateMembers(conversation.members, characters),
      }))
    );
  }, [characters]);

  // 마이페이지 등에서 ?room=<id>&members=<이름들> 로 들어오면 그 방 대화를 이어서 연다.
  useEffect(() => {
    // 개발 모드의 effect 재실행에서도 URL room을 정확히 한 번만 소비한다.
    if (roomEntryHandledRef.current) return;
    roomEntryHandledRef.current = true;

    const params = new URLSearchParams(window.location.search);
    const roomParam = initialRoomParamRef.current;

    // 일반 진입에서는 저장된 대화 목록만 유지하고 활성 대화는 복원하지 않는다.
    // 특정 대화를 명시한 room 파라미터가 있을 때만 해당 대화를 연다.
    if (!roomParam) {
      setActiveId('');
      return;
    }

    // 기록에서 전달된 방은 이번 진입에서만 연다. 쿼리를 남겨두면
    // 새로고침 때 다시 활성화되므로 즉시 기본 경로로 정리한다.
    window.history.replaceState({}, '', window.location.pathname);

    if (!authUser) return;
    const memberNames = (params.get('members') || '')
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean);

    const stored = readSessionConversations();
    const existing = stored.find((c) => String(c.roomId) === String(roomParam));

    if (existing) {
      setActiveId(existing.id);
    } else {
      const conversation = {
        id: crypto.randomUUID(),
        title: memberNames.join(', ') || '그룹 대화',
        members: memberNames.map((name) => createMember(name, characters)),
        roomId: String(roomParam),
        createdAt: new Date().toISOString(),
        messages: [],
      };
      setConversations((current) => [conversation, ...current]);
      setActiveId(conversation.id);
    }
  }, [authUser]);

  const activeConversation = conversations.find((c) => c.id === activeId) || null;
  const historyConversations = useMemo(() => conversations
    .map((conversation, index) => ({ conversation, index }))
    .sort((left, right) => (
      Number(Boolean(right.conversation.pinned)) - Number(Boolean(left.conversation.pinned))
      || left.index - right.index
    ))
    .map(({ conversation }) => conversation), [conversations]);
  const messages = activeConversation?.messages || [];
  const members = activeConversation?.members || [];
  const canChat = Boolean(activeConversation);
  const chatLayoutActive = canChat || searchChatActive;

  const prepareChatActivation = () => {
    if (chatLayoutActive || chatActivatedRef.current) return;
    const promptRect = promptAreaRef.current?.getBoundingClientRect();
    promptStartRectRef.current = promptRect
      ? {
          documentTop: promptRect.top + window.scrollY,
          scrollY: window.scrollY,
        }
      : null;

    const focusedElement = document.activeElement;
    restorePromptFocusRef.current = Boolean(
      focusedElement && promptAreaRef.current?.contains(focusedElement)
    );
  };

  useLayoutEffect(() => {
    if (!chatLayoutActive) {
      chatActivatedRef.current = false;
      return undefined;
    }
    if (chatActivatedRef.current) return undefined;
    chatActivatedRef.current = true;

    const prompt = promptAreaRef.current;
    const stage = chatStageRef.current;
    if (!prompt || !stage) return undefined;

    let animationFrameId = 0;
    let cleanupTimer = 0;
    const startedAt = window.performance.now();
    const duration = 720;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const startRect = promptStartRectRef.current;
    const startScroll = startRect?.scrollY ?? window.scrollY;

    if (!prefersReducedMotion && startRect) {
      const currentDocumentTop = prompt.getBoundingClientRect().top + window.scrollY;
      prompt.style.transition = 'none';
      prompt.style.transform = `translateY(${startRect.documentTop - currentDocumentTop}px)`;
      prompt.style.willChange = 'transform';
      window.scrollTo({ top: startScroll, left: 0, behavior: 'auto' });
      void prompt.offsetHeight;
    }

    const followPrompt = (now) => {
      const activeStage = chatStageRef.current;
      if (!activeStage) return;

      const progress = Math.min(1, Math.max(0, (now - startedAt) / duration));
      const easedProgress = 1 - ((1 - progress) ** 3);
      const stageRect = activeStage.getBoundingClientRect();
      const stageCenter = stageRect.top + window.scrollY + (stageRect.height / 2);
      const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      const centeredScroll = Math.min(maxScroll, Math.max(0, stageCenter - (window.innerHeight / 2)));

      window.scrollTo({
        top: startScroll + ((centeredScroll - startScroll) * easedProgress),
        left: window.scrollX,
        behavior: 'auto',
      });

      if (!prefersReducedMotion && progress < 1) {
        animationFrameId = window.requestAnimationFrame(followPrompt);
      }
    };

    animationFrameId = window.requestAnimationFrame((now) => {
      if (!prefersReducedMotion && startRect) {
        prompt.style.transition = `transform ${duration}ms cubic-bezier(0.4, 0, 0.2, 1)`;
        prompt.style.transform = 'translateY(0)';
      }
      if (restorePromptFocusRef.current) {
        prompt.querySelector('input')?.focus({ preventScroll: true });
      }
      followPrompt(now);
    });

    cleanupTimer = window.setTimeout(() => {
      prompt.style.removeProperty('transition');
      prompt.style.removeProperty('transform');
      prompt.style.removeProperty('will-change');
      promptStartRectRef.current = null;
      if (restorePromptFocusRef.current) {
        prompt.querySelector('input')?.focus({ preventScroll: true });
        restorePromptFocusRef.current = false;
      }
    }, duration);

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      window.clearTimeout(cleanupTimer);
    };
  }, [chatLayoutActive]);

  const recommendedCharacters = useMemo(() => {
    return rankCharactersForRecommendation(characters, preferences, { limit: 8 });
  }, [characters, preferences]);

  const characterGenreGroups = useMemo(() => {
    const groups = new Map();
    characters.forEach((character) => {
      const representativeGenre = getRepresentativeGenre(character);
      if (!groups.has(representativeGenre)) groups.set(representativeGenre, []);
      groups.get(representativeGenre).push(character);
    });
    return REPRESENTATIVE_GENRE_ORDER
      .filter((genre) => groups.has(genre))
      .map((genre) => ({ genre, characters: groups.get(genre) }));
  }, [characters]);

  const activeName = members.map((m) => m.name).join(', ') || '새로운 대화를 시작해보세요';
  const activeSubText =
    members.length > 1
      ? `${members.length}명 그룹 대화 · AI 대화`
      : members.length === 1
        ? '영화 속 캐릭터 · AI 대화'
        : '영화 속 캐릭터를 선택하면 대화가 시작됩니다';

  // 이름으로 캐릭터 이미지를 찾아 아바타에 쓴다(없으면 색상 그라디언트).
  const findImage = (name, fallbackMembers = members) => {
    if (normalizeName(name) === '무무') return MUMU_DEFAULT_IMAGE;
    return getCharacterFromList(name, characters)?.image ||
      hydrateMembers(fallbackMembers, characters).find(
        (member) => normalizeName(member.name) === normalizeName(name)
      )?.image ||
      '';
  };

  useEffect(() => {
    const roomId = activeConversation?.roomId;
    if (!roomId || loadedRoomIdsRef.current.has(String(roomId))) return;

    loadedRoomIdsRef.current.add(String(roomId));
    const controller = new AbortController();

    fetchChatRoomMessages(roomId, controller.signal)
      .then((roomMessages) => {
        if (controller.signal.aborted) return;

        updateConversation(activeConversation.id, (conversation) => ({
          ...conversation,
          messages: [
            ...conversation.messages.filter((message) => message.localOnly),
            ...mapRoomMessages(roomId, roomMessages),
          ],
        }));
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        loadedRoomIdsRef.current.delete(String(roomId));
        setError(fetchError.message);
      });

    return () => controller.abort();
  }, [activeConversation?.id, activeConversation?.roomId]);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return undefined;
    const handleScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distanceFromBottom < 80;
    };
    el.addEventListener('scroll', handleScroll);
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, activeId, typingCharacter]);

  useEffect(() => {
    const el = searchMessagesRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [characterSearchMessages, characterSearchPending]);

  // 컴포넌트 언마운트 시 실행 중인 타이핑 재생을 중단(타이머 정리).
  useEffect(
    () => () => {
      playbackIdRef.current += 1;
      window.clearTimeout(scrollHideTimerRef.current);
      visibleScrollbarRef.current?.classList.remove('is-scrolling');
    },
    []
  );

  const updateConversation = (id, updater) => {
    setConversations((current) => current.map((c) => (c.id === id ? updater(c) : c)));
  };

  const openCharacterPicker = (mode = 'new') => {
    if (busy || typingCharacter) return;
    setPickerMode(mode);
    setPickerQuery('');
    setPickedIds(mode === 'manage' ? members.map((member) => member.id) : []);
    setPromptMenuOpen(false);
    setHistoryOpen(false);
    setPickerOpen(true);
  };

  const openGroupConversationSetup = () => {
    if (busy || typingCharacter) return;
    prepareChatActivation();
    setSearchChatActive(true);
    window.requestAnimationFrame(() => openCharacterPicker('new'));
  };

  const returnToCharacterSearch = () => {
    abortRef.current?.abort();
    playbackIdRef.current += 1;
    prepareChatActivation();
    setActiveId('');
    setSearchChatActive(false);
    setInput('');
    setError('');
    setBusy(false);
    setTypingCharacter(null);
    setCharacterSearchMessages([]);
    setCharacterSearchPending(false);
    characterSearchRequestRef.current += 1;
    setPromptMenuOpen(false);
    setHistoryOpen(false);
    setPickerOpen(false);
    setPickerMode('new');
    setPickerQuery('');
    setPickedIds([]);
    stickToBottomRef.current = true;
    chatActivatedRef.current = false;
    promptStartRectRef.current = null;

    if (window.location.search) {
      window.history.replaceState({}, '', window.location.pathname);
    }

    window.requestAnimationFrame(() => {
      document.querySelector('.group-chat-home-stage')?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    });
  };

  // 대화 삭제: 서버 방이 있으면 삭제(DELETE /chat/rooms/{id})하고 로컬 리스트에서도 제거.
  const handleDeleteConversation = async (conversation) => {
    setHistoryMenuId('');
    if (conversation.roomId) {
      try {
        await deleteChatRoom(conversation.roomId);
      } catch (deleteError) {
        setError(deleteError.message);
        return;
      }
    }

    setConversations((current) => current.filter((c) => c.id !== conversation.id));
    setActiveId((current) => {
      if (current !== conversation.id) return current;
      const remaining = conversations.filter((c) => c.id !== conversation.id);
      return remaining[0]?.id || '';
    });
  };

  const toggleConversationPin = (conversation) => {
    setConversations((current) => current.map((item) => (
      item.id === conversation.id ? { ...item, pinned: !item.pinned } : item
    )));
    setHistoryMenuId('');
  };

  const renameConversation = (conversation) => {
    const title = window.prompt('대화 이름을 입력해 주세요.', conversation.title || '');
    const normalizedTitle = String(title || '').trim();
    if (!normalizedTitle) return;

    setConversations((current) => current.map((item) => (
      item.id === conversation.id ? { ...item, title: normalizedTitle, manualTitle: true } : item
    )));
    setHistoryMenuId('');
  };

  const togglePick = (id) => {
    setPickedIds((current) => {
      if (current.includes(id)) return current.filter((x) => x !== id);
      if (current.length >= 3) return current;
      return [...current, id];
    });
  };

  const startCharacterConversation = (
    pickedMembers,
    { mumuMessage = '', includeSearchHistory = false } = {},
  ) => {
    if (pickedMembers.length === 0) return;

    abortRef.current?.abort();
    prepareChatActivation();

    const createdAt = new Date().toISOString();
    const firstCharacter = pickedMembers[0];
    const lastSearchAnswerIndex = includeSearchHistory
      ? characterSearchMessages.findLastIndex((message) => message.role === 'assistant' && message.searchResult)
      : -1;
    const preservedSearchMessages = includeSearchHistory
      ? characterSearchMessages.map(({ searchResult, ...message }, index) => ({
          ...message,
          ...(index === lastSearchAnswerIndex ? {
            selectedCharacter: {
              id: firstCharacter.id,
              name: firstCharacter.name,
              image: firstCharacter.image,
              movieTitle: firstCharacter.movieTitle || '',
            },
          } : {}),
        }))
      : [];
    const openingMessages = [
      ...preservedSearchMessages,
      ...(mumuMessage ? [{
        id: createId(),
        role: 'assistant',
        character: '무무',
        content: mumuMessage,
        createdAt,
        localOnly: true,
      }] : []),
      ...(firstCharacter.greetingMessage ? [{
        id: createId(),
        role: 'assistant',
        character: firstCharacter.name,
        content: firstCharacter.greetingMessage,
        createdAt,
        localOnly: true,
      }] : []),
    ];

    const conversation = {
      id: crypto.randomUUID(),
      title: pickedMembers.map((m) => m.name).join(', '),
      members: pickedMembers,
      roomId: '',
      createdAt,
      messages: openingMessages,
    };

    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setPickerOpen(false);
    setPickerMode('new');
    setPickerQuery('');
    setPickedIds([]);
    setInput('');
    setError('');
    setCharacterSearchMessages([]);
    setCharacterSearchPending(false);
    characterSearchRequestRef.current += 1;
    stickToBottomRef.current = true;
  };

  // 완료: 고른 멤버들로 새 대화를 만든다(1명=1:1, 2명 이상=그룹). 제목은 멤버 이름들.
  const getPickedMembers = () => pickedIds
    .map((id) => characters.find((character) => character.id === id))
    .filter(Boolean)
    .map((character) => ({
      id: character.id,
      name: character.name,
      image: character.image,
      movieTitle: character.movieTitle,
      greetingMessage: character.greetingMessage,
    }));

  const confirmPicker = () => {
    const pickedMembers = getPickedMembers();
    startCharacterConversation(pickedMembers);
  };

  const applyMemberChanges = () => {
    if (!activeConversation || pickedIds.length === 0 || busy || typingCharacter) return;

    const nextMembers = getPickedMembers();
    const currentNames = new Set(members.map((member) => member.name));
    const nextNames = new Set(nextMembers.map((member) => member.name));
    const addedNames = nextMembers.filter((member) => !currentNames.has(member.name)).map((member) => member.name);
    const removedNames = members.filter((member) => !nextNames.has(member.name)).map((member) => member.name);

    if (addedNames.length === 0 && removedNames.length === 0) {
      setPickerOpen(false);
      return;
    }

    const eventParts = [];
    if (addedNames.length) {
      eventParts.push(addedNames.length === 1
        ? `${withSubjectParticle(addedNames[0])} 대화에 참여했어요.`
        : `${addedNames.join(', ')} 캐릭터가 대화에 참여했어요.`);
    }
    if (removedNames.length) {
      eventParts.push(removedNames.length === 1
        ? `${withSubjectParticle(removedNames[0])} 대화에서 나갔어요.`
        : `${removedNames.join(', ')} 캐릭터가 대화에서 나갔어요.`);
    }
    const createdAt = new Date().toISOString();

    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      members: nextMembers,
      roomId: '',
      title: conversation.manualTitle ? conversation.title : nextMembers.map((member) => member.name).join(', '),
      messages: [
        ...conversation.messages,
        {
          id: createId(),
          role: 'system',
          content: eventParts.join(' '),
          createdAt,
          localOnly: true,
          memberChange: true,
        },
      ],
    }));
    setPickerOpen(false);
    setPickerMode('new');
    setPickerQuery('');
    setPickedIds([]);
    stickToBottomRef.current = true;
  };

  const startSingleCharacterConversation = (character, options) => {
    startCharacterConversation(
      [{
        id: character.id,
        name: character.name,
        image: character.image,
        movieTitle: character.movieTitle,
        greetingMessage: character.greetingMessage,
      }],
      options
    );
    window.requestAnimationFrame(() => {
      document.querySelector('.group-chat-home-stage')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };

  // 홈 등의 캐릭터 카드에서 전달한 캐릭터를 새 1:1 대화로 연다.
  // 캐릭터를 찾은 뒤 쿼리를 제거해 새로고침/뒤로가기로 같은 대화가 중복 생성되지 않게 한다.
  useEffect(() => {
    if (characters.length === 0) return;

    const params = new URLSearchParams(window.location.search);
    const characterId = params.get('characterId');
    const characterName = normalizeName(params.get('characterName'));
    if (!characterId && !characterName) return;

    const selectedCharacter = characters.find((character) => (
      (characterId && String(character.id) === String(characterId))
      || (characterName && normalizeName(character.name) === characterName)
    ));

    window.history.replaceState({}, '', window.location.pathname);

    if (!selectedCharacter) {
      setError('선택한 캐릭터 정보를 찾을 수 없어요. 다른 캐릭터를 선택해 주세요.');
      return;
    }

    startSingleCharacterConversation(selectedCharacter);
  // 쿼리는 한 번만 소비하며, 캐릭터 목록이 준비됐을 때만 실행한다.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characters]);

  const selectCharacterFromDiscovery = (character) => {
    if (!activeConversation) {
      startSingleCharacterConversation(character);
      return;
    }

    if (members.some((member) => member.id === character.id || member.name === character.name)) {
      document.querySelector('.group-chat-home-stage')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (members.length >= 3) {
      setError('단체 대화에는 최대 3명까지 참여할 수 있어요.');
      return;
    }
    if (busy || typingCharacter) {
      setError('현재 답변이 끝난 뒤 캐릭터를 추가해 주세요.');
      return;
    }

    const addedMember = {
      id: character.id,
      name: character.name,
      image: character.image,
      movieTitle: character.movieTitle,
      greetingMessage: character.greetingMessage,
    };
    const createdAt = new Date().toISOString();

    updateConversation(activeConversation.id, (conversation) => {
      const nextMembers = [...conversation.members, addedMember];
      return {
        ...conversation,
        members: nextMembers,
        roomId: '',
        title: conversation.manualTitle ? conversation.title : nextMembers.map((member) => member.name).join(', '),
        messages: [
          ...conversation.messages,
          {
            id: createId(),
            role: 'system',
            content: `${withSubjectParticle(character.name)} 대화에 참여했어요.`,
            createdAt,
            localOnly: true,
            memberChange: true,
          },
        ],
      };
    });
    setError('');
    stickToBottomRef.current = true;
    window.requestAnimationFrame(() => {
      document.querySelector('.group-chat-home-stage')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };

  const searchCharacterBeforeChat = async () => {
    const query = input.trim();
    if (!query || characterSearchPending) return;

    const requestId = characterSearchRequestRef.current + 1;
    characterSearchRequestRef.current = requestId;
    setInput('');
    setCharacterSearchPending(true);

    // 즉시 결과가 튀어나오지 않도록 무무의 짧은 입력 중 상태를 먼저 보여준다.
    await sleep(600);
    if (characterSearchRequestRef.current !== requestId) return;

    const appendSearchExchange = (result) => {
      const createdAt = new Date().toISOString();
      setCharacterSearchMessages((current) => [
        ...current,
        {
          id: createId(),
          role: 'user',
          content: query,
          createdAt,
          localOnly: true,
        },
        {
          id: createId(),
          role: 'assistant',
          character: '무무',
          content: result.message,
          createdAt,
          localOnly: true,
          searchResult: result,
        },
      ]);
      setCharacterSearchPending(false);
    };

    if (charactersLoading) {
      appendSearchExchange({
        query,
        matches: [],
        message: '캐릭터 목록을 불러오고 있어요. 잠시 후 다시 검색해 주세요.',
      });
      return;
    }

    const normalizedQuery = normalizeCharacterSearchText(query);
    const exactMatches = characters.filter((character) => (
      normalizeCharacterSearchText(character.name) === normalizedQuery
    ));
    const partialMatches = exactMatches.length > 0 ? exactMatches : characters.filter((character) => (
      normalizeCharacterSearchText(character.name).includes(normalizedQuery)
    ));
    let matches = partialMatches.slice(0, 6);
    let usedClosestMatch = false;

    if (matches.length === 0 && characters.length > 0) {
      const queryLength = Array.from(normalizedQuery).length;
      matches = characters
        .map((character, index) => {
          const normalizedName = normalizeCharacterSearchText(character.name);
          return {
            character,
            index,
            distance: getEditDistance(normalizedQuery, normalizedName),
            lengthGap: Math.abs(queryLength - Array.from(normalizedName).length),
          };
        })
        .sort((left, right) => (
          left.distance - right.distance
          || left.lengthGap - right.lengthGap
          || left.index - right.index
        ))
        .slice(0, 1)
        .map(({ character }) => character);
      usedClosestMatch = matches.length > 0;
    }

    appendSearchExchange({
      query,
      matches,
      usedClosestMatch,
      message: usedClosestMatch
        ? `“${query}”는 아직 등록되지 않은 캐릭터예요. 이름이 가장 비슷한 ${matches[0].name} 캐릭터를 찾아봤어요.`
        : matches.length > 0
        ? matches.length === 1
          ? `${matches[0].name} 캐릭터를 찾았어요. 이미지를 누르면 바로 대화를 시작할 수 있어요.`
          : `${query}와(과) 관련된 캐릭터를 ${matches.length}명 찾았어요.`
        : '검색할 수 있는 캐릭터 정보가 없어요.',
    });
  };

  const updateMessage = (conversationId, messageId, updater) => {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((m) => (m.id === messageId ? updater(m) : m)),
    }));
  };

  // 텍스트를 한 글자씩 onUpdate로 흘려보낸다. isCancelled()가 true면 즉시 중단.
  const typeText = async ({ text, onUpdate, isCancelled }) => {
    let currentText = '';

    for (const character of text) {
      if (isCancelled()) return;

      currentText += character;
      onUpdate(currentText);

      await sleep(getTypingDelay(character));
    }
  };

  // 실행 중인 순차 재생을 중단한다(토큰 증가 → 루프가 다음 검사에서 멈춤).
  // 이미 출력된 텍스트는 그대로 남긴다.
  const cancelGroupPlayback = () => {
    playbackIdRef.current += 1;
    setTypingCharacter(null);
  };

  // 그룹 응답(여러 캐릭터 메시지)을 배열 순서대로 하나씩 "입력 중 → 타이핑"으로 재생한다.
  const playGroupMessages = async (conversationId, replyMessages) => {
    // 이 재생만의 토큰. 다른 재생이 시작되거나 취소되면 값이 달라져 루프가 멈춘다.
    const myPlaybackId = ++playbackIdRef.current;
    const isCancelled = () => myPlaybackId !== playbackIdRef.current;


    for (const reply of replyMessages) {
      if (isCancelled()) break;

      // 1~2. 현재 캐릭터를 "입력 중" 상태로 표시
      setTypingCharacter({ name: reply.character, image: findImage(reply.character) });

      // 3. 캐릭터가 말하기 전 잠깐 대기(delay_ms)
      await sleep(reply.delayMs ?? 600);
      if (isCancelled()) break;

      // 4. 빈 말풍선을 추가하고, "입력 중" 표시는 말풍선으로 대체(중복 표시 방지)
      const messageId = reply.id || createId();
      setTypingCharacter(null);
      updateConversation(conversationId, (conversation) => {
        // 동일 메시지 중복 추가 방지
        if (conversation.messages.some((m) => m.id === messageId)) return conversation;

        return {
          ...conversation,
          messages: [
            ...conversation.messages,
            {
              id: messageId,
              role: 'assistant',
              character: reply.character,
              content: '',
              intent: reply.intent,
              emotion: reply.emotion,
              movies: [],
              createdAt: reply.createdAt || new Date().toISOString(),
            },
          ],
        };
      });

      // 5. 텍스트를 한 글자씩 채워 넣는다(함수형 업데이트로 최신 상태 기준).
      await typeText({
        text: reply.content,
        isCancelled,
        onUpdate: (partial) => {
          updateMessage(conversationId, messageId, (message) => ({
            ...message,
            content: partial,
          }));
        },
      });
      if (isCancelled()) break;

      // 타이핑이 끝난 메시지에만 추천 영화(있으면)를 붙인다.
      if (reply.movies?.length) {
        updateMessage(conversationId, messageId, (message) => ({
          ...message,
          movies: reply.movies,
        }));
      }

      // 7. 다음 캐릭터가 입력을 시작하기 전 짧은 대기
      await sleep(300);
    }

    // 정상 종료일 때만 상태 정리(취소된 경우엔 다음 재생/취소자가 관리).
    if (!isCancelled()) {
      setTypingCharacter(null);
    }
  };

  const sendMessage = async (contentOverride) => {
    const content = (typeof contentOverride === 'string' ? contentOverride : input).trim();
    if (!content || busy || !activeConversation) return;

    // 이전 그룹 응답이 아직 타이핑 재생 중이면 즉시 중단(출력된 텍스트는 유지)하고
    // 새 사용자 메시지를 이어서 처리한다.
    cancelGroupPlayback();

    const conversationId = activeConversation.id;
    const roomId = activeConversation.roomId;
    const memberNames = members.map((m) => m.name);
    const isGroup = members.length > 1;
    const pendingId = `pending-${crypto.randomUUID()}`;
    const createdAt = new Date().toISOString();

    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: [
        ...conversation.messages,
        { id: crypto.randomUUID(), role: 'user', content, createdAt },
        {
          id: pendingId,
          role: 'assistant',
          content: '',
          character: isGroup ? memberNames.join(', ') : memberNames[0],
          createdAt,
          pending: true,
        },
      ],
    }));

    setInput('');
    setError('');
    setBusy(true);
    stickToBottomRef.current = true;

    const controller = new AbortController();
    abortRef.current = controller;

    const handleStreamChunk = (partialAnswer, payload) => {
      updateMessage(conversationId, pendingId, (message) => ({
        ...message,
        content: partialAnswer,
        character:
          normalizeName(payload?.character || payload?.data?.character) ||
          message.character,
        pending: false,
      }));
    };

    try {
      // 이어 대화는 방 기준, 새 대화는 멤버 수에 따라 1:1(/chat) vs 그룹(/chat/group).
      const history = activeConversation.messages
        .filter((message) => !message.pending && !message.error && !message.localOnly)
        .slice(-10)
        .map((message) => ({
          role: message.role,
          content: String(message.content || '').slice(0, 1000),
          ...(message.character ? { character: message.character } : {}),
          ...(Array.isArray(message.movies) && message.movies.length > 0
            ? { recommended_movies: message.movies }
            : {}),
        }));
      const response = isGroup
        ? await sendChat(
            { mode: 'group', characters: memberNames, message: content, history, guest: !authUser },
            controller.signal
          )
        : authUser && roomId
          ? await sendRoomMessage(
              roomId,
              { message: content, character: memberNames[0], history, guest: !authUser },
              controller.signal,
              handleStreamChunk
            )
          : await sendChat(
              { message: content, character: memberNames[0], history, guest: !authUser },
              controller.signal,
              handleStreamChunk
            );

      if (response?.conversationId) {
        loadedRoomIdsRef.current.add(String(response.conversationId));
        updateConversation(conversationId, (conversation) => ({
          ...conversation,
          roomId: response.conversationId,
        }));
      }

      // 그룹 응답은 라운드별 여러 캐릭터 답변 → 각 답변을 개별 말풍선으로 펼친다.
      // 백엔드가 rounds 대신 rouds를 내려도 api.js에서 response.rounds로 맞춰준다.
      const rounds = Array.isArray(response?.rounds) ? response.rounds : [];
      const replyMessages = [];

      rounds.forEach((round) => {
        const responses = Array.isArray(round?.responses) ? round.responses : [];
        const roundLabel =
          round?.label ||
          (round?.round ? `round ${round.round}` : response?.intent || '');

        responses.forEach((reply) => {
          const character =
            normalizeName(reply?.character || reply?.name) ||
            memberNames[replyMessages.length % memberNames.length] ||
            'AI';

          replyMessages.push({
            id: crypto.randomUUID(),
            role: 'assistant',
            character,
            content: reply?.answer || reply?.content || reply?.message || '',
            createdAt,
            intent: roundLabel,
            emotion: reply?.emotion,
            // 캐릭터가 말하기 전 대기 시간(백엔드가 안 주면 기본값)
            // input_recovery는 api.js가 이미 요청 시작부터 600ms 로딩을 보장한다.
            // 그룹 재생 단계에서 다시 600ms를 더 기다리지 않는다.
            delayMs:
              response?.intent === 'input_recovery'
                ? 0
                : reply?.delay_ms ?? reply?.delayMs ?? 600,
            movies: [],
          });
        });
      });

      if (replyMessages.length === 0) {
        replyMessages.push({
          id: crypto.randomUUID(),
          role: 'assistant',
          character: isGroup ? 'AI' : memberNames[0] || response?.character || 'AI',
          content: response?.answer || '응답 내용이 없습니다.',
          intent: response?.intent,
          createdAt,
          delayMs: 500,
          movies: response?.movies || [],
        });
      } else if (response?.movies?.length) {
        // 첫 번째 라운드의 첫 응답자가 실제 추천자다. 반응만 한 마지막
        // 캐릭터에게 영화 카드가 붙으면 추천 주체가 뒤바뀌어 보인다.
        replyMessages[0].movies = response.movies;
      }

      // 그룹 응답은 여러 캐릭터가 순차적으로 "입력 중 → 한 글자씩" 말하도록 재생한다.
      // (1:1 대화는 기존 방식 그대로 한 번에 반영한다.)
      if (isGroup) {
        // pending(로딩) 말풍선을 제거한 뒤 순차 재생을 시작한다.
        updateConversation(conversationId, (conversation) => ({
          ...conversation,
          messages: conversation.messages.filter((m) => m.id !== pendingId),
        }));

        // 추천받은 영화를 마이페이지 추천과 잇기 위해 저장한다.
        if (authUser) addRecommendedMovies(response?.movies || []);

        // busy를 먼저 풀어, 재생 중에도 사용자가 새 메시지를 보낼 수 있게 한다.
        setBusy(false);
        abortRef.current = null;

        await playGroupMessages(conversationId, replyMessages);
        return;
      }

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [
          ...conversation.messages.filter((m) => m.id !== pendingId),
          ...replyMessages,
        ],
      }));

      // 추천받은 영화를 마이페이지 추천과 잇기 위해 저장한다.
      if (authUser) addRecommendedMovies(response?.movies || []);
    } catch (requestError) {
      const aborted = requestError.name === 'AbortError';
      const errorMessage = aborted ? '응답을 중단했습니다.' : requestError.message;
      setError(aborted ? '' : errorMessage);

      updateMessage(conversationId, pendingId, (message) => ({
        ...message,
        content: message.content || errorMessage,
        pending: false,
        error: !aborted,
      }));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const statusText = error || characterLoadError || '';
  const normalizedPickerQuery = normalizeCharacterSearchText(pickerQuery);
  const pickerCharacters = normalizedPickerQuery
    ? characters.filter((character) => (
        normalizeCharacterSearchText(character.name).includes(normalizedPickerQuery)
        || normalizeCharacterSearchText(character.movieTitle).includes(normalizedPickerQuery)
      ))
    : characters;
  const selectedPickerCharacters = pickedIds
    .map((id) => characters.find((character) => character.id === id))
    .filter(Boolean);

  return (
    <main className="home-variant home3-page group-chat-home-page" aria-label="캐릭터와 대화">
      <div className="group-character-recommended">
        <CharacterDiscoveryRow
          title="추천 캐릭터"
          description="취향과 관심 장르를 바탕으로 먼저 골라봤어요."
          characters={recommendedCharacters}
          onSelect={selectCharacterFromDiscovery}
        />
      </div>

      <section ref={chatStageRef} className={`home3-chat-stage group-chat-home-stage${chatLayoutActive ? ' is-chatting' : ''}${(characterSearchMessages.length > 0 || characterSearchPending) && !canChat ? ' has-character-search' : ''}${isPickerOpen ? ' has-member-picker' : ''}`}>
        {historyOpen ? (
          <aside className="home3-chat-history group-chat-history" aria-label="대화 기록" ref={historyPanelRef}>
            <header>
              <strong>대화 기록</strong>
              <button type="button" onClick={() => { setHistoryOpen(false); setHistoryMenuId(''); }} aria-label="대화 기록 닫기">×</button>
            </header>
            <div className="home3-chat-history__list">
              {historyConversations.map((conversation) => (
                <div className="home3-chat-history__row" key={conversation.id}>
                  <button type="button" onClick={() => {
                    if (conversation.href) {
                      navigateTo(conversation.href);
                      return;
                    }
                    prepareChatActivation();
                    setActiveId(conversation.id);
                    setHistoryOpen(false);
                    setHistoryMenuId('');
                  }}>
                    <strong>{conversation.title}</strong>
                    <time dateTime={conversation.createdAt || undefined}>
                      {formatConversationStartedAt(conversation)}
                    </time>
                  </button>
                  {!conversation.linked ? <div className="home3-chat-history__actions">
                    <button
                      className={`home3-chat-history__pin${conversation.pinned ? ' is-pinned' : ''}`}
                      type="button"
                      onClick={() => toggleConversationPin(conversation)}
                      aria-label={conversation.pinned ? `${conversation.title} 고정 해제` : `${conversation.title} 상단 고정`}
                      title={conversation.pinned ? '고정 해제' : '상단 고정'}
                    >
                      <svg aria-hidden="true" viewBox="0 0 24 24">
                        <path d="m14.8 4.2 5 5-2.4 1.1-3.3 3.3-.4 4-1.2 1.2-3.6-3.6-4.1 4.1-1.1-1.1 4.1-4.1-3.6-3.6 1.2-1.2 4-.4 3.3-3.3 1.1-2.4Z" />
                      </svg>
                    </button>
                    <button
                      className="home3-chat-history__more"
                      type="button"
                      onClick={(event) => {
                        const rect = event.currentTarget.getBoundingClientRect();
                        setHistoryMenuPosition({ top: rect.top, left: rect.right + 12 });
                        setHistoryMenuId((current) => current === conversation.id ? '' : conversation.id);
                      }}
                      aria-label={`${conversation.title} 메뉴`}
                      aria-expanded={historyMenuId === conversation.id}
                    >⋮</button>
                    {historyMenuId === conversation.id ? (
                      <div
                        className="home3-chat-history__menu"
                        ref={historyMoreMenuRef}
                        style={{ top: historyMenuPosition.top, left: historyMenuPosition.left }}
                      >
                        <button type="button" onClick={() => toggleConversationPin(conversation)}>
                          {conversation.pinned ? '고정 해제' : '채팅 고정'}
                        </button>
                        <button type="button" onClick={() => renameConversation(conversation)}>이름 수정</button>
                        <button className="is-danger" type="button" onClick={() => handleDeleteConversation(conversation)}>삭제하기</button>
                      </div>
                    ) : null}
                  </div> : null}
                </div>
              ))}
              {historyConversations.length === 0 ? <p className="home3-chat-history__empty">저장된 대화가 없습니다.</p> : null}
            </div>
          </aside>
        ) : null}

        {isPickerOpen ? (
          <aside className="home3-chat-history group-chat-character-picker" aria-label="캐릭터 선택" ref={characterPickerRef}>
            <header>
              <strong>{pickerMode === 'manage' ? '대화 멤버 관리' : '대화 상대 선택'}</strong>
              <span>{pickedIds.length} / 3</span>
              <button type="button" onClick={() => { setPickerOpen(false); setPickerQuery(''); }} aria-label="캐릭터 선택 닫기">×</button>
            </header>
            <p className="group-chat-character-picker__guide">
              {pickerMode === 'manage'
                ? '추가하거나 제외할 캐릭터를 고른 뒤 변경을 적용해 주세요.'
                : '한 명은 1:1, 두 명 이상은 그룹 대화로 시작돼요.'}
            </p>
            {selectedPickerCharacters.length ? (
              <div className="group-chat-character-picker__selected" aria-label="선택한 캐릭터">
                {selectedPickerCharacters.map((character) => (
                  <button type="button" key={character.id} onClick={() => togglePick(character.id)}>
                    <span>{character.image ? <img src={character.image} alt="" /> : null}</span>
                    <strong>{character.name}</strong>
                    <b aria-hidden="true">×</b>
                  </button>
                ))}
              </div>
            ) : null}
            <label className="group-chat-character-picker__search">
              <span aria-hidden="true">⌕</span>
              <input
                type="search"
                value={pickerQuery}
                onChange={(event) => setPickerQuery(event.target.value)}
                placeholder="캐릭터 또는 영화 이름 검색"
                autoComplete="off"
              />
            </label>
            <div className="group-chat-character-picker__list" onScroll={showScrollbarWhileScrolling}>
              {charactersLoading ? <p className="home3-chat-history__empty">캐릭터를 불러오고 있어요.</p> : pickerCharacters.map((character) => (
                <button
                  type="button"
                  key={character.id}
                  className={pickedIds.includes(character.id) ? 'is-selected' : ''}
                  onClick={() => togglePick(character.id)}
                >
                  <span style={character.image ? undefined : { background: orbGradient(character.name) }}>
                    {character.image ? <img src={character.image} alt="" /> : null}
                  </span>
                  <strong>{character.name}</strong>
                </button>
              ))}
              {!charactersLoading && pickerCharacters.length === 0 ? (
                <p className="home3-chat-history__empty">일치하는 캐릭터가 없습니다.</p>
              ) : null}
            </div>
            <button
              className="group-chat-character-picker__done"
              type="button"
              onClick={pickerMode === 'manage' ? applyMemberChanges : confirmPicker}
              disabled={!pickedIds.length || busy || Boolean(typingCharacter)}
            >
              {pickedIds.length
                ? pickerMode === 'manage' ? '변경 적용' : `선택한 ${pickedIds.length}명과 대화 시작`
                : '최소 한 명을 선택해 주세요'}
            </button>
          </aside>
        ) : null}

        <header>
          <h1>{canChat ? `${activeName}와 이야기해볼까요?` : '영화 속 캐릭터와 대화해보세요.'}</h1>
          <p>{canChat ? activeSubText : '좋아하는 캐릭터를 선택하고 자유롭게 이야기를 시작해보세요.'}</p>
        </header>

        <div className="home3-chat-stage__conversation">
          {chatLayoutActive ? (
            <div className="group-chat-member-bar" aria-label="현재 대화 멤버">
              <div className="group-chat-member-bar__people">
                <div className="group-chat-member-bar__avatars" aria-hidden="true">
                  {(canChat ? members : [{ id: 'mumu-search', name: '무무', image: MUMU_DEFAULT_IMAGE }]).slice(0, 3).map((member) => (
                    <span className={member.name === '무무' ? 'is-mumu' : ''} key={member.id}>{member.image ? <img src={member.image} alt="" /> : null}</span>
                  ))}
                </div>
                <div>
                  <strong>{canChat ? members.map((member) => member.name).join(' · ') : '무무'}</strong>
                  <small>{canChat ? (members.length > 1 ? `${members.length}명이 함께 대화 중` : '1:1 대화 중') : '대화할 캐릭터 검색 중'}</small>
                </div>
              </div>
              <button
                type="button"
                onClick={() => openCharacterPicker(canChat ? 'manage' : 'new')}
                disabled={busy || Boolean(typingCharacter)}
              >멤버 관리</button>
            </div>
          ) : null}
          {(characterSearchMessages.length > 0 || characterSearchPending) && !canChat ? (
            <div className="group-character-search-answer" ref={searchMessagesRef} aria-live="polite" onScroll={showScrollbarWhileScrolling}>
              {characterSearchMessages.map((message) => {
                const isUser = message.role === 'user';
                const result = message.searchResult;
                return (
                  <div className={`home-variant-message is-${message.role}`} key={message.id}>
                    {!isUser ? (
                      <span className="home-variant-message__avatar">
                        <img src={MUMU_DEFAULT_IMAGE} alt="" />
                      </span>
                    ) : null}
                    <div className="home-variant-message__body">
                      {!isUser ? <span className="home-variant-message__name">무무</span> : null}
                      <p>{message.content}</p>
                      {result?.matches?.length > 0 ? (
                        <div className="group-character-search-answer__results">
                          {result.matches.map((character) => (
                            <button
                              type="button"
                              key={character.id}
                              onClick={() => startSingleCharacterConversation(character, {
                                includeSearchHistory: true,
                                mumuMessage: `좋아요. ${withObjectParticle(character.name)} 불러볼게요.\n포스터를 눌러 원하는 캐릭터를 추가하거나 멤버 관리를 통해 단체 대화를 시작해보세요.`,
                              })}
                            >
                              <span>{character.image ? <img src={character.image} alt="" /> : null}</span>
                              <strong>{character.name}</strong>
                              <small>{character.movieTitle || '출연 영화 정보 없음'}</small>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
              {characterSearchPending ? (
                <div className="home-variant-message is-assistant">
                  <span className="home-variant-message__avatar">
                    <img src={MUMU_DEFAULT_IMAGE} alt="" />
                  </span>
                  <div className="home-variant-message__body">
                    <span className="home-variant-message__name">무무</span>
                    <div className="home-variant-message__typing" role="status" aria-label="캐릭터를 찾고 있습니다"><span /><span /><span /></div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {messages.length > 0 || typingCharacter ? (
            <div className="home-variant-chat__messages" ref={messagesRef} aria-live="polite" onScroll={showScrollbarWhileScrolling}>
              {messages.map((message) => {
                if (message.memberChange) {
                  return <div className="group-chat-member-event" key={message.id}>{message.content}</div>;
                }
                const isUser = message.role === 'user';
                const avatarImage = isUser ? '' : findImage(message.character);
                return (
                  <div className={`home-variant-message is-${message.role}${message.error ? ' is-error' : ''}`} key={message.id}>
                    {!isUser ? (
                      <span className="home-variant-message__avatar">
                        {avatarImage ? <img src={avatarImage} alt="" /> : null}
                      </span>
                    ) : null}
                    <div className="home-variant-message__body">
                      {!isUser ? <span className="home-variant-message__name">{message.character || 'AI'}</span> : null}
                      {message.pending ? (
                        <div className="home-variant-message__typing" role="status" aria-label="응답을 준비하고 있습니다"><span /><span /><span /></div>
                      ) : <p>{message.content || '답변을 기다리는 중...'}</p>}
                      {message.selectedCharacter ? (
                        <div className="group-chat-preserved-character" aria-label={`${message.selectedCharacter.name} 캐릭터`}>
                          <span>{message.selectedCharacter.image ? <img src={message.selectedCharacter.image} alt="" /> : null}</span>
                          <strong>{message.selectedCharacter.name}</strong>
                          <small>{message.selectedCharacter.movieTitle || '출연 영화 정보 없음'}</small>
                        </div>
                      ) : null}
                      <ChatMovieRecommendations movies={message.movies} />
                    </div>
                  </div>
                );
              })}
              {typingCharacter ? (
                <div className="home-variant-message is-assistant">
                  <span className="home-variant-message__avatar">{typingCharacter.image ? <img src={typingCharacter.image} alt="" /> : null}</span>
                  <div className="home-variant-message__body">
                    <span className="home-variant-message__name">{typingCharacter.name || 'AI'}</span>
                    <div className="home-variant-message__typing" role="status"><span /><span /><span /></div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="home3-prompt-area" ref={promptAreaRef}>
            <form className="home3-prompt" onSubmit={(event) => {
              event.preventDefault();
              if (busy) abortRef.current?.abort();
              else if (canChat) sendMessage();
              else if (input.trim()) {
                if (!searchChatActive) {
                  prepareChatActivation();
                  setSearchChatActive(true);
                }
                void searchCharacterBeforeChat();
              }
            }}>
              <button ref={promptAddButtonRef} className="home3-prompt__add" type="button" aria-label="채팅 메뉴 열기" aria-expanded={promptMenuOpen} onClick={() => setPromptMenuOpen((current) => !current)}>+</button>
              {promptMenuOpen ? (
                <div className="home3-prompt-menu" ref={promptMenuRef}>
                  <button type="button" onClick={() => navigateTo('/home')}>무무와 새 채팅</button>
                  <button type="button" onClick={returnToCharacterSearch}>캐릭터와 새 채팅</button>
                  <button type="button" onClick={() => { setHistoryOpen(true); setPromptMenuOpen(false); }}>대화 기록</button>
                  <button
                    type="button"
                    className="home3-prompt-menu__image"
                    data-tooltip="이미지 첨부 기능은 준비중이에요."
                    onClick={() => { photoInputRef.current?.click(); setPromptMenuOpen(false); }}
                  >이미지 첨부</button>
                </div>
              ) : null}
              <input className="home3-photo-input" type="file" accept="image/*" ref={photoInputRef} onChange={(event) => setPhotoName(event.target.files?.[0]?.name || '')} />
              <input
                aria-label={canChat ? `${activeName}에게 메시지 보내기` : '대화할 캐릭터 검색하기'}
                autoComplete="off"
                placeholder={canChat
                  ? members.length > 1
                    ? '캐릭터들과 나누고 싶은 이야기를 입력해보세요.'
                    : `${activeName}에게 말을 걸어보세요.`
                  : '+ 버튼을 눌러 대화기록을 불러오거나, 원하는 캐릭터를 검색해보세요.'}
                value={input}
                onChange={(event) => {
                  const nextInput = event.target.value;
                  setInput(nextInput);
                }}
                aria-busy={busy}
              />
              <button className="home3-prompt__voice-input" type="button" aria-label="음성 인식 기능 준비 중" data-tooltip="음성 인식은 준비 중이에요">
                <svg aria-hidden="true" viewBox="0 0 24 24"><rect x="8.5" y="3" width="7" height="12" rx="3.5" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M8.5 21h7" /></svg>
              </button>
              <button className="home3-prompt__voice-chat" type="button" aria-label="AI 음성 대화 기능 준비 중" data-tooltip="AI 음성 대화는 준비 중이에요">
                <svg aria-hidden="true" viewBox="0 0 28 28"><path d="M5 11v6M9.5 7v14M14 10v8M18.5 5v18M23 11v6" /></svg>
              </button>
            </form>
            {photoName ? (
              <div className="home3-photo-chip"><span>{photoName}</span><small>이미지 분석 API 연결 전</small><button type="button" onClick={() => setPhotoName('')} aria-label="첨부 사진 제거">×</button></div>
            ) : null}
            {statusText ? <p className="home3-prompt-status" role="status">{statusText}</p> : null}
          </div>

          <GuestChatNotice
            showGuestMessage={!authUser}
            hidden={searchChatActive || messages.length > 0 || characterSearchMessages.length > 0 || characterSearchPending}
            mode="group"
            onGroupStart={openGroupConversationSetup}
            onSuggestionSelect={(suggestion) => {
              setInput(suggestion);
              window.requestAnimationFrame(() => {
                promptAreaRef.current?.querySelector('input:not([type="file"])')?.focus();
              });
            }}
          />
        </div>
      </section>

      <div className="group-character-genres" aria-label="장르별 캐릭터">
        {characterGenreGroups.map((group) => (
          <CharacterDiscoveryRow
            key={group.genre}
            title={group.genre}
            characters={group.characters}
            onSelect={selectCharacterFromDiscovery}
          />
        ))}
      </div>
    </main>
  );
}

export default GroupChatPage;
