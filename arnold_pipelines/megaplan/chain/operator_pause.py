"""Durable operator pause authority for Megaplan chains."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.planning.state import (
    STATE_BLOCKED,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FAILED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_INITIALIZED,
    STATE_PAUSED,
    STATE_PLANNED,
    STATE_PREPPED,
    STATE_REVIEWED,
)
from arnold_pipelines.megaplan.types import CliError

AUTHORITY_KEY = "operator_pause"
AUTHORITY_SCHEMA = "arnold.megaplan.operator-pause.v1"
RESUME_AUTHORITY_KEY = "operator_resume"
_RUNNER_RESUMABLE_STATES = {
    STATE_INITIALIZED,
    STATE_PREPPED,
    STATE_PLANNED,
    STATE_CRITIQUED,
    STATE_GATED,
    STATE_FINALIZED,
    STATE_EXECUTED,
    STATE_REVIEWED,
    STATE_DONE,
    STATE_FAILED,
    STATE_BLOCKED,
}


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
                    "previous_chain_last_state": authority["previous_chain_last_state"],
                }
            return True

        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_pause)
    return {"changed": True, "paused": True, "authority": authority}


def reconcile_quiesced_plan_pause(
    spec_path: Path,
    project_root: Path,
    *,
    session: str,
    authority: Mapping[str, Any],
) -> bool:
    """Converge the narrow writer-after-pause race after the runner is stopped.

    A runner can be killed after chain pause authority commits but still flush
    one final in-memory plan state.  Reapply the plan-side pause only when that
    flush restored the exact pre-pause semantic state and its recorded runner
    is demonstrably dead.  Any other mutation remains a hard stop.
    """

    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    state = chain_spec.load_chain_state(spec_path)
    canonical = pause_record(state)
    if canonical is None or dict(canonical) != dict(authority):
        raise CliError(
            "pause_authority_diverged",
            "chain pause authority changed while the runner was being stopped",
        )
    plan_name = canonical.get("plan") or state.current_plan_name
    plan_dir = find_plan_dir(project_root, plan_name) if isinstance(plan_name, str) else None
    if plan_dir is None or not (plan_dir / "state.json").exists():
        return False

    changed = False

    def _reconcile(current: dict[str, Any]) -> bool:
        nonlocal changed
        meta = current.get("meta")
        plan_pause = meta.get(AUTHORITY_KEY) if isinstance(meta, dict) else None
        if current.get("current_state") == STATE_PAUSED:
            if not isinstance(plan_pause, Mapping):
                raise CliError(
                    "pause_authority_diverged",
                    "paused plan lost its plan-side operator authority",
                )
            return False
        if current.get("current_state") != canonical.get("previous_plan_state"):
            raise CliError(
                "pause_authority_diverged",
                "plan changed beyond the pre-pause state while the runner stopped",
            )
        if isinstance(plan_pause, Mapping):
            raise CliError(
                "pause_authority_diverged",
                "non-paused plan retained conflicting operator pause authority",
            )
        active_step = current.get("active_step")
        lease = active_step.get("runner_lease") if isinstance(active_step, Mapping) else None
        worker_pid = active_step.get("worker_pid") if isinstance(active_step, Mapping) else None
        if (
            not isinstance(active_step, Mapping)
            or not isinstance(lease, Mapping)
            or lease.get("session") != session
            or isinstance(worker_pid, bool)
            or not isinstance(worker_pid, int)
            or worker_pid <= 0
            or Path(f"/proc/{worker_pid}").exists()
        ):
            raise CliError(
                "pause_authority_diverged",
                "plan-side pause was overwritten without a dead owned runner receipt",
            )
        current["current_state"] = STATE_PAUSED
        current.pop("active_step", None)
        next_meta = current.setdefault("meta", {})
        if not isinstance(next_meta, dict):
            raise CliError(
                "pause_authority_diverged",
                "plan metadata is not writable during pause reconciliation",
            )
        next_meta[AUTHORITY_KEY] = {
            "schema_version": AUTHORITY_SCHEMA,
            "paused_at": canonical.get("paused_at"),
            "reason": canonical.get("reason"),
            "previous_current_state": canonical.get("previous_plan_state"),
            "previous_chain_last_state": canonical.get("previous_chain_last_state"),
        }
        changed = True
        return True

    write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_reconcile)
    return changed


def resume_chain(
    spec_path: Path,
    project_root: Path,
    *,
    actor: str = "operator",
    verify_execution_binding: bool = True,
    expected_resume_authority: Mapping[str, Any] | None = None,
    allow_legacy_authority_cleared_hold: bool = False,
) -> dict[str, Any]:
    """Explicitly clear pause authority and restore the exact prior plan state."""

    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    state = chain_spec.load_chain_state(
        spec_path,
        verify_execution_binding=verify_execution_binding,
    )
    authority = pause_record(state)
    if authority is None:
        resumed = state.metadata.get(RESUME_AUTHORITY_KEY)
        resumed = dict(resumed) if isinstance(resumed, Mapping) else None
        expected = (
            dict(expected_resume_authority)
            if isinstance(expected_resume_authority, Mapping)
            else None
        )
        if expected is not None or allow_legacy_authority_cleared_hold:
            if resumed is None or (expected is not None and resumed != expected):
                raise CliError(
                    "resume_authority_mismatch",
                    "authority-cleared hold does not match canonical chain resume authority",
                )
            if resumed.get("schema_version") != AUTHORITY_SCHEMA:
                raise CliError(
                    "resume_authority_invalid",
                    "authority-cleared hold has an invalid resume authority schema",
                )
            plan_name = resumed.get("plan") or state.current_plan_name
            if not isinstance(plan_name, str) or not plan_name or plan_name != state.current_plan_name:
                raise CliError(
                    "resume_authority_diverged",
                    "authority-cleared hold no longer targets the canonical current plan",
                )
            plan_dir = find_plan_dir(project_root, plan_name)
            if plan_dir is None or not (plan_dir / "state.json").exists():
                raise CliError(
                    "resume_authority_diverged",
                    "authority-cleared hold current plan state is unavailable",
                )
            try:
                plan_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CliError(
                    "resume_authority_diverged",
                    "authority-cleared hold current plan state is unreadable",
                ) from exc
            plan_meta = plan_state.get("meta")
            plan_pause = plan_meta.get(AUTHORITY_KEY) if isinstance(plan_meta, dict) else None
            current_plan_state = plan_state.get("current_state")
            if (
                current_plan_state not in _RUNNER_RESUMABLE_STATES
                or (isinstance(plan_pause, Mapping) and plan_pause.get("schema_version") == AUTHORITY_SCHEMA)
            ):
                raise CliError(
                    "resume_authority_diverged",
                    "authority-cleared hold targets a plan state that is not runner-resumable",
                )
            # The direct phase intentionally may have advanced after --no-start
            # (for example gated -> finalized).  The receipt authorizes starting
            # the chain runner, not rewriting the newer plan state.
            return {
                "changed": False,
                "paused": False,
                "already_resumed": True,
                "plan": plan_name,
                "restored_plan_state": resumed.get("restored_plan_state"),
                "current_plan_state": current_plan_state,
                "resume_authority": resumed,
            }
        # A runner that was already exiting when pause_chain() committed can
        # persist its older in-memory ChainState after the pause receipt.  The
        # plan-side authority is written through the plan-state CAS and remains
        # the exact durable record needed to resume.  Reconcile only that
        # narrow, self-authenticating split-brain shape; every other missing
        # chain authority still fails closed.
        plan_dir = (
            find_plan_dir(project_root, state.current_plan_name)
            if state.current_plan_name
            else None
        )
        plan_state: dict[str, Any] = {}
        if plan_dir is not None and (plan_dir / "state.json").exists():
            try:
                loaded = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                loaded = {}
            if isinstance(loaded, dict):
                plan_state = loaded
        plan_meta = plan_state.get("meta")
        plan_pause = plan_meta.get(AUTHORITY_KEY) if isinstance(plan_meta, dict) else None
        previous_plan_state = (
            plan_pause.get("previous_current_state")
            if isinstance(plan_pause, dict)
            else None
        )
        if not (
            state.last_state == STATE_PAUSED
            and plan_state.get("current_state") == STATE_PAUSED
            and isinstance(plan_pause, dict)
            and plan_pause.get("schema_version") == AUTHORITY_SCHEMA
            and isinstance(previous_plan_state, str)
            and previous_plan_state
            and previous_plan_state != STATE_PAUSED
        ):
            raise CliError("chain_not_paused", "chain has no active operator pause")
        previous_chain_last_state = plan_pause.get("previous_chain_last_state")
        if not isinstance(previous_chain_last_state, str) or not previous_chain_last_state:
            previous_chain_last_state = previous_plan_state
        authority = {
            "schema_version": AUTHORITY_SCHEMA,
            "active": True,
            "paused_at": plan_pause.get("paused_at"),
            "actor": "reconciled-plan-authority",
            "reason": plan_pause.get("reason"),
            "previous_chain_last_state": previous_chain_last_state,
            "previous_plan_state": previous_plan_state,
            "plan": state.current_plan_name,
        }

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
    resume_authority = {
        "schema_version": AUTHORITY_SCHEMA,
        "resumed_at": _now(),
        "actor": actor,
        "plan": plan_name,
        "restored_plan_state": restore_state,
    }
    state.metadata[RESUME_AUTHORITY_KEY] = resume_authority
    chain_spec.save_chain_state(spec_path, state)
    return {
        "changed": True,
        "paused": False,
        "plan": plan_name,
        "restored_plan_state": restore_state,
        "resume_authority": resume_authority,
    }
