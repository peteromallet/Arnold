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
    HumanSuspension,
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


# ---------------------------------------------------------------------------
# T1: Contract boundary regression tests — x-arnold-resume round-trip
#     and dataclass field-name stability
# ---------------------------------------------------------------------------


class TestXArnoldResumeRoundTrip:
    """Prove resume_input_schema['x-arnold-resume'] survives to_json/from_json."""

    def test_x_arnold_resume_preserved_exactly(self) -> None:
        """x-arnold-resume payload round-trips exactly through HumanSuspension."""
        resume_payload: dict[str, Any] = {
            "produces": {"scan_report": "s3://bucket/scan-1.json"},
            "cursor": {"step": "scan-step", "iteration": 3},
            "reverify": True,
        }
        sus = HumanSuspension(
            kind="human",
            prompt="Re-verify?",
            resume_input_schema={"x-arnold-resume": resume_payload},
        )
        rt = HumanSuspension.from_json(sus.to_json())
        assert rt.resume_input_schema == {"x-arnold-resume": resume_payload}
        assert rt.resume_input_schema["x-arnold-resume"] == resume_payload
        # Verify nested equality
        assert rt.resume_input_schema["x-arnold-resume"]["produces"] == resume_payload["produces"]
        assert rt.resume_input_schema["x-arnold-resume"]["cursor"] == resume_payload["cursor"]
        assert rt.resume_input_schema["x-arnold-resume"]["reverify"] is True

    def test_x_arnold_resume_preserved_with_other_keys(self) -> None:
        """x-arnold-resume coexists with other resume_input_schema keys."""
        resume_payload: dict[str, Any] = {"step_id": "verify-1", "token": "abc123"}
        sus = HumanSuspension(
            kind="human",
            prompt="Approve?",
            resume_input_schema={
                "yes": "bool",
                "x-arnold-resume": resume_payload,
                "comment": "str",
            },
        )
        rt = HumanSuspension.from_json(sus.to_json())
        assert rt.resume_input_schema == {
            "yes": "bool",
            "x-arnold-resume": resume_payload,
            "comment": "str",
        }
        assert rt.resume_input_schema["x-arnold-resume"] == resume_payload

    def test_x_arnold_resume_survives_via_contract_result(self) -> None:
        """x-arnold-resume round-trips through ContractResult embedding."""
        resume_payload: dict[str, Any] = {"artifacts": ["file:///tmp/a.pdf"]}
        sus = HumanSuspension(
            kind="human",
            prompt="Check artifacts?",
            resume_input_schema={"x-arnold-resume": resume_payload},
        )
        cr = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=sus,
            payload={"phase": "verify"},
        )
        rt = ContractResult.from_json(cr.to_json())
        assert rt.status == ContractStatus.SUSPENDED
        assert rt.suspension is not None
        assert rt.suspension.resume_input_schema == {"x-arnold-resume": resume_payload}
        assert rt.suspension.resume_input_schema["x-arnold-resume"] == resume_payload

    def test_x_arnold_resume_absent_round_trips_normally(self) -> None:
        """When x-arnold-resume is absent, normal round-trip still works."""
        sus = HumanSuspension(
            kind="human",
            prompt="Proceed?",
            resume_input_schema={"allow": "bool", "reason": "str"},
        )
        rt = HumanSuspension.from_json(sus.to_json())
        assert rt.resume_input_schema == {"allow": "bool", "reason": "str"}
        assert "x-arnold-resume" not in rt.resume_input_schema

    def test_x_arnold_resume_nested_dicts_and_lists(self) -> None:
        """x-arnold-resume survives with nested dicts/lists/json types."""
        resume_payload: dict[str, Any] = {
            "nested": {"a": [1, 2, 3], "b": {"deep": True}},
            "list_of_strings": ["x", "y", "z"],
            "null_val": None,
        }
        sus = HumanSuspension(
            kind="human",
            prompt="Complex payload?",
            resume_input_schema={"x-arnold-resume": resume_payload},
        )
        rt = HumanSuspension.from_json(sus.to_json())
        assert rt.resume_input_schema["x-arnold-resume"] == resume_payload
        assert rt.resume_input_schema["x-arnold-resume"]["nested"]["b"]["deep"] is True
        assert rt.resume_input_schema["x-arnold-resume"]["null_val"] is None


