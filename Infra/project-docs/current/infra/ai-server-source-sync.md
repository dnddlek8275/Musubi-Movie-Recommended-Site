# GPU AI 서버–로컬 소스 비교 기록

확인일: 2026-08-11

## 비교 대상

- 운영 서버: `ubuntu@10.30.2.227` (Bastion `210.109.55.27` 경유)
- 서버 경로: `/home/ubuntu/cineverse`
- 로컬 경로: `AI/`
- 실행 진입점: `cineverse-api.service`의 `api.main:app`

비교에는 `api`, `llm`, `pipeline`, `rag`, `services`, `eval`, `test`, `train`,
`docs`, 캐릭터 프로필과 검증 관계 데이터를 포함했다. `.env`, 토큰, 모델,
Python venv, Milvus 볼륨, MinIO 데이터, 로그, 백업과 임시 파일은 제외했다.

## 결론

서버에서 로컬로 가져와야 할 최신 실행 코드는 없었다. 현재 서비스가 사용하는
`api`, `llm/client.py`, `pipeline`, `services`와 핵심 retriever·동기화 코드는
서버와 로컬이 동일했다. 서버 전체를 로컬에 덮어쓰면 오히려 아래 구버전 파일과
런타임 산출물이 섞이므로 수행하지 않는다.

### 로컬 최신본을 유지한 차이

- `AI/docs/*`: 서버 문서는 이전 `CineVerse` 명칭과 과거 Public IP를 사용한다.
- `AI/rag/insert_data.py`: 로컬은 `release_date` 필드와 스키마 처리가 추가돼 있다.
- `AI/rag/embedder.py`, `AI/rag/llm.py`: 로컬은 현재 `Musubi` 명칭을 사용한다.
- 일부 평가 결과: 실행 시점이 다른 측정 결과이므로 서버 결과로 덮어쓰지 않는다.
- `AI/pipeline/movie_pipeline.py`: 비교 중 로컬 작업 트리에 처리 단계별 시간 계측이
  추가됐으며 서버에는 없다. 이 변경은 보존하되 별도 배포 전 테스트·리뷰 대상이다.

### 서버에만 남은 레거시 복제 파일

서버 `rag/`에는 `main.py`, `intent.py`, `movie_pipeline.py`,
`character_pipeline.py`, `recommendation_context.py`가 추가로 존재한다. 실제
systemd 진입점 `api.main:app`은 루트 `pipeline/`을 import하므로 이 파일들은 현재
실행 경로가 아니다. 로컬에는 복사하지 않는다.

### 동일하거나 별도 관리되는 파일

- `data/character_relations_verified_v1.json`: 서버와 로컬 동일
- `ops/check-milvus-alerts.sh`: 저장소의 `Infra/scripts/check-milvus-alerts.sh`와
  동작 동일
- 서버 백업·평가 이력: 운영 장애 분석용으로 서버에 유지하며 소스 동기화 대상 아님

## 확인한 운영 설정

| 항목 | 값 |
|---|---|
| AI API | `0.0.0.0:80`, 사설망에서만 접근 |
| llama-server | `0.0.0.0:8081`, `--ctx-size 20480`, `-np 5` |
| 영화 컬렉션 | `movies_active` |
| 캐릭터 컬렉션 | `characters_verified_v5` |
| Milvus | `127.0.0.1:19530` |

비밀 값은 수집하거나 문서에 기록하지 않았다. 운영 서버 환경파일은
`/etc/cineverse/` 아래에서 root 권한으로 계속 관리한다.

## 검증 결과

- AI 단위 테스트: 112개 통과
- 하위 검증: 46개 통과
- PostgreSQL 고유 `tmdb_id`: 32,308개
- Milvus `movies_active` 고유 `tmdb_id`: 32,308개
- Milvus 누락·초과·중복: 모두 0개
- `cineverse-api.service`, `cineverse-llama.service`: active
- Milvus·etcd·MinIO: healthy

## 이후 동기화 원칙

1. 서버 전체 디렉터리를 `rsync --delete`로 로컬에 덮어쓰지 않는다.
2. 먼저 코드와 문서만 임시 경로에 복사해 파일별 diff를 확인한다.
3. 서버에서 직접 긴급 수정했다면 실행 경로의 파일만 로컬에 선택 반영한다.
4. 모델, DB 볼륨, 로그, 백업과 비밀 환경파일은 Git 소스와 분리한다.
5. 로컬 변경을 서버에 올릴 때는 전체 디렉터리 복사 대신 승인된 파일과 서비스
   재시작 범위를 명시하고, 배포 전후 health 및 회귀 테스트를 수행한다.
