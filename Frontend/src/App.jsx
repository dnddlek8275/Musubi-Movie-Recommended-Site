import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useState } from 'react';

import DefaultLayout from './default.jsx';
import LoginPage from './components/login/LoginPage.jsx';
import IntroPage from './components/intro/IntroPage.jsx';

import {
  clearStoredAuth,
  getStoredAuthUser,
  logoutUser,
  scheduleAutoLogout,
} from '/src/api.js';

import pageData from './components/index/indexPageData.json';

// 첫 화면에 필요하지 않은 대형 페이지는 해당 경로에 진입할 때만 내려받는다.
// 관리자·채팅·마이페이지 코드가 인트로/로그인 초기 번들에 섞이지 않게 한다.
const AdminApiPage = lazy(() => import('./components/admin/AdminApiPage.jsx'));
const GroupChatPage = lazy(() => import('./components/chat/GroupChatPage.jsx'));
const HomePage = lazy(() => import('./components/homeVariants/HomeVariantPage.jsx'));
const MovieDetailPage = lazy(() => import('./components/movieDetail/MovieDetailPage.jsx'));
const MyPage = lazy(() => import('./components/mypage/MyPage.jsx'));
const OnboardingPage = lazy(() => import('./components/onboarding/OnboardingPage.jsx'));
const PersonFilmographyPage = lazy(() => import('./components/person/PersonFilmographyPage.jsx'));
const Recommendation = lazy(() => import('./components/recomendation/recomendation.jsx'));
const SignupPage = lazy(() => import('./components/signup/SignupPage.jsx'));

const DESIGN_WIDTH = 1920;
// 이 폭 이하에서는 캔버스 축소(scale)를 끄고 CSS 반응형 1열 레이아웃으로 전환한다.
const MOBILE_BREAKPOINT = 768;

function PageLoadFallback() {
  return (
    <main
      aria-busy="true"
      aria-label="페이지 불러오는 중"
      style={{ minHeight: '100vh', background: 'var(--page-bg, #03080b)' }}
    />
  );
}

function LazyPage({ children }) {
  return <Suspense fallback={<PageLoadFallback />}>{children}</Suspense>;
}

