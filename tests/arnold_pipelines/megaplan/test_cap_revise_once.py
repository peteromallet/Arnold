"""Focused regressions for the ``override cap-revise-once`` seam.

Sol-adjudicated bounded operator correction authority (occurrence 7ce9c04b5100):
a critique-cap blocked park with real open flags must gain exactly one
agent-authored revise round without raising the global cap, clearing history,
waiving a flag, or weakening ``_critique_terminate_branch``.

Covered contracts:

- exact-shape acceptance and fail-closed rejection of every other blocked shape;
- CAS fences (state / iteration / events seq);
- grant custody records the open-significant baseline;
- one-shot consumption at the consuming gate with strict-decrease typing;
- workflow advertisement parity (and force-proceed un-advertised here);
- continued force-proceed rejection for this blocked shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.replan_state import (
    CAP_REVISE_ONCE_GRANT_KEY,
    cap_revise_once_override_allowed,
    events_max_seq,
    significant_flag_ids,
)

BLOCKED_ITERATE_GATE = {
    "recommendation": "ITERATE",
    "passed": False,
    "rationale": "ITERATE at cap",
}


def _cap_blocked_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "name": "demo",
        "current_state": "blocked",
        "iteration": 5,
        "config": {"robustness": "full"},
        "meta": {},
        "last_gate": dict(BLOCKED_ITERATE_GATE),
        "history": [
            {"step": "gate", "result": "blocked", "timestamp": "2026-01-01T00:00:00Z"},
        ],
        "latest_failure": None,
        "resume_cursor": None,
    }
    state.update(overrides)
    return state


def _gate_signals(plan_dir: Path, iteration: int, flag_ids: list[str]) -> None:
    payload = {
        "unresolved_flags": [
            {"id": flag_id, "severity": "significant", "status": "open"}
            for flag_id in flag_ids
        ],
    }
    (plan_dir / f"gate_signals_v{iteration}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_events(plan_dir: Path, seq: int) -> None:
    (plan_dir / "events.ndjson").write_text(
        json.dumps({"seq": seq, "kind": "state_written"}) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# predicate
# ---------------------------------------------------------------------------


def test_predicate_accepts_exact_cap_blocked_shape() -> None:
    assert cap_revise_once_override_allowed(_cap_blocked_state()) is True


@pytest.mark.parametrize(
    ("mutate", "label"),
    [
        (lambda s: s.update(current_state="critiqued"), "non_blocked_state"),
        (lambda s: s["last_gate"].update(recommendation="PROCEED"), "proceed_gate"),
        (lambda s: s["last_gate"].update(passed=True), "passed_gate"),
        (
            lambda s: s.update(resume_cursor={"phase": "revise"}),
            "resume_cursor_present",
        ),
        (
            lambda s: s.update(latest_failure={"kind": "phase_failed"}),
            "failure_record_present",
        ),
        (
            lambda s: s.update(history=[{"step": "revise", "result": "success"}]),
            "newest_history_not_gate_blocked",
        ),
        (
            lambda s: s["meta"].update(
                {
                    CAP_REVISE_ONCE_GRANT_KEY: {
                        "grant_seq": 1,
                        "consumed": False,
                        "baseline_flag_ids": ["CF-A", "CF-B"],
                    }
                }
            ),
            "unconsumed_grant_present",
        ),
    ],
)
def test_predicate_rejects_other_blocked_shapes(
    mutate: Any, label: str
) -> None:
    state = _cap_blocked_state()
    mutate(state)
    assert cap_revise_once_override_allowed(state) is False, label


def test_predicate_allows_new_grant_after_consumption() -> None:
    state = _cap_blocked_state()
    state["meta"][CAP_REVISE_ONCE_GRANT_KEY] = {
        "grant_seq": 1,
        "consumed": True,
        "baseline_flag_ids": ["CF-A"],
    }
    assert cap_revise_once_override_allowed(state) is True


# ---------------------------------------------------------------------------
# baseline helpers
# ---------------------------------------------------------------------------


def test_significant_flag_ids_filters_severity_and_status() -> None:
    flags = [
        {"id": "CF-A", "severity": "significant", "status": "open"},
        {"id": "CF-B", "severity": "likely-significant", "status": "open"},
        {"id": "CF-C", "severity": "minor", "status": "open"},
        {"id": "CF-D", "severity": "significant", "status": "resolved"},
        {"id": None, "severity": "significant", "status": "open"},
        "not-a-dict",
    ]
    assert significant_flag_ids(flags) == {"CF-A", "CF-B"}


def test_events_max_seq_reads_tail(tmp_path: Path) -> None:
    assert events_max_seq(tmp_path) is None
    _write_events(tmp_path, 632)
    assert events_max_seq(tmp_path) == 632


def test_gate_signals_baseline_fails_closed_without_flags(tmp_path: Path) -> None:
    _gate_signals(tmp_path, 5, [])
    with pytest.raises(ValueError):
        gate_signals_baseline_guard(tmp_path)


def gate_signals_baseline_guard(plan_dir: Path) -> dict[str, Any]:
    from arnold_pipelines.megaplan.replan_state import gate_signals_baseline

    return gate_signals_baseline(plan_dir, 5)


def test_gate_signals_baseline_records_sorted_ids_and_digest(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.replan_state import gate_signals_baseline

    _gate_signals(tmp_path, 5, ["CF-B", "CF-A"])
    baseline = gate_signals_baseline(tmp_path, 5)
    assert baseline["baseline_flag_ids"] == ["CF-A", "CF-B"]
    assert baseline["baseline_flag_count"] == 2
    assert baseline["baseline_digest"].startswith("sha256:")
    assert baseline["artifact"] == "gate_signals_v5.json"


# ---------------------------------------------------------------------------
# legacy override handler
# ---------------------------------------------------------------------------


def _run_legacy_override(
    tmp_path: Path,
    state: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    **cli_args: Any,
):
    from arnold_pipelines.megaplan.handlers import override as override_module

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(exist_ok=True)
    _gate_signals(plan_dir, state.get("iteration", 5), ["CF-A", "CF-B"])
    _write_events(plan_dir, 632)
    monkeypatch.setattr(
        override_module, "save_state_merge_meta", lambda *a, **k: None
    )
    monkeypatch.setattr(override_module, "now_utc", lambda: "2026-01-02T03:04:05Z")
    monkeypatch.setattr(
        override_module,
        "_warn_best_effort_emit_failure",
        lambda *a, **k: None,
    )
    args = argparse.Namespace(
        reason=cli_args.pop("reason", None),
        occurrence=cli_args.pop("occurrence", None),
        expected_state=cli_args.pop("expected_state", None),
        expected_iteration=cli_args.pop("expected_iteration", None),
        expected_max_event_seq=cli_args.pop("expected_max_event_seq", None),
    )
    assert not cli_args
    return plan_dir, override_module._override_cap_revise_once(
        tmp_path, plan_dir, state, args
    )


def test_override_handler_grants_and_lands_critiqued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _cap_blocked_state()
    plan_dir, response = _run_legacy_override(
        tmp_path,
        state,
        monkeypatch,
        reason="sol route b",
        occurrence="7ce9c04b5100",
    )

    from arnold_pipelines.megaplan.planning.state import STATE_CRITIQUED

    assert response["state"] == STATE_CRITIQUED
    assert state["current_state"] == STATE_CRITIQUED
    # Gate/critique custody is PRESERVED so ordinary revise authors the next
    # revision: last_gate must remain the blocking ITERATE gate.
    assert state["last_gate"] == BLOCKED_ITERATE_GATE
    grant = state["meta"][CAP_REVISE_ONCE_GRANT_KEY]
    assert grant["schema"] == "megaplan.cap_revise_once_grant.v1"
    assert grant["consumed"] is False
    assert grant["occurrence"] == "7ce9c04b5100"
    assert grant["baseline_flag_ids"] == ["CF-A", "CF-B"]
    assert grant["baseline_flag_count"] == 2
    assert grant["grant_seq"] == 1
    override_entry = state["meta"]["overrides"][-1]
    assert override_entry["action"] == "cap-revise-once"
    assert override_entry["from_state"] == "blocked"


def test_override_handler_is_one_shot_across_grants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError

    state = _cap_blocked_state()
    _, _ = _run_legacy_override(tmp_path, state, monkeypatch)
    # Land back in blocked with the grant consumed: a second explicit grant is
    # allowed (fresh operator decision), bumping grant_seq.
    state["current_state"] = "blocked"
    state["meta"][CAP_REVISE_ONCE_GRANT_KEY]["consumed"] = True
    state["history"].append(
        {"step": "gate", "result": "blocked", "timestamp": "2026-01-03T00:00:00Z"}
    )
    plan_dir, response = _run_legacy_override(tmp_path, state, monkeypatch)
    assert response["grant"]["grant_seq"] == 2

    # While a grant is UNCONSUMED, a second grant must fail closed.
    state["current_state"] = "blocked"
    state["meta"][CAP_REVISE_ONCE_GRANT_KEY]["consumed"] = False
    state["history"].append(
        {"step": "gate", "result": "blocked", "timestamp": "2026-01-04T00:00:00Z"}
    )
    with pytest.raises(CliError) as caught:
        _run_legacy_override(tmp_path, state, monkeypatch)
    assert caught.value.code == "invalid_transition"


def test_override_handler_fences_state_iteration_and_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError

    state = _cap_blocked_state()
    with pytest.raises(CliError) as caught:
        _run_legacy_override(
            tmp_path, state, monkeypatch, expected_state="planned"
        )
    assert caught.value.code == "state_drift"

    with pytest.raises(CliError) as caught:
        _run_legacy_override(
            tmp_path, state, monkeypatch, expected_iteration=9
        )
    assert caught.value.code == "iteration_drift"

    with pytest.raises(CliError) as caught:
        _run_legacy_override(
            tmp_path, state, monkeypatch, expected_max_event_seq=100
        )
    assert caught.value.code == "event_seq_drift"

    # Matching fences pass and the grant lands.
    _, response = _run_legacy_override(
        tmp_path,
        state,
        monkeypatch,
        expected_state="blocked",
        expected_iteration=5,
        expected_max_event_seq=632,
    )
    assert response["grant"]["consumed"] is False


def test_override_handler_requires_baseline_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError

    state = _cap_blocked_state()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_events(plan_dir, 632)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override.now_utc",
        lambda: "2026-01-02T03:04:05Z",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override._warn_best_effort_emit_failure",
        lambda *a, **k: None,
    )
    args = argparse.Namespace(
        reason=None,
        occurrence=None,
        expected_state=None,
        expected_iteration=None,
        expected_max_event_seq=None,
    )
    with pytest.raises(CliError) as caught:
        from arnold_pipelines.megaplan.handlers.override import (
            _override_cap_revise_once,
        )

        _override_cap_revise_once(tmp_path, plan_dir, state, args)
    assert caught.value.code == "cap_revise_once_baseline_missing"


# ---------------------------------------------------------------------------
# control binding branch
# ---------------------------------------------------------------------------


def test_control_binding_cap_revise_once_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.control.interface import ControlTransition, RunStateView
    from arnold_pipelines.megaplan.planning.control_binding import (
        PlanningControlBinding,
    )
    from arnold_pipelines.megaplan.planning.state import STATE_CRITIQUED

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _gate_signals(plan_dir, 5, ["CF-A", "CF-B"])
    _write_events(plan_dir, 632)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.now_utc",
        lambda: "2026-01-02T03:04:05Z",
    )
    state = _cap_blocked_state()
    state["meta"] = {}
    transition = ControlTransition(
        op="override",
        target_id="cap-revise-once",
        payload={
            "reason": "sol route b",
            "occurrence": "7ce9c04b5100",
            "expected_state": "blocked",
            "expected_iteration": 5,
            "expected_max_event_seq": 632,
            "plan_dir": str(plan_dir),
        },
    )
    result = PlanningControlBinding().apply_transition(
        RunStateView(run_id="demo", cursor="blocked", raw_state=state),
        transition,
    )
    assert result.accepted is True and result.mutated is True
    deltas = {delta.key: delta.value for delta in result.state_deltas}
    assert deltas["current_state"] == STATE_CRITIQUED
    assert deltas["meta"][CAP_REVISE_ONCE_GRANT_KEY]["consumed"] is False
    assert deltas["meta"][CAP_REVISE_ONCE_GRANT_KEY]["baseline_flag_ids"] == [
        "CF-A",
        "CF-B",
    ]


def test_control_binding_rejects_cap_revise_once_on_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.control.interface import ControlTransition, RunStateView
    from arnold_pipelines.megaplan.planning.control_binding import (
        PlanningControlBinding,
    )
    from arnold_pipelines.megaplan.types import CliError

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _gate_signals(plan_dir, 5, ["CF-A"])
    _write_events(plan_dir, 700)
    state = _cap_blocked_state()
    transition = ControlTransition(
        op="override",
        target_id="cap-revise-once",
        payload={
            "reason": "drift probe",
            "expected_max_event_seq": 632,
            "plan_dir": str(plan_dir),
        },
    )
    with pytest.raises(CliError) as caught:
        PlanningControlBinding().apply_transition(
            RunStateView(run_id="demo", cursor="blocked", raw_state=state),
            transition,
        )
    assert caught.value.code == "event_seq_drift"


# ---------------------------------------------------------------------------
# gate consumption and typing
# ---------------------------------------------------------------------------


def _grant_state(baseline_ids: list[str]) -> dict[str, Any]:
    state = _cap_blocked_state()
    state["iteration"] = 6
    state["meta"] = {
        CAP_REVISE_ONCE_GRANT_KEY: {
            "schema": "megaplan.cap_revise_once_grant.v1",
            "grant_seq": 1,
            "consumed": False,
            "baseline_flag_ids": baseline_ids,
            "baseline_flag_count": len(baseline_ids),
        }
    }
    return state


def _gate_summary(flag_ids: list[str]) -> dict[str, Any]:
    return {
        "recommendation": "ITERATE",
        "rationale": "still iterating",
        "unresolved_flags": [
            {"id": fid, "severity": "significant", "status": "open"}
            for fid in flag_ids
        ],
    }


def _run_gate_route(
    tmp_path: Path,
    state: dict[str, Any],
    flag_ids: list[str],
    *,
    prior_rounds: int = 5,
) -> dict[str, Any]:
    from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal

    state["history"] = [
        {"step": "gate", "result": "success", "recommendation": "ITERATE"}
    ] * prior_rounds
    _gate_signals(tmp_path, state["iteration"], flag_ids)
    return _build_gate_route_signal(
        state,
        _gate_summary(flag_ids),
        robustness="full",
        plan_dir=tmp_path,
    )


def test_consuming_gate_types_no_progress_without_decrease(
    tmp_path: Path,
) -> None:
    state = _grant_state(["CF-A", "CF-B", "CF-C"])
    route = _run_gate_route(tmp_path, state, ["CF-A", "CF-B", "CF-C", "CF-D"])
    assert route["result"] == "blocked"
    assert route["fallback_payload"]["reason"] == "cap_revise_no_progress"
    grant = state["meta"][CAP_REVISE_ONCE_GRANT_KEY]
    assert grant["consumed"] is True
    assert grant["strict_significant_decrease"] is False
    # Termination guard unchanged: state projected to blocked.
    assert state["current_state"] == "blocked"


def test_consuming_gate_keeps_normal_cap_block_on_decrease(
    tmp_path: Path,
) -> None:
    state = _grant_state(["CF-A", "CF-B", "CF-C"])
    route = _run_gate_route(tmp_path, state, ["CF-C"])
    assert route["result"] == "blocked"
    assert route["fallback_payload"]["reason"] == "correctness_or_security_flags"
    grant = state["meta"][CAP_REVISE_ONCE_GRANT_KEY]
    assert grant["consumed"] is True
    assert grant["strict_significant_decrease"] is True


def test_gate_below_cap_ordinary_iterate_consumes_grant(
    tmp_path: Path,
) -> None:
    state = _grant_state(["CF-A", "CF-B"])
    route = _run_gate_route(
        tmp_path, state, ["CF-A"], prior_rounds=1
    )
    assert route["result"] == "success"
    assert route["route_signal"] == "iterate"
    grant = state["meta"][CAP_REVISE_ONCE_GRANT_KEY]
    assert grant["consumed"] is True
    assert state["current_state"] == "critiqued"


def test_gate_proceed_consumes_grant(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal

    state = _grant_state(["CF-A", "CF-B"])
    state["current_state"] = "critiqued"
    summary = _gate_summary([])
    summary["recommendation"] = "PROCEED"
    summary["passed"] = True
    summary["preflight_results"] = {"project_dir_exists": True}
    route = _build_gate_route_signal(
        state, summary, robustness="full", plan_dir=tmp_path
    )
    assert route["result"] == "success"
    assert route["route_signal"] == "proceed"
    assert state["meta"][CAP_REVISE_ONCE_GRANT_KEY]["consumed"] is True


def test_gate_without_grant_unchanged(tmp_path: Path) -> None:
    state = _cap_blocked_state()
    state["iteration"] = 6
    state["meta"] = {}
    route = _run_gate_route(tmp_path, state, ["CF-A", "CF-B"])
    assert route["result"] == "blocked"
    assert route["fallback_payload"]["reason"] == "correctness_or_security_flags"
    assert CAP_REVISE_ONCE_GRANT_KEY not in state["meta"]


# ---------------------------------------------------------------------------
# workflow advertisement parity
# ---------------------------------------------------------------------------


def test_workflow_advertises_cap_revise_once_not_force_proceed() -> None:
    from arnold_pipelines.megaplan._core.workflow import workflow_next

    state = _cap_blocked_state()
    steps = workflow_next(state)
    assert "override cap-revise-once" in steps
    assert "override force-proceed" not in steps


def test_workflow_advertises_force_proceed_only_for_preflight_block() -> None:
    from arnold_pipelines.megaplan._core.workflow import workflow_next

    state = _cap_blocked_state()
    state["last_gate"] = {
        "recommendation": "PROCEED",
        "passed": False,
        "preflight_results": {
            "claude_available": False,
            "codex_available": True,
        },
    }
    steps = workflow_next(state)
    assert "override force-proceed" in steps
    assert "override cap-revise-once" not in steps

    # Any other blocked shape (e.g. the old unconditional advertisement) must
    # not advertise force-proceed.
    state["last_gate"] = {"recommendation": "PROCEED", "passed": False}
    steps = workflow_next(state)
    assert "override force-proceed" not in steps


# ---------------------------------------------------------------------------
# force-proceed stays rejected for this shape
# ---------------------------------------------------------------------------


def test_force_proceed_still_rejected_for_cap_block(tmp_path: Path) -> None:
    from arnold.control.interface import ControlTransition, RunStateView
    from arnold_pipelines.megaplan.planning.control_binding import (
        PlanningControlBinding,
    )
    from arnold_pipelines.megaplan.types import CliError

    state = _cap_blocked_state()
    transition = ControlTransition(
        op="override",
        target_id="force-proceed",
        payload={"reason": "ship it anyway", "plan_dir": str(tmp_path)},
    )
    with pytest.raises(CliError) as caught:
        PlanningControlBinding().apply_transition(
            RunStateView(run_id="demo", cursor="blocked", raw_state=state),
            transition,
        )
    assert caught.value.code == "invalid_transition"


# ---------------------------------------------------------------------------
# matrix declaration
# ---------------------------------------------------------------------------


def test_matrix_declares_cap_revise_once() -> None:
    from arnold_pipelines.megaplan.workflows.override_matrix import (
        CONTROL_ROUTED_ACTIONS,
        ROUTE_SIGNAL_BY_ACTION,
        get_entry,
    )

    entry = get_entry("cap-revise-once")
    assert entry.family == "terminal_route"
    assert entry.route_signal == "cap_revise_once"
    assert entry.target_ref == "revise"
    assert entry.control_routed is True
    assert "cap-revise-once" in CONTROL_ROUTED_ACTIONS
    assert ROUTE_SIGNAL_BY_ACTION["cap-revise-once"] == "cap_revise_once"
