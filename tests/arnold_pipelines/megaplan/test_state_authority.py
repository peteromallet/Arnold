"""Tests proving manifest-backed callers do not treat ``state.json`` as authority."""

from __future__ import annotations

import json
from pathlib import Path

from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
from arnold.kernel.journal import NDJsonEventJournal

from arnold_pipelines.megaplan.cli.projection import (
    project_execute_status,
    project_gate_status,
    project_inspect,
    project_override_status,
    project_resume_cursor,
    project_status,
    project_trace,
)


class TestStateJsonNotAuthority:
    def _seed_journal(self, artifact_root: Path) -> None:
        journal = NDJsonEventJournal(artifact_root)
        event = EventEnvelope(
            event_id="run:test:prep",
            family=EventFamily.NODE_LIFECYCLE,
            kind="node_completed",
            manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
            run_id="run:test",
            payload_schema_hash="sha256:" + "0" * 64,
            payload={"node_ref": "prep", "outputs": {"status": "prepped"}},
        )
        journal.append(event)

    def test_project_status_ignores_state_json(self, tmp_path: Path) -> None:
        self._seed_journal(tmp_path)
        (tmp_path / "state.json").write_text('{"current_state": "FAKE"}', encoding="utf-8")

        status = project_status(plan_name="test", artifact_root=tmp_path)
        assert status.current_state == "running"
        assert status.completed_nodes == ["prep"]

    def test_project_trace_ignores_state_json(self, tmp_path: Path) -> None:
        self._seed_journal(tmp_path)
        (tmp_path / "state.json").write_text('{"history": ["tampered"]}', encoding="utf-8")

        trace = project_trace(artifact_root=tmp_path)
        assert len(trace) == 1
        assert trace[0].node_ref == "prep"

    def test_project_inspect_flags_no_state_authority(self, tmp_path: Path) -> None:
        self._seed_journal(tmp_path)
        (tmp_path / "state.json").write_text('{"current_state": "FAKE"}', encoding="utf-8")

        inspect = project_inspect(artifact_root=tmp_path, plan_name="test")
        assert inspect["state_json_authority"] is False
        assert inspect["status"]["current_state"] != "FAKE"

    def test_resume_cursor_derives_from_journal(self, tmp_path: Path) -> None:
        self._seed_journal(tmp_path)
        (tmp_path / "state.json").write_text('{"last_event_sequence": 999}', encoding="utf-8")

        cursor = project_resume_cursor(
            artifact_root=tmp_path,
            manifest_hash="sha256:" + "a" * 64,
        )
        assert cursor.event_sequence == 0
        assert cursor.manifest_hash == "sha256:" + "a" * 64

    def test_gate_review_execute_override_projections_use_journal(self, tmp_path: Path) -> None:
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
                "target_node": "finalize",
                "trigger": "gate:proceed",
            },
        )
        journal.append(event)
        (tmp_path / "state.json").write_text('{"last_gate": {"recommendation": "ITERATE"}}', encoding="utf-8")

        gate = project_gate_status(tmp_path)
        assert gate["recommendations"][0]["recommendation"] == "PROCEED"

        overrides = project_override_status(tmp_path)
        assert len(overrides["override_actions"]) == 1

        execute = project_execute_status(tmp_path)
        assert execute["started"] is False
