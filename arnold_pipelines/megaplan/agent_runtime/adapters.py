"""Dependency-free adapter protocols for agent runtime integrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from arnold.agent.contracts import AgentDispatcher
from arnold_pipelines.megaplan.agent_runtime.contracts import AgentRequest, AgentResult


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PromptProvider(Protocol):
    def prompt_for(self, request: AgentRequest) -> str: ...


@runtime_checkable
class SessionStore(Protocol):
    def get_session(self, key: str) -> dict[str, Any] | None: ...

    def put_session(self, key: str, session: dict[str, Any]) -> None: ...


@runtime_checkable
class EventEmitter(Protocol):
    def emit(self, event: str, payload: dict[str, Any]) -> None: ...


@runtime_checkable
class LivenessTouch(Protocol):
    def touch(self) -> None: ...


@runtime_checkable
class KeySource(Protocol):
    def key_for(self, agent: str) -> str | None: ...


@runtime_checkable
class CommandRunner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> CommandResult: ...


__all__ = [
    "AgentDispatcher",
    "PromptProvider",
    "SessionStore",
    "EventEmitter",
    "LivenessTouch",
    "KeySource",
    "CommandRunner",
    "CommandResult",
]
