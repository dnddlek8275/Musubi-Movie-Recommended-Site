# 운영 DB Migration Runbook

이 문서는 PostgreSQL/PgBouncer 전용 VM과 Object Storage를 사용하는 운영
migration 및 백업 절차를 정의한다. 운영 DB는 `10.30.2.185`, 백업 저장소는
`storage-prod-team3/backups/postgresql/`이다. 실제 자격증명은 문서나 저장소에
기록하지 않는다.

## 연결 분리

- Backend Pod: 애플리케이션 계정으로 PgBouncer `6432` 연결
- Alembic Job: migration 계정으로 PostgreSQL `5432` 직접 연결
- `cineverse-secrets`와 `cineverse-migration-secrets`의 `DATABASE_URL`은
  서로 달라야 한다.
- migration 계정에는 대상 schema의 객체 생성·변경 권한이 필요하다.
- `pgcrypto`는 관리자가 운영 DB에 한 번 미리 설치한다.

Migration Job의 preflight는 다음 조건을 검사한다.

- 저장소의 Alembic head가 정확히 하나인지
- DB가 기록한 현재 revision을 저장소가 알고 있는지
- `pgcrypto`가 이미 설치되어 있는지
- migration 계정에 현재 schema의 `CREATE` 권한이 있는지
- migration 완료 후 DB revision이 저장소 head와 일치하는지

검사에 실패하면 `alembic upgrade head`를 실행하지 않거나, 완료 검증 실패로
Job을 실패 처리한다. Release workflow는 Job 성공 전에는 Deployment image를
교체하지 않는다.

## 백업 확인

DB VM에는 `cineverse-db-backup.timer`가 설치되어 있다. 매일 03:20 KST 이후
최대 15분의 임의 지연을 두고 custom-format `pg_dump`를 생성하여
`storage-prod-team3/backups/postgresql/`에 업로드한다. 재부팅 중 실행 시각을
놓치더라도 `Persistent=true`로 다음 부팅 후 실행한다.

백업 작업은 다음 안전장치를 적용한다.

- `flock`으로 중복 실행 방지
- `.partial` 파일에 먼저 생성 후 완료 시 원자적으로 이름 변경
- `pg_restore --list` 성공 후에만 업로드
- SHA-256 파일 동시 업로드
- 업로드 후 Object Storage의 파일 크기 재확인
- DB VM 로컬 파일은 3일만 보관
- `Nice=10`, 낮은 I/O 우선순위로 운영 부하 완화

상태 및 수동 실행 방법:

```bash
sudo systemctl status cineverse-db-backup.timer
sudo systemctl list-timers cineverse-db-backup.timer
sudo systemctl start cineverse-db-backup.service
sudo journalctl -u cineverse-db-backup.service -n 50 --no-pager
```

Object Storage 자격증명은 DB VM의
`/etc/cineverse/object-storage-backup.env`에 root 전용 `0600` 권한으로 둔다.
DB 비밀번호는 기존 `/etc/cineverse/db-credentials.env`를 사용한다.

Migration 직전 추가 수동 백업이 필요한 경우:

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/안전한/백업경로/cineverse-before-migration.dump \
  "postgresql://백업계정@DB_PRIVATE_ADDRESS:5432/cineverse"
