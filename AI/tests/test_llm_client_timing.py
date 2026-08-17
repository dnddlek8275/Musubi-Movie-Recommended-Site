import io
import importlib.util
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def _load_client_module():
    """Load the real client even when other tests installed an llm.client stub."""
    requests_stub = types.ModuleType("requests")
    requests_stub.post = lambda *args, **kwargs: None
    requests_stub.ConnectionError = ConnectionError
    requests_stub.Timeout = TimeoutError
    requests_stub.exceptions = types.SimpleNamespace(
        ConnectionError=ConnectionError,
        Timeout=TimeoutError,
    )
    original_requests = sys.modules.get("requests")
    sys.modules["requests"] = requests_stub
    try:
        path = Path(__file__).parents[1] / "llm" / "client.py"
        spec = importlib.util.spec_from_file_location("llm_client_timing_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = original_requests


client = _load_client_module()


class _Response:
    def __init__(self, *, payload=None, lines=None):
        self.ok = True
        self.status_code = 200
        self.text = ""
        self._payload = payload or {}
        self._lines = lines or []

    def json(self):
        return self._payload

    def iter_lines(self):
        return iter(self._lines)


def _timing_record(output: str) -> dict:
    line = next(line for line in output.splitlines() if "[LLMTiming]" in line)
    return json.loads(line.split("[LLMTiming] ", 1)[1])


class LlmClientTimingTests(unittest.TestCase):
    def test_nonstream_logs_server_token_metrics_without_fake_ttft(self):
        response = _Response(payload={
            "choices": [{"message": {"content": "안녕하세요"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 27, "completion_tokens": 24},
            "timings": {
                "prompt_ms": 353.3,
                "predicted_ms": 1096.9,
                "predicted_per_second": 21.88,
            },
        })
        output = io.StringIO()

        with patch.object(client.requests, "post", return_value=response), \
             patch.object(client.time, "perf_counter", side_effect=[10.0, 12.5]), \
             redirect_stdout(output):
            answer = client.chat([{"role": "user", "content": "안녕"}], profile="character_chat")

        self.assertEqual(answer, "안녕하세요")
        record = _timing_record(output.getvalue())
        self.assertEqual(record["prompt_tokens"], 27)
        self.assertEqual(record["output_tokens"], 24)
        self.assertEqual(record["generation_tokens_per_second"], 21.88)
        self.assertEqual(record["request_seconds"], 2.5)
        self.assertIsNone(record["ttft_seconds"])

    def test_stream_logs_exact_first_token_arrival(self):
        chunk = {
            "choices": [{"delta": {"content": "안녕"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            "timings": {"predicted_per_second": 20.0},
        }
        response = _Response(lines=[
            f"data: {json.dumps(chunk, ensure_ascii=False)}".encode(),
            b"data: [DONE]",
        ])
        output = io.StringIO()

        with patch.object(client.requests, "post", return_value=response), \
             patch.object(client.time, "perf_counter", side_effect=[20.0, 20.7, 22.0]), \
             redirect_stdout(output):
            tokens = list(client.chat_stream(
                [{"role": "user", "content": "안녕"}],
                profile="character_chat",
            ))

        self.assertEqual(tokens, ["안녕"])
        record = _timing_record(output.getvalue())
        self.assertTrue(record["stream"])
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["ttft_seconds"], 0.7)
        self.assertEqual(record["request_seconds"], 2.0)


if __name__ == "__main__":
    unittest.main()
