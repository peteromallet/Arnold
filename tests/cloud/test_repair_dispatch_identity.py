"""Focused tests for the canonical repair dispatch identity contract (T18).

These tests pin the exact occurrence-tuple contract introduced in Step 11:

* identity tuple exactness (all authority-bearing dimensions),
* normalized failure kind (fail / failed / error: detail),
* blocker vs phase-result digest precedence,
* source reread requirement before any mutating action,
* fence disagreement quarantine,
* stale attempt rejection and same-basename edge cases,
* non-authority of provenance fields.

The tests never assert that the contract grants repair/completion/cancellation
authority — it is a read-only binding layer.
"""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud import repair_revalidation


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


def _kwargs(**overrides):
    base = dict(
        environment_id="env-1",
        session_id="sess-1",
        chain_id="chain-1",
        plan_revision="rev-7",
        phase="execute",
        task_id="task-A",
        attempt_number=3,
        raw_failure_kind="failed: budget",
        blocker_digest="sha256:blocker-abc",
        phase_result_digest="",
        coordinator_fence_token="fence-xyz",
        source_reread_at="2026-07-21T10:00:00Z",
        source_digest="sha256:source-1",
    )
    base.update(overrides)
    return base


def _identity(**overrides):
    return repair_requests.derive_dispatch_identity_from_source_reread(
        **_kwargs(**overrides)
    )


# ──────────────────────────────────────────────────────────────────────
# 1. Identity tuple exactness
# ──────────────────────────────────────────────────────────────────────


class TestIdentityTupleExactness:
    def test_binds_every_authority_dimension(self):
        ident = _identity()
        assert ident.environment_id == "env-1"
        assert ident.session_id == "sess-1"
        assert ident.chain_id == "chain-1"
        assert ident.plan_revision == "rev-7"
        assert ident.phase == "execute"
        assert ident.task_id == "task-A"
        assert ident.attempt_number == 3
        assert ident.normalized_failure_kind == "failed:budget"
        assert ident.dispatch_digest_kind == "blocker"
        assert ident.dispatch_digest == "sha256:blocker-abc"
        assert ident.coordinator_fence_token == "fence-xyz"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("environment_id", "env-2"),
            ("session_id", "sess-2"),
            ("chain_id", "chain-2"),
            ("plan_revision", "rev-8"),
            ("phase", "verify"),
            ("task_id", "task-B"),
            ("attempt_number", 4),
            ("coordinator_fence_token", "fence-other"),
        ],
    )
    def test_each_dimension_changes_the_key(self, field, value):
        base = _identity()
        drift = _identity(**{field: value})
        assert repair_requests.repair_dispatch_identity_key(base) != (
            repair_requests.repair_dispatch_identity_key(drift)
        ), f"{field} drift must change the dispatch identity key"

    def test_normalized_failure_kind_drift_changes_key(self):
        base = _identity(raw_failure_kind="failed: budget")
        drift = _identity(raw_failure_kind="failed: timeout")
        assert repair_requests.repair_dispatch_identity_key(base) != (
            repair_requests.repair_dispatch_identity_key(drift)
        )

    def test_dispatch_digest_drift_changes_key(self):
        base = _identity(blocker_digest="sha256:blocker-abc")
        drift = _identity(blocker_digest="sha256:blocker-def")
        assert repair_requests.repair_dispatch_identity_key(base) != (
            repair_requests.repair_dispatch_identity_key(drift)
        )

    def test_provenance_does_not_change_key(self):
        # Same occurrence, reread at a later time with a different source
        # digest, must compare equal on the authority tuple.
        base = _identity(
            source_reread_at="2026-07-21T10:00:00Z",
            source_digest="sha256:source-1",
        )
        later = _identity(
            source_reread_at="2026-07-21T11:00:00Z",
            source_digest="sha256:source-2",
        )
        assert repair_requests.repair_dispatch_identity_key(base) == (
            repair_requests.repair_dispatch_identity_key(later)
        )

    def test_identity_is_frozen(self):
        ident = _identity()
        with pytest.raises(FrozenInstanceError):
            ident.attempt_number = 99  # type: ignore[misc]

    def test_as_dict_marks_authority_non_authoritative(self):
        ident = _identity()
        payload = ident.as_dict()
        assert payload["authority"] == "evidence_extracted_non_authoritative"
        assert payload["normalized_failure_kind"] == "failed:budget"
        assert "coordinator_fence_token" in payload


