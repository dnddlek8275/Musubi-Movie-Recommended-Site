import { useEffect, useState } from 'react';

import { fetchMovieRanking } from '../../api.js';
import PosterArt from './PosterArt.jsx';

const VISIBLE_COUNT = 3;
const SWAP_INTERVAL_MS = 5000;

function RankPanel() {
  const [rankings, setRankings] = useState([]);

  useEffect(() => {
    const controller = new AbortController();

    fetchMovieRanking(controller.signal)
      .then(setRankings)
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('실시간 랭킹 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, []);

  const [startIndex, setStartIndex] = useState(0);

  // 5초마다 한 칸씩 아래에서 위로 스와프, 10위까지 돌면 다시 1위부터
  useEffect(() => {
    if (rankings.length <= VISIBLE_COUNT) return undefined;

    const timer = setInterval(() => {
      setStartIndex((current) => (current + 1) % rankings.length);
    }, SWAP_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [rankings.length]);

  const visibleRankings = Array.from(
    { length: Math.min(VISIBLE_COUNT, rankings.length) },
    (_, i) => rankings[(startIndex + i) % rankings.length]
  );

  return (
    <article className="index-info-card rank-card">
      <div className="index-card-header">
        <h3>🔥 실시간 top10</h3>
        <a href="/recommendations">더보기 ›</a>
      </div>

      <div className="index-rank-list" key={startIndex}>
        {visibleRankings.map((movie) => (
          <div className="index-rank-item" key={movie.rank}>
            <strong>{movie.rank}</strong>
            <a
              className="index-rank-poster-link"
              href={`/recommendations?keyword=${encodeURIComponent(movie.title)}`}
              aria-label={`${movie.title} 검색 결과 보기`}
              title={`${movie.title} 검색`}
            >
              <PosterArt movie={movie} compact />
            </a>
            <div>
              <b>{movie.title}</b>
              <span>{movie.genre}</span>
            </div>
            <em>★ {movie.rating}</em>
            <span className="rank-change">{movie.change}</span>
          </div>
        ))}
      </div>
    </article>
  );
}

export default RankPanel;
