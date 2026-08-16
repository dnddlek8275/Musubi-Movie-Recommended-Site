# AI 운영 카나리 배포 결과 (2026-08-16)

## 배포 대상

- 운영 GPU 서버: `host-10-30-2-227`
- 모델: `gemma-4-12b-it-base-q4_k_m.gguf`
- 모델 크기: `7,381,383,392 bytes`
- 모델 SHA-256: `9808e158b9092505fd072c33813961ffab6a5c98f2f804815ec5e2b7d64bf1a4`
- 런타임 후보: 17개 파일
- 런타임 압축본 SHA-256: `205f24275a0a24390b902e64bf55a81363cd8927add06a6cab5e5ad73518cd39`

## 적용 내용

- 기존 모델 파일은 롤백용으로 유지했다.
- 새 모델은 별도 파일명으로 전송한 뒤 운영 서버에서 SHA-256을 재검증했다.
- 검증된 런타임 17개 파일을 한 변경 세트로 반영했다.
- `cineverse-llama.service`의 모델 경로를 새 모델로 변경했다.
- `--skip-chat-parsing` 옵션을 제거했다.
- LLM 헬스 확인 후 AI API를 기동했다.

## 롤백 자료

- 운영 서버 백업: `/home/ubuntu/cineverse-backups/ai-canary-20260816-062812`
- 백업 내용: 기존 런타임, 기존 systemd unit, 기존 모델 SHA-256, 운영 카나리 결과
- 기존 모델은 `/home/ubuntu/cineverse/gemma4-cineverse-v2.gguf`에 유지했다.

## 운영 카나리 결과

- 핵심 실제 API 케이스: `7/7` 통과
- hard check pass rate: `1.0`
- critical failure: `0`
- HTTP 오류: `0`
- 빈 응답: `0`
- 동일 답변: `0`
- 내부 프로필 노출: 원문 검토에서 발견되지 않음
- 공격적 갈등 조장 또는 상대 고의성 단정: 원문 검토에서 발견되지 않음
- 결과 파일: `production_canary_20260816.json`

평가 결과의 `release_gate_passed=false`는 새 운영 결과 파일에 수동 평가 완료 값을 자동으로 기록하지 않는 평가기 동작 때문이다. 자동 게이트는 통과했으며, 7개 답변 원문을 별도로 검토했다.

## 배포 후 상태

- `cineverse-llama.service`: active
- `cineverse-api.service`: active
- AI API health: ok
- LLM health: ok
- Milvus: ok (8 collections)
- etcd, MinIO, Milvus 컨테이너: healthy
- 런타임 17개 파일의 스테이징/운영 SHA-256 불일치: 0
- GPU: Tesla T4, 모델·API 합계 약 12.4 GiB 사용
- 루트 디스크: 55% 사용
- 시스템 RAM: 62 GiB 중 약 11 GiB 사용, 약 51 GiB available
- 배포 시점 systemd warning 이상 로그: 없음

llama.cpp 로그에는 SWA/컨텍스트 체크포인트 캐시 재처리에 관한 경고가 일부 기록됐다. 요청 실패나 서비스 오류가 아니라 캐시를 무효화하고 전체 프롬프트를 다시 처리했다는 런타임 경고이며, 카나리 7건의 응답 성공 여부에는 영향을 주지 않았다.
