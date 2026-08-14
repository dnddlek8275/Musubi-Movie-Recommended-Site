import { useState } from 'react';

import { clearStoredAuth, loginWithEmail } from '../../api.js';
import './login.css';

const SAVED_LOGIN_EMAIL_KEY = 'musubi.savedLoginEmail';

function getInitialForm() {
  const savedEmail = window.localStorage.getItem(SAVED_LOGIN_EMAIL_KEY) || '';
  return {
    email: savedEmail,
    password: '',
    remember: Boolean(savedEmail),
  };
}

function LoginForm({ onGuest, onLogin, onPasswordReset }) {
  const [form, setForm] = useState(getInitialForm);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const updateField = (event) => {
    const { checked, name, type, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const intro = event.currentTarget.closest('.intro');

    const email = form.email.trim();
    const password = form.password;

    if (!email || !password) {
      setStatus('이메일과 비밀번호를 모두 입력해 주세요.');
      return;
    }

    setBusy(true);
    setStatus('');
    clearStoredAuth();

    try {
      const user = await loginWithEmail({
        email,
        password,
      });

      if (form.remember) {
        window.localStorage.setItem(SAVED_LOGIN_EMAIL_KEY, email);
      } else {
        window.localStorage.removeItem(SAVED_LOGIN_EMAIL_KEY);
      }

      setStatus('로그인 성공');

      if (onLogin) {
        if (intro && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          intro.classList.add('is-leaving-for-member-onboarding');
          if (user.onboardingCompleted === false) {
            window.sessionStorage.setItem('musubi-onboarding-arrive', 'login');
            window.sessionStorage.removeItem('musubi-home-arrive');
          } else {
            window.sessionStorage.removeItem('musubi-onboarding-arrive');
            // 새 문서로 열리는 /home이 로그인 화면의 로고 위치를 이어받도록 한다.
            window.sessionStorage.setItem('musubi-home-arrive', 'login');
          }
          window.setTimeout(() => onLogin(user), 680);
        } else {
          onLogin(user);
        }
      } else {
        window.location.href = '/home';
      }
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const handleSignupNavigate = (event) => {
    event.preventDefault();

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.location.href = '/signup';
      return;
    }

    const intro = event.currentTarget.closest('.intro');
    if (!intro) {
      window.location.href = '/signup';
      return;
    }

    intro.classList.add('is-leaving-for-signup');
    window.sessionStorage.setItem('musubi-signup-arrive', '1');
    window.setTimeout(() => {
      window.location.href = '/signup';
    }, 430);
  };

  const handleGuestNavigate = (event) => {
    if (!onGuest) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onGuest();
      return;
    }

    const intro = event.currentTarget.closest('.intro');
    if (!intro) {
      onGuest();
      return;
    }

    intro.classList.add('is-leaving-for-guest-onboarding');
    window.sessionStorage.setItem('musubi-onboarding-arrive', 'guest');
    window.setTimeout(onGuest, 680);
  };

  const handlePasswordReset = (event) => {
    event.preventDefault();

    if (!onPasswordReset) {
      window.location.href = '/?auth=password-reset';
      return;
    }

    const intro = event.currentTarget.closest('.intro');
    if (!intro || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onPasswordReset();
      return;
    }

    intro.classList.add('is-switching-to-password-reset');
    window.setTimeout(() => {
      onPasswordReset();
      intro.classList.remove('is-switching-to-password-reset');
    }, 280);
  };

  return (
    <>
      <form className="login-form" onSubmit={handleSubmit}>
        <label className="login-field">
          <span>이메일</span>
          <input
            autoComplete="username"
            name="email"
            onChange={updateField}
            placeholder="이메일"
            type="text"
            value={form.email}
            disabled={busy}
          />
        </label>

        <label className="login-field">
          <span>비밀번호</span>
          <input
            autoComplete="current-password"
            name="password"
            onChange={updateField}
            placeholder="비밀번호"
            type="password"
            value={form.password}
            disabled={busy}
          />
        </label>

        <div className="login-options">
          <label className="login-check">
            <input
              checked={form.remember}
              name="remember"
              onChange={updateField}
              type="checkbox"
              disabled={busy}
            />
            <span>아이디 저장</span>
          </label>

          <a href="/?auth=password-reset" onClick={handlePasswordReset}>비밀번호 찾기</a>
        </div>

        {status ? (
          <p className="login-status" role="status">
            {status}
          </p>
        ) : null}

        <button className="login-submit" type="submit" disabled={busy}>
          {busy ? '로그인 중' : '로그인'}
        </button>

        {onGuest ? (
          <button className="login-guest" type="button" onClick={handleGuestNavigate} disabled={busy}>
            비회원으로 둘러보기
          </button>
        ) : null}
      </form>

      <p className="login-join">
        <a href="/signup" onClick={handleSignupNavigate}>회원가입</a>하고 더 많은 기능을 누려보세요
      </p>
    </>
  );
}

export default LoginForm;
