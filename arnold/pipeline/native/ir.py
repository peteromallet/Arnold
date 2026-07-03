"""Frozen IR dataclasses for the native Python pipeline runtime.

These types represent the intermediate representation produced by
decorator metadata and consumed by the compiler, graph projection,
and runtime.  They are deliberately neutral — no runtime evaluation
logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet, Mapping, Protocol, runtime_checkable


@runtime_checkable
class NativeInvocable(Protocol):
    """Structural metadata shared by native steps and workflows."""

    name: str
    stable_id: str | None
    inputs_schema: Mapping[str, Any] | None
    outputs_schema: Mapping[str, Any] | None


@dataclass(frozen=True)
class NativePhase:
    """A single phase in a native pipeline.

    Wraps a callable decorated with ``@phase``.  The phase carries
    no control-flow metadata of its own; branching and looping are
    modelled via :class:`NativeDecision` and :class:`NativeLoopGuard`
    in the enclosing :class:`NativePipeline`.
    """

    name: str
    """Unique name of this phase within its pipeline (derived from the
    decorated function name, but kept as a separate field for clarity)."""

    func: Callable[..., Any] = field(compare=False, hash=False)
    """The wrapped callable (excluded from equality/hash)."""

    stable_id: str | None = None
    """Stable semantic identity declared on the decorator, if any."""

    inputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared input schema metadata, if any."""

    outputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared output schema metadata, if any."""

    produces: tuple = ()
    """Typed ports this phase produces (Port instances)."""

    consumes: tuple = ()
    """Typed ports this phase consumes (PortRef instances)."""


@dataclass(frozen=True)
class NativeDecision:
    """A decision point in a native pipeline.

    Wraps a callable decorated with ``@decision``.  The *vocabulary*
    is the set of string labels the decision may return; the runtime
    uses these to select the next branch edge.

    When ``human_gate=True`` the decision represents a human-gate
    suspension point.  The additional metadata fields
    (``artifact_stage``, ``choices``, ``resume_input_schema``,
    ``override_routes``) carry the human-interaction contract so
    the runtime and graph projection can surface the gate without
    inspecting the callable body.
    """

    name: str
    """Unique name of this decision within its pipeline."""

    func: Callable[..., Any] = field(compare=False, hash=False)
    """The wrapped callable."""

    vocabulary: FrozenSet[str] = field(default_factory=frozenset)
    """Set of valid return labels (e.g. ``{'pass', 'fail'}``)."""

    decision_routes: dict[str, str | None] = field(default_factory=dict)
    """Maps decision labels to outgoing edge labels (e.g. ``{'pass': 'next', 'fail': 'halt'}``).
    A ``None`` value means the decision is terminal / has no next stage.
    This is build-time metadata for route-target validation."""

    # ── Human-gate metadata (all default-off for ordinary decisions) ──

    human_gate: bool = False
    """When ``True`` this decision is a human-gate suspension point.
    Ordinary decisions leave this ``False`` and the remaining human-gate
    fields at their defaults."""

    artifact_stage: str = ""
    """For human-gate decisions: the name of the stage whose artifact
    the user is being asked to inspect.  Empty for ordinary decisions."""

    choices: tuple[str, ...] = ()
    """For human-gate decisions: the ordered tuple of human-action labels
    (e.g. ``('continue', 'stop')``).  These are the labels the human
    can submit; they overlap with ``vocabulary`` but carry the
    human-interaction semantic.  Empty for ordinary decisions."""

    resume_input_schema: dict = field(default_factory=dict)
    """For human-gate decisions: a JSON Schema dict describing the
    shape of the resume input payload.  When non-empty the runtime
    validates the human's submission against this schema before
    resuming.  Defaults to an empty dict (no validation)."""

    override_routes: dict[str, str | None] = field(default_factory=dict)
    """For human-gate decisions: optional per-choice route overrides
    (e.g. ``{'continue': 'panel_review', 'stop': 'halt'}``).  When
    non-empty these take precedence over ``decision_routes`` for the
    corresponding choice labels.  Empty for ordinary decisions."""


@dataclass(frozen=True)
class NativeLoopGuard:
    """A loop guard attached to a ``while`` construct.

    The *guard* callable returns a boolean (``True`` → continue iterating).
    The *body* callable is the decorated function that runs each iteration.
    """

    guard: Callable[..., bool] = field(compare=False, hash=False)
    """Callable that returns True to continue looping."""

    body: Callable[..., Any] = field(compare=False, hash=False)
    """Callable executed on each loop iteration."""

    name: str = ""
    """Optional name for diagnostics."""


@dataclass(frozen=True)
class NativePipeline:
    """A complete native pipeline IR.

    Built from ``@pipeline``-decorated functions annotated with
    ``@phase``, ``@decision``, and loop constructs.  This is the
    root IR node consumed by the compiler and graph projection.
    """

    name: str
    """Pipeline name (derived from the decorated function name)."""

    func: Callable[..., Any] = field(compare=False, hash=False)
    """The top-level pipeline callable (excluded from equality/hash)."""

    stable_id: str | None = None
    """Stable semantic identity declared on the decorator, if any."""

    inputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared workflow input schema metadata, if any."""

    outputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared workflow output schema metadata, if any."""

    phases: tuple[NativePhase, ...] = ()
    """Phases in declaration order."""

    decisions: tuple[NativeDecision, ...] = ()
    """Decisions referenced by this pipeline."""

    loop_guards: tuple[NativeLoopGuard, ...] = ()
    """Loop guards used in ``while`` constructs."""

    description: str = ""
    """Optional human-readable description."""


# ── Parallel fan-out / fan-in IR ──────────────────────────────────────

@dataclass(frozen=True)
class ParallelInstruction:
    """Metadata for a parallel fan-out / fan-in block.

    Declares statically-bounded branches that execute concurrently
    (or sequentially in milestone order), followed by an optional
    reducer that combines results before advancing to the merge point.

    This is pure metadata — the actual instruction stream uses
    ``NativeInstruction(op="parallel", ...)`` to reference a parallel
    block by index into :attr:`NativeProgram.parallel_blocks`.
    """

    name: str = ""
    """Human-readable label for this parallel block."""

    branches: tuple[str, ...] = ()
    """Ordered branch names (derived from the callable names in the
    literal branch list)."""

    branch_funcs: tuple[Callable[..., Any], ...] = field(
        default_factory=tuple, compare=False, hash=False
    )
    """Callables for each branch, in declaration order."""

    reducer: Callable[..., Any] | None = field(
        default=None, compare=False, hash=False
    )
    """Optional reducer callable for fan-in.  When ``None``, branch
    results are collected into a list keyed by the parallel block name."""

    merge_pc: int | None = None
    """Program counter to advance to after all branches complete and
    the reducer runs.  ``None`` means halt after the parallel block."""


@dataclass(frozen=True)
class ParallelMapInstruction:
    """Metadata for a dynamic ``parallel_map`` fan-out block.

    Declares a runtime-list fan-out where a *mapper* callable is
    applied to each item of a collection resolved at runtime.  Results
    are collected and (optionally) reduced before advancing to the
    merge point.

    This is a **distinct** IR shape from :class:`ParallelInstruction`:
    ``ParallelInstruction`` models statically-bounded branches known at
    compile time, while ``ParallelMapInstruction`` models a dynamic
    fan-out over a runtime list whose cardinality is not known until
    execution.

    The actual instruction stream uses
    ``NativeInstruction(op="parallel_map", ...)`` to reference a
    ``parallel_map`` block by index into
    :attr:`NativeProgram.parallel_map_blocks`.
    """

    name: str = ""
    """Human-readable label for this parallel_map block."""

    items_ref: str = ""
    """Reference to the runtime collection — a parameter name or
    state key that resolves to an iterable at execution time."""

    mapper: Callable[..., Any] | None = field(
        default=None, compare=False, hash=False
    )
    """The callable applied to each item of the runtime collection."""

    mapper_name: str = ""
    """Name of the mapper callable (for diagnostics and trace emission)."""

    reducer: Callable[..., Any] | None = field(
        default=None, compare=False, hash=False
    )
    """Optional reducer callable for fan-in.  When ``None``, per-item
    results are collected into a list keyed by the block name."""

    path_template: str = ""
    """Path template for per-item call-site paths
    (e.g. ``'critique/{item_id}'``).  Variables are resolved from
    item attributes at execution time."""

    merge_pc: int | None = None
    """Program counter to advance to after all items complete and the
    reducer runs.  ``None`` means halt after the parallel_map block."""


# ── Native instruction set (produced by compiler, consumed by runtime/graph) ──

@dataclass(frozen=True)
class NativeInstruction:
    """A single resumable instruction in a native pipeline program.

    Each instruction carries an explicit program counter (``pc``) and
    enough metadata for the runtime and graph projection to advance
    state, route control flow, and resume from a checkpoint without
    relying on CPython frame state.
    """

    pc: int
    """Zero-based program counter — position in the instruction tuple."""

    op: str
    """Operation code: ``'phase'``, ``'decision'``, ``'jump'``, ``'halt'``,
    ``'subpipeline'``, ``'parallel'``, or ``'parallel_map'``."""

    name: str = ""
    """Human-readable label for the instruction (phase/decision name)."""

    func: Callable[..., Any] | None = field(default=None, compare=False, hash=False)
    """The callable to invoke for ``phase`` and ``decision`` ops."""

    subprogram: Any = field(default=None, compare=False, hash=False)
    """For ``subpipeline`` ops: the child :class:`NativeProgram` to execute.
    For ``parallel`` ops: the :class:`ParallelInstruction` metadata block.
    For ``parallel_map`` ops: the :class:`ParallelMapInstruction` metadata block.
    Excluded from equality/hash; ignored for other ops."""

    input_mapping: dict[str, str] = field(default_factory=dict)
    """For ``subpipeline`` ops: maps child input names to parent bindings."""

    output_mapping: dict[str, str] = field(default_factory=dict)
    """For ``subpipeline`` ops: maps child output names to parent bindings."""

    parallel_index: int | None = None
    """For ``parallel`` ops: index into :attr:`NativeProgram.parallel_blocks`."""

    next_pc: int | None = None
    """Program counter of the next instruction for sequential fall-through."""

    branches: dict[str, int] = field(default_factory=dict)
    """For ``decision`` ops: maps decision return labels to target program counters."""

    produces: tuple = ()
    """Typed ports this instruction produces (Port instances, for phase ops)."""

    consumes: tuple = ()
    """Typed ports this instruction consumes (PortRef instances, for phase ops)."""

    decision_vocabulary: FrozenSet[str] = field(default_factory=frozenset)
    """For ``decision`` ops: the set of valid return labels
    (e.g. ``frozenset({'pass', 'fail'})``).  Empty for non-decision ops."""


@dataclass(frozen=True)
class NativeProgram:
    """A complete compiled native pipeline program.

    The ``instructions`` tuple is ordered by program counter (``pc``).
    ``phases``, ``decisions``, and ``loop_guards`` mirror the
    :class:`NativePipeline` IR fields for consumption by graph
    projection.
    """

    name: str
    """Pipeline name."""

    stable_id: str | None = None
    """Stable semantic identity declared on the decorator, if any."""

    inputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared workflow input schema metadata, if any."""

    outputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared workflow output schema metadata, if any."""

    instructions: tuple[NativeInstruction, ...] = ()
    """Instructions in PC order."""

    phases: tuple[NativePhase, ...] = ()
    """Phases referenced by this program."""

    decisions: tuple[NativeDecision, ...] = ()
    """Decisions referenced by this program."""

    loop_guards: tuple[NativeLoopGuard, ...] = ()
    """Loop guards used in ``while`` constructs."""

    parallel_blocks: tuple[ParallelInstruction, ...] = ()
    """Parallel fan-out / fan-in blocks referenced by ``parallel`` ops."""

    parallel_map_blocks: tuple[ParallelMapInstruction, ...] = ()
    """Dynamic ``parallel_map`` fan-out blocks referenced by ``parallel_map`` ops."""

    description: str = ""
    """Optional human-readable description."""
