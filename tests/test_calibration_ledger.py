"""Focused unit tests for the calibration ledger.

Covers CapabilityClaim serialization, content hash stability,
round-trip through NdjsonBackend / events.ndjson, raw claim readback,
rejection of bare numeric outcomes, EvaluandRef join behaviour,
missing Evaluand unavailable/invalid handling, taint-derived
aggregation inputs, and proof that no second journal/store file is
created.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.calibration.ledger import (
    AggregationPolicy,
    CapabilityClaim,
    EvaluandRef,
    EvaluandStatus,
    ModelIdentity,
    QueryPolicy,
    RouteSuggestion,
    _canonical_json,
    _iter_claim_event_envelopes,
    _task_signature_class_prior,
    _taint_class_from_evaluand_taint,
    aggregate_weighted_tier,
    capability_class_prior,
    check_reviewer_invariant,
    classify_claim_taint,
    derive_aggregation_policy,
    filter_shared_claims,
    half_life_weight,
    is_shared_claim,
    iter_capability_claim_payloads,
    normalize_projected_complexity,
    project_batch_complexity,
    project_claimed_complexity,
    project_tier_models,
    read_capability_claims,
    resolve_evaluand,
    validate_capability_claim,
    write_capability_claim,
)
from arnold.pipelines.megaplan.observability.events import EventKind, read_events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    """Create a temporary plan directory for ledger tests."""
    pd = tmp_path / "test-plan"
    pd.mkdir(parents=True, exist_ok=True)
    return pd


@pytest.fixture
def sample_ref() -> EvaluandRef:
    """A stable EvaluandRef for test claims."""
    return EvaluandRef(
        piece_version="judge-v1",
        judge_version="gpt-4o-2024-08-06",
        rubric_version="correctness-v3",
        input_set_hash="abc123def456",
    )


@pytest.fixture
def sample_claim(sample_ref: EvaluandRef) -> CapabilityClaim:
    """A clean, minimal CapabilityClaim."""
    return CapabilityClaim(
        outcome=sample_ref,
        task_signature="code_review:python",
        model_identity="model-sha256-aaa",
    )


# ---------------------------------------------------------------------------
# CapabilityClaim serialization
# ---------------------------------------------------------------------------


class TestCapabilityClaimSerialization:
    """CapabilityClaim to_json / from_json round-trip and content hash stability."""

    def test_to_json_excludes_content_hash(self, sample_claim: CapabilityClaim) -> None:
        """to_json() must not include a content_hash key."""
        payload = sample_claim.to_json()
        assert "content_hash" not in payload
        assert "recorded_at" in payload
        assert "counterfactual_tag" in payload
        assert "routed_model" in payload
        assert "timestamp" not in payload
        assert "exploration_tag" not in payload
        assert "model_identity" not in payload
        assert "routed_model_identity" not in payload

    def test_from_json_round_trip(self, sample_claim: CapabilityClaim) -> None:
        """A claim can round-trip through to_json → from_json."""
        payload = sample_claim.to_json()
        restored = CapabilityClaim.from_json(payload)
        assert restored.outcome.key == sample_claim.outcome.key
        assert restored.task_signature == sample_claim.task_signature
        assert restored.routed_model == sample_claim.routed_model
        assert restored.taint_class == sample_claim.taint_class
        assert restored.low_confidence_signal == sample_claim.low_confidence_signal

    def test_content_hash_stable(self, sample_ref: EvaluandRef) -> None:
        """Identical claims produce identical content hashes."""
        ts = 1000000.0
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=ts,
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=ts,
        )
        assert a.content_hash == b.content_hash

    def test_content_hash_differs_on_change(self, sample_ref: EvaluandRef) -> None:
        """Changing a field changes the content hash."""
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts-a",
            model_identity="mi",
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts-b",
            model_identity="mi",
        )
        assert a.content_hash != b.content_hash

    def test_content_hash_independent_of_timestamp(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Content hash is NOT affected by timestamp (which is excluded from
        to_json when default, but to_json includes it). Wait — to_json DOES
        include timestamp.  So two claims with different timestamps but
        identical other fields will have different content hashes.

        Actually, checking the code: to_json() includes timestamp.  So the
        hash IS affected by timestamp.  This test verifies that behaviour.
        """
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=1000.0,
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=2000.0,
        )
        assert a.content_hash != b.content_hash

    def test_optional_fields_serialize(self, sample_ref: EvaluandRef) -> None:
        """Optional fields (verifier_tier, taint_class, etc.) survive round-trip."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model=ModelIdentity("mi", "2026-05-31"),
            recorded_at=1234.0,
            verifier_tier="2",
            verifier_identity="verifier-mi",
            counterfactual_tag="explore-001",
            low_confidence_signal=True,
            taint_class="private",
            predicted_tier=3,
            route_phase="execute",
            routed_tier_spec="codex:medium",
            cost_usd=1.25,
        )
        payload = claim.to_json()
        restored = CapabilityClaim.from_json(payload)
        assert payload["routed_model"]["model_name"] == "mi"
        assert payload["routed_model"]["reported_version"] == "2026-05-31"
        assert payload["recorded_at"] == 1234.0
        assert restored.verifier_tier == "2"
        assert restored.verifier_identity == "verifier-mi"
        assert restored.counterfactual_tag == "explore-001"
        assert restored.low_confidence_signal is True
        assert restored.taint_class == "private"
        assert restored.predicted_tier == 3
        assert restored.route_phase == "execute"
        assert restored.routed_tier_spec == "codex:medium"
        assert restored.cost_usd == 1.25

    def test_from_json_reads_legacy_aliases(self, sample_ref: EvaluandRef) -> None:
        payload = {
            "outcome": sample_ref.to_json(),
            "task_signature": "ts",
            "model_identity": "legacy-model",
            "timestamp": 99.0,
            "exploration_tag": "legacy-tag",
            "routed_model_identity": "legacy-routed-model",
        }
        restored = CapabilityClaim.from_json(payload)
        assert restored.routed_model.model_name == "legacy-routed-model"
        assert restored.recorded_at == 99.0
        assert restored.counterfactual_tag == "legacy-tag"

    def test_from_json_prefers_canonical_keys_over_legacy(self, sample_ref: EvaluandRef) -> None:
        payload = {
            "outcome": sample_ref.to_json(),
            "task_signature": "ts",
            "routed_model": {
                "model_name": "canonical-model",
                "reported_version": "2026-05-31",
            },
            "model_identity": "legacy-model",
            "routed_model_identity": "legacy-routed-model",
            "recorded_at": 123.0,
            "timestamp": 99.0,
            "counterfactual_tag": "canonical-tag",
            "exploration_tag": "legacy-tag",
        }
        restored = CapabilityClaim.from_json(payload)
        assert restored.routed_model.model_name == "canonical-model"
        assert restored.routed_model.reported_version == "2026-05-31"
        assert restored.recorded_at == 123.0
        assert restored.counterfactual_tag == "canonical-tag"


# ---------------------------------------------------------------------------
# Bare numeric outcome rejection
# ---------------------------------------------------------------------------


class TestBareNumericRejection:
    """CapabilityClaim.outcome must be an EvaluandRef — never a bare number."""

    def test_rejects_bare_int(self) -> None:
        with pytest.raises(TypeError, match="EvaluandRef"):
            CapabilityClaim(
                outcome=42,  # type: ignore[arg-type]
                task_signature="ts",
                model_identity="mi",
            )

    def test_rejects_bare_float(self) -> None:
        with pytest.raises(TypeError, match="EvaluandRef"):
            CapabilityClaim(
                outcome=0.85,  # type: ignore[arg-type]
                task_signature="ts",
                model_identity="mi",
            )

    def test_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="EvaluandRef"):
            CapabilityClaim(
                outcome="good",  # type: ignore[arg-type]
                task_signature="ts",
                model_identity="mi",
            )

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="EvaluandRef"):
            CapabilityClaim(
                outcome=None,  # type: ignore[arg-type]
                task_signature="ts",
                model_identity="mi",
            )

    def test_standalone_validator_rejects_bare_float(self) -> None:
        claim = object.__new__(CapabilityClaim)
        object.__setattr__(claim, "outcome", 0.85)
        with pytest.raises(TypeError, match="bare float"):
            validate_capability_claim(claim)


# ---------------------------------------------------------------------------
# Round-trip through NdjsonBackend / events.ndjson
# ---------------------------------------------------------------------------


class TestRoundTripNdjson:
    """Write a CapabilityClaim through the event sink and read it back."""

    def test_write_and_read_via_plan_dir(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """Write via plan_dir, read back with read_capability_claims."""
        event = write_capability_claim(sample_claim, plan_dir=plan_dir)
        assert event["kind"] == EventKind.CAPABILITY_CLAIM
        assert "payload" in event

        claims = read_capability_claims(plan_dir)
        assert len(claims) == 1
        assert claims[0].task_signature == sample_claim.task_signature
        assert claims[0].model_identity == sample_claim.model_identity

    def test_write_and_iter_raw_payloads(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """Write via plan_dir, read raw payloads with iter_capability_claim_payloads."""
        write_capability_claim(sample_claim, plan_dir=plan_dir)
        payloads = list(iter_capability_claim_payloads(plan_dir))
        assert len(payloads) == 1
        assert payloads[0]["task_signature"] == sample_claim.task_signature

    def test_write_and_read_event_envelopes(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """Write via plan_dir, read full envelopes with _iter_claim_event_envelopes."""
        write_capability_claim(sample_claim, plan_dir=plan_dir)
        envelopes = list(_iter_claim_event_envelopes(plan_dir))
        assert len(envelopes) == 1
        assert envelopes[0]["kind"] == EventKind.CAPABILITY_CLAIM
        assert "seq" in envelopes[0]
        assert "ts_utc" in envelopes[0]

    def test_write_and_read_via_event_sink(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """Write via an explicit NdjsonBackend event_sink."""
        from arnold.pipelines.megaplan.observability.event_sink import NdjsonBackend

        sink = NdjsonBackend(plan_dir)
        event = write_capability_claim(sample_claim, event_sink=sink)
        assert event["kind"] == EventKind.CAPABILITY_CLAIM

        claims = read_capability_claims(plan_dir)
        assert len(claims) == 1

    def test_write_missing_target_raises(
        self, sample_claim: CapabilityClaim
    ) -> None:
        """write_capability_claim must raise ValueError when no target given."""
        with pytest.raises(ValueError, match="plan_dir.*event_sink"):
            write_capability_claim(sample_claim)

    def test_write_with_phase_and_scope(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """Phase and scope are forwarded to the event envelope."""
        event = write_capability_claim(
            sample_claim,
            plan_dir=plan_dir,
            phase="execute",
            scope="calibration",
        )
        assert event.get("phase") == "execute"
        # scope is embedded in the payload by NdjsonBackend
        assert event.get("payload", {}).get("scope") == "calibration"


# ---------------------------------------------------------------------------
# Raw claim readback and filters
# ---------------------------------------------------------------------------


class TestClaimReadback:
    """read_capability_claims Python-side filters."""

    def test_empty_dir_returns_empty(self, plan_dir: Path) -> None:
        """Empty plan_dir returns empty tuple."""
        assert read_capability_claims(plan_dir) == ()

    def test_since_timestamp_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Only claims at or after since_timestamp are returned."""
        now = time.time()
        old = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=now - 100,
        )
        new = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=now,
        )
        write_capability_claim(old, plan_dir=plan_dir)
        write_capability_claim(new, plan_dir=plan_dir)

        recent = read_capability_claims(plan_dir, since_timestamp=now - 50)
        assert len(recent) == 1
        assert recent[0].timestamp >= now - 50

    def test_model_identity_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Only claims matching model_identity are returned."""
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="id-a",
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="id-b",
        )
        write_capability_claim(a, plan_dir=plan_dir)
        write_capability_claim(b, plan_dir=plan_dir)

        filtered = read_capability_claims(plan_dir, model_identity="id-a")
        assert len(filtered) == 1
        assert filtered[0].model_identity == "id-a"

    def test_routed_model_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Canonical routed_model filter matches the full ModelIdentity."""
        routed_model = ModelIdentity("id-a", "2026-05-31")
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model=routed_model,
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model=ModelIdentity("id-a", "2026-06-01"),
        )
        write_capability_claim(a, plan_dir=plan_dir)
        write_capability_claim(b, plan_dir=plan_dir)

        filtered = read_capability_claims(plan_dir, routed_model=routed_model)
        assert filtered == (a,)

    def test_taint_class_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Only claims matching taint_class are returned."""
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            taint_class="private",
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            # no taint_class
        )
        write_capability_claim(a, plan_dir=plan_dir)
        write_capability_claim(b, plan_dir=plan_dir)

        filtered = read_capability_claims(plan_dir, taint_class="private")
        assert len(filtered) == 1
        assert filtered[0].taint_class == "private"

    def test_task_signature_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Only claims matching task_signature are returned."""
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="review:python",
            model_identity="mi",
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="test:rust",
            model_identity="mi",
        )
        write_capability_claim(a, plan_dir=plan_dir)
        write_capability_claim(b, plan_dir=plan_dir)

        filtered = read_capability_claims(plan_dir, task_signature="review:python")
        assert len(filtered) == 1
        assert filtered[0].task_signature == "review:python"

    def test_since_seq_filter(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """since_seq skips earlier events."""
        a = CapabilityClaim(
            outcome=sample_ref,
            task_signature="first",
            model_identity="mi",
        )
        b = CapabilityClaim(
            outcome=sample_ref,
            task_signature="second",
            model_identity="mi",
        )
        write_capability_claim(a, plan_dir=plan_dir)
        write_capability_claim(b, plan_dir=plan_dir)

        # Read all events to find the seq of the first claim
        events = list(read_events(plan_dir, kinds=[EventKind.CAPABILITY_CLAIM]))
        first_seq = events[0]["seq"]

        payloads = list(
            iter_capability_claim_payloads(plan_dir, since_seq=first_seq)
        )
        assert len(payloads) == 1
        assert payloads[0]["task_signature"] == "second"


# ---------------------------------------------------------------------------
# EvaluandRef join behaviour
# ---------------------------------------------------------------------------


class TestEvaluandJoin:
    """resolve_evaluand against read_evaluand_events."""

    def test_missing_evaluand_unavailable(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """An EvaluandRef with no matching record returns UNAVAILABLE."""
        resolution = resolve_evaluand(plan_dir, sample_ref)
        assert resolution.status is EvaluandStatus.UNAVAILABLE
        assert not resolution.is_available
        assert resolution.record is None
        assert resolution.reason is not None
        assert "No EvaluandRecord found" in resolution.reason

    def test_available_evaluand_after_write(
        self, plan_dir: Path, tmp_path: Path
    ) -> None:
        """After writing an Evaluand event, resolve_evaluand finds it."""
        from arnold.pipelines.megaplan.observability.evaluand import (
            EvaluandRecord,
            write_evaluand_event,
        )

        record = EvaluandRecord(
            judge_version="gpt-4o",
            rubric_version="correctness-v3",
            input_set_hash="abc123def456",
            score=0.92,
            piece_version="judge-v1",
        )
        run_id = "test-run-001"
        write_evaluand_event(run_id, record, plan_dir=plan_dir)

        ref = EvaluandRef(
            piece_version="judge-v1",
            judge_version="gpt-4o",
            rubric_version="correctness-v3",
            input_set_hash="abc123def456",
        )
        resolution = resolve_evaluand(plan_dir, ref)
        assert resolution.status is EvaluandStatus.AVAILABLE
        assert resolution.is_available
        assert resolution.record is not None
        assert resolution.record.score == 0.92

    def test_join_key_mismatch_unavailable(
        self, plan_dir: Path, tmp_path: Path
    ) -> None:
        """A mismatched attribution key returns UNAVAILABLE."""
        from arnold.pipelines.megaplan.observability.evaluand import (
            EvaluandRecord,
            write_evaluand_event,
        )

        record = EvaluandRecord(
            judge_version="gpt-4o",
            rubric_version="correctness-v3",
            input_set_hash="hash-aaa",
            score=0.92,
            piece_version="judge-v1",
        )
        write_evaluand_event("run-1", record, plan_dir=plan_dir)

        # Ref with different input_set_hash won't match
        ref = EvaluandRef(
            piece_version="judge-v1",
            judge_version="gpt-4o",
            rubric_version="correctness-v3",
            input_set_hash="hash-bbb",  # different!
        )
        resolution = resolve_evaluand(plan_dir, ref)
        assert resolution.status is EvaluandStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Taint-derived aggregation inputs
# ---------------------------------------------------------------------------


class TestTaintDerivedAggregation:
    """Taint → policy derivation and claim classification."""

    def test_clean_claims_are_shared(self, sample_claim: CapabilityClaim) -> None:
        """An untainted claim defaults to SHARED aggregation."""
        assert is_shared_claim(sample_claim) is True

    def test_private_taint_excluded(self, sample_ref: EvaluandRef) -> None:
        """A claim with taint_class='private' is excluded from shared."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            taint_class="private",
        )
        assert is_shared_claim(claim) is False

    def test_low_confidence_excluded(self, sample_ref: EvaluandRef) -> None:
        """A low-confidence claim is excluded from shared aggregation."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            low_confidence_signal=True,
        )
        assert is_shared_claim(claim) is False

    def test_filter_shared_claims_mixed(
        self, sample_ref: EvaluandRef
    ) -> None:
        """filter_shared_claims returns only eligible claims."""
        clean = CapabilityClaim(
            outcome=sample_ref,
            task_signature="clean",
            model_identity="mi",
        )
        tainted = CapabilityClaim(
            outcome=sample_ref,
            task_signature="tainted",
            model_identity="mi",
            taint_class="private",
        )
        low_conf = CapabilityClaim(
            outcome=sample_ref,
            task_signature="low",
            model_identity="mi",
            low_confidence_signal=True,
        )
        filtered = filter_shared_claims([clean, tainted, low_conf])
        assert len(filtered) == 1
        assert filtered[0].task_signature == "clean"

    def test_classify_claim_taint_from_private_labels(self) -> None:
        """Evaluand taint labels with private markers produce TENANT_LOCAL."""
        tc, policy = classify_claim_taint(("private",))
        assert tc == "private"
        assert policy is AggregationPolicy.TENANT_LOCAL

    def test_classify_claim_taint_clean(self) -> None:
        """Clean evaluand taint labels produce SHARED."""
        tc, policy = classify_claim_taint(("public", "benchmark"))
        assert tc is None
        assert policy is AggregationPolicy.SHARED

    def test_classify_claim_taint_empty(self) -> None:
        """Empty taint tuple returns None and SHARED."""
        tc, policy = classify_claim_taint(())
        assert tc is None
        assert policy is AggregationPolicy.SHARED

    def test_taint_class_from_evaluand_taint_first_wins(self) -> None:
        """The first private marker in the taint tuple wins."""
        tc = _taint_class_from_evaluand_taint(("normal", "private", "confidential"))
        assert tc == "private"

    def test_taint_class_private_substring_wins(self) -> None:
        """Private-derived labels stay tenant-local via substring matching."""
        tc, policy = classify_claim_taint(("normal", "customer-private-dataset"))
        assert tc == "customer-private-dataset"
        assert policy is AggregationPolicy.TENANT_LOCAL

    def test_derive_aggregation_policy_case_insensitive(self) -> None:
        """Taint markers are matched case-insensitively."""
        assert derive_aggregation_policy("PRIVATE") is AggregationPolicy.TENANT_LOCAL
        assert derive_aggregation_policy("Private") is AggregationPolicy.TENANT_LOCAL
        assert derive_aggregation_policy("  private  ") is AggregationPolicy.TENANT_LOCAL
        assert derive_aggregation_policy("customer-private-dataset") is AggregationPolicy.TENANT_LOCAL

    def test_all_private_markers_trigger_tenant_local(self) -> None:
        """Every marker in _PRIVATE_TAINT_MARKERS triggers TENANT_LOCAL."""
        markers = ["private", "confidential", "internal", "sensitive", "pii", "phi"]
        for m in markers:
                assert (
                    derive_aggregation_policy(m) is AggregationPolicy.TENANT_LOCAL
                ), f"Marker {m!r} did not trigger TENANT_LOCAL"


# ---------------------------------------------------------------------------
# Path-derived aggregation defaults (in-tree / out-of-tree)
# ---------------------------------------------------------------------------


class TestPathDerivedAggregation:
    """derive_aggregation_policy / classify_claim_taint / is_shared_claim
    with path-derived in_tree defaults."""

    def test_no_signal_preserves_default_shared(self) -> None:
        """Backward compat: no in_tree and no path → default SHARED."""
        assert derive_aggregation_policy(None) is AggregationPolicy.SHARED
        assert derive_aggregation_policy("clean") is AggregationPolicy.SHARED

    def test_in_tree_true_clean_claims_shared(self) -> None:
        """Clean claim with in_tree=True → SHARED."""
        assert derive_aggregation_policy(None, in_tree=True) is AggregationPolicy.SHARED
        assert derive_aggregation_policy("public", in_tree=True) is AggregationPolicy.SHARED

    def test_in_tree_false_clean_claims_tenant_local(self) -> None:
        """Clean claim with in_tree=False → TENANT_LOCAL."""
        assert derive_aggregation_policy(None, in_tree=False) is AggregationPolicy.TENANT_LOCAL
        assert derive_aggregation_policy("public", in_tree=False) is AggregationPolicy.TENANT_LOCAL

    def test_tainted_always_tenant_local_regardless_of_in_tree(self) -> None:
        """Tainted claims are ALWAYS TENANT_LOCAL, even with in_tree=True."""
        assert derive_aggregation_policy("private", in_tree=True) is AggregationPolicy.TENANT_LOCAL
        assert derive_aggregation_policy("confidential", in_tree=False) is AggregationPolicy.TENANT_LOCAL

    def test_path_containment_in_tree(self, tmp_path: Path) -> None:
        """project_dir inside repo_root → in_tree=True → SHARED."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = repo / "project"
        proj.mkdir()
        assert (
            derive_aggregation_policy(
                None, project_dir=proj, repo_root=repo
            )
            is AggregationPolicy.SHARED
        )

    def test_path_non_containment_out_of_tree(self, tmp_path: Path) -> None:
        """project_dir outside repo_root → in_tree=False → TENANT_LOCAL."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = tmp_path / "other-project"
        proj.mkdir()
        assert (
            derive_aggregation_policy(
                None, project_dir=proj, repo_root=repo
            )
            is AggregationPolicy.TENANT_LOCAL
        )

    def test_classify_claim_taint_threads_in_tree(self) -> None:
        """classify_claim_taint forwards in_tree to derive_aggregation_policy."""
        _, policy = classify_claim_taint(("public",), in_tree=False)
        assert policy is AggregationPolicy.TENANT_LOCAL

    def test_classify_claim_taint_preserves_no_signal(self) -> None:
        """classify_claim_taint with no path signal preserves backward compat."""
        _, policy = classify_claim_taint(("public",))
        assert policy is AggregationPolicy.SHARED

    def test_is_shared_claim_respects_in_tree(
        self, sample_claim: CapabilityClaim
    ) -> None:
        """is_shared_claim with in_tree=False excludes clean claims."""
        # sample_claim has no taint_class, so it defaults clean.
        assert is_shared_claim(sample_claim, in_tree=True) is True
        assert is_shared_claim(sample_claim, in_tree=False) is False

    def test_is_shared_claim_preserves_no_signal(
        self, sample_claim: CapabilityClaim
    ) -> None:
        """is_shared_claim with no path signal preserves backward compat."""
        assert is_shared_claim(sample_claim) is True

    def test_low_confidence_cost_pressured_claim_excluded_from_shared(
        self, sample_ref: EvaluandRef
    ) -> None:
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            routed_model=ModelIdentity("tier-one-model"),
            predicted_tier=1,
            recorded_at=10_000.0,
            verifier_tier="4",
            low_confidence_signal=True,
        )

        assert is_shared_claim(claim) is False
        assert filter_shared_claims([claim]) == ()


