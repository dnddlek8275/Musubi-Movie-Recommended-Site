# 학습 데이터 분할 정책

원본 JSONL은 수정하지 않는다. `prepare_splits.py`가 생성한 버전 디렉터리의 `train.jsonl`, `dev.jsonl`, `test.jsonl`만 후속 학습과 평가에 사용한다.

## 고정 규칙

- 기본 분할 비율: train 80%, dev 10%, test 10%
- 기본 seed: 42
- 사용자 입력을 NFKC·소문자·공백/문장부호 제거 방식으로 정규화한다.
- 문자 3-gram Jaccard 0.88 이상인 입력은 하나의 그룹으로 묶은 뒤 분할한다.
- 같은 그룹은 어떤 경우에도 서로 다른 split에 들어가지 않는다.
- 빈 사용자 입력 또는 빈 답변은 제거하고 보고서에 기록한다.
- 결과의 `_source` 필드는 원본 파일과 줄 번호를 보존한다.

## 실행 예시

학습 데이터 파일을 로컬 `AI/data`에 준비한 뒤 `AI` 디렉터리에서 실행한다.

```bash
python3 train/prepare_splits.py \
  data/train_dataset.jsonl \
  --output-dir data/splits/v1
```

생성된 `split_report.json`에서 모든 `exact_prompt_overlap` 값이 0인지 확인한다. 분할 후에는 테스트셋을 학습·프롬프트 튜닝·규칙 작성에 사용하지 않는다.

## 멀티턴 데이터

서로 관련 있어 보이는 단일 질문 두 개를 무작위로 이어 붙이지 않는다. 기존 멀티턴 후보는 다음 명령으로 검사하며, 후속 질문이 앞 답변을 실제로 참조하고 독립 단일 질문을 그대로 재사용하지 않은 경우만 통과시킨다.

```bash
python3 train/filter_multiturn.py \
  --standalone data/train_dataset.jsonl \
  --multiturn data/train_multiturn.jsonl \
  --accepted data/splits/v1/multiturn_accepted.jsonl \
  --report data/splits/v1/multiturn_report.json
```
