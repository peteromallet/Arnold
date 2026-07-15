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

from .status_tree import MAX_NODE_LIMIT
from .subagent import list_managed_resident_agents
from .timezone import format_timestamp


CURRENTLY_RUNNING_COMMAND = "whats-cooking"
CURRENTLY_RUNNING_DESCRIPTION = "Show running Megaplan epics, chains, and resident subagents."
_RUNNING_SESSION_STATUSES = frozenset({"running", "repairing"})
_ATTENTION_SESSION_STATUS = "attention"
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


async def collect_currently_running(runtime: Any) -> CurrentlyRunningReport:
    """Read only the bounded status root and the managed-agent inventory.

    The status read deliberately goes through the resident's typed
    ``read_cloud_status_node`` registration.  Discord must not know the path or
    schema of the complete watchdog JSON.
    """

    async def read_status_node() -> tuple[Mapping[str, Any] | None, str | None]:
        try:
            registration = runtime.profile.tools().get("read_cloud_status_node")
            payload = registration.input_model(
                node_id="root", cursor=0, limit=MAX_NODE_LIMIT
            )
            if inspect.iscoroutinefunction(registration.handler):
                result = await registration.handler(payload)
            else:
                result = await asyncio.to_thread(registration.handler, payload)
            if inspect.isawaitable(result):
                result = await result
            if not getattr(result, "ok", False):
                return None, "canonical status node is unavailable"
            data = getattr(result, "data", None)
            node = data.get("node") if isinstance(data, Mapping) else None
            if not isinstance(node, Mapping):
                return None, "canonical status node returned no bounded root"
            return node, None
        except Exception as exc:  # command must degrade independently by source
            return None, f"canonical status node read failed ({exc.__class__.__name__})"

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
    """Return sessions with active execution, preserving attention overlays."""

    if not isinstance(status_node, Mapping) or status_node.get("stale_banner"):
        return []
    sessions = status_node.get("sessions")
    if not isinstance(sessions, list):
        return []
    discovered: list[Mapping[str, Any]] = []
    for row in sessions:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status") or "").casefold()
        if status in _RUNNING_SESSION_STATUSES or row.get("repairing") is True:
            discovered.append(row)
            continue
        # ``attention`` is an operator overlay, not an execution state.  Keep
        # an attention-classified session in the active listing when the
        # bounded canonical projection still observes live work or repair.
        if status == _ATTENTION_SESSION_STATUS and (
            row.get("process") is True or row.get("repairing") is True
        ):
            discovered.append(row)
    return discovered


def discover_attention_sessions(
    status_node: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return recently active canonical attention/blocked non-live chains.

    ``latest_activity`` is the status projection's authoritative activity
    timestamp.  The snapshot observation clock is deliberately used as the
    reference, so replayed snapshots preserve their truthful rolling window.
    The boundary is inclusive: activity exactly twelve hours before the
    snapshot is shown.
    """

    if not isinstance(status_node, Mapping) or status_node.get("stale_banner"):
        return []
    snapshot_time = _parse_utc_timestamp(status_node.get("generated_at"))
    if snapshot_time is None:
        return []
    sessions = status_node.get("sessions")
    if not isinstance(sessions, list):
        return []
    running = {id(row) for row in discover_running_sessions(status_node)}
    return [
        row for row in sessions
        if isinstance(row, Mapping)
        and id(row) not in running
        and str(row.get("status") or "").casefold()
        in {_ATTENTION_SESSION_STATUS, "blocked"}
        and _is_within_attention_window(row, snapshot_time)
    ]


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


def discover_recently_completed_sessions(
    status_node: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    """Return bounded terminal-success rows from the canonical status root.

    The root's ``recently_completed`` list is a recency-sorted projection of
    all canonical completed sessions.  The legacy three-row preview is only a
    compatibility fallback, never a source of completion inference.
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
    ]


def render_currently_running(
    report: CurrentlyRunningReport, *, now: datetime | None = None
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
        snapshot = _snapshot_label(status_node)
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
        lines.append(
            _agents_heading(
                f"{len(agents)} live · {len(completed_agents)} recently completed"
            )
        )
        lines.append(_subsection_heading("🟢", "Running", str(len(agents))))
        if agents:
            # Every live agent remains visible. Discord delivery chunks the
            # finished view safely instead of silently hiding active work.
            lines.extend(_render_agent(row, now=now) for row in agents)
        else:
            lines.append("_No live resident-managed agents._")
        lines.append(
            _subsection_heading(
                "✅", "Recently completed", str(len(completed_agents))
            )
        )
        if completed_agents:
            lines.extend(_render_agent(row, now=now) for row in completed_agents)
        else:
            lines.append("_No recently completed resident-managed agents._")
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
    active_phase = progress.get("active_phase")
    if active_phase is None:
        active_phase = row.get("active_phase")
    effective_session_status = _effective_session_status(row)
    if display_state and not (
        effective_session_status == "repairing" and display_state.casefold() == "failed"
    ):
        status = display_state
    elif _phase_name(active_phase) == "execute":
        status = "executing"
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
    session_status = effective_session_status
    if session_status and session_status.casefold() == _ATTENTION_SESSION_STATUS:
        details.append("⚠️ attention")
        operator_next = _optional_label(row.get("operator_next"))
        if operator_next:
            details.append(_safe_label(operator_next))
    elif session_status and session_status.casefold() != status.casefold():
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


def _render_agent(row: Mapping[str, Any], *, now: datetime | None = None) -> str:
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
    return (
        f"• **{_safe_label(description)}**\n"
        f"  `{details[0]}`"
        f"{' · ' + ' · '.join(details[1:]) if len(details) > 1 else ''}"
        f"{identity_detail}"
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


def _snapshot_label(status_node: Mapping[str, Any]) -> str | None:
    """Return an honest UTC-formatted freshness line when the root supplies it."""

    generated_at = status_node.get("generated_at") or status_node.get(
        "watchdog_generated_at"
    )
    if not generated_at:
        return None
    try:
        rendered = format_timestamp(generated_at, "UTC")
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
