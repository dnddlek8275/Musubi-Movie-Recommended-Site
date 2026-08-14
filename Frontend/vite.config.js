import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // 백엔드 실제 주소(프록시 대상). .env의 VITE_BACKEND_TARGET로 덮어쓸 수 있다.
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8080';

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
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      rollupOptions: {
        output: {
          // React 런타임은 화면 코드와 분리해 다음 배포에서도 브라우저 캐시를 재사용한다.
          manualChunks(id) {
            return id.includes('/node_modules/react') ? 'react-vendor' : undefined;
          },
        },
      },
    },
    preview: {
      headers: {
        'Referrer-Policy': 'strict-origin-when-cross-origin',
      },
    },
  };
});
