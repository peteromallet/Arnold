"""Query the append-only receipt audit log."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_COLUMNS = (
    "timestamp",
    "plan",
    "phase",
    "profile",
    "model",
    "duration_ms",
    "cost_usd",
    "scope_drift_severity",
    "verdict",
)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _since_cutoff(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)([hd])", value)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount)
    return datetime.now(timezone.utc) - delta


def _read_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                log.warning("Skipping malformed receipt line %s in %s: %s", line_number, path, exc)
                continue
            if isinstance(payload, dict):
                rows.append(payload)
            else:
                log.warning("Skipping non-object receipt line %s in %s", line_number, path)
    return rows


def _matches(receipt: dict[str, Any], args: Any, cutoff: datetime | None) -> bool:
    model = getattr(args, "model", None)
    if model and model not in {receipt.get("model_configured"), receipt.get("model_actual")}:
        return False
    phase = getattr(args, "phase", None)
    if phase and receipt.get("phase") != phase:
        return False
    profile = getattr(args, "profile", None)
    if profile and receipt.get("profile_name") != profile:
        return False
    if cutoff is not None:
        timestamp = _parse_timestamp(receipt.get("timestamp_utc"))
        if timestamp is None or timestamp < cutoff:
            return False
    return True


def _project(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": receipt.get("timestamp_utc"),
        "plan": receipt.get("plan_id"),
        "phase": receipt.get("phase"),
        "profile": receipt.get("profile_name"),
        "model": receipt.get("model_actual") or receipt.get("model_configured"),
        "duration_ms": receipt.get("duration_ms"),
        "cost_usd": receipt.get("cost_usd"),
        "scope_drift_severity": receipt.get("scope_drift_severity"),
        "verdict": receipt.get("verdict"),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _aggregations(records: list[dict[str, Any]], agg_spec: str) -> dict[str, Any]:
    requested = {part.strip() for part in agg_spec.split(",") if part.strip()}
    if not requested:
        return {}
    cost_values = [float(row["cost_usd"]) for row in records if isinstance(row.get("cost_usd"), int | float)]
    duration_values = [
        float(row["duration_ms"]) for row in records if isinstance(row.get("duration_ms"), int | float)
    ]
    result: dict[str, Any] = {
        "severity_distribution": dict(Counter(row.get("scope_drift_severity") for row in records)),
    }
    if "avg" in requested:
        result["avg"] = {
            "cost_usd": mean(cost_values) if cost_values else None,
            "duration_ms": mean(duration_values) if duration_values else None,
        }
    if "p50" in requested:
        result["p50"] = {
            "cost_usd": _percentile(cost_values, 0.50),
            "duration_ms": _percentile(duration_values, 0.50),
        }
    if "p95" in requested:
        result["p95"] = {
            "cost_usd": _percentile(cost_values, 0.95),
            "duration_ms": _percentile(duration_values, 0.95),
        }
    return result


def _format_table(records: list[dict[str, Any]], aggregations: dict[str, Any]) -> str:
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in records))
        for column in DEFAULT_COLUMNS
    }
    lines = [" | ".join(column.ljust(widths[column]) for column in DEFAULT_COLUMNS)]
    lines.append("-+-".join("-" * widths[column] for column in DEFAULT_COLUMNS))
    for row in records:
        lines.append(" | ".join(str(row.get(column, "")).ljust(widths[column]) for column in DEFAULT_COLUMNS))
    if aggregations:
        lines.append("")
        lines.append(json.dumps(aggregations, sort_keys=True))
    return "\n".join(lines) + "\n"


def handle_audit_query(root: Path, args: Any) -> Any:
    del root
    audit_dir = Path(
        getattr(args, "audit_dir", None)
        or os.environ.get("MEGAPLAN_AUDIT_DIR")
        or (Path.home() / ".megaplan" / "audit")
    )
    cutoff = _since_cutoff(getattr(args, "since", None))
    receipts = _read_receipts(audit_dir / "receipts.jsonl")
    records = [_project(receipt) for receipt in receipts if _matches(receipt, args, cutoff)]
    aggregations = _aggregations(records, getattr(args, "agg", "") or "")
    if getattr(args, "json", False):
        if aggregations:
            return {"records": records, "aggregations": aggregations}
        return records
    return _format_table(records, aggregations)
