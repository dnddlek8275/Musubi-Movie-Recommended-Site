# CineVerse

## 관리자 영화 API 화면

`/admin`에서 BE2 관리자 API 명세에 맞춘 콘텐츠 운영 화면을 사용할 수 있습니다.

- `GET /admin/check`: 관리자 권한 확인
- `GET /admin/tmdb-movies-search`: TMDB 영화 검색
- `POST /admin/tmdb-movies-register/{tmdb_id}`: TMDB 영화 등록
- `POST /admin/movie`: 영화 직접 등록
- `PATCH /admin/movie/{movie_id}`: 영화 부분 수정
- `DELETE /admin/movie/{movie_id}`: 영화 삭제
- `PATCH /admin/users/admin-role`: 관리자 권한 부여·회수

기존 로그인에서 저장한 Access Token과 refresh 흐름을 재사용합니다. 관리자 화면 진입 시 `/admin/check`로 실제 권한을 확인하며, 모든 관리자 응답은 HTTP 상태와 함께 `state === "success"`인지 검사합니다. 이 저장소에는 BE2 백엔드 소스가 없으므로 위 엔드포인트의 서버 구현 및 관리자 역할 발급은 백엔드 저장소에서 제공되어야 합니다.
