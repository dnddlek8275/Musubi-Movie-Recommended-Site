# 로컬 기준 데이터

## 현재 로컬 구성

2026-07-31에 기존 Backend/PostgreSQL 서버의 기준 데이터를 읽기 전용으로
확인한 뒤 로컬 Compose PostgreSQL에 가져왔다.

| 테이블 | 행 수 | 용도 |
|---|---:|---|
| `movies` | 34,105 | Backend 영화 카탈로그 |
| `movie_genres` | 75,783 | 영화-장르 검색 관계 |
| `movie_stats` | 34,105 | 로컬 테스트용 0 초기값 |
| `actors` | 96,547 | TMDB 배우 기준 데이터 |
| `movie_actors` | 291,996 | 영화-배우 관계 |
| `characters` | 50 | 채팅 캐릭터 |
| `character_aliases` | 15 | 캐릭터 별칭 |

영화·배우·캐릭터 관계의 FK 고아 행은 0건이다. 원격 DB에 있던 소량의
조회·검색·좋아요 테스트 수치는 복사하지 않고 `movie_stats`를 모두 0으로
초기화했다.

## 가져오지 않은 데이터

다음 테이블은 사용자·인증·실행 중 생성되는 데이터이므로 원격 서버에서
가져오지 않았다.

- `users`
- `refresh_tokens`
- `email_verification_codes`
- `password_reset_tokens`
- `chat_rooms`
- `chat_messages`
- `user_movie_interactions`
- `user_preference_scores`
- `admin_audit_logs`
- `daily_ai_recommendations`
- `daily_ai_recommendation_movies`

로컬에서 만든 테스트 계정과 채팅 데이터는 유지한다.

## `movies_final.csv`와의 차이

AI 검색 데이터인 `movies_final.csv`와 기존 Backend DB 영화 카탈로그는 같은
집합이 아니다.

| 비교 | 영화 수 |
|---|---:|
| 공통 TMDB ID | 13,421 |
| 기존 Backend DB에만 존재 | 20,684 |
| CSV에만 존재 | 20,060 |

두 데이터를 단순 행 수 차이로 판단하거나 내부 `movies.id`를 기준으로 병합하면
안 된다. 향후 병합이 필요하면 `tmdb_id`를 기준으로 영화 ID를 다시 매핑하고
`movie_actors`, `characters`, 일일 추천 연결을 함께 검증해야 한다.

## 배우 API 제한

배우 전체 96,547명을 한 응답으로 반환하지 않도록 `/movies/actors`는 다음
query parameter를 지원한다.

- `q`: 배우 이름 부분 검색
- `page`: 1부터 시작하는 페이지
- `limit`: 페이지당 1~100명, 기본 50명

Frontend 마이페이지 배우 선택창은 입력값으로 검색하며 한 번에 최대 50명만
표시한다.
