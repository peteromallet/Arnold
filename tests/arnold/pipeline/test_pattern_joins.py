"""Tests for Arnold ``pattern_joins`` and the Megaplan bridge (M3a T15)."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import pytest

from arnold.pipeline.pattern_joins import majority_vote as arnold_majority_vote
from arnold.pipeline.pattern_joins import weighted_vote as arnold_weighted_vote
from arnold.pipeline.types import (
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    recommendation: str | None = None,
    payload: Mapping[str, Any] | None = None,
    next_label: str = "halt",
) -> StepResult:
    """Build a StepResult with an optional verdict."""
    verdict = None
    if recommendation is not None or payload is not None:
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=recommendation,
            payload=payload or {},
        )
    return StepResult(verdict=verdict, next=next_label)


def _ctx() -> StepContext:
    return StepContext(artifact_root="/tmp/test", state={})


def _make_weighted_result(
    recommendation: str,
    reviewer_id: str,
) -> StepResult:
    """Build a StepResult with a weighted-verdict payload."""
    verdict = PipelineVerdict(
        score=1.0,
        recommendation=recommendation,
        payload={"reviewer_id": reviewer_id},
    )
    return StepResult(verdict=verdict)


# ---------------------------------------------------------------------------
# Arnold (neutral) majority_vote tests
# ---------------------------------------------------------------------------


class TestArnoldMajorityVote:
    def test_clear_majority_wins(self) -> None:
        join = arnold_majority_vote()
        results = [
            _make_result("approve"),
            _make_result("approve"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.next == "approve"

    def test_tie_with_default_on_tie_none_halts(self) -> None:
        join = arnold_majority_vote(default_on_tie=None)
        results = [
            _make_result("approve"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"
        assert out.verdict is not None
        assert out.verdict.recommendation is None

    def test_tie_with_explicit_default_on_tie_uses_it(self) -> None:
        join = arnold_majority_vote(default_on_tie="fallback")
        results = [
            _make_result("approve"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        assert out.next == "fallback"
        assert out.verdict is not None
        assert out.verdict.recommendation == "fallback"

    def test_empty_panel_halts_when_default_on_tie_none(self) -> None:
        join = arnold_majority_vote(default_on_tie=None)
        out = join([], _ctx())
        assert out.next == "halt"
        assert out.verdict is not None
        assert out.verdict.recommendation is None

    def test_empty_panel_uses_default_on_tie(self) -> None:
        join = arnold_majority_vote(default_on_tie="nobody")
        out = join([], _ctx())
        assert out.next == "nobody"

    def test_typed_reduce_true_puts_reduce_result_in_payload(self) -> None:
        join = arnold_majority_vote(typed_reduce=True)
        results = [
            _make_result("approve"),
            _make_result("approve"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert "reduce_result" in out.verdict.payload
        assert out.verdict.recommendation is None  # typed mode hides plain recommendation

    def test_typed_reduce_false_puts_recommendation(self) -> None:
        join = arnold_majority_vote(typed_reduce=False)
        results = [
            _make_result("approve"),
            _make_result("approve"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.verdict.payload == {}

    def test_no_hardcoded_tiebreaker_label(self) -> None:
        """The Arnold function must not default to 'tiebreaker'."""
        join = arnold_majority_vote()  # no default_on_tie
        results = [
            _make_result("a"),
            _make_result("b"),
        ]
        out = join(results, _ctx())
        # No default → ties halt
        assert out.next == "halt"

    def test_label_extractor_overrides_default(self) -> None:
        def extract(r: StepResult) -> str | None:
            return "always_a"

        join = arnold_majority_vote(label_extractor=extract)
        results = [
            _make_result("anything"),
            _make_result("else"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "always_a"
        assert out.next == "always_a"

    def test_none_verdicts_are_skipped(self) -> None:
        join = arnold_majority_vote()
        results = [
            _make_result(None),  # no verdict
            _make_result("approve"),
            _make_result("approve"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"


# ---------------------------------------------------------------------------
# Arnold (neutral) weighted_vote tests
# ---------------------------------------------------------------------------


class TestArnoldWeightedVote:
    def test_highest_weight_wins(self) -> None:
        join = arnold_weighted_vote({"r1": 2.0, "r2": 1.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "a"

    def test_weight_tie_halts_with_default_on_tie_none(self) -> None:
        join = arnold_weighted_vote({"r1": 1.0, "r2": 1.0}, default_on_tie=None)
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"

    def test_empty_panel_halts(self) -> None:
        join = arnold_weighted_vote({"r1": 1.0}, default_on_tie=None)
        out = join([], _ctx())
        assert out.next == "halt"

    def test_unknown_reviewer_gets_zero_weight(self) -> None:
        join = arnold_weighted_vote({"r1": 2.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "unknown"),  # weight 0.0
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "a"

    def test_typed_reduce_true(self) -> None:
        join = arnold_weighted_vote({"r1": 1.0}, typed_reduce=True)
        results = [_make_weighted_result("a", "r1")]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert "reduce_result" in out.verdict.payload
        assert out.verdict.recommendation is None

    def test_no_hardcoded_tiebreaker_label(self) -> None:
        """The Arnold function must not default to 'tiebreaker'."""
        join = arnold_weighted_vote({"r1": 1.0, "r2": 1.0})  # no default_on_tie
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"


# ---------------------------------------------------------------------------
# Megaplan bridge isolation tests
# ---------------------------------------------------------------------------


class TestMegaplanBridgeJoins:
    def test_bridge_majority_vote_uses_tiebreaker_default(self) -> None:
        """The Megaplan bridge must default to 'tiebreaker'."""
        from megaplan._pipeline.pattern_joins import majority_vote as mega_majority

        join = mega_majority()  # uses legacy default_on_tie='tiebreaker'
        results = [
            _make_result("approve"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        # Tie → should use 'tiebreaker'
        assert out.next == "tiebreaker"

    def test_bridge_weighted_vote_uses_tiebreaker_default(self) -> None:
        from megaplan._pipeline.pattern_joins import weighted_vote as mega_weighted

        join = mega_weighted({"r1": 1.0, "r2": 1.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.next == "tiebreaker"

    def test_bridge_delegates_to_arnold_core(self) -> None:
        """The Megaplan bridge must delegate to Arnold functions."""
        from megaplan._pipeline.pattern_joins import majority_vote as mega_majority
        from arnold.pipeline.pattern_joins import majority_vote as arnold_maj

        # Both should produce the same result for the same inputs.
        join_a = arnold_maj(default_on_tie="tiebreaker", typed_reduce=False)
        join_b = mega_majority()

        results = [_make_result("x"), _make_result("x")]
        out_a = join_a(results, _ctx())
        out_b = join_b(results, _ctx())

        assert out_a.next == out_b.next
        assert out_a.verdict is not None
        assert out_b.verdict is not None
        assert out_a.verdict.recommendation == out_b.verdict.recommendation


# ---------------------------------------------------------------------------
# Arnold boundary — no Megaplan imports
# ---------------------------------------------------------------------------


class TestPatternJoinsBoundary:
    def test_pattern_joins_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "pattern_joins.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"pattern_joins.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"pattern_joins.py imports from megaplan: {node.module!r}"
                    )

    def test_pattern_joins_has_no_forbidden_literals(self) -> None:
        import ast
        from pathlib import Path as P

        forbidden = frozenset({"planning", "proceed", "iterate", "escalate"})
        src = P(__file__).parents[3] / "arnold" / "pipeline" / "pattern_joins.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden, (
                    f"pattern_joins.py contains forbidden literal: {node.value!r}"
                )

    def test_pattern_joins_has_no_typed_ports_import(self) -> None:
        """The Arnold core must not import typed_ports_on."""
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "pattern_joins.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        assert alias.name != "typed_ports_on", (
                            "pattern_joins.py must not import typed_ports_on"
                        )


# ---------------------------------------------------------------------------
# T21 extensions — additional join tests
# ---------------------------------------------------------------------------


class TestMajorityVoteTally:
    """Extended majority_vote tests covering tally, scores, and provenance."""

    def test_tally_reflects_vote_counts(self) -> None:
        join = arnold_majority_vote()
        results = [
            _make_result("approve"),
            _make_result("approve"),
            _make_result("reject"),
            _make_result("approve"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        rr = out.verdict.payload.get("reduce_result")
        # typed_reduce=False → payload is empty {}
        # recommendation carries the winner
        assert out.verdict.recommendation == "approve"
        assert out.next == "approve"

    def test_reduce_result_in_payload_when_typed(self) -> None:
        join = arnold_majority_vote(typed_reduce=True)
        results = [
            _make_result("a"),
            _make_result("a"),
            _make_result("b"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        rr = out.verdict.payload.get("reduce_result")
        assert rr is not None
        assert rr.value == "a"
        assert rr.label == "a"
        assert rr.tally == {"a": 2, "b": 1}
        assert len(rr.scores) == 2  # (2.0, 1.0)

    def test_three_way_tie_halts_with_no_default(self) -> None:
        join = arnold_majority_vote(default_on_tie=None)
        results = [
            _make_result("a"),
            _make_result("b"),
            _make_result("c"),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"
        assert out.verdict.recommendation is None

    def test_unanimous_vote_wins(self) -> None:
        join = arnold_majority_vote()
        results = [
            _make_result("yes"),
            _make_result("yes"),
            _make_result("yes"),
        ]
        out = join(results, _ctx())
        assert out.next == "yes"
        assert out.verdict.recommendation == "yes"

    def test_panel_output_key_reserved_parameter(self) -> None:
        """panel_output_key is reserved — majority_vote ignores it today."""
        join = arnold_majority_vote(panel_output_key="custom_key")
        results = [
            _make_result("x"),
            _make_result("x"),
        ]
        out = join(results, _ctx())
        assert out.verdict.recommendation == "x"


class TestWeightedVoteExtended:
    """Extended weighted_vote tests."""

    def test_zero_weight_reviewers_do_not_affect_outcome(self) -> None:
        join = arnold_weighted_vote({"r1": 2.0, "r2": 0.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),  # weight 0
        ]
        out = join(results, _ctx())
        assert out.verdict.recommendation == "a"

    def test_all_zero_weights_halts(self) -> None:
        join = arnold_weighted_vote({"r1": 0.0, "r2": 0.0}, default_on_tie=None)
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"

    def test_weighted_reduce_result_typed(self) -> None:
        join = arnold_weighted_vote({"r1": 2.0, "r2": 1.0}, typed_reduce=True)
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        rr = out.verdict.payload.get("reduce_result")
        assert rr is not None
        assert rr.value == "a"
        assert "r1" in str(rr.tally) or rr.tally.get("a") == 1

    def test_no_reviewer_id_in_payload_defaults_to_zero(self) -> None:
        """When payload has no reviewer_id, weight defaults to 0.0."""
        join = arnold_weighted_vote({"r1": 2.0}, default_on_tie=None)
        results = [
            _make_result("a"),  # no reviewer_id
        ]
        out = join(results, _ctx())
        assert out.next == "halt"  # zero weight → no votes

    def test_negative_weights_treated_normally(self) -> None:
        """Negative weights accumulate (not rejected)."""
        join = arnold_weighted_vote({"r1": -1.0, "r2": 2.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.verdict.recommendation == "b"

    def test_non_dict_payload_handled(self) -> None:
        """When verdict.payload is not a Mapping, reviewer_id defaults to None."""
        verdict = PipelineVerdict(score=1.0, recommendation="x", payload=42)  # type: ignore[arg-type]
        result = StepResult(verdict=verdict)
        join = arnold_weighted_vote({"r1": 1.0}, default_on_tie=None)
        out = join([result], _ctx())
        assert out.next == "halt"  # no reviewer_id found


class TestJoinContextIgnored:
    """Verify ctx is ignored by vote functions (state-agnostic)."""

    def test_majority_vote_ignores_ctx(self) -> None:
        join = arnold_majority_vote()
        ctx1 = StepContext(artifact_root="/a", state={})
        ctx2 = StepContext(artifact_root="/b", state={"key": "val"})
        r1 = join([_make_result("x")], ctx1)
        r2 = join([_make_result("x")], ctx2)
        assert r1.next == r2.next

    def test_weighted_vote_ignores_ctx(self) -> None:
        join = arnold_weighted_vote({"r1": 1.0})
        ctx1 = StepContext(artifact_root="/a", state={"x": 1})
        ctx2 = StepContext(artifact_root="/b", state={})
        r1 = join([_make_weighted_result("x", "r1")], ctx1)
        r2 = join([_make_weighted_result("x", "r1")], ctx2)
        assert r1.next == r2.next
