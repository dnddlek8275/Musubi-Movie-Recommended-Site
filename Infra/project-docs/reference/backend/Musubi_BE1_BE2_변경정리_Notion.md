# Musubi BE1/BE2 백엔드 변경 정리

작성 기준: `Musubi_백엔드구조.docx` 원문 + 현재 BE2 코드 + 회의 결정 사항

작성일: 2026-06-24

## 1. 현재 확정된 큰 방향

- 프론트는 기본적으로 BE1에 요청한다.
- BE1은 사용자 인증, JWT 발급/검증, 프론트 응답 조립, AI/캐릭터/채팅 흐름을 담당한다.
- BE2는 PostgreSQL 기반 DB 로직, 관리자 API, 영화 반응 기록, 인기 랭킹, 취향 점수 계산을 담당한다.
- BE1과 BE2는 `Frontend -> BE1 -> BE2` 흐름으로 연동한다.
- BE2에 Redis는 사용하지 않는다.
- Refresh Token은 Redis가 아니라 PostgreSQL에 저장한다.
- Refresh Token 저장/조회/폐기처럼 DB 접근이 필요한 인증 보조 로직은 BE2가 API로 제공하고, 토큰 발급/최종 검증/응답은 BE1이 담당한다.
- 찜, 싫어요, 시청 완료, 관심 없음 기능은 현재 범위에서 제외한다.
- 찜 기능은 좋아요와 합쳐서 본다.
- 영화 데이터는 DB에 저장해서 사용한다.
- 외부 영화 API는 데이터 수집/업데이트 용도로 사용할 수 있으나, 현재 BE2 핵심 로직은 DB 저장 데이터를 기준으로 동작한다.

## 2. 원본 문서 대비 주요 변경 사항

| 항목 | 원본 문서 | 현재 결정/구현 |
| --- | --- | --- |
| Redis | JWT 블랙리스트, 랭킹, 캐시, 세션에 사용 | 사용하지 않음 |
| JWT | Access/Refresh + Redis 블랙리스트 | JWT 발급/Access Token 검증은 BE1 담당으로 확정. Refresh Token은 PostgreSQL에 저장하고, DB 저장/조회/폐기는 BE2 API가 담당 예정 |
| 프론트 요청 흐름 | 일부 API가 BE2 직접 요청처럼 보임 | 현재 방향은 `Frontend -> BE1 -> BE2` |
| 찜 | 별도 bookmark 기능 있음 | 제외. 좋아요로 통합 |
| 싫어요 | `dislike` 존재 | 제외 |
| 시청 완료 | 원본에는 명시 없음 | 추천 사이트 특성상 구현하지 않음 |
| 관심 없음 | 원본에는 명시 없음 | 구현하지 않음 |
| 랭킹 집계 | Redis Sorted Set 기반 | PostgreSQL `movie_stats` 누적 집계 |
| 검색 점수 | 원본 기준 없음 | 검색 결과 클릭 후 조회 시 `search_click +1` |
| 조회 점수 | 원본 기준 없음 | 일반 조회 `view +1` |
| 좋아요 점수 | 원본 기준 없음 | 좋아요 `like +2` |
| 취향 학습 | `user_preferences`에 행동 저장 | 영화 반응 로그 + 캐릭터 대화/선택 로그를 기반으로 `user_preference_scores`에 누적하는 방향 |
| 캐릭터 기반 취향 학습 | 원본에는 캐릭터 기능과 개인화 추천/취향 학습 로직이 분리되어 있음 | 캐릭터 대화/선택 데이터를 취향 학습에 반영하기로 결정. 세부 점수와 DB/API는 추가 설계 필요 |
| 관리자 API | 영화 등록/수정/삭제, 캐릭터 등록/수정, 통계 | 영화/캐릭터 목록/상세/등록/수정/삭제 + 통계 구현 |
| `admin_audit_logs` | 원본에 없음 | 테이블은 유지. 관리자 이력 저장 로직은 아직 연결하지 않음 |

