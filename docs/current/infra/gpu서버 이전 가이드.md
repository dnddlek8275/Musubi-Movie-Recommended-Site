# Musubi GPU 서버 프라이빗 서브넷 이전 가이드

## 1. 목적

현재 카카오클라우드 GPU 서버를 유지한 상태에서 신규 VPC의 프라이빗 서브넷에 복제 서버를 생성하고, 정상 작동을 검증한 후 안전하게 전환한다.

이 문서는 다음 범위를 다룬다.

- 신규 VPC와 퍼블릭·프라이빗 서브넷 구성
- Bastion을 통한 프라이빗 GPU 서버 관리 접속
- 기존 GPU 서버의 쓰기 작업 중단
- 커스텀 이미지 생성 및 신규 GPU 서버 복제
- 신규 서버의 서비스·데이터·GPU 성능 검증
- 장애 발생 시 롤백

## 현재 운영 상태 (2026-08-11)

이전과 트래픽 전환은 완료됐다. 아래 이전 절차는 재구축 및 롤백 참고용으로
유지하며 현재 운영 기준은 다음과 같다.

| 항목 | 운영 값 |
|---|---|
| Bastion Public IP | `210.109.55.27` |
| GPU VM Private IP | `10.30.2.227` |
| Backend AI 주소 | `http://10.30.2.227` |
| AI API / llama-server | `cineverse-api.service` / `cineverse-llama.service` |
| Milvus 영화 alias | `movies_active` |
| Milvus 캐릭터 컬렉션 | `characters_verified_v5` |

Backend Kubernetes ConfigMap도 위 사설 AI 주소를 사용한다. 2026-08-11 검증에서
두 AI systemd 서비스와 Milvus·etcd·MinIO 컨테이너가 정상이고, PostgreSQL과
Milvus의 고유 `tmdb_id` 32,308개가 누락·초과·중복 없이 일치했다.

## Milvus v2.4.0 반복 경고 운영 예외

다음 경고는 현재 사용 중인 `milvusdb/milvus:v2.4.0`의 버전 코드 오류로 인해 지속적으로 발생한다.

```text
field id not found, ignore to report indexed num entities
```

Milvus v2.4.0의 DataCoord 통계 코드가 `FieldID` 자리에 실제 필드 ID가 아닌 `IndexID`를 넣고, RootCoord가 이 값을 스키마의 필드 ID와 비교하면서 발생하는 경고다. 일자 컬럼 추가, 컬렉션 손상 또는 인덱스 손상을 의미하지 않는다. 현재 이전·신규 서버의 스키마와 `field-index` 메타데이터 값이 동일하고 컬렉션 행 수, 인덱스 상태 및 검색 결과가 정상임을 확인했다.

운영 시 원본 Docker 로그는 보존한다. 장애 점검과 알림 결과에서 위의 정확한 문구만 제외하며, 다른 `WARN`, `ERROR`, `FATAL`, `panic`, 컨테이너 비정상 상태 및 재시작 증가는 계속 확인한다. Milvus 전체 로그 레벨을 `error`로 올리지 않는다.

점검 명령:

```bash
/home/ubuntu/cineverse/ops/check-milvus-alerts.sh 10m
```

스크립트 종료 코드는 다음과 같다.

- `0`: 컨테이너가 정상이며 예외 문구를 제외한 경고·오류가 없음
- `1`: 확인해야 할 다른 경고 또는 오류가 있음
- `2`: 컨테이너가 없거나 실행·헬스 상태가 비정상

이 문제를 제거하려면 별도 테스트 환경에서 Milvus 업그레이드 호환성을 검증한 후 운영 버전을 변경한다. 현재 운영 이전 완료 단계에서는 버전을 유지한다.

## 2. 확인된 기존 서버 구성

### 서버 자원

| 항목 | 현재 상태 |
|---|---|
| OS | Ubuntu 24.04 LTS |
| CPU | Intel Xeon Gold 5220, 16 vCPU |
| 메모리 | 62 GiB |
| GPU | NVIDIA Tesla T4 15 GB |
| NVIDIA 드라이버 | 535.309.01 |
| CUDA 호환 버전 | 12.2 |
| 루트 볼륨 | 96 GB |
| 루트 볼륨 사용량 | 약 67 GB |

