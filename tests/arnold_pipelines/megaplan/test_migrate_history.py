"""Tests for historical migration tooling."""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.runtime.migrate_history import migrate_legacy_plan_directory


class TestMigrateHistory:
    def test_migrate_plan_directory_emits_state_artifact(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "legacy"
        plan_dir.mkdir(parents=True)
        state = {
            "name": "legacy",
            "current_state": "gated",
            "iteration": 3,
            "config": {"mode": "code"},
            "meta": {"notes": []},
        }
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

        result = migrate_legacy_plan_directory(plan_dir)
        assert result.migrated is True
        assert result.plan_name == "legacy"
        assert result.events_emitted == 1

        artifact_ids = {a["artifact_id"] for a in result.artifacts_emitted}
        assert "state" in artifact_ids

    def test_migrate_receipts_and_gate_signals(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "legacy"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "legacy", "current_state": "done", "iteration": 1}),
            encoding="utf-8",
        )
        (plan_dir / "receipt_plan.json").write_text(
            json.dumps({"step": "plan", "success": True, "summary": "planned", "artifacts": ["plan_v1.md"]}),
            encoding="utf-8",
        )
        (plan_dir / "gate_signals_v1.json").write_text(
            json.dumps({"signals": {"score": 1.0}, "robustness": "standard", "unresolved_flags": []}),
            encoding="utf-8",
        )

        result = migrate_legacy_plan_directory(plan_dir)
        artifact_ids = {a["artifact_id"] for a in result.artifacts_emitted}
        assert "receipt_plan" in artifact_ids
        assert "gate_signals_v1" in artifact_ids

    def test_missing_state_returns_not_migrated(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "empty"
        plan_dir.mkdir(parents=True)

        result = migrate_legacy_plan_directory(plan_dir)
        assert result.migrated is False
        assert result.events_emitted == 0
        assert len(result.quarantine) == 1

    def test_locks_and_capsules_are_quarantined(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "legacy"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "legacy", "current_state": "running", "iteration": 1}),
            encoding="utf-8",
        )
        (plan_dir / ".plan.lock").write_text("1234", encoding="utf-8")
        (plan_dir / "snapshot.capsule.json").write_text("{}", encoding="utf-8")

        result = migrate_legacy_plan_directory(plan_dir, archive=True)
        reasons = {q.reason for q in result.quarantine}
        assert "lock_archived" in reasons
        assert "capsule_archived" in reasons
        assert (result.archive_dir / ".plan.lock").exists()
        assert (result.archive_dir / "snapshot.capsule.json").exists()
