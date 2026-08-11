import { useEffect, useMemo, useState } from 'react';

import { fetchPersonFilmography, resolveMovieImage, togglePersonLike } from '../../api.js';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import './personFilmography.css';

function getDecade(year) {
  const numericYear = Number(year);
  return Number.isFinite(numericYear) && numericYear > 0
    ? Math.floor(numericYear / 10) * 10
    : null;
}

function FilmographySkeleton() {
  return (
    <main className="person-filmography person-filmography--loading" aria-busy="true" aria-label="필모그래피 불러오는 중">
      <SkeletonBlock className="person-filmography-skeleton__heading" />
      <div className="person-filmography__layout">
        <SkeletonBlock className="person-filmography-skeleton__profile" />
        <div className="person-filmography-skeleton__works">
          <SkeletonBlock className="person-filmography-skeleton__toolbar" />
          <div className="person-filmography-skeleton__grid">
            {Array.from({ length: 10 }, (_, index) => (
              <div key={index}>
                <SkeletonBlock className="person-filmography-skeleton__poster" />
                <SkeletonBlock className="person-filmography-skeleton__line" />
                <SkeletonBlock className="person-filmography-skeleton__line is-short" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

function PersonFilmographyPage({ authUser, identifier, role }) {
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [decade, setDecade] = useState('all');
  const [likeSaving, setLikeSaving] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setDecade('all');

    fetchPersonFilmography(role, identifier, controller.signal)
      .then(setPerson)
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        setError(fetchError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [identifier, role]);

  const movies = Array.isArray(person?.movies) ? person.movies : [];
  const decades = useMemo(
    () => [...new Set(movies.map((movie) => getDecade(movie.year)).filter(Boolean))].sort((a, b) => b - a),
    [movies]
  );
  const visibleMovies = decade === 'all'
    ? movies
    : movies.filter((movie) => String(getDecade(movie.year)) === decade);

  const handlePersonLike = async () => {
    if (!authUser) {
      setNotice('좋아요는 로그인 후 이용할 수 있어요.');
      return;
    }
    if (likeSaving) return;

    setLikeSaving(true);
    setNotice('');
    try {
      const result = await togglePersonLike(role, identifier);
      setPerson((current) => current ? { ...current, is_liked: Boolean(result.is_liked) } : current);
    } catch (likeError) {
      setNotice(likeError.message);
    } finally {
      setLikeSaving(false);
    }
  };

  if (loading) return <FilmographySkeleton />;

  if (error || !person) {
    return (
      <main className="person-filmography person-filmography--empty">
        <span>FILMOGRAPHY</span>
        <h1>필모그래피</h1>
        <p>{error || '등록된 인물 정보를 찾을 수 없습니다.'}</p>
        <button type="button" onClick={() => window.history.back()}>이전 화면으로</button>
      </main>
    );
  }

  const isDirector = person.role === 'director';
  const roleLabel = isDirector ? '감독' : '배우';

  return (
    <main className="person-filmography">
      <header className="person-filmography__heading">
        <span>PERSON · FILMOGRAPHY</span>
        <h1>필모그래피</h1>
      </header>

      <div className="person-filmography__layout">
        <aside className="person-filmography__profile">
          <div className="person-filmography__identity">
            <span className="person-filmography__avatar" aria-hidden="true">
              {person.profile_path
                ? <img src={resolveMovieImage(person.profile_path)} alt="" />
                : String(person.name || '?').slice(0, 1)}
            </span>
            <div>
              <small>{isDirector ? 'DIRECTOR' : 'ACTOR'}</small>
              <h2>{person.name}</h2>
              <p>{roleLabel}</p>
            </div>
          </div>
          <div className="person-filmography__profile-meta">
            <span>Musubi 등록 작품</span>
            <strong>{person.movie_count || movies.length}<small>편</small></strong>
          </div>
          <button
            className={`person-filmography__like${person.is_liked ? ' is-liked' : ''}`}
            type="button"
            onClick={handlePersonLike}
            disabled={likeSaving}
            aria-pressed={Boolean(person.is_liked)}
          >
            <span aria-hidden="true">{person.is_liked ? '♥' : '♡'}</span>
            {likeSaving ? '반영 중' : '좋아요'}
          </button>
          {notice ? <p className="person-filmography__notice" role="status">{notice}</p> : null}
        </aside>

        <section className="person-filmography__works">
          <div className="person-filmography__toolbar">
            <p><strong>{visibleMovies.length}</strong>개의 작품</p>
            <label>
              <select aria-label="연대별 작품 필터" value={decade} onChange={(event) => setDecade(event.target.value)}>
                <option value="all">전체 작품</option>
                {decades.map((value) => (
                  <option key={value} value={String(value)}>{value}년대</option>
                ))}
              </select>
            </label>
          </div>

          {visibleMovies.length ? (
            <div className="person-filmography__grid">
              {visibleMovies.map((movie) => {
                const poster = resolveMovieImage(movie.poster_path || '');
                const genres = Array.isArray(movie.genres) ? movie.genres.join(' · ') : '';
                const rating = Number(movie.vote_average);
                return (
                  <a href={`/movies/${movie.id}`} className="person-filmography-card" key={movie.id}>
                    <div className="person-filmography-card__poster">
                      {poster
                        ? <img src={poster} alt={`${movie.title} 포스터`} />
                        : <span>NO POSTER</span>}
                      {movie.year ? <small>{movie.year}</small> : null}
                    </div>
                    <strong>{movie.title}</strong>
                    {movie.character_name ? <p>{movie.character_name} 역</p> : <p>{genres || roleLabel}</p>}
                    <span>{Number.isFinite(rating) && rating > 0 ? `★ ${rating.toFixed(1)}` : '평점 정보 없음'}</span>
                  </a>
                );
              })}
            </div>
          ) : (
            <p className="person-filmography__no-results">해당 연대에 등록된 작품이 없습니다.</p>
          )}
        </section>
      </div>
    </main>
  );
}

export default PersonFilmographyPage;
