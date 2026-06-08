"""ResumeCursor — Sprint 5 Chunk D, third primitive.

Typed wrapper around the resume state legacy plans persist in
``state.json::resume_cursor``. Tied to the pipeline's stage names so
``resume_from(name)`` re-enters the pipeline at the right place.

Usage::

    cursor = ResumeCursor.load(plan_dir)
    if cursor:
        pipeline = pipeline.with_entry(cursor.stage)
        run_pipeline(pipeline, ctx, artifact_root=plan_dir)
    else:
        run_pipeline(pipeline, ctx, artifact_root=plan_dir)

    # After each stage:
    ResumeCursor(stage=node.name).save(plan_dir)

Sprint A addition: ``check_awaiting_user`` inspects ``awaiting_user.json``
so callers (e.g. ``handle_resume``) can dispatch to the human-gate resume
flow before falling through to ``state.json::resume_cursor`` recovery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan._pipeline.types import Pipeline

COMPOSITE_SUSPENSION_KIND = "composite_suspension"
COMPOSITE_SUSPENSION_CURSOR_VERSION = 1


def load_resume_cursor_payload(plan_dir: Path) -> dict[str, Any] | None:
    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    cursor = data.get("resume_cursor")
    if not isinstance(cursor, dict):
        return None
    return dict(cursor)


def is_composite_resume_cursor(cursor: Mapping[str, Any] | None) -> bool:
    if cursor is None:
        return False
    return cursor.get("kind") == COMPOSITE_SUSPENSION_KIND


def load_composite_resume_cursor(plan_dir: Path) -> dict[str, Any] | None:
    cursor = load_resume_cursor_payload(plan_dir)
    if not is_composite_resume_cursor(cursor):
        return None
    return dict(cursor)


def save_composite_resume_cursor(
    plan_dir: Path,
    *,
    children: Mapping[str, Any],
    version: int = COMPOSITE_SUSPENSION_CURSOR_VERSION,
    **extra: Any,
) -> Path:
    resolved_plan_dir = Path(plan_dir)
    payload: dict[str, Any] = {
        "kind": COMPOSITE_SUSPENSION_KIND,
        "version": version,
        "children": dict(children),
    }
    payload.update(extra)
    write_plan_state(
        resolved_plan_dir,
        mode="patch-key",
        key="resume_cursor",
        value=payload,
    )
    return resolved_plan_dir / "state.json"


def extract_composite_child_resume_cursor(
    plan_dir: Path,
    child_id: str,
) -> Any | None:
    cursor = load_composite_resume_cursor(plan_dir)
    if cursor is None:
        return None
    children = cursor.get("children")
    if not isinstance(children, Mapping):
        return None
    return children.get(child_id)


def extract_all_composite_child_resume_cursors(plan_dir: Path) -> dict[str, Any]:
    cursor = load_composite_resume_cursor(plan_dir)
    if cursor is None:
        return {}
    children = cursor.get("children")
    if not isinstance(children, Mapping):
        return {}
    return {str(child_id): value for child_id, value in children.items()}


@dataclass(frozen=True)
class ResumeCursor:
    """Where the pipeline should re-enter on resume.

    ``stage`` names the Pipeline stage to start from. ``payload``
    carries anything extra a Step might need on resume (e.g. partial
    fan-out completion). The legacy ``state.json::resume_cursor``
    schema is preserved when loading + saving:

        {"phase": "<stage_name>", "retry_strategy": "...", ...}

    ``phase`` is the legacy key; ResumeCursor reads/writes it.
    """

    stage: str
    payload: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.payload is None:
            object.__setattr__(self, "payload", {})

    @classmethod
    def load(cls, plan_dir: Path) -> "ResumeCursor | None":
        cursor = load_resume_cursor_payload(plan_dir)
        if cursor is None or is_composite_resume_cursor(cursor):
            return None
        stage = cursor.get("phase") or cursor.get("stage")
        if not isinstance(stage, str):
            return None
        payload = {k: v for k, v in cursor.items() if k not in {"phase", "stage"}}
        return cls(stage=stage, payload=payload)

    def save(self, plan_dir: Path, *, overwrite_composite: bool = False) -> Path:
        resolved_plan_dir = Path(plan_dir)
        path = resolved_plan_dir / "state.json"
        existing_cursor = load_resume_cursor_payload(resolved_plan_dir)
        if is_composite_resume_cursor(existing_cursor) and not overwrite_composite:
            raise ValueError(
                "state.json::resume_cursor already contains a composite suspension "
                "cursor; call save_composite_resume_cursor() to preserve it or pass "
                "overwrite_composite=True to replace it intentionally"
            )
        write_plan_state(
            resolved_plan_dir,
            mode="patch-key",
            key="resume_cursor",
            value={"phase": self.stage, **dict(self.payload)},
        )
        return path

    def with_payload(self, **overrides: Any) -> "ResumeCursor":
        merged = {**dict(self.payload), **overrides}
        return ResumeCursor(stage=self.stage, payload=merged)


def with_entry(pipeline: Pipeline, stage_name: str) -> Pipeline:
    """Return a copy of ``pipeline`` whose entry is ``stage_name``."""
    if stage_name not in pipeline.stages:
        raise KeyError(
            f"stage {stage_name!r} not in pipeline; available: "
            f"{sorted(pipeline.stages)}"
        )
    return Pipeline(
        stages=pipeline.stages,
        entry=stage_name,
        overlays=pipeline.overlays,
    )


def check_awaiting_user(plan_dir: Path) -> dict[str, Any] | None:
    """Check if ``plan_dir`` contains an ``awaiting_user.json`` pause file.

    Returns the parsed data if present and valid, ``None`` otherwise.
    This is the dispatch gate — callers check this before falling through
    to ``state.json::resume_cursor`` recovery.
    """
    awaiting_path = Path(plan_dir) / "awaiting_user.json"
    if not awaiting_path.exists():
        return None
    try:
        data = json.loads(awaiting_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data
