"""Canonical state-machine data shared by ``_core.workflow`` and ``_pipeline``.

Sprint 3 follow-up: the ``WORKFLOW`` dict and ``_ROBUSTNESS_OVERRIDES``
dict that used to live in ``megaplan/_core/workflow.py`` now live here.
This is the single source of truth — both the legacy state-machine
helpers in ``_core/workflow.py`` and the compiled ``Pipeline`` in
``megaplan/_pipeline/planning.py`` import from this module.

There are no behaviour changes. The legacy module re-exports
``WORKFLOW`` and ``_ROBUSTNESS_OVERRIDES`` so every existing import
keeps working. The Pipeline compilation reads from the same dicts
so the parity tests still pass. The only difference: the data is
defined exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass

from megaplan.types import (
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


@dataclass(frozen=True)
class Transition:
    next_step: str
    next_state: str
    condition: str = "always"


WORKFLOW: dict[str, list[Transition]] = {
    STATE_INITIALIZED: [
        Transition("prep", STATE_PREPPED),
        Transition("prep", STATE_AWAITING_HUMAN),
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
        Transition("override force-proceed", STATE_GATED, "gate_proceed_agent_availability_blocked"),
        Transition("gate", STATE_GATED, "gate_proceed_blocked"),
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
        Transition("review", STATE_DONE),
    ],
    STATE_AWAITING_HUMAN: [
        Transition("verify-human", STATE_DONE),
        Transition("resume-clarify", STATE_PREPPED),
    ],
    STATE_TIEBREAKER_PENDING: [
        Transition("tiebreaker-run", STATE_TIEBREAKER_READY),
    ],
    STATE_TIEBREAKER_READY: [
        Transition("tiebreaker-decide", STATE_CRITIQUED),
    ],
}


_ROBUSTNESS_OVERRIDES: dict[str, dict[str, list[Transition]]] = {
    "extreme": {},
    "thorough": {},
    "full": {
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
    "bare": {
        STATE_PLANNED: [
            Transition("finalize", STATE_GATED),
        ],
    },
}


_ROBUSTNESS_WORKFLOW_LEVELS: dict[str, tuple[str, ...]] = {
    "extreme": ("extreme",),
    "thorough": ("thorough",),
    "full": ("full",),
    "light": ("full", "light"),
    "bare": ("full", "light", "bare"),
}
