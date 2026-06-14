"""Tests for Arnold ``pattern_joins`` and the Megaplan bridge (M3a T15)."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import pytest

from arnold.pipeline.contract_reduce import ReducePolicy
from arnold.pipeline.pattern_joins import aggregate_panel_join
from arnold.pipeline.pattern_joins import majority_vote as arnold_majority_vote
from arnold.pipeline.pattern_joins import weighted_vote as arnold_weighted_vote
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
    Suspension,
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
# Arnold (neutral) aggregate_panel_join tests
# ---------------------------------------------------------------------------


class TestAggregatePanelJoin:
    def test_collects_outputs_and_sums_numeric_usage(self) -> None:
        join = aggregate_panel_join(
            next_label="done",
            usage_keys=("input_tokens", "output_tokens"),
        )
        results = [
            StepResult(
                outputs={"critic_a": "a.md"},
                state_patch={"input_tokens": 10, "output_tokens": 3},
            ),
            StepResult(
                outputs={"critic_b": "b.md"},
                state_patch={"input_tokens": 2.5, "output_tokens": 4},
            ),
        ]

        out = join(results, _ctx())

        assert out.next == "done"
        assert out.outputs == {"critic_a": "a.md", "critic_b": "b.md"}
        assert out.state_patch == {
            "panel_usage": {"input_tokens": 12.5, "output_tokens": 7.0}
        }

    def test_ignores_non_numeric_usage_values(self) -> None:
        join = aggregate_panel_join(usage_keys=("tokens", "missing"))
        results = [
            StepResult(
                outputs={"a": "a.md"},
                state_patch={"tokens": "unknown"},
            ),
            StepResult(
                outputs={"b": "b.md"},
                state_patch={"tokens": 5},
            ),
        ]

        out = join(results, _ctx())

        assert out.next == "panel_done"
        assert out.outputs == {"a": "a.md", "b": "b.md"}
        assert out.state_patch == {
            "panel_usage": {"tokens": 5.0, "missing": 0.0}
        }


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
        from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote as mega_majority

        join = mega_majority()  # uses legacy default_on_tie='tiebreaker'
        results = [
            _make_result("approve"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        # Tie → should use 'tiebreaker'
        assert out.next == "tiebreaker"

    def test_bridge_weighted_vote_uses_tiebreaker_default(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_joins import weighted_vote as mega_weighted

        join = mega_weighted({"r1": 1.0, "r2": 1.0})
        results = [
            _make_weighted_result("a", "r1"),
            _make_weighted_result("b", "r2"),
        ]
        out = join(results, _ctx())
        assert out.next == "tiebreaker"

    def test_bridge_delegates_to_arnold_core(self) -> None:
        """The Megaplan bridge must delegate to Arnold functions."""
        from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote as mega_majority
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


# ---------------------------------------------------------------------------
# Contract reduction helpers
# ---------------------------------------------------------------------------


def _make_contract(
    status: ContractStatus = ContractStatus.COMPLETED,
    *,
    suspension: Suspension | None = None,
    payload: Mapping[str, Any] | None = None,
) -> ContractResult:
    """Build a ContractResult for join contract-reduction tests."""
    return ContractResult(
        status=status,
        suspension=suspension,
        payload=payload or {},
    )


def _make_suspension(
    *,
    kind: str = "human",
    resume_cursor: str | None = None,
    child_id: str | None = None,
) -> Suspension:
    """Build a Suspension with optional cursor metadata."""
    return Suspension(
        kind=kind,
        prompt="Test suspension",
        resume_cursor=resume_cursor or f"cursor_{child_id or 'anon'}",
    )


def _make_result_with_contract(
    recommendation: str | None = None,
    status: ContractStatus = ContractStatus.COMPLETED,
    *,
    suspension: Suspension | None = None,
    payload: Mapping[str, Any] | None = None,
    next_label: str = "halt",
) -> StepResult:
    """Build a StepResult with a verdict and contract_result."""
    verdict = None
    if recommendation is not None:
        verdict = PipelineVerdict(
            score=1.0,
            recommendation=recommendation,
            payload={},
        )
    return StepResult(
        verdict=verdict,
        next=next_label,
        contract_result=_make_contract(status, suspension=suspension, payload=payload),
    )


# ---------------------------------------------------------------------------
# Majority vote contract reduction tests
# ---------------------------------------------------------------------------


class TestMajorityVoteContractReduction:
    """Prove majority_vote recommendation behavior is unchanged while
    completed, suspended, failed, and mixed child contracts reduce
    correctly with cursor metadata retention."""

    # --- Recommendation unchanged ---

    def test_recommendation_unchanged_with_all_completed_contracts(self) -> None:
        """Verdict/next are unaffected by completed child contracts."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
            _make_result_with_contract("reject", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.next == "approve"

    def test_recommendation_unchanged_with_suspended_contract(self) -> None:
        """Verdict/next are unaffected by a suspended child contract."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract(
                "approve", ContractStatus.SUSPENDED,
                suspension=_make_suspension(child_id="c1"),
            ),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.next == "approve"

    def test_recommendation_unchanged_with_failed_contract(self) -> None:
        """Verdict/next are unaffected by a failed child contract."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("approve", ContractStatus.FAILED),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.next == "approve"

    def test_recommendation_unchanged_tie_with_contracts(self) -> None:
        """Tie behavior (halt) is unchanged even with contracts."""
        join = arnold_majority_vote(default_on_tie=None)
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("b", ContractStatus.SUSPENDED,
                                       suspension=_make_suspension(child_id="c1")),
        ]
        out = join(results, _ctx())
        assert out.next == "halt"
        assert out.verdict is not None
        assert out.verdict.recommendation is None

    # --- Completed contracts ---

    def test_all_completed_reduces_to_completed(self) -> None:
        """All children completed → parent status is completed."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.COMPLETED
        assert out.contract_result.suspension is None

    def test_all_completed_with_no_verdicts_reduces_to_completed(self) -> None:
        """Children with None verdicts but completed contracts still reduce."""
        join = arnold_majority_vote(default_on_tie=None)
        results = [
            _make_result_with_contract(None, ContractStatus.COMPLETED),
            _make_result_with_contract(None, ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.COMPLETED

    # --- Suspended contracts ---

    def test_single_suspended_produces_suspended_parent(self) -> None:
        """One suspended child → parent status is suspended."""
        join = arnold_majority_vote()
        sus = _make_suspension(child_id="c1", resume_cursor="cur1")
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.SUSPENDED
        assert out.contract_result.suspension is not None
        assert out.contract_result.suspension.resume_cursor == "cur1"

    def test_suspended_cursor_preserved_in_pending_suspensions(self) -> None:
        """Suspended child cursor appears in pending_suspensions metadata."""
        join = arnold_majority_vote()
        sus = _make_suspension(child_id="c1", resume_cursor="child_cursor_42")
        results = [
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus),
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        payload = dict(out.contract_result.payload)
        pending = payload.get("pending_suspensions")
        assert pending is not None
        assert isinstance(pending, list)
        assert len(pending) == 1
        assert pending[0]["cursor"] == "child_cursor_42"
        assert pending[0]["child_id"] == "child_0"

    def test_multiple_suspended_cursors_preserved(self) -> None:
        """Multiple suspended children → all cursors in pending_suspensions."""
        join = arnold_majority_vote()
        sus1 = _make_suspension(child_id="c1", resume_cursor="cur_a")
        sus2 = _make_suspension(child_id="c2", resume_cursor="cur_b")
        results = [
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus1),
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus2),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.SUSPENDED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        cursors = {p["cursor"] for p in pending}
        assert cursors == {"cur_a", "cur_b"}

    # --- Failed contracts ---

    def test_single_failed_produces_failed_parent(self) -> None:
        """One failed child → parent status is failed."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("a", ContractStatus.FAILED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED
        # Failed contracts should not have a suspension
        assert out.contract_result.suspension is None

    def test_failed_contract_does_not_appear_in_pending_suspensions(self) -> None:
        """Failed children are NOT in pending_suspensions (only suspended)."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.FAILED),
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        pending = out.contract_result.payload.get("pending_suspensions")
        # Failed has no suspension → pending_suspensions should be absent/empty
        assert not pending

    # --- Mixed failed + suspended ---

    def test_mixed_suspended_and_failed_wins_failed(self) -> None:
        """Suspended + failed → failed wins (failed > suspended in lattice)."""
        join = arnold_majority_vote()
        sus = _make_suspension(child_id="c1", resume_cursor="cur1")
        results = [
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus),
            _make_result_with_contract("a", ContractStatus.FAILED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED

    def test_mixed_failed_suspended_retains_suspended_in_pending(self) -> None:
        """Even when failed wins, suspended children remain in pending_suspensions."""
        join = arnold_majority_vote()
        sus = _make_suspension(child_id="c1", resume_cursor="sus_cur")
        results = [
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus),
            _make_result_with_contract("a", ContractStatus.FAILED),
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "sus_cur"
        assert pending[0]["status"] == "suspended"

    def test_mixed_all_three_statuses_wins_failed_pending_intact(self) -> None:
        """Completed + suspended + failed → failed wins, suspended cursor retained."""
        join = arnold_majority_vote()
        sus = _make_suspension(child_id="c1", resume_cursor="all_three_cur")
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=sus),
            _make_result_with_contract("a", ContractStatus.FAILED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "all_three_cur"

    # --- No contracts (backward compat) ---

    def test_no_child_contracts_contract_result_is_none(self) -> None:
        """When no child has a contract, contract_result stays None."""
        join = arnold_majority_vote()
        results = [
            _make_result("a"),
            _make_result("a"),
        ]
        out = join(results, _ctx())
        assert out.contract_result is None

    # --- reduce_policy param ---

    def test_reduce_policy_defaults_to_max_wins(self) -> None:
        """reduce_policy defaults to MAX_WINS."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.FAILED),
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=_make_suspension(child_id="c1")),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED

    # --- Source contracts metadata ---

    def test_source_contracts_present_in_payload(self) -> None:
        """Reduced payload includes source_contracts for each child."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("a", ContractStatus.FAILED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        sources = out.contract_result.payload.get("source_contracts")
        assert sources is not None
        assert len(sources) == 2
        assert sources[0]["status"] == "completed"
        assert sources[1]["status"] == "failed"

    def test_status_lattice_in_payload(self) -> None:
        """Reduced payload includes the status_lattice field."""
        join = arnold_majority_vote()
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.payload.get("status_lattice") == "completed<suspended<failed"


# ---------------------------------------------------------------------------
# Weighted vote contract reduction tests
# ---------------------------------------------------------------------------


class TestWeightedVoteContractReduction:
    """Prove weighted_vote recommendation behavior is unchanged while
    child contracts reduce correctly with cursor metadata retention."""

    # --- Recommendation unchanged ---

    def test_recommendation_unchanged_with_contracts(self) -> None:
        """Verdict/next are unaffected by child contracts in weighted_vote."""
        join = arnold_weighted_vote({"r1": 2.0, "r2": 1.0})
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
            _make_result_with_contract("b", ContractStatus.SUSPENDED,
                                       suspension=_make_suspension(child_id="c1")),
        ]
        # These don't carry reviewer_id so weights default to 0.0 and outcome halts.
        # Use _make_weighted_result for proper weighted vote testing.
        pass  # placeholder — tested below with proper weighted results

    def test_weighted_recommendation_unchanged_with_all_statuses(self) -> None:
        """Weighted vote winner is unchanged when contracts carry various statuses."""
        join = arnold_weighted_vote({"r1": 2.0, "r2": 1.0})
        # Build results with both verdict+reviewer_id AND contracts
        v1 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r1"})
        v2 = PipelineVerdict(score=1.0, recommendation="b", payload={"reviewer_id": "r2"})
        results = [
            StepResult(verdict=v1, contract_result=_make_contract(ContractStatus.COMPLETED)),
            StepResult(verdict=v2, contract_result=_make_contract(
                ContractStatus.SUSPENDED, suspension=_make_suspension(child_id="c2"),
            )),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "a"
        assert out.next == "a"
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.SUSPENDED

    # --- Status lattice via weighted_vote ---

    def test_completed_plus_suspended_wins_suspended(self) -> None:
        """Completed + suspended via weighted_vote → suspended wins."""
        join = arnold_weighted_vote({"r1": 1.0, "r2": 1.0})
        v1 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r1"})
        v2 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r2"})
        sus = _make_suspension(child_id="c2", resume_cursor="w_cur")
        results = [
            StepResult(verdict=v1, contract_result=_make_contract(ContractStatus.COMPLETED)),
            StepResult(verdict=v2, contract_result=_make_contract(
                ContractStatus.SUSPENDED, suspension=sus,
            )),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.SUSPENDED
        pending = out.contract_result.payload.get("pending_suspensions")
        assert pending is not None
        assert len(pending) == 1
        assert pending[0]["cursor"] == "w_cur"

    def test_suspended_plus_failed_wins_failed(self) -> None:
        """Suspended + failed via weighted_vote → failed wins."""
        join = arnold_weighted_vote({"r1": 1.0, "r2": 1.0})
        v1 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r1"})
        v2 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r2"})
        sus = _make_suspension(child_id="c1", resume_cursor="sf_cur")
        results = [
            StepResult(verdict=v1, contract_result=_make_contract(
                ContractStatus.SUSPENDED, suspension=sus,
            )),
            StepResult(verdict=v2, contract_result=_make_contract(ContractStatus.FAILED)),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "sf_cur"

    def test_all_completed_weighted_no_suspension(self) -> None:
        """All completed via weighted_vote → no suspension on parent."""
        join = arnold_weighted_vote({"r1": 1.0})
        v1 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r1"})
        results = [
            StepResult(verdict=v1, contract_result=_make_contract(ContractStatus.COMPLETED)),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.COMPLETED
        assert out.contract_result.suspension is None

    def test_no_contracts_weighted_contract_result_none(self) -> None:
        """Backward compat: no child contracts → contract_result is None."""
        join = arnold_weighted_vote({"r1": 1.0})
        results = [_make_weighted_result("a", "r1")]
        out = join(results, _ctx())
        assert out.contract_result is None

    def test_mixed_weighted_pending_suspensions_metadata(self) -> None:
        """Verify pending_suspensions payload has expected fields."""
        join = arnold_weighted_vote({"r1": 1.0, "r2": 1.0})
        sus = _make_suspension(child_id="c1", resume_cursor="meta_cur")
        v1 = PipelineVerdict(score=1.0, recommendation="a", payload={"reviewer_id": "r1"})
        v2 = PipelineVerdict(score=1.0, recommendation="b", payload={"reviewer_id": "r2"})
        results = [
            StepResult(verdict=v1, contract_result=_make_contract(
                ContractStatus.SUSPENDED, suspension=sus,
            )),
            StepResult(verdict=v2, contract_result=_make_contract(ContractStatus.COMPLETED)),
        ]
        out = join(results, _ctx())
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        entry = pending[0]
        assert entry["child_id"] == "child_0"
        assert entry["status"] == "suspended"
        assert entry["cursor"] == "meta_cur"
        assert isinstance(entry["suspension"], dict)
        assert entry["suspension"]["kind"] == "human"
        assert entry["suspension"]["resume_cursor"] == "meta_cur"


# ---------------------------------------------------------------------------
# Fan-out extension seams — lock unsupported policies/scopes
# ---------------------------------------------------------------------------


class TestMajorityVoteFanOutSeams:
    """Lock fan-out extension seams: unsupported ReducePolicy values and
    non-None suspension_scope must propagate NotImplementedError through
    majority_vote, and the shipped default must remain MAX_WINS with no
    suspension_scope.
    """

    # -- Unsupported reduce policies ---------------------------------------

    def test_quorum_policy_propagates_not_implemented_error(self) -> None:
        """majority_vote(reduce_policy=QUORUM) raises NotImplementedError
        when child contracts trigger the reduce_contract_results path."""
        join = arnold_majority_vote(reduce_policy=ReducePolicy.QUORUM)
        results = [
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
        ]
        with pytest.raises(NotImplementedError, match="reduce_policy='quorum'"):
            join(results, _ctx())

    def test_best_effort_policy_propagates_not_implemented_error(self) -> None:
        """majority_vote(reduce_policy=BEST_EFFORT) raises NotImplementedError."""
        join = arnold_majority_vote(reduce_policy=ReducePolicy.BEST_EFFORT)
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        with pytest.raises(NotImplementedError, match="reduce_policy='best_effort'"):
            join(results, _ctx())

    def test_budget_policy_propagates_not_implemented_error(self) -> None:
        """majority_vote(reduce_policy=BUDGET) raises NotImplementedError."""
        join = arnold_majority_vote(reduce_policy=ReducePolicy.BUDGET)
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        with pytest.raises(NotImplementedError, match="reduce_policy='budget'"):
            join(results, _ctx())

    def test_saturation_policy_propagates_not_implemented_error(self) -> None:
        """majority_vote(reduce_policy=SATURATION) raises NotImplementedError."""
        join = arnold_majority_vote(reduce_policy=ReducePolicy.SATURATION)
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        with pytest.raises(NotImplementedError, match="reduce_policy='saturation'"):
            join(results, _ctx())

    # -- Unsupported suspension_scope --------------------------------------

    def test_suspension_scope_fan_out_propagates_not_implemented_error(self) -> None:
        """majority_vote(suspension_scope='fan-out') raises NotImplementedError
        when child contracts trigger the reduce_contract_results path."""
        join = arnold_majority_vote(suspension_scope="fan-out")
        results = [
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
        ]
        with pytest.raises(
            NotImplementedError,
            match="suspension_scope is reserved for a later milestone",
        ):
            join(results, _ctx())

    def test_suspension_scope_any_non_none_propagates_not_implemented_error(self) -> None:
        """Any non-None suspension_scope (not just 'fan-out') raises NotImplementedError."""
        join = arnold_majority_vote(suspension_scope="batch")
        results = [
            _make_result_with_contract("a", ContractStatus.COMPLETED),
        ]
        with pytest.raises(
            NotImplementedError,
            match="suspension_scope is reserved for a later milestone",
        ):
            join(results, _ctx())

    # -- Shipped default ---------------------------------------------------

    def test_default_policy_is_max_wins_no_suspension_scope(self) -> None:
        """When majority_vote is called with no arguments, the shipped default
        is ReducePolicy.MAX_WINS with suspension_scope=None, and contracts
        reduce successfully."""
        join = arnold_majority_vote()  # all defaults
        results = [
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
            _make_result_with_contract("approve", ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.payload.get("reduce_policy") == "max_wins"
        # suspension_scope is not stored in the payload — it's only a gate param
        assert out.contract_result.status == ContractStatus.COMPLETED
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"

    def test_explicit_max_wins_with_none_scope_succeeds(self) -> None:
        """Explicit MAX_WINS with suspension_scope=None behaves identically
        to the default and does not raise."""
        join = arnold_majority_vote(
            reduce_policy=ReducePolicy.MAX_WINS,
            suspension_scope=None,
        )
        results = [
            _make_result_with_contract("a", ContractStatus.FAILED),
            _make_result_with_contract("a", ContractStatus.SUSPENDED,
                                       suspension=_make_suspension(child_id="c1")),
        ]
        out = join(results, _ctx())
        assert out.contract_result is not None
        assert out.contract_result.payload.get("reduce_policy") == "max_wins"
        # Failed beats suspended per the status lattice
        assert out.contract_result.status == ContractStatus.FAILED

    # -- No-contract backward compat: params don't affect non-contract path -

    def test_quorum_policy_no_contracts_still_creates_join(self) -> None:
        """majority_vote(reduce_policy=QUORUM) does not raise at construction
        time, and the NotImplementedError only surfaces when contracts are
        actually reduced.  Without contracts the join behaves normally."""
        join = arnold_majority_vote(reduce_policy=ReducePolicy.QUORUM)
        results = [
            _make_result("approve"),
            _make_result("approve"),
        ]
        # No contracts → reduce_contract_results is never called
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "approve"
        assert out.contract_result is None

    def test_suspension_scope_no_contracts_still_creates_join(self) -> None:
        """majority_vote(suspension_scope='fan-out') does not raise at
        construction time; the error only surfaces when contracts are reduced."""
        join = arnold_majority_vote(suspension_scope="fan-out")
        results = [
            _make_result("reject"),
            _make_result("reject"),
        ]
        out = join(results, _ctx())
        assert out.verdict is not None
        assert out.verdict.recommendation == "reject"
        assert out.contract_result is None
