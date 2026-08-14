import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import {
  addLikedMovie,
  fetchCharacters,
  fetchLikedMovies,
  fetchUserPreferences,
  getLocalPreferences,
  removeLikedMovie,
} from '../../api.js';
import MiddlePanels from '../index/MiddlePanels.jsx';
import PromoBanner from '../index/PromoBanner.jsx';
import RecommendationRow from '../index/RecommendationRow.jsx';
import GuestChatNotice from '../chat/GuestChatNotice.jsx';
import ChatMovieRecommendations from '../chat/ChatMovieRecommendations.jsx';
import DeferredRender from '../common/DeferredRender.jsx';
import { rankCharactersForRecommendation } from '../../utils/characterRecommendation.js';
import { optimizeImageUrl } from '../../utils/imagePerformance.js';
import useMumuChat from './useMumuChat.js';
import { navigateTo } from '../../navigation.js';
import '../index/index.css';
import './homeVariants.css';

const HOME3_WELCOME_MESSAGES = [
  { title: '{name}님, 반갑습니다.', subtitle: '무무가 영화를 골라드릴게요.' },
  { title: '{name}님, 어떤 이야기가 필요하세요?', subtitle: '무무가 어울리는 영화를 찾아볼게요.' },
  { title: '{name}님, 오늘의 영화를 찾아볼까요?', subtitle: '지금 보고 싶은 느낌부터 이야기해 주세요.' },
  { title: '{name}님, 오늘 기분은 어떠세요?', subtitle: '그 기분에 어울리는 영화를 골라드릴게요.' },
  { title: '{name}님, 보고 싶은 영화가 있나요?', subtitle: '떠오르는 단어나 장르만 말해도 좋아요.' },
  { title: '{name}님, 취향에 맞는 영화를 찾아봐요.', subtitle: '좋아하는 분위기를 편하게 알려주세요.' },
  { title: '{name}님, 편하게 이야기해 주세요.', subtitle: '무무가 대화 속에서 취향을 알아갈게요.' },
  { title: '{name}님, 어떤 영화와 이어질까요?', subtitle: '무무와 천천히 취향을 찾아가 봐요.' },
  { title: '{name}님, 오늘은 어떤 영화가 끌리세요?', subtitle: '무무에게 지금 기분을 들려주세요.' },
  { title: '{name}님, 오늘 밤 뭐 볼지 고민되시나요?', subtitle: '무무가 함께 골라드릴게요.' },
];

