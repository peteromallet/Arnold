#!/usr/bin/env python3
"""Apply T14 changes to batch.py using AST-aware transforms."""
from pathlib import Path

path = Path("arnold_pipelines/megaplan/execute/batch.py")
content = path.read_text(encoding="utf-8")

# --- Change 1: Add recovery_policy imports ---
old_import = """from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    pre_existing_task_ids_from_contract,
)"""
new_import = """from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    pre_existing_task_ids_from_contract,
)
from arnold_pipelines.megaplan.orchestration.recovery_policy import (
    CIRCUIT_OPEN_THRESHOLD,
    CircuitState,
    classify_failure_class,
    normalize_failure_signature,
    circuit_transition,
)"""
assert old_import in content, "Import block not found"
content = content.replace(old_import, new_import)

# --- Change 2: Add _MAX_SERIAL_REWORK constant ---
old_const = """_UNROUTABLE_REWORK_ATTEMPTS_KEY = "unroutable_rework_attempts"
_MAX_UNROUTABLE_REWORK_RERUNS = 2
_ROUTABLE_REWORK_TARGET_KINDS = {"task", "bulk", "manifest"}"""
new_const = """_UNROUTABLE_REWORK_ATTEMPTS_KEY = "unroutable_rework_attempts"
_MAX_UNROUTABLE_REWORK_RERUNS = 2
# M8A T14 -- rework-wave ceiling: if review requests rework on more than
# _MAX_SERIAL_REWORK tasks, the executor refuses to dispatch and emits a typed
# blocker/escalation instead of running an unbounded rework wave.
_MAX_SERIAL_REWORK = 5
_ROUTABLE_REWORK_TARGET_KINDS = {"task", "bulk", "manifest"}"""
assert old_const in content, "Constants block not found"
content = content.replace(old_const, new_const)

# --- Change 3: Add _emit_rework_wave_blocker function ---
# Find the last "return response" before "def handle_execute_auto_loop"
old_func_end = """    response["result"] = "blocked"
    return response


def handle_execute_auto_loop(
    *,"""
new_func_end = """    response["result"] = "blocked"
    return response


def _emit_rework_wave_blocker(
    *,
    plan_dir: Path,
    state: PlanState,
    auto_approve: bool,
    reason: str,
    rework_task_ids: list[str],
) -> StepResponse:
    \"\"\"Emit a typed blocker when the rework wave exceeds the ceiling.

    M8A T14 -- when review requests rework on more than ``_MAX_SERIAL_REWORK``
    tasks, the executor refuses to dispatch and emits a typed
    blocker/escalation with preserved quality-block evidence (task IDs,
    rework-wave size, ceiling).  The blocker is clearable via ``override
    recover-blocked`` / ``force-proceed`` after operator review, same as
    ``_handle_unroutable_review_rework``.
    \"\"\"
    from arnold_pipelines.megaplan.observability.events import EventKind, emit

    sorted_ids = sorted(set(rework_task_ids))
    emit(
        EventKind.STATE_TRANSITION,
        plan_dir=plan_dir,
        phase="execute",
        payload={
            "reason": "rework_wave_exceeds_ceiling",
            "from": STATE_FINALIZED,
            "to": STATE_BLOCKED,
            "rework_wave_size": len(sorted_ids),
            "ceiling": _MAX_SERIAL_REWORK,
            "rework_task_ids": sorted_ids,
            "failed": f"rework-wave ceiling ({_MAX_SERIAL_REWORK}) exceeded",
        },
    )
    response: StepResponse = {
        "success": False,
        "step": "execute",
        "summary": reason,
        "artifacts": ["finalize.json", "final.md"],
        "monitor_hint": "",
        "next_step": "finalize",
        "state": STATE_FINALIZED,
        "files_changed": [],
        "deviations": [],
        "warnings": [reason],
        "auto_approve": auto_approve,
        "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
        "blocked_task_ids": sorted_ids,
        "_phase_outcome": "blocked_by_quality",
        "_blocked_retry_decision": {
            "outcome": "escalate",
            "reason": reason,
            "rework_wave_size": len(sorted_ids),
            "ceiling": _MAX_SERIAL_REWORK,
        },
    }
    return response


def handle_execute_auto_loop(
    *,"""
assert old_func_end in content, "Function end not found"
content = content.replace(old_func_end, new_func_end)

# --- Change 4: Add rework-wave ceiling enforcement ---
old_rework_mode = """                rework_mode = True
                pending_tasks = [
                    task
                    for task in tasks
                    if task.get("id") in set(review_rework_task_ids)
                ]
    if blocked_task_ids:"""
