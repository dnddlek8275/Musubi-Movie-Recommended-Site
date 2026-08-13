import { useEffect, useState } from 'react';

import { fetchMovies, getLocalPreferences } from '../../api.js';
import { HOME_MOVIE_COUNT } from './constants.js';
import MovieCard from '../movieCard/MovieCard.jsx';
import { PosterRowSkeleton } from '../common/LoadingSkeleton.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import SectionHeader from './SectionHeader.jsx';
import { getInternalMovieId } from '../../utils/movieIdentity.js';
import { navigateTo } from '../../navigation.js';

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
    id: getInternalMovieId(rawMovie),
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

function movieLikeKey(movie) {
  const id = movie?.movie_id ?? movie?.id;
  if (id !== undefined && id !== null) return `id:${id}`;

  const title = String(movie?.title || '').trim().toLocaleLowerCase('ko-KR');
  return title ? `title:${title}` : '';
}

function RecommendationRow({ authUser, likedMovieKeys = [], onToggleLike }) {
  const [movies, setMovies] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const displayName =
    authUser?.nickname || authUser?.name || authUser?.username || '게스트';
  const title = `${displayName}님을 위한 영화 추천!`;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    const guestPreferences = authUser ? null : getLocalPreferences();

    fetchMovies(controller.signal, '', { preferences: guestPreferences, limit: HOME_MOVIE_COUNT })
      .then((rawMovies) => {
        setMovies(rawMovies.map(normalizeMovie).slice(0, HOME_MOVIE_COUNT));
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        console.error('영화 목록 불러오기 실패:', fetchError);
        setError(fetchError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [authUser]);

  return (
    <section className="index-recommendations" aria-label="개인 영화 추천">
      <SectionHeader icon="👏" title={title} />

      <div className="index-movie-slider">
        <HorizontalScroller className="index-movie-row" ariaLabel="개인 추천 영화 목록">
          {loading ? <PosterRowSkeleton count={7} /> : movies.map((movie, index) => (
            <MovieCard
              index={index}
              isLiked={likedMovieKeys.includes(movieLikeKey(movie))}
              movie={movie}
              onToggleLike={onToggleLike}
              onSelect={(movie) => navigateTo(`/movies/${movie.id}`)}
              key={movie.id}
            />
          ))}
        </HorizontalScroller>
      </div>

      {movies.length === 0 && error ? (
        <p className="index-status" role="status">
          {error}
        </p>
      ) : null}

    </section>
  );
}

export default RecommendationRow;
