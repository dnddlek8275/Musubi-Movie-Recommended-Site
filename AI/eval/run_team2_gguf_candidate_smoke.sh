#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/ubuntu/team3-cineverse-eval-20260814
SOURCE="$ROOT/source-predeploy-20260816"
VENV="$ROOT/venv/bin"
LLAMA_BIN="$ROOT/llama-operating-build/bin/llama-server"
MODEL="$ROOT/gemma-4-12b-it-base-q4_k_m.gguf"
LLM_LOG="$ROOT/predeploy-gguf-llm.log"
API_LOG="$ROOT/predeploy-gguf-api.log"
RUN_LOG="$ROOT/predeploy-gguf-run.log"
TEST_LOG="$ROOT/predeploy-gguf-tests.log"
RESULT="${RESULT:-$ROOT/predeploy_gguf_candidate_smoke_20480_np5_20260816.json}"

case_args=(
  --case-id typo_listen_only
  --case-id typo_property_wording
  --case-id typo_secret_wording
  --case-id nospace_ambiguous
  --case-id relation_spacing_typo
  --case-id pronoun_property_followup
  --case-id correction_interview_to_presentation
)
if [[ "$#" -gt 0 ]]; then case_args=("$@"); fi

llm_pid=""
api_pid=""
cleanup() {
  if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; fi
  if [[ -n "$llm_pid" ]]; then kill "$llm_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

cd "$SOURCE"
export HF_HOME="$ROOT/hf-cache"
export LD_LIBRARY_PATH="$ROOT/llama-operating-build/bin:$VENV/../lib/python3.12/site-packages/nvidia/cuda_runtime/lib:$VENV/../lib/python3.12/site-packages/nvidia/cublas/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH=.
export CINEVERSE_MILVUS_URI="$ROOT/eval-lite.db"
export MOVIE_COLLECTION_NAME=movies_postgres_20260807
export CHARACTER_COLLECTION_NAME=characters_verified_v5
export LLM_BASE_URL=http://127.0.0.1:18081
export LLM_MODEL=google/gemma-4-12b-it

"$VENV/python" -m unittest discover -s tests >"$TEST_LOG" 2>&1

"$LLAMA_BIN" \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port 18081 \
  --ctx-size 20480 \
  -ngl 999 \
  --reasoning-budget 0 \
  -np 5 >"$LLM_LOG" 2>&1 &
llm_pid=$!
for _ in $(seq 1 180); do
  if curl -fsS http://127.0.0.1:18081/health >/dev/null; then break; fi
  if ! kill -0 "$llm_pid" 2>/dev/null; then exit 11; fi
  sleep 2
done
curl -fsS http://127.0.0.1:18081/health >/dev/null

"$VENV/uvicorn" api.main:app --host 127.0.0.1 --port 18080 >"$API_LOG" 2>&1 &
api_pid=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:18080/health >/dev/null; then break; fi
  if ! kill -0 "$api_pid" 2>/dev/null; then exit 12; fi
  sleep 2
done
curl -fsS http://127.0.0.1:18080/health >/dev/null

set +e
"$VENV/python" eval/run_real_user_eval.py \
  --base-url http://127.0.0.1:18080 \
  --cases eval/character_real_user_robustness_cases_v1.json \
  --output "$RESULT" "${case_args[@]}" >"$RUN_LOG" 2>&1
status=$?
set -e
if [[ "$status" -ne 0 && ! -s "$RESULT" ]]; then exit "$status"; fi
