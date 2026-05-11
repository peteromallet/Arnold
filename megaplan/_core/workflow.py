"""State machine — workflow transitions, robustness levels, step validation."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from megaplan.types import (
    CliError,
    PlanState,
    ROBUSTNESS_LEVELS,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_INITIALIZED,
    STATE_PLANNED,
    STATE_PREPPED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)
from megaplan.store import ProgressEventInput, RevisionConflict, Store
from .modes import is_creative_mode
from .io import find_plan_dir


@dataclass(frozen=True)
class Transition:
    next_step: str
    next_state: str
    condition: str = "always"


WORKFLOW: dict[str, list[Transition]] = {
    STATE_INITIALIZED: [
        Transition("prep", STATE_PREPPED),
    ],
    STATE_PREPPED: [
        Transition("plan", STATE_PLANNED),
    ],
    STATE_PLANNED: [
        Transition("critique", STATE_CRITIQUED),
        Transition("plan", STATE_PLANNED),
    ],
    STATE_CRITIQUED: [
        Transition("gate", STATE_GATED, "gate_unset"),
        Transition("revise", STATE_PLANNED, "gate_iterate"),
        Transition("tiebreaker", STATE_TIEBREAKER_PENDING, "gate_tiebreaker"),
        Transition("override add-note", STATE_CRITIQUED, "gate_escalate"),
        Transition("override force-proceed", STATE_GATED, "gate_escalate"),
        Transition("override abort", STATE_ABORTED, "gate_escalate"),
        Transition("revise", STATE_PLANNED, "gate_proceed_blocked"),
        Transition("override force-proceed", STATE_GATED, "gate_proceed_blocked"),
        Transition("gate", STATE_GATED, "gate_proceed"),
    ],
    STATE_GATED: [
        Transition("finalize", STATE_FINALIZED),
        Transition("override replan", STATE_PLANNED),
    ],
    STATE_FINALIZED: [
        Transition("execute", STATE_EXECUTED),
        Transition("override replan", STATE_PLANNED),
    ],
    STATE_EXECUTED: [
        # `handle_review()` may also return STATE_FINALIZED on a `needs_rework`
        # verdict. That rework loop depends on review payload semantics rather
        # than gate_* conditions, so it lives in the handler instead of here
        # because `_transition_matches()` only understands gate-based branches.
        Transition("review", STATE_DONE),
    ],
    STATE_AWAITING_HUMAN: [
        Transition("verify-human", STATE_DONE),
    ],
    STATE_TIEBREAKER_PENDING: [
        Transition("tiebreaker-run", STATE_TIEBREAKER_READY),
    ],
    STATE_TIEBREAKER_READY: [
        Transition("tiebreaker-decide", STATE_CRITIQUED),
    ],
}

# Each level's *own* overrides (not inherited).  Levels inherit from the
# level below them via _ROBUSTNESS_HIERARCHY so shared transitions are
# declared once: robust/superrobust have none, standard keeps the
# planned->critique routing documented explicitly, and light skips
# prep plus gate/review.
_ROBUSTNESS_OVERRIDES: dict[str, dict[str, list[Transition]]] = {
    "superrobust": {},
    "robust": {},
    "standard": {
        STATE_INITIALIZED: [
            Transition("plan", STATE_PLANNED),
        ],
    },
    "light": {
        STATE_INITIALIZED: [
            Transition("plan", STATE_PLANNED),
        ],
        STATE_CRITIQUED: [
            Transition("revise", STATE_GATED),
        ],
        STATE_EXECUTED: [],
    },
    "tiny": {},
}

_ROBUSTNESS_WORKFLOW_LEVELS: dict[str, tuple[str, ...]] = {
    "superrobust": ("superrobust",),
    "robust": ("robust",),
    "standard": ("standard",),
    "light": ("standard", "light"),
    "tiny": ("standard", "light", "tiny"),
}

_STEP_CONTEXT_STATES = {
    STATE_PLANNED,
    STATE_CRITIQUED,
    STATE_GATED,
    STATE_FINALIZED,
}


# ---------------------------------------------------------------------------
# Robustness helpers
# ---------------------------------------------------------------------------

def configured_robustness(state: PlanState) -> str:
    robustness = state["config"].get("robustness", "standard")
    if robustness not in ROBUSTNESS_LEVELS:
        return "standard"
    return robustness


def robustness_critique_instruction(robustness: str) -> str:
    if robustness == "light":
        return "Be pragmatic. Only flag issues that would cause real failures. Ignore style, minor edge cases, and issues the executor will naturally resolve."
    return "Use balanced judgment. Flag significant risks, but do not spend flags on minor polish or executor-obvious boilerplate."


# ---------------------------------------------------------------------------
# Intent / notes block for prompts
# ---------------------------------------------------------------------------

def intent_and_notes_block(state: PlanState) -> str:
    sections = []
    clarification = state.get("clarification", {})
    if clarification.get("intent_summary"):
        sections.append(f"User intent summary:\n{clarification['intent_summary']}")
        sections.append(f"Original idea:\n{state['idea']}")
    else:
        sections.append(f"Idea:\n{state['idea']}")
    notes = state["meta"].get("notes", [])
    if notes:
        notes_text = "\n".join(f"- {note['note']}" for note in notes)
        sections.append(f"User notes and answers:\n{notes_text}")
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Transition logic
# ---------------------------------------------------------------------------

def _normalize_workflow_robustness(robustness: Any) -> str:
    if robustness in ROBUSTNESS_LEVELS:
        return str(robustness)
    return "standard"


def _workflow_robustness_from_state(state: PlanState) -> str:
    config = state.get("config", {})
    if not isinstance(config, dict):
        return "standard"
    return _normalize_workflow_robustness(config.get("robustness", "standard"))


def _with_prep_from_state(state: PlanState) -> bool:
    """Read the ``with_prep`` flag persisted at init.

    Returns ``False`` when the key is missing or the config block is
    malformed — matches the flag's default-off semantics.
    """
    config = state.get("config", {})
    if not isinstance(config, dict):
        return False
    return bool(config.get("with_prep", False))


def _resolve_overrides(robustness: str, *, creative: bool) -> dict[str, list[Transition]]:
    if not creative:
        return _ROBUSTNESS_OVERRIDES.get(robustness, {})
    if robustness in {"superrobust", "robust", "standard"}:
        return {}
    if robustness == "light":
        return {
            STATE_PLANNED: [
                Transition("finalize", STATE_GATED),
            ],
            STATE_CRITIQUED: [
                Transition("revise", STATE_GATED),
            ],
            STATE_EXECUTED: [],
        }
    return _ROBUSTNESS_OVERRIDES.get(robustness, {})


def _workflow_for_robustness(
    robustness: str,
    *,
    creative: bool = False,
    with_prep: bool = False,
) -> dict[str, list[Transition]]:
    normalized = _normalize_workflow_robustness(robustness)
    merged = dict(WORKFLOW)
    for level in _ROBUSTNESS_WORKFLOW_LEVELS.get(normalized, _ROBUSTNESS_WORKFLOW_LEVELS["standard"]):
        merged.update(_resolve_overrides(level, creative=creative and normalized != "tiny"))
    # When --with-prep was set at init, prep must run regardless of the
    # robustness level. The standard/light/tiny override chain replaces
    # STATE_INITIALIZED -> prep with STATE_INITIALIZED -> plan; we undo
    # that replacement here so the default WORKFLOW transition wins.
    if with_prep:
        merged[STATE_INITIALIZED] = list(WORKFLOW[STATE_INITIALIZED])
    return merged


def _transition_matches(state: PlanState, condition: str) -> bool:
    if condition == "always":
        return True
    gate = state.get("last_gate", {})
    if not isinstance(gate, dict):
        gate = {}
    recommendation = gate.get("recommendation")
    if condition == "gate_unset":
        return not recommendation
    if condition == "gate_iterate":
        return recommendation == "ITERATE"
    if condition == "gate_escalate":
        return recommendation == "ESCALATE"
    if condition == "gate_tiebreaker":
        return recommendation == "TIEBREAKER"
    if condition == "gate_proceed_blocked":
        return recommendation == "PROCEED" and not gate.get("passed", False)
    if condition == "gate_proceed":
        return recommendation == "PROCEED" and gate.get("passed", False)
    return False


def workflow_includes_step(robustness: str, step: str, *, with_prep: bool = False) -> bool:
    if step == "step":
        return True
    workflow = _workflow_for_robustness(robustness, with_prep=with_prep)
    return any(
        transition.next_step == step
        for transitions in workflow.values()
        for transition in transitions
    )


def workflow_transition(state: PlanState, step: str) -> Transition | None:
    current = state.get("current_state")
    if not isinstance(current, str):
        return None
    workflow = _workflow_for_robustness(
        _workflow_robustness_from_state(state),
        creative=is_creative_mode(state),
        with_prep=_with_prep_from_state(state),
    )
    for transition in workflow.get(current, []):
        if transition.next_step == step and _transition_matches(state, transition.condition):
            return transition
    return None


def workflow_next(state: PlanState) -> list[str]:
    current = state.get("current_state")
    if not isinstance(current, str):
        return []
    workflow = _workflow_for_robustness(
        _workflow_robustness_from_state(state),
        creative=is_creative_mode(state),
        with_prep=_with_prep_from_state(state),
    )
    next_steps = [
        transition.next_step
        for transition in workflow.get(current, [])
        if _transition_matches(state, transition.condition)
    ]
    if current in _STEP_CONTEXT_STATES:
        next_steps.append("step")
    return next_steps


infer_next_steps = workflow_next


def _resume_phase_args(phase: str, cursor: dict[str, Any], plan: str) -> list[str]:
    args = [phase, "--plan", plan]
    if phase == "execute":
        args.extend(["--confirm-destructive", "--user-approved"])
        batch_index = cursor.get("batch_index")
        if isinstance(batch_index, int) and batch_index > 0:
            args.extend(["--batch", str(batch_index)])
    return args


def _default_resume_runner(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


_RESUME_ACTIVE_STATES: dict[str, str] = {
    "prep": "initialized",
    "plan": "initialized",
    "critique": "planned",
    "gate": "critiqued",
    "revise": "critiqued",
    "finalize": "gated",
    "execute": "finalized",
    "review": "executed",
}


def resume_plan(
    root: Path,
    plan: str,
    *,
    store: Store | None = None,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Resume a failed/blocked plan from its stored resume cursor."""

    from megaplan.store import PlanRepository

    plan_dir = find_plan_dir(root, plan)
    if plan_dir is None:
        raise CliError("missing_plan", f"Plan '{plan}' does not exist")
    repo = PlanRepository.from_plan_dir(plan_dir, store=store)
    loaded = repo.load_plan()
    cursor = loaded.resume_cursor
    if not isinstance(cursor, dict):
        raise CliError("missing_resume_cursor", f"Plan '{plan}' has no resume cursor")
    phase = cursor.get("phase")
    if not isinstance(phase, str) or not phase:
        raise CliError("invalid_resume_cursor", f"Plan '{plan}' has an invalid resume cursor", extra={"resume_cursor": cursor})
    args = _resume_phase_args(phase, cursor, plan)
    runner_fn = runner or _default_resume_runner
    previous_state = repo.load_state()
    active_state = _RESUME_ACTIVE_STATES.get(phase)
    if active_state and previous_state.get("current_state") in {"failed", "blocked"}:
        state = dict(previous_state)
        state["current_state"] = active_state
        repo.save_state(state)
    try:
        code, stdout, stderr = runner_fn(args, cwd=root)
    except RevisionConflict as error:
        repo.save_state(previous_state)
        state = repo.load_state()
        epic_id = state.get("epic_id") or (state.get("meta") or {}).get("epic_id")
        details = {"phase": phase, "message": str(error), "resume_cursor": cursor}
        if store is not None and isinstance(epic_id, str) and epic_id:
            store.append_progress_event(
                ProgressEventInput(
                    epic_id=epic_id,
                    plan_id=plan,
                    kind="execution_blocked",
                    summary=f"Resume blocked by revision conflict in phase '{phase}'",
                    details=details,
                )
            )
        raise CliError(
            "revision_conflict",
            f"Resume blocked by revision conflict while running '{phase}': {error}",
            extra=details,
        ) from error
    if code != 0:
        repo.save_state(previous_state)
        return {
            "success": False,
            "step": "resume",
            "plan": plan,
            "phase": phase,
            "resume_cursor": cursor,
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
        }
    state = repo.load_state()
    state.pop("latest_failure", None)
    state.pop("resume_cursor", None)
    repo.save_state(state)
    return {
        "success": True,
        "step": "resume",
        "plan": plan,
        "phase": phase,
        "command": args,
        "state": state.get("current_state"),
    }


def require_state(state: PlanState, step: str, allowed: set[str]) -> None:
    current = state["current_state"]
    if current not in allowed:
        raise CliError(
            "invalid_transition",
            f"Cannot run '{step}' while current state is '{current}'",
            valid_next=infer_next_steps(state),
            extra={"current_state": current},
        )
