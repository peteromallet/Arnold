from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.model_seam import _normalize_plan_capture_payload
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.workers.hermes import parse_agent_output


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
