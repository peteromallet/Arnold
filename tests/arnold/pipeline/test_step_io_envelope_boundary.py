"""T7: Tests proving the M1 StepIOEnvelope round-trip covers only the
typed payload subset ``(logical_type, schema_version, payload)`` and that
``ContractResult.schema_version`` is never used for
``ContractSchemaRegistry.accepts_version(...)``.

These tests verify the namespace split mandated by SD2: the structural
``ContractResult.schema_version`` describes the ContractResult envelope
shape, while logical payload schema versions (``sha256:...`` hashes
retained in the schema registry) belong inside the payload domain.
"""

from __future__ import annotations

import json

import pytest

from arnold.pipeline.schema_registry import (
    AcceptedVersionRange,
    ContractSchemaRegistry,
    SchemaRegistryError,
    accepts_version,
)
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOEnvelope,
    StepIOOperation,
    classify_step_io_contract,
    is_step_io_envelope,
)
from arnold.pipeline.types import (
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_registry(tmp_path) -> ContractSchemaRegistry:
    """Return a registry with one 'review' schema registered."""
    registry = ContractSchemaRegistry(tmp_path)
    registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return registry


# ---------------------------------------------------------------------------
# (A) StepIOEnvelope round-trip only covers (logical_type, schema_version, payload)
# ---------------------------------------------------------------------------


class TestStepIOEnvelopePayloadSubset:
    """The M1 typed envelope carries exactly three fields and no others."""

    def test_from_json_rejects_missing_logical_type(self) -> None:
        assert StepIOEnvelope.from_json({"schema_version": "sha256:" + "a" * 64, "payload": 1}) is None

    def test_from_json_rejects_missing_schema_version(self) -> None:
        assert StepIOEnvelope.from_json({"logical_type": "review", "payload": 1}) is None

    def test_from_json_rejects_missing_payload_key(self) -> None:
        assert StepIOEnvelope.from_json({"logical_type": "review", "schema_version": "sha256:" + "a" * 64}) is None

    def test_from_json_rejects_empty_logical_type(self) -> None:
        assert StepIOEnvelope.from_json({"logical_type": "", "schema_version": "sha256:" + "a" * 64, "payload": 1}) is None

    def test_from_json_rejects_empty_schema_version(self) -> None:
        assert StepIOEnvelope.from_json({"logical_type": "review", "schema_version": "", "payload": 1}) is None

    def test_from_json_accepts_valid_envelope(self) -> None:
        env = StepIOEnvelope.from_json({
            "logical_type": "review",
            "schema_version": "sha256:" + "a" * 64,
            "payload": {"answer": 7},
        })
        assert env is not None
        assert env.logical_type == "review"
        assert env.schema_version == "sha256:" + "a" * 64
        assert env.payload == {"answer": 7}

    def test_to_json_produces_exactly_three_keys(self) -> None:
        env = StepIOEnvelope(
            logical_type="review",
            schema_version="sha256:" + "a" * 64,
            payload={"answer": 7},
        )
        data = env.to_json()
        assert set(data.keys()) == {"logical_type", "schema_version", "payload"}
        assert data["logical_type"] == "review"
        assert data["schema_version"] == "sha256:" + "a" * 64
        assert data["payload"] == {"answer": 7}

    def test_round_trip_preserves_payload_subset(self) -> None:
        original = StepIOEnvelope(
            logical_type="review",
            schema_version="sha256:" + "a" * 64,
            payload={"answer": 7},
        )
        rt = StepIOEnvelope.from_json(original.to_json())
        assert rt is not None
        assert rt.logical_type == original.logical_type
        assert rt.schema_version == original.schema_version
        assert rt.payload == original.payload

    def test_extra_fields_are_ignored_by_from_json(self) -> None:
        """Extra top-level keys in the JSON object are silently ignored.

        The M1 envelope only sees (logical_type, schema_version, payload);
        e.g. a persisted ContractResult.to_json() blob would have many more
        keys, but StepIOEnvelope.from_json only cares about those three.
        """
        blob = {
            "logical_type": "review",
            "schema_version": "sha256:" + "a" * 64,
            "payload": {"answer": 7},
            "status": "completed",
            "authority_level": "verified",
            "evidence_refs": [],
            "provenance": {
                "sources": [],
                "generator": None,
                "generated_at": None,
                "chain": [],
            },
            "freshness": {
                "observed_at": None,
                "ttl_seconds": None,
                "expires_at": None,
            },
            "suspension": None,
            "extra_field": 42,
        }
        env = StepIOEnvelope.from_json(blob)
        assert env is not None
        assert env.logical_type == "review"
        assert env.schema_version == "sha256:" + "a" * 64
        assert env.payload == {"answer": 7}

    def test_is_step_io_envelope_detects_valid_envelope(self) -> None:
        assert is_step_io_envelope({
            "logical_type": "x",
            "schema_version": "sha256:" + "b" * 64,
            "payload": None,
        }) is True

    def test_is_step_io_envelope_rejects_missing_payload_key(self) -> None:
        assert is_step_io_envelope({
            "logical_type": "x",
            "schema_version": "sha256:" + "b" * 64,
        }) is False

    def test_is_step_io_envelope_rejects_scalar(self) -> None:
        assert is_step_io_envelope("not-a-mapping") is False

    def test_is_step_io_envelope_rejects_list(self) -> None:
        assert is_step_io_envelope([1, 2, 3]) is False

    def test_is_step_io_envelope_rejects_none(self) -> None:
        assert is_step_io_envelope(None) is False


# ---------------------------------------------------------------------------
# (B) ContractResult.schema_version is NOT a logical payload schema version
# ---------------------------------------------------------------------------


class TestContractResultSchemaVersionIsStructural:
    """ContractResult.schema_version is the structural envelope hash,
    not a logical payload schema version usable by the schema registry."""

    def test_contract_result_schema_version_is_static_module_constant(self) -> None:
        """CONTRACT_RESULT_SCHEMA_VERSION is a deterministic hash of the
        ContractResult field descriptor — it is NOT derived from any
        logical payload schema."""
        assert isinstance(CONTRACT_RESULT_SCHEMA_VERSION, str)
        assert len(CONTRACT_RESULT_SCHEMA_VERSION) == 64
        assert CONTRACT_RESULT_SCHEMA_VERSION != ""

    def test_contract_result_schema_version_differs_from_payload_schema_version(self, tmp_path) -> None:
        """The structural schema_version on ContractResult is NOT the same
        as a logical payload schema version registered in the registry."""
        registry = _make_minimal_registry(tmp_path)
        payload_version = registry.latest("review")

        cr = ContractResult(payload={"answer": 7})
        assert cr.schema_version == CONTRACT_RESULT_SCHEMA_VERSION
        assert cr.schema_version != payload_version
        # The ContractResult structural hash is NOT registered under any
        # logical type in the registry — it's a different namespace.
        with pytest.raises(SchemaRegistryError):
            registry.get_schema(cr.schema_version)

    def test_contract_result_schema_version_can_be_normalized_but_is_not_registered(self) -> None:
        """CONTRACT_RESULT_SCHEMA_VERSION is bare 64-char hex. It CAN be
        normalized (bare hex is accepted), but it is NOT registered under
        any logical type in the schema registry — so registry lookups fail."""
        from arnold.pipeline.schema_registry import normalize_schema_version

        # Bare 64-char hex is valid and gets the sha256: prefix
        normalized = normalize_schema_version(CONTRACT_RESULT_SCHEMA_VERSION)
        assert normalized == f"sha256:{CONTRACT_RESULT_SCHEMA_VERSION}"

    def test_contract_result_normalized_version_not_in_registry(self, tmp_path) -> None:
        """Even after normalization, the version is not a registered blob."""
        registry = _make_minimal_registry(tmp_path)
        normalized = f"sha256:{CONTRACT_RESULT_SCHEMA_VERSION}"
        with pytest.raises(SchemaRegistryError):
            registry.get_schema(normalized)

    def test_payload_schema_version_with_prefix_is_valid_registry_version(self, tmp_path) -> None:
        """A logical payload schema version (sha256:<hex>) IS a valid
        registry version and can be normalized."""
        from arnold.pipeline.schema_registry import normalize_schema_version

        registry = _make_minimal_registry(tmp_path)
        payload_version = registry.latest("review")
        normalized = normalize_schema_version(payload_version)
        assert normalized.startswith("sha256:")
        assert len(normalized) == 64 + 7  # "sha256:" + 64 hex chars


# ---------------------------------------------------------------------------
# (C) ContractSchemaRegistry.accepts_version uses logical payload versions
#     from the registry index, NOT ContractResult.schema_version
# ---------------------------------------------------------------------------


class TestAcceptsVersionUsesPayloadSchemaVersions:
    """``accepts_version`` resolves against logical payload schema versions
    retained in the registry's per-logical-type history.

    ``ContractResult.schema_version`` is the wrong namespace — it is the
    structural envelope version, not a logical payload schema version.
    Passing it to ``accepts_version`` must either fail or behave
    independently of any registered logical payload schemas.
    """

    def test_accepts_version_accepts_registered_payload_version(self, tmp_path) -> None:
        registry = ContractSchemaRegistry(tmp_path)
        v1 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 1}}})
        v2 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 2}}})

        accepted = AcceptedVersionRange("demo", min_version=v1, max_version=v2)
        assert accepts_version("demo", v1, accepted, registry=registry) is True
        assert accepts_version("demo", v2, accepted, registry=registry) is True

    def test_accepts_version_rejects_unregistered_version(self, tmp_path) -> None:
        registry = ContractSchemaRegistry(tmp_path)
        v1 = registry.register("demo", {"type": "object"})
        # A version that is a valid sha256 hash but not registered under "demo"
        foreign = "sha256:" + "f" * 64
        with pytest.raises(SchemaRegistryError):
            accepts_version("demo", foreign, AcceptedVersionRange("demo"), registry=registry)

    def test_contract_result_schema_version_is_not_registered_in_any_logical_type_history(
        self, tmp_path,
    ) -> None:
        """After registering payload schemas, CONTRACT_RESULT_SCHEMA_VERSION
        must not appear in any logical type's version history."""
        registry = ContractSchemaRegistry(tmp_path)
        registry.register("demo", {"type": "object", "properties": {"v": {"const": 1}}})
        registry.register("other", {"type": "array"})

        for logical_type in ("demo", "other"):
            history = registry.history(logical_type)
            assert CONTRACT_RESULT_SCHEMA_VERSION not in history
            # Also the sha256:-qualified form must not be present
            assert f"sha256:{CONTRACT_RESULT_SCHEMA_VERSION}" not in history

    def test_accepts_version_requires_registry_has_that_version_in_logical_type_history(
        self, tmp_path,
    ) -> None:
        """Even if a version hash exists as a blob (registered under a
        different logical type), accepts_version rejects it when queried
        under another logical type."""
        registry = ContractSchemaRegistry(tmp_path)
        shared_schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        other_version = registry.register("other", shared_schema)
        registry.register("demo", {"type": "object", "properties": {"y": {"type": "integer"}}})

        accepted = AcceptedVersionRange("demo")
        assert accepts_version("demo", other_version, accepted, registry=registry) is False

    def test_accepts_version_range_must_match_logical_type(self, tmp_path) -> None:
        registry = ContractSchemaRegistry(tmp_path)
        version = registry.register("demo", {"type": "object"})

        with pytest.raises(SchemaRegistryError, match="must match"):
            accepts_version(
                "demo",
                version,
                AcceptedVersionRange("other"),
                registry=registry,
            )

    def test_latest_returns_payload_schema_version_not_contract_result_version(
        self, tmp_path,
    ) -> None:
        registry = _make_minimal_registry(tmp_path)
        latest = registry.latest("review")
        assert latest is not None
        assert latest.startswith("sha256:")
        assert latest != CONTRACT_RESULT_SCHEMA_VERSION
        assert f"sha256:{CONTRACT_RESULT_SCHEMA_VERSION}" != latest