class TestDataclassFieldNames:
    """Prove HumanSuspension and ContractResult field names are stable."""

    def test_human_suspension_field_names(self) -> None:
        """HumanSuspension field names must exactly match the expected set."""
        from dataclasses import fields as _fields
        actual = frozenset(f.name for f in _fields(HumanSuspension))
        expected = frozenset({
            "kind",
            "awaitable",
            "prompt",
            "display_refs",
            "resume_input_schema",
            "resume_cursor",
            "thread_ref",
            "actor",
            "deadline",
            "on_timeout",
            "default_action",
        })
        assert actual == expected, f"Unexpected fields: {actual ^ expected}"

    def test_contract_result_field_names(self) -> None:
        """ContractResult field names must exactly match the expected set."""
        from dataclasses import fields as _fields
        actual = frozenset(f.name for f in _fields(ContractResult))
        expected = frozenset({
            "payload",
            "status",
            "schema_version",
            "suspension",
            "evidence_refs",
            "authority_level",
            "provenance",
            "freshness",
        })
        assert actual == expected, f"Unexpected fields: {actual ^ expected}"

    def test_suspension_alias_resolves_to_human_suspension(self) -> None:
        """Suspension alias is byte-identical to HumanSuspension."""
        assert Suspension is HumanSuspension
        # Ensure they have the same fields
        from dataclasses import fields as _fields
        assert frozenset(f.name for f in _fields(Suspension)) == frozenset(
            f.name for f in _fields(HumanSuspension)
        )

    def test_human_suspension_field_order_stable(self) -> None:
        """Field declaration order is part of the contract; it must not change."""
        from dataclasses import fields as _fields
        actual = tuple(f.name for f in _fields(HumanSuspension))
        expected = (
            "kind",
            "awaitable",
            "prompt",
            "display_refs",
            "resume_input_schema",
            "resume_cursor",
            "thread_ref",
            "actor",
            "deadline",
            "on_timeout",
            "default_action",
        )
        assert actual == expected, f"Field order changed: {actual}"

    def test_contract_result_field_order_stable(self) -> None:
        """Field declaration order is part of the contract; it must not change."""
        from dataclasses import fields as _fields
        actual = tuple(f.name for f in _fields(ContractResult))
        expected = (
            "payload",
            "status",
            "schema_version",
            "suspension",
            "evidence_refs",
            "authority_level",
            "provenance",
            "freshness",
        )
        assert actual == expected, f"Field order changed: {actual}"


# ---------------------------------------------------------------------------
# T3: Declaration-bearing human gate producer tests — generic/neutral path
# ---------------------------------------------------------------------------


