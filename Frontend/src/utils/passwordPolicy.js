export const MIN_PASSWORD_LENGTH = 10;
export const MAX_PASSWORD_LENGTH = 128;

export function getPasswordChecks(password) {
  return {
    length: password.length >= MIN_PASSWORD_LENGTH && password.length <= MAX_PASSWORD_LENGTH,
    letter: /[A-Za-z]/.test(password),
    number: /\d/.test(password),
    special: /[^A-Za-z0-9\s]/.test(password),
    noSpace: !/\s/.test(password),
  };
}

export function getPasswordPolicyError(password) {
  const checks = getPasswordChecks(password);
  if (!checks.length) return `비밀번호는 ${MIN_PASSWORD_LENGTH}~${MAX_PASSWORD_LENGTH}자로 입력해 주세요.`;
  if (!checks.letter) return '비밀번호에 영문을 포함해 주세요.';
  if (!checks.number) return '비밀번호에 숫자를 포함해 주세요.';
  if (!checks.special) return '비밀번호에 특수문자를 포함해 주세요.';
  if (!checks.noSpace) return '비밀번호에는 공백을 사용할 수 없습니다.';
  return '';
}
