import { useEffect, useState } from 'react';

import { fetchAiRecommendation } from '../../api.js';
import PosterArt from './PosterArt.jsx';

const SLIDE_INTERVAL_MS = 5000;
const EMPTY_PICK = { movie: '', poster_path: '', description: '' };

function AiPanel() {
  const [aiPick, setAiPick] = useState({
    title: 'AI의 추천 한 줄',
    copy: '',
    movies: [],
  });
  const [slideIndex, setSlideIndex] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    fetchAiRecommendation(controller.signal)
      .then((data) => setAiPick((current) => ({ ...current, ...data })))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('AI 추천 불러오기 실패:', error);
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

  const current = movies.length > 0 ? movies[slideIndex % movies.length] : EMPTY_PICK;

  return (
    <article className="index-info-card ai-card">
      <div className="index-card-header">
        <h3>🍿 {aiPick.title}</h3>
      </div>

      <p className="ai-copy">{aiPick.copy}</p>

      <div className="ai-pick-box" key={slideIndex}>
        <PosterArt
          movie={{ title: current.movie, poster_path: current.poster_path }}
          index={0}
          compact
        />
        <p>
          <strong>{current.movie}</strong>
          <span>{current.description}</span>
        </p>
      </div>

      {movies.length > 1 ? (
        <div className="ai-pick-dots" aria-hidden="true">
          {movies.map((movie, index) => (
            <span
              key={movie.movie || index}
              className={`ai-pick-dot ${
                index === slideIndex % movies.length ? 'ai-pick-dot--active' : ''
              }`}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}

export default AiPanel;