# ──────────────────────────────────────────────────────────────────────
# 2. Normalized failure kind
# ──────────────────────────────────────────────────────────────────────


class TestNormalizedFailureKind:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("fail", "fail"),
            ("Fail ", "fail"),
            ("failed", "failed"),
            ("failed: budget", "failed:budget"),
            ("Failed:Budget", "failed:Budget"),
            ("error", "error"),
            ("error: timeout", "error:timeout"),
            ("", ""),
        ],
    )
    def test_canonical_form(self, raw, expected):
        ident = _identity(raw_failure_kind=raw)
        assert ident is not None
        assert ident.normalized_failure_kind == expected
        assert ident.raw_failure_kind == raw

    def test_empty_failure_kind_still_mints_identity(self):
        # An empty failure kind normalizes to "" — the occurrence is still
        # bound via the digest + fence, so identity is allowed.
        ident = _identity(raw_failure_kind="")
        assert ident is not None
        assert ident.normalized_failure_kind == ""

    def test_fail_vs_failed_keys_differ(self):
        fail_id = _identity(raw_failure_kind="fail")
        failed_id = _identity(raw_failure_kind="failed")
        assert (
            repair_requests.repair_dispatch_identity_key(fail_id)
            != repair_requests.repair_dispatch_identity_key(failed_id)
        )


# ──────────────────────────────────────────────────────────────────────
# 3. Blocker vs phase-result digest
# ──────────────────────────────────────────────────────────────────────


class TestDispatchDigestPrecedence:
    def test_blocker_only(self):
        ident = _identity(blocker_digest="sha256:b1", phase_result_digest="")
        assert ident.dispatch_digest_kind == "blocker"
        assert ident.dispatch_digest == "sha256:b1"

    def test_phase_result_takes_precedence(self):
        ident = _identity(
            blocker_digest="sha256:b1", phase_result_digest="sha256:pr-1"
        )
        assert ident.dispatch_digest_kind == "phase_result"
        assert ident.dispatch_digest == "sha256:pr-1"

    def test_phase_result_only(self):
        ident = _identity(blocker_digest="", phase_result_digest="sha256:pr-1")
        assert ident.dispatch_digest_kind == "phase_result"

    def test_blocker_vs_phase_result_keys_differ(self):
        blocker_id = _identity(blocker_digest="sha256:same", phase_result_digest="")
        phase_id = _identity(blocker_digest="", phase_result_digest="sha256:same")
        # Even with the same digest string, the *kind* differs so the keys
        # must differ — this is the exact-tuple guarantee.
        assert (
            repair_requests.repair_dispatch_identity_key(blocker_id)
            != repair_requests.repair_dispatch_identity_key(phase_id)
        )

    def test_no_digest_refuses_identity(self):
        ident = _identity(blocker_digest="", phase_result_digest="")
        assert ident is None


# ──────────────────────────────────────────────────────────────────────
# 4. Source reread requirement
# ──────────────────────────────────────────────────────────────────────


class TestSourceRereadRequirement:
    @pytest.mark.parametrize(
        "action",
        [
            repair_requests.REPAIR_ACTION_REPAIR,
            repair_requests.REPAIR_ACTION_RETRY,
            repair_requests.REPAIR_ACTION_ESCALATION,
            repair_requests.REPAIR_ACTION_CANCELLATION,
            repair_requests.REPAIR_ACTION_ADOPTION,
        ],
    )
    def test_every_mutating_action_requires_fresh_reread(self, action):
        current = _identity()
        # No fresh reread supplied.
        verdict = repair_requests.require_source_reread_for_action(
            action, current_identity=current, fresh_identity=None
        )
        assert verdict.permitted is False
        assert "fresh source reread" in verdict.reason

    def test_unknown_action_kind_refused(self):
        current = _identity()
        fresh = _identity()
        verdict = repair_requests.require_source_reread_for_action(
            "promote", current_identity=current, fresh_identity=fresh
        )
        assert verdict.permitted is False
        assert "unknown repair action kind" in verdict.reason

    def test_missing_current_identity_refused(self):
        fresh = _identity()
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=None,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False
        assert "no current occurrence tuple" in verdict.reason

    def test_matching_fresh_reread_permitted(self):
        current = _identity()
        fresh = _identity()
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is True
        assert verdict.current_tuple_digest == verdict.fresh_tuple_digest
        assert verdict.current_tuple_digest != ""