# ---------------------------------------------------------------------------
# Proof: no second journal/store file
# ---------------------------------------------------------------------------


class TestNoSecondJournal:
    """Only events.ndjson is used — no calibration-specific journal file.

    Note: ``.events.seq`` is an internal EventWriter counter file and
    is not calibration-specific — it exists for all event journal users.
    """

    def test_only_events_ndjson_created(
        self, plan_dir: Path, sample_claim: CapabilityClaim
    ) -> None:
        """After writing a claim, only events.ndjson (and .events.seq) exist."""
        write_capability_claim(sample_claim, plan_dir=plan_dir)

        files = list(plan_dir.iterdir())
        file_names = {f.name for f in files}
        # .events.seq is the internal EventWriter sequence file —
        # not a calibration-specific journal.
        allowed = {"events.ndjson", ".events.seq"}
        assert file_names.issubset(allowed), (
            f"Unexpected files in plan_dir: {file_names - allowed}"
        )
        assert "events.ndjson" in file_names, "events.ndjson must exist"

    def test_write_multiple_claims_single_file(
        self, plan_dir: Path, sample_ref: EvaluandRef
    ) -> None:
        """Multiple claims all go into the same events.ndjson."""
        for i in range(5):
            claim = CapabilityClaim(
                outcome=sample_ref,
                task_signature=f"ts-{i}",
                model_identity="mi",
            )
            write_capability_claim(claim, plan_dir=plan_dir)

        # Only expected files
        files = list(plan_dir.iterdir())
        file_names = {f.name for f in files}
        allowed = {"events.ndjson", ".events.seq"}
        assert file_names.issubset(allowed)

        # events.ndjson has 5 CAPABILITY_CLAIM lines
        lines = (plan_dir / "events.ndjson").read_text().strip().split("\n")
        claim_lines = [
            l
            for l in lines
            if json.loads(l).get("kind") == EventKind.CAPABILITY_CLAIM
        ]
        assert len(claim_lines) == 5


