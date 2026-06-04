"""Neutral control-flow and graph-shape validator for pipeline definitions.

Pure graph-shape validation with zero megaplan imports.  Checks:

* ``Pipeline.entry`` names a real stage in ``Pipeline.stages``;
* every :class:`Edge`.``target`` names a real stage or the reserved
  terminal ``"halt"``;
* ``"halt"`` is never used as an :class:`Edge`.``label`` (it is reserved
  as a target only), except for the conventional ``label='halt' target='halt'``
  terminal pair;
* every stage that emits at least one ``kind == "decision"`` edge must cover
  the declared ``decision_vocabulary`` when non-empty;
* every stage that emits at least one ``kind == "override"`` edge must cover
  the declared ``override_vocabulary`` when non-empty;
* no stage is unreachable from :attr:`Pipeline.entry`;
* cycles are detected — a cycle is valid only when at least one edge
  in the cycle targets a stage with a ``loop_condition`` (guarded cycle);
  unguarded cycles are flagged as defects.
* every stage's prompt/resource dependencies are checked — a non-None
  ``prompt_key`` referencing an unknown resource bundle is flagged.

All access to stage/edge/pipeline fields is duck-typed via ``getattr``
so both Arnold and Megaplan shapes are accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class Diagnostics:
    """Result of :func:`validate` over a pipeline.

    Each defect is a short human-readable string naming the offending
    stage/edge so ``pipelines check`` can echo it on a non-zero exit.
    """

    defects: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.defects


@dataclass
class ValidationOptions:
    """Options controlling validation behaviour.

    ``decision_vocabulary_fallback``: when a stage has no declared
    ``decision_vocabulary`` but has decision edges, use this fallback
    set.  The default is the canonical planning vocabulary.  Set to
    ``None`` to suppress fallback (only declared vocabularies are checked).

    ``override_vocabulary_fallback``: same for override edges.

    ``detect_cycles``: when ``True`` (default), perform DFS-based
    cycle detection and flag unguarded cycles.
    """

    decision_vocabulary_fallback: frozenset[str] | None = field(
        default_factory=lambda: frozenset(
            {"proceed", "iterate", "tiebreaker", "escalate"}
        )
    )
    override_vocabulary_fallback: frozenset[str] | None = None
    detect_cycles: bool = True


# ── Duck-typed accessors ──────────────────────────────────────────────────


def _stage_edges(stage: Any) -> tuple:
    """Return the tuple of edges from *stage* (duck-typed)."""
    return tuple(getattr(stage, "edges", ()) or ())


def _stage_name(stage: Any) -> str:
    return getattr(stage, "name", "?")


def _stage_decision_vocabulary(
    stage: Any, options: ValidationOptions
) -> frozenset[str] | None:
    """Return the stage's decision vocabulary or fallback."""
    declared: frozenset[str] = frozenset(
        getattr(stage, "decision_vocabulary", frozenset()) or frozenset()
    )
    if declared:
        return declared
    return options.decision_vocabulary_fallback


def _stage_override_vocabulary(
    stage: Any, options: ValidationOptions
) -> frozenset[str] | None:
    """Return the stage's override vocabulary or fallback."""
    declared: frozenset[str] = frozenset(
        getattr(stage, "override_vocabulary", frozenset()) or frozenset()
    )
    if declared:
        return declared
    return options.override_vocabulary_fallback


# ── Validation ────────────────────────────────────────────────────────────


