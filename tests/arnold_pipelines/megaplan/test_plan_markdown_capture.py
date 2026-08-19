from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.model_seam import _normalize_plan_capture_payload
from arnold_pipelines.megaplan.orchestration.plan_structure import (
    PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    validate_plan_structure,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.workers.hermes import parse_agent_output


PHASED_PLAN_PAYLOAD = {
    "title": "Implementation Plan: m6 — Serve, backup, doctor and teardown",
    "overview": "Complete the runnable local system.",
    "phases": [
        {
            "name": "Phase 1: Backup & Restore — New Module",
            "steps": [
                {
                    "number": 1,
                    "title": "Create astrid/core/backup.py — backup create logic",
                    "scope": "Medium",
                    "complexity": 3,
                    "details": (
                        "Create astrid/core/backup.py with a create_backup function that "
                        "resolves the projects root, derives the database path via "
                        "derive_database_path and copies it to <out>/astrid.sqlite3. "
                        "Write unit tests in tests/v10/test_backup.py."
                    ),
                },
                {
                    "number": 2,
                    "title": "Add restore logic to astrid/core/backup.py",
                    "scope": "Medium",
                    "complexity": 3,
                    "details": (
                        "Add restore_backup function that validates the backup "
                        "directory (astrid.sqlite3, backup.json, media/) and "
                        "atomically swaps with rollback on failure. "
                        "Write unit tests for corruption rejection and rollback."
                    ),
                },
            ],
        },
        {
            "name": "Phase 2: Doctor Rework — Read-Only SQLite Diagnostics",
            "steps": [
                {
                    "number": 3,
                    "title": "Rework astrid/core/doctor.py — remove old checks",
                    "scope": "Medium",
                    "complexity": 3,
                    "details": (
                        "Remove old-system checks like _check_executor_registry and "
                        "_check_runpod_stale_handles from run_checks and add SQLite "
                        "checks. Ensure doctor opens DB strictly read-only."
                    ),
                },
                {
                    "number": 4,
                    "title": "Add doctor stable --json and corruption codes",
                    "scope": "Small",
                    "complexity": 2,
                    "details": (
                        "Update doctor.main to produce stable --json envelope. "
                        "Corruption produces exit 1 with database_corrupt or fk_violation."
                    ),
                },
            ],
        },
    ],
    "execution_order": [
        "Phase 1 (backup) — independent, safe to land first.",
        "Phase 2 (doctor) — independent, replaces existing module.",
    ],
    "validation_order": ["Run focused unit tests first.", "Run integration last."],
    "changed_surfaces": [
        "astrid/core/backup.py",
        "astrid/core/doctor.py",
        "tests/v10/test_backup.py",
    ],
    "test_blast_radius": {
        "strategy": "scoped",
        "selectors": [
            {"kind": "path", "value": "tests/v10/test_backup.py", "reason": "New module"},
        ],
    },
    "success_criteria": [
        {"criterion": "backup create produces a valid backup", "priority": "must"},
    ],
    "questions": ["Should astrid test survive as a hidden command?"],
    "assumptions": ["Backup destination format is a directory."],
}


PLAN_MARKDOWN = """# Implementation Plan: Post-Validation Narrative Synthesis

## Overview

Describe the change after validation artifacts exist.

## Main Phase

### Step 1: Add the post-validation narrator (`vibecomfy/comfy_nodes/agent/edit_narrative.py`)
1. Add the new module and wire the response builder.

## Success Criteria

```json
[
  {
    "criterion": "Narrative tests pass",
    "priority": "must",
    "requires": ["run_tests"]
  }
]
```

## Questions

- Should clean success paths keep the deterministic fast path?

## Assumptions

- The current response envelope shape stays unchanged.

## Changed Surfaces

```json
[
  "vibecomfy/comfy_nodes/agent/edit_response_contract.py",
  "tests/test_edit_narrative.py"
]
```

## Test Blast Radius

```json
{
  "strategy": "scoped",
  "selectors": [
    {
      "kind": "path",
      "value": "tests/test_edit_narrative.py",
      "reason": "Covers the new narrative path."
    }
  ],
  "full_suite_fallback": true,
  "rationale": "The change is localized to response construction."
}
```

## Execution Order
1. Land the narrator before updating response assembly.

## Validation Order
1. Run the focused narrative tests first.
"""


def test_normalize_plan_capture_payload_extracts_markdown_metadata() -> None:
    normalized = _normalize_plan_capture_payload({"plan": PLAN_MARKDOWN})

    assert normalized["plan"] == PLAN_MARKDOWN
    assert normalized["questions"] == [
        "Should clean success paths keep the deterministic fast path?"
    ]
    assert normalized["assumptions"] == [
        "The current response envelope shape stays unchanged."
    ]
    assert normalized["success_criteria"] == [
        {
            "criterion": "Narrative tests pass",
            "priority": "must",
            "requires": ["run_tests"],
        }
    ]
    assert normalized["changed_surfaces"] == [
        "vibecomfy/comfy_nodes/agent/edit_response_contract.py",
        "tests/test_edit_narrative.py",
    ]
    assert normalized["test_blast_radius"]["strategy"] == "scoped"


def test_normalize_plan_capture_flattens_grouped_changed_surfaces_without_notes() -> None:
    normalized = _normalize_plan_capture_payload(
        {
            "plan": PLAN_MARKDOWN,
            "questions": [],
            "success_criteria": [],
            "assumptions": [],
            "changed_surfaces": {
                "created_source": ["arnold/critique_ledger/store.py"],
                "created_tests": ["tests/arnold/critique_ledger/test_store.py"],
                "modified": ["arnold/critique_ledger/store.py"],
                "note": "This prose is not a path.",
            },
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [],
                "full_suite_fallback": True,
                "rationale": "Focused new-package tests.",
            },
        }
    )

    assert normalized["changed_surfaces"] == [
        "arnold/critique_ledger/store.py",
        "tests/arnold/critique_ledger/test_store.py",
    ]
    assert normalized["test_blast_radius"]["changed_surfaces"] == normalized[
        "changed_surfaces"
    ]


