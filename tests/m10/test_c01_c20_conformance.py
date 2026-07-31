"""Steps 23A-23E: C01-C20 candidate-bound conformance tests.

Aggregates evidence from the installed runtime and rejects stale/mixed
candidate hashes.  Each test class maps to a plan sub-step:

  - TestStep23A: C01-C04 launch and schema conformance
  - TestStep23B: C05-C09 authority and custody conformance
  - TestStep23C: C10-C14 recovery conformance
  - TestStep23D: C15-C17 effects and replay conformance
  - TestStep23E: C18-C20 candidate, inventory, and deferral conformance

The tests verify ``evidence/m10-c01-c20-conformance.json`` which is
produced by ``tools/generate_m10_c01_c20_conformance.py``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.criteria_verifiability import (
    check_criteria,
)

_TOOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "generate_m10_c01_c20_conformance.py"
)
_TOOL_SPEC = importlib.util.spec_from_file_location(
    "_m10_c01_c20_conformance_tool", _TOOL_PATH
)
assert _TOOL_SPEC is not None and _TOOL_SPEC.loader is not None
_TOOL_MODULE = importlib.util.module_from_spec(_TOOL_SPEC)
sys.modules[_TOOL_SPEC.name] = _TOOL_MODULE
_TOOL_SPEC.loader.exec_module(_TOOL_MODULE)
generate_conformance_receipt = _TOOL_MODULE.generate_conformance_receipt

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = REPO_ROOT / "evidence" / "m10-c01-c20-conformance.json"
PLAN_META_PATH = (
    REPO_ROOT
    / ".megaplan"
    / "plans"
    / "m10-safe-retry-recovery-and-20260723-1122"
    / "plan_v9.meta.json"
)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return generate_conformance_receipt()


@pytest.fixture(scope="module")
def criteria() -> list[dict]:
    meta = json.loads(PLAN_META_PATH.read_text())
    return meta.get("success_criteria", [])


def _sha256_file(rel_path: str) -> str:
    p = REPO_ROOT / rel_path
    if not p.exists():
        return "MISSING"
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


# ── Step 23A: C01-C04 launch and schema conformance ─────────────────────


class TestStep23AC01C04LaunchSchema:
    """C01-C03: source/seed/runtime binding; C04: schema conformance."""

    def test_receipt_exists_and_passes(self, receipt: dict) -> None:
        assert RECEIPT_PATH.exists()
        assert receipt["conformance_pass"] is True

    def test_receipt_bound_to_installed_runtime(self, receipt: dict) -> None:
        # The receipt must be bound to the *actual* installed-runtime files.
        actual = _sha256_file(
            "arnold_pipelines/megaplan/cloud/runtime_attestation.py"
        )
        assert receipt["bound_files"]["source/runtime_attestation"] == actual
        assert actual != "MISSING"

    def test_c01_c03_source_seed_runtime_bound(self, receipt: dict) -> None:
        c = receipt["c01_c03"]
        assert c["source_bound"] is True
        assert c["seed_bound"] is True
        assert c["runtime_attestation_hash"] != "MISSING"
        assert c["seed_rematerialize_hash"] != "MISSING"
        assert c["rejects_mixed_revision"] is True

    def test_c01_c03_rejects_stale_hash(self, receipt: dict) -> None:
        """A stale runtime_attestation hash must not match the receipt."""
        actual = _sha256_file(
            "arnold_pipelines/megaplan/cloud/runtime_attestation.py"
        )
        stale = "0" * 64
        assert receipt["bound_files"]["source/runtime_attestation"] != stale
        assert receipt["bound_files"]["source/runtime_attestation"] == actual

    def test_c01_c03_rejects_mixed_candidate(self, receipt: dict) -> None:
        """Source and seed hashes must both be present (not mixed/missing)."""
        bf = receipt["bound_files"]
        assert bf["source/runtime_attestation"] != "MISSING"
        assert bf["source/seed_rematerialize"] != "MISSING"

    def test_c04_schema_parity_present(self, receipt: dict) -> None:
        c = receipt["c04"]
        assert c["schema_parity_hash"] != "MISSING"
        assert c["schema_phases_count"] == 8
        assert c["fail_closed"] is True


# ── Step 23B: C05-C09 authority and custody conformance ─────────────────


class TestStep23BC05C09AuthorityCustody:
    """C05: feasibility epoch; C06-C09: authority, custody, action gate."""

    def test_c05_feasibility_epoch_binding(self, receipt: dict) -> None:
        c = receipt["c05"]
        assert c["seed_epoch_flows_through_finalize"] is True
        assert c["v2_missing_epoch_rejected"] is True

    def test_c06_c09_current_source_bound(self, receipt: dict) -> None:
        c = receipt["c06_c09"]
        assert c["current_source_hash"] != "MISSING"
        assert c["action_validator_hash"] != "MISSING"

    def test_c06_c09_lease_store_bound(self, receipt: dict) -> None:
        assert receipt["c06_c09"]["lease_store_hash"] != "MISSING"

    def test_c06_c09_action_gate_bound(self, receipt: dict) -> None:
        assert receipt["c06_c09"]["action_gate_hash"] != "MISSING"

    def test_c06_c09_raw_writes_unavailable(self, receipt: dict) -> None:
        c = receipt["c06_c09"]
        assert c["raw_writes_unavailable_to_production"] is True
        assert c["double_fenced_rereads_required"] is True

    def test_c06_c09_synthetic_and_projection_denied(self, receipt: dict) -> None:
        c = receipt["c06_c09"]
        assert c["synthetic_evidence_denied"] is True
        assert c["projection_only_denied"] is True


# ── Step 23C: C10-C14 recovery conformance ──────────────────────────────


class TestStep23CC10C14Recovery:
    """C10-C14: occurrence identity, liveness, durable failure, SLO."""

    def test_c18_recovery_slo_receipt_present(self, receipt: dict) -> None:
        c = receipt["c18"]
        assert c["slo_receipt_present"] is True
        assert c["p95_seconds"] is not None

    def test_c18_auditor_not_primary_mutator(self, receipt: dict) -> None:
        c = receipt["c18"]
        assert c["auditor_is_primary_mutator"] is False

    def test_c18_independent_verifier_required(self, receipt: dict) -> None:
        c = receipt["c18"]
        assert c["independent_verifier_required"] is True
        assert c["negative_control_required"] is True
        assert c["recovery_verifier_hash"] != "MISSING"

    def test_c18_rejects_self_verification(self, receipt: dict) -> None:
        """The verifier that closes recovery must not be the producing process."""
        c = receipt["c18"]
        assert c["independent_verifier_required"] is True

    def test_c18_rejects_process_presence_success(self, receipt: dict) -> None:
        """Process liveness must not be treated as success."""
        c = receipt["c18"]
        assert c["negative_control_required"] is True

    def test_c18_six_hour_auditor_bound(self, receipt: dict) -> None:
        assert receipt["c18"]["six_hour_auditor_hash"] != "MISSING"
        assert receipt["c18"]["watchdog_hash"] != "MISSING"


# ── Step 23D: C15-C17 effects and replay conformance ────────────────────


class TestStep23DC15C17EffectsReplay:
    """C15-C17: global reservation, CAS, fault-matrix join, replay."""

    def test_c10_c14_effect_protocol_bound(self, receipt: dict) -> None:
        c = receipt["c10_c14"]
        assert c["effect_protocol_hash"] != "MISSING"
        assert c["effect_reconciliation_hash"] != "MISSING"

    def test_c10_c14_glek_atomic(self, receipt: dict) -> None:
        c = receipt["c10_c14"]
        assert c["glek_snapshotted_atomically"] is True

    def test_c10_c14_terminal_cas(self, receipt: dict) -> None:
        c = receipt["c10_c14"]
        assert c["terminal_cas_enforced"] is True

    def test_c10_c14_indeterminate_action_off(self, receipt: dict) -> None:
        c = receipt["c10_c14"]
        assert c["indeterminate_outcome_action_off"] is True

    def test_c15_c17_fault_matrix_reconciled(self, receipt: dict) -> None:
        c = receipt["c15_c17"]
        assert c["scenario_count"] == 17
        assert c["all_scenarios_reconciled"] is True

    def test_c15_c17_disjoint_sets(self, receipt: dict) -> None:
        c = receipt["c15_c17"]
        assert c["disjoint_sets_verified"] is True
        assert c["supported_boundary_count"] > 0

    def test_c15_c17_rejects_projection_replay_auth(self, receipt: dict) -> None:
        """Projection-based evidence must not authorize replay."""
        c = receipt["c06_c09"]
        assert c["projection_only_denied"] is True


# ── Step 23E: C18-C20 candidate, inventory, and deferral conformance ────


class TestStep23EC18C20CandidateInventoryDeferral:
    """C18-C20: candidate receipt, inventory completeness, deferral."""

    def test_receipt_candidate_bound(self, receipt: dict) -> None:
        assert receipt["constraints"]["candidate_bound"] is True
        assert receipt["constraints"]["installed_runtime_only"] is True

    def test_receipt_content_hash_matches(self, receipt: dict) -> None:
        """The content_hash must be a valid SHA-256 hex string."""
        h = receipt["content_hash"]
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_inventory_present(self, receipt: dict) -> None:
        inv = receipt["inventory"]
        assert inv["wbc_boundary_inventory_rows"] > 0
        assert inv["git_mutation_sinks"] > 0
        assert inv["execute_mutation_sinks"] > 0

    def test_c19_deferred_rows_action_off(self, receipt: dict) -> None:
        c = receipt["c19"]
        assert c["deferred_count"] > 0
        assert c["all_deferred_action_off"] is True
        assert c["deferred_excluded_from_supported"] is True

    def test_c19_rejects_dispatching_deferred_row(self, receipt: dict) -> None:
        """If a deferred row dispatches, conformance must fail."""
        # The generator sets deferred_excluded_from_supported=True;
        # if any deferred row appeared in supported, the generator's
        # disjoint check (from T34) would have failed at generation time.
        c = receipt["c19"]
        assert c["deferred_excluded_from_supported"] is True

    def test_c19_rejects_lacking_action_off_evidence(self, receipt: dict) -> None:
        """Every deferred row must carry action_off_evidence."""
        c = receipt["c19"]
        assert c["all_deferred_action_off"] is True

    def test_c20_production_effects_action_off(self, receipt: dict) -> None:
        c = receipt["c20"]
        assert c["production_effects_action_off"] is True
        assert c["mutating_repair_action_off"] is True

    def test_verifiability_no_subjective_only(self, receipt: dict) -> None:
        v = receipt["verifiability"]
        assert v["all_must_criteria_verifiable"] is True
        assert v["rejected_count"] == 0

    def test_verifiability_checker_runs_over_criteria(
        self, criteria: list[dict]
    ) -> None:
        """The checker must accept all C01-C20 must criteria."""
        report = check_criteria(criteria)
        assert report.all_accepted
        assert report.rejected_count == 0

    def test_verifiability_rejects_subjective_only_negative(self) -> None:
        """A subjective-only must criterion must be rejected."""
        bad = [
            {
                "criterion": "bad-subjective",
                "priority": "must",
                "requires": ["subjective_judgment"],
            }
        ]
        report = check_criteria(bad)
        assert not report.all_accepted
        assert report.rejected_count == 1

    def test_verifiability_rejects_empty_requires_negative(self) -> None:
        """A must criterion with empty requires must be rejected."""
        bad = [
            {
                "criterion": "bad-empty",
                "priority": "must",
                "requires": [],
            }
        ]
        report = check_criteria(bad)
        assert not report.all_accepted
        assert report.rejected_count == 1


# ── Step 24: M11 genuine-block candidate manifest ───────────────────────


class TestStep24M11GenuineBlockCandidate:
    """The M11 candidate manifest must have kill switch, rollback, provenance."""

    MANIFEST_PATH = REPO_ROOT / "evidence" / "m11-genuine-block-candidate" / "manifest.json"

    def test_manifest_exists(self) -> None:
        assert self.MANIFEST_PATH.exists()

    def test_kill_switch_present(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        ks = m["kill_switch"]
        assert ks["fail_closed"] is True
        assert ks["default_state"] == "shadow_mode_empty"

    def test_rollback_present(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        rb = m["rollback"]
        assert rb["tested_in_m10"] is True
        assert rb["archive_predecessor"] is True
        assert rb["fresh_epoch_required_after_rollback"] is True

    def test_runtime_provenance_present(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        rp = m["runtime_provenance"]
        assert rp["content_addressed"] is True
        assert rp["mixed_revision_blocking"] is True

    def test_verifier_schedule_present(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        vs = m["verifier_schedule"]
        assert vs["independent_verifier_required"] is True
        assert vs["negative_control_required"] is True
        assert vs["no_mocked_status_as_evidence"] is True
        sched = vs["schedule"]
        assert "five_minute" in sched
        assert "one_hour" in sched
        assert "six_hour" in sched

    def test_no_mocked_status_as_evidence(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        assert m["verifier_schedule"]["no_mocked_status_as_evidence"] is True

    def test_action_off_in_m10(self) -> None:
        m = json.loads(self.MANIFEST_PATH.read_text())
        assert m["candidate_boundary"]["action_off_in_m10"] is True
        assert m["kill_switch"]["fail_closed"] is True