### 애플리케이션 구성

| 구성요소 | 실행 방식 | 포트 |
|---|---|---|
| FastAPI/uvicorn | `cineverse-api.service` | TCP 80 |
| llama-server | `cineverse-llama.service` | TCP 8081 |
| Milvus | Docker Compose | TCP 19530, 9091 |
| MinIO | Docker Compose | TCP 9000, 9001 |
| etcd | Docker Compose | 컨테이너 내부 2379, 2380 |

주요 프로젝트와 데이터는 `/home/ubuntu/cineverse`에 있으며, Milvus 데이터도 해당 프로젝트 아래의 로컬 Docker 볼륨에 저장되어 있다.

## 3. 목표 네트워크 구조

```text
Internet
   │
   ├── 관리자 PC
   │      │ SSH
   │      ▼
   │   Bastion 인스턴스
   │   Public Subnet
   │      │ Private IP
   │      ▼
   └── GPU 인스턴스
       Private Subnet
```

초기 복제 및 내부 작동 테스트에는 Bastion만 있어도 된다. 다음 작업이 필요해지면 NAT 인스턴스를 추가한다.

- `apt update` 또는 신규 패키지 설치
- Docker 이미지 다운로드
- pip 패키지 설치
- Hugging Face 모델 다운로드
- Git 저장소 또는 외부 API 접근

NAT는 프라이빗 GPU 서버의 인터넷 아웃바운드 경로이고, Bastion은 관리자 PC에서 프라이빗 서버로 들어가는 관리 접속 경로다.

## 4. 사전 준비

### 4.1 유지보수 시간 확보

일관된 커스텀 이미지를 생성하려면 기존 서버의 API와 데이터베이스를 정상 종료한 후 인스턴스를 정지해야 한다. 이 구간에는 기존 AI API를 사용할 수 없다.

### 4.2 기존 서버 삭제 금지

신규 서버의 전체 검증과 실제 호출 전환이 끝날 때까지 다음 작업을 하지 않는다.

- 기존 GPU 인스턴스 삭제
- 기존 루트 볼륨 삭제
- 기존 커스텀 이미지 삭제
- 기존 Public IP 해제
- 기존 서비스 설정 변경

### 4.3 CIDR 계획

신규 VPC CIDR은 기존 VPC 및 향후 연결할 네트워크와 겹치지 않아야 한다.

예시:

| 네트워크 | CIDR |
|---|---|
| 신규 VPC | `10.10.0.0/16` |
| 퍼블릭 서브넷 | `10.10.0.0/24` |
| 프라이빗 서브넷 | `10.10.10.0/24` |

위 CIDR은 예시이므로 실제 기존 네트워크 대역을 확인한 후 확정한다.

## 5. 신규 VPC 구성

### 5.1 VPC 및 서브넷 생성

카카오클라우드 콘솔에서 다음 리소스를 생성한다.

1. 신규 VPC
2. 퍼블릭 서브넷
3. 프라이빗 서브넷
4. Internet Gateway
5. 퍼블릭 라우팅 테이블
6. 프라이빗 라우팅 테이블

### 5.2 라우팅 테이블

퍼블릭 서브넷:

| 목적지 | 대상 |
|---|---|
| 신규 VPC CIDR | Local |
| `0.0.0.0/0` | Internet Gateway |

프라이빗 서브넷의 초기 테스트 구성:

| 목적지 | 대상 |
|---|---|
| 신규 VPC CIDR | Local |

GPU 서버의 인터넷 아웃바운드가 필요해지면 퍼블릭 서브넷에 NAT 인스턴스를 구성한 후 다음 경로를 추가한다.

| 목적지 | 대상 |
|---|---|
| `0.0.0.0/0` | NAT 인스턴스 |

## 6. Bastion 구성

### 6.1 Bastion 생성

