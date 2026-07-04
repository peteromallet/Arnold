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

    call_site_path: tuple[str, ...] = ()
    """Stable authored call-site path segments for this instruction.

    For nested workflow and dynamic fan-out call sites, these segments come
    from authored literal ids/names rather than inferred line numbers.
    """

    func: Callable[..., Any] | None = field(default=None, compare=False, hash=False)
    """The callable to invoke for ``phase`` and ``decision`` ops."""

    subprogram: Any = field(default=None, compare=False, hash=False)
    """For ``subpipeline`` ops: the child :class:`NativeProgram` to execute.
    For ``parallel`` ops: the :class:`ParallelInstruction` metadata block.
    For ``parallel_map`` ops: the :class:`ParallelMapInstruction` metadata block.
    Excluded from equality/hash; ignored for other ops."""

    parallel_index: int | None = None
    """For ``parallel`` ops: index into :attr:`NativeProgram.parallel_blocks`."""

    parallel_map_index: int | None = None
    """For ``parallel_map`` ops: index into
    :attr:`NativeProgram.parallel_map_blocks`."""

    next_pc: int | None = None
    """Program counter of the next instruction for sequential fall-through."""

    branches: dict[str, int] = field(default_factory=dict)
    """For ``decision`` ops: maps decision return labels to target program counters."""

    output_bindings: Mapping[str, str] = field(default_factory=dict)
    """For ``subpipeline`` ops: optional child-output -> parent-key bindings."""

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

    routing_topology: dict = field(default_factory=dict)
    """Product-neutral routing topology metadata.

    A dictionary that downstream tooling (replay, inspection, compatibility
    bridges) can populate with route artifacts.  Defaults to an empty dict
    so callers constructing ``NativeProgram(...)`` remain compatible without
    supplying this field.
    """

    description: str = ""
    """Optional human-readable description."""


# ── Composition graph ────────────────────────────────────────────────
#
# These dataclasses model the static call-tree topology of a compiled
# NativeProgram.  They are derived by a post-compile walk over the
# instruction stream (see :mod:`arnold.pipeline.native.composition`)
# and **do not** require a second AST walk.

from enum import Enum  # noqa: E402


class CompositionNodeKind(str, Enum):
    """Kinds of nodes that can appear in a :class:`NativeCompositionGraph`."""

    PHASE = "phase"
    """A regular step / phase."""

    DECISION = "decision"
    """A branch / decision point."""

    SUBPIPELINE = "subpipeline"
    """A child workflow / sub-pipeline."""

    PARALLEL = "parallel"
    """A statically-bounded parallel fan-out block."""

    PARALLEL_MAP = "parallel_map"
    """A dynamic runtime-list ``parallel_map`` fan-out block."""

    LOOP = "loop"
    """A loop construct (``while`` / guard)."""

    ROOT = "root"
    """Synthetic root node that anchors the graph."""


