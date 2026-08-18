# Musubi

## 관리자 영화 API 화면

`/admin`에서 BE2 관리자 API 명세에 맞춘 콘텐츠 운영 화면을 사용할 수 있습니다.

- `GET /admin/check`: 관리자 권한 확인
- `GET /admin/tmdb-movies-search`: TMDB 영화 검색
- `POST /admin/tmdb-movies-register/{tmdb_id}`: TMDB 영화 등록
- `POST /admin/movie`: 영화 직접 등록
- `PATCH /admin/movie/{movie_id}`: 영화 부분 수정
- `DELETE /admin/movie/{movie_id}`: 영화 삭제
- `PATCH /admin/users/admin-role`: 관리자 권한 부여·회수

기존 로그인에서 저장한 Access Token과 refresh 흐름을 재사용합니다. 관리자
화면 진입 시 `/admin/check`로 실제 권한을 확인하며, 모든 관리자 응답은 HTTP
상태와 함께 `state === "success"`인지 검사합니다. 백엔드 구현은 monorepo의
`Backend/`에서 관리합니다.

선택형 TTS와 GPU 모니터링 도구는 핵심 프론트와 분리해 `Infra/add-ons/`에
보관합니다.

## 배포 연결

프로덕션 빌드는 백엔드 호출에 동일 출처 `/api`를 사용합니다. Docker
환경에서는 nginx가 이 요청을 `backend:8080`으로 전달하며, SPA 경로는
`index.html`로 폴백합니다.

루트에서 `Infra/compose.yaml`을 사용하면 PostgreSQL, DB 마이그레이션, Backend,
Frontend를 순서대로 실행할 수 있습니다.
