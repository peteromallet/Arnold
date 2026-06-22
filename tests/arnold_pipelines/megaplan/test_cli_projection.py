"""Tests for CLI projection helpers backed by manifest journal events."""

from __future__ import annotations

from pathlib import Path

from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
from arnold.kernel.journal import NDJsonEventJournal


def _append_event(
    journal: NDJsonEventJournal,
    *,
    kind: str,
    payload: dict,
    family: EventFamily = EventFamily.NODE_LIFECYCLE,
) -> None:
    event = EventEnvelope(
        event_id=f"run:test:{kind}",
        family=family,
        kind=kind,
        manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
        run_id="run:test",
        payload_schema_hash="sha256:" + "0" * 64,
        payload=payload,
    )
    journal.append(event)


class TestStatusProjection:
    def test_project_status_from_events(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "prep"})
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep", "outputs": {}})
        _append_event(journal, kind="node_started", payload={"node_ref": "plan"})

        status = project_status(plan_name="test", artifact_root=tmp_path)
        assert status.plan_name == "test"
        assert status.completed_nodes == ["prep"]
        assert status.active_node == "plan"
        assert status.current_state == "running"

    def test_project_status_terminal_completed(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})
        _append_event(journal, kind="run_completed", payload={"reason": "done"})

        status = project_status(plan_name="test", artifact_root=tmp_path)
        assert status.current_state == "done"

    def test_project_status_suspended(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_suspended", payload={"node_ref": "gate", "route_id": "gate:human"})

        status = project_status(plan_name="test", artifact_root=tmp_path)
        assert status.current_state == "awaiting_human"
        assert status.suspended_nodes == ["gate"]


class TestTraceProjection:
    def test_project_trace_filters_by_node(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_trace

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "prep"})
        _append_event(journal, kind="node_started", payload={"node_ref": "plan"})
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})

        rows = project_trace(artifact_root=tmp_path, node_refs=("prep",))
        assert len(rows) == 2
        assert all(row.node_ref == "prep" for row in rows)


class TestCommandProjections:
    def test_project_gate_status(self, tmp_path: Path) -> None:
        from arnold.kernel.control import ControlTarget, ControlTransition, ControlTransitionType
        from arnold_pipelines.megaplan.cli.projection import project_gate_status

        journal = NDJsonEventJournal(tmp_path)
        event = EventEnvelope(
            event_id="run:test:ct",
            family=EventFamily.CONTROL_TRANSITION,
            kind="control_transition",
            manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
            run_id="run:test",
            payload_schema_hash="sha256:" + "0" * 64,
            payload={
                "kind": "override",
                "source_node": "gate",
                "target_node": "revise",
                "trigger": "gate:iterate",
            },
        )
        journal.append(event)

        gate_status = project_gate_status(artifact_root=tmp_path)
        assert len(gate_status["recommendations"]) == 1
        assert gate_status["recommendations"][0]["recommendation"] == "ITERATE"

    def test_project_review_status(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_review_status

        journal = NDJsonEventJournal(tmp_path)
        event = EventEnvelope(
            event_id="run:test:review",
            family=EventFamily.CONTROL_TRANSITION,
            kind="control_transition",
            manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
            run_id="run:test",
            payload_schema_hash="sha256:" + "0" * 64,
            payload={
                "kind": "override",
                "source_node": "review",
                "target_node": "halt",
                "trigger": "review:pass",
            },
        )
        journal.append(event)

        review_status = project_review_status(artifact_root=tmp_path)
        assert review_status["verdicts"][0]["verdict"] == "PASS"

    def test_project_execute_status(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_execute_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "execute"})

        status = project_execute_status(artifact_root=tmp_path)
        assert status["started"] is True
        assert status["completed"] is False

    def test_project_inspect_does_not_read_state_json(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_inspect

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})

        # Write a misleading state.json to prove it is not consulted.
        (tmp_path / "state.json").write_text('{"current_state": "FAKE"}', encoding="utf-8")

        inspect = project_inspect(artifact_root=tmp_path, plan_name="test", manifest_hash="sha256:abc")
        assert inspect["source_authority"] == "manifest_journal"
        assert inspect["state_json_authority"] is False
        assert inspect["status"]["current_state"] == "running"


class TestResumeCursorProjection:
    def test_project_resume_cursor_from_journal(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_resume_cursor

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_suspended", payload={"node_ref": "gate"})

        cursor = project_resume_cursor(
            artifact_root=tmp_path,
            manifest_hash="sha256:" + "a" * 64,
        )
        assert cursor.manifest_hash == "sha256:" + "a" * 64
        assert cursor.artifact_root == str(tmp_path)
        assert cursor.event_sequence is not None
