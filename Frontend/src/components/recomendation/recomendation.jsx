import { useEffect, useRef, useState } from 'react';

import {
  addLikedMovie,
  fetchDiscoverySections,
  fetchLikedMovies,
  fetchMoviesByCountry,
  fetchMoviesByGenre,
  fetchSearchSections,
  getLocalPreferences,
  removeLikedMovie,
} from '../../api.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import MovieCard from '../movieCard/MovieCard.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';
import { navigateTo } from '../../navigation.js';
import './recomendation.css';

const ROTATING_GENRES = [
  '한국영화',
  '드라마', '코미디', '스릴러', '액션', '공포', '로맨스', '범죄', '모험',
  '애니메이션', 'SF', '가족', '판타지', '미스터리', '다큐멘터리', '음악',
  '역사', '전쟁',
];
const GENRE_ROTATION_KEY = 'musubi.recommendationGenreRotation';

function GenreSelector({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const selectorRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!selectorRef.current?.contains(event.target)) setIsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false);
    };

    document.addEventListener('mousedown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [isOpen]);

  return (
    <span className="recommendation-genre-select" ref={selectorRef}>
      <button
        type="button"
        className="recommendation-genre-select__trigger"
        aria-label="장르 선택"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span>{value}</span>
        <span className="recommendation-genre-select__arrow" aria-hidden="true">⌄</span>
      </button>
      {isOpen && (
        <span className="recommendation-genre-select__menu" role="listbox" aria-label="장르 목록">
          {ROTATING_GENRES.map((genre) => (
            <button
              type="button"
              role="option"
              aria-selected={genre === value}
              className={genre === value ? 'is-selected' : ''}
              onClick={() => {
                onChange(genre);
                setIsOpen(false);
              }}
              key={genre}
            >
              {genre}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}

function shuffledGenres() {
  const genres = [...ROTATING_GENRES];
  for (let index = genres.length - 1; index > 0; index -= 1) {
    const target = Math.floor(Math.random() * (index + 1));
    [genres[index], genres[target]] = [genres[target], genres[index]];
  }
  return genres;
}

function nextRotatingGenre() {
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(GENRE_ROTATION_KEY) || 'null');
    const validQueue = Array.isArray(stored?.queue)
      && stored.queue.length === ROTATING_GENRES.length
      && ROTATING_GENRES.every((genre) => stored.queue.includes(genre));
    const queue = validQueue && Number(stored.index) < stored.queue.length
      ? stored.queue
      : shuffledGenres();
    const index = validQueue && Number(stored.index) < stored.queue.length
      ? Math.max(Number(stored.index), 0)
      : 0;
    const genre = queue[index];
    window.sessionStorage.setItem(GENRE_ROTATION_KEY, JSON.stringify({ queue, index: index + 1 }));
    return genre;
  } catch {
    return ROTATING_GENRES[Math.floor(Math.random() * ROTATING_GENRES.length)];
  }
}

function sectionTitle(section, displayName) {
  if (section.key === 'for-you') {
    return `${displayName}님을 위한 영화를 추천해드릴게요.`;
  }
  if (section.key === 'recent-likes') {
    return `${displayName}님이 마음을 남긴 영화, 최근 순서로 모았어요`;
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

function MovieSection({
  section,
  displayName,
  likedMovies,
  onToggleLike,
  source = '',
  titleContent = null,
  onReachEnd = null,
  isLoadingMore = false,
}) {
  const movies = section.movies.map(normalizeMovie);
  const title = sectionTitle(section, displayName);

  return (
    <section className="recommendation-row" aria-label={title}>
      <header className="recommendation-row__header">
        <div>
          <h3>{titleContent || title}</h3>
        </div>
      </header>

      <HorizontalScroller
        className="recommendation-row__movies"
        ariaLabel={`${title} 영화 목록`}
        onReachEnd={onReachEnd}
      >
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
                onSelect={(selected) => navigateTo(`/movies/${selected.id}${source ? `?source=${source}` : ''}`)}
              />
            </div>
          ))}
          {isLoadingMore ? (
            <div className="recommendation-row__item recommendation-row__item--loading" aria-label="다음 영화 불러오는 중">
              <div className="recommendation-skeleton__poster" />
              <div className="recommendation-skeleton__line is-title" />
              <div className="recommendation-skeleton__line" />
            </div>
          ) : null}
      </HorizontalScroller>
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

function SearchResults({ query, sections, likedMovies, onToggleLike, onLoadMore, loadingSections }) {
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
            onReachEnd={section.has_more ? () => onLoadMore(section) : null}
            isLoadingMore={loadingSections.has(section.type)}
          />
        ))}
      </div>
    </section>
  );
}

function Recommendation({ authUser, onLogout }) {
  const [sections, setSections] = useState([]);
  const [searchSections, setSearchSections] = useState([]);
  const [loadingSearchSections, setLoadingSearchSections] = useState(() => new Set());
  const searchLoadRef = useRef(new Set());
  const searchQueryRef = useRef('');
  const [likedMovies, setLikedMovies] = useState([]);
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedGenre, setSelectedGenre] = useState(nextRotatingGenre);
  const [genreMovies, setGenreMovies] = useState([]);
  const [genreLoading, setGenreLoading] = useState(true);
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
    searchQueryRef.current = query;
    setIsLoading(true);
    setStatus('');

    const request = query
      ? fetchSearchSections(controller.signal, query, { limit: 20, searchType }).then((groupedSections) => {
          setSections([]);
          setSearchSections(groupedSections);
          searchLoadRef.current.clear();
          setLoadingSearchSections(new Set());
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

  const loadMoreSearchSection = async (section) => {
    const category = String(section?.type || '').trim();
    if (!query || !category || !section?.has_more || searchLoadRef.current.has(category)) return;

    searchLoadRef.current.add(category);
    setLoadingSearchSections((current) => new Set(current).add(category));
    try {
      const nextPage = Math.max(Number(section.page) || 1, 1) + 1;
      const excludeIds = searchSections.flatMap((item) => (
        item.movies.map((movie) => movie.id ?? movie.movie_id).filter(Boolean)
      ));
      const nextSections = await fetchSearchSections(undefined, query, {
        limit: 20,
        searchType,
        category,
        page: nextPage,
        excludeIds,
      });
      if (searchQueryRef.current !== query) return;
      const nextSection = nextSections.find((item) => item.type === category);
      setSearchSections((current) => current.map((item) => {
        if (item.type !== category) return item;
        if (!nextSection) return { ...item, has_more: false };
        const knownIds = new Set(item.movies.map((movie) => String(movie.id)));
        const appended = nextSection.movies.filter((movie) => !knownIds.has(String(movie.id)));
        return {
          ...item,
          movies: [...item.movies, ...appended],
          page: nextSection.page,
          has_more: nextSection.has_more,
        };
      }));
    } catch (error) {
      if (error.name !== 'AbortError') setStatus(error.message);
    } finally {
      searchLoadRef.current.delete(category);
      setLoadingSearchSections((current) => {
        const next = new Set(current);
        next.delete(category);
        return next;
      });
    }
  };

  useEffect(() => {
    if (query) {
      setGenreMovies([]);
      setGenreLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setGenreLoading(true);
    const request = selectedGenre === '한국영화'
      ? fetchMoviesByCountry('KR', controller.signal, { limit: 25 })
      : fetchMoviesByGenre(selectedGenre, controller.signal, { limit: 25, sort: 'latest' });
    request
      .then(setGenreMovies)
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setGenreLoading(false);
      });
    return () => controller.abort();
  }, [query, selectedGenre]);

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

  const genreTitle = (
    <span className="recommendation-genre-title">
      <GenreSelector value={selectedGenre} onChange={setSelectedGenre} />
      <span>{selectedGenre === '한국영화' ? '최신순으로 모아봤어요.' : '영화만 모아봤어요.'}</span>
    </span>
  );

  const genreSection = {
    key: 'rotating-genre',
    title: `${selectedGenre} 영화만 모아봤어요.`,
    movies: genreMovies,
  };

  const sectionsWithGenre = displayedSections.flatMap((section) => (
    section.key === 'box-office'
      ? [section, genreSection]
      : [section]
  ));

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
            onLoadMore={loadMoreSearchSection}
            loadingSections={loadingSearchSections}
          />
        ) : sectionsWithGenre.map((section) => (
            section.key === 'rotating-genre' && genreLoading ? (
              <section className="recommendation-row recommendation-row--skeleton" aria-hidden="true" key={section.key}>
                <div className="recommendation-skeleton__heading" />
                <div className="recommendation-skeleton__movies">
                  {Array.from({ length: 8 }, (_, index) => (
                    <div className="recommendation-skeleton__card" key={index}>
                      <div className="recommendation-skeleton__poster" />
                      <div className="recommendation-skeleton__line is-title" />
                      <div className="recommendation-skeleton__line" />
                    </div>
                  ))}
                </div>
              </section>
            ) : (
            <MovieSection
              key={section.key}
              section={section}
              displayName={displayName}
              likedMovies={likedMovies}
              onToggleLike={handleToggleLike}
              titleContent={section.key === 'rotating-genre' ? genreTitle : null}
            />
            )
          ))}
      </div>
    </main>
  );
}

export default Recommendation;
