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

from datetime import datetime, timezone
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

# Activity age threshold for stale active-step warnings (seconds).
STALE_ACTIVE_STEP_S = 30 * 60


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
        text = f"plan bookkeeping {plan_percent}%"
        return f"{text} ({label})" if label else text
    return f"plan state {label}" if label else ""


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
        repair_summary = _repair_dispatch_summary(entry)
        if repair_summary:
            line += f" [{repair_summary}]"

        # Compact S4 annotations: semantic-health findings count, custody, warnings.
        s4_tags = _compact_s4_tags(entry)
        if s4_tags:
            line += " " + s4_tags

        lines.append(line)

    return _chunk_lines(lines, max_chars=max_chars)


def format_cloud_status_detailed(snapshot: Mapping[str, Any] | None) -> str:
    """Multi-line CLI / human view of the snapshot.

    Renders semantic health separately from lifecycle/activity, and custody
    separately from process liveness, including unmanaged-process and stale
    active-step warnings.
    """
    if not snapshot or not isinstance(snapshot, Mapping):
        return "Cloud status snapshot unavailable (degraded)."
    out = [f"Cloud status — {_summary_line(snapshot)}"]
    out.append(_evidence_citation(snapshot))
    degraded = snapshot.get("degraded")
    if isinstance(degraded, Mapping) and degraded.get("reasons"):
        out.append("degraded: " + "; ".join(degraded["reasons"]))
    out.append("")
    generated_at = _parse_iso(snapshot.get("generated_at"))
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
                progress_str += "  " + in_flight
            # Epic percentage-point change over the last 1h / 5h, from sweep history.
            delta_parts = []
            for window, key in (("1h", "epic_delta_1h"), ("5h", "epic_delta_5h")):
                delta = progress.get(key)
                if isinstance(delta, int):
                    delta_parts.append(f"{delta:+d} pp/{window}")
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
        projection_degraded = entry.get("repair_projection_degraded")
        if isinstance(projection_degraded, Mapping):
            reason = projection_degraded.get("reason") or "canonical repair projection unavailable"
            out.append(f"      repair_projection: degraded — {reason}")
        repair_summary = _repair_dispatch_summary(entry)
        if repair_summary:
            out.append(f"      repair_dispatch: {repair_summary}")
        evidence = entry.get("evidence") or {}
        if isinstance(evidence, Mapping) and evidence.get("marker"):
            out.append(f"      evidence: {evidence['marker']}")

        # --- S4: lifecycle / activity phase (separate from semantic health) ---
        _append_lifecycle_activity(out, entry)

        # --- S4: semantic health (separate from lifecycle/activity) ---
        _append_semantic_health(out, entry)

        # --- S4: custody (separate from process liveness) ---
        _append_custody_repair(out, entry)

        # --- S4: warnings ---
        _append_s4_warnings(out, entry, generated_at)

        _append_shadow_views(out, entry)

        # --- M9: evidence gaps (structured degraded-display annotations) ---
        _append_evidence_gaps(out, entry)

    # --- M9: source cursor vector ---
    cursor = snapshot.get("source_cursor_vector")
    if isinstance(cursor, Mapping) and cursor:
        authority = cursor.get("authority")
        if authority == "evidence_extracted_display_only" and isinstance(cursor.get("value"), Mapping):
            out.append("")
            out.append("source_cursor_vector [display-only, non-authoritative]: evidence provenance attached")
        elif authority == "absent":
            out.append("")
            out.append(f"source_cursor_vector: absent ({cursor.get('reason', 'not provided')})")

    return "\n".join(out)


# ── S4: compact tags for short format ──────────────────────────────────────


def _compact_s4_tags(entry: Mapping[str, Any]) -> str:
    """Build compact one-line S4 annotations for the short/Discord format.

    Returns a string like ``[SH:3] [custody:repairing] [⚠unmanaged]`` or
    empty string when nothing is noteworthy.
    """
    tags: list[str] = []

    # Semantic-health findings count (only when non-zero).
    health = entry.get("semantic_health")
    if isinstance(health, Mapping):
        total = health.get("total_count")
        if total:
            tags.append(f"[SH:{total}]")

    # Custody state when not empty/neutral.
    custody = entry.get("custody_state")
    if custody:
        tags.append(f"[custody:{custody}]")

    # Repair state when active.
    repair = entry.get("repair_state")
    if repair and repair != "none":
        tags.append(f"[repair:{repair}]")

    # Warnings compact.
    if entry.get("process") and not entry.get("tmux"):
        tags.append("[⚠unmanaged]")

    return " ".join(tags)


