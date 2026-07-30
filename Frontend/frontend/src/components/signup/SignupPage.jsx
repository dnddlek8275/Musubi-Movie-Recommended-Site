import { useState } from 'react';

import { registerWithEmail, requestEmailVerification } from '../../api.js';
import data from '/src/imgData.json';
import '../login/login.css';
import './signup.css';

const initialForm = {
  email: '',
  nickname: '',
  password: '',
  passwordConfirm: '',
  verificationCode: '',
};

function SignupPage() {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');

  const promos = data.hero.promos.slice(0, 4);

  const updateField = (event) => {
    const { name, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  };

  const handleVerificationRequest = async () => {
    const email = form.email.trim();

    if (!email || !email.includes('@')) {
      setStatus('인증번호를 받을 이메일을 확인해 주세요.');
      return;
    }

    setVerificationBusy(true);
    setStatus('');

    try {
      const result = await requestEmailVerification(email);
      const expiresIn = Number(result?.expires_in_seconds);
      setVerificationEmail(email);
      setStatus(
        Number.isFinite(expiresIn)
          ? `인증번호를 전송했습니다. ${Math.ceil(expiresIn / 60)}분 안에 입력해 주세요.`
          : '인증번호를 전송했습니다.'
      );
    } catch (error) {
      setStatus(error.message);
    } finally {
      setVerificationBusy(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const email = form.email.trim();
    const nickname = form.nickname.trim();
    const password = form.password;
    const passwordConfirm = form.passwordConfirm;
    const verificationCode = form.verificationCode.trim();

    if (!email || !nickname || !password || !passwordConfirm || !verificationCode) {
      setStatus('모든 항목을 입력해 주세요.');
      return;
    }

    if (email !== verificationEmail) {
      setStatus('현재 이메일로 인증번호를 먼저 받아 주세요.');
      return;
    }

    if (!/^\d{6}$/.test(verificationCode)) {
      setStatus('이메일로 받은 숫자 6자리 인증번호를 입력해 주세요.');
      return;
    }

    if (!email.includes('@')) {
      setStatus('이메일과 비밀번호를 다시 확인해 주세요.');
      return;
    }

    if (password !== passwordConfirm) {
      setStatus('비밀번호가 일치하지 않습니다.');
      return;
    }

    setBusy(true);
    setStatus('');

    try {
      await registerWithEmail({
        email,
        nickname,
        password,
        verificationCode,
      });

      setStatus('회원가입 성공. 로그인 페이지로 이동합니다.');
      window.setTimeout(() => {
        window.location.href = '/login';
      }, 700);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page signup-page" aria-label="회원가입">
      <section className="login-showcase" aria-label="CineVerse 추천 포스터">
        <div className="login-showcase__copy">
          <p>CINEVERSE</p>
          <h1>새로운 영화 취향을 시작하기</h1>
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

      <section className="login-form-panel" aria-label="회원가입 입력">
        <div className="login-form-panel__header">
          <span>Create account</span>
          <h2>회원가입</h2>
        </div>

        <form className="login-form signup-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>이메일</span>
            <span className="signup-email-row">
              <input
                autoComplete="email"
                disabled={busy || verificationBusy}
                name="email"
                onChange={updateField}
                placeholder="user1@example.com"
                type="email"
                value={form.email}
              />
              <button
                className="signup-verification-button"
                disabled={busy || verificationBusy}
                onClick={handleVerificationRequest}
                type="button"
              >
                {verificationBusy
                  ? '전송 중'
                  : verificationEmail === form.email.trim()
                    ? '재전송'
                    : '인증번호'}
              </button>
            </span>
          </label>

          <label className="login-field">
            <span>이메일 인증번호</span>
            <input
              autoComplete="one-time-code"
              disabled={busy}
              inputMode="numeric"
              maxLength={6}
              name="verificationCode"
              onChange={updateField}
              pattern="[0-9]{6}"
              placeholder="숫자 6자리"
              type="text"
              value={form.verificationCode}
            />
          </label>

          <label className="login-field">
            <span>닉네임</span>
            <input
              autoComplete="nickname"
              disabled={busy}
              name="nickname"
              onChange={updateField}
              placeholder="user1"
              type="text"
              value={form.nickname}
            />
          </label>

          <label className="login-field">
            <span>비밀번호</span>
            <input
              autoComplete="new-password"
              disabled={busy}
              name="password"
              onChange={updateField}
              placeholder="비밀번호"
              type="password"
              value={form.password}
            />
          </label>

          <label className="login-field">
            <span>비밀번호 확인</span>
            <input
              autoComplete="new-password"
              disabled={busy}
              name="passwordConfirm"
              onChange={updateField}
              placeholder="비밀번호 재입력"
              type="password"
              value={form.passwordConfirm}
            />
          </label>

          {status ? (
            <p className="login-status" role="status">
              {status}
            </p>
          ) : null}

          <button className="login-submit" type="submit" disabled={busy}>
            {busy ? '가입 중' : '회원가입'}
          </button>
        </form>

        <p className="login-join">
          이미 계정이 있다면 <a href="/login">로그인</a>
        </p>
      </section>
    </main>
  );
}

export default SignupPage;
