# Musubi 클라우드 아키텍처 현행 및 확장 계획

기준일: 2026-08-17
확장 작업 예정일: 2026-08-18 09:00 KST
상태 표기: `운영`은 현재 확인된 구성, `확장 예정`은 다음 작업에서 적용할 구성,
`후속 검토`는 이번 작업 범위 밖의 발전 방향이다.

## 1. 현재 운영 구조

```text
사용자
  -> DNS: movieverse.cloud
  -> Public Application Load Balancer (HTTPS 443)
  -> KKE Worker NodePort 31664
  -> ingress-nginx
       -> /     Frontend Service -> Frontend Pods
       -> /api  Backend Service  -> Backend Pods
                                -> PgBouncer 6432 -> PostgreSQL VM
                                -> AI API 80      -> GPU AI VM

관리자 PC
  -> Bastion 210.109.55.27
  -> Private VM SSH

Private outbound
  -> NAT + Bastion VM

PostgreSQL backup / profile assets
  -> Object Storage

Frontend / Backend images
  -> Container Registry
```

### 현재 인스턴스

| 구분 | 이름/수량 | 유형 | 사설 IP | 배치 | 상태 |
|---|---|---|---|---|---|
| KKE Worker | 2대 | `t1i.large` | `10.30.2.178`, `10.30.2.122` | Private | 운영 |
| GPU AI | `cineverse-gpu-vm-03` | `gn1i.4xlarge`, Tesla T4 | `10.30.2.227` | Private | 운영 |
| PostgreSQL | `cineverse-db-vm-03` | `t1i.large` | `10.30.2.185` | Private | 운영 |
| NAT + Bastion | `cineverse-bastion-nat-03` | 현재 콘솔 표시 `gn1i.4xlarge` | `10.30.1.134` | Public | 운영 |

현재 VPC는 `10.30.0.0/16`이다. 확인된 서브넷은 Public
`10.30.1.0/24`, Private `10.30.2.0/24`, Private `10.30.3.0/24`이다.
현재 표에 기재한 인스턴스는 모두 `kr-central-2-a`에 있다.

## 2. 현재 운영 경계

- 인터넷에 공개되는 서비스 진입점은 Public Load Balancer의 HTTPS 443이다.
- KKE Worker, PostgreSQL VM, GPU AI VM에는 퍼블릭 IP를 연결하지 않는다.
- Backend 애플리케이션은 PgBouncer 6432를 사용하고, Migration Job만
  PostgreSQL 5432에 직접 접속한다.
- Backend Pod는 사설망으로 GPU AI API 80에 접근한다.
- GPU VM 내부의 llama-server 8081과 Milvus 19530은 인터넷에 공개하지 않는다.
- GitHub Actions는 테스트·빌드·Registry Push까지 수행하며 운영 배포는 검증 후
  수동 `kubectl`/배포 스크립트로 실행한다.

## 3. 확인된 병목

현재 GPU AI VM 한 대에서 Gemma 4 12B GGUF, AI FastAPI, 영화 검색,
CrossEncoder 재정렬, Milvus가 함께 실행된다. 2026-08-17 운영 부하 테스트에서
5개 동시 요청은 모두 성공했으나 GPU 사용률이 100%에 도달했고 p95는
21.555초였다. 10개 동시 요청에서는 p95가 41.520초였다.

Kubernetes Backend Pod 수만 늘려도 AI 요청은 동일한 T4 한 장으로 모이므로
AI 처리량은 증가하지 않는다. 현재 admission queue는 과부하 시 전체 장애를
막지만, 수십 건의 동시 요청에 빠른 응답을 보장하는 용량은 아니다.

## 4. 2026-08-18 확장 예정 구조

첫 확장 단위는 GPU AI 실행 계층의 수평 확장이다.

```text
Backend Pods
  -> Internal AI Gateway / Load Balancer
       -> GPU AI VM 1 (현재 운영 인스턴스)
       -> GPU AI VM 2 (신규, Private)
```

### 이번 확장의 필수 조건

1. 신규 GPU VM은 퍼블릭 IP 없이 Private 서브넷에 생성한다.
2. 기존의 오래된 `team3-gpu-image`를 그대로 운영 기준으로 사용하지 않는다.
   현재 운영 서버의 모델·런타임·systemd 설정을 기준으로 새 이미지 또는 파일
   동기화본을 만들고 체크섬을 확인한다.
3. 두 GPU VM은 동일한 모델, AI API 소스, 환경 변수 스키마, 캐릭터 지식 데이터,
   Milvus 컬렉션 버전을 사용한다.
4. 트래픽 전환 전에 신규 GPU VM을 별도 사설 주소로 카나리 검증한다.
5. Gateway/LB는 헬스 실패 인스턴스를 대상에서 제외해야 한다.
6. 롤링 전환 중 최소 한 대는 정상 서비스 상태를 유지한다.
7. 배포 후 1·5·10 동시 요청을 재측정하고 p50, p95, 성공률, 429/503/5xx,
   GPU 사용률, VRAM을 기록한다.

### 아직 확정되지 않은 입력값

- 신규 GPU VM의 이름, 사설 IP, 가용 영역
- Internal AI Gateway/LB의 KakaoCloud 리소스 유형과 사설 주소
- 헬스체크 경로·주기·실패 임계값
- 운영 목표 p95와 목표 성공률

위 값은 클라우드 리소스 생성 과정에서 확인한 뒤 본 문서에 실제값으로 갱신한다.
확인 전에는 임의의 이름이나 IP를 발표 자료에 사용하지 않는다.

## 5. 확장 작업 순서

1. 현재 GPU VM의 서비스, 모델 SHA-256, llama.cpp build, systemd 옵션과 디스크
   사용량을 기록한다.
2. 신규 GPU VM을 Private 서브넷에 생성한다.
3. 현재 운영 기준 런타임과 모델을 전송하고 SHA-256을 비교한다.
4. AI API, llama-server, Milvus/etcd/MinIO를 시작하고 `/health`를 확인한다.
5. 핵심 일반 대화·추천·캐릭터 요청을 신규 VM 사설 주소에서 검증한다.
6. Internal AI Gateway/LB 대상에 신규 VM을 먼저 등록해 헬스를 확인한다.
7. 기존 VM을 추가하고 Backend의 AI endpoint를 Gateway/LB 주소로 전환한다.
8. 단계별 부하 테스트와 장애 대상 제외를 확인한다.
9. 문제가 있으면 Backend endpoint를 기존 GPU VM 주소로 되돌린다.

## 6. 후속 검토

- 두 가용 영역에 GPU 인스턴스와 네트워크 경로를 분산하는 구조
- NAT와 Bastion 역할 분리 및 가용 영역별 NAT 구성
- AI Gateway 자체의 이중화
- 모델·벡터 인덱스 버전 배포 자동화
- 대화 세션 및 서버 로컬 상태의 외부 저장소 분리
- 실제 트래픽 기반 GPU 자동 증감과 비용 한도 정책

후속 검토 항목은 현재 운영 또는 2026-08-18 완료 항목으로 표기하지 않는다.

## 7. 발표용 핵심 문장

Musubi는 프론트엔드와 백엔드를 Private Kubernetes에서 운영하고,
PostgreSQL과 GPU AI 워크로드는 전용 VM으로 분리한 혼합형 구조다. 현재 단일
T4의 동시 요청 병목이 측정되어, 다음 확장에서는 기존 모델과 파이프라인을 유지한
GPU AI VM을 추가하고 내부 Gateway/LB로 분산하는 방향을 적용한다.
