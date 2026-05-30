"""M4 T19 — pre-refactor golden for the blocked-task retry loop.

Synthetic blocked-by-quality / blocked-by-prereq injection. At each
iteration we feed a stub PhaseResult to RecoveryPolicy.classify with
blocked_retries_used and record (action, budget_kind, retries_used)
until classify halts.

The trace is byte-stable across the refactor at auto.py:2470-2570
because the classify call captures the same gate condition the legacy
loop uses (blocked_retry_count vs max_blocked_retries).

Recorded list of failure kind= values flowing through _record_failure
inside the blocked-retry region (auto.py grep'd for kind= in lines
2275..2750):
  - external_error (2312)
  - phase_failed (2372, 2387)
  - phase_callback_failed (2413)
  - execution_blocked (2498, 2552)
  - iteration_cap (2748)
Plus surrounding retry kinds reachable from the wider phase loop:
  - context_retry_exhausted, phase_timeout, gate_escalated,
    tasks_blocked, stalled, status_lookup_failed, no_next_step,
    cost_cap_exceeded, override_failed, human_required,
    plus the M4 close-out residue: tier_escalated (event-only),
    state_transition (event-only).

Of these 15+, RecoveryPolicy currently classifies four kinds explicitly
(context_exhausted, external_error transient/permanent, blocked_by_*,
timeout/internal_error); the remainder are left as "unclassified" halt
and listed in the M4 close-out for policy.halt(kind) follow-up.
"""
from __future__ import annotations

from megaplan.orchestration.phase_result import ExitKind
from megaplan.orchestration.recovery_policy import RecoveryPolicy


class _StubBlockedResult:
    """Result-shaped stub for blocked-by-quality classification."""

    def __init__(self, kind: ExitKind = ExitKind.blocked_by_quality):
        self.exit_kind = kind
        # No external-error markers — _looks_external must return False so
        # the classifier reaches the blocked-by-* branch (not the external
        # branch).
        self.message = "quality gate flagged deviations"


def record_blocked_retry_trace(
    max_blocked_retries: int,
    n_blocks: int,
    kind: ExitKind = ExitKind.blocked_by_quality,
    phase: str = "execute",
) -> list[tuple[str, str, int]]:
    """Drive the classifier under repeated blocked-by-quality results."""
    policy = RecoveryPolicy(max_blocked_retries=max_blocked_retries)
    result = _StubBlockedResult(kind=kind)
    trace: list[tuple[str, str, int]] = []
    used = 0
    for _ in range(n_blocks):
        dec = policy.classify(
            result,
            layer="phase",
            blocked_retries_used=used,
            phase=phase,
        )
        trace.append((dec.action, dec.budget_kind or "", used))
        if dec.action != "retry_fresh":
            break
        used += dec.budget_delta
    return trace


# Default golden (cap=1, 3 injections): retry then halt.
GOLDEN_TRACE_DEFAULT: list[tuple[str, str, int]] = [
    ("retry_fresh", "blocked", 0),
    ("halt", "blocked", 1),
]
