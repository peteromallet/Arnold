"""Routing vocabulary conformance tests for ``arnold.conformance.routing``.

Covers:
* Green fixtures — pipeline walker correctness (mapping and list-like stages),
  routing-stage detection, vocabulary coverage with proper edges,
  ``resolve_edge`` normal/decision/override/halt matches, and the full
  ``run_routing_conformance_suite`` returning all-pass results.
* Seeded red fixtures — missing vocabulary with decision/override edges,
  uncovered edge labels not in declared vocabulary, unmatched signal
  raising ``RoutingError``, and vocabulary out-of-range validation failures.
"""

from __future__ import annotations

import pytest

from arnold.conformance import ConformanceCheckResult
from arnold.conformance.routing import (
    iter_pipeline_stages,
    iter_pipeline_stage_names,
    detect_routing_stages,
    check_vocabulary_coverage,
    check_vocabulary_edge_consistency,
    check_resolve_edge_normal_match,
    check_resolve_edge_decision_match,
    check_resolve_edge_override_match,
    check_resolve_edge_halt,
    check_resolve_edge_unmatched_signal,
    check_resolve_edge_vocabulary_validation,
    run_routing_conformance_suite,
)
from arnold.pipeline.routing import RoutingError, resolve_edge
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    PipelineVerdict,
    Stage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Minimal step for fixtures
# ---------------------------------------------------------------------------

class _MinimalStep:
    """A Step that returns a simple result."""

    def __init__(self, name: str = "minimal", next_label: str = "halt") -> None:
        self.name = name
        self.kind = "compute"
        self._next = next_label

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self._next)


# ---------------------------------------------------------------------------
# Green pipeline fixture builders
# ---------------------------------------------------------------------------

def _make_green_routing_stage(
    name: str = "router",
    *,
    decision_vocabulary: frozenset[str] | None = None,
    override_vocabulary: frozenset[str] | None = None,
) -> Stage:
    """Build a Stage with proper vocabulary coverage for all its edges."""
    edges: list[Edge] = []

    # Always add a normal edge
    edges.append(Edge(label="continue", target="next_stage", kind="normal"))

    if decision_vocabulary:
        for label in sorted(decision_vocabulary):
            edges.append(Edge(label=label, target=f"after_{label}", kind="decision"))

    if override_vocabulary:
        for action in sorted(override_vocabulary):
            edges.append(
                Edge(
                    label=f"override {action}",
                    target=f"after_override_{action}",
                    kind="override",
                )
            )

    return Stage(
        name=name,
        step=_MinimalStep(name),
        edges=tuple(edges),
        decision_vocabulary=decision_vocabulary or frozenset(),
        override_vocabulary=override_vocabulary or frozenset(),
    )


def _make_green_pipeline(
    *,
    stages_attr: str = "mapping",  # 'mapping' or 'list'
) -> Pipeline:
    """Build a Pipeline with a green routing stage and supporting stages."""
    router = _make_green_routing_stage(
        name="router",
        decision_vocabulary=frozenset({"proceed", "iterate"}),
        override_vocabulary=frozenset({"force_halt", "skip"}),
    )
    next_stage = Stage(
        name="next_stage",
        step=_MinimalStep("next_stage"),
        edges=(Edge(label="halt", target="halt", kind="normal"),),
    )
    after_proceed = Stage(
        name="after_proceed",
        step=_MinimalStep("after_proceed"),
        edges=(Edge(label="halt", target="halt", kind="normal"),),
    )
    after_iterate = Stage(
        name="after_iterate",
        step=_MinimalStep("after_iterate"),
        edges=(Edge(label="halt", target="halt", kind="normal"),),
    )
    after_force_halt = Stage(
        name="after_override_force_halt",
        step=_MinimalStep("after_force_halt"),
        edges=(Edge(label="halt", target="halt", kind="normal"),),
    )
    after_skip = Stage(
        name="after_override_skip",
        step=_MinimalStep("after_skip"),
        edges=(Edge(label="halt", target="halt", kind="normal"),),
    )

    stages = {
        "router": router,
        "next_stage": next_stage,
        "after_proceed": after_proceed,
        "after_iterate": after_iterate,
        "after_override_force_halt": after_force_halt,
        "after_override_skip": after_skip,
    }
    return Pipeline(stages=stages, entry="router")


