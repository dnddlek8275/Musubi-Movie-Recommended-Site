# Musubi AI 운영 변경사항

기준일: 2026-08-17

## 1. 운영 기준 모델과 런타임

| 항목 | 운영 기준 |
|---|---|
| 베이스 모델 | Gemma 4 12B IT |
| GGUF | `gemma-4-12b-it-base-q4_k_m.gguf` |
| 모델 SHA-256 | `9808e158b9092505fd072c33813961ffab6a5c98f2f804815ec5e2b7d64bf1a4` |
| llama.cpp | build 9776, commit `ac4105d68b2955027115cf9bb50941ccf56974eb` |
| 실행 옵션 | `--ctx-size 20480`, `-np 5`, `--reasoning-budget 0`, GPU offload |
| 금지 옵션 | `--skip-chat-parsing` |
| 영화 컬렉션 | `movies_active` |
| 캐릭터 컬렉션 | `characters_verified_v5` |

기존 LoRA 병합 GGUF 대신 순수 베이스 Q4_K_M 후보와 새 파이프라인을 하나의
변경 세트로 검증했다. 배포 전 255/255 회귀 테스트와 실제 API 스모크 7/7이
통과했고, 2026-08-16 운영 카나리에서 모델과 런타임 교체를 완료했다.

## 2. 파이프라인 개선

### 캐릭터 대화

- 50명별 프로필 예시와 고유 실용문장 fallback으로 말투 평준화를 줄였다.
- 비밀·물건·면접·발표 등 다중 턴 문맥을 유지한다.
- 공백 없는 캐릭터 이름과 실제 사용자식 오타·축약을 정규화한다.
- 상대의 고의·속마음·경멸을 근거 없이 단정하는 표현을 차단한다.
- 욕설, 위협, 상대를 당황시키라는 조언을 제한한다.
- 경청 요청에는 질문·조언이 섞이지 않도록 검증한다.
- 검증된 캐릭터 관계·소품·사건만 결정적 응답에 사용한다.
- 검증 관계 JSON을 결정형 사전응답 로더에 연결해 Milvus 검색 결과와 무관하게
  명시적인 관계 질문에는 확인된 답을 반환한다.
- 일반 응답과 스트리밍 응답에 같은 캐릭터 보호 규칙을 적용한다.

### 일반 대화와 영화 추천

- 책·음악·맛집·게임·웹툰·여행 요청을 영화 추천으로 오분류하지 않는다.
- `오늘 뭐 볼까?`처럼 조건이 없는 짧은 요청은 불필요한 재작성 LLM을 생략한다.
- 구조화 추천 카드의 순번, 줄거리, 후속 비교를 기존 카드 데이터로 처리한다.
- 카드에 없는 줄거리를 생성하지 않고, 정보가 없음을 명시한다.
- 첫 추천 이후에도 구조화 영화 카드를 유지한다.
- 한국어 목적격 조사 `을/를`을 종성에 맞게 생성한다.

### 검색과 재정렬

- 장르·배우·감독·언어·연도·평점처럼 필드로 검증된 조건 검색은 CrossEncoder를
  생략한다.
- 일반 자연어 검색은 상위 12개 후보를 재정렬한다.
- 분위기·자유 주제·개인화 복합 요청은 최대 18개 후보를 재정렬한다.
- confidence 임계값은 평가 데이터가 부족해 아직 도입하지 않았다.

### 성능과 관측

- LLM 호출마다 prompt/output token, 프롬프트 처리시간, 생성시간, token/s와
  전체 시간을 `[LLMTiming]` JSON 로그로 기록한다.
- 일반 추천 출력은 2~3문장, 최대 150 생성 토큰으로 제한한다.
- llama-server 재시작 후 5개 슬롯을 프리워밍하는 도구를 추가했다.
- admission queue와 Slack watchdog으로 429, 503, 5xx, 대기·처리 지연을 감시한다.

## 3. 검증 결과

