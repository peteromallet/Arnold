"""Metric extraction for bake-off comparison."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core.io import collect_git_diff_patch
from arnold.pipelines.megaplan.bakeoff.state import BakeoffProfileRecord, BakeoffState


SCOPE_DRIFT_PENDING = {
    "plan": None,
    "critique": None,
    "gate": None,
    "finalize": None,
    "execute": None,
    "review": None,
    "sprint1_pending": True,
}


def collect_profile_metrics(
    bakeoff_state: BakeoffState,
    profile_record: BakeoffProfileRecord,
) -> dict[str, Any]:
    worktree = Path(profile_record["worktree"])
    plan_id = profile_record["plan_id"]
    plan_dir = worktree / ".megaplan" / "plans" / plan_id
    # cache-tolerant: read-only metrics emit, tolerates between-write skew.
    plan_state = _read_json(plan_dir / "state.json")
    outcome = profile_record.get("outcome") or {}
    mode = bakeoff_state.get("mode") or "code"
    output_path = bakeoff_state.get("output_path")
    patch = collect_git_diff_patch(worktree) if worktree.exists() else None
    review = _read_json(plan_dir / "review.json")

    metrics: dict[str, Any] = {
        "duration_s": _duration_s(profile_record.get("launched_at"), profile_record.get("terminated_at")),
        "cost_usd": _cost_usd(plan_state),
        "rework_cycles": _rework_cycles(plan_state, outcome),
        "escalations": _escalations(plan_state),
        "review_verdict": review.get("verdict") if isinstance(review.get("verdict"), str) else None,
        "diff_lines": _diff_lines(patch),
        "tests_added": _tests_added(patch),
        "scope_drift_severity_by_phase": dict(SCOPE_DRIFT_PENDING),
        "final_state": _final_state(plan_state, outcome),
        "outcome_status": outcome.get("status") if isinstance(outcome.get("status"), str) else None,
        "receipts_ref": _receipts_ref(plan_state, plan_dir),
    }
    if mode == "doc":
        # In doc-mode bake-offs, the "deliverable" is the doc artifact at
        # output_path inside each worktree, not the code diff. Surface
        # doc-specific metrics so judges and the markdown table can compare
        # apples to apples; tests_added is a code-mode concept and stays None.
        doc_metrics = _collect_doc_metrics(worktree, output_path)
        metrics.update(doc_metrics)
    return metrics


def _collect_doc_metrics(worktree: Path, output_path: str | None) -> dict[str, Any]:
    if not output_path:
        return {
            "doc_path": None,
            "doc_present": False,
            "doc_size_bytes": None,
            "doc_line_count": None,
            "tests_added": None,
        }
    doc_abs = worktree / output_path
    if not doc_abs.exists() or not doc_abs.is_file():
        return {
            "doc_path": output_path,
            "doc_present": False,
            "doc_size_bytes": None,
            "doc_line_count": None,
            "tests_added": None,
        }
    try:
        text = doc_abs.read_text(encoding="utf-8")
    except OSError:
        return {
            "doc_path": output_path,
            "doc_present": True,
            "doc_size_bytes": None,
            "doc_line_count": None,
            "tests_added": None,
        }
    return {
        "doc_path": output_path,
        "doc_present": True,
        "doc_size_bytes": len(text.encode("utf-8")),
        "doc_line_count": len(text.splitlines()),
        # tests_added is a code-mode concept; in doc mode keep it absent so
        # the comparison table doesn't claim "0 tests" as a meaningful signal.
        "tests_added": None,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _history(plan_state: dict[str, Any]) -> list[dict[str, Any]]:
    history = plan_state.get("history")
    return [entry for entry in history if isinstance(entry, dict)] if isinstance(history, list) else []


def _duration_s(start: Any, end: Any) -> float | None:
    started = _parse_time(start)
    ended = _parse_time(end)
    if started is None or ended is None:
        return None
    return max(0.0, round((ended - started).total_seconds(), 3))


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cost_usd(plan_state: dict[str, Any]) -> float | None:
    costs = [entry.get("cost_usd") for entry in _history(plan_state)]
    numeric = [float(value) for value in costs if isinstance(value, (int, float))]
    if numeric:
        return round(sum(numeric), 6)
    meta = plan_state.get("meta") if isinstance(plan_state.get("meta"), dict) else {}
    value = meta.get("total_cost_usd")
    return round(float(value), 6) if isinstance(value, (int, float)) else None


def _rework_cycles(plan_state: dict[str, Any], outcome: dict[str, Any]) -> int | None:
    review_cycles = max(0, sum(1 for entry in _history(plan_state) if entry.get("step") == "review") - 1)
    event_cycles = _rework_cycles_from_events(outcome)
    return max(review_cycles, event_cycles) if event_cycles is not None else review_cycles


def _rework_cycles_from_events(outcome: dict[str, Any]) -> int | None:
    events = outcome.get("events")
    if not isinstance(events, list):
        return None
    found: int | None = None
    for event in events:
        if not isinstance(event, dict):
            continue
        marker = event.get("type") or event.get("event") or event.get("name")
        if marker != "review_rework_cycle_count":
            continue
        for key in ("count", "cycles", "value"):
            value = event.get(key)
            if isinstance(value, int):
                found = max(found or 0, value)
    return found


def _escalations(plan_state: dict[str, Any]) -> int | None:
    count = sum(1 for entry in _history(plan_state) if entry.get("recommendation") == "ESCALATE")
    last_gate = plan_state.get("last_gate") if isinstance(plan_state.get("last_gate"), dict) else {}
    if last_gate.get("recommendation") == "ESCALATE" and count == 0:
        count += 1
    return count


def _final_state(plan_state: dict[str, Any], outcome: dict[str, Any]) -> str | None:
    for key in ("final_state", "state"):
        value = outcome.get(key)
        if isinstance(value, str):
            return value
    value = plan_state.get("current_state")
    return value if isinstance(value, str) else None


def _diff_lines(patch: str | None) -> int | None:
    if patch is None:
        return None
    if patch == "No git changes detected.":
        return 0
    return sum(
        1
        for line in patch.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
    )


def _tests_added(patch: str | None) -> int | None:
    if patch is None:
        return None
    added = 0
    current_path: str | None = None
    new_file = False
    removed_content = False
    for line in [*patch.splitlines(), "diff --git a/__end__ b/__end__"]:
        if line.startswith("diff --git "):
            if current_path and new_file and not removed_content and _is_test_path(current_path):
                added += 1
            current_path = _new_path_from_diff_header(line)
            new_file = False
            removed_content = False
        elif line.startswith("new file mode"):
            new_file = True
        elif line.startswith("-") and not line.startswith("---"):
            removed_content = True
    return added


def _new_path_from_diff_header(line: str) -> str | None:
    parts = line.split()
    if len(parts) < 4:
        return None
    path = parts[3]
    return path[2:] if path.startswith("b/") else path


def _is_test_path(path: str) -> bool:
    candidate = Path(path)
    return path.startswith("tests/") or (candidate.name.startswith("test_") and candidate.suffix == ".py")


def _receipts_ref(plan_state: dict[str, Any], plan_dir: Path) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for entry in _history(plan_state):
        output_file = entry.get("output_file")
        if isinstance(output_file, str) and output_file:
            _append_ref(refs, seen, _relative_to_plan_dir(Path(output_file), plan_dir))
    receipts_dir = plan_dir / "receipts"
    if receipts_dir.exists():
        for receipt in sorted(receipts_dir.glob("*.json")):
            _append_ref(refs, seen, receipt.relative_to(plan_dir).as_posix())
    return refs


def _relative_to_plan_dir(path: Path, plan_dir: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(plan_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _append_ref(refs: list[str], seen: set[str], value: str) -> None:
    if value not in seen:
        refs.append(value)
        seen.add(value)
