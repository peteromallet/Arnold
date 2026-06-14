from __future__ import annotations

import json
import logging
from pathlib import Path

from arnold.pipelines.megaplan.receipts.drift import ScopeDriftReport
from arnold.pipelines.megaplan.receipts.extractors import (
    critique_metrics,
    execute_metrics,
    extract_for_phase,
    finalize_metrics,
    gate_metrics,
    load_and_extract,
    prep_metrics,
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
PREP_KEYS = {
    "skip",
    "task_summary_present",
    "key_evidence_count",
    "relevant_code_count",
    "test_expectations_count",
    "constraints_count",
    "suggested_approach_present",
    "primary_criterion_present",
    "area_count",
    "fanout_count",
    "area_cap",
    "cap_applied",
    "status_counts",
    "completed_count",
    "partial_count",
    "timed_out_count",
    "error_count",
    "missed_units",
    "missed_units_count",
    "total_cost_usd",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "elapsed_time_ms",
    "files",
    "files_count",
    "code_refs",
    "code_refs_count",
    "per_unit_count",
    "per_unit_statuses",
    "gap_notes_count",
    "contradiction_notes_count",
    "overlap_groups_count",
    "cross_reference_performed",
    "cross_reference_missing_files_count",
    "model_resolution_trace",
    "critique_flags_count",
    "revise_cycles_count",
    "execution_failure_categories",
    "human_override_count",
}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_receipt_extractors_return_expected_metric_keys(tmp_path: Path) -> None:
    prep_payload = {
        "skip": False,
        "task_summary": "Investigate the prep orchestration.",
        "key_evidence": [{"point": "prep exists", "source": "repo", "relevance": "high"}],
        "relevant_code": [{"file_path": "megaplan/orchestration/prep_research.py", "why": "main flow", "functions": ["run_prep_orchestration"]}],
        "test_expectations": [{"test_id": "tests/test_prep.py", "what_it_checks": "prep orchestration", "status": "pass_to_pass"}],
        "constraints": ["Keep PLAN artifact names stable."],
        "suggested_approach": "Use triage, fan-out, then distill.",
    }
    prep_metrics_payload = {
        "area_count": 6,
        "fanout_count": 4,
        "completed_count": 1,
        "partial_count": 1,
        "timed_out_count": 1,
        "error_count": 1,
        "missed_units": ["a2", "a3"],
        "total_cost_usd": 0.6,
        "prompt_tokens": 9,
        "completion_tokens": 12,
        "total_tokens": 21,
        "elapsed_time_ms": 210,
        "files": ["megaplan/a.py", "megaplan/b.py"],
        "code_refs": ["pkg.a0", "pkg.a1"],
        "gap_notes": ["a2 timed out"],
        "contradiction_notes": ["a.py overlaps"],
        "overlap_groups": [{"kind": "file", "value": "megaplan/a.py", "areas": ["a0", "a1"]}],
        "cross_reference": {
            "performed": True,
            "checked_files": ["megaplan/a.py"],
            "existing_files": ["megaplan/a.py"],
            "missing_files": [],
            "shared_files": [],
        },
        "stage_metrics": {
            "triage": {"cost_usd": 0.1, "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "elapsed_time_ms": 10},
            "fanout": {"cost_usd": 0.2, "prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7, "elapsed_time_ms": 110},
            "distill": {"cost_usd": 0.3, "prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11, "elapsed_time_ms": 90},
        },
        "per_unit": [
            {"area": "a0", "status": "complete", "elapsed_time_ms": 30, "files": ["megaplan/a.py"], "code_refs": ["pkg.a0"]},
            {"area": "a1", "status": "partial", "elapsed_time_ms": 40, "files": ["megaplan/b.py"], "code_refs": ["pkg.a1"]},
            {"area": "a2", "status": "timed_out", "elapsed_time_ms": 50, "files": [], "code_refs": []},
            {"area": "a3", "status": "error", "elapsed_time_ms": 60, "files": [], "code_refs": []},
        ],
        "critique_flags_count": 0,
        "revise_cycles_count": 0,
        "execution_failure_categories": [],
        "human_override_count": 0,
    }
    prep_trace = {
        "flat_prep_input": "codex",
        "resolved_stage_models": {
            "triage": "codex",
            "fanout": "hermes:deepseek:deepseek-v4-flash",
            "distill": "codex",
        },
        "canonical_fallback_used": {"triage": False, "fanout": True, "distill": False},
    }
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
    _write_json(tmp_path / "prep.json", prep_payload)
    _write_json(tmp_path / "prep_metrics.json", prep_metrics_payload)
    _write_json(
        tmp_path / "state.json",
        {"config": {"prep_model_resolver_trace": prep_trace}},
    )
    _write_json(tmp_path / "critique_v1.json", critique_payload)
    _write_json(tmp_path / "gate_v1.json", gate_payload)
    _write_json(tmp_path / "finalize.json", finalize_payload)
    _write_json(tmp_path / "execution.json", execute_payload)
    _write_json(tmp_path / "review.json", review_payload)

    assert PREP_KEYS <= prep_metrics(prep_payload, prep_metrics_payload, prep_trace).keys()
    assert PLAN_KEYS <= plan_metrics({"plan": plan_text}).keys()
    assert CRITIQUE_KEYS <= critique_metrics(critique_payload).keys()
    assert GATE_KEYS <= gate_metrics(gate_payload).keys()
    assert FINALIZE_KEYS <= finalize_metrics(finalize_payload).keys()
    assert EXECUTE_KEYS <= execute_metrics(execute_payload, drift).keys()
    assert REVIEW_KEYS <= review_metrics(review_payload).keys()

    assert PREP_KEYS <= load_and_extract(tmp_path, "prep", 1).keys()
    assert PLAN_KEYS <= load_and_extract(tmp_path, "plan", 1).keys()
    assert CRITIQUE_KEYS <= load_and_extract(tmp_path, "critique", 1).keys()
    assert GATE_KEYS <= load_and_extract(tmp_path, "gate", 1).keys()
    assert FINALIZE_KEYS <= load_and_extract(tmp_path, "finalize", 1).keys()
    assert EXECUTE_KEYS <= load_and_extract(tmp_path, "execute", 1, drift_report=drift).keys()
    assert REVIEW_KEYS <= load_and_extract(tmp_path, "review", 1).keys()


def test_review_metrics_uses_finalize_totals_when_verdict_arrays_empty(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "finalize.json",
        {
            "tasks": [{"id": "T1"}, {"id": "T2"}, {"id": "T3"}],
            "sense_checks": [{"id": "SC1"}, {"id": "SC2"}],
        },
    )
    _write_json(
        tmp_path / "review.json",
        {
            "review_verdict": "needs_rework",
            "task_verdicts": [],
            "sense_check_verdicts": [],
            "rework_items": [],
        },
    )

    metrics = load_and_extract(tmp_path, "review", 1)

    assert metrics["task_verdicts_count"] == 0
    assert metrics["total_tasks"] == 3
    assert metrics["sense_check_verdicts_count"] == 0
    assert metrics["total_sense_checks"] == 2


def test_extract_for_phase_prep_returns_non_empty_metrics_and_revise_stays_empty_without_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        prep = extract_for_phase(
            "prep",
            {
                "skip": True,
                "task_summary": "",
                "key_evidence": [],
                "relevant_code": [],
                "test_expectations": [],
                "constraints": [],
                "suggested_approach": "",
            },
        )
        assert PREP_KEYS <= prep.keys()
        assert prep["skip"] is True
        assert extract_for_phase("revise", {"ignored": True}) == {}
    assert caplog.records == []


def test_extract_for_phase_covers_all_finish_step_phases() -> None:
    assert extract_for_phase("plan", {"plan": "## Step 1: Update a.py"}).keys() >= PLAN_KEYS
    assert extract_for_phase(
        "prep",
        {
            "skip": True,
            "task_summary": "",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "",
        },
    ).keys() >= PREP_KEYS
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


def test_load_and_extract_prep_handles_legacy_minimal_brief_without_sidecar(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "prep.json",
        {
            "skip": False,
            "task_summary": "legacy prep",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "follow the legacy brief",
        },
    )

    metrics = load_and_extract(tmp_path, "prep", 1)

    assert PREP_KEYS <= metrics.keys()
    assert metrics["task_summary_present"] is True
    assert metrics["area_count"] == 0
    assert metrics["fanout_count"] == 0
    assert metrics["cap_applied"] is False
    assert metrics["status_counts"] == {
        "complete": 0,
        "partial": 0,
        "timed_out": 0,
        "error": 0,
        "not_needed": 0,
    }
    assert metrics["model_resolution_trace"] == {}


def test_prep_extraction_returns_non_empty_values_for_metrics_rich_pipeline() -> None:
    """Prove that metrics-rich new pipeline outputs populate non-empty/non-default values."""
    prep_payload = {
        "skip": False,
        "task_summary": "Investigate prep orchestration",
        "key_evidence": [{"point": "prep exists", "source": "repo", "relevance": "high"}],
        "relevant_code": [{"file_path": "megaplan/orchestration/prep_research.py", "why": "main flow", "functions": ["run_prep_orchestration"]}],
        "test_expectations": [{"test_id": "tests/test_prep.py", "what_it_checks": "prep orchestration", "status": "pass_to_pass"}],
        "constraints": ["Keep PLAN artifact names stable."],
        "suggested_approach": "Use triage, fan-out, then distill.",
        "primary_criterion": "prep.json remains compatible",
    }
    metrics_payload = {
        "area_count": 6,
        "fanout_count": 4,
        "completed_count": 2,
        "partial_count": 1,
        "timed_out_count": 1,
        "error_count": 0,
        "missed_units": ["a2"],
        "total_cost_usd": 0.75,
        "prompt_tokens": 1200,
        "completion_tokens": 800,
        "total_tokens": 2000,
        "elapsed_time_ms": 5000,
        "files": ["megaplan/a.py", "megaplan/b.py"],
        "code_refs": ["pkg.a0", "pkg.a1"],
        "gap_notes": ["a2 timed out — no coverage for validation edge case"],
        "contradiction_notes": ["a0 and a1 both claim megaplan/a.py but with different scopes"],
        "overlap_groups": [{"kind": "file", "value": "megaplan/a.py", "areas": ["a0", "a1"]}],
        "cross_reference": {
            "performed": True,
            "checked_files": ["megaplan/a.py", "megaplan/b.py"],
            "existing_files": ["megaplan/a.py"],
            "missing_files": ["megaplan/b.py"],
            "shared_files": [],
        },
        "per_unit": [
            {"area": "a0", "status": "complete", "elapsed_time_ms": 1200, "files": ["megaplan/a.py"], "code_refs": ["pkg.a0"]},
            {"area": "a1", "status": "partial", "elapsed_time_ms": 1500, "files": ["megaplan/b.py"], "code_refs": ["pkg.a1"]},
            {"area": "a2", "status": "timed_out", "elapsed_time_ms": 800, "files": [], "code_refs": []},
            {"area": "a3", "status": "not_needed", "elapsed_time_ms": 0, "files": [], "code_refs": []},
        ],
        "critique_flags_count": 3,
        "revise_cycles_count": 2,
        "execution_failure_categories": ["timeout", "partial_output"],
        "human_override_count": 1,
    }
    resolver_trace = {
        "flat_prep_input": "codex",
        "resolved_stage_models": {
            "triage": "codex",
            "fanout": "hermes:deepseek:deepseek-v4-flash",
            "distill": "codex",
        },
        "canonical_fallback_used": {"triage": False, "fanout": True, "distill": False},
    }

    metrics = prep_metrics(prep_payload, metrics_payload, resolver_trace)

    # All expected keys present
    assert PREP_KEYS <= metrics.keys()

    # prep.json derived fields are non-empty
    assert metrics["skip"] is False
    assert metrics["task_summary_present"] is True
    assert metrics["key_evidence_count"] == 1
    assert metrics["relevant_code_count"] == 1
    assert metrics["test_expectations_count"] == 1
    assert metrics["constraints_count"] == 1
    assert metrics["suggested_approach_present"] is True
    assert metrics["primary_criterion_present"] is True

    # Metrics payload fields flow through with actual values
    assert metrics["area_count"] == 6
    assert metrics["fanout_count"] == 4
    assert metrics["area_cap"] == 4
    assert metrics["cap_applied"] is True  # 6 areas > 4 fanout slots
    assert metrics["completed_count"] == 2
    assert metrics["partial_count"] == 1
    assert metrics["timed_out_count"] == 1
    assert metrics["error_count"] == 0
    assert metrics["status_counts"]["complete"] == 2
    assert metrics["status_counts"]["partial"] == 1
    assert metrics["status_counts"]["timed_out"] == 1
    assert metrics["status_counts"]["error"] == 0
    assert metrics["status_counts"]["not_needed"] == 1
    assert metrics["missed_units"] == ["a2"]
    assert metrics["missed_units_count"] == 1
    assert metrics["total_cost_usd"] == 0.75
    assert metrics["prompt_tokens"] == 1200
    assert metrics["completion_tokens"] == 800
    assert metrics["total_tokens"] == 2000
    assert metrics["elapsed_time_ms"] == 5000
    assert metrics["files"] == ["megaplan/a.py", "megaplan/b.py"]
    assert metrics["files_count"] == 2
    assert metrics["code_refs"] == ["pkg.a0", "pkg.a1"]
    assert metrics["code_refs_count"] == 2
    assert metrics["per_unit_count"] == 4
    assert metrics["per_unit_statuses"] == ["complete", "partial", "timed_out", "not_needed"]

    # Distill adjudication fields
    assert metrics["gap_notes_count"] == 1
    assert metrics["contradiction_notes_count"] == 1
    assert metrics["overlap_groups_count"] == 1
    assert metrics["cross_reference_performed"] is True
    assert metrics["cross_reference_missing_files_count"] == 1

    # Downstream quality correlation placeholders
    assert metrics["critique_flags_count"] == 3
    assert metrics["revise_cycles_count"] == 2
    assert metrics["execution_failure_categories"] == ["timeout", "partial_output"]
    assert metrics["human_override_count"] == 1

    # Model resolution trace
    assert metrics["model_resolution_trace"] == resolver_trace


def test_extract_for_phase_prep_with_metrics_payload_returns_populated_values() -> None:
    """Prove that extract_for_phase prep with metrics payload returns non-empty metrics."""
    prep_payload = {
        "skip": False,
        "task_summary": "summary text",
        "key_evidence": [{"point": "k"}],
        "relevant_code": [{"file_path": "x.py"}],
        "test_expectations": [{"test_id": "t"}],
        "constraints": ["c"],
        "suggested_approach": "approach",
        "primary_criterion": "criterion",
    }
    metrics_payload = {
        "area_count": 3,
        "fanout_count": 3,
        "completed_count": 2,
        "partial_count": 1,
        "timed_out_count": 0,
        "error_count": 0,
        "total_cost_usd": 0.25,
        "prompt_tokens": 400,
        "completion_tokens": 300,
        "total_tokens": 700,
        "elapsed_time_ms": 1500,
        "files": ["x.py"],
        "code_refs": ["pkg.x"],
        "per_unit": [
            {"area": "a0", "status": "complete"},
            {"area": "a1", "status": "complete"},
            {"area": "a2", "status": "partial"},
        ],
    }
    resolver_trace = {"flat_prep_input": "hermes:deepseek"}

    metrics = extract_for_phase("prep", prep_payload, metrics_payload, resolver_trace)

    assert PREP_KEYS <= metrics.keys()
    assert metrics["area_count"] == 3
    assert metrics["fanout_count"] == 3
    assert metrics["cap_applied"] is False  # 3 == 3, not capped
    assert metrics["completed_count"] == 2
    assert metrics["partial_count"] == 1
    assert metrics["total_cost_usd"] == 0.25
    assert metrics["total_tokens"] == 700
    assert metrics["files_count"] == 1
    assert metrics["per_unit_count"] == 3
    assert metrics["model_resolution_trace"] == resolver_trace


def test_extract_for_phase_prep_with_minimal_skip_legacy_returns_zeroed_metrics() -> None:
    """Prove that legacy skip:true prep with no sidecar returns all keys but zeroed values."""
    prep_payload = {
        "skip": True,
        "task_summary": "",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "",
    }
    metrics = extract_for_phase("prep", prep_payload)

    assert PREP_KEYS <= metrics.keys()
    assert metrics["skip"] is True
    assert metrics["task_summary_present"] is False
    assert metrics["key_evidence_count"] == 0
    assert metrics["area_count"] == 0
    assert metrics["fanout_count"] == 0
    assert metrics["cap_applied"] is False
    assert metrics["completed_count"] == 0
    assert metrics["partial_count"] == 0
    assert metrics["timed_out_count"] == 0
    assert metrics["error_count"] == 0
    assert metrics["total_cost_usd"] == 0.0
    assert metrics["total_tokens"] == 0
    assert metrics["elapsed_time_ms"] == 0
    assert metrics["files_count"] == 0
    assert metrics["code_refs_count"] == 0
    assert metrics["per_unit_count"] == 0
    assert metrics["per_unit_statuses"] == []
    assert metrics["gap_notes_count"] == 0
    assert metrics["contradiction_notes_count"] == 0
    assert metrics["cross_reference_performed"] is False
    assert metrics["critique_flags_count"] == 0
    assert metrics["revise_cycles_count"] == 0
    assert metrics["human_override_count"] == 0
    assert metrics["model_resolution_trace"] == {}
