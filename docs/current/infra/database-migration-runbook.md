# 운영 DB Migration Runbook

이 문서는 PostgreSQL/PgBouncer VM과 Object Storage가 아직 생성되지 않은
상태에서 준비할 수 있는 운영 migration 절차를 정의한다. 실제 운영 DB 주소,
계정과 백업 저장소는 관리자 제공 후 채운다.

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

Object Storage 자동 백업이 준비되기 전에는 관리자가 PostgreSQL VM에서 수동
백업을 만들고 별도 안전한 위치에 보관해야 한다. 저장소에는 DB 자격증명과
실제 백업 경로를 기록하지 않는다.

관리자 실행 예시:

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/안전한/백업경로/cineverse-before-migration.dump \
  "postgresql://백업계정@DB_PRIVATE_ADDRESS:5432/CineVerse"
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

GitHub Actions의 `Build, Push, and Deploy` workflow에는 두 확인값이 필요하다.

- `confirmation`: `DEPLOY`
- `backup_confirmation`: `BACKUP_VERIFIED`

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

## 현재 보류 항목

- KakaoCloud Object Storage bucket과 접근키
- 자동 `pg_dump` 일정과 업로드 작업
- 백업 보존 기간과 Lifecycle
- 복구 시험용 PostgreSQL 환경
- 운영 migration 계정과 `pgcrypto` 설치

위 값이 확정되기 전에는 Production Release를 실행하지 않는다.
