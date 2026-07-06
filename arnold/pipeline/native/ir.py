"""Frozen IR dataclasses for the native Python pipeline runtime.

These types represent the intermediate representation produced by
decorator metadata and consumed by the compiler, graph projection,
and runtime.  They are deliberately neutral — no runtime evaluation
logic lives here.

**Path addressing contract**

Native paths use ``/`` as the formal delimiter and form a stable tree
rooted at ``root``.  Every path segment carries a **machine identity**
(a canonical, stable name that MUST NOT contain ``/``) and an optional
**display label** (a human-readable string with no delimiter restriction).
Stable path addressing uses machine identities only; display labels are
metadata for human consumption and MUST NOT be used for addressing,
routing, or persistence.

Child paths are formed by appending authored ``call_site_path`` segments
separated by ``/``:

  ``root/validate/sub_0/item_2``

where ``root`` is the default root path, ``validate`` is a child-workflow
call site, ``sub_0`` is a nested child, and ``item_2`` is a dynamic-map
item index.

Ownership:
    The IR types represent structure only.  Native ``.pypeline`` modules
    and named native subworkflows own the source-visible product topology.
    Boundary contracts and boundary receipts declare and check durable
    effects — they are not topology-bearing and do not influence the IR
    shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet, Mapping, Protocol, runtime_checkable

# ── Path constants ──────────────────────────────────────────────────

PATH_DELIMITER: str = "/"
"""Formal path delimiter for stable tree-shaped paths.

Segments joined by this delimiter form the machine-identity path.
Individual segments MUST NOT contain this character.
"""

ROOT_PATH: str = "root"
"""Default root path for all native pipeline path trees."""

# ── Protocol ────────────────────────────────────────────────────────

@runtime_checkable
class NativeInvocable(Protocol):
    """Structural metadata shared by native steps and workflows."""

    name: str
    stable_id: str | None
    inputs_schema: Mapping[str, Any] | None
    outputs_schema: Mapping[str, Any] | None


# ── Path primitives ─────────────────────────────────────────────────

@dataclass(frozen=True)
class PathSegment:
    """A single segment in a stable tree-shaped path.

    Each segment carries a **machine identity** (the canonical stable
    name used for addressing, routing, and persistence) and an optional
    **display label** (a human-readable label with no delimiter
    restrictions).

    The machine identity MUST NOT contain the path delimiter ``/``.
    Display labels MAY contain any characters.
    """

    identity: str
    """Stable machine identity — the canonical name for this segment.

    Used for addressing, routing, and persistence.  Must not contain
    the path delimiter (``/``).
    """

    label: str = ""
    """Optional human-readable display label.

    May contain any characters, including ``/``.  This label is metadata
    only and MUST NOT be used for addressing or routing.
    """

    def __str__(self) -> str:
        return self.identity


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

    # ── Side-effect metadata (M1) ──

    operation: str | None = None
    """For side-effecting phases: canonical operation from the effect
    taxonomy (e.g. ``'file_write'``, ``'git_commit'``).  ``None`` for pure
    phases."""

    target: str | None = None
    """For side-effecting phases: stable target identifier for the
    operation (e.g. a relpath, branch name).  ``None`` for pure phases."""

    idempotency_key: str | None = None
    """For side-effecting phases: explicit or derived idempotency key.
    ``None`` for pure phases."""

    effect_class: str | None = None
    """For side-effecting phases: effect class from the taxonomy
    (e.g. ``'filesystem_mutation'``, ``'git_repo_mutation'``).
    ``None`` for pure phases."""


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

    The ``stable_id`` provides a stable machine identity that survives
    code renames — it is the preferred identifier for loop nodes in
    topology graphs and trace paths.
    """

    guard: Callable[..., bool] = field(compare=False, hash=False)
    """Callable that returns True to continue looping."""

    body: Callable[..., Any] = field(compare=False, hash=False)
    """Callable executed on each loop iteration."""

    name: str = ""
    """Optional name for diagnostics."""

    stable_id: str | None = None
    """Stable machine identity for this loop construct.

    Used as the canonical loop node identity in topology graphs and
    path segments.  When ``None``, the ``name`` field serves as a
    fallback for identity purposes.
    """


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

    collection_schema: Mapping[str, Any] | None = field(
        default=None, compare=False, hash=False
    )
    """Declared schema of the runtime collection items.

    When non-``None``, this describes the expected shape of each item
    in the runtime collection (e.g. a JSON Schema dict).  This is
    metadata for static topology queries and tooling — the runtime
    does not enforce it by default.

    When ``None``, no item schema has been declared.
    """

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

    # ── Side-effect metadata (M1 — side-effect reconcile & idempotency) ──

    operation: str | None = None
    """For side-effecting phase ops: the canonical operation type from the
    effect taxonomy (e.g. ``'file_write'``, ``'git_commit'``).  ``None`` for
    pure steps and non-phase instructions."""

    target: str | None = None
    """For side-effecting phase ops: a stable target identifier for the
    operation (e.g. a relpath, branch name, or artifact logical-root id).
    ``None`` when no target is declared or the instruction is pure."""

    idempotency_key: str | None = None
    """For side-effecting phase ops: the idempotency key used by the effect
    ledger for deduplication and reconciliation.  When explicitly supplied via
    the decorator this is used verbatim; otherwise derived from
    ``(step_path, operation, target)`` at compile time.  ``None`` for pure
    steps and non-phase instructions."""

    effect_class: str | None = None
    """For side-effecting phase ops: the effect class from the taxonomy
    (e.g. ``'filesystem_mutation'``, ``'git_repo_mutation'``).  ``None`` for
    pure steps and non-phase instructions."""


