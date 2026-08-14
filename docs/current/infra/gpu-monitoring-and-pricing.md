# GPU 모니터링 및 AI 요금제 산정

작성일: 2026-08-11

## 결정 사항

- GPU 인스턴스 유형은 `gn1i.4xlarge`로 확정한다.
- 운영 장애 알림 수신 채널은 Slack Webhook으로 구성한다.
- 단일 Tesla T4 GPU 서버를 기준으로 무제한 AI 요금제는 제공하지 않는다.
- 사용자에게는 토큰 수 대신 완료된 AI 답변 횟수를 크레딧으로 표시한다.
- 실패, 타임아웃, 취소된 요청은 유료 크레딧에서 차감하지 않는다.
- 비회원 일일 제한은 유지하고, 회원 한도와 유료 가격은 운영 계측 이후 확정한다.
- GPU 사용률 100%만으로 장애를 판정하지 않는다. 대기시간, 응답시간, 온도,
  VRAM, Xid/ECC/CUDA OOM을 함께 판단한다.

## 현재 적용된 GPU 서버 모니터링

GPU VM `10.30.2.227`에 다음 구성이 적용되어 있다.

- KakaoCloud Monitoring Agent `1.1.0`
  - systemd unit: `kic_monitor_agent.service`
  - 부팅 시 자동 시작
  - CPU, 메모리, 디스크, 네트워크, NVIDIA SMI 메트릭 수집
  - Monitoring endpoint로 메트릭 전송 확인
- CineVerse GPU watchdog
  - systemd timer: `cineverse-gpu-watchdog.timer`
  - 실행 주기: 1분
  - 실행 파일: `/usr/local/sbin/cineverse-gpu-watchdog`
  - 로그: `/var/log/cineverse/gpu-monitor.log`
  - 로그 보존: 일 단위 회전, 14개 압축 보존
  - 장애 및 복구 알림: Slack Incoming Webhook 직접 전송
  - 동일 장애 중복 전송 방지: `/var/lib/cineverse-gpu-watchdog/alerts`
  - Webhook 보관: `/etc/cineverse/gpu-watchdog.env` (`root:root`, `0600`)

watchdog는 다음을 검사한다.

- `cineverse-api.service`, `cineverse-llama.service` 실행 상태
- GPU 사용률, VRAM, 온도, 전력
- GPU Xid, uncorrected volatile ECC 증가
- AI 서비스 로그의 CUDA OOM
- 루트 디스크 사용률
- AI 요청 수, 대기열 거절·타임아웃, 최대 대기시간과 처리시간

동시 요청 보호 정책과 다중 GPU 발전 방향은
`ai-capacity-and-scaling.md`에 기록한다.

배포 파일은 다음 위치에 보관한다.

- `Infra/scripts/cineverse-gpu-watchdog`
- `Infra/systemd/cineverse-gpu-watchdog.service`
- `Infra/systemd/cineverse-gpu-watchdog.timer`
- `Infra/systemd/cineverse-gpu-watchdog.logrotate`

## Slack 직접 알림 정책

카카오클라우드 Alert Center는 현재 사용하지 않는다. watchdog이 다음 이벤트를
감지하면 Slack으로 직접 전송하고, 상태가 정상으로 돌아오면 복구 알림을 전송한다.

| 심각도 | 조건 | 감지 방식 |
|---|---|---|
| 긴급 | `GPU_UNAVAILABLE` | GPU watchdog 로그 |
| 긴급 | `AI_API_DOWN` 또는 `LLAMA_SERVER_DOWN` | GPU watchdog 로그 |
| 긴급 | `GPU_XID`, `GPU_ECC_UNCORRECTED`, `CUDA_OOM` | GPU watchdog 로그 |
| 긴급 | `ROOT_DISK_CRITICAL` | GPU watchdog 로그 |
| 주의 | `GPU_TEMPERATURE_WARNING`, `GPU_VRAM_HIGH` | GPU watchdog 로그 |
| 주의 | `ROOT_DISK_WARNING` | GPU watchdog 로그 |
| 주의 | `AI_QUEUE_REJECTIONS`, `AI_QUEUE_WAIT_HIGH`, `AI_RESPONSE_SLOW` | AI admission 로그 |
| 긴급 | `AI_QUEUE_TIMEOUTS`, `AI_REQUEST_ERRORS` | AI admission 로그 |
| 긴급 | Frontend, Backend, DB, AI health 연속 실패 | Production Health(현재 Slack 미연결) |

같은 이벤트가 매분 반복되더라도 활성 상태 파일이 존재하는 동안에는 Slack을
다시 보내지 않는다. Slack 전송에 실패하면 활성 상태를 확정하지 않아 다음 실행에서
재시도한다. 2026-08-11 실제 Webhook 테스트 전송과 정상 주기 실행을 확인했다.

## AI 사용량 계측 설계

Backend에는 `ai_usage_events` 테이블과 ASGI middleware를 추가한다. 사용자에게
노출되는 다음 POST 요청만 기록한다.

