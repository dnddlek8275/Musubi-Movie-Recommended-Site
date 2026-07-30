import { useEffect, useState } from 'react';

import DefaultLayout from './default.jsx';
import ChatPage from '/src/components/chat/chat.jsx';
import AutoChatPage from '/src/components/chat/AutoChatPage.jsx';
import GroupChatPage from '/src/components/chat/GroupChatPage.jsx';
import Recommendation from '/src/components/recomendation/recomendation.jsx';
import IndexPage from './components/index/index.jsx';
import LoginPage from './components/login/LoginPage.jsx';
import PasswordResetPage from './components/login/PasswordResetPage.jsx';
import SignupPage from './components/signup/SignupPage.jsx';
import MyPage from './components/mypage/MyPage.jsx';
import AdminApiPage from './components/admin/AdminApiPage.jsx';

import {
  clearStoredAuth,
  getStoredAuthUser,
  logoutUser,
  scheduleAutoLogout,
} from '/src/api.js';

import pageData from './components/index/indexPageData.json';

const DESIGN_WIDTH = 1920;
// 이 폭 이하에서는 캔버스 축소(scale)를 끄고 CSS 반응형 1열 레이아웃으로 전환한다.
const MOBILE_BREAKPOINT = 768;

function App() {
  const [authUser, setAuthUser] = useState(() => getStoredAuthUser());

  // 이미 로그인된 상태로 접속하면 토큰 만료 시각에 맞춰 자동 로그아웃 타이머를 예약한다.
  useEffect(() => {
    scheduleAutoLogout();
  }, []);

  useEffect(() => {
    const appShell = document.querySelector('.app-shell');
    if (!appShell) return undefined;

    const updateScale = () => {
      // 모바일: 축소하지 않고(scale=1) 자연스러운 문서 높이로 되돌린다.
      if (window.innerWidth <= MOBILE_BREAKPOINT) {
        document.documentElement.style.setProperty('--page-scale', '1');
        document.body.style.height = 'auto';
        return;
      }

      const scale = window.innerWidth / DESIGN_WIDTH;

      document.documentElement.style.setProperty('--page-scale', String(scale));
      document.body.style.height = `${appShell.scrollHeight * scale}px`;
    };

    updateScale();

    const resizeObserver = new ResizeObserver(updateScale);
    resizeObserver.observe(appShell);
    window.addEventListener('resize', updateScale);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateScale);
    };
  }, []);

  const pathname = window.location.pathname;
  const isAdminPage = pathname.startsWith('/admin');

  // /chat/auto (CineBuddy 자동 대화), /chat/group (배우대기실) 은 /chat 보다 먼저 판별한다.
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
    pathname.startsWith('/recommendations');

  const isMyPage =
    pathname.startsWith('/components/mypage/MyPage') ||
    pathname.startsWith('/mypage');

  const isRecentRecommendations =
    isRecomendationPage &&
    new URLSearchParams(window.location.search).get('view') === 'recent';

  const isProtectedPage =
    isAutoChatPage ||
    isGroupChatPage ||
    isChatPage ||
    isMyPage ||
    isRecentRecommendations;

  const handleLogin = (user) => {
    setAuthUser(user);
    window.location.href = '/';
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

  if (isAdminPage) {
    return <AdminApiPage authUser={authUser} />;
  }

  return (
    <DefaultLayout
      authUser={authUser}
      footer={pageData.footer}
      navigation={pageData.navigation}
      onLogout={handleLogout}
    >
      {isProtectedPage && !authUser ? (
        <LoginPage onLogin={handleLogin} />
      ) : isAutoChatPage ? (
        <AutoChatPage />
      ) : isGroupChatPage ? (
        <GroupChatPage />
      ) : isChatPage ? (
        <ChatPage />
      ) : isLoginPage ? (
        <LoginPage onLogin={handleLogin} />
      ) : isPasswordResetPage ? (
        <PasswordResetPage />
      ) : isSignupPage ? (
        <SignupPage />
      ) : isRecomendationPage ? (
        <Recommendation authUser={authUser} />
      ) : isMyPage ? (
        <MyPage authUser={authUser} onUserUpdate={handleUserUpdate} />
      ) : (
        <IndexPage authUser={authUser} />
      )}
    </DefaultLayout>
  );
}

export default App;