def test_normalize_plan_capture_materializes_omitted_test_hints() -> None:
    normalized = _normalize_plan_capture_payload(
        {
            "plan": "# Plan\n\n## Overview\nWork.\n\n## Step 1: Patch\nEdit.\n\n## Validation Order\n1. Validate.\n",
            "questions": [],
            "success_criteria": [],
            "assumptions": [],
        }
    )

    assert normalized["changed_surfaces"] == []
    assert normalized["test_blast_radius"] == {
        "strategy": "none",
        "selectors": [],
        "changed_surfaces": [],
        "full_suite_fallback": True,
        "rationale": (
            "The model omitted optional test-selection hints; the harness must "
            "derive the authoritative repository floor."
        ),
    }


def test_parse_agent_output_prefers_plan_markdown_over_embedded_json(
    tmp_path: Path,
) -> None:
    payload, raw_output = parse_agent_output(
        object(),
        {"final_response": PLAN_MARKDOWN, "messages": []},
        output_path=tmp_path / "plan_output.json",
        schema=SCHEMAS["plan.json"],
        step="plan",
        project_dir=tmp_path,
        plan_dir=tmp_path,
    )

    assert raw_output == PLAN_MARKDOWN
    assert payload["plan"] == PLAN_MARKDOWN
    assert payload["success_criteria"][0]["criterion"] == "Narrative tests pass"
    assert payload["test_blast_radius"]["selectors"][0]["value"] == (
        "tests/test_edit_narrative.py"
    )


def test_parse_agent_output_accepts_omitted_optional_test_hints(
    tmp_path: Path,
) -> None:
    response = {
        "plan": "# Plan\n\n## Overview\nWork.\n\n## Step 1: Patch\nEdit.\n\n## Validation Order\n1. Validate.\n",
        "questions": [],
        "success_criteria": [],
        "assumptions": [],
    }

    payload, _raw_output = parse_agent_output(
        object(),
        {"final_response": json.dumps(response), "messages": []},
        output_path=tmp_path / "plan_output.json",
        schema=SCHEMAS["plan.json"],
        step="plan",
        project_dir=tmp_path,
        plan_dir=tmp_path,
    )

    assert payload["changed_surfaces"] == []
    assert payload["test_blast_radius"]["strategy"] == "none"
    assert payload["test_blast_radius"]["full_suite_fallback"] is True