@dataclass(frozen=True)
class NativeProgram:
    """A complete compiled native pipeline program.

    The ``instructions`` tuple is ordered by program counter (``pc``).
    ``phases``, ``decisions``, and ``loop_guards`` mirror the
    :class:`NativePipeline` IR fields for consumption by graph
    projection.

    The ``topology`` field carries the optional static topology /
    derived graph produced at compile time.  When populated, it
    provides a queryable structural graph without requiring execution.
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

    topology: Any = field(default=None, compare=False, hash=False)
    """Optional static topology / derived graph for this program.

    Populated at compile time by :func:`derive_topology`.  When
    non-``None``, this is a :class:`NativeTopology` instance that
    provides a queryable structural graph of nodes and edges without
    requiring execution.

    Excluded from equality/hash.
    """

    description: str = ""
    """Optional human-readable description."""


# ── Static topology / derived graph IR ───────────────────────────────

@dataclass(frozen=True)
class TopologyNode:
    """A single node in the static topology / derived graph.

    Nodes represent authored structural elements of a native pipeline
    program: phases, decisions, loop constructs, child workflow call
    sites, and dynamic-map templates.  The topology is derived at
    compile time and can be queried without execution.
    """

    node_id: str
    """Unique node identifier within the topology.

    Typically derived from the node's stable path (machine identity)
    to remain unique even when display labels collide.
    """

    kind: str
    """Node kind.

    One of:

    - ``'phase'`` — a single step/phase
    - ``'decision'`` — a decision point with branch labels
    - ``'loop'`` — a loop construct with a guard
    - ``'child_workflow'`` — a call site for a child workflow/subpipeline
    - ``'dynamic_map'`` — a dynamic parallel-map fan-out template
    """

    label: str = ""
    """Human-readable display label for this node."""

    path: str = ""
    """Stable tree path for this node (e.g. ``'root/step_A/sub_1'``).

    Uses ``/`` as the delimiter and machine-identity segments only.
    """

    stable_id: str | None = None
    """Stable semantic identity declared on the decorated callable, if any."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """Kind-specific metadata.

    For ``'phase'`` nodes: ``inputs_schema``, ``outputs_schema``.
    For ``'decision'`` nodes: ``vocabulary`` (list of branch labels),
    ``decision_routes``, ``human_gate``, ``choices``.
    For ``'loop'`` nodes: ``loop_stable_id``, ``guard_name``.
    For ``'child_workflow'`` nodes: ``child_name``, ``child_stable_id``,
    ``inputs_schema``, ``outputs_schema``, ``output_bindings``.
    For ``'dynamic_map'`` nodes: ``dynamic_map_metadata``
    (:class:`DynamicMapMetadata`).
    """


@dataclass(frozen=True)
class TopologyEdge:
    """A directed edge in the static topology.

    Edges represent control-flow transitions, child-workflow
    containment, and dynamic-map item template edges.
    """

    source: str
    """Source node ID."""

    target: str
    """Target node ID."""

    label: str = ""
    """Edge label.

    For control-flow edges this is the branch label (e.g. ``'pass'``,
    ``'fail'``) or ``'next'`` for unconditional fall-through.
    For child-workflow edges this is the call-site name.
    For dynamic-map edges this is the item path template.
    """

    kind: str = "control_flow"
    """Edge kind.

    One of:

    - ``'control_flow'`` — sequential or branch transition
    - ``'child_workflow'`` — parent → child workflow containment
    - ``'dynamic_map_item'`` — dynamic-map → per-item template edge
    """

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """Edge-specific metadata, if any."""


@dataclass(frozen=True)
class DynamicMapMetadata:
    """Static metadata for a dynamic parallel_map node.

    Captures the compile-time information about a dynamic fan-out
    so the topology graph can describe the template without executing
    the workflow.
    """

    items_ref: str = ""
    """Reference to the runtime collection — a parameter name or
    state key that resolves to an iterable at execution time."""

    mapper_name: str = ""
    """Name of the mapper callable (for diagnostics and trace emission)."""

    path_template: str = ""
    """Path template for per-item call-site paths
    (e.g. ``'critique/{item_id}'``)."""

    collection_schema: Mapping[str, Any] | None = None
    """Schema of the collection items, if declared."""

    reducer_name: str = ""
    """Name of the reducer callable, if any."""

    fan_in: bool = False
    """Whether a reducer is present for fan-in."""


@dataclass(frozen=True)
class NativeTopology:
    """Static topology / derived graph for a native pipeline program.

    Built from a :class:`NativeProgram` at compile time without
    execution.  Provides a queryable structural graph of the workflow's
    nodes and edges — the canonical answer to "what does this workflow
    contain?"

    This is the **primary public name** for the topology object.
    ``DerivedGraph`` is available as a compatibility alias.
    """

    name: str = ""
    """Name of the pipeline this topology describes."""

    nodes: tuple[TopologyNode, ...] = ()
    """Nodes in the topology, in declaration order."""

    edges: tuple[TopologyEdge, ...] = ()
    """Edges in the topology."""

    root_path: str = ROOT_PATH
    """Root path for the topology tree."""

    path_delimiter: str = PATH_DELIMITER
    """Path delimiter used throughout this topology."""

    # ── Query helpers ──────────────────────────────────────────────

    def _node_map(self) -> dict[str, TopologyNode]:
        """Return a dict mapping ``node_id`` → :class:`TopologyNode`."""
        return {node.node_id: node for node in self.nodes}

    def _edge_targets_by_source(self, kind: str) -> dict[str, list[str]]:
        """Return ``{source_id: [target_id, ...]}`` for edges of *kind*."""
        result: dict[str, list[str]] = {}
        for edge in self.edges:
            if edge.kind == kind:
                result.setdefault(edge.source, []).append(edge.target)
        return result

    def _edge_sources_by_target(self, kind: str) -> dict[str, str]:
        """Return ``{target_id: source_id}`` for edges of *kind*.

        When multiple edges of the same kind point to the same target,
        the last one wins (consistent with single-parent semantics for
        containment edges).
        """
        result: dict[str, str] = {}
        for edge in self.edges:
            if edge.kind == kind:
                result[edge.target] = edge.source
        return result

    def child(self, node_id: str) -> tuple[TopologyNode, ...]:
        """Return the direct children of *node_id*.

        Children are discovered via two complementary strategies:

        1. **Edge-based** — edges whose ``source`` is *node_id* and
           ``kind`` is ``'child_workflow'`` or ``'dynamic_map_item'``.

        2. **Path-based** — nodes whose ``path`` is an immediate
           child of this node's path in the tree (one additional
           segment separated by :attr:`path_delimiter`).

        Results are deduplicated and returned in declaration order.
        """
        node_map = self._node_map()
        node = node_map.get(node_id)
        if node is None:
            return ()

        seen: set[str] = set()

        # Strategy 1: edge-based containment
        containment_kinds = ("child_workflow", "dynamic_map_item")
        for kind in containment_kinds:
            targets = self._edge_targets_by_source(kind).get(node_id, [])
            for target_id in targets:
                if target_id not in seen and target_id in node_map:
                    seen.add(target_id)

        # Strategy 2: path-based immediate children
        prefix = node.path + self.path_delimiter
        for candidate in self.nodes:
            if candidate.node_id in seen:
                continue
            if not candidate.path.startswith(prefix):
                continue
            remainder = candidate.path[len(prefix):]
            if self.path_delimiter not in remainder:
                seen.add(candidate.node_id)

        return tuple(
            node_map[nid] for nid in seen if nid in node_map
        )

    def parent(self, node_id: str) -> TopologyNode | None:
        """Return the parent node of *node_id*, or ``None``.

        Parent is discovered via two complementary strategies:

        1. **Edge-based** — edges whose ``target`` is *node_id* and
           ``kind`` is ``'child_workflow'`` or ``'dynamic_map_item'``.

        2. **Path-based** — the node whose ``path`` is the direct
           parent prefix of this node's path.

        When both strategies produce candidates, edge-based wins.
        """
        node_map = self._node_map()
        node = node_map.get(node_id)
        if node is None:
            return None

        # Strategy 1: edge-based containment (preferred)
        containment_kinds = ("child_workflow", "dynamic_map_item")
        for kind in containment_kinds:
            sources = self._edge_sources_by_target(kind)
            if node_id in sources:
                return node_map.get(sources[node_id])

        # Strategy 2: path-based
        segments = node.path.split(self.path_delimiter)
        if len(segments) <= 1:
            return None
        parent_path = self.path_delimiter.join(segments[:-1])
        return node_map.get(parent_path)

    def ancestors(self, node_id: str) -> tuple[TopologyNode, ...]:
        """Return all ancestor nodes from immediate parent up to root.

        Ancestors are returned in order from nearest to farthest
        (parent, grandparent, ...).  The root-most ancestor is last.
        """
        result: list[TopologyNode] = []
        visited: set[str] = {node_id}
        current = self.parent(node_id)
        while current is not None:
            if current.node_id in visited:
                break  # safety: cycle guard
            visited.add(current.node_id)
            result.append(current)
            current = self.parent(current.node_id)
        return tuple(result)

    def descendants(self, node_id: str) -> tuple[TopologyNode, ...]:
        """Return all descendant nodes via BFS over children.

        Descendants are returned in breadth-first order.
        """
        node_map = self._node_map()
        if node_id not in node_map:
            return ()

        result: list[TopologyNode] = []
        visited: set[str] = {node_id}
        queue: list[str] = [node_id]

        while queue:
            current_id = queue.pop(0)
            for child_node in self.child(current_id):
                if child_node.node_id not in visited:
                    visited.add(child_node.node_id)
                    result.append(child_node)
                    queue.append(child_node.node_id)

        return tuple(result)

    def lookup_by_stable_id(self, stable_id: str) -> tuple[TopologyNode, ...]:
        """Return all nodes whose :attr:`TopologyNode.stable_id` matches."""
        if not stable_id:
            return ()
        return tuple(
            node for node in self.nodes if node.stable_id == stable_id
        )

    def lookup_by_path_prefix(self, prefix: str) -> tuple[TopologyNode, ...]:
        """Return nodes whose :attr:`TopologyNode.path` starts with *prefix*.

        The prefix comparison is a simple ``str.startswith`` on the
        machine-identity path.  Results are returned in declaration
        order.
        """
        if not prefix:
            return ()
        return tuple(
            node for node in self.nodes if node.path.startswith(prefix)
        )


# Compatibility alias — NativeTopology is the canonical name.
DerivedGraph = NativeTopology
"""Compatibility alias for :class:`NativeTopology`.

