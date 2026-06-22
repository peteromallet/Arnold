"""M4 T18 — pre-refactor golden for the external-error retry loop.

Synthetic external-error injection: at each iteration we feed a stub
PhaseResult to RecoveryPolicy.classify and record (action, budget_kind,
retries_used) until classify halts. The trace is byte-stable across
the refactor at auto.py:2189-2259 because the classify call is the
exact extracted shape of the legacy gate condition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind
from arnold_pipelines.megaplan.orchestration.recovery_policy import RecoveryPolicy


class _StubResult:
    """Result-shaped stub that carries external-error attributes directly,
    matching the shape RecoveryPolicy._is_retryable_external_error reads."""

    def __init__(self):
        self.exit_kind = ExitKind.external_error
        self.error_kind = "stream_content_stall"
        self.error_layer = "stream_content_stall"
        self.message = "stream stalled"
        self.status_code = None
        self.retry_after_s = None
        self.provider_error_code = ""
        self.provider = "fake"


def record_external_retry_trace(
    max_external_retries: int,
    n_transients: int,
    phase: str = "critique",
) -> list[tuple[str, str, int]]:
    """Drive the classifier under repeated transient external errors."""
    policy = RecoveryPolicy(max_external_retries=max_external_retries)
    result = _StubResult()
    trace: list[tuple[str, str, int]] = []
    used = 0
    for _ in range(n_transients):
        dec = policy.classify(
            result,
            layer="phase",
            external_retries_used=used,
            phase=phase,
        )
        trace.append((dec.action, dec.budget_kind or "", used))
        if dec.action != "retry_transient":
            break
        used += dec.budget_delta
    return trace


# Default golden trace: cap=1, three transient injections.
# Iteration 0: under cap → retry_transient (used=0)
# Iteration 1: cap reached → halt external_retry_exhausted (used=1)
GOLDEN_TRACE_DEFAULT: list[tuple[str, str, int]] = [
    ("retry_transient", "external", 0),
    ("halt", "external", 1),
]