def validate_control_flow(
    pipeline: Any, options: ValidationOptions | None = None
) -> Diagnostics:
    """Run control-flow validation over *pipeline*.

    Checks: entry existence, edge targets, reserved halt label,
    decision/override vocabulary coverage, reachability from entry,
    and unguarded cycle detection.

    Returns a :class:`Diagnostics` whose ``defects`` list is empty iff
    every check passes.
    """
    if options is None:
        options = ValidationOptions()

    diag = Diagnostics()
    stages: Mapping[str, Any] = getattr(pipeline, "stages", {})
    entry: str = getattr(pipeline, "entry", "")
    stage_names = set(stages.keys())

    # ── entry check ──────────────────────────────────────────────────
    if entry not in stage_names:
        diag.defects.append(
            f"entry stage {entry!r} not present in pipeline.stages"
        )

    for stage_name, stage in stages.items():
        edges = _stage_edges(stage)
        # Match both kind='gate' (legacy) and kind='decision' (current)
        decision_edges = [e for e in edges if getattr(e, "kind", "normal") in ("gate", "decision")]
        override_edges_list = [e for e in edges if getattr(e, "kind", "normal") == "override"]

        for edge in edges:
            label = getattr(edge, "label", "")
            target = getattr(edge, "target", "")

            # 'halt' is a reserved target sentinel; flagged as a label
            # only when the edge does NOT also resolve to the terminal target.
            if label == "halt" and target != "halt":
                diag.defects.append(
                    f"stage {stage_name!r}: edge uses reserved label 'halt' "
                    "(halt is a target sentinel, not an edge label)"
                )
            if target != "halt" and target not in stage_names:
                diag.defects.append(
                    f"stage {stage_name!r}: edge {label!r} targets "
                    f"unknown stage {target!r}"
                )

        # ── decision vocabulary check ────────────────────────────────
        if decision_edges:
            vocab = _stage_decision_vocabulary(stage, options)
            if vocab is not None:
                covered: set[str] = set()
                for edge in decision_edges:
                    kind = getattr(edge, "kind", "normal")
                    label = getattr(edge, "label", "")
                    # label is the decision key for kind='decision';
                    # recommendation is checked for legacy kind='gate' edges.
                    key = label if kind == "decision" else getattr(edge, "recommendation", None)
                    if not key:
                        diag.defects.append(
                            f"stage {stage_name!r}: decision edge {label!r} has "
                            "no recommendation set (label/recommendation is None)"
                        )
                    elif key not in vocab:
                        diag.defects.append(
                            f"stage {stage_name!r}: decision edge {label!r} has "
                            f"decision key {key!r} not in "
                            f"declared vocabulary {sorted(vocab)}"
                        )
                    else:
                        covered.add(key)
                missing = vocab - covered
                if missing:
                    diag.defects.append(
                        f"stage {stage_name!r}: decision vocabulary "
                        f"{sorted(vocab)} declares {sorted(missing)} "
                        f"but no decision edge covers them"
                    )

        # ── override vocabulary check ────────────────────────────────
        if override_edges_list:
            vocab = _stage_override_vocabulary(stage, options)
            if vocab is not None:
                covered: set[str] = set()
                for edge in override_edges_list:
                    label = getattr(edge, "label", "")
                    # label format is "override <action>"
                    if not label.startswith("override "):
                        diag.defects.append(
                            f"stage {stage_name!r}: override edge {label!r} "
                            "does not follow 'override <action>' label format"
                        )
                        continue
                    action = label[len("override "):]
                    if action not in vocab:
                        diag.defects.append(
                            f"stage {stage_name!r}: override edge {label!r} has "
                            f"action {action!r} not in "
                            f"declared override_vocabulary {sorted(vocab)}"
                        )
                    else:
                        covered.add(action)
                missing = vocab - covered
                if missing:
                    diag.defects.append(
                        f"stage {stage_name!r}: override vocabulary "
                        f"{sorted(vocab)} declares {sorted(missing)} "
                        f"but no override edge covers them"
                    )

    # ── Reachability from entry ──────────────────────────────────────
    if entry in stage_names:
        reachable: set[str] = set()
        frontier = [entry]
        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stage = stages.get(current)
            if stage is None:
                continue
            for edge in _stage_edges(stage):
                target = getattr(edge, "target", "")
                if target != "halt" and target in stage_names:
                    frontier.append(target)
        unreachable = stage_names - reachable
        for name in sorted(unreachable):
            diag.defects.append(
                f"stage {name!r} is unreachable from entry {entry!r}"
            )

    # ── Unguarded cycle detection ────────────────────────────────────
    if options.detect_cycles:
        _detect_unguarded_cycles(stages, entry, diag)

    return diag


