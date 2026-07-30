import { useEffect, useRef, useState } from 'react';

import { fetchMovies } from '../../api.js';
import { HOME_MOVIE_COUNT } from './constants.js';
import MovieCard from '../movieCard/MovieCard.jsx';
import MovieModal from '../movieCard/MovieModal.jsx';
import SectionHeader from './SectionHeader.jsx';

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

function resolvePosterPath(value) {
  const path = String(value || '').trim();

  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

// 영화 응답에서 출연진(배우) 이름 목록을 뽑아낸다. 백엔드마다 필드명이 달라질 수 있어
// 흔한 후보를 모두 확인하고, 문자열/객체 배열 모두 이름만 뽑아 정리한다.
export function extractCast(rawMovie) {
  const raw =
    rawMovie?.actors ??
    rawMovie?.cast ??
    rawMovie?.casts ??
    rawMovie?.actor_names ??
    rawMovie?.credits ??
    [];

  const list = Array.isArray(raw) ? raw : String(raw).split(',');

  return list
    .map((item) => {
      if (item && typeof item === 'object') {
        return String(item.actor_name || item.name || item.actor || '').trim();
      }
      return String(item || '').trim();
    })
    .filter(Boolean);
}

// movies 테이블 응답(genres 배열, vote_average 등)을 MovieCard가 쓰는 형태로 정리
export function normalizeMovie(rawMovie) {
  const poster = resolvePosterPath(
    rawMovie?.posterUrl ||
      rawMovie?.poster_url ||
      rawMovie?.poster_path ||
      rawMovie?.poster ||
      rawMovie?.image_url ||
      rawMovie?.image ||
      ''
  );

  return {
    id: rawMovie?.id ?? rawMovie?.movie_id ?? rawMovie?.tmdb_id,
    title: rawMovie?.title || rawMovie?.name || rawMovie?.movie || '',
    genre: Array.isArray(rawMovie?.genres)
      ? rawMovie.genres.join(', ')
      : rawMovie?.genre || rawMovie?.genres || '',
    rating:
      rawMovie?.vote_average ??
      rawMovie?.rating ??
      rawMovie?.ranking_score ??
      rawMovie?.score ??
      '',
    year: rawMovie?.year,
    // 추천 이유: 백엔드 응답 키 오타(reson) 대응 — reason으로 통일해서 보존.
    reason: rawMovie?.reason ?? rawMovie?.reson ?? '',
    // 출연진을 검색에 쓰기 위해 이름 배열로 보존한다.
    cast: extractCast(rawMovie),
    poster_path: poster,
    poster,
  };
}

function RecommendationRow({ authUser, likedMovies, onToggleLike }) {
  const [movies, setMovies] = useState([]);
  const [error, setError] = useState('');
  const [selectedMovie, setSelectedMovie] = useState(null);
  const rowRef = useRef(null);

  const displayName =
    authUser?.nickname || authUser?.name || authUser?.username || '게스트';
  const title = `${displayName}님을 위한 영화 추천!`;

  const scrollByCards = (direction) => {
    const row = rowRef.current;
    if (!row) return;

    row.scrollBy({ left: direction * (212 + 30) * 3, behavior: 'smooth' });
  };

  useEffect(() => {
    const controller = new AbortController();

    fetchMovies(controller.signal)
      .then((rawMovies) => {
        setMovies(rawMovies.map(normalizeMovie).slice(0, HOME_MOVIE_COUNT));
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        console.error('영화 목록 불러오기 실패:', fetchError);
        setError(fetchError.message);
      });

    return () => controller.abort();
  }, []);

  return (
    <section className="index-recommendations" aria-label="개인 영화 추천">
      <SectionHeader icon="👏" title={title} />

      <div className="index-movie-slider">
        <button
          className="index-movie-slider-btn index-movie-slider-btn--prev"
          type="button"
          onClick={() => scrollByCards(-1)}
          aria-label="이전 영화 보기"
        >
          ‹
        </button>

        <div className="index-movie-row" ref={rowRef}>
          {movies.map((movie, index) => (
            <MovieCard
              index={index}
              isLiked={likedMovies.includes(movie.title)}
              movie={movie}
              onToggleLike={onToggleLike}
              onSelect={setSelectedMovie}
              key={movie.id}
            />
          ))}
        </div>

        <button
          className="index-movie-slider-btn index-movie-slider-btn--next"
          type="button"
          onClick={() => scrollByCards(1)}
          aria-label="다음 영화 보기"
        >
          ›
        </button>
      </div>

      {movies.length === 0 && error ? (
        <p className="index-status" role="status">
          {error}
        </p>
      ) : null}

      <MovieModal movie={selectedMovie} onClose={() => setSelectedMovie(null)} />
    </section>
  );
}

export default RecommendationRow;
