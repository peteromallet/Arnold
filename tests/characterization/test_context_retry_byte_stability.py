"""M4 T17 — Byte-stability characterization for the context-retry loop.

Diffs the post-refactor trace emitted by the canonical recorder against
the frozen golden recorded as a separate prep commit.  If the refactor
of ``megaplan/auto.py:2131-2173`` changed the side-effect sequence
(counter bumps, event ordering, halt-vs-retry decisions) this test
fails with a byte-level diff.
"""
from __future__ import annotations

from tests.characterization._golden_recorders.context_retry_golden import (
    GOLDEN_TRACE_DEFAULT,
    record_context_retry_trace,
)


def test_context_retry_trace_matches_golden_default():
    trace = record_context_retry_trace(max_context_retries=2, n_context_exhausts=5)
    assert trace == GOLDEN_TRACE_DEFAULT


def test_context_retry_trace_no_retry_when_cap_zero():
    trace = record_context_retry_trace(max_context_retries=0, n_context_exhausts=3)
    # cap=0: immediate halt without any retry.
    assert trace == [{"event": "context_retry_exhausted", "n": 0}]


def test_context_retry_trace_one_retry_then_halt():
    trace = record_context_retry_trace(max_context_retries=1, n_context_exhausts=3)
    assert trace == [
        {"event": "context_retry", "n": 1},
        {"event": "context_retry_exhausted", "n": 1},
    ]