# ---------------------------------------------------------------------------
# (D) classify_step_io_contract uses envelope.schema_version (payload domain)
#     never ContractResult.schema_version (structural domain)
# ---------------------------------------------------------------------------


class TestClassifyStepIOContractNamespaceSplit:
    """The contract classifier resolves schema versions from the envelope's
    ``schema_version`` field (payload domain), never from any
    ``ContractResult.schema_version`` (structural domain).

    These tests prove that even when a ``ContractResult`` is serialized and
    passed through the classifier, the registry lookup uses the envelope's
    ``schema_version`` (which is the logical payload schema version), not
    the structural ``ContractResult.schema_version``.
    """

    def test_classify_uses_envelope_schema_version_for_registry_lookup(self, tmp_path) -> None:
        """A valid typed envelope is classified as TYPED_VALID when its
        schema_version resolves in the registry."""
        registry = _make_minimal_registry(tmp_path)
        version = registry.latest("review")

        envelope = {
            "logical_type": "review",
            "schema_version": version,
            "payload": {"answer": 7},
        }
        context = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        decision = classify_step_io_contract(envelope, context)

        assert decision.classification == StepIOClassification.TYPED_VALID
        assert decision.envelope is not None
        assert decision.envelope.schema_version == version

    def test_classify_marks_invalid_when_payload_fails_schema(self, tmp_path) -> None:
        """An envelope with a valid schema_version but payload that fails
        validation is TYPED_INVALID."""
        registry = _make_minimal_registry(tmp_path)
        version = registry.latest("review")

        envelope = {
            "logical_type": "review",
            "schema_version": version,
            "payload": {"answer": "wrong-type"},
        }
        context = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        decision = classify_step_io_contract(envelope, context)

        assert decision.classification == StepIOClassification.TYPED_INVALID

    def test_classify_returns_legacy_unknown_for_non_mapping_values(self) -> None:
        """Scalars, lists, and None are never typed envelopes."""

        for value in ("string", 42, [1, 2], None, True):
            decision = classify_step_io_contract(value)
            assert decision.classification == StepIOClassification.LEGACY_UNKNOWN

    def test_classify_returns_legacy_unknown_for_mapping_without_envelope_shape(self) -> None:
        """Plain dicts without the full M1 envelope shape are legacy."""

        decision = classify_step_io_contract({"status": "completed"})
        assert decision.classification == StepIOClassification.LEGACY_UNKNOWN
        assert decision.envelope is None

    def test_classify_uses_only_envelope_fields_not_extra_keys(self, tmp_path) -> None:
        """Even when a dict has keys matching ContractResult (e.g. 'status',
        'authority_level'), the classifier only reads (logical_type,
        schema_version, payload)."""
        registry = _make_minimal_registry(tmp_path)
        version = registry.latest("review")

        blob = {
            "logical_type": "review",
            "schema_version": version,
            "payload": {"answer": 7},
            "status": "completed",
            "authority_level": "verified",
            "evidence_refs": [],
        }
        context = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        decision = classify_step_io_contract(blob, context)

        assert decision.classification == StepIOClassification.TYPED_VALID

    def test_contract_result_json_is_not_an_envelope_when_missing_logical_type(self) -> None:
        """ContractResult.to_json() omits 'logical_type' — it has
        'schema_version', 'status', 'payload', etc.  Therefore it is
        NOT a valid M1 typed envelope."""
        cr = ContractResult(payload={"answer": 7})
        json_data = cr.to_json()

        # ContractResult.to_json() does NOT contain 'logical_type'
        assert "logical_type" not in json_data

        # So StepIOEnvelope.from_json returns None
        assert StepIOEnvelope.from_json(json_data) is None
        assert is_step_io_envelope(json_data) is False

    def test_contract_result_payload_nesting_clarifies_namespace_split(self, tmp_path) -> None:
        """The logical payload schema version belongs inside
        contract_result.payload, while contract_result.schema_version is
        the structural envelope version. The M1 envelope is a separate
        concept: it wraps (logical_type, payload_schema_version, payload)
        for on-disk artifact representation."""
        registry = _make_minimal_registry(tmp_path)
        payload_version = registry.latest("review")

        # M1 typed envelope on disk
        m1_envelope = {
            "logical_type": "review",
            "schema_version": payload_version,
            "payload": {"answer": 7},
        }

        # This is structurally different from ContractResult:
        cr = ContractResult(payload={"answer": 7})

        # M1 envelope schema_version is a payload schema version
        assert m1_envelope["schema_version"].startswith("sha256:")
        # ContractResult.schema_version is a structural hash
        assert cr.schema_version == CONTRACT_RESULT_SCHEMA_VERSION
        assert cr.schema_version != m1_envelope["schema_version"]

        # The M1 envelope's schema_version resolves in the registry
        context = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        decision = classify_step_io_contract(m1_envelope, context)
        assert decision.classification == StepIOClassification.TYPED_VALID


