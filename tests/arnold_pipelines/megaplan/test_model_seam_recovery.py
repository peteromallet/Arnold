from __future__ import annotations

import json

import pytest
from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    audit_step_payload,
    capture_step_output,
)
from arnold_pipelines.megaplan.orchestration.plan_structure import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers.hermes import _reconstruct_gate_payload


def _gate_capture_invocation() -> StepInvocation:
    return StepInvocation(
        kind="model",
        metadata={
            "validation_step": "gate",
            "compatibility_validation_step": "gate",
        },
    )


def _schema_valid_north_star_action() -> dict[str, object]:
    return {
        "id": "NSA-1",
        "question_id": "route-authority",
        "question": "Does the plan preserve route authority?",
        "concern": "The plan still leaves route authority split across two surfaces.",
        "category": "route_authority",
        "action_type": "change_plan",
        "severity": "blocking",
        "severity_source": "schema",
        "evidence": "The plan keeps two route entrypoints active without a single owner.",
        "plan_refs": ["Phase 2 - Step 1"],
        "required_change": "Collapse route authority to the canonical path.",
    }


def test_gate_reconstruction_conservatively_recovers_unknown_north_star_severity(
    tmp_path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    action = _schema_valid_north_star_action()
    action["category"] = "correctness"
    action["severity"] = "significant"
    action["severity_source"] = "worker"

    reconstructed = _reconstruct_gate_payload(
        plan_dir,
        {
            "recommendation": "ITERATE",
            "rationale": "The plan needs another revision.",
            "signals_assessment": "Significant concerns remain.",
            "north_star_actions": [action],
        },
    )

    assert reconstructed is not None
    recovered = reconstructed["north_star_actions"][0]
    assert recovered["severity"] == "blocking"
    assert recovered["severity_source"] == "explicit"
    assert recovered["concern"] == action["concern"]
    assert recovered["evidence"] == action["evidence"]


def test_gate_reconstruction_preserves_valid_north_star_severity(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    action = _schema_valid_north_star_action()

    reconstructed = _reconstruct_gate_payload(
        plan_dir,
        {
            "recommendation": "ITERATE",
            "rationale": "The plan needs another revision.",
            "signals_assessment": "Blocking concerns remain.",
            "north_star_actions": [action],
        },
    )

    assert reconstructed is not None
    assert reconstructed["north_star_actions"] == [action]


def test_plan_recovery_prefers_later_structured_plan_over_summary_payload(
    tmp_path,
) -> None:
    """Plan capture should not promote an early summary when raw output has the real plan."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "plan_output.json"

    summary_payload = {
        "plan": "Created the M2 implementation plan from the worker prompt.",
        "questions": [],
        "success_criteria": [{"criterion": "Cleanup is planned", "priority": "must"}],
        "assumptions": [],
    }
    structured_payload = {
        "plan": "\n".join(
            [
                "# Implementation Plan: M2 Parity And Delete",
                "",
                "## Overview",
                "",
                "Move callers to the canonical package, prove parity, then delete the duplicate root.",
                "",
                "## Phase 1: Canonical Migration",
                "",
                "### Step 1: Establish Baseline",
                "",
                "1. Scan `arnold_pipelines/megaplan` and `tests` for legacy imports.",
                "2. Record the current parity status in `.megaplan` artifacts.",
                "",
                "## Validation Order",
                "",
                "1. Run `python -m pytest tests/arnold_pipelines/megaplan/test_model_seam_recovery.py -q`.",
            ]
        ),
        "questions": [],
        "success_criteria": [{"criterion": "Cleanup has executable steps", "priority": "must"}],
        "assumptions": [],
    }
    output_path.write_text(json.dumps(summary_payload), encoding="utf-8")
    raw = "\n".join(
        [
            json.dumps({"type": "message", "content": json.dumps(summary_payload)}),
            json.dumps({"type": "message", "content": json.dumps(structured_payload)}),
        ]
    )

    invocation = StepInvocation(
        kind="model",
        metadata={
            "capture_recovery": {
                "step": "plan",
                "plan_dir": str(plan_dir),
                "output_path": str(output_path),
                "prefer_output_file": True,
            },
        },
    )

    outcome = capture_step_output(invocation, raw)

    assert outcome.legacy_payload == structured_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:raw_output",
    )


def test_plan_capture_normalizes_extra_model_metadata() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "validation_step": "plan",
            "compatibility_validation_step": "plan",
        },
    )
    outcome = capture_step_output(
        invocation,
        {
            "source": "model-added-metadata",
            "title": "Ship Fix",
            "overview": "Do the work.",
            "steps": [
                {
                    "title": "Patch worker (`arnold_pipelines/megaplan/workers/hermes.py`)",
                    "substeps": ["Promote valid raw markdown."],
                }
            ],
            "questions": [],
            "success_criteria": [{"criterion": "Tests pass", "priority": "must"}],
            "assumptions": [],
        },
    )

    assert "source" not in outcome.legacy_payload
    assert "### Step 1: Patch worker" in outcome.legacy_payload["plan"]


def test_plan_audit_rejects_numbered_list_without_step_headings() -> None:
    payload = {
        "plan": (
            "Implement in seven scoped slices.\n\n"
            "1. Add `vibecomfy/agent/server.py`.\n"
            "2. Add a Python-callable dispatcher."
        ),
        "questions": [],
        "success_criteria": [
            {
                "criterion": "The endpoint is implemented",
                "priority": "must",
                "requires": ["read_files"],
            }
        ],
        "assumptions": [],
    }

    with pytest.raises(ModelStructuralAuditError) as exc:
        audit_step_payload("plan", payload)

    assert PLAN_STRUCTURE_REQUIRED_STEP_ISSUE in str(exc.value)


def test_plan_structure_error_valid_next_retries_plan(monkeypatch, tmp_path) -> None:
    from arnold_pipelines.megaplan.handlers import shared

    monkeypatch.setattr(shared, "record_step_failure", lambda *args, **kwargs: None)
    state = {
        "current_state": "planned",
        "iteration": 1,
        "plan_versions": [{"version": 1, "file": "plan_v1.md", "hash": "old"}],
        "history": [],
        "meta": {},
        "config": {},
    }
    worker = WorkerResult(
        payload={},
        raw_output='{"plan": "1. Do the thing"}',
        duration_ms=5,
        cost_usd=0.0,
    )

    with pytest.raises(CliError) as exc:
        shared._validate_generated_plan_or_raise(
            plan_dir=tmp_path,
            state=state,
            step="plan",
            iteration=1,
            worker=worker,
            plan_text="1. Do the thing\n2. Run tests\n",
        )

    assert exc.value.valid_next == ["plan"]


@pytest.mark.parametrize(
    "north_star_actions",
    [
        [],
        [_schema_valid_north_star_action()],
    ],
    ids=["empty-north-star-actions", "schema-valid-north-star-action"],
)
def test_gate_capture_preserves_schema_owned_north_star_actions_and_strips_unknown_fields(
    north_star_actions: list[object],
) -> None:
    invocation = _gate_capture_invocation()
    payload = {
        "recommendation": "PROCEED",
        "rationale": "The plan is ready.",
        "signals_assessment": "Score is stable and no blocking flags remain.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": north_star_actions,
        "model_note": "unknown top-level data must still be stripped",
    }

    outcome = capture_step_output(invocation, payload)

    assert outcome.legacy_payload["north_star_actions"] == north_star_actions
    assert "model_note" not in outcome.legacy_payload


def test_gate_capture_with_schema_valid_north_star_action_is_stable_across_retries() -> None:
    invocation = _gate_capture_invocation()
    action = _schema_valid_north_star_action()
    payload = {
        "recommendation": "PROCEED",
        "rationale": "The plan is ready.",
        "signals_assessment": "No blocking flags remain.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [action],
    }

    for _attempt in range(40):
        outcome = capture_step_output(invocation, payload)
        assert outcome.legacy_payload["north_star_actions"] == [action]
