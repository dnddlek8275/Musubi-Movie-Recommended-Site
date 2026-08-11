import { useState } from 'react';

import { confirmPasswordReset, requestPasswordReset } from '../../api.js';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function PasswordResetForm({ onBack, token = '' }) {
  const isConfirmMode = Boolean(token);
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [status, setStatus] = useState('');
  const [sent, setSent] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus('');

    if (!isConfirmMode) {
      const normalizedEmail = email.trim().toLowerCase();
      if (!EMAIL_PATTERN.test(normalizedEmail)) {
        setStatus('가입한 이메일을 올바른 형식으로 입력해 주세요.');
        return;
      }

      setBusy(true);
      try {
        await requestPasswordReset(normalizedEmail);
        setSent(true);
        setStatus('이메일로 비밀번호 재설정 링크가 발송되었습니다.');
      } catch (error) {
        setSent(false);
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
    <div className="password-reset-inline">
      <header className="password-reset-inline__header">
        <small>ACCOUNT RECOVERY</small>
        <h2>{isConfirmMode ? '새 비밀번호 설정' : '비밀번호 찾기'}</h2>
        <p>
          {isConfirmMode
            ? '새로 사용할 비밀번호를 입력해 주세요.'
            : '가입한 이메일로 비밀번호 재설정 링크를 보내드릴게요.'}
        </p>
      </header>

      <form className="login-form password-reset-inline__form" onSubmit={handleSubmit}>
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
              disabled={busy}
              onChange={(event) => {
                setEmail(event.target.value);
                setSent(false);
                setStatus('');
              }}
              placeholder="이메일"
              type="email"
              value={email}
            />
          </label>
        )}

        {status ? <p className="login-status" role="status">{status}</p> : null}

        {!completed ? (
          <button className="login-submit" disabled={busy} type="submit">
            {busy
              ? isConfirmMode ? '처리 중' : '전송 중'
              : isConfirmMode
                ? '비밀번호 변경'
                : sent
                  ? '재전송'
                  : '전송'}
          </button>
        ) : null}
      </form>

      <button className="password-reset-inline__back" type="button" onClick={onBack}>
        로그인 화면으로 돌아가기
      </button>
    </div>
  );
}

export default PasswordResetForm;
