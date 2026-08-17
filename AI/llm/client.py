"""
Musubi LLM Client
llama-server (OpenAI 호환) 호출 모듈
"""

import json
import os
import time
import requests

from llm.sampling import DEFAULT_PARAMS, sampling_params

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8081")
LLM_MODEL    = os.environ.get("LLM_MODEL", "gemma-4-12b-it.Q4_K_M.gguf")
LLM_TIMEOUT  = int(os.environ.get("LLM_TIMEOUT", "300"))


def _server_metric(data: dict, usage_key: str, timing_key: str):
    usage = data.get("usage") or {}
    timings = data.get("timings") or {}
    value = usage.get(usage_key)
    if value is None:
        value = timings.get(timing_key)
    return value


def _log_timing(
    data: dict,
    *,
    started_at: float,
    profile: str | None,
    stream: bool,
    ttft_seconds: float | None,
    status: str = "ok",
) -> None:
    """Emit one machine-readable timing line without logging prompt contents."""
    timings = data.get("timings") or {}
    payload = {
        "event": "llm_timing",
        "status": status,
        "profile": profile or "default",
        "stream": stream,
        "request_seconds": round(time.perf_counter() - started_at, 4),
        # A non-streaming HTTP response cannot reveal exact first-token arrival.
        "ttft_seconds": round(ttft_seconds, 4) if ttft_seconds is not None else None,
        "prompt_tokens": _server_metric(data, "prompt_tokens", "prompt_n"),
        "output_tokens": _server_metric(data, "completion_tokens", "predicted_n"),
        "prompt_seconds": (
            round(float(timings["prompt_ms"]) / 1000, 4)
            if timings.get("prompt_ms") is not None else None
        ),
        "generation_seconds": (
            round(float(timings["predicted_ms"]) / 1000, 4)
            if timings.get("predicted_ms") is not None else None
        ),
        "generation_tokens_per_second": timings.get("predicted_per_second"),
    }
    print("  [LLMTiming] " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

def chat(
    messages: list[dict],
    max_tokens: int = 1024,
    profile: str | None = None,
    **kwargs,
) -> str:
    """
    llama-server /v1/chat/completions 호출.

    Args:
        messages:   OpenAI 형식 메시지 리스트
        max_tokens: 최대 생성 토큰 수
        **kwargs:   temperature 등 파라미터 오버라이드

    Returns:
        생성된 텍스트 (content 필드)
    """
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        **sampling_params(profile, **kwargs),
    }
    started_at = time.perf_counter()

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=LLM_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"LLM 서버에 연결할 수 없습니다: {LLM_BASE_URL}")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"LLM 서버 응답 시간 초과 ({LLM_TIMEOUT}s)")

    if not resp.ok:
        print(f"  [LLM] HTTP {resp.status_code}: {resp.text[:200]}")
        if resp.status_code == 500:
            return ""
        resp.raise_for_status()

    data    = resp.json()
    choice  = data["choices"][0]
    msg     = choice["message"]
    content = (msg.get("content") or "").strip()

    # --reasoning-budget 0 없이 기동된 경우 content가 비고 reasoning_content에 응답이 들어옴
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
        if content:
            print("  [LLM] ⚠ content 비어있음 — reasoning_content로 fallback (--reasoning-budget 0 확인 필요)")

    finish = choice.get("finish_reason", "")
    if finish == "length":
        print(f"  [LLM] ⚠ finish=length — max_tokens({max_tokens}) 부족할 수 있음")

    _log_timing(
        data,
        started_at=started_at,
        profile=profile,
        stream=False,
        ttft_seconds=None,
    )

    return content


def chat_stream(
    messages: list[dict],
    max_tokens: int = 1024,
    profile: str | None = None,
    **kwargs,
):
    """
    llama-server SSE 스트리밍 호출. 토큰이 생성될 때마다 yield.

    Yields:
        str: 생성된 토큰 조각
    """
    payload = {
        "model":  LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        **sampling_params(profile, **kwargs),
    }
    started_at = time.perf_counter()
    first_token_at = None
    final_data: dict = {}
    completed = False

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=LLM_TIMEOUT,
            stream=True,
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"LLM 서버에 연결할 수 없습니다: {LLM_BASE_URL}")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"LLM 서버 응답 시간 초과 ({LLM_TIMEOUT}s)")

    if not resp.ok:
        resp.raise_for_status()

    try:
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if decoded == "data: [DONE]":
                completed = True
                break
            if not decoded.startswith("data: "):
                continue
            try:
                chunk = json.loads(decoded[6:])
                if chunk.get("usage") or chunk.get("timings"):
                    final_data = chunk
                delta = chunk["choices"][0]["delta"]
                token = delta.get("content") or delta.get("reasoning_content") or ""
                if token:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield token
            except (json.JSONDecodeError, KeyError):
                continue
    finally:
        _log_timing(
            final_data,
            started_at=started_at,
            profile=profile,
            stream=True,
            ttft_seconds=(first_token_at - started_at) if first_token_at is not None else None,
            status="ok" if completed else "incomplete",
        )


def chat_json(
    messages: list[dict],
    max_tokens: int = 512,
    **kwargs,
) -> str:
    """
    JSON 응답을 기대하는 LLM 호출.
    temperature를 낮춰 일관성 확보.
    """
    return chat(
        messages,
        max_tokens=max_tokens,
        profile="structured",
        **kwargs,
    )
