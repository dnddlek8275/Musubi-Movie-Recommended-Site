# 운영 교체 전 확인 결과 (2026-08-16)

## 결론

- **운영 모델과 Team2 평가 모델은 같은 베이스 계열이지만 같은 후보 가중치는 아니다.**
  - Team2 평가: 순수 `google/gemma-4-12b-it` 베이스를 Transformers/Unsloth 4bit 로딩으로 실행했다.
  - 운영: 같은 베이스에 기존 CineVerse LoRA를 병합한 `gemma4-cineverse-v2.gguf`를 llama.cpp로 실행한다.
  - 따라서 후보 파이프라인만 운영에 올리면 Team2에서 평가한 조합과 달리 **기존 LoRA 병합 모델 + 후보 파이프라인** 조합이 된다.
- **운영 Milvus `characters_verified_v5`와 Team2 테스트 컬렉션은 호환되며, 조회한 전체 데이터도 동일하다.**
- **255건과 201건 차이 54건은 실패/제외 필터가 아니라 Team2에 복사된 테스트 소스가 로컬 최신본보다 이전이기 때문에 발생했다.**

순수 베이스 모델을 GGUF로 준비하고 운영과 동일한 llama.cpp build 9776/T4에서 Team2 무배포 검증을 완료했다. 운영 예정값 `--ctx-size 20480 -np 5`에서 최신 회귀 테스트 255건과 실제 API 스모크 7건이 모두 통과했다. 7개 응답의 원문 수동 검토도 완료되어 결과 JSON의 `manual_review_complete`와 `release_gate_passed`가 모두 `true`다. 새 GGUF에서는 기존 운영 옵션 `--skip-chat-parsing`을 제거해야 한다.

## 1. 모델 계보 확인

### 운영에서 확인한 사실

- 서비스: `cineverse-llama.service`
- 실행 모델: `/home/ubuntu/cineverse/gemma4-cineverse-v2.gguf`
- 파일 크기: `7,947,612,736 bytes`
- GGUF 메타데이터:
  - `general.architecture = gemma4`
  - `general.name = Gemma4 Merged`
  - `general.size_label = 13B`
  - `general.quantization_version = 2`
  - `general.file_type = 15`
- llama.cpp 실행 옵션에는 별도 런타임 LoRA가 없다. LoRA는 GGUF 생성 전에 가중치에 병합된 형태다.

### 저장소에서 확인한 생성 계보

- `train/export_gguf.py`: `BASE_MODEL = "google/gemma-4-12b-it"`, LoRA 디렉터리를 로드해 `q4_k_m` GGUF로 저장한다.
- `merge_and_convert.py`: 같은 베이스 모델에 `PeftModel` LoRA를 `merge_and_unload()`한 뒤 `gemma4-cineverse-v2.gguf`를 생성한다.
- `lora-adapter/adapter_config.json`: `base_model_name_or_path = "google/gemma-4-12b-it"`, PEFT 타입 `LORA`, rank 32다.
- Team2 스모크 스크립트는 `--adapter google/gemma-4-12b-it`로 순수 베이스를 직접 실행한다.

### 판정

`gemma4-cineverse-v2.gguf`는 `google/gemma-4-12b-it` 계열에서 파생된 모델이지만, 순수 베이스와 정확히 같은 후보는 아니다. LoRA 병합 및 GGUF 양자화가 적용되어 가중치와 런타임이 모두 다르다.

## 2. Milvus 컬렉션 대조

| 항목 | 운영 Milvus | Team2 Milvus Lite | 판정 |
|---|---:|---:|---|
| 컬렉션 | `characters_verified_v5` | `characters_verified_v5` | 동일 |
| 행 수 | 66 | 66 | 동일 |
| 캐릭터 수 | 50 | 50 | 동일 |
| 필드 | `id`, `character_name`, `movie`, `lang`, `data_type`, `text`, `metadata`, `dense_vector`, `sparse_vector` | 동일 | 동일 |
| dense 차원 | 1024 | 1024 | 동일 |
| 비벡터 데이터 SHA-256 | `b009632adbe51099c75686588091d7b5518e3b2474ad8b7b23beb94aadc832d1` | 동일 | 동일 |
| dense/sparse 포함 전체 데이터 SHA-256 | `048f16795194d1c207a2a6dca8e9922d79fb9b082f904df926f75c72f1b611d2` | 동일 | 동일 |

Milvus 서버와 Milvus Lite의 내부 `field_id`, collection ID, consistency level은 구현 환경에 따른 관리 메타데이터 차이다. 애플리케이션이 사용하는 스키마, 데이터, dense/sparse 벡터는 동일하다.

## 3. 255건과 201건 차이

양쪽 `unittest` discover 결과와 테스트 파일 AST를 함께 비교했다.

- 로컬: 255개
- Team2: 201개
- 로컬에만 존재: 54개
- Team2에만 존재: 0개
- import 실패 또는 실행 중 제외: 0개

### 모듈별 차이

| 모듈 | 로컬 | Team2 | 차이 |
|---|---:|---:|---:|
| `test_character_collection_defaults` | 1 | 0 | 1 |
| `test_character_regression_eval` | 7 | 0 | 7 |
| `test_ambiguous_input_prompts` | 28 | 26 | 2 |
| `test_llm_output_context` | 4 | 2 | 2 |
| `test_movie_quality` | 35 | 14 | 21 |
| `test_query_rewriter_mood` | 14 | 5 | 9 |
| `test_real_user_eval` | 6 | 4 | 2 |
| `test_recommendation_context` | 9 | 5 | 4 |
| `test_recommendation_presenter` | 21 | 15 | 6 |
| **합계** |  |  | **54** |

