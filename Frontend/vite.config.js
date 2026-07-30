import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // 백엔드 실제 주소(프록시 대상). .env의 VITE_BACKEND_TARGET로 덮어쓸 수 있다.
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://192.168.45.8:8080';

  return {
    plugins: [react()],
    server: {
      // 기본은 명세의 허용 Origin과 동일한 127.0.0.1이며, 필요할 때만 환경변수로 변경한다.
      host: env.VITE_DEV_HOST || '127.0.0.1',
      port: 5173,
      headers: {
        'Referrer-Policy': 'strict-origin-when-cross-origin',
      },
      proxy: {
        // VITE_API_BASE_URL=/be를 선택한 개발 환경에서만 같은 오리진 프록시로 사용한다.
        '/be': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/be/, ''),
          // VITE_API_BASE_URL=/be로 프록시를 선택한 경우 refresh cookie도 /be/auth 요청에 전송되게 한다.
          cookiePathRewrite: {
            '/auth': '/be/auth',
          },
        },
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
    preview: {
      headers: {
        'Referrer-Policy': 'strict-origin-when-cross-origin',
      },
    },
  };
});
