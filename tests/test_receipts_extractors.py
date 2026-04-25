from __future__ import annotations

import json
import logging
from pathlib import Path

from megaplan.receipts.drift import ScopeDriftReport
from megaplan.receipts.extractors import (
    critique_metrics,
    execute_metrics,
    extract_for_phase,
    finalize_metrics,
    gate_metrics,
    load_and_extract,
    plan_metrics,
    review_metrics,
)


PLAN_KEYS = {
    "step_count",
    "task_count",
    "files_referenced",
    "oos_file_count",
    "plan_chars",
    "plan_words",
    "success_criteria_count",
    "must_vs_info_ratio",
    "structure_warnings_count",
}
CRITIQUE_KEYS = {
    "findings_per_check",
    "severity_distribution",
    "clean_checks_count",
    "flagged_checks_count",
    "rubber_stamp_ratio",
}
GATE_KEYS = {"recommendation", "blocking_flags_resolved", "blocking_flags_remaining", "override_forced"}
FINALIZE_KEYS = {"tasks_count", "sense_checks_count", "per_task_evidence_file_count"}
EXECUTE_KEYS = {
    "files_claimed",
    "files_in_diff",
    "scope_drift_files_added",
    "scope_drift_files_missing",
    "loc_added",
    "loc_removed",
    "loc_added_outside_claimed",
    "commands_run_count",
    "advisory_issues_count",
    "blocking_issues_count",
    "per_task_files_claimed_count",
}
REVIEW_KEYS = {
    "review_verdict",
    "task_verdicts_count",
    "total_tasks",
    "sense_check_verdicts_count",
    "total_sense_checks",
    "missing_evidence_count",
    "rework_items_count",
    "criteria_pass_count",
    "criteria_deferred_count",
}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_receipt_extractors_return_expected_metric_keys(tmp_path: Path) -> None:
    plan_text = """
    ## Step 1: Update `megaplan/workers.py`
    Task 1 touches `megaplan/workers.py` and `megaplan/receipts/schema.py`.
    ## Step 2: Add tests
    Success criteria:
    - must: receipts are stable
    - info: no structure_warning
    """
    critique_payload = {
        "checks": [
            {"id": "correctness", "findings": [{"severity": "significant"}]},
            {"id": "scope", "findings": []},
        ]
    }
    gate_payload = {
        "recommendation": "proceed",
        "blocking_flags_resolved": ["FLAG-1"],
        "blocking_flags_remaining": [],
        "override_forced": False,
    }
    finalize_payload = {
        "tasks": [
            {"id": "T1", "evidence_files": ["a.txt"], "files_changed": ["a.py", "b.py"]},
            {"id": "T2", "evidence_files": ["b.txt", "c.txt"], "files_changed": ["c.py"]},
        ],
        "sense_checks": [{"id": "SC1"}, {"id": "SC2"}],
    }
    execute_payload = {
        "files_changed": ["a.py", "b.py"],
        "files_in_diff": ["a.py", "b.py", "extra.py"],
        "task_updates": [
            {"id": "T1", "files_changed": ["a.py"], "commands_run": ["pytest tests/test_a.py"]},
            {"id": "T2", "files_changed": ["b.py"], "commands_run": []},
        ],
        "advisory_issues": [{"id": "A1"}],
        "blocking_issues": [],
    }
    review_payload = {
        "verdict": "approved",
        "task_verdicts": [{"id": "T1", "missing_evidence": [], "rework_items": []}],
        "sense_check_verdicts": [{"id": "SC1"}],
        "criteria": [{"verdict": "passed"}, {"verdict": "deferred"}],
        "rework_items": [],
    }
    drift = ScopeDriftReport(
        files_added=["extra.py"],
        files_missing=[],
        loc_added=25,
        loc_removed=0,
        loc_added_outside_claimed=25,
        severity="high",
    )

    (tmp_path / "plan_v1.md").write_text(plan_text, encoding="utf-8")
    _write_json(tmp_path / "critique_v1.json", critique_payload)
    _write_json(tmp_path / "gate_v1.json", gate_payload)
    _write_json(tmp_path / "finalize.json", finalize_payload)
    _write_json(tmp_path / "execution.json", execute_payload)
    _write_json(tmp_path / "review.json", review_payload)

    assert PLAN_KEYS <= plan_metrics({"plan": plan_text}).keys()
    assert CRITIQUE_KEYS <= critique_metrics(critique_payload).keys()
    assert GATE_KEYS <= gate_metrics(gate_payload).keys()
    assert FINALIZE_KEYS <= finalize_metrics(finalize_payload).keys()
    assert EXECUTE_KEYS <= execute_metrics(execute_payload, drift).keys()
    assert REVIEW_KEYS <= review_metrics(review_payload).keys()

    assert PLAN_KEYS <= load_and_extract(tmp_path, "plan", 1).keys()
    assert CRITIQUE_KEYS <= load_and_extract(tmp_path, "critique", 1).keys()
    assert GATE_KEYS <= load_and_extract(tmp_path, "gate", 1).keys()
    assert FINALIZE_KEYS <= load_and_extract(tmp_path, "finalize", 1).keys()
    assert EXECUTE_KEYS <= load_and_extract(tmp_path, "execute", 1, drift_report=drift).keys()
    assert REVIEW_KEYS <= load_and_extract(tmp_path, "review", 1).keys()


def test_extract_for_phase_prep_and_revise_return_empty_without_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert extract_for_phase("prep", {"ignored": True}) == {}
        assert extract_for_phase("revise", {"ignored": True}) == {}
    assert caplog.records == []


def test_extract_for_phase_covers_all_finish_step_phases() -> None:
    assert extract_for_phase("plan", {"plan": "## Step 1: Update a.py"}).keys() >= PLAN_KEYS
    assert extract_for_phase("prep", {}) == {}
    assert extract_for_phase("critique", {"checks": []}).keys() >= CRITIQUE_KEYS
    assert extract_for_phase("revise", {}) == {}
    assert extract_for_phase("gate", {}).keys() >= GATE_KEYS
    assert extract_for_phase("finalize", {"tasks": [], "sense_checks": []}).keys() >= FINALIZE_KEYS
    assert extract_for_phase("execute", {}, drift_report=None).keys() >= EXECUTE_KEYS
    assert extract_for_phase("review", {}).keys() >= REVIEW_KEYS
    assert extract_for_phase("unknown", {}) == {}


def test_malformed_payloads_return_extractor_error() -> None:
    malformed = []
    for result in (
        plan_metrics(malformed),
        critique_metrics(malformed),
        gate_metrics(malformed),
        finalize_metrics(malformed),
        execute_metrics(malformed),
        review_metrics(malformed),
    ):
        assert "_extractor_error" in result
