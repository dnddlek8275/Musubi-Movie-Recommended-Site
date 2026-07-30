import { useEffect, useState } from 'react';

import {
  addLikedMovie,
  fetchCharacters,
  fetchLikedMovies,
  likeMovie,
  removeLikedMovie,
} from '../../api.js';
import GenreSection from './GenreSection.jsx';
import HeroArea from './HeroArea.jsx';
import MiddlePanels from './MiddlePanels.jsx';
import RecommendationRow from './RecommendationRow.jsx';
import { VISIBLE_CHARACTER_COUNT } from './constants.js';
import './index.css';

// DB/API에서 받아온 캐릭터 데이터를 프론트에서 쓰기 좋은 형태로 정리하는 함수
function normalizeCharacter(rawCharacter, index) {
  const name = String(rawCharacter?.name || rawCharacter?.character || '').trim();

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

function IndexPage({ authUser }) {
  const [likedMovies, setLikedMovies] = useState([]);
  const [status, setStatus] = useState('');
  const [characters, setCharacters] = useState([]);
  const [visibleCharacters, setVisibleCharacters] = useState([]);

  // 캐릭터 랜덤으로 뽑음
  const pickRandomCharacters = (source) => {
    const pool = source ?? characters;
    const shuffledCharacters = [...pool].sort(() => Math.random() - 0.5);

    setVisibleCharacters(
      shuffledCharacters.slice(0, VISIBLE_CHARACTER_COUNT)
    );
  };

  // 화면 처음 열림 → 캐릭터 목록 요청 → 성공하면 랜덤으로 일부만 노출
  useEffect(() => {
    const controller = new AbortController();

    fetchCharacters(controller.signal)
      .then((rawCharacters) => {
        const normalized = rawCharacters.map(normalizeCharacter).filter(Boolean);

        setCharacters(normalized);
        pickRandomCharacters(normalized);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('캐릭터 목록 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!authUser) {
      setLikedMovies([]);
      return undefined;
    }

    const controller = new AbortController();
    fetchLikedMovies(controller.signal)
      .then((movies) => {
        setLikedMovies(movies.map((movie) => movie.title).filter(Boolean));
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

    const wasLiked = likedMovies.includes(movie.title);

    setStatus('');
    setLikedMovies((current) =>
      wasLiked
        ? current.filter((title) => title !== movie.title)
        : [...current, movie.title]
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
      setLikedMovies((current) =>
        wasLiked
          ? Array.from(new Set([...current, movie.title]))
          : current.filter((title) => title !== movie.title)
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
        likedMovies={likedMovies}
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
