from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan._core.state import append_history
from arnold_pipelines.megaplan.cloud.repair_contract import (
    CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    DISPATCH_INTENT_L1,
    _is_evidence_bound_deterministic_quality_block,
    classify_repair_dispatch,
)
from arnold_pipelines.megaplan.handlers.review import _review_quality_block_failure
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED, STATE_EXECUTED
from arnold_pipelines.megaplan.run_state.classifiers import _IMPLEMENTATION_BLOCK_TOKENS
from arnold_pipelines.megaplan.run_state.decision_contract import MACHINE_REPAIRABLE_FAILURE_KINDS
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState
from arnold_pipelines.megaplan.workflows.handler_contract import apply_state_projection


def _rework_items() -> list[dict[str, object]]:
    return [
        {
            "task_id": "T2",
            "issue": "import check failed",
            "deterministic_check": {
                "command": "python -c 'import package'",
                "baseline_status": "failed",
                "post_status": "failed",
            },
        }
    ]


def _emit_in_production_order(state: dict[str, object]) -> dict[str, object]:
    apply_state_projection(state, STATE_BLOCKED, route_signal="blocked")  # type: ignore[arg-type]
    append_history(state, {"step": "review", "result": "needs_rework", "cost_usd": 0.0})  # type: ignore[arg-type]
    failure = _review_quality_block_failure(
        state=state,  # type: ignore[arg-type]
        blockers=["unresolved blocking rework: deterministic import check"],
        rework_items=_rework_items(),  # type: ignore[arg-type]
        review_artifact_hash="a" * 64,
    )
    state["latest_failure"] = failure
    state["resume_cursor"] = {
        "phase": "review",
        "retry_strategy": "manual_review",
        "evidence_cursor": dict(failure["evidence_cursor"]),  # type: ignore[index]
    }
    return failure


def _live_target(state: dict[str, object], failure: dict[str, object]) -> dict[str, object]:
    return {
        "authoritative_source": "plan_state",
        "current_refs": {
            "current_plan_name": "review-quality-plan",
            "plan_current_state": "blocked",
        },
        "plan_state": {
            "present": True,
            "name": "review-quality-plan",
            "current_state": "blocked",
            "current_phase": "review",
            "resume_cursor": dict(state["resume_cursor"]),  # type: ignore[arg-type]
        },
        "event_cursors": {
            "evidence_cursor": dict(failure["evidence_cursor"]),
        },
    }


def _custody() -> dict[str, object]:
    return {
        "blocker_id": "blocker:quality-review",
        "active_request_ids": ["request-quality-review"],
        "custody_bucket": CUSTODY_BUCKET_REPAIRABLE_NOT_REPAIRING,
    }


