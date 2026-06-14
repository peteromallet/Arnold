"""Neutral control carriers shared across Arnold control-plane integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from arnold.runtime.outcome import RunOutcome


@dataclass(frozen=True)
class ControlTarget:
    """Neutral control target carrier distinct from Megaplan's control-message target type."""

    id: str
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    kind: str = "workflow_step"


ControlTargetRef = ControlTarget
ControlInterfaceTarget = ControlTarget

CONTROL_TARGET_FORCE_ADVANCE = "force-advance"
CONTROL_TARGET_REROUTE = "re-route"
CONTROL_TARGET_RECOVER_FROM_STUCK = "recover-from-stuck"
CONTROL_TARGET_ABORT = "abort"


@dataclass(frozen=True)
class ControlProjection:
    """Projected forward/recovery targets plus non-actionable diagnostics."""

    valid_targets: tuple[ControlTarget, ...] = ()
    recover_targets: tuple[ControlTarget, ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    recovery: bool = False

    @property
    def targets(self) -> tuple[ControlTarget, ...]:
        return self.recover_targets if self.recovery else self.valid_targets

    def __iter__(self):
        return iter(self.targets)

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int) -> ControlTarget:
        return self.targets[index]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tuple):
            return self.targets == other
        return super().__eq__(other)


@dataclass(frozen=True)
class RunStateView:
    """Minimal SDK view of a run state."""

    run_id: str
    outcome: RunOutcome | None = None
    cursor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw_state: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlTransition:
    """Requested out-of-band control operation."""

    op: str
    target_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ControlTransitionRequest:
    """Caller-facing request for an out-of-band control operation."""

    action: str
    target_id: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    actor: str | None = None
    source: str | None = None
    reason: str | None = None
    note: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    expected_versions: Mapping[str, int] = field(default_factory=dict)
    idempotency_key: str | None = None

    @property
    def op(self) -> str:
        return self.action

    @property
    def payload(self) -> Mapping[str, Any]:
        payload = {**dict(self.metadata), **dict(self.params)}
        for key in ("actor", "source", "reason", "note"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class ArtifactRequest:
    """Caller-facing artifact synthesis request."""

    artifact_type: str
    transition: ControlTransition | ControlTransitionRequest
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlTransitionResult:
    """Result of applying a control transition through a binding."""

    accepted: bool
    mutated: bool = False
    reason: str | None = None
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    state_deltas: Sequence[Any] = field(default_factory=tuple)
    events: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


class ControlBinding(Protocol):
    """Binding contract implemented by each run type."""

    def valid_targets(self, run_state: RunStateView) -> Sequence[ControlTarget]:
        """Return forward control targets for ``run_state``."""

    def recover_targets(self, run_state: RunStateView) -> Sequence[ControlTarget]:
        """Return reverse recovery targets for ``run_state``."""

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition | ControlTransitionRequest,
    ) -> ControlTransitionResult:
        """Apply a requested transition."""

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransition | ControlTransitionRequest,
    ) -> Mapping[str, Any]:
        """Create binding-owned artifacts for a transition."""


@dataclass(frozen=True)
class ControlTransitionConflict:
    """Observed stale-version conflict while applying a control transition."""

    key: str
    expected: int
    actual: int


__all__ = [
    "ControlBinding",
    "CONTROL_TARGET_ABORT",
    "CONTROL_TARGET_FORCE_ADVANCE",
    "CONTROL_TARGET_RECOVER_FROM_STUCK",
    "CONTROL_TARGET_REROUTE",
    "ArtifactRequest",
    "ControlProjection",
    "ControlInterfaceTarget",
    "ControlTarget",
    "ControlTargetRef",
    "ControlTransition",
    "ControlTransitionConflict",
    "ControlTransitionRequest",
    "ControlTransitionResult",
    "RunOutcome",
    "RunStateView",
]
