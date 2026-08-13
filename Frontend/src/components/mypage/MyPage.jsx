import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import {
  checkAccountNicknameAvailability,
  confirmAccountEmailVerification,
  deleteChatRoom,
  deleteMyAccount,
  deleteProfileImage,
  deletePreference,
  fetchChatRecommendedMovies,
  fetchChatRoomMessages,
  fetchChatRooms,
  fetchLikedMovies,
  fetchMyReviews,
  fetchPreferenceInsights,
  fetchRecentMovies,
  fetchUserPreferences,
  fetchUserProfile,
  fetchWishlistMovies,
  removeLikedMovie,
  requestAccountEmailVerification,
  resetLearnedPreferences,
  resolveMovieImage,
  updateAccountProfile,
  updateChatRoomTitle,
  updateProfileImage,
  updateUserPreferences,
} from '../../api.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import { PanelSkeleton, PosterRowSkeleton, SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';
import { getInternalMovieId } from '../../utils/movieIdentity.js';
import { formatRating } from '../../utils/formatRating.js';
import TastePreferenceModal from './TastePreferenceModal.jsx';
import './mypage.css';

const TABS = [
  ['overview', '한눈에 보기'],
  ['taste', '취향 관리'],
  ['chat', '대화 기록'],
  ['activity', '영화 활동'],
  ['reviews', '내 활동'],
  ['account', '계정 설정'],
];

const TASTE_TYPES = [
  ['genres', 'genre', '장르'],
  ['actors', 'actor', '배우'],
  ['keywords', 'keyword', '키워드'],
];

const DEFAULT_AVATAR = '/images/character/mu/upper-body/mu-upper-default-v1.webp';
const CHAT_STORAGE_KEYS = ['cineverse.autochat.conversations', 'cineverse.groupchat.conversations'];

function uniqueText(values) {
  return Array.from(new Set((Array.isArray(values) ? values : [])
    .map((value) => String(value?.value ?? value?.name ?? value ?? '').trim())
    .filter(Boolean)));
}

function learnedValues(data, key) {
  return uniqueText(data?.[key] || data?.[key.replace(/s$/, '')] || []).slice(0, 12);
}

function movieId(movie) {
  return getInternalMovieId(movie) ?? '';
}

function moviePoster(movie) {
  return resolveMovieImage(movie?.posterUrl || movie?.poster_url || movie?.poster_path || movie?.poster || '');
}

function formatDate(value) {
  const parsed = value ? new Date(value) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(parsed);
}

function readStoredChatMetadata() {
  const metadata = new Map();
  CHAT_STORAGE_KEYS.forEach((key) => {
    try {
      const stored = JSON.parse(window.localStorage.getItem(key) || (key.includes('groupchat') ? '{}' : '[]'));
      const conversations = Array.isArray(stored) ? stored : stored?.conversations;
      (Array.isArray(conversations) ? conversations : []).forEach((conversation) => {
        const roomId = conversation?.roomId ?? conversation?.room_id;
        const title = String(conversation?.title || '').trim();
        if (!roomId) return;
        const current = metadata.get(String(roomId)) || {};
        metadata.set(String(roomId), {
          ...current,
          ...(title && !['새 대화', '제목 생성 중…'].includes(title) ? { title } : {}),
          pinned: Boolean(conversation?.pinned),
        });
      });
    } catch (error) {
      // 손상된 로컬 기록 하나가 전체 마이페이지를 막지 않도록 건너뛴다.
    }
  });
  return metadata;
}

function updateStoredChatRoom(roomId, updater, room = null) {
  CHAT_STORAGE_KEYS.forEach((key) => {
    try {
      const fallback = key.includes('groupchat') ? '{}' : '[]';
      const stored = JSON.parse(window.localStorage.getItem(key) || fallback);
      const conversations = Array.isArray(stored) ? stored : stored?.conversations;
      if (!Array.isArray(conversations)) return;
      let matched = false;
      const next = conversations.map((conversation) => {
        if (String(conversation?.roomId ?? conversation?.room_id ?? '') !== String(roomId)) return conversation;
        matched = true;
        return updater(conversation);
      });
      const targetKey = room?.type === 'general'
        ? 'cineverse.autochat.conversations'
        : 'cineverse.groupchat.conversations';
      if (!matched && room && key === targetKey) {
        next.unshift(updater({
          id: `room-${roomId}`,
          roomId: String(roomId),
          title: room.title,
          members: room.members || [],
          messages: [],
        }));
      }
      window.localStorage.setItem(key, JSON.stringify(Array.isArray(stored) ? next : { ...stored, conversations: next }));
    } catch (error) {
      // 손상된 로컬 기록은 서버 기록 조작을 막지 않도록 건너뛴다.
    }
  });
}

function removeStoredChatRoom(roomId) {
  CHAT_STORAGE_KEYS.forEach((key) => {
    try {
      const fallback = key.includes('groupchat') ? '{}' : '[]';
      const stored = JSON.parse(window.localStorage.getItem(key) || fallback);
      const conversations = Array.isArray(stored) ? stored : stored?.conversations;
      if (!Array.isArray(conversations)) return;
      const next = conversations.filter((conversation) => (
        String(conversation?.roomId ?? conversation?.room_id ?? '') !== String(roomId)
      ));
      window.localStorage.setItem(key, JSON.stringify(Array.isArray(stored) ? next : { ...stored, conversations: next }));
    } catch (error) {
      // 손상된 로컬 기록은 서버 기록 삭제를 막지 않도록 건너뛴다.
    }
  });
}

