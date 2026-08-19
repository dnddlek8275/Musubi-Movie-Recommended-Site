# Musubi 발표용 최신 자료 — 2026-08-19 검증

폴더명은 최초 산출일인 2026-08-17을 유지하며, 아래 두 문서는
2026-08-19 운영 상태와 검증 결과를 반영해 갱신했다.

## 이번에 신규·갱신한 문서

- `Musubi_클라우드아키텍처_최신.docx`
  - 현재 운영 인스턴스·서브넷·트래픽 경로
  - 멀티 AZ 10 VM 및 이중 로드 밸런서 구성 완료 상태
  - KKE·GPU·PostgreSQL Primary–Standby 검증 결과
  - 운영 점검·검증·롤백 절차
- `Musubi_AI_변경사항_최신.docx`
  - 현재 운영 모델·llama.cpp·이중 GPU 기준
  - 캐릭터·일반 대화·추천·검색 파이프라인 변경
  - 회귀·스모크·부하 검증 결과
  - 2026-08-19 GPU-B → GPU-A 롤링 배포 범위와 알려진 한계

## 기존 최종 산출물

WBS, IA, 요구사항정의서, 기획서, 기능정의서, 화면설계서는
`Infra/project-docs/final-delivery/2026-08-14/`의 최종본을 기준으로 사용한다. 이번 작업에서는
확인되지 않은 기능·화면을 임의로 추가하지 않았으며, 변경이 확인된 클라우드와 AI
자료만 2026-08-17 버전으로 분리했다.

## 원본 근거

- `Infra/project-docs/current/infra/multi-az-architecture.md`
- `Infra/project-docs/current/infra/cloud-architecture-expansion-20260818.md`
- `Infra/project-docs/current/infra/ai-capacity-and-scaling.md`
- `AI/eval/AI_CHANGELOG_20260817.md`
- `AI/eval/PREDEPLOY_VERIFICATION_20260816.md`
- `AI/eval/PRODUCTION_CANARY_DEPLOYMENT_20260816.md`
- `AI/eval/ITERATIVE_REFINEMENT_20260818.md`

## 최종 확인 기록

- GitHub `main`: `54ef57fa1f04b07fc47d1d3c813b071f367f6ba7`
- 인프라: 멀티 AZ 10 VM, Public/AI HA, PostgreSQL Primary–Standby 구성 완료
- AI: GPU-B → GPU-A 순서로 런타임 10개 파일 롤링 배포 완료
- AI 검증: 432 tests + 108 subtests 통과, 양쪽 서비스 health 및 추천 스모크 확인
- 미확인: 해당 배포 세션에서 운영 Kubernetes의 `AI_BASE_URL` 실적용 여부
