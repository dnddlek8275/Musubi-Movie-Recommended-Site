#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:18080}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/eval/postdeploy_iterative}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$OUTPUT_DIR"
cd "$ROOT"

run_eval() {
  local cases="$1"
  local output="$2"
  shift 2

  set +e
  "$PYTHON_BIN" eval/run_real_user_eval.py \
    --base-url "$BASE_URL" \
    --cases "$cases" \
    --output "$output" \
    "$@"
  local status=$?
  set -e

  if [[ ! -s "$output" ]]; then
    echo "Evaluation did not produce a result file (exit=$status): $output" >&2
    return 1
  fi
}

assert_targeted_passed() {
  "$PYTHON_BIN" - "$1" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
failed = [row["id"] for row in result["results"] if not row["passed"]]
if failed:
    raise SystemExit(f"targeted failures: {failed}")
print(f"targeted gate passed: {len(result['results'])}/{len(result['results'])}")
PY
}

assert_automatic_gate() {
  "$PYTHON_BIN" - "$1" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
summary = result["summary"]
if not summary["automatic_gate_passed"]:
    raise SystemExit(f"automatic gate failed: {summary}")
print(f"automatic gate passed: {summary['hard_pass_count']}/{summary['case_count']}")
PY
}

ROBUST_TARGET="$OUTPUT_DIR/robustness_targeted.json"
ADVERSARIAL_TARGET="$OUTPUT_DIR/adversarial_targeted.json"
ROBUST_FULL="$OUTPUT_DIR/robustness_full.json"
ADVERSARIAL_FULL="$OUTPUT_DIR/adversarial_full.json"

run_eval eval/character_real_user_robustness_cases_v1.json "$ROBUST_TARGET" \
  --case-id slang_anger_context \
  --case-id emoji_listen_only \
  --case-id topic_switch_simple_chat
assert_targeted_passed "$ROBUST_TARGET"

run_eval eval/character_adversarial_cases_v1.json "$ADVERSARIAL_TARGET" \
  --case-id hostile_insult_no_threat \
  --case-id retaliation_request_no_violence \
  --case-id villain_revenge_advice
assert_targeted_passed "$ADVERSARIAL_TARGET"

run_eval eval/character_real_user_robustness_cases_v1.json "$ROBUST_FULL"
assert_automatic_gate "$ROBUST_FULL"

run_eval eval/character_adversarial_cases_v1.json "$ADVERSARIAL_FULL"
assert_automatic_gate "$ADVERSARIAL_FULL"

echo "Automatic post-deployment gates passed. Manual review is still required."
