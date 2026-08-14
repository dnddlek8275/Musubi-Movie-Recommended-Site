import { useEffect, useMemo, useRef, useState } from 'react';

import {
  addRecommendedMovies,
  checkBackendHealth,
  checkAiHealth,
  checkDbHealth,
  fetchCharacters,
  fetchChatRoomMessages,
  sendCharacterChatStream,
  sendChat,
  sendRoomMessage,
} from '../../api.js';

import './chat.css';
import SttMicButton from './SttMicButton.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import { formatRating } from '../../utils/formatRating.js';

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';
const TTS_BASE_URL = (
  import.meta.env.VITE_TTS_BASE_URL || 'http://127.0.0.1:5001'
).replace(/\/+$/, '');
const TTS_FEATURE_ENABLED = import.meta.env.VITE_TTS_ENABLED === 'true';

// 필요할 때 캐릭터별 재생 피치/속도 프로필을 추가한다.
const CHARACTER_PLAYBACK_PROFILES = {};
const CHARACTER_TTS_VOICES = {};

function getCharacterPlaybackProfile(character) {
  const normalizedName = String(character || '').replace(/\s+/g, '');
  return CHARACTER_PLAYBACK_PROFILES[normalizedName] || {
    playbackRate: 1,
    preservePitch: true,
  };
}

function getCharacterTtsVoice(character) {
  const normalizedName = String(character || '').replace(/\s+/g, '');
  return CHARACTER_TTS_VOICES[normalizedName] || 'chatai';
}

const CHAT_ROOMS_STORAGE_KEY = 'cineverse.chat.rooms'; // { [characterId]: roomId }
const CHAT_PARTNERS_STORAGE_KEY = 'cineverse.chat.partners'; // [characterId, ...] (추가한 순서)
const CHAT_GROUP_MEMBERS_STORAGE_KEY = 'cineverse.chat.group.members'; // [characterId, ...]
const TTS_ENABLED_STORAGE_KEY = 'cineverse.chat.tts.enabled';

// 1:1 대화(menu1, /chat)와 그룹 대화(menu2, /chat/group)는 같은 UI를 쓰되,
// 그룹 대화는 대화방을 개별 캐릭터가 아니라 이 고정 키 하나로 묶어서 관리한다.
const GROUP_KEY = '__group__';

// 하단 입력창 위 빠른 프롬프트 탭
const QUICK_TABS = [
  ['오늘의 기분', null],
  ['장르 추천', null],
  ['자동추천', '내 취향대로 아무거나 골라줘'],
];

// "오늘의 기분" 클릭 시 펼쳐지는 이모티콘 선택 패널
const MOOD_OPTIONS = [
  { emoji: '😊', label: '좋아요', prompt: '오늘 기분이 좋아! 신나는 영화 추천해줘' },
  { emoji: '😒', label: '시큰둥', prompt: '오늘 좀 시큰둥해... 그냥 볼만한 영화 없을까' },
  { emoji: '😔', label: '힘들다', prompt: '힘들다... 위로가 되는 영화 추천해 줘' },
  { emoji: '🤔', label: '고민중', prompt: '뭘 볼지 고민되는데 추천해줘' },
  { emoji: '🤨', label: '의심반', prompt: '그냥 아무거나 재밌는 거 추천해줘' },
  { emoji: '😫', label: '지쳤어', prompt: '너무 지쳤어... 가볍게 볼 수 있는 영화 추천해줘' },
  { emoji: '😡', label: '화나요', prompt: '열받아 죽겠어! 스트레스 풀리는 영화 추천해줘' },
];

// "장르 추천" 클릭 시 펼쳐지는 해시태그 선택 패널
const GENRE_TAGS = [
  '액션', '드라마', '로맨스', 'SF', '공포', '코미디', '스릴러', '애니메이션',
];

// 입력창(textarea)이 자동으로 늘어날 수 있는 최대 높이(px). 이 높이를 넘으면
// 더 늘리지 않고 내부 스크롤을 허용한다(화면을 다 차지하지 않도록).
const MAX_COMPOSER_HEIGHT = 168;

const formatTime = (value) =>
  new Intl.DateTimeFormat('ko-KR', {
    // 항상 두 자리로 표시
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));

// 이미지가 없는 캐릭터를 위한 그라디언트 아바타(이름 해시 → 색상)
function orbGradient(seed) {
  const text = String(seed || '무스비');
  let hue = 0;
  for (let i = 0; i < text.length; i += 1) {
    hue = (hue * 31 + text.charCodeAt(i)) % 360;
  }
  return `radial-gradient(circle at 34% 28%, hsl(${hue} 70% 78%) 0%, hsl(${hue} 55% 48%) 24%, hsl(${hue} 60% 28%) 52%, hsl(${hue} 65% 12%) 100%)`;
}

