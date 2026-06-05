#!/usr/bin/env python3
"""Record the workflow_next control-flow parity matrix.

This fixture is a control-flow parity reference, NOT drift-provably-zero.
It records the legacy workflow_next fold over the full robustness x
prep/feedback x state x verdict matrix so graph projection tests can
catch accidental future control-flow drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arnold.pipelines.megaplan._core.topology import predecessors
from arnold.pipelines.megaplan._core.workflow import (
    _STEP_CONTEXT_STATES,
    _transition_matches,
    _workflow_for_robustness,
)
from arnold.pipelines.megaplan.planning.state import CANONICAL_PLAN_STATES

FIXTURE_PATH = ROOT / "tests" / "parity" / "fixtures" / "workflow_next_matrix.json"
LABEL = "control-flow parity, NOT drift-provably-zero"

ROBUSTNESS_LEVELS = ("extreme", "thorough", "full", "light", "bare")
MODE_FLAGS = (
    {"with_prep": False, "with_feedback": False},
    {"with_prep": True, "with_feedback": False},
    {"with_prep": False, "with_feedback": True},
    {"with_prep": True, "with_feedback": True},
)
VERDICTS: dict[str, Any] = {
    "unset": {},
    "iterate": {"recommendation": "ITERATE"},
    "escalate": {"recommendation": "ESCALATE"},
    "tiebreaker": {"recommendation": "TIEBREAKER"},
    "proceed": {"recommendation": "PROCEED", "passed": True},
    "proceed_blocked": {
        "recommendation": "PROCEED",
        "passed": False,
        "preflight_results": {},
    },
    "proceed_agent_availability_blocked": {
        "recommendation": "PROCEED",
        "passed": False,
        "preflight_results": {
            "claude_available": False,
            "codex_available": True,
        },
    },
    "malformed_gate": "not-a-dict",
}
RECOVERY_STAGES = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "finalize",
    "execute",
    "review",
    "feedback",
)


def _state(
    current_state: str,
    robustness: str,
    flags: dict[str, bool],
    verdict: str,
) -> dict[str, Any]:
    return {
        "current_state": current_state,
        "config": {
            "robustness": robustness,
            "with_prep": flags["with_prep"],
            "with_feedback": flags["with_feedback"],
        },
        "last_gate": VERDICTS[verdict],
    }


def record() -> dict[str, Any]:
    states = sorted(CANONICAL_PLAN_STATES)
    verdicts = tuple(VERDICTS)
    cases: list[dict[str, Any]] = []
    for robustness in ROBUSTNESS_LEVELS:
        for flags in MODE_FLAGS:
            for state in states:
                for verdict in verdicts:
                    case_state = _state(state, robustness, flags, verdict)
                    workflow = _workflow_for_robustness(
                        robustness,
                        creative=False,
                        with_prep=flags["with_prep"],
                        with_feedback=flags["with_feedback"],
                    )
                    next_steps = [
                        transition.next_step
                        for transition in workflow.get(state, [])
                        if _transition_matches(case_state, transition.condition)
                    ]
                    if state in _STEP_CONTEXT_STATES:
                        next_steps.append("step")
                    cases.append(
                        {
                            "robustness": robustness,
                            "with_prep": flags["with_prep"],
                            "with_feedback": flags["with_feedback"],
                            "state": state,
                            "verdict": verdict,
                            "next_steps": next_steps,
                        }
                    )

    return {
        "label": LABEL,
        "source": "legacy workflow_next fold over _workflow_for_robustness",
        "dimensions": {
            "robustness": list(ROBUSTNESS_LEVELS),
            "modes": [dict(flags) for flags in MODE_FLAGS],
            "states": states,
            "verdicts": list(verdicts),
        },
        "recovery_predecessors": {
            stage: predecessors(stage, policy="recovery") for stage in RECOVERY_STAGES
        },
        "cases": cases,
    }


def main() -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = record()
    FIXTURE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE_PATH.relative_to(ROOT)} ({len(payload['cases'])} cases)")


if __name__ == "__main__":
    main()
