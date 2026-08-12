import { useEffect, useState } from 'react';

import {
  fetchActors,
  getLocalPreferences,
  fetchOnboardingOptions,
  fetchUserPreferences,
  saveOnboardingPreferences,
  updateUserPreferences,
} from '../../api.js';
import ThemeToggle from '../HeaderFooter/ThemeToggle.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';
import './onboarding.css';

const STEPS = [
  {
    key: 'genres',
    eyebrow: 'STEP 01',
    title: '어떤 장르를 좋아하세요?',
    titleLines: ['어떤 장르를', '좋아하세요?'],
    description: '여러 개 선택할수록 취향에 가까운 영화를 찾기 쉬워져요.',
    mascot: '/images/character/mu/upper-body/mu-upper-thinking-v1.webp',
  },
  {
    key: 'actors',
    eyebrow: 'STEP 02',
    title: '좋아하는 배우가 있나요?',
    titleLines: ['좋아하는', '배우가 있나요?'],
    description: '관심 있는 배우를 검색하고 선택해 주세요.',
    mascot: '/images/character/mu/upper-body/mu-upper-searching-v1.webp',
  },
  {
    key: 'keywords',
    eyebrow: 'STEP 03',
    title: '어떤 이야기에 끌리세요?',
    titleLines: ['어떤 이야기에', '끌리세요?'],
    description: '마음이 가는 영화 키워드를 골라주세요.',
    mascot: '/images/character/mu/upper-body/mu-upper-joy-v1.webp',
    mascotClass: 'onboarding-step-mu--keyword',
  },
];

const MUMU_WALK_FRAMES = [
  '/images/character/mu/walk/mumu-walk-1-v1.webp',
  '/images/character/mu/walk/mumu-walk-2-v1.webp',
  '/images/character/mu/walk/mumu-walk-3-v1.webp',
];

const MUMU_SUCCESS_IMAGE = '/images/character/mu/mu-success-cutout-v2.webp';

function toggleValue(values, value, limit) {
  if (values.includes(value)) return values.filter((item) => item !== value);
  if (values.length >= limit) return values;
  return [...values, value];
}

