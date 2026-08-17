#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/ubuntu/team3-cineverse-eval-20260814
SOURCE="$ROOT/source"
VENV="$ROOT/venv/bin"
LLM_LOG="$ROOT/generalization-450-llm.log"
API_LOG="$ROOT/generalization-450-api.log"
RUN_LOG="$ROOT/generalization-450-run.log"
RESULT="${RESULT:-$ROOT/character_multiturn_generalization_all50_final_v1_20260815.json}"

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

"$VENV/python" eval/run_character_multiturn_generalization.py \
  --api-base http://127.0.0.1:18080 \
  --all-profiles \
  --profile-path character_profiles_ALL_50.json \
  --resume \
  --similarity-threshold 0.90 \
  --output "$RESULT" "$@" >"$RUN_LOG" 2>&1
