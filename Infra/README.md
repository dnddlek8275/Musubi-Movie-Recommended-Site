# Musubi Infrastructure

운영 인프라는 2개 가용 영역에 총 10 VM을 배치하는 구조로 구성을 완료했다. 현재 운영 상태와 점검 항목의 기준 문서는 [`multi-az-architecture.md`](project-docs/current/infra/multi-az-architecture.md)로 통일한다.

## 운영 구성 요약

- KKE Worker 4대: AZ별 2대
- GPU AI VM 2대: AZ별 1대
- PostgreSQL VM 2대: Primary/Standby
- NAT+Bastion VM 2대: AZ별 1대
- Public LB HA 및 Internal AI LB HA는 관리형 자원으로 운영
- 별도 Ops VM 없이 모니터링은 Kubernetes에서 운영

현재 폴더에는 애플리케이션 배포용 Kubernetes 템플릿을 보관합니다.
VPC, 서브넷, ALB, Kubernetes Cluster, PostgreSQL VM과 GPU VM은 관리자
권한으로 별도 생성해야 합니다.

## Kubernetes 파일

```text
k8s/
├── base/                    # Namespace, Deployment, Service, Ingress
├── secret.example.yaml     # Git에 올릴 수 있는 Secret 구조 예제
└── README.md                # 사전 값, 적용 및 검증 절차
```

`secret.example.yaml`의 값은 예시일 뿐이며 실제 자격증명이 아닙니다. 실제
Secret 파일은 저장소 밖에서 만들고 Git에 커밋하지 않습니다.

관리자로부터 Registry, 도메인, DB·AI 사설 주소와 Object Storage
자격증명을 받은 후 [Kubernetes 안내](k8s/README.md)의 교체 목록에
반영해야 합니다.

GitHub Actions의 검사·수동 배포 흐름은
[CI/CD 안내](project-docs/current/infra/ci-cd.md)를 확인합니다.

## 보조 자료

- `project-docs/`: 현행 아키텍처, 운영 절차, 요구사항 및 발표용 근거 문서
- `add-ons/`: 선택형 TTS·GPU 모니터링·프로토타입
- `compose.yaml`: 로컬 통합 실행 구성