- `/chat/auto`: `general_chat`
- `/chat/character`: `character_chat`
- `/chat/group`: `group_chat`
- `/chat/rooms/{room_id}/messages`: `chat_continue`

저장 항목은 사용자 ID, 요청 종류, 성공 상태, HTTP 상태, 최초 응답시간, 전체
응답시간, 응답 바이트, 시작·종료 시각이다. 사용자 계정 삭제 시 해당 사용자의
계측 데이터도 함께 삭제되도록 FK CASCADE를 사용한다. 계측 DB 저장 실패는 실제
채팅 응답에 영향을 주지 않는다.

현재 구현 파일은 다음과 같다.

- `Backend/app/models/ai_usage.py`
- `Backend/app/services/ai_usage_service.py`
- `Backend/alembic/versions/20260811_0033_create_ai_usage_events.py`

### V1 배포 결과

2026-08-11 V1 릴리스에서 migration Job으로 운영 DB를
`20260808_0026`에서 `20260811_0033`으로 올리고 Backend를 롤링 배포했다.
`ai_usage_events` 테이블 생성과 계측 저장을 확인했으며, 확인 시점에 성공·실패를
포함한 이벤트 9건이 저장돼 있었다. 계측 저장 실패가 실제 채팅 응답을 실패시키지
않는 기존 정책은 유지한다.

운영 이미지는 Git commit SHA `2765f04a4d8d0345996d0b4b2fb18961dce8639a`를
사용한다. 배포 직후 Backend·Frontend rollout, DB·AI health, 랭킹·검색·추천 API,
Pod 재시작과 Warning 이벤트를 확인했고 차단 오류는 없었다.

## 요금제 산정 절차

KakaoCloud 공식 요금표 기준 `gn1i.4xlarge`는 T4 1개, vCPU 16개,
메모리 64GiB 구성이며 시간당 1,272원, 30일 월간 915,840원이다. VAT, 루트
볼륨, 추가 볼륨, 아웃바운드 트래픽 등은 별도다. 14일 연속 실행 시 GPU
인스턴스 본체 비용은 427,392원(VAT 별도)으로 계산한다. 실제 정산에는 Billing의
예상 청구 금액과 프로젝트 크레딧 적용 여부를 사용하며 임의 가격은 사용하지
않는다.

위 사양과 가격은 2026-08-11
[KakaoCloud Virtual Machine 요금표](https://kakaocloud.com/services/virtual-machine/pricing)와
[GPU 인스턴스 사양](https://docs.kakaocloud.com/service/bcs/bcs-specifications/accelerated-computing/gpu-instance)에서
재확인했다. 이후 가격 산정 시에는 같은 공식 페이지와 실제 Billing을 다시 확인한다.

```text
월 AI 고정비
= GPU 인스턴스 915,840원 + GPU 볼륨 + AI 네트워크 + AI 백업 비용
  + 공용 DB/Kubernetes/Load Balancer 비용 중 AI 배분액

안전 월 처리량
= 부하 테스트에서 SLO를 만족하는 시간당 성공 응답 수
  × 월 가동시간 × 0.6

AI 답변 1회 원가 하한
= 월 AI 고정비 ÷ 안전 월 처리량
```

가격 결정에는 위 원가 하한과 예상 실제 사용량 기준 손익분기 원가 중 더 큰 값을
사용한다. 최소 3일, 권장 7일 동안 다음 값을 수집한 후 한도를 확정한다.

GPU 인스턴스 본체 비용만 단순 배분한 참고값은 다음과 같다. 볼륨, 공용 인프라,
트래픽, VAT, 결제 수수료와 운영 여유분은 포함하지 않은 값이므로 실제 상품
원가는 이보다 높다.

| 월 성공 AI 답변 수 | GPU 본체 기준 답변 1회 비용 |
|---:|---:|
| 1,000건 | 915.84원 |
| 5,000건 | 183.17원 |
| 10,000건 | 91.58원 |
| 20,000건 | 45.79원 |

- 비회원·회원별 성공 AI 요청 수
- 요청 유형별 p50/p95 최초 응답시간과 전체 응답시간
- 시간대별 동시 요청 및 오류율
- GPU 95% 이상 지속 시간과 VRAM 추이
- CUDA OOM, Xid, ECC 발생 여부
- 예상 청구 금액과 GPU 리소스 비용 비중

## 초기 상품 정책

- 비회원: 현재 일일 제한 유지
- 무료 회원: 운영 측정 후 일일 횟수 확정, 무제한 금지
- 유료 회원: 월간 완료 답변 크레딧 방식
- 추가 사용: 별도 크레딧 또는 다음 결제 주기 초기화
- 관리자·부하 테스트: 일반 사용자 과금 통계와 분리
- 실패·타임아웃·취소: 크레딧 미차감

현재 회원 요청 제한과 결제 기능은 적용하지 않는다. 계측 결과와 카카오클라우드
Billing 데이터를 검토한 뒤 정책, 한도, 가격을 확정한다.
