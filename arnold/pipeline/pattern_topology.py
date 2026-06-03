"""Policy-neutral decision-edge topology builders for Arnold pipelines.

Every function in this module is *stateless*: it returns primitive
pipeline objects (specifically :class:`Edge` tuples) that callers wire
into their pipeline.  No Megaplan vocabulary literals appear here —
this is the Arnold-neutral surface.

The key helper :func:`decision_edges` maps caller-supplied decision and
override labels to ``kind='decision'`` / ``kind='override'`` edges
suitable for consumption by the shared routing resolver in
:mod:`arnold.pipeline.routing`.
"""

from __future__ import annotations

from typing import Mapping

from arnold.pipeline.types import Edge, Stage, Step

__all__ = ["decision_edges", "loop_back_stage"]


def decision_edges(
    decisions: Mapping[str, str],
    overrides: Mapping[str, str] | None = None,
    fallback_edges: tuple[Edge, ...] = (),
) -> tuple[Edge, ...]:
    """Build decision and override edges from caller-supplied mappings.

    Each ``(key, target)`` in *decisions* becomes an :class:`Edge` with
    ``kind='decision'`` and ``label=<key>``.

    Each ``(action, target)`` in *overrides* becomes an :class:`Edge`
    with ``kind='override'`` and ``label='override <action>'``.

    *fallback_edges* are appended after all generated edges (preserving
    their existing ``kind`` and ``label`` as-is).

    **No Megaplan label literals** (``proceed``, ``iterate``,
    ``tiebreaker``, ``escalate``, ``force_proceed``, ``abort``,
    ``replan``, ``add_note``) are baked in — the caller supplies every
    label.  This keeps the module policy-neutral and suitable for any
    runtime that consumes :class:`Edge` objects.

    Args:
        decisions: Mapping of decision key → target stage name.
        overrides: Optional mapping of override action → target stage
            name.  ``None`` is treated as empty.
        fallback_edges: Additional edges to append after the generated
            decision and override edges.

    Returns:
        A tuple of :class:`Edge` objects, with decision edges first,
        then override edges, then fallback edges.

    Example:

        >>> from arnold.pipeline.pattern_topology import decision_edges
        >>> edges = decision_edges(
        ...     decisions={"approve": "done", "rework": "revise"},
        ...     overrides={"abort": "halt", "force_proceed": "done"},
        ...     fallback_edges=(Edge(label="next", target="next_stage"),),
        ... )
        >>> for e in edges:
        ...     print(f"{e.kind:>10}  {e.label:<20} → {e.target}")
           decision  approve              → done
           decision  rework               → revise
           override  override abort       → halt
           override  override force_proceed → done
             normal  next                 → next_stage
    """
    result: list[Edge] = []

    for key, target in decisions.items():
        result.append(Edge(label=key, target=target, kind="decision"))

    if overrides:
        for action, target in overrides.items():
            result.append(
                Edge(label=f"override {action}", target=target, kind="override")
            )

    result.extend(fallback_edges)
    return tuple(result)


def loop_back_stage(
    name: str,
    step: Step,
    *,
    decisions: Mapping[str, str],
    on_loop_back: str,
    loop_back_label: str = "loop_back",
    overrides: Mapping[str, str] | None = None,
    fallback_edges: tuple[Edge, ...] = (),
    decision_vocabulary: frozenset[str] = frozenset(),
    override_vocabulary: frozenset[str] = frozenset(),
) -> Stage:
    """Build a Stage with decision/override routing and a self-loop edge.

    The returned :class:`Stage` contains:

    * Decision edges (``kind='decision'``) from *decisions*.
    * Override edges (``kind='override'``) from *overrides*.
    * A loop-back edge (``kind='normal'``, label=*loop_back_label*)
      targeting *on_loop_back*.
    * Any *fallback_edges* appended at the end.

    **No Megaplan label literals** are baked in — every label is
    caller-supplied.  The caller decides what the loop-back label
    is and which targets each decision/override edge points at.

    Args:
        name: Stage name within the pipeline.
        step: The executable step for this stage.
        decisions: Mapping of decision key → target stage name.
        on_loop_back: Target stage name for the loop-back edge.
        loop_back_label: Label for the loop-back edge (default
            ``\"loop_back\"``).
        overrides: Optional mapping of override action → target stage
            name.
        fallback_edges: Additional edges appended after all generated
            edges.
        decision_vocabulary: Declared set of valid decision keys.
        override_vocabulary: Declared set of valid override actions.

    Returns:
        A :class:`Stage` ready for insertion into a pipeline.
    """
    routing_edges = decision_edges(
        decisions=decisions,
        overrides=overrides,
        fallback_edges=(
            Edge(label=loop_back_label, target=on_loop_back, kind="normal"),
        ) + fallback_edges,
    )
    return Stage(
        name=name,
        step=step,
        edges=routing_edges,
        decision_vocabulary=decision_vocabulary,
        override_vocabulary=override_vocabulary,
    )