- 위치: 신규 VPC의 퍼블릭 서브넷
- 이미지: 일반 Ubuntu 이미지
- Public IP: 연결
- GPU: 불필요
- 키페어: 관리자가 보유한 키페어

### 6.2 Bastion 보안그룹

인바운드:

| 프로토콜 | 포트 | 출발지 |
|---|---:|---|
| TCP | 22 | 관리자 공인 IP `/32` |

SSH 22번을 `0.0.0.0/0`에 개방하지 않는다.

### 6.3 GPU 서버 보안그룹

초기 테스트 시 다음 규칙만 허용한다.

| 프로토콜 | 포트 | 출발지 |
|---|---:|---|
| TCP | 22 | Bastion의 사설 IP `/32` 또는 Bastion 보안그룹 |
| TCP | 80 | Bastion의 사설 IP `/32` 또는 테스트 클라이언트 보안그룹 |

`8081`, `19530`, `9000`, `9001`, `9091`은 단일 GPU 서버 내부에서만 사용하므로 외부 인바운드를 허용하지 않는다.

## 7. 기존 GPU 서버 커스텀 이미지 생성

### 7.1 서버 접속

이 절은 이전 당시 원본 서버를 위한 역사적 절차다. 현재 운영 GPU 서버 접속은
다음 Bastion 경유 명령을 사용한다.

```bash
ssh -i Team3-Key.pem \
  -o 'ProxyCommand=ssh -i "Team3-Key.pem" -W %h:%p ubuntu@210.109.55.27' \
  ubuntu@10.30.2.227
```

### 7.2 사전 상태 기록

```bash
date
uptime
df -hT
free -h
nvidia-smi
sudo systemctl status cineverse-api.service --no-pager
sudo systemctl status cineverse-llama.service --no-pager
cd /home/ubuntu/cineverse/milvus
sudo docker-compose ps
curl --fail http://localhost/health
```

점검 결과에 오류가 있다면 이미지 생성 전에 원인을 확인한다. 비정상 상태를 그대로 복제하지 않는다.

### 7.3 FastAPI 중단

새로운 요청과 Milvus 쓰기를 차단하기 위해 API를 가장 먼저 중단한다.

```bash
sudo systemctl stop cineverse-api.service
```

확인:

```bash
sudo systemctl is-active cineverse-api.service
sudo ss -lntp | grep ':80 '
```

정상 결과:

- 서비스 상태: `inactive`
- 포트 80: 출력 없음

### 7.4 llama-server 중단

```bash
sudo systemctl stop cineverse-llama.service
```

확인:

```bash
sudo systemctl is-active cineverse-llama.service
sudo ss -lntp | grep ':8081 '
nvidia-smi
```

정상 결과:

- 서비스 상태: `inactive`
- 포트 8081: 출력 없음
- llama-server의 GPU 메모리 반환

### 7.5 Milvus, etcd, MinIO 중단

```bash
cd /home/ubuntu/cineverse/milvus
sudo docker-compose stop
```

확인:

```bash
sudo docker-compose ps
sudo docker ps
sudo ss -lntp | grep -E ':(19530|9000|9001|9091) '
```

`docker-compose down` 대신 `stop`을 사용한다. `stop`은 기존 컨테이너와 Compose 구성을 보존하므로 복구가 단순하다.

### 7.6 최종 중단 확인

```bash
sudo systemctl is-active cineverse-api.service
sudo systemctl is-active cineverse-llama.service
sudo docker ps
sudo ss -lntp | grep -E ':(80|8081|19530|9000|9001|9091) '
```

모든 대상 서비스가 중단된 것을 확인한 후 카카오클라우드 콘솔에서 기존 GPU 인스턴스를 정지한다.

### 7.7 커스텀 이미지 생성

카카오클라우드 콘솔:

```text
Compute
→ Beyond Compute Service
→ Virtual Machine
→ 인스턴스
→ 기존 GPU 인스턴스의 더보기 메뉴
→ 이미지 생성
```

권장 이름 예시:

```text
cineverse-gpu-before-private-migration-YYYYMMDD
```

이미지 상태가 사용 가능한 상태가 될 때까지 기다린다.

