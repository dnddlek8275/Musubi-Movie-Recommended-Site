import { useEffect, useRef, useState } from 'react';

import {
  addLikedMovie,
  fetchDiscoverySections,
  fetchLikedMovies,
  fetchSearchSections,
  getLocalPreferences,
  removeLikedMovie,
} from '../../api.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import MovieCard from '../movieCard/MovieCard.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';
import './recomendation.css';

function sectionTitle(section, displayName) {
  if (section.key === 'for-you') {
    return `${displayName}님을 위한 영화를 추천해드릴게요.`;
  }
  if (section.key === 'recent-likes') {
    return `${displayName}님이 마음을 남긴 영화, 최근 순서로 모았어요`;
  }
  if (section.key === 'preferred-genres') {
    return `${displayName}님의 장르 취향을 조금 더 넓혀볼까요?`;
  }
  if (section.key === 'preferred-actors') {
    return `${displayName}님이 눈여겨본 배우들의 다른 작품이에요`;
  }
  if (section.key === 'site-popular') {
    return 'Musubi 실시간 인기 차트';
  }
  if (section.key === 'random-picks') {
    return `${displayName}님, 우연히 만난 영화가 인생 영화가 될지도 몰라요`;
  }
  if (!section.preference_value) return section.title;

  const label = section.preference_type === 'keyword'
    ? getKeywordLabel(section.preference_value)
    : section.preference_value;
  const preferenceIndex = Number(section.key.replace('preference-', ''));
  if (preferenceIndex === 1) return `${displayName}님이 좋아하는 ${label} 영화를 모았어요`;
  if (preferenceIndex === 2) return `${label}에도 자주 눈길이 가셨네요`;
  return `${displayName}님의 ${label} 취향까지 놓치지 않았어요`;
}

function MovieSection({ section, displayName, likedMovies, onToggleLike, source = '' }) {
  const rowRef = useRef(null);
  const movies = section.movies.map(normalizeMovie);
  const title = sectionTitle(section, displayName);
  const [scrollState, setScrollState] = useState({ canGoBack: false, canGoForward: false });

  const updateScrollState = () => {
    const row = rowRef.current;
    if (!row) return;
    const maxScrollLeft = Math.max(row.scrollWidth - row.clientWidth, 0);
    setScrollState({
      canGoBack: row.scrollLeft > 4,
      canGoForward: row.scrollLeft < maxScrollLeft - 4,
    });
  };

  useEffect(() => {
    const frame = window.requestAnimationFrame(updateScrollState);
    window.addEventListener('resize', updateScrollState);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', updateScrollState);
    };
  }, [movies.length]);

  const scroll = (direction) => {
    const distance = Math.max((rowRef.current?.clientWidth || 1160) * 0.86, 320);
    rowRef.current?.scrollBy({ left: direction * distance, behavior: 'smooth' });
  };

  return (
    <section className="recommendation-row" aria-label={title}>
      <header className="recommendation-row__header">
        <div>
          <h3>{title}</h3>
        </div>
      </header>

      <div className={`recommendation-row__slider${scrollState.canGoBack ? ' has-prev' : ''}${scrollState.canGoForward ? ' has-more' : ''}`}>
        <button className="recommendation-row__arrow is-prev" type="button" onClick={() => scroll(-1)} disabled={!scrollState.canGoBack} aria-label="이전 영화 보기">‹</button>
        <div className="recommendation-row__movies" ref={rowRef} onScroll={updateScrollState}>
          {movies.map((movie, index) => (
            <div className="recommendation-row__item" key={movie.id ?? `${movie.title}-${index}`}>
              {section.key === 'box-office' || section.key === 'site-popular' ? (
                <b className="recommendation-row__rank">
                  {section.movies[index]?.rank || index + 1}
                </b>
              ) : null}
              <MovieCard
                index={index}
                isLiked={likedMovies.includes(movie.title)}
                movie={movie}
                onToggleLike={onToggleLike}
                onSelect={(selected) => { window.location.href = `/movies/${selected.id}${source ? `?source=${source}` : ''}`; }}
              />
            </div>
          ))}
        </div>
        <button className="recommendation-row__arrow is-next" type="button" onClick={() => scroll(1)} disabled={!scrollState.canGoForward} aria-label="다음 영화 보기">›</button>
      </div>
    </section>
  );
}

function RecommendationSkeleton() {
  return Array.from({ length: 3 }, (_, sectionIndex) => (
    <section className="recommendation-row recommendation-row--skeleton" aria-hidden="true" key={sectionIndex}>
      <div className="recommendation-skeleton__heading" />
      <div className="recommendation-skeleton__movies">
        {Array.from({ length: 8 }, (_, cardIndex) => (
          <div className="recommendation-skeleton__card" key={cardIndex}>
            <div className="recommendation-skeleton__poster" />
            <div className="recommendation-skeleton__line is-title" />
            <div className="recommendation-skeleton__line" />
          </div>
        ))}
      </div>
    </section>
  ));
}