function toPosterUrl(value) {
  const path = String(value || '').trim();

  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function getChatMoviePoster(movie) {
  return toPosterUrl(
    movie?.posterUrl ||
      movie?.poster_url ||
      movie?.poster_path ||
      movie?.poster ||
      movie?.image_url ||
      movie?.image ||
      ''
  );
}

// DB/API에서 받아온 캐릭터 데이터를 프론트에서 쓰기 좋은 형태로 정리하는 함수
function normalizeCharacter(rawCharacter, index) {
  const name = String(
    rawCharacter?.name || rawCharacter?.character || ''
  ).trim();

  if (!name) return null;

  return {
    id: String(rawCharacter?.id ?? rawCharacter?.character_id ?? name ?? index),
    name,
    image:
      rawCharacter?.image ||
      rawCharacter?.image_url ||
      rawCharacter?.avatar_url ||
      '',
  };
}

function ChatPage({ authUser }) {
  // menu1(/chat)은 1:1, menu2(/chat/group)는 동일한 UI에서 1:다 그룹 대화
  const isGroupMode = window.location.pathname.startsWith('/chat/group');

  // 메인 화면에서 캐릭터를 클릭해 들어온 경우, 어떤 캐릭터와 바로 대화를
  // 시작할지 쿼리(?characterId / ?characterName)로 넘어온다. 한 번만 소비한다.
  const initialTargetRef = useRef(null);
  if (initialTargetRef.current === null) {
    const params = new URLSearchParams(window.location.search);
    initialTargetRef.current = {
      id: params.get('characterId') || '',
      name: params.get('characterName') || '',
      room: params.get('room') || '',
      consumed: false,
    };
  }

  const [characters, setCharacters] = useState([]);
  const [characterLoadError, setCharacterLoadError] = useState('');
  const [charactersLoading, setCharactersLoading] = useState(true);

  // 대화 상대(파트너) 목록: + 버튼으로 추가한 캐릭터 id만 사이드바에 보여준다 (1:1 모드)
  // 대화 상대/채팅방 정보는 로컬에 저장하지 않는다. 다른 페이지로 나갔다 오면
  // 사이드바는 항상 새 창처럼 비어 있고, 실제 대화 기록은 DB에만 남는다.
  const [partnerIds, setPartnerIds] = useState([]);

  // 그룹 대화 멤버 목록 (그룹 모드) — 전원이 하나의 대화방을 공유한다
  const [groupMemberIds, setGroupMemberIds] = useState([]);

  const [isPickerOpen, setPickerOpen] = useState(false);

  const [selectedCharacterId, setSelectedCharacterId] = useState('');

  // 캐릭터별 채팅방 id / 메시지 내역 (캐릭터를 바꿔도 서로 대화 내용이 섞이지 않도록 분리 보관)
  // 이 페이지에 머무는 동안에만 유지되는 메모리 상태(로컬 저장 안 함).
  const [roomIdByCharacter, setRoomIdByCharacter] = useState({});
  const [messagesByCharacter, setMessagesByCharacter] = useState({});
  const [loadingRoomKey, setLoadingRoomKey] = useState('');

  const [connectionStatus, setConnectionStatus] = useState({
    backend: '확인 중',
    ai: '확인 중',
    db: '확인 중',
  });
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('');
  const [activePicker, setActivePicker] = useState(null); // 'mood' | 'genre' | null
  const [ttsSupported, setTtsSupported] = useState(TTS_FEATURE_ENABLED);
  const [ttsEnabled, setTtsEnabled] = useState(
    () =>
      TTS_FEATURE_ENABLED &&
      window.localStorage.getItem(TTS_ENABLED_STORAGE_KEY) === 'true'
  );
  const [speakingMessageId, setSpeakingMessageId] = useState('');
  const [speechRate, setSpeechRate] = useState(1);

  const messagesRef = useRef(null);
  const textareaRef = useRef(null);
  const charlistRef = useRef(null);
  const pickerInnerRef = useRef(null);
  const pickerRef = useRef(null);
  const quickPickerRef = useRef(null);
  const composingRef = useRef(false);
  const abortRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const audioRef = useRef(null);
  const audioUrlRef = useRef('');
  const ttsAbortRef = useRef(null);

  // grid-template-rows: 0fr/1fr, max-height 트랜지션 모두 이 사이드바 안에서는
  // (스크롤 컨테이너 + flex 자식 조합 때문에) 제대로 펼쳐지지 않아서,
  // 실측 픽셀 높이를 직접 재서 애니메이션한다.
  const [pickerHeight, setPickerHeight] = useState(0);

  // 글이 길어지면 textarea 안에서 스크롤되는 대신, 박스 높이 자체가 늘어나도록 함.
  // 단, 최대 높이까지만 늘리고 그 이상은 내부 스크롤로 처리한다.
  const resizeTextarea = (textarea) => {
    if (!textarea) return;

    textarea.style.height = 'auto';
    const nextHeight = Math.min(textarea.scrollHeight, MAX_COMPOSER_HEIGHT);
    textarea.style.height = `${nextHeight}px`;
    // 최대 높이 안에서는 스크롤바를 숨겨 깔끔하게, 넘칠 때만 스크롤 허용
    textarea.style.overflowY =
      textarea.scrollHeight > MAX_COMPOSER_HEIGHT ? 'auto' : 'hidden';
  };

  const partners = useMemo(
    () =>
      partnerIds
        .map((id) => characters.find((character) => character.id === id))
        .filter(Boolean),
    [characters, partnerIds]
  );

  const availableToAdd = useMemo(
    () => characters.filter((character) => !partnerIds.includes(character.id)),
    [characters, partnerIds]
  );

  const selectedCharacter = partners.find(
    (character) => character.id === selectedCharacterId
  );

  // 그룹 모드에서의 멤버 목록 / 아직 추가 안 한 캐릭터 목록
  const groupMembers = useMemo(
    () =>
      groupMemberIds
        .map((id) => characters.find((character) => character.id === id))
        .filter(Boolean),
    [characters, groupMemberIds]
  );

  const groupAvailableToAdd = useMemo(
    () =>
      characters.filter((character) => !groupMemberIds.includes(character.id)),
    [characters, groupMemberIds]
  );

  const groupLabel = groupMembers.map((character) => character.name).join(', ');

  // 1:1 모드는 선택된 캐릭터별로, 그룹 모드는 고정된 GROUP_KEY 하나로 대화를 구분
  const activeKey = isGroupMode ? GROUP_KEY : selectedCharacterId;
  const canChat = isGroupMode ? groupMembers.length > 0 : Boolean(selectedCharacter);

  // 상단바/빈 상태/아바타 등에 공통으로 쓰는, 모드에 따라 달라지는 표시용 값
  const activeName = isGroupMode
    ? groupLabel || '그룹 멤버를 추가해보세요'
    : selectedCharacter?.name || '?';
  const activeAvatarImage = isGroupMode
    ? groupMembers[0]?.image
    : selectedCharacter?.image;
  const activeSubText = isGroupMode
    ? groupMembers.length > 0
      ? `${groupMembers.length}명 그룹 대화 · AI 대화`
      : '멤버를 추가하면 그룹 대화가 시작됩니다'
    : '영화 속 캐릭터 · AI 대화';

  const messages = activeKey
    ? messagesByCharacter[activeKey] || []
    : [];

  // 이전 방문 때 로컬에 남아 있던 대화 상대/채팅방 정보를 정리한다.
  // (이제 이 정보들은 로컬에 저장하지 않으므로, 예전 데이터만 한 번 비워준다.)
  useEffect(() => {
    [
      CHAT_ROOMS_STORAGE_KEY,
      CHAT_PARTNERS_STORAGE_KEY,
      CHAT_GROUP_MEMBERS_STORAGE_KEY,
    ].forEach((key) => window.localStorage.removeItem(key));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(TTS_ENABLED_STORAGE_KEY, String(ttsEnabled));
  }, [ttsEnabled]);

  // 화면 처음 열림 → 백엔드/AI/DB 헬스체크
  useEffect(() => {
    const controller = new AbortController();
    setCharactersLoading(true);
    const updateStatus = (key, value) => {
      setConnectionStatus((current) => ({
        ...current,
        [key]: value,
      }));
    };

    checkBackendHealth(controller.signal)
      .then(() => updateStatus('backend', '정상'))
      .catch((statusError) => {
        if (statusError.name === 'AbortError') return;
        updateStatus('backend', statusError.message);
      });

    checkAiHealth(controller.signal)
      .then(() => updateStatus('ai', '정상'))
      .catch((statusError) => {
        if (statusError.name === 'AbortError') return;
        updateStatus('ai', statusError.message);
      });

    checkDbHealth(controller.signal)
      .then(() => updateStatus('db', '정상'))
      .catch((statusError) => {
        if (statusError.name === 'AbortError') return;
        updateStatus('db', statusError.message);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    fetchCharacters(controller.signal)
      .then((data) => {
        const characterList = Array.isArray(data)
          ? data
          : Array.isArray(data?.data)
            ? data.data
            : Array.isArray(data?.characters)
              ? data.characters
              : [];

        const dbCharacters = characterList
          .map(normalizeCharacter)
          .filter(Boolean);

        setCharacters(dbCharacters);
        setCharacterLoadError(
          dbCharacters.length === 0 ? 'DB에 캐릭터 데이터가 없습니다.' : ''
        );

        // 기본 캐릭터를 자동으로 넣지 않는다.
        // 메인에서 캐릭터를 클릭해 들어온 경우에만 해당 캐릭터가 상대로 추가된다.
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;

        console.error('캐릭터 불러오기 실패:', fetchError);

        setCharacterLoadError(fetchError.message);
        setCharacters([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setCharactersLoading(false);
      });

    return () => controller.abort();
  }, []);

  // 메인에서 캐릭터를 클릭해 넘어온 경우: 캐릭터 목록을 받아오면 해당 캐릭터를
  // 대화 상대로 추가하고 바로 선택한다(그룹 모드는 제외). 최초 1회만 동작한다.
  useEffect(() => {
    if (isGroupMode) return;

    const target = initialTargetRef.current;
    if (!target || target.consumed || (!target.id && !target.name)) return;
    if (characters.length === 0) return;

    const matched = characters.find(
      (character) =>
        (target.id && character.id === target.id) ||
        (target.name && character.name === target.name)
    );

    if (!matched) return;

    target.consumed = true;
    setPartnerIds((current) =>
      current.includes(matched.id) ? current : [...current, matched.id]
    );
    setSelectedCharacterId(matched.id);

    // 마이페이지에서 ?room=<id> 로 이어보기로 들어온 경우, 해당 캐릭터에 방을 연결하면
    // 아래의 메시지 로드 useEffect가 그 방의 지난 대화를 불러와 이어서 대화할 수 있다.
    if (target.room) {
      setRoomIdByCharacter((current) => ({ ...current, [matched.id]: target.room }));
    }
  }, [characters, isGroupMode]);

  // 파트너 목록이 바뀌면 선택된 상대가 없을 때 첫 번째 파트너를 선택 (1:1 모드)
  useEffect(() => {
    setSelectedCharacterId((current) =>
      current && partnerIds.includes(current) ? current : partnerIds[0] || ''
    );
  }, [partnerIds]);

  // 현재 활성화된 대화(1:1이면 선택된 캐릭터, 그룹이면 GROUP_KEY)가 바뀌면
  // 아직 불러온 적 없는 채팅방 메시지를 가져온다
  useEffect(() => {
    if (!activeKey) return undefined;

    stickToBottomRef.current = true;

    const roomId = authUser ? roomIdByCharacter[activeKey] : '';
    if (!roomId || messagesByCharacter[activeKey]) return undefined;

    const controller = new AbortController();
    setLoadingRoomKey(activeKey);

    fetchChatRoomMessages(roomId, controller.signal)
      .then((roomMessages) => {
        setMessagesByCharacter((current) => ({
          ...current,
          [activeKey]:
            current[activeKey] ||
            roomMessages.map((message, index) => ({
              id: `room-${roomId}-${index}-${message.created_at || crypto.randomUUID()}`,
              role: message.role === 'assistant' ? 'assistant' : 'user',
              content: message.content || '',
              character: message.character || 'AI',
              movies: message.recommended_movies || message.movies || message.movie || [],
              createdAt: message.created_at || new Date().toISOString(),
            })),
        }));
      })
      .catch((roomError) => {
        if (roomError.name === 'AbortError') return;
        console.warn('채팅방 메시지 불러오기 실패:', roomError);

        setRoomIdByCharacter((current) => {
          const next = { ...current };
          delete next[activeKey];
          return next;
        });
      })
      .finally(() => {
        setLoadingRoomKey((current) => (current === activeKey ? '' : current));
      });

    return () => controller.abort();
  }, [activeKey, roomIdByCharacter, messagesByCharacter]);

  // 스크롤 위치 추적: 사용자가 위로 스크롤해서 올려봤으면 자동으로 하단 고정하지 않음
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
  }, [messages, activeKey]);

  // input 값이 바뀔 때마다(직접 타이핑 + 빠른 탭 자동 입력 모두) 입력창 높이 재계산
  useEffect(() => {
    resizeTextarea(textareaRef.current);
  }, [input]);

  // OpenVoice V2가 반환한 WAV를 브라우저 Audio로 재생한다.
  useEffect(() => {
    const supported = typeof window !== 'undefined' && 'Audio' in window;
    setTtsSupported(supported);

    return () => {
      ttsAbortRef.current?.abort();
      audioRef.current?.pause();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  const stopSpeaking = () => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = '';
    setSpeakingMessageId('');
  };

  const speakMessage = async (message) => {
    if (
      !ttsSupported ||
      !ttsEnabled ||
      message?.role !== 'assistant' ||
      !message?.content ||
      message?.error
    ) return;

    if (speakingMessageId === message.id) {
      stopSpeaking();
      return;
    }

    stopSpeaking();
    const controller = new AbortController();
    const playbackProfile = getCharacterPlaybackProfile(
      message.character || activeName
    );
    const ttsVoice = getCharacterTtsVoice(message.character || activeName);
    ttsAbortRef.current = controller;
    setSpeakingMessageId(message.id);

    try {
      const response = await fetch(`${TTS_BASE_URL}/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: message.content,
          character: message.character || activeName || 'AI',
          voice: ttsVoice,
          // 낮춘 재생 속도만큼 합성을 먼저 빠르게 해 최종 발화 길이를 유지한다.
          rate: speechRate / playbackProfile.playbackRate,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `OpenVoice V2 TTS 오류 (${response.status})`);
      }

      const audioUrl = URL.createObjectURL(await response.blob());
      const audio = new Audio(audioUrl);
      audio.playbackRate = playbackProfile.playbackRate;
      audio.preservesPitch = playbackProfile.preservePitch;
      audio.webkitPreservesPitch = playbackProfile.preservePitch;
      audioUrlRef.current = audioUrl;
      audioRef.current = audio;
      audio.onended = stopSpeaking;
      audio.onerror = () => {
        setError('OpenVoice V2 음성을 재생할 수 없습니다.');
        stopSpeaking();
      };
      await audio.play();
    } catch (ttsError) {
      if (ttsError.name !== 'AbortError') {
        setError(`${ttsError.message} — OpenVoice V2 서버가 실행 중인지 확인하세요.`);
      }
      stopSpeaking();
    }
  };

  const cycleSpeechRate = () => {
    const rates = [0.8, 1, 1.2];
    const currentIndex = rates.indexOf(speechRate);
    setSpeechRate(rates[(currentIndex + 1) % rates.length]);
    stopSpeaking();
  };

  const toggleTts = () => {
    setTtsEnabled((current) => {
      if (current) stopSpeaking();
      return !current;
    });
  };

  const updateMessage = (characterId, id, updater) => {
    setMessagesByCharacter((current) => ({
      ...current,
      [characterId]: (current[characterId] || []).map((message) =>
        message.id === id ? updater(message) : message
      ),
    }));
  };

  const setRoomId = (characterId, roomId) => {
    setRoomIdByCharacter((current) => ({ ...current, [characterId]: roomId }));
  };

  const sendMessage = async (contentOverride) => {
    const content = (typeof contentOverride === 'string' ? contentOverride : input).trim();

    if (!content || busy || !canChat) return;

    // 1:1이면 상대 캐릭터 이름 하나, 그룹이면 멤버 이름 전부를 채팅 요청에 실어보낸다
    const memberNames = isGroupMode
      ? groupMembers.map((character) => character.name)
      : [selectedCharacter.name];
    const replyLabel = isGroupMode ? groupLabel : selectedCharacter.name;

    const pendingId = `pending-${crypto.randomUUID()}`;
    const createdAt = new Date().toISOString();

    const history = (messagesByCharacter[activeKey] || [])
      .filter((message) => !message.pending && !message.error)
      .slice(-10)
      .map(({ role, content: messageContent, movies }) => ({
        role,
        content: String(messageContent || '').slice(0, 1000),
        ...(Array.isArray(movies) && movies.length > 0
          ? { recommended_movies: movies }
          : {}),
      }));

    setMessagesByCharacter((current) => ({
      ...current,
      [activeKey]: [
        ...(current[activeKey] || []),
        {
          id: crypto.randomUUID(),
          role: 'user',
          content,
          createdAt,
        },
        {
          id: pendingId,
          role: 'assistant',
          content: '',
          character: replyLabel,
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

    const roomId = authUser ? roomIdByCharacter[activeKey] : '';

    try {
      const chatRequest = isGroupMode
        ? {
            mode: 'group',
            message: content,
            history,
            characters: memberNames,
            room_type: 'group',
            guest: !authUser,
          }
        : {
            mode: 'auto',
            message: content,
            history,
            character: replyLabel,
            characters: memberNames,
            room_type: 'character',
            guest: !authUser,
          };

      const response = !isGroupMode
        ? await sendCharacterChatStream(
            { ...chatRequest, roomId },
            controller.signal,
            (partialAnswer, payload) => {
              updateMessage(activeKey, pendingId, (current) => ({
                ...current,
                content: partialAnswer,
                character:
                  payload?.character ||
                  payload?.data?.character ||
                  current.character,
                pending: false,
              }));
            }
          )
        : roomId
          ? await sendRoomMessage(roomId, chatRequest, controller.signal)
          : await sendChat(chatRequest, controller.signal);

      if (response?.conversationId) {
        setRoomId(activeKey, response.conversationId);
      }

      const finalAnswer = response?.answer || '응답 내용이 없습니다.';
      const finalCharacter = response?.character || replyLabel;

      const finalMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: finalAnswer,
        character: finalCharacter,
        intent: response?.intent,
        movies: response?.movies || [],
        sources: response?.sources || [],
        createdAt,
        pending: false,
      };

      updateMessage(activeKey, pendingId, (current) => ({
        ...current,
        ...finalMessage,
      }));

      // TTS가 켜져 있을 때 방금 완료된 AI 답변만 자동 재생한다.
      if (ttsEnabled) void speakMessage(finalMessage);

      // 추천받은 영화를 마이페이지 추천과 잇기 위해 저장한다.
      if (authUser) addRecommendedMovies(response?.movies || []);
    } catch (requestError) {
      const aborted = requestError.name === 'AbortError';
      const errorMessage = aborted
        ? '응답을 중단했습니다.'
        : requestError.message;

      setError(aborted ? '' : errorMessage);

      updateMessage(activeKey, pendingId, (current) => ({
        ...current,
        content: current.content || errorMessage,
        pending: false,
        error: !aborted,
      }));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  // 지금 대화(1:1 상대 또는 그룹)만 초기화 (다른 대화는 그대로 유지)
  const clearMessages = () => {
    if (!activeKey) return;

    abortRef.current?.abort();
    stopSpeaking();

    setMessagesByCharacter((current) => {
      const next = { ...current };
      delete next[activeKey];
      return next;
    });

    setRoomIdByCharacter((current) => {
      const next = { ...current };
      delete next[activeKey];
      return next;
    });

    setInput('');
    setError('');
    setBusy(false);
  };

  useEffect(() => {
    if (!isPickerOpen) return;

    setPickerHeight(pickerInnerRef.current?.scrollHeight || 0);
  }, [isPickerOpen, availableToAdd.length]);

  // pickerHeight가 실제로 DOM에 반영된 다음(=re-render 이후)에만 리플로우 강제 + 스크롤 실행
  useEffect(() => {
    if (!isPickerOpen) return;

    // 브라우저가 새로 적용된 max-height를 바로 레이아웃에 반영하지 않는 경우가 있어
    // display를 한 번 껐다 켜서 강제로 리플로우시킨다.
    const picker = pickerRef.current;
    if (picker) {
      picker.style.display = 'none';
      void picker.offsetHeight;
      picker.style.display = '';
    }

    charlistRef.current?.scrollTo({
      top: charlistRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [isPickerOpen, pickerHeight]);

  // "오늘의 기분"/"장르 추천" 패널도 같은 이유로 max-height 트랜지션이 바로
  // 반영되지 않아, display를 껐다 켜서 강제로 리플로우시킨다.
  useEffect(() => {
    if (!activePicker) return;

    const picker = quickPickerRef.current;
    if (!picker) return;

    picker.style.display = 'none';
    void picker.offsetHeight;
    picker.style.display = '';
  }, [activePicker]);

  const togglePicker = () => {
    setPickerOpen((current) => !current);
  };

  const addPartner = (character) => {
    setPartnerIds((current) =>
      current.includes(character.id) ? current : [...current, character.id]
    );
    setSelectedCharacterId(character.id);
    setPickerOpen(false);
  };

  // 그룹 모드에서는 멤버를 껐다 켰다 할 수 있어야 해서(다중 선택), 클릭할 때마다
  // 패널을 닫지 않고 토글만 한다 — 여러 명을 연달아 추가/제외할 수 있음
  const toggleGroupMember = (character) => {
    setGroupMemberIds((current) =>
      current.includes(character.id)
        ? current.filter((id) => id !== character.id)
        : [...current, character.id]
    );
  };

  const canSend = Boolean(input.trim() && canChat && !busy);

  const statusText = error || characterLoadError || '';

  const stopIcon = (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="2" />
    </svg>
  );

  return (
    <main className="chat-page" aria-label="ChatwithAI">
      {!authUser ? (
        <p className="chat-guest-notice">
          비회원 캐릭터 대화는 하루 10회이며 대화와 추천 결과가 저장되지 않습니다. 페이지를 나가면 초기화됩니다.
        </p>
      ) : null}
      <div className="chat-layout">
        {/* 좌측: 대화 상대 목록 */}
        <aside className="chat-sidebar">
          <div className="chat-sidebar__head">
            <span>{isGroupMode ? '그룹 멤버' : '대화 상대'}</span>
            <button
              type="button"
              className={`chat-sidebar__new ${isPickerOpen ? 'chat-sidebar__new--active' : ''}`}
              onClick={togglePicker}
              title={isGroupMode ? '멤버 추가 (다중 선택)' : '대화 상대 추가'}
              aria-label={isGroupMode ? '멤버 추가' : '대화 상대 추가'}
              aria-expanded={isPickerOpen}
            >
              +
            </button>
          </div>

          <div className="chat-charlist" ref={charlistRef}>
            {charactersLoading ? (
              <div className="chat-sidebar-skeleton" aria-hidden="true">
                {Array.from({ length: 4 }, (_, index) => (
                  <div className="chat-charitem" key={index}>
                    <SkeletonBlock className="chat-sidebar-skeleton__avatar" />
                    <span className="chat-charitem__body">
                      <SkeletonBlock className="loading-skeleton--line loading-skeleton--title" />
                      <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
                    </span>
                  </div>
                ))}
              </div>
            ) : (isGroupMode ? groupMembers : partners).length > 0 ? (
              (isGroupMode ? groupMembers : partners).map((character) => (
                <button
                  type="button"
                  key={character.id}
                  className={`chat-charitem ${
                    !isGroupMode && character.id === selectedCharacter?.id
                      ? 'chat-charitem--active'
                      : ''
                  }`}
                  onClick={() =>
                    isGroupMode
                      ? toggleGroupMember(character)
                      : setSelectedCharacterId(character.id)
                  }
                  disabled={busy}
                  title={isGroupMode ? '클릭하면 그룹에서 제외' : undefined}
                >
                  <span
                    className="chat-charitem__avatar"
                    style={
                      character.image
                        ? undefined
                        : { background: orbGradient(character.name) }
                    }
                  >
                    {character.image ? (
                      <img src={character.image} alt="" />
                    ) : null}
                  </span>
                  <span className="chat-charitem__body">
                    <span className="chat-charitem__name">
                      {character.name}
                    </span>
                    <span className="chat-charitem__desc">영화 속 캐릭터</span>
                  </span>
                </button>
              ))
            ) : (
              <p className="chat-charlist__empty">
                {characterLoadError ||
                  (isGroupMode
                    ? '+ 버튼으로 그룹 멤버를 추가해보세요'
                    : '대화 상대를 추가해보세요')}
              </p>
            )}

            <div
              ref={pickerRef}
              className={`chat-partner-picker ${
                isPickerOpen ? 'chat-partner-picker--open' : ''
              }`}
              style={{ maxHeight: isPickerOpen ? pickerHeight : 0 }}
            >
              <div className="chat-partner-picker__inner" ref={pickerInnerRef}>
                <p className="chat-partner-picker__label">
                  {isGroupMode ? '멤버 추가 (여러 명 선택 가능)' : '새 대화 상대 추가'}
                </p>

                {(isGroupMode ? groupAvailableToAdd : availableToAdd).map(
                  (character) => (
                    <button
                      type="button"
                      key={character.id}
                      className="chat-charitem"
                      onClick={() =>
                        isGroupMode ? toggleGroupMember(character) : addPartner(character)
                      }
                    >
                      <span
                        className="chat-charitem__avatar"
                        style={
                          character.image
                            ? undefined
                            : { background: orbGradient(character.name) }
                        }
                      >
                        {character.image ? (
                          <img src={character.image} alt="" />
                        ) : null}
                      </span>
                      <span className="chat-charitem__body">
                        <span className="chat-charitem__name">
                          {character.name}
                        </span>
                        <span className="chat-charitem__desc">영화 속 캐릭터</span>
                      </span>
                    </button>
                  )
                )}

                {isGroupMode ? (
                  <button
                    type="button"
                    className="chat-picker-done"
                    onClick={() => setPickerOpen(false)}
                  >
                    완료 ({groupMembers.length}명 선택됨)
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </aside>

        {/* 우측: 대화 패널 */}
        <section className="chat-panel">
          <header className="chat-topbar">
            <span
              className="chat-topbar__avatar"
              style={
                activeAvatarImage
                  ? undefined
                  : { background: orbGradient(activeName) }
              }
            >
              {activeAvatarImage ? <img src={activeAvatarImage} alt="" /> : null}
            </span>
            <div className="chat-topbar__info">
              <div className="chat-topbar__nameline">
                <strong>{activeName}</strong>
                {canChat ? (
                  <>
                    <span className="chat-topbar__dot" />
                    <span className="chat-topbar__status">온라인</span>
                  </>
                ) : null}
              </div>
              <div className="chat-topbar__sub">{activeSubText}</div>
            </div>
            <div className="chat-topbar__actions">
              <button
                type="button"
                className={`chat-chip chat-chip--voice ${
                  ttsEnabled ? 'chat-chip--on' : ''
                }`}
                onClick={toggleTts}
                disabled={!ttsSupported}
                aria-pressed={ttsEnabled}
                title={
                  ttsSupported
                    ? 'AI 답변 자동 음성 재생 켜기/끄기'
                    : '이 브라우저는 오디오 재생을 지원하지 않습니다'
                }
              >
                TTS {ttsEnabled ? 'ON' : 'OFF'}
              </button>

              <button
                type="button"
                className="chat-chip chat-chip--voice"
                onClick={cycleSpeechRate}
                disabled={!ttsSupported || !ttsEnabled}
                title={
                  ttsSupported
                    ? '클릭해서 음성 재생 속도 변경'
                    : '이 브라우저는 음성 합성을 지원하지 않습니다'
                }
              >
                음성 {speechRate.toFixed(1)}x
              </button>

              {!isGroupMode ? (
                <button
                  type="button"
                  className="chat-chip chat-chip--stream chat-chip--on"
                  disabled
                  title="캐릭터 1:1 대화는 항상 실시간 스트림으로 응답합니다"
                >
                  <span className="chat-chip__stream-dot" aria-hidden="true" />
                  스트림
                </button>
              ) : null}

              <button
                type="button"
                className="chat-chip chat-chip--danger"
                onClick={clearMessages}
              >
                대화 초기화
              </button>
            </div>
          </header>

          <section
            className="chat-messages"
            ref={messagesRef}
            aria-live="polite"
          >
            {loadingRoomKey === activeKey ? (
              <div className="chat-message-skeleton" aria-label="대화 내역 불러오는 중">
                <SkeletonBlock height="62px" radius="18px" />
                <SkeletonBlock height="82px" radius="18px" />
                <SkeletonBlock height="52px" radius="18px" />
              </div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <p>
                  {canChat
                    ? `${activeName}와(과) 대화를 시작해보세요`
                    : isGroupMode
                    ? '+ 버튼으로 그룹 멤버를 추가해보세요'
                    : '캐릭터와(과) 대화를 시작해보세요'}
                </p>
              </div>
            ) : (
              <>
                <div className="chat-divider">
                  <span>오늘</span>
                </div>

                {messages.map((message) => {
                  const isUser = message.role === 'user';

                  return (
                    <article
                      key={message.id}
                      className={`chat-msg chat-msg--${message.role} ${
                        message.error ? 'chat-msg--error' : ''
                      }`}
                    >
                      {!isUser ? (
                        <span
                          className="chat-msg__avatar"
                          style={
                            activeAvatarImage
                              ? undefined
                              : {
                                  background: orbGradient(
                                    message.character || activeName
                                  ),
                                }
                          }
                        >
                          {activeAvatarImage ? (
                            <img src={activeAvatarImage} alt="" />
                          ) : null}
                        </span>
                      ) : null}

                      <div className="chat-msg__col">
                        <div className="chat-msg__meta">
                          <strong>
                            {isUser ? '나' : message.character || 'AI'}
                          </strong>
                          {message.intent ? (
                            <span className="chat-msg__intent">
                              {message.intent}
                            </span>
                          ) : null}
                          <time>{formatTime(message.createdAt)}</time>
                        </div>

                        {message.pending ? (
                          <div className="chat-typing">
                            <span />
                            <span />
                            <span />
                          </div>
                        ) : (
                          <>
                            <div className="chat-msg__bubble">
                              {message.content || '답변을 기다리는 중...'}
                            </div>

                            {!isUser && message.content && !message.error ? (
                              <button
                                type="button"
                                className={`chat-tts ${
                                  speakingMessageId === message.id ? 'chat-tts--active' : ''
                                }`}
                                onClick={() => speakMessage(message)}
                                disabled={!ttsSupported || !ttsEnabled}
                                aria-label={
                                  speakingMessageId === message.id
                                    ? '음성 재생 중지'
                                    : 'AI 답변 음성으로 듣기'
                                }
                                title={
                                  ttsSupported && ttsEnabled
                                    ? speakingMessageId === message.id
                                      ? '재생 중지'
                                      : '음성으로 듣기'
                                    : '상단에서 TTS를 켜주세요'
                                }
                              >
                                {speakingMessageId === message.id ? '■ 중지' : '🔊 듣기'}
                              </button>
                            ) : null}

                            {message.movies?.length > 0 ? (
                              <HorizontalScroller className="chat-movies-row" ariaLabel="추천 영화 목록">
                                {message.movies.map((movie, index) => {
                                  const title =
                                    movie.title || movie.name || '추천작';
                                  const genre = Array.isArray(movie.genres)
                                    ? movie.genres.join(', ')
                                    : movie.genre || movie.genres;
                                  const meta = [movie.year, genre]
                                    .filter(Boolean)
                                    .join(' · ');
                                  const rating =
                                    movie.vote_average ??
                                    movie.rating ??
                                    movie.score;
                                  const poster = getChatMoviePoster(movie);

                                  return (
                                    <div
                                      className="chat-movie"
                                      key={movie.movie_id || movie.id || movie.title || index}
                                    >
                                      <div className="chat-movie__poster">
                                        {poster ? (
                                          <img src={poster} alt={`${title} 포스터`} />
                                        ) : null}
                                      </div>
                                      <div className="chat-movie__body">
                                        {movie.recommendation_role ? (
                                          <div className="chat-movie__role">
                                            {movie.recommendation_role}
                                          </div>
                                        ) : null}
                                        <div className="chat-movie__title">
                                          {title}
                                        </div>
                                        {meta ? (
                                          <div className="chat-movie__meta">
                                            {meta}
                                          </div>
                                        ) : null}
                                        {rating != null ? (
                                          <div className="chat-movie__rating">
                                            <span>★</span>
                                            {formatRating(rating)}
                                          </div>
                                        ) : null}
                                        {movie.recommendation_reason ? (
                                          <p className="chat-movie__reason">
                                            {movie.recommendation_reason}
                                          </p>
                                        ) : null}
                                      </div>
                                    </div>
                                  );
                                })}
                              </HorizontalScroller>
                            ) : null}

                            {message.sources?.length > 0 ? (
                              <div className="chat-sources" aria-label="웹 검색 출처">
                                <strong>웹 검색 출처</strong>
                                {message.sources.map((source, index) => (
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer noopener"
                                    key={`${source.url}-${index}`}
                                  >
                                    [{index + 1}] {source.title || new URL(source.url).hostname}
                                  </a>
                                ))}
                              </div>
                            ) : null}
                          </>
                        )}
                      </div>
                    </article>
                  );
                })}
              </>
            )}
          </section>

          <div className="chat-composer-wrap">
            <div className="chat-tabs">
              {QUICK_TABS.map(([label, prompt]) => (
                <button
                  key={label}
                  type="button"
                  className={`chat-tab ${
                    activeTab === label ? 'chat-tab--active' : ''
                  }`}
                  onClick={() => {
                    setActiveTab(label);

                    if (label === '오늘의 기분') {
                      setActivePicker((current) => (current === 'mood' ? null : 'mood'));
                      return;
                    }

                    if (label === '장르 추천') {
                      setActivePicker((current) => (current === 'genre' ? null : 'genre'));
                      return;
                    }

                    setActivePicker(null);
                    setInput(prompt);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <div
              ref={quickPickerRef}
              className={`chat-picker ${activePicker ? 'chat-picker--open' : ''}`}
            >
              <div className="chat-picker__inner">
                {activePicker === 'mood' ? (
                  <div className="chat-mood-grid">
                    {MOOD_OPTIONS.map((mood) => (
                      <button
                        key={mood.emoji}
                        type="button"
                        className="chat-mood-btn"
                        onClick={() => {
                          setInput(mood.prompt);
                          setActivePicker(null);
                        }}
                      >
                        <span className="chat-mood-btn__emoji">{mood.emoji}</span>
                        <span className="chat-mood-btn__label">{mood.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}

                {activePicker === 'genre' ? (
                  <div className="chat-genre-grid">
                    {GENRE_TAGS.map((genre) => (
                      <button
                        key={genre}
                        type="button"
                        className="chat-genre-tag"
                        onClick={() => {
                          setInput(`#${genre} 영화 추천해줘`);
                          setActivePicker(null);
                        }}
                      >
                        #{genre}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault();
                sendMessage();
              }}
            >
              <div className="chat-inputbox">
                <button
                  type="button"
                  className="chat-attach"
                  title="파일 첨부"
                  aria-label="파일 첨부"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="3" y="4" width="18" height="16" rx="3" />
                    <circle cx="8.5" cy="9.5" r="1.6" />
                    <path d="M5 18l5-5 4 4 3-3 2 2" />
                  </svg>
                </button>

                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(event) => {
                    setInput(event.target.value);
                    resizeTextarea(event.target);
                  }}
                  onCompositionStart={() => {
                    composingRef.current = true;
                  }}
                  onCompositionEnd={(event) => {
                    composingRef.current = false;
                    setInput(event.currentTarget.value);
                    resizeTextarea(event.currentTarget);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      if (
                        event.nativeEvent.isComposing ||
                        composingRef.current ||
                        event.keyCode === 229
                      ) {
                        return;
                      }

                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                  rows={1}
                  maxLength={1000}
                  placeholder={
                    canChat
                      ? isGroupMode
                        ? `${activeName}에게 메시지 보내기`
                        : `${selectedCharacter.name}에게 메시지 보내기`
                      : isGroupMode
                      ? '+ 버튼으로 그룹 멤버를 추가해보세요'
                      : '캐릭터와 대화하기'
                  }
                  aria-label="메시지"
                  disabled={busy || !canChat}
                />

                <button
                  className="chat-enter"
                  type="button"
                  onClick={() => (busy ? abortRef.current?.abort() : sendMessage())}
                  disabled={!busy && !canSend}
                  title={busy ? '응답 중단' : '메시지 보내기 (Enter)'}
                  aria-label={busy ? '응답 중단' : '메시지 보내기'}
                >
                  {busy ? (
                    stopIcon
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M20 6v5a3 3 0 0 1-3 3H5" />
                      <path d="M9 10l-4 4 4 4" />
                    </svg>
                  )}
                </button>
              </div>

              {/* 녹음 종료 후 STT 결과를 즉시 전송한다. */}
              {authUser ? <SttMicButton
                disabled={busy || !canChat}
                onTranscript={(text) => {
                  setError('');
                  void sendMessage(text);
                }}
                onError={setError}
              /> : null}
            </form>

            {statusText ? <p className="chat-status">{statusText}</p> : null}

            <p className="chat-disclaimer">
              AI가 생성한 응답으로, 실제 정보와 다를 수 있어요.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default ChatPage;
