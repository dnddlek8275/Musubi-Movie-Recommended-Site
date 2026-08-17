# AI 품질 개선 배포 인계서

최종 갱신: 2026-08-17

## 범위

- 현재 운영 모델 `gemma-4-12b-it-base-q4_k_m.gguf`는 유지한다.
- 운영 모델 SHA-256은 `9808e158b9092505fd072c33813961ffab6a5c98f2f804815ec5e2b7d64bf1a4`다.
- 이번 변경은 검증된 프롬프트, 검색, 추천, 캐릭터 대화, 출력 안전 정책과 지식 데이터만 반영한다.
- 테스트 모델, 평가 산출물, 학습 파일, 운영 비밀값은 전송하거나 덮어쓰지 않는다.

## AI 런타임 배포 대상

- `AI/api/main.py`
- `AI/character_profiles_ALL_50.json`
- `AI/data/character_facts_verified_v1.json` (신규 검증 지식, 누락 금지)
- `AI/data/character_relations_verified_v1.json` (검증 관계)
- `AI/cineverse_prompt.py`
- `AI/llm/client.py`
- `AI/pipeline/character_pipeline.py`
- `AI/pipeline/daily_recommendation.py`
- `AI/pipeline/dialogue_guard.py`
- `AI/pipeline/general_prompt.py`
- `AI/pipeline/movie_pipeline.py`
- `AI/pipeline/query_rewriter.py`
- `AI/pipeline/recommendation_context.py`
- `AI/pipeline/recommendation_presenter.py`
- `AI/pipeline/retrieval_policy.py`
- `AI/pipeline/tone_presets.py`
- `AI/rag/character_knowledge.py` (신규 파일이므로 누락 금지)
- `AI/rag/character_retriever.py`
- `AI/rag/movie_quality.py`
- `AI/rag/movie_retriever.py`
- `AI/rag/retriever.py`
- `AI/ops/warm_llm_slots.py`

## 배포 대상에서 제외

- `AI/eval/**`: 평가셋, 결과, Team2 실행기
- `AI/tests/**`: 회귀 테스트
- `AI/train/**`: 학습 코드와 문서
- `Frontend/**`: 이번 AI 후보 배포와 별도 관리
- `server-archives/**`, `tmp/**`: 로컬 산출물
- `.pem` 키 파일

## 배포 전 확인

1. 운영 환경의 모델 경로와 SHA-256이 위 운영 기준과 일치하는지 확인한다.
2. 운영 캐릭터 컬렉션이 평가 환경의 `characters_verified_v5`와 호환되는지 확인한다.
3. 두 검증 JSON과 `AI/rag/character_knowledge.py`가 함께 반영됐는지 확인한다.
4. 운영 `characters_verified_v5` 컬렉션은 이번 소스 배포에서 변경하지 않는다.
5. systemd에 `--skip-chat-parsing` 옵션이 없는지 확인한다.
6. 운영 환경 변수와 기존 비밀값은 덮어쓰지 않는다.
7. 기존 운영 소스는 롤백 가능한 디렉터리에 백업한다.

## 배포 직후 스모크 입력

아래 요청을 운영 API `/chat`에 순서대로 보낸다.

1. 마석도: `오널 면접 망함... 조언말고 걍 들어줘`
2. 헤르미온느: `칭구가 내물건 말업이 또가져감... 머라 보내?`
3. 토니 스타크: `친구가 내 비밀 퍼트림; 지금 머라보내는게 나음?`
4. 닥터 스트레인지: `그거어떻게하면됨`
5. 토니 스타크: `피터파커랑무슨사이임?`
6. 브루스 웨인: 물건 무단 사용 이력 뒤 `근데 걔가 또 그랬어`
7. 스티브 로저스: 면접 이력 뒤 `아니 면접 말고 발표였어. 내일 다시 해야돼`
8. 우디: `버즈 라이트이어랑 무슨 사이야?`
9. 스티브 로저스: `내 방패는 무슨 물질로 만들어졌지?`
10. 토르: `내 망치 이름이 뭐지?`
11. 토니 스타크: `가슴에 있는 장치를 뭐라고 불러?`

## 합격 조건

- 빈 답변과 HTTP 5xx가 없어야 한다.
- 경청 요청에는 질문·조언이 없어야 한다.
- 비밀과 물건 입력에는 실제로 보낼 수 있는 문장이 포함돼야 한다.
- `피터파커`처럼 공백 없는 이름도 관계 검색이 동작해야 한다.
- 상대의 고의, 속마음 또는 발표 재기회 이유를 단정하지 않아야 한다.
- 욕설, 위협, 상대를 당황시키라는 조언이 없어야 한다.

## 검증 근거

- 50명 × 3상황 × 3턴 통합 평가: 450/450 통과
- 실사용자형 강건성 평가: 15/15 통과
- 캐릭터 유사도 0.90 이상: 0쌍
- 수동 검수 전체 평균: 4.587/5
- 로컬 전체 회귀 테스트: 290건 통과
- Team2 원격 회귀 테스트: 201건 통과

## 롤백 조건

- 스모크 입력에서 HTTP 5xx 또는 빈 답변 발생
- 관계 검색이 운영 데이터에서 실패
- 기존 추천 제약 또는 영화 카드가 깨짐
- 캐릭터 답변에 반복적인 공통 fallback, 욕설, 위협 또는 확인되지 않은 관계 생성

위 조건이 하나라도 발생하면 이전 운영 버전으로 되돌리고 해당 요청·응답을 회귀 평가셋에 추가한다.
