"""Tests for CompletionBinding, SubjectInstanceId, bind().

Exercises hash determinism, evidence window semantics, and subject
instance distinctness.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

import pytest

from arnold.workflow.completion.binding import (
    CompletionBinding,
    bind,
    compute_binding_hash,
)
from arnold.workflow.completion.spec import (
    SubjectKind,
    make_completion_spec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_spec():
    """Create a sample CompletionSpec for binding tests."""
    return make_completion_spec(
        obligation_id="binding-spec-001",
        subject_kind=SubjectKind.WORKFLOW,
        canonical_name="test.workflow",
    )


@pytest.fixture
def another_spec():
    """Create another CompletionSpec with different identity."""
    return make_completion_spec(
        obligation_id="binding-spec-002",
        subject_kind=SubjectKind.STEP,
        canonical_name="test.step",
    )


# ---------------------------------------------------------------------------
# SubjectInstanceId — type alias
# ---------------------------------------------------------------------------


class TestSubjectInstanceId:
    """SubjectInstanceId is a typed identity record."""

    def test_is_typed_identity(self) -> None:
        """SubjectInstanceId preserves both id and subject kind."""
        from arnold.workflow.completion.binding import SubjectInstanceId
        uid = SubjectInstanceId("instance:test-001", SubjectKind.STEP)
        assert uid.id == "instance:test-001"
        assert uid.subject_kind is SubjectKind.STEP


# ---------------------------------------------------------------------------
# bind() — factory function
# ---------------------------------------------------------------------------


class TestBind:
    """bind() factory for CompletionBinding."""

    def test_basic_bind(self, sample_spec) -> None:
        """bind creates a CompletionBinding with matching spec_hash."""
        binding = bind(sample_spec, "instance:basic-001", "", "")
        assert binding.spec_hash == sample_spec.spec_hash
        assert binding.subject_instance_id == "instance:basic-001"
        assert binding.binding_hash.startswith("sha256:")

    def test_different_instance_distinct(self, sample_spec) -> None:
        """Same spec, different instance IDs produce different bindings."""
        binding_a = bind(sample_spec, "instance:dist-a", "", "")
        binding_b = bind(sample_spec, "instance:dist-b", "", "")
        assert binding_a.binding_hash != binding_b.binding_hash

    def test_different_spec_distinct(self, sample_spec, another_spec) -> None:
        """Different specs, same instance ID produce different bindings."""
        binding_a = bind(sample_spec, "instance:same", "", "")
        binding_b = bind(another_spec, "instance:same", "", "")
        assert binding_a.binding_hash != binding_b.binding_hash

    def test_identical_bindings_match(self, sample_spec) -> None:
        """Identical spec + instance produces identical binding_hash."""
        binding_a = bind(sample_spec, "instance:det-001", "", "")
        binding_b = bind(sample_spec, "instance:det-001", "", "")
        assert binding_a.binding_hash == binding_b.binding_hash


# ---------------------------------------------------------------------------
# CompletionBinding — dataclass construction
# ---------------------------------------------------------------------------


class TestCompletionBinding:
    """CompletionBinding frozen dataclass."""

    def test_requires_non_empty_instance_id(self) -> None:
        """ValueError on empty subject_instance_id."""
        spec = make_completion_spec(
            obligation_id="binding-empty-inst",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.empty",
        )
        # Compute a valid binding_hash so the check reaches subject_instance_id
        from arnold.workflow.completion.binding import compute_binding_hash
        valid_hash = compute_binding_hash(
            spec_hash=spec.spec_hash,
            subject_instance_id="will-be-overridden",
            evidence_window_start="",
            evidence_window_end="",
        )
        with pytest.raises(ValueError, match="subject_instance_id"):
            CompletionBinding(
                binding_hash=valid_hash,
                spec_hash=spec.spec_hash,
                subject_instance_id="",
                evidence_window_start="",
                evidence_window_end="",
            )

    def test_requires_sha256_prefix(self) -> None:
        """ValueError on non-sha256 prefixed hash."""
        spec = make_completion_spec(
            obligation_id="binding-bad-prefix",
            subject_kind=SubjectKind.STEP,
            canonical_name="test.badprefix",
        )
        with pytest.raises(ValueError, match="sha256:"):
            CompletionBinding(
                binding_hash="md5:abc123",
                spec_hash=spec.spec_hash,
                subject_instance_id="instance:badprefix",
                evidence_window_start="",
                evidence_window_end="",
            )

    def test_auto_computes_binding_hash(self) -> None:
        """Valid CompletionBinding via bind() factory."""
        spec = make_completion_spec(
            obligation_id="binding-auto-hash",
            subject_kind=SubjectKind.WORKFLOW,
            canonical_name="test.autohash",
        )
        binding = bind(
            spec=spec,
            subject_instance_id="instance:autohash",
        )
        assert binding.binding_hash.startswith("sha256:")
        assert binding.spec_hash == spec.spec_hash
        # binding_hash is deterministic: identical bind() calls match
        binding2 = bind(
            spec=spec,
            subject_instance_id="instance:autohash",
        )
        assert binding.binding_hash == binding2.binding_hash

    def test_round_trip(self, sample_spec) -> None:
        """Round-trip through to_dict and from_dict."""
        binding = bind(sample_spec, "instance:rt-001", "", "")
        data = binding.to_dict()
        restored = CompletionBinding.from_dict(data)
        assert restored.binding_hash == binding.binding_hash
        assert restored.spec_hash == binding.spec_hash
        assert restored.subject_instance_id == binding.subject_instance_id

    def test_approved_typed_contract_fields_round_trip(self, sample_spec) -> None:
        binding = bind(
            sample_spec,
            "instance:approved",
            "2026-08-31T00:00:00Z",
            "2026-08-31T01:00:00Z",
            admission_source="s2f:receipt#approved",
            bound_artifacts=("sha256:artifact",),
        )
        assert binding.obligation_id == sample_spec.obligation_id
        assert binding.subject_instance_id.id == "instance:approved"
        assert binding.subject_instance_id.subject_kind is SubjectKind.WORKFLOW
        assert binding.admission_source == "s2f:receipt#approved"
        assert binding.evidence_window == (
            "2026-08-31T00:00:00Z", "2026-08-31T01:00:00Z"
        )
        assert binding.bound_artifacts == ("sha256:artifact",)
        assert binding.schema_version == "arnold.workflow.completion_binding.v1"
        assert CompletionBinding.from_dict(binding.to_dict()) == binding

    def test_binding_hash_covers_typed_contract_fields(self, sample_spec) -> None:
        base = bind(sample_spec, "instance:hash-fields")
        changed = bind(
            sample_spec,
            "instance:hash-fields",
            admission_source="s2f:other",
            bound_artifacts=("sha256:artifact",),
        )
        assert changed.binding_hash != base.binding_hash


# ---------------------------------------------------------------------------
# compute_binding_hash — standalone hash function
# ---------------------------------------------------------------------------


class TestComputeBindingHash:
    """Standalone binding_hash computation."""

    def test_returns_sha256_prefixed(self) -> None:
        """compute_binding_hash returns sha256: prefixed hash."""
        h = compute_binding_hash(
            spec_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            subject_instance_id="instance:ch-001",
            evidence_window_start="",
            evidence_window_end="",
        )
        assert h.startswith("sha256:")
        int(h[len("sha256:"):], 16)

    def test_deterministic(self) -> None:
        """Identical inputs produce identical hash."""
        h1 = compute_binding_hash(
            spec_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            subject_instance_id="instance:det",
            evidence_window_start="",
            evidence_window_end="",
        )
        h2 = compute_binding_hash(
            spec_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            subject_instance_id="instance:det",
            evidence_window_start="",
            evidence_window_end="",
        )
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        """Different inputs produce different hashes."""
        h1 = compute_binding_hash(
            spec_hash="sha256:" + "a" * 64,
            subject_instance_id="instance:a",
            evidence_window_start="",
            evidence_window_end="",
        )
        h2 = compute_binding_hash(
            spec_hash="sha256:" + "b" * 64,
            subject_instance_id="instance:b",
            evidence_window_start="",
            evidence_window_end="",
        )
        assert h1 != h2


# ---------------------------------------------------------------------------
# Evidence window — subject instance distinctness
# ---------------------------------------------------------------------------


class TestEvidenceWindow:
    """Subject instance distinctness affects binding identity."""

    def test_same_spec_different_runs(self, sample_spec) -> None:
        """Same spec from different workflow runs has different binding."""
        run_1 = bind(sample_spec, "instance:run-001", "", "")
        run_2 = bind(sample_spec, "instance:run-002", "", "")
        assert run_1.binding_hash != run_2.binding_hash

    def test_same_spec_same_run(self, sample_spec) -> None:
        """Same spec from same run produces identical binding."""
        run_1a = bind(sample_spec, "instance:run-003", "", "")
        run_1b = bind(sample_spec, "instance:run-003", "", "")
        assert run_1a.binding_hash == run_1b.binding_hash
