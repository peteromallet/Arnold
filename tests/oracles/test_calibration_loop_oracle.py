"""M5 T18 — synthetic calibration-loop oracle.

Simulates a co-degradation trace where a cheap routed model is "verified" by
an even cheaper reviewer that rubber-stamps a bad result. The oracle asserts
that the reviewer invariant marks the trace low-confidence and that the noisy
signal never enters shared aggregation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.calibration import (
    CapabilityClaim,
    EvaluandRef,
    aggregate_weighted_tier,
    check_reviewer_invariant,
    filter_shared_claims,
    read_capability_claims,
    resolve_evaluand,
    write_capability_claim,
)
from arnold_pipelines.megaplan.observability.evaluand import EvaluandRecord, write_evaluand_event


def _make_ref(piece_version: str) -> EvaluandRef:
    return EvaluandRef(
        piece_version=piece_version,
        judge_version="judge:v1",
        rubric_version="rubric:v1",
        input_set_hash="input:loop",
    )


def test_cheap_verifier_rubber_stamp_is_low_confidence_and_not_shared(tmp_path: Path) -> None:
    strong_ref = _make_ref("candidate:trusted")
    weak_ref = _make_ref("candidate:cheap-rubber-stamp")
    write_evaluand_event(
        "trusted-run",
        EvaluandRecord(
            judge_version=strong_ref.judge_version,
            rubric_version=strong_ref.rubric_version,
            input_set_hash=strong_ref.input_set_hash,
            score=0.94,
            piece_version=strong_ref.piece_version,
            provenance={"oracle": "trusted"},
            taint=(),
        ),
        plan_dir=tmp_path,
        phase="judge",
        scope="oracle",
    )
    write_evaluand_event(
        "cheap-run",
        EvaluandRecord(
            judge_version=weak_ref.judge_version,
            rubric_version=weak_ref.rubric_version,
            input_set_hash=weak_ref.input_set_hash,
            score=0.11,
            piece_version=weak_ref.piece_version,
            provenance={"oracle": "cheap-rubber-stamp"},
            taint=(),
        ),
        plan_dir=tmp_path,
        phase="judge",
        scope="oracle",
    )

    low_confidence, reason = check_reviewer_invariant(
        routed_model_tier=3,
        verifier_tier=2,
    )
    assert low_confidence is True
    assert reason is not None
    assert "verifier_tier" in reason

    trusted_claim = CapabilityClaim(
        outcome=strong_ref,
        task_signature="oracle:calibration-loop",
        routed_model="executor:trusted",
        recorded_at=10_000.0,
        predicted_tier=4,
        verifier_tier="4",
        verifier_identity="reviewer:strong",
        low_confidence_signal=False,
    )
    rubber_stamp_claim = CapabilityClaim(
        outcome=weak_ref,
        task_signature="oracle:calibration-loop",
        routed_model="executor:cheap",
        recorded_at=10_000.0,
        predicted_tier=1,
        verifier_tier="2",
        verifier_identity="reviewer:cheaper",
        low_confidence_signal=low_confidence,
    )
    write_capability_claim(trusted_claim, plan_dir=tmp_path, phase="execute", scope="oracle")
    write_capability_claim(
        rubber_stamp_claim,
        plan_dir=tmp_path,
        phase="execute",
        scope="oracle",
    )

    claims = read_capability_claims(tmp_path)
    assert len(claims) == 2
    weak_resolution = resolve_evaluand(tmp_path, weak_ref)
    assert weak_resolution.is_available is True
    assert weak_resolution.record.score == pytest.approx(0.11)

    shared_claims = filter_shared_claims(claims)
    assert shared_claims == (trusted_claim,)
    assert aggregate_weighted_tier(shared_claims, now=10_000.0) == pytest.approx(4.0)
    assert aggregate_weighted_tier(claims, now=10_000.0) == pytest.approx(2.5)
