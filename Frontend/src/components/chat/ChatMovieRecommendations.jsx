import { useRef, useState } from 'react';

import { resolveChatMovieId } from '../../api.js';
import { navigateTo } from '../../navigation.js';
import PosterArt from '../index/PosterArt.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';

function ChatMovieRecommendations({ movies }) {
  const [openingKey, setOpeningKey] = useState('');
  const [status, setStatus] = useState('');
  const abortRef = useRef(null);

  if (!Array.isArray(movies) || movies.length === 0) return null;

  const openMovie = async (movie, key) => {
    if (openingKey) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setOpeningKey(key);
    setStatus('');

    try {
      const movieId = await resolveChatMovieId(movie, controller.signal);
      navigateTo(`/movies/${movieId}`);
    } catch (error) {
      if (error.name !== 'AbortError') setStatus(error.message);
      setOpeningKey('');
    }
  };

  return (
    <>
      <HorizontalScroller className="home-variant-message__movies" ariaLabel="추천 영화">
        {movies.slice(0, 3).map((movie, index) => {
          const title = movie.title || movie.name || movie.movie || `추천 영화 ${index + 1}`;
          const key = String(movie.movie_id || movie.tmdb_id || movie.id || `${title}-${index}`);
          return (
            <button
              type="button"
              key={key}
              aria-label={`${title} 상세 페이지 보기`}
              aria-busy={openingKey === key}
              onClick={() => openMovie(movie, key)}
            >
              <PosterArt movie={{ ...movie, title }} compact />
              <span className="home-variant-message__movie-copy">
                {movie.recommendation_role ? (
                  <small className="home-variant-message__movie-role">{movie.recommendation_role}</small>
                ) : null}
                <strong>{title}</strong>
                {movie.recommendation_reason ? (
                  <span className="home-variant-message__movie-reason">{movie.recommendation_reason}</span>
                ) : null}
              </span>
            </button>
          );
        })}
      </HorizontalScroller>
      {status ? <p className="home-variant-message__movie-status" role="status">{status}</p> : null}
    </>
  );
}

export default ChatMovieRecommendations;