const CHAT_HISTORY_DATE_FORMATTER = new Intl.DateTimeFormat('ko-KR', {
  year: '2-digit',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const MUMU_EMOTION_IMAGES = {
  default: '/images/character/mu/upper-body/mu-upper-default-v1.webp',
  joy: '/images/character/mu/upper-body/mu-upper-joy-v1.webp',
  thinking: '/images/character/mu/upper-body/mu-upper-thinking-v1.webp',
  searching: '/images/character/mu/upper-body/mu-upper-searching-v1.webp',
  sorry: '/images/character/mu/upper-body/mu-upper-sorry-v1.webp',
};

function getMumuEmotionImage(emotion) {
  return MUMU_EMOTION_IMAGES[emotion] || MUMU_EMOTION_IMAGES.default;
}

function formatChatHistoryDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : CHAT_HISTORY_DATE_FORMATTER.format(date);
}

function movieLikeKey(movie) {
  const id = movie?.movie_id ?? movie?.id;
  if (id !== undefined && id !== null) return `id:${id}`;

  const title = String(movie?.title || '').trim().toLocaleLowerCase('ko-KR');
  return title ? `title:${title}` : '';
}

function MockChatMessages({ messages, compact = false }) {
  const messagesRef = useRef(null);

  useEffect(() => {
    const element = messagesRef.current;
    if (element) element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
  }, [messages.length]);

  return (
    <div
      className={`home-variant-chat__messages${compact ? ' is-compact' : ''}`}
      aria-live="polite"
      ref={messagesRef}
    >
      {messages.map((message) => (
        <div
          className={`home-variant-message is-${message.role}${message.error ? ' is-error' : ''}`}
          key={message.id}
        >
          {message.role === 'assistant' ? (
            <span className="home-variant-message__avatar">
              <img src={getMumuEmotionImage(message.pending ? 'searching' : message.emotion)} alt="" decoding="async" />
            </span>
          ) : null}
          <div className="home-variant-message__body">
            {message.role === 'assistant' ? (
              <span className="home-variant-message__name">{message.character || '무무'}</span>
            ) : null}
            {message.pending ? (
              <div
                className="home-variant-message__typing"
                role="status"
                aria-label="응답을 준비하고 있습니다"
              >
                <span aria-hidden="true" />
                <span aria-hidden="true" />
                <span aria-hidden="true" />
              </div>
            ) : (
              <p>{message.text || message.content}</p>
            )}
            <ChatMovieRecommendations movies={message.movies} />
            {Array.isArray(message.sources) && message.sources.length ? (
              <div className="home-variant-message__sources" aria-label="웹 검색 출처">
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
          </div>
        </div>
      ))}
    </div>
  );
}

function VariantRecommendations({ authUser }) {
  const [likedMovieKeys, setLikedMovieKeys] = useState([]);
  const [likeStatus, setLikeStatus] = useState('');

  useEffect(() => {
    if (!authUser) {
      setLikedMovieKeys([]);
      return undefined;
    }

    const controller = new AbortController();
    fetchLikedMovies(controller.signal)
      .then((movies) => {
        setLikedMovieKeys(
          Array.from(new Set(movies.map(movieLikeKey).filter(Boolean)))
        );
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setLikeStatus(error.message);
      });

    return () => controller.abort();
  }, [authUser]);

  const toggleLike = async (movie) => {
    if (!authUser) {
      setLikeStatus('로그인 후 좋아요를 누를 수 있어요.');
      return;
    }

    const likeKey = movieLikeKey(movie);
    if (!likeKey) {
      setLikeStatus('영화 식별 정보가 없어 좋아요를 변경할 수 없습니다.');
      return;
    }

    const wasLiked = likedMovieKeys.includes(likeKey);
    setLikeStatus('');
    setLikedMovieKeys((current) => (
      wasLiked
        ? current.filter((key) => key !== likeKey)
        : Array.from(new Set([...current, likeKey]))
    ));

    try {
      if (wasLiked) await removeLikedMovie(movie);
      else await addLikedMovie(movie);
    } catch (error) {
      setLikedMovieKeys((current) => (
        wasLiked
          ? Array.from(new Set([...current, likeKey]))
          : current.filter((key) => key !== likeKey)
      ));
      setLikeStatus(error.message);
    }
  };

  return (
    <>
      <RecommendationRow
        authUser={authUser}
        likedMovieKeys={likedMovieKeys}
        onToggleLike={toggleLike}
      />
      {likeStatus ? <p className="index-status" role="status">{likeStatus}</p> : null}
    </>
  );
}

function CharacterPicker({
  onSelect,
  authUser = null,
  eyebrow = 'CHARACTER LOUNGE',
  title = '이야기할 캐릭터를 선택해 보세요',
  description = '선택하면 이 페이지에서 대화를 이어갑니다',
  limit = 7,
  slider = false,
}) {
  const [characters, setCharacters] = useState([]);
  const [preferences, setPreferences] = useState(() => getLocalPreferences());
  const rowRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchCharacters(controller.signal)
      .then((items) => setCharacters(limit ? items.slice(0, limit) : items))
      .catch((error) => {
        if (error.name !== 'AbortError') setCharacters([]);
      });
    return () => controller.abort();
  }, [limit]);

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
      .catch((error) => {
        if (error.name !== 'AbortError') setPreferences(getLocalPreferences());
      });
    return () => controller.abort();
  }, [authUser]);

  const rankedCharacters = useMemo(() => {
    return rankCharactersForRecommendation(characters, preferences);
  }, [characters, preferences]);

  const displayCharacters = rankedCharacters.length > 0
    ? rankedCharacters
    : Array.from({ length: limit || 7 }, (_, index) => ({
        id: `preview-${index}`,
        name: `캐릭터 ${String(index + 1).padStart(2, '0')}`,
        image: `/images/characters/character-${String(index + 1).padStart(2, '0')}.webp`,
      }));

  // 브라우저가 가로 스크롤 위치를 복원하거나 취향 데이터가 비동기로 갱신돼도
  // 추천 목록은 항상 현재 1순위 캐릭터부터 보여준다.
  useLayoutEffect(() => {
    const row = rowRef.current;
    if (!row) return undefined;

    const showFirstCharacter = () => {
      row.scrollTo({ left: 0, behavior: 'auto' });
    };
    showFirstCharacter();
    const frameId = window.requestAnimationFrame(showFirstCharacter);
    window.addEventListener('pageshow', showFirstCharacter);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener('pageshow', showFirstCharacter);
    };
  }, [rankedCharacters]);

  const scrollCharacters = (direction) => {
    rowRef.current?.scrollBy({ left: direction * (190 + 18) * 5, behavior: 'smooth' });
  };

  return (
    <section className="home-variant-characters" aria-label="캐릭터 선택창">
      <header>
        <div><small>{eyebrow}</small><h2>{title}</h2></div>
        <span>{description}</span>
      </header>
      <div className={`home-variant-character-slider${slider ? ' is-scrollable' : ''}`}>
        {slider ? (
          <button
            className="home-variant-character-slider__arrow is-prev"
            type="button"
            onClick={() => scrollCharacters(-1)}
            aria-label="이전 캐릭터 보기"
          >‹</button>
        ) : null}
        <div className="home-variant-characters__list" ref={rowRef}>
          {displayCharacters.map((character, index) => {
            const name = character.name || character.character || `캐릭터 ${index + 1}`;
            const image = character.image || character.image_url || character.avatar_url
              || `/images/characters/character-${String(index + 1).padStart(2, '0')}.webp`;
            const movieTitle = String(character.movie_title || character.movieTitle || '').trim()
              || '출연 영화 정보 없음';
            return (
              <button type="button" key={character.id || name} onClick={() => onSelect(character)}>
                <span><img src={optimizeImageUrl(image)} alt="" decoding="async" loading="lazy" /></span>
                <div className="home-variant-character-card__info">
                  <b>{name}</b>
                  <span className="home-variant-character-card__movie">{movieTitle}</span>
                </div>
              </button>
            );
          })}
        </div>
        {slider ? (
          <button
            className="home-variant-character-slider__arrow is-next"
            type="button"
            onClick={() => scrollCharacters(1)}
            aria-label="다음 캐릭터 보기"
          >›</button>
        ) : null}
      </div>
    </section>
  );
}