function LegacyAutoChatRedirect() {
  useEffect(() => {
    window.location.replace(`/home${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyHomeRedirect() {
  useEffect(() => {
    window.location.replace(`/home${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyCharacterChatRedirect() {
  useEffect(() => {
    window.location.replace(`/chat/group${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyPasswordResetRedirect() {
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') || '';
    const target = token
      ? `/?resetToken=${encodeURIComponent(token)}`
      : '/?auth=password-reset';
    window.location.replace(target);
  }, []);
  return null;
}

function App() {
  const [authUser, setAuthUser] = useState(() => getStoredAuthUser());
  const [isArrivingHome] = useState(
    () => window.sessionStorage.getItem('musubi-home-arrive') === 'onboarding'
  );

  // 모든 페이지는 새로고침하거나 새 문서로 이동할 때 이전 스크롤 위치를
  // 복원하지 않고 항상 페이지 최상단에서 시작한다.
  useLayoutEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    const resetScroll = () => window.scrollTo({ top: 0, left: 0, behavior: 'auto' });

    window.history.scrollRestoration = 'manual';
    resetScroll();
    window.addEventListener('pageshow', resetScroll);
    const frameId = window.requestAnimationFrame(resetScroll);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener('pageshow', resetScroll);
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  // 이미 로그인된 상태로 접속하면 토큰 만료 시각에 맞춰 자동 로그아웃 타이머를 예약한다.
  useEffect(() => {
    scheduleAutoLogout();
    window.sessionStorage.removeItem('musubi-home-arrive');
  }, []);

  useLayoutEffect(() => {
    const updateScale = () => {
      // zoom은 보이는 크기와 문서 레이아웃 높이를 함께 줄여
      // transform 축소 때 생기던 화면 아래의 빈 스크롤 영역을 만들지 않는다.
      document.body.style.height = 'auto';

      if (window.innerWidth <= MOBILE_BREAKPOINT) {
        document.documentElement.style.setProperty('--page-scale', '1');
        return;
      }

      const scale = window.innerWidth / DESIGN_WIDTH;

      document.documentElement.style.setProperty('--page-scale', String(scale));
    };

    const platform = String(
      navigator.userAgentData?.platform || navigator.platform || navigator.userAgent || ''
    ).toLowerCase();
    document.documentElement.dataset.clientPlatform = platform.includes('win')
      ? 'windows'
      : 'default';

    updateScale();

    window.addEventListener('resize', updateScale);

    return () => {
      window.removeEventListener('resize', updateScale);
      document.body.style.height = 'auto';
    };
  }, []);

  const pathname = window.location.pathname;
  const isAdminPage = pathname.startsWith('/admin');
  const isOnboardingPage = pathname.startsWith('/onboarding');
  const movieDetailMatch = pathname.match(/^\/movies\/(\d+)\/?$/);
  const personMatch = pathname.match(/^\/people\/(actor|director)\/([^/]+)\/?$/);
  const isLegacyHomePage = /^\/home[2-5]\/?$/.test(pathname);

  // /chat/auto (무무 자동 대화), /chat/group (배우대기실) 은 /chat 보다 먼저 판별한다.
  const isAutoChatPage =
    pathname.startsWith('/chat/auto') ||
    pathname.startsWith('/cinebuddy');

  const isGroupChatPage =
    pathname.startsWith('/chat/group') ||
    pathname.startsWith('/chatgroup');

  const isChatPage =
    !isAutoChatPage &&
    !isGroupChatPage &&
    (pathname.startsWith('/components/chat/chat') ||
      pathname.startsWith('/chat'));

  const isLoginPage =
    pathname.startsWith('/components/login/LoginPage') ||
    pathname.startsWith('/login');

  const isSignupPage =
    pathname.startsWith('/components/signup/SignupPage') ||
    pathname.startsWith('/signup');

  const isPasswordResetPage =
    pathname.startsWith('/password-reset') ||
    pathname.startsWith('/reset-password');

  const isRecomendationPage =
    pathname.startsWith('/components/recomendation/recomendation') ||
    pathname.startsWith('/recomendation') ||
    pathname.startsWith('/recommendation') ||
    pathname.startsWith('/recommendations');

  const isMyPage =
    pathname.startsWith('/components/mypage/MyPage') ||
    pathname === '/mypage' ||
    pathname.startsWith('/mypage/');

  const isRecentRecommendations =
    isRecomendationPage &&
    new URLSearchParams(window.location.search).get('view') === 'recent';

  const isProtectedPage =
    isMyPage ||
    isRecentRecommendations;

  const handleLogin = (user) => {
    setAuthUser(user);
    if (user?.onboardingCompleted === false) {
      window.location.replace('/onboarding');
      return;
    }

    window.sessionStorage.removeItem('musubi-onboarding-arrive');
    window.sessionStorage.removeItem('musubi-home-arrive');
    window.location.replace('/home');
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (error) {
      console.error('로그아웃 실패:', error);
      clearStoredAuth();
    } finally {
      setAuthUser(null);

      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
  };

  const handleUserUpdate = (user) => {
    setAuthUser(user);
  };

  const handleIntroStart = () => {
    window.location.replace('/onboarding?mode=guest');
  };

  const handleOnboardingComplete = useCallback(() => {
    window.location.replace('/home');
  }, []);

  if (isAdminPage) {
    return <LazyPage><AdminApiPage authUser={authUser} /></LazyPage>;
  }

  if (pathname === '/') {
    return <IntroPage onLogin={handleLogin} onStart={handleIntroStart} />;
  }

  if (isOnboardingPage) {
    const isGuest = new URLSearchParams(window.location.search).get('mode') === 'guest';
    return (
      <LazyPage>
        <OnboardingPage
          authUser={authUser}
          isGuest={isGuest}
          onComplete={handleOnboardingComplete}
        />
      </LazyPage>
    );
  }

  if (isLoginPage || (isProtectedPage && !authUser)) {
    return (
      <LoginPage
        onGuest={handleIntroStart}
        onLogin={handleLogin}
      />
    );
  }

  if (isSignupPage) {
    return <LazyPage><SignupPage /></LazyPage>;
  }

  if (isPasswordResetPage) {
    return <LegacyPasswordResetRedirect />;
  }

  if (isAutoChatPage) {
    return <LegacyAutoChatRedirect />;
  }

  if (isChatPage) {
    return <LegacyCharacterChatRedirect />;
  }

  if (isLegacyHomePage) {
    return <LegacyHomeRedirect />;
  }

  return (
    <DefaultLayout
      authUser={authUser}
      footer={pageData.footer}
      isHomeArriving={pathname === '/home' && isArrivingHome}
      navigation={pageData.navigation}
      onLogout={handleLogout}
    >
      <LazyPage>
        {personMatch ? (
          <PersonFilmographyPage
            authUser={authUser}
            identifier={decodeURIComponent(personMatch[2])}
            role={personMatch[1]}
          />
        ) : movieDetailMatch ? (
          <MovieDetailPage authUser={authUser} movieId={movieDetailMatch[1]} />
        ) : isGroupChatPage ? (
          <GroupChatPage authUser={authUser} onLogout={handleLogout} />
        ) : isRecomendationPage ? (
          <Recommendation authUser={authUser} onLogout={handleLogout} />
        ) : isMyPage ? (
          <MyPage authUser={authUser} onLogout={handleLogout} onUserUpdate={handleUserUpdate} />
        ) : (
          <HomePage authUser={authUser} onLogout={handleLogout} />
        )}
      </LazyPage>
    </DefaultLayout>
  );
}

export default App;
