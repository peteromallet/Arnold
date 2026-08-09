"""Doc-mode section assembly — collects per-batch executor outputs into a single document."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import list_batch_artifacts, read_json


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


_BOLD_DASH_HEADER_RE = re.compile(
    r"^\*\*(?P<id>[^*]+?)\*\*\s*[\u2014\-:]\s*(?P<rest>.*)$"
)
_INLINE_LOAD_BEARING_RE = re.compile(
    r"_load_bearing\s*:\s*(?P<value>true|false)_", re.IGNORECASE
)


def extract_settled_decisions(doc_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract settled decisions from a doc-mode artifact.

    Two primary markdown shapes are accepted so doc authors can pick whichever
    reads more naturally:

    Bold-dash shape (preferred for inline prose):
        - **SD-001** — One-sentence decision summary. _load_bearing: true_
          Rationale: Brief why.

    YAML-ish shape (preferred when many fields per entry):
        - id: SD-001
          load_bearing: true
          decision: One-sentence decision summary
          rationale: Brief why.

    Both forms coexist within the same section. Missing `load_bearing`
    defaults to ``false``. Malformed entries are dropped with a warning
    but never raise.
    """
    lines = doc_text.splitlines()
    start_index: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == "## Settled Decisions":
            start_index = index + 1
            break
    if start_index is None:
        return [], []

    section_lines: list[str] = []
    for line in lines[start_index:]:
        if line.strip().startswith("## "):
            break
        section_lines.append(line)

    decisions: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, str] | None = None
    allowed_keys = {"id", "decision", "rationale", "load_bearing"}

    def flush_current() -> None:
        nonlocal current
        if current is None:
            return
        decision_id = current.get("id", "").strip()
        decision_text = current.get("decision", "").strip()
        if not decision_id or not decision_text:
            missing = []
            if not decision_id:
                missing.append("id")
            if not decision_text:
                missing.append("decision")
            warnings.append(
                f"Dropped malformed settled decision entry missing {', '.join(missing)}"
            )
            current = None
            return
        decisions.append(
            {
                "id": decision_id,
                "decision": decision_text,
                "rationale": current.get("rationale", "").strip(),
                "load_bearing": current.get("load_bearing", "").strip().lower() == "true",
            }
        )
        current = None

    def try_parse_bold_dash_header(entry: str) -> dict[str, str] | None:
        """Match `**SD-NNN** — summary. _load_bearing: true_` and return fields."""
        match = _BOLD_DASH_HEADER_RE.match(entry)
        if not match:
            return None
        rest = match.group("rest").strip()
        fields: dict[str, str] = {"id": match.group("id").strip()}
        lb_match = _INLINE_LOAD_BEARING_RE.search(rest)
        if lb_match:
            fields["load_bearing"] = lb_match.group("value")
            rest = _INLINE_LOAD_BEARING_RE.sub("", rest).strip()
        fields["decision"] = rest.rstrip().rstrip(".").strip() or rest.strip()
        return fields

    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            flush_current()
            entry = stripped[2:].strip()

            bold_dash = try_parse_bold_dash_header(entry)
            if bold_dash is not None:
                current = bold_dash
                continue

            current = {}
            if ":" not in entry:
                warnings.append(f"Ignored malformed settled decision line: {stripped}")
                continue
            key, value = entry.split(":", 1)
            key = key.strip().lower()
            if key in allowed_keys:
                current[key] = value.strip()
            else:
                warnings.append(f"Ignored malformed settled decision line: {stripped}")
            continue
        if line.startswith("  ") and current is not None:
            if ":" not in stripped:
                warnings.append(f"Ignored malformed settled decision line: {stripped}")
                continue
            key, value = stripped.split(":", 1)
            key = key.strip().lower()
            if key in allowed_keys:
                # Don't overwrite a non-empty value already populated by the header line.
                existing = current.get(key, "").strip()
                if not existing:
                    current[key] = value.strip()
            else:
                warnings.append(f"Ignored malformed settled decision line: {stripped}")
            continue
        warnings.append(f"Ignored malformed settled decision line: {stripped}")

    flush_current()
    return decisions, warnings


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
    for batch_path in list_batch_artifacts(plan_dir):
        try:
            batch_payloads.append(read_json(batch_path))
        except (OSError, ValueError):
            pass

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