```

백업 파일이 생성됐다는 사실만으로 복구 가능성을 확정하지 않는다. 최소한
목록을 읽을 수 있는지 검사하고, 운영 DB와 분리된 검증용 DB에 복구 시험을
완료해야 `BACKUP_VERIFIED`로 판단한다.

```bash
pg_restore --list /안전한/백업경로/cineverse-before-migration.dump
```

복구 시험용 DB의 생성·삭제와 접근 권한은 관리자가 담당한다. 검증용 DB 대상이
확정되지 않은 상태에서 운영자가 임의 주소로 복구 명령을 실행하지 않는다.

## 수동 Release 실행 조건

GitHub Actions는 이미지를 Build·Push할 뿐 운영 DB와 Kubernetes를 변경하지
않는다. 운영자는 `Infra/k8s/scripts/manual-release.sh`를 실행할 때 다음 두
환경변수를 명시해야 한다.

- `CONFIRM_DEPLOY=DEPLOY`
- `BACKUP_VERIFIED=BACKUP_VERIFIED`

`BACKUP_VERIFIED`는 다음 항목을 모두 확인했다는 의미다.

1. migration 직전 백업 시각과 파일을 확인했다.
2. 백업 파일의 `pg_restore --list` 검사가 성공했다.
3. 분리된 검증용 DB에서 복구 시험이 성공했다.
4. 복구 담당자와 백업 위치를 알고 있다.

## 실패 시 동작

- preflight 실패: migration 미실행, Deployment 미변경
- Alembic 실패: Job 로그와 describe 정보 출력, Deployment 미변경
- 완료 revision 불일치: Job 실패, Deployment 미변경
- rollout 실패: migration은 이미 적용됐을 수 있으므로 자동 downgrade하지 않음

Migration은 자동으로 downgrade하지 않는다. downgrade에는 테이블·컬럼 삭제가
포함될 수 있고, `20260703_0003` downgrade는 `character` 유형 선호 데이터를
삭제한다. 애플리케이션 rollback이 필요하면 기존 image로 되돌리되, DB downgrade는
별도 검토와 백업 확인 후 수동으로 수행한다.

## 검증 이력과 보류 항목

- 2026-08-10: 자동 백업 1회 실행 및 Object Storage 업로드 성공
- 2026-08-10: 별도 임시 DB에 복원 성공, public 테이블 26개와 Alembic
  revision `20260808_0026` 확인 후 임시 DB 삭제
- 2026-08-10: 신규 DB에 스키마와 일일 박스오피스 9건만 있고 기존 데이터가
  복원되지 않은 상태를 확인했다. 로컬의
  `musubi_before_tmdb_daily_sync_20260807.dump`를 현재 `0026` 스키마의 임시
  DB에 data-only로 복원하여 무결성을 먼저 검증한 뒤 운영 DB를 교체했다.
- 복원 후 운영 DB는 영화 32,302개, 캐릭터 50개, 배우 103,510개,
  영화-배우 관계 282,388개이며 검사한 고아 관계는 0건이다.
- 활성 Milvus alias `movies_active`는 `movies_postgres_20260807`을 가리킨다.
  PostgreSQL 복원 후 DB에 없는 잔여 벡터 6개를 제거했으며, 최종 TMDB ID는
  PostgreSQL과 Milvus 각각 32,302개로 누락·추가 모두 0건이다.
- 복원 직후 기준 백업은
  `storage-prod-team3/backups/postgresql/cineverse-20260810T090236Z.dump`이며
  크기는 19,322,788 bytes이다. 교체 직전 베타 DB 백업은
  `cineverse-20260810T084912Z.dump`이다.
- `/api/ready`, `/api/db-test`, `/api/ai-health`, `/api/movies/ranking`,
  `/api/chat/characters`를 3회 연속 검사해 모두 HTTP 200을 확인했고 영화 검색도
  HTTP 200을 확인했다.
- 2026-08-11: V1 migration 직전
  `storage-prod-team3/backups/postgresql/cineverse-20260811T051900Z.dump`를 생성했다.
  크기는 19,363,140 bytes이며 SHA-256 확인, `pg_restore --list`, 분리된 임시 DB
  복구를 통과했다. 복구 DB는 public 테이블 26개, revision `20260808_0026`, 영화
  32,309개를 확인한 뒤 제거했다.
- 2026-08-11: `backend-migration-20260811061013` Job으로 revision을
  `20260811_0033`까지 적용하고 완료 revision을 재검증했다. 새 Backend·Frontend
  이미지는 commit SHA `2765f04a4d8d0345996d0b4b2fb18961dce8639a`로 rollout했다.
- 배포 후 PostgreSQL은 영화 32,309행과 고유한 비어 있지 않은 `tmdb_id`
  32,308개를 보유한다. Milvus `movies_active` 전체 iterator도 고유 ID 32,308개로,
  PostgreSQL 대비 누락·초과·중복이 모두 0개다.
- 배포 후 `/`, `/api/health`, `/api/ready`, `/api/db-test`, `/api/ai-health`가 모두
  HTTP 200이고 랭킹 10건, 검색 결과, 비회원 추천 5건을 확인했다. 배포 시점의
  Warning 이벤트와 최근 Backend 오류 로그는 없었다.
- 2026-08-12: 제목 현지화 migration 직전 자동 백업
  `storage-prod-team3/backups/postgresql/cineverse-20260812T041636Z.dump`와
  SHA-256 파일을 Object Storage에 업로드했다. dump 크기는 19,435,194 bytes이다.
- migration Job으로 revision `20260812_0035`를 적용하고, TMDB가 제공하는 공식
  한국어 제목 871건을 PostgreSQL에 반영했다. TMDB에서 삭제된 404 영화 29편은
  사용자 활동 참조가 없음을 확인한 뒤 PostgreSQL과 Milvus에서 제거했다.
- `backend-vector-sync-20260812042743` Job이 제목 변경 871건의 임베딩 재생성을
  완료했으며, 동기화 작업은 완료 2,298건, pending/failed 0건이다.
- 배포 이미지는 commit `c19ca70895a06f52f93745c40ce816595517ab0d`이며,
  Backend·Frontend Deployment는 각각 2/2 Ready, 신규 Pod 재시작 0회로
  롤아웃됐다.
- 배포 후 PostgreSQL 영화는 32,281행이고, 유효한 고유 `tmdb_id`는 32,280개다.
  Milvus `movies_active` iterator도 32,280행·고유 ID 32,280개이며, 두 ID 집합의
  정렬 SHA-256은
  `ce249e208400c1fd088319620acc45b79f4912901b668d7de5376fb5c6fe8371`로
  일치한다. PostgreSQL 대비 Milvus 누락·초과·중복은 모두 0개다.
- `/`, `/api/health`, `/api/ready`, `/api/db-test`, `/api/ai-health`, 랭킹,
  카테고리 검색, 비회원 추천을 재검사해 모두 HTTP 200을 확인했다. 브라우저에서
  `/`와 `/home` 렌더링 및 콘솔 경고·오류 없음도 확인했다.
- 전체 Milvus iterator 감사 중 `MVCC timestamp`를 서버에서 받지 못해 클라이언트
  timestamp로 대체했다는 PyMilvus 경고가 1회 발생했다. 감사 조회는 정상 완료됐고
  PostgreSQL과 Milvus의 전체 ID 해시도 일치하므로 데이터 불일치나 동기화 실패로
  판정하지 않는다.

아직 추가할 운영 안전장치는 다음과 같다.

- Object Storage Lifecycle에 `backups/postgresql/` Prefix 30일 보존 설정
- 백업 서비스 실패 알림 연동
- 정기 복구 훈련과 복구 시간 기록
- 접근키 교체 주기와 폐기 절차 확정

## Object Storage Lifecycle 권장값

현재 일일 백업에는 다음 단일 정책을 적용한다.

| 항목 | 값 |
|---|---|
| 대상 버킷 | `storage-prod-team3` |
| 정책 이름 | `postgresql-daily-30d` |
| 필터 | Prefix 지정 |
| Prefix | `backups/postgresql/` |
| 동작 | 만료 후 삭제 |
| 보존 기간 | 30일 |
| 상태 | 활성화 |

버킷 전체에 정책을 적용하면 `assets/`까지 삭제될 수 있으므로 반드시 Prefix를
지정한다. 카카오클라우드 Lifecycle은 객체 생성 후 지정 일수가 지나면 자동
삭제하도록 설정할 수 있다. 월간 1년 보존이 필요해지면 일일 백업과 같은
Prefix에 예외를 섞지 않고 `backups/postgresql-monthly/`처럼 분리한 뒤 별도
정책을 추가한다.

## 멀티 AZ 확장 후 복구 정책 (최종 목표)

이 절은 2026-08-18 확정한 10 VM 목표 구조에 적용한다. 구축 완료 전에는 현재
단일 PostgreSQL 운영 상태와 혼동하지 않는다.

- `kr-central-2-a`: PostgreSQL Primary + PgBouncer
- `kr-central-2-b`: PostgreSQL Standby
- Primary 변경 사항은 Standby로 streaming replication
- Backend는 정상 운영 시 Primary에 연결
- 장애 시 자동 승격이 아니라 운영자가 Standby를 수동 승격
- 승격 전 복제 상태와 마지막 재생 위치를 확인하고, 승격 후 Backend 연결 정보를
  새 Primary로 전환
- Object Storage 백업은 복제와 별도로 유지하며, 복제 장애와 논리적 데이터 손상에
  대비한 복구 수단으로 사용

수동 승격 훈련에서는 기존 Primary 격리, Standby 승격, PgBouncer/Backend 연결
전환, 쓰기 검증, 기존 Primary 재합류 또는 재구축 순서를 기록한다.