class TestBuildResumeReverifySchema:
    """Tests for the neutral build_resume_reverify_schema() helper."""

    def test_no_args_returns_empty_dict(self) -> None:
        """When no declaration fields are supplied, returns empty dict (no-declaration parity)."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema()
        assert result == {}

    def test_all_none_args_returns_empty_dict(self) -> None:
        """Explicit None values produce empty dict, same as absent args."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(
            port=None, content_type=None, artifact_path=None, artifact_ref=None,
        )
        assert result == {}

    def test_port_only_produces_declaration(self) -> None:
        """Providing port alone produces x-arnold-resume with port + default invalid_policy."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(port="scan_output")
        assert result == {
            "x-arnold-resume": {
                "port": "scan_output",
                "invalid_policy": "resuspend",
            }
        }

    def test_content_type_only_produces_declaration(self) -> None:
        """Providing content_type alone produces x-arnold-resume with content_type + default invalid_policy."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(content_type="text/markdown")
        assert result == {
            "x-arnold-resume": {
                "content_type": "text/markdown",
                "invalid_policy": "resuspend",
            }
        }

    def test_artifact_path_only_produces_declaration(self) -> None:
        """Providing artifact_path alone produces x-arnold-resume with artifact_path + default invalid_policy."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(artifact_path="/tmp/scan/v1.md")
        assert result == {
            "x-arnold-resume": {
                "artifact_path": "/tmp/scan/v1.md",
                "invalid_policy": "resuspend",
            }
        }

    def test_artifact_ref_only_produces_declaration(self) -> None:
        """Providing artifact_ref alone produces x-arnold-resume with artifact_ref + default invalid_policy."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        ref = {"uri": "s3://bkt/file.md", "content_type": "text/markdown"}
        result = build_resume_reverify_schema(artifact_ref=ref)
        assert result == {
            "x-arnold-resume": {
                "artifact_ref": ref,
                "invalid_policy": "resuspend",
            }
        }

    def test_all_fields_produces_full_declaration(self) -> None:
        """All declaration fields + custom invalid_policy produce complete x-arnold-resume."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(
            port="report_port",
            content_type="application/json",
            artifact_path="/tmp/report/v3.json",
            artifact_ref={"name": "report", "uri": "s3://bkt/report.json"},
            invalid_policy="reject",
        )
        assert result == {
            "x-arnold-resume": {
                "port": "report_port",
                "content_type": "application/json",
                "artifact_path": "/tmp/report/v3.json",
                "artifact_ref": {"name": "report", "uri": "s3://bkt/report.json"},
                "invalid_policy": "reject",
            }
        }

    def test_empty_string_port_still_produces_declaration(self) -> None:
        """Empty string for port is still a provided value — produces declaration."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(port="")
        assert "x-arnold-resume" in result
        assert result["x-arnold-resume"]["port"] == ""

    def test_invalid_policy_default_is_resuspend(self) -> None:
        """Default invalid_policy is 'resuspend' when not overridden."""
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema

        result = build_resume_reverify_schema(port="p")
        assert result["x-arnold-resume"]["invalid_policy"] == "resuspend"

    def test_result_is_megaplan_free(self) -> None:
        """build_resume_reverify_schema does not import megaplan at runtime."""
        import sys

        # Ensure no megaplan module is pulled in by this import
        before = {k for k in sys.modules if "megaplan" in k.lower()}
        from arnold.pipeline.steps.human_gate import build_resume_reverify_schema  # noqa: F811
        after = {k for k in sys.modules if "megaplan" in k.lower()}
        leaked = after - before
        assert not leaked, f"megaplan modules leaked on import: {leaked}"

        # Invoke the function to confirm it doesn't trigger megaplan imports
        result = build_resume_reverify_schema(port="test")
        assert "x-arnold-resume" in result


