import { useEffect, useState } from 'react';

import { fetchAiRecommendation } from '../../api.js';
import { navigateTo } from '../../navigation.js';
import PosterArt from './PosterArt.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';

const SLIDE_INTERVAL_MS = 12500;

function AiPanel() {
  const [aiPick, setAiPick] = useState({
    title: 'AI의 추천 한 줄',
    copy: '',
    movies: [],
  });
  const [slideIndex, setSlideIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    fetchAiRecommendation(controller.signal)
      .then((data) => setAiPick((current) => ({ ...current, ...data })))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('AI 추천 불러오기 실패:', error);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  const movies = aiPick.movies || [];

  // 슬라이스가 2개 이상일 때만 일정 주기로 한 장씩 넘긴다.
  useEffect(() => {
    if (movies.length <= 1) return undefined;

    setSlideIndex(0);
    const timer = setInterval(() => {
      setSlideIndex((current) => (current + 1) % movies.length);
    }, SLIDE_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [movies.length]);

  const carouselPosition = (index) => {
    if (index === slideIndex % movies.length) return 'active';
    const nextIndex = (slideIndex + 1) % movies.length;
    return index === nextIndex ? 'next' : 'previous';
  };

  return (
    <article className="index-info-card ai-card">
      <div className="index-card-header">
        <h3>🍿 {aiPick.title}</h3>
      </div>

      {loading ? (
        <SkeletonBlock className="ai-copy-skeleton" />
      ) : (
        <p className="ai-copy">{String(aiPick.copy || '').trim().replace(/\s+/g, ' ')}</p>
      )}

      {loading ? (
        <div className="ai-pick-box ai-pick-box--skeleton">
          <SkeletonBlock className="ai-poster-skeleton" />
          <div>
            <SkeletonBlock className="loading-skeleton--line loading-skeleton--title" />
            <SkeletonBlock className="loading-skeleton--line" />
            <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
          </div>
        </div>
      ) : (
        <div className="ai-carousel" aria-label="오늘의 AI 추천 영화">
          <div className="ai-carousel__stage">
            {movies.map((movie, index) => {
              const position = carouselPosition(index);
              return (
                <button
                  className={`ai-carousel__card ai-carousel__card--${position}`}
                  type="button"
                  key={movie.movie_id || movie.movie || index}
                  onClick={() => {
                    if (position === 'active' && movie.movie_id) {
                      navigateTo(`/movies/${movie.movie_id}`);
                      return;
                    }
                    setSlideIndex(index);
                  }}
                  aria-label={position === 'active'
                    ? `${movie.movie} 상세 페이지로 이동`
                    : `${movie.movie} 포스터를 가운데로 이동`}
                  aria-current={position === 'active' ? 'true' : undefined}
                >
                  <PosterArt
                    movie={{ title: movie.movie, poster_path: movie.poster_path }}
                    compact
                  />
                  <span className="ai-carousel__shade" />
                  <span className="ai-carousel__caption">
                    <strong>{movie.movie}</strong>
                    {position === 'active' ? <small>{movie.description}</small> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

    </article>
  );
}

export default AiPanel;
