// CineVerse 로고. "Cine" 글자색은 테마에 따라 바뀐다(다크: 흰색, 라이트: #2D3C5D).
// 색 전환은 .logo-ink { fill: var(--logo-ink) } 로 처리한다(headerFooter.css).
function Logo() {
  return (
    <svg
      className="site-logo__svg"
      viewBox="30 55 760 195"
      width="362"
      height="93"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="CineVerse"
    >
      <defs>
        <radialGradient id="logoSphereGrad" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#dde4ea" />
        </radialGradient>
        <linearGradient id="logoOrbitGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8fe3da" />
          <stop offset="100%" stopColor="#3f9f93" />
        </linearGradient>
        <linearGradient id="logoTriGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#37476d" />
          <stop offset="100%" stopColor="#1f2c47" />
        </linearGradient>
        <filter id="logoTriShadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#0f1a2e" floodOpacity="0.35" />
        </filter>
      </defs>

      <g transform="translate(150,150)">
        <g transform="rotate(-22)" opacity="0.55">
          <path
            d="M -120,0 A 120,48 0 0,0 120,0"
            fill="none"
            stroke="url(#logoOrbitGrad)"
            strokeWidth="5.5"
            strokeLinecap="round"
          />
          <circle cx="-101" cy="16" r="5" fill="#4fb8ac" />
        </g>

        <circle
          r="88"
          fill="url(#logoSphereGrad)"
          stroke="#c3ccd6"
          strokeWidth="1"
          strokeOpacity="0.6"
        />

        <path
          d="M -55,-58 A 82,82 0 0,1 40,-72"
          fill="none"
          stroke="#ffffff"
          strokeWidth="7"
          strokeLinecap="round"
          opacity="0.45"
        />

        <g filter="url(#logoTriShadow)">
          <path
            d="
              M -27,-45
              Q -19,-49 -12,-45
              L 47,-4
              Q 53,0 47,4
              L -12,45
              Q -19,49 -27,45
              Q -31,42 -31,36
              L -31,-36
              Q -31,-42 -27,-45
              Z"
            fill="url(#logoTriGrad)"
          />
        </g>

        <g transform="rotate(-22)">
          <path
            d="M -120,0 A 120,48 0 0,1 120,0"
            fill="none"
            stroke="url(#logoOrbitGrad)"
            strokeWidth="6.5"
            strokeLinecap="round"
          />
          <circle cx="90" cy="26" r="7.5" fill="#7fd8cf" />
          <circle cx="87.5" cy="23.5" r="2.4" fill="#ffffff" opacity="0.8" />
        </g>
      </g>

      <g fontFamily="Arial, 'Helvetica Neue', sans-serif" fontWeight="800">
        <text className="logo-ink" x="300" y="172" fontSize="90" letterSpacing="-1">
          Cine<tspan fill="#4fb8ac">Verse</tspan>
        </text>
      </g>
    </svg>
  );
}

export default Logo;