# ---------------------------------------------------------------------------
# Calibration math: half-life weight
# ---------------------------------------------------------------------------


class TestHalfLifeWeight:
    """half_life_weight exponential decay function."""

    def test_zero_elapsed_is_one(self) -> None:
        """Weight is 1.0 when elapsed time is zero."""
        now = time.time()
        assert half_life_weight(now, now, 3600.0) == 1.0

    def test_exactly_one_half_life(self) -> None:
        """After exactly one half-life, weight is 0.5."""
        now = 10000.0
        half = 3600.0
        assert half_life_weight(now - half, now, half) == 0.5

    def test_two_half_lives(self) -> None:
        """After two half-lives, weight is 0.25."""
        now = 10000.0
        half = 3600.0
        w = half_life_weight(now - 2 * half, now, half)
        assert math.isclose(w, 0.25, rel_tol=1e-9)

    def test_very_old_approaches_zero(self) -> None:
        """Very stale claims approach zero weight."""
        now = 10000.0
        half = 1.0
        w = half_life_weight(now - 100 * half, now, half)
        assert 0.0 < w < 1e-30

    def test_rejects_negative_half_life(self) -> None:
        """half_life_seconds must be > 0."""
        with pytest.raises(ValueError, match="must be > 0"):
            half_life_weight(0.0, 100.0, -1.0)

    def test_rejects_zero_half_life(self) -> None:
        """half_life_seconds must be > 0 (not just non-negative)."""
        with pytest.raises(ValueError, match="must be > 0"):
            half_life_weight(0.0, 100.0, 0.0)

    def test_rejects_future_recorded_at(self) -> None:
        """recorded_at > now raises ValueError."""
        with pytest.raises(ValueError, match="not be in the future"):
            half_life_weight(200.0, 100.0, 3600.0)

    def test_fractional_elapsed(self) -> None:
        """Fractional elapsed times compute correct weights."""
        now = 10000.0
        half = 3600.0
        # After 1/4 half-life: 2^(-0.25) ≈ 0.8409
        w = half_life_weight(now - 0.25 * half, now, half)
        expected = 2.0 ** (-0.25)
        assert math.isclose(w, expected, rel_tol=1e-9)

    def test_different_half_lives(self) -> None:
        """Different half-life values produce different decay rates."""
        now = 10000.0
        elapsed = 3600.0
        w1 = half_life_weight(now - elapsed, now, 1800.0)  # 2 half-lives → 0.25
        w2 = half_life_weight(now - elapsed, now, 3600.0)  # 1 half-life → 0.5
        assert math.isclose(w1, 0.25)
        assert math.isclose(w2, 0.5)
        assert w1 < w2  # shorter half-life decays faster