function roomInfo(room, index, storedMetadata) {
  const id = room?.room_id ?? room?.roomId ?? room?.id ?? '';
  const type = room?.room_type || room?.roomType || 'general';
  const members = uniqueText(room?.characters);
  const stored = storedMetadata.get(String(id)) || {};
  const storedTitle = stored.title;
  const fallbackMessage = String(room?.fallbackTitle || '').replace(/\s+/g, ' ').trim();
  const title = storedTitle
    || room?.title
    || (fallbackMessage ? `${fallbackMessage.slice(0, 28)}${fallbackMessage.length > 28 ? '…' : ''}` : '')
    || (members.length ? members.join(' · ') : type === 'general' ? '무무와 영화 이야기' : '캐릭터 대화');
  const href = type === 'general'
    ? `/home?room=${id}`
    : `/chat/group?room=${id}${members.length ? `&members=${encodeURIComponent(members.join(','))}` : ''}`;
  return {
    id: String(id || `room-${index}`),
    title,
    href,
    members,
    type,
    pinned: room?.pinned ?? stored.pinned ?? false,
    date: formatDate(room?.updated_at || room?.updatedAt || room?.created_at || room?.createdAt),
  };
}

function EmptyState({ children }) {
  return <p className="mypage-empty">{children}</p>;
}

function TasteRow({ label, values, category }) {
  const formatValue = (value) => category === 'keywords' ? getKeywordLabel(value) : value;
  return (
    <div className="mypage-taste-row">
      <strong>{label}</strong>
      <div>{values.length ? values.slice(0, 6).map((value) => <span key={value}>{formatValue(value)}</span>) : <small>아직 분석 전</small>}</div>
    </div>
  );
}

function EditableTasteRow({ category, preferenceType, label, values, mode, editable = false, insight = '', insightLoading = false, onAdd, onRemove, busy }) {
  const [draft, setDraft] = useState('');
  const displayedValues = mode === 'learned' ? values.slice(0, 8) : values;
  const submit = (event) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    onAdd(category, value);
    setDraft('');
  };
  const insightReason = typeof insight === 'object' ? String(insight?.reason || '').trim() : String(insight || '').trim();
  const formatValue = (value) => category === 'keywords' ? getKeywordLabel(value) : value;
  const learnedSummary = insightLoading
    ? '무무가 취향을 분석하고 있어요…'
    : insightReason;
  return (
    <div className="mypage-taste-editor-row">
      <div className="mypage-taste-editor-row__heading">
        <strong>{label}</strong>
        {mode === 'learned' && learnedSummary ? <span>{learnedSummary}</span> : null}
      </div>
      <div className="mypage-taste-editor-row__rail">
        {displayedValues.length ? displayedValues.map((value) => (
          <span key={value}>{formatValue(value)}{editable ? <button disabled={busy} type="button" onClick={() => onRemove(category, preferenceType, value)} aria-label={`${formatValue(value)} 삭제`}>×</button> : null}</span>
        )) : <small>{mode === 'direct' ? '아직 입력한 취향이 없어요.' : '아직 분석 전'}</small>}
      </div>
      {mode === 'direct' && editable ? (
        <form onSubmit={submit}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={`${label} 추가`} /><button disabled={busy} type="submit">추가</button></form>
      ) : null}
    </div>
  );
}

function MovieStrip({ id, title, description, movies, emptyText = '아직 이곳에 표시할 영화가 없습니다.', liked = false, onUnlike, unlikeBusy }) {
  return (
    <section className="mypage-movie-section" id={id}>
      <header className="mypage-section-heading"><div><h2>{title}</h2>{description ? <p>{description}</p> : null}</div></header>
      {movies.length ? (
        <HorizontalScroller className="mypage-movie-strip" ariaLabel={`${title} 목록`}>
          {movies.map((movie, index) => {
            const id = movieId(movie);
            const poster = moviePoster(movie);
            return (
              <article className="mypage-movie-card" key={`${id || 'movie'}-${index}`}>
                <div className="mypage-movie-card__poster">
                  {id ? <a href={`/movies/${id}`} aria-label={`${movie.title || movie.name} 상세 보기`} /> : null}
                  {poster ? <img src={poster} alt="" /> : <span>포스터 준비 중</span>}
                  {liked ? (
                    <button className="mypage-movie-like is-liked" disabled={unlikeBusy === String(id)} type="button" onClick={() => onUnlike(movie)} aria-label={`${movie.title || movie.name} 좋아요 취소`}>♥</button>
                  ) : null}
                </div>
                {id ? <a className="mypage-movie-card__title" href={`/movies/${id}`}>{movie.title || movie.name || '제목 정보 없음'}</a> : <strong>{movie.title || movie.name || '제목 정보 없음'}</strong>}
                <small>{movie.genre || (Array.isArray(movie.genres) ? movie.genres.slice(0, 2).join(', ') : '영화')}</small>
              </article>
            );
          })}
        </HorizontalScroller>
      ) : <EmptyState>{emptyText}</EmptyState>}
    </section>
  );
}