function SearchResultsSkeleton() {
  return (
    <section className="recommendation-search recommendation-search--skeleton" aria-hidden="true">
      <div className="recommendation-skeleton__heading" />
      <div className="recommendation-search__grid">
        {Array.from({ length: 18 }, (_, index) => (
          <div className="recommendation-skeleton__card" key={index}>
            <div className="recommendation-skeleton__poster" />
            <div className="recommendation-skeleton__line is-title" />
            <div className="recommendation-skeleton__line" />
          </div>
        ))}
      </div>
    </section>
  );
}

function SearchResults({ query, sections, likedMovies, onToggleLike }) {
  return (
    <section className="recommendation-search" aria-label={`${query} 검색 결과`}>
      <header className="recommendation-search__header">
        <h1><span>“{query}”</span> 검색 결과</h1>
        <p>{sections.length > 0 ? '검색 필드별 결과를 최신 개봉일순으로 모았어요' : '일치하는 영화를 찾지 못했어요'}</p>
      </header>

      <div className="recommendation-search__sections">
        {sections.map((section) => (
          <MovieSection
            key={section.key || section.type}
            section={section}
            displayName=""
            likedMovies={likedMovies}
            onToggleLike={onToggleLike}
            source="search"
          />
        ))}
      </div>
    </section>
  );
}

function Recommendation({ authUser, onLogout }) {
  const [sections, setSections] = useState([]);
  const [searchSections, setSearchSections] = useState([]);
  const [likedMovies, setLikedMovies] = useState([]);
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const query = new URLSearchParams(window.location.search).get('keyword')?.trim() || '';
  const searchType = new URLSearchParams(window.location.search).get('type')?.trim() || '';
  const displayName = authUser?.nickname
    || authUser?.name
    || authUser?.username
    || authUser?.email
    || '게스트';
  const prioritizePopular = !query && window.location.hash === '#site-popular';
  const displayedSections = prioritizePopular
    ? [...sections].sort((first, second) => (
        Number(second.key === 'site-popular') - Number(first.key === 'site-popular')
      ))
    : sections;

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setStatus('');

    const request = query
      ? fetchSearchSections(controller.signal, query, { limit: 20, searchType }).then((groupedSections) => {
          setSections([]);
          setSearchSections(groupedSections);
        })
      : fetchDiscoverySections(
          controller.signal,
          authUser ? null : getLocalPreferences(),
          25,
        ).then((sectionData) => {
          setSearchSections([]);
          setSections(sectionData.filter((section) => Array.isArray(section.movies) && section.movies.length > 0));
        });

    request
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [authUser, query, searchType]);

  useEffect(() => {
    if (!authUser) return undefined;
    const controller = new AbortController();
    fetchLikedMovies(controller.signal)
      .then((movies) => setLikedMovies(movies.map((movie) => normalizeMovie(movie).title).filter(Boolean)))
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      });
    return () => controller.abort();
  }, [authUser]);

  const handleToggleLike = async (movie) => {
    if (!authUser) {
      setStatus('좋아요는 로그인 후 이용할 수 있어요.');
      return;
    }
    const wasLiked = likedMovies.includes(movie.title);
    setLikedMovies((current) => wasLiked
      ? current.filter((title) => title !== movie.title)
      : [...current, movie.title]);
    try {
      if (wasLiked) {
        await removeLikedMovie(movie);
        setSections((current) => current.map((section) => section.key === 'recent-likes'
          ? {
              ...section,
              movies: section.movies.filter((item) => (
                (item.movie_id ?? item.id) !== movie.id && item.title !== movie.title
              )),
            }
          : section));
      } else {
        await addLikedMovie(movie);
        setSections((current) => current.map((section) => section.key === 'recent-likes'
          ? {
              ...section,
              movies: [
                movie,
                ...section.movies.filter((item) => (
                  (item.movie_id ?? item.id) !== movie.id && item.title !== movie.title
                )),
              ].slice(0, 25),
            }
          : section));
      }
    } catch (error) {
      setLikedMovies((current) => wasLiked
        ? Array.from(new Set([...current, movie.title]))
        : current.filter((title) => title !== movie.title));
      setStatus(error.message);
    }
  };

  return (
    <main className="recommendation cinema-nav-page">
      {status ? <p className="recommendation__status" role="status">{status}</p> : null}

      <div className="recommendation__sections">
        {isLoading ? (
          query ? <SearchResultsSkeleton /> : <RecommendationSkeleton />
        ) : query ? (
          <SearchResults
            query={query}
            sections={searchSections}
            likedMovies={likedMovies}
            onToggleLike={handleToggleLike}
          />
        ) : displayedSections.map((section) => (
            <MovieSection
              key={section.key}
              section={section}
              displayName={displayName}
              likedMovies={likedMovies}
              onToggleLike={handleToggleLike}
            />
          ))}
      </div>
    </main>
  );
}

export default Recommendation;