def test_normalize_phased_plan_payload_renders_flat_step_sections() -> None:
    """A provider payload that groups steps under phases must render to the
    canonical flat `## Step N:` markdown the structural auditor requires
    (Gap 5b: astrid-first m6 worker_structural_audit_failed regression)."""
    normalized = _normalize_plan_capture_payload(dict(PHASED_PLAN_PAYLOAD))

    plan_text = normalized["plan"]
    # Exactly one H1 + Overview + globally numbered step sections across phases.
    assert plan_text.startswith("# Implementation Plan: m6 — Serve, backup, doctor and teardown")
    assert "## Overview" in plan_text
    for step_number in range(1, 5):
        assert f"## Step {step_number}:" in plan_text
    # Phase grouping must not break global sequential numbering.
    assert "## Step 1: Create astrid/core/backup.py — backup create logic" in plan_text
    assert "## Step 3: Rework astrid/core/doctor.py — remove old checks" in plan_text
    # Execution Order section (auditor requires it).
    assert "## Execution Order" in plan_text
    # The structural auditor must pass with zero issues.
    issues = validate_plan_structure(plan_text)
    assert issues == [], f"phased render failed structural audit: {issues}"
    # Metadata still normalized to the canonical schema.
    assert normalized["questions"] == ["Should astrid test survive as a hidden command?"]
    assert normalized["changed_surfaces"] == [
        "astrid/core/backup.py",
        "astrid/core/doctor.py",
        "tests/v10/test_backup.py",
    ]
    assert normalized["success_criteria"][0]["criterion"].startswith(
        "backup create produces"
    )


def test_normalize_phased_plan_derives_substeps_and_refs_from_details() -> None:
    """Phased steps that carry only `details` prose (no structured
    actions/files) must still satisfy the auditor's numbered-substep and
    backticked-file-ref checks by deriving them from the prose."""
    payload = {
        "title": "Plan",
        "overview": "Do work.",
        "phases": [
            {
                "name": "Phase 1",
                "steps": [
                    {
                        "title": "Patch dispatch",
                        "details": (
                            "Change _dispatch_projects to route through "
                            "_dispatch_product instead of old cli.project.main. "
                            "Update doctor.main for the new envelope."
                        ),
                    },
                ],
            }
        ],
        "execution_order": ["Land the patch first."],
    }
    normalized = _normalize_plan_capture_payload(payload)
    plan_text = normalized["plan"]

    assert "## Step 1: Patch dispatch" in plan_text
    assert "1. Change " in plan_text  # derived numbered substep
    # Backticked code identifiers satisfy the file-ref check.
    assert "`doctor.main`" in plan_text
    assert "`_dispatch_product`" in plan_text
    assert "`cli.project.main`" in plan_text
    assert validate_plan_structure(plan_text) == []


def test_normalize_phased_plan_payload_preserves_flat_steps_path() -> None:
    """The pre-existing flat `steps[]` render path must remain unaffected."""
    flat = {
        "title": "Flat Plan",
        "overview": "Work.",
        "steps": [
            {
                "title": "Patch",
                "details": "Edit src/thing.py and add tests in tests/test_thing.py.",
            }
        ],
        "execution_order": ["Land it."],
    }
    normalized = _normalize_plan_capture_payload(flat)
    plan_text = normalized["plan"]
    assert "## Step 1: Patch" in plan_text
    assert "1. Edit " in plan_text
    assert "`src/thing.py`" in plan_text
    assert validate_plan_structure(plan_text) == []


def test_backtick_file_refs_preserves_existing_spans() -> None:
    """Tokens already inside a backtick span must never be double-wrapped."""
    from arnold_pipelines.megaplan.model_seam import _backtick_file_refs

    # Existing spans stay byte-identical.
    assert _backtick_file_refs("use `sqlite3.Connection.backup()` here") == (
        "use `sqlite3.Connection.backup()` here"
    )
    assert _backtick_file_refs("see `doctor.main` and `cli.project.main`") == (
        "see `doctor.main` and `cli.project.main`"
    )
    # Bare tokens outside spans still get wrapped.
    assert _backtick_file_refs("edit doctor.main then run tests/test_x.py") == (
        "edit `doctor.main` then run `tests/test_x.py`"
    )
    # Mixed: existing spans protected, bare tokens wrapped.
    assert _backtick_file_refs("open `astrid/core/backup.py` and fix doctor.main") == (
        "open `astrid/core/backup.py` and fix `doctor.main`"
    )