def validate(
    pipeline: Any, options: ValidationOptions | None = None
) -> Diagnostics:
    """Run the full graph-shape validation over *pipeline*.

    Delegates to :func:`validate_control_flow`, :func:`validate_dataflow_paths`,
    and :func:`validate_resource_dependencies`.

    Returns a :class:`Diagnostics` whose ``defects`` list is empty iff
    every check passes.
    """
    diag = validate_control_flow(pipeline, options)
    # Merge dataflow defects — dataflow validation runs even when
    # control-flow defects exist so callers get the full picture.
    df_diag = validate_dataflow_paths(pipeline, options)
    diag.defects.extend(df_diag.defects)
    # Merge prompt/resource defects
    res_diag = validate_resource_dependencies(pipeline, options)
    diag.defects.extend(res_diag.defects)
    return diag


# ── Dataflow validation ───────────────────────────────────────────────────


def _normalize_dependency(
    dep: Any,
) -> tuple[str, bool, bool, bool]:
    """Normalize a single dependency item into (name, optional, external, late_bound).

    * Plain strings become required wildcard refs (``optional=False``,
      ``external=False``, ``late_bound=False``) with content type ``*/*``.
    * :class:`ReadRef`, :class:`WriteRef`, and :class:`BindingRef` instances
      preserve their metadata.
    * ``Port`` and ``PortRef`` instances expose ``name`` / ``port_name``
      and are treated as required unless tainted optional.

    Returns ``(name, optional, external, late_bound)``.
    """
    if isinstance(dep, str):
        # Plain string — required wildcard ref
        return (dep, False, False, False)

    # Duck-type dataclass wrappers — check known field names
    name: str | None = getattr(dep, "name", None)
    optional: bool = bool(getattr(dep, "optional", False))
    external: bool = bool(getattr(dep, "external", False))
    late_bound: bool = bool(getattr(dep, "late_bound", False))

    # PortRef uses port_name instead of name
    if name is None:
        name = getattr(dep, "port_name", None)

    if name is None:
        # Fallback: try string coercion
        name = str(dep)

    return (name, optional, external, late_bound)


