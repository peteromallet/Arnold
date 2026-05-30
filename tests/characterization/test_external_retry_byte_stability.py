"""M4 T18 — byte-stability test for the external-error retry refactor.

Diff the post-refactor RecoveryPolicy classification trace against the
golden recorded BEFORE the auto.py:2189-2259 binding change.
"""
from __future__ import annotations

from tests.characterization._golden_recorders.external_retry_golden import (
    GOLDEN_TRACE_DEFAULT,
    record_external_retry_trace,
)


def test_external_retry_matches_golden_default():
    trace = record_external_retry_trace(max_external_retries=1, n_transients=3)
    assert trace == GOLDEN_TRACE_DEFAULT


def test_external_retry_cap_zero_halts_immediately():
    trace = record_external_retry_trace(max_external_retries=0, n_transients=2)
    assert trace[0][0] == "halt"
    assert trace[0][1] == "external"


def test_external_retry_cap_two_yields_two_retries_then_halt():
    trace = record_external_retry_trace(max_external_retries=2, n_transients=4)
    actions = [t[0] for t in trace]
    assert actions == ["retry_transient", "retry_transient", "halt"]
