"""Bounded discovery and Discord rendering for currently running resident work."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import inspect
import json
import os
from pathlib import Path
import re
from typing import Any

from agentbox.redaction import redact_text

from .subagent import list_managed_resident_agents
from .timezone import format_timestamp


CURRENTLY_RUNNING_COMMAND = "whats-cooking"
CURRENTLY_RUNNING_DESCRIPTION = "Show running Megaplan epics, chains, and resident subagents."
_RUNNING_SESSION_STATUSES = frozenset({"running", "repairing"})
_ATTENTION_SESSION_STATUS = "attention"
_NON_EXECUTION_SERVICE_SESSIONS = frozenset({"megaplan-resident-discord"})
_ATTENTION_WINDOW = timedelta(hours=12)
_TERMINAL_AGENT_STATUSES = frozenset(
    {"completed", "failed", "interrupted", "cancelled", "superseded", "unknown"}
)
_RECENT_AGENT_COMPLETION_WINDOW = timedelta(hours=1)
_MAX_LABEL_CHARS = 140
_MAX_RECENT_COMPLETED = 5
_EPICS_SECTION_ICON = "⛓️"
_AGENTS_SECTION_ICON = "🤖"
_OPAQUE_AGENT_LABELS = frozenset(
    {
        "handle the delegated resident request",
        "handle the delegated request",
        "handle the delegated task",
        "handle the resident request",
        "resident delegated agent",
    }
)
_SUBAGENT_ID_RE = re.compile(
    r"^subagent-\d{8}-(?P<time>\d{6})-(?P<suffix>[a-z0-9]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CurrentlyRunningReport:
    """The two canonical, independently degradable inputs to the command."""

    status_node: Mapping[str, Any] | None
    managed_agents: Mapping[str, Any] | None
    status_error: str | None = None
    managed_agents_error: str | None = None


@dataclass
class _ManagedAgentTree:
    """One node in a bounded, presentation-only managed-run forest."""

    row: Mapping[str, Any]
    index: int
    children: list["_ManagedAgentTree"]
    provenance_note: str | None = None


async def collect_currently_running(runtime: Any) -> CurrentlyRunningReport:
    """Collect a fresh bounded status root and the managed-agent inventory."""

    async def read_status_node() -> tuple[Mapping[str, Any] | None, str | None]:
        try:
            collector = runtime.profile.collect_fresh_cloud_status_root
            if inspect.iscoroutinefunction(collector):
                node = await collector()
            else:
                node = await asyncio.to_thread(collector)
            if inspect.isawaitable(node):
                node = await node
            if not isinstance(node, Mapping):
                return None, "fresh canonical status collection returned no bounded root"
            return node, None
        except Exception as exc:  # command must degrade independently by source
            return None, f"fresh canonical status collection failed ({exc.__class__.__name__})"

    async def read_managed_agents() -> tuple[Mapping[str, Any] | None, str | None]:
        project_root = Path(getattr(runtime, "project_root", Path.cwd()))
        try:
            result = await asyncio.to_thread(
                list_managed_resident_agents,
                project_root=project_root,
            )
            result = await asyncio.to_thread(
                _with_human_agent_descriptions,
                result,
                project_root=project_root,
            )
        except Exception as exc:  # command must still report canonical chain state
            return None, f"managed-agent inventory read failed ({exc.__class__.__name__})"
        return result, None

    (status_node, status_error), (managed_agents, managed_agents_error) = (
        await asyncio.gather(read_status_node(), read_managed_agents())
    )
    return CurrentlyRunningReport(
        status_node=status_node,
        managed_agents=managed_agents,
        status_error=status_error,
        managed_agents_error=managed_agents_error,
    )


def discover_running_sessions(status_node: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Return sessions with active execution, preserving attention overlays.

    M9 (T23): Consumes source-cursor-aware session rows.  Sessions whose
    source_cursor shows all-unknown or all-stale lifecycle/process_correlation
    dimensions without live process/tmux signals are rejected — unknown cannot
    be reported as running.  Attention overlays are preserved only when backed
    by execution truth (live process or repair), never from stale projection
    metadata alone.
    """

    if not isinstance(status_node, Mapping) or status_node.get("stale_banner"):
        return []
    sessions = status_node.get("sessions")
    if not isinstance(sessions, list):
        return []
    discovered: list[Mapping[str, Any]] = []
    for row in sessions:
        if not isinstance(row, Mapping):
            continue
        session = str(row.get("session") or "").strip().casefold()
        if session in _NON_EXECUTION_SERVICE_SESSIONS:
            continue
        # A live runner is useful liveness evidence, but canonical plan state
        # owns the presentation bucket. Blocked work belongs under attention.
        if (_canonical_progress_state(row) or "").casefold() == "blocked":
            continue
        status = str(row.get("status") or "").casefold()
        if status in _RUNNING_SESSION_STATUSES or row.get("repairing") is True:
            # ── M9: running/repairing truth preserved; source-cursor staleness
            #      does NOT demote a live execution signal, but sessions with
            #      missing timestamps are failed to unknown/no-active-authority.
            if _m9_session_has_authoritative_timestamps(row) is False:
                # Missing timestamps = cannot confirm execution progress →
                # fail to unknown, do not report as running.
                continue
            discovered.append(row)
            continue
        # ``attention`` is an operator overlay, not an execution state.  Keep
        # an attention-classified session in the active listing when the
        # bounded canonical projection still observes live work or repair.
        if status == _ATTENTION_SESSION_STATUS and (
            row.get("process") is True or row.get("repairing") is True
        ):
            # ── M9: attention overlay preserved only with execution truth ──
            if _m9_session_has_authoritative_timestamps(row) is not False:
                discovered.append(row)
    return discovered


