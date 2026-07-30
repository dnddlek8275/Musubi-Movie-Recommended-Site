import { useEffect, useState } from 'react';

const STORAGE_KEY = 'cineverse-theme';

// index.html의 인라인 스크립트가 먼저 심어둔 data-theme을 그대로 이어받는다. (기본: dark)
function getInitialTheme() {
  if (typeof document !== 'undefined') {
    const attr = document.documentElement.getAttribute('data-theme');
    if (attr === 'light' || attr === 'dark') return attr;
  }

  try {
    return localStorage.getItem(STORAGE_KEY) || 'dark';
  } catch (error) {
    return 'dark';
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);

    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      // localStorage를 못 쓰는 환경(사생활 보호 모드 등)에서는 저장만 생략한다.
    }
  }, [theme]);

  const isLight = theme === 'light';

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setTheme(isLight ? 'dark' : 'light')}
      aria-label={isLight ? '다크 모드로 전환' : '라이트 모드로 전환'}
      title={isLight ? '다크 모드로 전환' : '라이트 모드로 전환'}
    >
      <span className="theme-toggle__icon" aria-hidden="true">
        {isLight ? '☀' : '☾'}
      </span>
    </button>
  );
}

export default ThemeToggle;
