# CineVerse 최종 멀티 AZ 클라우드 아키텍처

기준일: 2026-08-19
상태: 멀티 AZ 인프라 구성 완료

## 1. 현재 운영 상태와 최종 목표

기존 운영 환경은 `kr-central-2-a` 중심의 5 VM 구조였다. 2026-08-18에
Public-B/Private-B, NAT+Bastion-B, KKE Worker-B 2대, GPU-B와 PostgreSQL
Standby를 추가해 두 AZ에 역할을 분산한 총 10 VM 구성을 완료했다. 서비스
운영 상태는 정기 점검과 모니터링으로 관리한다.

| 구분 | 기존 운영 | 2026-08-18 현재 | 최종 확정 목표 |
|---|---:|---:|---:|
| KKE Worker VM | 2 | 4 | 4 (AZ별 2) |
| GPU AI VM | 1 | 2 | 2 (AZ별 1) |
| PostgreSQL VM | 1 | 2 | 2 (Primary/Standby) |
| NAT+Bastion VM | 1 | 2 | 2 (AZ별 1) |
| 합계 | 5 | 10 | 10 |

## 2. 네트워크

- VPC: `cineverse-vpc-03`, `10.30.0.0/16`
- `kr-central-2-a`: Public-A `10.30.1.0/24`, Private-A `10.30.2.0/24`
- `kr-central-2-b`: Private-B `10.30.3.0/24`, Public-B `10.30.4.0/24`
- Public-A/B 기본 경로: `0.0.0.0/0 -> Internet Gateway`
- Private-A 기본 경로: `0.0.0.0/0 -> NAT+Bastion-A`
- Private-B 기본 경로: `0.0.0.0/0 -> NAT+Bastion-B`

### 2026-08-18 적용 현황

- NAT+Bastion-B: Private `10.30.4.87`, Public `210.109.82.26`
- Private-B 라우팅 테이블: `cineverse-rt-private-b-03`
- NAT+Bastion-B의 IP forwarding 및 `10.30.3.0/24` MASQUERADE 영구 설정 완료
- NAT 네트워크 인터페이스 패킷 송신 허용 IP: `0.0.0.0/0`
- Private-B에서 컨테이너 이미지 Pull, DNS, HTTPS 아웃바운드 검증 완료

## 3. VM 배치

| AZ | Public subnet | Private subnet |
|---|---|---|
| kr-central-2-a | NAT+Bastion-A | KKE Worker-A1/A2, GPU-A, PostgreSQL Primary |
| kr-central-2-b | NAT+Bastion-B | KKE Worker-B1/B2, GPU-B, PostgreSQL Standby |

NAT와 Bastion은 AZ별로 한 VM에서 함께 운영한다. 별도 Ops VM은 두지 않으며 모니터링 워크로드는 Kubernetes에서 운영한다.

현재 AZ-B KKE 노드 풀은 `cineverse-worker-b-3`이며 `t1i.large`, 루트 볼륨 50GB, 노드 2대로 구성한다. 노드 사설 IP는 `10.30.3.66`, `10.30.3.111`이고 두 노드 모두 Kubernetes `Ready` 상태를 확인했다.

## 4. 관리형 자원

다음 자원은 VM 수에 포함하지 않는다.

- Public Load Balancer A/B 및 Public HA Group
- Internal AI Load Balancer A/B 및 Internal HA Group
- KKE control plane
- Container Registry
- Object Storage

### Public Load Balancer 적용 현황

- AZ-A: `LoadBalancer03`, Public IP `210.109.82.156`
- AZ-B: `cineverse-public-alb-b-03`, Private IP `10.30.4.116`, Public IP `210.109.83.237`
- AZ-B 대상 그룹: `cineverse-ingress-http-b-03`
  - `10.30.3.66:31664`
  - `10.30.3.111:31664`
- 대상 그룹 알고리즘: Round Robin
- 상태 확인: HTTP GET `/`, 포트 `31664`, 정상 응답 코드 `404`
- Public HA Group: `cineverse-public-alb-ha-03`
- HA Group DNS: `cineverse-public-alb-ha-03-022a02773f.blb.kr-central-2.kakaocloud.com`
- `movieverse.cloud` 루트 A 레코드:
  - `210.109.82.156`
  - `210.109.83.237`
- HTTP `80`은 HTTPS로 리다이렉트하고, HTTPS `443`은 TLS 1.3과 `movieverse.cloud` 인증서를 사용한다.

## 5. 트래픽 흐름

### 사용자 요청

`movieverse.cloud -> Public LB HA Group -> Public LB-A/B -> ingress-nginx NodePort -> KKE Worker -> Frontend/Backend Pod`

- Public ALB에서 TLS를 종료한 뒤 ingress-nginx HTTP NodePort `31664`로 전달한다.
- `externalTrafficPolicy: Cluster`

### AI 요청

`Backend Pod -> Internal AI LB HA Group -> GPU-A 또는 GPU-B -> AI FastAPI -> llama-server / Milvus`

