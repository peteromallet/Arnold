"""Discord application-command helpers for managed-agent follow-up."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from arnold_pipelines.megaplan.resident.provenance import (
    DelegationProvenanceError,
    normalize_delegation_provenance,
)
from arnold_pipelines.megaplan.resident.subagent import list_managed_resident_agents


FOLLOW_UP_COMMAND = "follow-up"
FOLLOW_UP_DESCRIPTION = "Interrupt and continue one live resident-managed agent."
_FULL_RUN_ID_RE = re.compile(
    r"^subagent-[0-9]{8}-[0-9]{6}-[A-Za-z0-9]{8}$"
)
_DISPLAYED_SUFFIX_RE = re.compile(r"^[0-9]{6}-[A-Za-z0-9]{8}$")


class DiscordFollowUpError(ValueError):
    """The slash-command target, provenance, or instruction is unsafe."""


@dataclass(frozen=True)
class LiveManagedAgentTarget:
    """One exact live run selected from the canonical managed inventory."""

    run_id: str
    manifest_path: str
    launch_provenance: dict[str, Any]
    status: str


def displayed_run_suffix(run_id: str) -> str | None:
    """Return the same suffix shown by ``/whats-cooking``."""

    if not _FULL_RUN_ID_RE.fullmatch(run_id):
        return None
    return "-".join(run_id.split("-")[-2:])


def resolve_live_managed_agent(
    selector: str,
    *,
    project_root: str | Path,
    workspace_root: str | Path | None = "/workspace",
) -> LiveManagedAgentTarget:
    """Resolve one full run ID or unique displayed suffix, live-only."""

    selector = str(selector or "").strip()
    if not (
        _FULL_RUN_ID_RE.fullmatch(selector)
        or _DISPLAYED_SUFFIX_RE.fullmatch(selector)
    ):
        raise DiscordFollowUpError(
            "agent must be a full managed run ID or displayed suffix such as "
            "191551-60596066"
        )

    inventory = list_managed_resident_agents(
        project_root=Path(project_root).resolve(),
        workspace_root=workspace_root,
        recent_limit=1_000_000,
        queue_limit=1_000_000,
    )
    rows: list[Mapping[str, Any]] = []
    for field in ("running", "queued", "recent"):
        values = inventory.get(field)
        if isinstance(values, list):
            rows.extend(row for row in values if isinstance(row, Mapping))

    def matches(row: Mapping[str, Any]) -> bool:
        run_id = str(row.get("run_id") or "")
        return run_id == selector or displayed_run_suffix(run_id) == selector

    candidates = [row for row in rows if matches(row)]
    unique_locations = {
        (str(row.get("run_id") or ""), str(row.get("manifest_path") or ""))
        for row in candidates
    }
    if len(unique_locations) > 1:
        matched_ids = sorted({run_id for run_id, _path in unique_locations})
        raise DiscordFollowUpError(
            "agent selector is ambiguous across managed runs: "
            + ", ".join(matched_ids)
        )
    if not candidates:
        raise DiscordFollowUpError(
            f"no resident-managed run matches agent selector: {selector}"
        )

    row = candidates[0]
    run_id = str(row.get("run_id") or "")
    status = str(row.get("status") or "unknown")
    if row.get("live") is not True:
        raise DiscordFollowUpError(
            f"resident-managed run {run_id} is not live (status: {status})"
        )
    launch_provenance = row.get("launch_provenance")
    if not isinstance(launch_provenance, Mapping):
        raise DiscordFollowUpError(
            f"resident-managed run {run_id} has no immutable launch provenance"
        )
    try:
        normalized = normalize_delegation_provenance(launch_provenance)
    except DelegationProvenanceError as exc:
        raise DiscordFollowUpError(
            f"resident-managed run {run_id} has malformed launch provenance"
        ) from exc
    if normalized.get("applicability") != "applicable":
        raise DiscordFollowUpError(
            f"resident-managed run {run_id} is not owned by a Discord request"
        )
    return LiveManagedAgentTarget(
        run_id=run_id,
        manifest_path=str(row.get("manifest_path") or ""),
        launch_provenance=normalized,
        status=status,
    )


def command_control_provenance(
    target: LiveManagedAgentTarget,
    *,
    interaction_id: str,
    operator_user_id: str,
    conversation_key: str,
) -> dict[str, Any]:
    """Bind an interaction to the target's immutable delivery ownership."""

    target_provenance = dict(target.launch_provenance)
    if target_provenance.get("conversation_key") != conversation_key:
        raise DiscordFollowUpError(
            "the live agent belongs to a different Discord conversation"
        )
    try:
        return normalize_delegation_provenance(
            {
                **target_provenance,
                "discord_interaction_id": interaction_id,
                "discord_operator_user_id": operator_user_id,
                "discord_application_command": FOLLOW_UP_COMMAND,
                "delegation_id": f"discord-follow-up-{interaction_id}",
                "source_kind": "discord_application_command",
            }
        )
    except DelegationProvenanceError as exc:
        raise DiscordFollowUpError(
            "the Discord interaction provenance is malformed"
        ) from exc


def render_follow_up_receipt(result: Any) -> str:
    """Render acceptance without claiming delegated task completion."""

    continuation = str(getattr(result, "continuation_run_id", None) or "")
    followup_id = str(getattr(result, "followup_id", "") or "")
    target_run_id = str(getattr(result, "target_run_id", "") or "")
    status = str(getattr(result, "status", "unknown") or "unknown")
    if not continuation:
        raise DiscordFollowUpError(
            "the follow-up returned no interrupting continuation receipt"
        )
    return (
        f"Follow-up durably accepted for `{target_run_id}`.\n"
        f"Interrupting continuation: `{continuation}` (receipt `{followup_id}`).\n"
        f"Status: `{status}` — the instruction is attached; target completion is not claimed."
    )


__all__ = [
    "DiscordFollowUpError",
    "FOLLOW_UP_COMMAND",
    "FOLLOW_UP_DESCRIPTION",
    "LiveManagedAgentTarget",
    "command_control_provenance",
    "displayed_run_suffix",
    "render_follow_up_receipt",
    "resolve_live_managed_agent",
]