현재 루트 볼륨은 96GB이며, 카카오클라우드의 커스텀 이미지 권장 대상 크기인 1TB 이하에 해당한다.

## 8. 기존 서버 복구

커스텀 이미지 생성이 완료되면 기존 인스턴스를 다시 시작한다.

부팅 후 접속하여 Docker 컨테이너 상태를 확인한다.

```bash
cd /home/ubuntu/cineverse/milvus
sudo docker-compose ps
```

컨테이너가 실행되지 않았다면:

```bash
sudo docker-compose start
```

Milvus 관련 컨테이너가 모두 정상 상태가 된 후 LLM과 API를 시작한다.

```bash
sudo systemctl start cineverse-llama.service
sudo systemctl start cineverse-api.service
```

검증:

```bash
sudo systemctl status cineverse-llama.service --no-pager
sudo systemctl status cineverse-api.service --no-pager
curl --fail http://localhost/health
nvidia-smi
```

두 systemd 서비스는 현재 `enabled` 상태이므로 부팅 시 자동 실행되지만, 실제 상태는 반드시 확인한다.

## 9. 신규 프라이빗 GPU 서버 생성

생성한 커스텀 이미지에서 새 인스턴스를 생성한다.

| 항목 | 설정 |
|---|---|
| VPC | 신규 VPC |
| Subnet | 프라이빗 서브넷 |
| Public IP | 연결하지 않음 |
| 이미지 | 기존 서버에서 생성한 커스텀 이미지 |
| GPU 타입 | 기존과 동일하거나 호환되는 Tesla T4급 |
| 루트 볼륨 | 최소 96GB 이상 |
| 권장 루트 볼륨 | 향후 공간을 고려해 150~200GB |
| 키페어 | Bastion 경유 접속에 사용할 키 |
| 보안그룹 | GPU 서버 전용 보안그룹 |

동일 계정·프로젝트의 커스텀 이미지가 신규 VPC 인스턴스 생성 화면에서 선택되는지 생성 전에 확인한다.

## 10. 신규 GPU 서버 접속

개인키를 Bastion에 복사하지 않고 ProxyJump를 사용한다.

```bash
ssh \
  -i Team3-Key.pem \
  -J ubuntu@BASTION_PUBLIC_IP \
  ubuntu@NEW_GPU_PRIVATE_IP
```

또는 `~/.ssh/config`에 다음과 같이 등록한다.

```sshconfig
Host cineverse-bastion
    HostName BASTION_PUBLIC_IP
    User ubuntu
    IdentityFile /absolute/path/to/Team3-Key.pem

Host cineverse-private-gpu
    HostName NEW_GPU_PRIVATE_IP
    User ubuntu
    IdentityFile /absolute/path/to/Team3-Key.pem
    ProxyJump cineverse-bastion
```

접속:

```bash
ssh cineverse-private-gpu
```

## 11. 신규 서버 검증

### 11.1 OS 및 자원

```bash
hostname
date
uptime
cat /etc/os-release
lscpu
free -h
df -hT
df -ih
```

확인 항목:

- Ubuntu 정상 부팅
- CPU 및 메모리 사양
- 루트 볼륨 크기
- 파일시스템 오류 여부
- 기존 프로젝트 파일 존재 여부

### 11.2 GPU

```bash
nvidia-smi
```

확인 항목:

- Tesla T4 인식
- NVIDIA 드라이버 정상
- ECC 오류 없음
- Xid 오류 없음
- 온도 및 전력 상태 정상

커널 GPU 오류 확인:

```bash
sudo journalctl -k --no-pager | grep -iE 'NVRM|Xid'
```

### 11.3 프로젝트 파일

```bash
sudo du -sh /home/ubuntu/cineverse
ls -lh /home/ubuntu/cineverse/gemma4-cineverse-v2.gguf
ls -la /home/ubuntu/cineverse
```

기존 서버에서 확인된 프로젝트 용량은 약 26GB이며, 서비스 모델은 약 7.95GB다.

### 11.4 Docker와 Milvus

```bash
cd /home/ubuntu/cineverse/milvus
sudo docker-compose ps
```