def _m9_session_has_authoritative_timestamps(
    row: Mapping[str, Any],
) -> bool | None:
    """Check that a session row has authoritative timestamp evidence.

    Returns:
        ``True`` when timestamps are present and usable.
        ``False`` when timestamps are missing — session should fail to unknown.
        ``None`` when source_cursor shows all unknown (no authority to confirm).
    """
    # Check for source-cursor metadata
    source_cursor = row.get("source_cursor") if isinstance(row, Mapping) else None
    if isinstance(source_cursor, Mapping):
        dims = source_cursor.get("dimensions")
        if isinstance(dims, list):
            lifecycle_states = [
                d.get("state") for d in dims
                if isinstance(d, Mapping) and d.get("dimension") == "lifecycle"
            ]
            pc_states = [
                d.get("state") for d in dims
                if isinstance(d, Mapping) and d.get("dimension") == "process_correlation"
            ]
            # All-unknown lifecycle + process_correlation → no authority
            all_lc_unknown = lifecycle_states and all(s == "unknown" for s in lifecycle_states)
            all_pc_unknown = pc_states and all(s == "unknown" for s in pc_states)
            if all_lc_unknown and all_pc_unknown:
                return None

    # Check for essential timestamp fields
    latest_activity = row.get("latest_activity")
    generated_at = row.get("generated_at")
    if latest_activity is None and generated_at is None:
        return False
    return True


def discover_attention_sessions(
    status_node: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return canonical blocked/attention chains that remain useful to show.

    ``latest_activity`` is the status projection's authoritative activity
    timestamp.  The snapshot observation clock is deliberately used as the
    reference, so replayed snapshots preserve their truthful rolling window.
    The boundary is inclusive. Canonically blocked chains with a live runner
    remain visible regardless of the rolling window: liveness is detail, not a
    reason to misclassify the plan as running.

    M9 (T23): Sessions with missing timestamps are failed to unknown /
    no-active-authority and excluded from the attention listing.  Stale
    banners suppress the entire listing.
    """

    if not isinstance(status_node, Mapping) or status_node.get("stale_banner"):
        return []
    snapshot_time = _parse_utc_timestamp(status_node.get("generated_at"))
    if snapshot_time is None:
        # ── M9: missing snapshot timestamp → no active authority, return empty ──
        return []
    sessions = status_node.get("sessions")
    if not isinstance(sessions, list):
        return []
    running = {id(row) for row in discover_running_sessions(status_node)}
    discovered: list[Mapping[str, Any]] = []
    for row in sessions:
        if not isinstance(row, Mapping) or id(row) in running:
            continue
        if (
            str(row.get("session") or "").strip().casefold()
            in _NON_EXECUTION_SERVICE_SESSIONS
        ):
            continue
        if _m9_session_has_authoritative_timestamps(row) is False:
            continue
        canonical_blocked = (
            (_canonical_progress_state(row) or "").casefold() == "blocked"
        )
        session_attention = str(row.get("status") or "").casefold() in {
            _ATTENTION_SESSION_STATUS,
            "blocked",
        }
        if not (canonical_blocked or session_attention):
            continue
        if canonical_blocked and _runner_is_live(row):
            discovered.append(row)
        elif _is_within_attention_window(row, snapshot_time):
            discovered.append(row)
    return discovered


def _canonical_progress_state(row: Mapping[str, Any]) -> str | None:
    """Return canonical presentation state with the required fallback order."""

    progress = row.get("progress")
    if not isinstance(progress, Mapping):
        return None
    return _optional_label(progress.get("display_state")) or _optional_label(
        progress.get("plan_state")
    )


def _runner_is_live(row: Mapping[str, Any]) -> bool:
    """Keep process/session liveness distinct from canonical display state."""

    return (
        str(row.get("status") or "").casefold() in _RUNNING_SESSION_STATUSES
        or row.get("process") is True
        or row.get("repairing") is True
    )


def _is_within_attention_window(
    row: Mapping[str, Any], snapshot_time: datetime
) -> bool:
    """Return whether authoritative activity is in the preceding 12 hours."""

    latest_activity = _parse_utc_timestamp(row.get("latest_activity"))
    return bool(
        latest_activity is not None
        and timedelta() <= snapshot_time - latest_activity <= _ATTENTION_WINDOW
    )


def discover_live_managed_agents(
    managed_agents: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return only runs whose canonical managed-agent observation is live."""

    if not isinstance(managed_agents, Mapping):
        return []
    rows = managed_agents.get("running")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("live") is True
        and str(row.get("status") or "").casefold() not in _TERMINAL_AGENT_STATUSES
    ]


