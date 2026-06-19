"""Tests for the Megaplan parity comparison harness (T17).

Validates:
1. The harness can compare every golden trace against itself (identity check).
2. Narrow named volatility normalization only masks specifically named fields.
3. Diff reporting produces useful, surface-localized output.
4. Golden trace loading covers all 8 scenarios.
5. The harness handles blocked goldens correctly.
6. Artifact diff detail correctly identifies only-in-native, only-in-golden, and hash mismatches.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.arnold.pipelines.megaplan.data.native_parity.scenarios import (
    PARITY_SCENARIOS,
    PARITY_SCENARIO_BY_ID,
)
from tests.arnold.pipelines.megaplan.parity_harness import (
    GoldenTrace,
    MegaplanParityHarness,
    _artifact_diff_detail,
    normalize_cursor_narrow,
    normalize_envelope_narrow,
    normalize_state_narrow,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def harness() -> MegaplanParityHarness:
    return MegaplanParityHarness()


# ═══════════════════════════════════════════════════════════════════════
# Golden trace loading
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenTraceLoading:
    """The harness can load all 8 golden traces."""

    def test_all_eight_goldens_loadable(self, harness: MegaplanParityHarness) -> None:
        """Every scenario_id in the catalog has a loadable golden trace."""
        available = harness.list_available_goldens()
        assert len(available) == 8, f"Expected 8 goldens, got {len(available)}: {available}"

        for scenario in PARITY_SCENARIOS:
            golden = harness.load_golden(scenario.scenario_id)
            assert golden.scenario_id == scenario.scenario_id
            assert golden.schema_version == 1
            assert golden.generated_by == "graph_executor"

    def test_blocked_goldens_have_reason(self, harness: MegaplanParityHarness) -> None:
        """Blocked goldens carry a non-empty blocked_reason."""
        blocked_ids = {
            "revise_loop",
            "tiebreaker",
            "escalate",
            "override_force_proceed",
            "override_abort",
            "suspension_resume",
            "execute_review_artifact",
        }
        for sid in blocked_ids:
            golden = harness.load_golden(sid)
            assert golden.blocked is True, f"{sid} should be blocked"
            assert golden.blocked_reason, f"{sid} missing blocked_reason"
            assert golden.stage_sequence == []
            assert golden.state is None

    def test_unblocked_golden_has_complete_data(self, harness: MegaplanParityHarness) -> None:
        """The unblocked golden (happy_finalize) has all non-null fields."""
        golden = harness.load_golden("happy_finalize")
        assert golden.blocked is False
        assert len(golden.stage_sequence) > 0
        assert golden.final_stage is not None
        assert isinstance(golden.state, dict)
        assert isinstance(golden.envelope, dict)
        assert isinstance(golden.artifact_inventory, dict)

    def test_missing_golden_raises(self, harness: MegaplanParityHarness) -> None:
        """Loading a non-existent golden raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            harness.load_golden("nonexistent_scenario")


