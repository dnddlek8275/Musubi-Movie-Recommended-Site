import { useEffect, useState } from 'react';

import { fetchRecentMovies } from '../../api.js';
import PosterArt from './PosterArt.jsx';
import { normalizeMovie } from './RecommendationRow.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import { navigateTo } from '../../navigation.js';

function RecentPanel({ authUser }) {
  const [recentMovies, setRecentMovies] = useState([]);
  const [loading, setLoading] = useState(Boolean(authUser));

  useEffect(() => {
    if (!authUser) {
      setRecentMovies([]);
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);

    fetchRecentMovies(controller.signal)
      .then((rawMovies) => setRecentMovies(rawMovies.map(normalizeMovie)))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('최근 본 영화 불러오기 실패:', error);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [authUser]);

  return (
    <article className="index-info-card recent-card">
      <div className="index-card-header">
        <h3>최근 본 영화</h3>
        <a href="/mypage?tab=activity">더보기 ›</a>
      </div>

      <div className="index-recent-row">
        {loading ? Array.from({ length: 4 }, (_, index) => (
          <SkeletonBlock className="index-recent-skeleton" key={index} />
        )) : recentMovies.map((movie, index) => (
          <button
            className="index-recent-poster"
            type="button"
            onClick={() => navigateTo(`/movies/${movie.id}`)}
            key={movie.id ?? movie.title}
          >
            <PosterArt movie={{ ...movie, tone: index + 11 }} index={index} compact />
          </button>
        ))}
      </div>

    </article>
  );
}

export default RecentPanel;
