"""Tests for criteria_verifiability — machine-verifiable acceptance criteria gate."""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.criteria_verifiability import (
    CriterionCheck,
    CriteriaCheckReport,
    MACHINE_CAPABILITIES,
    HUMAN_CAPABILITIES,
    check_criteria,
    must_criteria_are_verifiable,
    reject_subjective_criteria,
)


# ── Helper builders ─────────────────────────────────────────────────────────


def _must_criteria(*requires: str) -> list[dict]:
    """Build a list with one must criterion."""
    return [
        {
            "criterion": "test-criterion",
            "priority": "must",
            "requires": list(requires),
        }
    ]


def _criterion(
    idx: int = 0,
    criterion_id: str = "C01",
    priority: str = "must",
    requires: tuple[str, ...] = (),
) -> dict:
    return {
        "criterion": criterion_id,
        "priority": priority,
        "requires": list(requires),
    }


# ── Positive tests (machine-verifiable criteria are accepted) ───────────────


def test_empty_criteria_list_accepted() -> None:
    """An empty criteria list has no rejections."""
    report = check_criteria([])
    assert report.all_accepted
    assert report.rejected_count == 0
    assert report.accepted_count == 0


def test_must_with_read_files_accepted() -> None:
    report = check_criteria(_must_criteria("read_files"))
    assert report.all_accepted
    assert report.accepted_count == 1


def test_must_with_run_tests_accepted() -> None:
    report = check_criteria(_must_criteria("run_tests"))
    assert report.all_accepted


def test_must_with_run_shell_accepted() -> None:
    report = check_criteria(_must_criteria("run_shell"))
    assert report.all_accepted


def test_must_with_parse_diff_accepted() -> None:
    report = check_criteria(_must_criteria("parse_diff"))
    assert report.all_accepted


def test_must_with_read_build_output_accepted() -> None:
    report = check_criteria(_must_criteria("read_build_output"))
    assert report.all_accepted


def test_must_with_run_linter_accepted() -> None:
    report = check_criteria(_must_criteria("run_linter"))
    assert report.all_accepted


def test_must_with_multiple_machine_caps_accepted() -> None:
    report = check_criteria(_must_criteria("read_files", "run_tests", "parse_diff"))
    assert report.all_accepted
    assert report.accepted_count == 1


def test_must_with_machine_and_human_caps_accepted() -> None:
    """A must criterion with both machine and human caps is accepted."""
    report = check_criteria(_must_criteria("read_files", "subjective_judgment"))
    assert report.all_accepted


def test_non_must_priorities_not_rejected() -> None:
    """Criteria with should/could/info priority are not subject to the gate."""
    for priority in ("should", "could", "info", "optional"):
        report = check_criteria([
            {"criterion": f"test-{priority}", "priority": priority, "requires": []}
        ])
        assert report.all_accepted, f"priority={priority} should be accepted"
        assert report.rejected_count == 0


# ── Negative tests (subjective-only must criteria are rejected) ─────────────


def test_must_with_empty_requires_rejected() -> None:
    report = check_criteria(_must_criteria())
    assert not report.all_accepted
    assert report.rejected_count == 1
    check = report.checks[0]
    assert check.verdict == "rejected_subjective"
    assert "empty requires" in check.reason.lower()


def test_must_with_subjective_judgment_only_rejected() -> None:
    report = check_criteria(_must_criteria("subjective_judgment"))
    assert not report.all_accepted
    assert report.rejected_count == 1
    check = report.checks[0]
    assert check.verdict == "rejected_subjective"
    assert "subjective" in check.reason.lower()


def test_must_with_human_review_only_rejected() -> None:
    report = check_criteria(_must_criteria("human_review"))
    assert not report.all_accepted
    assert report.rejected_count == 1


def test_must_with_multiple_human_caps_rejected() -> None:
    report = check_criteria(_must_criteria("subjective_judgment", "human_review", "human_approval"))
    assert not report.all_accepted
    assert report.rejected_count == 1


def test_must_with_unknown_capability_rejected() -> None:
    """Unknown capabilities not in machine or human sets fail closed."""
    report = check_criteria(_must_criteria("some_unknown_cap"))
    assert not report.all_accepted
    assert report.rejected_count == 1


def test_reject_subjective_criteria_returns_reasons() -> None:
    reasons = reject_subjective_criteria(_must_criteria("subjective_judgment"))
    assert len(reasons) == 1
    assert "subjective" in reasons[0].lower()


def test_reject_subjective_criteria_empty_on_valid() -> None:
    reasons = reject_subjective_criteria(_must_criteria("read_files", "run_tests"))
    assert reasons == []


# ── C01-C20 positive coverage ───────────────────────────────────────────────