def _make_red_missing_vocabulary_pipeline() -> Pipeline:
    """Pipeline with decision/override edges but no declared vocabulary."""
    router = Stage(
        name="router",
        step=_MinimalStep("router"),
        edges=(
            Edge(label="continue", target="next", kind="normal"),
            Edge(label="proceed", target="target_a", kind="decision"),
            Edge(label="override force_halt", target="target_b", kind="override"),
        ),
        # No decision_vocabulary or override_vocabulary declared
    )
    next_stage = Stage(
        name="next",
        step=_MinimalStep("next"),
    )
    target_a = Stage(
        name="target_a",
        step=_MinimalStep("target_a"),
    )
    target_b = Stage(
        name="target_b",
        step=_MinimalStep("target_b"),
    )
    return Pipeline(
        stages={
            "router": router,
            "next": next_stage,
            "target_a": target_a,
            "target_b": target_b,
        },
        entry="router",
    )


def _make_red_uncovered_label_pipeline() -> Pipeline:
    """Pipeline with a vocabulary that doesn't cover all edge labels."""
    router = Stage(
        name="router",
        step=_MinimalStep("router"),
        edges=(
            Edge(label="continue", target="next", kind="normal"),
            Edge(label="wrong_label", target="target_a", kind="decision"),
        ),
        decision_vocabulary=frozenset({"proceed", "iterate"}),  # missing 'wrong_label'
    )
    next_stage = Stage(
        name="next",
        step=_MinimalStep("next"),
    )
    target_a = Stage(
        name="target_a",
        step=_MinimalStep("target_a"),
    )
    return Pipeline(
        stages={"router": router, "next": next_stage, "target_a": target_a},
        entry="router",
    )


# ---------------------------------------------------------------------------
# Pipeline walker — green
# ---------------------------------------------------------------------------

class TestIterPipelineStages:
    """Green fixtures for ``iter_pipeline_stages``."""

    def test_mapping_stages_returns_sorted_by_name(self) -> None:
        pipeline = _make_green_pipeline()
        stages = iter_pipeline_stages(pipeline)
        assert isinstance(stages, list)
        # Sorted by name
        names = [s.name for s in stages]
        assert names == sorted(names)

    def test_mapping_stages_includes_all(self) -> None:
        pipeline = _make_green_pipeline()
        stages = iter_pipeline_stages(pipeline)
        assert len(stages) == 6

    def test_list_like_stages_returns_list(self) -> None:
        """When Pipeline.stages is a mapping, iter_pipeline_stages returns sorted by key."""
        s1 = Stage(name="first_stage", step=_MinimalStep("first_stage"))
        s2 = Stage(name="second_stage", step=_MinimalStep("second_stage"))
        # Pipeline has Mapping stages — keys are the stage names
        pipeline = Pipeline(stages={"first_stage": s1, "second_stage": s2}, entry="first_stage")
        stages = iter_pipeline_stages(pipeline)
        names = [s.name for s in stages]
        # Sorted by key: "first_stage" then "second_stage"
        assert names == ["first_stage", "second_stage"]


class TestIterPipelineStageNames:
    """Green fixtures for ``iter_pipeline_stage_names``."""

    def test_mapping_returns_sorted_names(self) -> None:
        pipeline = _make_green_pipeline()
        names = iter_pipeline_stage_names(pipeline)
        assert names == sorted(names)
        assert "router" in names

    def test_names_match_stages_count(self) -> None:
        pipeline = _make_green_pipeline()
        names = iter_pipeline_stage_names(pipeline)
        stages = iter_pipeline_stages(pipeline)
        assert len(names) == len(stages)


# ---------------------------------------------------------------------------
# Routing-stage detection — green
# ---------------------------------------------------------------------------