def validate_dataflow_paths(
    pipeline: Any, options: ValidationOptions | None = None
) -> Diagnostics:
    """Run path-sensitive dataflow validation over *pipeline*.

    Uses deterministic fixed-point analysis over the graph:

    1. Track available artifact/port names as sets per stage.
    2. At join points (stages with multiple predecessors), use
       **intersection** of predecessor availability — a consume is valid
       only when every incoming path provides it.
    3. Normalize reads/writes/produces/consumes via
       :func:`_normalize_dependency`: plain strings become required
       wildcard refs, while ``ReadRef``/``WriteRef``/``BindingRef``
       preserve their metadata.
    4. ``pipeline.binding_map`` entries and explicit ``external`` /
       ``late_bound`` refs are treated as satisfiers (they are provided
       from outside the pipeline or at runtime).
    5. Emits deterministic defects naming the stage, the dependency,
       and at least one predecessor route through which the dependency
       is missing.

    Returns a :class:`Diagnostics` whose ``defects`` list is empty iff
    every dataflow dependency is satisfiable.
    """
    if options is None:
        options = ValidationOptions()

    diag = Diagnostics()
    stages: dict[str, Any] = dict(getattr(pipeline, "stages", {}) or {})
    entry: str = getattr(pipeline, "entry", "")
    binding_map: dict | None = getattr(pipeline, "binding_map", None)

    if not stages or entry not in stages:
        # Control-flow validation already flags these; nothing to do here.
        return diag

    # ── Build predecessor map ────────────────────────────────────────────
    predecessors: dict[str, list[str]] = {name: [] for name in stages}
    for src_name, stage in stages.items():
        for edge in _stage_edges(stage):
            target = getattr(edge, "target", "")
            if target != "halt" and target in stages:
                predecessors[target].append(src_name)

    def _stage_produces(stage: Any) -> list[tuple[str, bool, bool, bool]]:
        """Return the effective set of names that *stage* produces."""
        result: list[tuple[str, bool, bool, bool]] = []
        for p in getattr(stage, "produces", ()) or ():
            result.append(_normalize_dependency(p))
        for w in getattr(stage, "writes", ()) or ():
            result.append(_normalize_dependency(w))
        return result

    def _stage_consumes(stage: Any) -> list[tuple[str, bool, bool, bool]]:
        """Return the effective set of names that *stage* consumes."""
        result: list[tuple[str, bool, bool, bool]] = []
        for c in getattr(stage, "consumes", ()) or ():
            result.append(_normalize_dependency(c))
        for r in getattr(stage, "reads", ()) or ():
            result.append(_normalize_dependency(r))
        return result

    # Seed initial availability from binding_map and external/late_bound refs
    initial_available: set[str] = set()
    if isinstance(binding_map, dict):
        initial_available.update(binding_map.keys())

    # ── Compute per-stage produces/consumes ───────────────────────────────
    produces: dict[str, set[str]] = {}
    consumes: dict[str, list[tuple[str, bool, bool, bool]]] = {}
    for name, stage in stages.items():
        produces[name] = {n for n, *_ in _stage_produces(stage)}
        consumes[name] = _stage_consumes(stage)
        # External/late-bound consumptions are always satisfied
        for c_name, c_opt, c_ext, c_late in consumes[name]:
            if c_ext or c_late:
                initial_available.add(c_name)

    # ── Fixed-point availability analysis ────────────────────────────────
    # available_at[stage] = set of names guaranteed available when entering stage
    available_at: dict[str, set[str]] = {name: set() for name in stages}

    # Seed entry with initial availability
    available_at[entry] = set(initial_available)

    changed = True
    while changed:
        changed = False
        # Topological-ish: iterate stages in a fixed order for determinism
        for name in sorted(stages):
            preds = predecessors.get(name, [])
            if name == entry:
                # Entry already seeded; skip recomputation from preds
                new_incoming = set(initial_available)
            elif preds:
                # Join: intersection of predecessor out-sets
                pred_out_sets = [
                    available_at[p] | produces.get(p, set()) for p in preds
                ]
                if pred_out_sets:
                    new_incoming = pred_out_sets[0].copy()
                    for s in pred_out_sets[1:]:
                        new_incoming &= s
                else:
                    new_incoming = set()
            else:
                new_incoming = set()

            # Merge with current available
            combined = available_at[name] | new_incoming
            if combined != available_at[name]:
                available_at[name] = combined
                changed = True

    # ── Check each stage's consumes against availability ─────────────────
    # Also track which predecessor route(s) fail for reporting
    for name in sorted(stages):
        incoming = available_at.get(name, set())
        for c_name, c_opt, c_ext, c_late in consumes.get(name, []):
            if c_opt or c_ext or c_late:
                # Optional/external/late-bound always satisfied
                continue
            if c_name in incoming:
                continue
            if c_name in produces.get(name, set()):
                # Stage produces what it consumes — self-satisfying
                continue
            # Build a route hint: find a predecessor where it's missing
            route_hint = ""
            preds = predecessors.get(name, [])
            if preds:
                # Find first predecessor that doesn't provide this dep
                for p in preds:
                    p_available = available_at.get(p, set()) | produces.get(p, set())
                    if c_name not in p_available:
                        route_hint = f" (missing from predecessor {p!r})"
                        break
                if not route_hint and preds:
                    route_hint = f" (available at all predecessors but not after join)"
            diag.defects.append(
                f"stage {name!r}: dependency {c_name!r} is unsatisfied"
                f"{route_hint}"
            )

    return diag


