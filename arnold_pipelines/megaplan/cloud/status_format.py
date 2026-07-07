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

When a session entry carries canonical resolver fields (``canonical_state``,
``canonical_resolver``, etc.) the formatters render the canonical
classification, stale-source warnings, and next-action hints alongside the
legacy output.  Entries without canonical fields continue to render exactly
as before — the formatters tolerate partial snapshots gracefully.
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

# Canonical-state emoji hints for short-format surfaces.
_CANONICAL_EMOJI: dict[str, str] = {
    "RUNNING": "🟢",
    "REPAIRING": "🛠️",
    "RETRYABLE_EXECUTION_BLOCK": "🔁",
    "REAL_IMPLEMENTATION_BLOCK": "🧱",
    "HUMAN_ACTION_REQUIRED": "👤",
    "COMPLETED": "✅",
    "STALE_DERIVED_STATE": "⏳",
    "BROKEN_STATE_MACHINE": "💥",
    "UNKNOWN": "❓",
}

# Human-readable short labels for canonical states.
_CANONICAL_LABEL: dict[str, str] = {
    "RUNNING": "running",
    "REPAIRING": "repairing",
    "RETRYABLE_EXECUTION_BLOCK": "retryable-block",
    "REAL_IMPLEMENTATION_BLOCK": "impl-block",
    "HUMAN_ACTION_REQUIRED": "needs-human",
    "COMPLETED": "complete",
    "STALE_DERIVED_STATE": "stale",
    "BROKEN_STATE_MACHINE": "broken-sm",
    "UNKNOWN": "unknown",
}


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


# --- canonical resolver rendering helpers ----------------------------------


def _canonical_info(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract canonical resolver fields from a session entry for rendering.

    Returns ``None`` when the entry carries no canonical resolver data, so
    callers can branch cleanly and preserve legacy output.
    """
    resolver = entry.get("canonical_resolver")
    if not isinstance(resolver, Mapping) or not resolver:
        return None
    return {
        "state": entry.get("canonical_state"),
        "reason": entry.get("canonical_reason"),
        "human_required": entry.get("canonical_human_required"),
        "human_gate": entry.get("canonical_human_gate"),
        "stale_sources": resolver.get("stale_sources") or [],
        "next_action": resolver.get("next_action", ""),
        "confidence": resolver.get("confidence", "medium"),
        "running": resolver.get("running", False),
        "repairable": resolver.get("repairable", False),
        "source_of_truth": resolver.get("source_of_truth") or [],
    }


def _canonical_short_tag(entry: Mapping[str, Any]) -> str:
    """Return a compact canonical-state tag suitable for Discord one-liners.

    Returns an empty string when there is no canonical data or when the
    canonical classification mirrors the legacy status (avoiding noise).
    """
    info = _canonical_info(entry)
    if info is None or not info["state"]:
        return ""
    state = str(info["state"])
    emoji = _CANONICAL_EMOJI.get(state, "❓")
    label = _CANONICAL_LABEL.get(state, state.lower())
    return f" {emoji}⟨{label}⟩"


def _canonical_stale_warning(entry: Mapping[str, Any]) -> str:
    """Return a compact stale-source warning, or empty string if none."""
    info = _canonical_info(entry)
    if info is None:
        return ""
    stale = info["stale_sources"]
    if not stale:
        return ""
    # Keep it short for Discord; truncate source names.
    names = [str(s)[:24] for s in stale[:3]]
    suffix = "…" if len(stale) > 3 else ""
    return f" ⚠️stale:{','.join(names)}{suffix}"


def _canonical_next_action_hint(entry: Mapping[str, Any]) -> str:
    """Return a compact next-action hint, or empty string if none."""
    info = _canonical_info(entry)
    if info is None:
        return ""
    action = info["next_action"]
    if not action or not isinstance(action, str) or not action.strip():
        return ""
    return f" → {action.strip()[:80]}"


def _canonical_detail_lines(entry: Mapping[str, Any]) -> list[str]:
    """Return multi-line canonical detail block for the CLI formatter.

    Returns an empty list when canonical data is absent so the detailed
    formatter can skip the block entirely.
    """
    info = _canonical_info(entry)
    if info is None:
        return []
    lines: list[str] = []
    state = info["state"]
    if state:
        label = _CANONICAL_LABEL.get(str(state), str(state).lower())
        lines.append(f"      canonical: {label} (confidence={info['confidence']})")
        reason = info["reason"]
        if reason:
            lines.append(f"      canonical_reason: {reason[:200]}")
    stale = info["stale_sources"]
    if stale:
        for i, src in enumerate(stale[:5]):
            lines.append(f"      stale_source[{i}]: {src}")
        if len(stale) > 5:
            lines.append(f"      … +{len(stale) - 5} more stale sources")
    action = info["next_action"]
    if action and isinstance(action, str) and action.strip():
        lines.append(f"      next_action: {action.strip()[:200]}")
    return lines


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
        if entry.get("operator_next") and status in {"repairing", "blocked", "attention"}:
            line += f" ({entry['operator_next']})"
        # --- canonical resolver hints (additive; absent fields produce empty strings) ---
        line += _canonical_short_tag(entry)
        line += _canonical_stale_warning(entry)
        line += _canonical_next_action_hint(entry)
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
        progress_str = (
            f"  progress={progress.get('percent')}%"
            if isinstance(progress, Mapping) and progress.get("percent") is not None
            else ""
        )
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
        # --- canonical resolver detail block (additive; absent → no output) ---
        out.extend(_canonical_detail_lines(entry))
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
        line = (
            f"{emoji} {entry.get('session', '?')}: {entry.get('status')} — "
            f"{entry.get('operator_next', '')}".rstrip()
        )
        # --- canonical resolver context (additive; absent → no suffix) ---
        canon_tag = _canonical_short_tag(entry)
        if canon_tag:
            line += canon_tag
        line += _canonical_next_action_hint(entry)
        lines.append(line)
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
