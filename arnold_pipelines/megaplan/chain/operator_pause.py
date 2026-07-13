"""Durable operator pause authority for Megaplan chains."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.planning.state import STATE_DONE, STATE_PAUSED
from arnold_pipelines.megaplan.types import CliError

AUTHORITY_KEY = "operator_pause"
AUTHORITY_SCHEMA = "arnold.megaplan.operator-pause.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pause_record(state: chain_spec.ChainState) -> dict[str, Any] | None:
    value = state.metadata.get(AUTHORITY_KEY)
    if isinstance(value, dict) and value.get("active") is True:
        return dict(value)
    return None


def is_paused(state: chain_spec.ChainState) -> bool:
    return pause_record(state) is not None


def pause_chain(
    spec_path: Path,
    project_root: Path,
    *,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Persist pause authority without deleting workspace, cursor, or artifacts."""

    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    spec = chain_spec.load_spec(spec_path)
    state = chain_spec.load_chain_state(spec_path)
    if state.current_milestone_index >= len(spec.milestones) and len(state.completed) >= len(spec.milestones):
        raise CliError("chain_complete", "completed chains cannot be paused")
    existing = pause_record(state)
    if existing is not None:
        return {"changed": False, "paused": True, "authority": existing}

    plan_dir = find_plan_dir(project_root, state.current_plan_name) if state.current_plan_name else None
    previous_plan_state: str | None = None
    if plan_dir is not None and (plan_dir / "state.json").exists():
        raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        previous_plan_state = raw.get("current_state")
        if previous_plan_state == STATE_DONE:
            raise CliError("plan_complete", "the current plan is already complete")

    authority = {
        "schema_version": AUTHORITY_SCHEMA,
        "active": True,
        "paused_at": _now(),
        "actor": actor,
        "reason": reason.strip() or "operator requested pause",
        "previous_chain_last_state": state.last_state,
        "previous_plan_state": previous_plan_state,
        "plan": state.current_plan_name,
    }
    state.metadata[AUTHORITY_KEY] = authority
    state.last_state = STATE_PAUSED
    chain_spec.save_chain_state(spec_path, state)

    if plan_dir is not None and previous_plan_state != STATE_PAUSED:
        def _pause(current: dict[str, Any]) -> bool:
            if current.get("current_state") == STATE_DONE:
                raise CliError("plan_complete", "the current plan completed while pause was applied")
            current["current_state"] = STATE_PAUSED
            meta = current.setdefault("meta", {})
            if isinstance(meta, dict):
                meta[AUTHORITY_KEY] = {
                    "schema_version": AUTHORITY_SCHEMA,
                    "paused_at": authority["paused_at"],
                    "reason": authority["reason"],
                    "previous_current_state": previous_plan_state,
                }
            return True

        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_pause)
    return {"changed": True, "paused": True, "authority": authority}


def resume_chain(spec_path: Path, project_root: Path, *, actor: str = "operator") -> dict[str, Any]:
    """Explicitly clear pause authority and restore the exact prior plan state."""

    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    state = chain_spec.load_chain_state(spec_path)
    authority = pause_record(state)
    if authority is None:
        raise CliError("chain_not_paused", "chain has no active operator pause")

    plan_name = authority.get("plan") or state.current_plan_name
    plan_dir = find_plan_dir(project_root, plan_name) if isinstance(plan_name, str) else None
    restore_state = authority.get("previous_plan_state")
    if plan_dir is not None and isinstance(restore_state, str) and restore_state:
        def _resume(current: dict[str, Any]) -> bool:
            if current.get("current_state") != STATE_PAUSED:
                raise CliError(
                    "pause_authority_diverged",
                    "plan state changed after operator pause; refusing implicit recovery",
                )
            current["current_state"] = restore_state
            meta = current.get("meta")
            if isinstance(meta, dict):
                meta.pop(AUTHORITY_KEY, None)
            return True

        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_resume)

    state.last_state = authority.get("previous_chain_last_state")
    state.metadata.pop(AUTHORITY_KEY, None)
    state.metadata["operator_resume"] = {
        "schema_version": AUTHORITY_SCHEMA,
        "resumed_at": _now(),
        "actor": actor,
        "restored_plan_state": restore_state,
    }
    chain_spec.save_chain_state(spec_path, state)
    return {"changed": True, "paused": False, "plan": plan_name, "restored_plan_state": restore_state}