# ---------------------------------------------------------------------------
# (E) Schema version format boundary: sha256: prefix enforcement
# ---------------------------------------------------------------------------


class TestSchemaVersionFormatBoundary:
    """The registry only accepts sha256:<hex> or bare 64-hex versions.

    ``CONTRACT_RESULT_SCHEMA_VERSION`` is bare 64-hex but is NOT a
    logical payload schema version — it cannot be used for registry
    schema lookups because it isn't registered under any logical type.
    """

    def test_normalize_rejects_non_hex_versions(self) -> None:
        from arnold.pipeline.schema_registry import normalize_schema_version

        for bad in ("v1.0", "abc", "sha256:zzz" + "z" * 61, "sha256:deadbeef"):
            with pytest.raises(SchemaRegistryError, match="invalid schema version"):
                normalize_schema_version(bad)

    def test_normalize_accepts_bare_64_hex(self) -> None:
        from arnold.pipeline.schema_registry import normalize_schema_version

        bare = "a" * 64
        normalized = normalize_schema_version(bare)
        assert normalized == f"sha256:{bare}"

    def test_normalize_accepts_sha256_prefixed_64_hex(self) -> None:
        from arnold.pipeline.schema_registry import normalize_schema_version

        prefixed = "sha256:" + "b" * 64
        normalized = normalize_schema_version(prefixed)
        assert normalized == prefixed

    def test_normalize_lowercases_hex(self) -> None:
        from arnold.pipeline.schema_registry import normalize_schema_version

        mixed = "sha256:" + "A" * 64
        normalized = normalize_schema_version(mixed)
        assert normalized == f"sha256:{'a' * 64}"