필요한 경우:

```bash
sudo docker-compose start
```

다음 컨테이너가 정상이어야 한다.

- `milvus-standalone`
- `milvus-etcd`
- `milvus-minio`

포트 확인:

```bash
sudo ss -lntp | grep -E ':(19530|9000|9001|9091) '
```

Milvus 컬렉션과 엔터티 수는 기존 서버와 비교해야 한다. 단순히 컨테이너가 `healthy`라고 표시되는 것만으로 데이터 복제를 확정하지 않는다.

### 11.5 llama-server와 API

```bash
sudo systemctl status cineverse-llama.service --no-pager
sudo systemctl status cineverse-api.service --no-pager
```

필요한 경우:

```bash
sudo systemctl start cineverse-llama.service
sudo systemctl start cineverse-api.service
```

포트 확인:

```bash
sudo ss -lntp | grep -E ':(80|8081) '
```

헬스 체크:

```bash
curl --fail http://localhost/health
```

### 11.6 API 기능 테스트

최소한 다음 기능을 기존 서버와 신규 서버에서 동일한 요청으로 비교한다.

- `/health`
- `/chat/auto`
- `/recommend`
- `/chat/group`
- `/chat/group/rounds`
- `/chat/group/auto`

비교 항목:

- HTTP 상태 코드
- 응답 JSON 스키마
- 캐릭터 이름과 별칭 처리
- 영화 목록 반환
- Milvus 검색 정상 여부
- 오류 로그 발생 여부

### 11.7 성능 기준

기존 서버에서 관찰된 참고값:

| 항목 | 기존 서버 참고값 |
|---|---|
| 모델 생성 속도 | 약 9.8~10.8 tokens/s |
| 최근 요청 처리 시간 | 약 4.5~6.9초 |
| 유휴 GPU 온도 | 약 49°C |
| 서비스 실행 중 GPU 메모리 | 약 12.8GB |
| ECC/Xid 오류 | 없음 |
| GPU 스로틀 | 없음 |

신규 서버에서 다음을 측정한다.

- 단일 요청의 첫 응답 시간
- 전체 응답 시간
- tokens/s
- 동시 요청 2개와 5개의 응답 시간
- GPU 사용률
- GPU 메모리
- 온도
- 오류 및 요청 실패율

GPU 사용률이 생성 중 72~100%인 것만으로 장애는 아니다. 온도, 스로틀, CUDA OOM, Xid 오류 및 요청 지연을 함께 판단한다.

## 12. NAT 추가 판단

다음 명령이 필요한데 실패한다면 NAT 아웃바운드 경로가 필요한지 확인한다.

```bash
sudo apt update
docker pull IMAGE_NAME
pip install PACKAGE_NAME
git fetch
curl https://example.com
```

NAT를 추가할 경우:

1. 퍼블릭 서브넷에 NAT 인스턴스 생성
2. Public IP 연결
3. IP forwarding 및 SNAT 설정
4. 프라이빗 라우팅 테이블에 `0.0.0.0/0 → NAT 인스턴스` 추가
5. GPU 서버에서 외부 IP 및 DNS 통신 확인

NAT는 외부에서 GPU 서버로 SSH 접속하기 위한 장치가 아니다.

## 13. 전환

신규 서버 검증이 끝난 후 실제 백엔드 또는 호출 주체의 AI API 목적지를 신규 GPU 서버의 사설 IP로 변경한다.

권장 전환 순서:

1. 신규 서버 최종 헬스 체크
2. 신규 서버 로그 모니터링 시작
3. 테스트 클라이언트만 신규 서버로 연결
4. 실제 백엔드 연결 대상 변경
5. `/health`, 채팅, 추천 기능 재검증
6. 오류율과 응답시간 관찰
7. 안정화 기간 동안 기존 서버 유지

신규 VPC에 백엔드가 아직 없다면, 초기 테스트는 Bastion에서 신규 GPU 서버의 사설 IP로 직접 호출할 수 있다.

```bash
curl http://NEW_GPU_PRIVATE_IP/health
```

## 14. 롤백