## 3. 기술 스택 현황

| 분류 | 현재 기준 |
| --- | --- |
| API 프레임워크 | FastAPI `0.137.0` |
| 언어/런타임 | Python `>=3.14` |
| DB | PostgreSQL `17.10` |
| ORM | SQLAlchemy |
| 마이그레이션 | Alembic |
| DB Driver | psycopg |
| 설정 | pydantic-settings + `.env` |
| 패키지 설치 | `python -m pip install -e .` |
| Redis | 사용하지 않음 |
| 배포/CI/CD | 아직 구현 전 |

## 4. BE1/BE2 역할 정리

### BE1 담당

- 프론트 요청 수신
- 회원가입/로그인/JWT 발급/Access Token 검증
- Refresh Token 생성 및 재발급 응답 처리
- 프론트에 내려줄 응답 조립
- 영화 추천 API 연동
- AI 서버 호출
- 캐릭터 대화 API 연동
- WebSocket 그룹 채팅
- 채팅 관련 API
- 영화 상세 조회 화면 흐름 처리
- BE2 내부 API 호출 시 `user_id`, `movie_id`, `source` 전달

### BE2 담당

- PostgreSQL 스키마 설계 및 Alembic 마이그레이션
- 영화/캐릭터 관리자 CRUD
- 관리자 통계 조회
- 영화 조회/검색 후 조회/좋아요 기록 저장
- 실시간 인기 랭킹 집계
- 사용자 영화 취향 점수 누적
- 사용자 캐릭터 기반 취향 점수 누적 예정
- 사용자 취향 점수 조회
- 영화 데이터 저장 구조 관리
- Refresh Token 저장/조회/폐기용 DB API 제공 예정

## 5. BE1 -> BE2 연동 흐름

### 5.1 인증 흐름

Access Token과 Refresh Token의 최종 담당은 BE1이다. 다만 Refresh Token은 DB 저장/조회/폐기가 필요하므로, 해당 DB 처리는 BE2가 내부 API로 제공한다.

#### 로그인

```text
Frontend -> BE1: 로그인 요청
BE1 -> BE2: 사용자 계정 조회/검증에 필요한 DB 요청
BE1: Access Token + Refresh Token 생성
BE1 -> BE2: Refresh Token 저장 요청
BE1 -> Frontend: Access Token + Refresh Token 응답
```

#### 일반 API 요청

```text
Frontend -> BE1: Authorization: Bearer {access_token}
BE1: Access Token 서명/만료 검증 후 user_id 추출
BE1 -> BE2: user_id 포함 내부 API 호출
BE2: user_id 기준으로 DB 로직 처리
BE2 -> BE1 -> Frontend: 응답 반환
```

#### Access Token 재발급

```text
Frontend -> BE1: Refresh Token으로 재발급 요청
BE1 -> BE2: Refresh Token 유효성 확인 요청
BE2 -> DB: Refresh Token 존재 여부/만료/폐기 여부 조회
BE2 -> BE1: 유효한 경우 user_id 반환
BE1: 새 Access Token 발급
BE1 -> Frontend: 새 Access Token 응답
```

#### 로그아웃

```text
Frontend -> BE1: 로그아웃 요청
BE1 -> BE2: Refresh Token 폐기 요청
BE2 -> DB: Refresh Token 삭제 또는 revoked 처리
BE1 -> Frontend: 로그아웃 완료 응답
```

정리:

| 작업 | 담당 |
| --- | --- |
| Access Token 생성 | BE1 |
| Access Token 서명/만료 검증 | BE1 |
| Refresh Token 생성 | BE1 |
| Refresh Token DB 저장 | BE2 |
| Refresh Token DB 조회/유효성 확인 | BE2 |
| Refresh Token 폐기 | BE2 |
| 새 Access Token 발급 | BE1 |

현재 BE2 코드에는 Refresh Token 저장/조회/폐기 API가 아직 구현되어 있지 않다. 이 부분은 인증 연동 단계에서 추가해야 한다.