function OnboardingPage({ authUser, isGuest, onComplete }) {
  const [isArrivingWithLogo] = useState(
    () => ['signup', 'guest', 'login'].includes(window.sessionStorage.getItem('musubi-onboarding-arrive'))
  );
  const [leavingToHome, setLeavingToHome] = useState(false);
  const [started, setStarted] = useState(false);
  const [leavingWelcome, setLeavingWelcome] = useState(false);
  const [walkSettled, setWalkSettled] = useState(false);
  const [walkFrame, setWalkFrame] = useState(0);
  const [stepControlsReady, setStepControlsReady] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisDotCount, setAnalysisDotCount] = useState(1);
  const [step, setStep] = useState(0);
  const [options, setOptions] = useState({ genres: [], keywords: [] });
  const [actors, setActors] = useState([]);
  const [actorSearch, setActorSearch] = useState('');
  const [preferences, setPreferences] = useState({ genres: [], actors: [], keywords: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const successImage = new Image();
    successImage.src = MUMU_SUCCESS_IMAGE;
    window.sessionStorage.removeItem('musubi-onboarding-arrive');
    const restoreOnboardingPage = () => setLeavingToHome(false);
    window.addEventListener('pageshow', restoreOnboardingPage);
    return () => window.removeEventListener('pageshow', restoreOnboardingPage);
  }, []);

  const completeToHome = async () => {
    setLeavingToHome(true);
    window.sessionStorage.setItem('musubi-home-arrive', 'onboarding');
    await new Promise((resolve) => window.setTimeout(resolve, 680));
    onComplete();
  };

  useEffect(() => {
    if (!isGuest && !authUser) {
      window.location.href = '/';
      return undefined;
    }

    const controller = new AbortController();
    const requests = [
      fetchOnboardingOptions(controller.signal),
      fetchActors(controller.signal, { limit: 24, onboarding: true }),
    ];
    if (!isGuest) requests.push(fetchUserPreferences(controller.signal));

    Promise.all(requests)
      .then(async ([optionData, actorData, memberPreferences]) => {
        if (memberPreferences?.onboarding_completed) {
          await completeToHome();
          return;
        }

        setOptions({
          ...optionData,
          keywords: Array.from(new Set(optionData.keywords || [])),
        });
        setActors(actorData);

        const savedPreferences = isGuest
          ? getLocalPreferences()
          : memberPreferences?.preferences;

        if (savedPreferences) {
          setPreferences({
            genres: savedPreferences.genres || [],
            actors: savedPreferences.actors || [],
            keywords: savedPreferences.keywords || [],
          });
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [authUser, isGuest, onComplete]);

  useEffect(() => {
    if (step !== 1) return undefined;

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchActors(controller.signal, {
        query: actorSearch,
        limit: 24,
        onboarding: !actorSearch.trim(),
      })
        .then(setActors)
        .catch((error) => {
          if (error.name !== 'AbortError') setStatus(error.message);
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [actorSearch, step]);

  useEffect(() => {
    if (!leavingWelcome) return undefined;

    const frameTimer = window.setInterval(
      () => setWalkFrame((currentFrame) => (currentFrame + 1) % MUMU_WALK_FRAMES.length),
      105,
    );
    const settleTimer = window.setTimeout(() => setWalkSettled(true), 1650);
    const transitionTimer = window.setTimeout(() => setStarted(true), 1950);

    return () => {
      window.clearInterval(frameTimer);
      window.clearTimeout(settleTimer);
      window.clearTimeout(transitionTimer);
    };
  }, [leavingWelcome]);

  useEffect(() => {
    if (!analyzing) return undefined;

    const dotTimer = window.setInterval(
      () => setAnalysisDotCount((count) => (count % 3) + 1),
      420,
    );

    return () => window.clearInterval(dotTimer);
  }, [analyzing]);

  useEffect(() => {
    if (!started) return undefined;

    const timer = window.setTimeout(() => setStepControlsReady(true), 420);
    return () => window.clearTimeout(timer);
  }, [started]);

  const current = STEPS[step];
  const selectedCount = preferences[current.key].length;

  const handleFinish = async () => {
    setSaving(true);
    setStatus('');

    try {
      if (isGuest) {
        await updateUserPreferences(preferences);
        localStorage.setItem('musubi.guestOnboardingCompleted', 'true');
      } else {
        await saveOnboardingPreferences(preferences);
      }

      setAnalyzing(true);
      await new Promise((resolve) => window.setTimeout(resolve, 2200));
      await completeToHome();
    } catch (error) {
      setStatus(error.message);
      setSaving(false);
    }
  };

  const handleSkip = async () => {
    const emptyPreferences = { genres: [], actors: [], keywords: [] };
    setSaving(true);
    setStatus('');

    try {
      if (isGuest) {
        await updateUserPreferences(emptyPreferences);
        localStorage.setItem('musubi.guestOnboardingCompleted', 'true');
      } else {
        await saveOnboardingPreferences(emptyPreferences);
      }

      await completeToHome();
    } catch (error) {
      setStatus(error.message);
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <main
        className={`onboarding onboarding--loading${isArrivingWithLogo ? ' onboarding--arriving-with-logo' : ''}${leavingToHome ? ' onboarding--leaving-for-home' : ''}`}
        aria-label="취향 설정 준비 중"
      >
        <header className="onboarding-header">
          <span className="onboarding-logo" aria-label="Musubi">
            <img className="onboarding-logo__dark" src="/images/brand/musubi-logo-dark.webp" alt="Musubi" decoding="async" />
            <img className="onboarding-logo__light" src="/images/brand/musubi-logo.webp" alt="Musubi" decoding="async" />
          </span>
        </header>
        <div className="onboarding-theme-toggle">
          <ThemeToggle />
        </div>
        <section className="onboarding-card" aria-hidden="true">
          <div className="onboarding-welcome onboarding-welcome--skeleton">
            <div className="onboarding-welcome__title">
              <SkeletonBlock className="onboarding-welcome-skeleton__title-piece is-left" />
              <SkeletonBlock className="onboarding-welcome-skeleton__title-piece is-right" />
            </div>
            <div className="onboarding-mu-stage">
              <SkeletonBlock className="onboarding-welcome-skeleton__mascot" />
            </div>
            <div className="onboarding-welcome__message onboarding-welcome__message--left">
              <SkeletonBlock className="onboarding-welcome-skeleton__label" />
              <SkeletonBlock className="onboarding-welcome-skeleton__copy" />
              <SkeletonBlock className="onboarding-welcome-skeleton__copy is-short" />
            </div>
            <div className="onboarding-welcome__message onboarding-welcome__message--right">
              <SkeletonBlock className="onboarding-welcome-skeleton__copy" />
              <SkeletonBlock className="onboarding-welcome-skeleton__copy is-short" />
            </div>
            <SkeletonBlock className="onboarding-welcome__skip onboarding-welcome-skeleton__button" />
            <SkeletonBlock className="onboarding-welcome__start onboarding-welcome-skeleton__button" />
          </div>
        </section>
      </main>
    );
  }

  return (
    <main
      className={`onboarding${started && !stepControlsReady ? ' onboarding--step-arriving' : ''}${isArrivingWithLogo ? ' onboarding--arriving-with-logo' : ''}${leavingToHome ? ' onboarding--leaving-for-home' : ''}`}
      data-step={step + 1}
      aria-label="초기 취향 설정"
    >
      <div className="onboarding-atmosphere" aria-hidden="true">
        <span className="onboarding-glow onboarding-glow--one" />
        <span className="onboarding-glow onboarding-glow--two" />
        <span className="onboarding-filmstrip" />
        <svg className="onboarding-thread" viewBox="0 0 1440 240" preserveAspectRatio="none">
          <path d="M-40 138 C 180 24, 350 228, 570 118 S 960 36, 1140 142 S 1370 208, 1490 72" />
        </svg>
      </div>
      <header className="onboarding-header">
        <a href="/?scene=4" aria-label="Musubi 로그인 화면으로 이동" className="onboarding-logo">
          <img className="onboarding-logo__dark" src="/images/brand/musubi-logo-dark.webp" alt="Musubi" decoding="async" />
          <img className="onboarding-logo__light" src="/images/brand/musubi-logo.webp" alt="Musubi" decoding="async" />
        </a>
      </header>
      <div className="onboarding-theme-toggle">
        <ThemeToggle />
      </div>

      <section className="onboarding-card">
        {!started ? (
          <div className={`onboarding-welcome${leavingWelcome ? ' is-leaving' : ''}${walkSettled ? ' is-settled' : ''}`}>
            <h1 className="onboarding-welcome__title">
              <span>반가워요,</span>
              <span>저는 <em>무무</em>예요!</span>
            </h1>
            <div className="onboarding-welcome__message onboarding-welcome__message--left">
              <span className="onboarding-mu-label">Welcome to the MUSUBI</span>
              <p>Musubi의 마스코트 무무가<br />당신의 취향을 분석해서</p>
            </div>
            <div className="onboarding-mu-stage">
              <img
                src={leavingWelcome
                  ? walkSettled
                    ? '/images/character/mu/mu-thinking-v1.webp'
                    : MUMU_WALK_FRAMES[walkFrame]
                  : '/images/character/mu/mu-onboarding-hi-v1.webp?v=20260812-1'}
                alt={leavingWelcome ? '' : '손을 흔들며 인사하는 Musubi 마스코트 무무'}
              />
            </div>
            <div className="onboarding-welcome__message onboarding-welcome__message--right">
              <p>마음에 쏙 드는 영화를<br />이어드릴게요.</p>
            </div>
            <button
              className="onboarding-welcome__start"
              type="button"
              disabled={saving || leavingWelcome}
              onClick={() => setLeavingWelcome(true)}
            >
              무무와 취향 찾기
            </button>
            <button className="onboarding-welcome__skip" type="button" disabled={saving} onClick={handleSkip}>
              {saving ? '이동 중...' : '건너뛰기'}
            </button>
            {status ? <p className="onboarding-welcome__status" role="status">{status}</p> : null}
          </div>
        ) : analyzing ? (
          <div className="onboarding-analysis" role="status" aria-live="polite">
            <div className="onboarding-analysis__visual">
              <span className="onboarding-analysis__ring" />
              <img src={MUMU_SUCCESS_IMAGE} alt="취향 분석을 마친 Musubi 마스코트 무무" />
              {[...preferences.genres, ...preferences.actors, ...preferences.keywords]
                .slice(0, 6)
                .map((item, index) => (
                  <span
                    className={`onboarding-analysis__tag onboarding-analysis__tag--${index + 1}`}
                    key={`${item}-${index}`}
                  >
                    {getKeywordLabel(item)}
                  </span>
                ))}
            </div>
            <span className="onboarding-mu-label">MUMU IS CONNECTING...</span>
            <h1>취향을 영화와 잇고 있어요</h1>
            <p>선택한 취향을 분석해 첫 추천을 준비할게요.</p>
            <div className="onboarding-analysis__dots" aria-hidden="true">
              {'.'.repeat(analysisDotCount)}
            </div>
          </div>
        ) : (
          <>
        <div className="onboarding-progress" aria-label={`${step + 1} / ${STEPS.length} 단계`}>
          {STEPS.map((item, index) => (
            <button
              type="button"
              className={`${index <= step ? 'is-on' : ''}${index === step ? ' is-current' : ''}`}
              key={item.key}
              disabled={index > step || saving}
              onClick={() => setStep(index)}
              aria-label={`${index + 1}단계 ${item.title}`}
            >
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{item.key === 'genres' ? '장르' : item.key === 'actors' ? '배우' : '키워드'}</strong>
            </button>
          ))}
        </div>

        <div className="onboarding-step-content" key={current.key}>
        <div className="onboarding-copy">
          <img
            className={`onboarding-step-mu${current.mascotClass ? ` ${current.mascotClass}` : ''}`}
            src={current.mascot}
            alt=""
            aria-hidden="true"
          />
          <span className="onboarding-step-label">{current.eyebrow} · WITH MUMU</span>
          <h1>
            {current.titleLines
              ? current.titleLines.map((line, index) => (
                  <span key={line}>
                    {line}
                    {index < current.titleLines.length - 1 ? <br /> : null}
                  </span>
                ))
              : current.title}
          </h1>
          <p>{current.description}</p>
        </div>

        {current.key === 'genres' ? (
          <div className="onboarding-choice-panel">
            <div className="onboarding-choice-panel__header">
              <span>최대 5개까지 선택할 수 있어요</span>
              <strong>{selectedCount} / 5 선택</strong>
            </div>
            <div className="onboarding-choice-grid onboarding-choice-grid--genres">
              {options.genres.map((genre) => {
                const selected = preferences.genres.includes(genre);
                return (
                  <button
                    className={selected ? 'is-selected' : ''}
                    type="button"
                    aria-pressed={selected}
                    key={genre}
                    onClick={() => setPreferences((value) => ({ ...value, genres: toggleValue(value.genres, genre, 5) }))}
                  >
                    {genre}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {current.key === 'actors' ? (
          <div className="onboarding-choice-panel onboarding-choice-panel--actors">
            <div className="onboarding-choice-panel__header">
              <span>최대 5명까지 선택할 수 있어요</span>
              <strong>{selectedCount} / 5 선택</strong>
            </div>
            <div className="onboarding-actor-area">
              <label className="onboarding-search">
                <span className="onboarding-search__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" focusable="false">
                    <circle cx="10.8" cy="10.8" r="6.3" />
                    <path d="m15.5 15.5 4.2 4.2" />
                  </svg>
                </span>
                <input value={actorSearch} onChange={(event) => setActorSearch(event.target.value)} placeholder="배우 이름을 입력해 주세요" />
              </label>
              <div className="onboarding-choice-grid onboarding-choice-grid--actors">
                {actors.map((actor) => {
                  const selected = preferences.actors.includes(actor.name);
                  return (
                    <button
                      className={selected ? 'is-selected' : ''}
                      type="button"
                      aria-pressed={selected}
                      key={actor.id || actor.name}
                      onClick={() => setPreferences((value) => ({ ...value, actors: toggleValue(value.actors, actor.name, 5) }))}
                    >
                      <span className="onboarding-actor-photo">
                        {actor.image_url ? <img src={actor.image_url} alt="" /> : actor.name.slice(0, 1)}
                      </span>
                      <span>{actor.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : null}

        {current.key === 'keywords' ? (
          <div className="onboarding-choice-panel">
            <div className="onboarding-choice-panel__header">
              <span>최대 6개까지 선택할 수 있어요</span>
              <strong>{selectedCount} / 6 선택</strong>
            </div>
            <div className="onboarding-choice-grid onboarding-choice-grid--keywords">
              {options.keywords.map((keyword) => {
                const selected = preferences.keywords.includes(keyword);
                return (
                  <button
                    className={selected ? 'is-selected' : ''}
                    type="button"
                    aria-pressed={selected}
                    key={keyword}
                    onClick={() => setPreferences((value) => ({ ...value, keywords: toggleValue(value.keywords, keyword, 6) }))}
                  >
                    {getKeywordLabel(keyword, { compact: true, hashtag: true })}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
        </div>

        {status ? <p className="onboarding-status" role="status">{status}</p> : null}

        <footer className={`onboarding-actions${step === 0 ? ' onboarding-actions--first' : ''}`}>
          {step > 0 ? (
            <button type="button" className="onboarding-back" disabled={saving} onClick={() => setStep((value) => value - 1)}>이전</button>
          ) : null}
          <button
            type="button"
            className="onboarding-next"
            disabled={saving}
            onClick={step === STEPS.length - 1 ? handleFinish : () => setStep((value) => value + 1)}
          >
            {saving ? '저장 중' : step === STEPS.length - 1 ? '무무에게 분석 맡기기' : '다음'}
          </button>
        </footer>
          </>
        )}
      </section>
    </main>
  );
}

export default OnboardingPage;
