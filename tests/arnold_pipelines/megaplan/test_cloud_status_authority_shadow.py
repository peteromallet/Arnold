from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from arnold_pipelines.megaplan.cloud.status_snapshot import _compose_shadow_views


def test_cloud_status_shadow_keeps_authority_liveness_and_custody_separate(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "session.json"
    watchdog_path = tmp_path / "watchdog-report.json"
    needs_human_path = tmp_path / "session.needs-human.json"
    repair_progress_path = tmp_path / "session.repair-progress.json"
    plan_source = str(tmp_path / "plans" / "plan-1" / "state.json")
    chain_source = str(tmp_path / "chains" / "session.json")

    views = _compose_shadow_views(
        session="session-1",
        marker={
            "branch": "main",
            "dirty_workspace": False,
            "auth": True,
            "no_push": False,
        },
        marker_path=marker_path,
        watchdog_report_path=watchdog_path,
        watchdog_item={"status": "stale"},
        chain_health={
            "last_state": "executing",
            "pushed_sha": "abc123",
            "pr_number": 42,
        },
        needs_human={"summary": "approval required"},
        needs_human_path=needs_human_path,
        repair_progress={"updated_at": "2026-07-11T00:00:00Z", "status": "active"},
        repair_progress_path=repair_progress_path,
        plan_state={"tasks": [{"id": "T1", "status": "done"}]},
        current_target={
            "plan_state": {
                "name": "plan-1",
                "current_state": "done",
                "path": plan_source,
            },
            "chain_state": {
                "last_state": "executing",
                "path": chain_source,
            },
        },
        liveness={"tmux": False, "process": False},
        latest_activity="2026-07-11T00:00:00Z",
        now=datetime(2026, 7, 11, 0, 10, tzinfo=timezone.utc),
    )

    shadow = views["status_authority_shadow"]
    diagnostics = {item["code"]: item for item in shadow["diagnostics"]}

    assert shadow["shadow"] is True
    assert shadow["read_only"] is True
    assert shadow["status_consumers_unchanged"] is True
    assert views["execution_authority"]["shadow"] is True
    assert views["runner"]["shadow"] is True
    assert views["publication"]["shadow"] is True

    assert diagnostics["legacy_status_execution_authority_drift"]["source"] == (
        f"{plan_source},{chain_source}"
    )
    assert diagnostics["runner_liveness_separate_from_execution_authority"][
        "source"
    ] == str(watchdog_path)
    assert diagnostics["publication_separate_from_execution_authority"][
        "domain"
    ] == "publication"
    assert diagnostics["human_gate_separate_from_execution_authority"][
        "source"
    ] == str(needs_human_path)
    assert diagnostics["recovery_custody_separate_from_execution_authority"][
        "source"
    ] == str(repair_progress_path)
    assert "runner" not in views["execution_authority"]
    assert "publication" not in views["execution_authority"]
