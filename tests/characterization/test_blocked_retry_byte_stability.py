"""M4 T19 — byte-stability characterization of the blocked-task retry loop."""
from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind
from tests.characterization._golden_recorders.blocked_retry_golden import (
    GOLDEN_TRACE_DEFAULT,
    record_blocked_retry_trace,
)


def test_blocked_retry_matches_golden_default():
    assert record_blocked_retry_trace(max_blocked_retries=1, n_blocks=3) == GOLDEN_TRACE_DEFAULT


def test_blocked_retry_zero_cap_halts_immediately():
    trace = record_blocked_retry_trace(max_blocked_retries=0, n_blocks=2)
    assert trace == [("halt", "blocked", 0)]


def test_blocked_retry_cap_two_retries_twice_then_halt():
    trace = record_blocked_retry_trace(max_blocked_retries=2, n_blocks=4)
    assert trace == [
        ("retry_fresh", "blocked", 0),
        ("retry_fresh", "blocked", 1),
        ("halt", "blocked", 2),
    ]


@pytest.mark.parametrize("kind", [ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq])
def test_blocked_retry_handles_both_blocked_exit_kinds(kind):
    trace = record_blocked_retry_trace(max_blocked_retries=1, n_blocks=2, kind=kind)
    assert trace[0][0] == "retry_fresh"
    assert trace[-1][0] == "halt"
