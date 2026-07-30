import { useState } from 'react';

import { confirmPasswordReset, requestPasswordReset } from '../../api.js';
import data from '/src/imgData.json';

import './login.css';

function PasswordResetPage() {
  const token = new URLSearchParams(window.location.search).get('token') || '';
  const isConfirmMode = Boolean(token);
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [status, setStatus] = useState('');
  const [completed, setCompleted] = useState(false);
  const [busy, setBusy] = useState(false);
  const promos = data.hero.promos.slice(0, 4);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus('');

    if (!isConfirmMode) {
      const normalizedEmail = email.trim();
      if (!normalizedEmail || !normalizedEmail.includes('@')) {
        setStatus('가입한 이메일을 확인해 주세요.');
        return;
      }

      setBusy(true);
      try {
        await requestPasswordReset(normalizedEmail);
        setCompleted(true);
        setStatus('가입된 이메일이면 비밀번호 재설정 링크가 전송됩니다.');
      } catch (error) {
        setStatus(error.message);
      } finally {
        setBusy(false);
      }
      return;
    }

    if (newPassword.length < 8 || newPassword.length > 128) {
      setStatus('새 비밀번호는 8~128자로 입력해 주세요.');
      return;
    }

    if (newPassword !== passwordConfirm) {
      setStatus('새 비밀번호가 일치하지 않습니다.');
      return;
    }

    setBusy(true);
    try {
      await confirmPasswordReset(token, newPassword);
      setCompleted(true);
      setStatus('비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page" aria-label="비밀번호 재설정">
      <section className="login-showcase" aria-label="CineVerse 추천 포스터">
        <div className="login-showcase__copy">
          <p>CINEVERSE</p>
          <h1>다시 이어서 볼 준비하기</h1>
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

      <section className="login-form-panel" aria-label="비밀번호 재설정 입력">
        <div className="login-form-panel__header">
          <span>Account recovery</span>
          <h2>{isConfirmMode ? '새 비밀번호 설정' : '비밀번호 찾기'}</h2>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {isConfirmMode ? (
            <>
              <label className="login-field">
                <span>새 비밀번호</span>
                <input
                  autoComplete="new-password"
                  disabled={busy || completed}
                  maxLength={128}
                  minLength={8}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="8자 이상"
                  type="password"
                  value={newPassword}
                />
              </label>

              <label className="login-field">
                <span>새 비밀번호 확인</span>
                <input
                  autoComplete="new-password"
                  disabled={busy || completed}
                  maxLength={128}
                  minLength={8}
                  onChange={(event) => setPasswordConfirm(event.target.value)}
                  placeholder="비밀번호 재입력"
                  type="password"
                  value={passwordConfirm}
                />
              </label>
            </>
          ) : (
            <label className="login-field">
              <span>가입 이메일</span>
              <input
                autoComplete="email"
                disabled={busy || completed}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@example.com"
                type="email"
                value={email}
              />
            </label>
          )}

          {status ? (
            <p className="login-status" role="status">
              {status}
            </p>
          ) : null}

          {completed ? (
            <a className="login-submit login-submit--link" href="/login">
              로그인으로 돌아가기
            </a>
          ) : (
            <button className="login-submit" disabled={busy} type="submit">
              {busy
                ? '처리 중'
                : isConfirmMode
                  ? '비밀번호 변경'
                  : '재설정 링크 받기'}
            </button>
          )}
        </form>

        <p className="login-join">
          비밀번호가 기억나면 <a href="/login">로그인</a>
        </p>
      </section>
    </main>
  );
}

export default PasswordResetPage;
