"""Policy-neutral edge routing resolver for Arnold pipelines.

This module provides the shared routing dispatch that both the Arnold
and Megaplan executors consume.  The resolver is opinion-free: it uses
only ``kind`` and ``label`` matching against a stage's edge set, with
vocabulary validation when the stage declares decision/override sets.

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arnold.pipeline.types import Edge, PipelineVerdict, Stage, StepResult

__all__ = ["resolve_edge", "RoutingError"]


class RoutingError(Exception):
    """Raised when no edge matches the current routing signal.

    Signals include: an override action or decision key that falls
    outside the stage's declared vocabulary, or a dispatch signal
    for which no matching edge exists in the stage's edge set.
    """


def resolve_edge(
    stage: "Stage",
    result: "StepResult",
    verdict: "PipelineVerdict | None",
    edges: "tuple[Edge, ...]",
) -> "Edge | None":
    """Resolve the next edge using the 4-priority dispatch.

    Dispatch order:

    1. **halt** — ``result.next == 'halt'`` returns ``None`` immediately.
       The caller is responsible for terminating the pipeline loop.
    2. **override** — ``verdict.override`` is matched against edges with
       ``kind='override'`` and ``label='override <action>'``.
    3. **decision** — ``verdict.recommendation`` is matched against edges
       with ``kind='decision'`` and ``label=<decision_key>``.
    4. **normal** — fallback label match: edges with ``kind='normal'``
       and ``label == result.next``.

    Vocabulary validation:

    * When ``stage.override_vocabulary`` is non-empty and
      ``verdict.override`` is set, the override action **must** be a
      member of that frozenset.  A :class:`RoutingError` is raised
      otherwise.
    * When ``stage.decision_vocabulary`` is non-empty and
      ``verdict.recommendation`` is set, the decision key **must** be a
      member of that frozenset.  A :class:`RoutingError` is raised
      otherwise.
    * An empty vocabulary (the default) skips validation — the stage
      participates in the dispatch tier but imposes no restriction on
      which strings are allowed.

    Args:
        stage: The enclosing stage (used for its ``name`` and
            ``*_vocabulary`` fields).
        result: The step result whose ``next`` field is the normal
            label.
        verdict: The verdict extracted from ``result.verdict`` (may be
            ``None``).
        edges: The stage's outgoing edge tuple.

    Returns:
        The matched :class:`Edge`, or ``None`` when
        ``result.next == 'halt'``.

    Raises:
        RoutingError: When a verdict override/decision falls outside the
            stage's declared vocabulary, or when no matching edge is
            found for a non-halt dispatch signal.
    """
    # ── Priority 1: halt short-circuit ──────────────────────────────
    if result.next == "halt":
        return None

    # ── Priority 2: override dispatch ────────────────────────────────
    if verdict is not None and verdict.override is not None:
        override_action = verdict.override

        # Validate against stage.override_vocabulary when declared.
        if stage.override_vocabulary:
            if override_action not in stage.override_vocabulary:
                raise RoutingError(
                    f"Stage {stage.name!r}: override action "
                    f"{override_action!r} is not in "
                    f"override_vocabulary="
                    f"{set(stage.override_vocabulary)!r}"
                )

        target_label = f"override {override_action}"
        for edge in edges:
            if edge.kind == "override" and edge.label == target_label:
                return edge

        raise RoutingError(
            f"Stage {stage.name!r}: verdict override={override_action!r} "
            f"but no matching kind='override' edge with "
            f"label={target_label!r} was found"
        )

    # ── Priority 3: decision dispatch ────────────────────────────────
    if verdict is not None and verdict.recommendation is not None:
        decision_key = verdict.recommendation

        # Validate against stage.decision_vocabulary when declared.
        if stage.decision_vocabulary:
            if decision_key not in stage.decision_vocabulary:
                raise RoutingError(
                    f"Stage {stage.name!r}: decision key "
                    f"{decision_key!r} is not in "
                    f"decision_vocabulary="
                    f"{set(stage.decision_vocabulary)!r}"
                )

        for edge in edges:
            if edge.kind == "decision" and edge.label == decision_key:
                return edge

        raise RoutingError(
            f"Stage {stage.name!r}: verdict recommendation="
            f"{decision_key!r} but no matching kind='decision' edge "
            f"with label={decision_key!r} was found"
        )

    # ── Priority 4: normal label match ───────────────────────────────
    for edge in edges:
        if edge.kind == "normal" and edge.label == result.next:
            return edge

    raise RoutingError(
        f"Stage {stage.name!r}: next={result.next!r} "
        f"but no matching kind='normal' edge with "
        f"label={result.next!r} was found"
    )