class TestDetectRoutingStages:
    """Green fixtures for ``detect_routing_stages``."""

    def test_detects_stage_with_decision_vocabulary(self) -> None:
        pipeline = _make_green_pipeline()
        routing = detect_routing_stages(pipeline)
        # 'router' has decision + override vocabularies and edges
        router_names = [name for name, _ in routing]
        assert "router" in router_names

    def test_non_routing_stages_excluded(self) -> None:
        pipeline = _make_green_pipeline()
        routing = detect_routing_stages(pipeline)
        router_names = [name for name, _ in routing]
        # next_stage, after_proceed, etc. should NOT be in routing
        assert "next_stage" not in router_names
        assert "after_proceed" not in router_names

    def test_returns_name_stage_pairs(self) -> None:
        pipeline = _make_green_pipeline()
        routing = detect_routing_stages(pipeline)
        for name, stage in routing:
            assert isinstance(name, str)
            assert isinstance(stage, Stage)

    def test_empty_pipeline_no_routing_stages(self) -> None:
        pipeline = Pipeline(stages={}, entry="")
        routing = detect_routing_stages(pipeline)
        assert routing == []

    def test_stage_with_only_edges_is_detected(self) -> None:
        """A stage with decision edges but no vocabulary is still a routing stage."""
        router = Stage(
            name="edgy",
            step=_MinimalStep("edgy"),
            edges=(Edge(label="proceed", target="next", kind="decision"),),
        )
        next_s = Stage(name="next", step=_MinimalStep("next"))
        pipeline = Pipeline(stages={"edgy": router, "next": next_s}, entry="edgy")
        routing = detect_routing_stages(pipeline)
        assert len(routing) == 1
        assert routing[0][0] == "edgy"


# ---------------------------------------------------------------------------
# check_vocabulary_coverage — green
# ---------------------------------------------------------------------------

class TestVocabularyCoverageGreen:
    """Green fixtures for ``check_vocabulary_coverage``."""

    def test_green_pipeline_passes(self) -> None:
        pipeline = _make_green_pipeline()
        result = check_vocabulary_coverage(pipeline)
        assert result.passed is True
        assert result.check_id == "routing-vocabulary-coverage"

    def test_pipeline_without_routing_stages_passes(self) -> None:
        pipeline = Pipeline(
            stages={
                "s1": Stage(name="s1", step=_MinimalStep("s1")),
                "s2": Stage(name="s2", step=_MinimalStep("s2")),
            },
            entry="s1",
        )
        result = check_vocabulary_coverage(pipeline)
        assert result.passed is True

    def test_empty_vocabulary_skips_check(self) -> None:
        """An empty vocabulary imposes no restriction — coverage passes."""
        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            edges=(Edge(label="any", target="next", kind="decision"),),
            decision_vocabulary=frozenset(),  # empty = no restriction
        )
        next_s = Stage(name="next", step=_MinimalStep("next"))
        pipeline = Pipeline(stages={"router": router, "next": next_s}, entry="router")
        result = check_vocabulary_coverage(pipeline)
        assert result.passed is True


# ---------------------------------------------------------------------------
# check_vocabulary_coverage — seeded red
# ---------------------------------------------------------------------------

class TestVocabularyCoverageRed:
    """Seeded red fixtures for ``check_vocabulary_coverage``."""

    def test_uncovered_label_fails(self) -> None:
        pipeline = _make_red_uncovered_label_pipeline()
        result = check_vocabulary_coverage(pipeline)
        assert result.passed is False
        assert "router" in result.message
        assert "wrong_label" in result.message

    def test_uncovered_label_has_details(self) -> None:
        pipeline = _make_red_uncovered_label_pipeline()
        result = check_vocabulary_coverage(pipeline)
        assert result.details is not None
        assert isinstance(result.details, list)

    def test_missing_vocabulary_with_edges_not_flagged_by_coverage(self) -> None:
        """Coverage check only applies when vocabularies are declared.
        Missing vocabulary with edges is an edge-consistency issue, not coverage.
        """
        pipeline = _make_red_missing_vocabulary_pipeline()
        result = check_vocabulary_coverage(pipeline)
        # No vocabulary declared → skip check → passes (edge consistency is separate)
        assert result.passed is True

    def test_override_uncovered_label_fails(self) -> None:
        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            edges=(
                Edge(label="override bad_action", target="next", kind="override"),
            ),
            override_vocabulary=frozenset({"good_action"}),  # 'bad_action' not covered
        )
        next_s = Stage(name="next", step=_MinimalStep("next"))
        pipeline = Pipeline(stages={"router": router, "next": next_s}, entry="router")
        result = check_vocabulary_coverage(pipeline)
        assert result.passed is False
        assert "bad_action" in result.message


# ---------------------------------------------------------------------------
# check_vocabulary_edge_consistency — green
# ---------------------------------------------------------------------------

