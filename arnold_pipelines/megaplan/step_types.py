"""Step execution contracts: StepContext and StepResult.

Rehomed from ``arnold_pipelines.megaplan._pipeline.types`` during the M3
burn-down (T11).  These are Megaplan-specific runtime contracts that are
INCOMPATIBLE with Arnold's StepContext/StepResult per the T8 shape audit,
so they live in a Megaplan-owned responsibility-named module rather than
being repointed to ``arnold.pipeline.types``.

Dependencies:
* ``RunEnvelope`` / ``EMPTY_ENVELOPE`` — from ``arnold.runtime.envelope``
* ``PipelineVerdict`` / ``ContractResult`` — from ``arnold.pipeline.types``
  (FULLY COMPATIBLE per T8)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, runtime_checkable

from arnold.pipeline.types import (
    ContractResult,
    Edge,
    PipelineVerdict,
    Port,
    PortRef,
    ReadRef,
    WriteRef,
)
from arnold.runtime.envelope import EMPTY_ENVELOPE, RunEnvelope

NextEdge = str
EdgeKind = Literal["normal", "decision", "override"]


@dataclass
class StepContext:
    """Context handed to ``Step.run`` at dispatch time.

    ``state`` is typed ``Any`` in Sprint 1: the live megaplan ``PlanState``
    is a ``TypedDict`` at ``megaplan/types.py:146``, and tightening the
    annotation belongs to Sprint 2 once the port is in flight.
    """

    plan_dir: Path
    state: Any
    profile: Any
    mode: str
    inputs: Mapping[str, Path] = field(default_factory=dict)
    budget: Any = None
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)


@dataclass(frozen=True)
class StepResult:
    """What a ``Step.run`` invocation returns.

    ``outputs`` maps a label to a filesystem path. The executor verifies
    existence only; layout under ``ctx.plan_dir`` is unconstrained beyond
    that. ``next`` is matched against the enclosing stage's edges (with
    ``'halt'`` reserved). ``state_patch`` is applied to working state via
    a defensive ``dict(...)`` copy.

    ``contract_result`` carries typed seam payloads when a step emits an
    evidence-first contract. Its ``schema_version`` is the structural
    ``ContractResult`` envelope version, while any logical payload schema
    version belongs inside ``contract_result.payload``.
    """

    outputs: Mapping[str, Path] = field(default_factory=dict)
    verdict: PipelineVerdict | None = None
    next: NextEdge = "halt"
    state_patch: Mapping[str, Any] = field(default_factory=dict)
    contract_result: ContractResult | None = None
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)


class StepMixinProperty:
    """Property-based default typed-port declarations for non-dataclass Steps.

    Provides empty ``produces``/``consumes`` via ``@property`` so
    non-dataclass Step implementations satisfy the
    ``arnold_pipelines.megaplan._pipeline.types.Step`` Protocol's
    instance-level attribute contract without boilerplate.
    Dataclass Step subclasses can use
    ``arnold_pipelines.megaplan._pipeline.types.StepMixin`` instead.
    """

    @property
    def produces(self) -> tuple[Any, ...]:  # pragma: no cover - trivial
        return ()

    @property
    def consumes(self) -> tuple[Any, ...]:  # pragma: no cover - trivial
        return ()


@runtime_checkable
class Step(Protocol):
    """Megaplan step protocol with typed-port declarations."""

    name: str
    kind: str
    prompt_key: str | None
    slot: str | None
    produces: tuple[Port, ...]
    consumes: tuple[PortRef, ...]

    def run(self, ctx: StepContext) -> StepResult: ...


@dataclass
class StepMixin:
    """Default typed-port declarations for dataclass steps."""

    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Stage:
    """Megaplan stage shape retained for handler-backed planning pipelines."""

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()
    reads: tuple[ReadRef, ...] = field(default_factory=tuple)
    writes: tuple[WriteRef, ...] = field(default_factory=tuple)
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)
    invocation: Any = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    loop_condition: Callable[[Any], bool] | None = None
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ParallelStage:
    """Megaplan fan-out stage shape retained for bridge translation."""

    name: str
    steps: tuple[Step, ...]
    join: Callable[[list[StepResult], StepContext], StepResult]
    edges: tuple[Edge, ...] = ()
    max_workers: int | None = None
    reads: tuple[ReadRef, ...] = field(default_factory=tuple)
    writes: tuple[WriteRef, ...] = field(default_factory=tuple)
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)
    invocation: Any = None
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Overlay:
    """A named transformation from one Pipeline to another."""

    name: str
    apply: Callable[["Pipeline"], "Pipeline"]


@dataclass(frozen=True)
class Pipeline:
    """Megaplan graph shape with optional overlays."""

    stages: Mapping[str, Stage | ParallelStage]
    entry: str
    overlays: tuple[Overlay, ...] = ()
    binding_map: dict | None = None
    resource_bundles: tuple[Any, ...] = field(default_factory=tuple)
