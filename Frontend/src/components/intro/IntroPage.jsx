import { useEffect, useMemo, useState } from 'react';

import data from '/src/imgData.json';
import LoginForm from '../login/LoginForm.jsx';
import PasswordResetForm from '../login/PasswordResetForm.jsx';
import './intro.css';

const SCENE_DURATIONS = [3400, 4600, 5200, 5200];
const GENRES = [
  '#로맨스',
  '#SF',
  '#스릴러',
  '#코미디',
  '취향에 맞게 쏙',
  '이제 고민은 끝',
  '#공포',
  '#액션',
  '#드라마',
  '#판타지',
  '#미스터리',
  '10,000+ 개의 영화',
];

const CHIP_POSITIONS = [
  [19, 9, -3, 0.2],
  [22, 72, 3, 1.1],
  [72, 12, 2, 0.7],
  [78, 75, -2, 1.8],
  [43, 4, 4, 1.3],
  [48, 80, -4, 0.4],
  [8, 47, 2, 1.6],
  [85, 45, -3, 0.9],
  [28, 22, 3, 2.1],
  [64, 65, -2, 1.4],
  [62, 25, 4, 0.1],
  [18, 39, -4, 2.3],
];

const POPCORN = Array.from({ length: 34 }, (_, index) => ({
  left: (index * 29) % 100,
  dx: ((index * 43) % 140) - 70,
  rotation: 300 + ((index * 37) % 120),
  duration: 2.2 + ((index * 17) % 18) / 10,
  delay: ((index * 13) % 16) / 10,
  size: 18 + ((index * 11) % 20),
}));

const MU_INTRO_STATES = [
  {
    src: '/images/character/mu/upper-body/mu-upper-default-v1.webp',
    scale: 1,
    positionY: '16%',
  },
  {
    src: '/images/character/mu/upper-body/mu-upper-joy-v1.webp',
    scale: 1.13,
    positionY: '17%',
  },
  {
    src: '/images/character/mu/upper-body/mu-upper-thinking-v1.webp',
    scale: 1.02,
    positionY: '16%',
  },
  {
    src: '/images/character/mu/upper-body/mu-upper-searching-v1.webp',
    scale: 1.04,
    positionY: '17%',
  },
];

function getInitialTheme() {
  const theme = document.documentElement.getAttribute('data-theme');
  return theme === 'dark' ? 'dark' : 'light';
}

function getInitialScene() {
  const params = new URLSearchParams(window.location.search);
  const requestedScene = Number(params.get('scene'));
  const isPasswordReset = params.get('auth') === 'password-reset' || params.has('resetToken');
  return requestedScene === 4 || isPasswordReset ? 4 : 0;
}