function Home3Prompt({ chat, promptRef, onBeforeSend, onNewChat, onOpenHistory }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [photoName, setPhotoName] = useState('');
  const photoInputRef = useRef(null);
  const addButtonRef = useRef(null);
  const promptMenuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const closeMenuFromOutside = (event) => {
      if (
        addButtonRef.current?.contains(event.target)
        || promptMenuRef.current?.contains(event.target)
      ) return;
      setMenuOpen(false);
    };

    document.addEventListener('pointerdown', closeMenuFromOutside);
    return () => document.removeEventListener('pointerdown', closeMenuFromOutside);
  }, [menuOpen]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (chat.busy) {
      chat.stopResponse();
      return;
    }
    onBeforeSend?.();
    chat.sendMessage();
  };

  return (
    <div className="home3-prompt-area" ref={promptRef}>
      <form className="home3-prompt" onSubmit={handleSubmit}>
        <button
          ref={addButtonRef}
          className="home3-prompt__add"
          type="button"
          aria-label="채팅 메뉴 열기"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >+</button>
        {menuOpen ? (
          <div className="home3-prompt-menu" ref={promptMenuRef}>
            <button type="button" onClick={() => { onNewChat(); setMenuOpen(false); }}>무무와 새 채팅</button>
            <button type="button" onClick={() => navigateTo('/chat/group')}>캐릭터와 새 채팅</button>
            <button type="button" onClick={() => { onOpenHistory(); setMenuOpen(false); }}>대화 기록</button>
            <button
              type="button"
              className="home3-prompt-menu__image"
              data-tooltip="이미지 첨부 기능은 준비중이에요."
              onClick={() => { photoInputRef.current?.click(); setMenuOpen(false); }}
            >이미지 첨부</button>
          </div>
        ) : null}
        <input
          className="home3-photo-input"
          type="file"
          accept="image/*"
          ref={photoInputRef}
          onChange={(event) => setPhotoName(event.target.files?.[0]?.name || '')}
        />
        <input
          aria-label="무무에게 영화 요청하기"
          autoComplete="off"
          placeholder="무무에게 영화를 물어보세요"
          value={chat.draft}
          onChange={(event) => chat.setDraft(event.target.value)}
          aria-busy={chat.busy}
        />
        <button
          className="home3-prompt__voice-input"
          type="button"
          aria-label="음성 인식 기능 준비 중"
          data-tooltip="음성 인식은 준비 중이에요"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <rect x="8.5" y="3" width="7" height="12" rx="3.5" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M8.5 21h7" />
          </svg>
        </button>
        <button
          className="home3-prompt__voice-chat"
          type="button"
          aria-label="AI 음성 대화 기능 준비 중"
          data-tooltip="AI 음성 대화는 준비 중이에요"
        >
          <svg aria-hidden="true" viewBox="0 0 28 28">
            <path d="M5 11v6M9.5 7v14M14 10v8M18.5 5v18M23 11v6" />
          </svg>
        </button>
      </form>
      {photoName ? (
        <div className="home3-photo-chip">
          <span>{photoName}</span>
          <small>이미지 분석 API 연결 전</small>
          <button type="button" onClick={() => {
            setPhotoName('');
            if (photoInputRef.current) photoInputRef.current.value = '';
          }} aria-label="첨부 사진 제거">×</button>
        </div>
      ) : null}
      {chat.error ? <p className="home3-prompt-status" role="status">{chat.error}</p> : null}
    </div>
  );
}