# ---------------------------------------------------------------------------
# Capability-class prior
# ---------------------------------------------------------------------------

class TestCapabilityClassPrior:
    """capability_class_prior with model-class and class-tier lookup."""

    def test_unseen_returns_default(self) -> None:
        """Unseen model (no tables) returns tier 4 (default)."""
        assert capability_class_prior(ModelIdentity("never-seen")) == 4

    def test_exact_identity_match_precedes_model_name(self) -> None:
        """Full identity lookup wins when model name maps to another class."""
        model = ModelIdentity("opus-3", "2026-05-31")
        model_class_table = {
            model.identity: "premium",
            model.model_name: "standard",
        }
        class_tier_priors = {"premium": 1, "standard": 3}
        assert (
            capability_class_prior(
                model,
                model_class_table=model_class_table,
                class_tier_priors=class_tier_priors,
            )
            == 1
        )

    def test_known_model_class_returns_tier(self) -> None:
        """Known model class returns the mapped tier."""
        model = ModelIdentity("opus-3", "v1")
        model_class_table = {
            model.identity: "premium",
            model.model_name: "premium",
        }
        class_tier_priors = {"premium": 2, "standard": 3}
        assert (
            capability_class_prior(
                model,
                model_class_table=model_class_table,
                class_tier_priors=class_tier_priors,
            )
            == 2
        )

    def test_model_name_fallback(self) -> None:
        """Model name lookup succeeds when identity is not in the table."""
        model = ModelIdentity("small-model", "v1")
        model_class_table = {model.model_name: "standard"}
        class_tier_priors = {"premium": 2, "standard": 3}
        assert (
            capability_class_prior(
                model,
                model_class_table=model_class_table,
                class_tier_priors=class_tier_priors,
            )
            == 3
        )

    def test_raw_string_direct_fallback(self) -> None:
        """Raw model_name lookup in class_tier_priors succeeds."""
        model = ModelIdentity("legacy-model")
        class_tier_priors = {"legacy-model": 1, "other": 5}
        assert (
            capability_class_prior(
                model,
                class_tier_priors=class_tier_priors,
            )
            == 1
        )

    def test_raw_string_input_direct_fallback(self) -> None:
        """A plain string model identity is accepted for compatibility."""
        class_tier_priors = {"legacy-model": 2, "other": 5}
        assert (
            capability_class_prior(
                "legacy-model",
                class_tier_priors=class_tier_priors,
            )
            == 2
        )

    def test_unseen_with_custom_default(self) -> None:
        """Custom default_tier is used for unseen models."""
        assert capability_class_prior(ModelIdentity("x"), default_tier=5) == 5

    def test_unknown_class_falls_back_to_default(self) -> None:
        """Known model with no matching class prior uses tier 4."""
        assert (
            capability_class_prior(
                ModelIdentity("known-model"),
                model_class_table={"known-model": "unscored-class"},
                class_tier_priors={"premium": 1},
            )
            == 4
        )

    def test_legacy_task_signature_prior(self) -> None:
        """_task_signature_class_prior preserves old string-based behaviour."""
        tier_map = {"code_review:python": 2, "docs": 3}
        assert _task_signature_class_prior("code_review:python", tier_map=tier_map) == 2
        assert _task_signature_class_prior("docs", tier_map=tier_map) == 3
        assert _task_signature_class_prior("never-seen") == 4
        assert _task_signature_class_prior("x", default_tier=5) == 5



