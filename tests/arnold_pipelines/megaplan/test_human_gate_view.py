"""Tests for HumanGateView – deterministic hashing, source hash/revision binding,
stale freshness-token diagnostics, superseded override evidence diagnostics,
and preservation of needs-human sidecars as observations only.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from arnold_pipelines.megaplan.authority import (
    HumanGateDiagnostic,
    HumanGateObservation,
    HumanGateView,
    derive_human_gate_view,
)
from arnold_pipelines.run_authority import canonical_json


# ---------------------------------------------------------------------------
# HumanGateObservation contract
# ---------------------------------------------------------------------------

class TestHumanGateObservationContract:
    """The observation type must enforce its own invariants."""

    def test_valid_gate_type_required(self) -> None:
        with pytest.raises(ValueError, match="unsupported gate_type"):
            HumanGateObservation(
                observation_id="obs-1",
                gate_type="bogus_type",
                gate_reason="test",
                source="test/source.json",
            )

    def test_empty_observation_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="observation_id"):
            HumanGateObservation(
                observation_id="",
                gate_type="needs_human",
                gate_reason="test",
                source="test/source.json",
            )

    def test_empty_gate_reason_rejected(self) -> None:
        with pytest.raises(ValueError, match="gate_reason"):
            HumanGateObservation(
                observation_id="obs-1",
                gate_type="needs_human",
                gate_reason="",
                source="test/source.json",
            )

    def test_empty_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="source"):
            HumanGateObservation(
                observation_id="obs-1",
                gate_type="needs_human",
                gate_reason="test",
                source="",
            )

    def test_all_valid_gate_types_accepted(self) -> None:
        valid_types = (
            "needs_human", "override", "user_action",
            "approval_checkpoint", "denial_checkpoint", "suspension",
        )
        for gate_type in valid_types:
            obs = HumanGateObservation(
                observation_id=f"obs-{gate_type}",
                gate_type=gate_type,
                gate_reason="test reason",
                source="test/source.json",
            )
            assert obs.gate_type == gate_type
            assert obs.stale_token is False
            assert obs.superseded is False

    def test_default_flags_are_false(self) -> None:
        obs = HumanGateObservation(
            observation_id="obs-defaults",
            gate_type="needs_human",
            gate_reason="reason",
            source="test/source.json",
        )
        assert obs.stale_token is False
        assert obs.superseded is False

    def test_to_dict_roundtrip_preserves_all_fields(self) -> None:
        obs = HumanGateObservation(
            observation_id="obs-rtt",
            gate_type="override",
            gate_reason="manual override by admin",
            source="admin/override.json",
            stale_token=True,
            superseded=True,
        )
        d = obs.to_dict()
        assert d["observation_id"] == "obs-rtt"
        assert d["gate_type"] == "override"
        assert d["gate_reason"] == "manual override by admin"
        assert d["source"] == "admin/override.json"
        assert d["stale_token"] is True
        assert d["superseded"] is True

    def test_ordering_is_stable(self) -> None:
        a = HumanGateObservation("a", "needs_human", "r1", "s1")
        b = HumanGateObservation("b", "override", "r2", "s2")
        c = HumanGateObservation("c", "needs_human", "r1", "s1")
        sorted_items = sorted([b, c, a])
        # order=True sorts by all fields in declaration order:
        # (observation_id, gate_type, gate_reason, source, stale_token, superseded)
        assert [item.observation_id for item in sorted_items] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# HumanGateDiagnostic contract
# ---------------------------------------------------------------------------

class TestHumanGateDiagnosticContract:
    """Diagnostics must be comparable and serializable."""

    def test_to_dict(self) -> None:
        diag = HumanGateDiagnostic(
            code="stale_token",
            reason="token references old revision",
            source="sidecar/needs_human.json",
        )
        d = diag.to_dict()
        assert d["code"] == "stale_token"
        assert d["reason"] == "token references old revision"
        assert d["source"] == "sidecar/needs_human.json"

    def test_ordering_is_stable(self) -> None:
        a = HumanGateDiagnostic("a", "ra", "sa")
        b = HumanGateDiagnostic("b", "rb", "sb")
        assert sorted([b, a]) == [a, b]


# ---------------------------------------------------------------------------
# HumanGateView contract
# ---------------------------------------------------------------------------

class TestHumanGateViewContract:
    """The view must enforce its status invariant."""

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported HumanGateView status"):
            HumanGateView(
                schema_version=1,
                status="bogus",
                human_required=False,
                typed_gate=None,
                observations=(),
                source_paths=(),
                diagnostics=(),
                view_hash="hash",
            )

    def test_valid_statuses_accepted(self) -> None:
        for status in ("blocked", "attention_needed", "resolved", "unknown"):
            view = HumanGateView(
                schema_version=1,
                status=status,
                human_required=False,
                typed_gate=None,
                observations=(),
                source_paths=(),
                diagnostics=(),
                view_hash="hash",
            )
            assert view.status == status

    def test_shadow_and_read_only_flags_in_payload(self) -> None:
        view = HumanGateView(
            schema_version=1,
            status="unknown",
            human_required=False,
            typed_gate=None,
            observations=(),
            source_paths=(),
            diagnostics=(),
            view_hash="hash",
        )
        payload = view._payload()
        assert payload["shadow"] is True
        assert payload["read_only"] is True

    def test_to_dict_includes_view_hash(self) -> None:
        view = HumanGateView(
            schema_version=1,
            status="unknown",
            human_required=False,
            typed_gate=None,
            observations=(),
            source_paths=(),
            diagnostics=(),
            view_hash="abc123",
        )
        d = view.to_dict()
        assert d["view_hash"] == "abc123"

    def test_to_json_produces_valid_json(self) -> None:
        view = HumanGateView(
            schema_version=1,
            status="unknown",
            human_required=False,
            typed_gate=None,
            observations=(),
            source_paths=(),
            diagnostics=(),
            view_hash="abc123",
        )
        raw = view.to_json()
        parsed = json.loads(raw)
        assert parsed["view_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Deterministic hashing
# ---------------------------------------------------------------------------

class TestDeterministicHashing:
    """The same inputs in any order MUST produce identical view hashes."""

    def test_same_signals_same_hash_regardless_of_order(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "manual review required",
             "source": "sidecar/needs_human.json"},
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json"},
        ]
        first = derive_human_gate_view(signals)
        second = derive_human_gate_view(list(reversed(signals)))
        assert first == second
        assert first.view_hash == second.view_hash
        assert first.to_json() == second.to_json()
        assert len(first.view_hash) == 64  # SHA-256 hex digest

    def test_empty_signals_produce_deterministic_hash(self) -> None:
        first = derive_human_gate_view([])
        second = derive_human_gate_view([])
        assert first == second
        assert first.view_hash == second.view_hash

    def test_hash_changes_when_signals_change(self) -> None:
        signals_a = [
            {"gate_type": "needs_human", "gate_reason": "reason A",
             "source": "sidecar/a.json"},
        ]
        signals_b = [
            {"gate_type": "needs_human", "gate_reason": "reason B",
             "source": "sidecar/b.json"},
        ]
        view_a = derive_human_gate_view(signals_a)
        view_b = derive_human_gate_view(signals_b)
        assert view_a.view_hash != view_b.view_hash

    def test_hash_changes_with_revision_binding(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-7"},
        ]
        view_old = derive_human_gate_view(signals, current_plan_revision="rev-1")
        view_match = derive_human_gate_view(signals, current_plan_revision="rev-7")
        assert view_old.view_hash != view_match.view_hash
        # Both are deterministic within their revision context.
        assert derive_human_gate_view(signals, current_plan_revision="rev-1").view_hash == view_old.view_hash

    def test_duplicate_signals_deduplicated(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert len(view.observations) == 1


# ---------------------------------------------------------------------------
# Source view hash / revision binding
# ---------------------------------------------------------------------------

class TestSourceViewHashRevisionBinding:
    """The revision context binds the view hash; stale-plan signals are flagged."""

    def test_plan_ref_mismatch_flags_stale_token(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-2"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-1")
        assert view.observations[0].stale_token is True
        assert any(d.code == "stale_token" for d in view.diagnostics)

    def test_plan_ref_match_does_not_flag_stale_token(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-7"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-7")
        assert view.observations[0].stale_token is False
        assert not any(d.code == "stale_token" for d in view.diagnostics)

    def test_no_current_revision_no_stale_detection(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-99"},
        ]
        view = derive_human_gate_view(signals)
        # Without current_plan_revision, no stale detection occurs.
        assert view.observations[0].stale_token is False
        assert not any(d.code == "stale_token" for d in view.diagnostics)

    def test_explicit_stale_flag_always_honoured(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "stale_token": True},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-1")
        assert view.observations[0].stale_token is True
        assert any(d.code == "stale_token" for d in view.diagnostics)

    def test_explicit_stale_flag_without_revision_binding(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "stale": True},
        ]
        view = derive_human_gate_view(signals)
        assert view.observations[0].stale_token is True

    def test_plan_revision_alias_detection(self) -> None:
        """plan_ref, plan_revision, and target_ref aliases all work."""
        for alias in ("plan_ref", "plan_revision", "target_ref"):
            signals = [
                {"gate_type": "needs_human", "gate_reason": "review",
                 "source": "sidecar/needs_human.json", alias: "rev-old"},
            ]
            view = derive_human_gate_view(signals, current_plan_revision="rev-new")
            assert view.observations[0].stale_token is True, f"alias {alias} not detected"

    def test_multiple_signals_some_stale_some_fresh(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review v1",
             "source": "sidecar/a.json", "plan_ref": "rev-1"},
            {"gate_type": "needs_human", "gate_reason": "review v2",
             "source": "sidecar/b.json", "plan_ref": "rev-2"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-2")
        stale = [o for o in view.observations if o.stale_token]
        fresh = [o for o in view.observations if not o.stale_token]
        assert len(stale) == 1
        assert stale[0].gate_reason == "review v1"
        assert len(fresh) == 1
        assert fresh[0].gate_reason == "review v2"


# ---------------------------------------------------------------------------
# Stale freshness-token diagnostics
# ---------------------------------------------------------------------------

class TestStaleTokenDiagnostics:
    """Diagnostics must be raised for every stale token and for all-stale scenarios."""

    def test_stale_token_diagnostic_includes_observation_id(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-old"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        stale_diags = [d for d in view.diagnostics if d.code == "stale_token"]
        assert len(stale_diags) == 1
        assert view.observations[0].observation_id in stale_diags[0].reason

    def test_all_needs_human_stale_produces_stale_needs_human_diagnostic(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review 1",
             "source": "sidecar/a.json", "plan_ref": "rev-old"},
            {"gate_type": "needs_human", "gate_reason": "review 2",
             "source": "sidecar/b.json", "plan_ref": "rev-old"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        diag = next((d for d in view.diagnostics if d.code == "stale_needs_human"), None)
        assert diag is not None
        assert "no live human gate detected" in diag.reason
        assert "sidecar/a.json" in diag.source or "sidecar/b.json" in diag.source

    def test_view_status_is_attention_needed_when_all_stale(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-old"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        # Not blocked because the stale signal is not a live blocker.
        assert view.status == "attention_needed"
        assert view.human_required is False

    def test_stale_token_on_override_diagnostic(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "old override",
             "source": "admin/override.json", "plan_ref": "rev-old"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        stale_diags = [d for d in view.diagnostics if d.code == "stale_token"]
        assert len(stale_diags) == 1
        assert "override" in stale_diags[0].reason.lower()


# ---------------------------------------------------------------------------
# Superseded override evidence diagnostics
# ---------------------------------------------------------------------------

class TestSupersededOverrideDiagnostics:
    """Override observations flagged as superseded must produce diagnostics."""

    def test_superseded_flag_produces_diagnostic(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "old override",
             "source": "admin/override.json", "superseded": True},
        ]
        view = derive_human_gate_view(signals)
        assert view.observations[0].superseded is True
        diag = next((d for d in view.diagnostics if d.code == "superseded_override"), None)
        assert diag is not None
        assert "superseded" in diag.reason.lower()

    def test_superseded_override_alias_detection(self) -> None:
        """Both 'superseded' and 'superseded_override' flags are detected."""
        for alias in ("superseded", "superseded_override"):
            signals = [
                {"gate_type": "override", "gate_reason": "old override",
                 "source": "admin/override.json", alias: True},
            ]
            view = derive_human_gate_view(signals)
            assert view.observations[0].superseded is True, f"alias {alias} not detected"

    def test_all_overrides_superseded_produces_stale_or_superseded_diagnostic(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "old override 1",
             "source": "admin/o1.json", "superseded": True},
            {"gate_type": "override", "gate_reason": "old override 2",
             "source": "admin/o2.json", "superseded": True},
        ]
        view = derive_human_gate_view(signals)
        diag = next((d for d in view.diagnostics if d.code == "stale_or_superseded_override"), None)
        assert diag is not None
        assert "no active override is in effect" in diag.reason

    def test_stale_and_superseded_override_produces_two_diagnostic_types(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "old override",
             "source": "admin/override.json",
             "plan_ref": "rev-old", "superseded": True},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        diag_codes = {d.code for d in view.diagnostics}
        assert "stale_token" in diag_codes
        assert "superseded_override" in diag_codes

    def test_live_override_not_superseded_no_superseded_diagnostic(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json"},
        ]
        view = derive_human_gate_view(signals)
        assert not any(d.code == "superseded_override" for d in view.diagnostics)
        assert view.status == "resolved"


# ---------------------------------------------------------------------------
# Preservation of needs-human sidecars as observations only
# ---------------------------------------------------------------------------

class TestNeedsHumanSidecarObservationsOnly:
    """Raw marker files/sidecars must be observations, never gate authority."""

    def test_needs_human_observed_not_authority(self) -> None:
        """A needs_human signal is projected as an observation with shadow/read_only
        flags — it does NOT constitute gate authority on its own."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "manual review required",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        d = view.to_dict()
        assert d["shadow"] is True
        assert d["read_only"] is True
        assert "authority" not in d

    def test_raw_type_alias_normalized_to_observation(self) -> None:
        """Signals with 'type' or 'kind' keys instead of 'gate_type' are normalized."""
        for key in ("type", "kind"):
            signals = [
                {key: "needs_human", "gate_reason": "review",
                 "source": "sidecar/needs_human.json"},
            ]
            view = derive_human_gate_view(signals)
            assert len(view.observations) == 1
            assert view.observations[0].gate_type == "needs_human"

    def test_unknown_gate_type_normalized_to_needs_human(self) -> None:
        signals = [
            {"gate_type": "weird_unknown_type", "gate_reason": "review",
             "source": "sidecar/weird.json"},
        ]
        view = derive_human_gate_view(signals)
        assert len(view.observations) == 1
        # unknown type is normalised to "needs_human" inside the normalizer
        assert view.observations[0].gate_type == "needs_human"

    def test_non_mapping_signals_skipped(self) -> None:
        """Non-dict items in the iterable are silently skipped."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
            "not_a_dict",
            42,
            None,
        ]
        view = derive_human_gate_view(signals)
        assert len(view.observations) == 1

    def test_observation_id_computed_deterministically_when_missing(self) -> None:
        """When no observation_id is provided, one is derived from the content hash."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        obs = view.observations[0]
        assert len(obs.observation_id) == 64  # SHA-256 hex digest
        # Same input, same derived id.
        view2 = derive_human_gate_view(signals)
        assert view2.observations[0].observation_id == obs.observation_id

    def test_explicit_observation_id_preserved(self) -> None:
        signals = [
            {"observation_id": "explicit-id-42", "gate_type": "needs_human",
             "gate_reason": "review", "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.observations[0].observation_id == "explicit-id-42"

    def test_various_reason_aliases_accepted(self) -> None:
        for alias in ("gate_reason", "reason", "rationale"):
            signals = [
                {"gate_type": "needs_human", alias: "review required",
                 "source": "sidecar/needs_human.json"},
            ]
            view = derive_human_gate_view(signals)
            assert view.observations[0].gate_reason == "review required", f"alias {alias} not read"

    def test_missing_reason_defaults_to_unspecified(self) -> None:
        signals = [
            {"gate_type": "needs_human", "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.observations[0].gate_reason == "unspecified"

    def test_missing_source_defaults_to_observation_scheme(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review"},
        ]
        view = derive_human_gate_view(signals)
        assert view.observations[0].source.startswith("observation://")

    def test_source_paths_aggregated_from_observations(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
            {"gate_type": "override", "gate_reason": "override",
             "source": "admin/override.json"},
        ]
        view = derive_human_gate_view(signals)
        assert set(view.source_paths) == {"sidecar/needs_human.json", "admin/override.json"}

    def test_gate_observation_is_not_execution_authority(self) -> None:
        """Even a blocking status is a projection, not a gate directive."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "blocking review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "blocked"
        assert view.human_required is True
        # It is still a shadow/read-only projection.
        assert view.to_dict()["shadow"] is True
        assert view.to_dict()["read_only"] is True


# ---------------------------------------------------------------------------
# Status determination (blocked / resolved / attention_needed / unknown)
# ---------------------------------------------------------------------------

class TestHumanGateStatusDetermination:
    """Status semantics: blocked when live needs-human or user_action;
    resolved when explicit checkpoint or live override without blocker;
    attention_needed for ambiguous signals; unknown when empty."""

    def test_empty_signals_yields_unknown(self) -> None:
        view = derive_human_gate_view([])
        assert view.status == "unknown"
        assert view.human_required is False
        assert view.typed_gate is None

    def test_live_needs_human_yields_blocked(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "blocked"
        assert view.human_required is True
        assert view.typed_gate is not None

    def test_user_action_yields_blocked(self) -> None:
        signals = [
            {"gate_type": "user_action", "gate_reason": "manual step",
             "source": "plan/user_action.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "blocked"
        assert view.human_required is True

    def test_approval_checkpoint_without_blocker_yields_resolved(self) -> None:
        signals = [
            {"gate_type": "approval_checkpoint", "gate_reason": "approved",
             "source": "review/approval.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "resolved"
        assert view.human_required is False

    def test_denial_checkpoint_without_blocker_yields_resolved(self) -> None:
        signals = [
            {"gate_type": "denial_checkpoint", "gate_reason": "denied",
             "source": "review/denial.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "resolved"

    def test_live_override_without_blocker_yields_resolved(self) -> None:
        signals = [
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "resolved"

    def test_needs_human_trumps_override(self) -> None:
        """A live needs-human blocks even when an override is present."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "must review",
             "source": "sidecar/needs_human.json"},
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "blocked"
        assert view.human_required is True

    def test_suspension_without_blocker_yields_attention_needed(self) -> None:
        signals = [
            {"gate_type": "suspension", "gate_reason": "paused",
             "source": "plan/suspension.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.status == "attention_needed"
        assert view.human_required is False

    def test_typed_gate_is_none_when_not_blocked(self) -> None:
        view = derive_human_gate_view([])
        assert view.typed_gate is None

    def test_typed_gate_populated_from_live_needs_human(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "security review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        assert view.typed_gate == "security review"


# ---------------------------------------------------------------------------
# Integration: cross-cutting determinism and revision binding
# ---------------------------------------------------------------------------

class TestCrossCuttingDeterminism:
    """When stale tokens, superseded overrides, and revision context interact,
    the view must remain deterministic and all diagnostics must be present."""

    def test_full_scenario_determinism(self) -> None:
        """Complex mix of signals — deterministic across reorderings."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-2"},
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json", "superseded": True},
            {"gate_type": "approval_checkpoint", "gate_reason": "approved",
             "source": "review/approval.json"},
            {"gate_type": "user_action", "gate_reason": "manual step",
             "source": "plan/user_action.json"},
        ]
        view1 = derive_human_gate_view(signals, current_plan_revision="rev-1")
        view2 = derive_human_gate_view(list(reversed(signals)), current_plan_revision="rev-1")
        assert view1 == view2
        assert view1.view_hash == view2.view_hash

    def test_full_scenario_all_diagnostics_present(self) -> None:
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-2"},
            {"gate_type": "override", "gate_reason": "admin override",
             "source": "admin/override.json", "superseded": True},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-1")
        diag_codes = {d.code for d in view.diagnostics}
        assert "stale_token" in diag_codes, "missing stale-token diagnostic"
        assert "superseded_override" in diag_codes, "missing superseded-override diagnostic"
        assert "stale_or_superseded_override" in diag_codes, "missing aggregate override diagnostic"

    def test_full_scenario_status(self) -> None:
        """needs_human is stale → not live; no live needs-human or user_action → resolved
        (approval_checkpoint + override, though the override is superseded)."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-2"},
            {"gate_type": "approval_checkpoint", "gate_reason": "approved",
             "source": "review/approval.json"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-1")
        assert view.status == "resolved"
        assert view.human_required is False

    def test_view_does_not_import_or_mutate_runner_publication(self) -> None:
        """HumanGateView's dictionary must not contain runner or publication fields."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json"},
        ]
        view = derive_human_gate_view(signals)
        d = view.to_dict()
        forbidden = {"runner_status", "publication_status", "execution_status",
                     "accepted_task_ids", "next_ready_wave"}
        assert forbidden.isdisjoint(d.keys()), f"view leaked forbidden keys: {forbidden & d.keys()}"

    def test_diagnostics_are_deduplicated(self) -> None:
        """Identical diagnostics from different observation paths are deduplicated."""
        signals = [
            {"gate_type": "needs_human", "gate_reason": "review",
             "source": "sidecar/needs_human.json", "plan_ref": "rev-old"},
        ]
        view = derive_human_gate_view(signals, current_plan_revision="rev-new")
        # We may also get a `stale_needs_human` diag; but `stale_token` should appear only once.
        stale_token_diags = [d for d in view.diagnostics if d.code == "stale_token"]
        assert len(stale_token_diags) == 1
