"""Tests for watchdog retry-loop state machine."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.watchdog.retry import (
    RetryCapExceeded,
    RetryLoop,
    RetryOutcome,
)


def test_retry_loop_caps_at_three_attempts():
    loop = RetryLoop()
    result, done = loop.attempt(RetryOutcome.UNRESOLVED)
    assert result is RetryOutcome.UNRESOLVED and done is False
    result, done = loop.attempt(RetryOutcome.UNRESOLVED)
    assert result is RetryOutcome.UNRESOLVED and done is False
    result, done = loop.attempt(RetryOutcome.UNRESOLVED)
    assert result is RetryOutcome.UNRESOLVED and done is True
    assert loop.attempt_count == 3
    with pytest.raises(RetryCapExceeded):
        loop.attempt(RetryOutcome.UNRESOLVED)


def test_success_before_cap():
    loop = RetryLoop()
    result, done = loop.attempt(RetryOutcome.UNRESOLVED)
    assert done is False
    result, done = loop.attempt(RetryOutcome.RESOLVED)
    assert result is RetryOutcome.RESOLVED and done is True
    assert loop.attempt_count == 2


def test_terminal_mid_loop():
    loop = RetryLoop()
    result, done = loop.attempt(RetryOutcome.TERMINAL)
    assert result is RetryOutcome.TERMINAL and done is True
    assert loop.attempt_count == 1
