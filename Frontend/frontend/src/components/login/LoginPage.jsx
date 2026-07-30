import { useState } from 'react';

import { clearStoredAuth, loginWithEmail } from '../../api.js';

import data from '/src/imgData.json';

import './login.css';


const initialForm = {
  email: '',
  password: '',
  remember: true,
};

function LoginPage({ onLogin }) {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const promos = data.hero.promos.slice(0, 4);

  const updateField = (event) => {
    const { checked, name, type, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const email = form.email.trim();
    const password = form.password;

    if (!email || !password) {
      setStatus('이메일과 비밀번호를 입력해 주세요.');
      return;
    }

    if (!email.includes('@')) {
      setStatus('입력한 정보를 다시 확인해 주세요.');
      return;
    }

    setBusy(true);
    setStatus('');

    // 로그인 시도 전에 이전 세션을 비운다. 이렇게 해야 로그인이 실패하면
    // 로그아웃 상태로 남고(옛 세션이 로그인된 것처럼 남지 않음), 성공해야만 로그인된다.
    clearStoredAuth();

    try {
      const user = await loginWithEmail({
        email,
        password,
        remember: form.remember,
      });

      onLogin?.(user);
      setStatus('로그인 성공');
      window.location.href = '/';
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page" aria-label="로그인">
      <section className="login-showcase" aria-label="CineVerse 추천 포스터">
        <div className="login-showcase__copy">
          <p>CINEVERSE</p>
          <h1>오늘의 영화로 이어가기</h1>
        </div>

        <div className="login-poster-grid" aria-hidden="true">
          {promos.map((promo) => (
            <img
              className="login-poster-grid__image"
              src={promo.image}
              alt=""
              key={promo.id}
            />
          ))}
        </div>
      </section>

      <section className="login-form-panel" aria-label="로그인 입력">
        <div className="login-form-panel__header">
          <span>Welcome back</span>
          <h2>로그인</h2>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>이메일</span>
            <input
              autoComplete="email"
              name="email"
              onChange={updateField}
              placeholder="name@example.com"
              type="email"
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

            <a href="/password-reset">비밀번호 찾기</a>
          </div>

          {status ? (
            <p className="login-status" role="status">
              {status}
            </p>
          ) : null}

          <button className="login-submit" type="submit" disabled={busy}>
            {busy ? '로그인 중' : '로그인'}
          </button>
        </form>

        <p className="login-join">
          아직 계정이 없다면 <a href="/signup">회원가입</a>
        </p>
      </section>
    </main>
  );
}

export default LoginPage;