### 5.2 영화 상세 조회

1. 프론트가 BE1에 영화 상세 조회 요청
2. BE1이 JWT를 검증하고 `user_id` 추출
3. BE1이 영화 상세 데이터를 응답하기 전 또는 후에 BE2 호출
4. BE2 호출 예시

```http
POST /movies/{movie_id}/view
```

```json
{
  "user_id": 1,
  "source": "direct"
}
```

5. BE2는 `view` 행동을 저장하고 랭킹/취향 점수를 갱신

### 5.3 검색 결과 클릭 후 상세 조회

1. 프론트가 BE1에 검색 요청
2. 프론트가 검색 결과 중 영화를 클릭
3. BE1이 BE2에 조회 기록 저장 요청
4. BE2 호출 예시

```http
POST /movies/{movie_id}/view
```

```json
{
  "user_id": 1,
  "source": "search"
}
```

5. BE2는 `source="search"`를 `search_click`으로 변환해서 저장
6. 랭킹 점수는 `+1`, 취향 점수는 `+0.8`

### 5.4 좋아요

1. 프론트가 BE1에 좋아요 요청
2. BE1이 JWT를 검증하고 `user_id` 추출
3. BE1이 BE2에 좋아요 기록 저장 요청

```http
POST /movies/{movie_id}/like
```

```json
{
  "user_id": 1,
  "source": "direct"
}
```

4. BE2는 `like` 행동을 저장하고 랭킹/취향 점수를 갱신

## 6. 공통 API 응답 포맷

현재 BE2는 팀 회의에서 정한 공통 응답 포맷을 사용한다.

### 성공 응답

```json
{
  "state": "success",
  "data": {},
  "message": "요청 처리 성공"
}
```

### 에러 응답

```json
{
  "state": "error",
  "message": "요청 처리 실패",
  "error": "error detail"
}
```

## 7. 팀 개발 규칙

| 항목 | 현재 규칙 |
| --- | --- |
| 라우터 prefix | `/기능명` |
| Pydantic 스키마 네이밍 | `CreateMovie`, `UpdateMovie`, `ReadMovie` 형식 |
| 스키마 파일 구조 | `schemas/admin.py`, `schemas/movie.py`처럼 기능별 분리 |
| DB 세션 dependency | `get_db` |
| DB 세션 방식 | 동기 SQLAlchemy `Session` |
| Endpoint 함수 | 일반 `def` 사용 |

## 8. BE2 현재 API 목록

### 관리자 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/admin/stats` | 관리자 통계 조회 |
| GET | `/admin/movies` | 영화 목록 조회 |
| GET | `/admin/movies/{movie_id}` | 영화 상세 조회 |
| POST | `/admin/movies` | 영화 등록 |
| PUT | `/admin/movies/{movie_id}` | 영화 수정 |
| DELETE | `/admin/movies/{movie_id}` | 영화 삭제 |
| GET | `/admin/characters` | 캐릭터 목록 조회 |
| GET | `/admin/characters/{character_id}` | 캐릭터 상세 조회 |
| POST | `/admin/characters` | 캐릭터 등록 |
| PUT | `/admin/characters/{character_id}` | 캐릭터 수정 |
| DELETE | `/admin/characters/{character_id}` | 캐릭터 삭제 |

### 영화 반응/랭킹 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/movies/ranking` | 영화 인기 랭킹 조회 |
| POST | `/movies/{movie_id}/view` | 영화 조회 또는 검색 후 조회 기록 |
| POST | `/movies/{movie_id}/like` | 영화 좋아요 기록 |

### 사용자 취향 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/users/{user_id}/preferences` | 사용자 취향 점수 조회 |

지원 쿼리:

| Query | 설명 |
| --- | --- |
| `preference_type` | `genre`, `actor`, `director`, `keyword`, `language` 중 하나 |
| `limit` | 조회 개수. 기본값 20, 최대 100 |

