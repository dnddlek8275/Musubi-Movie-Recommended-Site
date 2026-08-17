"""Warm every llama-server slot with the shared general-chat prompt.

This is intended to run after ``cineverse-llama.service`` starts.  It does not
change model output policy: each request generates only one disposable token
while leaving the shared system-prompt prefix available to llama.cpp's prompt
cache.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from pipeline.general_prompt import (  # noqa: E402
    ANSWER_NOW_REMINDER,
    GENERAL_CHAT_SYSTEM_PROMPT,
)
from pipeline.tone_presets import build_turn_guidance  # noqa: E402


LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8081")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma-4-12b-it.Q4_K_M.gguf")


def wait_until_ready(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "llama-server is not ready"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"health returned HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(last_error)


def warm_slot(index: int, base_url: str, timeout_seconds: float) -> dict:
    message = f"일반 대화 슬롯 준비 확인 {index + 1}"
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": GENERAL_CHAT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    message
                    + "\n\n"
                    + build_turn_guidance(message, [])
                    + ANSWER_NOW_REMINDER
                ),
            },
        ],
        "max_tokens": 1,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
    }
    started = time.monotonic()
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"warm-up returned HTTP {response.status}")
        response.read()
    return {
        "slot_request": index + 1,
        "duration_seconds": round(time.monotonic() - started, 3),
        "status": "ok",
    }


def warm_slots(slots: int, base_url: str, timeout_seconds: float) -> list[dict]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=slots) as executor:
        futures = [
            executor.submit(warm_slot, index, base_url, timeout_seconds)
            for index in range(slots)
        ]
        return [future.result() for future in futures]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slots",
        type=int,
        default=int(os.environ.get("LLM_PARALLEL_SLOTS", "5")),
    )
    parser.add_argument("--base-url", default=LLM_BASE_URL)
    parser.add_argument("--ready-timeout", type=float, default=120.0)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.slots < 1:
        raise ValueError("--slots must be at least 1")
    started = time.monotonic()
    wait_until_ready(args.base_url, args.ready_timeout)
    results = warm_slots(args.slots, args.base_url, args.request_timeout)
    print(
        json.dumps(
            {
                "status": "ok",
                "slots": args.slots,
                "duration_seconds": round(time.monotonic() - started, 3),
                "results": results,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
