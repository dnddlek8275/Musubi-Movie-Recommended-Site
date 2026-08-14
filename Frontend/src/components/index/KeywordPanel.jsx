import { useEffect, useRef, useState } from 'react';

import { fetchUserPreferences } from '../../api.js';
import Tag from './Tag.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';

const EMPTY_PREFERENCES = {
  genres: [],
  actors: [],
  keywords: [],
};

function preferenceValues(values) {
  return Array.from(new Set((Array.isArray(values) ? values : [])
    .map((item) => String(item?.value ?? item ?? '').trim())
    .filter(Boolean)));
}

function PreferenceRow({ label, values, loading, formatValue = (value) => value, moreHref = '' }) {
  const valuesRef = useRef(null);
  const visibleValues = values.slice(0, 6);
  const [isTruncated, setIsTruncated] = useState(values.length > 6);

  useEffect(() => {
    const container = valuesRef.current;
    if (!container) return undefined;

    const updateTruncation = () => {
      setIsTruncated(values.length > 6 || container.scrollWidth > container.clientWidth + 1);
    };

    updateTruncation();
    const resizeObserver = new ResizeObserver(updateTruncation);
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, [values]);

  return (
    <div className="keyword-preference-row">
      <div className="keyword-preference-row__heading">
        <strong>{label}</strong>
        {moreHref ? <a href={moreHref}>더보기 &gt;</a> : null}
      </div>
      <div
        className={`keyword-preference-values${isTruncated ? ' keyword-preference-values--truncated' : ''}`}
        ref={valuesRef}
      >
        {loading ? (
          <>
            <SkeletonBlock className="index-keyword-skeleton" />
            <SkeletonBlock className="index-keyword-skeleton" />
          </>
        ) : visibleValues.length ? visibleValues.map((value, index) => (
          <Tag key={`${value}-${index}`}>{formatValue(value)}</Tag>
        )) : (
          <span className="keyword-preference-empty">분석 전</span>
        )}
      </div>
    </div>
  );
}

function KeywordPanel({ authUser }) {
  const [preferences, setPreferences] = useState(EMPTY_PREFERENCES);
  const [loading, setLoading] = useState(Boolean(authUser));

  useEffect(() => {
    if (!authUser) {
      setPreferences(EMPTY_PREFERENCES);
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);

    fetchUserPreferences(controller.signal)
      .then((data) => {
        // 사용자가 직접 선택한 값이 아니라 활동에서 점수순으로 분석된 취향만 표시한다.
        const learnedPreferences = data.learned_preferences || {};
        setPreferences({
          genres: preferenceValues(learnedPreferences.genres),
          actors: preferenceValues(learnedPreferences.actors),
          keywords: preferenceValues(learnedPreferences.keywords),
        });
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('관심 키워드 불러오기 실패:', error);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [authUser]);

  return (
    <article className="index-info-card keyword-card">
      <div className="keyword-preferences">
        <PreferenceRow label="선호 장르" values={preferences.genres} loading={loading} moreHref="/mypage?tab=taste" />
        <PreferenceRow label="선호 배우" values={preferences.actors} loading={loading} />
        <PreferenceRow label="관심 키워드" values={preferences.keywords} loading={loading} formatValue={getKeywordLabel} />
      </div>
    </article>
  );
}

export default KeywordPanel;
