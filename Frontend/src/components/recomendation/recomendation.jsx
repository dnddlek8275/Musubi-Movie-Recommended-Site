import { useEffect, useMemo, useRef, useState } from 'react';

import {
  addLikedMovie,
  fetchLikedMovies,
  fetchMovies,
  fetchMoviesByGenre,
  fetchRecentMovies,
  removeLikedMovie,
} from '../../api.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import MovieCard from '../movieCard/MovieCard.jsx';
import MovieModal from '../movieCard/MovieModal.jsx';
import './recomendation.css';

const INITIAL_ROWS = 3;

function getItemsPerRow() {
  if (typeof window === 'undefined') return 7;

  if (window.matchMedia('(max-width: 520px)').matches) return 2;
  if (window.matchMedia('(max-width: 900px)').matches) return 3;
  if (window.matchMedia('(max-width: 1180px)').matches) return 4;

  return 7;
}

function normalizeSearchValue(value) {
  return String(value || '').toLowerCase();
}

function compactSearchValue(value) {
  return normalizeSearchValue(value).replace(/\s+/g, '');
}

function Recommendation({ authUser }) {
  const queryParams = new URLSearchParams(window.location.search);

  // 최근 본 영화 패널의 "더보기 ›"(?view=recent)로 들어왔을 때만 최근 본 영화 목록을 보여주고,
  // 그 외(menu3 등)로 들어오면 기존처럼 영화 추천 목록을 보여준다.
  const isRecentView = queryParams.get('view') === 'recent';

  // 장르별 추천의 "더보기 ›"(?genre=장르명)로 들어오면 장르 API 결과로 시작한다.
  const initialGenre = queryParams.get('genre') || '';
  const initialKeyword = queryParams.get('keyword') || initialGenre;

  const [movies, setMovies] = useState([]);
  const [likedMovies, setLikedMovies] = useState([]);
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [searchText, setSearchText] = useState(initialKeyword);
  const [status, setStatus] = useState('');
  const [itemsPerRow, setItemsPerRow] = useState(() => getItemsPerRow());
  const [visibleCount, setVisibleCount] = useState(
    () => getItemsPerRow() * INITIAL_ROWS
  );
  const loadMoreRef = useRef(null);
  const isInitialGenreSearch = Boolean(initialGenre) && searchText === initialGenre;

  useEffect(() => {
    const controller = new AbortController();

    const request = isRecentView
      ? fetchRecentMovies(controller.signal, 50).then((rawMovies) =>
          rawMovies.map(normalizeMovie)
        )
      : isInitialGenreSearch
        ? fetchMoviesByGenre(initialGenre, controller.signal, { limit: 50 }).then((rawMovies) =>
            rawMovies.map(normalizeMovie)
          )
        : fetchMovies(controller.signal, searchText, {
            limit: searchText.trim() ? 50 : 30,
          }).then((rawMovies) =>
            rawMovies.map(normalizeMovie)
          );

    request
      .then(setMovies)
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('영화 목록 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, [initialGenre, isRecentView, searchText]);

  useEffect(() => {
    if (!authUser) {
      setLikedMovies([]);
      return undefined;
    }

    const controller = new AbortController();

    fetchLikedMovies(controller.signal)
      .then((rawMovies) => {
        setLikedMovies(
          rawMovies
            .map((movie) => normalizeMovie(movie).title)
            .filter(Boolean)
        );
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setStatus(error.message);
      });

    return () => controller.abort();
  }, [authUser]);

  const filteredMovies = useMemo(() => {
    if (!isRecentView) return movies;

    const keyword = normalizeSearchValue(searchText).trim();
    const compactKeyword = compactSearchValue(searchText);

    if (!keyword) return movies;

    return movies.filter((movie) => {
      const title = normalizeSearchValue(movie.title);
      const genre = normalizeSearchValue(movie.genre);
      // 출연진(배우) 이름도 검색 대상에 포함해, 배우명을 치면 그 배우의 필모가 뜨게 한다.
      const cast = normalizeSearchValue(
        (Array.isArray(movie.cast) ? movie.cast : []).join(', ')
      );
      const compactTitle = compactSearchValue(movie.title);
      const compactGenre = compactSearchValue(movie.genre);
      const compactCast = compactSearchValue(cast);

      return (
        title.includes(keyword) ||
        genre.includes(keyword) ||
        cast.includes(keyword) ||
        compactTitle.includes(compactKeyword) ||
        compactGenre.includes(compactKeyword) ||
        compactCast.includes(compactKeyword)
      );
    });
  }, [isRecentView, movies, searchText]);

  const visibleMovies = filteredMovies.slice(0, visibleCount);
  const canLoadMore = visibleMovies.length < filteredMovies.length;

  useEffect(() => {
    const handleResize = () => {
      const nextItemsPerRow = getItemsPerRow();

      setItemsPerRow(nextItemsPerRow);
      setVisibleCount((currentVisibleCount) =>
        Math.max(currentVisibleCount, nextItemsPerRow * INITIAL_ROWS)
      );
    };

    window.addEventListener('resize', handleResize);

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    setVisibleCount(itemsPerRow * INITIAL_ROWS);
  }, [itemsPerRow, searchText, movies]);

  useEffect(() => {
    const loadMoreTarget = loadMoreRef.current;

    if (!loadMoreTarget || !canLoadMore) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;

        setVisibleCount((currentVisibleCount) =>
          Math.min(currentVisibleCount + itemsPerRow, filteredMovies.length)
        );
      },
      {
        rootMargin: '240px 0px',
      }
    );

    observer.observe(loadMoreTarget);

    return () => observer.disconnect();
  }, [canLoadMore, filteredMovies.length, itemsPerRow, visibleCount]);

  const handleToggleLike = async (movie) => {
    // 로그인하지 않은 상태에서는 좋아요를 누를 수 없다.
    if (!authUser) {
      setStatus('로그인 해주세요.');
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

  const emptyMessage = searchText.trim()
    ? '검색어가 포함된 영화가 없습니다.'
    : isRecentView
    ? '최근 본 영화가 없습니다.'
    : '추천 영화가 없습니다.';

  return (
    <main className="recommendation">
      <div className="recommendation__header">
        <div>
          <h2>{isRecentView ? '최근 본 영화' : '영화 추천'}</h2>
        </div>

        <input
          className="recommendation__search"
          type="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="영화 제목으로 검색"
          aria-label="영화 검색"
        />
      </div>

      {status ? (
        <p className="recommendation__status" role="status">
          {status}
        </p>
      ) : null}

      <div className="recommendation__result">
        {filteredMovies.length > 0 ? (
          <div className="recommendation__grid">
            {visibleMovies.map((movie, index) => (
              <MovieCard
                index={index}
                isLiked={likedMovies.includes(movie.title)}
                movie={movie}
                onToggleLike={handleToggleLike}
                onSelect={setSelectedMovie}
                key={movie.id ?? movie.title}
              />
            ))}
          </div>
        ) : (
          <p className="recommendation__empty">{emptyMessage}</p>
        )}

        {canLoadMore ? (
          <div
            className="recommendation__sentinel"
            ref={loadMoreRef}
            aria-hidden="true"
          />
        ) : null}
      </div>

      <MovieModal
        movie={selectedMovie}
        onClose={() => setSelectedMovie(null)}
        source={!isRecentView && !isInitialGenreSearch && searchText.trim() ? 'search' : 'direct'}
      />
    </main>
  );
}

export default Recommendation;
