"""State machine — workflow transitions, robustness levels, step validation.

Sprint 3: the raw state-machine data (the ``WORKFLOW`` dict + the
``_ROBUSTNESS_OVERRIDES`` dict + the ``_ROBUSTNESS_WORKFLOW_LEVELS``
dict + the ``Transition`` dataclass) now lives in
``megaplan/_core/workflow_data.py``. This module re-exports those
names so every existing import keeps working unchanged. The
``Pipeline`` in ``megaplan/_pipeline/planning.py`` reads from the
same shared module, so the data is defined exactly once — no
parallel sources, no parity-drift risk.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from megaplan.types import (
    CliError,
    PlanState,
    ROBUSTNESS_LEVELS,
    normalize_robustness,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_INITIALIZED,
    STATE_PLANNED,
    STATE_PREPPED,
    STATE_REVIEWED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)
from megaplan.store import ProgressEventInput, RevisionConflict, Store
from .modes import is_creative_mode
from .io import find_plan_dir
from .workflow_data import (
    Transition,
    WORKFLOW,
    _ROBUSTNESS_OVERRIDES,
    _ROBUSTNESS_WORKFLOW_LEVELS,
)

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
    """Return the canonical robustness for ``state``.

    Accepts canonical (``bare|light|full|thorough|extreme``) or legacy
    (``tiny|light|standard|robust|superrobust``) names in stored config,
    so older plan states stay readable after the rename.
    """
    robustness = state["config"].get("robustness", "full")
    return normalize_robustness(robustness)


def adaptive_critique_enabled(state: PlanState) -> bool:
    """Return whether adaptive critique evaluator routing is enabled."""
    return bool(state["config"].get("adaptive_critique", False))


def pinned_critic_model(state: PlanState) -> str:
    """Return the model the farmed-out critic is pinned to, or "" if unpinned.

    When set, the adaptive evaluator still selects lenses, but every critic
    dispatch is forced to this model instead of the evaluator's per-lens
    assignment (which can escalate to premium models).
    """
    return str(state["config"].get("critic_model", "") or "").strip()


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


def intent_brief_reference(state: PlanState) -> str:
    """Slim reference to the original brief for post-plan phases."""
    clarification = (state.get("clarification") or {}).get("intent_summary")
    if clarification:
        summary = clarification
    else:
        idea = (state.get("idea") or "").strip()
        first = idea.split("\n\n", 1)[0].split(". ", 1)[0]
        summary = first[:200] + ("..." if len(first) > 200 else "")
    return (
        f"Brief summary: {summary}\n"
        "(Full brief in state.idea; success criteria in plan_v1.meta.json.)"
    )


# ---------------------------------------------------------------------------
# Transition logic
# ---------------------------------------------------------------------------

def _normalize_workflow_robustness(robustness: Any) -> str:
    return normalize_robustness(robustness)


def _workflow_robustness_from_state(state: PlanState) -> str:
    config = state.get("config", {})
    if not isinstance(config, dict):
        return "full"
    return _normalize_workflow_robustness(config.get("robustness", "full"))


def _with_prep_from_state(state: PlanState) -> bool:
    """Read the ``with_prep`` flag persisted at init.

    Returns ``False`` when the key is missing or the config block is
    malformed — matches the flag's default-off semantics.
    """
    config = state.get("config", {})
    if not isinstance(config, dict):
        return False
    return bool(config.get("with_prep", False))


def _with_feedback_from_state(state: PlanState) -> bool:
    """Read the ``with_feedback`` flag persisted at init.

    Returns ``False`` when the key is missing or the config block is
    malformed — matches the flag's default-off semantics.
    """
    config = state.get("config", {})
    if not isinstance(config, dict):
        return False
    return bool(config.get("with_feedback", False))


def _resolve_overrides(robustness: str, *, creative: bool) -> dict[str, list[Transition]]:
    if not creative:
        return _ROBUSTNESS_OVERRIDES.get(robustness, {})
    if robustness in {"extreme", "thorough", "full"}:
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


class BuildBindingError(Exception):
    """Raised by :func:`build_with_binding` when contracts.bind() fails."""

    def __init__(self, gradient: Any) -> None:
        self.gradient = gradient
        super().__init__(str(gradient))


def build_with_binding(
    pipeline: Any,
    *,
    robustness: str = "thorough",
    creative: bool = False,
    with_prep: bool = False,
    with_feedback: bool = False,
) -> Any:
    """Build the pipeline for ``robustness`` and, when typed_ports_on(),
    bind it.

    Deviation (M2 / T5): the M2 brief sketched a ``(robustness, ...)``-only
    signature deriving a ``Pipeline`` from the workflow data here, but
    ``_workflow_for_robustness`` returns the legacy ``dict[state, list[
    Transition]]`` state-machine — not a ``Pipeline`` object — so this
    function takes a pre-built :class:`Pipeline` as a positional argument
    instead. Flag-OFF behavior returns ``pipeline`` unchanged.

    Flag-ON: calls :func:`megaplan._pipeline.contracts.bind` and either
    raises :class:`BuildBindingError` on a :class:`RepairGradient`, or
    returns the same pipeline with ``binding_map`` attached via
    :func:`dataclasses.replace`.
    """
    # Touch resolution helpers so the call participates in workflow
    # normalization (even if the result isn't used today).
    _ = _resolve_overrides(robustness, creative=creative)
    _ = _workflow_for_robustness(
        robustness, creative=creative, with_prep=with_prep, with_feedback=with_feedback
    )

    from megaplan._pipeline.flags import typed_ports_on

    if not typed_ports_on():
        return pipeline

    import dataclasses

    from megaplan._pipeline import contracts
    from megaplan._pipeline.types import Pipeline

    stages = pipeline.stages
    edges = []
    for src, stage in stages.items():
        for edge in getattr(stage, "edges", ()):
            if edge.target != "halt":
                edges.append((src, edge.target))

    result = contracts.bind(list(stages.values()) and dict(stages), edges)
    # contracts.bind expects a Mapping; pass the stages mapping directly.
    result = contracts.bind(dict(stages), edges)
    if isinstance(result, contracts.RepairGradient):
        raise BuildBindingError(result)

    if isinstance(pipeline, Pipeline):
        return dataclasses.replace(pipeline, binding_map=result.binding_map)
    # Fallback: best-effort attribute set for non-Pipeline objects.
    try:
        object.__setattr__(pipeline, "binding_map", result.binding_map)
    except Exception:
        pass
    return pipeline


def _workflow_for_robustness(
    robustness: str,
    *,
    creative: bool = False,
    with_prep: bool = False,
    with_feedback: bool = False,
) -> dict[str, list[Transition]]:
    normalized = _normalize_workflow_robustness(robustness)
    merged = dict(WORKFLOW)
    for level in _ROBUSTNESS_WORKFLOW_LEVELS.get(normalized, _ROBUSTNESS_WORKFLOW_LEVELS["full"]):
        merged.update(_resolve_overrides(level, creative=creative))
    # When --with-prep was set at init, prep must run regardless of the
    # robustness level. The full/light/bare override chain replaces
    # STATE_INITIALIZED -> prep with STATE_INITIALIZED -> plan; we undo
    # that replacement here so the default WORKFLOW transition wins.
    if with_prep:
        merged[STATE_INITIALIZED] = list(WORKFLOW[STATE_INITIALIZED])
    # When --with-feedback was set at init, feedback runs regardless of
    # robustness. Light/bare set STATE_EXECUTED: [] to skip review; we
    # undo that so review can run (feedback needs it). We also rewire
    # STATE_EXECUTED → review → STATE_REVIEWED (instead of STATE_DONE)
    # and add STATE_REVIEWED → feedback → STATE_DONE.
    if with_feedback:
        merged[STATE_EXECUTED] = [Transition("review", STATE_REVIEWED)]
        merged[STATE_REVIEWED] = [Transition("feedback", STATE_DONE)]
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
    if condition == "gate_proceed_agent_availability_blocked":
        preflight = gate.get("preflight_results", {})
        if not isinstance(preflight, dict):
            preflight = {}
        failed = {name for name, passed in preflight.items() if not passed}
        return (
            recommendation == "PROCEED"
            and not gate.get("passed", False)
            and bool(failed)
            and failed <= {"claude_available", "codex_available"}
        )
    if condition == "gate_proceed_blocked":
        return recommendation == "PROCEED" and not gate.get("passed", False)
    if condition == "gate_proceed":
        return recommendation == "PROCEED" and gate.get("passed", False)
    return False


def workflow_includes_step(
    robustness: str,
    step: str,
    *,
    with_prep: bool = False,
    with_feedback: bool = False,
) -> bool:
    if step == "step":
        return True
    from megaplan._core.topology import RunTopologyConfig, build_topology

    graph = build_topology(
        RunTopologyConfig(
            robustness=normalize_robustness(robustness),
            creative=False,
            with_prep=with_prep,
            with_feedback=with_feedback,
        )
    )
    return any(edge.step == step for edge in graph.edges)


def workflow_transition(state: PlanState, step: str) -> Transition | None:
    current = state.get("current_state")
    if not isinstance(current, str):
        return None
    from megaplan._core.topology import RunTopologyConfig, build_topology

    graph = build_topology(
        RunTopologyConfig(
            robustness=_workflow_robustness_from_state(state),
            creative=is_creative_mode(state),
            with_prep=_with_prep_from_state(state),
            with_feedback=_with_feedback_from_state(state),
        )
    )
    for edge in graph.successors(current):
        if edge.step == step and _transition_matches(state, edge.condition):
            return Transition(edge.step, edge.dst, edge.condition)
    return None


def workflow_next(state: PlanState) -> list[str]:
    current = state.get("current_state")
    if not isinstance(current, str):
        return []
    from megaplan._core.topology import RunTopologyConfig, build_topology

    graph = build_topology(
        RunTopologyConfig(
            robustness=_workflow_robustness_from_state(state),
            creative=is_creative_mode(state),
            with_prep=_with_prep_from_state(state),
            with_feedback=_with_feedback_from_state(state),
        )
    )
    next_steps = [
        edge.step
        for edge in graph.successors(current)
        if _transition_matches(state, edge.condition)
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


# `_RESUME_ACTIVE_STATES` is now derived on demand from the realized graph
# via `topology.predecessors(phase, policy='resume')` — see M3 Step 7.


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
    from megaplan._core import topology as _topology
    active_state = _topology.predecessors(phase, policy="resume")
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
