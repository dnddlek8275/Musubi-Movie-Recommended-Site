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

GitHub `production` Environment에 필요한 Variable:

| 이름 | 설명 |
|---|---|
| `REGISTRY_HOST` | 카카오클라우드 Container Registry 로그인 호스트 |
| `FRONTEND_IMAGE_REPOSITORY` | `team3-front-repo`를 포함한 전체 이미지 경로(태그 제외) |
| `BACKEND_IMAGE_REPOSITORY` | `team3-back-repo`를 포함한 전체 이미지 경로(태그 제외) |
| `BUILD_PLATFORMS` | Worker Node와 같은 플랫폼. 확인 전에는 추측해 입력하지 않음 |

필요한 Secret:

| 이름 | 설명 |
|---|---|
| `REGISTRY_USERNAME` | Registry 로그인 계정 |
| `REGISTRY_PASSWORD` | Registry 로그인 비밀번호 또는 토큰 |

`KUBE_CONFIG`, `KUBECTL_VERSION`은 이 workflow에 사용하지 않는다. 과거 자동
배포용으로 GitHub에 등록했다면 제거하는 것을 권장한다.

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
3. migration 성공 후에만 Backend·Frontend 이미지 교체
4. 두 Deployment의 rollout 완료 대기
5. 운영 `/api/ready`, `/api/db-test`, `/api/ai-health` 검사

Migration은 자동 downgrade하지 않는다. rollout 실패 시 DB에는 migration이
이미 적용됐을 수 있으므로, 기존 이미지로 돌아갈 수 있는지는 migration의
하위 호환성을 먼저 확인한다.

## 운영 상태 모니터링

`.github/workflows/production-health.yaml`은 10분마다 다음 공개 주소를 검사한다.

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

인프라 알림은 카카오클라우드 Alert Center를 기본으로 사용하고 Slack/Teams
장애 채널을 1차 수신처, 이메일을 2차 수신처로 권장한다. 카카오클라우드에서
지원하는 이메일, SMS, 알림톡, Slack, Webhook 중 실제 수신 채널이 확정되면
Worker·DB·GPU VM 메트릭과 백업 실패 알림을 연동한다. Webhook URL은 GitHub
Secret 또는 VM의 root 전용 환경 파일로 관리하며 저장소에 기록하지 않는다.

## 아직 확정되지 않은 부분

- 카카오클라우드 Registry의 실제 호스트와 전체 Repository 주소
- Kubernetes Worker Node의 CPU 아키텍처와 `BUILD_PLATFORMS`
- GitHub 알림을 수신할 담당자와 Slack/Teams 채널
- 실패한 배포의 애플리케이션 rollback 판단 기준
