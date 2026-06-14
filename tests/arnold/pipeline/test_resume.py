from __future__ import annotations

import json
from pathlib import Path

from arnold.pipeline.resume import (
    COMPOSITE_RESUME_CURSOR_FILENAME,
    RESUME_CURSOR_FILENAME,
    persist_composite_resume_cursor,
    persist_resume_cursor,
    read_composite_resume_cursor,
    read_resume_cursor,
)


def test_persist_and_read_resume_cursor(tmp_path: Path) -> None:
    path = persist_resume_cursor(
        tmp_path,
        stage="human_review",
        resume_cursor="cursor-1",
        reason="awaiting_human",
    )

    assert path == tmp_path / RESUME_CURSOR_FILENAME
    assert read_resume_cursor(tmp_path) == {
        "stage": "human_review",
        "resume_cursor": "cursor-1",
        "reason": "awaiting_human",
    }


def test_read_resume_cursor_absorbs_missing_and_malformed(tmp_path: Path) -> None:
    assert read_resume_cursor(tmp_path) is None
    (tmp_path / RESUME_CURSOR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
    assert read_resume_cursor(tmp_path) is None
    (tmp_path / RESUME_CURSOR_FILENAME).write_text("{", encoding="utf-8")
    assert read_resume_cursor(tmp_path) is None


def test_persist_and_read_composite_resume_cursor(tmp_path: Path) -> None:
    path = persist_composite_resume_cursor(
        tmp_path,
        children={"left": {"cursor": "a"}, "right": {"cursor": "b"}},
        shared_awaitable="approval/1",
    )

    assert path == tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME
    assert read_composite_resume_cursor(tmp_path) == {
        "kind": "composite_suspension",
        "version": 1,
        "children": {"left": {"cursor": "a"}, "right": {"cursor": "b"}},
        "shared_awaitable": "approval/1",
    }


def test_read_composite_resume_cursor_absorbs_missing_and_malformed(tmp_path: Path) -> None:
    assert read_composite_resume_cursor(tmp_path) is None
    (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).write_text(
        json.dumps(["not", "a", "dict"]),
        encoding="utf-8",
    )
    assert read_composite_resume_cursor(tmp_path) is None
