# 실사용형 고정 평가셋

`real_user_cases_v1.json`은 모델·프롬프트·검색 설정 변경 전후를 같은 기준으로 비교하기 위한 고정 평가셋이다. 이 파일의 사례를 학습 또는 튜닝 데이터로 사용하지 않는다.

## 평가 원칙

- 자동 평가는 조건 위반, 빈 결과, 근거 목록 밖 영화명, RAG 라우팅, 반복 답변처럼 객관적으로 확인 가능한 항목만 판정한다.
- 캐릭터다움, 자연스러움, 구체성은 자동 정규식 점수로 대체하지 않고 사람이 블라인드 평가한다.
- 평가셋을 보고 개별 사례만 통과시키는 규칙을 추가하지 않는다. 실패 유형을 일반화한 뒤 별도 개발셋으로 수정 효과를 확인한다.
- 평가셋 버전을 변경하면 이전 결과와 직접 비교하지 않는다.

## 실행

AI 디렉터리에서 스키마만 검증한다.

```bash
python3 eval/run_real_user_eval.py --validate-only
```

로컬 API가 실행 중일 때 전체 평가를 수행한다.

```bash
python3 eval/run_real_user_eval.py \
  --base-url http://127.0.0.1 \
  --output eval/real_user_results_candidate.json
```

운영 서버에 배포하지 않고 후보 API 주소만 바꿔 현행 모델과 후보 모델을 각각 측정한다.

## 배포 전 게이트

- 자동 hard check 통과율 95% 이상
- critical failure 0건
- 정규화한 완전 동일 답변 비율 5% 이하
- 수동 평가 전체 평균 4.0/5 이상
- 수동 평가 각 차원 평균 3.5/5 이상

자동 게이트가 모두 통과해도 `manual_scores`가 비어 있으면 `release_gate_passed`는 `false`다.

## 수동 블라인드 평가

평가자는 모델 이름을 보지 않고 각 응답을 1~5점으로 평가한다.

- `relevance`: 사용자 요청과 조건을 직접 충족하는가
- `naturalness`: 반복·부자연스러운 규칙문 없이 대화다운가
- `specificity`: 범용 격언 대신 현재 상황에 구체적으로 답하는가
- `character_fidelity`: 이름을 가려도 캐릭터의 차이가 드러나는가
- `groundedness`: 제공된 영화 목록·검증 관계·대화 이력 밖 사실을 만들지 않는가

현행 모델과 후보 모델의 순서를 무작위로 섞어 최소 2명이 독립 평가하고, 점수 차이가 2점 이상이면 제3자가 재평가한다.

체크포인트별 결과의 수동 평가까지 끝나면 다음 명령으로 모든 게이트를 통과한 최상위 후보만 선택한다.

```bash
python3 eval/select_checkpoint.py \
  eval/candidates/checkpoint-*.json \
  --output eval/candidates/selection.json
```
