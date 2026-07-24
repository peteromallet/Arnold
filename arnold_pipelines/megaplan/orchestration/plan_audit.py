"""Tiebreaker audit tracking — records and aggregates tiebreaker usage stats."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_json, read_json, resolve_plan_dir

AUDIT_FILE = "tiebreaker_audit.json"


def record_tiebreaker_audit(
    plan_dir: Path,
    decision: dict[str, Any],
    researcher_data: dict[str, Any],
    challenger_data: dict[str, Any],
    tokens_spent: int = 0,
    time_seconds: float = 0.0,
) -> dict[str, Any]:
    """Append an audit record to tiebreaker_audit.json in plan_dir."""
    record: dict[str, Any] = {
        "plan_name": decision.get("question", ""),
        "tiebreaker_index": _next_index(plan_dir),
        "fuzzy_group_id": decision.get("fuzzy_group_id", ""),
        "question": decision.get("question", ""),
        "researcher_pick": researcher_data.get("recommendation", ""),
        "challenger_pick": challenger_data.get("recommendation", ""),
        "human_pick": decision.get("human_pick", ""),
        "action": decision.get("action", ""),
        "matched_researcher": decision.get("human_pick", "") == researcher_data.get("recommendation", ""),
        "matched_challenger": decision.get("human_pick", "") == challenger_data.get("recommendation", ""),
        "tokens_spent": tokens_spent,
        "time_seconds": time_seconds,
        "timestamp": decision.get("timestamp", ""),
    }
    records = load_tiebreaker_audit(plan_dir)
    records.append(record)
    atomic_write_json(plan_dir / AUDIT_FILE, records)
    return record


def load_tiebreaker_audit(plan_dir: Path) -> list[dict[str, Any]]:
    """Read audit records from plan_dir. Returns empty list if none exist."""
    audit_path = plan_dir / AUDIT_FILE
    if not audit_path.exists():
        return []
    data = read_json(audit_path)
    if not isinstance(data, list):
        return []
    return data


def aggregate_tiebreaker_audit(root: Path) -> dict[str, Any]:
    """Cross-plan aggregation for --global flag. Scans all plan directories."""
    megaplan_dir = root / ".megaplan" / "plans"
    if not megaplan_dir.is_dir():
        return {"plans": [], "totals": _empty_totals()}

    plan_summaries: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []

    for plan_path in sorted(megaplan_dir.iterdir()):
        if not plan_path.is_dir():
            continue
        records = load_tiebreaker_audit(plan_path)
        if not records:
            continue
        all_records.extend(records)
        plan_summaries.append({
            "plan_dir": plan_path.name,
            "tiebreaker_count": len(records),
            "tokens_spent": sum(r.get("tokens_spent", 0) for r in records),
            "time_seconds": sum(r.get("time_seconds", 0) for r in records),
            "matched_researcher": sum(1 for r in records if r.get("matched_researcher")),
            "matched_challenger": sum(1 for r in records if r.get("matched_challenger")),
        })

    totals = _compute_totals(all_records)
    return {"plans": plan_summaries, "totals": totals}


def _next_index(plan_dir: Path) -> int:
    return len(load_tiebreaker_audit(plan_dir))


def _empty_totals() -> dict[str, Any]:
    return {
        "total_tiebreakers": 0,
        "total_tokens": 0,
        "total_time_seconds": 0.0,
        "matched_researcher_count": 0,
        "matched_challenger_count": 0,
    }


def _compute_totals(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return _empty_totals()
    return {
        "total_tiebreakers": len(records),
        "total_tokens": sum(r.get("tokens_spent", 0) for r in records),
        "total_time_seconds": sum(r.get("time_seconds", 0) for r in records),
        "matched_researcher_count": sum(1 for r in records if r.get("matched_researcher")),
        "matched_challenger_count": sum(1 for r in records if r.get("matched_challenger")),
    }


def render_audit_report(data: dict[str, Any]) -> str:
    """Render audit data as a human-readable text report."""
    lines: list[str] = []
    totals = data.get("totals", _empty_totals())
    lines.append("=== Tiebreaker Audit Report ===")
    lines.append(f"Total tiebreakers: {totals['total_tiebreakers']}")
    lines.append(f"Total tokens: {totals['total_tokens']}")
    lines.append(f"Total time: {totals['total_time_seconds']:.1f}s")
    lines.append(f"Matched researcher: {totals['matched_researcher_count']}")
    lines.append(f"Matched challenger: {totals['matched_challenger_count']}")

    plans = data.get("plans", [])
    if plans:
        lines.append("")
        lines.append("Per-plan breakdown:")
        for p in plans:
            lines.append(
                f"  {p['plan_dir']}: {p['tiebreaker_count']} tiebreakers, "
                f"{p['tokens_spent']} tokens, {p['time_seconds']:.1f}s"
            )

    return "\n".join(lines)