function ReviewList({ reviews }) {
  return (
    <div className="mypage-review-list">
      {reviews.length ? reviews.map((review) => {
        const movie = review.movie || {};
        const id = movieId(movie);
        const poster = moviePoster(movie);
        const title = movie.title || movie.name || '제목 정보 없음';
        const comment = String(review.comment || '').trim();
        return (
          <a className="mypage-review-card" href={id ? `/movies/${id}` : undefined} key={review.id}>
            <div className="mypage-review-card__poster">
              {poster ? <img src={poster} alt="" /> : <span>포스터 준비 중</span>}
            </div>
            <div className="mypage-review-card__body">
              <header><strong>{title}</strong><span>★ {formatRating(review.score)}</span></header>
              <p className={comment ? '' : 'is-rating-only'}>{comment || '별점만 남긴 평가입니다.'}</p>
              <time dateTime={review.updated_at || review.created_at}>{formatDate(review.updated_at || review.created_at) || '날짜 정보 없음'}</time>
            </div>
            <b aria-hidden="true">›</b>
          </a>
        );
      }) : <EmptyState>아직 작성한 리뷰가 없습니다.</EmptyState>}
    </div>
  );
}

function ChatColumn({ title, rooms, side, onPin, onRename, onDelete }) {
  const [menuId, setMenuId] = useState('');
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (!menuId) return undefined;
    const closeMenu = (event) => {
      if (
        !(event.target instanceof Element)
        || !event.target.closest('.mypage-chat-record__actions, .mypage-chat-record__menu')
      ) setMenuId('');
    };
    document.addEventListener('pointerdown', closeMenu);
    window.addEventListener('resize', closeMenu);
    window.addEventListener('scroll', closeMenu, true);
    return () => {
      document.removeEventListener('pointerdown', closeMenu);
      window.removeEventListener('resize', closeMenu);
      window.removeEventListener('scroll', closeMenu, true);
    };
  }, [menuId]);

  return (
    <section className={`mypage-chat-column is-${side}`}>
      <header><h3>{title}</h3><span>{rooms.length}개의 대화방</span></header>
      <div>
        {rooms.length ? rooms.map((room) => (
          <article className="mypage-chat-record" key={room.id}>
            <a href={room.href}><strong>{room.title}</strong><time>{room.date || '날짜 정보 없음'}</time></a>
            <div className="mypage-chat-record__actions">
              <button className={`mypage-chat-record__pin${room.pinned ? ' is-pinned' : ''}`} type="button" onClick={() => onPin(room)} aria-label={room.pinned ? `${room.title} 고정 해제` : `${room.title} 상단 고정`} title={room.pinned ? '고정 해제' : '상단 고정'}>
                <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m14.8 4.2 5 5-2.4 1.1-3.3 3.3-.4 4-1.2 1.2-3.6-3.6-4.1 4.1-1.1-1.1 4.1-4.1-3.6-3.6 1.2-1.2 4-.4 3.3-3.3 1.1-2.4Z" /></svg>
              </button>
              <button className="mypage-chat-record__more" type="button" onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const menuWidth = 144;
                const menuHeight = 124;
                const gap = 8;
                const hasRoomOnRight = rect.right + gap + menuWidth <= window.innerWidth - gap;
                setMenuPosition({
                  top: Math.max(gap, Math.min(rect.top, window.innerHeight - menuHeight - gap)),
                  left: hasRoomOnRight
                    ? rect.right + gap
                    : Math.max(gap, rect.left - menuWidth - gap),
                });
                setMenuId((current) => current === room.id ? '' : room.id);
              }} aria-label={`${room.title} 메뉴`} aria-expanded={menuId === room.id}>⋮</button>
              {menuId === room.id ? createPortal(
                <div className="mypage-chat-record__menu" style={{ top: menuPosition.top, left: menuPosition.left }}>
                  <button type="button" onClick={() => { onPin(room); setMenuId(''); }}>{room.pinned ? '고정 해제' : '채팅 고정'}</button>
                  <button type="button" onClick={() => { onRename(room); setMenuId(''); }}>이름 수정</button>
                  <button className="is-danger" type="button" onClick={() => { onDelete(room); setMenuId(''); }}>삭제하기</button>
                </div>,
                document.body,
              ) : null}
            </div>
          </article>
        )) : <EmptyState>저장된 대화가 없습니다.</EmptyState>}
      </div>
    </section>
  );
}

