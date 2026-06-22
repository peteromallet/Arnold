"""M4 T17 — Synthetic context-exhaustion injection + golden trace recorder.

Produces a byte-stable event-stream + counter trace describing the sequence
of side-effects the auto.py context-retry loop emits when ExitKind.context_
exhausted is seen on the execute phase.

The recorder is a *simulator* of the loop's contract — not a driver of the
real auto.py — so the golden is small, hermetic, and survives the T17
refactor as long as the contract (counter bumps + emit lines + recorded
failure on cap exhaustion) is preserved verbatim.

Golden shape: a list of event dicts, in order::

    [{"event": "context_retry", "n": 1}, ...,
     {"event": "context_retry_exhausted", "n": N}]
"""
from __future__ import annotations

from typing import Iterable

from arnold_pipelines.megaplan.orchestration.recovery_policy import RecoveryPolicy


def record_context_retry_trace(
    max_context_retries: int,
    n_context_exhausts: int,
) -> list[dict]:
    """Simulate the canonical loop and return its byte-stable trace.

    Mirrors the side-effect sequence at megaplan/auto.py:2131-2173: each
    iteration that observes ``ExitKind.context_exhausted`` either bumps
    ``context_retry_count`` and retries (one ``context_retry`` event), or
    records the cap-exhausted failure and stops (one
    ``context_retry_exhausted`` event).
    """
    policy = RecoveryPolicy(max_context_retries=max_context_retries)
    counter = 0
    trace: list[dict] = []

    # Synthetic context-exhaustion injection: a stub PhaseResult-like object.
    class _Stub:
        exit_kind = "context_exhausted"
        message = ""

    for _ in range(n_context_exhausts):
        decision = policy.classify(
            _Stub(), layer="phase", context_retries_used=counter, phase="execute"
        )
        if decision.action == "retry_fresh":
            counter += decision.budget_delta
            trace.append({"event": "context_retry", "n": counter})
        elif decision.action == "halt":
            trace.append({"event": "context_retry_exhausted", "n": counter})
            break
    return trace


# The canonical recorded golden — frozen byte-stable trace used by the
# post-refactor characterization test.
GOLDEN_TRACE_DEFAULT: list[dict] = [
    {"event": "context_retry", "n": 1},
    {"event": "context_retry", "n": 2},
    {"event": "context_retry_exhausted", "n": 2},
]
