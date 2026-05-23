"""Smoke tests for doc-mode section assembly (megaplan.runtime.doc_assembly)."""
from __future__ import annotations

import json
from pathlib import Path

from megaplan.runtime.doc_assembly import assemble_doc, extract_sections, extract_settled_decisions
from megaplan.worktrees.identity import make_task_identity


def _write_task_artifact(plan_dir: Path, task_id: str, payload: dict) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    identity = make_task_identity(task_id)
    artifact_path = plan_dir / "tasks" / identity.task_key / "execution.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _finalize_with_tasks(*task_ids: str) -> dict:
    return {"tasks": [{"id": tid} for tid in task_ids]}


def test_extract_sections_collects_done_only() -> None:
    payloads = [
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Intro text",
                    "sections_written": ["intro"],
                },
                {
                    "task_id": "T2",
                    "status": "in_progress",
                    "executor_notes": "should not appear",
                    "sections_written": ["body"],
                },
            ]
        }
    ]
    sections = extract_sections(payloads)
    assert sections == {"intro": "Intro text"}


def test_assemble_doc_orders_sections_by_task_index(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"

    # Task artifacts are written out of plan order but assembled in plan order.
    _write_task_artifact(plan_dir, "T2", {
        "task_updates": [
            {"task_id": "T2", "status": "done",
             "executor_notes": "Body content", "sections_written": ["body"]},
        ]
    })
    _write_task_artifact(plan_dir, "T1", {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "Intro content", "sections_written": ["intro"]},
        ]
    })

    finalize = _finalize_with_tasks("T1", "T2")
    assemble_doc(plan_dir, output_path, finalize)
    text = output_path.read_text(encoding="utf-8")
    assert text == "Intro content\n\nBody content"


def test_assemble_doc_is_idempotent(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"
    _write_task_artifact(plan_dir, "T1", {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "Hello", "sections_written": ["s1"]},
        ]
    })
    finalize = _finalize_with_tasks("T1")
    assemble_doc(plan_dir, output_path, finalize)
    first = output_path.read_text(encoding="utf-8")
    assemble_doc(plan_dir, output_path, finalize)
    second = output_path.read_text(encoding="utf-8")
    assert first == second == "Hello"


def test_assemble_doc_handles_no_task_artifacts(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "out.md"
    assemble_doc(plan_dir, output_path, _finalize_with_tasks())
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == ""


def test_assemble_doc_handles_empty_task_artifact(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"
    _write_task_artifact(plan_dir, "T1", {"task_updates": []})
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.read_text(encoding="utf-8") == ""


def test_assemble_doc_creates_parent_directory(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "nested" / "deep" / "out.md"
    _write_task_artifact(plan_dir, "T1", {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "X", "sections_written": ["s1"]},
        ]
    })
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "X"


def test_assemble_doc_preserves_executor_written_file(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"
    output_path.write_text("# Real document\n\nAuthored content here.", encoding="utf-8")
    _write_task_artifact(plan_dir, "T1", {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "Verification prose, not content", "sections_written": ["s1"]},
        ]
    })
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.read_text(encoding="utf-8") == "# Real document\n\nAuthored content here."


def test_assemble_doc_falls_back_when_file_empty(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"
    output_path.write_text("", encoding="utf-8")
    _write_task_artifact(plan_dir, "T1", {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "Fallback body", "sections_written": ["s1"]},
        ]
    })
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.read_text(encoding="utf-8") == "Fallback body"


def test_extract_sections_duplicate_section_id_last_wins(tmp_path: Path) -> None:
    """Document current behavior: when two tasks claim the same section_id,
    the later payload wins. This locks the contract so any future change is
    deliberate."""
    payloads = [
        {"task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "first", "sections_written": ["dup"]},
        ]},
        {"task_updates": [
            {"task_id": "T2", "status": "done",
             "executor_notes": "second", "sections_written": ["dup"]},
        ]},
    ]
    sections = extract_sections(payloads)
    assert sections == {"dup": "second"}


def test_extract_settled_decisions_empty_doc() -> None:
    decisions, warnings = extract_settled_decisions("")
    assert decisions == []
    assert warnings == []


def test_extract_settled_decisions_missing_section() -> None:
    decisions, warnings = extract_settled_decisions("# Title\n\nNo settled decisions here.")
    assert decisions == []
    assert warnings == []