function AccountEditor({ profile, authUser, onCancel, onSaved, onDeleteRequest }) {
  const initialEmail = profile.email || authUser?.email || '';
  const initialNickname = profile.nickname || authUser?.nickname || '';
  const [nickname, setNickname] = useState(initialNickname);
  const [email, setEmail] = useState(initialEmail);
  const [personalContext, setPersonalContext] = useState(profile.personal_context || authUser?.personal_context || '');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [nicknameCheck, setNicknameCheck] = useState({ checkedNickname: '', available: false });
  const [emailVerificationSent, setEmailVerificationSent] = useState(false);
  const [emailVerified, setEmailVerified] = useState(false);
  const [profileImage, setProfileImage] = useState(profile.profile_image || authUser?.profile_image || '');
  const [imageBusy, setImageBusy] = useState(false);
  const fileInputRef = useRef(null);
  const normalizedNickname = nickname.trim();
  const nicknameChanged = normalizedNickname.toLocaleLowerCase('ko-KR') !== initialNickname.trim().toLocaleLowerCase('ko-KR');
  const nicknameWasChecked = !nicknameChanged || (
    nicknameCheck.available
    && nicknameCheck.checkedNickname.toLocaleLowerCase('ko-KR') === normalizedNickname.toLocaleLowerCase('ko-KR')
  );
  const emailChanged = email.trim().toLowerCase() !== initialEmail.trim().toLowerCase();

  useEffect(() => {
    if (seconds <= 0) return undefined;
    const timer = window.setInterval(() => setSeconds((current) => Math.max(0, current - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [seconds]);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  const checkNickname = async () => {
    if (!nicknameChanged) { setMessage('현재 사용 중인 닉네임입니다.'); return; }
    if (normalizedNickname.length < 2) { setMessage('닉네임은 2자 이상 입력해 주세요.'); return; }
    setBusy(true); setMessage('');
    try {
      const result = await checkAccountNicknameAvailability(normalizedNickname);
      setNicknameCheck({ checkedNickname: normalizedNickname, available: result.available });
      setMessage(result.message || (result.available ? '사용 가능한 닉네임입니다.' : '이미 사용 중인 닉네임입니다.'));
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const sendCode = async () => {
    if (!emailChanged) { setMessage('새 이메일을 입력해 주세요.'); return; }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) { setMessage('올바른 이메일 형식으로 입력해 주세요.'); return; }
    setBusy(true); setMessage('');
    try {
      const result = await requestAccountEmailVerification(email.trim());
      setSeconds(Number(result.expires_in_seconds) || 300);
      setEmailVerificationSent(true);
      setEmailVerified(false);
      setCode('');
      setMessage('인증번호를 전송했습니다. 받은 번호를 입력해 주세요.');
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const confirmEmail = async () => {
    const nextEmail = email.trim().toLowerCase();
    if (!emailVerificationSent) { setMessage('먼저 인증번호를 전송해 주세요.'); return; }
    if (!/^\d{6}$/.test(code)) { setMessage('이메일 인증번호 6자리를 입력해 주세요.'); return; }
    setBusy(true); setMessage('');
    try {
      await confirmAccountEmailVerification(nextEmail, code);
      setEmailVerified(true);
      setMessage('이메일 인증이 완료되었습니다.');
    } catch (error) {
      setEmailVerified(false);
      setMessage(error.message);
    } finally { setBusy(false); }
  };

  const selectProfileImage = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setMessage('JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setMessage('프로필 이미지는 5MB 이하만 업로드할 수 있습니다.');
      return;
    }
    setImageBusy(true); setMessage('');
    try {
      const result = await updateProfileImage(file);
      const nextImage = result.user_profile || result.profile_image || '';
      setProfileImage(nextImage);
      onSaved({ profile_image: nextImage }, { keepOpen: true });
      setMessage('프로필 이미지를 변경했습니다.');
    } catch (error) { setMessage(error.message); }
    finally { setImageBusy(false); }
  };

  const removeProfileImage = async () => {
    if (!profileImage || imageBusy) return;
    setImageBusy(true); setMessage('');
    try {
      await deleteProfileImage();
      setProfileImage('');
      onSaved({ profile_image: '' }, { keepOpen: true });
      setMessage('프로필 이미지를 삭제했습니다.');
    } catch (error) { setMessage(error.message); }
    finally { setImageBusy(false); }
  };

  const submit = async (event) => {
    event.preventDefault();
    const nextNickname = nickname.trim();
    const nextEmail = email.trim().toLowerCase();
    if (nextNickname.length < 2) { setMessage('닉네임은 2자 이상 입력해 주세요.'); return; }
    if (!nicknameWasChecked) { setMessage('변경할 닉네임의 중복확인을 완료해 주세요.'); return; }
    if (emailChanged && !/^\S+@\S+\.\S+$/.test(nextEmail)) { setMessage('올바른 이메일 형식으로 입력해 주세요.'); return; }
    if (emailChanged && !emailVerified) { setMessage('새 이메일 인증을 완료해 주세요.'); return; }
    setBusy(true); setMessage('');
    try {
      const updated = await updateAccountProfile({ nickname: nextNickname, email: emailChanged ? nextEmail : '', verificationCode: emailChanged ? code : '', personalContext: personalContext.trim() });
      onSaved(updated);
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };

  const timerText = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  return (
    <section className="mypage-panel mypage-account-editor" aria-labelledby="account-editor-title">
      <header><span>ACCOUNT EDIT</span><h3 id="account-editor-title">계정 정보 입력 / 수정</h3></header>
      <form noValidate onSubmit={submit}>
        <div className="mypage-account-image-field">
          <span className="mypage-account-image-preview">
            <img src={profileImage || DEFAULT_AVATAR} alt="현재 프로필" onError={(event) => { event.currentTarget.src = DEFAULT_AVATAR; }} />
          </span>
          <div><strong>프로필 이미지</strong><small>JPG, PNG, WEBP · 최대 5MB</small><span><button disabled={imageBusy} type="button" onClick={() => fileInputRef.current?.click()}>{imageBusy ? '처리 중…' : '이미지 선택'}</button>{profileImage ? <button disabled={imageBusy} type="button" onClick={removeProfileImage}>삭제</button> : null}</span></div>
          <input ref={fileInputRef} className="mypage-account-image-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={selectProfileImage} />
        </div>
        <label>닉네임<span className="mypage-account-field-row"><input value={nickname} onChange={(event) => { setNickname(event.target.value); setNicknameCheck({ checkedNickname: '', available: false }); setMessage(''); }} maxLength={50} /><button disabled={busy || !nicknameChanged || nicknameWasChecked} type="button" onClick={checkNickname}>{nicknameWasChecked && nicknameChanged ? '확인 완료' : '중복확인'}</button></span></label>
        <label>이메일<span className="mypage-account-field-row"><input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setCode(''); setSeconds(0); setEmailVerificationSent(false); setEmailVerified(false); setMessage(''); }} /><button disabled={busy || !emailChanged} type="button" onClick={sendCode}>{emailVerificationSent ? '재전송' : '인증 전송'}</button></span></label>
        {emailChanged ? <label>인증번호<span className="mypage-account-field-row mypage-account-code-row"><span className="mypage-account-code"><input disabled={!emailVerificationSent || emailVerified} inputMode="numeric" maxLength={6} value={code} onChange={(event) => { setCode(event.target.value.replace(/\D/g, '')); setEmailVerified(false); }} placeholder="6자리 인증번호" />{seconds && !emailVerified ? <time>{timerText}</time> : null}</span><button disabled={busy || !emailVerificationSent || emailVerified || code.length !== 6} type="button" onClick={confirmEmail}>{emailVerified ? '인증 완료' : '인증 확인'}</button></span></label> : null}
        <label>무무에게 알려줄 내 정보<textarea value={personalContext} onChange={(event) => setPersonalContext(event.target.value)} maxLength={500} rows={3} placeholder="이름, 나이, 관심사, 좋아하는 것처럼 대화와 추천에 참고했으면 하는 내용을 자유롭게 적어주세요." /><span className="mypage-account-meta"><small>AI 대화와 영화 추천에만 참고합니다. 비밀번호나 주민등록번호 같은 민감 정보는 입력하지 마세요.</small><small>{personalContext.length}/500 · 선택 입력</small></span></label>
        {message ? <p className="mypage-account-message">{message}</p> : null}
        <footer><button type="button" onClick={onCancel}>취소</button><button disabled={busy} type="submit">{busy ? '저장 중…' : '변경사항 저장'}</button></footer>
      </form>
      <section className="mypage-account-danger" aria-labelledby="account-management-title">
        <div><h4 id="account-management-title">계정 관리</h4><p>탈퇴하면 저장된 취향과 활동 기록을 복구할 수 없습니다.</p></div>
        <button type="button" onClick={onDeleteRequest}>계정 탈퇴</button>
      </section>
    </section>
  );
}

function MyPage({ authUser, onLogout, onUserUpdate }) {
  const requestedTab = new URLSearchParams(window.location.search).get('tab');
  const [activeTab, setActiveTab] = useState(
    () => TABS.some(([key]) => key === requestedTab) ? requestedTab : 'overview'
  );
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [profile, setProfile] = useState({});
  const [preferences, setPreferences] = useState({ genres: [], actors: [], keywords: [] });
  const [learned, setLearned] = useState({});
  const [combined, setCombined] = useState({});
  const [rooms, setRooms] = useState([]);
  const [recent, setRecent] = useState([]);
  const [liked, setLiked] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [wishlisted, setWishlisted] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [unlikeBusy, setUnlikeBusy] = useState('');
  const [tasteBusy, setTasteBusy] = useState(false);
  const [tasteModalOpen, setTasteModalOpen] = useState(false);
  const [preferenceInsights, setPreferenceInsights] = useState({});
  const [insightsRequested, setInsightsRequested] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountDeleteConfirmOpen, setAccountDeleteConfirmOpen] = useState(false);
  const [accountDeleteBusy, setAccountDeleteBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      fetchUserProfile(controller.signal),
      fetchUserPreferences(controller.signal),
      fetchChatRooms(controller.signal),
      fetchRecentMovies(controller.signal, 50),
      fetchLikedMovies(controller.signal),
      fetchChatRecommendedMovies(controller.signal, 50),
      fetchMyReviews(controller.signal),
      fetchWishlistMovies(controller.signal),
    ]).then(async (results) => {
      if (controller.signal.aborted) return;
      const [profileResult, preferenceResult, roomResult, recentResult, likedResult, recommendedResult, reviewResult, wishlistResult] = results;
      if (profileResult.status === 'fulfilled') setProfile(profileResult.value || {});
      if (preferenceResult.status === 'fulfilled') {
        setPreferences(preferenceResult.value?.preferences || {});
        setLearned(preferenceResult.value?.learned_preferences || {});
        setCombined(preferenceResult.value?.combined_preferences || {});
      }
      if (roomResult.status === 'fulfilled') {
        const roomList = roomResult.value || [];
        const hydrated = await Promise.all(roomList.map(async (room) => {
          try {
            const messages = await fetchChatRoomMessages(room.room_id, controller.signal);
            const firstUser = messages.find((message) => message.role === 'user' && String(message.content || '').trim());
            return { ...room, fallbackTitle: firstUser?.content || '' };
          } catch (error) { return room; }
        }));
        if (!controller.signal.aborted) setRooms(hydrated);
      }
      if (recentResult.status === 'fulfilled') setRecent((recentResult.value || []).map(normalizeMovie));
      if (likedResult.status === 'fulfilled') setLiked((likedResult.value || []).map(normalizeMovie));
      if (recommendedResult.status === 'fulfilled') setRecommended((recommendedResult.value || []).map(normalizeMovie));
      if (reviewResult.status === 'fulfilled') setReviews(reviewResult.value || []);
      if (wishlistResult.status === 'fulfilled') setWishlisted((wishlistResult.value || []).map(normalizeMovie));
      if (results.some((result) => result.status === 'rejected')) setStatus('일부 기록을 불러오지 못했습니다.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const openArchiveSection = (tab) => setActiveTab(tab);

  useEffect(() => {
    if (activeTab !== 'taste' || insightsRequested) return;
    const controller = new AbortController();
    setInsightsRequested(true);
    setInsightsLoading(true);
    fetchPreferenceInsights(controller.signal)
      .then((result) => setPreferenceInsights(result || {}))
      .catch(() => setPreferenceInsights({
        genres: { value: '', reason: '분석 문장을 불러오지 못했습니다.' },
        actors: { value: '', reason: '분석 문장을 불러오지 못했습니다.' },
        keywords: { value: '', reason: '분석 문장을 불러오지 못했습니다.' },
      }))
      .finally(() => { if (!controller.signal.aborted) setInsightsLoading(false); });
    return () => controller.abort();
  }, [activeTab]);

  const displayName = profile.nickname || authUser?.nickname || authUser?.name || '사용자';
  const avatar = profile.profile_image || authUser?.profile_image || DEFAULT_AVATAR;
  const chatRows = useMemo(() => {
    const metadata = readStoredChatMetadata();
    return rooms
      .map((room, index) => roomInfo(room, index, metadata))
      .sort((left, right) => Number(Boolean(right.pinned)) - Number(Boolean(left.pinned)));
  }, [rooms]);
  const generalChats = chatRows.filter((room) => room.type === 'general');
  const characterChats = chatRows.filter((room) => room.type !== 'general');
  const direct = {
    genres: uniqueText(preferences.genres),
    actors: uniqueText(preferences.actors),
    keywords: uniqueText(preferences.keywords),
  };
  const learnedTaste = {
    genres: learnedValues(learned, 'genres'),
    actors: learnedValues(learned, 'actors'),
    keywords: learnedValues(learned, 'keywords'),
  };
  const combinedTaste = {
    genres: learnedValues(combined, 'genres').length
      ? learnedValues(combined, 'genres')
      : uniqueText([...direct.genres, ...learnedTaste.genres]),
    actors: learnedValues(combined, 'actors').length
      ? learnedValues(combined, 'actors')
      : uniqueText([...direct.actors, ...learnedTaste.actors]),
    keywords: learnedValues(combined, 'keywords').length
      ? learnedValues(combined, 'keywords')
      : uniqueText([...direct.keywords, ...learnedTaste.keywords]),
  };

  const handleUnlike = async (movie) => {
    const id = String(movieId(movie));
    if (!id || unlikeBusy) return;
    setUnlikeBusy(id); setStatus('');
    try {
      await removeLikedMovie(movie);
      setLiked((current) => current.filter((item) => String(movieId(item)) !== id));
    } catch (error) { setStatus(error.message); }
    finally { setUnlikeBusy(''); }
  };

  const toggleChatPin = (room) => {
    const pinned = !room.pinned;
    updateStoredChatRoom(room.id, (conversation) => ({ ...conversation, pinned }), room);
    setRooms((current) => current.map((item) => (
      String(item?.room_id ?? item?.roomId ?? item?.id ?? '') === room.id
        ? { ...item, pinned }
        : item
    )));
  };

  const renameChatRoom = async (room) => {
    const title = window.prompt('대화 이름을 입력해 주세요.', room.title || '');
    const normalized = String(title || '').trim();
    if (!normalized || normalized === room.title) return;
    setStatus('');
    try {
      await updateChatRoomTitle(room.id, normalized);
      updateStoredChatRoom(room.id, (conversation) => ({ ...conversation, title: normalized, manualTitle: true }), room);
      setRooms((current) => current.map((item) => (
        String(item?.room_id ?? item?.roomId ?? item?.id ?? '') === room.id
          ? { ...item, title: normalized }
          : item
      )));
    } catch (error) { setStatus(error.message); }
  };

  const removeChatRoom = async (room) => {
    setStatus('');
    try {
      await deleteChatRoom(room.id);
      removeStoredChatRoom(room.id);
      setRooms((current) => current.filter((item) => String(item?.room_id ?? item?.roomId ?? item?.id ?? '') !== room.id));
    } catch (error) { setStatus(error.message); }
  };

  const removeTaste = async (category, preferenceType, value, mode) => {
    if (tasteBusy) return;
    setTasteBusy(true); setStatus('');
    try {
      await deletePreference(preferenceType, value);
      setLearned((current) => ({ ...current, [category]: (current[category] || []).filter((item) => String(item?.value ?? item) !== value) }));
    } catch (error) { setStatus(error.message); }
    finally { setTasteBusy(false); }
  };

  const saveDirectTaste = async (nextPreferences) => {
    const nextDirect = {
      genres: uniqueText(nextPreferences?.genres),
      actors: uniqueText(nextPreferences?.actors),
      keywords: uniqueText(nextPreferences?.keywords),
    };
    setTasteBusy(true); setStatus('');
    try {
      await updateUserPreferences(nextDirect);
      setPreferences(nextDirect);
      setCombined({
        genres: uniqueText([...nextDirect.genres, ...learnedTaste.genres]),
        actors: uniqueText([...nextDirect.actors, ...learnedTaste.actors]),
        keywords: uniqueText([...nextDirect.keywords, ...learnedTaste.keywords]),
      });
      setTasteModalOpen(false);
      setStatus('직접 선택한 취향을 수정했습니다.');
    }
    catch (error) {
      setStatus(error.message);
      throw error;
    }
    finally { setTasteBusy(false); }
  };

  const handleResetLearnedTaste = async () => {
    if (tasteBusy) return;
    setTasteBusy(true); setStatus('');
    try {
      await resetLearnedPreferences();
      setLearned({ genres: [], actors: [], keywords: [] });
      setCombined({ genres: direct.genres, actors: direct.actors, keywords: direct.keywords });
      setPreferenceInsights({
        genres: { value: '', reason: '분석할 데이터가 더 필요해요.' },
        actors: { value: '', reason: '분석할 데이터가 더 필요해요.' },
        keywords: { value: '', reason: '분석할 데이터가 더 필요해요.' },
      });
      setResetConfirmOpen(false);
      setStatus('활동에서 학습한 취향을 초기화했습니다.');
    } catch (error) { setStatus(error.message); }
    finally { setTasteBusy(false); }
  };

  const handleDeleteAccount = async () => {
    if (accountDeleteBusy) return;
    setAccountDeleteBusy(true); setStatus('');
    try {
      await deleteMyAccount();
      window.location.replace('/');
    } catch (error) {
      setStatus(error.message);
      setAccountDeleteConfirmOpen(false);
      setAccountDeleteBusy(false);
    }
  };

  if (loading) {
    return <main className="mypage cinema-nav-page" aria-busy="true"><section className="mypage-shell mypage-skeleton" aria-hidden="true"><SkeletonBlock className="mypage-skeleton__hero" /><PanelSkeleton lines={3} /><PosterRowSkeleton count={6} /></section></main>;
  }

  return (
    <main className="mypage cinema-nav-page">
      <div className="mypage-shell">
        {status ? <p className="mypage-status">{status}</p> : null}
        <section className="mypage-profile-hero">
          <div className="mypage-profile-main"><div className="mypage-avatar"><img src={avatar} alt="" onError={(event) => { event.currentTarget.src = DEFAULT_AVATAR; }} /></div><div><span className="mypage-eyebrow">MUSUBI PROFILE</span><h1>{displayName}님의 취향 아카이브</h1><p>무무가 대화와 영화 활동을 통해 이해한 취향을 한곳에 모았어요.</p></div></div>
          <div className="mypage-profile-actions"><button type="button" onClick={() => setActiveTab('account')}>내 정보</button></div>
          <div className="mypage-stats">
            <button type="button" onClick={() => openArchiveSection('chat')}><strong>{chatRows.length}</strong><span>저장 대화</span></button>
            <button type="button" onClick={() => openArchiveSection('activity')}><strong>{recent.length}</strong><span>최근 본 영화</span></button>
            <button type="button" onClick={() => openArchiveSection('activity')}><strong>{liked.length}</strong><span>좋아요</span></button>
            <button type="button" onClick={() => openArchiveSection('reviews')}><strong>{reviews.length}</strong><span>리뷰</span></button>
            <button type="button" onClick={() => openArchiveSection('activity')}><strong>{recommended.length}</strong><span>채팅 추천</span></button>
          </div>
        </section>

        <nav className="mypage-tabs" aria-label="마이페이지 메뉴">{TABS.map(([key, label]) => <button className={activeTab === key ? 'is-active' : ''} type="button" onClick={() => setActiveTab(key)} key={key}>{label}</button>)}</nav>

        {activeTab === 'overview' ? <div className="mypage-overview">
          <div className="mypage-overview-grid">
            <article className="mypage-panel mypage-taste-panel"><header className="mypage-section-heading"><div><span>TASTE INSIGHT</span><h2>무무가 이해한 나</h2></div><button type="button" onClick={() => setActiveTab('taste')}>자세히 보기</button></header><TasteRow label="선호 장르" values={combinedTaste.genres} category="genres" /><TasteRow label="선호 배우" values={combinedTaste.actors} category="actors" /><TasteRow label="관심 키워드" values={combinedTaste.keywords} category="keywords" /></article>
            <article className="mypage-panel mypage-chat-panel"><header className="mypage-section-heading"><div><span>CONTINUE THE CONVERSATION</span><h2>대화 이어하기</h2></div><button type="button" onClick={() => setActiveTab('chat')}>전체 기록</button></header>{chatRows.length ? chatRows.slice(0, 3).map((room) => <a href={room.href} className="mypage-chat-row" key={room.id}><div><strong>{room.title}</strong><time>{room.date || '날짜 정보 없음'}</time></div><b>›</b></a>) : <EmptyState>아직 저장된 대화가 없습니다.</EmptyState>}</article>
          </div>
          <MovieStrip title="내가 좋아요 누른 영화" description="하트를 다시 누르면 좋아요를 취소할 수 있어요." movies={liked} liked onUnlike={handleUnlike} unlikeBusy={unlikeBusy} />
        </div> : null}

        {activeTab === 'taste' ? <section className="mypage-tab-page"><header><span>TASTE CONTROL</span><h2>나의 영화 취향</h2><p>직접 선택한 취향과 활동을 통해 발견한 취향을 한눈에 확인해보세요.</p></header><div className="mypage-taste-columns">
          <article className="mypage-panel mypage-taste-editor is-direct"><header><div><h3>직접 선택한 취향</h3><p>추천에 바로 반영되는 취향입니다. 장르, 배우, 키워드를 순서대로 다시 선택할 수 있어요.</p></div><button disabled={tasteBusy} type="button" onClick={() => setTasteModalOpen(true)}>수정하기</button></header>{TASTE_TYPES.map(([category, type, label]) => <EditableTasteRow key={category} category={category} preferenceType={type} label={label} values={direct[category]} mode="direct" busy={tasteBusy} onAdd={() => {}} onRemove={() => {}} />)}</article>
          <article className="mypage-panel mypage-taste-editor is-learned"><header><div><h3>활동에서 발견한 취향</h3><p>조회·좋아요·검색 활동을 바탕으로 무무가 발견한 취향입니다.</p></div><button className="is-reset" disabled={tasteBusy} type="button" onClick={() => setResetConfirmOpen(true)}>초기화</button></header>{TASTE_TYPES.map(([category, type, label]) => <EditableTasteRow key={category} category={category} preferenceType={type} label={label} values={learnedTaste[category]} mode="learned" insight={preferenceInsights[category]} insightLoading={insightsLoading} busy={tasteBusy} onAdd={() => {}} onRemove={(...args) => removeTaste(...args, 'learned')} />)}</article>
        </div></section> : null}

        {activeTab === 'chat' ? <section className="mypage-tab-page"><header><span>MY CONVERSATIONS</span><h2>대화 기록</h2><p>캐릭터 대화와 무무의 일반 대화를 나누어 확인할 수 있어요.</p></header><div className="mypage-chat-columns"><ChatColumn title="캐릭터 대화" rooms={characterChats} side="character" onPin={toggleChatPin} onRename={renameChatRoom} onDelete={removeChatRoom} /><ChatColumn title="일반 대화" rooms={generalChats} side="general" onPin={toggleChatPin} onRename={renameChatRoom} onDelete={removeChatRoom} /></div></section> : null}

        {activeTab === 'activity' ? <section className="mypage-tab-page"><header><span>MOVIE ACTIVITY</span><h2>나의 영화 활동</h2><p>조회와 좋아요, 찜, 대화 추천을 기준으로 정리했습니다.</p></header><MovieStrip id="wishlisted-movies" title="찜한 영화" description="보고 싶은 영화를 모아두는 공간이에요." movies={wishlisted} emptyText="아직 찜한 영화가 없습니다." /><MovieStrip id="recent-movies" title="최근 본 영화" movies={recent} /><MovieStrip id="chat-recommended-movies" title="채팅에서 추천받은 영화" movies={recommended} /><MovieStrip id="liked-movies" title="내가 좋아요 누른 영화" movies={liked} liked onUnlike={handleUnlike} unlikeBusy={unlikeBusy} /></section> : null}

        {activeTab === 'reviews' ? <section className="mypage-tab-page"><header><span>MY ACTIVITY</span><h2>내 활동</h2><p>내가 남긴 리뷰를 확인하고 해당 영화 상세페이지로 이동할 수 있어요.</p></header><ReviewList reviews={reviews} /></section> : null}

        {activeTab === 'account' ? <section className="mypage-tab-page"><header><span>ACCOUNT</span><h2>계정 설정</h2><p>프로필과 로그인 정보를 확인합니다.</p></header>{accountOpen ? <AccountEditor profile={profile} authUser={authUser} onCancel={() => setAccountOpen(false)} onDeleteRequest={() => setAccountDeleteConfirmOpen(true)} onSaved={(updated, options = {}) => { const next = { ...profile, ...updated }; setProfile(next); onUserUpdate?.({ ...authUser, ...updated }); if (!options.keepOpen) setAccountOpen(false); }} /> : <article className="mypage-panel mypage-account-card"><div><span>프로필</span><span className="mypage-account-card__avatar"><img src={avatar} alt="" onError={(event) => { event.currentTarget.src = DEFAULT_AVATAR; }} /></span></div><div><span>닉네임</span><strong>{displayName}</strong></div><div><span>이메일</span><strong>{profile.email || authUser?.email || '-'}</strong></div><button type="button" onClick={() => setAccountOpen(true)}>계정 정보 입력 / 수정</button></article>}</section> : null}
      </div>
      {tasteModalOpen ? <TastePreferenceModal initialPreferences={direct} saving={tasteBusy} onClose={() => { if (!tasteBusy) setTasteModalOpen(false); }} onSave={saveDirectTaste} /> : null}
      {resetConfirmOpen ? <div className="mypage-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !tasteBusy) setResetConfirmOpen(false); }}><section className="mypage-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="taste-reset-title"><span>TASTE RESET</span><h2 id="taste-reset-title">활동에서 발견한 취향을 초기화할까요?</h2><p>조회·좋아요·검색으로 학습한 취향 점수만 삭제됩니다.<br />직접 선택한 취향은 그대로 유지됩니다.</p><footer><button disabled={tasteBusy} type="button" onClick={() => setResetConfirmOpen(false)}>취소</button><button disabled={tasteBusy} type="button" onClick={handleResetLearnedTaste}>{tasteBusy ? '초기화 중…' : '초기화'}</button></footer></section></div> : null}
      {accountDeleteConfirmOpen ? <div className="mypage-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !accountDeleteBusy) setAccountDeleteConfirmOpen(false); }}><section className="mypage-confirm-modal is-account-delete" role="dialog" aria-modal="true" aria-labelledby="account-delete-title"><span>ACCOUNT DELETE</span><h2 id="account-delete-title">정말 계정을 탈퇴하시겠어요?</h2><p>탈퇴하면 계정 정보와 좋아요, 영화 활동, 취향 및 대화 기록이 삭제되며 되돌릴 수 없습니다.</p><footer><button disabled={accountDeleteBusy} type="button" onClick={() => setAccountDeleteConfirmOpen(false)}>취소</button><button disabled={accountDeleteBusy} type="button" onClick={handleDeleteAccount}>{accountDeleteBusy ? '탈퇴 처리 중…' : '계정 탈퇴'}</button></footer></section></div> : null}
    </main>
  );
}

export default MyPage;
