"""Deterministic fake omp RPC client fixtures for worker tests.

Implements the duck-typed ``RpcClient`` surface that
``arnold_pipelines.megaplan.workers.omp.run_omp_step`` consumes, so tests can
exercise the full worker error matrix, structured-output capture, retry
semantics, and cost reconciliation without spawning a ``bun --mode rpc``
child.  Each fake records lifecycle calls (``start``/``stop``/``set_model``/
``set_thinking_level``) for orphan-child and attempt-idempotency assertions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from omp_rpc import (
    PromptTurn,
    RpcProcessExitError,
    RpcProtocolError,
    RpcTimeoutError,
)


class _FakeSessionStats:
    def __init__(self, tokens: Mapping[str, int] | None = None, cost: float = 0.0):
        self.tokens = dict(tokens or {})
        self.cost = cost
        self.session_id = "fake-session"
        self.session_file = None
        self.user_messages = 1
        self.assistant_messages = 1
        self.tool_calls = 0
        self.tool_results = 0
        self.total_messages = 2
        self.premium_requests = 0


@dataclass
class FakeRpcClient:
    """Scripted fake implementing the omp RpcClient duck-typed surface."""

    provider: str | None = None
    model: str | None = None
    cwd: str | None = None
    thinking: str | None = None
    tools: Sequence[str] | None = None
    custom_tools: Sequence[Any] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    startup_timeout: float = 30.0
    request_timeout: float = 30.0

    # ── Scripted behavior ──────────────────────────────────────────────
    #: Callable(turn) invoked from prompt_and_wait; may raise.
    turn_factory: Callable[[], PromptTurn] | None = None
    #: Exception raised from start(); simulates launch failures.
    start_error: BaseException | None = None
    #: Exception raised from set_model().
    set_model_error: BaseException | None = None
    #: Messages returned by get_messages().
    messages: list[dict[str, Any]] = field(default_factory=list)
    #: Session stats returned by get_session_stats().
    session_stats: _FakeSessionStats | None = None
    #: Exception raised from prompt_and_wait().
    prompt_error: BaseException | None = None
    #: stderr text exposed after failures.
    stderr_text: str = ""
    #: Fail start() the first N attempts, then succeed (retry fixture).
    start_failures_before_success: int = 0

    # ── Lifecycle recording ────────────────────────────────────────────
    started: int = field(default=0, init=False)
    stopped: int = field(default=0, init=False)
    set_model_calls: list[tuple[str, str]] = field(default_factory=list, init=False)
    thinking_levels: list[str | None] = field(default_factory=list, init=False)
    prompt_calls: int = field(default=0, init=False)
    abort_calls: int = field(default=0, init=False)
    #: Recorded ``set_auto_compaction`` calls (bool payloads) — memory-lever
    #: observability for the cgroup-OOM worker fix (occurrence 1ac805e5eef9).
    auto_compaction_calls: list[bool] = field(default_factory=list, init=False)
    #: When set, ``set_auto_compaction`` raises this exception (simulates an
    #: RpcClient that does not implement the lever).
    auto_compaction_error: BaseException | None = None

    @property
    def stderr(self) -> str:
        return self.stderr_text

    @property
    def command(self) -> tuple[str, ...]:
        return ("omp", "--mode", "rpc", "--provider", str(self.provider), "--model", str(self.model))

    def start(self) -> "FakeRpcClient":
        if self.start_error is not None:
            raise self.start_error
        if self.started < self.start_failures_before_success:
            self.started += 1
            raise RpcProcessExitError("omp exited before ready", 1)
        self.started += 1
        return self

    def stop(self) -> None:
        self.stopped += 1

    def __enter__(self) -> "FakeRpcClient":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def set_auto_compaction(self, enabled: bool) -> None:
        if self.auto_compaction_error is not None:
            raise self.auto_compaction_error
        self.auto_compaction_calls.append(enabled)

    def set_model(self, provider: str, model_id: str) -> Any:
        if self.set_model_error is not None:
            raise self.set_model_error
        self.set_model_calls.append((provider, model_id))
        return type(
            "ModelInfo",
            (),
            {
                "id": model_id,
                "name": model_id,
                "provider": provider,
                "reasoning": True,
            },
        )()

    def get_state(self) -> Any:
        return type(
            "SessionState",
            (),
            {
                "model": None,
                "session_id": "fake-session",
                "thinking_level": self.thinking,
                "is_streaming": False,
            },
        )()

    def set_thinking_level(self, level: str) -> None:
        self.thinking_levels.append(level)

    def abort(self) -> None:
        self.abort_calls += 1

    def prompt_and_wait(
        self, message: str, *, timeout: float | None = None
    ) -> PromptTurn:
        self.prompt_calls += 1
        if self.prompt_error is not None:
            raise self.prompt_error
        if self.turn_factory is None:
            raise AssertionError("fake client has no turn_factory scripted")
        return self.turn_factory()

    def get_messages(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.messages)

    def get_session_stats(self) -> _FakeSessionStats | None:
        return self.session_stats


# ── Turn builders ───────────────────────────────────────────────────────

def make_turn(
    *,
    assistant_text: str | None = None,
    error_message: str | None = None,
    stop_reason: str = "stop",
    usage: Mapping[str, Any] | None = None,
) -> PromptTurn:
    """Build a PromptTurn with an optional assistant message + usage."""
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": [],
        "api": "openai-completions",
        "provider": "fake",
        "model": "fake/model",
        "stopReason": stop_reason,
        "timestamp": 0,
    }
    if error_message is not None:
        assistant_message["errorMessage"] = error_message
    if usage is not None:
        assistant_message["usage"] = dict(usage)
    return PromptTurn(
        events=(),
        messages=(assistant_message,),
        assistant_message=assistant_message,
        assistant_text=assistant_text,
    )


def usage_message(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    cache_write: int = 0,
    cost_total: float | None = None,
    total_tokens: int | None = None,
) -> dict[str, Any]:
    """Build an AssistantMessage dict with a ``usage`` payload."""
    usage: dict[str, Any] = {
        "input": input_tokens,
        "output": output_tokens,
        "cacheRead": cache_read,
        "cacheWrite": cache_write,
    }
    if total_tokens is not None:
        usage["totalTokens"] = total_tokens
    if cost_total is not None:
        usage["cost"] = {
            "input": cost_total * 0.5,
            "output": cost_total * 0.5,
            "cacheRead": 0.0,
            "cacheWrite": 0.0,
            "total": cost_total,
        }
    return {
        "role": "assistant",
        "content": [],
        "api": "openai-completions",
        "provider": "fake",
        "model": "fake/model",
        "usage": usage,
        "stopReason": "stop",
        "timestamp": 0,
    }


__all__ = [
    "FakeRpcClient",
    "make_turn",
    "usage_message",
    "_FakeSessionStats",
]
