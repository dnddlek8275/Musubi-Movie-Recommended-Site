import { useEffect, useMemo, useRef, useState } from 'react';

import {
  addRecommendedMovies,
  deleteChatRoom,
  fetchChatRooms,
  fetchChatRoomMessages,
  generateChatTitle,
  sendChat,
  sendRoomMessage,
  updateChatRoomTitle,
} from '../../api.js';

const STORAGE_KEY = 'cineverse.autochat.conversations';

function readStoredConversations() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function createConversation(roomId = '') {
  const now = new Date();
  return {
    id: crypto.randomUUID(),
    title: '새 대화',
    roomId: String(roomId || ''),
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
    messages: [],
  };
}

function mapRoomMessages(roomId, messages) {
  return (messages || []).map((message, index) => ({
    id: `room-${roomId}-${index}`,
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content || '',
    character: message.role === 'assistant' ? message.character || '무무' : '',
    emotion: message.role === 'assistant' ? message.emotion || 'default' : '',
    createdAt: message.created_at || message.createdAt || new Date().toISOString(),
    movies: message.recommended_movies || message.movies || [],
  }));
}

export default function useMumuChat(authUser) {
  const [conversations, setConversations] = useState(() => (
    authUser ? readStoredConversations() : []
  ));
  const [activeId, setActiveId] = useState('');
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [guestRemaining, setGuestRemaining] = useState(null);
  const [roomLoading, setRoomLoading] = useState(false);
  const [linkedConversations, setLinkedConversations] = useState([]);
  const abortRef = useRef(null);
  const titleRequestsRef = useRef(new Set());
  const initialRoomIdRef = useRef(
    new URLSearchParams(window.location.search).get('room') || '',
  );
  const roomEntryHandledRef = useRef(false);

  const updateConversation = (conversationId, updater) => {
    setConversations((current) => current.map((conversation) => (
      conversation.id === conversationId ? updater(conversation) : conversation
    )));
  };

  useEffect(() => {
    // 개발 모드의 effect 재실행에서도 URL room을 정확히 한 번만 소비한다.
    if (roomEntryHandledRef.current) return undefined;
    roomEntryHandledRef.current = true;

    const roomId = initialRoomIdRef.current;
    const stored = authUser ? readStoredConversations() : [];
    const meaningfulStored = stored.filter((item) => (
      Boolean(item.roomId) || (Array.isArray(item.messages) && item.messages.length > 0)
    ));
    // 새로고침하거나 다른 페이지에서 돌아왔을 때는 직전 대화를 자동으로
    // 펼치지 않는다. URL로 특정 방을 명시한 경우에만 해당 기록을 연다.
    let conversation = roomId
      ? meaningfulStored.find((item) => String(item.roomId) === String(roomId))
      : null;

    if (!conversation) conversation = createConversation(roomId);
    const nextConversations = meaningfulStored.some((item) => item.id === conversation.id)
      ? meaningfulStored
      : [conversation, ...meaningfulStored];

    setConversations(nextConversations);
    setActiveId(conversation.id);

    // 대화 기록에서 넘어온 room 파라미터는 한 번만 소비한다.
    // 이후 새로고침하면 초기 비활성 화면으로 돌아간다.
    if (roomId) window.history.replaceState({}, '', window.location.pathname);

    if (!authUser || !roomId) return undefined;

    const controller = new AbortController();
    setRoomLoading(true);
    fetchChatRoomMessages(roomId, controller.signal)
      .then((messages) => {
        updateConversation(conversation.id, (current) => ({
          ...current,
          messages: mapRoomMessages(roomId, messages),
        }));
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setError(loadError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRoomLoading(false);
      });

    return () => controller.abort();
  }, [authUser]);

  useEffect(() => {
    if (!authUser) return undefined;

    const controller = new AbortController();
    fetchChatRooms(controller.signal)
      .then((rooms) => {
        const generalRooms = (rooms || []).filter((room) => (
          String(room?.room_type || room?.roomType || 'general') === 'general'
        ));
        const characterRooms = (rooms || [])
          .filter((room) => {
            const type = String(room?.room_type || room?.roomType || '');
            return type === 'character' || type === 'group';
          })
          .map((room) => {
            const roomId = String(room.room_id ?? room.roomId ?? '');
            const members = Array.isArray(room.characters) ? room.characters.filter(Boolean) : [];
            const params = new URLSearchParams({ room: roomId });
            if (members.length) params.set('members', members.join(','));
            return {
              id: `linked-character-${roomId}`,
              roomId,
              roomType: String(room?.room_type || room?.roomType || 'character'),
              title: String(room.title || '').trim() || members.join(', ') || '캐릭터 대화',
              createdAt: room.created_at || room.createdAt || new Date().toISOString(),
              updatedAt: room.updated_at || room.updatedAt || room.created_at || room.createdAt || new Date().toISOString(),
              href: `/chat/group?${params.toString()}`,
              linked: true,
            };
          });

        setLinkedConversations(characterRooms);

        setConversations((current) => {
          const localByRoomId = new Map(
            current
              .filter((conversation) => conversation.roomId)
              .map((conversation) => [String(conversation.roomId), conversation]),
          );
          const serverRoomIds = new Set(generalRooms.map((room) => String(room.room_id ?? room.roomId ?? '')));
          const hydrated = generalRooms.map((room) => {
            const roomId = String(room.room_id ?? room.roomId ?? '');
            const local = localByRoomId.get(roomId);
            const serverTitle = String(room.title || '').trim();
            return {
              ...createConversation(roomId),
              ...local,
              roomId,
              title: serverTitle || local?.title || '무무와 영화 이야기',
              titleSeed: String(room.title_seed || room.titleSeed || local?.titleSeed || '').trim(),
              titleGenerated: Boolean(serverTitle) || Boolean(local?.titleGenerated),
              titlePersisted: Boolean(serverTitle),
              createdAt: local?.createdAt || room.created_at || room.createdAt || new Date().toISOString(),
              updatedAt: room.updated_at || room.updatedAt || local?.updatedAt || new Date().toISOString(),
              messages: Array.isArray(local?.messages) ? local.messages : [],
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
          setError(loadError.message);
        }
      });

    return () => controller.abort();
  }, [authUser]);

  useEffect(() => {
    if (!authUser) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [authUser, conversations]);

  useEffect(() => {
    if (!authUser) return;

    conversations.forEach((conversation) => {
      const firstUserMessage = (conversation.messages || []).find(
        (message) => message.role === 'user' && String(message.content || message.text || '').trim(),
      );
      const content = String(
        firstUserMessage?.content || firstUserMessage?.text || conversation.titleSeed || '',
      ).trim();
      const legacyDateTitle = /^\d{2}\.\s*\d{2}\./.test(String(conversation.title || ''));
      const legacyFallbackTitle = (
        !conversation.titleGenerated
        && Boolean(conversation.title)
        && content.startsWith(String(conversation.title))
      );
      const needsTitle = (
        !conversation.title
        || conversation.title === '새 대화'
        || conversation.title === '제목 생성 중…'
        || (
          conversation.title === '무무와 영화 이야기'
          && Boolean(content)
          && !conversation.titleGenerated
        )
        || legacyDateTitle
        || legacyFallbackTitle
      );
      if (!content || !needsTitle || titleRequestsRef.current.has(conversation.id)) return;

      titleRequestsRef.current.add(conversation.id);
      void generateChatTitle(content)
        .then((title) => {
          updateConversation(conversation.id, (current) => ({
            ...current,
            title: current.manualTitle ? current.title : title || content.slice(0, 30),
            titleGenerated: !current.manualTitle,
            titlePersisted: false,
          }));
        })
        .catch(() => {
          updateConversation(conversation.id, (current) => ({
            ...current,
            title: current.manualTitle ? current.title : content.slice(0, 30) || '새 대화',
            titleGenerated: false,
            titlePersisted: false,
          }));
        });
    });
  }, [authUser, conversations]);

  useEffect(() => {
    if (!authUser) return;

    conversations.forEach((conversation) => {
      if (
        !conversation.roomId
        || !conversation.titleGenerated
        || conversation.titlePersisted
        || !String(conversation.title || '').trim()
      ) return;

      updateConversation(conversation.id, (current) => ({ ...current, titlePersisted: 'saving' }));
      void updateChatRoomTitle(conversation.roomId, conversation.title)
        .then(() => {
          updateConversation(conversation.id, (current) => ({ ...current, titlePersisted: true }));
        })
        .catch(() => {
          updateConversation(conversation.id, (current) => ({ ...current, titlePersisted: 'failed' }));
        });
    });
  }, [authUser, conversations]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) || null,
    [activeId, conversations],
  );

  const newConversation = () => {
    abortRef.current?.abort();
    const conversation = createConversation();
    setConversations((current) => [
      conversation,
      ...current.filter((item) => (
        Boolean(item.roomId) || (Array.isArray(item.messages) && item.messages.length > 0)
      )),
    ]);
    setActiveId(conversation.id);
    setDraft('');
    setBusy(false);
    setError('');
  };

  const selectConversation = async (conversationId) => {
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation || busy) return;
    setActiveId(conversationId);
    setError('');

    if (!authUser || !conversation.roomId || conversation.messages?.length) return;
    setRoomLoading(true);
    try {
      const messages = await fetchChatRoomMessages(conversation.roomId);
      updateConversation(conversationId, (current) => ({
        ...current,
        messages: mapRoomMessages(conversation.roomId, messages),
      }));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setRoomLoading(false);
    }
  };

  const removeConversation = async (conversationId) => {
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation || busy) return;

    try {
      if (authUser && conversation.roomId) await deleteChatRoom(conversation.roomId);
    } catch (deleteError) {
      setError(deleteError.message);
      return;
    }

    const remaining = conversations.filter((item) => item.id !== conversationId);
    if (activeId === conversationId) {
      if (remaining.length) {
        setActiveId(remaining[0].id);
      } else {
        const replacement = createConversation();
        setConversations([replacement]);
        setActiveId(replacement.id);
        return;
      }
    }
    setConversations(remaining);
  };

  const renameConversation = (conversationId, title) => {
    const normalizedTitle = String(title || '').trim().slice(0, 30);
    if (!normalizedTitle) return;
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      title: normalizedTitle,
      manualTitle: true,
      titleGenerated: true,
      titlePersisted: false,
    }));
  };

  const toggleConversationPin = (conversationId) => {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      pinned: !conversation.pinned,
    }));
  };

  const sendMessage = async (contentOverride) => {
    const content = String(
      typeof contentOverride === 'string' ? contentOverride : draft,
    ).trim();
    if (!content || busy || !activeConversation) return;

    const conversationId = activeConversation.id;
    const roomId = authUser ? activeConversation.roomId : '';
    const history = (activeConversation.messages || [])
      .filter((message) => !message.pending && !message.error)
      .slice(-10)
      .map((message) => {
        const movies = message.movies || message.recommended_movies || [];
        return {
          role: message.role,
          content: String(message.content || message.text || '').slice(0, 1000),
          ...(message.character && message.character !== '무무'
            ? { character: message.character }
            : {}),
          ...(movies.length > 0 ? { recommended_movies: movies.slice(0, 3) } : {}),
        };
      });
    const pendingId = `pending-${crypto.randomUUID()}`;
    const createdAt = new Date().toISOString();
    const isFirstMessage = history.length === 0;

    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      title: isFirstMessage ? '제목 생성 중…' : conversation.title,
      updatedAt: createdAt,
      messages: [
        ...(conversation.messages || []),
        { id: crypto.randomUUID(), role: 'user', content, createdAt },
        {
          id: pendingId,
          role: 'assistant',
          character: '무무',
          emotion: 'searching',
          content: '',
          createdAt,
          pending: true,
        },
      ],
    }));
    setDraft('');
    setError('');
    setBusy(true);

    if (isFirstMessage) {
      titleRequestsRef.current.add(conversationId);
      void generateChatTitle(content)
        .then((title) => {
          updateConversation(conversationId, (conversation) => ({
            ...conversation,
            title: conversation.manualTitle ? conversation.title : title || content.slice(0, 30),
            titleGenerated: !conversation.manualTitle,
            titlePersisted: false,
          }));
        })
        .catch(() => {
          updateConversation(conversationId, (conversation) => ({
            ...conversation,
            title: conversation.manualTitle ? conversation.title : content.slice(0, 30) || '새 대화',
            titleGenerated: false,
            titlePersisted: false,
          }));
        });
    }

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = roomId
        ? await sendRoomMessage(
            roomId,
            { message: content, character: null, history, guest: !authUser },
            controller.signal,
          )
        : await sendChat(
            { message: content, character: null, history, guest: !authUser },
            controller.signal,
          );

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        roomId: response?.conversationId || conversation.roomId,
        messages: conversation.messages.map((message) => (
          message.id === pendingId
            ? {
                ...message,
                content: response?.answer || '응답 내용이 없습니다.',
                character: response?.character || '무무',
                intent: response?.intent,
                emotion: response?.emotion || 'default',
                movies: response?.movies || [],
                sources: response?.sources || [],
                pending: false,
              }
            : message
        )),
      }));

      if (!authUser && Number.isFinite(response?.guestRemaining)) {
        setGuestRemaining(response.guestRemaining);
      }

      if (authUser) void addRecommendedMovies(response?.movies || []);
    } catch (requestError) {
      const aborted = requestError.name === 'AbortError';
      const messageText = aborted ? '응답을 중단했습니다.' : requestError.message;
      if (!aborted) setError(messageText);
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) => (
          message.id === pendingId
            ? {
                ...message,
                content: messageText,
                emotion: aborted ? 'default' : 'sorry',
                pending: false,
                error: !aborted,
              }
            : message
        )),
      }));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const stopResponse = () => abortRef.current?.abort();

  return {
    activeId,
    busy,
    conversations,
    draft,
    error,
    guestRemaining,
    linkedConversations,
    messages: activeConversation?.messages || [],
    newConversation,
    renameConversation,
    removeConversation,
    roomLoading,
    selectConversation,
    sendMessage,
    setDraft,
    stopResponse,
    toggleConversationPin,
  };
}
