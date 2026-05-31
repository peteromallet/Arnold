"""Domain-neutral control interface for run outcomes and control operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from importlib import import_module
from typing import Any, Mapping, Protocol, Sequence

from megaplan._core.state import write_plan_state
from megaplan._pipeline.types import StateDelta, StateDeltaConflict, apply_delta
from megaplan.run_outcome import RunOutcome


@dataclass(frozen=True)
class ControlTarget:
    """A target the current run state can transition toward or recover through."""

    id: str
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    kind: str = "workflow_step"


ControlTargetRef = ControlTarget
ControlInterfaceTarget = ControlTarget


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
    """Minimal SDK view of a run state.

    Bindings own the shape and meaning of ``raw_state``. The shared interface
    only carries neutral outcome/projection metadata across the boundary.
    """

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
    state_deltas: Sequence[StateDelta] = field(default_factory=tuple)
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


def _event_payload(
    kind: str,
    *,
    run_state: RunStateView,
    transition: ControlTransition | ControlTransitionRequest,
    mutated: bool,
    target_state: Mapping[str, Any] | None = None,
    conflict: ControlTransitionConflict | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "run_id": run_state.run_id,
        "op": transition.op,
        "target_id": transition.target_id,
        "idempotency_key": transition.idempotency_key,
        "mutated": mutated,
    }
    if target_state is not None:
        payload["state_version"] = target_state.get("_state_meta", {}).get("versions", {})
        payload["outcome"] = run_state.outcome.value if run_state.outcome is not None else None
        payload["cursor"] = run_state.cursor
    if conflict is not None:
        payload["conflict"] = {
            "key": conflict.key,
            "expected": conflict.expected,
            "actual": conflict.actual,
        }
    return payload


def _extract_state_deltas(result: ControlTransitionResult) -> tuple[StateDelta, ...]:
    if result.state_deltas:
        return tuple(result.state_deltas)
    raw = result.artifacts.get("state_deltas")
    if raw is None:
        raw = result.artifacts.get("deltas")
    if raw is None:
        return ()
    if isinstance(raw, StateDelta):
        return (raw,)
    return tuple(delta for delta in raw if isinstance(delta, StateDelta))


def _projection_from_targets(
    targets: Sequence[ControlTarget],
    *,
    recovery: bool,
) -> ControlProjection:
    actionable: list[ControlTarget] = []
    diagnostics: list[Mapping[str, Any]] = []
    for target in targets:
        if target.metadata.get("kind") == "diagnostic":
            diagnostics.append(dict(target.metadata))
        else:
            actionable.append(target)
    if recovery:
        return ControlProjection(
            recover_targets=tuple(actionable),
            diagnostics=tuple(diagnostics),
            recovery=True,
        )
    return ControlProjection(
        valid_targets=tuple(actionable),
        diagnostics=tuple(diagnostics),
        recovery=False,
    )


def _resolve_binding_and_state(
    run_state: RunStateView | Mapping[str, Any],
    binding: ControlBinding | str,
) -> tuple[RunStateView, ControlBinding]:
    if isinstance(binding, str):
        if binding != "planning":
            raise ValueError(f"unknown control binding: {binding!r}")
        planning = import_module("megaplan." + "planning")

        resolved_state = (
            run_state
            if isinstance(run_state, RunStateView)
            else planning.planning_run_state_view(run_state)
        )
        return resolved_state, planning.planning_control_binding()
    if not isinstance(run_state, RunStateView):
        planning = import_module("megaplan." + "planning")

        run_state = planning.planning_run_state_view(run_state)
    return run_state, binding


def read_valid_targets(
    run_state: RunStateView | Mapping[str, Any],
    binding: ControlBinding | str = "planning",
    *,
    recovery: bool = False,
) -> ControlProjection:
    """Read binding-projected targets for ``run_state``."""

    run_state, binding = _resolve_binding_and_state(run_state, binding)
    targets = binding.recover_targets(run_state) if recovery else binding.valid_targets(run_state)
    return _projection_from_targets(tuple(targets), recovery=recovery)


def synthesize_artifacts(
    run_state: RunStateView | Mapping[str, Any],
    transition: ControlTransition | ControlTransitionRequest,
    binding: ControlBinding | str,
) -> Mapping[str, Any]:
    """Delegate artifact synthesis to the binding."""

    run_state, binding = _resolve_binding_and_state(run_state, binding)
    return binding.synthesize_artifacts(run_state, transition)


def apply_transition(
    run_state: RunStateView | Mapping[str, Any],
    transition: ControlTransition | ControlTransitionRequest,
    binding: ControlBinding | str | None = None,
    *,
    plan_dir: str | Path | None = None,
) -> ControlTransitionResult:
    """Apply a transition through a binding and optional CAS-backed state write."""

    if binding is None:
        return ControlTransitionResult(
            accepted=False,
            mutated=False,
            reason="control_interface_transition_stub",
        )
    run_state, binding = _resolve_binding_and_state(run_state, binding)
    if plan_dir is None:
        return binding.apply_transition(run_state, transition)

    binding_result = binding.apply_transition(run_state, transition)
    if not binding_result.accepted:
        return binding_result

    deltas = _extract_state_deltas(binding_result)
    if not deltas:
        events = tuple(binding_result.events) + (
            _event_payload(
                "STATE_TRANSITION",
                run_state=run_state,
                transition=transition,
                mutated=False,
            ),
        )
        return ControlTransitionResult(
            accepted=True,
            mutated=False,
            reason=binding_result.reason,
            artifacts=binding_result.artifacts,
            state_deltas=binding_result.state_deltas,
            events=events,
        )

    applied_state: dict[str, Any] | None = None

    def _apply_control_deltas(current: dict[str, Any]) -> bool:
        nonlocal applied_state
        expected_versions = getattr(transition, "expected_versions", {}) or {}
        versions = current.get("_state_meta", {}).get("versions", {})
        if not isinstance(versions, Mapping):
            versions = {}
        for key, expected in expected_versions.items():
            actual = versions.get(key, 0)
            actual = actual if isinstance(actual, int) else 0
            if actual != expected:
                raise StateDeltaConflict(key, expected, actual)
        next_state = dict(current)
        for delta in deltas:
            next_state, _ = apply_delta(next_state, delta)
        remove_keys = binding_result.artifacts.get("remove_state_keys", ())
        if isinstance(remove_keys, Sequence) and not isinstance(remove_keys, (str, bytes)):
            for key in remove_keys:
                if isinstance(key, str):
                    next_state.pop(key, None)
        current.clear()
        current.update(next_state)
        applied_state = next_state
        return True

    try:
        persisted = write_plan_state(
            Path(plan_dir),
            mode="patch-many",
            patch={},
            mutation=_apply_control_deltas,
        )
    except StateDeltaConflict as exc:
        conflict = ControlTransitionConflict(
            key=exc.key,
            expected=exc.expected,
            actual=exc.actual,
        )
        return ControlTransitionResult(
            accepted=False,
            mutated=False,
            reason="control_transition_conflict",
            artifacts={
                **dict(binding_result.artifacts),
                "conflict": {
                    "key": conflict.key,
                    "expected": conflict.expected,
                    "actual": conflict.actual,
                },
            },
            state_deltas=binding_result.state_deltas,
            events=tuple(binding_result.events)
            + (
                _event_payload(
                    "STATE_TRANSITION",
                    run_state=run_state,
                    transition=transition,
                    mutated=False,
                    conflict=conflict,
                ),
            ),
        )

    next_state = applied_state if applied_state is not None else persisted
    events = tuple(binding_result.events) + (
        _event_payload(
            "OVERRIDE_APPLIED",
            run_state=run_state,
            transition=transition,
            mutated=True,
            target_state=next_state,
        ),
        _event_payload(
            "STATE_TRANSITION",
            run_state=run_state,
            transition=transition,
            mutated=True,
            target_state=next_state,
        ),
    )
    return ControlTransitionResult(
        accepted=True,
        mutated=True,
        reason=binding_result.reason,
        artifacts=binding_result.artifacts,
        state_deltas=binding_result.state_deltas,
        events=events,
    )


__all__ = [
    "ControlBinding",
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
    "apply_transition",
    "read_valid_targets",
    "synthesize_artifacts",
]
