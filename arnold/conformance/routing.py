"""Routing vocabulary conformance checks.

This module provides a local pipeline walker for mapping/list stages, routing-stage
detection by decision/override edges or declared vocabularies, vocabulary coverage
checks, and seeded unmatched-signal checks through the existing ``resolve_edge``
behaviour — without changing runtime routing semantics.

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from arnold.conformance import ConformanceCheckResult
from arnold.pipeline.routing import RoutingError, resolve_edge
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    StepResult,
)


# ---------------------------------------------------------------------------
# Pipeline walker — handles mapping and list-like stages
# ---------------------------------------------------------------------------


def iter_pipeline_stages(pipeline: Pipeline) -> list[Stage | ParallelStage]:
    """Return every stage in *pipeline* in a deterministic order.

    Handles both ``Mapping``-shaped and list-like ``Pipeline.stages``.
    """
    stages = pipeline.stages
    if isinstance(stages, Mapping):
        # Sort by name for determinism
        return [stages[name] for name in sorted(stages)]
    # list-like
    return list(stages)


def iter_pipeline_stage_names(pipeline: Pipeline) -> list[str]:
    """Return every stage name in *pipeline* in deterministic order."""
    stages = pipeline.stages
    if isinstance(stages, Mapping):
        return sorted(stages)
    return [s.name for s in stages]


# ---------------------------------------------------------------------------
# Routing-stage detection
# ---------------------------------------------------------------------------


def _has_routing_vocabulary(stage: Stage | ParallelStage) -> bool:
    """Return True when *stage* declares any routing vocabulary."""
    return bool(stage.decision_vocabulary or stage.override_vocabulary)


def _has_routing_edges(stage: Stage | ParallelStage) -> bool:
    """Return True when *stage* has decision or override edges."""
    for edge in stage.edges:
        if edge.kind in ("decision", "override"):
            return True
    return False


def detect_routing_stages(
    pipeline: Pipeline,
) -> list[tuple[str, Stage | ParallelStage]]:
    """Return ``(name, stage)`` pairs for every stage that participates in routing.

    A stage participates in routing when it declares a non-empty
    ``decision_vocabulary`` / ``override_vocabulary``, or when any of its
    edges have ``kind='decision'`` or ``kind='override'``.
    """
    result: list[tuple[str, Stage | ParallelStage]] = []
    stages = pipeline.stages
    if isinstance(stages, Mapping):
        for name in sorted(stages):
            stage = stages[name]
            if _has_routing_vocabulary(stage) or _has_routing_edges(stage):
                result.append((name, stage))
    else:
        for stage in stages:
            if _has_routing_vocabulary(stage) or _has_routing_edges(stage):
                result.append((stage.name, stage))
    return result


# ---------------------------------------------------------------------------
# Vocabulary coverage checks
# ---------------------------------------------------------------------------


def check_vocabulary_coverage(
    pipeline: Pipeline,
) -> ConformanceCheckResult:
    """Verify that every decision/override edge label has a matching entry in
    the stage's declared vocabulary.

    When a stage declares a ``decision_vocabulary``, every edge with
    ``kind='decision'`` must have a ``label`` that is a member of that
    vocabulary.  The same holds for ``override_vocabulary`` and
    ``kind='override'`` edges.

    An empty vocabulary skips the check (no restriction is imposed).
    """
    diagnostics: list[str] = []
    routing_stages = detect_routing_stages(pipeline)

    for name, stage in routing_stages:
        # Check decision vocabulary
        if stage.decision_vocabulary:
            for edge in stage.edges:
                if edge.kind == "decision":
                    if edge.label not in stage.decision_vocabulary:
                        diagnostics.append(
                            f"Stage {name!r}: decision edge label {edge.label!r} "
                            f"not in decision_vocabulary="
                            f"{set(stage.decision_vocabulary)!r}"
                        )

        # Check override vocabulary
        if stage.override_vocabulary:
            for edge in stage.edges:
                if edge.kind == "override":
                    expected_label = f"override {edge.label}" if not edge.label.startswith("override ") else edge.label
                    # The actual label format is "override <action>"
                    action = edge.label
                    if action.startswith("override "):
                        action = action[len("override "):]
                    if action not in stage.override_vocabulary:
                        diagnostics.append(
                            f"Stage {name!r}: override edge label {edge.label!r} "
                            f"(action={action!r}) not in override_vocabulary="
                            f"{set(stage.override_vocabulary)!r}"
                        )

    if diagnostics:
        return ConformanceCheckResult(
            check_id="routing-vocabulary-coverage",
            passed=False,
            message="; ".join(diagnostics),
            details=diagnostics,
        )
    return ConformanceCheckResult(check_id="routing-vocabulary-coverage", passed=True)


def check_vocabulary_edge_consistency(
    pipeline: Pipeline,
) -> ConformanceCheckResult:
    """Verify that stages with declared vocabularies have matching edges, and
    stages with decision/override edges have declared vocabularies.

    This is an opinionated check: a stage with a non-empty vocabulary should
    define edges for every declared value, and a stage with decision/override
    edges should declare the corresponding vocabulary so resolve_edge can
    validate.
    """
    diagnostics: list[str] = []
    routing_stages = detect_routing_stages(pipeline)

    for name, stage in routing_stages:
        # Stages with declared decision vocabulary should have decision edges
        if stage.decision_vocabulary:
            decision_labels = {
                e.label for e in stage.edges if e.kind == "decision"
            }
            uncovered = stage.decision_vocabulary - decision_labels
            if uncovered:
                diagnostics.append(
                    f"Stage {name!r}: decision_vocabulary declares "
                    f"{set(uncovered)!r} but no matching decision edges exist"
                )

        # Stages with declared override vocabulary should have override edges
        if stage.override_vocabulary:
            override_actions: set[str] = set()
            for e in stage.edges:
                if e.kind == "override":
                    label = e.label
                    if label.startswith("override "):
                        label = label[len("override "):]
                    override_actions.add(label)
            uncovered = stage.override_vocabulary - override_actions
            if uncovered:
                diagnostics.append(
                    f"Stage {name!r}: override_vocabulary declares "
                    f"{set(uncovered)!r} but no matching override edges exist"
                )

        # Stages with decision edges should declare a vocabulary
        has_decision_edges = any(e.kind == "decision" for e in stage.edges)
        if has_decision_edges and not stage.decision_vocabulary:
            diagnostics.append(
                f"Stage {name!r}: has decision edges but no decision_vocabulary declared"
            )

        # Stages with override edges should declare a vocabulary
        has_override_edges = any(e.kind == "override" for e in stage.edges)
        if has_override_edges and not stage.override_vocabulary:
            diagnostics.append(
                f"Stage {name!r}: has override edges but no override_vocabulary declared"
            )

    if diagnostics:
        return ConformanceCheckResult(
            check_id="routing-vocabulary-edge-consistency",
            passed=False,
            message="; ".join(diagnostics),
            details=diagnostics,
        )
    return ConformanceCheckResult(
        check_id="routing-vocabulary-edge-consistency", passed=True
    )


# ---------------------------------------------------------------------------
# Seeded unmatched-signal checks via resolve_edge
# ---------------------------------------------------------------------------


def check_resolve_edge_normal_match(
    stage: Stage,
    result: StepResult,
    edges: tuple[Edge, ...],
    expected_target: str,
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` returns the correct normal-match edge.

    Parameters
    ----------
    stage:
        The stage to resolve from.
    result:
        A ``StepResult`` whose ``next`` field is the normal label.
    edges:
        The stage's edge set.
    expected_target:
        The expected ``edge.target`` for the matched edge.
    """
    try:
        matched = resolve_edge(stage, result, result.verdict, edges)
    except RoutingError as exc:
        return ConformanceCheckResult(
            check_id="resolve-edge-normal-match",
            passed=False,
            message=(
                f"resolve_edge raised RoutingError for next={result.next!r}: {exc}"
            ),
            details={
                "stage": stage.name,
                "next": result.next,
                "edges": [(e.kind, e.label, e.target) for e in edges],
            },
        )

    if matched is None:
        return ConformanceCheckResult(
            check_id="resolve-edge-normal-match",
            passed=False,
            message=(
                f"resolve_edge returned None for next={result.next!r} "
                f"(halt short-circuit when not expected)"
            ),
        )

    if matched.target != expected_target:
        return ConformanceCheckResult(
            check_id="resolve-edge-normal-match",
            passed=False,
            message=(
                f"resolve_edge matched target={matched.target!r}, "
                f"expected {expected_target!r}"
            ),
            details={"matched": matched, "expected_target": expected_target},
        )

    return ConformanceCheckResult(check_id="resolve-edge-normal-match", passed=True)


