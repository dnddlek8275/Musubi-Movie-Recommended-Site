"""Bounded admission control for GPU-backed AI endpoints.

The limiter is intentionally process-local because the production AI API runs as
one uvicorn process in front of one physical GPU.  It prevents HTTP concurrency
from growing without bound when llama-server's five slots are already occupied.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
AI_PATHS = {
    "/chat",
    "/chat/auto",
    "/chat/group",
    "/chat/group/auto",
    "/chat/group/rounds",
    "/chat/stream",
    "/chat/title",
    "/recommend",
    "/recommend/daily-copy",
    "/web/search",
}
GROUP_PATHS = {"/chat/group", "/chat/group/auto", "/chat/group/rounds"}


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _non_negative_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _positive_float(name: str, default: float) -> float:
    try:
        return max(0.1, float(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class AdmissionSettings:
    capacity: int = 5
    max_queue: int = 10
    wait_timeout_seconds: float = 40.0
    log_path: str = "/var/log/cineverse/ai-admission.log"

    @classmethod
    def from_env(cls) -> "AdmissionSettings":
        return cls(
            capacity=_positive_int("AI_MAX_CONCURRENT_REQUESTS", 5),
            max_queue=_non_negative_int("AI_MAX_QUEUED_REQUESTS", 10),
            wait_timeout_seconds=_positive_float("AI_QUEUE_WAIT_TIMEOUT_SECONDS", 40.0),
            log_path=os.getenv(
                "AI_ADMISSION_LOG_PATH",
                "/var/log/cineverse/ai-admission.log",
            ),
        )


class WeightedAdmissionController:
    """Atomically reserves one or more of the GPU's logical request slots."""

    def __init__(self, capacity: int, max_queue: int) -> None:
        self.capacity = capacity
        self.max_queue = max_queue
        self.available = capacity
        self.waiting = 0
        self.active_requests = 0
        self._condition = asyncio.Condition()

    async def acquire(self, weight: int, timeout: float) -> tuple[str, float]:
        weight = min(max(1, weight), self.capacity)
        started = time.monotonic()
        async with self._condition:
            if self.available < weight:
                if self.waiting >= self.max_queue:
                    return "full", 0.0
                self.waiting += 1
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self.available >= weight),
                        timeout=timeout,
                    )
                except TimeoutError:
                    return "timeout", time.monotonic() - started
                finally:
                    self.waiting -= 1
            self.available -= weight
            self.active_requests += 1
            return "acquired", time.monotonic() - started

    async def release(self, weight: int) -> None:
        weight = min(max(1, weight), self.capacity)
        async with self._condition:
            self.available = min(self.capacity, self.available + weight)
            self.active_requests = max(0, self.active_requests - 1)
            self._condition.notify_all()


class AdmissionEventLog:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def write(self, event: str, **fields) -> None:
        parts = [f"epoch={int(time.time())}", f"event={event}"]
        parts.extend(f"{key}={value}" for key, value in fields.items())
        line = " ".join(parts) + "\n"
        async with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            except OSError as exc:
                # Monitoring must never make the user request fail.
                print(f"[AIAdmission] event log unavailable: {exc}")


class AIAdmissionMiddleware:
    """ASGI middleware that bounds active and queued GPU work."""

    def __init__(
        self,
        app,
        *,
        settings: AdmissionSettings | None = None,
        controller: WeightedAdmissionController | None = None,
        event_log: AdmissionEventLog | None = None,
    ) -> None:
        self.app = app
        self.settings = settings or AdmissionSettings.from_env()
        self.controller = controller or WeightedAdmissionController(
            self.settings.capacity,
            self.settings.max_queue,
        )
        self.event_log = event_log or AdmissionEventLog(self.settings.log_path)

    async def _reject(self, send, status: int, code: str, message: str, wait: float) -> None:
        body = json.dumps(
            {
                "detail": {
                    "state": "failure",
                    "code": code,
                    "message": message,
                    "retry_after_seconds": 5,
                }
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"retry-after", b"5"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
        await self.event_log.write(
            "AI_REQUEST_REJECTED" if status == 429 else "AI_QUEUE_TIMEOUT",
            status=status,
            code=code,
            wait_seconds=f"{wait:.3f}",
            active=self.controller.active_requests,
            waiting=self.controller.waiting,
        )

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or scope.get("method") != "POST" or path not in AI_PATHS:
            await self.app(scope, receive, send)
            return

        weight = self.settings.capacity if path in GROUP_PATHS else 1
        state, wait_seconds = await self.controller.acquire(
            weight,
            self.settings.wait_timeout_seconds,
        )
        if state == "full":
            await self._reject(
                send,
                429,
                "AI_QUEUE_FULL",
                "현재 AI 요청이 많습니다. 잠시 후 다시 시도해 주세요.",
                wait_seconds,
            )
            return
        if state == "timeout":
            await self._reject(
                send,
                503,
                "AI_QUEUE_WAIT_TIMEOUT",
                "AI 요청 대기 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
                wait_seconds,
            )
            return

        started = time.monotonic()
        status_code = 500

        async def tracked_send(message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except BaseException:
            status_code = 500
            raise
        finally:
            duration = time.monotonic() - started
            await self.controller.release(weight)
            await self.event_log.write(
                "AI_REQUEST_COMPLETE",
                path=path,
                status=status_code,
                weight=weight,
                wait_seconds=f"{wait_seconds:.3f}",
                duration_seconds=f"{duration:.3f}",
                active=self.controller.active_requests,
                waiting=self.controller.waiting,
            )
