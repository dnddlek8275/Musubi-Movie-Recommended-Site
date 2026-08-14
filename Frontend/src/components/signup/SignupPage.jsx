import { useEffect, useState } from 'react';

import {
  checkNicknameAvailability,
  confirmEmailVerification,
  loginWithEmail,
  registerWithEmail,
  requestEmailVerification,
} from '../../api.js';
import IntroPage from '../intro/IntroPage.jsx';
import { getPasswordChecks } from '../../utils/passwordPolicy.js';
import '../login/login.css';
import './signup.css';

const initialForm = {
  email: '',
  nickname: '',
  password: '',
  passwordConfirm: '',
  verificationCode: '',
};

const EMAIL_DOMAINS = ['naver.com', 'gmail.com', 'daum.net', 'kakao.com', 'outlook.com'];
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function SignupPage() {
  const [isArrivingFromLogin] = useState(() => {
    const shouldAnimate = window.sessionStorage.getItem('musubi-signup-arrive') === '1';
    return shouldAnimate;
  });
  const [leavingToOnboarding, setLeavingToOnboarding] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');
  const [verificationExpiresAt, setVerificationExpiresAt] = useState(0);
  const [verificationSecondsLeft, setVerificationSecondsLeft] = useState(0);
  const [verificationConfirmed, setVerificationConfirmed] = useState(false);
  const [confirmationBusy, setConfirmationBusy] = useState(false);
  const [emailMessage, setEmailMessage] = useState({ message: '', state: 'idle' });
  const [verificationMessage, setVerificationMessage] = useState({ message: '', state: 'idle' });
  const [emailTouched, setEmailTouched] = useState(false);
  const [nicknameBusy, setNicknameBusy] = useState(false);
  const [nicknameCheck, setNicknameCheck] = useState({
    checkedNickname: '',
    message: '',
    state: 'idle',
  });
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [passwordConfirmVisible, setPasswordConfirmVisible] = useState(false);

  const normalizedEmail = form.email.trim().toLowerCase();
  const emailIsValid = EMAIL_PATTERN.test(normalizedEmail);
  const verificationWasSent = Boolean(
    verificationEmail && verificationEmail === normalizedEmail
  );
  const normalizedNickname = form.nickname.trim().toLocaleLowerCase('ko-KR');
  const nicknameWasChecked =
    nicknameCheck.state === 'available' &&
    nicknameCheck.checkedNickname === normalizedNickname;
  const passwordChecks = getPasswordChecks(form.password);
  const passwordIsValid = Object.values(passwordChecks).every(Boolean);

  useEffect(() => {
    window.sessionStorage.removeItem('musubi-signup-arrive');
    const restoreSignupPage = () => setLeavingToOnboarding(false);
    window.addEventListener('pageshow', restoreSignupPage);
    return () => window.removeEventListener('pageshow', restoreSignupPage);
  }, []);

  useEffect(() => {
    if (!verificationExpiresAt || verificationConfirmed) {
      setVerificationSecondsLeft(0);
      return undefined;
    }

    const updateCountdown = () => {
      setVerificationSecondsLeft(
        Math.max(0, Math.ceil((verificationExpiresAt - Date.now()) / 1000))
      );
    };

    updateCountdown();
    const timer = window.setInterval(updateCountdown, 1000);
    return () => window.clearInterval(timer);
  }, [verificationConfirmed, verificationExpiresAt]);

  const countdownText = `${String(Math.floor(verificationSecondsLeft / 60)).padStart(2, '0')}:${String(
    verificationSecondsLeft % 60
  ).padStart(2, '0')}`;

  const updateField = (event) => {
    const { name, value } = event.target;
    const emailChangedAfterVerification =
      name === 'email' && value.trim().toLowerCase() !== verificationEmail;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
      ...(emailChangedAfterVerification ? { verificationCode: '' } : {}),
    }));

    if (emailChangedAfterVerification) {
      setVerificationEmail('');
      setVerificationExpiresAt(0);
      setVerificationConfirmed(false);
      setEmailMessage({ message: '', state: 'idle' });
      setVerificationMessage({ message: '', state: 'idle' });
    }
    if (name === 'verificationCode') {
      setVerificationConfirmed(false);
      setVerificationMessage({ message: '', state: 'idle' });
    }
    if (name === 'nickname') {
      setNicknameCheck({ checkedNickname: '', message: '', state: 'idle' });
    }
  };

  const selectEmailDomain = (domain) => {
    const localPart = form.email.split('@')[0].trim();

    if (!localPart) {
      setEmailTouched(true);
      setStatus('@ 앞의 이메일 아이디를 먼저 입력해 주세요.');
      return;
    }

    setForm((currentForm) => ({
      ...currentForm,
      email: `${localPart}@${domain}`,
      verificationCode: '',
    }));
    setVerificationEmail('');
    setVerificationExpiresAt(0);
    setVerificationConfirmed(false);
    setEmailMessage({ message: '', state: 'idle' });
    setVerificationMessage({ message: '', state: 'idle' });
    setEmailTouched(true);
    setStatus('');
  };

  const handleVerificationRequest = async () => {
    const email = normalizedEmail;
    setEmailTouched(true);

    if (!emailIsValid) {
      setStatus('올바른 형식의 이메일을 입력해 주세요.');
      return;
    }

    setVerificationBusy(true);
    setStatus('');

    try {
      const result = await requestEmailVerification(email);
      const expiresIn = Number(result?.expires_in_seconds) || 300;
      setVerificationEmail(email);
      setVerificationExpiresAt(Date.now() + expiresIn * 1000);
      setVerificationConfirmed(false);
      setForm((currentForm) => ({ ...currentForm, email }));
      setEmailMessage({ message: '', state: 'idle' });
      setVerificationMessage({ message: '', state: 'idle' });
      setStatus('');
    } catch (error) {
      setEmailMessage({ message: error.message, state: 'error' });
      setStatus('');
    } finally {
      setVerificationBusy(false);
    }
  };

  const handleVerificationConfirm = async () => {
    const code = form.verificationCode.trim();

    if (verificationSecondsLeft <= 0) {
      setVerificationMessage({ message: '인증 시간이 만료되었습니다. 재전송해 주세요.', state: 'error' });
      return;
    }
    if (!/^\d{6}$/.test(code)) {
      setVerificationMessage({ message: '숫자 6자리 인증번호를 입력해 주세요.', state: 'error' });
      return;
    }

    setConfirmationBusy(true);
    setVerificationMessage({ message: '', state: 'idle' });
    try {
      await confirmEmailVerification(normalizedEmail, code);
      setVerificationConfirmed(true);
      setVerificationMessage({ message: '이메일 인증이 완료되었습니다.', state: 'success' });
      setStatus('');
    } catch (error) {
      setVerificationConfirmed(false);
      setVerificationMessage({ message: error.message, state: 'error' });
    } finally {
      setConfirmationBusy(false);
    }
  };

  const handleNicknameCheck = async () => {
    const nickname = form.nickname.trim();

    if (nickname.length < 2) {
      setNicknameCheck({
        checkedNickname: '',
        message: '닉네임은 2자 이상 입력해 주세요.',
        state: 'unavailable',
      });
      return;
    }

    setNicknameBusy(true);
    setNicknameCheck({ checkedNickname: '', message: '', state: 'checking' });

    try {
      const result = await checkNicknameAvailability(nickname);
      setNicknameCheck({
        checkedNickname: normalizedNickname,
        message: result.message,
        state: result.available ? 'available' : 'unavailable',
      });
    } catch (error) {
      setNicknameCheck({
        checkedNickname: '',
        message: error.message,
        state: 'unavailable',
      });
    } finally {
      setNicknameBusy(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const email = normalizedEmail;
    const nickname = form.nickname.trim();
    const password = form.password;
    const passwordConfirm = form.passwordConfirm;
    const verificationCode = form.verificationCode.trim();

    if (!emailIsValid) {
      setEmailTouched(true);
      setStatus('올바른 형식의 이메일을 입력해 주세요.');
      return;
    }
    if (!verificationWasSent) {
      setStatus('현재 이메일로 인증번호를 먼저 받아 주세요.');
      return;
    }
    if (!/^\d{6}$/.test(verificationCode)) {
      setStatus('이메일로 받은 숫자 6자리 인증번호를 입력해 주세요.');
      return;
    }
    if (!verificationConfirmed) {
      setStatus('이메일 인증번호 확인을 완료해 주세요.');
      return;
    }
    if (!nicknameWasChecked) {
      setStatus('닉네임 중복 확인을 완료해 주세요.');
      return;
    }
    if (!passwordIsValid) {
      setStatus('비밀번호 생성 조건을 모두 충족해 주세요.');
      return;
    }
    if (password !== passwordConfirm) {
      setStatus('비밀번호가 일치하지 않습니다.');
      return;
    }

    setBusy(true);
    setStatus('');

    try {
      await registerWithEmail({ email, nickname, password, verificationCode });
      try {
        await loginWithEmail({ email, password, remember: false });
        setStatus('회원가입 성공. 취향 설정으로 이동합니다.');
        setLeavingToOnboarding(true);
        window.sessionStorage.setItem('musubi-onboarding-arrive', 'signup');
        window.setTimeout(() => {
          window.location.replace('/onboarding');
        }, 680);
      } catch (loginError) {
        setStatus('회원가입은 완료되었습니다. 로그인 화면에서 로그인해 주세요.');
        window.setTimeout(() => {
          window.location.href = '/login';
        }, 1100);
      }
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const signupForm = (
    <>
      <form className="login-form signup-form" onSubmit={handleSubmit}>
        <label className="login-field">
          <span>이메일</span>
          <span className="signup-email-row">
            <input
              autoComplete="email"
              disabled={busy || verificationBusy || confirmationBusy}
              name="email"
              onBlur={() => setEmailTouched(true)}
              onChange={updateField}
              placeholder="이메일"
              type="email"
              value={form.email}
            />
            <button
              className="signup-verification-button"
              disabled={busy || verificationBusy}
              onClick={handleVerificationRequest}
              type="button"
            >
              {verificationBusy ? '전송 중' : verificationWasSent ? '재전송' : '전송'}
            </button>
          </span>
          <span className="signup-domain-picker" aria-label="이메일 도메인 빠른 선택">
            <small>빠른 선택</small>
            {EMAIL_DOMAINS.map((domain) => (
              <button type="button" key={domain} onClick={() => selectEmailDomain(domain)}>
                @{domain}
              </button>
            ))}
          </span>
          {emailTouched && form.email && !emailIsValid ? (
            <small className="signup-field-message is-error" role="alert">
              올바른 이메일 형식이 아닙니다.
            </small>
          ) : null}
          {emailMessage.message ? (
            <small className={`signup-field-message is-${emailMessage.state}`} role="status">
              {emailMessage.message}
            </small>
          ) : null}
        </label>

        {verificationWasSent ? (
          <label className="login-field signup-verification-field">
            <span>이메일 인증번호</span>
            <span className="signup-code-row">
              <span className="signup-code-input">
                <input
                  autoComplete="one-time-code"
                  disabled={busy || confirmationBusy || verificationConfirmed}
                  inputMode="numeric"
                  maxLength={6}
                  name="verificationCode"
                  onChange={updateField}
                  pattern="[0-9]{6}"
                  placeholder="인증번호 6자리"
                  type="text"
                  value={form.verificationCode}
                />
                {!verificationConfirmed ? (
                  <time className={verificationSecondsLeft === 0 ? 'is-expired' : ''}>{countdownText}</time>
                ) : null}
              </span>
              <button
                className="signup-verification-button"
                disabled={busy || confirmationBusy || verificationConfirmed || verificationSecondsLeft === 0}
                onClick={handleVerificationConfirm}
                type="button"
              >
                {confirmationBusy ? '확인 중' : verificationConfirmed ? '인증완료' : '확인'}
              </button>
            </span>
            {verificationMessage.message ? (
              <small className={`signup-field-message is-${verificationMessage.state}`} role="status">
                {verificationMessage.message}
              </small>
            ) : null}
          </label>
        ) : null}

        <label className="login-field">
          <span>닉네임</span>
          <span className="signup-nickname-row">
            <input
              autoComplete="nickname"
              disabled={busy || nicknameBusy}
              maxLength={50}
              name="nickname"
              onChange={updateField}
              placeholder="닉네임"
              type="text"
              value={form.nickname}
            />
            <button
              className="signup-verification-button"
              disabled={busy || nicknameBusy}
              onClick={handleNicknameCheck}
              type="button"
            >
              {nicknameBusy ? '확인 중' : '중복확인'}
            </button>
          </span>
          {nicknameCheck.message ? (
            <small
              className={`signup-field-message${nicknameCheck.state === 'available' ? ' is-success' : ' is-error'}`}
              role="status"
            >
              {nicknameCheck.message}
            </small>
          ) : null}
        </label>

        <label className="login-field">
          <span>비밀번호</span>
          <span className="signup-password-input">
            <input
              autoComplete="new-password"
              disabled={busy}
              name="password"
              onChange={updateField}
              placeholder="비밀번호"
              type={passwordVisible ? 'text' : 'password'}
              value={form.password}
            />
            <button type="button" onClick={() => setPasswordVisible((visible) => !visible)}>
              {passwordVisible ? '숨기기' : '보기'}
            </button>
          </span>
          <span className="signup-password-rules" aria-label="비밀번호 생성 조건">
            <small className={passwordChecks.length ? 'is-valid' : ''}>10자 이상</small>
            <small className={passwordChecks.letter ? 'is-valid' : ''}>영문</small>
            <small className={passwordChecks.number ? 'is-valid' : ''}>숫자</small>
            <small className={passwordChecks.special ? 'is-valid' : ''}>특수문자</small>
            <small className={passwordChecks.noSpace ? 'is-valid' : ''}>공백 없음</small>
          </span>
        </label>

        <label className="login-field">
          <span>비밀번호 확인</span>
          <span className="signup-password-input">
            <input
              autoComplete="new-password"
              disabled={busy}
              name="passwordConfirm"
              onChange={updateField}
              placeholder="비밀번호 재입력"
              type={passwordConfirmVisible ? 'text' : 'password'}
              value={form.passwordConfirm}
            />
            <button type="button" onClick={() => setPasswordConfirmVisible((visible) => !visible)}>
              {passwordConfirmVisible ? '숨기기' : '보기'}
            </button>
          </span>
          {form.passwordConfirm && form.password !== form.passwordConfirm ? (
            <small className="signup-field-message is-error">비밀번호가 일치하지 않습니다.</small>
          ) : null}
        </label>

        {status ? <p className="login-status" role="status">{status}</p> : null}

        <button className="login-submit" type="submit" disabled={busy}>
          {busy ? '가입 중' : '회원가입'}
        </button>
      </form>

      <p className="login-join">
        <a href="/login">로그인 화면으로 돌아가기</a>
      </p>
    </>
  );

  return (
    <IntroPage
      entryClassName="intro-entry__login--signup"
      entryContent={signupForm}
      initialScene={4}
      pageClassName={`intro--signup${isArrivingFromLogin ? ' is-arriving-from-login' : ''}${leavingToOnboarding ? ' is-leaving-for-onboarding' : ''}`}
    />
  );
}

export default SignupPage;
