"""Smoke tests for doc-mode section assembly (megaplan.doc_assembly)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.doc_assembly import assemble_doc, extract_sections


def _write_batch(plan_dir: Path, index: int, payload: dict) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"execution_batch_{index}.json").write_text(
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

    # Batch 1 has T2's section, batch 2 has T1's section — written out of plan order.
    _write_batch(plan_dir, 1, {
        "task_updates": [
            {"task_id": "T2", "status": "done",
             "executor_notes": "Body content", "sections_written": ["body"]},
        ]
    })
    _write_batch(plan_dir, 2, {
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
    _write_batch(plan_dir, 1, {
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


def test_assemble_doc_handles_no_batches(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "out.md"
    assemble_doc(plan_dir, output_path, _finalize_with_tasks())
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == ""


def test_assemble_doc_handles_empty_batch(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "out.md"
    _write_batch(plan_dir, 1, {"task_updates": []})
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.read_text(encoding="utf-8") == ""


def test_assemble_doc_creates_parent_directory(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    output_path = tmp_path / "nested" / "deep" / "out.md"
    _write_batch(plan_dir, 1, {
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
    _write_batch(plan_dir, 1, {
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
    _write_batch(plan_dir, 1, {
        "task_updates": [
            {"task_id": "T1", "status": "done",
             "executor_notes": "Fallback body", "sections_written": ["s1"]},
        ]
    })
    assemble_doc(plan_dir, output_path, _finalize_with_tasks("T1"))
    assert output_path.read_text(encoding="utf-8") == "Fallback body"


def test_extract_sections_duplicate_section_id_last_wins(tmp_path: Path) -> None:
    """Document current behavior: when two tasks claim the same section_id,
    the later batch wins. This locks the contract so any future change is
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