# ──────────────────────────────────────────────────────────────────────
# 5. Fence disagreement quarantine
# ──────────────────────────────────────────────────────────────────────


class TestFenceDisagreement:
    def test_fence_drift_quarantines(self):
        current = _identity(coordinator_fence_token="fence-A")
        fresh = _identity(coordinator_fence_token="fence-B")
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_RETRY,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False
        assert "disagrees" in verdict.reason or "fence" in verdict.reason
        assert verdict.current_fence_token == "fence-A"
        assert verdict.fresh_fence_token == "fence-B"

    def test_attempt_drift_quarantines(self):
        current = _identity(attempt_number=3)
        fresh = _identity(attempt_number=4)
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_ESCALATION,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False
        assert "disagrees" in verdict.reason
        assert verdict.current_tuple_digest != verdict.fresh_tuple_digest

    def test_revision_drift_quarantines(self):
        current = _identity(plan_revision="rev-7")
        fresh = _identity(plan_revision="rev-9")
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_CANCELLATION,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False


# ──────────────────────────────────────────────────────────────────────
# 6. Stale reread rejection
# ──────────────────────────────────────────────────────────────────────


class TestStaleRereadRejection:
    def test_older_reread_quarantined(self):
        current = _identity(source_reread_at="2026-07-21T11:00:00Z")
        fresh = _identity(source_reread_at="2026-07-21T10:00:00Z")
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_ADOPTION,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False
        assert "stale" in verdict.reason

    def test_equal_or_later_reread_permitted(self):
        current = _identity(source_reread_at="2026-07-21T10:00:00Z")
        fresh_same = _identity(source_reread_at="2026-07-21T10:00:00Z")
        fresh_later = _identity(source_reread_at="2026-07-21T12:00:00Z")
        v1 = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=current,
            fresh_identity=fresh_same,
        )
        v2 = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=current,
            fresh_identity=fresh_later,
        )
        assert v1.permitted is True
        assert v2.permitted is True


# ──────────────────────────────────────────────────────────────────────
# 7. Same-basename edge cases — distinct occurrences must not collide
# ──────────────────────────────────────────────────────────────────────


class TestSameBasenameEdgeCases:
    def test_same_task_id_different_sessions_dont_collide(self):
        a = _identity(session_id="sess-1")
        b = _identity(session_id="sess-2")
        assert (
            repair_requests.repair_dispatch_identity_key(a)
            != repair_requests.repair_dispatch_identity_key(b)
        )

    def test_same_chain_different_environments_dont_collide(self):
        a = _identity(environment_id="env-1")
        b = _identity(environment_id="env-2")
        assert (
            repair_requests.repair_dispatch_identity_key(a)
            != repair_requests.repair_dispatch_identity_key(b)
        )

    def test_recycled_fence_token_with_other_drift_quarantines(self):
        # A fence token reused across a different attempt must not let a
        # stale dispatch slip through.
        current = _identity(attempt_number=3, coordinator_fence_token="fence-recycled")
        fresh = _identity(attempt_number=5, coordinator_fence_token="fence-recycled")
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=current,
            fresh_identity=fresh,
        )
        assert verdict.permitted is False


# ──────────────────────────────────────────────────────────────────────
# 8. derive_dispatch_identity_from_source_reread input validation
# ──────────────────────────────────────────────────────────────────────


class TestDeriveInputValidation:
    @pytest.mark.parametrize(
        "overrides,desc",
        [
            ({"environment_id": ""}, "missing environment"),
            ({"session_id": ""}, "missing session"),
            ({"chain_id": ""}, "missing chain"),
            ({"plan_revision": ""}, "missing revision"),
            ({"phase": ""}, "missing phase"),
            ({"coordinator_fence_token": ""}, "missing fence"),
            ({"source_reread_at": ""}, "missing reread timestamp"),
            ({"source_digest": ""}, "missing source digest"),
            ({"attempt_number": 0}, "zero attempt"),
            ({"attempt_number": -1}, "negative attempt"),
            ({"attempt_number": "not-an-int"}, "non-int attempt"),
            ({"blocker_digest": "", "phase_result_digest": ""}, "no digest anchor"),
        ],
    )
    def test_missing_required_fields_refuse_identity(self, overrides, desc):
        ident = _identity(**overrides)
        assert ident is None, f"expected None for {desc}"

    def test_non_int_attempt_string_accepts_when_numeric(self):
        ident = _identity(attempt_number="4")
        assert ident is not None
        assert ident.attempt_number == 4