def test_t23_production_order_fingerprint_matches_live_blocked_target(tmp_path: Path) -> None:
    disposable = (tmp_path / "t23-disposable").resolve()
    disposable.mkdir()
    project_root = Path(__file__).parents[2].resolve()
    assert disposable != project_root and project_root not in disposable.parents

    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_EXECUTED,
        "history": [{"step": "review", "result": "needs_rework"}] * 3,
        "meta": {"total_cost_usd": 0.0},
    }
    failure = _emit_in_production_order(state)
    target = _live_target(state, failure)

    assert state["current_state"] == STATE_BLOCKED
    assert len(state["history"]) == 4  # type: ignore[arg-type]
    assert failure["kind"] == "quality_gate_blocked"
    assert failure["target"]["current_state"] == "blocked"  # type: ignore[index]
    assert failure["target"]["history_index"] == 4  # type: ignore[index]
    assert failure["evidence_cursor"]["history_index"] == 4  # type: ignore[index]
    recomputed = hashlib.sha256(
        json.dumps(
            {
                "current_state": "blocked",
                "history_index": 4,
                "phase": "review",
                "plan_name": "review-quality-plan",
                "evidence_cursor": dict(failure["evidence_cursor"]),  # type: ignore[arg-type]
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert failure["target"]["target_fingerprint"] == recomputed  # type: ignore[index]
    assert _is_evidence_bound_deterministic_quality_block(
        current_state="blocked",
        retry_strategy="manual_review",
        failure_kind="quality_gate_blocked",
        latest_failure=failure,
        current_target=target,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=_custody(),
    )
    assert decision.dispatch_intent == DISPATCH_INTENT_L1


def test_t23_pre_block_executed_fingerprint_is_not_dispatchable(tmp_path: Path) -> None:
    (tmp_path / "t23-preblock").mkdir()
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_EXECUTED,
        "history": [{"step": "review", "result": "needs_rework"}] * 3,
        "meta": {"total_cost_usd": 0.0},
    }
    pre_block = _review_quality_block_failure(
        state=state,  # type: ignore[arg-type]
        blockers=["unresolved blocking rework: deterministic import check"],
        rework_items=_rework_items(),  # type: ignore[arg-type]
        review_artifact_hash="a" * 64,
    )
    apply_state_projection(state, STATE_BLOCKED, route_signal="blocked")  # type: ignore[arg-type]
    append_history(state, {"step": "review", "result": "needs_rework", "cost_usd": 0.0})  # type: ignore[arg-type]
    state["latest_failure"] = pre_block
    state["resume_cursor"] = {
        "phase": "review",
        "retry_strategy": "manual_review",
        "evidence_cursor": dict(pre_block["evidence_cursor"]),  # type: ignore[index]
    }
    target = _live_target(state, pre_block)
    assert pre_block["kind"] == "review_quality_blocked_unknown"
    assert not _is_evidence_bound_deterministic_quality_block(
        current_state="blocked",
        retry_strategy="manual_review",
        failure_kind="quality_gate_blocked",
        latest_failure=pre_block,
        current_target=target,
    )
    decision = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=_custody(),
    )
    assert decision.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_label_only_canonical_and_recovery_view_must_not_l1(tmp_path: Path) -> None:
    (tmp_path / "t23-label").mkdir()
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_EXECUTED,
        "history": [{"step": "review", "result": "needs_rework"}] * 3,
        "meta": {"total_cost_usd": 0.0},
    }
    failure = _emit_in_production_order(state)
    target = _live_target(state, failure)
    label_only = {"kind": "quality_gate_blocked", "phase": "review", "metadata": {}}
    state["latest_failure"] = label_only

    canonical = classify_repair_dispatch(
        canonical_run_state=CanonicalRunState(
            canonical_state=CanonicalState.REAL_IMPLEMENTATION_BLOCK,
            confidence="high",
            repairable=True,
            running=False,
            next_action="machine_repair_or_replan",
            reason="label-only quality_gate_blocked",
        ),
        plan_state=state,
        current_target=target,
        custody_projection=_custody(),
    )
    recovery = classify_repair_dispatch(
        plan_state=state,
        current_target=target,
        custody_projection=_custody(),
        recovery_view={
            "custody_bucket": "repairable_not_repairing",
            "status": "repairable",
            "recovery_needed": True,
            "permitted_actions": [{"action_type": "repair_dispatch"}],
        },
    )
    assert canonical.dispatch_intent != DISPATCH_INTENT_L1
    assert recovery.dispatch_intent != DISPATCH_INTENT_L1


def test_t23_rejected_class_matrix_stays_closed(tmp_path: Path) -> None:
    (tmp_path / "t23-matrix").mkdir()
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_EXECUTED,
        "history": [{"step": "review", "result": "needs_rework"}] * 3,
        "meta": {"total_cost_usd": 0.0},
    }
    failure = _emit_in_production_order(state)
    target = _live_target(state, failure)
    for failure_kind in (
        "liveness",
        "quota_exceeded",
        "open_pr",
        "human_only",
        "awaiting_human",
        "review_quality_blocked_unknown",
        "quality_gate_circuit_open",
    ):
        state["latest_failure"] = {
            "kind": failure_kind,
            "phase": "review",
            "metadata": {"deterministic": True, "repairability": "deterministic_machine"},
        }
        decision = classify_repair_dispatch(
            plan_state=state,
            current_target=target,
            custody_projection=_custody(),
        )
        assert decision.dispatch_intent != DISPATCH_INTENT_L1, failure_kind


def test_t23_quality_gate_blocked_is_not_a_standalone_l1_token() -> None:
    assert "quality_gate_blocked" not in MACHINE_REPAIRABLE_FAILURE_KINDS
    assert "quality_gate_blocked" not in _IMPLEMENTATION_BLOCK_TOKENS


def test_t23_watchdog_and_supervise_do_not_dispatch_on_quality_label() -> None:
    wrappers = Path(__file__).parents[2] / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
    watchdog = (wrappers / "arnold-watchdog").read_text(encoding="utf-8")
    supervise = (wrappers / "arnold-supervise").read_text(encoding="utf-8")
    assert 'PLAN_STATUS_FAILURE_KIND:-}" == "quality_gate_blocked"' not in watchdog
    assert 'PLAN_STATUS_FAILURE_KIND:-}" == "review_quality_blocked_unknown"' not in watchdog
    assert 'PLAN_STATUS_FAILURE_KIND:-}" == "quality_gate_circuit_open"' not in watchdog
    assert 'kind in {"quality_gate_blocked", "review_rework_exhausted"}' not in supervise
    assert 'kind.startswith("review_quality_blocked")' not in supervise
    assert "PLAN_STATUS_DISPATCH_DECISION" in watchdog
    assert "classify_repair_dispatch" in watchdog
    assert "quality_block_dispatch=" in watchdog
    assert "emit(\"PLAN_STATUS_DISPATCH_DECISION\"" in watchdog


