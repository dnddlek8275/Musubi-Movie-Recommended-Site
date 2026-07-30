import { useEffect, useRef, useState } from 'react';

import { fetchUserPreferences } from '../../api.js';
import Tag from './Tag.jsx';

function KeywordPanel({ authUser }) {
  const [keywords, setKeywords] = useState([]);
  const [isTruncated, setIsTruncated] = useState(false);
  const keywordsRef = useRef(null);

  useEffect(() => {
    if (!authUser) {
      setKeywords([]);
      return undefined;
    }

    const controller = new AbortController();

    fetchUserPreferences(controller.signal)
      .then((data) => {
        const preferences = data.preferences || data || {};

        setKeywords([
          ...(preferences.genres || []),
          ...(preferences.actors || []),
          ...(preferences.keywords || []),
        ]);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('관심 키워드 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, [authUser]);

  useEffect(() => {
    const container = keywordsRef.current;
    if (!container) return undefined;

    const updateTruncation = () => {
      setIsTruncated(container.scrollHeight > container.clientHeight + 1);
    };

    updateTruncation();

    const resizeObserver = new ResizeObserver(updateTruncation);
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, [keywords]);

  return (
    <article className="index-info-card keyword-card">
      <div className="index-card-header">
        <h3>나의 관심 키워드</h3>
        <a href="/recommendations">더보기 ›</a>
      </div>

      <div
        className={`index-keywords${isTruncated ? ' index-keywords--truncated' : ''}`}
        ref={keywordsRef}
      >
        {keywords.map((keyword, index) => (
          <Tag key={`${keyword}-${index}`}>{keyword}</Tag>
        ))}
      </div>
    </article>
  );
}

export default KeywordPanel;
