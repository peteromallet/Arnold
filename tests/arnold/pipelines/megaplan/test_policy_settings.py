"""Reporting parity tests for ``arnold.pipelines.megaplan.policy_settings``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold.pipelines.megaplan.execute import _resolve_execute_approval_mode
from arnold.pipelines.megaplan.execute.batch import _resolve_max_tasks_per_batch
from arnold.pipelines.megaplan.orchestration.iteration_pressure import (
    compute_iteration_pressure,
    has_mechanical_recurrence,
)
from arnold.pipelines.megaplan.policy_settings import (
    SETTING_SPECS,
    describe_effective_policy_settings,
)
from megaplan.execute._binding.tier import select_batch_tier


def _by_key(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {entry["key"]: entry for entry in entries}


def test_setting_specs_cover_required_policy_keys() -> None:
    assert [spec.key for spec in SETTING_SPECS] == [
        "destructive_confirmation",
        "review_approval",
        "blocked_lifecycle",
        "batch_transitions",
        "evidence_requirements",
        "tier_selection",
        "iteration_pressure",
    ]


def test_destructive_confirmation_reports_execute_stage_default() -> None:
    entries = _by_key(describe_effective_policy_settings())

    destructive = entries["destructive_confirmation"]
    assert destructive["status"] == "effective"
    assert destructive["value"] is True
    assert destructive["source"] == (
        "arnold.pipelines.megaplan.stages.execute._DEFAULTS.confirm_destructive"
    )


def test_review_approval_reports_existing_resolver_result() -> None:
    state = {
        "config": {"auto_approve": False},
        "meta": {"user_approved_gate": True},
    }

    entries = _by_key(describe_effective_policy_settings(state=state))
    review_approval = entries["review_approval"]

    assert review_approval["status"] == "effective"
    assert review_approval["value"] == _resolve_execute_approval_mode(
        auto_approve=False,
        user_approved_gate=True,
    )
    assert review_approval["source"] == "state.meta.user_approved_gate"


def test_batch_transitions_report_matches_existing_batch_resolver() -> None:
    args = argparse.Namespace(max_tasks_per_batch=3)
    state = {"config": {}}
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending"},
            {"id": "T2", "status": "pending"},
            {"id": "T3", "status": "pending"},
            {"id": "T4", "status": "pending"},
        ]
    }

    entries = _by_key(
        describe_effective_policy_settings(
            args=args,
            state=state,
            finalize_data=finalize_data,
        )
    )
    batch_transitions = entries["batch_transitions"]

    assert batch_transitions["status"] == "effective"
    assert batch_transitions["value"] == {
        "max_tasks_per_batch": _resolve_max_tasks_per_batch(state, args),
        "global_batch_count": 2,
    }
    assert batch_transitions["source"] == "args.max_tasks_per_batch"


def test_evidence_requirements_report_doc_mode_audit_summary(tmp_path: Path) -> None:
    finalize_data = {
        "config": {"mode": "doc"},
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "sections_written": ["intro"],
                "executor_notes": "Expanded the introduction section with the requested context.",
            }
        ],
        "sense_checks": [{"id": "SC1", "executor_note": "Verified the introduction now covers the missing scope."}],
    }
    state = {"config": {"mode": "doc"}}

    entries = _by_key(
        describe_effective_policy_settings(
            state=state,
            finalize_data=finalize_data,
            project_dir=tmp_path,
        )
    )
    evidence = entries["evidence_requirements"]

    assert evidence["status"] == "effective"
    assert evidence["source"] == (
        "arnold.pipelines.megaplan.orchestration.execution_evidence.validate_execution_evidence"
    )
    assert evidence["value"] == {
        "mode": "doc",
        "skipped": False,
        "finding_count": 0,
    }


def test_tier_selection_report_matches_existing_tier_helpers() -> None:
    args = argparse.Namespace(tier_models={"execute": {"3": "codex:medium", "5": "codex:high"}})
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "complexity": 3,
                "complexity_justification": "Moderate multi-file change.",
            },
            {
                "id": "T2",
                "complexity": 1,
                "complexity_justification": "Small follow-up edit.",
            },
        ]
    }

    entries = _by_key(describe_effective_policy_settings(args=args, finalize_data=finalize_data))
    tier_selection = entries["tier_selection"]

    assert tier_selection["status"] == "effective"
    assert tier_selection["value"] == {
        "selected_tier": select_batch_tier(finalize_data, ["T1", "T2"]),
        "tier_map": {3: "codex:medium", 5: "codex:high"},
    }


def test_iteration_pressure_report_matches_existing_computation(tmp_path: Path) -> None:
    critiques = {
        "critique_v1.json": {"flags": [{"id": "FLAG-1", "status": "addressed", "concern": "Strengthen execute validation coverage"}]},
        "critique_v2.json": {"flags": [{"id": "FLAG-1", "status": "open", "concern": "Strengthen execute validation coverage"}]},
        "critique_v3.json": {"flags": [{"id": "FLAG-1", "status": "addressed", "concern": "Strengthen execute validation coverage"}]},
        "critique_v4.json": {"flags": [{"id": "FLAG-1", "status": "open", "concern": "Strengthen execute validation coverage"}]},
    }
    for name, payload in critiques.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")

    state = {"iteration": 4}
    expected_entries = compute_iteration_pressure(tmp_path, state)

    entries = _by_key(describe_effective_policy_settings(state=state, plan_dir=tmp_path))
    iteration_pressure = entries["iteration_pressure"]

    assert expected_entries
    assert iteration_pressure["status"] == "effective"
    assert iteration_pressure["value"] == {
        "entry_count": len(expected_entries),
        "has_mechanical_recurrence": has_mechanical_recurrence(expected_entries),
        "max_iterations_open": max(entry["iterations_open"] for entry in expected_entries),
    }
