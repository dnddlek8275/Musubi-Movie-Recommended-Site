import { useEffect, useMemo, useRef, useState } from 'react';

import {
  fetchActors,
  fetchCharacters,
  fetchChatRooms,
  fetchLikedMovies,
  fetchMovies,
  fetchRecentMovies,
  fetchUserPreferences,
  fetchUserProfile,
  fetchChatRecommendedMovies,
  getRecommendedMovies,
  deletePreference,
  deletePreferenceType,
  deleteProfileImage,
  removeLikedMovie,
  savePreferredActor,
  updateProfileImage,
  updateUserPreferences,
  updateUserProfile,
} from '../../api.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import './mypage.css';

const GENRE_SLOT_COUNT = 7;
const CHAT_PREVIEW_COUNT = 4;
const RECOMMENDATION_SLOT_COUNT = 6;
const PICKED_MOVIE_SLOT_COUNT = 9;

function toTagText(items) {
  return Array.isArray(items) ? items.join(', ') : '';
}

function parseTags(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

// 포스터 URL을 여러 필드에서 찾고, 상대경로면 TMDB 베이스를 붙인다.
// 하드코딩 fallback(picsum) 없이, 없으면 빈 문자열을 반환한다(→ 검은 placeholder).
function getPoster(movie) {
  const raw =
    movie?.poster ||
    movie?.poster_path ||
    movie?.poster_url ||
    movie?.posterUrl ||
    movie?.image_url ||
    movie?.image ||
    '';
  const path = String(raw).trim();

  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function getMovieGenre(movie) {
  if (movie?.genre) return movie.genre;
  if (Array.isArray(movie?.genres)) return movie.genres.join(', ');
  return movie?.genres || '';
}

function formatRating(movie) {
  return movie?.rating || movie?.vote_average || '0.0';
}

function MoviePosterCard({ isRemovable = false, movie, index, onRemove }) {
  const poster = getPoster(movie);

  return (
    <article className="mypage-poster-card">
      <div className="mypage-poster-card__image">
        {poster ? (
          <img src={poster} alt="" />
        ) : (
          <div className="mypage-poster-card__placeholder" aria-hidden="true" />
        )}
        <button
          className="mypage-heart"
          type="button"
          onClick={isRemovable && onRemove ? () => onRemove(movie) : undefined}
          aria-label={`${movie.title} 찜 해제`}
          title={isRemovable ? '찜 해제' : '찜한 영화'}
        >
          ♡
        </button>
      </div>
      <div className="mypage-poster-card__info">
        <strong>
          {movie.title}
          {movie.year ? ` (${movie.year})` : ''}
        </strong>
        <span>{getMovieGenre(movie) || '영화'}</span>
        <em>★ {formatRating(movie)}</em>
      </div>
    </article>
  );
}

// 데이터가 없을 때도 카드 자리는 그대로 비워서 보여주는 빈 포스터 박스
function EmptyPosterCard() {
  return <article className="mypage-poster-card mypage-poster-card--empty" aria-hidden="true" />;
}

function EditInput({ disabled, label, onChange, value }) {
  return (
    <label className="mypage-edit-field">
      <span>{label}</span>
      <input value={value} disabled={disabled} onChange={onChange} />
    </label>
  );
}

function MyPage({ authUser, onUserUpdate }) {
  const [profile, setProfile] = useState({
    email: authUser?.email || '',
    nickname: authUser?.nickname || '',
    profile_image: authUser?.profile_image || '',
  });
  // 프로필 이미지 업로드 직후 즉시 미리보기용(서버가 내부 경로를 줄 수 있어 로컬 URL 사용)
  const [avatarPreview, setAvatarPreview] = useState('');
  const [preferenceText, setPreferenceText] = useState({
    genres: '',
    actors: '',
    keywords: '',
  });
  const [movies, setMovies] = useState([]);
  const [likedMovies, setLikedMovies] = useState([]);
  const [recentMovies, setRecentMovies] = useState([]);
  // AI/캐릭터 채팅에서 추천받은 영화를 마이페이지 추천에 연결한다.
  // 초기값은 로컬 캐시(즉시 표시), 이후 서버(/user/chatai-reommended-movies)로 갱신.
  const [chatRecommended, setChatRecommended] = useState(() => getRecommendedMovies());
  const [characters, setCharacters] = useState([]);
  const [actors, setActors] = useState([]);
  const [actorsError, setActorsError] = useState('');
  const [chatRooms, setChatRooms] = useState([]);
  const [isActorPickerOpen, setIsActorPickerOpen] = useState(false);
  const [isProfileEditing, setIsProfileEditing] = useState(false);
  const [isPreferenceEditing, setIsPreferenceEditing] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [addingGenreIndex, setAddingGenreIndex] = useState(null);
  const [newGenreInput, setNewGenreInput] = useState('');
  const [isChatHistoryModalOpen, setIsChatHistoryModalOpen] = useState(false);
  const [isPreferenceDeleteModalOpen, setIsPreferenceDeleteModalOpen] = useState(false);
  const [deletingPreferenceType, setDeletingPreferenceType] = useState('');
  const [areKeywordsTruncated, setAreKeywordsTruncated] = useState(false);
  const keywordListRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    Promise.allSettled([
      fetchUserProfile(controller.signal),
      fetchUserPreferences(controller.signal),
      fetchMovies(controller.signal),
      fetchLikedMovies(controller.signal),
      fetchRecentMovies(controller.signal),
      fetchCharacters(controller.signal),
      fetchChatRooms(controller.signal),
      fetchActors(controller.signal),
      fetchChatRecommendedMovies(controller.signal),
    ]).then((results) => {
      if (controller.signal.aborted) return;

      const [
        profileResult,
        preferencesResult,
        moviesResult,
        likedResult,
        recentResult,
        characterResult,
        chatRoomsResult,
        actorsResult,
        chatRecommendedResult,
      ] = results;

      // 서버 응답이 빈 배열이어도 로컬의 오래된 추천 이력을 남기지 않는다.
      if (
        chatRecommendedResult.status === 'fulfilled' &&
        Array.isArray(chatRecommendedResult.value)
      ) {
        setChatRecommended(chatRecommendedResult.value);
      }

      if (profileResult.status === 'fulfilled') {
        setProfile({
          email: profileResult.value.email || authUser?.email || '',
          nickname: profileResult.value.nickname || authUser?.nickname || '',
          profile_image:
            profileResult.value.profile_image || authUser?.profile_image || '',
        });
      }

      if (preferencesResult.status === 'fulfilled') {
        const preferences =
          preferencesResult.value.preferences || preferencesResult.value || {};

        setPreferenceText({
          genres: toTagText(preferences.genres),
          actors: toTagText(preferences.actors),
          keywords: toTagText(preferences.keywords),
        });
      }

      if (moviesResult.status === 'fulfilled') {
        setMovies(moviesResult.value.map(normalizeMovie));
      }

      if (likedResult.status === 'fulfilled') {
        setLikedMovies(likedResult.value.map((movie) => normalizeMovie(movie)));
      }

      if (recentResult.status === 'fulfilled') {
        setRecentMovies(recentResult.value.map((movie) => normalizeMovie(movie)));
      }

      if (characterResult.status === 'fulfilled') {
        setCharacters(characterResult.value);
      }

      if (chatRoomsResult.status === 'fulfilled') {
        setChatRooms(chatRoomsResult.value);
      }

      if (actorsResult.status === 'fulfilled') {
        setActors(actorsResult.value);
      } else {
        // 서버 에러(state: 'error') 등으로 실패한 경우만 에러 안내를 남긴다.
        setActorsError(actorsResult.reason?.message || '배우 목록을 불러오지 못했습니다.');
      }

      if (results.some((result) => result.status === 'rejected')) {
        setStatusMessage('일부 정보를 불러오지 못했습니다.');
      }
    });

    return () => controller.abort();
  }, [authUser]);

  const preferences = useMemo(
    () => ({
      genres: parseTags(preferenceText.genres),
      actors: parseTags(preferenceText.actors),
      keywords: parseTags(preferenceText.keywords),
    }),
    [preferenceText]
  );

  // index/KeywordPanel.jsx와 동일하게 DB의 genres, actors, keywords를 자르지 않고 그대로 표시한다.
  // 각 태그에 어떤 분류(장르/배우/키워드)에서 왔는지 함께 담아, X 버튼으로 개별 삭제할 때 사용한다.
  const keywordTags = [
    ...(preferences.genres || []).map((text) => ({ text, category: 'genres' })),
    ...(preferences.actors || []).map((text) => ({ text, category: 'actors' })),
    ...(preferences.keywords || []).map((text) => ({ text, category: 'keywords' })),
  ];

  useEffect(() => {
    const keywordList = keywordListRef.current;

    if (!keywordList || isPreferenceEditing) {
      setAreKeywordsTruncated(false);
      return undefined;
    }

    const updateTruncation = () => {
      setAreKeywordsTruncated(keywordList.scrollHeight > keywordList.clientHeight + 1);
    };

    updateTruncation();
    const resizeObserver = new ResizeObserver(updateTruncation);
    resizeObserver.observe(keywordList);

    return () => resizeObserver.disconnect();
  }, [isPreferenceEditing, preferenceText]);

  const displayName = profile.nickname || authUser?.nickname || '게스트';
  // "채팅 이력" 추천은 AI/캐릭터 채팅에서 실제로 추천받은 영화만 보여준다.
  // 채팅 기록이 없으면 비워 둔다(일반 추천으로 폴백하지 않음).
  const recommendationMovies = chatRecommended
    .map((movie) => normalizeMovie(movie))
    .filter((movie) => movie.title)
    .filter((movie, index, list) => {
      const key = String(movie.id ?? movie.title);
      return list.findIndex((item) => String(item.id ?? item.title) === key) === index;
    })
    .slice(0, RECOMMENDATION_SLOT_COUNT);
  const pickedMovies = likedMovies.slice(0, PICKED_MOVIE_SLOT_COUNT);
  // user_preferences의 actors를 기준으로 표시하고, 사진은 /actors 응답(없으면 같은 이름의 캐릭터)에서 가져온다.
  const preferredActors = preferences.actors.map((actorName) => {
    const matchedActor = actors.find((actor) => actor.name === actorName);
    const matchedCharacter = characters.find(
      (character) => character.name === actorName
    );

    return {
      id: matchedActor?.id || actorName,
      name: actorName,
      image_url:
        matchedActor?.image_url ||
        matchedCharacter?.image_url ||
        matchedCharacter?.imageUrl ||
        matchedCharacter?.img ||
        '',
    };
  });

  // + 버튼으로 추가할 수 있는 배우(이미 선호에 있는 배우는 제외)
  const availableActors = actors.filter(
    (actor) => actor.name && !preferences.actors.includes(actor.name)
  );

  // 선호 배우 + "배우 추가" 슬롯 1칸을 빼고 남는 칸은 빈 자리로 채운다.
  const emptyActorSlotCount = Math.max(
    0,
    GENRE_SLOT_COUNT - preferredActors.length - 1
  );

  const genreButtons = preferences.genres;

  // /chat/rooms 응답을 대화 이력 행으로 정리한다.
  // - 제목: 이야기한 캐릭터 이름들(characters). 없으면 일반(CineBuddy) 방으로 본다.
  // - 링크: 방 종류에 맞는 페이지로 room_id를 넘겨, 눌렀을 때 그 대화가 이어지게 한다.
  const allChatRows = chatRooms.map((room, index) => {
    const roomId = room.room_id ?? room.roomId ?? room.id ?? '';
    const roomType = room.room_type || room.roomType || 'general';
    const names = (Array.isArray(room.characters) ? room.characters : [])
      .map((character) => (typeof character === 'string' ? character : character?.name))
      .filter(Boolean);

    const title =
      names.length > 0
        ? names.join(', ')
        : roomType === 'group'
          ? '그룹 대화'
          : 'CineBuddy';

    let href;
    if (roomType === 'group') {
      href = `/chat/group?room=${roomId}&members=${encodeURIComponent(names.join(','))}`;
    } else if (roomType === 'character') {
      href = `/chat?room=${roomId}&characterName=${encodeURIComponent(names[0] || '')}`;
    } else {
      href = `/chat/auto?room=${roomId}`;
    }

    return { key: String(roomId) || `room-${index}`, title, href };
  });
  const hasMoreChatHistory = allChatRows.length > CHAT_PREVIEW_COUNT;
  const chatRows = allChatRows.slice(0, hasMoreChatHistory ? CHAT_PREVIEW_COUNT - 1 : CHAT_PREVIEW_COUNT);

  const avatarUrl =
    avatarPreview ||
    profile.profile_image ||
    '/images/cinebuddy.png';

  const hasProfileImage = Boolean(avatarPreview || profile.profile_image);

  // 프로필 이미지 변경: 파일 선택 즉시 PATCH /user/profile_image 업로드.
  const handleProfileImageChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // 같은 파일 다시 선택 가능하도록 초기화
    if (!file) return;

    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setStatusMessage('jpg, png, webp 이미지만 업로드할 수 있어요.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setStatusMessage('이미지는 최대 5MB까지 업로드할 수 있어요.');
      return;
    }

    try {
      const result = await updateProfileImage(file);
      const uploadedImage = result?.user_profile || '';
      // 이전 미리보기 URL 정리 후 서버 URL(없으면 로컬 미리보기)로 갱신
      setAvatarPreview((current) => {
        if (current) URL.revokeObjectURL(current);
        return uploadedImage || URL.createObjectURL(file);
      });
      if (uploadedImage) {
        setProfile((current) => ({ ...current, profile_image: uploadedImage }));
      }
      setStatusMessage('프로필 이미지를 변경했습니다.');
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  // 프로필 이미지 삭제: DELETE /user/delete/profile_image
  const handleProfileImageDelete = async () => {
    try {
      await deleteProfileImage();
      setAvatarPreview((current) => {
        if (current) URL.revokeObjectURL(current);
        return '';
      });
      setProfile((current) => ({ ...current, profile_image: '' }));
      setStatusMessage('프로필 이미지를 삭제했습니다.');
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  const handleSaveProfile = async () => {
    try {
      const savedProfile = await updateUserProfile(profile);
      const nextUser = {
        ...(authUser || {}),
        email: savedProfile.email || profile.email,
        nickname: savedProfile.nickname || profile.nickname,
      };

      localStorage.setItem('auth_user', JSON.stringify(nextUser));
      onUserUpdate?.(nextUser);
      setIsProfileEditing(false);
      setStatusMessage('내 정보가 저장되었습니다.');
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  const handleSavePreferences = async () => {
    try {
      await updateUserPreferences(preferences);
      setIsPreferenceEditing(false);
      setStatusMessage('관심 키워드가 저장되었습니다.');
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  // 장르별 추천의 빈 "+" 슬롯을 누르면 그 자리에서 바로 장르를 추가할 수 있게 함
  const handleAddGenre = async () => {
    const nextGenre = newGenreInput.trim();

    setAddingGenreIndex(null);
    setNewGenreInput('');

    if (!nextGenre || preferences.genres.includes(nextGenre)) return;

    const nextGenres = [...preferences.genres, nextGenre];
    setPreferenceText((current) => ({ ...current, genres: nextGenres.join(', ') }));

    try {
      await updateUserPreferences({ ...preferences, genres: nextGenres });
      setStatusMessage(`'${nextGenre}' 장르를 추가했습니다.`);
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  // "배우 추가" 슬롯의 + 를 누른 뒤 목록에서 배우를 고르면 선호 배우에 추가하고 저장한다.
  const handleAddActor = async (actor) => {
    setIsActorPickerOpen(false);

    if (!actor?.name || preferences.actors.includes(actor.name)) return;

    const nextActors = [...preferences.actors, actor.name];
    const nextPreferences = {
      genres: preferences.genres,
      actors: nextActors,
      keywords: preferences.keywords,
    };

    setPreferenceText({
      genres: nextPreferences.genres.join(', '),
      actors: nextActors.join(', '),
      keywords: nextPreferences.keywords.join(', '),
    });

    try {
      // 서버에 선호 배우 저장 (POST /movies/actor/{actor_id})
      if (actor.id) {
        const saved = await savePreferredActor(actor.id);

        // 서버가 최종 선호 배우 목록을 주면 그 값으로 동기화한다.
        if (Array.isArray(saved?.user_preferred_actors)) {
          setPreferenceText((current) => ({
            ...current,
            actors: saved.user_preferred_actors.join(', '),
          }));
        }
      }

      await updateUserPreferences(nextPreferences);
      setStatusMessage(`'${actor.name}' 배우를 추가했습니다.`);
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  // 배우/장르/키워드 태그의 X 버튼: 해당 항목을 선호 목록에서 개별 삭제하고 저장한다.
  const handleRemovePreference = async (category, value) => {
    const nextPreferences = {
      genres: preferences.genres,
      actors: preferences.actors,
      keywords: preferences.keywords,
      [category]: (preferences[category] || []).filter((item) => item !== value),
    };

    setPreferenceText({
      genres: nextPreferences.genres.join(', '),
      actors: nextPreferences.actors.join(', '),
      keywords: nextPreferences.keywords.join(', '),
    });

    // 앱 카테고리(genres/actors/keywords) → 서버 preference_type(genre/actor/keyword) 매핑.
    const typeMap = { genres: 'genre', actors: 'actor', keywords: 'keyword' };
    const preferenceType = typeMap[category];

    try {
      if (preferenceType) {
        // 서버에서 선호값 삭제 (DELETE /user/preference/delete)
        const saved = await deletePreference(preferenceType, value);

        // 서버가 최종 선호 배열을 주면 그 값으로 화면을 갱신한다.
        setPreferenceText((current) => ({
          ...current,
          genres: saved.genres.join(', '),
          actors: saved.actors.join(', '),
        }));
      }

      await updateUserPreferences(nextPreferences);
      setStatusMessage(`'${value}'을(를) 삭제했습니다.`);
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

  const handleDeletePreferenceType = async (preferenceType) => {
    if (deletingPreferenceType) return;

    setDeletingPreferenceType(preferenceType);
    setStatusMessage('');

    try {
      const result = await deletePreferenceType(preferenceType);
      const refreshed = await fetchUserPreferences();
      const nextPreferences = refreshed.preferences || refreshed || {};

      setPreferenceText({
        genres: toTagText(nextPreferences.genres),
        actors: toTagText(nextPreferences.actors),
        keywords: toTagText(nextPreferences.keywords),
      });
      setIsPreferenceDeleteModalOpen(false);
      setStatusMessage(result.message || '선택한 취향을 모두 삭제했습니다.');
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setDeletingPreferenceType('');
    }
  };

  const handleRemoveLikedMovie = async (movie) => {
    setLikedMovies((current) => current.filter((item) => item.title !== movie.title));

    try {
      await removeLikedMovie(movie);
    } catch (error) {
      setLikedMovies((current) => [movie, ...current]);
      setStatusMessage(error.message);
    }
  };

  return (
    <main className="mypage">
      {statusMessage ? <p className="mypage-status">{statusMessage}</p> : null}

      <section className="mypage-top">
        <article className="mypage-welcome-card">
          <button
            className="mypage-text-link"
            type="button"
            onClick={isProfileEditing ? handleSaveProfile : () => setIsProfileEditing(true)}
          >
            {isProfileEditing ? '저장하기' : '내정보 수정하기'} ›
          </button>

          <div className="mypage-avatar-wrap">
            <div className="mypage-avatar-media">
              <img
                className="mypage-avatar"
                src={avatarUrl}
                alt=""
                onError={(event) => {
                  // 프로필 이미지 URL이 깨졌을 때(내부 경로/도달 불가) 기본 이미지로 대체.
                  if (event.currentTarget.src.endsWith('/images/cinebuddy.png')) return;
                  event.currentTarget.src = '/images/cinebuddy.png';
                }}
              />

              <label className="mypage-avatar-edit" title="프로필 사진 변경">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleProfileImageChange}
                  hidden
                />
                <span aria-hidden="true">📷</span>
                <span className="sr-only">프로필 사진 변경</span>
              </label>
            </div>

            {hasProfileImage ? (
              <button
                type="button"
                className="mypage-avatar-delete"
                onClick={handleProfileImageDelete}
              >
                사진 삭제
              </button>
            ) : null}
          </div>

          <div className="mypage-welcome-card__copy">
            {isProfileEditing ? (
              <div className="mypage-edit-stack">
                <EditInput
                  label="닉네임"
                  value={profile.nickname}
                  disabled={false}
                  onChange={(event) =>
                    setProfile((current) => ({ ...current, nickname: event.target.value }))
                  }
                />
                <EditInput
                  label="이메일"
                  value={profile.email}
                  disabled={false}
                  onChange={(event) =>
                    setProfile((current) => ({ ...current, email: event.target.value }))
                  }
                />
              </div>
            ) : (
              <h1>{displayName}님! 환영합니다!</h1>
            )}
          </div>
        </article>

        <article className="mypage-keyword-card">
          <div className="mypage-card-title">
            <h2>나의 관심 키워드</h2>
            <div className="mypage-card-actions">
              <button
                className="mypage-delete-all"
                type="button"
                onClick={() => setIsPreferenceDeleteModalOpen(true)}
              >
                전체 삭제
              </button>
              <button
                className="mypage-text-link"
                type="button"
                onClick={isPreferenceEditing ? handleSavePreferences : () => setIsPreferenceEditing(true)}
              >
                {isPreferenceEditing ? '저장하기' : '수정하기'} ›
              </button>
            </div>
          </div>

          {isPreferenceEditing ? (
            <div className="mypage-edit-stack mypage-edit-stack--keywords">
              <EditInput
                label="장르"
                value={preferenceText.genres}
                disabled={false}
                onChange={(event) =>
                  setPreferenceText((current) => ({ ...current, genres: event.target.value }))
                }
              />
              <EditInput
                label="배우"
                value={preferenceText.actors}
                disabled={false}
                onChange={(event) =>
                  setPreferenceText((current) => ({ ...current, actors: event.target.value }))
                }
              />
              <EditInput
                label="키워드"
                value={preferenceText.keywords}
                disabled={false}
                onChange={(event) =>
                  setPreferenceText((current) => ({ ...current, keywords: event.target.value }))
                }
              />
            </div>
          ) : (
            <div
              ref={keywordListRef}
              className={`mypage-keywords${areKeywordsTruncated ? ' mypage-keywords--truncated' : ''}`}
            >
              {keywordTags.map((tag, index) => (
                <span className="mypage-keyword-chip" key={`${tag.category}-${tag.text}-${index}`}>
                  {tag.text}
                  <button
                    className="mypage-remove-x"
                    type="button"
                    onClick={() => handleRemovePreference(tag.category, tag.text)}
                    aria-label={`${tag.text} 삭제`}
                    title="삭제"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </article>
      </section>

      <section className="mypage-recommend-chat">
        <div className="mypage-recommend">
          <h2>{displayName} 님을 위한 영화 추천, 채팅 이력</h2>
          <div className="mypage-poster-row mypage-poster-row--compact">
            {recommendationMovies.map((movie, index) => (
              <MoviePosterCard movie={movie} index={index} key={movie.id || movie.title} />
            ))}
            {Array.from({
              length: Math.max(0, RECOMMENDATION_SLOT_COUNT - recommendationMovies.length),
            }).map((_, index) => (
              <EmptyPosterCard key={`empty-recommend-${index}`} />
            ))}
          </div>
        </div>

        <aside className="mypage-chat-list" aria-label="채팅 이력">
          {chatRows.map((row) => (
            <a className="mypage-chat-item" href={row.href} key={row.key}>
              <strong>{row.title}와 대화중 ....</strong>
              <span>대화하기 ›</span>
            </a>
          ))}

          {hasMoreChatHistory ? (
            <button
              type="button"
              className="mypage-chat-item mypage-chat-item--more"
              onClick={() => setIsChatHistoryModalOpen(true)}
              aria-label="이전 대화 내역 모두 보기"
            >
              ...
            </button>
          ) : (
            Array.from({ length: Math.max(0, CHAT_PREVIEW_COUNT - chatRows.length) }).map(
              (_, index) => (
                <div
                  className="mypage-chat-item mypage-chat-item--empty"
                  key={`empty-${index}`}
                  aria-hidden="true"
                />
              )
            )
          )}
        </aside>
      </section>

      <section className="mypage-actors">
        <h2>선호 배우</h2>
        <div className="mypage-actor-panel">
          {preferredActors.map((actor, index) => (
            <article className="mypage-actor" key={actor.id || index}>
              <div className="mypage-actor__media">
                {/* 사진을 누르면 해당 배우 이름으로 검색 페이지로 이동 */}
                <a
                  className="mypage-actor__circle"
                  href={`/recommendations?keyword=${encodeURIComponent(actor.name)}`}
                  title={`${actor.name} 검색`}
                  aria-label={`${actor.name} 검색`}
                >
                  {actor.image_url ? (
                    <img src={actor.image_url} alt="" />
                  ) : (
                    <span>{actor.name ? actor.name.slice(0, 1) : ''}</span>
                  )}
                </a>
                <button
                  className="mypage-remove-x mypage-remove-x--actor"
                  type="button"
                  onClick={() => handleRemovePreference('actors', actor.name)}
                  aria-label={`${actor.name} 삭제`}
                  title="삭제"
                >
                  ×
                </button>
              </div>
              <strong>{actor.name}</strong>
            </article>
          ))}

          {/* 배우 추가 슬롯 */}
          <article className="mypage-actor">
            <div className="mypage-actor__media">
              <button
                className="mypage-actor__circle mypage-actor__circle--add"
                type="button"
                onClick={() => setIsActorPickerOpen(true)}
                aria-label="배우 추가"
                title="배우 추가"
              >
                +
              </button>
            </div>
            <strong>배우 추가</strong>
          </article>

          {Array.from({ length: emptyActorSlotCount }).map((_, index) => (
            <article
              className="mypage-actor mypage-actor--empty"
              key={`empty-actor-${index}`}
              aria-hidden="true"
            >
              <div className="mypage-actor__media">
                <div className="mypage-actor__circle" />
              </div>
              <strong />
            </article>
          ))}
        </div>
      </section>

      <section className="mypage-genres">
        <h2>장르별 추천</h2>
        <div className="mypage-genre-row">
          {Array.from({ length: GENRE_SLOT_COUNT }).map((_, index) => {
            const genre = genreButtons[index];

            if (genre) {
              return (
                <div className="mypage-genre-slot" key={index}>
                  <a
                    className="mypage-genre-button"
                    href={`/recommendations?keyword=${encodeURIComponent(genre)}`}
                  >
                    {genre}
                  </a>
                  <button
                    className="mypage-remove-x mypage-remove-x--genre"
                    type="button"
                    onClick={() => handleRemovePreference('genres', genre)}
                    aria-label={`${genre} 삭제`}
                    title="삭제"
                  >
                    ×
                  </button>
                </div>
              );
            }

            if (addingGenreIndex === index) {
              return (
                <input
                  autoFocus
                  className="mypage-genre-input"
                  key={index}
                  value={newGenreInput}
                  onChange={(event) => setNewGenreInput(event.target.value)}
                  onBlur={handleAddGenre}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      handleAddGenre();
                    }
                    if (event.key === 'Escape') {
                      setAddingGenreIndex(null);
                      setNewGenreInput('');
                    }
                  }}
                  placeholder="장르 입력"
                />
              );
            }

            return (
              <button
                className="mypage-genre-button mypage-genre-button--add"
                type="button"
                key={index}
                onClick={() => setAddingGenreIndex(index)}
                aria-label="장르 추가"
              >
                +
              </button>
            );
          })}
        </div>
      </section>

      <section className="mypage-picked">
        <h2>찜한 영화</h2>
        <div className="mypage-poster-row">
          {pickedMovies.map((movie, index) => (
            <MoviePosterCard
              movie={movie}
              index={index}
              key={movie.id || `${movie.title}-${index}`}
              isRemovable={likedMovies.some((likedMovie) => likedMovie.title === movie.title)}
              onRemove={handleRemoveLikedMovie}
            />
          ))}
          {Array.from({
            length: Math.max(0, PICKED_MOVIE_SLOT_COUNT - pickedMovies.length),
          }).map((_, index) => (
            <EmptyPosterCard key={`empty-picked-${index}`} />
          ))}
        </div>
      </section>

      {isChatHistoryModalOpen ? (
        <div
          className="mypage-modal-backdrop"
          onClick={() => setIsChatHistoryModalOpen(false)}
          role="presentation"
        >
          <div
            className="mypage-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="전체 대화 이력"
          >
            <button
              className="mypage-modal__close"
              type="button"
              onClick={() => setIsChatHistoryModalOpen(false)}
              aria-label="닫기"
            >
              ×
            </button>

            <h3 className="mypage-modal__title">그동안 나눈 대화 이력</h3>

            <div className="mypage-modal__list">
              {allChatRows.map((row) => (
                <a className="mypage-chat-item" href={row.href} key={row.key}>
                  <strong>{row.title}와 대화중 ....</strong>
                  <span>바로가기 ›</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {isPreferenceDeleteModalOpen ? (
        <div
          className="mypage-modal-backdrop"
          onClick={() => {
            if (!deletingPreferenceType) setIsPreferenceDeleteModalOpen(false);
          }}
          role="presentation"
        >
          <div
            className="mypage-modal mypage-preference-delete-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="preference-delete-title"
          >
            <button
              className="mypage-modal__close"
              type="button"
              disabled={Boolean(deletingPreferenceType)}
              onClick={() => setIsPreferenceDeleteModalOpen(false)}
              aria-label="닫기"
            >
              ×
            </button>

            <h3 className="mypage-modal__title" id="preference-delete-title">
              취향 전체 삭제
            </h3>
            <p className="mypage-preference-delete-modal__description">
              삭제할 취향 종류를 선택하세요. 해당 종류의 저장된 취향과 자동 학습 점수가 모두 삭제됩니다.
            </p>

            <div className="mypage-preference-delete-options">
              {[
                { type: 'genre', label: '선호 장르 전체 삭제' },
                { type: 'actor', label: '선호 배우 전체 삭제' },
                { type: 'keyword', label: '관심 키워드 전체 삭제' },
              ].map((option) => (
                <button
                  className="mypage-preference-delete-option"
                  type="button"
                  key={option.type}
                  disabled={Boolean(deletingPreferenceType)}
                  onClick={() => handleDeletePreferenceType(option.type)}
                >
                  {deletingPreferenceType === option.type ? '삭제 중…' : option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {isActorPickerOpen ? (
        <div
          className="mypage-modal-backdrop"
          onClick={() => setIsActorPickerOpen(false)}
          role="presentation"
        >
          <div
            className="mypage-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="배우 추가"
          >
            <button
              className="mypage-modal__close"
              type="button"
              onClick={() => setIsActorPickerOpen(false)}
              aria-label="닫기"
            >
              ×
            </button>

            <h3 className="mypage-modal__title">선호 배우 추가</h3>

            <div className="mypage-actor-picker">
              {availableActors.length > 0 ? (
                availableActors.map((actor) => (
                  <button
                    className="mypage-actor-pick"
                    type="button"
                    key={actor.id || actor.name}
                    onClick={() => handleAddActor(actor)}
                  >
                    <span className="mypage-actor-pick__circle">
                      {actor.image_url ? (
                        <img src={actor.image_url} alt="" />
                      ) : (
                        <span>{actor.name ? actor.name.slice(0, 1) : '+'}</span>
                      )}
                    </span>
                    <span className="mypage-actor-pick__name">{actor.name}</span>
                  </button>
                ))
              ) : (
                <p className="mypage-actor-picker__empty">
                  {actorsError
                    ? actorsError
                    : actors.length === 0
                    ? '등록된 배우가 없습니다.'
                    : '이미 모든 배우를 추가했습니다.'}
                </p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default MyPage;