function IntroPage({ entryClassName = '', entryContent, initialScene, onLogin, onStart, pageClassName = '' }) {
  const [scene, setScene] = useState(() =>
    Number.isInteger(initialScene) ? initialScene : getInitialScene()
  );
  const [theme, setTheme] = useState(getInitialTheme);
  const [authMode, setAuthMode] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('auth') === 'password-reset' || params.has('resetToken')
      ? 'password-reset'
      : 'login';
  });
  const [resetToken] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('resetToken') || '';
  });
  const promos = data.introHero?.promos || data.hero.promos;
  const bannerFlowDurations = [68, 54, 61, 47];
  const bannerRows = useMemo(
    () => Array.from(
      { length: 4 },
      (_, rowIndex) => promos.filter((_, index) => index % 4 === rowIndex),
    ),
    [promos],
  );

  const chips = useMemo(
    () =>
      GENRES.map((label, index) => {
        const [top, left, rotation, delay] = CHIP_POSITIONS[index];
        return { label, top, left, rotation, delay };
      }),
    [],
  );

  useEffect(() => {
    if (scene >= SCENE_DURATIONS.length) return undefined;

    const timer = window.setTimeout(
      () => setScene((current) => current + 1),
      SCENE_DURATIONS[scene],
    );

    return () => window.clearTimeout(timer);
  }, [scene]);

  useEffect(() => {
    const resetTransientTransition = () => {
      document.querySelector('.intro')?.classList.remove(
        'is-leaving-for-signup',
        'is-leaving-for-guest-onboarding',
        'is-leaving-for-member-onboarding',
      );
    };

    window.addEventListener('pagehide', resetTransientTransition);
    window.addEventListener('pageshow', resetTransientTransition);
    return () => {
      window.removeEventListener('pagehide', resetTransientTransition);
      window.removeEventListener('pageshow', resetTransientTransition);
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);

    try {
      localStorage.setItem('cineverse-theme', theme);
    } catch (error) {
      // 저장소 접근이 제한된 환경에서는 현재 화면의 테마만 전환한다.
    }
  }, [theme]);

  const handleSceneAdvance = (event) => {
    if (event.target.closest('button')) return;

    if (scene < 4) {
      setScene((current) => current + 1);
    }
  };

  const openPasswordReset = () => {
    setAuthMode('password-reset');
    window.history.replaceState(null, '', '/?auth=password-reset');
  };

  const closePasswordReset = () => {
    setAuthMode('login');
    window.history.replaceState(null, '', '/');
  };

  const resolvedEntryContent = entryContent || (
    authMode === 'password-reset' ? (
      <PasswordResetForm token={resetToken} onBack={closePasswordReset} />
    ) : (
      <LoginForm onGuest={onStart} onLogin={onLogin} onPasswordReset={openPasswordReset} />
    )
  );

  return (
    <main
      className={`intro${pageClassName ? ` ${pageClassName}` : ''}`}
      aria-label="Musubi 서비스 소개"
      onClick={handleSceneAdvance}
    >
      <div className="intro__backdrop" aria-hidden="true" />
      <div className="intro__vignette" aria-hidden="true" />

      <button
        className={`intro-skip-logo${scene === 4 ? ' intro-skip-logo--final' : ''}`}
        type="button"
        aria-label="인트로 마지막 화면으로 이동"
        onClick={(event) => {
          event.stopPropagation();
          setScene(4);
        }}
      >
        <img
          className="intro-skip-logo__image intro-skip-logo__image--dark"
          src="/images/brand/musubi-logo-dark.webp"
          alt=""
        />
        <img
          className="intro-skip-logo__image intro-skip-logo__image--light"
          src="/images/brand/musubi-logo.webp"
          alt=""
        />
      </button>

      <button
        className="intro-theme-toggle"
        type="button"
        aria-label={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
        title={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
        onClick={(event) => {
          event.stopPropagation();
          setTheme((current) => (current === 'light' ? 'dark' : 'light'));
        }}
      >
        <span aria-hidden="true">{theme === 'light' ? '☀' : '☾'}</span>
      </button>

      <section
        className={`intro-scene intro-scene--chaos${scene === 0 ? ' is-active' : ''}`}
        aria-hidden={scene !== 0}
      >
        <div className="intro-chips" aria-hidden="true">
          {chips.map((chip) => (
            <span
              className="intro-chip"
              key={chip.label}
              style={{
                '--chip-top': `${chip.top}%`,
                '--chip-left': `${chip.left}%`,
                '--chip-rotation': `${chip.rotation}deg`,
                '--chip-delay': `${chip.delay}s`,
              }}
            >
              {chip.label}
            </span>
          ))}
        </div>
        <h1>세상엔 너무 많은 영화들이 있어요</h1>
        <p>오늘 밤, 뭘 봐야 할지 또 30분째 고민 중이라면</p>
      </section>

      <section
        className={`intro-scene intro-scene--friend${scene === 1 ? ' is-active' : ''}`}
        aria-hidden={scene !== 1}
      >
        <div className="intro-popcorn-layer" aria-hidden="true">
          {POPCORN.map((kernel, index) => (
            <img
              className="intro-kernel"
              src="/images/intro/popcorn-v1.webp"
              alt=""
              key={index}
              style={{
                '--kernel-left': `${kernel.left}%`,
                '--kernel-dx': `${kernel.dx}px`,
                '--kernel-rotation': `${kernel.rotation}deg`,
                '--kernel-duration': `${kernel.duration}s`,
                '--kernel-delay': `${kernel.delay}s`,
                '--kernel-size': `${kernel.size * 1.5}px`,
              }}
            />
          ))}
        </div>
        <div className="intro-scene__content">
          <span className="intro-badge">팝! 등장</span>
          <h2>
            나한테 <strong>딱 맞는 영화</strong>를
            <br />
            찾아줄 친구가 나타났어요
          </h2>
          <p>고민은 팝콘처럼 톡톡 튀어 사라지게</p>
        </div>
      </section>

      <section
        className={`intro-scene intro-scene--chat${scene === 2 ? ' is-active' : ''}`}
        aria-hidden={scene !== 2}
      >
        <div className="intro-phone">
          <div className="intro-phone__title">영화를 이어주는 메신저, 무무</div>
          <div className="intro-chat">
            <div className="intro-bubble-row intro-bubble-row--me" style={{ '--delay': '.2s' }}>
              <div className="intro-bubble">오늘 기분이 좀 꿀꿀해... 위로되는 영화 없을까?</div>
            </div>
            <div className="intro-response-sequence">
              <div className="intro-bubble-row intro-bubble-row--typing" style={{ '--delay': '.72s', '--typing-duration': '.93s' }}>
                <div className="intro-typing"><span /><span /><span /></div>
              </div>
              <div className="intro-bubble-row" style={{ '--delay': '1.65s' }}>
                <div className="intro-bubble">
                  그런 날엔 잔잔하게 웃다가 마음이 따뜻해지는 영화가 좋죠 🎬
                </div>
              </div>
            </div>
            <div className="intro-response-sequence">
              <div className="intro-bubble-row intro-bubble-row--typing" style={{ '--delay': '2.02s', '--typing-duration': '.78s' }}>
                <div className="intro-typing"><span /><span /><span /></div>
              </div>
              <div className="intro-bubble-row" style={{ '--delay': '2.8s' }}>
                <div className="intro-bubble">
                  <div className="intro-movie-card">
                    <img
                      className="intro-movie-card__poster"
                      src="/images/posters/today-us.webp?v=20260812-1"
                      decoding="async"
                      loading="lazy"
                      alt="오늘, 우리 포스터"
                    />
                    <div>
                      <b>오늘, 우리</b>
                      <span>드라마 · 108분 · 잔잔한 위로</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="intro-bubble-row intro-bubble-row--me" style={{ '--delay': '3.52s' }}>
              <div className="intro-bubble">오 좋다, 바로 볼래!</div>
            </div>
          </div>
        </div>
        <p className="intro-caption">추천도 대화하듯, 자연스럽게</p>
      </section>

      <section
        className={`intro-scene intro-scene--characters${scene === 3 ? ' is-active' : ''}`}
        aria-hidden={scene !== 3}
      >
        <div className="intro-avatars" aria-hidden="true">
          {MU_INTRO_STATES.map((avatar, index) => (
            <span
              className={`intro-avatar${index === 0 || index === 2 ? ' intro-avatar--pick' : ''}`}
              key={avatar.src}
              style={{
                '--delay': `${0.15 + index * 0.12}s`,
                '--avatar-scale': avatar.scale,
                '--avatar-position-y': avatar.positionY,
              }}
            >
              <img src={avatar.src} alt="" />
            </span>
          ))}
        </div>
        <div className="intro-phone">
          <div className="intro-phone__title">영화를 이어주는 메신저, 무무</div>
          <div className="intro-chat">
            <div className="intro-bubble-row intro-bubble-row--me" style={{ '--delay': '.9s' }}>
              <div className="intro-bubble">오늘은 미스터리 영화가 보고 싶어.</div>
            </div>
            <div className="intro-response-sequence">
              <div className="intro-bubble-row intro-bubble-row--typing" style={{ '--delay': '1.15s', '--typing-duration': '.85s' }}>
                <div className="intro-typing"><span /><span /><span /></div>
              </div>
              <div className="intro-bubble-row" style={{ '--delay': '2s' }}>
                <div className="intro-bubble">단서를 따라 몰입할 수 있는 작품을 찾아볼게요. 🔍</div>
              </div>
            </div>
            <div className="intro-bubble-row intro-bubble-row--me" style={{ '--delay': '2.6s' }}>
              <div className="intro-bubble">너무 무겁지는 않았으면 좋겠어.</div>
            </div>
            <div className="intro-response-sequence">
              <div className="intro-bubble-row intro-bubble-row--typing" style={{ '--delay': '2.92s', '--typing-duration': '.82s' }}>
                <div className="intro-typing"><span /><span /><span /></div>
              </div>
              <div className="intro-bubble-row" style={{ '--delay': '3.74s' }}>
                <div className="intro-bubble">그럼 재치 있는 추리 영화부터 이어드릴게요.</div>
              </div>
            </div>
          </div>
        </div>
        <p className="intro-caption">무무와 대화하며, 나만의 영화를 찾아보세요</p>
      </section>

      <section
        className={`intro-scene intro-scene--cta${scene === 4 ? ' is-active' : ''}`}
        aria-hidden={scene !== 4}
      >
        <div className="intro-entry">
          <section
            className={`intro-entry__login${entryClassName ? ` ${entryClassName}` : ''}${!entryContent && authMode === 'password-reset' ? ' intro-entry__login--reset' : ''}`}
            aria-label={entryContent ? '회원가입 입력' : authMode === 'password-reset' ? '비밀번호 재설정' : '로그인 및 비회원 입장'}
          >
            <div className="intro-entry__heading">
              <p>영화와 사람을 잇다</p>
            </div>
            {resolvedEntryContent}
          </section>

          <section className="intro-entry__posters" aria-label="Musubi 영화 배너">
            <div className="intro-entry__banner-stage" aria-hidden="true">
              {bannerRows.map((row, rowIndex) => (
                <div
                  className={`intro-entry__banner-track intro-entry__banner-track--${rowIndex + 1}`}
                  key={`banner-row-${rowIndex + 1}`}
                  style={{ '--intro-banner-flow-duration': `${bannerFlowDurations[rowIndex]}s` }}
                >
                  {[0, 1].map((copyIndex) => (
                    <div className="intro-entry__banner-group" key={`banner-copy-${copyIndex}`}>
                      {row.map((promo, promoIndex) => (
                        <img
                          className="intro-entry__banner"
                          src={promo.highResolutionImage || promo.image}
                          alt=""
                          key={`${copyIndex}-${promo.id}`}
                          loading={copyIndex === 0 && promoIndex === 0 ? 'eager' : 'lazy'}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <div className="intro-entry__poster-copy">
              <span>MUSUBI</span>
              <strong>오늘의 영화로<br />새로운 이야기를 만나보세요</strong>
            </div>
          </section>
        </div>
      </section>

      <nav className="intro-dots" aria-label="인트로 장면 선택">
        {Array.from({ length: 5 }, (_, index) => (
          <button
            className={`intro-dot${scene === index ? ' is-active' : ''}`}
            type="button"
            aria-label={`${index + 1}번째 장면으로 이동`}
            aria-current={scene === index ? 'step' : undefined}
            key={index}
            onClick={(event) => {
              event.stopPropagation();
              setScene(index);
            }}
          />
        ))}
      </nav>
    </main>
  );
}

export default IntroPage;