def discover_recently_completed_managed_agents(
    managed_agents: Mapping[str, Any] | None, *, snapshot_at: datetime
) -> list[Mapping[str, Any]]:
    """Return successful managed-agent completions from the preceding hour.

    The inventory's bounded ``recent`` projection remains the truncation
    boundary.  Only explicit successful completions are included; failed,
    interrupted, cancelled, superseded, unknown, and future-dated rows are
    excluded.  The exact one-hour boundary is inclusive.
    """

    if not isinstance(managed_agents, Mapping):
        return []
    rows = managed_agents.get("recent")
    if not isinstance(rows, list):
        return []
    reference = snapshot_at.astimezone(UTC)
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("status") or "").casefold() == "completed"
        and str(row.get("terminal_outcome") or "completed").casefold()
        == "completed"
        and (finished_at := _parse_utc_timestamp(row.get("finished_at"))) is not None
        and timedelta()
        <= reference - finished_at
        <= _RECENT_AGENT_COMPLETION_WINDOW
    ]


def _project_managed_agent_forest(
    rows: list[Mapping[str, Any]],
    *,
    parents_in_other_section: Mapping[str, str] | None = None,
) -> list[_ManagedAgentTree]:
    """Project bounded rows through durable ``run_id``/``parent_run_id`` edges.

    Query aggregation and ``delivery_owner_run_id`` deliberately do not create
    edges here: they govern synthesis/delivery cardinality, not process
    ancestry.

    Input order remains the sibling order.  Root groups are ordered by the
    earliest input position of any member, so nesting a newer child never
    silently moves the whole family behind an unrelated older run.  Missing or
    ambiguous evidence never suppresses a row: that row remains a root with an
    honest provenance note.
    """

    nodes = [
        _ManagedAgentTree(row=row, index=index, children=[])
        for index, row in enumerate(rows)
    ]
    indices_by_id: dict[str, list[int]] = {}
    for node in nodes:
        run_id = _managed_run_id(node.row.get("run_id"))
        if run_id is not None:
            indices_by_id.setdefault(run_id, []).append(node.index)

    parent_indices: list[int | None] = [None] * len(nodes)
    other_sections = parents_in_other_section or {}
    for node in nodes:
        run_id = _managed_run_id(node.row.get("run_id"))
        if run_id is None:
            node.provenance_note = "invalid or missing run ID; hierarchy unavailable"
            continue
        if len(indices_by_id[run_id]) != 1:
            node.provenance_note = "duplicate run ID; hierarchy unavailable"
            continue

        raw_parent = node.row.get("parent_run_id")
        if raw_parent is None or (
            isinstance(raw_parent, str) and not raw_parent.strip()
        ):
            continue
        parent_run_id = _managed_run_id(raw_parent)
        if parent_run_id is None:
            node.provenance_note = "invalid parent provenance"
            continue
        if parent_run_id == run_id:
            node.provenance_note = "invalid self-parent provenance"
            continue
        parent_matches = indices_by_id.get(parent_run_id, [])
        if len(parent_matches) == 1:
            parent_indices[node.index] = parent_matches[0]
        elif len(parent_matches) > 1:
            node.provenance_note = f"parent `{parent_run_id}` is ambiguous"
        elif parent_run_id in other_sections:
            node.provenance_note = (
                f"parent `{parent_run_id}` is in {other_sections[parent_run_id]}"
            )
        else:
            node.provenance_note = f"parent `{parent_run_id}` is outside this status window"

    # A parent relation is a functional graph.  Break every node participating
    # in a cycle, while allowing non-cyclic descendants to remain beneath the
    # now-rooted cycle members.
    cycle_nodes: set[int] = set()
    settled: set[int] = set()
    for start in range(len(nodes)):
        if start in settled:
            continue
        path: list[int] = []
        position: dict[int, int] = {}
        cursor: int | None = start
        while cursor is not None and cursor not in settled:
            if cursor in position:
                cycle_nodes.update(path[position[cursor] :])
                break
            position[cursor] = len(path)
            path.append(cursor)
            cursor = parent_indices[cursor]
        settled.update(path)
    for index in cycle_nodes:
        parent_indices[index] = None
        nodes[index].provenance_note = "invalid parent cycle; shown as a root"

    roots: list[_ManagedAgentTree] = []
    for node, parent_index in zip(nodes, parent_indices, strict=True):
        if parent_index is None:
            roots.append(node)
        else:
            nodes[parent_index].children.append(node)

    root_first_index: dict[int, int] = {node.index: node.index for node in roots}
    for node in nodes:
        cursor = node.index
        while (parent_index := parent_indices[cursor]) is not None:
            cursor = parent_index
        root_first_index[cursor] = min(root_first_index[cursor], node.index)
    roots.sort(key=lambda node: root_first_index[node.index])
    return roots


