"""Tests for ``arnold.runtime.envelope`` (T2 / SC2)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from arnold.runtime.envelope import (
    RUNTIME_ENVELOPE_SCHEMA_VERSION,
    CrossCuttingEnvelope,
    RuntimeEnvelope,
)
from arnold.runtime.resume import (
    TRUST_QUARANTINED_MANIFEST_MISMATCH,
    TRUST_TRUSTED,
    TRUST_UNKNOWN,
    ResumeCursorRef,
)


class TestRuntimeEnvelopeShape:
    def test_runtime_envelope_is_frozen(self) -> None:
        env = RuntimeEnvelope(plugin_id="plug-1", run_id="r-1")
        with pytest.raises(FrozenInstanceError):
            env.plugin_id = "mutated"  # type: ignore[misc]

    def test_cross_cutting_envelope_is_frozen(self) -> None:
        cc = CrossCuttingEnvelope()
        with pytest.raises(FrozenInstanceError):
            cc.deadline = "2030-01-01T00:00:00Z"  # type: ignore[misc]

    def test_schema_version_is_int_class_constant(self) -> None:
        assert isinstance(RuntimeEnvelope.schema_version, int)
        assert RuntimeEnvelope.schema_version == RUNTIME_ENVELOPE_SCHEMA_VERSION
        # Pinnable without instantiation
        assert RuntimeEnvelope.schema_version >= 1

    def test_trust_state_default_is_unknown(self) -> None:
        env = RuntimeEnvelope(plugin_id="plug-1", run_id="r-1")
        assert env.trust_state == TRUST_UNKNOWN
        assert TRUST_UNKNOWN == "unknown"

    def test_no_lease_fencing_capacity_grant_on_runtime_envelope(self) -> None:
        env = RuntimeEnvelope()
        for forbidden in ("lease_id", "fencing_token", "capacity_grant"):
            assert not hasattr(env, forbidden), (
                f"RuntimeEnvelope must not carry {forbidden!r} in M2a "
                "— that field is M3 hinge scope."
            )

    def test_no_lease_fencing_capacity_grant_on_cross_cutting_envelope(self) -> None:
        cc = CrossCuttingEnvelope()
        for forbidden in ("lease_id", "fencing_token", "capacity_grant"):
            assert not hasattr(cc, forbidden), (
                f"CrossCuttingEnvelope must not carry {forbidden!r} in M2a "
                "— that field is M3 hinge scope."
            )

    def test_cross_cutting_fields_mirror_existing_run_envelope_shape(self) -> None:
        # Structural-mirror assertion: the seven cross-cutting fields the
        # brief enumerates exist on the M2a Arnold sub-record.
        cc = CrossCuttingEnvelope()
        for f in (
            "taint",
            "cost",
            "lineage",
            "deadline",
            "cancellation",
            "retry_budget",
            "error_class",
        ):
            assert hasattr(cc, f), (
                f"CrossCuttingEnvelope missing structural field {f!r}"
            )


class TestRuntimeEnvelopeJsonRoundTrip:
    def test_round_trip_equality_default(self) -> None:
        env = RuntimeEnvelope(plugin_id="plug-1", run_id="r-1")
        round_tripped = RuntimeEnvelope.from_json(env.to_json())
        assert round_tripped == env

    def test_round_trip_equality_with_full_cross_cutting(self) -> None:
        env = RuntimeEnvelope(
            plugin_id="plug-1",
            manifest_hash="sha256:aaaa",
            plugin_state_schema_version=3,
            run_id="r-1",
            artifact_root="/tmp/run-1",
            resume_cursor=ResumeCursorRef(
                plugin_id="plug-1",
                run_id="r-1",
                cursor={"step": "ingest", "offset": 42},
            ),
            trust_state=TRUST_TRUSTED,
            created_at="2026-06-02T15:32:00Z",
            cross_cutting=CrossCuttingEnvelope(
                taint=("sensitive", "user-data"),
                cost={"usd": 0.12},
                lineage=("plan-9", "epoch-2"),
                deadline="2026-06-02T16:00:00Z",
                cancellation="user-cancel",
                retry_budget={"remaining": 3},
                error_class=None,
            ),
        )
        round_tripped = RuntimeEnvelope.from_json(env.to_json())
        assert round_tripped == env

    def test_round_trip_equality_with_quarantined_trust(self) -> None:
        env = RuntimeEnvelope(
            plugin_id="plug-1",
            run_id="r-1",
            trust_state=TRUST_QUARANTINED_MANIFEST_MISMATCH,
        )
        round_tripped = RuntimeEnvelope.from_json(env.to_json())
        assert round_tripped == env
        assert round_tripped.trust_state == "quarantined-manifest-mismatch"

    def test_persisted_schema_version_field_carried(self) -> None:
        env = RuntimeEnvelope(plugin_id="plug-1", run_id="r-1")
        # to_json carries the version
        import json as _json

        blob = _json.loads(env.to_json())
        assert blob["schema_version"] == RuntimeEnvelope.schema_version

    def test_schema_version_mismatch_rejected(self) -> None:
        # Hand-craft a persisted blob with a divergent schema_version
        bad = '{"schema_version": 9999, "plugin_id": "p", "run_id": "r"}'
        with pytest.raises(ValueError):
            RuntimeEnvelope.from_json(bad)
