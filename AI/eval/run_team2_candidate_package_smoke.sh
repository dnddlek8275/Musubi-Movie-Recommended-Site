#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/ubuntu/team3-cineverse-eval-20260814
SOURCE=/home/ubuntu/team3-candidate-smoke-20260816/AI
VENV="$ROOT/venv/bin"
LLM_LOG="$ROOT/candidate-package-smoke-llm.log"
API_LOG="$ROOT/candidate-package-smoke-api.log"
RUN_LOG="$ROOT/candidate-package-smoke-run.log"
TEST_LOG="$ROOT/candidate-package-smoke-tests.log"
RESULT="${RESULT:-$ROOT/candidate_package_smoke_20260816.json}"
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
export PYTHONPATH=.
export CINEVERSE_MILVUS_URI="$ROOT/eval-lite.db"
export MOVIE_COLLECTION_NAME=movies_postgres_20260807
export CHARACTER_COLLECTION_NAME=characters_verified_v5
export LLM_BASE_URL=http://127.0.0.1:18081
export LLM_MODEL=google/gemma-4-12b-it

"$VENV/python" -m unittest discover -s tests >"$TEST_LOG" 2>&1

"$VENV/python" eval/serve_transformers_openai.py --adapter google/gemma-4-12b-it --host 127.0.0.1 --port 18081 >"$LLM_LOG" 2>&1 &
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
