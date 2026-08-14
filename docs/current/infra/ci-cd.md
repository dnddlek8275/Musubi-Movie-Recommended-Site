# Musubi CI/CD

## 확정 운영 원칙

- GitHub Actions: 테스트, 컨테이너 빌드, Container Registry Push까지만 수행
- Kubernetes migration 및 배포: 운영자가 로컬에서 수동 실행
- GitHub Actions에는 운영 kubeconfig와 Kubernetes 변경 권한을 저장하지 않음
- 운영 이미지는 Git commit SHA를 태그로 사용하며 `latest`를 사용하지 않음

## CI

`.github/workflows/ci.yaml`은 `dev` 브랜치 Push와 `dev` 대상 Pull Request에서
실행한다.

- Frontend: `npm ci`, 의존성 감사, Vite 프로덕션 빌드
- Backend: Python 3.12 설치, 의존성 검사, 구문 컴파일, Alembic 단일 head 검사,
  단위 테스트와 FastAPI 라우트 검사
- PostgreSQL: 임시 PostgreSQL 17에 Alembic 전체 적용 후 Backend 실제 기동,
  `/health`, `/ready`, `/db-test` 검사
- Container: Frontend·Backend 이미지를 빌드하되 Registry에는 Push하지 않음
- Kubernetes: Kustomization 참조와 리소스 스키마 검사

## 이미지 Build·Push

`.github/workflows/release.yaml`은 GitHub Actions에서 수동으로 실행한다. 실행 시
`confirmation`에 `PUBLISH`를 입력한다. 선택한 Git revision의 SHA가 이미지
태그가 되며 Kubernetes에는 접근하지 않는다.

GitHub Repository Actions Variable로 다음 값이 등록돼 있다. `production` job에서도
Repository Variable을 사용한다.

| 이름 | 운영 값 |
|---|---|
| `REGISTRY_HOST` | `kc-sfacspace05.kr-central-2.kcr.dev` |
| `FRONTEND_IMAGE_REPOSITORY` | `kc-sfacspace05.kr-central-2.kcr.dev/team3-front-repo/frontend` |
| `BACKEND_IMAGE_REPOSITORY` | `kc-sfacspace05.kr-central-2.kcr.dev/team3-back-repo/backend` |
| `BUILD_PLATFORMS` | `linux/amd64` |

필요한 Secret:

| 이름 | 설명 |
|---|---|
| `REGISTRY_USERNAME` | Registry 로그인 계정 |
| `REGISTRY_PASSWORD` | Registry 로그인 비밀번호 또는 토큰 |

`KUBE_CONFIG`, `KUBECTL_VERSION`은 이 workflow에 사용하지 않는다. 과거 자동
배포용으로 GitHub에 등록했다면 제거하는 것을 권장한다.

기본 브랜치 `main`에는 Actions 등록을 위한 동일한 `release.yaml`이 있다. 실제
V1 이미지는 `dev`의 merge commit
`2765f04a4d8d0345996d0b4b2fb18961dce8639a`에서 빌드했고 Frontend·Backend 모두
KCR Push에 성공했다.

## 운영자 수동 배포

Actions 실행 결과 Summary에 출력된 Frontend·Backend 전체 이미지 주소를
확인한다. 배포 전 최신 백업과 복구 가능성을 확인한 뒤, kubeconfig가 설정된
관리자 단말의 저장소 루트에서 다음과 같이 실행한다.

```bash
CONFIRM_DEPLOY=DEPLOY \
BACKUP_VERIFIED=BACKUP_VERIFIED \
bash Infra/k8s/scripts/manual-release.sh \
  REGISTRY_HOST/PROJECT/team3-front-repo:GIT_SHA \
  REGISTRY_HOST/PROJECT/team3-back-repo:GIT_SHA
```

스크립트는 다음 순서로 동작한다.

1. 클러스터 사전 검사
2. 고유 이름의 Alembic migration Job 실행
3. migration이 등록한 영화 벡터 작업을 별도 Job에서 모두 처리하고 잔여 작업 0건 확인
4. migration과 벡터 동기화 성공 후에만 Backend·Frontend 이미지 교체
5. 두 Deployment의 rollout 완료 대기
6. 운영 `/api/ready`, `/api/db-test`, `/api/ai-health` 검사

벡터 동기화 Job은 `cineverse-secrets`의 `AI_SYNC_TOKEN`을 사용한다. pending 또는
failed 작업이 남으면 배포 스크립트는 실패로 종료하며 Deployment 이미지를 교체하지
않는다.

Migration은 자동 downgrade하지 않는다. rollout 실패 시 DB에는 migration이
이미 적용됐을 수 있으므로, 기존 이미지로 돌아갈 수 있는지는 migration의
하위 호환성을 먼저 확인한다.

## 운영 상태 모니터링

`.github/workflows/production-health.yaml`에는 10분마다 다음 공개 주소를 검사하는
정의가 있다.

- `/`
- `/api/health`
- `/api/ready`
- `/api/db-test`
- `/api/ai-health`
- TLS 인증서 잔여기간 14일 이상

일시적인 네트워크 오류는 2회 재시도한다. 최종 실패하면 GitHub Actions가
실패한다. 예약 workflow 알림은 해당 workflow를 만든 사용자에게 전달되므로,
그 사용자가 GitHub 알림 설정의 Actions 항목에서 웹 또는 이메일과
`실패한 workflow만 알림`을 활성화해야 한다. 예약 실행은 GitHub 부하에 따라
지연될 수 있으므로 이 검사는 초기 synthetic monitor이며 엄격한 실시간 장애
감시를 대체하지 않는다. DB VM의 백업 성공 여부도 이 검사에는 포함되지 않는다.

2026-08-11 기준 GitHub 기본 브랜치에 등록된 workflow는 `CI`와
`Build and Push Images` 두 개다. `production-health.yaml`은 `dev`에만 있어 예약
실행이 활성화되지 않았다. 이를 실제로 사용하려면 기본 브랜치에 등록하는 별도
승인 작업이 필요하다.

GPU VM은 Alert Center 대신 1분 주기의 watchdog이 Slack Incoming Webhook으로
직접 장애·복구 알림을 전송한다. Webhook URL은 VM의 root 전용 환경 파일에만
보관한다. Kubernetes·DB 백업·공개 서비스 health 알림은 아직 같은 Slack 채널로
통합되지 않았다.

## 아직 확정되지 않은 부분

- `production-health.yaml` 기본 브랜치 등록 및 실패 알림 수신자
- Kubernetes·DB 백업 장애의 Slack 통합 방식
- 실패한 배포의 애플리케이션 rollback 판단 기준