class TestHumanGateCheckpointResumeInputSchema:
    """Checkpoint round-trip for resume_input_schema through the generic
    write_human_gate_checkpoint → read_human_gate_checkpoint →
    make_human_suspension pipeline."""

    def test_resume_input_schema_round_trips_through_checkpoint(self, tmp_path: Path):
        """resume_input_schema written via write_human_gate_checkpoint is read back exactly."""
        from arnold.pipeline.steps.human_gate import (
            build_resume_reverify_schema,
            make_human_suspension,
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"
        resume_schema = build_resume_reverify_schema(
            port="scan_out", content_type="text/markdown", artifact_path="/tmp/v1.md",
        )

        written = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="test-pipe",
            version=1,
            artifact_stage="scan",
            prompt="Review?",
            resume_input_schema=resume_schema,
            stage="decide",
            choices=["yes", "no"],
        )

        assert written["resume_input_schema"] == resume_schema

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        assert read["resume_input_schema"] == resume_schema

        suspension = make_human_suspension(read)
        assert suspension.resume_input_schema == resume_schema
        assert suspension.resume_input_schema["x-arnold-resume"]["port"] == "scan_out"

    def test_empty_resume_input_schema_not_embedded(self, tmp_path: Path):
        """When resume_input_schema is empty/None, it is NOT written to checkpoint."""
        from arnold.pipeline.steps.human_gate import (
            make_human_suspension,
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"

        # Empty dict
        written = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="test-pipe",
            version=1,
            artifact_stage="scan",
            prompt="Review?",
            resume_input_schema={},
            stage="decide",
            choices=["yes"],
        )
        assert "resume_input_schema" not in written

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        assert "resume_input_schema" not in read

        suspension = make_human_suspension(read)
        assert suspension.resume_input_schema == {}

        # None
        checkpoint_path2 = tmp_path / "awaiting_user2.json"
        written2 = write_human_gate_checkpoint(
            checkpoint_path2,
            pipeline="test-pipe",
            version=1,
            artifact_stage="scan",
            prompt="Review?",
            resume_input_schema=None,
            stage="decide",
            choices=["yes"],
        )
        assert "resume_input_schema" not in written2

    def test_resume_input_schema_coexists_with_other_checkpoint_keys(self, tmp_path: Path):
        """resume_input_schema in checkpoint coexists with all standard keys."""
        from arnold.pipeline.steps.human_gate import (
            build_resume_reverify_schema,
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"
        resume_schema = build_resume_reverify_schema(port="p1")

        write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="pipeline-x",
            version=2,
            artifact_stage="verify",
            prompt="Check this",
            display_refs=(),
            resume_input_schema=resume_schema,
            stage="human_gate",
            choices=["ok", "reject"],
            message="Paused waiting for human.",
        )

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        assert read["pipeline"] == "pipeline-x"
        assert read["version"] == 2
        assert read["stage"] == "human_gate"
        assert read["artifact_stage"] == "verify"
        assert read["choices"] == ["ok", "reject"]
        assert read["resume_input_schema"] == resume_schema

    def test_resume_input_schema_survives_write_read_without_declaration(self, tmp_path: Path):
        """A non-x-arnold-resume resume_input_schema also round-trips through checkpoint."""
        from arnold.pipeline.steps.human_gate import (
            make_human_suspension,
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"
        schema = {"yes": "bool", "reason": "str"}

        write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="p",
            version=1,
            artifact_stage="a",
            prompt="?",
            resume_input_schema=schema,
            stage="g",
            choices=["yes", "no"],
        )

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        assert read["resume_input_schema"] == schema

        suspension = make_human_suspension(read)
        assert suspension.resume_input_schema == schema

    def test_make_human_suspension_defaults_schema_to_empty_dict(self) -> None:
        """When checkpoint has no resume_input_schema, make_human_suspension returns empty dict."""
        from arnold.pipeline.steps.human_gate import make_human_suspension

        checkpoint: dict[str, Any] = {
            "pipeline": "test",
            "version": 1,
            "prompt": "Go?",
            "display_refs": [],
            "stage": "decide",
        }
        suspension = make_human_suspension(checkpoint)
        assert suspension.resume_input_schema == {}

    def test_make_human_suspension_with_non_dict_schema_defaults_to_empty(self) -> None:
        """When resume_input_schema is not a dict, make_human_suspension defaults to {}."""
        from arnold.pipeline.steps.human_gate import make_human_suspension

        checkpoint: dict[str, Any] = {
            "pipeline": "test",
            "version": 1,
            "prompt": "Go?",
            "display_refs": [],
            "resume_input_schema": "not-a-dict",
        }
        suspension = make_human_suspension(checkpoint)
        assert suspension.resume_input_schema == {}

    def test_human_suspension_to_json_from_json_preserves_x_arnold_resume_from_checkpoint(
        self, tmp_path: Path,
    ) -> None:
        """Full pipeline: build schema → write checkpoint → read → make suspension →
        to_json → from_json preserves x-arnold-resume exactly."""
        from arnold.pipeline.steps.human_gate import (
            build_resume_reverify_schema,
            make_human_suspension,
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )
        from arnold.pipeline.types import HumanSuspension

        checkpoint_path = tmp_path / "awaiting_user.json"
        resume_schema = build_resume_reverify_schema(
            port="out", content_type="text/plain", artifact_path="/tmp/x.md",
        )

        write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="p",
            version=1,
            artifact_stage="a",
            resume_input_schema=resume_schema,
            stage="g",
            choices=["ok"],
        )

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        suspension = make_human_suspension(read, resume_cursor="c-1")

        # to_json/from_json round-trip
        rt = HumanSuspension.from_json(suspension.to_json())
        assert rt.resume_input_schema == resume_schema
        assert rt.resume_cursor == "c-1"
        assert rt.resume_input_schema["x-arnold-resume"]["port"] == "out"

    def test_write_human_gate_checkpoint_returns_dict(self, tmp_path: Path) -> None:
        """write_human_gate_checkpoint returns the written checkpoint dict."""
        from arnold.pipeline.steps.human_gate import write_human_gate_checkpoint

        checkpoint_path = tmp_path / "awaiting_user.json"
        result = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="p",
            version=1,
            artifact_stage="a",
            stage="s",
            choices=["c"],
        )
        assert isinstance(result, dict)
        assert result["pipeline"] == "p"
        assert checkpoint_path.exists()


