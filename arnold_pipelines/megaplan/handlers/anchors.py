from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.anchors import anchor_show_payload, format_anchor_show_text
from arnold_pipelines.megaplan.types import StepResponse


def handle_anchors(root: Path, args: argparse.Namespace) -> StepResponse:
    action = getattr(args, "anchors_action", None)
    if action != "show":
        return {"success": False, "step": "anchors", "summary": f"Unsupported anchors action: {action}"}

    from arnold_pipelines.megaplan._core import load_plan

    plan_name = getattr(args, "plan", None)
    plan_dir, state = load_plan(root, plan_name)
    payload: dict[str, Any] = anchor_show_payload(
        state,
        plan_dir,
        anchor_type=getattr(args, "anchor_type", "north_star") or "north_star",
    )
    if getattr(args, "as_json", False) or getattr(args, "json", False):
        return {"success": True, "step": "anchors", "plan": plan_name, **payload}
    return format_anchor_show_text(str(plan_name), payload)