신규 서버에서 다음 문제가 발생하면 기존 서버로 즉시 되돌린다.

- GPU 또는 드라이버 미인식
- Milvus 데이터 누락
- 모델 로딩 실패
- API 오류 증가
- 기존 대비 심각한 성능 저하
- 네트워크 연결 실패

롤백 절차:

1. 백엔드의 AI API 목적지를 기존 서버 주소로 복구
2. 기존 서버 `/health` 확인
3. 기존 서버에서 대표 채팅·추천 요청 확인
4. 신규 서버로의 요청 중단
5. 신규 서버 로그와 설정 분석

신규 서버 문제를 해결하기 전까지 기존 서버와 커스텀 이미지를 삭제하지 않는다.

## 15. 최종 체크리스트

### 네트워크

- [ ] 신규 VPC CIDR이 기존 네트워크와 겹치지 않음
- [ ] 퍼블릭·프라이빗 서브넷 생성
- [ ] Internet Gateway 연결
- [ ] 퍼블릭 라우팅 테이블 연결
- [ ] Bastion Public IP 연결
- [ ] Bastion SSH를 관리자 IP `/32`로 제한
- [ ] GPU 서버 SSH를 Bastion에서만 허용
- [ ] GPU 서버에 Public IP를 연결하지 않음

### 이미지 및 이전

- [ ] 기존 서버 상태 기록
- [ ] FastAPI 중단
- [ ] llama-server 중단
- [ ] Milvus·etcd·MinIO 정상 중단
- [ ] 기존 인스턴스 정지
- [ ] 커스텀 이미지 생성 완료
- [ ] 기존 서버 재가동 및 정상 확인
- [ ] 신규 프라이빗 GPU 서버 생성

### 검증

- [ ] Bastion 경유 SSH 성공
- [ ] OS·CPU·메모리·디스크 정상
- [ ] NVIDIA GPU와 드라이버 정상
- [ ] 프로젝트와 모델 파일 존재
- [ ] Milvus 컨테이너 정상
- [ ] Milvus 데이터 건수 일치
- [ ] llama-server 정상
- [ ] FastAPI 정상
- [ ] `/health` 정상
- [ ] 채팅·추천·그룹 채팅 정상
- [ ] 기존 서버 대비 성능 비교 완료
- [ ] 오류·OOM·Xid·스로틀 없음

### 전환과 롤백

- [ ] 테스트 트래픽 전환
- [ ] 실제 백엔드 연결 전환
- [ ] 안정화 기간 모니터링
- [ ] 기존 서버 유지
- [ ] 롤백 경로 확인

## 16. 카카오클라우드 공식 참고자료

- [이미지 생성 및 관리](https://docs.kakaocloud.com/service/bcs/vm/how-to-guides/vm-manage-image)
- [인스턴스 생성 및 연결](https://docs.kakaocloud.com/service/bcs/vm/how-to-guides/vm-create-instance)
- [인스턴스 관리](https://docs.kakaocloud.com/en/service/bcs/vm/how-to-guides/vm-manage-instance)
- [서브넷](https://docs.kakaocloud.com/en/service/networking/vpc/main/vpc-subnet)
- [라우팅 테이블](https://docs.kakaocloud.com/en/service/networking/vpc/main/vpc-route-table)
- [Internet Gateway](https://docs.kakaocloud.com/en/service/networking/vpc/main/vpc-internet-gateway)
- [NAT 인스턴스 사용](https://docs.kakaocloud.com/en/service/networking/vpc/how-to-guides/vpc-appx-1)
- [프라이빗 서브넷 네트워크 구성](https://docs.kakaocloud.com/tutorial/networking-content-delivery/private-subnet)

---

최초 작성 기준일: 2026-07-29
운영 상태 갱신일: 2026-08-11
대상: KakaoCloud Musubi GPU 서버
주의: 이 문서는 현재 확인된 서버 구성을 기준으로 작성되었다. 실제 이전 전에 콘솔의 인스턴스 유형, GPU 가용 수량, 커스텀 이미지 선택 가능 여부와 네트워크 CIDR을 다시 확인한다.
