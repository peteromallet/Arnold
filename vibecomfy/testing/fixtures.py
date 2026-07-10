"""Pytest fixtures and plain factory helpers for VibeComfy user tests (T4).

Builders use only the public `VibeWorkflow` surface — `add_node`, `connect`,
`register_input`, `finalize_metadata` — never private internals.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Protocol

import pytest

from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


class WorkflowFactory(Protocol):
    def __call__(self, id: str = "test-workflow", **metadata: Any) -> VibeWorkflow: ...


class HandleFactory(Protocol):
    def __call__(
        self,
        node_id: str,
        output_slot: int | str = 0,
        output_type: str | None = None,
        name: str | None = None,
    ) -> Handle: ...


def make_workflow_factory() -> WorkflowFactory:
    """Return a callable that builds a minimal `VibeWorkflow` for tests.

    Usage:
        wf = make_workflow_factory()("my-test")
    """

    def _factory(id: str = "test-workflow", **metadata: Any) -> VibeWorkflow:
        wf = VibeWorkflow(id=id, source=WorkflowSource(id=id, source_type="test"))
        for key, value in metadata.items():
            wf.metadata[key] = value
        return wf

    return _factory


def make_handle_factory() -> HandleFactory:
    """Return a callable that builds a public `Handle`."""

    def _factory(
        node_id: str,
        output_slot: int | str = 0,
        output_type: str | None = None,
        name: str | None = None,
    ) -> Handle:
        return Handle(node_id=node_id, output_slot=output_slot, output_type=output_type, name=name)

    return _factory


@pytest.fixture
def vibecomfy_workflow_factory() -> WorkflowFactory:
    """Pytest fixture wrapping `make_workflow_factory`."""
    return make_workflow_factory()


@pytest.fixture
def vibecomfy_handle_factory() -> HandleFactory:
    """Pytest fixture wrapping `make_handle_factory`."""
    return make_handle_factory()


_dry_runtime_cache: dict[str, Any] = {}


class DryRuntime:
    """Small dry-run harness that records compiled prompts."""

    def __init__(self, schema_provider: Any) -> None:
        self.schema_provider = schema_provider
        self.prompts: list[dict[str, Any]] = []

    def __call__(self, wf: VibeWorkflow, **kwargs: Any) -> Any:
        return self.run_sync(wf, **kwargs)

    def run_sync(self, wf: VibeWorkflow, **kwargs: Any) -> Any:
        from vibecomfy.runtime.session import RunResult
        from vibecomfy.testing.dry_run import dry_run

        kwargs.setdefault("schema_provider", self.schema_provider)
        result = dry_run(wf, **kwargs)
        self.prompts.append(result.api_dict)

        run_dir = Path(tempfile.mkdtemp(prefix="vibecomfy-dry-runtime-"))
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text("{}", encoding="utf-8")
        log_path = run_dir / "run.log"
        log_path.write_text("", encoding="utf-8")
        return RunResult(
            run_id=f"dry-{len(self.prompts)}",
            prompt_id=None,
            outputs=[],
            metadata_path=str(metadata_path),
            log_path=str(log_path),
        )


@pytest.fixture(scope="session")
def dry_runtime() -> Any:
    """Session-scoped dry-run helper. Caches a single stub schema provider."""
    from vibecomfy.testing._stub_schema import _StubSchemaProvider

    if "stub" not in _dry_runtime_cache:
        _dry_runtime_cache["stub"] = _StubSchemaProvider()

    return DryRuntime(_dry_runtime_cache["stub"])


__all__ = [
    "make_workflow_factory",
    "make_handle_factory",
    "WorkflowFactory",
    "HandleFactory",
    "DryRuntime",
    "vibecomfy_workflow_factory",
    "vibecomfy_handle_factory",
    "dry_runtime",
]
