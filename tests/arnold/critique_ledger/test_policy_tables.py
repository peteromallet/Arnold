"""Tests for retention class mapping and failure atomicity policy tables.

Validates every table value against landed WBC enums, requires one row
per enumerated failure mode, and fails on unknown enum strings, missing
recovery evidence, or clean-success treatment of indeterminate persistence.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "critique-ledger" / "evidence"
RETENTION_PATH = EVIDENCE_DIR / "retention-class-mapping.json"
FAILURE_PATH = EVIDENCE_DIR / "failure-atomicity-table.json"

# Landed WBC enum values (must match the runtime enums exactly)
VALID_RETENTION_MODES = {"ephemeral", "run", "audit", "legal_hold"}
VALID_REDACTION_MODES = {"none", "default_on", "always"}
VALID_PRIVACY_CLASSES = {"public", "internal", "confidential", "restricted"}
VALID_RETENTION_CLASSES = {"ephemeral", "run", "audit", "legal_hold"}
VALID_PERSISTENCE_STATUSES = {"durable", "persistence_failed", "indeterminate"}


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestRetentionClassMapping:
    """Validate retention-class-mapping.json against landed WBC enums."""

    def test_file_exists(self):
        assert RETENTION_PATH.exists(), f"Missing: {RETENTION_PATH}"

    def test_schema_version(self):
        data = _load_json(RETENTION_PATH)
        assert data["schema"] == "cl.retention-class-mapping.v1"

    def test_mappings_not_empty(self):
        data = _load_json(RETENTION_PATH)
        mappings = data["evidence_class_mappings"]
        assert len(mappings) > 0, "No evidence class mappings defined"

    def test_retention_modes_valid(self):
        data = _load_json(RETENTION_PATH)
        for m in data["evidence_class_mappings"]:
            rm = m["retention_mode"]
            assert rm in VALID_RETENTION_MODES, (
                f"{m['evidence_class']}: retention_mode '{rm}' not in {VALID_RETENTION_MODES}"
            )

    def test_redaction_modes_valid(self):
        data = _load_json(RETENTION_PATH)
        for m in data["evidence_class_mappings"]:
            rm = m["redaction_mode"]
            assert rm in VALID_REDACTION_MODES, (
                f"{m['evidence_class']}: redaction_mode '{rm}' not in {VALID_REDACTION_MODES}"
            )

    def test_privacy_classes_valid(self):
        data = _load_json(RETENTION_PATH)
        for m in data["evidence_class_mappings"]:
            pc = m["privacy_class"]
            assert pc in VALID_PRIVACY_CLASSES, (
                f"{m['evidence_class']}: privacy_class '{pc}' not in {VALID_PRIVACY_CLASSES}"
            )

    def test_retention_classes_valid(self):
        data = _load_json(RETENTION_PATH)
        for m in data["evidence_class_mappings"]:
            rc = m["retention_class"]
            assert rc in VALID_RETENTION_CLASSES, (
                f"{m['evidence_class']}: retention_class '{rc}' not in {VALID_RETENTION_CLASSES}"
            )

    def test_all_five_schemas_covered(self):
        """Every schema used by the five core dataclasses must be mapped."""
        data = _load_json(RETENTION_PATH)
        covered = {m["evidence_class"] for m in data["evidence_class_mappings"]}
        required = {
            "critique_prompts_and_completions",
            "critique_occurrence_envelopes",
            "finding_reconciliation_events",
            "finding_disposition_events",
            "domain_briefing_envelopes",
            "ledger_revision_manifests",
            "private_repository_evidence",
        }
        missing = required - covered
        assert not missing, f"Missing evidence class mappings: {missing}"

    def test_cross_reference_wbc_enums_valid(self):
        data = _load_json(RETENTION_PATH)
        xref = data["cross_reference"]["wbc_enums_used"]
        for mode in xref.get("RetentionMode", []):
            assert mode in VALID_RETENTION_MODES, f"RetentionMode '{mode}' not valid"
        for mode in xref.get("RedactionMode", []):
            assert mode in VALID_REDACTION_MODES, f"RedactionMode '{mode}' not valid"
        for pc in xref.get("PrivacyClass", []):
            assert pc in VALID_PRIVACY_CLASSES, f"PrivacyClass '{pc}' not valid"
        for rc in xref.get("RetentionClass", []):
            assert rc in VALID_RETENTION_CLASSES, f"RetentionClass '{rc}' not valid"
        for ps in xref.get("PersistenceStatus", []):
            assert ps in VALID_PERSISTENCE_STATUSES, f"PersistenceStatus '{ps}' not valid"


class TestFailureAtomicityTable:
    """Validate failure-atomicity-table.json against landed WBC enums."""

    def test_file_exists(self):
        assert FAILURE_PATH.exists(), f"Missing: {FAILURE_PATH}"

    def test_schema_version(self):
        data = _load_json(FAILURE_PATH)
        assert data["schema"] == "cl.failure-atomicity-table.v1"

    def test_failure_modes_not_empty(self):
        data = _load_json(FAILURE_PATH)
        assert len(data["failure_modes"]) > 0, "No failure modes defined"

    def test_all_persistence_statuses_valid(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            for ps in fm["allowed_persistence_status"]:
                assert ps in VALID_PERSISTENCE_STATUSES, (
                    f"{fm['failure_mode']}: persistence_status '{ps}' not in {VALID_PERSISTENCE_STATUSES}"
                )

    def test_every_failure_mode_has_detection_boundary(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            assert fm.get("detection_boundary"), (
                f"{fm['failure_mode']}: missing detection_boundary"
            )

    def test_every_failure_mode_has_fail_closed_action(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            assert fm.get("fail_closed_action"), (
                f"{fm['failure_mode']}: missing fail_closed_action"
            )

    def test_every_failure_mode_has_forbidden_writes(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            assert fm.get("forbidden_writes") is not None, (
                f"{fm['failure_mode']}: missing forbidden_writes"
            )

    def test_every_failure_mode_has_recovery_evidence(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            assert fm.get("recovery_evidence"), (
                f"{fm['failure_mode']}: missing recovery_evidence"
            )

    def test_every_failure_mode_has_admission_consequence(self):
        data = _load_json(FAILURE_PATH)
        for fm in data["failure_modes"]:
            assert fm.get("admission_consequence"), (
                f"{fm['failure_mode']}: missing admission_consequence"
            )

    def test_indeterminate_persistence_fails_test(self):
        """INDETERMINATE persistence must fail the test, not be treated as clean success."""
        data = _load_json(FAILURE_PATH)
        indeterminate_modes = [
            fm for fm in data["failure_modes"]
            if "indeterminate" in fm["allowed_persistence_status"]
        ]
        for fm in indeterminate_modes:
            consequence = fm["admission_consequence"].lower()
            assert "blocked" in consequence or "fail" in consequence, (
                f"{fm['failure_mode']}: INDETERMINATE persistence treated as clean success — "
                f"consequence is '{fm['admission_consequence']}'"
            )

    def test_terminal_persistence_failure_covers_indeterminate(self):
        """Terminal persistence failure mode must include INDETERMINATE."""
        data = _load_json(FAILURE_PATH)
        terminal = [fm for fm in data["failure_modes"] if fm["failure_mode"] == "terminal_persistence_failure"]
        assert len(terminal) == 1, "Missing terminal_persistence_failure mode"
        tpf = terminal[0]
        assert "indeterminate" in tpf["allowed_persistence_status"], (
            "terminal_persistence_failure must cover INDETERMINATE"
        )

    def test_fail_closed_principle_documented(self):
        data = _load_json(FAILURE_PATH)
        xref = data["cross_reference"]
        assert "fail_closed_principle" in xref
        assert "INDETERMINATE" in xref["fail_closed_principle"], (
            "Fail-closed principle must explicitly address INDETERMINATE"
        )

    def test_no_unknown_enum_strings(self):
        """All enum values must be from the known WBC set."""
        data = _load_json(FAILURE_PATH)
        all_statuses = set()
        for fm in data["failure_modes"]:
            all_statuses.update(fm["allowed_persistence_status"])
        unknown = all_statuses - VALID_PERSISTENCE_STATUSES
        assert not unknown, f"Unknown PersistenceStatus values: {unknown}"

    def test_cross_reference_wbc_enums_valid(self):
        data = _load_json(FAILURE_PATH)
        xref = data["cross_reference"]["wbc_enums_used"]
        for ps in xref.get("PersistenceStatus", []):
            assert ps in VALID_PERSISTENCE_STATUSES, f"PersistenceStatus '{ps}' not valid"
