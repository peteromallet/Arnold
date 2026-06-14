"""Live status rendering for foreground bake-off runs."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core.state import load_plan
from arnold.pipelines.megaplan.bakeoff.state import bakeoff_root


def print_live_status(root: Path, exp_id: str) -> None:
    state_path = bakeoff_root(root, exp_id) / "bakeoff.json"
    if not state_path.exists():
        return
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    lines = ["profile | state | phase | iter | age | cost"]
    for record in data.get("profiles", []):
        lines.append(_profile_status_line(record))
    if len(lines) > 1:
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


def _profile_status_line(record: dict[str, Any]) -> str:
    plan_state: dict[str, Any] = {}
    worktree = Path(str(record.get("worktree", "")))
    if worktree.exists():
        try:
            _, plan_state = load_plan(worktree, record.get("plan_id"))
        except Exception:
            plan_state = {}
    meta = plan_state.get("meta") if isinstance(plan_state.get("meta"), dict) else {}
    active = plan_state.get("active_step") if isinstance(plan_state.get("active_step"), dict) else {}
    return " | ".join(
        [
            str(record.get("name") or ""),
            str(plan_state.get("current_state") or ""),
            str(active.get("phase") or active.get("step") or ""),
            str(plan_state.get("iteration") or ""),
            _age(record.get("launched_at")),
            str(meta.get("total_cost_usd") or ""),
        ]
    )


def _age(launched_at: Any) -> str:
    if not isinstance(launched_at, str) or not launched_at:
        return ""
    try:
        start = datetime.fromisoformat(launched_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    seconds = int((datetime.now(timezone.utc) - start).total_seconds())
    return f"{max(0, seconds)}s"
