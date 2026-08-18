# 운영 모니터링 및 알림

## 현재 적용 범위

공개 서비스는 GitHub Actions `Production Health`가 10분 주기로 확인한다.
점검 실패는 GitHub Actions 실패 기록과 계정 알림으로 확인한다. 예약 workflow
알림을 받을 사용자는 GitHub Actions 웹/이메일 알림을 활성화해야 한다. 예약
실행은 지연될 수 있으므로 이는 초기 synthetic monitor로 사용한다. Kubernetes의
liveness/readiness probe, HPA, ALB health check는 각각 Pod 복구, 확장, 트래픽
대상 제외를 담당하지만 담당자에게 장애 알림을 보내는 기능은 별도다.

GPU VM에는 2026-08-11 KakaoCloud Monitoring Agent 1.1.0과 1분 주기의
`cineverse-gpu-watchdog.timer`를 적용했다. Agent가 CPU·메모리·디스크·네트워크와
NVIDIA SMI 메트릭을 전송하며, watchdog 로그는
`/var/log/cineverse/gpu-monitor.log`에서 수집한다. 장애 알림은 카카오클라우드
Alert Center를 거치지 않고 watchdog이 Slack Incoming Webhook으로 직접 전송한다.
상세 기준과 요금제 산정 절차는 `gpu-monitoring-and-pricing.md`를 따른다.

## 권장 알림 경로

1. GPU watchdog → Slack Incoming Webhook: GPU VM 장애의 기본 수신 경로
2. GitHub Actions 알림: 공개 서비스 주기 점검 실패 확인
3. 이메일: 채널 알림 누락에 대비한 보조 수신처와 주간 보고
4. Alert Center/전화 호출 서비스: 운영 기간과 당직 체계가 확대될 때 추가

현재 프로젝트 운영 기간과 규모에서는 별도 Alert Center 정책을 만들지 않고
watchdog의 직접 Slack 전송을 사용한다. Webhook은 Git에 저장하지 않으며 GPU VM의
root 전용 파일 `/etc/cineverse/gpu-watchdog.env`에 권한 `0600`으로 보관한다.
같은 장애는 최초 감지 시 한 번만 알리고, 정상 전환 시 복구 알림을 보낸다.

## 심각도 기준

| 단계 | 조건 | 처리 |
|---|---|---|
| 긴급 | Frontend, Backend ready, DB 연결이 연속 실패 | 운영 채널 즉시 알림 |
| 높음 | AI health 연속 실패 | 운영 채널 알림, 일반 API와 분리 확인 |
| 높음 | DB 백업 service 실패 또는 26시간 이상 성공 기록 없음 | 운영 채널과 이메일 알림 |
| 주의 | TLS 인증서 만료 14일 미만 | 운영 채널과 이메일 알림 |
| 정보 | 일시적 1회 실패 후 재시도 성공 | 기록만 유지 |

헬스 체크는 AI 추론을 실행하지 않는 `/api/ai-health`만 호출한다. 실제 사용자
대화 품질과 답변 지연시간은 별도의 synthetic test가 필요하며 현재 범위에는
포함하지 않는다.

## 현재 연동 및 향후 개선

- 2026-08-11 Slack Webhook 형식 검증 및 실제 테스트 전송 완료
- GPU watchdog Slack 직접 전송 적용 완료
- Webhook 교체 시 `/etc/cineverse/gpu-watchdog.env`만 갱신
- 향후 장기 운영 시 Alert Center 및 보조 이메일 수신처 추가 검토

GitHub Actions 실패 알림과 DB VM의 `cineverse-db-backup.service` 실패 알림은
아직 같은 Slack 채널에 연결하지 않았다. 장기 운영 전 이 두 경로를 추가한다.

## 멀티 AZ 확장 후 추가 감시 항목 (최종 목표)

- KKE Worker 4대의 AZ별 Ready 상태와 Pod 분산 여부
- Public LB A/B 및 Internal AI LB A/B 대상의 Healthy 상태
- GPU-A/B의 모델 체크섬, AI API health, GPU 메모리와 응답 지연
- PostgreSQL Primary/Standby replication 상태와 replication lag
- NAT+Bastion-A/B의 IP forwarding, NAT 규칙, 외부 연결 상태
- 단일 AZ 장애 모의 시 공개 서비스, AI 요청, DB 쓰기 경로의 생존 여부

별도 Ops VM은 추가하지 않고 모니터링 워크로드는 Kubernetes에서 운영한다.
