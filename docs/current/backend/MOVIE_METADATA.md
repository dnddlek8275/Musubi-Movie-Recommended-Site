# 영화 상세 메타데이터

## 저장 항목

`movies` 테이블은 다음 상세 정보를 저장한다.

| 컬럼 | 형식 | 출처 및 의미 |
| --- | --- | --- |
| `runtime` | 정수, nullable | TMDB 러닝타임(분). 최초 보강 시 CSV 값이 있으면 먼저 사용한다. |
| `production_countries` | ISO 3166-1 alpha-2 배열, nullable | TMDB 제작 국가 코드 목록 |
| `certification` | 문자열, nullable | TMDB 개봉 정보에 등록된 관람등급 |
| `certification_country` | ISO 3166-1 alpha-2, nullable | 선택된 관람등급의 국가. 한국(`KR`) 등급을 우선하고, 없으면 미국(`US`) 등급을 사용한다. |

TMDB에 값이 없는 항목은 추측하거나 대체값을 만들지 않고 `NULL`로 유지한다.

## 2026-08-05 로컬 DB 보강 결과

대상 영화는 총 34,920편이다. `movies_final.csv`의 러닝타임을 먼저 반영한 뒤,
TMDB 영화 상세정보와 개봉 정보를 조회했다. API 일시 실패는 0건이었다.

| 항목 | 확보 건수 | 보유율 |
| --- | ---: | ---: |
| 러닝타임 | 34,676 | 99.3% |
| 제작 국가 | 33,338 | 95.5% |
| 연령등급 | 22,748 | 65.1% |

연령등급 22,748건 가운데 한국 등급은 7,883건, 한국 등급이 없어 선택한 미국
등급은 14,865건이다. 수치는 현재 로컬 DB 기준이며 이후 영화 추가·동기화에
따라 달라질 수 있다.

## 성인물 제외 정책

- TMDB 검색·상세조회에서 `adult=false`가 명시된 영화만 등록한다.
- TMDB의 `adult=false` 오분류를 보완하기 위해 `adult video`, `erotic movie`,
  `hardcore`, `porn film`, `softcore` 키워드가 있는 작품도 차단한다.
- 다만 한국 `전체/12/15세` 또는 미국 `G/PG/PG-13` 등급이 명시된 작품은
  키워드 오탐 가능성이 있으므로 자동 차단하지 않는다.
- 2026-08-06 3차 감사에서 이 기준과 영문 줄거리 증거를 TMDB 최신 상세정보와
  대조해 204편을 로컬 DB에서 삭제했다. 삭제 직전 백업은
  `backups/musubi_before_adult_cleanup_round3_20260806.dump`이다.
- 등급·키워드가 모두 누락된 영화는 자동 판별을 보장할 수 없으므로 이후에도
  주기적인 감사가 필요하다.
- 2026-08-07 재감사에서는 후보 진입 규칙 누락을 수정해 명백한 성인물 1편을
  먼저 제거하고, `sexploitation`, `nudistploitation`, 직접 성인 영상물 분류 및
  포르노 산업 다큐멘터리라는 TMDB 최신 근거가 있는 66편을 추가 제거했다.
  단순히 성매매·성적 소재가 줄거리에 등장하는 일반 영화는 삭제하지 않았다.
- 해당 작업 전 복구용 백업은
  `backups/musubi_before_milvus_sync_20260807.dump`이며, 최종 영화 수는
  32,302편이다.
- AI 추천은 PostgreSQL의 최종 `tmdb_id` 목록으로 Milvus를 재색인했다.
- 2026-08-07 일일 증분 동기화에서 신규 5편과 기존 변경 634편을 반영해
  PostgreSQL과 Milvus가 각각 32,307편이 됐다. 자세한 실행 기준은
  `TMDB_DAILY_SYNC.md`를 따른다.
  두 저장소의 누락·초과·중복은 모두 0건이며, 성인물 추천 요청은 AI
  파이프라인에서도 영화 목록 없이 차단한다.
- 2026-08-11 운영 재검증에서는 PostgreSQL 영화 32,309행 중 고유한 비어 있지
  않은 `tmdb_id`가 32,308개였고, Milvus `movies_active`의 전체 iterator도
  32,308개를 반환했다. 두 ID 집합의 누락·초과·중복은 모두 0개다.

### 감독·출연진 추가 보강

감독 또는 출연진이 비어 있던 영화 1,987편을 TMDB 크레딧으로 다시 조회했다.
기존 값은 덮어쓰지 않았으며 출연진은 TMDB 표시 순서 기준 상위 10명과 배우별
배역 관계를 함께 저장했다. API 일시 실패는 0건이었다.

| 항목 | 보강 전 | 추가 확보 | 보강 후 | 보유율 |
| --- | ---: | ---: | ---: | ---: |
| 감독 | 33,707 | 1,020 | 34,727 | 99.4% |
| 출연진 | 33,041 | 1,008 | 34,049 | 97.5% |

나머지는 현재 TMDB 크레딧 응답에도 해당 값이 없어 `NULL` 또는 빈 배열로
유지했다.

## 다시 실행하는 방법

CSV 러닝타임만 보강한다.

```bash
docker compose run --rm \
  -v "$(pwd)/movies_final.csv:/data/movies_final.csv:ro" \
  backend python scripts/backfill_movie_metadata.py \
  --source csv --csv-path /data/movies_final.csv
```

TMDB의 세 항목을 보강한다. 이미 저장된 값은 덮어쓰지 않으며 체크포인트를
사용해 중단 지점부터 재개할 수 있다.

```bash
docker compose run --rm \
  -v "$(pwd)/Backend/.runtime/tmdb-checkpoints:/app/.runtime/tmdb-checkpoints" \
  backend python scripts/backfill_movie_metadata.py \
  --source tmdb \
  --checkpoint /app/.runtime/tmdb-checkpoints/movie-metadata.json \
  --concurrency 20
```

감독·상위 출연진 10명과 배우 관계를 보강한다.

```bash
docker compose run --rm \
  -v "$(pwd)/Backend/.runtime/tmdb-checkpoints:/app/.runtime/tmdb-checkpoints" \
  backend python scripts/backfill_movie_credits.py \
  --checkpoint /app/.runtime/tmdb-checkpoints/movie-credits.json \
  --concurrency 20 --apply
```
