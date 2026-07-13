"""Shared formatters for the canonical cloud status snapshot.

One formatter set, consumed by every status surface so they can never disagree:

- :func:`format_cloud_status_short` — compact Discord reply (chunked to fit the
  2000-character message limit).
- :func:`format_cloud_status_detailed` — multi-line CLI / human view.
- :func:`format_attention_only` — watchdog alert body for sessions needing eyes.

All three take the snapshot dict produced by
:mod:`arnold_pipelines.megaplan.cloud.status_snapshot` and render plain text.
They never read files or SSH; they only format what the snapshot already holds,
so a snapshot is genuinely the single source of truth.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

# Discord's hard per-message ceiling. Stay under it with headroom for code fences.
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_SAFE_LIMIT = 1900

_STATUS_EMOJI = {
    "running": "🟢",
    "repairing": "🛠️",
    "blocked": "🚫",
    "complete": "✅",
    "attention": "⚠️",
}

_STATUS_ORDER = ("running", "repairing", "blocked", "attention", "complete")


def _summary_line(snapshot: Mapping[str, Any]) -> str:
    summary = snapshot.get("summary") or {}
    parts = [
        f"{summary.get('running', 0)} running",
        f"{summary.get('repairing', 0)} repairing",
        f"{summary.get('blocked', 0)} blocked",
        f"{summary.get('attention', 0)} attention",
        f"{summary.get('complete', 0)} complete",
    ]
    return ", ".join(parts)


def _evidence_citation(snapshot: Mapping[str, Any]) -> str:
    generated = snapshot.get("generated_at") or snapshot.get("watchdog_generated_at") or "?"
    source = snapshot.get("source", "?")
    return f"source: {source} · generated: {generated}"


def _ordered_sessions(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sessions = [s for s in (snapshot.get("sessions") or []) if isinstance(s, Mapping)]

    def rank(entry: Mapping[str, Any]) -> tuple[int, str]:
        status = entry.get("status", "")
        try:
            return (_STATUS_ORDER.index(status), entry.get("session", ""))
        except ValueError:
            return (len(_STATUS_ORDER), entry.get("session", ""))

    return sorted(sessions, key=rank)


def _in_flight_progress_text(progress: Any) -> str:
    """Render progress with the canonical derived label when it is available."""
    if not isinstance(progress, Mapping):
        return ""
    label = progress.get("display_state") or progress.get("plan_state")
    plan_percent = progress.get("plan_percent")
    if plan_percent is not None:
        text = f"in-flight {plan_percent}%"
        return f"{text} ({label})" if label else text
    return f"in-flight {label}" if label else ""


def format_cloud_status_short(
    snapshot: Mapping[str, Any] | None,
    *,
    max_chars: int = DISCORD_SAFE_LIMIT,
) -> list[str]:
    """Compact Discord reply, chunked to fit the message limit.

    Returns one or more strings; each fits under ``max_chars``. An absent
    snapshot yields a single explicit degraded-mode message so the resident
    never answers partial plan files as full cloud status.
    """
    if not snapshot or not isinstance(snapshot, Mapping) or not snapshot.get("sessions"):
        reason = "snapshot unavailable"
        if snapshot and isinstance(snapshot, Mapping):
            degraded = snapshot.get("degraded")
            if isinstance(degraded, Mapping) and degraded.get("reasons"):
                reason = "; ".join(degraded["reasons"])
        return [
            f"Cloud status is degraded: {reason}. "
            "Falling back to local plan evidence only — this is NOT the canonical shared-runner view."
        ]

    header = (
        f"**Cloud status:** {_summary_line(snapshot)}\n"
        f"{_evidence_citation(snapshot)}"
    )
    lines = [header]
    for entry in _ordered_sessions(snapshot):
        status = entry.get("status", "attention")
        emoji = _STATUS_EMOJI.get(status, "❓")
        plan = entry.get("current_plan") or entry.get("session", "?")
        line = f"{emoji} `{entry.get('session', '?')}` — {status}: {plan}"
        in_flight = _in_flight_progress_text(entry.get("progress"))
        if in_flight:
            line += f"; {in_flight}"
        if entry.get("operator_next") and status in {"repairing", "blocked", "attention"}:
            line += f" ({entry['operator_next']})"
        lines.append(line)

    return _chunk_lines(lines, max_chars=max_chars)


def format_cloud_status_detailed(snapshot: Mapping[str, Any] | None) -> str:
    """Multi-line CLI / human view of the snapshot."""
    if not snapshot or not isinstance(snapshot, Mapping):
        return "Cloud status snapshot unavailable (degraded)."
    out = [f"Cloud status — {_summary_line(snapshot)}"]
    out.append(_evidence_citation(snapshot))
    degraded = snapshot.get("degraded")
    if isinstance(degraded, Mapping) and degraded.get("reasons"):
        out.append("degraded: " + "; ".join(degraded["reasons"]))
    out.append("")
    for entry in _ordered_sessions(snapshot):
        status = entry.get("status", "attention")
        progress = entry.get("progress")
        progress_str = ""
        if isinstance(progress, Mapping) and progress.get("percent") is not None:
            progress_str = f"  progress={progress.get('percent')}%"
            # In-flight plan stage estimate (completed lifecycle stages / total),
            # or the raw plan state when it is not percentage-able (e.g. blocked).
            in_flight = _in_flight_progress_text(progress)
            if in_flight:
                progress_str += "  plan=" + in_flight.removeprefix("in-flight ")
            # Epic % gained over the last 1h / 5h, from sweep history.
            delta_parts = []
            for window, key in (("1h", "epic_delta_1h"), ("5h", "epic_delta_5h")):
                delta = progress.get(key)
                if isinstance(delta, int):
                    delta_parts.append(f"{delta:+d}%/{window}")
            if delta_parts:
                progress_str += "  (" + ", ".join(delta_parts) + ")"
            # Ladder stages the plan newly reached in the past hour.
            stage_changes = progress.get("stage_changes_1h") or []
            if stage_changes:
                progress_str += "  stages1h:" + "→".join(stage_changes)
        out.append(
            f"[{status}] {entry.get('session', '?')}  "
            f"plan={entry.get('current_plan') or '-'}  "
            f"completed={entry.get('completed_count')}/{entry.get('milestone_count') or '-'}"
            f"{progress_str}"
        )
        if entry.get("latest_activity"):
            out.append(f"      latest_activity: {entry['latest_activity']}")
        if entry.get("operator_next"):
            out.append(f"      operator_next: {entry['operator_next']}")
        evidence = entry.get("evidence") or {}
        if isinstance(evidence, Mapping) and evidence.get("marker"):
            out.append(f"      evidence: {evidence['marker']}")
    return "\n".join(out)


def format_attention_only(snapshot: Mapping[str, Any] | None) -> str:
    """Watchdog alert body: only sessions needing human or repair attention.

    Returns an empty string when nothing needs attention, so callers can skip
    the notification entirely.
    """
    if not snapshot or not isinstance(snapshot, Mapping):
        return ""
    noteworthy = [
        entry
        for entry in (snapshot.get("sessions") or [])
        if isinstance(entry, Mapping) and entry.get("status") in {"blocked", "attention", "repairing"}
    ]
    if not noteworthy:
        return ""
    lines = [f"Cloud status needs attention — {_summary_line(snapshot)}"]
    for entry in sorted(noteworthy, key=lambda e: _STATUS_ORDER.index(e.get("status", "attention")) if e.get("status") in _STATUS_ORDER else len(_STATUS_ORDER)):
        emoji = _STATUS_EMOJI.get(entry.get("status"), "⚠️")
        lines.append(
            f"{emoji} {entry.get('session', '?')}: {entry.get('status')} — "
            f"{entry.get('operator_next', '')}".rstrip()
        )
    return "\n".join(lines)


def _chunk_lines(lines: Iterable[str], *, max_chars: int) -> list[str]:
    """Pack lines into the fewest chunks that each fit under ``max_chars``."""
    cap = max(64, int(max_chars))
    chunks: list[str] = []
    current: list[str] = []
    running = 0
    for line in lines:
        cost = len(line) + 1  # +1 for the joining newline
        if cost > cap and not current:
            # A single oversized line becomes its own chunk (truncated hard).
            chunks.append(line[: cap - 1])
            current = []
            running = 0
            continue
        if current and running + cost > cap:
            chunks.append("\n".join(current))
            current = []
            running = 0
        current.append(line)
        running += cost
    if current:
        chunks.append("\n".join(current))
    return chunks or [""]
