"""Bakeoff-owned binding hooks for the shared control interface.

Callers inject a ``BakeoffControlBinding`` instance directly (e.g. via
``bakeoff_control_binding()``) rather than relying on string dispatch
(``binding="bakeoff"``).  The control interface's ``_resolve_binding_and_state``
supports both the canonical ``"megaplan"`` and legacy ``"planning"`` string
dispatch; all new bindings use direct ``ControlBinding`` injection.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arnold.pipelines.megaplan.bakeoff.state import BakeoffPhase
from arnold.control.interface import (
    CONTROL_TARGET_ABORT,
    ControlTargetRef,
    ControlTransition,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from arnold.runtime.outcome import RunOutcome


BAKEOFF_TARGET_RUN_PROFILES = "run-profiles"
BAKEOFF_TARGET_COMPARE = "compare"
BAKEOFF_TARGET_SELECT = "select"
BAKEOFF_TARGET_MERGE = "merge"

_TERMINAL_PROFILE_OUTCOMES = frozenset(
    {
        "done",
        "failed",
        "aborted",
        "cancelled",
        "paused",
        "stalled",
        "blocked",
        "worker_blocked",
        "cost_cap_exceeded",
        "context_retry_exhausted",
        "human_required",
        "awaiting_human",
        "tiebreaker_pending",
        "tiebreaker_ready",
        "escalated",
        "cap",
    }
)
_PHASES_REQUIRING_HUMAN = frozenset({"compared", "picked"})
_KNOWN_TARGETS = frozenset(
    {
        BAKEOFF_TARGET_RUN_PROFILES,
        BAKEOFF_TARGET_COMPARE,
        BAKEOFF_TARGET_SELECT,
        BAKEOFF_TARGET_MERGE,
        CONTROL_TARGET_ABORT,
    }
)
_TARGET_TO_ACTION = {
    BAKEOFF_TARGET_RUN_PROFILES: "resume",
    BAKEOFF_TARGET_COMPARE: "compare",
    BAKEOFF_TARGET_SELECT: "pick",
    BAKEOFF_TARGET_MERGE: "merge",
    CONTROL_TARGET_ABORT: "abandon",
}


def bakeoff_run_state_view(
    raw_state: Mapping[str, object],
    *,
    run_id: str | None = None,
) -> RunStateView:
    """Build a supervisor-facing run-state view directly from bakeoff state."""

    state = dict(raw_state)
    experiment_id = state.get("experiment_id")
    resolved_run_id = (
        run_id
        or (experiment_id if isinstance(experiment_id, str) and experiment_id else "bakeoff-run")
    )
    phase = state.get("phase")
    phase_str = phase if isinstance(phase, str) and phase else None
    return RunStateView(
        run_id=resolved_run_id,
        outcome=_project_bakeoff_outcome(phase_str),
        cursor=phase_str,
        metadata={
            "projection_surface": "supervisor",
            "bakeoff_phase": phase_str,
            "has_terminal_profile_set": _all_profiles_terminal(state),
        },
        raw_state=state,
    )


class BakeoffControlBinding:
    """Control binding for bakeoff state transitions at the supervisor boundary."""

    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        return _targets_for_phase(run_state.raw_state, recovery=False)

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        return _targets_for_phase(run_state.raw_state, recovery=True)

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition | ControlTransitionRequest,
    ) -> ControlTransitionResult:
        target_id = _transition_target_id(transition)
        if target_id not in _KNOWN_TARGETS:
            return ControlTransitionResult(
                accepted=False,
                mutated=False,
                reason="bakeoff_control_binding_transition_unimplemented",
            )
        available = {
            target.id for target in self.valid_targets(run_state)
        } | {target.id for target in self.recover_targets(run_state)}
        if target_id not in available:
            return ControlTransitionResult(
                accepted=False,
                mutated=False,
                reason="bakeoff_control_binding_target_unavailable",
            )
        artifacts = self.synthesize_artifacts(run_state, transition)
        return ControlTransitionResult(
            accepted=True,
            mutated=False,
            reason=f"bakeoff:{artifacts['bakeoff_action']}",
            artifacts=artifacts,
        )

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransition | ControlTransitionRequest,
    ) -> Mapping[str, Any]:
        target_id = _transition_target_id(transition)
        bakeoff_action = _TARGET_TO_ACTION.get(target_id)
        if bakeoff_action is None:
            return {}
        raw_state = run_state.raw_state
        artifacts: dict[str, Any] = {
            "target_id": target_id,
            "bakeoff_action": bakeoff_action,
        }
        experiment_id = raw_state.get("experiment_id")
        if isinstance(experiment_id, str) and experiment_id:
            artifacts["experiment_id"] = experiment_id
        if target_id == BAKEOFF_TARGET_SELECT:
            chosen_profile = _selected_profile(raw_state)
            if chosen_profile is not None:
                artifacts["profile"] = chosen_profile
        return artifacts


def bakeoff_control_binding() -> BakeoffControlBinding:
    return BakeoffControlBinding()


def _project_bakeoff_outcome(phase: str | None) -> RunOutcome | None:
    if phase == "merged":
        return RunOutcome.SUCCEEDED
    if phase == "abandoned":
        return RunOutcome.FAILED
    if phase in _PHASES_REQUIRING_HUMAN:
        return RunOutcome.AWAITING_HUMAN
    return None


def _targets_for_phase(
    raw_state: Mapping[str, object],
    *,
    recovery: bool,
) -> tuple[ControlTargetRef, ...]:
    phase = raw_state.get("phase")
    if not isinstance(phase, str):
        return ()
    if phase == "running":
        if recovery:
            return (_target(BAKEOFF_TARGET_RUN_PROFILES, phase),)
        if _all_profiles_terminal(raw_state):
            return (
                _target(BAKEOFF_TARGET_COMPARE, phase),
                _target(CONTROL_TARGET_ABORT, phase),
            )
        return (
            _target(BAKEOFF_TARGET_RUN_PROFILES, phase),
            _target(CONTROL_TARGET_ABORT, phase),
        )
    if phase == "compared":
        targets = [_target(BAKEOFF_TARGET_SELECT, phase)]
        if _selected_profile(raw_state) is not None:
            targets.append(_target(BAKEOFF_TARGET_MERGE, phase))
        targets.append(_target(CONTROL_TARGET_ABORT, phase))
        return tuple(targets)
    if phase == "picked":
        return (
            _target(BAKEOFF_TARGET_MERGE, phase),
            _target(CONTROL_TARGET_ABORT, phase),
        )
    return ()


def _target(target_id: str, phase: BakeoffPhase | str) -> ControlTargetRef:
    return ControlTargetRef(
        id=target_id,
        label=target_id,
        metadata={
            "kind": "control_target",
            "actionable": True,
            "surface": "supervisor",
            "bakeoff_phase": phase,
        },
    )


def _all_profiles_terminal(raw_state: Mapping[str, object]) -> bool:
    profiles = raw_state.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        return False
    for profile in profiles:
        if not isinstance(profile, Mapping):
            return False
        outcome = profile.get("outcome")
        if not isinstance(outcome, Mapping):
            return False
        status = outcome.get("status")
        if not isinstance(status, str) or status not in _TERMINAL_PROFILE_OUTCOMES:
            return False
    return True


def _selected_profile(raw_state: Mapping[str, object]) -> str | None:
    selected = raw_state.get("chosen_profile")
    if isinstance(selected, str) and selected:
        return selected
    return None


def _transition_target_id(
    transition: ControlTransition | ControlTransitionRequest,
) -> str | None:
    target_id = transition.target_id
    if isinstance(target_id, str) and target_id:
        return target_id
    action = getattr(transition, "action", None)
    if isinstance(action, str) and action in _KNOWN_TARGETS:
        return action
    op = getattr(transition, "op", None)
    if isinstance(op, str) and op in _KNOWN_TARGETS:
        return op
    return None


__all__ = [
    "BAKEOFF_TARGET_COMPARE",
    "BAKEOFF_TARGET_MERGE",
    "BAKEOFF_TARGET_RUN_PROFILES",
    "BAKEOFF_TARGET_SELECT",
    "BakeoffControlBinding",
    "bakeoff_control_binding",
    "bakeoff_run_state_view",
]