## 9. BE2 현재 DB 테이블

| 테이블 | 목적 |
| --- | --- |
| `users` | 사용자 기본 정보 저장 |
| `movies` | 영화 기본 정보 및 외부 동기화 정보 저장 |
| `characters` | 캐릭터 프로필/프롬프트 저장 |
| `chat_rooms` | 채팅방 정보 저장 |
| `chat_messages` | 채팅 메시지 저장 |
| `user_movie_interactions` | 사용자 영화 행동 로그 저장 |
| `user_preference_scores` | 사용자별 취향 점수 누적 저장 |
| `movie_stats` | 영화별 랭킹용 누적 통계 저장 |
| `admin_audit_logs` | 관리자 작업 이력 저장용 테이블. 현재 로직 미연결 |

## 10. 원본 DB 스키마 대비 변경된 테이블

### 10.1 `movies`

추가/변경:

- `tmdb_id`는 현재 선택값으로 변경됨
- `keywords` 추가
- `last_synced_at` 추가
- `updated_at` 추가

변경 이유:

- TMDB에 없는 자체 입력 영화도 저장 가능해야 함
- 키워드는 취향 학습 축으로 사용됨
- 외부 API 수집/업데이트 시 마지막 동기화 시각이 필요함

### 10.2 `characters`

원본:

- `movie` 문자열 컬럼

현재:

- `movie_id` 추가
- `movie_title` 사용

변경 이유:

- 영화 테이블과 연결할 수 있게 하기 위함
- 영화가 삭제되어도 캐릭터 설정은 남길 수 있도록 `movie_id`는 `SET NULL` 처리

### 10.3 `user_preferences` 대체

원본:

- `user_preferences`
- `action_type`: `like / dislike / bookmark / click`

현재:

- `user_movie_interactions`
- `user_preference_scores`
- `movie_stats`

변경 이유:

- 행동 로그, 개인 취향 점수, 인기 랭킹 통계를 분리하기 위함
- 제외된 기능인 `dislike`, `bookmark`를 저장하지 않기 위함

## 11. 행동 점수 기준

### 랭킹 점수

| 행동 | 저장 action_type | 점수 |
| --- | --- | ---: |
| 일반 조회 | `view` | 1 |
| 검색 후 조회 | `search_click` | 1 |
| 좋아요 | `like` | 2 |

### 영화 기반 취향 점수

| 행동 | 점수 |
| --- | ---: |
| 일반 조회 | 0.5 |
| 검색 후 조회 | 0.8 |
| 좋아요 | 2.0 |

취향 점수 반영 대상:

- 장르
- 배우
- 감독
- 키워드
- 언어

### 캐릭터 기반 취향 점수

캐릭터 기반 취향 학습도 진행하기로 결정했다. 다만 현재 BE2 코드에는 아직 캐릭터 기반 취향 점수 누적 로직이 없다.

추가 설계가 필요한 항목:

- 캐릭터 대화 시작을 점수로 볼지
- 캐릭터 대화 메시지 수를 점수로 볼지
- 캐릭터 좋아요/선택 같은 별도 행동을 둘지
- 캐릭터의 원작 영화, 배우, 장르, 키워드를 사용자 취향에 어떻게 연결할지
- 캐릭터 기반 점수를 영화 기반 점수와 같은 `user_preference_scores`에 누적할지, 별도 테이블로 분리할지

현재 추천 방향:

- 캐릭터와 대화하거나 캐릭터를 선택하면 해당 캐릭터의 `movie_id`, `movie_title`, `actor` 정보를 기준으로 취향 점수에 반영한다.
- 캐릭터가 영화와 연결되어 있으면 연결된 영화의 장르/감독/배우/키워드/언어도 함께 취향 점수에 반영할 수 있다.
- 세부 점수는 영화 기반 점수보다 낮게 시작하고, 팀 회의 후 확정한다.

## 12. `source` 값 기준