| 검증 | 결과 |
|---|---:|
| 50명 × 3상황 × 3턴 캐릭터 평가 | 450/450 통과 |
| 유사도 0.90 이상 캐릭터 답변 | 86쌍 → 0쌍 |
| 실사용자형 강건성 평가 | 15/15 통과 |
| 배포 전 최신 회귀 테스트 | 255/255 통과 |
| 배포 전 실제 API 스모크 | 7/7 통과 |
| 2026-08-17 로컬 전체 회귀 테스트 | 290/290 통과 |

2026-08-17 운영 지연 최적화 후 단일 추천은 7.719초에서 6.494초로
15.9% 감소했고, 5개 동시 요청 p95는 21.555초에서 19.103초로 11.4%
감소했다. 조건 검색 카나리에서는 CrossEncoder 생략 경로의 검색 시간이
0.273초였다.

## 4. 이번 배포 대상

이번 배포에서는 모델 파일과 llama-server 실행 옵션을 변경하지 않고, 검증된
AI API·파이프라인·검색 정책·캐릭터 지식 소스만 반영한다.

- API: `AI/api/main.py`
- LLM client: `AI/llm/client.py`
- Pipeline: character, movie, intent, query rewrite, recommendation context/presenter,
  general prompt, retrieval policy, tone preset
- RAG: movie retriever, character knowledge와 검증 지식 JSON
- 운영 도구: llama 슬롯 프리워밍

`AI/eval/**`, `AI/tests/**`, `AI/train/**`, 모델 파일, `.env`, Milvus 볼륨,
로그와 로컬 아카이브는 운영 배포 대상이 아니다.

2026-08-17 운영 서버에는 로컬과 해시가 달랐던 런타임 8개 파일만 소스 단위로
백업 후 반영했다. 첫 카나리에서 우디–버즈 관계 JSON이 결정형 로더에 연결되지
않은 문제가 확인돼 로더와 캐릭터 파이프라인 2개 파일을 추가 반영했다. 이후
우디–버즈와 마석도–장첸 관계 카나리가 모두 통과했고 `/health`의 LLM·Milvus·
embedder가 모두 `ok`임을 확인했다. 모델 파일과 llama-server는 변경하지 않았다.

## 5. 알려진 한계

- 단일 Tesla T4에서 동시 생성 시 token/s가 요청별 5.27~9.33까지 낮아졌다.
- 10개 동시 추천 요청 p95는 41.520초였고, 20개 이상에서는 admission 한도에
  따라 429/503이 발생했다.
- 캐릭터 원작 지식은 검증된 내부 데이터 범위까지만 답할 수 있다.
- confidence 기반 CrossEncoder 분기는 실제 평가 데이터 축적 후 도입한다.
- 운영 트래픽의 장기간 A/B 결과는 아직 없다.

## 6. 배포 후 합격 조건과 롤백

합격 조건:

- AI API와 llama-server가 `active`
- `/health`의 LLM·Milvus·embedder가 `ok`
- 핵심 일반 대화·추천·캐릭터 요청에서 HTTP 5xx와 빈 답변 0건
- 내부 프로필 노출, 공격적 표현, 관계 환각 없음
- 추천 카드와 후속 질문 문맥 유지

롤백 조건:

- HTTP 5xx 또는 빈 답변 반복
- 내부 프로필 또는 시스템 지침 노출
- 영화 카드 응답 파손
- 관계 검색 실패, 욕설·위협·고의성 단정 재발
- 기존 운영 대비 명확한 지연·오류율 악화

## 7. 근거 문서

- `AI/eval/PREDEPLOY_VERIFICATION_20260816.md`
- `AI/eval/REPLACEMENT_DECISION_20260816.md`
- `AI/eval/PRODUCTION_CANARY_DEPLOYMENT_20260816.md`
- `AI/eval/GENERAL_CHAT_REGRESSION_PROBE_20260817.md`
- `AI/eval/CHARACTER_STREAM_PARITY_PROBE_20260817.md`
- `AI/eval/CHARACTER_KNOWLEDGE_PROBE_20260817.md`
- `docs/current/infra/ai-capacity-and-scaling.md`
