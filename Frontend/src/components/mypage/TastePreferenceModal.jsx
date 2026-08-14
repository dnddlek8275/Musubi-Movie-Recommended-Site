import { useEffect, useMemo, useState } from 'react';

import { fetchActors, fetchOnboardingOptions } from '../../api.js';
import { getKeywordLabel } from '../../utils/keywordLabels.js';

const STEPS = [
  {
    key: 'genres',
    label: '장르',
    title: '좋아하는 장르를 골라주세요',
    description: '영화 추천의 가장 기본이 되는 취향이에요.',
    limit: 5,
  },
  {
    key: 'actors',
    label: '배우',
    title: '좋아하는 배우를 선택해 주세요',
    description: '배우 이름을 검색해서 최대 5명까지 고를 수 있어요.',
    limit: 5,
  },
  {
    key: 'keywords',
    label: '키워드',
    title: '끌리는 이야기 키워드를 골라주세요',
    description: '분위기와 소재 취향을 추천에 함께 반영해요.',
    limit: 6,
  },
];

function cleanValues(values) {
  return Array.from(new Set((Array.isArray(values) ? values : [])
    .map((value) => String(value || '').trim())
    .filter(Boolean)));
}

function toggleValue(values, value, limit) {
  if (values.includes(value)) return values.filter((item) => item !== value);
  if (values.length >= limit) return values;
  return [...values, value];
}

function TastePreferenceModal({ initialPreferences, saving = false, onClose, onSave }) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState(() => ({
    genres: cleanValues(initialPreferences?.genres),
    actors: cleanValues(initialPreferences?.actors),
    keywords: cleanValues(initialPreferences?.keywords),
  }));
  const [options, setOptions] = useState({ genres: [], keywords: [] });
  const [actors, setActors] = useState([]);
  const [actorSearch, setActorSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [actorLoading, setActorLoading] = useState(false);
  const [status, setStatus] = useState('');

  const current = STEPS[step];
  const selected = draft[current.key];
  const selectedLabel = (value) => current.key === 'keywords'
    ? getKeywordLabel(value, { compact: true, hashtag: true })
    : value;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [onClose, saving]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetchOnboardingOptions(controller.signal),
      fetchActors(controller.signal, { limit: 24, onboarding: true }),
    ])
      .then(([optionData, actorData]) => {
        setOptions({
          genres: cleanValues(optionData.genres),
          keywords: cleanValues(optionData.keywords),
        });
        setActors(actorData);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (step !== 1 || !actorSearch.trim()) return undefined;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setActorLoading(true);
      fetchActors(controller.signal, { query: actorSearch, limit: 24 })
        .then(setActors)
        .catch((error) => {
          if (error.name !== 'AbortError') setStatus(error.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setActorLoading(false);
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [actorSearch, step]);

  const choices = useMemo(() => {
    if (current.key === 'genres') return options.genres.map((value) => ({ id: value, value }));
    if (current.key === 'keywords') return options.keywords.map((value) => ({ id: value, value }));
    return actors.map((actor) => ({
      id: actor.id || actor.name,
      value: actor.name,
      image: actor.image_url,
    })).filter((actor) => actor.value);
  }, [actors, current.key, options]);

  const toggle = (value) => {
    setStatus('');
    setDraft((preferences) => ({
      ...preferences,
      [current.key]: toggleValue(preferences[current.key], value, current.limit),
    }));
  };

  const save = async () => {
    setStatus('');
    try {
      await onSave(draft);
    } catch (error) {
      setStatus(error.message || '취향을 저장하지 못했습니다.');
    }
  };

  return (
    <div
      className="mypage-modal-backdrop mypage-taste-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) onClose();
      }}
    >
      <section
        className="mypage-taste-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="taste-preference-modal-title"
      >
        <header className="mypage-taste-modal__header">
          <div>
            <span>MY TASTE</span>
            <h2 id="taste-preference-modal-title">직접 선택한 취향 수정</h2>
          </div>
          <button type="button" disabled={saving} onClick={onClose} aria-label="취향 수정 닫기">×</button>
        </header>

        <nav className="mypage-taste-modal__steps" aria-label="취향 수정 단계">
          {STEPS.map((item, index) => (
            <button
              type="button"
              className={`${index === step ? 'is-current' : ''}${index < step ? ' is-complete' : ''}`}
              aria-current={index === step ? 'step' : undefined}
              disabled={index > step || saving}
              onClick={() => setStep(index)}
              key={item.key}
            >
              <strong>{item.label}</strong>
            </button>
          ))}
        </nav>

        <div className="mypage-taste-modal__copy">
          <div>
            <span>STEP {String(step + 1).padStart(2, '0')}</span>
            <h3>{current.title}</h3>
            <p>{current.description}</p>
          </div>
          <strong>{selected.length} / {current.limit}</strong>
        </div>

        <div
          className={`mypage-taste-modal__selected${selected.length ? '' : ' is-empty'}`}
          aria-label={`선택한 ${current.label}`}
        >
          {selected.length ? selected.map((value) => (
              <button type="button" onClick={() => toggle(value)} key={value}>
                {selectedLabel(value)} <span aria-hidden="true">×</span>
              </button>
            )) : null}
        </div>

        <div className="mypage-taste-modal__search-slot">
          {current.key === 'actors' ? (
            <label className="mypage-taste-modal__search">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.2" /><path d="m15.2 15.2 4.3 4.3" /></svg>
              <input
                value={actorSearch}
                onChange={(event) => setActorSearch(event.target.value)}
                placeholder="배우 이름 검색"
                autoFocus
              />
            </label>
          ) : null}
        </div>

        <div className={`mypage-taste-modal__choices is-${current.key}`} aria-busy={loading || actorLoading}>
          {loading || actorLoading ? <p>선택지를 불러오고 있어요…</p> : choices.length ? choices.map((choice) => {
            const isSelected = selected.includes(choice.value);
            return (
              <button
                type="button"
                className={isSelected ? 'is-selected' : ''}
                aria-pressed={isSelected}
                onClick={() => toggle(choice.value)}
                key={choice.id}
              >
                {current.key === 'actors' ? (
                  <span className="mypage-taste-modal__actor-photo">
                    {choice.image ? <img src={choice.image} alt="" /> : choice.value.slice(0, 1)}
                  </span>
                ) : null}
                <span>{current.key === 'keywords' ? getKeywordLabel(choice.value, { compact: true, hashtag: true }) : choice.value}</span>
              </button>
            );
          }) : <p>표시할 선택지가 없습니다.</p>}
        </div>

        <p className={`mypage-taste-modal__status${status ? '' : ' is-empty'}`} role="status">{status || '\u00a0'}</p>

        <footer className="mypage-taste-modal__actions">
          <button type="button" disabled={saving} onClick={step === 0 ? onClose : () => setStep((value) => value - 1)}>
            {step === 0 ? '취소' : '이전'}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={step === STEPS.length - 1 ? save : () => setStep((value) => value + 1)}
          >
            {saving ? '저장 중…' : step === STEPS.length - 1 ? '취향 저장' : '다음'}
          </button>
        </footer>
      </section>
    </div>
  );
}

export default TastePreferenceModal;