# ═══════════════════════════════════════════════════════════════════════
# Golden-to-self identity checks
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenToSelfIdentity:
    """Comparing a golden against itself produces 'match' on every dimension."""

    ALL_DIMENSIONS = (
        "topology_hash",
        "stage_sequence",
        "state",
        "envelope",
        "resume_cursor",
        "artifact_inventory",
        "event_fold",
    )

    def test_happy_finalize_self_match(self, harness: MegaplanParityHarness) -> None:
        report = harness.compare_golden_to_self("happy_finalize")
        for dim in self.ALL_DIMENSIONS:
            assert report[dim] == "match", (
                f"Dimension '{dim}' should be 'match' for happy_finalize self-comparison, "
                f"got: {report[dim]}"
            )

    def test_revise_loop_blocked_self_match(self, harness: MegaplanParityHarness) -> None:
        """Blocked goldens also match themselves on all dimensions."""
        report = harness.compare_golden_to_self("revise_loop")
        for dim in self.ALL_DIMENSIONS:
            assert report[dim] == "match", (
                f"Dimension '{dim}' should be 'match' for blocked revise_loop self-comparison, "
                f"got: {report[dim]}"
            )

    @pytest.mark.parametrize("scenario_id", [
        "happy_finalize",
        "revise_loop",
        "tiebreaker",
        "escalate",
        "override_force_proceed",
        "override_abort",
        "suspension_resume",
        "execute_review_artifact",
    ])
    def test_all_goldens_match_themselves(
        self, harness: MegaplanParityHarness, scenario_id: str
    ) -> None:
        """Every golden trace in the catalog matches itself on all dimensions."""
        report = harness.compare_golden_to_self(scenario_id)
        mismatches = {
            dim: report[dim]
            for dim in self.ALL_DIMENSIONS
            if report[dim] != "match"
        }
        assert not mismatches, (
            f"Golden '{scenario_id}' self-comparison has mismatches: {mismatches}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Narrow named volatility normalization
# ═══════════════════════════════════════════════════════════════════════


class TestNarrowVolatilityNormalization:
    """Normalization only masks specifically named volatile fields."""

    # ── state normalization ───────────────────────────────────────────

    def test_state_strips_named_volatile_keys(self) -> None:
        """Named volatile keys are stripped from state."""
        state = {
            "name": "test-plan",
            "idea": "test idea",
            "invocation_id": "abc-123",
            "session_id": "def-456",
            "started_at": "2024-01-01T00:00:00Z",
            "timestamp": 1234567890,
            "ts_utc": "2024-01-01T00:00:00Z",
            "ts_rel_init_s": 0.001,
            "finished_at": "2024-01-01T01:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "__state__": {"internal": "data"},
            "__envelope__": {"run_id": "xyz"},
            "__child_contract_results__": {"child": "stuff"},
            "resume_cursor": "opaque-cursor-string",
        }
        normalized = normalize_state_narrow(state)

        # Volatile keys must be absent
        for key in (
            "invocation_id", "session_id", "started_at", "timestamp",
            "ts_utc", "ts_rel_init_s", "finished_at", "created_at",
            "updated_at", "__state__", "__envelope__",
            "__child_contract_results__", "resume_cursor",
        ):
            assert key not in normalized, f"'{key}' should be stripped"

        # Non-volatile keys must be preserved
        assert normalized["name"] == "test-plan"
        assert normalized["idea"] == "test idea"

    def test_state_preserves_non_volatile_keys(self) -> None:
        """Non-volatile keys pass through unchanged."""
        state = {
            "config": {"agent": "claude", "mode": "code"},
            "history": [{"step": "init", "result": "success"}],
            "iteration": 2,
            "last_gate": {"passed": True, "recommendation": "PROCEED"},
            "nested_volatile_like": {"invocation_like": "keep-me"},
        }
        normalized = normalize_state_narrow(state)
        assert normalized["config"] == {"agent": "claude", "mode": "code"}
        assert normalized["history"] == [{"step": "init", "result": "success"}]
        assert normalized["iteration"] == 2
        assert normalized["last_gate"] == {"passed": True, "recommendation": "PROCEED"}
        assert normalized["nested_volatile_like"] == {"invocation_like": "keep-me"}

    def test_state_absolute_paths_normalized(self) -> None:
        """Absolute path values are replaced with '<absolute-path>'."""
        state = {
            "project_dir": "/Users/test/project",
            "config": {"work_dir": "/tmp/work"},
            "nested": [{"path": "/var/log"}, {"relative": "data/output"}],
        }
        normalized = normalize_state_narrow(state)
        assert normalized["project_dir"] == "<absolute-path>"
        assert normalized["config"]["work_dir"] == "<absolute-path>"
        assert normalized["nested"][0]["path"] == "<absolute-path>"
        assert normalized["nested"][1]["relative"] == "data/output"

    def test_state_handles_none(self) -> None:
        """normalize_state_narrow(None) returns None."""
        assert normalize_state_narrow(None) is None

    # ── envelope normalization ─────────────────────────────────────────

    def test_envelope_masks_named_volatile_keys(self) -> None:
        """Named volatile keys are masked in envelope."""
        envelope = {
            "run_id": "run-123",
            "plugin_id": "megaplan",
            "lease_id": "lease-abc",
            "fencing_token": "token-xyz",
            "deadline": 1234567890.0,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
            "cost": 5.0,
            "capacity_grant": 100,
            "taint": "clean",
            "retry_budget": 3,
            "cancellation": False,
        }
        normalized = normalize_envelope_narrow(envelope)

        # Volatile keys masked
        for key in (
            "run_id", "plugin_id", "lease_id", "fencing_token",
            "deadline", "created_at", "updated_at", "cost", "capacity_grant",
        ):
            assert normalized[key] == "<masked>", (
                f"'{key}' should be '<masked>', got {normalized[key]!r}"
            )

        # Non-volatile keys preserved
        assert normalized["taint"] == "clean"
        assert normalized["retry_budget"] == 3
        assert normalized["cancellation"] is False

    def test_envelope_handles_none(self) -> None:
        """normalize_envelope_narrow(None) returns None."""
        assert normalize_envelope_narrow(None) is None

    # ── cursor normalization ──────────────────────────────────────────

    def test_cursor_masks_named_volatile_keys(self) -> None:
        """Named volatile keys are masked in cursor."""
        cursor = {
            "resume_cursor": "opaque-string",
            "cursor_id": "uuid-12345",
            "stage": "critique__pc3",
            "stages": ["prep__pc0", "plan__pc1"],
            "native": {"pc": 3, "version": 1},
        }
        normalized = normalize_cursor_narrow(cursor)

        assert normalized["resume_cursor"] == "<masked>"
        assert normalized["cursor_id"] == "<masked>"
        assert normalized["stage"] == "critique__pc3"
        assert normalized["stages"] == ["prep__pc0", "plan__pc1"]
        assert normalized["native"] == {"pc": 3, "version": 1}

    def test_cursor_handles_none(self) -> None:
        """normalize_cursor_narrow(None) returns None."""
        assert normalize_cursor_narrow(None) is None

    # ── blanket sanitization guard ────────────────────────────────────

    def test_no_blanket_sanitization(self) -> None:
        """The normalizer does NOT blank out non-named fields.

        If a dictionary has a key that happens to look volatile but isn't
        in the named volatile set, it must pass through unchanged.
        """
        state = {
            "gate_payload": {
                "recommendation": "PROCEED",
                "call": 1,
                "scenario": "happy_finalize",
                "stage": "gate",
            },
            "critique_payload": {
                "call": 2,
                "scenario": "happy_finalize",
                "stage": "critique",
            },
        }
        normalized = normalize_state_narrow(state)
        assert normalized == state, (
            f"Non-volatile state should pass through unchanged.\n"
            f"Expected: {state}\nGot: {normalized}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Diff reporting
# ═══════════════════════════════════════════════════════════════════════


class TestDiffReporting:
    """The harness produces useful, surface-localized diff reports."""

    def test_stage_sequence_mismatch_report(self, harness: MegaplanParityHarness) -> None:
        """A deliberate stage sequence mismatch produces a readable diff."""
        native_trace = {
            "stage_sequence": ["prep", "plan", "critique", "gate", "finalize"],
            "state": {},
            "envelope": {},
            "resume_cursor": None,
            "artifact_inventory": {},
            "event_fold": None,
            "topology_hash": None,
        }
        report = harness.compare_native_to_golden(native_trace, "happy_finalize")

        stage_report = report["stage_sequence"]
        assert stage_report != "match"
        assert "native" in stage_report
        assert "golden" in stage_report
        assert "detail" in stage_report
        assert "mismatch" in stage_report["detail"].lower()

    def test_artifact_diff_detail(self) -> None:
        """Artifact diff identifies only-in-native, only-in-golden, and hash mismatches."""
        native_inv = {
            "artifact_root_files": {
                "state.json": "sha256:aaa",
                "events.ndjson": "sha256:bbb",
                "extra_native_file.txt": "sha256:ccc",
            }
        }
        golden_inv = {
            "artifact_root_files": {
                "state.json": "sha256:aaa",
                "events.ndjson": "sha256:ddd",  # different hash
                "extra_golden_file.txt": "sha256:eee",
            }
        }

        result = _artifact_diff_detail(native_inv, golden_inv)
        assert "only_in_native" in result
        assert "artifact_root_files/extra_native_file.txt" in result["only_in_native"]
        assert "only_in_golden" in result
        assert "artifact_root_files/extra_golden_file.txt" in result["only_in_golden"]
        assert "hash_mismatches" in result
        assert "artifact_root_files/events.ndjson" in result["hash_mismatches"]

    def test_native_vs_golden_blocked(self, harness: MegaplanParityHarness) -> None:
        """Comparing against a blocked golden surfaces the blocked status."""
        native_trace = {
            "stage_sequence": ["prep", "plan"],
            "state": {},
            "envelope": {},
            "resume_cursor": None,
            "artifact_inventory": {},
            "event_fold": None,
            "topology_hash": None,
        }
        report = harness.compare_native_to_golden(native_trace, "revise_loop")
        assert report["blocked"]["golden_blocked"] is True
        assert report["stage_sequence"] == "golden_blocked"
        assert report["state"] == "golden_blocked"


# ═══════════════════════════════════════════════════════════════════════
# Harness invariants
# ═══════════════════════════════════════════════════════════════════════


class TestHarnessInvariants:
    """Structural invariants of the harness itself."""

    def test_all_dimensions_present_in_report(self, harness: MegaplanParityHarness) -> None:
        """Every comparison report includes all required dimensions."""
        report = harness.compare_golden_to_self("happy_finalize")
        required = {
            "_label",
            "topology_hash",
            "stage_sequence",
            "state",
            "envelope",
            "resume_cursor",
            "artifact_inventory",
            "event_fold",
        }
        assert set(report.keys()) == required, (
            f"Report keys: {set(report.keys())}, expected: {required}"
        )

    def test_golden_trace_roundtrip(self, harness: MegaplanParityHarness) -> None:
        """GoldenTrace from_json produces a stable object."""
        golden = harness.load_golden("happy_finalize")
        # Serialize and deserialize to verify stability
        raw = {
            "schema_version": golden.schema_version,
            "scenario_id": golden.scenario_id,
            "generated_by": golden.generated_by,
            "blocked": golden.blocked,
            "blocked_reason": golden.blocked_reason,
            "stage_sequence": golden.stage_sequence,
            "final_stage": golden.final_stage,
            "halt_reason": golden.halt_reason,
            "state": golden.state,
            "envelope": golden.envelope,
            "resume_cursor": golden.resume_cursor,
            "artifact_inventory": golden.artifact_inventory,
        }
        json_str = json.dumps(raw, sort_keys=True, default=str)
        reread = json.loads(json_str)
        assert reread["scenario_id"] == "happy_finalize"
        assert reread["stage_sequence"] == golden.stage_sequence

    def test_data_dir_default(self) -> None:
        """Default data_dir resolves to the native_parity directory."""
        harness = MegaplanParityHarness()
        expected_suffix = "tests/arnold/pipelines/megaplan/data/native_parity"
        assert str(harness._data_dir).endswith(expected_suffix), (
            f"Default data_dir should end with '{expected_suffix}', "
            f"got '{harness._data_dir}'"
        )

    def test_native_dict_with_missing_keys(self, harness: MegaplanParityHarness) -> None:
        """Native trace dicts with missing keys default gracefully."""
        native_trace: dict = {}
        report = harness.compare_native_to_golden(native_trace, "happy_finalize")
        # Should not crash; missing keys become empty defaults
        assert "stage_sequence" in report
        assert "state" in report