두 GPU VM은 동일한 운영용 Gemma 4 12B GGUF, 런타임, AI API, 설정을 사용한다. 시험 모델은 배포 대상에서 제외한다. 각 GPU VM의 Milvus, etcd, MinIO 데이터는 PostgreSQL 기준으로 동기화한다.

### DB 요청

`Backend Pod -> PgBouncer -> PostgreSQL Primary`

Primary는 Standby로 스트리밍 복제한다. 장애 시 자동 승격이 아닌 수동 승격 절차를 사용하며, Object Storage 백업을 별도로 유지한다.

### PostgreSQL 복제 적용 현황 (2026-08-19)

- Primary: `10.30.2.185`, PostgreSQL 17.10, 애플리케이션 쓰기 대상
- Standby: `10.30.3.190`, PostgreSQL 17.11, `transaction_read_only=on`
- 방식: 물리 비동기 스트리밍 복제 (`streaming`, `sync_state=async`)
- 물리 복제 슬롯: `cineverse_standby_b` (활성 상태 확인)
- Standby PostgreSQL 서비스: 부팅 자동 시작 `enabled`
- PostgreSQL 서비스 재시작 후 WAL receiver가 `streaming`으로 자동 재연결됨을 확인
- 주요 9개 테이블의 행 수와 `cineverse` DB 크기가 Primary/Standby에서 일치함을 확인
- Standby 실제 루트 볼륨: 50GB. Primary 100GB보다 작으므로 운영 데이터 증가 전에 100GB 이상으로 확장한다.
- 자동 장애조치와 자동 승격은 구성하지 않았다. 장애 시 수동 승격 및 Backend DB 접속 대상 변경이 필요하다.

## 6. 보안 원칙

- 인터넷에는 Public Load Balancer의 80/443만 공개한다.
- SSH는 AZ별 NAT+Bastion을 통해서만 허용한다.
- KKE Worker, DB, GPU AI VM은 Private subnet에 둔다.
- `5432`, `6432`, `8081`, `19530`, `9000`, `9001`은 인터넷에 공개하지 않는다.
- DB와 AI 서비스의 인바운드는 필요한 내부 보안 그룹 간 통신으로 제한한다.
- PostgreSQL VM은 AZ-B KKE 워커가 PgBouncer를 사용할 수 있도록 `TCP 6432`, 출발지 `10.30.3.0/24`만 추가 허용한다.

## 7. 장애 대응 범위

- KKE: 2개 AZ의 4개 Worker에 Pod를 분산하고 PodDisruptionBudget 및 topology spread를 적용한다.
- Public 진입점: Public LB A/B와 HA Group으로 AZ 장애 시 생존 경로를 확보한다.
- AI: Internal AI LB A/B가 정상 GPU 대상으로 전달한다.
- DB: Standby 상태와 복제 지연을 감시하고, 장애 시 운영자가 수동 승격한다.
- NAT/Bastion: Private-A와 Private-B가 각 AZ의 NAT+Bastion을 사용한다.

## 8. 1단계 멀티 AZ 검증 결과 (2026-08-18)

- KKE Worker 4대 `Ready`
- Frontend Deployment: AZ-A 1 Pod, AZ-B 1 Pod
- Backend Deployment: AZ-A 1 Pod, AZ-B 1 Pod
- ingress-nginx Controller: AZ-A 1 Pod, AZ-B 1 Pod
- Frontend/Backend/Ingress에 zone 및 hostname topology spread 적용
- Frontend와 Backend PodDisruptionBudget `minAvailable: 1` 유지
- 공개 `/home`, `/api/health`, `/` 응답 HTTP 200 확인
- Public HA Group이 AZ-A/AZ-B 로드 밸런서 두 노드를 포함하고 Active/Online 상태임을 확인
- 권한 DNS에서 `movieverse.cloud`가 `210.109.82.156`, `210.109.83.237` 두 주소로 조회됨을 확인
- 각 Public IP를 지정한 HTTPS `/api/health` 요청이 모두 HTTP 200으로 응답함을 확인
- HA Group DNS의 HTTP 리다이렉트와 HTTPS `/api/health` 정상 응답 확인
- 운영 이미지 태그와 애플리케이션 설정은 변경하지 않음

## 9. 구축 완료 및 후속 검증

- 총 10 VM이 지정 AZ와 subnet에 배치됨
- Public/Private 라우팅 및 보안 그룹 검증 완료
- KKE Worker 4대 Ready, Frontend/Backend Pod가 두 AZ에 분산됨
- Internal AI LB A/B 대상의 헬스 체크 정상
- PostgreSQL Standby가 `streaming`, `async`, 읽기 전용으로 연결되고 서비스 재시작 후 자동 재연결됨

다음 항목은 인프라 자원 배치와 별개로 후속 운영 검증이 필요하다.

- 두 GPU의 모델 체크섬·런타임·API 설정 최종 대조
- GPU-A 장애를 가정한 Internal AI LB 우회 테스트
- PostgreSQL 수동 승격 및 Backend DB 접속 대상 전환 훈련
- Object Storage 백업 복원 훈련
- Standby 루트 볼륨 50GB를 Primary와 같은 100GB 이상으로 확장
