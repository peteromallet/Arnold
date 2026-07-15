from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.repair_investigation import (
    MAX_CONTEXT_BYTES,
    REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
    build_investigation_context,
    validate_investigator_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    workspace = tmp_path / "workspace"
    plan = "current-m5a"
    spec = workspace / ".megaplan/initiatives/demo/chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    state = workspace / ".megaplan/plans" / plan / "state.json"
    _write(
        state,
        {
            "name": plan,
            "current_state": "blocked",
            "latest_failure": {
                "failure_kind": "execution_blocked",
                "phase": "execute",
                "task_id": "T30",
                "message": "exact CAS receipt error",
            },
            "history": [{"step": "execute", "result": "blocked"}],
        },
    )
    (state.parent / "events.ndjson").write_text("", encoding="utf-8")
    _write(
        workspace / ".megaplan/plans/.chains/chain.json",
        {
            "current_plan_name": plan,
            "current_milestone_index": 1,
            "completed": [{"plan": "m5"}],
            "last_state": "blocked",
            "metadata": {"chain_spec_path": str(spec)},
        },
    )
    repair_data = tmp_path / "repair-data.json"
    _write(
        repair_data,
        {
            "outcome": "repairing",
            "attempts": [
                {
                    "attempt_id": index,
                    "dev_hypothesis": f"prior hypothesis {index}",
                    "dev_summary": [f"prior action {index}"],
                    "problem_signature": {"phase_or_step": "execute"},
                }
                for index in range(10)
            ],
        },
    )
    request = tmp_path / "request.json"
    _write(
        request,
        {
            "request_id": "old-request",
            "problem_signature": {
                "milestone_or_plan": "old-m5",
                "phase_or_step": "review",
            },
            "target": {"plan_name": "old-m5"},
        },
    )
    goal = tmp_path / "goal.json"
    _write(
        goal,
        {
            "goal_id": "goal-1",
            "checkpoint_digest": "abc",
            "target": {"plan_name": plan},
            "frozen_checkpoint": {
                "latest_failure": {"message": "exact frozen execute error"}
            },
        },
    )
    return workspace, spec, repair_data, request, goal


def test_context_is_bounded_and_carries_exact_error_and_recent_repairs(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    assert len(json.dumps(context).encode()) <= MAX_CONTEXT_BYTES
    assert context["exact_error"]["message"] == "exact CAS receipt error"
    assert [item["attempt_id"] for item in context["prior_repairs"]] == [4, 5, 6, 7, 8, 9]
    assert context["request"]["matches_current_target"] is False
    assert context["frozen_checkpoint"]["latest_failure"]["message"] == (
        "exact frozen execute error"
    )
    assert "old-m5" in context["request"]["mismatch_reason"]
    assert len(context["context_digest"]) == 64


def test_investigator_receipt_is_bound_to_context_and_requires_evidence() -> None:
    receipt = {
        "schema_version": REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
        "context_digest": "digest-1",
        "real_blocker": "mechanical relaunch ignores a fresh execute worker",
        "evidence_paths": ["/workspace/state.json"],
        "prior_repairs_considered": ["attempt-11"],
        "preserve_live": True,
        "recommended_action": "preserve_live",
        "guard_weakening_risk": "none",
    }

    assert validate_investigator_receipt(receipt, expected_context_digest="digest-1") == receipt
    with pytest.raises(ValueError, match="context digest disagrees"):
        validate_investigator_receipt(receipt, expected_context_digest="digest-2")


def test_repair_loop_embeds_bounded_context_for_sandbox_independent_investigation() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert '<authoritative_repair_context>' in wrapper
    assert 'cat "$INVESTIGATION_CONTEXT_PATH" >> "$INVESTIGATOR_PROMPT_PATH"' in wrapper
    assert "does not depend on filesystem sandbox availability" in wrapper
