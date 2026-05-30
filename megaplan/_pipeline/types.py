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

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Mapping,
    Protocol,
    TypeAlias,
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

    ``produces`` and ``consumes`` are INSTANCE-level typed-port
    declarations (no ``ClassVar``) read by the binder only when
    :func:`megaplan._pipeline.flags.typed_ports_on` returns true.
    Implementations may inherit defaults from :class:`StepMixin`.
    """

    name: str
    kind: Literal["produce", "judge", "decide", "subloop", "override"]
    prompt_key: str | None
    slot: str | None
    produces: tuple["Port", ...]
    consumes: tuple["PortRef", ...]

    def run(self, ctx: StepContext) -> StepResult: ...


@dataclass
class StepMixin:
    """Default typed-port declarations for ``@dataclass`` Step classes.

    Provides empty ``produces``/``consumes`` tuples via
    ``field(default_factory=tuple)`` so dataclass Step subclasses satisfy
    the :class:`Step` Protocol's instance-level attribute contract without
    boilerplate. Non-dataclass Step implementations can subclass
    :class:`StepMixinProperty` instead (returns ``()`` via ``@property``).
    """

    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)


class StepMixinProperty:
    """Property-based default typed-port declarations for non-dataclass Steps."""

    @property
    def produces(self) -> tuple["Port", ...]:  # pragma: no cover - trivial
        return ()

    @property
    def consumes(self) -> tuple["PortRef", ...]:  # pragma: no cover - trivial
        return ()


@dataclass(frozen=True)
class Stage:
    """A single-Step stage with labelled outgoing edges.

    ``produces`` / ``consumes`` (M2 / T1b) optionally override the wrapped
    Step's typed-port declarations. When empty, the binder falls back to
    the Step's own ``produces`` / ``consumes`` tuples. Read by the binder
    only when :func:`megaplan._pipeline.flags.typed_ports_on` is true.
    """

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)


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
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)


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


# ── Typed Port primitives (M2 / T1) ─────────────────────────────────────


@dataclass(frozen=True)
class Port:
    """A named typed port that declares its content type.

    Every pipeline Step declares zero-or-more ports via ``produces`` and
    ``consumes``.  The executor uses these declarations for
    contract-level validation and routing-key construction when
    ``MEGAPLAN_TYPED_PORTS`` is on.
    """

    name: str
    content_type: str
    taint: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PortRef:
    """A reference to a named port with its declared content type."""

    port_name: str
    content_type: str


@dataclass(frozen=True)
class RoutingKey:
    """A content-type–qualified routing key for fan-out dispatch.

    Concretely::

        RoutingKey(key="text/markdown")

    The executor constructs routing keys formed from the
    content type declared on a producing port.
    """

    key: str


# ── Content type registry ───────────────────────────────────────────────


def _canonical_json_dumps(value: Any) -> str:
    """Serialize *value* deterministically with sorted keys.

    Mirrors :func:`megaplan.store.snapshot.canonical_json_dumps` but kept
    local so the ``_pipeline`` package has zero dependency on the store
    layer.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def register_schema(schema_obj: Any) -> str:
    """Return the deterministic SHA-256 hex digest of *schema_obj*'s
    canonical JSON representation.

    ``schema_obj`` may be any JSON-serialisable value (typically a
    ``dict``, ``list``, or Pydantic ``BaseModel``).  The returned string
    is the raw hex digest (no ``sha256:`` prefix) so callers can format
    the prefix as they wish.
    """
    raw = _canonical_json_dumps(schema_obj)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ContentTypeRegistry:
    """Map content-type names → schema SHA-256 digests.

    Mirrors :class:`PipelineRegistry` (``registry.py:88``) but for
    content-type schemas instead of pipeline builders.  Duplicate
    registration raises ``ValueError``.
    """

    _schemas: dict[str, str] = field(default_factory=dict)

    def register(self, name: str, schema_obj: Any) -> str:
        if name in self._schemas:
            raise ValueError(f"content type {name!r} already registered")
        digest = register_schema(schema_obj)
        self._schemas[name] = digest
        return digest

    def get(self, name: str) -> str:
        """Return the SHA-256 digest registered for *name*.

        Raises ``KeyError`` when *name* is not registered.
        """
        if name not in self._schemas:
            raise KeyError(
                f"no content type named {name!r}; "
                f"available: {sorted(self._schemas)}"
            )
        return self._schemas[name]

    def __contains__(self, name: str) -> bool:
        return name in self._schemas

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas))


# ── Module-level builtins ───────────────────────────────────────────────