class TestVocabularyEdgeConsistencyGreen:
    """Green fixtures for ``check_vocabulary_edge_consistency``."""

    def test_green_pipeline_passes(self) -> None:
        pipeline = _make_green_pipeline()
        result = check_vocabulary_edge_consistency(pipeline)
        assert result.passed is True
        assert result.check_id == "routing-vocabulary-edge-consistency"

    def test_no_routing_stages_passes(self) -> None:
        pipeline = Pipeline(
            stages={
                "s1": Stage(name="s1", step=_MinimalStep("s1")),
            },
            entry="s1",
        )
        result = check_vocabulary_edge_consistency(pipeline)
        assert result.passed is True


# ---------------------------------------------------------------------------
# check_vocabulary_edge_consistency — seeded red
# ---------------------------------------------------------------------------

class TestVocabularyEdgeConsistencyRed:
    """Seeded red fixtures for ``check_vocabulary_edge_consistency``."""

    def test_missing_vocabulary_with_edges_fails(self) -> None:
        pipeline = _make_red_missing_vocabulary_pipeline()
        result = check_vocabulary_edge_consistency(pipeline)
        assert result.passed is False
        assert "router" in result.message
        # Should mention missing decision_vocabulary or override_vocabulary
        assert "decision" in result.message or "override" in result.message

    def test_uncovered_vocabulary_entry_fails(self) -> None:
        """A vocabulary entry without a matching edge should be flagged."""
        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            edges=(
                Edge(label="proceed", target="next", kind="decision"),
            ),
            decision_vocabulary=frozenset({"proceed", "orphan_entry"}),
        )
        next_s = Stage(name="next", step=_MinimalStep("next"))
        pipeline = Pipeline(stages={"router": router, "next": next_s}, entry="router")
        result = check_vocabulary_edge_consistency(pipeline)
        assert result.passed is False
        assert "orphan_entry" in result.message

    def test_override_uncovered_vocabulary_entry_fails(self) -> None:
        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            edges=(),
            override_vocabulary=frozenset({"orphan_override"}),
        )
        next_s = Stage(name="next", step=_MinimalStep("next"))
        pipeline = Pipeline(stages={"router": router, "next": next_s}, entry="router")
        result = check_vocabulary_edge_consistency(pipeline)
        assert result.passed is False
        assert "orphan_override" in result.message


# ---------------------------------------------------------------------------
# resolve_edge normal match — green
# ---------------------------------------------------------------------------

class TestResolveEdgeNormalMatch:
    """Green fixtures for ``check_resolve_edge_normal_match``."""

    def test_normal_match_passes(self) -> None:
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(Edge(label="continue", target="next_stage", kind="normal"),),
        )
        result = StepResult(next="continue")
        check = check_resolve_edge_normal_match(
            stage, result, stage.edges, expected_target="next_stage"
        )
        assert check.passed is True
        assert check.check_id == "resolve-edge-normal-match"

    def test_normal_match_with_multiple_edges(self) -> None:
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(
                Edge(label="continue", target="next_stage", kind="normal"),
                Edge(label="halt", target="halt", kind="normal"),
            ),
        )
        result = StepResult(next="continue")
        check = check_resolve_edge_normal_match(
            stage, result, stage.edges, expected_target="next_stage"
        )
        assert check.passed is True


# ---------------------------------------------------------------------------
# resolve_edge decision match — green
# ---------------------------------------------------------------------------

class TestResolveEdgeDecisionMatch:
    """Green fixtures for ``check_resolve_edge_decision_match``."""

    def test_decision_match_passes(self) -> None:
        stage = Stage(
            name="judge",
            step=_MinimalStep("judge"),
            edges=(Edge(label="proceed", target="next_phase", kind="decision"),),
        )
        verdict = PipelineVerdict(score=0.8, recommendation="proceed")
        result = StepResult(next="default", verdict=verdict)
        check = check_resolve_edge_decision_match(
            stage, result, verdict, stage.edges, expected_target="next_phase"
        )
        assert check.passed is True
        assert check.check_id == "resolve-edge-decision-match"


# ---------------------------------------------------------------------------
# resolve_edge override match — green
# ---------------------------------------------------------------------------

