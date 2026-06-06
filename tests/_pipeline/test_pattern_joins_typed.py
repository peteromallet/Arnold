"""T7 — pattern_joins typed-port flag-ON behavior."""
from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipelines.megaplan._pipeline.types import (
    PipelineVerdict,
    ReduceResult,
    StepContext,
    StepResult,
)
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    Suspension,
)


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")


def _vote(rec, reviewer_id=None):
    payload = {"reviewer_id": reviewer_id} if reviewer_id is not None else {}
    return StepResult(verdict=PipelineVerdict(score=1.0, recommendation=rec, payload=payload))


def test_majority_vote_flag_off_byte_identical(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    join = majority_vote()
    results = [_vote("iterate"), _vote("iterate"), _vote("proceed")]
    out = join(results, _ctx(tmp_path))
    assert out.verdict is not None
    assert out.verdict.recommendation == "iterate"
    assert out.next == "iterate"
    assert "reduce_result" not in dict(out.verdict.payload or {})


def test_majority_vote_flag_on_emits_reduce_result(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = majority_vote()
    results = [_vote("iterate"), _vote("iterate"), _vote("proceed")]
    out = join(results, _ctx(tmp_path))
    assert out.verdict is not None
    assert out.verdict.recommendation is None
    rr = out.verdict.payload["reduce_result"]
    assert isinstance(rr, ReduceResult)
    assert rr.label == "iterate"
    assert rr.tally == {"iterate": 2, "proceed": 1}
    assert out.next == "iterate"


def test_majority_vote_tie_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = majority_vote()
    out = join([_vote("iterate"), _vote("proceed")], _ctx(tmp_path))
    rr = out.verdict.payload["reduce_result"]
    assert rr.label is None
    assert out.next == "tiebreaker"


def test_weighted_vote_flag_off_byte_identical(monkeypatch, tmp_path):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    join = weighted_vote({"a": 2.0, "b": 1.0})
    out = join(
        [_vote("iterate", "a"), _vote("proceed", "b")], _ctx(tmp_path)
    )
    assert out.verdict.recommendation == "iterate"
    assert out.next == "iterate"


def test_weighted_vote_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    join = weighted_vote({"a": 2.0, "b": 1.0})
    out = join(
        [_vote("iterate", "a"), _vote("proceed", "b")], _ctx(tmp_path)
    )
    assert out.verdict.recommendation is None
    rr = out.verdict.payload["reduce_result"]
    assert isinstance(rr, ReduceResult)
    assert rr.label == "iterate"
    assert out.next == "iterate"


# ---------------------------------------------------------------------------
# Typed join contract reduction helpers
# ---------------------------------------------------------------------------


def _mk_contract(status=ContractStatus.COMPLETED, suspension=None):
    return ContractResult(status=status, suspension=suspension, payload={})


def _mk_suspension(resume_cursor="typed_cur"):
    return Suspension(kind="human", prompt="Typed test", resume_cursor=resume_cursor)


def _vote_with_contract(rec, reviewer_id=None, status=ContractStatus.COMPLETED, suspension=None):
    payload = {"reviewer_id": reviewer_id} if reviewer_id is not None else {}
    verdict = PipelineVerdict(score=1.0, recommendation=rec, payload=payload)
    contract = _mk_contract(status=status, suspension=suspension)
    return StepResult(verdict=verdict, contract_result=contract)


# ---------------------------------------------------------------------------
# Typed majority_vote contract reduction tests
# ---------------------------------------------------------------------------


class TestTypedMajorityVoteContractReduction:
    """Prove typed majority_vote recommendation unchanged + contract reduction."""

    def test_typed_majority_recommendation_unchanged_with_completed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        results = [
            _vote_with_contract("iterate", status=ContractStatus.COMPLETED),
            _vote_with_contract("iterate", status=ContractStatus.COMPLETED),
            _vote_with_contract("proceed", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        rr = out.verdict.payload["reduce_result"]
        assert rr.label == "iterate"
        assert out.next == "iterate"
        # Contract should be present and completed
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.COMPLETED

    def test_typed_majority_recommendation_unchanged_with_suspended(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        sus = _mk_suspension("typed_sus_cur")
        results = [
            _vote_with_contract("iterate", status=ContractStatus.SUSPENDED, suspension=sus),
            _vote_with_contract("iterate", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        # Recommendation should still be "iterate"
        rr = out.verdict.payload["reduce_result"]
        assert rr.label == "iterate"
        assert out.next == "iterate"
        # Contract status should be suspended (wins over completed)
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.SUSPENDED

    def test_typed_majority_recommendation_unchanged_with_failed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        results = [
            _vote_with_contract("iterate", status=ContractStatus.FAILED),
            _vote_with_contract("iterate", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        rr = out.verdict.payload["reduce_result"]
        assert rr.label == "iterate"
        assert out.next == "iterate"
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED

    def test_typed_majority_suspended_cursor_in_pending(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        sus = _mk_suspension("typed_pending_cur")
        results = [
            _vote_with_contract("a", status=ContractStatus.SUSPENDED, suspension=sus),
            _vote_with_contract("a", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        assert out.contract_result is not None
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "typed_pending_cur"

    def test_typed_majority_mixed_failed_suspended_wins_failed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        sus = _mk_suspension("mixed_cur")
        results = [
            _vote_with_contract("a", status=ContractStatus.SUSPENDED, suspension=sus),
            _vote_with_contract("a", status=ContractStatus.FAILED),
        ]
        out = join(results, _ctx(tmp_path))
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.FAILED
        # Suspended cursor still preserved in pending_suspensions
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "mixed_cur"

    def test_typed_majority_no_contracts_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = majority_vote()
        results = [_vote("a"), _vote("a")]
        out = join(results, _ctx(tmp_path))
        assert out.contract_result is None


# ---------------------------------------------------------------------------
# Typed weighted_vote contract reduction tests
# ---------------------------------------------------------------------------


class TestTypedWeightedVoteContractReduction:
    """Prove typed weighted_vote recommendation unchanged + contract reduction."""

    def test_typed_weighted_recommendation_unchanged_completed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = weighted_vote({"a": 2.0, "b": 1.0})
        results = [
            _vote_with_contract("iterate", "a", status=ContractStatus.COMPLETED),
            _vote_with_contract("proceed", "b", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        rr = out.verdict.payload["reduce_result"]
        assert rr.label == "iterate"
        assert out.next == "iterate"
        assert out.contract_result is not None
        assert out.contract_result.status == ContractStatus.COMPLETED

    def test_typed_weighted_suspended_wins_over_completed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = weighted_vote({"a": 2.0, "b": 1.0})
        sus = _mk_suspension("w_sus_cur")
        results = [
            _vote_with_contract("iterate", "a", status=ContractStatus.SUSPENDED, suspension=sus),
            _vote_with_contract("proceed", "b", status=ContractStatus.COMPLETED),
        ]
        out = join(results, _ctx(tmp_path))
        rr = out.verdict.payload["reduce_result"]
        # Winner is still "iterate" (heavier weight) but contract status is suspended
        assert rr.label == "iterate"
        assert out.contract_result.status == ContractStatus.SUSPENDED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "w_sus_cur"

    def test_typed_weighted_failed_wins_over_suspended(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = weighted_vote({"a": 1.0, "b": 1.0})
        sus = _mk_suspension("w_fail_cur")
        results = [
            _vote_with_contract("iterate", "a", status=ContractStatus.SUSPENDED, suspension=sus),
            _vote_with_contract("iterate", "b", status=ContractStatus.FAILED),
        ]
        out = join(results, _ctx(tmp_path))
        assert out.contract_result.status == ContractStatus.FAILED
        pending = list(out.contract_result.payload.get("pending_suspensions", []))
        assert len(pending) == 1
        assert pending[0]["cursor"] == "w_fail_cur"

    def test_typed_weighted_no_contracts_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        join = weighted_vote({"a": 1.0})
        results = [_vote("a", "a")]
        out = join(results, _ctx(tmp_path))
        assert out.contract_result is None