# ──────────────────────────────────────────────────────────────────────
# 9. revalidate_dispatch_identity convenience wrapper
# ──────────────────────────────────────────────────────────────────────


class TestRevalidateDispatchIdentity:
    def test_permitted_path(self):
        current = _identity()
        fresh = _identity()
        permitted, reason, verdict = (
            repair_revalidation.revalidate_dispatch_identity(
                repair_requests.REPAIR_ACTION_REPAIR,
                current_identity=current,
                fresh_identity=fresh,
            )
        )
        assert permitted is True
        assert "matches" in reason
        assert verdict.permitted is True

    def test_quarantine_path(self):
        current = _identity()
        fresh = _identity(attempt_number=4)
        permitted, reason, verdict = (
            repair_revalidation.revalidate_dispatch_identity(
                repair_requests.REPAIR_ACTION_CANCELLATION,
                current_identity=current,
                fresh_identity=fresh,
            )
        )
        assert permitted is False
        assert "disagrees" in reason
        assert verdict.permitted is False


# ──────────────────────────────────────────────────────────────────────
# 10. repair_contract re-export surface
# ──────────────────────────────────────────────────────────────────────


class TestContractReexport:
    def test_all_symbols_reexported(self):
        for name in (
            "RepairDispatchIdentity",
            "SourceRereadVerdict",
            "derive_dispatch_identity_from_source_reread",
            "repair_dispatch_identity_key",
            "require_source_reread_for_action",
            "REPAIR_ACTION_REPAIR",
            "REPAIR_ACTION_RETRY",
            "REPAIR_ACTION_ESCALATION",
            "REPAIR_ACTION_CANCELLATION",
            "REPAIR_ACTION_ADOPTION",
            "REPAIR_ACTION_KINDS",
        ):
            assert hasattr(repair_contract, name), f"repair_contract missing {name}"

    def test_action_kinds_set_is_complete(self):
        assert repair_requests.REPAIR_ACTION_KINDS == frozenset(
            {
                "repair",
                "retry",
                "escalation",
                "cancellation",
                "adoption",
            }
        )


# ──────────────────────────────────────────────────────────────────────
# 11. Non-authority invariant
# ──────────────────────────────────────────────────────────────────────


class TestNonAuthority:
    def test_identity_dict_never_claims_authority(self):
        ident = _identity()
        payload = ident.as_dict()
        assert payload["authority"] == "evidence_extracted_non_authoritative"
        # No bearer-token / grant / lease fields leak into the payload.
        for forbidden in ("grant", "lease", "bearer", "authorization"):
            assert forbidden not in str(payload).lower(), (
                f"authority-like field leaked into dispatch identity: {forbidden}"
            )

    def test_verdict_does_not_grant_completion(self):
        current = _identity()
        fresh = _identity()
        verdict = repair_requests.require_source_reread_for_action(
            repair_requests.REPAIR_ACTION_REPAIR,
            current_identity=current,
            fresh_identity=fresh,
        )
        # The verdict is a binding/observability record, not a completion
        # grant.  It carries only fence + tuple digests.
        assert hasattr(verdict, "permitted")
        assert hasattr(verdict, "reason")
        assert not hasattr(verdict, "completed")
        assert not hasattr(verdict, "verified")


# ──────────────────────────────────────────────────────────────────────
# 12. Determinism — key stability across interpreter reloads
# ──────────────────────────────────────────────────────────────────────


class TestKeyDeterminism:
    def test_key_is_stable_string(self):
        ident = _identity()
        key = repair_requests.repair_dispatch_identity_key(ident)
        assert isinstance(key, str)
        assert len(key) == 64  # sha256 hex

    def test_key_independent_of_module_reload(self):
        ident = _identity()
        key_before = repair_requests.repair_dispatch_identity_key(ident)
        importlib.reload(repair_requests)
        # After reload the identity class is a different object, but the key
        # function still works on the original instance because it reads
        # attributes by name.
        key_after = repair_requests.repair_dispatch_identity_key(ident)
        assert key_before == key_after