def test_extract_settled_decisions_parses_three_entries() -> None:
    doc_text = """# Plan

## Settled Decisions
- id: SD-001
  load_bearing: true
  decision: Keep SQLite for local state
  rationale: Existing workflows depend on it.
- id: SD-002
  load_bearing: false
  decision: Use markdown bullets for docs
  rationale: Easier to review in diffs.
- id: SD-9
  decision: Preserve IDs verbatim
  rationale: Parser should be tolerant.

## Next Section
Body
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert warnings == []
    assert decisions == [
        {
            "id": "SD-001",
            "load_bearing": True,
            "decision": "Keep SQLite for local state",
            "rationale": "Existing workflows depend on it.",
        },
        {
            "id": "SD-002",
            "load_bearing": False,
            "decision": "Use markdown bullets for docs",
            "rationale": "Easier to review in diffs.",
        },
        {
            "id": "SD-9",
            "load_bearing": False,
            "decision": "Preserve IDs verbatim",
            "rationale": "Parser should be tolerant.",
        },
    ]


def test_extract_settled_decisions_drops_malformed_entry_with_warning() -> None:
    doc_text = """## Settled Decisions
- id: SD-001
  decision: Keep the adapter layer
  rationale: It isolates storage changes.
- decision: Missing an ID should be dropped
  rationale: This line is intentionally malformed.
- id: SD-002
  load_bearing: false
  decision: Keep the current CLI nouns
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert decisions == [
        {
            "id": "SD-001",
            "decision": "Keep the adapter layer",
            "rationale": "It isolates storage changes.",
            "load_bearing": False,
        },
        {
            "id": "SD-002",
            "decision": "Keep the current CLI nouns",
            "rationale": "",
            "load_bearing": False,
        },
    ]
    assert warnings == ["Dropped malformed settled decision entry missing id"]


def test_extract_settled_decisions_heading_without_entries() -> None:
    decisions, warnings = extract_settled_decisions("## Settled Decisions\n\n## Later\nbody")
    assert decisions == []
    assert warnings == []


def test_extract_settled_decisions_load_bearing_is_case_insensitive() -> None:
    doc_text = """## Settled Decisions
- id: SD-003
  load_bearing: TRUE
  decision: Promote must-level constraints from docs
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert warnings == []
    assert decisions == [
        {
            "id": "SD-003",
            "decision": "Promote must-level constraints from docs",
            "rationale": "",
            "load_bearing": True,
        }
    ]


def test_extract_settled_decisions_bold_dash_shape() -> None:
    """The bold-dash inline shape from the spec must also parse."""
    doc_text = """# Parent Design

## Settled Decisions

- **SD-001** \u2014 Use UUIDv4 for file IDs. _load_bearing: true_
  Rationale: Needed for cross-session stability.
- **SD-002** \u2014 Default model is claude-sonnet-4-6. _load_bearing: false_
  Rationale: Balance of speed and capability.

## Other content
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert warnings == []
    assert decisions == [
        {
            "id": "SD-001",
            "decision": "Use UUIDv4 for file IDs",
            "rationale": "Needed for cross-session stability.",
            "load_bearing": True,
        },
        {
            "id": "SD-002",
            "decision": "Default model is claude-sonnet-4-6",
            "rationale": "Balance of speed and capability.",
            "load_bearing": False,
        },
    ]


def test_extract_settled_decisions_bold_dash_without_load_bearing_defaults_false() -> None:
    doc_text = """## Settled Decisions

- **SD-010** \u2014 Keep IDs stable across runs.
  Rationale: Stability prevents breakage.
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert warnings == []
    assert decisions == [
        {
            "id": "SD-010",
            "decision": "Keep IDs stable across runs",
            "rationale": "Stability prevents breakage.",
            "load_bearing": False,
        }
    ]


def test_extract_settled_decisions_mixed_shapes_in_same_section() -> None:
    doc_text = """## Settled Decisions

- **SD-100** \u2014 Bold-dash line form. _load_bearing: true_
  Rationale: It reads naturally inline.
- id: SD-101
  load_bearing: false
  decision: YAML-ish form still works
  rationale: Authors pick whichever shape fits.
"""
    decisions, warnings = extract_settled_decisions(doc_text)
    assert warnings == []
    assert [d["id"] for d in decisions] == ["SD-100", "SD-101"]
    assert decisions[0]["load_bearing"] is True
    assert decisions[1]["load_bearing"] is False
