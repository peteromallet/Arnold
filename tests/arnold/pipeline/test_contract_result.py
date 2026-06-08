"""Tests for ContractResult and related types (M0a T2).

Covers default assertions, round-trip equality, schema_version,
strict/lenient from_json, json.dumps survival, Suspension/EvidenceArtifactRef
round-trips, and FrozenInstanceError for all new dataclasses.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from arnold.pipeline.types import (
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Provenance,
    Suspension,
    register_schema,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_cr() -> ContractResult:
    """Return a default-constructed ContractResult (no args)."""
    return ContractResult()


def _populated_cr() -> ContractResult:
    """Return a fully-populated ContractResult with all fields non-default."""
    ev = EvidenceArtifactRef(
        uri="s3://bucket/logs/scan-1.json",
        content_type="application/json",
        digest="sha256:abc123",
        size_bytes=2048,
        name="scan-output",
    )
    sus = Suspension(
        kind="human",
        awaitable="approval/42",
        prompt="Approve the deployment?",
        display_refs=(ev,),
        resume_input_schema={"yes": "bool", "no": "bool"},
        resume_cursor="cursor-7",
        thread_ref="thread/1",
        actor="alice",
        deadline="2026-06-06T00:00:00Z",
        on_timeout="reject",
        default_action="reject",
    )
    prov = Provenance(
        sources=("policy:scan-v1",),
        generator="scanner@1.2",
        generated_at="2026-06-05T10:00:00Z",
        chain=("scan-step", "validate-step"),
    )
    fresh = Freshness(
        observed_at="2026-06-05T10:00:00Z",
        ttl_seconds=3600,
        expires_at="2026-06-05T11:00:00Z",
    )
    return ContractResult(
        payload={"score": 0.95, "label": "high"},
        status=ContractStatus.COMPLETED,
        schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
        suspension=sus,
        evidence_refs=(ev,),
        authority_level="verified",
        provenance=prov,
        freshness=fresh,
    )


def _suspension_full() -> Suspension:
    """Return a Suspension with every field populated."""
    ev = EvidenceArtifactRef(
        uri="s3://bucket/img.png",
        content_type="image/png",
        digest="sha256:def456",
        size_bytes=1024,
        name="diagram",
    )
    return Suspension(
        kind="human",
        awaitable="task/99",
        prompt="Proceed?",
        display_refs=(ev,),
        resume_input_schema={"allow": "bool"},
        resume_cursor="c-1",
        thread_ref="t-1",
        actor="bob",
        deadline="2026-07-01T00:00:00Z",
        on_timeout="approve",
        default_action="approve",
    )


def _ev_ref() -> EvidenceArtifactRef:
    """Return a fully-populated EvidenceArtifactRef."""
    return EvidenceArtifactRef(
        uri="file:///tmp/report.pdf",
        content_type="application/pdf",
        digest="sha256:ghi789",
        size_bytes=4096,
        name="final-report",
    )


# ---------------------------------------------------------------------------
# T2(a): Default-constructed ContractResult assertions
# ---------------------------------------------------------------------------


class TestDefaultContractResult:
    """Default ContractResult() has expected field values."""

    def test_status_is_completed(self) -> None:
        cr = _default_cr()
        assert cr.status == ContractStatus.COMPLETED

    def test_suspension_is_none(self) -> None:
        cr = _default_cr()
        assert cr.suspension is None

    def test_evidence_refs_is_empty_tuple(self) -> None:
        cr = _default_cr()
        assert cr.evidence_refs == ()

    def test_authority_level_is_empty_string(self) -> None:
        cr = _default_cr()
        assert cr.authority_level == ""

    def test_provenance_is_default(self) -> None:
        cr = _default_cr()
        assert cr.provenance == Provenance()

    def test_freshness_is_default(self) -> None:
        cr = _default_cr()
        assert cr.freshness == Freshness()

    def test_payload_is_empty_dict(self) -> None:
        cr = _default_cr()
        assert cr.payload == {}

    def test_schema_version_is_current_schema_hash(self) -> None:
        cr = _default_cr()
        assert cr.schema_version == CONTRACT_RESULT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# T2(b): Fully-populated ContractResult round-trips
# ---------------------------------------------------------------------------


class TestContractResultRoundTrip:
    """Fully-populated ContractResult survives to_json/from_json."""

    def test_default_round_trip_equality(self) -> None:
        cr = _default_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt == cr

    def test_full_round_trip_equality(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt == cr

    def test_full_round_trip_payload(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.payload == cr.payload
        assert rt.payload["score"] == 0.95

    def test_full_round_trip_status(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.status == ContractStatus.COMPLETED

    def test_full_round_trip_suspension(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.suspension == cr.suspension

    def test_full_round_trip_evidence_refs(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.evidence_refs == cr.evidence_refs

    def test_full_round_trip_authority_level(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.authority_level == "verified"

    def test_full_round_trip_provenance(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.provenance == cr.provenance

    def test_full_round_trip_freshness(self) -> None:
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert rt.freshness == cr.freshness


# ---------------------------------------------------------------------------
# T2(c): schema_version in to_json()
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    """schema_version field in to_json() output."""

    def test_default_to_json_has_nonempty_schema_version(self) -> None:
        cr = _default_cr()
        j = cr.to_json()
        assert "schema_version" in j
        assert j["schema_version"] != ""
        assert j["schema_version"] == CONTRACT_RESULT_SCHEMA_VERSION

    def test_populated_to_json_has_correct_schema_version(self) -> None:
        cr = _populated_cr()
        j = cr.to_json()
        assert "schema_version" in j
        assert j["schema_version"] == CONTRACT_RESULT_SCHEMA_VERSION

    def test_schema_version_is_64_char_hex(self) -> None:
        assert len(CONTRACT_RESULT_SCHEMA_VERSION) == 64
        # All hex characters
        assert all(c in "0123456789abcdef" for c in CONTRACT_RESULT_SCHEMA_VERSION)

    def test_schema_version_reproducible_via_register_schema(self) -> None:
        """Re-derive schema version via register_schema() must match."""
        from dataclasses import fields as _dc_fields
        import re as _re

        def _normalise_type_name(t: Any) -> str:
            s = t if isinstance(t, str) else str(t)
            s = _re.sub(r"\s+", "", s)
            s = _re.sub(r"typing\.", "", s)
            return s

        descriptor: dict[str, str] = {
            f.name: _normalise_type_name(f.type) for f in _dc_fields(ContractResult)
        }
        re_derived = register_schema(descriptor)
        assert re_derived == CONTRACT_RESULT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Strict-version ValueError in from_json
# ---------------------------------------------------------------------------


class TestStrictSchemaVersion:
    """from_json raises ValueError on schema_version mismatch."""

    def test_mismatched_schema_version_raises_value_error(self) -> None:
        bad_data = {
            "schema_version": "0000000000000000000000000000000000000000000000000000000000000000",
            "status": "completed",
            "payload": {},
            "suspension": None,
            "evidence_refs": [],
            "authority_level": "",
            "provenance": {},
            "freshness": {},
        }
        with pytest.raises(ValueError, match="schema_version mismatch"):
            ContractResult.from_json(bad_data)

    def test_empty_schema_version_does_not_raise(self) -> None:
        """Empty persisted schema_version is treated as 'missing' and should not raise."""
        data: dict[str, Any] = {
            "schema_version": "",
            "status": "completed",
            "payload": {},
            "suspension": None,
            "evidence_refs": [],
            "authority_level": "",
            "provenance": {},
            "freshness": {},
        }
        cr = ContractResult.from_json(data)
        assert cr.status == ContractStatus.COMPLETED

    def test_missing_schema_version_does_not_raise(self) -> None:
        """Missing schema_version key should not raise."""
        data: dict[str, Any] = {
            "status": "completed",
            "payload": {},
            "suspension": None,
            "evidence_refs": [],
            "authority_level": "",
            "provenance": {},
            "freshness": {},
        }
        cr = ContractResult.from_json(data)
        assert cr.status == ContractStatus.COMPLETED
        assert cr.schema_version == CONTRACT_RESULT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Lenient unknown keys
# ---------------------------------------------------------------------------


class TestLenientUnknownKeys:
    """from_json is lenient for unknown top-level keys."""

    def test_unknown_key_is_tolerated(self) -> None:
        data: dict[str, Any] = {
            "schema_version": CONTRACT_RESULT_SCHEMA_VERSION,
            "status": "completed",
            "payload": {},
            "suspension": None,
            "evidence_refs": [],
            "authority_level": "",
            "provenance": {},
            "freshness": {},
            "extra_field": "should-be-ignored",
            "another_extra": 42,
        }
        # Should not raise
        cr = ContractResult.from_json(data)
        assert cr.status == ContractStatus.COMPLETED

    def test_unknown_key_preserves_round_trip(self) -> None:
        """Unknown keys are silently dropped but known keys round-trip."""
        cr = _populated_cr()
        j = cr.to_json()
        j["future_field"] = "v2-data"
        rt = ContractResult.from_json(j)
        # Round-trip must still produce an equal result (unknown field dropped)
        assert rt == cr


# ---------------------------------------------------------------------------
# json.dumps survival
# ---------------------------------------------------------------------------


class TestJsonDumpsSurvival:
    """to_json() output survives json.dumps and json.loads."""

    def test_default_json_dumps_survives(self) -> None:
        cr = _default_cr()
        s = json.dumps(cr.to_json(), sort_keys=True)
        loaded = json.loads(s)
        rt = ContractResult.from_json(loaded)
        # After round-trip, schema_version is populated from the wire
        assert rt.status == cr.status
        assert rt.suspension is None
        assert rt.evidence_refs == ()
        assert rt.authority_level == ""
        assert rt.schema_version == CONTRACT_RESULT_SCHEMA_VERSION

    def test_populated_json_dumps_survives(self) -> None:
        cr = _populated_cr()
        s = json.dumps(cr.to_json(), sort_keys=True)
        loaded = json.loads(s)
        rt = ContractResult.from_json(loaded)
        assert rt == cr

    def test_json_dumps_no_exceptions(self) -> None:
        """json.dumps must not raise TypeError on to_json() output."""
        cr = _populated_cr()
        # This would raise if any value is non-serializable
        s = json.dumps(cr.to_json())
        assert isinstance(s, str)
        assert len(s) > 0


# ---------------------------------------------------------------------------
# Suspension full-field round-trip
# ---------------------------------------------------------------------------


class TestSuspensionRoundTrip:
    """Suspension with all fields populated survives round-trip."""

    def test_full_suspension_round_trip_equality(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt == sus

    def test_full_suspension_kind(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.kind == "human"

    def test_full_suspension_awaitable(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.awaitable == "task/99"

    def test_full_suspension_prompt(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.prompt == "Proceed?"

    def test_full_suspension_display_refs(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert len(rt.display_refs) == 1
        assert rt.display_refs[0] == sus.display_refs[0]

    def test_full_suspension_resume_input_schema(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.resume_input_schema == {"allow": "bool"}

    def test_full_suspension_resume_cursor(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.resume_cursor == "c-1"

    def test_full_suspension_thread_ref(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.thread_ref == "t-1"

    def test_full_suspension_actor(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.actor == "bob"

    def test_full_suspension_deadline(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.deadline == "2026-07-01T00:00:00Z"

    def test_full_suspension_on_timeout(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.on_timeout == "approve"

    def test_full_suspension_default_action(self) -> None:
        sus = _suspension_full()
        rt = Suspension.from_json(sus.to_json())
        assert rt.default_action == "approve"

    def test_default_suspension_round_trip(self) -> None:
        sus = Suspension(kind="")
        rt = Suspension.from_json(sus.to_json())
        assert rt == sus


# ---------------------------------------------------------------------------
# EvidenceArtifactRef standalone + embedded round-trip
# ---------------------------------------------------------------------------


class TestEvidenceArtifactRefRoundTrip:
    """EvidenceArtifactRef survives round-trip standalone and embedded."""

    def test_standalone_round_trip_equality(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt == ref

    def test_standalone_uri(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt.uri == "file:///tmp/report.pdf"

    def test_standalone_content_type(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt.content_type == "application/pdf"

    def test_standalone_digest(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt.digest == "sha256:ghi789"

    def test_standalone_size_bytes(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt.size_bytes == 4096

    def test_standalone_name(self) -> None:
        ref = _ev_ref()
        rt = EvidenceArtifactRef.from_json(ref.to_json())
        assert rt.name == "final-report"

    def test_embedded_in_contract_result(self) -> None:
        """EvidenceArtifactRef embedded in ContractResult survives round-trip."""
        cr = _populated_cr()
        rt = ContractResult.from_json(cr.to_json())
        assert len(rt.evidence_refs) == 1
        assert rt.evidence_refs[0] == cr.evidence_refs[0]
        assert rt.evidence_refs[0].uri == "s3://bucket/logs/scan-1.json"

    def test_multiple_evidence_refs_round_trip(self) -> None:
        ev1 = EvidenceArtifactRef(
            uri="file:///a.txt", content_type="text/plain", name="a"
        )
        ev2 = EvidenceArtifactRef(
            uri="file:///b.txt", content_type="text/plain", name="b"
        )
        cr = ContractResult(
            payload={"scanned": True},
            evidence_refs=(ev1, ev2),
            authority_level="asserted",
        )
        rt = ContractResult.from_json(cr.to_json())
        assert len(rt.evidence_refs) == 2
        assert rt.evidence_refs[0] == ev1
        assert rt.evidence_refs[1] == ev2


# ---------------------------------------------------------------------------
# FrozenInstanceError on all new dataclasses
# ---------------------------------------------------------------------------


class TestFrozen:
    """All new dataclasses are frozen (raise FrozenInstanceError on mutation)."""

    def test_evidence_artifact_ref_is_frozen(self) -> None:
        ref = _ev_ref()
        with pytest.raises(Exception):
            ref.uri = "mutated"  # type: ignore[misc]

    def test_suspension_is_frozen(self) -> None:
        sus = Suspension(kind="human")
        with pytest.raises(Exception):
            sus.kind = "mutated"  # type: ignore[misc]

    def test_provenance_is_frozen(self) -> None:
        prov = Provenance()
        with pytest.raises(Exception):
            prov.generator = "mutated"  # type: ignore[misc]

    def test_freshness_is_frozen(self) -> None:
        fresh = Freshness()
        with pytest.raises(Exception):
            fresh.ttl_seconds = 999  # type: ignore[misc]

    def test_contract_result_is_frozen(self) -> None:
        cr = _default_cr()
        with pytest.raises(Exception):
            cr.status = ContractStatus.FAILED  # type: ignore[misc]

    def test_contract_result_from_json_produces_frozen(self) -> None:
        cr = ContractResult.from_json({"status": "completed", "payload": {}})
        with pytest.raises(Exception):
            cr.authority_level = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ContractStatus enum
# ---------------------------------------------------------------------------


class TestContractStatus:
    """ContractStatus enum has the expected three members."""

    def test_three_members(self) -> None:
        assert ContractStatus.COMPLETED.value == "completed"
        assert ContractStatus.SUSPENDED.value == "suspended"
        assert ContractStatus.FAILED.value == "failed"

    def test_from_value(self) -> None:
        assert ContractStatus("completed") == ContractStatus.COMPLETED
        assert ContractStatus("suspended") == ContractStatus.SUSPENDED
        assert ContractStatus("failed") == ContractStatus.FAILED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ContractStatus("unknown")


# ---------------------------------------------------------------------------
# Provenance round-trip
# ---------------------------------------------------------------------------


class TestProvenanceRoundTrip:
    """Provenance survives to_json/from_json."""

    def test_default_round_trip(self) -> None:
        prov = Provenance()
        rt = Provenance.from_json(prov.to_json())
        assert rt == prov

    def test_populated_round_trip(self) -> None:
        prov = Provenance(
            sources=("policy:v1", "rule:v1"),
            generator="scanner@1.0",
            generated_at="2026-01-01T00:00:00Z",
            chain=("a", "b", "c"),
        )
        rt = Provenance.from_json(prov.to_json())
        assert rt == prov
        assert rt.sources == ("policy:v1", "rule:v1")
        assert rt.chain == ("a", "b", "c")


# ---------------------------------------------------------------------------
# Freshness round-trip
# ---------------------------------------------------------------------------


class TestFreshnessRoundTrip:
    """Freshness survives to_json/from_json."""

    def test_default_round_trip(self) -> None:
        fresh = Freshness()
        rt = Freshness.from_json(fresh.to_json())
        assert rt == fresh

    def test_populated_round_trip(self) -> None:
        fresh = Freshness(
            observed_at="2026-01-01T00:00:00Z",
            ttl_seconds=300,
            expires_at="2026-01-01T00:05:00Z",
        )
        rt = Freshness.from_json(fresh.to_json())
        assert rt == fresh


# ---------------------------------------------------------------------------
# ContractResult with FAILED and SUSPENDED status
# ---------------------------------------------------------------------------


class TestContractResultStatuses:
    """ContractResult round-trips with all three status values."""

    def test_failed_status(self) -> None:
        cr = ContractResult(
            status=ContractStatus.FAILED,
            payload={"error": "timeout"},
        )
        rt = ContractResult.from_json(cr.to_json())
        assert rt.status == ContractStatus.FAILED
        assert rt.suspension is None

    def test_suspended_status(self) -> None:
        sus = Suspension(kind="human", prompt="Awaiting input")
        cr = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=sus,
            payload={"step": "verify"},
        )
        rt = ContractResult.from_json(cr.to_json())
        assert rt.status == ContractStatus.SUSPENDED
        assert rt.suspension == sus

    def test_null_suspension_serialised_as_none(self) -> None:
        cr = ContractResult(status=ContractStatus.COMPLETED, suspension=None)
        j = cr.to_json()
        assert j["suspension"] is None
