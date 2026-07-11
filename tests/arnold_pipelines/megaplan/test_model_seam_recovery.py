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


def test_gate_audit_strips_unknown_top_level_fields_from_inline_payload() -> None:
    payload = {
        "recommendation": "PROCEED",
        "rationale": "The plan is ready.",
        "signals_assessment": "Score is stable and no blocking flags remain.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [
            {
                "id": "NSA-1",
                "action": "This model-added field should not break gate validation.",
            }
        ],
    }

    audit_step_payload("gate", payload)
