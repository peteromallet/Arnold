"""Tests for T27/T28 observability behavior."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import LocalJournalBackend, NodeOutcome, NodeState
from arnold.execution.observability import ExecutionLogger, ProgressReport, build_progress_report
from arnold.execution.state_store import FileStateStore
from arnold.manifest import WorkflowEdge, WorkflowManifest, WorkflowNode, WorkflowPolicy
from arnold.manifest import BudgetPolicy


def _manifest(*nodes: WorkflowNode, edges: tuple[WorkflowEdge, ...] = (), policy=None) -> WorkflowManifest:
    return WorkflowManifest(id="demo", nodes=nodes, edges=edges, policy=policy)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _capture_logger() -> tuple[ExecutionLogger, _CaptureHandler]:
    logger = logging.getLogger("arnold.execution.test_obs")
    logger.setLevel(logging.DEBUG)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    return ExecutionLogger(logger), handler


def _event_kinds(handler: _CaptureHandler) -> list[str]:
    return [getattr(r, "arnold_event_kind", r.message) for r in handler.records]


def test_logger_emits_run_started_and_completed(tmp_path: Path) -> None:
    logger, handler = _capture_logger()
    manifest = _manifest(WorkflowNode(id="a", kind="noop"))

    result = run(manifest, artifact_root=tmp_path, logger=logger)

    assert result.state is ExecutionState.COMPLETED
    kinds = _event_kinds(handler)
    assert "run_started" in kinds
    assert "run_completed" in kinds


def test_logger_emits_node_started_and_completed(tmp_path: Path) -> None:
    logger, handler = _capture_logger()
    manifest = _manifest(WorkflowNode(id="a", kind="noop"))

    run(manifest, artifact_root=tmp_path, logger=logger)

    kinds = _event_kinds(handler)
    assert "node_started" in kinds
    assert "node_completed" in kinds


def test_logger_emits_node_failed_and_run_failed(tmp_path: Path) -> None:
    logger, handler = _capture_logger()
    manifest = _manifest(
        WorkflowNode(id="fragile", kind="task", policy=WorkflowPolicy(retry=WorkflowPolicy(retry=None).retry)),
    )
    # Single attempt failure: no retry policy, so it fails immediately.
    backend = LocalJournalBackend(logger=logger)
    backend._execute_node_payload = lambda coordinate, node, context: NodeOutcome(state=NodeState.FAILED, error="boom")  # type: ignore[method-assign]

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.FAILED
    kinds = _event_kinds(handler)
    assert "node_started" in kinds
    assert "node_failed" in kinds


def test_logger_emits_budget_events(tmp_path: Path) -> None:
    logger, handler = _capture_logger()
    manifest = _manifest(
        WorkflowNode(id="spender", kind="task"),
        policy=WorkflowPolicy(budget=BudgetPolicy(max_cost=10.0)),
    )
    backend = LocalJournalBackend(logger=logger)
    backend._budget_for_node = lambda coordinate, node: __import__("arnold.kernel", fromlist=["BudgetReservation"]).BudgetReservation(node_ref=coordinate.node_ref, cost=2.0)  # type: ignore[method-assign]

    result = backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    assert result.state is ExecutionState.COMPLETED
    kinds = _event_kinds(handler)
    assert "budget_reserved" in kinds
    assert "budget_settled" in kinds


def test_logger_emits_checkpoint_saved_when_store_attached(tmp_path: Path) -> None:
    logger, handler = _capture_logger()
    store = FileStateStore(tmp_path / "checkpoints")
    manifest = _manifest(WorkflowNode(id="a", kind="noop"))

    run(manifest, artifact_root=tmp_path / "artifacts", state_store=store, logger=logger)

    assert any(getattr(r, "arnold_event_kind", None) == "checkpoint_saved" for r in handler.records)


def test_build_progress_report_from_journal(tmp_path: Path) -> None:
    manifest = _manifest(
        WorkflowNode(id="a", kind="noop"),
        WorkflowNode(id="b", kind="noop"),
        edges=(WorkflowEdge(id="e1", source="a", target="b"),),
    )
    run(manifest, artifact_root=tmp_path)

    from arnold.kernel import read_event_journal

    events = read_event_journal(tmp_path)
    report = build_progress_report(events)

    assert isinstance(report, ProgressReport)
    assert report.total_nodes == 2
    assert report.completed == 2
    assert report.pending == 0
    assert report.failed == 0


def test_build_progress_report_failed_node(tmp_path: Path) -> None:
    manifest = _manifest(WorkflowNode(id="a", kind="task"))
    backend = LocalJournalBackend()
    backend._execute_node_payload = lambda coordinate, node, context: NodeOutcome(state=NodeState.FAILED, error="boom")  # type: ignore[method-assign]
    backend.run_manifest(manifest, artifact_root=tmp_path, registries=ExecutionRegistries())

    from arnold.kernel import read_event_journal

    events = read_event_journal(tmp_path)
    report = build_progress_report(events)

    assert report.total_nodes == 1
    assert report.failed == 1
    assert report.completed == 0
    assert report.health_status == "healthy"