# ── S4: lifecycle / activity phase ────────────────────────────────────────


def _append_lifecycle_activity(out: list[str], entry: Mapping[str, Any]) -> None:
    """Render lifecycle state and activity phase independently from status.

    Lifecycle state is the plan's ``current_state`` (prepped, planned, …).
    Activity phase is the phase the session is currently in (execute, repair,
    blocked, …).  These are rendered together as one line because they are the
    two orthogonal axes of "what stage is the plan at" vs "what is the session
    doing right now."
    """
    lifecycle = entry.get("lifecycle_state")
    phase = entry.get("activity_phase")
    if lifecycle or phase:
        lc = lifecycle or "?"
        ap = phase or "?"
        out.append(f"      lifecycle: {lc}  activity: {ap}")


# ── S4: semantic health ───────────────────────────────────────────────────


def _append_semantic_health(out: list[str], entry: Mapping[str, Any]) -> None:
    """Render semantic-health projection independently from lifecycle/activity.

    The semantic-health payload is a read-only consumer projection produced by
    :func:`inspect_semantic_health` + :func:`cloud_counts_summary`.  It carries
    a stable fingerprint, total finding count, and dimension counts.  This
    line is separate from the lifecycle/activity line so operators can
    distinguish "the plan is executing" from "the plan has 3 boundary findings."
    """
    health = entry.get("semantic_health")
    if not isinstance(health, Mapping):
        return
    total = health.get("total_count")
    fp = health.get("fingerprint", "?")
    fp_short = fp[:12] if isinstance(fp, str) else "?"
    parts = [f"findings={total}" if total is not None else "findings=?"]
    parts.append(f"fp={fp_short}")

    # Add dimension counts for quick operator visibility.
    by_kind = health.get("counts_by_kind")
    if isinstance(by_kind, Mapping) and by_kind:
        kind_strs = [f"{k}:{v}" for k, v in sorted(by_kind.items())]
        parts.append("kinds={" + ", ".join(kind_strs) + "}")

    out.append("      semantic_health: " + "  ".join(parts))


# ── S4: custody / repair state ─────────────────────────────────────────────


def _append_custody_repair(out: list[str], entry: Mapping[str, Any]) -> None:
    """Render custody state separately from process liveness.

    Custody tracks the repair-queue bucket (repairing, repairable_not_repairing,
    broken_superfixer, …).  Process liveness (tmux/process booleans) is a
    separate concept shown elsewhere.  Repair state tells whether a repair loop
    is active, stale, or none.
    """
    custody = entry.get("custody_state")
    repair = entry.get("repair_state")
    repairable = entry.get("repairable_issue")
    parts: list[str] = []
    if custody:
        parts.append(f"custody={custody}")
    if repair and repair != "none":
        parts.append(f"repair={repair}")
    if isinstance(repairable, Mapping):
        kind = repairable.get("kind", "?")
        phase = repairable.get("phase", "")
        if phase:
            parts.append(f"issue={kind}/{phase}")
        else:
            parts.append(f"issue={kind}")
    if parts:
        out.append("      " + "  ".join(parts))


# ── S4: warnings ───────────────────────────────────────────────────────────


