"""StepwiseDriver Protocol and isolation-mode contract.

This module defines the step-level execution protocol that M2b drivers
will implement.  The surface is deliberately minimal: a
``runtime_checkable`` Protocol with three operations (``advance``,
``checkpoint``, ``resume``), a two-element isolation-mode constant
(:data:`ISOLATION_MODES`), and two frozen outcome carriers.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
:data:`ISOLATION_MODES` is a ``frozenset[str]`` rather than an enum so
that settings-validation code can do a membership test without importing
an enum type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef
from arnold.workflow.native_wbc import begin_native_wbc_attempt

__all__ = [
    "ISOLATION_MODES",
    "ADVANCE_OUTCOME_KINDS",
    "CHECKPOINT_OUTCOME_KINDS",
    "AdvanceOutcome",
    "CheckpointOutcome",
    "PipelineStepwiseDriver",
    "StepwiseDriver",
]


# ---------------------------------------------------------------------------
# Isolation-mode constant
# ---------------------------------------------------------------------------

ISOLATION_MODES: frozenset[str] = frozenset({"in_process", "subprocess_isolated"})
"""The complete set of isolation modes the runtime supports.

Exactly two members: ``"in_process"`` (same-process execution) and
``"subprocess_isolated"`` (forked subprocess with a clean environment).
Settings validation rejects any value outside this set.
"""


# ---------------------------------------------------------------------------
# Outcome kind constants
# ---------------------------------------------------------------------------

ADVANCE_OUTCOME_KINDS: frozenset[str] = frozenset(
    {"advanced", "halted", "awaiting", "failed"}
)
"""Prescribed ``kind`` literal set for :class:`AdvanceOutcome`.

``"advanced"``  — step executed and moved execution forward.
``"halted"``    — pipeline has reached a terminal state.
``"awaiting"``  — step is blocked pending an external signal.
``"failed"``    — step execution failed; ``errors`` carries detail.
"""

CHECKPOINT_OUTCOME_KINDS: frozenset[str] = frozenset(
    {"advanced", "halted", "awaiting", "failed"}
)
"""Prescribed ``kind`` literal set for :class:`CheckpointOutcome`.

