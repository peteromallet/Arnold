"""Step 8B1 tests: global logical-effect identity with snapshotting.

Covers:
* GlobalEffectIdentity stability and determinism.
* Atomic reservation + GLEK snapshot persistence.
* Idempotent re-reservation preserves snapshot (no re-derivation).
* Regeneration-survival (NSA-M10-FIX-4): retry reads v1 snapshot, not v2 schema.
* Torn-snapshot impossibility (same-row / same-transaction atomicity).
* Multi-effect per attempt (composite PK).
* Snapshot query and index join.
"""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest

from arnold.workflow.attempt_ledger_store import (
    GlobalEffectReservation,
    GlobalEffectOutcome,
    GlobalEffectConflict,
    GlobalEffectConflictError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity


# ── Helpers ───────────────────────────────────────────────────────────────


def _store_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def _make_identity(
    boundary_schema_hash: str = "sha256:v1",
) -> GlobalEffectIdentity:
    return GlobalEffectIdentity(
        environment_id="env-test",
        action_target="git-push",
        action_version="1.0.0",
        effect_family="git",
        provider_target="https://github.com/org/repo",
        canonical_request_identity="sha256:abc123",
        boundary_schema_hash=boundary_schema_hash,
    )


# ── GlobalEffectIdentity unit tests ──────────────────────────────────────


class TestGlobalEffectIdentity:
    def test_stable_key(self):
        ident = _make_identity()
        assert ident.global_logical_effect_key.startswith("glek:")

    def test_deterministic_same_inputs(self):
        a = _make_identity()
        b = _make_identity()
        assert a.global_logical_effect_key == b.global_logical_effect_key

    def test_different_boundary_schema_different_key(self):
        a = _make_identity("sha256:v1")
        b = _make_identity("sha256:v2")
        assert a.global_logical_effect_key != b.global_logical_effect_key

    def test_empty_field_rejected(self):
        with pytest.raises(ValueError):
            GlobalEffectIdentity(
                environment_id="",
                action_target="x",
                action_version="1",
                effect_family="git",
                provider_target="x",
                canonical_request_identity="x",
                boundary_schema_hash="x",
            )

    def test_to_dict_round_trip(self):
        ident = _make_identity()
        d = ident.to_dict()
        assert d["global_logical_effect_key"] == ident.global_logical_effect_key
        assert d["environment_id"] == ident.environment_id


# ── Store-level reservation tests ────────────────────────────────────────


class TestReserveGlobalEffect:
    def test_first_reservation_is_new(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            result = store.reserve_global_effect(aid, ident)
            assert result.is_new is True
            assert result.reservation_count == 1
            assert result.attempt_id == aid
            assert result.global_logical_effect_key == ident.global_logical_effect_key
            assert result.effect_identity.boundary_schema_hash == "sha256:v1"
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_re_reservation_preserves_snapshot(self):
        """Re-reservation returns original snapshot, count increments."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident_v1 = _make_identity("sha256:v1")
            r1 = store.reserve_global_effect(aid, ident_v1)
            r2 = store.reserve_global_effect(aid, ident_v1)
            assert r2.is_new is False
            assert r2.reservation_count == 2
            assert r2.first_reserved_ns == r1.first_reserved_ns
            assert r2.effect_identity.boundary_schema_hash == "sha256:v1"
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_regeneration_survival(self):
        """NSA-M10-FIX-4: retry reads v1 snapshot, not regenerated v2 schema."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident_v1 = _make_identity("sha256:v1")
            store.reserve_global_effect(aid, ident_v1)

            # Simulate inventory regeneration: new identity with v2 schema.
            ident_v2 = _make_identity("sha256:v2")

            # Retry reads the persisted snapshot via get_global_effect_reservation.
            glek_v1 = ident_v1.global_logical_effect_key
            persisted = store.get_global_effect_reservation(aid, glek_v1)
            assert persisted is not None
            assert persisted.effect_identity.boundary_schema_hash == "sha256:v1"
            assert persisted.global_logical_effect_key == glek_v1
            # The v2 identity produces a different GLEK — no collision.
            assert ident_v2.global_logical_effect_key != glek_v1
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_torn_snapshot_impossible(self):
        """Same-transaction persistence: reservation always has a snapshot."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            result = store.reserve_global_effect(aid, ident)
            assert result.is_new is True

            # Immediately readable — no window for a torn snapshot.
            persisted = store.get_global_effect_reservation(
                aid, ident.global_logical_effect_key
            )
            assert persisted is not None
            assert persisted.effect_identity.environment_id == ident.environment_id
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_multi_effect_per_attempt(self):
        """A single attempt can carry multiple distinct global effects."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident_a = _make_identity("sha256:v1")
            ident_b = GlobalEffectIdentity(
                environment_id="env-test",
                action_target="cloud-apply",
                action_version="2.0.0",
                effect_family="cloud",
                provider_target="aws://acct-1",
                canonical_request_identity="sha256:def456",
                boundary_schema_hash="sha256:v1",
            )
            r_a = store.reserve_global_effect(aid, ident_a)
            r_b = store.reserve_global_effect(aid, ident_b)
            assert r_a.global_logical_effect_key != r_b.global_logical_effect_key

            all_res = store.get_global_effect_reservations_for_attempt(aid)
            assert len(all_res) == 2
            keys = {r.global_logical_effect_key for r in all_res}
            assert r_a.global_logical_effect_key in keys
            assert r_b.global_logical_effect_key in keys
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_nonexistent_returns_none(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            result = store.get_global_effect_reservation(
                str(uuid.uuid4()), "glek:nonexistent"
            )
            assert result is None

            all_res = store.get_global_effect_reservations_for_attempt(
                str(uuid.uuid4())
            )
            assert all_res == ()
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_empty_attempt_id_rejected(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            with pytest.raises(ValueError):
                store.reserve_global_effect("", _make_identity())
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_reservation_creates_attempt_reservation(self):
        """GLEK reservation also creates the attempt reservation row."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            store.reserve_global_effect(aid, _make_identity())

            # The attempt reservation should exist.
            res = store.get_reservation(aid)
            assert res is not None
            assert res.attempt_id == aid
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_global_effect_table_exists_in_new_store(self):
        """New stores created from _init_schema have the GLEK table."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            conn = store.conn
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                "  AND name='global_effect_reservations'"
            )
            assert cur.fetchone() is not None
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
                "  AND name='idx_global_effect_attempt'"
            )
            assert cur.fetchone() is not None
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Step 8B2: terminal outcome CAS ───────────────────────────────────────


class TestAcceptTerminalOutcome:
    """Step 8B2: atomically accept one terminal per attempt/effect."""

    def test_first_accept_is_new(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            store.reserve_global_effect(aid, ident)
            outcome = store.accept_terminal_outcome(
                aid, ident.global_logical_effect_key, "COMPLETED", {"result": "ok"}
            )
            assert outcome.is_duplicate is False
            assert outcome.outcome_kind == "COMPLETED"
            assert outcome.outcome_payload == {"result": "ok"}
            assert outcome.attempt_id == aid
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_idempotent_re_accept_same_outcome(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            store.reserve_global_effect(aid, ident)
            glek = ident.global_logical_effect_key
            o1 = store.accept_terminal_outcome(aid, glek, "COMPLETED", {"x": 1})
            o2 = store.accept_terminal_outcome(aid, glek, "COMPLETED", {"x": 1})
            assert o2.is_duplicate is True
            assert o2.accepted_at_ns == o1.accepted_at_ns
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_divergent_outcome_quarantined(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            store.reserve_global_effect(aid, ident)
            glek = ident.global_logical_effect_key
            store.accept_terminal_outcome(aid, glek, "COMPLETED", {"x": 1})
            with pytest.raises(GlobalEffectConflictError) as exc_info:
                store.accept_terminal_outcome(aid, glek, "FAILED", {"err": "bad"})
            assert exc_info.value.conflict_kind == "divergent_outcome"
            conflicts = store.list_global_effect_conflicts(aid)
            assert len(conflicts) == 1
            assert conflicts[0].conflict_kind == "divergent_outcome"
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_unreserved_outcome_rejected(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            with pytest.raises(ValueError):
                store.accept_terminal_outcome(aid, "glek:none", "COMPLETED", {})
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_cross_attempt_exclusivity(self):
        """Only one attempt may accept a terminal outcome per GLEK."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid1 = str(uuid.uuid4())
            aid2 = str(uuid.uuid4())
            ident = _make_identity()
            glek = ident.global_logical_effect_key
            # Both attempts reserve the same GLEK.
            store.reserve_global_effect(aid1, ident)
            store.reserve_global_effect(aid2, ident)
            # First attempt accepts terminal.
            store.accept_terminal_outcome(aid1, glek, "COMPLETED", {})
            # Second attempt must be quarantined.
            with pytest.raises(GlobalEffectConflictError) as exc_info:
                store.accept_terminal_outcome(aid2, glek, "COMPLETED", {})
            assert exc_info.value.conflict_kind == "cross_attempt_outcome"
            conflicts = store.list_global_effect_conflicts(aid2)
            assert len(conflicts) == 1
            assert conflicts[0].conflict_kind == "cross_attempt_outcome"
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_multi_effect_per_attempt(self):
        """Multiple GLEKs in same attempt each get their own outcome."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            id1 = _make_identity("sha256:a")
            id2 = _make_identity("sha256:b")
            store.reserve_global_effect(aid, id1)
            store.reserve_global_effect(aid, id2)
            o1 = store.accept_terminal_outcome(aid, id1.global_logical_effect_key, "COMPLETED", {})
            o2 = store.accept_terminal_outcome(aid, id2.global_logical_effect_key, "FAILED", {"err": "x"})
            assert o1.outcome_kind == "COMPLETED"
            assert o2.outcome_kind == "FAILED"
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Step 8B3: dispatch eligibility ───────────────────────────────────────


class TestDispatchEligibility:
    """Step 8B3: prevent overlapping dispatch eligibility."""

    def test_eligible_when_reserved_and_no_terminal(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            store.reserve_global_effect(aid, ident)
            assert store.is_dispatch_eligible(aid, ident.global_logical_effect_key) is True
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_not_eligible_when_no_reservation(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            assert store.is_dispatch_eligible(aid, "glek:none") is False
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_not_eligible_after_terminal(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid = str(uuid.uuid4())
            ident = _make_identity()
            store.reserve_global_effect(aid, ident)
            store.accept_terminal_outcome(aid, ident.global_logical_effect_key, "COMPLETED", {})
            assert store.is_dispatch_eligible(aid, ident.global_logical_effect_key) is False
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_not_eligible_for_other_attempt_after_terminal(self):
        """Once terminal accepted, other attempts for same GLEK are blocked."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            aid1 = str(uuid.uuid4())
            aid2 = str(uuid.uuid4())
            ident = _make_identity()
            glek = ident.global_logical_effect_key
            store.reserve_global_effect(aid1, ident)
            store.reserve_global_effect(aid2, ident)
            store.accept_terminal_outcome(aid1, glek, "COMPLETED", {})
            # aid2 has a reservation but GLEK is terminal in aid1.
            assert store.is_dispatch_eligible(aid2, glek) is False
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
