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
    AdmissionDisposition,
    AmbiguousBindingError,
    CANONICAL_BINDING_SCHEMA_VERSION,
    CompletionBinding,
    LEGACY_BINDING_SCHEMA_VERSION,
    ResumeDisposition,
    admit_binding,
    bind,
    compute_binding_hash,
    resume_binding,
)
from arnold.workflow.completion.evidence import EvidenceScope, EvidenceWindow, ScalarCursor
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


def _canonical_scope(**changes):
    values = {
        "subject_id": "subject:binding",
        "occurrence_id": "occurrence:binding",
        "attempt_id": "attempt:1",
        "generation": 0,
        "source_lock": "source:v1",
        "runtime_lock": "runtime:v1",
        "dependency_lock": "dependency:v1",
        "store_id": "store:primary",
        "store_incarnation": "store-incarnation:1",
        "restore_id": "restore:1",
        "restore_generation": 0,
        "evidence_window": EvidenceWindow(ScalarCursor(1), ScalarCursor(9)),
        "custody": {"target": "run/binding", "epoch": 2},
        "authority_fence": {"token": 3, "epoch": 2},
        "epoch": 2,
        "wbc_version": "wbc:v1",
        "admitted_child_set_digest": "sha256:" + "b" * 64,
    }
    values.update(changes)
    return EvidenceScope(**values)


def _canonical_binding(spec, **changes):
    fields = {
        "evidence_scope": _canonical_scope(),
        "semantic_path": "workflow/step/0",
        "component_lock": "component:v1",
        "graph_lock": "graph:v1",
        "installed_artifact_digest": "artifact:v1",
        "prompt_asset_digest": "prompt:v1",
        "tool_asset_digest": "tool:v1",
        "policy_asset_digest": "policy:v1",
        "prompt_tool_bindings_digest": "calls:v1",
        "call_site_policy_digest": "call-policy:v1",
        "admission_receipt": {"id": "receipt:1", "digest": "receipt:v1"},
        "product_contract_digest": "contract:v1",
        "asset_digests": {"source": "source-asset:v1"},
        "bound_artifacts": ("artifact:output:v1",),
    }
    fields.update(changes)
    return bind(spec, "instance:c2", **fields)


def test_canonical_binding_uses_scope_and_round_trips(sample_spec) -> None:
    binding = _canonical_binding(sample_spec)
    assert binding.is_canonical
    assert binding.schema_version == CANONICAL_BINDING_SCHEMA_VERSION
    assert binding.evidence_scope == _canonical_scope()
    assert binding.evidence_window is None
    encoded = binding.to_dict()
    assert "evidence_scope" in encoded
    assert "evidence_window" not in encoded
    assert CompletionBinding.from_dict(encoded) == binding


def test_canonical_hash_covers_semantic_and_artifact_locks(sample_spec) -> None:
    base = _canonical_binding(sample_spec)
    for field, value in {
        "semantic_path": "workflow/other",
        "component_lock": "component:v2",
        "graph_lock": "graph:v2",
        "installed_artifact_digest": "artifact:v2",
        "prompt_asset_digest": "prompt:v2",
        "tool_asset_digest": "tool:v2",
        "policy_asset_digest": "policy:v2",
        "prompt_tool_bindings_digest": "calls:v2",
        "call_site_policy_digest": "call-policy:v2",
        "admission_receipt": {"id": "receipt:2"},
        "product_contract_digest": "contract:v2",
        "asset_digests": {"source": "source-asset:v2"},
        "bound_artifacts": ("artifact:output:v2",),
    }.items():
        changed = _canonical_binding(sample_spec, **{field: value})
        assert changed.binding_hash != base.binding_hash, field


def test_admission_is_idempotent_and_conflicts_are_explicit(sample_spec) -> None:
    binding = _canonical_binding(sample_spec)
    assert admit_binding(binding).disposition is AdmissionDisposition.ADMITTED
    repeat = admit_binding(CompletionBinding.from_dict(binding.to_dict()), [binding])
    assert repeat.disposition is AdmissionDisposition.IDEMPOTENT
    assert repeat.binding == binding
    conflict = _canonical_binding(sample_spec, semantic_path="workflow/changed")
    result = admit_binding(conflict, [binding])
    assert result.disposition is AdmissionDisposition.CONFLICT
    assert not result.accepted


def test_resume_requires_explicit_disposition_for_changed_binding(sample_spec) -> None:
    pinned = _canonical_binding(sample_spec)
    changed = _canonical_binding(sample_spec, semantic_path="workflow/changed")
    blocked = resume_binding(pinned, changed)
    assert blocked.disposition is ResumeDisposition.REQUIRES_EXPLICIT
    assert not blocked.accepted
    migrated = resume_binding(pinned, changed, disposition="migration")
    assert migrated.disposition is ResumeDisposition.MIGRATION
    assert migrated.accepted
    assert resume_binding(pinned, pinned).pinned


def test_c1_shape_is_legacy_unknown_without_coordinate_reinterpretation(sample_spec) -> None:
    legacy = bind(sample_spec, "instance:legacy", "cursor-start", "cursor-end")
    assert legacy.schema_version == LEGACY_BINDING_SCHEMA_VERSION
    assert legacy.is_legacy
    assert legacy.evidence_scope is None
    assert legacy.evidence_window == ("cursor-start", "cursor-end")
    decoded = CompletionBinding.from_dict(legacy.to_dict())
    assert decoded.compatibility_status == "legacy/unknown"
    assert decoded.evidence_window_record is None
    assert admit_binding(decoded).disposition is AdmissionDisposition.LEGACY_UNKNOWN
    explicit = resume_binding(decoded, decoded, disposition="quarantine")
    assert explicit.disposition is ResumeDisposition.QUARANTINE
    assert explicit.accepted


def test_mixed_coordinate_shapes_and_future_versions_are_rejected(sample_spec) -> None:
    binding = _canonical_binding(sample_spec)
    mixed = binding.to_dict()
    mixed["evidence_window"] = ["old-start", "old-end"]
    with pytest.raises(AmbiguousBindingError):
        CompletionBinding.from_dict(mixed)
    future = binding.to_dict()
    future["schema_version"] = "arnold.workflow.completion_binding.v99"
    with pytest.raises(ValueError, match="unsupported"):
        CompletionBinding.from_dict(future)


def test_canonical_aliases_and_one_shot_artifacts_are_bound(sample_spec) -> None:
    scope = _canonical_scope()
    binding = bind(
        sample_spec,
        "instance:aliases",
        evidence_window=scope,
        semantic_lock={"path": "workflow/step/0"},
        artifact_locks=("artifact-lock:v1",),
        bound_artifacts=(item for item in ("output:v1",)),
    )
    restored = CompletionBinding.from_dict(binding.to_dict())
    assert restored == binding
    assert binding.artifact_locks == ["artifact-lock:v1"]
    assert binding.bound_artifacts == ("output:v1",)


def test_required_disposition_alias_and_coordinate_schema_are_explicit(sample_spec) -> None:
    scope = _canonical_scope()
    binding = _canonical_binding(sample_spec)
    conflict = _canonical_binding(sample_spec, semantic_path="workflow/conflict")
    result = admit_binding(conflict, [binding], disposition="new_attempt_required")
    assert result.disposition is AdmissionDisposition.NEW_ATTEMPT
    assert result.accepted
    with pytest.raises(AmbiguousBindingError):
        bind(sample_spec, "instance:bad-schema", evidence_scope=scope, schema_version=LEGACY_BINDING_SCHEMA_VERSION)
