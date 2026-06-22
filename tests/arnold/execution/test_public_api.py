from __future__ import annotations

from pathlib import Path

import pytest

from arnold.execution import (
    ExecutionRegistries,
    ExecutionResult,
    ExecutionState,
    run,
)
from arnold.manifest import WorkflowManifest, WorkflowNode


def test_run_exposes_sync_manifest_api(tmp_path: Path) -> None:
    manifest = WorkflowManifest(
        id="demo",
        nodes=(WorkflowNode(id="start", kind="agent"),),
    )

    result = run(manifest, artifact_root=tmp_path)

    assert isinstance(result, ExecutionResult)
    assert result.state is ExecutionState.COMPLETED
    assert result.manifest_id == "demo"
    assert result.manifest_hash == manifest.manifest_hash
    assert result.artifact_root == tmp_path


def test_run_uses_supplied_backend_and_registries(tmp_path: Path) -> None:
    manifest = WorkflowManifest(id="demo", nodes=(WorkflowNode(id="start", kind="agent"),))
    registries = ExecutionRegistries(capabilities={"agent.default": object()})
    seen: dict[str, object] = {}

    class RecordingBackend:
        def run_manifest(self, manifest, *, artifact_root, registries, resume_cursor=None):
            seen["manifest"] = manifest
            seen["artifact_root"] = artifact_root
            seen["registries"] = registries
            seen["resume_cursor"] = resume_cursor
            return ExecutionResult(
                state=ExecutionState.SUSPENDED,
                manifest_id=manifest.id,
                manifest_hash=manifest.manifest_hash,
                artifact_root=artifact_root,
                resume_cursor=resume_cursor,
            )

    result = run(manifest, artifact_root=tmp_path, registries=registries, backend=RecordingBackend())

    assert result.state is ExecutionState.SUSPENDED
    assert seen == {
        "manifest": manifest,
        "artifact_root": tmp_path,
        "registries": registries,
        "resume_cursor": None,
    }


def test_result_states_are_explicit() -> None:
    assert {state.value for state in ExecutionState} == {
        "completed",
        "failed",
        "suspended",
        "cancelled",
        "quarantined",
    }


def test_run_rejects_non_manifest_inputs(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(object(), artifact_root=tmp_path)  # type: ignore[arg-type]


def test_run_rejects_dsl_pipeline_and_step_objects(tmp_path: Path) -> None:
    from arnold.workflow.dsl import Pipeline, Step

    pipeline = Pipeline(id="demo", version="1", steps=(Step(id="s1", kind="agent"),))
    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(pipeline, artifact_root=tmp_path)  # type: ignore[arg-type]

    step = Step(id="s1", kind="agent")
    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(step, artifact_root=tmp_path)  # type: ignore[arg-type]