new_rework_mode = """                rework_mode = True
                pending_tasks = [
                    task
                    for task in tasks
                    if task.get("id") in set(review_rework_task_ids)
                ]
                # M8A T14 -- rework-wave ceiling enforcement: if review
                # requests rework on more than _MAX_SERIAL_REWORK tasks,
                # refuse to dispatch and emit a typed blocker/escalation
                # with preserved quality-block evidence. This prevents
                # unbounded rework waves from consuming the plan's budget.
                if len(review_rework_task_ids) > _MAX_SERIAL_REWORK:
                    rework_ids = sorted(review_rework_task_ids)
                    ceiling_reason = (
                        f"review rework wave ({len(rework_ids)} tasks) exceeds "
                        f"{_MAX_SERIAL_REWORK}-task ceiling; "
                        "remaining tasks should be replanned as a separate "
                        "milestone. Blocked task IDs: "
                        + ", ".join(rework_ids[:10])
                        + (f" and {len(rework_ids) - 10} more" if len(rework_ids) > 10 else "")
                    )
                    log.warning(
                        "rework-wave ceiling hit: %d rework tasks > %d -- "
                        "emitting typed blocker instead of dispatching",
                        len(review_rework_task_ids),
                        _MAX_SERIAL_REWORK,
                    )
                    return _emit_rework_wave_blocker(
                        plan_dir=plan_dir,
                        state=state,
                        auto_approve=auto_approve,
                        reason=ceiling_reason,
                        rework_task_ids=rework_ids,
                    )
    if blocked_task_ids:"""
assert old_rework_mode in content, "Rework mode block not found"
content = content.replace(old_rework_mode, new_rework_mode)

# --- Change 5: Add evidence to blocked retry decisions (Block 1 - baseline_deviations) ---
# Block 1 has: "deviations": _deviation_dicts(baseline_deviations), and "_phase_outcome": "blocked_by_quality"
old_block1 = """                    "_phase_outcome": "blocked_by_quality",
                    # Attach the typed retry decision so the handler can
                    # emit targeted anchor evidence without re-deriving it.
                    "_blocked_retry_decision": {
                        "outcome": _retry_decision.outcome.value,
                        "reason": _retry_decision.reason,
                    },
                }
                _attach_next_step_runtime(response)
                return response

            blocked_list = ", ".join(sorted(prereq_blocked_ids or blocked_task_ids))"""

new_block1 = """                    "_phase_outcome": "blocked_by_quality",
                    # Attach the typed retry decision so the handler can
                    # emit targeted anchor evidence without re-deriving it.
                    # M8A T14 -- preserve `failed: <detail>` command/artifact
                    # evidence for quality-block traceability.
                    "_blocked_retry_decision": {
                        "outcome": _retry_decision.outcome.value,
                        "reason": _retry_decision.reason,
                        "failed": "blocked_by_quality: baseline deviations prevent execution; review deviations for task-level detail",
                        "evidence": {
                            "deviations": _deviation_dicts(baseline_deviations),
                            "blocked_task_ids": sorted(prereq_blocked_ids or blocked_task_ids),
                        },
                    },
                }
                _attach_next_step_runtime(response)
                return response

            blocked_list = ", ".join(sorted(prereq_blocked_ids or blocked_task_ids))"""

assert old_block1 in content, "Block1 not found"
content = content.replace(old_block1, new_block1)

# --- Change 6: Add evidence to blocked retry decisions (Block 2 - blocked_by_prereq) ---
old_block2 = """                    "_phase_outcome": "blocked_by_prereq",
                # Attach the typed retry decision so the handler can
                # emit targeted anchor evidence without re-deriving it.
                "_blocked_retry_decision": {
                    "outcome": _retry_decision.outcome.value,
                    "reason": _retry_decision.reason,
                },
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)"""

new_block2 = """                    "_phase_outcome": "blocked_by_prereq",
                # Attach the typed retry decision so the handler can
                # emit targeted anchor evidence without re-deriving it.
                # M8A T14 -- preserve `failed: <detail>` command/artifact
                # evidence for prerequisite-block traceability.
                "_blocked_retry_decision": {
                    "outcome": _retry_decision.outcome.value,
                    "reason": _retry_decision.reason,
                    "failed": "blocked_by_prereq: prerequisite-blocked tasks prevent dependent execution; review blocked task evidence",
                    "evidence": {
                        "blocked_task_ids": sorted(prereq_blocked_ids or blocked_task_ids),
                    },
                },
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)"""

assert old_block2 in content, "Block2 not found"
content = content.replace(old_block2, new_block2)

# Write back
path.write_text(content, encoding="utf-8")
print("All changes applied successfully.")