def _managed_run_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _managed_agent_section_ids(
    rows: list[Mapping[str, Any]], section: str
) -> dict[str, str]:
    """Return only unambiguous durable IDs for cross-section orphan labels."""

    counts: dict[str, int] = {}
    for row in rows:
        run_id = _managed_run_id(row.get("run_id"))
        if run_id is not None:
            counts[run_id] = counts.get(run_id, 0) + 1
    return {run_id: section for run_id, count in counts.items() if count == 1}


def _render_agent_forest(
    roots: list[_ManagedAgentTree], *, now: datetime | None
) -> list[str]:
    rendered: list[str] = []
    pending: list[tuple[_ManagedAgentTree, int]] = [
        (node, 0) for node in reversed(roots)
    ]
    while pending:
        node, depth = pending.pop()
        rendered.append(
            _render_agent(
                node.row,
                now=now,
                depth=depth,
                provenance_note=node.provenance_note,
            )
        )
        pending.extend((child, depth + 1) for child in reversed(node.children))
    return rendered


def discover_recently_completed_sessions(
    status_node: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return bounded terminal-success rows from the canonical status root.

    The root's ``recently_completed`` list is a recency-sorted projection of
    all canonical completed sessions.  The legacy three-row preview is only a
    compatibility fallback, never a source of completion inference.

    M9 (T23): Sessions with missing timestamps are excluded — completion
    cannot be confirmed without authoritative timestamp evidence.
    """

    if not isinstance(status_node, Mapping) or status_node.get("stale_banner"):
        return []
    rows = status_node.get("recently_completed")
    if not isinstance(rows, list):
        rows = status_node.get("completed_sessions_preview")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("status") or "").casefold()
        in {"complete", "completed", "finished", "success", "succeeded"}
        # ── M9: exclude completions without authoritative timestamps ──
        and _m9_session_has_authoritative_timestamps(row) is not False
    ]


def render_currently_running(
    report: CurrentlyRunningReport,
    *,
    now: datetime | None = None,
    timezone_name: str = "UTC",
) -> str:
    """Render a compact, truthful status card using Discord markdown."""

    status_node = report.status_node
    stale_banner = (
        str(status_node.get("stale_banner") or "").strip()
        if isinstance(status_node, Mapping)
        else ""
    )
    lines: list[str] = ["# Currently running"]
    if stale_banner:
        # This canonical banner is intentionally verbatim and must be first.
        lines = [stale_banner, "", *lines]
    if isinstance(status_node, Mapping):
        snapshot = _snapshot_label(status_node, timezone_name=timezone_name)
        if snapshot:
            lines.extend((snapshot, ""))

    attention = discover_attention_sessions(status_node)
    completed = discover_recently_completed_sessions(status_node)
    displayed_completed = completed[:_MAX_RECENT_COMPLETED]

    if report.status_error:
        lines.extend(
            (_epics_heading(), f"⚠️ {_safe_label(report.status_error)}.")
        )
    elif stale_banner:
        lines.extend((
            _epics_heading(),
            "⚠️ Progress unavailable — the canonical status snapshot is stale.",
        ))
    else:
        degraded = status_node.get("degraded") if isinstance(status_node, Mapping) else None
        sessions = discover_running_sessions(status_node)
        lines.append(_epics_heading(f"{len(sessions)} active"))
        if degraded:
            lines.append(f"⚠️ {_degraded_label(degraded)}")
        if sessions:
            lines.append(_subsection_heading("🟢", "Running", str(len(sessions))))
            lines.extend(_render_session(row) for row in sessions)

    if attention:
        lines.append(_subsection_heading("⚠️", "Needs attention", str(len(attention))))
        lines.extend(_render_session(row) for row in attention)
    if displayed_completed:
        lines.append(_subsection_heading("✅", "Recently completed", f"{len(displayed_completed)} shown"))
        lines.extend(_render_completed_session(row) for row in displayed_completed)
        omitted = max(
            0,
            len(completed) - len(displayed_completed),
            int(status_node.get("recently_completed_omitted_count") or 0)
            if isinstance(status_node, Mapping)
            else 0,
        )
        if omitted:
            lines.append(f"_…{omitted} older completed chains omitted._")

    lines.append("")
    if report.managed_agents_error:
        lines.extend(
            (
                _agents_heading(),
                f"⚠️ {_safe_label(report.managed_agents_error)}.",
            )
        )
    else:
        agents = discover_live_managed_agents(report.managed_agents)
        snapshot_at = _managed_agent_snapshot_time(status_node, now=now)
        completed_agents = discover_recently_completed_managed_agents(
            report.managed_agents, snapshot_at=snapshot_at
        )
        running_ids = _managed_agent_section_ids(agents, "Running")
        completed_ids = _managed_agent_section_ids(
            completed_agents, "Recently completed"
        )
        running_forest = _project_managed_agent_forest(
            agents, parents_in_other_section=completed_ids
        )
        completed_forest = _project_managed_agent_forest(
            completed_agents, parents_in_other_section=running_ids
        )
        lines.append(
            _agents_heading(
                f"{len(agents)} live · {len(completed_agents)} recently completed"
            )
        )
        lines.append(_subsection_heading("🟢", "Running", str(len(agents))))
        if agents:
            # Every live agent remains visible. Discord delivery chunks the
            # finished view safely instead of silently hiding active work.
            lines.extend(_render_agent_forest(running_forest, now=now))
        else:
            lines.append("_No live resident-managed agents._")
        lines.append(
            _subsection_heading(
                "✅", "Recently completed", str(len(completed_agents))
            )
        )
        if completed_agents:
            lines.extend(_render_agent_forest(completed_forest, now=now))
        else:
            lines.append("_No recently completed resident-managed agents._")
        omitted = _nonnegative_int(
            report.managed_agents.get("recent_omitted_count")
            if isinstance(report.managed_agents, Mapping)
            else None
        )
        if omitted:
            lines.append(
                f"_…{omitted} additional terminal managed runs omitted by the bounded inventory._"
            )
    return "\n".join(lines)


def _epics_heading(summary: str | None = None) -> str:
    """Return the consistent visual heading for canonical chain work."""

    return _section_heading(_EPICS_SECTION_ICON, "Epics & chains", summary)


def _agents_heading(summary: str | None = None) -> str:
    """Return the consistent visual heading for resident-managed work."""

    return _section_heading(_AGENTS_SECTION_ICON, "Managed agents", summary)


def _subsection_heading(icon: str, title: str, summary: str) -> str:
    """Return a Discord Markdown H3 subordinate to the Epics & chains H2."""

    return f"### {icon} {title} · {summary}"


def _section_heading(icon: str, title: str, summary: str | None = None) -> str:
    suffix = f" · {summary}" if summary else ""
    return f"## {icon} {title}{suffix}"


def _render_session(row: Mapping[str, Any]) -> str:
    progress = row.get("progress") if isinstance(row.get("progress"), Mapping) else {}
    name = _first_label(row.get("display_name"), row.get("session"), "unnamed session")
    current_plan = _first_label(progress.get("current_plan"), row.get("current_plan"))
    name_label = f"`{_safe_label(name)}`"
    if current_plan and current_plan.casefold() != name.casefold():
        name_label = f"{name_label} · `{_safe_label(current_plan)}`"

    display_state = _optional_label(progress.get("display_state"))
    canonical_progress_state = _canonical_progress_state(row)
    active_phase = progress.get("active_phase")
    if active_phase is None:
        active_phase = row.get("active_phase")
    effective_session_status = _effective_session_status(row)
    if display_state and not (
        effective_session_status == "repairing" and display_state.casefold() == "failed"
    ):
        status = display_state
    elif (
        canonical_progress_state
        and canonical_progress_state.casefold() == "blocked"
    ):
        status = canonical_progress_state
    elif _phase_name(active_phase) == "execute":
        status = "executing"
    elif effective_session_status == _ATTENTION_SESSION_STATUS:
        # ── M9 (T29): attention is an overlay, never the primary execution label.
        #      When a session has live process/repair evidence but an attention
        #      status, the main label must reflect execution truth, not the
        #      attention overlay.
        status = _first_label(
            progress.get("plan_state"), progress.get("display_state"), "active"
        )
    else:
        status = _first_label(
            progress.get("plan_state"), effective_session_status, "status unavailable"
        )
        if effective_session_status == "repairing" and status.casefold() == "failed":
            status = effective_session_status

    details: list[str] = []
    overall_percent = _percent(progress.get("percent"))
    if overall_percent is not None:
        details.append(f"{overall_percent}% overall")
        delta_1h = _percentage_point_delta(progress.get("epic_delta_1h"))
        if delta_1h is not None:
            details.append(f"{delta_1h:+g} pp in the past hour")
    else:
        details.append("overall progress unavailable")
    plan_percent = _percent(progress.get("plan_percent"))
    if plan_percent is not None:
        details.append(f"{plan_percent}% plan bookkeeping (not acceptance)")
    blocked_with_live_runner = status.casefold() == "blocked" and _runner_is_live(row)
    if blocked_with_live_runner:
        if row.get("process") is True:
            details.append("runner process alive")
        elif effective_session_status:
            details.append(f"runner {effective_session_status}")
    # ── M9 (T29): attention is an overlay, never the primary execution label.
    #      Check the raw session status for attention reasons separately from
    #      effective_session_status so that attention reasons remain visible
    #      even when repair overrides the effective status to "repairing".
    raw_status = _optional_label(row.get("status"))
    attention_shown = False
    if raw_status and raw_status.casefold() == _ATTENTION_SESSION_STATUS:
        details.append("⚠️ attention")
        attention_shown = True
        operator_next = _optional_label(row.get("operator_next"))
        if operator_next:
            details.append(_safe_label(operator_next))
    session_status = effective_session_status
    # Show chain status only when it differs from the primary label AND
    # attention has not already been shown (avoids redundant "chain attention").
    if (not attention_shown
            and session_status
            and session_status.casefold() != status.casefold()
            and not blocked_with_live_runner):
        details.append(f"chain {session_status}")
    return f"• {name_label}\n  `{_safe_label(status)}` · {' · '.join(details)}"


def _effective_session_status(row: Mapping[str, Any]) -> str | None:
    """Prefer an active repair signal over a stale failure display state."""

    session_status = _optional_label(row.get("status"))
    if row.get("repairing") is True or (
        session_status and session_status.casefold() == "repairing"
    ):
        return "repairing"
    return session_status


def _percentage_point_delta(value: object) -> int | float | None:
    """Return a canonical progress delta without treating absent history as zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _render_completed_session(row: Mapping[str, Any]) -> str:
    """Render a terminal-success chain using only canonical status evidence."""

    progress = row.get("progress") if isinstance(row.get("progress"), Mapping) else {}
    name = _first_label(row.get("display_name"), row.get("session"), "unnamed session")
    details = ["completed"]
    completed_count = progress.get("completed_count", row.get("completed_count"))
    milestone_count = progress.get("milestone_count", row.get("milestone_count"))
    if (
        isinstance(completed_count, int)
        and not isinstance(completed_count, bool)
        and isinstance(milestone_count, int)
        and not isinstance(milestone_count, bool)
        and milestone_count >= 0
    ):
        details.append(f"{completed_count}/{milestone_count} milestones")
    elif (percent := _percent(progress.get("percent"))) is not None:
        details.append(f"{percent}% overall")
    latest_activity = _parse_utc_timestamp(row.get("completed_at") or row.get("latest_activity"))
    if latest_activity is not None:
        details.append(f"completed {format_timestamp(latest_activity, 'UTC')}")
    suffix = f" · {' · '.join(details[1:])}" if len(details) > 1 else ""
    return f"• **{_safe_label(name)}**\n  `{details[0]}`{suffix}"


def _render_agent(
    row: Mapping[str, Any],
    *,
    now: datetime | None = None,
    depth: int = 0,
    provenance_note: str | None = None,
) -> str:
    description = _agent_description(row) or "Resident-managed task"
    status = _first_label(row.get("status"), "running")
    identity = _agent_identity(row.get("run_id"))
    identity_detail = f" · agent `{_safe_label(identity)}`" if identity else ""
    details = [_safe_label(status)]
    elapsed = _agent_elapsed(row, now=now)
    if elapsed:
        details.append(elapsed)
    token_usage = _agent_token_usage(row)
    if token_usage:
        details.append(token_usage)
    delivery = _agent_delivery_status(row)
    if delivery:
        details.append(delivery)
    marker = "• " if depth == 0 else f"{'  ' * depth}↳ "
    detail_indent = "  " * (depth + 1)
    if provenance_note:
        details.append(f"⚠ {_safe_label(provenance_note)}")
    return (
        f"{marker}**{_safe_label(description)}**\n"
        f"{detail_indent}`{details[0]}`"
        f"{' · ' + ' · '.join(details[1:]) if len(details) > 1 else ''}"
        f"{identity_detail}"
    )


def _agent_delivery_status(row: Mapping[str, Any]) -> str | None:
    """Render terminal Discord delivery state without changing delivery policy."""

    if str(row.get("status") or "").casefold() not in _TERMINAL_AGENT_STATUSES:
        return None
    delivery = row.get("completion_delivery")
    if not isinstance(delivery, Mapping):
        return None
    status = _optional_label(delivery.get("status"))
    if not status or status.casefold() == "not_applicable":
        return None
    return f"delivery {status.replace('_', ' ')}"


def _nonnegative_int(value: Any) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else 0
    )


