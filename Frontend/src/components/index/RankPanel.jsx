import { useEffect, useState } from 'react';

import { fetchMovieRanking } from '../../api.js';
import PosterArt from './PosterArt.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';

const VISIBLE_COUNT = 4;
const SWAP_INTERVAL_MS = 5000;
const RANK_REFRESH_INTERVAL_MS = 60000;

function RankPanel() {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    const loadRankings = () => {
      fetchMovieRanking(controller.signal)
        .then(setRankings)
        .catch((error) => {
          if (error.name === 'AbortError') return;
          console.error('실시간 랭킹 불러오기 실패:', error);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    };

    loadRankings();
    const refreshTimer = window.setInterval(loadRankings, RANK_REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(refreshTimer);
      controller.abort();
    };
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
        <h3>실시간 TOP10</h3>
      </div>

      <div className="index-rank-list" key={startIndex}>
        {loading ? Array.from({ length: VISIBLE_COUNT }, (_, index) => (
          <div className="index-rank-item index-rank-item--skeleton" key={index}>
            <SkeletonBlock className="index-rank-number-skeleton" />
            <SkeletonBlock className="index-rank-poster-skeleton" />
            <div>
              <SkeletonBlock className="loading-skeleton--line loading-skeleton--title" />
            </div>
          </div>
        )) : visibleRankings.map((movie) => {
          const href = movie.id
            ? `/movies/${movie.id}`
            : `/recommendations?keyword=${encodeURIComponent(movie.title)}`;

          return (
            <a
              className={`index-rank-item ${movie.rank <= 3 ? 'index-rank-item--top' : ''}`}
              href={href}
              key={movie.rank}
              aria-label={`${movie.rank}위 ${movie.title} 상세 보기`}
            >
              <strong className="index-rank-number">{movie.rank}</strong>
              <span className="index-rank-poster">
              <PosterArt movie={movie} compact />
              </span>
              <span className="index-rank-copy">
                <b>{movie.title}</b>
              </span>
              <span
                className={`index-rank-trend${movie.isNew ? ' is-new' : movie.rankChange > 0 ? ' is-up' : movie.rankChange < 0 ? ' is-down' : ''}`}
                aria-label={movie.isNew
                  ? 'TOP10 신규 진입'
                  : movie.rankChange > 0
                  ? `${movie.rankChange}계단 상승`
                  : movie.rankChange < 0
                    ? `${Math.abs(movie.rankChange)}계단 하락`
                    : '순위 변동 없음'}
              >
                {movie.isNew ? <b className="index-rank-trend__new">NEW</b> : (
                  <>
                    <i aria-hidden="true">{movie.rankChange > 0 ? '↑' : movie.rankChange < 0 ? '↓' : '—'}</i>
                    {movie.rankChange ? <b>{Math.abs(movie.rankChange)}</b> : null}
                  </>
                )}
              </span>
            </a>
          );
        })}
      </div>

      <a className="index-rank-more" href="/recommendations#site-popular">
        실시간 차트보기 ›
      </a>
    </article>
  );
}

export default RankPanel;
