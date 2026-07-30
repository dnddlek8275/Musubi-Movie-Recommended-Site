# CineVerse Frontend Docker 배포 메모

이 프론트는 Vite 기반 React 앱이다. 배포 이미지는 `npm run build`로 만든 `dist/`를 nginx로 서빙한다.

## Docker 이미지 빌드

백엔드 API 주소는 Vite 특성상 빌드 시점에 반영된다.

```bash
docker build \
  --build-arg VITE_API_BASE_URL=http://백엔드주소 \
  -t cineverse-frontend:local .
```

TMDB 이미지 베이스 URL을 바꿔야 하면 같이 넘긴다.

```bash
docker build \
  --build-arg VITE_API_BASE_URL=http://백엔드주소 \
  --build-arg VITE_TMDB_IMAGE_BASE_URL=https://image.tmdb.org/t/p/w500 \
  -t cineverse-frontend:local .
```

## 로컬 컨테이너 실행

```bash
docker run --rm -p 5173:80 cineverse-frontend:local
```

확인:

```bash
open http://localhost:5173
```

## Kubernetes 연결 메모

프론트 컨테이너는 내부에서 80 포트를 사용한다.

```yaml
ports:
  - containerPort: 80
```

SPA 라우팅을 위해 nginx의 `try_files $uri $uri/ /index.html;` 설정을 포함했다.

## 주의사항

- `.env`, `node_modules`, `dist`는 이미지/깃에 포함하지 않는다.
- `VITE_API_BASE_URL`은 런타임이 아니라 빌드 시점에 반영된다.
- API 서버 주소가 바뀌면 이미지를 다시 빌드해야 한다.