def _append_s4_warnings(
    out: list[str],
    entry: Mapping[str, Any],
    generated_at: datetime | None,
) -> None:
    """Emit operator-facing warnings for unmanaged processes and stale steps.

    - **unmanaged-process**: process liveness is true but the session is not
      under tmux — a runner that escaped its terminal and may not be monitored.
    - **stale active-step**: the ``latest_activity`` timestamp is older than
      ``STALE_ACTIVE_STEP_S`` relative to the snapshot generation time.
    """
    warnings: list[str] = []

    # Unmanaged-process: process alive, tmux dead.
    if entry.get("process") and not entry.get("tmux"):
        warnings.append("unmanaged-process (process alive without tmux)")

    # Stale active-step: activity_phase is active but latest_activity is old.
    activity_phase = entry.get("activity_phase", "")
    if activity_phase and activity_phase not in ("done", "complete", ""):
        latest = entry.get("latest_activity")
        if latest and generated_at:
            latest_dt = _parse_iso(latest)
            if latest_dt is not None:
                age_s = (generated_at - latest_dt).total_seconds()
                if age_s > STALE_ACTIVE_STEP_S:
                    age_min = int(age_s // 60)
                    warnings.append(
                        f"stale active-step (last activity {age_min}m ago)"
                    )

    if warnings:
        out.append("      warnings: " + "; ".join(warnings))


# ── M9: evidence gaps ──────────────────────────────────────────────────────


def _append_evidence_gaps(out: list[str], entry: Mapping[str, Any]) -> None:
    """Render structured evidence gaps for one session entry.

    Gaps are pure display annotations — they never feed dispatch, completion,
    cancellation, publication, or delivery.  Each gap is rendered as a single
    line prefixed with ``evidence_gap:`` so operators can distinguish degraded
    fields from live data.
    """
    gaps = entry.get("evidence_gaps")
    if not isinstance(gaps, Mapping) or not gaps:
        return
    for gap_key in sorted(gaps.keys()):
        gap = gaps[gap_key]
        if not isinstance(gap, Mapping):
            continue
        gap_id = gap.get("gap", gap_key)
        reason = gap.get("reason", "")
        status = gap.get("evidence_status", "unknown")
        out.append(f"      evidence_gap: {gap_id} [{status}] — {reason}")


# ── ISO parsing helper ──────────────────────────────────────────────────────


def _parse_iso(value: Any) -> datetime | None:
    """Parse a best-effort ISO-8601 string into a naive UTC datetime."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # Handle both 'Z' suffix and '+00:00' offset.
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


# ── shadow views ────────────────────────────────────────────────────────────


def _append_shadow_views(out: list[str], entry: Mapping[str, Any]) -> None:
    """Render the additive authority diagnostics without changing legacy status.

    The snapshot builder owns collection and classification.  This formatter only
    makes the independent, read-only projections visible to an operator, keeping
    their hashes and source-addressable contradictions close to the session that
    produced them.
    """

    execution = entry.get("execution_authority")
    if isinstance(execution, Mapping):
        out.append(
            "      execution_authority [shadow, read-only]: "
            f"accepted_tasks={len(execution.get('accepted_task_ids') or ())} "
            f"unresolved_claims={len(execution.get('unresolved_claim_ids') or ())} "
            f"quarantined={len(execution.get('quarantine_ids') or ())} "
            f"hash={execution.get('view_hash') or '?'}"
        )
        _append_shadow_diagnostics(out, execution)

    runner = entry.get("runner")
    if isinstance(runner, Mapping):
        out.append(
            "      runner [shadow, read-only]: "
            f"status={runner.get('status') or 'unknown'} "
            f"hash={runner.get('view_hash') or '?'}"
        )
        _append_shadow_diagnostics(out, runner)

    publication = entry.get("publication")
    if isinstance(publication, Mapping):
        out.append(
            "      publication [shadow, read-only]: "
            f"status={publication.get('status') or 'unknown'} "
            f"hash={publication.get('view_hash') or '?'}"
        )
        for observation in _sorted_mapping_items(publication.get("observations"), "field"):
            field = observation.get("field") or "unknown"
            state = observation.get("state") or "unknown"
            value = observation.get("value")
            rendered_value = f" value={value}" if value is not None else ""
            out.append(
                f"        observation: {field}={state}{rendered_value} "
                f"[source: {observation.get('source') or '?'}]"
            )
        _append_shadow_diagnostics(out, publication)

    human_gate = entry.get("human_gate")
    if isinstance(human_gate, Mapping):
        out.append(
            "      human_gate [shadow, read-only]: "
            f"status={human_gate.get('status') or 'unknown'} "
            f"human_required={human_gate.get('human_required')} "
            f"hash={human_gate.get('view_hash') or '?'}"
        )
        for observation in _sorted_mapping_items(human_gate.get("observations"), "observation_id"):
            gate_type = observation.get("gate_type") or "unknown"
            gate_reason = observation.get("gate_reason") or ""
            stale = observation.get("stale_token")
            superseded = observation.get("superseded")
            flags = []
            if stale:
                flags.append("stale")
            if superseded:
                flags.append("superseded")
            flag_str = f" [{','.join(flags)}]" if flags else ""
            out.append(
                f"        observation: {gate_type} - {gate_reason}{flag_str} "
                f"[source: {observation.get('source') or '?'}]"
            )
        _append_shadow_diagnostics(out, human_gate)

    recovery = entry.get("recovery")
    if isinstance(recovery, Mapping):
        out.append(
            "      recovery [shadow, read-only]: "
            f"status={recovery.get('status') or 'unknown'} "
            f"recovery_needed={recovery.get('recovery_needed')} "
            f"hash={recovery.get('view_hash') or '?'}"
        )
        for observation in _sorted_mapping_items(recovery.get("observations"), "observation_id"):
            bucket = observation.get("custody_bucket") or "unknown"
            state = observation.get("current_state") or ""
            active = observation.get("active_request_count")
            active_str = f" active_requests={active}" if active is not None else ""
            out.append(
                f"        custody: {bucket} state={state}{active_str} "
                f"[source: {observation.get('source') or '?'}]"
            )
        for action in _sorted_mapping_items(recovery.get("permitted_actions"), "action_id"):
            action_type = action.get("action_type") or "unknown"
            rationale = action.get("rationale") or ""
            out.append(
                f"        permitted: {action_type} — {rationale} "
                f"[source: {action.get('source') or '?'}]"
            )
        _append_shadow_diagnostics(out, recovery)

    # --- composition facade (aggregate hash only) ---------------------------
    facade = entry.get("megaplan_plan_view")
    if isinstance(facade, Mapping):
        out.append(
            "      megaplan_plan_view [shadow, read-only, facade]: "
            f"hash={facade.get('view_hash') or '?'} "
            f"schema_version={facade.get('schema_version') or '?'}"
        )


def _append_shadow_diagnostics(out: list[str], view: Mapping[str, Any]) -> None:
    """Append deterministic source paths and reasons for one shadow view."""

    for diagnostic in _sorted_mapping_items(view.get("diagnostics"), "code"):
        code = diagnostic.get("code") or "unknown"
        subject = diagnostic.get("subject_id") or diagnostic.get("field")
        subject_text = f" subject={subject}" if subject else ""
        out.append(
            f"        diagnostic: {code}{subject_text} — "
            f"{diagnostic.get('reason') or 'no reason provided'} "
            f"[source: {diagnostic.get('source') or '?'}]"
        )

    source_paths = sorted(
        str(path) for path in (view.get("source_paths") or ()) if isinstance(path, str) and path
    )
    if source_paths:
        out.append("        source_paths: " + ", ".join(source_paths))


def _sorted_mapping_items(value: Any, field: str) -> list[Mapping[str, Any]]:
    """Return mapping records in a stable order even for externally supplied data."""

    items = [item for item in (value or ()) if isinstance(item, Mapping)]
    return sorted(items, key=lambda item: (str(item.get(field) or ""), str(item.get("source") or "")))


def _repair_dispatch_summary(entry: Mapping[str, Any]) -> str:
    dispatch = entry.get("repair_dispatch")
    if not isinstance(dispatch, Mapping):
        return ""
    budget = dispatch.get("retry_budget")
    budget = budget if isinstance(budget, Mapping) else {}
    cursor = dispatch.get("evidence_cursor")
    cursor = cursor if isinstance(cursor, Mapping) else {}
    cursor_value = cursor.get("history_index") or cursor.get("event_seq") or "?"
    return (
        f"decision={dispatch.get('decision') or 'unknown'} "
        f"request/claim/attempt={dispatch.get('request_count', 0)}/"
        f"{dispatch.get('claim_count', 0)}/{dispatch.get('attempt_count', 0)} "
        f"budget={budget.get('remaining_attempts', '?')}/{budget.get('max_attempts', '?')} "
        f"cursor={cursor_value}"
    )


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
        base = (
            f"{emoji} {entry.get('session', '?')}: {entry.get('status')} — "
            f"{entry.get('operator_next', '')}".rstrip()
        )
        # Append compact S4 context.
        s4_tags = _compact_s4_tags(entry)
        if s4_tags:
            base += " " + s4_tags
        lines.append(base)
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