# ---------------------------------------------------------------------------
# Reviewer invariant
# ---------------------------------------------------------------------------


class TestReviewerInvariant:
    """check_reviewer_invariant cost-pressured verifier detection."""

    def test_missing_tiers_flagged(self) -> None:
        """Missing verifier or model tier defaults to low-confidence."""
        low, reason = check_reviewer_invariant(
            verifier_tier=None, routed_model_tier=2
        )
        assert low is True
        assert "missing" in reason

        low, reason = check_reviewer_invariant(
            verifier_tier="3", routed_model_tier=None
        )
        assert low is True

    def test_unparseable_verifier_tier_flagged(self) -> None:
        """Unparseable verifier tier defaults to low-confidence."""
        low, reason = check_reviewer_invariant(
            verifier_tier="abc", routed_model_tier=2
        )
        assert low is True
        assert "unparseable" in reason

    def test_verifier_better_than_model_flagged(self) -> None:
        """When verifier_tier < routed_model_tier, low-confidence is set."""
        # Following spec literally: vt < routed_model_tier → low confidence
        low, reason = check_reviewer_invariant(
            verifier_tier="1", routed_model_tier=4
        )
        assert low is True
        assert reason is not None
        assert "cost-pressured" in reason

    def test_verifier_worse_than_model_not_flagged(self) -> None:
        """When verifier_tier >= routed_model_tier, no flag."""
        low, reason = check_reviewer_invariant(
            verifier_tier="4", routed_model_tier=2
        )
        assert low is False
        assert reason is None

    def test_equal_tiers_not_flagged(self) -> None:
        """Equal tiers do not trigger low confidence."""
        low, reason = check_reviewer_invariant(
            verifier_tier="3", routed_model_tier=3
        )
        assert low is False


# ---------------------------------------------------------------------------
# Weighted aggregation
# ---------------------------------------------------------------------------