Same four members as :data:`ADVANCE_OUTCOME_KINDS`; the shared set keeps
consumer code uniform across outcome types.
"""


# ---------------------------------------------------------------------------
# Outcome carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdvanceOutcome:
    """Result of one :meth:`StepwiseDriver.advance` call.

    ``kind`` must be a member of :data:`ADVANCE_OUTCOME_KINDS`.
    ``payload`` is opaque to Arnold.  ``errors`` follows the same
    convention as :class:`~arnold.runtime.operations.OperationResult`:
    first entry is a runtime-neutral error class, rest are driver detail.
    """

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckpointOutcome:
    """Result of one :meth:`StepwiseDriver.checkpoint` call.

    ``kind`` must be a member of :data:`CHECKPOINT_OUTCOME_KINDS`.
    ``payload`` is opaque to Arnold.
    """

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# StepwiseDriver Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepwiseDriver(Protocol):
    """Protocol for Arnold step-level execution drivers.

    Drivers are responsible for the mechanics of executing one step at a
    time within a given isolation boundary.  M2b migrates
    ``megaplan/drivers/`` onto this surface.

    Attributes
    ----------
    isolation_mode:
        One of the two values in :data:`ISOLATION_MODES`:
        ``"in_process"`` or ``"subprocess_isolated"``.
    """

    isolation_mode: str

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:  # pragma: no cover
        ...

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:  # pragma: no cover
        ...

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:  # pragma: no cover
        ...


class PipelineStepwiseDriver:
    """Concrete in-process :class:`StepwiseDriver` for Arnold ``Pipeline`` graphs.

    The canonical ``run_pipeline`` executor walks an entire graph until halt or
    suspension. This driver exposes the same neutral execution semantics one
    stage at a time so callers can host an operator loop around ``advance`` /
    ``checkpoint`` / ``resume`` without reimplementing Arnold's routing,
    hook, parallel-stage, or typed step-IO behavior.
    """

    isolation_mode = "in_process"

    def __init__(
        self,
        pipeline: Any,
        *,
        initial_state: Mapping[str, Any] | None = None,
        registry: Any = None,
        hooks: Any = None,
        parallel_safe: Any = None,
        start_stage: str | None = None,
        initial_context: Any = None,
    ) -> None:
        from arnold.pipeline.executor import DEFAULT_PARALLEL_SAFE
        from arnold.execution.hooks import NullExecutorHooks
        from arnold.execution.operations import NullOperationRegistry

        self.pipeline = pipeline
        self.registry = registry if registry is not None else NullOperationRegistry()
        self.hooks = hooks if hooks is not None else NullExecutorHooks()
        self._parallel_safe = (
            self.hooks.is_parallel_safe if hooks is not None else parallel_safe
        )
        if self._parallel_safe is None:
            self._parallel_safe = DEFAULT_PARALLEL_SAFE
        self._state: Any = dict(initial_state or {})
        self._owned_keys: frozenset[str] = frozenset()
        self._current_stage: str | None = start_stage or pipeline.entry
        self._iteration = 0
        self._hook_extensions: Mapping[str, Any] = (
            initial_context.hook_extensions if initial_context is not None else {}
        )

    @property
    def current_stage(self) -> str | None:
        """Name of the next stage to execute, or ``None`` after halt."""

        return self._current_stage

    @property
    def state(self) -> Any:
        """Current working state snapshot held by the stepwise driver."""

        if isinstance(self._state, dict):
            return dict(self._state)
        return self._state

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:
        from arnold.pipeline.executor import (
            _build_ctx,
            _enforce_typed_step_io_handoff,
            _run_parallel_stage,
            _stash_halt_reason,
        )
        from arnold.pipeline.routing import RoutingError, resolve_edge
        from arnold.pipeline.state import StateDelta
        from arnold.pipeline.types import ParallelStage, StepResult

        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_execution",
            surface="stepwise_driver.advance",
            run_id=envelope.run_id,
            plugin_id=envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"stage": self._current_stage, "iteration": self._iteration},
            metadata={"isolation_mode": self.isolation_mode},
        )
        if self._current_stage is None:
            outcome = AdvanceOutcome(kind="halted", payload=self._checkpoint_payload())
            attempt.terminal(
                status="completed",
                outcome=outcome.kind,
                payload={"current_stage": self._current_stage},
            )
            return outcome

        stage = self.pipeline.stages.get(self._current_stage)
        if stage is None:
            missing = self._current_stage
            self._current_stage = None
            outcome = AdvanceOutcome(
                kind="failed",
                payload=self._checkpoint_payload(),
                errors=("missing-stage", str(missing)),
            )
            attempt.terminal(
                status="failed",
                outcome=outcome.kind,
                payload={"errors": list(outcome.errors)},
            )
            return outcome

        ctx = _build_ctx(self._state, envelope, self._hook_extensions)
        halt_loop, halt_reason = self.hooks.should_halt_loop(
            stage,
            self._state,
            self._iteration,
        )
        if halt_loop:
            _stash_halt_reason(self.hooks, halt_reason)
            self.hooks.on_stage_complete(
                stage,
                ctx,
                StepResult(),
                self._state,
                self._owned_keys,
            )
            self._current_stage = None
            outcome = AdvanceOutcome(kind="halted", payload=self._checkpoint_payload())
            attempt.terminal(
                status="completed",
                outcome=outcome.kind,
                payload={"halt_reason": halt_reason},
            )
            return outcome

        try:
            if isinstance(stage, ParallelStage):
                result = _run_parallel_stage(
                    stage,
                    self._state,
                    envelope,
                    self._parallel_safe,
                    self.hooks,
                    hook_extensions=self._hook_extensions,
                )
            else:
                ctx = self.hooks.on_step_start(stage, ctx)
                try:
                    result = stage.step.run(ctx)
                except BaseException as exc:
                    self.hooks.on_step_error(stage, ctx, exc)
                    raise
                result = self.hooks.on_step_end(stage, ctx, result)

            suspend, halt_reason = self.hooks.should_suspend(stage, self._state, result)
            if suspend:
                _stash_halt_reason(self.hooks, halt_reason)
                self.hooks.on_stage_complete(
                    stage,
                    ctx,
                    result,
                    self._state,
                    self._owned_keys,
                )
                outcome = AdvanceOutcome(
                    kind="awaiting",
                    payload={
                        **self._checkpoint_payload(),
                        "stage": stage.name,
                        "halt_reason": halt_reason,
                    },
                )
                attempt.effect("suspend", {"stage": stage.name, "halt_reason": halt_reason})
                attempt.terminal(
                    status="suspended",
                    outcome=outcome.kind,
                    payload={"stage": stage.name, "halt_reason": halt_reason},
                )
                return outcome

            _enforce_typed_step_io_handoff(
                pipeline=self.pipeline,
                stage=stage,
                result=result,
                hook_extensions=self._hook_extensions,
            )

            if result.outputs:
                if isinstance(self._state, dict):
                    self._state.update(result.outputs)
                else:
                    self._state = dict(result.outputs)

            if result.contract_result is not None and isinstance(self._state, dict):
                published = self._state.get("__contract_results__")
                if not isinstance(published, dict):
                    published = {}
                    self._state["__contract_results__"] = published
                published[stage.name] = result.contract_result

            if result.state_patch:
                self._state, self._owned_keys = self.hooks.merge_state(
                    stage,
                    self._state,
                    StateDelta(patches=(dict(result.state_patch),)),
                    self._owned_keys,
                )

            try:
                edge = resolve_edge(stage, result, result.verdict, stage.edges)
            except RoutingError as exc:
                fallback = self.hooks.resolve_routing_fallback(
                    stage,
                    result,
                    stage.edges,
                    exc,
                )
                if fallback is not None:
                    edge = fallback
                elif not stage.decision_vocabulary and not stage.override_vocabulary:
                    edge = None
                else:
                    raise

            if edge is None or edge.target == "halt":
                _stash_halt_reason(self.hooks, "halt")
                self.hooks.on_stage_complete(
                    stage,
                    ctx,
                    result,
                    self._state,
                    self._owned_keys,
                )
                self._current_stage = None
                outcome = AdvanceOutcome(kind="halted", payload=self._checkpoint_payload())
                attempt.terminal(
                    status="completed",
                    outcome=outcome.kind,
                    payload={"stage": stage.name, "next_stage": None},
                )
                return outcome

            consumer_stage = self.pipeline.stages.get(edge.target)
            if consumer_stage is not None:
                self.hooks.on_edge_traverse(stage, consumer_stage, ctx, result)
            self.hooks.on_stage_complete(
                stage,
                ctx,
                result,
                self._state,
                self._owned_keys,
            )
            self._current_stage = edge.target
            self._iteration += 1
            outcome = AdvanceOutcome(kind="advanced", payload=self._checkpoint_payload())
            attempt.effect("advance", {"stage": stage.name, "next_stage": self._current_stage})
            attempt.terminal(
                status="completed",
                outcome=outcome.kind,
                payload={"stage": stage.name, "next_stage": self._current_stage},
            )
            return outcome
        except BaseException as exc:
            outcome = AdvanceOutcome(
                kind="failed",
                payload=self._checkpoint_payload(),
                errors=(exc.__class__.__name__, str(exc)),
            )
            attempt.terminal(
                status="failed",
                outcome=outcome.kind,
                payload={"errors": list(outcome.errors)},
            )
            return outcome

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:
        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_execution",
            surface="stepwise_driver.checkpoint",
            run_id=envelope.run_id,
            plugin_id=envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"stage": self._current_stage, "iteration": self._iteration},
            metadata={"isolation_mode": self.isolation_mode},
        )
        outcome = CheckpointOutcome(kind="advanced", payload=self._checkpoint_payload())
        attempt.effect("checkpoint", {"current_stage": self._current_stage})
        attempt.terminal(
            status="completed",
            outcome=outcome.kind,
            payload={"current_stage": self._current_stage},
        )
        return outcome

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:
        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_execution",
            surface="stepwise_driver.resume",
            run_id=cursor.run_id or envelope.run_id,
            plugin_id=cursor.plugin_id or envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"cursor_stage": cursor.cursor.get("stage"), "iteration": self._iteration},
            metadata={"isolation_mode": self.isolation_mode},
        )
        cursor_body = dict(cursor.cursor)
        stage = cursor_body.get("stage")
        if isinstance(stage, str) and stage:
            self._current_stage = stage
        state = cursor_body.get("state")
        if isinstance(state, Mapping):
            self._state = dict(state)
        self._iteration = int(cursor_body.get("iteration") or self._iteration)
        resumed = RuntimeEnvelope(
            plugin_id=cursor.plugin_id,
            run_id=cursor.run_id,
            manifest_hash=envelope.manifest_hash,
            artifact_root=envelope.artifact_root,
            resume_cursor=cursor,
        )
        attempt.effect("resume", {"stage": self._current_stage, "iteration": self._iteration})
        attempt.terminal(
            status="completed",
            outcome="resumed",
            payload={"stage": self._current_stage, "iteration": self._iteration},
        )
        return resumed

    def _checkpoint_payload(self) -> dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "state": self.state,
            "iteration": self._iteration,
            "isolation_mode": self.isolation_mode,
        }
