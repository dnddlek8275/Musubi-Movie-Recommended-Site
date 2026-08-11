import { useEffect, useState } from 'react';

import {
  addLikedMovie,
  fetchCharacters,
  fetchLikedMovies,
  fetchUserPreferences,
  getLocalPreferences,
  likeMovie,
  removeLikedMovie,
} from '../../api.js';
import GenreSection from './GenreSection.jsx';
import HeroArea from './HeroArea.jsx';
import MiddlePanels from './MiddlePanels.jsx';
import RecommendationRow from './RecommendationRow.jsx';
import { VISIBLE_CHARACTER_COUNT } from './constants.js';
import './index.css';

// 좋아요 여부는 번역/원문 제목이 달라져도 같은 값을 유지하는 DB movie_id로
// 판별한다. id가 없는 임시 영화 데이터만 정규화한 제목을 보조 키로 사용한다.
function movieLikeKey(movie) {
  const id = movie?.movie_id ?? movie?.id;
  if (id !== undefined && id !== null) return `id:${id}`;

  const title = String(movie?.title || '').trim().toLocaleLowerCase('ko-KR');
  return title ? `title:${title}` : '';
}

// DB/API에서 받아온 캐릭터 데이터를 프론트에서 쓰기 좋은 형태로 정리하는 함수
function normalizeCharacter(rawCharacter, index) {
  const name = String(rawCharacter?.name || rawCharacter?.character || '').trim();

  if (!name) return null;

  return {
    id: String(rawCharacter?.id ?? rawCharacter?.character_id ?? name ?? index),
    name,
    actor: String(rawCharacter?.actor || '').trim(),
    genres: Array.isArray(rawCharacter?.genres) ? rawCharacter.genres : [],
    keywords: Array.isArray(rawCharacter?.keywords) ? rawCharacter.keywords : [],
    movieTitle: String(rawCharacter?.movie_title || '').trim(),
    image:
      rawCharacter?.image ||
      rawCharacter?.image_url ||
      rawCharacter?.avatar_url ||
      '',
  };
}

function characterPreferenceScore(character, preferences) {
  const normalize = (value) => String(value || '').trim().toLocaleLowerCase('ko-KR');
  const preferredActors = new Set((preferences?.actors || []).map(normalize));
  const preferredGenres = new Set((preferences?.genres || []).map(normalize));
  const preferredKeywords = new Set((preferences?.keywords || []).map(normalize));

  let score = preferredActors.has(normalize(character.actor)) ? 8 : 0;
  score += character.genres.some((genre) => preferredGenres.has(normalize(genre))) ? 4 : 0;
  score += character.keywords.some((keyword) => preferredKeywords.has(normalize(keyword))) ? 6 : 0;
  return score;
}

function IndexPage({ authUser }) {
  const [likedMovieKeys, setLikedMovieKeys] = useState([]);
  const [status, setStatus] = useState('');
  const [characters, setCharacters] = useState([]);
  const [visibleCharacters, setVisibleCharacters] = useState([]);
  const [activePreferences, setActivePreferences] = useState({ genres: [], actors: [], keywords: [] });

  // 캐릭터 랜덤으로 뽑음
  const pickRandomCharacters = (source, preferences = activePreferences) => {
    const pool = source ?? characters;
    const shuffledCharacters = [...pool]
      .map((character) => ({
        character,
        preferenceScore: characterPreferenceScore(character, preferences),
        randomOrder: Math.random(),
      }))
      .sort(
        (left, right) =>
          right.preferenceScore - left.preferenceScore ||
          left.randomOrder - right.randomOrder
      )
      .map(({ character }) => character);

    setVisibleCharacters(
      shuffledCharacters.slice(0, VISIBLE_CHARACTER_COUNT)
    );
  };

  // 화면 처음 열림 → 캐릭터 목록 요청 → 성공하면 랜덤으로 일부만 노출
  useEffect(() => {
    const controller = new AbortController();

    const preferencesRequest = authUser
      ? fetchUserPreferences(controller.signal)
          .then((data) => data.preferences || {})
          .catch((error) => {
            if (error.name === 'AbortError') throw error;
            return { genres: [], actors: [], keywords: [] };
          })
      : Promise.resolve(getLocalPreferences());

    Promise.all([fetchCharacters(controller.signal), preferencesRequest])
      .then(([rawCharacters, preferences]) => {
        const normalized = rawCharacters.map(normalizeCharacter).filter(Boolean);

        setCharacters(normalized);
        setActivePreferences(preferences);
        pickRandomCharacters(normalized, preferences);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('캐릭터 목록 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, [authUser]);

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
        if (error.name !== 'AbortError') setStatus(error.message);
      });

    return () => controller.abort();
  }, [authUser]);

  // 다음 버튼 누르면 랜덤 캐릭터 다시 뽑기
  const handleNextCharacters = () => {
    pickRandomCharacters();
  };

  // 하트 토글
  const handleToggleLike = async (movie) => {
    // 로그인하지 않은 상태에서는 좋아요를 누를 수 없다.
    if (!authUser) {
      setStatus('로그인 후 좋아요를 누를 수 있어요.');
      return;
    }

    const likeKey = movieLikeKey(movie);
    if (!likeKey) {
      setStatus('영화 식별 정보가 없어 좋아요를 변경할 수 없습니다.');
      return;
    }

    const wasLiked = likedMovieKeys.includes(likeKey);

    setStatus('');
    setLikedMovieKeys((current) =>
      wasLiked
        ? current.filter((key) => key !== likeKey)
        : Array.from(new Set([...current, likeKey]))
    );

    try {
      if (wasLiked) {
        await removeLikedMovie(movie);
      } else if (movie.id !== undefined && movie.id !== null) {
        await likeMovie(movie.id);
      } else {
        await addLikedMovie(movie);
      }
    } catch (error) {
      setLikedMovieKeys((current) =>
        wasLiked
          ? Array.from(new Set([...current, likeKey]))
          : current.filter((key) => key !== likeKey)
      );
      setStatus(error.message);
    }
  };

  return (
    <main className="index-page">
      <HeroArea
        authUser={authUser}
        onNextCharacters={handleNextCharacters}
        visibleCharacters={visibleCharacters}
      />

      <RecommendationRow
        authUser={authUser}
        likedMovieKeys={likedMovieKeys}
        onToggleLike={handleToggleLike}
      />

      {status ? (
        <p className="index-status" role="status">
          {status}
        </p>
      ) : null}

      <MiddlePanels authUser={authUser} />

      <GenreSection />
    </main>
  );
}

export default IndexPage;