Prefer ``NativeTopology`` in new code.  This alias exists so existing
references to ``DerivedGraph`` do not break.
"""


# ── Composition graph IR (pre-existing, consumed by composition.py) ──

# CompositionNodeKind constants — simple string-based kind identifiers
# used by the composition graph derivation in composition.py.
@dataclass(frozen=True)
class _CompositionNodeKindConstants:
    ROOT: str = "root"
    PHASE: str = "phase"
    DECISION: str = "decision"
    LOOP: str = "loop"
    SUBPIPELINE: str = "subpipeline"
    PARALLEL: str = "parallel"
    PARALLEL_MAP: str = "parallel_map"


CompositionNodeKind = _CompositionNodeKindConstants()
"""Node-kind constants for the composition graph."""


@dataclass(frozen=True)
class CompositionNode:
    """A single node in the composition graph.

    Pre-existing type consumed by ``composition.py``.  New code
    should also consider :class:`TopologyNode` for topology queries.
    """

    node_id: str
    """Unique node identifier."""

    kind: str
    """Node kind (one of ``CompositionNodeKind`` constants)."""

    label: str = ""
    """Human-readable label."""

    stable_id: str | None = None
    """Stable semantic identity, if declared."""

    parent_id: str | None = None
    """Parent node ID, if any."""

    path_segments: tuple[str, ...] = ()
    """Stable path segments from root to this node."""

    inputs_schema: Mapping[str, Any] | None = None
    """Declared input schema, if any."""

    outputs_schema: Mapping[str, Any] | None = None
    """Declared output schema, if any."""

    child_ids: tuple[str, ...] = ()
    """Ordered child node IDs."""

    # ── Decision-specific ──────────────────────────────────────

    branch_labels: tuple[str, ...] = ()
    """For decision nodes: all branch labels (taken + untaken)."""

    decision_vocabulary: FrozenSet[str] = field(default_factory=frozenset)
    """For decision nodes: the full decision vocabulary."""

    untaken_branches: tuple[str, ...] = ()
    """For decision nodes: branch labels with no wired route."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """For loop-decision nodes: loop region metadata
    (``body_start_pc``, ``exit_pc``, ``back_jump_pc``)."""

    # ── Parallel-specific ──────────────────────────────────────

    parallel_branches: tuple[str, ...] = ()
    """For parallel nodes: ordered branch names."""

    parallel_map_has_reducer: bool = False
    """For parallel/parallel_map nodes: whether a reducer is present."""

    # ── Parallel-map-specific ──────────────────────────────────

    parallel_map_items_ref: str = ""
    """For parallel_map nodes: reference to the runtime collection."""

    parallel_map_path_template: str = ""
    """For parallel_map nodes: path template for per-item call sites."""

    parallel_map_mapper_name: str = ""
    """For parallel_map nodes: name of the mapper callable."""


@dataclass(frozen=True)
class CompositionEdge:
    """A directed edge in the composition graph.

    Pre-existing type consumed by ``composition.py``.
    """

    source_id: str
    """Source node ID."""

    target_id: str
    """Target node ID."""

    label: str = ""
    """Edge label (branch name, flow kind, etc.)."""

    kind: str = ""
    """Edge kind (``'flow'``, ``'branch'``, ``'loop'``, etc.)."""


@dataclass(frozen=True)
class NativeCompositionGraph:
    """Complete composition graph for a native pipeline program.

    Pre-existing type consumed by ``composition.py``.  Contains nodes
    keyed by ID, ordered edges, and untaken route labels.  Supports
    serialization via ``to_dict()`` / ``from_dict()``.
    """

    program_name: str
    """Name of the pipeline described by this graph."""

    root_id: str
    """ID of the root node."""

    nodes: Mapping[str, CompositionNode] = field(default_factory=dict)
    """Nodes keyed by node ID."""

    edges: tuple[CompositionEdge, ...] = ()
    """Edges in the graph."""

    untaken_route_labels: tuple[str, ...] = ()
    """Decision branch labels that exist in the vocabulary but have
    no wired route in the compiled program."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for embedding in routing_topology."""
        from dataclasses import asdict as _asdict
        return {
            "program_name": self.program_name,
            "root_id": self.root_id,
            "nodes": {
                nid: _asdict(node) for nid, node in self.nodes.items()
            },
            "edges": [_asdict(e) for e in self.edges],
            "untaken_route_labels": list(self.untaken_route_labels),
        }

    def nodes_by_kind(self, kind: str) -> tuple[CompositionNode, ...]:
        """Return all nodes of the given *kind*."""
        return tuple(
            node for node in self.nodes.values() if node.kind == kind
        )

    # ── Query helpers ──────────────────────────────────────────────

    def child(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return the direct children of *node_id* via :attr:`CompositionNode.child_ids`.

        Returns an empty tuple when *node_id* is unknown or has no children.
        """
        node = self.nodes.get(node_id)
        if node is None:
            return ()
        return tuple(
            self.nodes[child_id]
            for child_id in node.child_ids
            if child_id in self.nodes
        )

    def parent(self, node_id: str) -> CompositionNode | None:
        """Return the parent node of *node_id*, or ``None``.

        Uses :attr:`CompositionNode.parent_id` for direct lookup.
        """
        node = self.nodes.get(node_id)
        if node is None or node.parent_id is None:
            return None
        return self.nodes.get(node.parent_id)

    def ancestors(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return all ancestor nodes from immediate parent up to root.

        Ancestors are returned in order from nearest to farthest
        (parent, grandparent, ...).  The root-most ancestor is last.
        """
        result: list[CompositionNode] = []
        visited: set[str] = {node_id}
        current = self.parent(node_id)
        while current is not None:
            if current.node_id in visited:
                break  # safety: cycle guard
            visited.add(current.node_id)
            result.append(current)
            current = self.parent(current.node_id)
        return tuple(result)

    def descendants(self, node_id: str) -> tuple[CompositionNode, ...]:
        """Return all descendant nodes via BFS over children.

        Descendants are returned in breadth-first order.
        """
        if node_id not in self.nodes:
            return ()

        result: list[CompositionNode] = []
        visited: set[str] = {node_id}
        queue: list[str] = [node_id]

        while queue:
            current_id = queue.pop(0)
            for child_node in self.child(current_id):
                if child_node.node_id not in visited:
                    visited.add(child_node.node_id)
                    result.append(child_node)
                    queue.append(child_node.node_id)

        return tuple(result)

    def lookup_by_stable_id(self, stable_id: str) -> tuple[CompositionNode, ...]:
        """Return all nodes whose :attr:`CompositionNode.stable_id` matches."""
        if not stable_id:
            return ()
        return tuple(
            node for node in self.nodes.values()
            if node.stable_id == stable_id
        )

    def lookup_by_path_prefix(self, prefix: str) -> tuple[CompositionNode, ...]:
        """Return nodes whose stable path starts with *prefix*.

        The stable path is built by joining :attr:`CompositionNode.path_segments`
        with ``/``.  The prefix comparison is a simple ``str.startswith``.
        Results are returned in stable path order.
        """
        if not prefix:
            return ()
        matching = [
            node
            for node in self.nodes.values()
            if "/".join(node.path_segments).startswith(prefix)
        ]
        matching.sort(key=lambda n: "/".join(n.path_segments))
        return tuple(matching)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> NativeCompositionGraph:
        """Deserialize from a plain dict."""
        return cls(
            program_name=str(raw.get("program_name", "")),
            root_id=str(raw.get("root_id", "")),
            nodes={
                str(nid): CompositionNode(
                    node_id=str(node.get("node_id", "")),
                    kind=str(node.get("kind", "")),
                    label=str(node.get("label", "")),
                    stable_id=node.get("stable_id"),
                    parent_id=node.get("parent_id"),
                    path_segments=tuple(node.get("path_segments", ())),
                    inputs_schema=node.get("inputs_schema"),
                    outputs_schema=node.get("outputs_schema"),
                    child_ids=tuple(node.get("child_ids", ())),
                    branch_labels=tuple(node.get("branch_labels", ())),
                    decision_vocabulary=frozenset(node.get("decision_vocabulary", ())),
                    untaken_branches=tuple(node.get("untaken_branches", ())),
                    metadata=dict(node.get("metadata", {})),
                    parallel_branches=tuple(node.get("parallel_branches", ())),
                    parallel_map_has_reducer=bool(node.get("parallel_map_has_reducer", False)),
                    parallel_map_items_ref=str(node.get("parallel_map_items_ref", "")),
                    parallel_map_path_template=str(node.get("parallel_map_path_template", "")),
                    parallel_map_mapper_name=str(node.get("parallel_map_mapper_name", "")),
                )
                for nid, node in raw.get("nodes", {}).items()
            },
            edges=tuple(
                CompositionEdge(
                    source_id=str(e.get("source_id", "")),
                    target_id=str(e.get("target_id", "")),
                    label=str(e.get("label", "")),
                    kind=str(e.get("kind", "")),
                )
                for e in raw.get("edges", [])
            ),
            untaken_route_labels=tuple(
                str(label) for label in raw.get("untaken_route_labels", ())
            ),
        )
