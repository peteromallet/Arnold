"""Frozen IR dataclasses for the native Python pipeline runtime.

These types represent the intermediate representation produced by
decorator metadata and consumed by the compiler, graph projection,
and runtime.  They are deliberately neutral — no runtime evaluation
logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet, Tuple


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
    ``'subpipeline'``, or ``'parallel'``."""

    name: str = ""
    """Human-readable label for the instruction (phase/decision name)."""

    func: Callable[..., Any] | None = field(default=None, compare=False, hash=False)
    """The callable to invoke for ``phase`` and ``decision`` ops."""

    subprogram: Any = field(default=None, compare=False, hash=False)
    """For ``subpipeline`` ops: the child :class:`NativeProgram` to execute.
    For ``parallel`` ops: the :class:`ParallelInstruction` metadata block.
    Excluded from equality/hash; ignored for other ops."""

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

    description: str = ""
    """Optional human-readable description."""
