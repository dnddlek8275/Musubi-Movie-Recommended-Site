# CineVerse Kubernetes 배포 템플릿

이 템플릿은 현재 문서에서 확인된 다음 구조를 반영합니다.

- `/` → Frontend Service
- `/api` → Backend Service
- Frontend 및 Backend 각 2개 Pod
- Backend → PgBouncer `6432`
- Alembic Job → PostgreSQL `5432`
- Backend → GPU AI FastAPI `80`
- Public ALB에서 TLS 종료

## 적용 전에 반드시 받을 값

다음 값은 현재 저장소 자료만으로 확정할 수 없습니다.

| 위치 | 필요한 실제 값 |
|---|---|
| `base/backend.yaml`, `base/migration-job.yaml` | Backend Registry 이미지와 태그 |
| `base/frontend.yaml` | Frontend Registry 이미지와 태그 |
| `base/configmap.yaml` | 운영 도메인, AI VM Private DNS/IP, SMTP 발신 정보 |
| `base/ingress.yaml` | 운영 도메인과 실제 IngressClass |
| 실제 Secret | DB 주소·계정·비밀번호, JWT 키, TMDB·SMTP 자격증명 |
| `uploads-pvc.example.yaml` | `ReadWriteMany`을 지원하는 StorageClass와 필요한 용량 |
| Deployment | 관리자와 합의한 CPU·메모리 requests/limits |

예제의 `service.example.com`, `registry.example.com`, `db.internal`,
`ai.internal`은 실제 운영 값이 아닙니다.

## Secret 생성

`secret.example.yaml`은 구조 확인용이며 Kustomization에 포함하지 않았습니다.
복사본은 저장소 밖에서 관리합니다.

```bash
cp Infra/k8s/secret.example.yaml /안전한/외부경로/cineverse-secret.yaml
```

값을 교체한 후 적용합니다.

```bash
kubectl apply -f /안전한/외부경로/cineverse-secret.yaml
```

Secret을 Git에 커밋하지 않습니다.

## 적용 순서

1. Registry 이미지 주소와 ConfigMap·Ingress 예시값을 실제 값으로 교체합니다.
2. RWX StorageClass·용량과 CPU·메모리 값을 관리자와 확정합니다.
3. Namespace와 ConfigMap을 먼저 적용합니다.
4. `uploads-pvc.example.yaml`의 두 자리표시자를 교체해 PVC를 적용합니다.
5. 실제 Secret을 적용합니다.
6. 마이그레이션 Job을 단독 실행하고 성공을 확인합니다.
7. Kustomize 기본 리소스를 적용해 Backend와 Frontend를 시작합니다.

```bash
kubectl apply -f Infra/k8s/base/namespace.yaml
kubectl apply -f Infra/k8s/base/configmap.yaml
kubectl apply -f /안전한/외부경로/backend-uploads-pvc.yaml
kubectl apply -f /안전한/외부경로/cineverse-secret.yaml
kubectl apply -f Infra/k8s/base/migration-job.yaml
kubectl -n cineverse wait --for=condition=complete job/backend-migration --timeout=300s
kubectl -n cineverse logs job/backend-migration
kubectl apply -k Infra/k8s/base
kubectl -n cineverse rollout status deployment/backend
kubectl -n cineverse rollout status deployment/frontend
```

같은 이름의 완료된 Job을 다시 실행할 때는 기존 Job을 지운 뒤 재적용해야
합니다. DB 마이그레이션 전에는 운영 DB를 백업합니다.

## 검증

```bash
kubectl kustomize Infra/k8s/base
kubectl -n cineverse get deployments,pods,services,ingresses,pvc
curl --fail https://실제도메인/api/health
curl --fail https://실제도메인/api/db-test
curl --fail https://실제도메인/api/ai-health
```

## 아직 템플릿에 넣지 않은 항목

- ingress-nginx Controller 및 Public ALB 설치 설정
- VPC, Subnet, Security Group, NAT+Bastion
- PostgreSQL·PgBouncer VM과 GPU VM 생성
- DNS Record와 ALB 인증서
- CPU·메모리 requests/limits 및 HPA
- Registry 인증용 imagePullSecret
- Object Storage DB 백업 자동화

위 항목은 클라우드 계정과 관리자 확정값이 없으므로 현재 자료만으로 정확하게
작성할 수 없습니다.