def _t23_eval_plan_attention_env(tmp_path: Path, state: dict[str, object]) -> dict[str, str]:
    """Exec production plan_attention_status_env and eval its emitted env."""
    from tests.cloud.test_watchdog_wrappers import (
        _extract_wrapper_function,
        _run_watchdog_shell,
    )

    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "review-quality-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    initiative_dir = workspace / ".megaplan" / "initiatives" / "demo"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    initiative_dir.mkdir(parents=True)
    spec_path = initiative_dir / "chain.yaml"
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "review-quality-plan",
                "current_milestone_index": 0,
                "last_state": "blocked",
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    repo_root = Path(__file__).parents[2].resolve()
    script = "\n\n".join(
        [
            f"SRC_DIR={str(repo_root)!r}",
            f"PYTHONPATH={str(repo_root)!r}:${{PYTHONPATH:-}}",
            "export SRC_DIR PYTHONPATH",
            _extract_wrapper_function("plan_attention_status_env"),
            (
                "eval \"$(plan_attention_status_env "
                f"{str(workspace)!r} {str(spec_path)!r} chain '')\""
            ),
            'printf "DECISION=%s\\n" "${PLAN_STATUS_DISPATCH_DECISION-UNSET}"',
            'printf "INTENT=%s\\n" "${PLAN_STATUS_DISPATCH_INTENT-UNSET}"',
            'printf "KIND=%s\\n" "${PLAN_STATUS_FAILURE_KIND-UNSET}"',
            (
                'if [[ "${PLAN_STATUS_DISPATCH_DECISION:-}" == "dispatch_l1_repair" ]]; '
                'then printf "ADMIT=1\\n"; else printf "ADMIT=0\\n"; fi'
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr + "\n" + result.stdout
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    return parsed


def test_t23_label_only_quality_gate_blocked_does_not_dispatch_via_env_eval(
    tmp_path: Path,
) -> None:
    (tmp_path / "t23-label-env").mkdir()
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_BLOCKED,
        "history": [{"step": "review", "result": "needs_rework"}] * 4,
        "meta": {"total_cost_usd": 0.0},
        "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": "quality_gate_blocked",
            "phase": "review",
            "metadata": {},
        },
    }
    parsed = _t23_eval_plan_attention_env(tmp_path / "label-only", state)
    assert parsed["KIND"] == "quality_gate_blocked"
    assert parsed["DECISION"] == ""
    assert parsed["ADMIT"] == "0"


def test_t23_complete_evidence_bound_shape_is_only_quality_block_l1_via_env_eval(
    tmp_path: Path,
) -> None:
    (tmp_path / "t23-bound-env").mkdir()
    state: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_EXECUTED,
        "history": [{"step": "review", "result": "needs_rework"}] * 3,
        "meta": {"total_cost_usd": 0.0},
    }
    failure = _emit_in_production_order(state)
    assert failure["kind"] == "quality_gate_blocked"
    parsed = _t23_eval_plan_attention_env(tmp_path / "complete-shape", state)
    assert parsed["KIND"] == "quality_gate_blocked"
    assert parsed["DECISION"] == "dispatch_l1_repair"
    assert parsed["ADMIT"] == "1"

    closed: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_BLOCKED,
        "history": [{"step": "review", "result": "needs_rework"}] * 4,
        "meta": {"total_cost_usd": 0.0},
        "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": "review_quality_blocked_unknown",
            "phase": "review",
            "metadata": {"deterministic": True, "repairability": "deterministic_machine"},
        },
    }
    unknown = _t23_eval_plan_attention_env(tmp_path / "unknown-label", closed)
    assert unknown["KIND"] == "review_quality_blocked_unknown"
    assert unknown["DECISION"] == ""
    assert unknown["ADMIT"] == "0"

    circuit: dict[str, object] = {
        "name": "review-quality-plan",
        "current_state": STATE_BLOCKED,
        "history": [{"step": "review", "result": "needs_rework"}] * 4,
        "meta": {"total_cost_usd": 0.0},
        "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": "quality_gate_circuit_open",
            "phase": "review",
            "metadata": {},
        },
    }
    circuit_parsed = _t23_eval_plan_attention_env(tmp_path / "circuit-open", circuit)
    assert circuit_parsed["KIND"] == "quality_gate_circuit_open"
    assert circuit_parsed["DECISION"] == ""
    assert circuit_parsed["ADMIT"] == "0"
