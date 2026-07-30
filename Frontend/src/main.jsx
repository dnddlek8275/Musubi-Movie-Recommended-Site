import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

// crypto.randomUUID는 보안 컨텍스트(HTTPS/localhost)에서만 제공된다.
// HTTP LAN IP(예: http://192.168.x.x)로 접속하면 없어서 터지므로, 없을 때 폴리필한다.
if (typeof crypto !== 'undefined' && typeof crypto.randomUUID !== 'function') {
  try {
    crypto.randomUUID = function randomUUID() {
      // getRandomValues는 비보안 컨텍스트에서도 사용 가능하다.
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
      bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
      return (
        `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-` +
        `${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
      );
    };
  } catch (error) {
    console.warn('crypto.randomUUID 폴리필 적용 실패:', error);
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
