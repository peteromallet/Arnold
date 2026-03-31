"""Shared benchmark interfaces for the eval harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from evals.audit import EvalAudit
    from evals.config import EvalConfig
    from evals.run_evals import CommandRunner, PreparedWorkspace


ScoringStatus = Literal["passed", "failed", "error", "escalated"]


@dataclass(slots=True)
class ScoringResult:
    status: ScoringStatus
    build_result: dict[str, Any] | None = None
    eval_result: dict[str, Any] | None = None
    test_result: dict[str, Any] | None = None
    results_json: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    conditional: bool = False


@dataclass(slots=True)
class VerifyResult:
    passed: bool
    test_output: str
    tests_run: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@runtime_checkable
class Benchmark(Protocol):
    def setup_source(
        self,
        config: "EvalConfig",
        *,
        timeout_seconds: int | None = None,
        runner: "CommandRunner | None" = None,
    ) -> Path: ...

    def list_tasks(
        self,
        source_root: Path,
        configured: list[str],
        cli_selected: list[str] | None,
    ) -> list[str]: ...

    def prepare_workspace(
        self,
        task_name: str,
        source_root: str | Path,
        config: "EvalConfig",
        *,
        timeout_seconds: int | None = None,
        runner: "CommandRunner | None" = None,
    ) -> "PreparedWorkspace": ...

    def read_prompt(self, task_name: str, source_root: str | Path) -> str: ...

    def score(
        self,
        prepared: "PreparedWorkspace",
        audit: "EvalAudit",
        config: "EvalConfig",
        *,
        build_fn: Any = None,
        results_fn: Any = None,
        eval_fn: Any = None,
    ) -> ScoringResult: ...

    def capture_environment(self, source_root: str | Path) -> dict[str, Any]: ...

    def megaplan_env_overrides(self, prepared: "PreparedWorkspace") -> dict[str, str]: ...

    def cleanup_workspace(self, prepared: "PreparedWorkspace") -> None: ...

__all__ = ["Benchmark", "ScoringResult", "ScoringStatus", "VerifyResult"]