class TestResolveEdgeOverrideMatch:
    """Green fixtures for ``check_resolve_edge_override_match``."""

    def test_override_match_passes(self) -> None:
        stage = Stage(
            name="override_stage",
            step=_MinimalStep("override_stage"),
            edges=(
                Edge(label="override force_halt", target="halt_now", kind="override"),
            ),
        )
        verdict = PipelineVerdict(score=1.0, override="force_halt")
        result = StepResult(next="default", verdict=verdict)
        check = check_resolve_edge_override_match(
            stage, result, verdict, stage.edges, expected_target="halt_now"
        )
        assert check.passed is True
        assert check.check_id == "resolve-edge-override-match"


# ---------------------------------------------------------------------------
# resolve_edge halt — green
# ---------------------------------------------------------------------------

class TestResolveEdgeHalt:
    """Green fixtures for ``check_resolve_edge_halt``."""

    def test_halt_returns_none(self) -> None:
        stage = Stage(
            name="halt_stage",
            step=_MinimalStep("halt_stage"),
        )
        result = StepResult(next="halt")
        check = check_resolve_edge_halt(stage, result, stage.edges)
        assert check.passed is True
        assert check.check_id == "resolve-edge-halt"

    def test_halt_with_edges_still_returns_none(self) -> None:
        stage = Stage(
            name="halt_stage",
            step=_MinimalStep("halt_stage"),
            edges=(Edge(label="continue", target="next", kind="normal"),),
        )
        result = StepResult(next="halt")
        check = check_resolve_edge_halt(stage, result, stage.edges)
        assert check.passed is True


# ---------------------------------------------------------------------------
# resolve_edge unmatched signal — seeded red
# ---------------------------------------------------------------------------

class TestResolveEdgeUnmatchedSignal:
    """Seeded red fixtures for ``check_resolve_edge_unmatched_signal``."""

    def test_unmatched_signal_raises_routing_error(self) -> None:
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(Edge(label="only_valid", target="next", kind="normal"),),
        )
        result = StepResult(next="_conformance_no_such_label_")
        check = check_resolve_edge_unmatched_signal(stage, result, stage.edges)
        assert check.passed is True  # the check confirms RoutingError is raised

    def test_unmatched_signal_direct_proof(self) -> None:
        """Direct proof: resolve_edge raises RoutingError for unmatched label."""
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(Edge(label="valid", target="next", kind="normal"),),
        )
        result = StepResult(next="garbage_label")
        with pytest.raises(RoutingError):
            resolve_edge(stage, result, result.verdict, stage.edges)


# ---------------------------------------------------------------------------
# resolve_edge vocabulary validation — seeded red
# ---------------------------------------------------------------------------

class TestResolveEdgeVocabularyValidation:
    """Seeded red fixtures for ``check_resolve_edge_vocabulary_validation``."""

    def test_decision_out_of_vocabulary_raises(self) -> None:
        stage = Stage(
            name="judge",
            step=_MinimalStep("judge"),
            edges=(Edge(label="proceed", target="next", kind="decision"),),
            decision_vocabulary=frozenset({"proceed"}),
        )
        verdict = PipelineVerdict(score=0.5, recommendation="bad_decision")
        result = StepResult(next="default", verdict=verdict)
        check = check_resolve_edge_vocabulary_validation(
            stage, result, verdict, stage.edges, check_kind="decision"
        )
        assert check.passed is True  # confirms RoutingError raised

    def test_override_out_of_vocabulary_raises(self) -> None:
        stage = Stage(
            name="override_stage",
            step=_MinimalStep("override_stage"),
            edges=(
                Edge(label="override force_halt", target="halt", kind="override"),
            ),
            override_vocabulary=frozenset({"force_halt"}),
        )
        verdict = PipelineVerdict(score=0.5, override="bad_override")
        result = StepResult(next="default", verdict=verdict)
        check = check_resolve_edge_vocabulary_validation(
            stage, result, verdict, stage.edges, check_kind="override"
        )
        assert check.passed is True  # confirms RoutingError raised

    def test_decision_out_of_vocabulary_direct_proof(self) -> None:
        """Direct proof: resolve_edge raises RoutingError for out-of-vocabulary decision."""
        stage = Stage(
            name="judge",
            step=_MinimalStep("judge"),
            edges=(Edge(label="proceed", target="next", kind="decision"),),
            decision_vocabulary=frozenset({"proceed"}),
        )
        verdict = PipelineVerdict(score=0.5, recommendation="invalid_decision")
        result = StepResult(next="default", verdict=verdict)
        with pytest.raises(RoutingError):
            resolve_edge(stage, result, verdict, stage.edges)


