"""Doc-mode section assembly — collects per-batch executor outputs into a single document."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from megaplan._core import read_json


def extract_sections(batch_payloads: list[dict[str, Any]]) -> dict[str, str]:
    """Map section_id to rendered text from executor output.

    Scans task_updates across all batch payloads. Each task with status
    'done' contributes its sections_written entries. The section content
    is taken from the task's executor_notes (the authored text).
    """
    sections: dict[str, str] = {}
    for payload in batch_payloads:
        for task in payload.get("task_updates", []):
            if not isinstance(task, dict):
                continue
            if task.get("status") != "done":
                continue
            notes = task.get("executor_notes", "")
            for section_id in task.get("sections_written", []):
                if isinstance(section_id, str) and section_id.strip():
                    sections[section_id] = notes
    return sections


def _task_order_index(finalize_data: dict[str, Any]) -> dict[str, int]:
    """Build a mapping from task_id to its position in the finalize task list."""
    return {
        task["id"]: index
        for index, task in enumerate(finalize_data.get("tasks", []))
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def _section_plan_order(
    finalize_data: dict[str, Any],
    batch_payloads: list[dict[str, Any]],
) -> list[str]:
    """Return section IDs ordered by their owning task's position in the plan."""
    task_index = _task_order_index(finalize_data)
    section_to_task: dict[str, str] = {}
    for payload in batch_payloads:
        for task in payload.get("task_updates", []):
            if not isinstance(task, dict):
                continue
            task_id = task.get("task_id", "")
            for section_id in task.get("sections_written", []):
                if isinstance(section_id, str) and section_id.strip():
                    section_to_task.setdefault(section_id, task_id)
    ordered = sorted(
        section_to_task.keys(),
        key=lambda sid: task_index.get(section_to_task.get(sid, ""), 999),
    )
    return ordered


def assemble_doc(
    plan_dir: Path,
    output_path: Path,
    finalize_data: dict[str, Any],
) -> Path:
    """Fallback document assembly from per-batch executor notes.

    The executor is the primary author: per `prompts/execute_doc.py`, it writes
    the document directly to `output_path` during each task, and keeps
    `executor_notes` verification-focused (not section content). When the
    executor wrote the file successfully, this function preserves that file
    and does nothing else.

    Fallback path — only if the output file is missing or empty — assembles
    text from `executor_notes` in `execution_batch_*.json`, ordered by the
    owning task's position in `finalize_data`. This is a degraded best-effort
    output for the sandbox-blocked case; callers should treat its content as
    verification prose rather than authored sections.

    The file is written atomically (temp file + rename).
    """
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    batch_payloads: list[dict[str, Any]] = []
    batch_index = 1
    while True:
        batch_path = plan_dir / f"execution_batch_{batch_index}.json"
        if not batch_path.exists():
            break
        try:
            batch_payloads.append(read_json(batch_path))
        except (OSError, ValueError):
            pass
        batch_index += 1

    sections = extract_sections(batch_payloads)
    ordered_ids = _section_plan_order(finalize_data, batch_payloads)

    lines: list[str] = []
    for section_id in ordered_ids:
        content = sections.get(section_id, "")
        if content:
            lines.append(content)

    assembled_text = "\n\n".join(lines) if lines else ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(output_path.parent),
        suffix=".tmp",
    )
    closed = False
    try:
        os.write(fd, assembled_text.encode("utf-8"))
        os.close(fd)
        closed = True
        os.replace(tmp_path, str(output_path))
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return output_path
