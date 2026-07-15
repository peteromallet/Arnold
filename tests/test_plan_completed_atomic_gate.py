"""Tests for T18: plan-completed marker gate in atomic/enforce mode.

In atomic (fail-closed) mode ``_mark_plan_completed_by_chain`` must NOT
write a plan-done projection (``STATE_DONE`` in the plan's ``state.json``)
unless the chain state carries an accepted acceptance transaction (receipt)
for the target milestone.

Shadow / warn / off modes preserve the original plan-done projection
behavior exactly regardless of acceptance receipt presence.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan.chain import _mark_plan_completed_by_chain
from arnold_pipelines.megaplan.chain.spec import ChainState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _atomic_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "atomic"
    return state


def _enforce_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "enforce"
    return state


def _shadow_state() -> ChainState:
    return ChainState()  # default == shadow


def _warn_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "warn"
    return state


def _off_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "off"
    return state


def _state_with_receipt(
    mode: str = "atomic",
    label: str = "m1",
    transaction_id: str = "tx-abc123",
) -> ChainState:
    state = ChainState()
    state.completion_contract_mode = mode
    state.completed.append(
        {
            "label": label,
            "plan": "test-plan",
            "status": "done",
            "acceptance_receipt": {
                "transaction_id": transaction_id,
                "snapshot_hash": "sha256:deadbeef",
            },
        }
    )
    return state


def _state_without_receipt(mode: str = "atomic") -> ChainState:
    state = ChainState()
    state.completion_contract_mode = mode
    return state


def _plan_state(root: Path, plan_name: str) -> dict:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    return json.loads((plan_dir / "state.json").read_text())


def _write_plan_state(root: Path, plan_name: str, current_state: str) -> None:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {"current_state": current_state, "active_step": {"phase": "test"}}
    (plan_dir / "state.json").write_text(json.dumps(state))


# ---------------------------------------------------------------------------
# Plan-done marker blocked in atomic / enforce without receipt
# ---------------------------------------------------------------------------


def test_atomic_without_receipt_does_not_write_plan_done(tmp_path):
    """Plan-done marker is blocked when mode=atomic and no receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    output_lines: list[str] = []

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="atomic test",
        writer=lambda t: output_lines.append(t),
        state=_atomic_state(),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "executed", "plan state must be unchanged"
    assert any("plan-done marker blocked" in line for line in output_lines), (
        "must log block reason"
    )


def test_enforce_without_receipt_does_not_write_plan_done(tmp_path):
    """Plan-done marker is blocked when mode=enforce and no receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    output_lines: list[str] = []

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="enforce test",
        writer=lambda t: output_lines.append(t),
        state=_enforce_state(),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "executed", "plan state must be unchanged"
    assert any("plan-done marker blocked" in line for line in output_lines)


def test_atomic_with_receipt_writes_plan_done(tmp_path):
    """Plan-done marker succeeds when mode=atomic with a receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="atomic with receipt",
        writer=lambda _: None,
        state=_state_with_receipt(label="m1"),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "done"
    assert plan["meta"]["chain_completion"]["reason"] == "atomic with receipt"
    assert plan["meta"]["chain_completion"]["milestone_label"] == "m1"


def test_atomic_with_receipt_for_wrong_label_is_blocked(tmp_path):
    """Receipt must match the milestone label being completed."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    output_lines: list[str] = []
    # state has receipt for "m1" but we're completing "m2"
    state = _state_with_receipt(label="m1")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m2",
        completion_reason="mismatched label",
        writer=lambda t: output_lines.append(t),
        state=state,
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "executed", "plan state must be unchanged"
    assert any("plan-done marker blocked" in line for line in output_lines)


def test_atomic_without_state_param_writes_plan_done(tmp_path):
    """When state=None (legacy caller) plan-done marker is always written."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="legacy no-state",
        writer=lambda _: None,
        # state not passed -> None
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "done"


# ---------------------------------------------------------------------------
# Shadow / warn / off modes always write
# ---------------------------------------------------------------------------


def test_shadow_without_receipt_writes_plan_done(tmp_path):
    """Shadow mode always writes plan-done regardless of receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="shadow test",
        writer=lambda _: None,
        state=_shadow_state(),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "done"


def test_warn_without_receipt_writes_plan_done(tmp_path):
    """Warn mode always writes plan-done regardless of receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="warn test",
        writer=lambda _: None,
        state=_warn_state(),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "done"


def test_off_without_receipt_writes_plan_done(tmp_path):
    """Off mode always writes plan-done regardless of receipt."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="off test",
        writer=lambda _: None,
        state=_off_state(),
    )

    plan = _plan_state(root, "plan-m1")
    assert plan["current_state"] == "done"


# ---------------------------------------------------------------------------
# Plan-done marker suppresses active_step / latest_failure / resume_cursor
# ---------------------------------------------------------------------------


def test_plan_done_clears_active_step(tmp_path):
    """Plan-done marker removes active_step."""
    root = tmp_path / "project"
    root.mkdir()
    _write_plan_state(root, "plan-m1", "executed")

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="clear test",
        writer=lambda _: None,
    )

    plan = _plan_state(root, "plan-m1")
    assert "active_step" not in plan


def test_plan_done_clears_latest_failure(tmp_path):
    """Plan-done marker removes latest_failure."""
    root = tmp_path / "project"
    root.mkdir()
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = {
        "current_state": "executed",
        "latest_failure": {"kind": "test", "message": "boom"},
    }
    (plan_dir / "state.json").write_text(json.dumps(state))

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="clear failure",
        writer=lambda _: None,
    )

    plan = json.loads((plan_dir / "state.json").read_text())
    assert "latest_failure" not in plan


def test_plan_done_clears_resume_cursor(tmp_path):
    """Plan-done marker removes resume_cursor."""
    root = tmp_path / "project"
    root.mkdir()
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = {
        "current_state": "executed",
        "resume_cursor": {"phase": "recover"},
    }
    (plan_dir / "state.json").write_text(json.dumps(state))

    _mark_plan_completed_by_chain(
        root,
        "plan-m1",
        milestone_label="m1",
        completion_reason="clear cursor",
        writer=lambda _: None,
    )

    plan = json.loads((plan_dir / "state.json").read_text())
    assert "resume_cursor" not in plan
