import { useEffect, useRef, useState } from 'react';

import {
  addRecommendedMovies,
  deleteChatRoom,
  fetchCharacter,
  fetchChatRoomMessages,
  sendChat,
  sendRoomMessage,
} from '../../api.js';

import './chat.css';
import SttMicButton from './SttMicButton.jsx';

const TTS_BASE_URL = (
  import.meta.env.VITE_TTS_BASE_URL || 'http://127.0.0.1:5001'
).replace(/\/+$/, '');
const TTS_FEATURE_ENABLED = import.meta.env.VITE_TTS_ENABLED === 'true';
const TTS_ENABLED_STORAGE_KEY = 'cineverse.chat.tts.enabled';

// /chat/auto 전용 페이지. UI는 chat 페이지와 동일하되, 대화 상대가 CineBuddy 하나뿐이라
// 사이드바에는 "대화 상대"가 아니라 "대화 리스트"(내가 연 대화들)를 보여준다.
// + 를 누르면 새 대화를 열고, 그 대화는 시작 시간을 제목으로 저장된다.
const STORAGE_KEY = 'cineverse.autochat.conversations';
const BOT_NAME = 'CineBuddy';
const BOT_COLOR = '#f3ead8'; // 이미지 로딩 전/실패 시 배경(캐릭터 이미지 톤과 맞춤)
const BOT_IMAGE = '/images/cinebuddy.png'; // CineBuddy 캐릭터 이미지

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

const QUICK_TABS = [
  ['오늘의 기분', null],
  ['장르 추천', null],
  ['자동추천', '내 취향대로 아무거나 골라줘'],
];

const MOOD_OPTIONS = [
  { emoji: '😊', label: '좋아요', prompt: '오늘 기분이 좋아! 신나는 영화 추천해줘' },
  { emoji: '😒', label: '시큰둥', prompt: '오늘 좀 시큰둥해... 그냥 볼만한 영화 없을까' },
  { emoji: '😔', label: '힘들다', prompt: '힘들다... 위로가 되는 영화 추천해 줘' },
  { emoji: '🤔', label: '고민중', prompt: '뭘 볼지 고민되는데 추천해줘' },
  { emoji: '🤨', label: '의심반', prompt: '그냥 아무거나 재밌는 거 추천해줘' },
  { emoji: '😫', label: '지쳤어', prompt: '너무 지쳤어... 가볍게 볼 수 있는 영화 추천해줘' },
  { emoji: '😡', label: '화나요', prompt: '열받아 죽겠어! 스트레스 풀리는 영화 추천해줘' },
];

const GENRE_TAGS = [
  '액션', '드라마', '로맨스', 'SF', '공포', '코미디', '스릴러', '애니메이션',
];

const MAX_COMPOSER_HEIGHT = 168;

const formatTime = (value) =>
  new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));

// 대화 제목: 채팅을 시작한(= + 를 누른) 시간대로 저장한다.
const formatTitle = (value) =>
  new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));