_BUILTIN_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/markdown",
        "image/png",
        "application/x-git-diff",
        "application/x-verdict+json",
        "application/x-routing-key+json",
        "application/x-fanout-results+json",
    }
)

CONTENT_TYPES = ContentTypeRegistry()
for _ct in sorted(_BUILTIN_CONTENT_TYPES):
    CONTENT_TYPES.register(_ct, {"content_type": _ct})


# ── Reduce / Selection result primitives (M2 / T2a) ────────────────────


@dataclass(frozen=True)
class ReduceResult:
    """Structured output of a reduce-kind step.

    ``value`` is the reduced value; ``scores`` is a per-input ordered
    tuple of floats; ``tally`` is a mapping of label → count; ``provenance``
    records source step / port identifiers; ``label`` optionally names
    the chosen variant (e.g. ``"winner"``).
    """

    value: Any
    scores: tuple[float, ...] = ()
    tally: Mapping[str, int] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()
    label: str | None = None


@dataclass(frozen=True)
class SelectionResult:
    """Structured output of a selection / tournament reduce.

    ``winner`` is the selected index; ``subset`` are the candidates
    that survived an earlier filter; ``losers`` are the eliminated
    candidates; ``scores`` is per-candidate; ``cleared`` is true when the
    decision unambiguously cleared the tiebreaker threshold.
    """

    winner: int
    subset: tuple[int, ...] = ()
    losers: tuple[int, ...] = ()
    scores: tuple[float, ...] = ()
    cleared: bool = False


Reduce: TypeAlias = Callable[[list[StepResult], StepContext], ReduceResult]


# ── State delta (CAS) primitives (M2 / T2b) ────────────────────────────


class StateDeltaConflict(Exception):
    """Raised by :func:`apply_delta` when the delta's ``version`` does not
    match the current version recorded in ``state['_state_meta']['versions']``.

    Carries the offending ``key``, the ``expected`` version that the delta
    claimed, and the ``actual`` version observed in state at apply time.
    """

    def __init__(self, key: str, expected: int, actual: int) -> None:
        super().__init__(
            f"state delta for key {key!r} expected version {expected}, "
            f"found {actual}"
        )
        self.key = key
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class StateDelta:
    """Compare-and-swap state mutation.

    ``op`` is one of:

    * ``'replace'`` — last-writer-wins assignment of ``value`` at ``key``.
    * ``'accumulate'`` — append ``value`` to an existing list at ``key``
      (creating ``[]`` if missing); retains all prior entries.
    * ``'deep_merge'`` — recursively merge ``value`` (a mapping) into the
      mapping at ``key``; non-mapping leaves are overwritten.

    ``version`` is the version the writer last observed for ``key``.
    :func:`apply_delta` raises :class:`StateDeltaConflict` when the
    actual version in ``state['_state_meta']['versions']`` differs.
    """

    op: Literal["replace", "accumulate", "deep_merge"]
    key: str
    value: Any
    version: int


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, Mapping):
        out = dict(base)
        for k, v in overlay.items():
            out[k] = _deep_merge(out.get(k), v) if k in out else v
        return out
    return overlay


def apply_delta(
    state: Mapping[str, Any], delta: StateDelta
) -> tuple[dict[str, Any], int]:
    """Apply *delta* to *state* under CAS semantics.

    Returns ``(new_state, new_version)``. Raises
    :class:`StateDeltaConflict` when ``delta.version`` does not match the
    version recorded at ``state['_state_meta']['versions'][delta.key]``
    (absent ⇒ ``0``).
    """
    new_state: dict[str, Any] = dict(state)
    meta = dict(new_state.get("_state_meta", {}))
    versions = dict(meta.get("versions", {}))
    actual = int(versions.get(delta.key, 0))
    if actual != delta.version:
        raise StateDeltaConflict(delta.key, delta.version, actual)

    if delta.op == "replace":
        new_state[delta.key] = delta.value
    elif delta.op == "accumulate":
        existing = list(new_state.get(delta.key, []))
        existing.append(delta.value)
        new_state[delta.key] = existing
    elif delta.op == "deep_merge":
        existing = new_state.get(delta.key, {})
        new_state[delta.key] = _deep_merge(existing, delta.value)
    else:  # pragma: no cover - exhaustive Literal
        raise ValueError(f"unknown StateDelta op: {delta.op!r}")

    new_version = actual + 1
    versions[delta.key] = new_version
    meta["versions"] = versions
    new_state["_state_meta"] = meta
    return new_state, new_version