function HomePage({ authUser, onLogout }) {
  const displayName = authUser?.nickname || authUser?.name || authUser?.username || '게스트';
  const [welcomeMessage] = useState(() => (
    HOME3_WELCOME_MESSAGES[Math.floor(Math.random() * HOME3_WELCOME_MESSAGES.length)]
  ));
  const welcomeTitle = welcomeMessage.title.replace('{name}', displayName);
  const chat = useMumuChat(authUser);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyBottom, setHistoryBottom] = useState(0);
  const [historyMenuId, setHistoryMenuId] = useState('');
  const [historyMenuPosition, setHistoryMenuPosition] = useState({ top: 0, left: 0 });
  const chatStageRef = useRef(null);
  const promptRef = useRef(null);
  const historyPanelRef = useRef(null);
  const historyMoreMenuRef = useRef(null);
  const chatActivatedRef = useRef(false);
  const promptStartRectRef = useRef(null);
  const restorePromptFocusRef = useRef(false);

  useEffect(() => {
    if (chat.messages.length > 0) return;
    chatActivatedRef.current = false;
    promptStartRectRef.current = null;
  }, [chat.messages.length]);

  useEffect(() => {
    if (!historyOpen) return undefined;

    const closeHistoryFromOutside = (event) => {
      if (historyMoreMenuRef.current?.contains(event.target)) return;
      if (historyPanelRef.current?.contains(event.target)) {
        setHistoryMenuId('');
        return;
      }
      setHistoryMenuId('');
      setHistoryOpen(false);
    };

    document.addEventListener('pointerdown', closeHistoryFromOutside);
    return () => document.removeEventListener('pointerdown', closeHistoryFromOutside);
  }, [historyOpen]);

  useLayoutEffect(() => {
    if (!historyOpen) return undefined;

    const alignHistoryBottom = () => {
      const stageRect = chatStageRef.current?.getBoundingClientRect();
      const promptRect = promptRef.current?.getBoundingClientRect();
      if (!stageRect || !promptRect) return;
      // 입력창 자체의 하단선에 패널 테두리를 맞춘다. prompt-area 아래 예약 여백은 제외한다.
      setHistoryBottom(Math.max(0, Math.round(stageRect.bottom - promptRect.bottom) + 36));
    };

    alignHistoryBottom();
    const observer = new ResizeObserver(alignHistoryBottom);
    if (chatStageRef.current) observer.observe(chatStageRef.current);
    if (promptRef.current) observer.observe(promptRef.current);
    window.addEventListener('resize', alignHistoryBottom);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', alignHistoryBottom);
    };
  }, [historyOpen, chat.messages.length]);

  const prepareChatActivation = () => {
    if (chatActivatedRef.current || chat.messages.length > 0) return;
    const promptRect = promptRef.current?.getBoundingClientRect();
    promptStartRectRef.current = promptRect
      ? {
          documentTop: promptRect.top + window.scrollY,
          documentBottom: promptRect.bottom + window.scrollY,
          scrollY: window.scrollY,
        }
      : null;

    const focusedElement = document.activeElement;
    restorePromptFocusRef.current = Boolean(
      focusedElement && promptRef.current?.contains(focusedElement)
    );
  };

  const startNewChat = () => {
    chat.newConversation();
    setHistoryOpen(false);
    window.history.replaceState({}, '', '/home');
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
  };

  const startCharacterChat = (character) => {
    const params = new URLSearchParams();
    if (character?.id !== undefined && character?.id !== null) {
      params.set('characterId', String(character.id));
    } else if (character?.name) {
      params.set('characterName', character.name);
    }
    navigateTo(`/chat/group${params.toString() ? `?${params.toString()}` : ''}`);
  };

  const toggleHistoryPin = (conversation) => {
    if (conversation.linked) return;
    chat.toggleConversationPin(conversation.id);
    setHistoryMenuId('');
  };

  const renameHistory = (conversation) => {
    if (conversation.linked) return;
    const title = window.prompt('대화 이름을 입력해 주세요.', conversation.title || '');
    if (!String(title || '').trim()) return;
    chat.renameConversation(conversation.id, title);
    setHistoryMenuId('');
  };

  const deleteHistory = async (conversation) => {
    if (conversation.linked) return;
    setHistoryMenuId('');
    await chat.removeConversation(conversation.id);
  };

  const selectHistory = (conversation) => {
    if (conversation.href) {
      navigateTo(conversation.href);
      return;
    }
    chat.selectConversation(conversation.id);
    setHistoryOpen(false);
  };

  const historyConversations = chat.conversations
    .filter((conversation) => (
      Boolean(conversation.roomId)
      || (Array.isArray(conversation.messages) && conversation.messages.length > 0)
    ))
    .sort((left, right) => {
    if (Boolean(left.pinned) !== Boolean(right.pinned)) return left.pinned ? -1 : 1;
    return new Date(right.updatedAt || right.createdAt || 0) - new Date(left.updatedAt || left.createdAt || 0);
    });

  useLayoutEffect(() => {
    if (chat.messages.length === 0 || chatActivatedRef.current) return undefined;
    chatActivatedRef.current = true;

    let animationFrameId = 0;
    let cleanupTimer = 0;
    const startedAt = window.performance.now();
    const followDuration = 760;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const prompt = promptRef.current;

    if (!prompt) return undefined;

    const startRect = promptStartRectRef.current;
    const currentRect = prompt.getBoundingClientRect();
    const startScroll = startRect?.scrollY ?? window.scrollY;
    // 첫 메시지가 생기며 flex 레이아웃으로 바뀌는 순간의 위치 점프를 FLIP으로 상쇄한다.
    // 이후 채팅 영역과 같은 속도로 transform을 풀어 입력창도 자연스럽게 내려간다.
    if (!prefersReducedMotion && startRect) {
      const currentDocumentTop = currentRect.top + window.scrollY;
      prompt.style.transition = 'none';
      prompt.style.transform = `translateY(${startRect.documentTop - currentDocumentTop}px)`;
      prompt.style.willChange = 'transform';
      window.scrollTo({ top: startRect.scrollY, left: 0, behavior: 'auto' });
      void prompt.offsetHeight;
    }

    const followPrompt = (now) => {
      const activePrompt = promptRef.current;
      const activeStage = chatStageRef.current;
      if (!activePrompt || !activeStage) return;

      const progress = Math.min(1, Math.max(0, (now - startedAt) / 720));
      const easedProgress = 1 - ((1 - progress) ** 3);
      const stageRect = activeStage.getBoundingClientRect();
      const stageCenter = stageRect.top + window.scrollY + (stageRect.height / 2);
      const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      const centeredScroll = Math.min(
        maxScroll,
        Math.max(0, stageCenter - (window.innerHeight / 2)),
      );

      // 채팅 영역이 확장되는 동안 그 중심과 브라우저 화면 중심을 같은 속도로 맞춘다.
      window.scrollTo({
        top: startScroll + ((centeredScroll - startScroll) * easedProgress),
        left: window.scrollX,
        behavior: 'auto',
      });

      if (!prefersReducedMotion && now - startedAt < followDuration) {
        animationFrameId = window.requestAnimationFrame(followPrompt);
      }
    };

    animationFrameId = window.requestAnimationFrame((now) => {
      window.scrollTo({ top: startScroll, left: 0, behavior: 'auto' });
      if (!prefersReducedMotion && startRect) {
        prompt.style.transition = 'transform 720ms cubic-bezier(0.4, 0, 0.2, 1)';
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
      if (restorePromptFocusRef.current) {
        prompt.querySelector('input')?.focus({ preventScroll: true });
        restorePromptFocusRef.current = false;
      }
    }, followDuration);

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      window.clearTimeout(cleanupTimer);
      prompt.style.removeProperty('transition');
      prompt.style.removeProperty('transform');
      prompt.style.removeProperty('will-change');
    };
  }, [chat.messages.length]);

  return (
    <main className="home-variant home3-page">
      <section className="home3-cinema-hero" aria-label="Musubi 주요 영화">
        <div className="home3-cinema-hero__banner"><PromoBanner highResolution /></div>
      </section>

      <section
        className={`home3-chat-stage${chat.messages.length > 0 ? ' is-chatting' : ''}`}
        ref={chatStageRef}
      >
        {historyOpen ? (
          <aside
            className="home3-chat-history"
            aria-label="대화 기록"
            ref={historyPanelRef}
            style={{ '--history-bottom': `${historyBottom}px` }}
          >
            <header>
              <strong>대화 기록</strong>
              <button type="button" onClick={() => setHistoryOpen(false)} aria-label="대화 기록 닫기">×</button>
            </header>
            <div className="home3-chat-history__list">
              {historyConversations.map((conversation) => (
                <div className="home3-chat-history__row" key={conversation.id}>
                  <button type="button" onClick={() => selectHistory(conversation)}>
                    <strong>{conversation.title}</strong>
                    <time dateTime={conversation.updatedAt || conversation.createdAt}>
                      {formatChatHistoryDate(conversation.updatedAt || conversation.createdAt)}
                    </time>
                  </button>
                  {!conversation.linked ? <div className="home3-chat-history__actions">
                    <button
                      className={`home3-chat-history__pin${conversation.pinned ? ' is-pinned' : ''}`}
                      type="button"
                      onClick={() => toggleHistoryPin(conversation)}
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
                        <button type="button" onClick={() => toggleHistoryPin(conversation)}>
                          {conversation.pinned ? '고정 해제' : '채팅 고정'}
                        </button>
                        <button type="button" onClick={() => renameHistory(conversation)}>이름 수정</button>
                        <button className="is-danger" type="button" onClick={() => deleteHistory(conversation)}>삭제하기</button>
                      </div>
                    ) : null}
                  </div> : null}
                </div>
              ))}
              {historyConversations.length === 0 ? (
                <p className="home3-chat-history__empty">저장된 대화가 없습니다.</p>
              ) : null}
            </div>
          </aside>
        ) : null}
        <header>
          <h1>{welcomeTitle}</h1>
          <p>{welcomeMessage.subtitle}</p>
        </header>
        <div className="home3-chat-stage__conversation">
          {chat.messages.length > 0 ? <MockChatMessages messages={chat.messages} /> : null}
          {chat.roomLoading ? <p className="home3-chat-loading">이전 대화를 불러오는 중…</p> : null}
          <Home3Prompt
            chat={chat}
            promptRef={promptRef}
            onBeforeSend={prepareChatActivation}
            onNewChat={startNewChat}
            onOpenHistory={() => setHistoryOpen(true)}
          />
          <GuestChatNotice
            showGuestMessage={!authUser}
            hidden={chat.messages.length > 0}
            mode="home"
            onSuggestionSelect={(suggestion) => {
              chat.setDraft(suggestion);
              window.requestAnimationFrame(() => {
                promptRef.current?.querySelector('input[aria-label="무무에게 영화 요청하기"]')?.focus();
              });
            }}
          />
        </div>
      </section>

      <DeferredRender minHeight={420}>
        <div className="home3-character-lounge">
          <CharacterPicker
            authUser={authUser}
            eyebrow=""
            title="💬 영화 속 캐릭터와 대화하기"
            description=""
            limit={0}
            slider
            onSelect={startCharacterChat}
          />
        </div>
      </DeferredRender>

      <DeferredRender minHeight={520}>
        <div className="home3-existing-recommendation"><VariantRecommendations authUser={authUser} /></div>
      </DeferredRender>
      <DeferredRender minHeight={520}>
        <MiddlePanels authUser={authUser} />
      </DeferredRender>
    </main>
  );
}

export default HomePage;
