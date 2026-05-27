"""Frozen primitive types for the megaplan `_pipeline` package.

This module defines the small, frozen dataclass + Protocol surface that the
Sprint-1 standalone pipeline executor and demo build on. Sprint 2 will port
existing handlers onto these primitives; the shapes declared here are
**frozen at end of Sprint 1** and must not be changed without a revision
note in ``briefs/megaplan-decomposition.md``.

Contract notes (load-bearing for executor authors and Step authors):

(a) ``'halt'`` is the reserved terminal ``NextEdge`` label / ``Edge.target``
    value. Step authors MUST NOT use ``'halt'`` as a non-terminal edge
    label. The executor treats either ``result.next == 'halt'`` or an edge
    whose ``target == 'halt'`` as the terminal sentinel.

(b) ``'subloop'`` and ``'override'`` are reserved ``Step.kind`` Literal
    values for forward compatibility. The Sprint-1 executor MUST NOT branch
    on them; they exist so Sprint 2 (and beyond) can introduce a tiebreaker
    subloop kind and an escape-edge override kind without changing the
    frozen Protocol.

(c) ``PipelineVerdict``, ``StepResult``, and ``StepContext`` instances are
    conceptually immutable. Callers MUST NOT mutate ``payload``,
    ``state_patch``, ``inputs``, or ``outputs`` after construction. Because
    ``@dataclass(frozen=True)`` does not deeply freeze ``Mapping`` fields,
    the executor applies ``state_patch`` via ``state.update(dict(result.state_patch))``
    — a defensive copy that prevents cross-call aliasing if a Step returns
    a shared default dict.

(d) Deviation note: the brief at ``briefs/megaplan-decomposition.md:124-128``
    originally sketched ``stages: dict[str, Stage]`` and
    ``overlays: list[Overlay]``. This module widens to
    ``Mapping[str, Stage | ParallelStage]`` and ``tuple[Overlay, ...]`` so
    that (1) ``Pipeline`` itself can be ``@dataclass(frozen=True)`` (frozen
    dataclasses do not accept ``list`` defaults without a default_factory),
    and (2) a ``ParallelStage`` can be addressed by name like a ``Stage``
    without requiring callers to unwrap an intermediate type. The full
    revision note lives in ``briefs/megaplan-decomposition.md`` under the
    ``## Revision notes`` heading (added in Sprint 1 T5).

(e) Typed-gate dispatch (Sprint 4 Chunk A): ``PipelineVerdict.recommendation`` and
    ``Edge.kind`` together replace the legacy ``"gate_<condition>:<next>"``
    label-string encoding for gate transitions. When a Step returns a
    ``PipelineVerdict`` whose ``recommendation`` is set (one of the
    ``GateRecommendation`` literals), the executor matches outgoing edges
    by ``(kind == "gate" and recommendation == verdict.recommendation)``
    in preference to label-string matching. ``kind == "normal"`` edges
    continue to dispatch on ``Edge.label == result.next``. ``kind ==
    "override"`` is reserved for Chunk D — the executor MUST NOT branch on
    it in Chunk A. ``PipelineVerdict.override`` is added now (defaulted, additive)
    so that Chunk D can wire override edges without re-freezing ``PipelineVerdict``;
    it is not consumed by the Chunk-A executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Mapping,
    Protocol,
    runtime_checkable,
)

if TYPE_CHECKING:  # pragma: no cover - typing-only aliases
    BudgetRef = Any
    Profile = Any


NextEdge = str

GateRecommendation = Literal["proceed", "iterate", "tiebreaker", "escalate"]
OverrideAction = Literal["force_proceed", "abort", "replan", "add_note"]
EdgeKind = Literal["normal", "gate", "override"]


@dataclass(frozen=True)
class Edge:
    """A labelled transition from one stage to another.

    Dispatch depends on ``kind``:

    * ``kind == "normal"`` (default): the executor matches when
      ``Edge.label == StepResult.next``. ``label`` is the sole match key.
    * ``kind == "gate"``: the executor matches when
      ``Edge.recommendation == StepResult.verdict.recommendation``.
      ``label`` is NOT consulted for dispatch and is held only for
      debug-readable rendering (planning emits the recommendation name as
      the label, e.g. ``"iterate"``).
    * ``kind == "override"``: reserved for Chunk D; not dispatched by the
      Chunk-A executor.

    ``target`` is the name of the next stage in ``Pipeline.stages``. The
    reserved target ``'halt'`` terminates the pipeline.
    """

    label: str
    target: str
    kind: EdgeKind = "normal"
    recommendation: GateRecommendation | None = None


@dataclass(frozen=True)
class PipelineVerdict:
    """Structured output of a judge-kind Step.

    ``score`` is a float in ``[0.0, 1.0]`` by convention but is not
    enforced here. ``flags`` and ``notes`` are free-form. ``payload`` is a
    Mapping for arbitrary structured detail; see the immutability note in
    the module docstring.

    ``recommendation`` is the typed gate signal consumed by the executor's
    ``kind == "gate"`` edge dispatch (Sprint 4 Chunk A). When set, the
    executor matches the enclosing stage's gate edges by
    ``Edge.recommendation == verdict.recommendation`` in preference to the
    legacy ``Edge.label == result.next`` path. ``override`` is added now
    for forward compatibility with Chunk D's override-edge dispatch; the
    Chunk-A executor does not consume it.
    """

    score: float
    flags: tuple[str, ...] = ()
    notes: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    recommendation: GateRecommendation | None = None
    override: OverrideAction | None = None


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class StepResult:
    """What a ``Step.run`` invocation returns.

    ``outputs`` maps a label to a filesystem path. The executor verifies
    existence only; layout under ``ctx.plan_dir`` is unconstrained beyond
    that. ``next`` is matched against the enclosing stage's edges (with
    ``'halt'`` reserved). ``state_patch`` is applied to working state via
    a defensive ``dict(...)`` copy.
    """

    outputs: Mapping[str, Path] = field(default_factory=dict)
    verdict: "PipelineVerdict | None" = None
    next: NextEdge = "halt"
    state_patch: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Step(Protocol):
    """Structural Protocol for pipeline steps.

    Implementations must expose ``name``, ``kind``, ``prompt_key``, and
    ``slot`` as attributes, plus a ``run(ctx)`` method returning a
    ``StepResult``. ``@runtime_checkable`` enables ``isinstance(obj, Step)``
    sanity checks; a missing attribute surfaces at instantiation/check
    time rather than as a silent miss.
    """

    name: str
    kind: Literal["produce", "judge", "decide", "subloop", "override"]
    prompt_key: str | None
    slot: str | None

    def run(self, ctx: StepContext) -> StepResult: ...


@dataclass(frozen=True)
class Stage:
    """A single-Step stage with labelled outgoing edges."""

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()


@dataclass(frozen=True)
class ParallelStage:
    """A fan-out stage whose Steps run concurrently and barrier-join.

    The executor submits each step to a ``ThreadPoolExecutor`` and passes
    the ordered list of ``StepResult`` values to ``join`` along with the
    shared ``StepContext``. ``join`` returns a single ``StepResult`` whose
    ``next`` label dispatches like a regular Stage. The empty-steps case
    is guarded in the executor via ``max(1, max_workers or len(steps))``.

    **Thread-safety contract**: every Step in ``steps`` MUST be hermetic
    with respect to shared mutable state. Steps that read or write the
    plan's ``state.json`` (e.g. :class:`InProcessHandlerStep`) are NOT
    safe for parallel fan-out — concurrent handler invocations would race
    through the same plan directory. The executor enforces this at
    submission time: a ``ParallelStage`` containing an
    ``InProcessHandlerStep`` is rejected with a ``ValueError`` before any
    handler executes. Hermetic steps such as ``PanelReviewerStep`` (which
    writes to a per-reviewer output directory and does not touch shared
    state) satisfy the contract.
    """

    name: str
    steps: tuple[Step, ...]
    join: Callable[[list[StepResult], StepContext], StepResult]
    edges: tuple[Edge, ...] = ()
    max_workers: int | None = None


@dataclass(frozen=True)
class Overlay:
    """A named transformation from one Pipeline to another.

    Overlays let profiles add/remove/wrap stages without mutating the base
    ``Pipeline``. Sprint 1 defines only the shape; application is Sprint 2.
    """

    name: str
    apply: Callable[["Pipeline"], "Pipeline"]


@dataclass(frozen=True)
class Pipeline:
    """A named graph of stages with an entry point and optional overlays."""

    stages: Mapping[str, "Stage | ParallelStage"]
    entry: str
    overlays: tuple[Overlay, ...] = ()

    @classmethod
    def builder(
        cls,
        name: str,
        description: str = "",
        *,
        default_profile: str | None = None,
        supported_modes: tuple[str, ...] = (),
        pipeline_dir: Path | None = None,
        worker: "Callable[..., str] | None" = None,
        prompt_registry: "Callable[[str], str] | None" = None,
        pipeline_version: int = 1,
    ) -> "Any":
        """Return a :class:`PipelineBuilder` for fluent construction.

        Pipeline-level metadata (``description`` / ``default_profile`` /
        ``supported_modes``) is held on the returned builder rather than
        the frozen :class:`Pipeline` dataclass — the dataclass has only
        ``stages / entry / overlays`` (T1.j audit). The
        :class:`PipelineRegistry` surfaces the metadata via
        ``PipelineRegistry.metadata`` (T9). Imported lazily to avoid an
        import cycle (``builder`` depends on this module)."""
        from megaplan._pipeline.builder import PipelineBuilder

        return PipelineBuilder(
            name=name,
            description=description,
            default_profile=default_profile,
            supported_modes=tuple(supported_modes),
            pipeline_dir=pipeline_dir,
            worker=worker,
            prompt_registry=prompt_registry,
            pipeline_version=pipeline_version,
        )
