import { useEffect, useState } from 'react';

import { fetchRecentMovies } from '../../api.js';
import MovieModal from '../movieCard/MovieModal.jsx';
import PosterArt from './PosterArt.jsx';
import { normalizeMovie } from './RecommendationRow.jsx';

function RecentPanel({ authUser }) {
  const [recentMovies, setRecentMovies] = useState([]);
  const [selectedMovie, setSelectedMovie] = useState(null);

  useEffect(() => {
    if (!authUser) {
      setRecentMovies([]);
      return undefined;
    }

    const controller = new AbortController();

    fetchRecentMovies(controller.signal)
      .then((rawMovies) => setRecentMovies(rawMovies.map(normalizeMovie)))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('최근 본 영화 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, [authUser]);

  return (
    <article className="index-info-card recent-card">
      <div className="index-card-header">
        <h3>최근 본 영화</h3>
        <a href="/recommendations?view=recent">더보기 ›</a>
      </div>

      <div className="index-recent-row">
        {recentMovies.map((movie, index) => (
          <button
            className="index-recent-poster"
            type="button"
            onClick={() => setSelectedMovie(movie)}
            key={movie.id ?? movie.title}
          >
            <PosterArt movie={{ ...movie, tone: index + 11 }} index={index} compact />
          </button>
        ))}
      </div>

      <MovieModal movie={selectedMovie} onClose={() => setSelectedMovie(null)} />
    </article>
  );
}

export default RecentPanel;