function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function toPosterUrl(value) {
  const path = String(value || '').trim();

  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function getMoviePoster(movie) {
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

// 이미지가 없는 소환 캐릭터용 색상 아바타(이름 해시 → 색상)
function orbGradient(seed) {
  const text = String(seed || 'AI');
  let hue = 0;
  for (let i = 0; i < text.length; i += 1) {
    hue = (hue * 31 + text.charCodeAt(i)) % 360;
  }
  return `radial-gradient(circle at 34% 28%, hsl(${hue} 70% 78%) 0%, hsl(${hue} 55% 48%) 24%, hsl(${hue} 60% 28%) 52%, hsl(${hue} 65% 12%) 100%)`;
}

function createConversation() {
  const now = new Date();

  return {
    id: crypto.randomUUID(),
    title: formatTitle(now),
    roomId: '',
    createdAt: now.toISOString(),
    messages: [],
  };
}

// 서버 방(room) 메시지를 이 페이지의 메시지 형태로 변환한다.
function mapRoomMessages(roomId, roomMessages) {
  return (roomMessages || []).map((message, index) => ({
    id: `room-${roomId}-${index}`,
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content || '',
    // 소환된 캐릭터가 있으면 그 이름을 유지(일반 CineBuddy 응답이면 character는 null → BOT_NAME).
    character: message.character || BOT_NAME,
    createdAt: message.created_at || message.createdAt || new Date().toISOString(),
    movies: message.recommended_movies || message.movies || [],
  }));
}

// 긴 답변 전체를 한 번에 합성하면 첫 음성이 늦어지므로 짧은 문장 단위로 나눈다.
function splitTtsChunks(text, maxLength = 70) {
  const sentences = String(text || '').match(/[^.!?。！？\n]+[.!?。！？]?|\n+/g) || [];
  const chunks = [];

  for (const sentence of sentences) {
    const value = sentence.trim();
    if (!value) continue;
    if (value.length <= maxLength) {
      chunks.push(value);
      continue;
    }
    for (let index = 0; index < value.length; index += maxLength) {
      chunks.push(value.slice(index, index + maxLength).trim());
    }
  }

  return chunks.filter(Boolean);
}

function AutoChatPage() {
  // 대화 리스트: + 로 연 대화들을 저장한다(시작 시간이 제목).
  const [conversations, setConversations] = useState(() =>
    readJson(STORAGE_KEY, [])
  );
  const [activeId, setActiveId] = useState('');

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
  const [speechRate, setSpeechRate] = useState(1);
  // 챗봇 대화 중 소환된 캐릭터 이미지 캐시 (이름 → 이미지 URL)
  const [characterImages, setCharacterImages] = useState({});

  const messagesRef = useRef(null);
  const textareaRef = useRef(null);
  const quickPickerRef = useRef(null);
  const composingRef = useRef(false);
  const abortRef = useRef(null);
  const ttsAbortRef = useRef(null);
  const audioRef = useRef(null);
  const audioUrlRef = useRef('');
  const stickToBottomRef = useRef(true);

  // 마이페이지 등에서 ?room=<id> 로 들어오면 그 방 대화를 이어서 연다.
  // 없으면: 저장된 대화가 있으면 첫 대화를, 없으면 새 대화를 하나 연다.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get('room');
    const stored = readJson(STORAGE_KEY, []);

    if (roomParam) {
      const existing = stored.find((c) => String(c.roomId) === String(roomParam));

      if (existing) {
        setActiveId(existing.id);
      } else {
        const conversation = {
          id: crypto.randomUUID(),
          title: formatTitle(new Date()),
          roomId: String(roomParam),
          createdAt: new Date().toISOString(),
          messages: [],
        };
        setConversations((current) => [conversation, ...current]);
        setActiveId(conversation.id);
      }

      fetchChatRoomMessages(roomParam)
        .then((roomMessages) => {
          const mapped = mapRoomMessages(roomParam, roomMessages);
          setConversations((current) =>
            current.map((c) =>
              String(c.roomId) === String(roomParam) ? { ...c, messages: mapped } : c
            )
          );

          // 소환된 캐릭터(=CineBuddy가 아닌 이름)들의 프로필 이미지를 미리 불러온다.
          Array.from(
            new Set(
              mapped
                .filter((m) => m.character && m.character !== BOT_NAME)
                .map((m) => m.character)
            )
          ).forEach((name) => loadCharacterImage(name));
        })
        .catch(() => {});

      return;
    }

    if (stored.length > 0) {
      setActiveId(stored[0].id);
      return;
    }

    const conversation = createConversation();
    setConversations([conversation]);
    setActiveId(conversation.id);
  }, []);

  // 대화 리스트를 로컬에 저장(= + 기준으로 저장). 메시지 진행 상황도 함께 남긴다.
  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    const supported = typeof window !== 'undefined' && 'Audio' in window;
    setTtsSupported(supported);
    return () => {
      ttsAbortRef.current?.abort();
      audioRef.current?.pause();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  useEffect(() => {
    window.localStorage.setItem(TTS_ENABLED_STORAGE_KEY, String(ttsEnabled));
  }, [ttsEnabled]);

  const activeConversation =
    conversations.find((conversation) => conversation.id === activeId) || null;
  const messages = activeConversation?.messages || [];
  const canChat = Boolean(activeConversation);

  const resizeTextarea = (textarea) => {
    if (!textarea) return;

    textarea.style.height = 'auto';
    const nextHeight = Math.min(textarea.scrollHeight, MAX_COMPOSER_HEIGHT);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > MAX_COMPOSER_HEIGHT ? 'auto' : 'hidden';
  };

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
  }, [messages, activeId]);

  useEffect(() => {
    resizeTextarea(textareaRef.current);
  }, [input]);

  useEffect(() => {
    if (!activePicker) return;

    const picker = quickPickerRef.current;
    if (!picker) return;

    picker.style.display = 'none';
    void picker.offsetHeight;
    picker.style.display = '';
  }, [activePicker]);

  const updateConversation = (id, updater) => {
    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === id ? updater(conversation) : conversation
      )
    );
  };

  // 소환된 캐릭터의 프로필 이미지를 단건 조회 API로 가져와 캐시한다(이름/별칭 지원).
  const loadCharacterImage = (name) => {
    if (!name || characterImages[name] !== undefined) return;

    fetchCharacter(name)
      .then((character) => {
        setCharacterImages((current) => ({
          ...current,
          [name]: character.image || character.image_url || '',
        }));
      })
      .catch(() => {
        setCharacterImages((current) => ({ ...current, [name]: '' }));
      });
  };

  const updateMessage = (conversationId, messageId, updater) => {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) =>
        message.id === messageId ? updater(message) : message
      ),
    }));
  };

  const stopSpeaking = () => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = '';
  };

  const speakAiAnswer = async (message, onChunkStart) => {
    if (!ttsSupported || !ttsEnabled || message?.role !== 'assistant' || !message?.content) {
      return;
    }

    stopSpeaking();
    const controller = new AbortController();
    ttsAbortRef.current = controller;

    try {
      const chunks = splitTtsChunks(message.content);
      if (chunks.length === 0) {
        ttsAbortRef.current = null;
        return;
      }
      const synthesize = async (text) => {
        const response = await fetch(`${TTS_BASE_URL}/synthesize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text,
            character: 'chatai',
            voice: 'chatai',
            rate: speechRate,
            language: 'AUTO',
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || `TTS 오류 (${response.status})`);
        }
        return response.blob();
      };

      // 첫 문장은 짧게 합성해 빠르게 재생하고, 재생 중 다음 문장을 미리 합성한다.
      let nextAudio = synthesize(chunks[0]);
      let visibleText = '';
      for (let index = 0; index < chunks.length; index += 1) {
        // eslint-disable-next-line no-await-in-loop
        const blob = await nextAudio;
        nextAudio = index + 1 < chunks.length ? synthesize(chunks[index + 1]) : null;

        visibleText = `${visibleText}${visibleText ? ' ' : ''}${chunks[index]}`;
        onChunkStart?.(visibleText);

        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audioUrlRef.current = audioUrl;
        audioRef.current = audio;
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve, reject) => {
          audio.onended = resolve;
          audio.onerror = () => reject(new Error('chatai 음성을 재생할 수 없습니다.'));
          audio.play().catch(reject);
        });
        URL.revokeObjectURL(audioUrl);
        if (audioUrlRef.current === audioUrl) audioUrlRef.current = '';
      }

      ttsAbortRef.current = null;
      audioRef.current = null;
    } catch (ttsError) {
      onChunkStart?.(message.content);
      if (ttsError.name !== 'AbortError') {
        setError(`${ttsError.message} — TTS 서버를 확인해주세요.`);
      }
      stopSpeaking();
    }
  };

  const toggleTts = () => {
    setTtsEnabled((current) => {
      if (current) stopSpeaking();
      return !current;
    });
  };

  const cycleSpeechRate = () => {
    const rates = [0.8, 1, 1.2];
    const index = rates.indexOf(speechRate);
    setSpeechRate(rates[(index + 1) % rates.length]);
    stopSpeaking();
  };

  // 대화 삭제: 서버 방이 있으면 삭제(DELETE /chat/rooms/{id})하고, 로컬 리스트에서도 제거.
  const handleDeleteConversation = async (conversation) => {
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

  // + : 새 대화를 열고(=저장) 바로 선택한다.
  const handleNewConversation = () => {
    const conversation = createConversation();

    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setInput('');
    setError('');
    stickToBottomRef.current = true;
  };

  const sendMessage = async (contentOverride) => {
    const content = (typeof contentOverride === 'string' ? contentOverride : input).trim();

    if (!content || busy || !activeConversation) return;

    const conversationId = activeConversation.id;
    const roomId = activeConversation.roomId;
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
          character: BOT_NAME,
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

    try {
      // 첫 메시지만 /chat/auto로 방을 만들고, 이후에는 같은 room_id로 이어서 대화한다.
      const response = roomId
        ? await sendRoomMessage(
            roomId,
            { message: content, character: null },
            controller.signal
          )
        : await sendChat(
            { message: content, character: null },
            controller.signal
          );

      if (response?.conversationId) {
        updateConversation(conversationId, (conversation) => ({
          ...conversation,
          roomId: response.conversationId,
        }));
      }

      // 챗봇 대화 중 캐릭터가 소환되면(응답에 character 존재) 그 캐릭터로 표시한다.
      const summoned =
        response?.character && response.character !== BOT_NAME
          ? response.character
          : '';

      if (summoned) loadCharacterImage(summoned);

      const finalMessage = {
        id: pendingId,
        role: 'assistant',
        content: response?.answer || '응답 내용이 없습니다.',
        character: summoned || BOT_NAME,
        intent: response?.intent,
        movies: response?.movies || [],
        createdAt,
        pending: false,
      };

      if (ttsEnabled) {
        updateMessage(conversationId, pendingId, (message) => ({
          ...message,
          ...finalMessage,
          content: '',
        }));
        void speakAiAnswer(finalMessage, (visibleText) => {
          updateMessage(conversationId, pendingId, (message) => ({
            ...message,
            content: visibleText,
          }));
        });
      } else {
        updateMessage(conversationId, pendingId, (message) => ({
          ...message,
          ...finalMessage,
        }));
      }

      // 추천받은 영화를 마이페이지 추천과 잇기 위해 저장한다.
      addRecommendedMovies(response?.movies || []);
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

  // 지금 대화만 초기화(메시지/방 비우기). 대화 리스트에서 사라지지는 않는다.
  const clearMessages = () => {
    if (!activeConversation) return;

    abortRef.current?.abort();
    stopSpeaking();

    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      roomId: '',
      messages: [],
    }));

    setInput('');
    setError('');
    setBusy(false);
  };

  const canSend = Boolean(input.trim() && canChat && !busy);
  const statusText = busy ? 'CineBuddy가 답변 중입니다.' : error || '';

  const stopIcon = (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="2" />
    </svg>
  );

  return (
    <main className="chat-page" aria-label="CineBuddy와 대화">
      <div className="chat-layout">
        {/* 좌측: 대화 리스트 */}
        <aside className="chat-sidebar">
          <div className="chat-sidebar__head">
            <span>대화 리스트</span>
            <button
              type="button"
              className="chat-sidebar__new"
              onClick={handleNewConversation}
              title="새 대화 열기"
              aria-label="새 대화 열기"
            >
              +
            </button>
          </div>

          <div className="chat-charlist">
            {conversations.length > 0 ? (
              conversations.map((conversation) => (
                <div className="chat-conv-row" key={conversation.id}>
                  <button
                    type="button"
                    className={`chat-charitem ${
                      conversation.id === activeId ? 'chat-charitem--active' : ''
                    }`}
                    onClick={() => setActiveId(conversation.id)}
                    disabled={busy}
                  >
                    <span
                      className="chat-charitem__avatar"
                      style={{ background: BOT_COLOR }}
                    >
                      <img src={BOT_IMAGE} alt="" />
                    </span>
                    <span className="chat-charitem__body">
                      <span className="chat-charitem__name">{conversation.title}</span>
                      <span className="chat-charitem__desc">{BOT_NAME}</span>
                    </span>
                  </button>

                  <button
                    type="button"
                    className="chat-conv-del"
                    onClick={() => handleDeleteConversation(conversation)}
                    title="대화 삭제"
                    aria-label="대화 삭제"
                  >
                    ✕
                  </button>
                </div>
              ))
            ) : (
              <p className="chat-charlist__empty">
                + 버튼으로 새 대화를 열어보세요
              </p>
            )}
          </div>
        </aside>

        {/* 우측: 대화 패널 */}
        <section className="chat-panel">
          <header className="chat-topbar">
            <span
              className="chat-topbar__avatar"
              style={{ background: BOT_COLOR }}
            >
              <img src={BOT_IMAGE} alt="" />
            </span>
            <div className="chat-topbar__info">
              <div className="chat-topbar__nameline">
                <strong>{BOT_NAME}</strong>
                <span className="chat-topbar__dot" />
                <span className="chat-topbar__status">온라인</span>
              </div>
              <div className="chat-topbar__sub">AI 영화 친구 · 자동 추천</div>
            </div>
            <div className="chat-topbar__actions">
              <button
                type="button"
                className={`chat-chip chat-chip--voice ${ttsEnabled ? 'chat-chip--on' : ''}`}
                onClick={toggleTts}
                disabled={!ttsSupported}
                aria-pressed={ttsEnabled}
                title="AI 답변 자동 음성 재생 켜기/끄기"
              >
                TTS {ttsEnabled ? 'ON' : 'OFF'}
              </button>
              <button
                type="button"
                className="chat-chip chat-chip--voice"
                onClick={cycleSpeechRate}
                disabled={!ttsSupported || !ttsEnabled}
                title="TTS 재생 속도 변경"
              >
                음성 {speechRate.toFixed(1)}x
              </button>
              <button
                type="button"
                className="chat-chip chat-chip--danger"
                onClick={clearMessages}
              >
                대화 초기화
              </button>
            </div>
          </header>

          <section className="chat-messages" ref={messagesRef} aria-live="polite">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <p>{BOT_NAME}와(과) 대화를 시작해보세요</p>
              </div>
            ) : (
              <>
                <div className="chat-divider">
                  <span>오늘</span>
                </div>

                {messages.map((message) => {
                  const isUser = message.role === 'user';
                  // 소환된 캐릭터면 그 이름/이미지로, 아니면 CineBuddy로 표시.
                  const isBot = !message.character || message.character === BOT_NAME;
                  const characterImage = isBot ? '' : characterImages[message.character];
                  const displayName = isBot ? BOT_NAME : message.character;

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
                            isBot
                              ? { background: BOT_COLOR }
                              : characterImage
                                ? undefined
                                : { background: orbGradient(displayName) }
                          }
                        >
                          {isBot ? (
                            <img src={BOT_IMAGE} alt="" />
                          ) : characterImage ? (
                            <img src={characterImage} alt="" />
                          ) : null}
                        </span>
                      ) : null}

                      <div className="chat-msg__col">
                        <div className="chat-msg__meta">
                          <strong>{isUser ? '나' : displayName}</strong>
                          {message.intent ? (
                            <span className="chat-msg__intent">{message.intent}</span>
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

                            {message.movies?.length > 0 ? (
                              <div className="chat-movies-row">
                                {message.movies.map((movie, index) => {
                                  const title = movie.title || movie.name || '추천작';
                                  const meta = [movie.year, movie.genre]
                                    .filter(Boolean)
                                    .join(' · ');
                                  const rating = movie.rating ?? movie.score;
                                  const poster = getMoviePoster(movie);

                                  return (
                                    <div
                                      className="chat-movie"
                                      key={movie.id || movie.title || index}
                                    >
                                      <div
                                        className="chat-movie__poster"
                                        style={
                                          poster
                                            ? { backgroundImage: `url(${poster})` }
                                            : undefined
                                        }
                                      >
                                      </div>
                                      <div className="chat-movie__body">
                                        <div className="chat-movie__title">{title}</div>
                                        {meta ? (
                                          <div className="chat-movie__meta">{meta}</div>
                                        ) : null}
                                        {rating != null ? (
                                          <div className="chat-movie__rating">
                                            <span>★</span>
                                            {rating}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>
                                  );
                                })}
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
                  className={`chat-tab ${activeTab === label ? 'chat-tab--active' : ''}`}
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
                  placeholder={`${BOT_NAME}에게 메시지 보내기`}
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

              <SttMicButton
                disabled={busy}
                onTranscript={(text) => {
                  setError('');
                  void sendMessage(text);
                }}
                onError={setError}
              />
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

export default AutoChatPage;
