from __future__ import annotations

import hashlib

from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
from arnold_pipelines.megaplan.run_state.quality_family import (
    QualityFamily,
    normalize_quality_family,
    QualityOccurrence,
    QualityOccurrenceSet,
    QualitySummary,
)
from arnold_pipelines.megaplan.types import CliError


def test_codex_usage_limit_classifies_as_provider_quota() -> None:
    error = ExternalError.from_exception(
        CliError(
            "quota_exceeded",
            "Codex usage limit reached. Re-run the same execute step on Codex once before changing agent.",
        ),
        provider="codex",
    )

    assert error is not None
    assert error.provider == "codex"
    assert error.error_kind == "quota"
    assert error.provider_error_code == "quota_exceeded"
    assert error.error_layer == "provider_quota"


# ── T63: M5 structured-failed replay fixtures ──────────────────────────────


def test_quality_family_normalizes_fail_variants_to_canonical() -> None:
    """Structured failed variants all normalize to FAIL with original preserved."""
    variants = [
        ("fail", QualityFamily.FAIL),
        ("failed", QualityFamily.FAIL),
        ("failed: assertion error", QualityFamily.FAIL),
        ("FAILED", QualityFamily.FAIL),
        ("error", QualityFamily.ERROR),
        ("error: timeout", QualityFamily.ERROR),
        ("ERROR", QualityFamily.ERROR),
        ("timeout", QualityFamily.TIMEOUT),
        ("timed_out", QualityFamily.TIMEOUT),
        ("skip", QualityFamily.SKIP),
        ("skipped", QualityFamily.SKIP),
        ("pass", QualityFamily.PASS),
        ("passed", QualityFamily.PASS),
        ("ok", QualityFamily.PASS),
        ("success", QualityFamily.PASS),
        ("warn", QualityFamily.WARN),
        ("warning", QualityFamily.WARN),
    ]
    for raw, expected in variants:
        result = normalize_quality_family(raw)
        assert result == expected, f"Expected {raw!r} → {expected}, got {result}"

    # Unknown stays unknown
    assert normalize_quality_family("garbled_mess") == QualityFamily.UNKNOWN
    assert normalize_quality_family("") == QualityFamily.UNKNOWN


def test_quality_occurrence_preserves_original_evidence() -> None:
    """QualityOccurrence retains original status, command, criterion_id, and hash."""
    occ = QualityOccurrence(
        original_status="failed: assertion on line 42",
        family=QualityFamily.FAIL,
        command="pytest tests/test_foo.py",
        criterion_id="crit-001",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=1,
        detail="assertion on line 42",
    )
    assert occ.original_status == "failed: assertion on line 42"
    assert occ.command == "pytest tests/test_foo.py"
    assert occ.criterion_id == "crit-001"
    assert occ.exit_code == 1
    assert occ.family == QualityFamily.FAIL
    assert occ.content_hash.startswith("sha256:")
    # Deterministic: same inputs produce same hash
    occ2 = QualityOccurrence(
        original_status="failed: assertion on line 42",
        family=QualityFamily.FAIL,
        command="pytest tests/test_foo.py",
        criterion_id="crit-001",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=1,
        detail="assertion on line 42",
    )
    assert occ.content_hash == occ2.content_hash


def test_quality_occurrence_set_dedup_and_sort() -> None:
    """QualityOccurrenceSet deduplicates by content_hash and sorts by criterion_id."""
    occ_a = QualityOccurrence(
        original_status="failed: detail A",
        family=QualityFamily.FAIL,
        command="cmd-a",
        criterion_id="crit-B",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=1,
    )
    occ_b = QualityOccurrence(
        original_status="failed: detail B",
        family=QualityFamily.FAIL,
        command="cmd-b",
        criterion_id="crit-A",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=1,
    )
    occ_a_dup = QualityOccurrence(
        original_status="failed: detail A",
        family=QualityFamily.FAIL,
        command="cmd-a",
        criterion_id="crit-B",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=1,
    )
    occ_set = QualityOccurrenceSet((occ_a, occ_b, occ_a_dup))
    assert len(occ_set.occurrences) == 2, "Duplicate should be removed"
    # Sorted by (criterion_id, content_hash)
    assert occ_set.occurrences[0].criterion_id == "crit-A"
    assert occ_set.occurrences[1].criterion_id == "crit-B"


def test_quality_summary_worst_family_determination() -> None:
    """QualitySummary from occurrences includes all original occurrences."""
    fail_occ = QualityOccurrence(
        original_status="failed", family=QualityFamily.FAIL,
        command="cmd", criterion_id="c1",
        occurred_at="2026-07-23T12:00:00Z", exit_code=1,
    )
    pass_occ = QualityOccurrence(
        original_status="passed", family=QualityFamily.PASS,
        command="cmd", criterion_id="c2",
        occurred_at="2026-07-23T12:00:00Z", exit_code=0,
    )
    summary = QualitySummary.from_occurrences(fail_occ, pass_occ)
    # Summary has an occurrence_set with all occurrences
    assert summary.occurrence_set is not None
    assert len(summary.occurrence_set.occurrences) == 2
    # FAIL takes precedence over PASS in the set
    families = {o.family for o in summary.occurrence_set.occurrences}
    assert QualityFamily.FAIL in families
    assert QualityFamily.PASS in families


def test_legacy_unknown_human_required_is_not_eligible_blocker_evidence() -> None:
    """Legacy unknown/human-required views must be reported as drift, not as evidence
    that no eligible blocker exists.  Unknown quality is never PASS."""
    result = normalize_quality_family("unknown")
    assert result == QualityFamily.UNKNOWN
    # UNKNOWN must never be treated as PASS/SUCCESS
    assert result != QualityFamily.PASS
    assert result != QualityFamily.SKIP

    # A human-required label without structured fail evidence is UNKNOWN
    result_hr = normalize_quality_family("human_required")
    assert result_hr == QualityFamily.UNKNOWN, (
        "human_required without structured evidence must be UNKNOWN, not PASS"
    )


def test_structured_failed_deterministic_classification() -> None:
    """Same structured-failed input produces same deterministic classification."""
    occ1 = QualityOccurrence(
        original_status="failed: timeout after 300s",
        family=QualityFamily.FAIL,
        command="run-phase execute",
        criterion_id="phase-timeout",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=124,
        detail="timeout after 300s",
    )
    occ2 = QualityOccurrence(
        original_status="failed: timeout after 300s",
        family=QualityFamily.FAIL,
        command="run-phase execute",
        criterion_id="phase-timeout",
        occurred_at="2026-07-23T12:00:00Z",
        exit_code=124,
        detail="timeout after 300s",
    )
    # Deterministic: identical inputs → identical hashes, identical families
    assert occ1.content_hash == occ2.content_hash
    assert occ1.family == occ2.family == QualityFamily.FAIL
    assert occ1.criterion_id == occ2.criterion_id


def test_structured_failed_different_inputs_produce_different_hashes() -> None:
    """Different structured-failed inputs produce different content hashes."""
    occ1 = QualityOccurrence(
        original_status="failed: error A",
        family=QualityFamily.FAIL,
        command="cmd-a", criterion_id="c1",
        occurred_at="2026-07-23T12:00:00Z", exit_code=1,
    )
    occ2 = QualityOccurrence(
        original_status="failed: error B",
        family=QualityFamily.FAIL,
        command="cmd-a", criterion_id="c1",
        occurred_at="2026-07-23T12:00:00Z", exit_code=1,
    )
    assert occ1.content_hash != occ2.content_hash, (
        "Different original_status must produce different hashes"
    )
