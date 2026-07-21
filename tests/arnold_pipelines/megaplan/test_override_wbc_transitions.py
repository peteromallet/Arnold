from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.control.interface import ControlTransition
from arnold_pipelines.megaplan.control_interface import apply_transition, emit_override_authority_receipt
from arnold_pipelines.megaplan.orchestration.override_authority import OverrideAuthorityError
from arnold_pipelines.megaplan.planning.control_binding import planning_run_state_view


_RECEIPT_FILES = {
    "abort": "override_abort_authority.json",
    "force-proceed": "override_force_proceed_authority.json",
    "replan": "override_replan_authority.json",
    "recover-blocked": "override_recover_blocked_authority.json",
    "resume-clarify": "override_resume_clarify_authority.json",
    "adopt-execution": "override_adopt_execution_authority.json",
    "suspension-waiver": "override_suspension_authority.json",
    "human-gate": "override_human_gate_authority.json",
}
_ACTION_TYPES = {
    "abort": "cancellation",
    "force-proceed": "completion",
    "replan": "publication",
    "recover-blocked": "repair",
    "resume-clarify": "delivery",
    "adopt-execution": "publication",
    "suspension-waiver": "delivery",
    "human-gate": "delivery",
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_state(root: Path, *, current_state: str = "critiqued") -> dict[str, object]:
    return {
        "name": "demo-plan",
        "idea": "Override WBC receipt test",
        "current_state": current_state,
        "iteration": 1,
        "created_at": "2026-07-20T00:00:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [{"file": "plan_v1.md"}],
        "history": [],
        "meta": {"current_invocation_id": "inv-override"},
        "last_gate": {},
        "latest_failure": None,
    }


def _required_artifacts(action: str) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    if action == "adopt-execution":
        artifacts["execution.json"] = {
            "task_updates": [{"task_id": "T1", "status": "done"}],
            "sense_check_acknowledgments": [{"sense_check_id": "SC1"}],
        }
        artifacts["finalize.json"] = {
            "tasks": [{"id": "T1", "status": "done"}],
            "sense_checks": [{"id": "SC1"}],
        }
    if action == "suspension-waiver":
        artifacts["human_verifications.json"] = [{"criterion_idx": 0, "verdict": "pass"}]
    if action == "human-gate":
        artifacts["approval_record.json"] = {
            "approval_scope": "execute:approval-approved",
            "approved": True,
        }
    return artifacts


def _emit_receipt(tmp_path: Path, action: str) -> dict[str, object]:
    plan_dir = tmp_path / "plan"
    state = _base_state(tmp_path)
    state["meta"]["overrides"] = [
        {"action": action, "timestamp": "2026-07-20T00:00:00Z"}
    ]
    _write_json(plan_dir / "state.json", state)
    _write_json(plan_dir / "plan_v1.md", {"placeholder": True})
    for name, payload in _required_artifacts(action).items():
        _write_json(plan_dir / name, payload)
    emit_override_authority_receipt(plan_dir, state, action)
    return json.loads(
        (plan_dir / "boundary_receipts" / _RECEIPT_FILES[action]).read_text(
            encoding="utf-8"
        )
    )


@pytest.mark.parametrize(
    ("action", "expected_action_type"),
    [
        ("abort", "cancellation"),
        ("force-proceed", "completion"),
        ("replan", "publication"),
        ("recover-blocked", "repair"),
        ("resume-clarify", "delivery"),
        ("adopt-execution", "publication"),
        ("suspension-waiver", "delivery"),
        ("human-gate", "delivery"),
    ],
)
def test_override_receipts_include_required_wbc_transition_evidence(
    tmp_path: Path,
    action: str,
    expected_action_type: str,
) -> None:
    receipt = _emit_receipt(tmp_path, action)

    evidence = receipt["details"]["wbc_transition_evidence"]
    assert evidence["transition"] == action
    assert evidence["source_record"]["semantic_sha256"]
    assert evidence["fixture_safety"]["authorized"] is True
    assert evidence["action_boundary"]["gate_result"] == "authorized"
    assert evidence["action_boundary"]["action_type"] == expected_action_type
    assert (
        receipt["authority_records"][0]["details"]["wbc_transition_evidence"]["transition"]
        == action
    )


def test_override_wbc_matrix_covers_all_authority_action_kinds(tmp_path: Path) -> None:
    seen = {
        _emit_receipt(tmp_path / action.replace("-", "_"), action)["details"][
            "wbc_transition_evidence"
        ]["action_boundary"]["action_type"]
        for action in _ACTION_TYPES
    }

    assert seen == {"repair", "completion", "cancellation", "publication", "delivery"}


def test_human_gate_receipt_requires_approval_record(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    state = _base_state(tmp_path, current_state="awaiting_human")
    state["meta"]["overrides"] = [{"action": "human-gate", "timestamp": "2026-07-20T00:00:00Z"}]
    _write_json(plan_dir / "state.json", state)

    with pytest.raises(OverrideAuthorityError, match="approval_record.json"):
        emit_override_authority_receipt(plan_dir, state, "human-gate")


def test_suspension_waiver_receipt_requires_human_verifications(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    state = _base_state(tmp_path, current_state="awaiting_human_verify")
    state["meta"]["overrides"] = [
        {"action": "suspension-waiver", "timestamp": "2026-07-20T00:00:00Z"}
    ]
    _write_json(plan_dir / "state.json", state)

    with pytest.raises(OverrideAuthorityError, match="human_verifications.json"):
        emit_override_authority_receipt(plan_dir, state, "suspension-waiver")


def test_routed_abort_transition_emits_wbc_receipt(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    state = _base_state(tmp_path, current_state="critiqued")
    _write_json(plan_dir / "state.json", state)

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="abort",
            payload={"reason": "operator aborted the run"},
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    receipt = json.loads(
        (plan_dir / "boundary_receipts" / "override_abort_authority.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["details"]["wbc_transition_evidence"]["transition"] == "abort"
