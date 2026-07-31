# CineVerse Infrastructure

현재 폴더에는 애플리케이션 배포용 Kubernetes 템플릿을 보관합니다.
VPC, 서브넷, ALB, Kubernetes Cluster, PostgreSQL VM과 GPU VM은 관리자
권한으로 별도 생성해야 합니다.

## Kubernetes 파일

```text
k8s/
├── base/                    # Namespace, Deployment, Service, Ingress
├── uploads-pvc.example.yaml
├── secret.example.yaml     # Git에 올릴 수 있는 Secret 구조 예제
└── README.md                # 사전 값, 적용 및 검증 절차
```

`secret.example.yaml`의 값은 예시일 뿐이며 실제 자격증명이 아닙니다. 실제
Secret 파일은 저장소 밖에서 만들고 Git에 커밋하지 않습니다.

관리자로부터 Registry, 도메인, DB·AI 사설 주소와 RWX StorageClass를 받은
후 [Kubernetes 안내](k8s/README.md)의 교체 목록에 반영해야 합니다.

GitHub Actions의 검사·수동 배포 흐름은
[CI/CD 안내](../docs/current/infra/ci-cd.md)를 확인합니다.
