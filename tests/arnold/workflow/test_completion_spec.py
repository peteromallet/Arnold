"""Tests for CompletionSpec, SubjectKind, Obligation, ProofMode, identity helpers.

Exercises round-trip serialization, hash determinism, SubjectKind usage,
obligation identity, and tombstone semantics.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

import pytest

from arnold.workflow.completion.spec import (
    CompletionSpec,
    Obligation,
    ProofMode,
    SubjectKind,
    compute_spec_hash,
    make_completion_spec,
    obligation_identity,
    tombstone_spec,
)


# ---------------------------------------------------------------------------
# SubjectKind — enumeration values
# ---------------------------------------------------------------------------


class TestSubjectKind:
    """SubjectKind enum values and properties."""

    def test_values(self) -> None:
        """All required SubjectKind values exist."""
        assert SubjectKind.WORKFLOW.value == "workflow"
        assert SubjectKind.STEP.value == "step"
        assert SubjectKind.DYNAMIC_TASK.value == "dynamic_task"
        assert SubjectKind.EFFECT.value == "effect"
        assert SubjectKind.HUMAN_BOUNDARY.value == "human_boundary"
        assert set(kind.value for kind in SubjectKind) == {
            "workflow",
            "step",
            "dynamic_task",
            "effect",
            "human_boundary",
        }

    def test_six_variants(self) -> None:
        """The five unified SubjectKind variants."""
        variants = set(SubjectKind)
        assert len(variants) == 5
        assert SubjectKind.WORKFLOW in variants
        assert SubjectKind.STEP in variants
        assert SubjectKind.DYNAMIC_TASK in variants
        assert SubjectKind.EFFECT in variants
        assert SubjectKind.HUMAN_BOUNDARY in variants


# ---------------------------------------------------------------------------
# ProofMode — enumeration values
# ---------------------------------------------------------------------------


class TestProofMode:
    """ProofMode enum values."""

    def test_values(self) -> None:
        """All four ProofMode values exist."""
        assert ProofMode.PRESENCE.value == "presence"
        assert ProofMode.COMPLETE_CAPTURE_ABSENCE.value == "complete_capture_absence"
        assert ProofMode.SET_EQUALITY.value == "set_equality"
        assert ProofMode.AGGREGATE.value == "aggregate"

    def test_four_modes(self) -> None:
        """Four ProofMode variants."""
        assert len(set(ProofMode)) == 4


# ---------------------------------------------------------------------------
# Obligation — construction and serialization
# ---------------------------------------------------------------------------


class TestObligation:
    """Obligation dataclass construction, __post_init__, serialization."""

    def test_basic_construction(self) -> None:
        """Minimal Obligation with required fields."""
        obl = Obligation(
            obligation_id="obl-001",
            kind=ProofMode.PRESENCE,
            description="Verify presence of acceptance receipt",
        )
        assert obl.obligation_id == "obl-001"
        assert obl.kind == ProofMode.PRESENCE
        assert obl.description == "Verify presence of acceptance receipt"
        assert obl.required is True
        assert obl.target_evidence_kinds == ()

    def test_from_dict_round_trip(self) -> None:
        """Obligation round-trips through to_dict and from_dict."""
        obl = Obligation(
            obligation_id="obl-002",
            kind=ProofMode.SET_EQUALITY,
            description="Check evidence set",
            target_evidence_kinds=("receipt", "log"),
            required=False,
        )
        data = obl.to_dict()
        restored = Obligation.from_dict(data)
        assert restored.obligation_id == obl.obligation_id
        assert restored.kind == obl.kind
        assert restored.description == obl.description
        assert restored.target_evidence_kinds == obl.target_evidence_kinds
        assert restored.required == obl.required

    def test_requires_non_empty_id(self) -> None:
        """Obligation raises ValueError for empty obligation_id."""
        with pytest.raises(ValueError, match="obligation_id"):
            Obligation(
                obligation_id="",
                kind=ProofMode.PRESENCE,
                description="desc",
            )

    def test_requires_non_empty_description(self) -> None:
        """Obligation raises ValueError for empty description."""
        with pytest.raises(ValueError, match="description"):
            Obligation(
                obligation_id="obl-003",
                kind=ProofMode.PRESENCE,
                description="",
            )

    def test_string_kind_normalized(self) -> None:
        """String kind value is normalized to ProofMode enum."""
        obl = Obligation(
            obligation_id="obl-004",
            kind="presence",
            description="string kind",
        )
        assert isinstance(obl.kind, ProofMode)
        assert obl.kind == ProofMode.PRESENCE


# ---------------------------------------------------------------------------
# CompletionSpec — construction, hash determinism, round-trip
# ---------------------------------------------------------------------------


class TestCompletionSpec:
    """CompletionSpec construction, hash computation, round-trip."""

    def test_basic_construction(self) -> None:
        """Minimal CompletionSpec with make_completion_spec."""
        spec = make_completion_spec(
            obligation_id="spec-001",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.workflow",
        )
        assert spec.obligation_id == "spec-001"
        assert spec.subject_kind == SubjectKind.WORKFLOW
        assert spec.canonical_name == "test.workflow"
        assert spec.spec_hash.startswith("sha256:")
        assert len(spec.spec_hash) == 64 + len("sha256:")

    def test_hash_determinism(self) -> None:
        """Identical specs produce identical spec_hash."""
        spec_a = make_completion_spec(
            obligation_id="spec-det",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.step",
        )
        spec_b = make_completion_spec(
            obligation_id="spec-det",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.step",
        )
        assert spec_a.spec_hash == spec_b.spec_hash

    def test_hash_differs_for_different_inputs(self) -> None:
        """Different obligation_id produces different hash."""
        spec_a = make_completion_spec(
            obligation_id="spec-diff-a",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.step",
        )
        spec_b = make_completion_spec(
            obligation_id="spec-diff-b",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.step",
        )
        assert spec_a.spec_hash != spec_b.spec_hash

    def test_subject_kind_affects_hash(self) -> None:
        """Different SubjectKind produces different hash."""
        spec_a = make_completion_spec(
            obligation_id="spec-kind",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.subject",
        )
        spec_b = make_completion_spec(
            obligation_id="spec-kind",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.subject",
        )
        assert spec_a.spec_hash != spec_b.spec_hash

    def test_round_trip_to_dict(self) -> None:
        """CompletionSpec round-trips through to_dict and from_dict."""
        spec = make_completion_spec(
            obligation_id="spec-rt",
            subject_kind=SubjectKind.EFFECT,
            canonical_name="test.effect",
        )
        data = spec.to_dict()
        restored = CompletionSpec.from_dict(data)
        assert restored.spec_hash == spec.spec_hash
        assert restored.obligation_id == spec.obligation_id
        assert restored.subject_kind == spec.subject_kind
        assert restored.canonical_name == spec.canonical_name
        assert restored.schema_version == spec.schema_version

    def test_with_obligations(self) -> None:
        """CompletionSpec with obligations produces deterministic hash."""
        obl = Obligation(
            obligation_id="obl-in-spec",
            kind=ProofMode.PRESENCE,
            description="Test obligation",
        )
        spec = make_completion_spec(
            obligation_id="spec-obl",
            subject_kind=SubjectKind.HUMAN_BOUNDARY,
            canonical_name="test.review",
            obligations=(obl,),
        )
        assert spec.spec_hash.startswith("sha256:")
        assert len(spec.obligations) == 1
        assert spec.obligations[0].obligation_id == "obl-in-spec"

    def test_string_subject_kind_normalized(self) -> None:
        """String subject_kind value is normalized to SubjectKind enum."""
        spec = make_completion_spec(
            obligation_id="spec-str-kind",
            subject_kind=SubjectKind("step"),
            canonical_name="test.step",
        )
        assert isinstance(spec.subject_kind, SubjectKind)
        assert spec.subject_kind == SubjectKind.STEP

    def test_validates_schema_version(self) -> None:
        """Invalid schema_version raises ValueError."""
        with pytest.raises(ValueError, match="schema_version"):
            CompletionSpec(
                spec_hash="",
                obligation_id="spec-bad-schema",
                subject_kind=SubjectKind.STEP,
                schema_version="invalid.v1",
            )


# ---------------------------------------------------------------------------
# compute_spec_hash — standalone hash function
# ---------------------------------------------------------------------------


class TestComputeSpecHash:
    """Standalone spec_hash computation."""

    def test_returns_sha256_prefixed(self) -> None:
        """compute_spec_hash returns sha256: prefixed digest."""
        h = compute_spec_hash(
            obligation_id="ch-001",
            subject_kind=SubjectKind.WORKFLOW,
            obligations=(),
            schema_version="arnold.workflow.completion_spec.v1",
            canonical_name="test.hash",
        )
        assert h.startswith("sha256:")
        assert len(h) == 64 + len("sha256:")
        int(h[len("sha256:"):], 16)  # raises if not hex

    def test_deterministic(self) -> None:
        """Identical inputs produce identical hash."""
        h1 = compute_spec_hash(
            obligation_id="ch-det",
            subject_kind=SubjectKind.STEP,
            obligations=(),
            schema_version="arnold.workflow.completion_spec.v1",
            canonical_name="test.det",
        )
        h2 = compute_spec_hash(
            obligation_id="ch-det",
            subject_kind=SubjectKind.STEP,
            obligations=(),
            schema_version="arnold.workflow.completion_spec.v1",
            canonical_name="test.det",
        )
        assert h1 == h2


# ---------------------------------------------------------------------------
# obligation_identity — identity tuple
# ---------------------------------------------------------------------------


class TestObligationIdentity:
    """obligation_identity helper."""

    def test_returns_tuple(self) -> None:
        """Returns (spec_hash, obligation_id) tuple."""
        spec = make_completion_spec(
            obligation_id="id-001",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.identity",
        )
        identity = obligation_identity(spec)
        assert isinstance(identity, tuple)
        assert len(identity) == 2
        assert identity[0] == spec.spec_hash
        assert identity[1] == spec.obligation_id


# ---------------------------------------------------------------------------
# tombstone_spec — tombstone semantics
# ---------------------------------------------------------------------------


class TestTombstoneSpec:
    """tombstone_spec preserves hash lineage but changes identity."""

    def test_spec_hash_differs(self) -> None:
        """Tombstone produces a different spec_hash from the original."""
        original = make_completion_spec(
            obligation_id="tomb-001",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.original",
        )
        tombstone = tombstone_spec(original)
        assert tombstone.spec_hash != original.spec_hash

    def test_changes_obligation_id(self) -> None:
        """Tombstone has a different obligation_id."""
        original = make_completion_spec(
            obligation_id="tomb-002",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.original",
        )
        tombstone = tombstone_spec(original)
        assert tombstone.obligation_id != original.obligation_id
        assert tombstone.obligation_id.startswith("tombstone:")

    def test_changes_canonical_name(self) -> None:
        """Tombstone canonical_name reflects tombstone suffix."""
        original = make_completion_spec(
            obligation_id="tomb-003",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.original",
        )
        tombstone = tombstone_spec(original)
        assert "__tombstone" in tombstone.canonical_name
        assert "test.original" in tombstone.canonical_name

    def test_tombstone_is_valid_spec(self) -> None:
        """Tombstone is a valid CompletionSpec (passes __post_init__)."""
        original = make_completion_spec(
            obligation_id="tomb-004",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.valid",
        )
        tombstone = tombstone_spec(original)
        # Reconstruct to verify round-trip validity
        data = tombstone.to_dict()
        restored = CompletionSpec.from_dict(data)
        assert restored.spec_hash == tombstone.spec_hash
