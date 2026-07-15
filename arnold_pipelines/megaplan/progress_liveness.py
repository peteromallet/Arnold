"""Typed progress/liveness policy for long-lived model streams.

The policy deliberately separates transport activity from productive activity.
A warm socket or a periodic heartbeat is useful evidence that the provider is
reachable, but it cannot keep an attempt alive forever when no visible output,
reasoning delta, or tool transition is observable.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Mapping


class ProgressAction(str, Enum):
    CONTINUE = "continue"
    SUSPECT = "suspect"
    FALLBACK = "fallback"


class ProgressReason(str, Enum):
    POLICY_DISABLED = "policy_disabled"
    INITIAL_GRACE = "initial_grace"
    VISIBLE_PROGRESS = "visible_progress"
    REASONING_PROGRESS = "reasoning_progress"
    TOOL_ACTIVITY = "tool_activity"
    PROVIDER_HEARTBEAT_ONLY = "provider_heartbeat_only"
    SLOW_VISIBLE_OUTPUT = "slow_visible_output"
    REASONING_GRACE_EXHAUSTED = "reasoning_grace_exhausted"
    NO_OBSERVABLE_ACTIVITY = "no_observable_activity"
    TOOL_ACTIVITY_TIMEOUT = "tool_activity_timeout"
    STREAMING_TIMEOUT = "streaming_timeout"


@dataclass(frozen=True, slots=True)
class ProviderProgressCapabilities:
    visible_output: bool = True
    reasoning: bool = False
    tool_activity: bool = False
    provider_events: bool = False


@dataclass(frozen=True, slots=True)
class SlowOutputPolicy:
    """Conservative, validated bounds for progress-based fallback.

    Defaults apply only to execute-shaped phases. Callers may disable the
    policy explicitly, but invalid values fail closed during dispatch.
    """

    enabled: bool = True
    initial_grace_s: float = 180.0
    observation_window_s: float = 300.0
    silence_timeout_s: float = 180.0
    min_visible_chars_per_s: float = 0.05
    reasoning_grace_s: float = 600.0
    tool_grace_s: float = 900.0
    heartbeat_grace_s: float = 60.0
    escalation_grace_s: float = 30.0
    surface_streaming_timeouts: bool = True

    @classmethod
    def from_config(
        cls,
        raw: object,
        *,
        phase: str,
    ) -> "SlowOutputPolicy":
        if raw is None:
            return cls(enabled=phase in {"execute", "loop_execute"})
        if not isinstance(raw, Mapping):
            raise TypeError("slow_output_policy must be a mapping")

        merged: dict[str, Any] = {
            key: value for key, value in raw.items() if key != "phases"
        }
        phases = raw.get("phases")
        if phases is not None:
            if not isinstance(phases, Mapping):
                raise TypeError("slow_output_policy.phases must be a mapping")
            phase_raw = phases.get(phase)
            if phase_raw is not None:
                if not isinstance(phase_raw, Mapping):
                    raise TypeError(
                        f"slow_output_policy.phases.{phase} must be a mapping"
                    )
                merged.update(phase_raw)

        valid = {field.name for field in fields(cls)}
        unknown = sorted(set(merged) - valid)
        if unknown:
            raise ValueError(
                "slow_output_policy contains unknown keys: " + ", ".join(unknown)
            )

        defaults = cls(enabled=phase in {"execute", "loop_execute"})
        values = {field.name: getattr(defaults, field.name) for field in fields(cls)}
        values.update(merged)
        for name in ("enabled", "surface_streaming_timeouts"):
            if not isinstance(values[name], bool):
                raise TypeError(f"slow_output_policy.{name} must be a boolean")
        for name in valid - {"enabled", "surface_streaming_timeouts"}:
            value = values[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"slow_output_policy.{name} must be a number")
            if float(value) < 0:
                raise ValueError(f"slow_output_policy.{name} must be non-negative")
            values[name] = float(value)
        if values["silence_timeout_s"] == 0:
            raise ValueError("slow_output_policy.silence_timeout_s must be positive")
        if values["observation_window_s"] == 0:
            raise ValueError("slow_output_policy.observation_window_s must be positive")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ProgressSample:
    now: float
    visible_chars: int = 0
    reasoning_chars: int = 0
    last_visible_at: float | None = None
    last_reasoning_at: float | None = None
    tool_active: bool = False
    tool_active_since: float | None = None
    tool_result_count: int = 0
    provider_event_count: int = 0
    last_provider_event_at: float | None = None


@dataclass(frozen=True, slots=True)
class ProgressDecision:
    action: ProgressAction
    reason: ProgressReason
    elapsed_s: float
    silence_s: float
    visible_rate_chars_per_s: float
    suspect_for_s: float = 0.0


class ProgressLivenessMonitor:
    """Stateful staged escalation with hysteresis.

    A concerning observation first enters ``suspect``. It must remain the same
    concern for ``escalation_grace_s`` before fallback is requested. Any real
    content/reasoning/tool transition clears the suspect state.
    """

    def __init__(
        self,
        policy: SlowOutputPolicy,
        capabilities: ProviderProgressCapabilities,
        *,
        started_at: float,
    ) -> None:
        self.policy = policy
        self.capabilities = capabilities
        self.started_at = started_at
        self._suspect_reason: ProgressReason | None = None
        self._suspect_since: float | None = None
        self._last_visible_chars = 0
        self._last_reasoning_chars = 0
        self._last_tool_results = 0

    def streaming_timeout(self, *, now: float) -> ProgressDecision:
        if not self.policy.enabled or not self.policy.surface_streaming_timeouts:
            return self._continue(ProgressReason.POLICY_DISABLED, now, 0.0, 0.0)
        return ProgressDecision(
            ProgressAction.FALLBACK,
            ProgressReason.STREAMING_TIMEOUT,
            max(0.0, now - self.started_at),
            max(0.0, now - self.started_at),
            0.0,
            self.policy.escalation_grace_s,
        )

    def observe(self, sample: ProgressSample) -> ProgressDecision:
        now = sample.now
        elapsed = max(0.0, now - self.started_at)
        visible_rate = sample.visible_chars / max(elapsed, 1.0)
        self._last_visible_chars = max(self._last_visible_chars, sample.visible_chars)
        self._last_reasoning_chars = max(
            self._last_reasoning_chars, sample.reasoning_chars
        )
        self._last_tool_results = max(self._last_tool_results, sample.tool_result_count)

        last_productive_at = max(
            value
            for value in (
                self.started_at,
                sample.last_visible_at,
                sample.last_reasoning_at,
            )
            if value is not None
        )
        silence = max(0.0, now - last_productive_at)

        if not self.policy.enabled:
            return self._continue(
                ProgressReason.POLICY_DISABLED, now, silence, visible_rate
            )

        if sample.tool_active and self.capabilities.tool_activity:
            tool_since = sample.tool_active_since or now
            if now - tool_since <= self.policy.tool_grace_s:
                return self._continue(
                    ProgressReason.TOOL_ACTIVITY, now, silence, visible_rate
                )
            return self._escalate(
                ProgressReason.TOOL_ACTIVITY_TIMEOUT,
                now=now,
                silence_s=silence,
                visible_rate=visible_rate,
            )

        if elapsed < self.policy.initial_grace_s:
            return self._continue(
                ProgressReason.INITIAL_GRACE, now, silence, visible_rate
            )

        if sample.visible_chars > 0:
            if silence > self.policy.silence_timeout_s:
                return self._escalate(
                    ProgressReason.NO_OBSERVABLE_ACTIVITY,
                    now=now,
                    silence_s=silence,
                    visible_rate=visible_rate,
                )
            if (
                elapsed >= self.policy.observation_window_s
                and visible_rate < self.policy.min_visible_chars_per_s
            ):
                return self._escalate(
                    ProgressReason.SLOW_VISIBLE_OUTPUT,
                    now=now,
                    silence_s=silence,
                    visible_rate=visible_rate,
                )
            return self._continue(
                ProgressReason.VISIBLE_PROGRESS, now, silence, visible_rate
            )

        if sample.reasoning_chars > 0 and self.capabilities.reasoning:
            if elapsed <= self.policy.reasoning_grace_s and silence <= self.policy.silence_timeout_s:
                return self._continue(
                    ProgressReason.REASONING_PROGRESS, now, silence, visible_rate
                )
            return self._escalate(
                ProgressReason.REASONING_GRACE_EXHAUSTED,
                now=now,
                silence_s=silence,
                visible_rate=visible_rate,
            )

        if (
            sample.provider_event_count > 0
            and self.capabilities.provider_events
            and sample.last_provider_event_at is not None
            and elapsed <= self.policy.initial_grace_s + self.policy.heartbeat_grace_s
        ):
            return self._continue(
                ProgressReason.PROVIDER_HEARTBEAT_ONLY, now, silence, visible_rate
            )

        return self._escalate(
            ProgressReason.NO_OBSERVABLE_ACTIVITY,
            now=now,
            silence_s=silence,
            visible_rate=visible_rate,
        )

    def _continue(
        self,
        reason: ProgressReason,
        now: float,
        silence_s: float,
        visible_rate: float,
    ) -> ProgressDecision:
        if reason not in {
            ProgressReason.PROVIDER_HEARTBEAT_ONLY,
            ProgressReason.INITIAL_GRACE,
        }:
            self._clear_suspect()
        return ProgressDecision(
            ProgressAction.CONTINUE,
            reason,
            max(0.0, now - self.started_at),
            silence_s,
            visible_rate,
        )

    def _escalate(
        self,
        reason: ProgressReason,
        *,
        now: float,
        silence_s: float,
        visible_rate: float,
    ) -> ProgressDecision:
        if self._suspect_reason != reason or self._suspect_since is None:
            self._suspect_reason = reason
            self._suspect_since = now
        suspect_for = max(0.0, now - self._suspect_since)
        action = (
            ProgressAction.FALLBACK
            if suspect_for >= self.policy.escalation_grace_s
            else ProgressAction.SUSPECT
        )
        return ProgressDecision(
            action,
            reason,
            max(0.0, now - self.started_at),
            silence_s,
            visible_rate,
            suspect_for,
        )

    def _clear_suspect(self) -> None:
        self._suspect_reason = None
        self._suspect_since = None


__all__ = [
    "ProgressAction",
    "ProgressDecision",
    "ProgressLivenessMonitor",
    "ProgressReason",
    "ProgressSample",
    "ProviderProgressCapabilities",
    "SlowOutputPolicy",
]