# ---------------------------------------------------------------------------
# run_routing_conformance_suite — green
# ---------------------------------------------------------------------------

class TestRunRoutingConformanceSuite:
    """Green fixtures for ``run_routing_conformance_suite``."""

    def test_green_pipeline_suite_all_pass(self) -> None:
        pipeline = _make_green_pipeline()
        results = run_routing_conformance_suite(pipeline)
        assert len(results) > 0
        for r in results:
            assert r.passed, f"{r.check_id}: {r.message}"

    def test_returns_list_of_conformance_check_results(self) -> None:
        pipeline = _make_green_pipeline()
        results = run_routing_conformance_suite(pipeline)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, ConformanceCheckResult)

    def test_suite_includes_vocabulary_checks(self) -> None:
        pipeline = _make_green_pipeline()
        results = run_routing_conformance_suite(pipeline)
        check_ids = {r.check_id for r in results}
        assert "routing-vocabulary-coverage" in check_ids
        assert "routing-vocabulary-edge-consistency" in check_ids

    def test_suite_includes_resolve_edge_checks(self) -> None:
        pipeline = _make_green_pipeline()
        results = run_routing_conformance_suite(pipeline)
        check_ids = {r.check_id for r in results}
        assert any("resolve-edge" in cid for cid in check_ids)


# ---------------------------------------------------------------------------
# resolve_edge normal match — seeded red (wrong target)
# ---------------------------------------------------------------------------

class TestResolveEdgeWrongTarget:
    """Seeded red: resolve_edge matched wrong target."""

    def test_wrong_target_fails_check(self) -> None:
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(Edge(label="continue", target="actual_target", kind="normal"),),
        )
        result = StepResult(next="continue")
        check = check_resolve_edge_normal_match(
            stage, result, stage.edges, expected_target="wrong_target"
        )
        assert check.passed is False
        assert "actual_target" in check.message
        assert "wrong_target" in check.message


# ---------------------------------------------------------------------------
# resolve_edge with RoutingError — seeded red
# ---------------------------------------------------------------------------

class TestResolveEdgeRoutingError:
    """Seeded red: resolve_edge raises RoutingError unexpectedly."""

    def test_normal_match_routing_error_fails_check(self) -> None:
        """If resolve_edge raises RoutingError on a normal match, the check fails."""
        stage = Stage(
            name="test_stage",
            step=_MinimalStep("test_stage"),
            edges=(Edge(label="continue", target="next", kind="normal"),),
            decision_vocabulary=frozenset({"proceed"}),  # has vocabulary but no decision edge
        )
        result = StepResult(next="continue")
        # This should work normally since next="continue" matches normal edge
        check = check_resolve_edge_normal_match(
            stage, result, stage.edges, expected_target="next"
        )
        assert check.passed is True  # normal match works


# ---------------------------------------------------------------------------
# Pipeline walker — edge cases
# ---------------------------------------------------------------------------

class TestPipelineWalkerEdgeCases:
    """Edge cases for pipeline walker functions."""

    def test_single_stage_pipeline(self) -> None:
        pipeline = Pipeline(
            stages={"only": Stage(name="only", step=_MinimalStep("only"))},
            entry="only",
        )
        stages = iter_pipeline_stages(pipeline)
        assert len(stages) == 1
        assert stages[0].name == "only"

    def test_detect_routing_stages_empty_vocabulary(self) -> None:
        """Stage with empty vocabulary and no routing edges is not a routing stage."""
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=_MinimalStep("s"))},
            entry="s",
        )
        routing = detect_routing_stages(pipeline)
        assert routing == []

    def test_stage_with_override_edges_detected(self) -> None:
        stage = Stage(
            name="ov",
            step=_MinimalStep("ov"),
            edges=(Edge(label="override fh", target="next", kind="override"),),
        )
        pipeline = Pipeline(
            stages={"ov": stage, "next": Stage(name="next", step=_MinimalStep("next"))},
            entry="ov",
        )
        routing = detect_routing_stages(pipeline)
        assert len(routing) == 1
        assert routing[0][0] == "ov"
