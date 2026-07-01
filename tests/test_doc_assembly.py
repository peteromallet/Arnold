from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.runtime.doc_assembly import assemble_doc


def _write_batch(
    plan_dir: Path,
    batch_index: int,
    *,
    task_id: str,
    status: str,
    sections_written: list[str],
    executor_notes: str,
) -> None:
    (plan_dir / f"execution_batch_{batch_index}.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": task_id,
                        "status": status,
                        "sections_written": sections_written,
                        "executor_notes": executor_notes,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_assemble_doc_keeps_existing_non_empty_output(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "final.md"
    output_path.write_text("primary author output", encoding="utf-8")

    result = assemble_doc(plan_dir, output_path, {"tasks": []})

    assert result == output_path
    assert output_path.read_text(encoding="utf-8") == "primary author output"


def test_assemble_doc_falls_back_to_done_task_notes_in_plan_order(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "final.md"

    _write_batch(
        plan_dir,
        1,
        task_id="T2",
        status="done",
        sections_written=["body"],
        executor_notes="Body section",
    )
    _write_batch(
        plan_dir,
        2,
        task_id="T1",
        status="done",
        sections_written=["intro"],
        executor_notes="Intro section",
    )
    _write_batch(
        plan_dir,
        3,
        task_id="T3",
        status="blocked",
        sections_written=["ignored"],
        executor_notes="Should not appear",
    )

    finalize_data = {
        "tasks": [
            {"id": "T1"},
            {"id": "T2"},
            {"id": "T3"},
        ]
    }

    assemble_doc(plan_dir, output_path, finalize_data)

    assert output_path.read_text(encoding="utf-8") == "Intro section\n\nBody section"
