from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

from vibecomfy.handles import Handle
from vibecomfy.runtime.session import RunResult
from vibecomfy.workflow import VibeWorkflow, WorkflowSource

WorkflowFactory = Callable[[str], VibeWorkflow]
HandleFactory = Callable[[str, int | str, str | None, str | None], Handle]


def make_workflow_factory() -> WorkflowFactory:
    """Return a small factory for deterministic in-memory workflows."""

    def factory(workflow_id: str = "test-workflow") -> VibeWorkflow:
        return VibeWorkflow(
            id=workflow_id,
            source=WorkflowSource(id=workflow_id, source_type="test"),
        )

    return factory


def make_handle_factory() -> HandleFactory:
    """Return a factory for typed handle placeholders."""

    def factory(
        node_id: str = "1",
        output_slot: int | str = 0,
        output_type: str | None = None,
        name: str | None = None,
    ) -> Handle:
        return Handle(
            node_id=str(node_id),
            output_slot=output_slot,
            output_type=output_type,
            name=name,
        )

    return factory


@dataclass(slots=True)
class DryRuntime:
    """Runtime double that compiles workflows without launching ComfyUI."""

    root: Path
    runs: list[RunResult] = field(default_factory=list)
    prompts: list[dict[str, Any]] = field(default_factory=list)

    async def run(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        return self.run_sync(workflow, backend=backend)

    def run_sync(self, workflow: VibeWorkflow, *, backend: str = "api") -> RunResult:
        run_id = f"dry-run-{len(self.runs) + 1}"
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        api_dict = workflow.compile(backend=backend)
        self.prompts.append(api_dict)
        metadata_path = run_dir / "metadata.json"
        log_path = run_dir / "comfy.log"
        metadata_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "workflow_id": workflow.id,
                    "runtime": "dry",
                    "backend": backend,
                    "api": api_dict,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        log_path.write_text("", encoding="utf-8")
        result = RunResult(
            run_id=run_id,
            prompt_id=None,
            outputs=[],
            metadata_path=str(metadata_path),
            log_path=str(log_path),
        )
        self.runs.append(result)
        return result


@pytest.fixture
def vibecomfy_workflow_factory() -> WorkflowFactory:
    return make_workflow_factory()


@pytest.fixture
def vibecomfy_handle_factory() -> HandleFactory:
    return make_handle_factory()


@pytest.fixture
def dry_runtime(tmp_path: Path) -> DryRuntime:
    return DryRuntime(tmp_path / "dry-runtime")


__all__ = [
    "DryRuntime",
    "HandleFactory",
    "WorkflowFactory",
    "dry_runtime",
    "make_handle_factory",
    "make_workflow_factory",
    "vibecomfy_handle_factory",
    "vibecomfy_workflow_factory",
]
