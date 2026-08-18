# BF16·Q8·Q4 품질 비교

이 비교는 서버·장비 제한과 처리시간을 평가 대상에서 제외한다. 동일한 병합 체크포인트, 프롬프트, 검색 결과, 생성 프로필과 `real_user_cases_v1.json`을 사용하고 모델 표현 형식만 변경한다.

## 비교 대상

- `bf16`: LoRA 병합 후 BF16 기준 모델
- `q8`: 같은 병합 모델의 Q8_0 GGUF
- `q4`: 같은 병합 모델의 Q4_K_M GGUF

모델마다 별도 로컬 API를 실행하고 다음과 같이 결과를 만든다.

```bash
python3 eval/run_real_user_eval.py --base-url http://127.0.0.1:8101 --output eval/variants/bf16.json
python3 eval/run_real_user_eval.py --base-url http://127.0.0.1:8102 --output eval/variants/q8.json
python3 eval/run_real_user_eval.py --base-url http://127.0.0.1:8103 --output eval/variants/q4.json
```

각 결과의 수동 블라인드 평가를 완료한 후 품질 차이를 집계한다.

```bash
python3 eval/compare_model_variants.py \
  bf16=eval/variants/bf16.json \
  q8=eval/variants/q8.json \
  q4=eval/variants/q4.json \
  --reference bf16 \
  --output eval/variants/comparison.json
```

세 결과의 평가셋 버전과 케이스 순서가 다르면 비교기는 실행을 거부한다. 처리시간이나 초당 토큰 수는 보고서에 포함하지 않는다.

현재 자료에는 BF16·Q8 실행 결과가 없으므로 어느 양자화가 최종적으로 적합한지는 아직 판단할 수 없다.
