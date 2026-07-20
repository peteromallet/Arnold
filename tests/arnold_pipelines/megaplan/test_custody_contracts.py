"""Comprehensive custody contract tests for M7 controlled authoritative writers.

Covers canonical round trips, malformed-input rejection, and proof that the
F01 tuple cannot omit or reinterpret chain/session identity, failure
signature, grant/fence refs, WBC attempt ref, lease identity, or monotonic
custody epoch.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from arnold_pipelines.megaplan.custody.contracts import (
    CUSTODY_LEASE_EVENT_TYPES,
    CustodyLease,
    CustodyLeaseEvent,
    CustodyTargetKey,
    RepairOccurrenceKey,
    build_custody_target_key,
    build_repair_occurrence_key,
    normalize_custody_lease,
    normalize_custody_lease_event,
    normalize_custody_target_key,
    normalize_repair_occurrence_key,
    occurrence_digest,
    target_digest,
)
from arnold_pipelines.run_authority.contracts import (
    ContractError,
    IdentityConflict,
    PayloadConflict,
)

# ── Shared fixtures ────────────────────────────────────────────────────────


def _base_f01() -> dict[str, str]:
    """Return a valid F01 tuple dict."""
    return {
        "environment": "prod",
        "session": "sess-001",
        "chain": "chain-alpha",
        "plan_revision": "rev-42",
        "phase": "execute",
        "task": "task-7",
        "attempt": "a3",
        "normalized_failure_kind": "timeout",
        "blocker_or_phase_result_hash": "abc123def",
        "fence": "fence-9",
    }


def _make_target(**overrides: str) -> CustodyTargetKey:
    kwargs = dict(_base_f01(), chain_identity="chain-id-01")
    kwargs.update(overrides)
    return CustodyTargetKey(**kwargs)


def _make_occurrence_key(target: CustodyTargetKey | None = None, **overrides) -> RepairOccurrenceKey:
    t = target if target is not None else _make_target()
    kwargs = dict(
        target=t,
        run_id="run-001",
        run_revision="rev-100",
        coordinator_attempt_id="coord-500",
        fence_token=42,
        wbc_attempt_reference="wbc-att-77",
    )
    kwargs.update(overrides)
    return RepairOccurrenceKey(**kwargs)


def _make_lease(**overrides) -> CustodyLease:
    occ = _make_occurrence_key()
    kwargs = dict(
        lease_id="lease-001",
        occurrence_key=occ,
        owner_host="host-1",
        owner_pid="12345",
        owner_boot_id="boot-abc",
        run_authority_grant_id="grant-99",
        coordinator_fence_token=42,
        wbc_attempt_reference="wbc-att-77",
        custody_epoch=1,
        acquired_at="2025-01-01T00:00:00Z",
        expires_at="2025-01-02T00:00:00Z",
        idempotency_key="idem-lease-001",
        causal_predecessor="",
    )
    kwargs.update(overrides)
    return CustodyLease(**kwargs)


def _make_event(**overrides) -> CustodyLeaseEvent:
    kwargs = dict(
        event_id="evt-001",
        lease_id="lease-001",
        sequence=1,
        event_type="acquire",
        occurred_at="2025-01-01T00:00:00Z",
        custody_epoch=1,
        owner_host="host-1",
        owner_pid="12345",
        owner_boot_id="boot-abc",
        run_authority_grant_id="grant-99",
        coordinator_fence_token=42,
        wbc_attempt_reference="wbc-att-77",
        occurrence_digest="sha256:aaaa",
        idempotency_key="idem-evt-001",
        causal_predecessor="",
        payload={"note": "test"},
    )
    kwargs.update(overrides)
    return CustodyLeaseEvent(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyTargetKey — round trips and identity
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyTargetKeyRoundTrip:
    """Canonical round trips for CustodyTargetKey."""

    def test_full_round_trip_via_dict_and_json(self) -> None:
        target = _make_target()
        d = target.to_dict()
        assert d["contract_type"] == "custody_target_key"
        assert d["schema_version"] == 1
        assert d["environment"] == "prod"
        assert d["chain_identity"] == "chain-id-01"

        # JSON round trip
        encoded = target.to_json()
        decoded = CustodyTargetKey.from_json(encoded)
        assert decoded == target
        assert decoded.target_digest == target.target_digest

        # Dict round trip
        from_dict = CustodyTargetKey.from_dict(d)
        assert from_dict == target

    def test_deterministic_json(self) -> None:
        a = _make_target()
        b = _make_target()
        assert a.to_json() == b.to_json()
        assert a.target_digest == b.target_digest

    def test_f01_tuple_representation(self) -> None:
        target = _make_target()
        tup = target.to_tuple()
        assert len(tup) == 10
        assert tup == (
            "prod", "sess-001", "chain-alpha", "rev-42", "execute",
            "task-7", "a3", "timeout", "abc123def", "fence-9",
        )

    def test_target_digest_is_deterministic(self) -> None:
        a = _make_target()
        b = _make_target(chain_identity="chain-id-01")  # same identity
        assert a.target_digest == b.target_digest

        # Different chain identity => different digest
        c = _make_target(chain_identity="different-id")
        assert c.target_digest != a.target_digest

    def test_deep_immutability(self) -> None:
        target = _make_target()
        with pytest.raises(FrozenInstanceError):
            target.environment = "dev"  # type: ignore[misc]

    def test_chain_identity_can_be_empty(self) -> None:
        target = _make_target(chain_identity="")
        assert target.chain_identity == ""
        assert target.to_dict()["chain_identity"] == ""

    def test_normalize_custody_target_key(self) -> None:
        payload = dict(_base_f01(), chain_identity="cid-1")
        target = normalize_custody_target_key(payload)
        assert target is not None
        assert target.environment == "prod"
        assert target.chain_identity == "cid-1"

    def test_build_custody_target_key_success(self) -> None:
        target = build_custody_target_key(**_base_f01(), chain_identity="cid-2")
        assert target is not None
        assert target.chain_identity == "cid-2"

    def test_build_custody_target_key_returns_none_on_empty_fields(self) -> None:
        bad = dict(_base_f01())
        del bad["environment"]
        target = build_custody_target_key(**bad)
        assert target is None


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyTargetKey — malformed inputs: each F01 tuple member
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyTargetKeyMalformedF01:
    """Prove the F01 tuple cannot omit any member."""

    F01_FIELDS = (
        "environment",
        "session",
        "chain",
        "plan_revision",
        "phase",
        "task",
        "attempt",
        "normalized_failure_kind",
        "blocker_or_phase_result_hash",
        "fence",
    )

    def test_each_f01_field_required_non_empty(self) -> None:
        """Each F01 field rejects empty strings."""
        for field_name in self.F01_FIELDS:
            kwargs = dict(_base_f01(), chain_identity="cid")
            kwargs[field_name] = ""
            with pytest.raises(ContractError, match=field_name):
                CustodyTargetKey(**kwargs)

    def test_each_f01_field_missing_rejected(self) -> None:
        """Omitting any F01 field raises TypeError (missing required arg)."""
        for field_name in self.F01_FIELDS:
            kwargs = dict(_base_f01(), chain_identity="cid")
            del kwargs[field_name]
            with pytest.raises(TypeError):
                CustodyTargetKey(**kwargs)

    def test_empty_string_environment_rejected(self) -> None:
        with pytest.raises(ContractError, match="environment"):
            _make_target(environment="")

    def test_empty_string_session_rejected(self) -> None:
        with pytest.raises(ContractError, match="session"):
            _make_target(session="")

    def test_empty_string_chain_rejected(self) -> None:
        with pytest.raises(ContractError, match="chain"):
            _make_target(chain="")

    def test_empty_string_normalized_failure_kind_rejected(self) -> None:
        with pytest.raises(ContractError, match="normalized_failure_kind"):
            _make_target(normalized_failure_kind="")

    def test_empty_string_blocker_hash_rejected(self) -> None:
        with pytest.raises(ContractError, match="blocker_or_phase_result_hash"):
            _make_target(blocker_or_phase_result_hash="")

    def test_empty_string_fence_rejected(self) -> None:
        with pytest.raises(ContractError, match="fence"):
            _make_target(fence="")

    def test_chain_identity_must_be_string(self) -> None:
        with pytest.raises(ContractError, match="chain_identity"):
            _make_target(chain_identity=42)  # type: ignore[arg-type]

    def test_whitespace_only_f01_field_rejected(self) -> None:
        """Whitespace-only strings are rejected for required F01 fields."""
        for field_name in self.F01_FIELDS:
            kwargs = dict(_base_f01(), chain_identity="cid")
            kwargs[field_name] = "   "
            with pytest.raises(ContractError, match=field_name):
                CustodyTargetKey(**kwargs)

    def test_normalize_returns_none_for_invalid_payload(self) -> None:
        assert normalize_custody_target_key(None) is None
        assert normalize_custody_target_key(42) is None  # type: ignore[arg-type]
        assert normalize_custody_target_key([]) is None  # type: ignore[arg-type]
        # Missing required field => None
        bad = dict(_base_f01())
        bad["environment"] = ""
        assert normalize_custody_target_key(bad) is None

    def test_cannot_reinterpret_environment(self) -> None:
        """F01 environment cannot be silently reinterpreted."""
        t1 = _make_target(environment="prod")
        t2 = _make_target(environment="staging")
        assert t1.environment != t2.environment
        assert t1.target_digest != t2.target_digest
        assert t1 != t2

    def test_cannot_reinterpret_session(self) -> None:
        t1 = _make_target(session="sess-001")
        t2 = _make_target(session="sess-002")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest

    def test_cannot_reinterpret_chain(self) -> None:
        t1 = _make_target(chain="chain-alpha")
        t2 = _make_target(chain="chain-beta")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest

    def test_cannot_reinterpret_chain_identity(self) -> None:
        t1 = _make_target(chain_identity="cid-a")
        t2 = _make_target(chain_identity="cid-b")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest

    def test_cannot_reinterpret_normalized_failure_kind(self) -> None:
        t1 = _make_target(normalized_failure_kind="timeout")
        t2 = _make_target(normalized_failure_kind="crash")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest

    def test_cannot_reinterpret_blocker_hash(self) -> None:
        t1 = _make_target(blocker_or_phase_result_hash="abc")
        t2 = _make_target(blocker_or_phase_result_hash="def")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest

    def test_cannot_reinterpret_fence(self) -> None:
        t1 = _make_target(fence="fence-9")
        t2 = _make_target(fence="fence-99")
        assert t1 != t2
        assert t1.target_digest != t2.target_digest


# ═══════════════════════════════════════════════════════════════════════════════
# RepairOccurrenceKey — round trips, digest, and malformed inputs
# ═══════════════════════════════════════════════════════════════════════════════


class TestRepairOccurrenceKeyRoundTrip:
    """Canonical round trips for RepairOccurrenceKey."""

    def test_full_round_trip(self) -> None:
        ok = _make_occurrence_key()
        d = ok.to_dict()
        assert d["contract_type"] == "repair_occurrence_key"
        assert d["run_id"] == "run-001"
        assert d["fence_token"] == 42
        assert d["occurrence_digest"].startswith("sha256:")

        # JSON serialization is deterministic and round-trips via normalize
        encoded = ok.to_json()
        parsed = json.loads(encoded)
        assert parsed["contract_type"] == "repair_occurrence_key"
        # Rebuild via normalize (the canonical factory for nested contracts)
        rebuilt = normalize_repair_occurrence_key(parsed)
        assert rebuilt is not None
        assert rebuilt.run_id == ok.run_id
        assert rebuilt.occurrence_digest == ok.occurrence_digest
        assert rebuilt.to_json() == encoded

    def test_occurrence_digest_is_deterministic(self) -> None:
        a = _make_occurrence_key()
        b = _make_occurrence_key()
        assert a.occurrence_digest == b.occurrence_digest

        # Different fence token => different digest
        c = _make_occurrence_key(fence_token=99)
        assert c.occurrence_digest != a.occurrence_digest

        # Different chain_identity in target => different digest
        target2 = _make_target(chain_identity="other-cid")
        d = _make_occurrence_key(target=target2)
        assert d.occurrence_digest != a.occurrence_digest

    def test_occurrence_digest_embedding_in_target(self) -> None:
        """Changing one F01 field changes the occurrence digest."""
        a = _make_occurrence_key()
        target2 = _make_target(environment="staging")
        b = _make_occurrence_key(target=target2)
        assert b.occurrence_digest != a.occurrence_digest

    def test_to_dict_includes_all_fields(self) -> None:
        ok = _make_occurrence_key()
        d = ok.to_dict()
        required_keys = {
            "contract_type", "schema_version", "target", "run_id",
            "run_revision", "coordinator_attempt_id", "fence_token",
            "wbc_attempt_reference", "occurrence_digest",
        }
        assert required_keys <= set(d)

    def test_wbc_attempt_reference_can_be_empty(self) -> None:
        ok = _make_occurrence_key(wbc_attempt_reference="")
        assert ok.wbc_attempt_reference == ""
        assert ok.to_dict()["wbc_attempt_reference"] == ""

    def test_deep_immutability(self) -> None:
        ok = _make_occurrence_key()
        with pytest.raises(FrozenInstanceError):
            ok.run_id = "changed"  # type: ignore[misc]
        # target is also frozen
        with pytest.raises(FrozenInstanceError):
            ok.target.environment = "changed"  # type: ignore[misc]

    def test_normalize_repair_occurrence_key(self) -> None:
        target_dict = dict(_base_f01(), chain_identity="cid-1")
        payload = {
            "target": target_dict,
            "run_id": "r1",
            "run_revision": "rv1",
            "coordinator_attempt_id": "c1",
            "fence_token": 7,
            "wbc_attempt_reference": "wbc-1",
        }
        ok = normalize_repair_occurrence_key(payload)
        assert ok is not None
        assert ok.run_id == "r1"
        assert ok.fence_token == 7

    def test_build_repair_occurrence_key(self) -> None:
        target = _make_target()
        ok = build_repair_occurrence_key(
            target=target,
            run_id="r1",
            run_revision="rv1",
            coordinator_attempt_id="c1",
            fence_token=10,
            wbc_attempt_reference="wbc-x",
        )
        assert ok is not None
        assert ok.run_id == "r1"
        assert ok.fence_token == 10


class TestRepairOccurrenceKeyMalformed:
    """Prove RepairOccurrenceKey rejects malformed inputs."""

    def test_missing_run_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="run_id"):
            _make_occurrence_key(run_id="")

    def test_missing_run_revision_rejected(self) -> None:
        with pytest.raises(ContractError, match="run_revision"):
            _make_occurrence_key(run_revision="")

    def test_missing_coordinator_attempt_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="coordinator_attempt_id"):
            _make_occurrence_key(coordinator_attempt_id="")

    def test_negative_fence_token_rejected(self) -> None:
        with pytest.raises(ContractError, match="fence_token"):
            _make_occurrence_key(fence_token=-1)

    def test_non_integer_fence_token_rejected(self) -> None:
        with pytest.raises(ContractError, match="fence_token"):
            _make_occurrence_key(fence_token="42")  # type: ignore[arg-type]

    def test_wbc_attempt_reference_must_be_string(self) -> None:
        with pytest.raises(ContractError, match="wbc_attempt_reference"):
            _make_occurrence_key(wbc_attempt_reference=99)  # type: ignore[arg-type]

    def test_normalize_returns_none_on_invalid(self) -> None:
        assert normalize_repair_occurrence_key(None) is None
        assert normalize_repair_occurrence_key(42) is None  # type: ignore[arg-type]
        # Invalid target
        assert normalize_repair_occurrence_key({"target": {"environment": ""}}) is None

    def test_cannot_reinterpret_run_identity(self) -> None:
        a = _make_occurrence_key(run_id="run-a")
        b = _make_occurrence_key(run_id="run-b")
        assert a != b
        # run_id is identity-affecting but not in the occurrence digest
        assert a.to_dict()["run_id"] != b.to_dict()["run_id"]

    def test_cannot_reinterpret_coordinator_attempt(self) -> None:
        a = _make_occurrence_key(coordinator_attempt_id="coord-a")
        b = _make_occurrence_key(coordinator_attempt_id="coord-b")
        assert a != b
        # coordinator_attempt_id is identity-affecting but not in the occurrence digest
        assert a.to_dict()["coordinator_attempt_id"] != b.to_dict()["coordinator_attempt_id"]

    def test_cannot_reinterpret_fence_token(self) -> None:
        a = _make_occurrence_key(fence_token=1)
        b = _make_occurrence_key(fence_token=2)
        assert a != b
        assert a.occurrence_digest != b.occurrence_digest

    def test_cannot_reinterpret_wbc_attempt_reference(self) -> None:
        a = _make_occurrence_key(wbc_attempt_reference="wbc-a")
        b = _make_occurrence_key(wbc_attempt_reference="wbc-b")
        assert a != b
        # WBC ref is not in the occurrence digest, but it is in identity
        assert a.to_dict() != b.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyLease — round trips and identity
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyLeaseRoundTrip:
    """Canonical round trips for CustodyLease."""

    def test_full_round_trip(self) -> None:
        lease = _make_lease()
        d = lease.to_dict()
        assert d["contract_type"] == "custody_lease"
        assert d["lease_id"] == "lease-001"
        assert d["custody_epoch"] == 1
        assert d["run_authority_grant_id"] == "grant-99"
        assert d["wbc_attempt_reference"] == "wbc-att-77"

        # JSON serialization is deterministic and round-trips via normalize
        encoded = lease.to_json()
        parsed = json.loads(encoded)
        assert parsed["contract_type"] == "custody_lease"
        # Rebuild via normalize (the canonical factory for nested contracts)
        rebuilt = normalize_custody_lease(parsed)
        assert rebuilt is not None
        assert rebuilt.lease_id == lease.lease_id
        assert rebuilt.custody_epoch == lease.custody_epoch
        assert rebuilt.digest() == lease.digest()
        assert rebuilt.to_json() == encoded

    def test_deterministic_serialization(self) -> None:
        a = _make_lease()
        b = _make_lease()
        assert a.to_json() == b.to_json()
        assert a.digest() == b.digest()

    def test_owner_identity_tuple(self) -> None:
        lease = _make_lease()
        assert lease.owner_identity == ("host-1", "12345", "boot-abc")

    def test_is_expired(self) -> None:
        # Create a lease that expires far in the future (not expired)
        future_lease = _make_lease(
            acquired_at="2025-01-01T00:00:00Z",
            expires_at="2099-01-01T00:00:00Z",
        )
        assert not future_lease.is_expired

        # Create a lease that expired in the past
        past_lease = _make_lease(
            acquired_at="2020-01-01T00:00:00Z",
            expires_at="2020-01-02T00:00:00Z",
        )
        assert past_lease.is_expired

    def test_causal_predecessor_can_be_empty(self) -> None:
        lease = _make_lease(causal_predecessor="")
        assert lease.causal_predecessor == ""

    def test_wbc_attempt_reference_can_be_empty(self) -> None:
        lease = _make_lease(wbc_attempt_reference="")
        assert lease.wbc_attempt_reference == ""

    def test_owner_boot_id_can_be_empty(self) -> None:
        lease = _make_lease(owner_boot_id="")
        assert lease.owner_boot_id == ""

    def test_deep_immutability(self) -> None:
        lease = _make_lease()
        with pytest.raises(FrozenInstanceError):
            lease.lease_id = "changed"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            lease.occurrence_key.run_id = "changed"  # type: ignore[misc]

    def test_normalize_custody_lease(self) -> None:
        occ_dict = _make_occurrence_key().to_dict()
        payload = {
            "occurrence_key": occ_dict,
            "lease_id": "l-1",
            "owner_host": "h1",
            "owner_pid": "123",
            "owner_boot_id": "b1",
            "run_authority_grant_id": "g-1",
            "coordinator_fence_token": 7,
            "wbc_attempt_reference": "w-1",
            "custody_epoch": 1,
            "acquired_at": "2025-01-01T00:00:00Z",
            "expires_at": "2025-01-02T00:00:00Z",
            "idempotency_key": "ik-1",
            "causal_predecessor": "",
        }
        lease = normalize_custody_lease(payload)
        assert lease is not None
        assert lease.lease_id == "l-1"


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyLease — malformed inputs
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyLeaseMalformed:
    """Prove CustodyLease rejects malformed and reinterpretable inputs."""

    def test_missing_lease_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="lease_id"):
            _make_lease(lease_id="")

    def test_missing_owner_host_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_host"):
            _make_lease(owner_host="")

    def test_missing_owner_pid_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_pid"):
            _make_lease(owner_pid="")

    def test_non_string_owner_boot_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_boot_id"):
            _make_lease(owner_boot_id=42)  # type: ignore[arg-type]

    def test_missing_run_authority_grant_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="run_authority_grant_id"):
            _make_lease(run_authority_grant_id="")

    def test_negative_coordinator_fence_token_rejected(self) -> None:
        with pytest.raises(ContractError, match="coordinator_fence_token"):
            _make_lease(coordinator_fence_token=-1)

    def test_non_integer_fence_token_rejected(self) -> None:
        with pytest.raises(ContractError, match="coordinator_fence_token"):
            _make_lease(coordinator_fence_token="42")  # type: ignore[arg-type]

    def test_non_string_wbc_attempt_reference_rejected(self) -> None:
        with pytest.raises(ContractError, match="wbc_attempt_reference"):
            _make_lease(wbc_attempt_reference=99)  # type: ignore[arg-type]

    def test_missing_custody_epoch_rejected_as_zero(self) -> None:
        """custody_epoch must be >= 1."""
        with pytest.raises(ContractError, match="custody_epoch"):
            _make_lease(custody_epoch=0)

    def test_negative_custody_epoch_rejected(self) -> None:
        with pytest.raises(ContractError, match="custody_epoch"):
            _make_lease(custody_epoch=-5)

    def test_boolean_custody_epoch_rejected(self) -> None:
        with pytest.raises(ContractError, match="custody_epoch"):
            _make_lease(custody_epoch=True)  # type: ignore[arg-type]

    def test_missing_acquired_at_rejected(self) -> None:
        with pytest.raises(ContractError, match="acquired_at"):
            _make_lease(acquired_at="")

    def test_missing_expires_at_rejected(self) -> None:
        with pytest.raises(ContractError, match="expires_at"):
            _make_lease(expires_at="")

    def test_missing_idempotency_key_rejected(self) -> None:
        with pytest.raises(ContractError, match="idempotency_key"):
            _make_lease(idempotency_key="")

    def test_non_string_causal_predecessor_rejected(self) -> None:
        with pytest.raises(ContractError, match="causal_predecessor"):
            _make_lease(causal_predecessor=42)  # type: ignore[arg-type]

    def test_invalid_iso_timestamp_rejected(self) -> None:
        with pytest.raises(ContractError, match="invalid ISO-8601"):
            _make_lease(acquired_at="not-a-date")

    def test_expires_at_not_after_acquired_at_rejected(self) -> None:
        with pytest.raises(ContractError, match="expires_at must be strictly after"):
            _make_lease(
                acquired_at="2025-01-02T00:00:00Z",
                expires_at="2025-01-01T00:00:00Z",
            )

    def test_expires_at_equal_to_acquired_at_rejected(self) -> None:
        with pytest.raises(ContractError, match="expires_at must be strictly after"):
            _make_lease(
                acquired_at="2025-01-01T00:00:00Z",
                expires_at="2025-01-01T00:00:00Z",
            )

    def test_normalize_returns_none_on_invalid(self) -> None:
        assert normalize_custody_lease(None) is None
        assert normalize_custody_lease({}) is None
        # Missing occurrence_key
        assert normalize_custody_lease({"lease_id": "x"}) is None

    # ── Monotonic epoch enforcement ───────────────────────────────────────

    def test_monotonic_epoch_happy_path(self) -> None:
        prev = _make_lease(custody_epoch=1, lease_id="l-1")
        curr = _make_lease(custody_epoch=2, lease_id="l-2")
        curr.assert_monotonic_epoch(prev)  # should not raise

    def test_non_monotonic_epoch_rejected(self) -> None:
        prev = _make_lease(custody_epoch=2, lease_id="l-1")
        curr = _make_lease(custody_epoch=1, lease_id="l-2")
        with pytest.raises(ContractError, match="monotonic"):
            curr.assert_monotonic_epoch(prev)

    def test_equal_epoch_treated_as_non_monotonic(self) -> None:
        prev = _make_lease(custody_epoch=1, lease_id="l-1")
        curr = _make_lease(custody_epoch=1, lease_id="l-2")
        with pytest.raises(ContractError, match="monotonic"):
            curr.assert_monotonic_epoch(prev)

    def test_same_lease_id_rejected_in_monotonic_check(self) -> None:
        prev = _make_lease(custody_epoch=1, lease_id="l-same")
        curr = _make_lease(custody_epoch=2, lease_id="l-same")
        with pytest.raises(ContractError, match="lease_id must differ"):
            curr.assert_monotonic_epoch(prev)

    # ── Cannot reinterpret identity fields ────────────────────────────────

    def test_cannot_reinterpret_lease_identity(self) -> None:
        a = _make_lease(lease_id="lease-a")
        b = _make_lease(lease_id="lease-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_owner_identity(self) -> None:
        a = _make_lease(owner_host="host-a")
        b = _make_lease(owner_host="host-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_grant_reference(self) -> None:
        a = _make_lease(run_authority_grant_id="grant-a")
        b = _make_lease(run_authority_grant_id="grant-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_fence_token(self) -> None:
        a = _make_lease(coordinator_fence_token=1)
        b = _make_lease(coordinator_fence_token=2)
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_wbc_attempt_reference(self) -> None:
        a = _make_lease(wbc_attempt_reference="wbc-a")
        b = _make_lease(wbc_attempt_reference="wbc-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_custody_epoch(self) -> None:
        a = _make_lease(custody_epoch=1)
        b = _make_lease(custody_epoch=2)
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_idempotency_key(self) -> None:
        a = _make_lease(idempotency_key="ik-a")
        b = _make_lease(idempotency_key="ik-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_causal_predecessor(self) -> None:
        a = _make_lease(causal_predecessor="")
        b = _make_lease(causal_predecessor="prev-lease-1")
        assert a != b
        assert a.digest() != b.digest()


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyLeaseEvent — round trips
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyLeaseEventRoundTrip:
    """Canonical round trips for CustodyLeaseEvent."""

    def test_full_round_trip(self) -> None:
        evt = _make_event()
        d = evt.to_dict()
        assert d["contract_type"] == "custody_lease_event"
        assert d["event_id"] == "evt-001"
        assert d["lease_id"] == "lease-001"
        assert d["sequence"] == 1
        assert d["event_type"] == "acquire"

        encoded = evt.to_json()
        decoded = CustodyLeaseEvent.from_json(encoded)
        assert decoded == evt
        assert decoded.digest() == evt.digest()

    def test_all_event_types_round_trip(self) -> None:
        for event_type in sorted(CUSTODY_LEASE_EVENT_TYPES):
            evt = _make_event(event_type=event_type)
            assert evt.event_type == event_type
            encoded = evt.to_json()
            decoded = CustodyLeaseEvent.from_json(encoded)
            assert decoded == evt
            assert decoded.event_type == event_type

    def test_payload_hash_is_deterministic(self) -> None:
        a = _make_event(payload={"x": 1, "y": 2})
        b = _make_event(payload={"y": 2, "x": 1})  # reordered
        assert a.payload_hash == b.payload_hash
        assert a.to_json() == b.to_json()

    def test_payload_hash_differs_for_different_payload(self) -> None:
        a = _make_event(payload={"x": 1})
        b = _make_event(payload={"x": 2})
        assert a.payload_hash != b.payload_hash

    def test_payload_is_frozen(self) -> None:
        evt = _make_event(payload={"key": "value"})
        # payload is a MappingProxyType, immutable
        with pytest.raises(TypeError):
            evt.payload["new"] = "mutation"  # type: ignore[index]

    def test_deterministic_serialization(self) -> None:
        a = _make_event()
        b = _make_event()
        assert a.to_json() == b.to_json()
        assert a.digest() == b.digest()

    def test_owner_identity(self) -> None:
        evt = _make_event()
        assert evt.owner_identity == ("host-1", "12345", "boot-abc")

    def test_deep_immutability(self) -> None:
        evt = _make_event()
        with pytest.raises(FrozenInstanceError):
            evt.event_id = "changed"  # type: ignore[misc]

    def test_normalize_custody_lease_event(self) -> None:
        payload = {
            "event_id": "e1",
            "lease_id": "l1",
            "sequence": 1,
            "event_type": "acquire",
            "occurred_at": "2025-01-01T00:00:00Z",
            "custody_epoch": 1,
            "owner_host": "h1",
            "owner_pid": "123",
            "owner_boot_id": "b1",
            "run_authority_grant_id": "g1",
            "coordinator_fence_token": 0,
            "wbc_attempt_reference": "",
            "occurrence_digest": "sha256:abcd",
            "idempotency_key": "ik1",
            "causal_predecessor": "",
            "payload": {},
        }
        evt = normalize_custody_lease_event(payload)
        assert evt is not None
        assert evt.event_id == "e1"


# ═══════════════════════════════════════════════════════════════════════════════
# CustodyLeaseEvent — malformed inputs
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustodyLeaseEventMalformed:
    """Prove CustodyLeaseEvent rejects malformed and reinterpretable inputs."""

    def test_missing_event_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="event_id"):
            _make_event(event_id="")

    def test_missing_lease_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="lease_id"):
            _make_event(lease_id="")

    def test_zero_sequence_rejected(self) -> None:
        with pytest.raises(ContractError, match="sequence"):
            _make_event(sequence=0)

    def test_negative_sequence_rejected(self) -> None:
        with pytest.raises(ContractError, match="sequence"):
            _make_event(sequence=-1)

    def test_unknown_event_type_rejected(self) -> None:
        with pytest.raises(ContractError, match="unknown event_type"):
            _make_event(event_type="unknown_type")  # type: ignore[arg-type]

    def test_missing_occurred_at_rejected(self) -> None:
        with pytest.raises(ContractError, match="occurred_at"):
            _make_event(occurred_at="")

    def test_zero_custody_epoch_rejected(self) -> None:
        with pytest.raises(ContractError, match="custody_epoch"):
            _make_event(custody_epoch=0)

    def test_negative_custody_epoch_rejected(self) -> None:
        with pytest.raises(ContractError, match="custody_epoch"):
            _make_event(custody_epoch=-1)

    def test_missing_owner_host_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_host"):
            _make_event(owner_host="")

    def test_missing_owner_pid_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_pid"):
            _make_event(owner_pid="")

    def test_non_string_owner_boot_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="owner_boot_id"):
            _make_event(owner_boot_id=42)  # type: ignore[arg-type]

    def test_missing_run_authority_grant_id_rejected(self) -> None:
        with pytest.raises(ContractError, match="run_authority_grant_id"):
            _make_event(run_authority_grant_id="")

    def test_negative_coordinator_fence_token_rejected(self) -> None:
        with pytest.raises(ContractError, match="coordinator_fence_token"):
            _make_event(coordinator_fence_token=-1)

    def test_non_string_wbc_attempt_reference_rejected(self) -> None:
        with pytest.raises(ContractError, match="wbc_attempt_reference"):
            _make_event(wbc_attempt_reference=99)  # type: ignore[arg-type]

    def test_missing_occurrence_digest_rejected(self) -> None:
        with pytest.raises(ContractError, match="occurrence_digest"):
            _make_event(occurrence_digest="")

    def test_missing_idempotency_key_rejected(self) -> None:
        with pytest.raises(ContractError, match="idempotency_key"):
            _make_event(idempotency_key="")

    def test_non_string_causal_predecessor_rejected(self) -> None:
        with pytest.raises(ContractError, match="causal_predecessor"):
            _make_event(causal_predecessor=42)  # type: ignore[arg-type]

    def test_non_object_payload_rejected(self) -> None:
        with pytest.raises(ContractError, match="payload must be an object"):
            _make_event(payload="not-an-object")  # type: ignore[arg-type]

    def test_normalize_returns_none_on_invalid(self) -> None:
        assert normalize_custody_lease_event(None) is None
        assert normalize_custody_lease_event({}) is None

    # ── Monotonic sequence enforcement ────────────────────────────────────

    def test_monotonic_sequence_happy_path(self) -> None:
        prev = _make_event(event_id="evt-1", sequence=1)
        curr = _make_event(event_id="evt-2", sequence=2)
        curr.assert_monotonic_sequence(prev)  # should not raise

    def test_non_monotonic_sequence_rejected(self) -> None:
        prev = _make_event(event_id="evt-1", sequence=2)
        curr = _make_event(event_id="evt-2", sequence=1)
        with pytest.raises(ContractError, match="monotonic"):
            curr.assert_monotonic_sequence(prev)

    def test_equal_sequence_rejected(self) -> None:
        prev = _make_event(event_id="evt-1", sequence=1)
        curr = _make_event(event_id="evt-2", sequence=1)
        with pytest.raises(ContractError, match="monotonic"):
            curr.assert_monotonic_sequence(prev)

    def test_different_lease_id_rejected_in_sequence_check(self) -> None:
        prev = _make_event(event_id="evt-1", lease_id="lease-a", sequence=1)
        curr = _make_event(event_id="evt-2", lease_id="lease-b", sequence=2)
        with pytest.raises(IdentityConflict, match="lease_id mismatch"):
            curr.assert_monotonic_sequence(prev)

    # ── Monotonic epoch enforcement (events) ──────────────────────────────

    def test_event_monotonic_epoch_happy_path(self) -> None:
        prev = _make_event(event_id="evt-1", custody_epoch=1)
        curr = _make_event(event_id="evt-2", custody_epoch=2)
        curr.assert_monotonic_epoch(prev)  # should not raise

    def test_event_monotonic_epoch_equal_ok(self) -> None:
        """custody_epoch can stay the same between events."""
        prev = _make_event(event_id="evt-1", custody_epoch=1)
        curr = _make_event(event_id="evt-2", custody_epoch=1)
        curr.assert_monotonic_epoch(prev)  # should not raise

    def test_event_epoch_decrease_rejected(self) -> None:
        prev = _make_event(event_id="evt-1", custody_epoch=2)
        curr = _make_event(event_id="evt-2", custody_epoch=1)
        with pytest.raises(ContractError, match="non-decreasing"):
            curr.assert_monotonic_epoch(prev)

    # ── Cannot reinterpret event identity ─────────────────────────────────

    def test_cannot_reinterpret_event_type(self) -> None:
        a = _make_event(event_type="acquire")
        b = _make_event(event_type="release")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_lease_id_in_event(self) -> None:
        a = _make_event(lease_id="lease-a")
        b = _make_event(lease_id="lease-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_sequence(self) -> None:
        a = _make_event(sequence=1)
        b = _make_event(sequence=2)
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_owner_in_event(self) -> None:
        a = _make_event(owner_host="host-a")
        b = _make_event(owner_host="host-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_grant_in_event(self) -> None:
        a = _make_event(run_authority_grant_id="grant-a")
        b = _make_event(run_authority_grant_id="grant-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_fence_in_event(self) -> None:
        a = _make_event(coordinator_fence_token=1)
        b = _make_event(coordinator_fence_token=2)
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_wbc_in_event(self) -> None:
        a = _make_event(wbc_attempt_reference="wbc-a")
        b = _make_event(wbc_attempt_reference="wbc-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_occurrence_digest_in_event(self) -> None:
        a = _make_event(occurrence_digest="sha256:aaaa")
        b = _make_event(occurrence_digest="sha256:bbbb")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_custody_epoch_in_event(self) -> None:
        a = _make_event(custody_epoch=1)
        b = _make_event(custody_epoch=2)
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_idempotency_key_in_event(self) -> None:
        a = _make_event(idempotency_key="ik-a")
        b = _make_event(idempotency_key="ik-b")
        assert a != b
        assert a.digest() != b.digest()

    def test_cannot_reinterpret_causal_predecessor_in_event(self) -> None:
        a = _make_event(causal_predecessor="")
        b = _make_event(causal_predecessor="prev-evt")
        assert a != b
        assert a.digest() != b.digest()

    # ── Payload conflict detection ────────────────────────────────────────

    def test_tampered_payload_hash_rejected(self) -> None:
        evt = _make_event(payload={"x": 1})
        d = evt.to_dict()
        d["payload_hash"] = "deadbeef" * 8  # tamper
        with pytest.raises(PayloadConflict):
            CustodyLeaseEvent.from_dict(d)


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-model integration: F01 tuple integrity across all four models
# ═══════════════════════════════════════════════════════════════════════════════


class TestCrossModelF01Integrity:
    """Prove the F01 tuple identity propagates faithfully through all models."""

    def test_f01_change_in_target_propagates_to_occurrence_key(self) -> None:
        target_a = _make_target(environment="prod")
        target_b = _make_target(environment="staging")
        ok_a = _make_occurrence_key(target=target_a)
        ok_b = _make_occurrence_key(target=target_b)
        assert ok_a.occurrence_digest != ok_b.occurrence_digest

    def test_f01_change_in_occurrence_propagates_to_lease(self) -> None:
        target_a = _make_target(chain="chain-alpha")
        target_b = _make_target(chain="chain-beta")
        ok_a = _make_occurrence_key(target=target_a)
        ok_b = _make_occurrence_key(target=target_b)
        lease_a = _make_lease(occurrence_key=ok_a)
        lease_b = _make_lease(occurrence_key=ok_b)
        assert lease_a.digest() != lease_b.digest()

    def test_f01_change_propagates_to_event_through_lease_identity(self) -> None:
        occ_a = _make_occurrence_key()
        occ_b = _make_occurrence_key(target=_make_target(chain="chain-gamma"))
        lease_a = _make_lease(lease_id="l-a", occurrence_key=occ_a)
        lease_b = _make_lease(lease_id="l-b", occurrence_key=occ_b)
        # Events referencing different leases have different lease_id
        evt_a = _make_event(lease_id=lease_a.lease_id, event_id="evt-a")
        evt_b = _make_event(lease_id=lease_b.lease_id, event_id="evt-b")
        assert evt_a.lease_id != evt_b.lease_id
        assert evt_a.digest() != evt_b.digest()

    def test_all_eight_event_types_are_valid_and_distinct(self) -> None:
        for event_type in sorted(CUSTODY_LEASE_EVENT_TYPES):
            evt = _make_event(event_type=event_type)
            decoded = CustodyLeaseEvent.from_json(evt.to_json())
            assert decoded.event_type == event_type

    def test_from_dict_rejects_extra_fields(self) -> None:
        target = _make_target()
        d = target.to_dict()
        d["extra_field"] = "should not be here"
        with pytest.raises(ContractError):
            CustodyTargetKey.from_dict(d)

    def test_from_dict_rejects_missing_contract_type(self) -> None:
        target = _make_target()
        d = target.to_dict()
        del d["contract_type"]
        with pytest.raises(ContractError):
            CustodyTargetKey.from_dict(d)

    def test_from_dict_rejects_wrong_schema_version(self) -> None:
        target = _make_target()
        d = target.to_dict()
        d["schema_version"] = 999
        with pytest.raises(ContractError):
            CustodyTargetKey.from_dict(d)

    def test_target_digest_function_is_deterministic(self) -> None:
        f01 = _base_f01()
        d1 = target_digest({**f01, "chain_identity": "cid"})
        d2 = target_digest({**f01, "chain_identity": "cid"})
        assert d1 == d2

    def test_occurrence_digest_function_is_deterministic(self) -> None:
        f01 = _base_f01()
        d1 = occurrence_digest(f01, fence_token=42, chain_identity="cid")
        d2 = occurrence_digest(f01, fence_token=42, chain_identity="cid")
        assert d1 == d2

    def test_occurrence_digest_changes_with_fence_token(self) -> None:
        f01 = _base_f01()
        d1 = occurrence_digest(f01, fence_token=1)
        d2 = occurrence_digest(f01, fence_token=2)
        assert d1 != d2

    def test_occurrence_digest_changes_with_chain_identity(self) -> None:
        f01 = _base_f01()
        d1 = occurrence_digest(f01, fence_token=1, chain_identity="cid-a")
        d2 = occurrence_digest(f01, fence_token=1, chain_identity="cid-b")
        assert d1 != d2