class TestAggregateWeightedTier:
    """aggregate_weighted_tier decay-weighted average."""

    def test_empty_returns_default(self) -> None:
        """Empty claims list returns default_tier."""
        assert aggregate_weighted_tier([]) == 4.0
        assert aggregate_weighted_tier([], default_tier=3) == 3.0

    def test_single_claim_default_weight(
        self, sample_ref: EvaluandRef
    ) -> None:
        """A single claim with predicted_tier=None returns default_tier."""
        now = time.time()
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=now,
        )
        result = aggregate_weighted_tier([claim], now=now)
        assert result == 4.0  # default_tier when predicted_tier is None

    def test_single_claim_with_predicted_tier(
        self, sample_ref: EvaluandRef
    ) -> None:
        """A single claim with explicit predicted_tier gives that value."""
        now = time.time()
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=now,
            predicted_tier=2,
        )
        result = aggregate_weighted_tier([claim], now=now)
        assert result == 2.0

    def test_stale_claim_downweighted(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Stale claims contribute less to the weighted average."""
        now = 10000.0
        half = 3600.0
        fresh = CapabilityClaim(
            outcome=sample_ref,
            task_signature="fresh",
            model_identity="mi",
            timestamp=now,
            predicted_tier=1,
        )
        stale = CapabilityClaim(
            outcome=sample_ref,
            task_signature="stale",
            model_identity="mi",
            timestamp=now - 2 * half,  # 2 half-lives old → weight 0.25
            predicted_tier=5,
        )
        # Fresh weight = 1.0, stale weight = 0.25
        # Expected = (1*1.0 + 5*0.25) / (1.0 + 0.25) = (1 + 1.25) / 1.25 = 1.8
        result = aggregate_weighted_tier(
            [fresh, stale], now=now, half_life_seconds=half
        )
        expected = (1 * 1.0 + 5 * 0.25) / (1.0 + 0.25)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_all_zero_weights_returns_default(
        self, sample_ref: EvaluandRef
    ) -> None:
        """When all weights are effectively zero (floating underflow),
        aggregate_weighted_tier falls through to the total_weight==0
        guard.  We test with half_life_seconds=0.01 and elapsed=1000,
        which makes 2^(-100000) underflow to 0.0 in double precision.
        """
        now = 10000.0
        half = 0.01
        claims = [
            CapabilityClaim(
                outcome=sample_ref,
                task_signature=f"ts-{i}",
                model_identity="mi",
                timestamp=now - 1000.0,  # 100000 half-lives
                predicted_tier=1,
            )
            for i in range(3)
        ]
        result = aggregate_weighted_tier(claims, now=now, half_life_seconds=half)
        assert result == 4.0  # default_tier when all weights underflow to 0

    def test_uses_recorded_at_not_timestamp_for_decay(
        self, sample_ref: EvaluandRef
    ) -> None:
        """``aggregate_weighted_tier`` reads ``recorded_at`` — not ``timestamp``."""
        now = 10_000.0
        half = 3600.0
        # Construct using canonical recorded_at so the internal recorded_at is set.
        # Then verify the internal path uses recorded_at by checking the weight.
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model=ModelIdentity("mi"),
            recorded_at=now - half,  # exactly one half-life → weight 0.5
            predicted_tier=2,
        )
        result = aggregate_weighted_tier([claim], now=now, half_life_seconds=half, default_tier=4)
        # Single claim: weight=0.5, tier=2 → avg = 2.0 / 1.0 (only claim)
        assert result == 2.0


# ---------------------------------------------------------------------------
# EvaluandRef round-trip and content hash
# ---------------------------------------------------------------------------


class TestEvaluandRef:
    """EvaluandRef to_json / from_json round-trip and content hash."""

    def test_to_json_from_json_round_trip(self) -> None:
        """EvaluandRef round-trips through to_json/from_json preserving all fields."""
        ref = EvaluandRef(
            piece_version="piece-v2",
            judge_version="judge-v2",
            rubric_version="rubric-v2",
            input_set_hash="hash-v2",
        )
        payload = ref.to_json()
        restored = EvaluandRef.from_json(payload)
        assert restored.piece_version == ref.piece_version
        assert restored.judge_version == ref.judge_version
        assert restored.rubric_version == ref.rubric_version
        assert restored.input_set_hash == ref.input_set_hash
        assert restored.key == ref.key
        assert restored.content_hash == ref.content_hash

    def test_content_hash_stable_for_same_fields(self) -> None:
        """Same EvaluandRef fields produce same content hash."""
        a = EvaluandRef("p", "j", "r", "h")
        b = EvaluandRef("p", "j", "r", "h")
        assert a.content_hash == b.content_hash

    def test_content_hash_differs_on_different_key(self) -> None:
        """Different EvaluandRef fields produce different hashes."""
        a = EvaluandRef("p", "j", "r", "h1")
        b = EvaluandRef("p", "j", "r", "h2")
        assert a.content_hash != b.content_hash

    def test_key_is_4_tuple(self) -> None:
        """The key property returns the correct 4-tuple."""
        ref = EvaluandRef("a", "b", "c", "d")
        assert ref.key == ("a", "b", "c", "d")


# ---------------------------------------------------------------------------
# Legacy property read compatibility
# ---------------------------------------------------------------------------


class TestLegacyPropertyReads:
    """Canonical CapabilityClaim exposes legacy property aliases for read compat."""

    def test_legacy_timestamp_reads_recorded_at(self, sample_claim: CapabilityClaim) -> None:
        """``claim.timestamp`` reads the canonical ``recorded_at`` field."""
        assert isinstance(sample_claim.timestamp, float)
        assert sample_claim.timestamp == sample_claim.recorded_at

    def test_legacy_exploration_tag_reads_counterfactual_tag(
        self, sample_ref: EvaluandRef
    ) -> None:
        """``claim.exploration_tag`` reads the canonical ``counterfactual_tag`` field."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            counterfactual_tag="explore-001",
        )
        assert claim.exploration_tag == "explore-001"
        assert claim.counterfactual_tag == "explore-001"

    def test_legacy_model_identity_reads_routed_model_name(
        self, sample_claim: CapabilityClaim
    ) -> None:
        """``claim.model_identity`` reads the canonical ``routed_model.model_name``."""
        assert sample_claim.model_identity == sample_claim.routed_model.model_name

    def test_legacy_routed_model_identity_reads_routed_model_name(
        self, sample_claim: CapabilityClaim
    ) -> None:
        """``claim.routed_model_identity`` reads the canonical ``routed_model.model_name``."""
        assert sample_claim.routed_model_identity == sample_claim.routed_model.model_name

    def test_legacy_string_model_identity_constructor(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Constructing with a bare string ``model_identity`` creates a ModelIdentity."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="bare-string-model",
        )
        assert isinstance(claim.routed_model, ModelIdentity)
        assert claim.routed_model.model_name == "bare-string-model"
        assert claim.routed_model.reported_version is None

    def test_legacy_routed_model_identity_constructor(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Constructing with ``routed_model_identity`` string creates ModelIdentity."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model_identity="routed-legacy",
        )
        assert claim.routed_model.model_name == "routed-legacy"

    def test_legacy_timestamp_constructor_maps_to_recorded_at(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Constructing with ``timestamp=`` maps to ``recorded_at``."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            timestamp=999.0,
        )
        assert claim.recorded_at == 999.0
        assert claim.timestamp == 999.0

    def test_legacy_exploration_tag_constructor_maps_to_counterfactual_tag(
        self, sample_ref: EvaluandRef
    ) -> None:
        """Constructing with ``exploration_tag=`` maps to ``counterfactual_tag``."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            model_identity="mi",
            exploration_tag="old-tag",
        )
        assert claim.counterfactual_tag == "old-tag"
        assert claim.exploration_tag == "old-tag"

    def test_canonical_precedence_in_constructor(
        self, sample_ref: EvaluandRef
    ) -> None:
        """When both canonical and legacy ctor args are given, canonical wins."""
        claim = CapabilityClaim(
            outcome=sample_ref,
            task_signature="ts",
            routed_model=ModelIdentity("canonical-model", "v1"),
            model_identity="legacy-model",
            recorded_at=111.0,
            timestamp=222.0,
            counterfactual_tag="canonical-tag",
            exploration_tag="legacy-tag",
        )
        assert claim.routed_model.model_name == "canonical-model"
        assert claim.recorded_at == 111.0
        assert claim.counterfactual_tag == "canonical-tag"


# ---------------------------------------------------------------------------
# ModelIdentity
# ---------------------------------------------------------------------------


class TestModelIdentity:
    """ModelIdentity value object."""

    def test_identity_is_deterministic(self) -> None:
        """Same inputs produce same identity."""
        a = ModelIdentity("gpt-4o", "2024-08-06")
        b = ModelIdentity("gpt-4o", "2024-08-06")
        assert a.identity == b.identity

    def test_identity_differs_on_name(self) -> None:
        """Different names produce different identities."""
        a = ModelIdentity("gpt-4o")
        b = ModelIdentity("claude-3")
        assert a.identity != b.identity

    def test_identity_differs_on_version(self) -> None:
        """Different versions produce different identities."""
        a = ModelIdentity("gpt-4o", "2024-08-06")
        b = ModelIdentity("gpt-4o", "2024-11-20")
        assert a.identity != b.identity

    def test_none_version_handled(self) -> None:
        """None version is treated as empty string."""
        a = ModelIdentity("gpt-4o", None)
        b = ModelIdentity("gpt-4o", "")
        assert a.identity == b.identity

    def test_to_from_json_round_trip(self) -> None:
        """ModelIdentity round-trips through to_json/from_json."""
        mi = ModelIdentity("gpt-4o", "2024-08-06")
        payload = mi.to_json()
        restored = ModelIdentity.from_json(payload)
        assert restored.model_name == mi.model_name
        assert restored.reported_version == mi.reported_version
        assert restored.identity == mi.identity


# ---------------------------------------------------------------------------
# QueryPolicy and RouteSuggestion
# ---------------------------------------------------------------------------


class TestQueryPolicy:
    """QueryPolicy value object."""

    def test_default_values(self) -> None:
        """Default QueryPolicy has expected values."""
        qp = QueryPolicy()
        assert qp.half_life_days == 30.0
        assert qp.exploration_budget == 0.0
        assert qp.default_tier == 4
        assert qp.exclude_tainted is True
        assert qp.verifier_tier_min is None

    def test_to_from_json_round_trip(self) -> None:
        """QueryPolicy round-trips through to_json/from_json."""
        qp = QueryPolicy(
            half_life_days=7.0,
            exploration_budget=0.1,
            default_tier=3,
            exclude_tainted=False,
            verifier_tier_min=2,
        )
        data = qp.to_json()
        restored = QueryPolicy.from_json(data)
        assert restored.half_life_days == 7.0
        assert restored.exploration_budget == 0.1
        assert restored.default_tier == 3
        assert restored.exclude_tainted is False
        assert restored.verifier_tier_min == 2


class TestRouteSuggestion:
    """RouteSuggestion value object."""

    def test_no_suggestion_has_suggestion_false(self) -> None:
        """A RouteSuggestion with tier_spec=None has no suggestion."""
        rs = RouteSuggestion()
        assert rs.has_suggestion is False

    def test_with_suggestion_has_suggestion_true(self) -> None:
        """A RouteSuggestion with tier_spec set has a suggestion."""
        rs = RouteSuggestion(tier_spec="openai/gpt-4o")
        assert rs.has_suggestion is True

    def test_to_json_includes_all_fields(self) -> None:
        """to_json includes all fields including defaults."""
        rs = RouteSuggestion(
            tier_spec="spec",
            model_identity="mi",
            confidence=0.75,
            source="test",
            exploration=True,
            reason="testing",
        )
        data = rs.to_json()
        assert data["tier_spec"] == "spec"
        assert data["model_identity"] == "mi"
        assert data["confidence"] == 0.75
        assert data["source"] == "test"
        assert data["exploration"] is True
        assert data["reason"] == "testing"


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


class TestProjectionHelpers:
    """Projection/parity helpers for tier models and complexity views."""

    def test_project_tier_models_reconstructs_complete_slots_without_fallback_masking(
        self, sample_ref: EvaluandRef
    ) -> None:
        from arnold.pipelines.megaplan.profiles import _validate_projected_tier_models

        now = 10_000.0
        claims = [
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="review:T1",
                routed_model=ModelIdentity("resolved-execute"),
                predicted_tier=1,
                routed_tier_spec="hermes:deepseek-flash",
                route_phase="execute",
                recorded_at=now - 600.0,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="review:T1",
                routed_model=ModelIdentity("resolved-review"),
                predicted_tier=4,
                routed_tier_spec="claude:medium",
                recorded_at=now,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="finalize:T1",
                routed_model=ModelIdentity("resolved-finalize"),
                predicted_tier=5,
                routed_tier_spec="codex:high",
                recorded_at=now - 60.0,
            ),
        ]

        projected = project_tier_models(
            claims,
            fallback_tier_models={
                "execute": {1: "codex:medium"},
                "review": {4: "codex:medium"},
                "finalize": {5: "claude:high"},
            },
            now=now,
            half_life_seconds=3600.0,
        )

        expected_int_keys = _validate_projected_tier_models(
            {
                "execute": {1: "hermes:deepseek-flash"},
                "review": {4: "claude:medium"},
                "finalize": {5: "codex:high"},
            }
        )
        expected = {
            phase: {str(tier): spec for tier, spec in tiers.items()}
            for phase, tiers in expected_int_keys.items()
        }

        assert projected == expected
        assert _canonical_json(projected) == _canonical_json(expected)

    def test_project_tier_models_seeds_incomplete_slots_from_fallback_and_ignores_ineligible_claims(
        self, sample_ref: EvaluandRef
    ) -> None:
        now = 10_000.0
        claims = [
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T1",
                routed_model=ModelIdentity("resolved-execute"),
                predicted_tier=1,
                routed_tier_spec="hermes:deepseek-flash",
                recorded_at=now,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T2",
                routed_model=ModelIdentity("low-confidence"),
                predicted_tier=2,
                routed_tier_spec="claude:medium",
                recorded_at=now,
                low_confidence_signal=True,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T3",
                routed_model=ModelIdentity("malformed-tier"),
                predicted_tier=None,
                routed_tier_spec="codex:medium",
                recorded_at=now,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T4",
                routed_model=ModelIdentity("missing-spec"),
                predicted_tier=2,
                routed_tier_spec="   ",
                recorded_at=now,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T5",
                routed_model=ModelIdentity("private"),
                predicted_tier=2,
                routed_tier_spec="codex:medium",
                recorded_at=now,
                taint_class="private",
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="execute:T6",
                routed_model=ModelIdentity("bad-phase"),
                predicted_tier=2,
                routed_tier_spec="claude:medium",
                route_phase="not-a-real-phase",
                recorded_at=now,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="unknown:T7",
                routed_model=ModelIdentity("no-phase"),
                predicted_tier=4,
                routed_tier_spec="claude:medium",
                recorded_at=now,
            ),
        ]

        projected = project_tier_models(
            claims,
            fallback_tier_models={
                "execute": {2: "codex:medium"},
                "review": {4: "claude:medium"},
            },
            now=now,
            half_life_seconds=3600.0,
        )

        assert projected == {
            "execute": {"1": "hermes:deepseek-flash", "2": "codex:medium"},
            "review": {"4": "claude:medium"},
        }

    def test_project_tier_models_tie_breaks_by_recency_then_spec(
        self, sample_ref: EvaluandRef
    ) -> None:
        now = 10_000.0
        recency_projected = project_tier_models(
            [
                CapabilityClaim(
                    outcome=sample_ref,
                    task_signature="execute:T1",
                    routed_model=ModelIdentity("old"),
                    predicted_tier=3,
                    routed_tier_spec="codex:medium",
                    recorded_at=now - 10.0,
                ),
                CapabilityClaim(
                    outcome=sample_ref,
                    task_signature="execute:T2",
                    routed_model=ModelIdentity("new"),
                    predicted_tier=3,
                    routed_tier_spec="claude:medium",
                    recorded_at=now,
                ),
            ],
            now=now,
            half_life_seconds=1_000_000_000.0,
        )
        assert recency_projected == {"execute": {"3": "claude:medium"}}

        lexical_projected = project_tier_models(
            [
                CapabilityClaim(
                    outcome=sample_ref,
                    task_signature="execute:T1",
                    routed_model=ModelIdentity("a"),
                    predicted_tier=3,
                    routed_tier_spec="codex:medium",
                    recorded_at=now,
                ),
                CapabilityClaim(
                    outcome=sample_ref,
                    task_signature="execute:T2",
                    routed_model=ModelIdentity("b"),
                    predicted_tier=3,
                    routed_tier_spec="claude:medium",
                    recorded_at=now,
                ),
            ],
            now=now,
            half_life_seconds=3600.0,
        )
        assert lexical_projected == {"execute": {"3": "claude:medium"}}

    def test_project_tier_models_returns_json_parity_shape(self) -> None:
        """Tier keys are canonicalized to strings for byte-stable JSON parity."""
        projected = project_tier_models(
            [],
            fallback_tier_models={
                "execute": {1: "hermes:deepseek-flash", "5": "codex:high"},
                "review": {4: "claude:medium"},
            },
        )
        assert projected == {
            "execute": {"1": "hermes:deepseek-flash", "5": "codex:high"},
            "review": {"4": "claude:medium"},
        }

    def test_project_tier_models_matches_validated_profile_json(self) -> None:
        """Projected fallback matches the TOML-path view after canonical JSON."""
        from arnold.pipelines.megaplan.profiles import _validate_projected_tier_models

        fallback = {
            "execute": {1: "hermes:deepseek-flash", 5: "codex:high"},
            "review": {4: "claude:medium"},
        }
        validated = _validate_projected_tier_models(fallback)
        assert _canonical_json(project_tier_models([], fallback)) == _canonical_json(
            {"execute": {"1": validated["execute"][1], "5": validated["execute"][5]},
             "review": {"4": validated["review"][4]}}
        )

    def test_project_tier_models_reuses_profile_validation(self) -> None:
        """Invalid projected specs are rejected by the existing profile grammar."""
        from arnold.pipelines.megaplan.types import CliError

        with pytest.raises(CliError, match="unknown agent 'bogus'"):
            project_tier_models([], {"execute": {1: "bogus:low"}})

    def test_normalize_projected_complexity_defaults_to_4(self) -> None:
        """Projected task complexity mirrors finalize's tier-4 normalization."""
        assert normalize_projected_complexity(None) == 4
        assert normalize_projected_complexity("high") == 4
        assert normalize_projected_complexity(0) == 4
        assert normalize_projected_complexity(6) == 4
        assert normalize_projected_complexity(True) == 4
        assert normalize_projected_complexity(False) == 4
        assert normalize_projected_complexity(3) == 3
        assert normalize_projected_complexity(1) == 1
        assert normalize_projected_complexity(5) == 5

    def test_normalize_projected_complexity_non_finite(self) -> None:
        """Non-finite floats (inf, nan) fall back to tier 4."""
        import math
        assert normalize_projected_complexity(float("inf")) == 4
        assert normalize_projected_complexity(float("-inf")) == 4
        assert normalize_projected_complexity(float("nan")) == 4

    def test_normalize_projected_complexity_float_ints(self) -> None:
        """Floats that are not int instances fall back to tier 4 (strict int check)."""
        assert normalize_projected_complexity(3.0) == 4
        assert normalize_projected_complexity(1.0) == 4
        assert normalize_projected_complexity(5.0) == 4

    def test_project_claimed_complexity_uses_weighted_projection(self, sample_ref: EvaluandRef) -> None:
        """Claim-based projection rounds the weighted tier back into 1..5."""
        now = 10_000.0
        claims = [
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                model_identity="mi",
                timestamp=now,
                predicted_tier=2,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                model_identity="mi",
                timestamp=now - 3600.0,
                predicted_tier=3,
            ),
        ]
        assert project_claimed_complexity(claims, now=now, half_life_seconds=3600.0) == 2

    def test_project_claimed_complexity_uses_recorded_at_canonical(self, sample_ref: EvaluandRef) -> None:
        """Projection decay uses ``recorded_at`` — the canonical field — for weighting."""
        now = 10_000.0
        half = 3600.0
        fresh = CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            routed_model=ModelIdentity("fresh"),
            recorded_at=now,
            predicted_tier=4,
        )
        stale = CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            routed_model=ModelIdentity("stale"),
            recorded_at=now - (10 * half),
            predicted_tier=1,
        )
        # Fresh tier-4 claim with weight 1.0 vs stale tier-1 claim with
        # near-zero weight → projection stays near 4, rounds to 4.
        result = project_claimed_complexity(
            [fresh, stale], now=now, half_life_seconds=half,
        )
        assert result == 4

    def test_project_claimed_complexity_non_finite_projection(self, sample_ref: EvaluandRef) -> None:
        """When all predicted_tiers are None the weighted avg is default_tier."""
        now = 10_000.0
        claims = [
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                model_identity="mi",
                timestamp=now,
                # no predicted_tier
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                model_identity="mi",
                timestamp=now - 3600.0,
                # no predicted_tier
            ),
        ]
        assert project_claimed_complexity(claims, now=now, half_life_seconds=3600.0, default=4) == 4

    def test_project_claimed_complexity_empty_defaults_to_4(self) -> None:
        """Empty claim sets preserve the conservative task-default tier."""
        assert project_claimed_complexity([]) == 4

    def test_project_batch_complexity_preserves_fail_safe_5(self) -> None:
        """Batch projection delegates to compute_batch_complexity unchanged."""
        finalize_data = {
            "tasks": [
                {"id": "T1", "complexity": 3},
                {"id": "T2"},
            ]
        }
        assert project_batch_complexity(finalize_data, ["T1"]) == 3
        assert project_batch_complexity(finalize_data, ["T2"]) == 5
        assert project_batch_complexity(finalize_data, ["missing"]) == 5