class TestHumanGateCheckpointNoDeclaration:
    """No-declaration parity: behavior unchanged when x-arnold-resume is absent."""

    def test_checkpoint_without_resume_input_schema_matches_legacy_shape(self, tmp_path: Path):
        """When no resume_input_schema passed, checkpoint shape is identical to pre-T2 behavior."""
        from arnold.pipeline.steps.human_gate import (
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"
        write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="legacy-pipe",
            version=3,
            artifact_stage="review",
            prompt="Approve?",
            stage="human_decide",
            choices=["yes", "no"],
            message="Review the artifact.",
        )

        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        # No declaration key present
        assert "resume_input_schema" not in read
        # All standard keys present
        assert read["pipeline"] == "legacy-pipe"
        assert read["version"] == 3
        assert read["artifact_stage"] == "review"
        assert read["stage"] == "human_decide"
        assert read["choices"] == ["yes", "no"]

    def test_read_human_gate_checkpoint_returns_none_for_missing_file(self, tmp_path: Path):
        """read_human_gate_checkpoint returns None when file doesn't exist."""
        from arnold.pipeline.steps.human_gate import read_human_gate_checkpoint

        result = read_human_gate_checkpoint(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_human_gate_checkpoint_returns_none_for_malformed_json(self, tmp_path: Path):
        """read_human_gate_checkpoint returns None for malformed JSON."""
        from arnold.pipeline.steps.human_gate import read_human_gate_checkpoint

        (tmp_path / "bad.json").write_text("{not valid json")
        result = read_human_gate_checkpoint(tmp_path / "bad.json")
        assert result is None

    def test_read_human_gate_checkpoint_returns_none_for_non_dict(self, tmp_path: Path):
        """read_human_gate_checkpoint returns None when file contains a list instead of dict."""
        from arnold.pipeline.steps.human_gate import read_human_gate_checkpoint

        (tmp_path / "list.json").write_text("[1, 2, 3]")
        result = read_human_gate_checkpoint(tmp_path / "list.json")
        assert result is None

    def test_cleanup_behavior_unchanged_when_declaration_absent(self, tmp_path: Path):
        """Cleanup (file deletion) works identically with or without declaration.
        The read/delete logic is independent of resume_input_schema presence."""
        import json

        from arnold.pipeline.steps.human_gate import read_human_gate_checkpoint

        # Write a checkpoint WITHOUT declaration (legacy shape)
        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint_path.write_text(json.dumps({
            "pipeline": "test",
            "version": 1,
            "stage": "decide",
            "artifact_stage": "review",
            "choices": ["ok"],
            "message": "...",
            "_resume_choice": "ok",
        }))

        # Read should succeed
        read = read_human_gate_checkpoint(checkpoint_path)
        assert read is not None
        assert read["_resume_choice"] == "ok"
        assert "resume_input_schema" not in read

        # Cleanup: delete (simulating resume cleanup)
        checkpoint_path.unlink()
        assert not checkpoint_path.exists()

        # Re-read after cleanup returns None
        assert read_human_gate_checkpoint(checkpoint_path) is None