BE2의 영화 반응 기록은 `source` 값으로 사용자가 어떤 흐름에서 영화를 눌렀는지 구분한다.

| source | 의미 |
| --- | --- |
| `direct` | 일반 상세 조회 |
| `search` | 검색 결과 클릭 후 상세 조회 |
| `recommend` | 추천 결과에서 상세 조회 |
| `ranking` | 랭킹 목록에서 상세 조회 |
| `admin` | 관리자 흐름 |
| `unknown` | 출처를 알 수 없음 |

현재 BE2 로직에서는 `source="search"`일 때만 `action_type="search_click"`으로 저장하고, 그 외 조회는 `action_type="view"`로 저장한다.

## 13. 구현 완료된 BE2 범위

- FastAPI 프로젝트 구조 구성
- PostgreSQL 연결 설정
- Alembic 마이그레이션 구성
- 초기 테이블 생성 마이그레이션 작성
- 공통 성공/에러 응답 포맷 적용
- 관리자 영화 CRUD
- 관리자 캐릭터 CRUD
- 관리자 통계 조회
- 영화 조회 기록 저장
- 검색 후 조회 기록 저장
- 좋아요 기록 저장
- 영화 인기 랭킹 조회
- 사용자 영화 기반 취향 점수 누적
- 사용자 취향 점수 조회
- 주요 코드 주석 정리

## 14. 아직 보류/미구현

| 항목 | 상태 |
| --- | --- |
| JWT 최종 연동 | BE1 담당으로 확정. BE2 연동 코드는 아직 추가 전 |
| Refresh Token DB API | BE2 담당 예정. 저장/조회/폐기 API 아직 미구현 |
| BE2 관리자 권한 검증 | JWT/BE1 연동 방식 확정 후 추가 |
| Redis | 사용하지 않기로 결정 |
| Milvus/RAG 연동 | 현재 BE2 범위에서는 구현 전 |
| AI 서버 연동 | BE1 담당으로 보임. 현재 BE2 구현 범위 아님 |
| 캐릭터 대화 로직 | BE1/AI 흐름에서 별도 진행 예정 |
| 캐릭터 기반 취향 학습 | 진행하기로 결정. 세부 점수/테이블/API 아직 미구현 |
| 관리자 작업 이력 저장 | `admin_audit_logs` 테이블만 있음 |
| 카카오 클라우드 배포 | 미구현 |
| CI/CD | 미구현 |

## 15. BE1/BE2 회의 필요 안건

### 15.1 BE1이 BE2에 넘길 사용자 식별값

현재 BE2는 요청 body의 `user_id`를 사용한다.

현재 결정:

- 프론트는 JWT를 BE1에만 보낸다.
- BE1이 Access Token을 검증하고 `user_id`를 추출한다.
- BE1이 BE2 내부 API 호출 시 `user_id`를 전달한다.
- BE2는 JWT를 직접 검증하지 않는다.

추가로 정해야 할 것:

- BE1이 BE2에 `user_id`를 body로 넘길지, 내부 헤더로 넘길지 결정 필요
- 현재 BE2 구현은 body 방식

### 15.2 Refresh Token 저장/조회/폐기 API

현재 결정:

- Access Token 생성/검증은 BE1이 담당한다.
- Refresh Token 생성은 BE1이 담당한다.
- Refresh Token 저장/조회/폐기는 DB 접근이 필요하므로 BE2가 담당한다.
- BE1은 재발급 요청을 받으면 BE2에 Refresh Token 검증을 요청한다.
- BE2가 유효한 토큰이면 `user_id`를 반환한다.
- BE1은 반환받은 `user_id`로 새 Access Token을 발급한다.

추가 구현 필요:

- Refresh Token 저장 테이블
- Refresh Token 저장 API
- Refresh Token 검증 API
- Refresh Token 폐기 API

### 15.3 영화 상세 조회와 반응 기록 호출 타이밍

결정 필요:

- BE1이 영화 상세 응답 전에 BE2 기록 API를 호출할지
- 상세 응답 후 비동기/백그라운드처럼 호출할지

현재 추천:

- 초기 구현은 상세 응답 처리 중 BE2 기록 API를 호출한다.
- 추후 성능 문제가 생기면 비동기 처리로 분리한다.

### 15.4 좋아요 API 담당

결정 필요:

- 프론트가 BE1에 좋아요 요청
- BE1이 BE2에 좋아요 기록 요청

현재 추천:

- 프론트는 BE1만 호출한다.
- BE1은 인증/중복 클릭 정책/응답 조립을 담당한다.
- BE2는 좋아요 기록 및 점수 갱신만 담당한다.

### 15.5 검색 후 조회 source 전달

결정 필요:

- 검색 결과 클릭 시 BE1이 `source="search"`를 BE2에 넘길지

현재 추천:

- BE1이 검색 결과 클릭 흐름을 알고 있으므로 BE1이 `source="search"`를 넘긴다.
- BE2는 `source="search"`면 `search_click`으로 저장한다.

### 15.6 `admin_audit_logs` 유지 여부

현재 상태:

- 테이블은 존재한다.
- 관리자 CRUD에서 실제 기록 저장은 아직 하지 않는다.

결정 필요:

- 유지할지
- 삭제할지
- 나중에 관리자 작업 이력 기능으로 연결할지

현재 추천:

- 테이블은 유지한다.
- 실제 기록 저장은 관리자 권한/JWT 구조 확정 후 연결한다.

### 15.7 캐릭터 기반 취향 학습 설계

현재 결정:

- 취향 학습에 캐릭터 기반 데이터도 반영한다.
- 현재 구현된 취향 학습은 영화 조회/검색 후 조회/좋아요 기반이다.
- 캐릭터 기반 취향 학습은 아직 코드에 없다.

추가로 정해야 할 것:

- 어떤 캐릭터 행동을 기록할지
- 행동별 점수를 몇 점으로 둘지
- 캐릭터 대화 횟수/메시지 수를 점수화할지
- 캐릭터와 연결된 영화의 장르/배우/감독/키워드까지 반영할지
- 기존 `user_preference_scores`를 그대로 사용할지, 캐릭터 전용 테이블을 둘지

현재 추천:

- 먼저 캐릭터 대화 시작 또는 캐릭터 선택을 낮은 점수로 반영한다.
- 캐릭터가 `movie_id`로 영화와 연결되어 있으면 해당 영화 메타데이터를 취향 점수에 함께 반영한다.
- 캐릭터 자체 선호를 따로 보여줄 필요가 생기면 별도 테이블을 추가한다.

## 16. 현재 문서에서 삭제 또는 수정해야 할 내용

삭제/수정 권장:

- Redis 활용 방안 전체
- `/movies/{id}/bookmark`
- `/users/me/bookmarks`
- `dislike`
- `bookmark`
- Redis 기반 랭킹 설명
- Redis 기반 JWT 블랙리스트 설명
- BE2가 Redis 세션/캐시를 담당한다는 설명

수정 권장:

- `user_preferences`를 현재 3개 테이블 구조로 변경
- 랭킹 기준을 PostgreSQL `movie_stats` 기준으로 변경
- 프론트 요청 흐름을 `Frontend -> BE1 -> BE2`로 명확히 변경
- BE2 API 목록을 현재 구현된 엔드포인트 기준으로 변경
- JWT 발급/Access Token 검증은 BE1 담당으로 표시
- Refresh Token DB 저장/조회/폐기는 BE2 담당 예정으로 표시
- BE2는 JWT를 직접 검증하지 않는 것으로 표시

추가 권장:

- 공통 응답 포맷
- BE1이 BE2에 넘겨야 하는 payload 예시
- Refresh Token 저장/조회/폐기용 BE2 API 명세
- 행동 점수 기준
- 취향 점수 기준
- `source` 값 기준
- 보류 항목 목록
