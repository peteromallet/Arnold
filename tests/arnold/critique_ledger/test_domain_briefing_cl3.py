"""T18 schema tests for the CL3 DomainBriefingEnvelope contract.

Covers every new field, the exact split_parentrefs tuple serialization,
strict rejection of unknown keys, preserve-mode extras, and migration-free
loading of legacy payloads with empty defaults.
"""

from __future__ import annotations

import pytest

from arnold.critique_ledger.schemas import (
    SCHEMA_VERSION,
    DomainBriefingEnvelope,
)


class TestDomainBriefingCL3Fields:
    """Exhaustive coverage of the CL3 briefing envelope serialized contract."""

    def _full_envelope(self) -> DomainBriefingEnvelope:
        return DomainBriefingEnvelope(
            schema_version=SCHEMA_VERSION,
            briefing_id="briefing-cl3",
            revision_manifest_hash="manifest-hash",
            budget_level="high",
            domains=("domain_a", "domain_b"),
            findings=("F1", "F2"),
            open_findings=("F1",),
            blocked_findings=("F2",),
            accepted_risk_findings=("F3",),
            unknown_findings=("F4",),
            resolved_findings=("F5",),
            duplicate_findings=("F6",),
            acted_on_findings=("F1",),
            ignored_findings=("F7",),
            deferred_findings=("F8",),
            cross_domain_refs=("XD-1",),
            spillover_findings=("F9",),
            prior_instructions=("PI-1",),
            revision_actions=("RA-1",),
            conclusions=("C-1",),
            questions=("Q-1",),
            reopen_conditions=("RC-1",),
            evidence_refs=("E-1",),
            evidence_unavailable=("EU-1",),
            split_parent_refs=(("F1", "splits"), ("F2", "merges")),
            stale_flag=True,
            rebuild_trigger="stale",
            input_set_hash="input-hash",
            included_reasons={"F1": "kept"},
            excluded_reasons={"F9": "budget"},
            no_additional_findings=True,
            no_open_blocking_findings=False,
            no_known_findings=False,
            no_adjacent_text_match=True,
            is_truncated=True,
            truncation_warning="budget cap reached",
            timestamp_utc="2026-08-07T00:00:00Z",
            metadata={"k": "v"},
        )

    def test_every_new_field_round_trips(self) -> None:
        env = self._full_envelope()
        d = env.to_dict()
        # disposition sub-buckets
        assert d["accepted_risk_findings"] == ["F3"]
        assert d["resolved_findings"] == ["F5"]
        assert d["duplicate_findings"] == ["F6"]
        assert d["acted_on_findings"] == ["F1"]
        assert d["ignored_findings"] == ["F7"]
        assert d["deferred_findings"] == ["F8"]
        # evidence / freshness / identity
        assert d["evidence_unavailable"] == ["EU-1"]
        assert d["input_set_hash"] == "input-hash"
        assert d["no_additional_findings"] is True
        assert d["no_open_blocking_findings"] is False
        assert d["no_known_findings"] is False
        assert d["no_adjacent_text_match"] is True
        assert d["split_parent_refs"] == [["F1", "splits"], ["F2", "merges"]]
        # full round-trip preserves equality
        env2 = DomainBriefingEnvelope.from_dict(d)
        assert env2 == env

    def test_split_parent_refs_exact_serialization(self) -> None:
        env = DomainBriefingEnvelope(
            split_parent_refs=(("P1", "splits"), ("P2", "merges")),
        )
        d = env.to_dict()
        # serialized as list of [parent, relationship] lists
        assert d["split_parent_refs"] == [["P1", "splits"], ["P2", "merges"]]
        # parsed back as tuples of (str, str)
        env2 = DomainBriefingEnvelope.from_dict(d)
        assert env2.split_parent_refs == (("P1", "splits"), ("P2", "merges"))
        assert all(isinstance(pair, tuple) for pair in env2.split_parent_refs)
        assert all(
            isinstance(parent, str) and isinstance(rel, str)
            for parent, rel in env2.split_parent_refs
        )

    def test_split_parent_refs_empty_default(self) -> None:
        env = DomainBriefingEnvelope()
        assert env.split_parent_refs == ()
        assert env.to_dict()["split_parent_refs"] == []

    def test_strict_rejects_unknown_keys(self) -> None:
        env = self._full_envelope()
        d = env.to_dict()
        d["future_field"] = "unknown"
        with pytest.raises(ValueError, match="Unknown field"):
            DomainBriefingEnvelope.from_dict(d, mode="strict")

    def test_preserve_mode_keeps_extras(self) -> None:
        env = self._full_envelope()
        d = env.to_dict(mode="preserve")
        d["future_field"] = "kept"
        env2 = DomainBriefingEnvelope.from_dict(d, mode="preserve")
        assert env2._extra == {"future_field": "kept"}
        # preserve to_dict re-emits the extras
        out = env2.to_dict(mode="preserve")
        assert out["future_field"] == "kept"

    def test_legacy_payload_loads_with_empty_defaults(self) -> None:
        legacy = {
            "schema_version": SCHEMA_VERSION,
            "briefing_id": "legacy",
            "budget_level": "standard",
            "domains": ["domain_a"],
            "findings": ["F1"],
            "open_findings": ["F1"],
        }
        env = DomainBriefingEnvelope.from_dict(legacy)
        assert env.briefing_id == "legacy"
        assert env.findings == ("F1",)
        # every new field defaults to empty / false / None
        assert env.accepted_risk_findings == ()
        assert env.resolved_findings == ()
        assert env.duplicate_findings == ()
        assert env.acted_on_findings == ()
        assert env.ignored_findings == ()
        assert env.deferred_findings == ()
        assert env.blocked_findings == ()
        assert env.unknown_findings == ()
        assert env.evidence_unavailable == ()
        assert env.evidence_refs == ()
        assert env.spillover_findings == ()
        assert env.cross_domain_refs == ()
        assert env.split_parent_refs == ()
        assert env.input_set_hash == ""
        assert env.no_additional_findings is False
        assert env.no_known_findings is False
        assert env.no_open_blocking_findings is False
        assert env.no_adjacent_text_match is False
        assert env.rebuild_trigger is None
        assert env.truncation_warning is None
        assert env.is_truncated is False
        assert env.stale_flag is False
        assert env._extra == {}

    def test_legacy_payload_strict_round_trip(self) -> None:
        legacy = {
            "schema_version": SCHEMA_VERSION,
            "briefing_id": "legacy",
            "budget_level": "standard",
            "domains": ("d1",),
            "findings": ("F1",),
        }
        env = DomainBriefingEnvelope.from_dict(legacy, mode="strict")
        out = env.to_dict(mode="strict")
        env2 = DomainBriefingEnvelope.from_dict(out, mode="strict")
        assert env2 == env

    def test_round_trip_is_deterministic(self) -> None:
        env = self._full_envelope()
        d1 = env.to_dict(mode="strict")
        d2 = DomainBriefingEnvelope.from_dict(d1).to_dict(mode="strict")
        assert d1 == d2
