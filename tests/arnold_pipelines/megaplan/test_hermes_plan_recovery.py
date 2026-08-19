from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.workers.hermes import (
    _reconstruct_plan_payload,
    _recover_plan_payload_from_raw_markdown,
)

PLAN_MD_WITH_PHASES = """# Implementation Plan: m6 — Serve, backup, doctor and teardown

## Overview

Complete the runnable local system.

## Phase 1: Backup & Restore — New Module

### Step 1: Create astrid/core/backup.py

1. Create `astrid/core/backup.py` with a `create_backup` function.
2. Write unit tests in `tests/v10/test_backup.py`.

## Execution Order

1. Step 1
"""


def test_plan_payload_recovers_from_valid_raw_markdown() -> None:
    raw_plan = "\n".join(
        [
            "# Implementation Plan: Fix",
            "",
            "## Overview",
            "",
            "Repair the worker path.",
            "",
            "## Main Phase",
            "",
            "### Step 1: Patch worker (`arnold_pipelines/megaplan/workers/hermes.py`)",
            "",
            "1. Promote valid raw markdown into the plan payload.",
            "",
            "## Validation Order",
            "",
            "1. Run `python -m pytest tests/arnold_pipelines/megaplan/test_hermes_plan_recovery.py`.",
        ]
    )

    recovered = _recover_plan_payload_from_raw_markdown(
        {
            "plan": "summary only",
            "questions": ["q"],
            "success_criteria": [{"criterion": "passes", "priority": "must"}],
            "assumptions": ["a"],
        },
        raw_plan,
    )

    assert recovered is not None
    assert recovered["plan"].startswith("# Implementation Plan: Fix")
    assert recovered["questions"] == ["q"]
    assert recovered["success_criteria"] == [{"criterion": "passes", "priority": "must"}]
    assert recovered["assumptions"] == ["a"]


def test_reconstruct_plan_payload_reads_model_plan_md(tmp_path: Path) -> None:
    """The model-authored plan.md artifact is promoted to the capture payload
    (astrid-first m6: model wrote plan.md via file tool, final message carried
    only fenced metadata blocks -> worker_structural_audit_failed)."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.md").write_text(PLAN_MD_WITH_PHASES, encoding="utf-8")

    reconstructed = _reconstruct_plan_payload(plan_dir)
    assert reconstructed is not None
    assert reconstructed["plan"] == PLAN_MD_WITH_PHASES

    # Missing / empty plan.md -> None (no fabrication).
    assert _reconstruct_plan_payload(tmp_path / "nope") is None
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    (empty_dir / "plan.md").write_text("   \n", encoding="utf-8")
    assert _reconstruct_plan_payload(empty_dir) is None


def test_reconstruct_plan_payload_passes_capture_audit(tmp_path: Path) -> None:
    """A reconstructed payload must satisfy the structural auditor end to end."""
    from arnold.execution.step_invocation import StepInvocation
    from arnold_pipelines.megaplan.schemas import SCHEMAS
    from arnold_pipelines.megaplan.workers.hermes import capture_step_output

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.md").write_text(PLAN_MD_WITH_PHASES, encoding="utf-8")

    reconstructed = _reconstruct_plan_payload(plan_dir)
    assert reconstructed is not None
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "hermes",
            "model": "test",
            "normalized_model": "test",
            "validation_step": "plan",
            "compatibility_validation_step": "plan",
            "schema": SCHEMAS["plan.json"],
        },
    )
    outcome = capture_step_output(invocation, reconstructed)
    assert outcome.legacy_payload["plan"].startswith("# Implementation Plan: m6")
    assert "### Step 1:" in outcome.legacy_payload["plan"]


def test_plan_payload_does_not_recover_raw_without_steps() -> None:
    recovered = _recover_plan_payload_from_raw_markdown(
        {"questions": []},
        "# Summary\n\nNo implementation steps here.",
    )

    assert recovered is None