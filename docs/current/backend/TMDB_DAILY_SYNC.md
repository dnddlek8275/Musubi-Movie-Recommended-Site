# TMDB–PostgreSQL–Milvus 일일 동기화

## 기준

- 기준 원본은 PostgreSQL `movies` 테이블이다.
- TMDB 데이터를 Milvus에 직접 추가하지 않는다.
- 매일 18:30(Asia/Seoul) Kubernetes CronJob이 전날 변경분을 처리한다.
- 기존 영화는 TMDB 변경 목록에 포함된 경우 최신 상세정보로 갱신한다.
- 신규 영화는 최근 45일부터 향후 365일 범위의 Discover 결과에서 선별한다.
- 신규 등록 기준은 `adult=false`, 포스터 있음, 평점 6.0 이상, 투표 100개 이상이다.
- 상세정보 단계에서 제목·줄거리·키워드·장르·연령등급을 함께 검사하는 성인물 추가 차단 규칙도 다시 적용한다.

TMDB의 Daily ID Export는 전체 상세 데이터가 아니므로 매일 전체 파일을 그대로
DB에 넣지 않는다. 변경 목록과 제한된 Discover 조회를 사용해 API 호출과 신규 저품질
영화 유입을 통제한다.

## 처리 순서

1. TMDB 변경 ID와 최근·개봉 예정 후보 ID를 조회한다.
2. TMDB 상세정보, 크레딧, 키워드, 개봉일과 번역을 조회한다.
3. `tmdb_id` 기준으로 PostgreSQL 영화·장르·배우 관계와 `movie_genre_weights`를 한 트랜잭션에서 반영한다.
4. 같은 트랜잭션에서 `movie_vector_sync_jobs`에 upsert/delete 작업을 기록한다.
5. PostgreSQL 커밋 이후 GPU AI API에 최대 50개씩 전달한다.
6. GPU 서버는 먼저 임베딩을 만든 뒤 같은 `tmdb_id`의 기존 Milvus 행을 삭제하고
   새 행을 삽입한다.
7. 성공한 작업만 `completed`, 실패한 작업은 `failed`로 남겨 다음 실행에서 재시도한다.

## 장애와 중복 방지

- CronJob `concurrencyPolicy: Forbid`로 동시 실행을 막는다.
- `tmdb_daily_sync_runs.sync_date`로 날짜별 실행 결과를 기록한다.
- 3시간 이상 남아 있는 `running` 기록은 비정상 종료로 보고 다시 실행할 수 있다.
- PostgreSQL 반영이 실패하면 Milvus 작업은 생성되지 않는다.
- AI API 호출이 실패하면 PostgreSQL 영화는 유지되고 작업만 재시도 상태로 남는다.
- Milvus 기존 컬렉션 전체를 삭제하거나 매일 전체 영화를 재임베딩하지 않는다.

## 2026-08-07 최초 증분 실행 결과

- 대상 날짜: 2026-08-06
- 신규 등록: 5편
- 기존 갱신: 634편
- 삭제·실패: 0편
- Milvus 완료 작업: 639건
- 최종 PostgreSQL/Milvus: 각각 32,307편
- 양쪽 `tmdb_id` 중복: 0건

## 2026-08-11 운영 확인

- Kubernetes CronJob `tmdb-daily-sync`: `30 18 * * *`, `Asia/Seoul`, suspend 해제
- 최근 Job: `Completed`, 재시작 0회
- `tmdb_daily_sync_runs`의 최신 대상 날짜: 2026-08-09
- `movie_vector_sync_jobs`: `completed` 843건, 다른 상태 0건
- PostgreSQL 영화: 32,309행
- PostgreSQL 고유한 비어 있지 않은 `tmdb_id`: 32,308개
- Milvus `movies_active` iterator: 32,308행, 고유 ID 32,308개
- PostgreSQL 대비 Milvus 누락·초과·중복: 모두 0개

스케줄은 변경하지 않는다. 18:30 KST 실행 전에는 전날 대상 날짜가 최신 기록으로
보이는 것이 정상이며, 다음 실행 후 Job 완료·오류 로그·건수와 정합성을 다시 본다.

## 인증 설정

Backend와 GPU AI 서비스에 동일한 `AI_SYNC_TOKEN`을 설정한다. 이 값은 Secret이나
root 전용 환경파일에 두며 Git에 커밋하지 않는다.

```env
AI_SYNC_TOKEN=공유_랜덤_토큰
TMDB_SYNC_MIN_RATING=6.0
TMDB_SYNC_MIN_VOTES=100
TMDB_SYNC_DISCOVER_MAX_PAGES=20
TMDB_SYNC_FETCH_CONCURRENCY=5
```

GPU 서비스는 `MOVIE_COLLECTION_NAME=movies_active`, `MILVUS_HOST`, `MILVUS_PORT`도
설정해야 한다. 내부 API `POST /internal/movies/sync`는 Bearer 토큰이 없거나 틀리면
401을 반환한다.

## 수동 실행과 확인

```bash
python scripts/sync_tmdb_daily.py --date 2026-08-06
```

Milvus 전달을 제외하고 PostgreSQL까지만 처리하려면 다음 옵션을 사용한다.

```bash
python scripts/sync_tmdb_daily.py --date 2026-08-06 --skip-vector-dispatch
```

상태 확인 SQL:

```sql
SELECT * FROM tmdb_daily_sync_runs ORDER BY sync_date DESC;
SELECT status, operation, count(*)
FROM movie_vector_sync_jobs
GROUP BY status, operation;
```
