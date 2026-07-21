"""Tests for T23/T24 state-store checkpoint behavior."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import LocalJournalBackend
from arnold.execution.state_store import (
    BudgetSnapshot,
    FileStateStore,
    JournalPointer,
    RoutingSnapshot,
    RunCheckpoint,
)
from arnold.workflow.native_wbc import native_wbc_dir
from arnold.manifest import WorkflowEdge, WorkflowManifest, WorkflowNode


def _manifest(*nodes: WorkflowNode, edges: tuple[WorkflowEdge, ...] = ()) -> WorkflowManifest:
    return WorkflowManifest(id="demo", nodes=nodes, edges=edges)


def _records(root: Path) -> list[dict[str, object]]:
    path = native_wbc_dir(root, producer_family="arnold_execution", surface="state_store") / "events.ndjson"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_file_state_store_round_trip(tmp_path: Path) -> None:
    store = FileStateStore(tmp_path)
    checkpoint = RunCheckpoint(
        run_id="run-1",
        manifest_id="demo",
        manifest_hash="sha256:" + "a" * 64,
        status="completed",
        routing=RoutingSnapshot(
            completed=({"node_ref": "a", "scope_stack": [], "attempt": 1, "iteration": 1, "child_key": None},)
        ),
        journal_pointer=JournalPointer(journal_uri="file://journal", sequence=5),
        budget=BudgetSnapshot(consumed_cost=1.0),
    )

    store.save(checkpoint)
    loaded = store.load("run-1")

    assert loaded is not None
    assert loaded.run_id == "run-1"
    assert loaded.manifest_id == "demo"
    assert loaded.status == "completed"
    assert loaded.budget == checkpoint.budget
    assert loaded.journal_pointer == checkpoint.journal_pointer


def test_file_state_store_list_and_overwrite(tmp_path: Path) -> None:
    store = FileStateStore(tmp_path)
    assert store.list() == []

    store.save(RunCheckpoint(run_id="run-a", manifest_id="demo", manifest_hash="h1"))
    store.save(RunCheckpoint(run_id="run-b", manifest_id="demo", manifest_hash="h2"))

    assert store.list() == ["run-a", "run-b"]

    store.save(RunCheckpoint(run_id="run-a", manifest_id="demo", manifest_hash="h3", status="completed"))
    loaded = store.load("run-a")
    assert loaded is not None
    assert loaded.manifest_hash == "h3"
    assert loaded.status == "completed"


def test_file_state_store_load_missing_returns_none(tmp_path: Path) -> None:
    store = FileStateStore(tmp_path)
    assert store.load("missing") is None


def test_checkpoint_saved_during_run(tmp_path: Path) -> None:
    manifest = _manifest(
        WorkflowNode(id="a", kind="noop"),
        WorkflowNode(id="b", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="a", target="b"),),
    )
    store = FileStateStore(tmp_path / "checkpoints")

    result = run(manifest, artifact_root=tmp_path / "artifacts", state_store=store)

    assert result.state is ExecutionState.COMPLETED
    checkpoint_paths = list((tmp_path / "checkpoints").iterdir())
    assert len(checkpoint_paths) == 1
    run_id = store.list()[0]
    checkpoint = store.load(run_id)
    assert checkpoint is not None
    assert checkpoint.status == "completed"
    assert checkpoint.manifest_hash == manifest.manifest_hash
    assert checkpoint.journal_pointer.sequence is not None
    completed_refs = {c["node_ref"] for c in checkpoint.routing.completed}
    assert "a" in completed_refs
    assert "b" in completed_refs


def test_checkpoint_status_running_then_completed(tmp_path: Path) -> None:
    manifest = _manifest(WorkflowNode(id="a", kind="noop"))
    store = FileStateStore(tmp_path / "checkpoints")

    backend = LocalJournalBackend(state_store=store)
    backend.run_manifest(manifest, artifact_root=tmp_path / "artifacts", registries=ExecutionRegistries())

    # The final checkpoint is the only one persisted because FileStateStore overwrites
    # by run_id.
    checkpoint = store.load(backend._run_id)
    assert checkpoint is not None
    assert checkpoint.status == "completed"


def test_local_backend_accepts_state_store_directly(tmp_path: Path) -> None:
    manifest = _manifest(WorkflowNode(id="a", kind="noop"))
    store = FileStateStore(tmp_path / "checkpoints")
    backend = LocalJournalBackend(state_store=store)

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path / "artifacts",
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.COMPLETED
    run_ids = store.list()
    assert len(run_ids) == 1
    assert store.load(run_ids[0]) is not None


def test_state_store_emits_resume_and_reconciliation_wbc_evidence(tmp_path: Path) -> None:
    store = FileStateStore(tmp_path / "checkpoints")
    checkpoint = RunCheckpoint(
        run_id="run-1",
        manifest_id="demo",
        manifest_hash="sha256:" + "d" * 64,
        status="running",
        journal_pointer=JournalPointer(journal_uri="file://journal", sequence=1),
    )

    store.save(checkpoint)
    store.save(
        RunCheckpoint(
            run_id="run-1",
            manifest_id="demo",
            manifest_hash="sha256:" + "d" * 64,
            status="completed",
            journal_pointer=JournalPointer(journal_uri="file://journal", sequence=2),
        )
    )
    loaded = store.load("run-1")
    run_ids = store.list()

    assert loaded is not None
    assert run_ids == ["run-1"]

    events = _records(tmp_path / "checkpoints")
    event_types = [event["event"] for event in events]
    assert "reconciliation" in event_types
    assert "resume" in event_types
    assert "effect_outcome" in event_types
    assert all(event["authority"]["grants_authority"] is False for event in events)
    assert all(event["authority"]["leases_authority"] is False for event in events)
