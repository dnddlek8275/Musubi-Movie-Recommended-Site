import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useState } from 'react';

import DefaultLayout from './default.jsx';
import LoginPage from './components/login/LoginPage.jsx';
import IntroPage from './components/intro/IntroPage.jsx';
import { NAVIGATION_EVENT, navigateTo, replaceTo } from './navigation.js';

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
const UserActivityPage = lazy(() => import('./components/userActivity/UserActivityPage.jsx'));

const DESIGN_WIDTH = 1920;
// 모바일에서는 축소 캔버스 대신 실제 1열 반응형 레이아웃을 사용한다.
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
    replaceTo(`/home${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyHomeRedirect() {
  useEffect(() => {
    replaceTo(`/home${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyCharacterChatRedirect() {
  useEffect(() => {
    replaceTo(`/chat/group${window.location.search}${window.location.hash}`);
  }, []);
  return null;
}

function LegacyPasswordResetRedirect() {
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') || '';
    const target = token
      ? `/?resetToken=${encodeURIComponent(token)}`
      : '/?auth=password-reset';
    replaceTo(target);
  }, []);
  return null;
}

function App() {
  const [, setNavigationVersion] = useState(0);
  const pathname = window.location.pathname;
  const search = window.location.search;
  const hash = window.location.hash;
  const [authUser, setAuthUser] = useState(() => getStoredAuthUser());
  const [isArrivingHome] = useState(
    () => ['login', 'onboarding'].includes(window.sessionStorage.getItem('musubi-home-arrive'))
  );

  // 동일 출처 링크는 문서 전체를 다시 받지 않고 현재 React 앱 안에서 전환한다.
  // 브라우저 뒤로/앞으로 가기와 기존 <a href> 링크를 모두 지원한다.
  useEffect(() => {
    const refreshRoute = () => setNavigationVersion((value) => value + 1);
    const handleDocumentClick = (event) => {
      if (
        event.defaultPrevented
        || event.button !== 0
        || event.metaKey
        || event.ctrlKey
        || event.shiftKey
        || event.altKey
      ) return;
      const anchor = event.target.closest?.('a[href]');
      if (!anchor || anchor.target || anchor.download || anchor.dataset.fullReload === 'true') return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
      event.preventDefault();
      navigateTo(`${url.pathname}${url.search}${url.hash}`);
    };

    window.addEventListener('popstate', refreshRoute);
    window.addEventListener(NAVIGATION_EVENT, refreshRoute);
    document.addEventListener('click', handleDocumentClick);
    return () => {
      window.removeEventListener('popstate', refreshRoute);
      window.removeEventListener(NAVIGATION_EVENT, refreshRoute);
      document.removeEventListener('click', handleDocumentClick);
    };
  }, []);

  useLayoutEffect(() => {
    if (hash) {
      let frameId = 0;
      let attempts = 0;
      const findHashTarget = () => {
        let targetId = hash.slice(1);
        try {
          targetId = decodeURIComponent(targetId);
        } catch {
          // 잘못 인코딩된 해시는 원문 ID로 한 번만 확인한다.
        }
        const target = document.getElementById(targetId);
        if (target) {
          target.scrollIntoView();
          return;
        }
        attempts += 1;
        if (attempts < 20) frameId = window.requestAnimationFrame(findHashTarget);
      };
      frameId = window.requestAnimationFrame(findHashTarget);
      return () => window.cancelAnimationFrame(frameId);
    } else {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    }
    return undefined;
  }, [pathname, search, hash]);

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
      document.body.style.height = 'auto';

      if (window.innerWidth <= MOBILE_BREAKPOINT) {
        document.documentElement.style.setProperty('--page-scale', '1');
        return;
      }

      // 1920px 시안은 작은 데스크톱 화면에 맞춰 축소하되,
      // 1920px보다 큰 화면에서 UI가 불필요하게 확대되지는 않게 한다.
      const scale = Math.min(1, window.innerWidth / DESIGN_WIDTH);
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

  const isAdminPage = pathname.startsWith('/admin');
  const isOnboardingPage = pathname.startsWith('/onboarding');
  const movieDetailMatch = pathname.match(/^\/movies\/(\d+)\/?$/);
  const personMatch = pathname.match(/^\/people\/(actor|director)\/([^/]+)\/?$/);
  const userActivityMatch = pathname.match(/^\/users\/(\d+)\/activity\/?$/);
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
        replaceTo('/login');
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
      {/* 경로가 바뀌면 페이지 내부의 일시 상태를 새로 시작한다.
          채팅을 나갔다 돌아왔을 때 이전 활성 UI가 재사용되는 것을 막는다. */}
      <LazyPage key={pathname}>
        {userActivityMatch ? (
          <UserActivityPage authUser={authUser} userId={userActivityMatch[1]} />
        ) : personMatch ? (
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
