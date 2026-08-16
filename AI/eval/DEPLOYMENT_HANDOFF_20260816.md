# AI 품질 개선 배포 인계서

## 범위

- 기존 `google/gemma-4-12b-it` 모델은 유지한다.
- 이번 후보는 모델 교체가 아니라 프롬프트, 프로필, 검색, 추천, 캐릭터 대화 및 출력 안전 정책 개선이다.
- Codex는 운영 배포를 수행하지 않는다. 실제 배포와 트래픽 전환은 사용자가 진행한다.

## AI 런타임 배포 대상

- `AI/api/main.py`
- `AI/character_profiles_ALL_50.json`
- `AI/cineverse_prompt.py`
- `AI/llm/client.py`
- `AI/llm/sampling.py` (신규 파일이므로 누락 금지)
- `AI/pipeline/character_pipeline.py`
- `AI/pipeline/daily_recommendation.py`
- `AI/pipeline/dialogue_guard.py`
- `AI/pipeline/movie_pipeline.py`
- `AI/pipeline/query_rewriter.py`
- `AI/pipeline/recommendation_context.py`
- `AI/pipeline/recommendation_presenter.py`
- `AI/pipeline/tone_presets.py`
- `AI/rag/character_retriever.py`
- `AI/rag/movie_quality.py`
- `AI/rag/movie_retriever.py`
- `AI/rag/retriever.py`

## 배포 대상에서 제외

- `AI/eval/**`: 평가셋, 결과, Team2 실행기
- `AI/tests/**`: 회귀 테스트
- `AI/train/**`: 학습 코드와 문서
- `Frontend/**`: 이번 AI 후보 배포와 별도 관리
- `server-archives/**`, `tmp/**`: 로컬 산출물
- `.pem` 키 파일

## 배포 전 확인

1. 운영 환경의 모델이 `google/gemma-4-12b-it`인지 확인한다.
2. 운영 캐릭터 컬렉션이 평가 환경의 `characters_verified_v5`와 호환되는지 확인한다.
3. `AI/llm/sampling.py`가 신규 파일로 함께 반영됐는지 확인한다.
4. 운영 환경 변수와 기존 비밀값은 덮어쓰지 않는다.
5. 기존 운영 버전의 파일 또는 이미지 태그를 롤백 가능하게 보존한다.

## 배포 직후 스모크 입력

아래 요청을 운영 API `/chat`에 순서대로 보낸다.

1. 마석도: `오널 면접 망함... 조언말고 걍 들어줘`
2. 헤르미온느: `칭구가 내물건 말업이 또가져감... 머라 보내?`
3. 토니 스타크: `친구가 내 비밀 퍼트림; 지금 머라보내는게 나음?`
4. 닥터 스트레인지: `그거어떻게하면됨`
5. 토니 스타크: `피터파커랑무슨사이임?`
6. 브루스 웨인: 물건 무단 사용 이력 뒤 `근데 걔가 또 그랬어`
7. 스티브 로저스: 면접 이력 뒤 `아니 면접 말고 발표였어. 내일 다시 해야돼`

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
- 로컬 회귀 테스트: 255건 통과
- Team2 원격 회귀 테스트: 201건 통과

## 롤백 조건

- 스모크 입력에서 HTTP 5xx 또는 빈 답변 발생
- 관계 검색이 운영 데이터에서 실패
- 기존 추천 제약 또는 영화 카드가 깨짐
- 캐릭터 답변에 반복적인 공통 fallback, 욕설, 위협 또는 확인되지 않은 관계 생성

위 조건이 하나라도 발생하면 이전 운영 버전으로 되돌리고 해당 요청·응답을 회귀 평가셋에 추가한다.