# ── Prompt / resource dependency validation ──────────────────────────────────


def _stage_step(stage: Any) -> Any:
    """Duck-typed accessor for the step inside a stage.

    Handles both ``Stage.step`` (single step) and ``ParallelStage.steps``
    (tuple of steps).  For parallel stages the first step is returned as
    the representative for prompt_key lookups.
    """
    step = getattr(stage, "step", None)
    if step is not None:
        return step
    steps = getattr(stage, "steps", None)
    if steps is not None and len(steps) > 0:
        return steps[0]
    return None


def _step_prompt_key(stage: Any) -> str | None:
    """Duck-typed accessor for ``prompt_key`` on a stage's step.

    Returns the ``prompt_key`` from ``stage.step`` (or first step in
    ``stage.steps``), or ``None`` when no step carries one.
    """
    step = _stage_step(stage)
    if step is None:
        return None
    return getattr(step, "prompt_key", None)


def _pipeline_resource_bundles(pipeline: Any) -> tuple[Any, ...]:
    """Duck-typed accessor for ``resource_bundles`` on a pipeline."""
    bundles = getattr(pipeline, "resource_bundles", ()) or ()
    if isinstance(bundles, tuple):
        return bundles
    if isinstance(bundles, (list, set)):
        return tuple(bundles)
    return ()


def validate_resource_dependencies(
    pipeline: Any, options: ValidationOptions | None = None
) -> Diagnostics:
    """Validate prompt/resource dependencies for every stage.

    Checks performed:

    1. Every stage whose step declares a ``prompt_key`` must have that
       key resolvable — by convention the pipeline's ``resource_bundles``
       tuple carries bundle objects that downstream prompt resolution
       uses.  A missing prompt key (non-None ``prompt_key`` with no
       matching resource bundle) is flagged.

    2. Every ``resource_bundle`` name declared on the pipeline is
       reported for coverage (bundle-scoped validation).

    3. Deterministic ordering: defects are emitted in sorted stage-name
       order so callers see stable output.

    This function performs **NO global mutable prompt registry** lookup.
    It duck-types ``prompt_key`` from both Arnold and Megaplan step
    shapes via :func:`_step_prompt_key`.

    Parameters
    ----------
    pipeline:
        A pipeline whose stages carry steps with optional ``prompt_key``
        and whose ``resource_bundles`` tuple carries bundle descriptors.
    options:
        Optional :class:`ValidationOptions` (unused for now; accepted for
        signature consistency).

    Returns
    -------
    Diagnostics:
        A :class:`Diagnostics` whose ``defects`` list is empty iff
        every prompt/resource dependency is satisfiable.
    """
    if options is None:
        options = ValidationOptions()

    diag = Diagnostics()
    stages: dict[str, Any] = dict(getattr(pipeline, "stages", {}) or {})
    if not stages:
        return diag

    bundles = _pipeline_resource_bundles(pipeline)

    # Collect known bundle identifiers — a bundle may be a string name
    # or an object carrying a ``name`` / ``bundle_key`` attribute.
    known_bundle_names: set[str] = set()
    for b in bundles:
        if isinstance(b, str):
            known_bundle_names.add(b)
        else:
            bname = getattr(b, "name", None) or getattr(b, "bundle_key", None)
            if bname is not None and isinstance(bname, str):
                known_bundle_names.add(bname)

    # ── Walk stages in deterministic (sorted) order ────────────────────
    for stage_name in sorted(stages):
        stage = stages[stage_name]
        prompt_key = _step_prompt_key(stage)

        if prompt_key is not None and isinstance(prompt_key, str) and prompt_key.strip():
            # A step declares it needs a prompt_key — check against bundles
            if known_bundle_names and prompt_key not in known_bundle_names:
                # Check if any bundle can satisfy: look for a bundle with
                # a bundle_key matching or prefix-matching the prompt_key
                resolved = False
                for b in bundles:
                    if isinstance(b, str):
                        if b == prompt_key or prompt_key.startswith(b):
                            resolved = True
                            break
                    else:
                        bname = getattr(b, "name", None) or getattr(b, "bundle_key", None)
                        if bname is not None and isinstance(bname, str):
                            if bname == prompt_key or prompt_key.startswith(bname):
                                resolved = True
                                break
                if not resolved and known_bundle_names:
                    diag.defects.append(
                        f"stage {stage_name!r}: prompt_key {prompt_key!r} references "
                        f"no known resource bundle (available: {sorted(known_bundle_names)})"
                    )

            # Also report bundle-scoped coverage: flag stages that have prompt_keys
            # but no bundles at all on the pipeline (soft defect — the pipeline
            # may rely on a separate prompt registry).
            if not bundles:
                diag.defects.append(
                    f"stage {stage_name!r}: declares prompt_key {prompt_key!r} "
                    f"but pipeline has no resource_bundles"
                )

    return diag