def test_C01_launch_identity_criteria_accepted() -> None:
    """C01: exact source/runtime binding requires run_shell + read_files."""
    criteria = [
        {
            "criterion": "C01: Launch manifest validation blocks mismatched source/runtime/seed",
            "priority": "must",
            "requires": ["run_shell", "read_files", "parse_diff"],
        }
    ]
    report = check_criteria(criteria)
    assert report.all_accepted


def test_C02_seed_epoch_criteria_accepted() -> None:
    """C02: seed epoch attestation requires run_tests + read_files."""
    criteria = [
        {
            "criterion": "C02: Seed epoch is attested and archived predecessor epochs are preserved",
            "priority": "must",
            "requires": ["run_tests", "read_files"],
        }
    ]
    report = check_criteria(criteria)
    assert report.all_accepted


def test_C03_source_revision_binding_accepted() -> None:
    """C03: exact source revision binding requires run_shell + parse_diff."""
    criteria = [
        {
            "criterion": "C03: Every executable consumer attests to one exact content-addressed source binding",
            "priority": "must",
            "requires": ["run_shell", "read_files", "parse_diff"],
        }
    ]
    report = check_criteria(criteria)
    assert report.all_accepted


def test_C04_schema_parity_accepted() -> None:
    """C04: strict schema parity requires run_tests + parse_diff + read_files."""
    criteria = [
        {
            "criterion": "C04: Strict schema parity rejects unknown fields across all phases",
            "priority": "must",
            "requires": ["run_tests", "parse_diff", "read_files"],
        }
    ]
    report = check_criteria(criteria)
    assert report.all_accepted


def test_C15_fault_matrix_accepted() -> None:
    """C15: fault matrix coverage requires run_tests + read_files."""
    criteria = [
        {
            "criterion": "C15: F01-F17 fault matrix covers every injection edge",
            "priority": "must",
            "requires": ["run_tests", "read_files"],
        }
    ]
    report = check_criteria(criteria)
    assert report.all_accepted


def test_multiple_must_criteria_mixed_accept_reject() -> None:
    """Mix of valid and subjective-only must criteria."""
    criteria = [
        {
            "criterion": "C01: valid machine check",
            "priority": "must",
            "requires": ["run_tests", "read_files"],
        },
        {
            "criterion": "CX: subjective-only",
            "priority": "must",
            "requires": ["subjective_judgment"],
        },
        {
            "criterion": "C02: another valid check",
            "priority": "must",
            "requires": ["run_shell"],
        },
    ]
    report = check_criteria(criteria)
    assert not report.all_accepted
    assert report.accepted_count == 2
    assert report.rejected_count == 1


# ── Former imported-decision negatives ─────────────────────────────────────


def test_former_subjective_imported_decision_rejected() -> None:
    """A criterion that was previously accepted as subjective_judgment must now be rejected."""
    criteria = [
        {
            "criterion": "Imported decision adherence",
            "priority": "must",
            "requires": ["subjective_judgment"],
        }
    ]
    report = check_criteria(criteria)
    assert not report.all_accepted


def test_former_empty_requires_must_rejected() -> None:
    """A must criterion with no requires (previously accepted) must be rejected."""
    criteria = [
        {
            "criterion": "Some imported decision",
            "priority": "must",
            "requires": [],
        }
    ]
    report = check_criteria(criteria)
    assert not report.all_accepted


# ── must_criteria_are_verifiable helper ─────────────────────────────────────


def test_must_criteria_are_verifiable_true() -> None:
    assert must_criteria_are_verifiable(_must_criteria("read_files", "run_tests"))


def test_must_criteria_are_verifiable_false() -> None:
    assert not must_criteria_are_verifiable(_must_criteria("subjective_judgment"))


# ── Report structure ────────────────────────────────────────────────────────


def test_report_fields_populated() -> None:
    report = check_criteria(_must_criteria("read_files"))
    assert len(report.checks) == 1
    check = report.checks[0]
    assert isinstance(check, CriterionCheck)
    assert check.verdict == "acceptable"
    assert check.priority == "must"
    assert check.requires == ("read_files",)
    assert check.index == 0


def test_rejected_report_fields_populated() -> None:
    report = check_criteria(_must_criteria("subjective_judgment"))
    check = report.checks[0]
    assert check.verdict == "rejected_subjective"
    assert check.priority == "must"
    assert check.requires == ("subjective_judgment",)


# ── Custom capability sets ──────────────────────────────────────────────────


def test_custom_machine_caps() -> None:
    """Custom machine capability sets are respected."""
    custom_machine = frozenset({"custom_cap"})
    criteria = _must_criteria("custom_cap")
    report = check_criteria(criteria, machine_caps=custom_machine)
    assert report.all_accepted


def test_custom_machine_caps_reject_unknown() -> None:
    """When custom_machine excludes a cap, it fails closed."""
    custom_machine = frozenset({"custom_cap"})
    criteria = _must_criteria("read_files")
    report = check_criteria(criteria, machine_caps=custom_machine)
    assert not report.all_accepted