@dataclass(frozen=True)
class CompositionNode:
    """A single node in a :class:`NativeCompositionGraph`.

    Every node carries a stable *node_id* (unique within the graph),
    a human-readable *label*, and a *kind* that determines which
    metadata fields are meaningful.

    Nodes form a **containment** tree via *parent_id* / *child_ids*
    (for sub-pipeline nesting, not control-flow routing).  Control-flow
    edges are modelled separately via :class:`CompositionEdge`.
    """

    node_id: str
    """Unique stable identifier within the enclosing graph.

    Anchored by ``stable_id`` and call-site identity; never changes
    when the display label is renamed.
    """

    kind: CompositionNodeKind
    """Semantic kind of this node."""

    label: str = ""
    """Human-readable label (display name / phase name)."""

    stable_id: str | None = None
    """Stable semantic identity from the underlying IR, if declared."""

    # ── containment ────────────────────────────────────────────────

    parent_id: str | None = None
    """Node id of the containing parent, or ``None`` for the root node."""

    child_ids: tuple[str, ...] = ()
    """Ordered child node ids (sub-pipeline containment)."""

    # ── path ───────────────────────────────────────────────────────

    path_segments: tuple[str, ...] = ()
    """Stable path segments from the graph root to this node.

    Anchored by ``stable_id`` and call-site identity per the settled
    SD2 decision.  Display names are metadata-only and do not affect
    path segments.
    """

    # ── interfaces ─────────────────────────────────────────────────

    inputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared input interface metadata, if any."""

    outputs_schema: Mapping[str, Any] | None = field(default=None, compare=False, hash=False)
    """Declared output interface metadata, if any."""

    # ── decision metadata ──────────────────────────────────────────

    branch_labels: tuple[str, ...] = ()
    """Ordered branch labels for :attr:`kind` ``decision`` nodes."""

    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    """Set of valid return labels for decision nodes
    (e.g. ``frozenset({'pass', 'fail'})``)."""

    untaken_branches: tuple[str, ...] = ()
    """Branch labels that exist at compile-time but were not taken
    during a particular execution (populated post-execution)."""

    # ── parallel metadata ──────────────────────────────────────────

    parallel_branches: tuple[str, ...] = ()
    """Ordered branch names for :attr:`kind` ``parallel`` nodes."""

    # ── parallel_map metadata ──────────────────────────────────────

    parallel_map_items_ref: str = ""
    """Reference to the runtime collection for ``parallel_map`` nodes
    (e.g. a parameter name or state key)."""

    parallel_map_path_template: str = ""
    """Path template for per-item call-site paths
    (e.g. ``'critique/{item_id}'``)."""

    parallel_map_mapper_name: str = ""
    """Name of the mapper callable for ``parallel_map`` nodes."""

    parallel_map_has_reducer: bool = False
    """Whether the ``parallel_map`` block has a reducer for fan-in."""

    # ── extensibility ──────────────────────────────────────────────

    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)
    """Extensible metadata bag for downstream tooling."""


@dataclass(frozen=True)
class CompositionEdge:
    """A directed edge between two nodes in a :class:`NativeCompositionGraph`.

    Edges represent **control-flow routing** between sibling nodes
    (not containment parent/child relationships).
    """

    source_id: str
    """``node_id`` of the source node."""

    target_id: str
    """``node_id`` of the target node."""

    label: str = ""
    """Edge label (e.g. branch label, ``'halt'``, or stage name)."""

    kind: str = "flow"
    """Edge kind: ``'flow'`` (sequential), ``'branch'`` (decision),
    ``'override'`` (human-gate override), or ``'loop'`` (back-edge)."""


@dataclass(frozen=True)
class NativeCompositionGraph:
    """Static composition graph derived from a compiled :class:`NativeProgram`.

    The graph captures the complete call-tree topology including
    * containment (parent/child for sub-pipelines),
    * control-flow edges (sequential, branch, parallel merge),
    * decision vocabulary and untaken branches,
    * parallel and parallel-map metadata,
    * and declared interfaces.

    Graphs are derived by :func:`arnold.pipeline.native.composition.derive_composition_graph`
    (a post-compile walk over the instruction stream) and can be
    serialized / queried without executing the workflow.

    The serialized form is stored under
    ``NativeProgram.routing_topology["composition_graph"]``
    alongside the existing ``nodes`` / ``routes`` records so that
    downstream validators and consumers remain compatible.
    """

    program_name: str
    """Name of the source :class:`NativeProgram`."""

    root_id: str | None = None
    """``node_id`` of the root node."""

    nodes: Mapping[str, CompositionNode] = field(default_factory=dict, compare=False, hash=False)
    """All nodes in the graph, keyed by ``node_id``."""

    edges: tuple[CompositionEdge, ...] = ()
    """All directed control-flow edges."""

    untaken_route_labels: tuple[str, ...] = ()
    """Route labels present in the static topology that are not taken
    by any edge (informational for audits and static analysis)."""

    # ── query helpers (no runtime state needed) ────────────────────

    def find_node(self, node_id: str) -> CompositionNode | None:
        """Return the node with *node_id*, or ``None``."""
        return self.nodes.get(node_id)

    def children_of(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return containment children of *node_id* in order."""
        node = self.find_node(node_id)
        if node is None:
            return ()
        return tuple(
            child for child_id in node.child_ids
            if (child := self.find_node(child_id)) is not None
        )

    def parent_of(self, node_id: str) -> CompositionNode | None:
        """Return the containment parent of *node_id*, or ``None``."""
        node = self.find_node(node_id)
        if node is None or node.parent_id is None:
            return None
        return self.find_node(node.parent_id)

    def ancestors_of(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return containment ancestors from root to *node_id*'s parent."""
        result: list[CompositionNode] = []
        current = self.parent_of(node_id)
        while current is not None:
            result.append(current)
            current = self.parent_of(current.parent_id) if current.parent_id else None
        result.reverse()
        return tuple(result)

    def descendants_of(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return all containment descendants of *node_id* in depth-first order."""
        result: list[CompositionNode] = []
        _stack = list(self.children_of(node_id))
        while _stack:
            child = _stack.pop(0)
            result.append(child)
            _stack = list(self.children_of(child.node_id)) + _stack
        return tuple(result)

    def path_of(self, node_id: str) -> tuple[str, ...]:
        """Return the stable path segments for *node_id*."""
        node = self.find_node(node_id)
        if node is None:
            return ()
        return node.path_segments

    def nodes_by_kind(self, kind: CompositionNodeKind) -> tuple[CompositionNode, ...]:
        """Return all nodes of the given *kind*."""
        return tuple(n for n in self.nodes.values() if n.kind == kind)

    def outgoing_edges(self, node_id: str) -> tuple[CompositionEdge, ...]:
        """Return all edges whose source is *node_id*."""
        return tuple(e for e in self.edges if e.source_id == node_id)

    def incoming_edges(self, node_id: str) -> tuple[CompositionEdge, ...]:
        """Return all edges whose target is *node_id*."""
        return tuple(e for e in self.edges if e.target_id == node_id)

    # ── serialization ──────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a JSON-compatible dict.

        The output shape is suitable for storage under
        ``routing_topology["composition_graph"]``.
        """
        return {
            "program_name": self.program_name,
            "root_id": self.root_id,
            "nodes": {
                nid: _composition_node_to_dict(n)
                for nid, n in self.nodes.items()
            },
            "edges": [
                {"source_id": e.source_id, "target_id": e.target_id,
                 "label": e.label, "kind": e.kind}
                for e in self.edges
            ],
            "untaken_route_labels": list(self.untaken_route_labels),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NativeCompositionGraph:
        """Deserialize a graph from a dict produced by :meth:`to_dict`."""
        nodes_raw: dict[str, Any] = dict(data.get("nodes", {}))
        nodes: dict[str, CompositionNode] = {}
        for nid, nd in nodes_raw.items():
            if not isinstance(nd, Mapping):
                continue
            nodes[nid] = _composition_node_from_dict(nid, nd)

        edges_raw = data.get("edges")
        edges: tuple[CompositionEdge, ...] = ()
        if isinstance(edges_raw, (list, tuple)):
            edges = tuple(
                CompositionEdge(
                    source_id=str(e.get("source_id", "")),
                    target_id=str(e.get("target_id", "")),
                    label=str(e.get("label", "")),
                    kind=str(e.get("kind", "flow")),
                )
                for e in edges_raw
                if isinstance(e, Mapping)
            )

        return cls(
            program_name=str(data.get("program_name", "")),
            root_id=data.get("root_id") if isinstance(data.get("root_id"), str) else None,
            nodes=nodes,
            edges=edges,
            untaken_route_labels=tuple(
                str(l) for l in (data.get("untaken_route_labels") or ())
            ),
        )


# ── serialization helpers (private) ──────────────────────────────────


def _composition_node_to_dict(node: CompositionNode) -> dict[str, Any]:
    """Serialize a single :class:`CompositionNode` to a JSON-safe dict."""
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "kind": node.kind.value,
        "label": node.label,
    }
    if node.stable_id is not None:
        result["stable_id"] = node.stable_id
    if node.parent_id is not None:
        result["parent_id"] = node.parent_id
    if node.child_ids:
        result["child_ids"] = list(node.child_ids)
    if node.path_segments:
        result["path_segments"] = list(node.path_segments)
    if node.inputs_schema is not None:
        result["inputs_schema"] = dict(node.inputs_schema)
    if node.outputs_schema is not None:
        result["outputs_schema"] = dict(node.outputs_schema)
    if node.branch_labels:
        result["branch_labels"] = list(node.branch_labels)
    if node.decision_vocabulary:
        result["decision_vocabulary"] = sorted(node.decision_vocabulary)
    if node.untaken_branches:
        result["untaken_branches"] = list(node.untaken_branches)
    if node.parallel_branches:
        result["parallel_branches"] = list(node.parallel_branches)
    if node.parallel_map_items_ref:
        result["parallel_map_items_ref"] = node.parallel_map_items_ref
    if node.parallel_map_path_template:
        result["parallel_map_path_template"] = node.parallel_map_path_template
    if node.parallel_map_mapper_name:
        result["parallel_map_mapper_name"] = node.parallel_map_mapper_name
    if node.parallel_map_has_reducer:
        result["parallel_map_has_reducer"] = True
    if node.metadata:
        result["metadata"] = dict(node.metadata)
    return result


def _composition_node_from_dict(node_id: str, data: Mapping[str, Any]) -> CompositionNode:
    """Deserialize a single :class:`CompositionNode` from a dict."""
    kind_raw = data.get("kind", "phase")
    try:
        kind = CompositionNodeKind(kind_raw)
    except ValueError:
        kind = CompositionNodeKind.PHASE

    def _tuple_of_str(val: Any) -> tuple[str, ...]:
        if isinstance(val, (list, tuple)):
            return tuple(str(v) for v in val)
        return ()

    def _frozenset_of_str(val: Any) -> frozenset[str]:
        if isinstance(val, (list, tuple, set, frozenset)):
            return frozenset(str(v) for v in val)
        return frozenset()

    return CompositionNode(
        node_id=node_id,
        kind=kind,
        label=str(data.get("label", "")),
        stable_id=data.get("stable_id") if isinstance(data.get("stable_id"), str) else None,
        parent_id=data.get("parent_id") if isinstance(data.get("parent_id"), str) else None,
        child_ids=_tuple_of_str(data.get("child_ids")),
        path_segments=_tuple_of_str(data.get("path_segments")),
        inputs_schema=(
            dict(data["inputs_schema"])
            if isinstance(data.get("inputs_schema"), Mapping) else None
        ),
        outputs_schema=(
            dict(data["outputs_schema"])
            if isinstance(data.get("outputs_schema"), Mapping) else None
        ),
        branch_labels=_tuple_of_str(data.get("branch_labels")),
        decision_vocabulary=_frozenset_of_str(data.get("decision_vocabulary")),
        untaken_branches=_tuple_of_str(data.get("untaken_branches")),
        parallel_branches=_tuple_of_str(data.get("parallel_branches")),
        parallel_map_items_ref=str(data.get("parallel_map_items_ref", "")),
        parallel_map_path_template=str(data.get("parallel_map_path_template", "")),
        parallel_map_mapper_name=str(data.get("parallel_map_mapper_name", "")),
        parallel_map_has_reducer=bool(data.get("parallel_map_has_reducer", False)),
        metadata=dict(data.get("metadata", {})),
    )
