from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.progress_liveness import (
    ProgressAction,
    ProgressLivenessMonitor,
    ProgressReason,
    ProgressSample,
    ProviderProgressCapabilities,
    SlowOutputPolicy,
)
from arnold_pipelines.megaplan.workers.hermes import _StreamTracker, _WorkerStallWatchdog


CAPABILITIES = ProviderProgressCapabilities(
    visible_output=True,
    reasoning=True,
    tool_activity=True,
    provider_events=True,
)


def _policy(**overrides) -> SlowOutputPolicy:
    values = {
        "enabled": True,
        "initial_grace_s": 10.0,
        "observation_window_s": 20.0,
        "silence_timeout_s": 10.0,
        "min_visible_chars_per_s": 1.0,
        "reasoning_grace_s": 30.0,
        "tool_grace_s": 40.0,
        "heartbeat_grace_s": 5.0,
        "escalation_grace_s": 3.0,
        "surface_streaming_timeouts": True,
    }
    values.update(overrides)
    return SlowOutputPolicy(**values)


def test_slow_visible_output_uses_staged_escalation_and_reason_code() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    suspect = monitor.observe(
        ProgressSample(now=20.0, visible_chars=5, last_visible_at=20.0)
    )
    fallback = monitor.observe(
        ProgressSample(now=23.1, visible_chars=6, last_visible_at=23.1)
    )
    assert suspect.action is ProgressAction.SUSPECT
    assert fallback.action is ProgressAction.FALLBACK
    assert fallback.reason is ProgressReason.SLOW_VISIBLE_OUTPUT


def test_reasoning_is_progress_only_for_a_bounded_grace() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    healthy = monitor.observe(
        ProgressSample(now=25.0, reasoning_chars=400, last_reasoning_at=25.0)
    )
    suspect = monitor.observe(
        ProgressSample(now=31.0, reasoning_chars=500, last_reasoning_at=31.0)
    )
    fallback = monitor.observe(
        ProgressSample(now=34.1, reasoning_chars=600, last_reasoning_at=34.1)
    )
    assert healthy.reason is ProgressReason.REASONING_PROGRESS
    assert suspect.reason is ProgressReason.REASONING_GRACE_EXHAUSTED
    assert fallback.action is ProgressAction.FALLBACK


def test_provider_heartbeat_cannot_prove_progress_forever() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    bounded = monitor.observe(
        ProgressSample(
            now=12.0,
            provider_event_count=4,
            last_provider_event_at=12.0,
        )
    )
    suspect = monitor.observe(
        ProgressSample(
            now=16.0,
            provider_event_count=8,
            last_provider_event_at=16.0,
        )
    )
    assert bounded.reason is ProgressReason.PROVIDER_HEARTBEAT_ONLY
    assert suspect.reason is ProgressReason.NO_OBSERVABLE_ACTIVITY


def test_no_observable_activity_advances_after_hysteresis() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    assert monitor.observe(ProgressSample(now=11.0)).action is ProgressAction.SUSPECT
    decision = monitor.observe(ProgressSample(now=14.1))
    assert decision.action is ProgressAction.FALLBACK
    assert decision.reason is ProgressReason.NO_OBSERVABLE_ACTIVITY


def test_tool_activity_is_protected_but_not_unbounded() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    active = monitor.observe(
        ProgressSample(now=35.0, tool_active=True, tool_active_since=5.0)
    )
    suspect = monitor.observe(
        ProgressSample(now=46.0, tool_active=True, tool_active_since=5.0)
    )
    fallback = monitor.observe(
        ProgressSample(now=49.1, tool_active=True, tool_active_since=5.0)
    )
    assert active.reason is ProgressReason.TOOL_ACTIVITY
    assert suspect.reason is ProgressReason.TOOL_ACTIVITY_TIMEOUT
    assert fallback.action is ProgressAction.FALLBACK


def test_good_visible_rate_and_sparse_thinking_resist_false_positive() -> None:
    monitor = ProgressLivenessMonitor(_policy(), CAPABILITIES, started_at=0.0)
    visible = monitor.observe(
        ProgressSample(now=20.0, visible_chars=40, last_visible_at=20.0)
    )
    reasoning = monitor.observe(
        ProgressSample(
            now=25.0,
            visible_chars=40,
            reasoning_chars=1,
            last_visible_at=20.0,
            last_reasoning_at=25.0,
        )
    )
    assert visible.action is ProgressAction.CONTINUE
    assert reasoning.action is ProgressAction.CONTINUE


def test_disabled_policy_never_requests_fallback() -> None:
    monitor = ProgressLivenessMonitor(
        _policy(enabled=False), CAPABILITIES, started_at=0.0
    )
    decision = monitor.observe(ProgressSample(now=10_000.0))
    assert decision.action is ProgressAction.CONTINUE
    assert decision.reason is ProgressReason.POLICY_DISABLED


def test_streaming_timeout_surfaces_immediately_through_watchdog() -> None:
    class Agent:
        _executing_tools = False

        def __init__(self) -> None:
            self.interrupt_reason = None

        def interrupt(self, reason: str) -> None:
            self.interrupt_reason = reason

    agent = Agent()
    watchdog = _WorkerStallWatchdog(agent, _StreamTracker(), 600.0, _policy())
    watchdog.record_streaming_timeout()
    assert watchdog.tripped is True
    assert watchdog.reason_code == ProgressReason.STREAMING_TIMEOUT.value
    assert "streaming_timeout" in agent.interrupt_reason
    assert watchdog.tool_activity_observed is False
    watchdog.record_tool_activity()
    assert watchdog.tool_activity_observed is True


def test_policy_validation_fails_closed_and_supports_phase_override() -> None:
    policy = SlowOutputPolicy.from_config(
        {
            "enabled": False,
            "phases": {"execute": {"enabled": True, "silence_timeout_s": 99}},
        },
        phase="execute",
    )
    assert policy.enabled is True
    assert policy.silence_timeout_s == 99

    with pytest.raises(ValueError, match="unknown keys"):
        SlowOutputPolicy.from_config({"mystery": 1}, phase="execute")
    with pytest.raises(ValueError, match="non-negative"):
        SlowOutputPolicy.from_config({"reasoning_grace_s": -1}, phase="execute")
    with pytest.raises(TypeError, match="must be a number"):
        SlowOutputPolicy.from_config({"tool_grace_s": "forever"}, phase="execute")
    with pytest.raises(ValueError, match="must be positive"):
        SlowOutputPolicy.from_config({"silence_timeout_s": 0}, phase="execute")
