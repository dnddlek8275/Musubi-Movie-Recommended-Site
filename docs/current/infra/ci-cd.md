# CineVerse CI/CD

## CI

`.github/workflows/ci.yaml`은 `dev` 브랜치 Push와 `dev` 대상 Pull Request에서
실행한다.

- Frontend: `npm ci`, 의존성 감사, Vite 프로덕션 빌드
- Backend: Python 3.12 설치, 의존성 검사, 구문 컴파일, Alembic 단일 head 검사,
  상태검사 단위 테스트, FastAPI 라우트 검사
- PostgreSQL: 임시 PostgreSQL 17 생성, Alembic 전체 적용, Backend 실제 기동,
  `/health`, `/ready`, `/db-test` HTTP 검사
- Container: Frontend·Backend 이미지를 빌드하되 Registry에는 올리지 않음
- Kubernetes: Kustomization 참조와 Kubernetes 리소스 스키마 검사

현재 Backend 단위 테스트는 `/ready`, `/db-test`, `/ai-health`, API 500 응답,
AI 채팅의 500·502·504 상태 코드와 스트리밍 연결 실패를 검사한다. 로그인·추천의
전체 기능 테스트는 아직 없으며, 자동 통합 검사는 DB 스키마 전체 적용과
Backend 실제 연결 확인까지 수행한다.

## 수동 Release

`.github/workflows/release.yaml`은 자동 실행되지 않는다. GitHub Actions에서
수동 실행하고 `confirmation`에 `DEPLOY`, `backup_confirmation`에
`BACKUP_VERIFIED`를 정확히 입력해야 한다.

Production Environment에 승인 규칙을 설정하는 것을 권장한다.

필요한 GitHub Environment Variable:

| 이름 | 설명 |
|---|---|
| `REGISTRY_HOST` | Container Registry 호스트 |
| `REGISTRY_NAMESPACE` | Registry 프로젝트 또는 Namespace |
| `BUILD_PLATFORMS` | Worker Node에 맞는 이미지 플랫폼 목록 |
| `KUBECTL_VERSION` | 실제 Kubernetes Cluster와 호환되는 kubectl 버전 |

필요한 GitHub Environment Secret:

| 이름 | 설명 |
|---|---|
| `REGISTRY_USERNAME` | Registry 로그인 계정 |
| `REGISTRY_PASSWORD` | Registry 로그인 비밀번호 또는 토큰 |
| `KUBE_CONFIG` | kubeconfig 파일을 Base64로 인코딩한 값 |

Release는 다음 순서로 실행한다.

1. Frontend·Backend 이미지를 변경 불가능한 태그로 빌드하고 Registry에 Push
2. 애플리케이션 Secret과 migration Secret이 분리됐는지 확인
3. Alembic Job에서 DB 권한·`pgcrypto`·현재 revision 사전 검사
4. `alembic upgrade head` 실행
5. 적용 revision이 저장소 head와 일치하는지 확인
6. Backend·Frontend Deployment 이미지 교체
7. 두 Deployment의 Rollout 성공 확인

Migration Job이 실패하면 로그와 Job 상태를 출력하고 Deployment image 교체를
실행하지 않는다. 상세 백업·복구 절차는
`docs/current/infra/database-migration-runbook.md`를 따른다.

## 아직 확정되지 않은 부분

- 카카오클라우드 Container Registry의 실제 인증 방식과 주소
- Kubernetes Worker Node의 CPU 아키텍처
- 실제 kubeconfig 발급 및 권한 범위
- GitHub Production Environment 승인 담당자
- 실패한 배포의 자동 롤백 정책

위 값이 확정되기 전에는 Release 워크플로를 실행하지 않는다.