def check_resolve_edge_decision_match(
    stage: Stage,
    result: StepResult,
    verdict: PipelineVerdict,
    edges: tuple[Edge, ...],
    expected_target: str,
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` matches a decision edge when a
    recommendation is set on the verdict.
    """
    try:
        matched = resolve_edge(stage, result, verdict, edges)
    except RoutingError as exc:
        return ConformanceCheckResult(
            check_id="resolve-edge-decision-match",
            passed=False,
            message=(
                f"resolve_edge raised RoutingError for "
                f"recommendation={verdict.recommendation!r}: {exc}"
            ),
            details={
                "stage": stage.name,
                "recommendation": verdict.recommendation,
                "edges": [(e.kind, e.label, e.target) for e in edges],
            },
        )

    if matched is None:
        return ConformanceCheckResult(
            check_id="resolve-edge-decision-match",
            passed=False,
            message="resolve_edge returned None for decision dispatch",
        )

    if matched.target != expected_target:
        return ConformanceCheckResult(
            check_id="resolve-edge-decision-match",
            passed=False,
            message=(
                f"resolve_edge decision match target={matched.target!r}, "
                f"expected {expected_target!r}"
            ),
        )

    return ConformanceCheckResult(check_id="resolve-edge-decision-match", passed=True)


def check_resolve_edge_override_match(
    stage: Stage,
    result: StepResult,
    verdict: PipelineVerdict,
    edges: tuple[Edge, ...],
    expected_target: str,
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` matches an override edge when an override
    action is set on the verdict.
    """
    try:
        matched = resolve_edge(stage, result, verdict, edges)
    except RoutingError as exc:
        return ConformanceCheckResult(
            check_id="resolve-edge-override-match",
            passed=False,
            message=(
                f"resolve_edge raised RoutingError for "
                f"override={verdict.override!r}: {exc}"
            ),
            details={
                "stage": stage.name,
                "override": verdict.override,
                "edges": [(e.kind, e.label, e.target) for e in edges],
            },
        )

    if matched is None:
        return ConformanceCheckResult(
            check_id="resolve-edge-override-match",
            passed=False,
            message="resolve_edge returned None for override dispatch",
        )

    if matched.target != expected_target:
        return ConformanceCheckResult(
            check_id="resolve-edge-override-match",
            passed=False,
            message=(
                f"resolve_edge override match target={matched.target!r}, "
                f"expected {expected_target!r}"
            ),
        )

    return ConformanceCheckResult(check_id="resolve-edge-override-match", passed=True)


def check_resolve_edge_halt(
    stage: Stage,
    result: StepResult,
    edges: tuple[Edge, ...],
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` returns ``None`` when ``result.next == 'halt'``."""
    try:
        matched = resolve_edge(stage, result, result.verdict, edges)
    except RoutingError as exc:
        return ConformanceCheckResult(
            check_id="resolve-edge-halt",
            passed=False,
            message=f"resolve_edge raised RoutingError on halt: {exc}",
        )

    if matched is not None:
        return ConformanceCheckResult(
            check_id="resolve-edge-halt",
            passed=False,
            message=(
                f"resolve_edge returned edge target={matched.target!r} "
                f"for halt instead of None"
            ),
        )

    return ConformanceCheckResult(check_id="resolve-edge-halt", passed=True)


def check_resolve_edge_unmatched_signal(
    stage: Stage,
    result: StepResult,
    edges: tuple[Edge, ...],
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` raises ``RoutingError`` when no edge
    matches a non-halt signal.

    This is the seeded unmatched-signal check: we construct a ``StepResult``
    with a ``next`` label that has no matching edge, and confirm
    ``resolve_edge`` surfaces the failure.
    """
    try:
        matched = resolve_edge(stage, result, result.verdict, edges)
        return ConformanceCheckResult(
            check_id="resolve-edge-unmatched-signal",
            passed=False,
            message=(
                f"resolve_edge returned {matched!r} for unmatched next={result.next!r} "
                f"instead of raising RoutingError"
            ),
            details={
                "stage": stage.name,
                "next": result.next,
                "available_labels": [
                    (e.kind, e.label) for e in edges
                ],
            },
        )
    except RoutingError:
        return ConformanceCheckResult(
            check_id="resolve-edge-unmatched-signal", passed=True
        )
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="resolve-edge-unmatched-signal",
            passed=False,
            message=(
                f"resolve_edge raised unexpected {type(exc).__name__}: {exc}"
            ),
        )


def check_resolve_edge_vocabulary_validation(
    stage: Stage,
    result: StepResult,
    verdict: PipelineVerdict,
    edges: tuple[Edge, ...],
    *,
    check_kind: str,
) -> ConformanceCheckResult:
    """Verify that ``resolve_edge`` validates vocabularies.

    When *stage* declares a non-empty vocabulary and the *verdict* carries
    a value outside that vocabulary, ``resolve_edge`` must raise
    ``RoutingError``.

    Parameters
    ----------
    check_kind:
        Either ``"decision"`` or ``"override"`` — which vocabulary to test.
    """
    try:
        matched = resolve_edge(stage, result, verdict, edges)
        return ConformanceCheckResult(
            check_id=f"resolve-edge-{check_kind}-vocabulary-validation",
            passed=False,
            message=(
                f"resolve_edge returned {matched!r} for out-of-vocabulary "
                f"{check_kind} instead of raising RoutingError"
            ),
            details={
                "stage": stage.name,
                f"{check_kind}_vocabulary": (
                    stage.decision_vocabulary
                    if check_kind == "decision"
                    else stage.override_vocabulary
                ),
                "value": (
                    verdict.recommendation
                    if check_kind == "decision"
                    else verdict.override
                ),
            },
        )
    except RoutingError:
        return ConformanceCheckResult(
            check_id=f"resolve-edge-{check_kind}-vocabulary-validation", passed=True
        )
    except Exception as exc:
        return ConformanceCheckResult(
            check_id=f"resolve-edge-{check_kind}-vocabulary-validation",
            passed=False,
            message=(
                f"resolve_edge raised unexpected {type(exc).__name__}: {exc}"
            ),
        )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


def run_routing_conformance_suite(
    pipeline: Pipeline,
) -> list[ConformanceCheckResult]:
    """Run all routing conformance checks against *pipeline*.

    Returns an ordered list of ``ConformanceCheckResult`` values suitable for
    constructing a ``ConformanceSuiteResult``.
    """
    results: list[ConformanceCheckResult] = []

    # Vocabulary coverage
    results.append(check_vocabulary_coverage(pipeline))
    results.append(check_vocabulary_edge_consistency(pipeline))

    # Per-stage resolve_edge checks
    for name, stage in detect_routing_stages(pipeline):
        # Build a normal-match test
        normal_edges = [e for e in stage.edges if e.kind == "normal"]
        if normal_edges:
            test_result = StepResult(next=normal_edges[0].label)
            results.append(
                check_resolve_edge_normal_match(
                    stage, test_result, stage.edges, normal_edges[0].target
                )
            )

        # Build a decision-match test
        decision_edges = [e for e in stage.edges if e.kind == "decision"]
        if decision_edges and stage.decision_vocabulary:
            for vocab_entry in sorted(stage.decision_vocabulary):
                verdict = PipelineVerdict(score=1.0, recommendation=vocab_entry)
                matching = [e for e in decision_edges if e.label == vocab_entry]
                if matching:
                    test_result = StepResult(next="default", verdict=verdict)
                    results.append(
                        check_resolve_edge_decision_match(
                            stage, test_result, verdict, stage.edges, matching[0].target
                        )
                    )

        # Build an override-match test
        override_edges = [e for e in stage.edges if e.kind == "override"]
        if override_edges and stage.override_vocabulary:
            for vocab_entry in sorted(stage.override_vocabulary):
                target_label = f"override {vocab_entry}"
                matching = [e for e in override_edges if e.label == target_label]
                if matching:
                    verdict = PipelineVerdict(score=1.0, override=vocab_entry)
                    test_result = StepResult(next="default", verdict=verdict)
                    results.append(
                        check_resolve_edge_override_match(
                            stage, test_result, verdict, stage.edges, matching[0].target
                        )
                    )

        # Unmatched signal test
        unmatched_label = "_conformance_no_such_label_"
        test_result = StepResult(next=unmatched_label)
        results.append(
            check_resolve_edge_unmatched_signal(stage, test_result, stage.edges)
        )

        # Vocabulary out-of-range tests
        if stage.decision_vocabulary:
            bad_key = "_conformance_bad_decision_"
            if bad_key not in stage.decision_vocabulary:
                verdict = PipelineVerdict(score=1.0, recommendation=bad_key)
                test_result = StepResult(next="default", verdict=verdict)
                results.append(
                    check_resolve_edge_vocabulary_validation(
                        stage, test_result, verdict, stage.edges, check_kind="decision"
                    )
                )

        if stage.override_vocabulary:
            bad_action = "_conformance_bad_override_"
            if bad_action not in stage.override_vocabulary:
                verdict = PipelineVerdict(score=1.0, override=bad_action)
                test_result = StepResult(next="default", verdict=verdict)
                results.append(
                    check_resolve_edge_vocabulary_validation(
                        stage, test_result, verdict, stage.edges, check_kind="override"
                    )
                )

    return results


__all__ = [
    "iter_pipeline_stages",
    "iter_pipeline_stage_names",
    "detect_routing_stages",
    "check_vocabulary_coverage",
    "check_vocabulary_edge_consistency",
    "check_resolve_edge_normal_match",
    "check_resolve_edge_decision_match",
    "check_resolve_edge_override_match",
    "check_resolve_edge_halt",
    "check_resolve_edge_unmatched_signal",
    "check_resolve_edge_vocabulary_validation",
    "run_routing_conformance_suite",
]