def _agent_elapsed(row: Mapping[str, Any], *, now: datetime | None) -> str | None:
    """Render duration from durable lifecycle timestamps, never process guesses."""

    started_at = _parse_utc_timestamp(row.get("started_at"))
    if started_at is None:
        return None
    finished_at = (
        _parse_utc_timestamp(row.get("finished_at"))
        if str(row.get("status") or "").casefold() in _TERMINAL_AGENT_STATUSES
        else None
    )
    endpoint = finished_at or (now.astimezone(UTC) if now else datetime.now(UTC))
    elapsed = endpoint - started_at
    if elapsed < timedelta(0):
        return None
    return f"{_format_duration(elapsed)} elapsed"


def _agent_token_usage(row: Mapping[str, Any]) -> str | None:
    """Return only an explicitly persisted total-token measurement.

    The managed-agent manifest has no derived usage fallback.  In particular,
    max-token settings, log size, and provider session metadata are not usage.
    A future manifest writer may persist ``usage.total_tokens``; until then the
    field is omitted from the Discord view.
    """

    usage = row.get("usage")
    if not isinstance(usage, Mapping):
        return None
    total = usage.get("total_tokens")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        return None
    return f"{_format_token_count(total)} tokens used"


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _format_duration(value: timedelta) -> str:
    seconds = int(value.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _format_token_count(value: int) -> str:
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "m"


def _agent_description(row: Mapping[str, Any]) -> str | None:
    """Prefer a purpose-built label, rejecting known opaque launch defaults."""

    for field in ("display_description", "description"):
        candidate = _optional_label(row.get(field))
        if candidate and candidate.casefold().startswith("current request:"):
            candidate = candidate.split(":", 1)[1].strip()
        if candidate and not _is_opaque_agent_label(candidate):
            return candidate
    return None


def _is_opaque_agent_label(value: Any) -> bool:
    candidate = _optional_label(value)
    if not candidate:
        return True
    if candidate.casefold().startswith("current request:"):
        candidate = candidate.split(":", 1)[1].strip()
    normalized = candidate.casefold().rstrip(". !")
    return normalized in _OPAQUE_AGENT_LABELS


def _agent_identity(value: Any) -> str | None:
    run_id = _optional_label(value)
    if not run_id:
        return None
    match = _SUBAGENT_ID_RE.fullmatch(run_id)
    if match:
        return f"{match.group('time')}-{match.group('suffix')}"
    return run_id


def _with_human_agent_descriptions(
    inventory: Mapping[str, Any], *, project_root: Path
) -> dict[str, Any]:
    """Hydrate opaque legacy labels from their exact immutable inbound source."""

    result = dict(inventory)
    for field in ("running", "recent"):
        rows = inventory.get(field)
        if not isinstance(rows, list):
            continue
        hydrated: list[Any] = []
        for row in rows:
            if not isinstance(row, Mapping) or _agent_description(row):
                hydrated.append(row)
                continue
            source_label = _authoritative_source_label(row, project_root=project_root)
            hydrated.append(
                {**dict(row), "display_description": source_label}
                if source_label
                else row
            )
        result[field] = hydrated
    return result


def _authoritative_source_label(
    row: Mapping[str, Any], *, project_root: Path
) -> str | None:
    """Read one manifest-bound source record, refusing ambiguous provenance."""

    provenance = row.get("launch_provenance")
    if not isinstance(provenance, Mapping):
        return None
    source_record_id = str(provenance.get("source_record_id") or "").strip()
    conversation_id = str(provenance.get("resident_conversation_id") or "").strip()
    discord_message_id = str(
        provenance.get("discord_message_id")
        or provenance.get("reply_to_message_id")
        or ""
    ).strip()
    if not re.fullmatch(r"msg_[a-z0-9]+", source_record_id) or not conversation_id:
        return None

    roots: list[Path] = []
    configured_root = str(os.environ.get("MEGAPLAN_RESIDENT_STORE_ROOT") or "").strip()
    if configured_root:
        roots.append(Path(configured_root).expanduser().resolve())
    roots.append(project_root.resolve() / ".megaplan" / "resident")
    project_dir = str(row.get("project_dir") or "").strip()
    if project_dir:
        roots.append(Path(project_dir).resolve() / ".megaplan" / "resident")

    labels: set[str] = set()
    for root in dict.fromkeys(roots):
        try:
            record = json.loads(
                (root / "messages" / f"{source_record_id}.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, ValueError, TypeError):
            continue
        if (
            not isinstance(record, Mapping)
            or str(record.get("id") or "") != source_record_id
            or str(record.get("direction") or "") != "inbound"
            or str(record.get("conversation_id") or "") != conversation_id
            or (
                discord_message_id
                and str(record.get("discord_message_id") or "") != discord_message_id
            )
        ):
            continue
        label = _source_record_label(record)
        if label:
            labels.add(label)
    return next(iter(labels)) if len(labels) == 1 else None


def _source_record_label(record: Mapping[str, Any]) -> str | None:
    content = _optional_label(record.get("content"))
    if not content:
        return None
    reply = record.get("discord_reply_provenance")
    ancestors = reply.get("ancestors") if isinstance(reply, Mapping) else None
    ancestor = None
    if isinstance(ancestors, list) and ancestors and isinstance(ancestors[0], Mapping):
        ancestor = _optional_label(ancestors[0].get("content"))
    deictic = bool(
        len(content) <= 80
        and re.search(r"\b(?:this|that|it|yes|no)\b", content, re.IGNORECASE)
    )
    if deictic and ancestor:
        return f"{content} — re: {ancestor}"
    return content


def _snapshot_label(
    status_node: Mapping[str, Any], *, timezone_name: str = "UTC"
) -> str | None:
    """Return an honest user-local freshness line when the root supplies it."""

    generated_at = status_node.get("generated_at") or status_node.get(
        "watchdog_generated_at"
    )
    if not generated_at:
        return None
    try:
        rendered = format_timestamp(generated_at, timezone_name)
    except (TypeError, ValueError):
        return "_Snapshot time unavailable._"
    return f"_Snapshot generated {rendered}_"


def _managed_agent_snapshot_time(
    status_node: Mapping[str, Any] | None, *, now: datetime | None
) -> datetime:
    """Choose the renderer snapshot clock for rolling managed-agent status."""

    if isinstance(status_node, Mapping):
        generated_at = _parse_utc_timestamp(
            status_node.get("generated_at") or status_node.get("watchdog_generated_at")
        )
        if generated_at is not None:
            return generated_at
    return now.astimezone(UTC) if now else datetime.now(UTC)


def _degraded_label(value: Any) -> str:
    reasons = value.get("reasons") if isinstance(value, Mapping) else None
    if isinstance(reasons, list):
        rendered = "; ".join(
            _safe_label(reason) for reason in reasons[:2] if str(reason or "").strip()
        )
        if rendered:
            return f"Canonical epic/chain status is degraded: {rendered}."
    return "Canonical epic/chain status is degraded."


def _phase_name(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("phase") or value.get("name")
    return str(value or "").strip().casefold()


def _percent(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _optional_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    return value or None


def _first_label(*values: Any) -> str:
    for value in values:
        rendered = _optional_label(value)
        if rendered:
            return rendered
    return ""


def _safe_label(value: Any) -> str:
    text = " ".join(redact_text(str(value or "")).split()).strip()
    text = text.replace("@", "@\u200b").replace("`", "'")
    if len(text) > _MAX_LABEL_CHARS:
        text = f"{text[: _MAX_LABEL_CHARS - 1]}…"
    return text or "unavailable"


__all__ = [
    "CURRENTLY_RUNNING_COMMAND",
    "CURRENTLY_RUNNING_DESCRIPTION",
    "CurrentlyRunningReport",
    "collect_currently_running",
    "discover_live_managed_agents",
    "discover_recently_completed_managed_agents",
    "discover_attention_sessions",
    "discover_recently_completed_sessions",
    "discover_running_sessions",
    "render_currently_running",
]
