"""CLI helpers for explicit graph-to-native cursor upgrades."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from arnold.pipeline.native.checkpoint import (
    CursorUpgradeError,
    NativeCursorCorruptError,
    upgrade_graph_cursor_to_native,
)
from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipelines.megaplan.pipeline import megaplan


def run_upgrade_cursor(plan_dir: str | Path, *, dry_run: bool = True) -> int:
    """Run the cursor upgrade command and print a JSON diagnostic."""

    root = Path(plan_dir)
    try:
        if not root.exists():
            raise CursorUpgradeError(
                "missing_plan_dir",
                f"Plan directory does not exist: {root}",
                cursor_path=str(root / "resume_cursor.json"),
            )
        result = upgrade_graph_cursor_to_native(
            root,
            program=compile_pipeline(megaplan),
            dry_run=dry_run,
        )
    except NativeCursorCorruptError as exc:
        _print_error(
            code="corrupt_native_cursor",
            message=exc.detail,
            cursor_path=exc.cursor_path,
        )
        return 1
    except CursorUpgradeError as exc:
        _print_error(
            code=exc.code,
            message=exc.detail,
            cursor_path=exc.cursor_path,
            details=exc.details,
        )
        return 1

    print(json.dumps(result.to_jsonable(), indent=2))
    return 0


def _print_error(
    *,
    code: str,
    message: str,
    cursor_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "success": False,
        "error": code,
        "message": message,
    }
    if cursor_path:
        payload["cursor_path"] = cursor_path
    if details:
        payload["details"] = dict(details)
    print(json.dumps(payload, indent=2), file=sys.stderr)


__all__ = ["run_upgrade_cursor"]
