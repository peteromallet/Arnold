"""Tests for T17: reconciliation cannot grant atomic-mode completion authority.

In atomic (fail-closed) mode the three reconciliation entry points —
``_append_reconciled_completed_record``,
``_append_reconciled_completed_record_with_guard``, and
``_reconcile_chain_from_ground_truth`` — must NEVER turn a ground-truth
projection (terminal plan state, merged PR state, reviewed finalized state,
or any other derived observation) into completion authority without an
accepted acceptance transaction.

Shadow mode preserves the original legacy reconciliation behavior exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan.chain import (
    _append_reconciled_completed_record,
    _append_reconciled_completed_record_with_guard,
    _reconcile_chain_from_ground_truth,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    MilestoneSpec,
    load_chain_state,
    save_chain_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atomic_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "atomic"
    return state


def _shadow_state() -> ChainState:
    return ChainState()  # default == shadow


def _write_chain_spec(root: Path, *, with_branch: bool = True) -> Path:
    idea = root / "idea.md"
    idea.write_text("ship milestone\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    branch_line = "    branch: test/m1\n" if with_branch else ""
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n"
        + branch_line,
        encoding="utf-8",
    )
    (root / "NORTHSTAR.md").write_text("North Star\n", encoding="utf-8")
    return spec_path


def _write_terminal_plan_state(root: Path, plan_name: str = "m1-plan") -> str:
    """Write a plan state.json whose current_state is 'done' (terminal)."""
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "done",
                "latest_failure": None,
                "last_gate": {"recommendation": "PROCEED"},
                "active_step": {"phase": "execute"},
                "meta": {"chain_policy": {"milestone_label": "m1"}},
            }
        ),
        encoding="utf-8",
    )
    return plan_name


def _write_finalized_reviewed_plan_state(root: Path, plan_name: str = "m1-plan") -> str:
    """Write a finalized plan state.json with successful review."""
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "finalized",
                "latest_failure": None,
                "last_gate": {"recommendation": "PROCEED"},
                "active_step": {"phase": "execute"},
                "review": {"status": "approved"},
                "meta": {"chain_policy": {"milestone_label": "m1"}},
            }
        ),
        encoding="utf-8",
    )
    return plan_name


# ---------------------------------------------------------------------------
# _append_reconciled_completed_record (non-guard variant)
# ---------------------------------------------------------------------------

def test_append_reconciled_record_blocked_in_atomic_mode(tmp_path: Path) -> None:
    """Atomic mode: _append_reconciled_completed_record returns False, no mutation."""
    state = _atomic_state()
    state.current_milestone_index = 0
    prior_completed = list(state.completed)
    messages: list[str] = []

    milestone = MilestoneSpec(label="m1", idea="idea.md")

    result = _append_reconciled_completed_record(
        tmp_path,
        state,
        plan_name="m1-plan",
        milestone=milestone,
        pr_number=42,
        pr_state="merged",
        completion_reason="terminal plan state",
        writer=messages.append,
    )

    assert result is False
    assert state.completed == prior_completed
    assert any("atomic mode" in m for m in messages)


def test_append_reconciled_record_allowed_in_shadow_mode(tmp_path: Path) -> None:
    """Shadow mode: _append_reconciled_completed_record appends normally."""
    state = _shadow_state()
    milestone = MilestoneSpec(label="m1", idea="idea.md")

    result = _append_reconciled_completed_record(
        tmp_path,
        state,
        plan_name="m1-plan",
        milestone=milestone,
        pr_number=None,
        pr_state=None,
        completion_reason="terminal plan state",
        writer=lambda _m: None,
    )

    assert result is True
    assert len(state.completed) == 1
    assert state.completed[0]["label"] == "m1"
    assert state.completed[0]["plan"] == "m1-plan"


# ---------------------------------------------------------------------------
# _append_reconciled_completed_record_with_guard
# ---------------------------------------------------------------------------

def test_append_reconciled_record_with_guard_blocked_in_atomic_mode(tmp_path: Path) -> None:
    """Atomic mode: _append_reconciled_completed_record_with_guard returns (False, reason)."""
    state = _atomic_state()
    prior_completed = list(state.completed)
    prior_index = state.current_milestone_index
    messages: list[str] = []

    milestone = MilestoneSpec(label="m1", idea="idea.md")

    appended, reason = _append_reconciled_completed_record_with_guard(
        tmp_path,
        state,
        plan_name="m1-plan",
        milestone=milestone,
        pr_number=42,
        pr_state="merged",
        completion_reason="reviewed finalized plan with merged PR",
        writer=messages.append,
    )

    assert appended is False
    assert "atomic mode" in reason or "fail-closed" in reason
    # State completely unchanged.
    assert state.completed == prior_completed
    assert state.current_milestone_index == prior_index
    assert any("atomic mode" in m for m in messages)


def test_append_reconciled_record_with_guard_allowed_in_shadow_mode(tmp_path: Path) -> None:
    """Shadow mode: _append_reconciled_completed_record_with_guard delegates to guard."""
    state = _shadow_state()
    milestone = MilestoneSpec(label="m1", idea="idea.md")

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        appended, reason = _append_reconciled_completed_record_with_guard(
            tmp_path,
            state,
            plan_name="m1-plan",
            milestone=milestone,
            pr_number=None,
            pr_state=None,
            completion_reason="terminal plan state",
            writer=lambda _m: None,
        )

    assert appended is True
    assert len(state.completed) == 1


# ---------------------------------------------------------------------------
# _reconcile_chain_from_ground_truth
# ---------------------------------------------------------------------------

def test_reconcile_atomic_terminal_plan_state_does_not_advance(tmp_path: Path) -> None:
    """Atomic mode: terminal plan state projection must NOT grant completion authority."""
    spec_path = _write_chain_spec(tmp_path, with_branch=False)
    spec = chain_module.load_spec(spec_path)
    plan_name = _write_terminal_plan_state(tmp_path)
    state = _atomic_state()
    state.current_milestone_index = 0
    state.current_plan_name = plan_name
    save_chain_state(spec_path, state)

    prior_completed = list(state.completed)
    prior_index = state.current_milestone_index
    prior_last_state = state.last_state

    reconciled = _reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        spec,
        state,
        writer=lambda _m: None,
        push_enabled=False,
    )

    # Cursor must not advance, no completed record, no "done" state.
    assert reconciled.completed == prior_completed
    assert reconciled.current_milestone_index == prior_index
    assert reconciled.last_state == prior_last_state


def test_reconcile_atomic_merged_pr_state_does_not_advance(tmp_path: Path) -> None:
    """Atomic mode: merged PR state projection must NOT grant completion authority."""
    spec_path = _write_chain_spec(tmp_path, with_branch=True)
    spec = chain_module.load_spec(spec_path)
    plan_name = _write_terminal_plan_state(tmp_path)
    state = _atomic_state()
    state.current_milestone_index = 0
    state.current_plan_name = plan_name
    state.pr_number = 42
    state.pr_state = "merged"
    save_chain_state(spec_path, state)

    prior_completed = list(state.completed)
    prior_index = state.current_milestone_index

    with patch.object(
        chain_module, "_pr_state", return_value="merged"
    ):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _m: None,
            push_enabled=True,
        )

    assert reconciled.completed == prior_completed
    assert reconciled.current_milestone_index == prior_index


def test_reconcile_atomic_reviewed_finalized_plan_does_not_advance(tmp_path: Path) -> None:
    """Atomic mode: reviewed finalized plan projection must NOT grant completion authority."""
    spec_path = _write_chain_spec(tmp_path, with_branch=True)
    spec = chain_module.load_spec(spec_path)
    plan_name = _write_finalized_reviewed_plan_state(tmp_path)
    state = _atomic_state()
    state.current_milestone_index = 0
    state.current_plan_name = plan_name
    state.pr_number = 42
    state.pr_state = "merged"
    save_chain_state(spec_path, state)

    prior_completed = list(state.completed)
    prior_index = state.current_milestone_index

    with patch.object(
        chain_module, "_pr_state", return_value="merged"
    ):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _m: None,
            push_enabled=True,
        )

    assert reconciled.completed == prior_completed
    assert reconciled.current_milestone_index == prior_index


def test_reconcile_atomic_preserves_completed_records_from_transactions(tmp_path: Path) -> None:
    """Atomic mode: existing accepted-transaction-backed completed records are preserved
    (not removed by PR-state reconciliation)."""
    spec_path = _write_chain_spec(tmp_path, with_branch=True)
    spec = chain_module.load_spec(spec_path)
    state = _atomic_state()
    state.current_milestone_index = 1
    state.completed = [
        {"label": "m1", "plan": "m1-plan", "status": "done", "pr_number": 42, "pr_state": "merged"}
    ]
    save_chain_state(spec_path, state)

    # Even if the live PR state is NOT merged, the accepted record must survive.
    with patch.object(
        chain_module, "_pr_state", return_value="closed"
    ):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _m: None,
            push_enabled=True,
        )

    assert len(reconciled.completed) == 1
    assert reconciled.completed[0]["label"] == "m1"


def test_reconcile_shadow_terminal_plan_state_advances(tmp_path: Path) -> None:
    """Shadow mode regression: terminal plan state reconciliation still works."""
    spec_path = _write_chain_spec(tmp_path, with_branch=False)
    spec = chain_module.load_spec(spec_path)
    plan_name = _write_terminal_plan_state(tmp_path)
    state = _shadow_state()
    state.current_milestone_index = 0
    state.current_plan_name = plan_name
    save_chain_state(spec_path, state)

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _m: None,
            push_enabled=False,
        )

    # Shadow mode should append the completed record from the projection.
    assert len(reconciled.completed) >= 1
    assert reconciled.completed[0]["label"] == "m1"


def test_reconcile_shadow_merged_pr_advances(tmp_path: Path) -> None:
    """Shadow mode regression: merged PR reconciliation still works."""
    spec_path = _write_chain_spec(tmp_path, with_branch=True)
    spec = chain_module.load_spec(spec_path)
    plan_name = _write_terminal_plan_state(tmp_path)
    state = _shadow_state()
    state.current_milestone_index = 0
    state.current_plan_name = plan_name
    state.pr_number = 42
    state.pr_state = "open"
    save_chain_state(spec_path, state)

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ), patch.object(
        chain_module, "_pr_state", return_value="merged"
    ):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _m: None,
            push_enabled=True,
        )

    assert len(reconciled.completed) >= 1
    assert reconciled.completed[-1]["label"] == "m1"
