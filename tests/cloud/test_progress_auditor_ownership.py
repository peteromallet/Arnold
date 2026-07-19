from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.progress_auditor_ownership import (
    OWNERSHIP_SCHEMA,
    inspect_existing_ownership,
    launch_suppressed_by_existing_owner,
)
from arnold_pipelines.megaplan.cloud.progress_auditor_controller import (
    run_escalation_controller,
)
from tests.cloud.test_progress_auditor import _run_dispatch_one
from tests.cloud.test_progress_auditor_escalation import _true_stall


NOW = datetime(2026, 7, 15, 1, 30, tzinfo=timezone.utc)


def _finding(*, blocker_id: str = "blocker:v1:target") -> dict:
    return {
        "session": "target-session",
        "plan": "target-plan",
        "reasons": ["oauth token refresh repair is not converging"],
        "repair_custody_summary": {"blocker_id": blocker_id},
        "current_target": {"target_id": "target-session:target-plan"},
    }


def _write_manifest(root: Path, run_id: str, **overrides) -> Path:
    manifest = {
        "schema_version": "arnold-managed-agent-run-v2",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": run_id,
        "run_kind": "automatic_root_cause_repair",
        "task_kind": "root_cause",
        "status": "running",
        "created_at": "2026-07-15T01:20:00+00:00",
        "started_at": "2026-07-15T01:20:01+00:00",
        "updated_at": "2026-07-15T01:20:02+00:00",
        "description": "repair oauth token refresh for target session",
        "links": {
            "cloud_session": "target-session",
            "plan": "target-plan",
            "blocker_id": "blocker:v1:target",
        },
    }
    manifest.update(overrides)
    path = root / ".megaplan" / "plans" / "resident-subagents" / run_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _inspect(root: Path, finding: dict, *, status_probe=None) -> dict:
    kwargs = {}
    if status_probe is not None:
        kwargs["status_probe"] = status_probe
    return inspect_existing_ownership(
        finding,
        project_root=root,
        workspace_root=None,
        now=NOW,
        **kwargs,
    )


def test_no_matching_agent_keeps_repair_actionable(tmp_path: Path) -> None:
    result = _inspect(tmp_path, _finding())

    assert result["decision"] == "no_matching_agent"
    assert result["suppress_new_repair_launch"] is False
    assert result["actionable"] is True
    assert result["candidate_count"] == 0


def test_healthy_matching_agent_causes_documented_no_new_launch(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "managed-healthy")

    result = _inspect(
        tmp_path,
        _finding(),
        status_probe=lambda _manifest, _path: ("running", True),
    )

    assert result["decision"] == "existing_owner_no_new_launch"
    assert result["healthy_aligned_run_ids"] == ["managed-healthy"]
    assert result["suppress_new_repair_launch"] is True
    assert result["actionable"] is False
    assert launch_suppressed_by_existing_owner(
        {"existing_agent_ownership": result}
    ) is True


@pytest.mark.parametrize(
    ("status", "observed", "live", "expected_health"),
    [
        ("running", "interrupted", False, "stale"),
        ("failed", "failed", False, "failed"),
    ],
)
def test_matching_but_stale_or_failed_agent_remains_actionable(
    tmp_path: Path,
    status: str,
    observed: str,
    live: bool,
    expected_health: str,
) -> None:
    _write_manifest(tmp_path, "managed-unhealthy", status=status)

    result = _inspect(
        tmp_path,
        _finding(),
        status_probe=lambda _manifest, _path: (observed, live),
    )

    assert result["decision"] == "matching_owner_actionable"
    assert result["suppress_new_repair_launch"] is False
    assert result["actionable"] is True
    assert result["candidates"][0]["health"]["classification"] == expected_health


def test_unrelated_agent_does_not_suppress_action(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "managed-unrelated",
        description="repair database migration in another workspace",
        links={
            "cloud_session": "another-session",
            "plan": "another-plan",
            "blocker_id": "blocker:v1:other",
        },
    )

    result = _inspect(
        tmp_path,
        _finding(),
        status_probe=lambda _manifest, _path: ("running", True),
    )

    assert result["decision"] == "no_matching_agent"
    assert result["suppress_new_repair_launch"] is False
    assert result["candidates"][0]["match"]["classification"] == "unrelated"


def test_ambiguous_prose_overlap_is_surfaced_without_guessing(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "managed-ambiguous",
        description="investigate oauth token refresh failure",
        links={},
    )

    result = _inspect(
        tmp_path,
        _finding(blocker_id=""),
        status_probe=lambda _manifest, _path: ("running", True),
    )

    assert result["decision"] == "ambiguous_overlap_requires_judgement"
    assert result["ambiguous_run_ids"] == ["managed-ambiguous"]
    assert result["suppress_new_repair_launch"] is False
    assert result["actionable"] is True
    assert "prose_or_partial_scope_overlap_not_treated_as_ownership" in result["uncertainties"]
    assert result["candidates"][0]["direction"]["classification"] == "uncertain"


def test_read_only_review_does_not_claim_repair_direction(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "managed-review",
        run_kind="automatic_progress_audit_agent",
        task_kind="review",
    )

    result = _inspect(
        tmp_path,
        _finding(),
        status_probe=lambda _manifest, _path: ("running", True),
    )

    assert result["decision"] == "matching_owner_actionable"
    assert result["candidates"][0]["direction"]["classification"] == "wrong_scope"
    assert result["suppress_new_repair_launch"] is False


def _healthy_ownership() -> dict:
    return {
        "schema_version": OWNERSHIP_SCHEMA,
        "decision": "existing_owner_no_new_launch",
        "suppress_new_repair_launch": True,
        "healthy_aligned_run_ids": ["managed-existing-owner"],
    }


def test_wrapper_noops_before_launching_a_reviewer_for_healthy_owner(
    tmp_path: Path,
) -> None:
    brief, response, error, updated = _run_dispatch_one(
        tmp_path,
        gather_payload={
            "plan": "target-plan",
            "session": "target-session",
            "reasons": ["true stall"],
            "session_header": {"kind": "chain"},
            "existing_agent_ownership": _healthy_ownership(),
        },
    )

    assert "existing_agent_ownership" in brief
    assert response.startswith("NO_NEW_LAUNCH\n")
    assert error == ""
    assert updated["existing_agent_judgement"] == {
        "decision": "no_new_launch_no_op",
        "owner_run_id": "managed-existing-owner",
        "basis": "healthy_live_manifest_with_stable_objective_alignment",
        "reviewer_launched": False,
        "repair_launched": False,
    }
    assert updated["codex_launch_attempted"] is False
    assert updated["_codex_argv"] == []


def test_authorized_controller_noops_before_repair_dispatch_for_healthy_owner(
    tmp_path: Path,
) -> None:
    finding = _true_stall()
    finding["existing_agent_ownership"] = _healthy_ownership()
    queue = tmp_path / ".megaplan" / "repair-queue"

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("healthy owner must suppress repair dispatch")
        ),
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "existing_owner_no_new_launch"
    assert item["existing_owner_run_id"] == "managed-existing-owner"
    assert item["repair_dispatched"] is False
    assert result["l3_escalation_summary"]["dispatched"] == 0
    assert not (queue / "requests").exists()