# ── Cycle detection ───────────────────────────────────────────────────────


def _detect_unguarded_cycles(
    stages: Mapping[str, Any],
    entry: str,
    diag: Diagnostics,
) -> None:
    """DFS-based unguarded-cycle detection.

    A cycle is *guarded* when at least one edge in the cycle targets a
    stage that declares a ``loop_condition``.  Unguarded cycles are
    flagged as defects.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {name: WHITE for name in stages}
    # parent_edge tracks (src, target) for each DFS-tree edge
    parent_edge: dict[str, tuple[str, str] | None] = {name: None for name in stages}

    def _edge_targets(src_name: str) -> list[tuple[str, Any]]:
        """Return list of (target_name, edge) for non-halt edges from src."""
        stage = stages.get(src_name)
        if stage is None:
            return []
        result: list[tuple[str, Any]] = []
        for edge in _stage_edges(stage):
            target = getattr(edge, "target", "")
            if target != "halt" and target in stages:
                result.append((target, edge))
        return result

    def _dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor, edge in _edge_targets(node):
            if color[neighbor] == GRAY:
                # Back edge found — extract the cycle
                cycle = _extract_cycle(node, neighbor, parent_edge)
                if not _cycle_has_guard(cycle, stages):
                    cycle_str = " → ".join(cycle)
                    diag.defects.append(
                        f"unguarded cycle detected: {cycle_str} "
                        "(add a loop_condition to at least one stage in the cycle)"
                    )
            elif color[neighbor] == WHITE:
                parent_edge[neighbor] = (node, neighbor)
                _dfs(neighbor)
        color[node] = BLACK

    # Start DFS from entry and any other unvisited nodes
    if entry in color:
        _dfs(entry)
    for name in stages:
        if color.get(name) == WHITE:
            _dfs(name)


def _extract_cycle(
    start: str,
    back_target: str,
    parent_edge: dict[str, tuple[str, str] | None],
) -> list[str]:
    """Extract the cycle path from *start* back to *back_target* via parent edges."""
    # Walk from start up the parent chain to back_target
    path: list[str] = [start]
    current = start
    while current != back_target:
        pe = parent_edge.get(current)
        if pe is None:
            break
        src, _ = pe
        path.append(src)
        current = src
    path.append(start)  # close the cycle
    path.reverse()
    return path


def _cycle_has_guard(
    cycle: list[str],
    stages: Mapping[str, Any],
) -> bool:
    """Return True if any stage in *cycle* has a ``loop_condition``."""
    for name in cycle:
        stage = stages.get(name)
        if stage is not None:
            lc = getattr(stage, "loop_condition", None)
            if lc is not None:
                return True
    return False