### 누락 범위의 성격

- 캐릭터 컬렉션 기본값 및 캐릭터 회귀 평가: 8건
- 모호한 입력과 출력 정리: 4건
- 영화 추천 품질·분위기 재작성·표현 근거: 36건
- 실사용 평가 게이트 및 멀티턴 추천 문맥: 6건

즉 누락분은 대부분 후속 파이프라인 개선 과정에서 로컬에 추가된 회귀 테스트다. Team2의 201건 성공은 당시 복사된 테스트 집합에 대한 성공이며, 현재 로컬 최신 255건 전체의 원격 성공을 의미하지 않는다.

## 배포 게이트

1. 순수 `google/gemma-4-12b-it`를 Q4_K_M GGUF로 변환했다. **완료**
2. 운영과 같은 llama.cpp build 9776 및 Team2 T4에서 후보 파이프라인과 결합했다. **1차 4096/np1 및 최종 20480/np5 검증 완료**
3. 로컬 최신 테스트 255건을 Team2 격리 소스에서 실행했다. **255/255 통과**
4. 실제 API 스모크 7건을 실행했다. **7/7 통과, critical failure 0, 자동 게이트 통과**
5. 7개 응답 원문에 5개 차원의 수동 점수와 근거 메모를 기록했다. **평균 4.5857/5, 모든 차원 기준 통과**
6. 운영 예정값 `--ctx-size 20480 -np 5`로 최종 스모크를 실행했다. **7/7 통과, 5개 슬롯 각각 4096 컨텍스트 확인**
7. 운영 교체 시 순수 베이스 GGUF, 검증된 런타임 17개 파일, `--skip-chat-parsing` 제거를 하나의 교체 단위로 적용해야 한다. **배포 시 필수**
8. 기존 모델·소스·서비스 설정을 즉시 되돌릴 수 있게 보관한 뒤 카나리 검증한다. **배포 시 필수**

## GGUF 무배포 검증 결과

- 모델: `gemma-4-12b-it-base-q4_k_m.gguf`
- 크기: `7,381,383,392 bytes`
- SHA-256: `9808e158b9092505fd072c33813961ffab6a5c98f2f804815ec5e2b7d64bf1a4`
- 메타데이터: `Gemma 4 12B`, Google, `general.file_type = 15`, LoRA 병합 없음
- llama.cpp: 운영과 동일한 build 9776, commit `ac4105d68b2955027115cf9bb50941ccf56974eb`
- 테스트: 255/255 통과
- API 스모크: 7/7 통과
- 1차 스모크 실행값: `--ctx-size 4096 -np 1`
- 최종 스모크 실행값: `--ctx-size 20480 -np 5`
- 실제 초기화: 5개 슬롯, 슬롯당 `n_ctx = 4096`
- 자동 게이트: 통과
- 수동 평균: 4.5857/5
- 수동 차원 평균: 관련성 4.9286, 자연스러움 4.2857, 구체성 4.2857, 캐릭터 충실도 4.5, 근거성 4.9286
- 수동/릴리스 게이트: 통과
- 최종 결과 파일: `eval/predeploy_gguf_candidate_smoke_20480_np5_20260816.json`

### 실행 옵션 호환성 확인

초기 검증에서 기존 운영 옵션 `--skip-chat-parsing`을 유지했을 때 캐릭터 내부 프로필이 응답으로 노출됐다. 이 옵션을 제거하자 llama.cpp가 새 GGUF의 canonical Gemma 4 chat template를 `peg-gemma4` 형식으로 파싱했고, 문제 사례 3/3 및 전체 사례 7/7이 통과했다.

운영 예정 실행 조건은 다음과 같으며 Team2 최종 스모크에 동일하게 사용했다.

```text
llama-server -m gemma-4-12b-it-base-q4_k_m.gguf \
  --host 0.0.0.0 --port 8081 --ctx-size 20480 \
  -ngl 999 --reasoning-budget 0 -np 5
```

`--skip-chat-parsing`은 포함하지 않는다.

## 교체 단위

다음 세 항목 중 일부만 적용하면 검증한 조합과 달라진다. 반드시 하나의 변경 세트로 취급한다.

1. 기존 LoRA 병합 GGUF를 순수 베이스 `gemma-4-12b-it-base-q4_k_m.gguf`로 교체
2. `AI/llm/sampling.py`를 포함한 검증된 런타임 17개 파일 반영
3. systemd의 llama-server 실행 옵션에서 `--skip-chat-parsing` 제거

정확한 현재 판정은 **운영 예정 `20480 / np=5` 조합의 자동 품질 검증과 원문 수동 검토가 모두 통과해 운영 카나리 교체 근거가 완성된 상태**이다. 다만 `typo_secret_wording` 답변의 “당황하게 만들어”는 갈등을 키울 수 있어 자연스러움 3.5로 가장 낮게 평가했으며, 카나리에서 유사 공격적 표현 증가 여부를 관찰해야 한다.

이번 확인 과정에서는 운영 서비스 재시작, 모델 교체, 컬렉션 수정 및 배포를 수행하지 않았다.
