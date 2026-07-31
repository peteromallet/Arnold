from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.control.interface import ControlTransition, ControlTransitionRequest
from arnold_pipelines.megaplan.control_interface import apply_transition
from arnold_pipelines.megaplan.handlers.finalize import (
    _reject_finalize_unresolved_north_star,
)
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_run_state_view,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _state(root: Path) -> dict[str, object]:
    return {
        "name": "m11-replay",
        "current_state": "critiqued",
        "iteration": 10,
        "config": {
            "project_dir": str(root),
            "strict_notes": False,
        },
        "meta": {},
        "last_gate": {},
        "_state_meta": {"versions": {"current_state": 3, "meta": 7, "last_gate": 2}},
    }


def _seed_custody(plan_dir: Path) -> None:
    _write(
        plan_dir / "faults.json",
        {
            "flags": [
                {
                    "id": "F-current",
                    "severity": "significant",
                    "status": "open",
                    "concern": "executor: current blocking critique",
                    "evidence": "attempt 70",
                }
            ]
        },
    )
    _write(
        plan_dir / "gate_carry.json",
        {
            "north_star_actions": [
                {
                    "id": "NS-current",
                    "concern": "current route authority is unresolved",
                    "category": "route_authority",
                    "action_type": "add_gate",
                    "evidence": "north-star evidence",
                }
            ]
        },
    )


@pytest.fixture
def gate_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.run_gate_checks",
        lambda *args, **kwargs: {
            "preflight_results": {},
            "criteria_check": {},
            "unresolved_flags": [],
        },
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.build_gate_signals",
        lambda *args, **kwargs: {
            "robustness": "standard",
            "signals": {},
            "warnings": [],
        },
    )


def test_force_proceed_atomically_disposes_critique_and_north_star(
    tmp_path: Path,
    gate_runtime: None,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "m11-replay"
    state = _state(tmp_path)
    _write(plan_dir / "state.json", state)
    _seed_custody(plan_dir)

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="force-proceed",
            payload={
                "root": str(tmp_path),
                "plan_dir": str(plan_dir),
                "reason": "operator accepts explicit debt",
            },
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    persisted = json.loads((plan_dir / "state.json").read_text())
    custody = persisted["meta"]["force_proceed_custody"]
    assert persisted["current_state"] == "gated"
    assert [row["subject_id"] for row in custody["critique_dispositions"]] == ["F-current"]
    assert [row["subject_id"] for row in custody["north_star_dispositions"]] == ["NS-current"]
    assert custody["transaction_id"].startswith("force-proceed:")

    faults = json.loads((plan_dir / "faults.json").read_text())
    assert faults["flags"][0]["status"] == "accepted_tradeoff"
    assert (
        faults["flags"][0]["gate_resolution"]["force_proceed_transaction_id"]
        == custody["transaction_id"]
    )
    carry = json.loads((plan_dir / "gate_carry.json").read_text())
    assert carry["force_proceed_transaction_id"] == custody["transaction_id"]
    assert [row["id"] for row in carry["north_star_actions"]] == ["NS-current"]

    # Finalize consumes the committed operator disposition rather than stale
    # revise metadata and therefore cannot resurrect the pre-force blocker.
    _write(plan_dir / "plan_v1.meta.json", {})
    persisted["plan_versions"] = [{"file": "plan_v1.md", "meta_file": "plan_v1.meta.json"}]
    _reject_finalize_unresolved_north_star(plan_dir, persisted)


def test_force_proceed_cas_conflict_publishes_no_projection(
    tmp_path: Path,
    gate_runtime: None,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "m11-replay"
    state = _state(tmp_path)
    _write(plan_dir / "state.json", state)
    _seed_custody(plan_dir)
    original_carry = (plan_dir / "gate_carry.json").read_bytes()

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransitionRequest(
            action="override",
            target_id="force-proceed",
            params={
                "root": str(tmp_path),
                "plan_dir": str(plan_dir),
                "reason": "stale operator request",
            },
            expected_versions={"meta": 6},
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is False
    assert result.reason == "control_transition_conflict"
    assert not (plan_dir / "gate.json").exists()
    assert (plan_dir / "gate_carry.json").read_bytes() == original_carry
    assert not (tmp_path / ".megaplan" / "debt.json").exists()


def test_force_proceed_retry_repairs_projections_without_duplicate_debt(
    tmp_path: Path,
    gate_runtime: None,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "m11-replay"
    state = _state(tmp_path)
    _write(plan_dir / "state.json", state)
    _seed_custody(plan_dir)
    transition = ControlTransition(
        op="override",
        target_id="force-proceed",
        payload={
            "root": str(tmp_path),
            "plan_dir": str(plan_dir),
            "reason": "operator accepts explicit debt",
        },
    )
    first = apply_transition(
        planning_run_state_view(state),
        transition,
        "megaplan",
        plan_dir=plan_dir,
    )
    assert first.accepted is True
    debt_path = tmp_path / ".megaplan" / "debt.json"
    debt_before = json.loads(debt_path.read_text())

    persisted = json.loads((plan_dir / "state.json").read_text())
    (plan_dir / "gate_carry.json").unlink()
    second = apply_transition(
        planning_run_state_view(persisted),
        transition,
        "megaplan",
        plan_dir=plan_dir,
    )

    assert second.accepted is True
    assert second.mutated is False
    assert (plan_dir / "gate_carry.json").exists()
    assert json.loads(debt_path.read_text()) == debt_before
