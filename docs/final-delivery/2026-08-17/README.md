# Musubi 발표용 최신 자료 — 2026-08-17

이 폴더는 2026-08-17 기준으로 갱신한 발표 준비용 산출물이다.

## 이번에 신규·갱신한 문서

- `Musubi_클라우드아키텍처_최신.docx`
  - 현재 운영 인스턴스·서브넷·트래픽 경로
  - 단일 T4 병목 측정 결과
  - 2026-08-18 GPU VM 2대 및 Internal AI Gateway/LB 확장 계획
  - 당일 실행·검증·롤백 순서와 미확정 입력값
- `Musubi_AI_변경사항_최신.docx`
  - 현재 운영 모델과 llama.cpp 기준
  - 캐릭터·일반 대화·추천·검색 파이프라인 변경
  - 회귀·스모크·부하 검증 결과
  - 이번 소스 배포 범위와 알려진 한계

## 기존 최종 산출물

WBS, IA, 요구사항정의서, 기획서, 기능정의서, 화면설계서는
`docs/final-delivery/2026-08-14/`의 최종본을 기준으로 사용한다. 이번 작업에서는
확인되지 않은 기능·화면을 임의로 추가하지 않았으며, 변경이 확인된 클라우드와 AI
자료만 2026-08-17 버전으로 분리했다.

## 원본 근거

- `docs/current/infra/cloud-architecture-expansion-20260818.md`
- `docs/current/infra/ai-capacity-and-scaling.md`
- `AI/eval/AI_CHANGELOG_20260817.md`
- `AI/eval/PREDEPLOY_VERIFICATION_20260816.md`
- `AI/eval/PRODUCTION_CANARY_DEPLOYMENT_20260816.md`

## 배포 기록

Git 커밋, 이미지 태그, Kubernetes rollout, AI API 스모크 결과는 실제 배포 완료 후
이 섹션에 확정값으로 기록한다.
