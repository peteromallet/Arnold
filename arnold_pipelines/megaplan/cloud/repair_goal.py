"""Durable goal custody for automatic cloud repair.

The repair process is an action worker, not the success authority.  This module
captures the target's frozen acceptance checkpoint before a repair is launched
and keeps one durable goal open until authoritative target evidence moves past
that checkpoint or an explicit approval/authorization gate is observed.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPAIR_GOAL_SCHEMA = "arnold-repair-goal-v1"
GOAL_ACTIVE = "active"
GOAL_PROGRESSED = "progressed"
GOAL_APPROVAL_REQUIRED = "approval_required"
TERMINAL_GOAL_STATUSES = frozenset({GOAL_PROGRESSED, GOAL_APPROVAL_REQUIRED})

_BLOCKED_STATES = frozenset(
    {
        "blocked",
        "failed",
        "stalled",
        "retrying_failure",
        "repairing",
        "needs_human",
    }
)
_APPROVAL_STATES = frozenset(
    {
        "awaiting_human",
        "awaiting_human_verify",
        "awaiting_approval",
        "awaiting_authorization",
        "awaiting_pr_merge",
        "blocked_prep_clarification",
        "blocked_human_verification",
        "human_action_required",
        "human_prerequisite",
    }
)
_TERMINAL_TARGET_STATES = frozenset({"done", "complete", "completed", "finalized"})
_STAGE_ORDER = {
    "init": 0,
    "initialized": 0,
    "prep": 1,
    "prepared": 1,
    "plan": 2,
    "planned": 2,
    "critique": 3,
    "critiqued": 3,
    "gate": 4,
    "gated": 4,
    "finalize": 5,
    "finalized": 5,
    "execute": 6,
    "executed": 6,
    "review": 7,
    "reviewed": 8,
    "awaiting_pr_merge": 9,
    "merged": 10,
    "done": 11,
    "complete": 11,
    "completed": 11,
}
_FRESH_WORKER_SECONDS = 600
_FRESH_RUNNER_TRANSITION_SECONDS = 180
_DETERMINISTIC_OWNER_REPEAT_LIMIT = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe or "unknown"


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _pid_live(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state != "Z"


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _compact_failure(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = {
        key: value.get(key)
        for key in (
            "failure_kind",
            "kind",
            "phase",
            "step",
            "task_id",
            "blocked_task_id",
            "message",
            "error",
            "timestamp",
        )
        if value.get(key) not in (None, "", [], {})
    }
    compact["fingerprint"] = _digest(compact) if compact else ""
    return compact


def _target_stage(state: Mapping[str, Any], chain: Mapping[str, Any]) -> str:
    active = state.get("active_step") if isinstance(state.get("active_step"), Mapping) else {}
    failure = state.get("latest_failure") if isinstance(state.get("latest_failure"), Mapping) else {}
    history = state.get("history") if isinstance(state.get("history"), list) else []
    latest_history = history[-1] if history and isinstance(history[-1], Mapping) else {}
    for value in (active.get("phase"), failure.get("phase"), failure.get("step")):
        normalized = str(value or "").strip().lower()
        if normalized in _STAGE_ORDER:
            return normalized
    candidates = [
        str(value or "").strip().lower()
        for value in (latest_history.get("step"), chain.get("last_state"), state.get("current_state"))
    ]
    ranked = [value for value in candidates if value in _STAGE_ORDER]
    if ranked:
        return max(ranked, key=lambda value: _STAGE_ORDER[value])
    return next((value for value in candidates if value), "")


def _active_worker_observation(state: Mapping[str, Any], *, captured_at: str) -> dict[str, Any]:
    active = state.get("active_step") if isinstance(state.get("active_step"), Mapping) else {}
    pid = active.get("worker_pid")
    last_activity_at = str(active.get("last_activity_at") or "")
    activity_time = _parse_time(last_activity_at)
    captured_time = _parse_time(captured_at) or datetime.now(timezone.utc)
    age = max(0.0, (captured_time - activity_time).total_seconds()) if activity_time else None
    live = _pid_live(pid)
    return {
        "phase": str(active.get("phase") or "").strip().lower(),
        "run_id": str(active.get("run_id") or ""),
        "worker_pid": pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
        "worker_pid_live": live,
        "last_activity_at": last_activity_at,
        "last_activity_kind": str(active.get("last_activity_kind") or ""),
        "last_activity_detail": str(active.get("last_activity_detail") or "")[:500],
        "activity_age_seconds": age,
        "fresh": bool(live and age is not None and age <= _FRESH_WORKER_SECONDS),
    }


def _runner_transition_observation(
    *,
    remote_spec: str,
    plan_name: str,
    plan_path: Path | None,
    captured_at: str,
) -> dict[str, Any]:
    """Boundedly preserve a driver while it consumes a completed step result."""

    target_pid: int | None = None
    for proc_path in Path("/proc").glob("[0-9]*"):
        try:
            argv = [
                item.decode("utf-8", errors="replace")
                for item in (proc_path / "cmdline").read_bytes().split(b"\0")
                if item
            ]
        except OSError:
            continue
        is_chain = all(item in argv for item in ("arnold_pipelines.megaplan", "chain", "start"))
        is_plan = all(item in argv for item in ("arnold_pipelines.megaplan", "auto"))
        matches_spec = bool(remote_spec and "--spec" in argv and remote_spec in argv)
        matches_plan = bool(plan_name and "--plan" in argv and plan_name in argv)
        if (is_chain and matches_spec) or (is_plan and matches_plan):
            target_pid = int(proc_path.name)
            break

    captured_time = _parse_time(captured_at) or datetime.now(timezone.utc)
    state_age: float | None = None
    if plan_path is not None:
        try:
            state_time = datetime.fromtimestamp(plan_path.stat().st_mtime, timezone.utc)
            state_age = max(0.0, (captured_time - state_time).total_seconds())
        except OSError:
            pass
    live = _pid_live(target_pid)
    return {
        "runner_pid": target_pid,
        "runner_pid_live": live,
        "plan_state_age_seconds": state_age,
        "fresh": bool(live and state_age is not None and state_age <= _FRESH_RUNNER_TRANSITION_SECONDS),
    }


def repair_goal_path(marker_dir: str | Path, session: str, blocker_id: str) -> Path:
    blocker_digest = hashlib.sha256(blocker_id.encode("utf-8")).hexdigest()[:20]
    return (
        Path(marker_dir)
        / "repair-goals"
        / _safe_name(session)
        / f"goal-{blocker_digest}.json"
    )


def _candidate_chain_states(workspace: Path) -> list[Path]:
    root = workspace / ".megaplan" / "plans" / ".chains"
    return sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def _select_chain_state(workspace: Path, plan_name: str, remote_spec: str) -> tuple[Path | None, dict[str, Any]]:
    fallback: tuple[Path | None, dict[str, Any]] = (None, {})
    for path in _candidate_chain_states(workspace):
        payload = _load_json(path)
        if not payload:
            continue
        if fallback[0] is None:
            fallback = (path, payload)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        spec = str(metadata.get("chain_spec_path") or payload.get("chain_spec_path") or "")
        current_plan = str(payload.get("current_plan_name") or "")
        completed_plans = {
            str(item.get("plan") or "")
            for item in payload.get("completed") or []
            if isinstance(item, dict)
        }
        if (remote_spec and spec == remote_spec) or (
            plan_name and (current_plan == plan_name or plan_name in completed_plans)
        ):
            return path, payload
    return fallback


def _latest_acceptance_event(events_path: Path) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    try:
        handle = events_path.open(encoding="utf-8", errors="replace")
    except OSError:
        return latest
    with handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("kind") != "state_transition":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            latest = {
                "seq": int(event.get("seq") or 0),
                "ts_utc": str(event.get("ts_utc") or ""),
                "kind": "state_transition",
                "from": str(payload.get("from") or ""),
                "to": str(payload.get("to") or ""),
            }
    return latest


def capture_checkpoint(
    *,
    workspace: str | Path,
    plan_name: str = "",
    remote_spec: str = "",
) -> dict[str, Any]:
    root = Path(workspace)
    chain_path, chain = _select_chain_state(root, plan_name, remote_spec)
    resolved_plan = plan_name or str(chain.get("current_plan_name") or "")
    plan_path = root / ".megaplan" / "plans" / resolved_plan / "state.json" if resolved_plan else None
    state = _load_json(plan_path)
    if not resolved_plan:
        resolved_plan = str(state.get("name") or state.get("plan_name") or "")
    events_path = plan_path.parent / "events.ndjson" if plan_path is not None else None
    acceptance = _latest_acceptance_event(events_path) if events_path is not None else {}
    completed = chain.get("completed") if isinstance(chain.get("completed"), list) else []
    captured_at = utc_now()
    latest_failure = _compact_failure(state.get("latest_failure"))
    active_worker = _active_worker_observation(state, captured_at=captured_at)
    runner_transition = _runner_transition_observation(
        remote_spec=remote_spec,
        plan_name=resolved_plan,
        plan_path=plan_path,
        captured_at=captured_at,
    )
    target_stage = _target_stage(state, chain)
    checkpoint = {
        "captured_at": captured_at,
        "plan_name": resolved_plan,
        "plan_state": str(state.get("current_state") or state.get("state") or "").lower(),
        "plan_iteration": int(state.get("iteration") or 0),
        "plan_history_length": len(state.get("history") or []) if isinstance(state.get("history"), list) else 0,
        "plan_state_path": str(plan_path) if plan_path is not None else "",
        "events_path": str(events_path) if events_path is not None else "",
        "acceptance": acceptance,
        "chain_state_path": str(chain_path) if chain_path is not None else "",
        "chain_last_state": str(chain.get("last_state") or "").lower(),
        "chain_current_plan_name": str(chain.get("current_plan_name") or ""),
        "chain_current_milestone_index": int(chain.get("current_milestone_index") or 0),
        "chain_completed_count": len(completed),
        "chain_pr_state": str(chain.get("pr_state") or "").lower(),
        "target_stage": target_stage,
        "target_stage_rank": _STAGE_ORDER.get(target_stage, -1),
        "latest_failure": latest_failure,
        "latest_failure_cleared": not bool(latest_failure),
        "active_worker": active_worker,
        "runner_transition": runner_transition,
    }
    progress_facts = {
        "plan_name": checkpoint["plan_name"],
        "plan_state": checkpoint["plan_state"],
        "plan_iteration": checkpoint["plan_iteration"],
        "plan_history_length": checkpoint["plan_history_length"],
        "acceptance_seq": int(acceptance.get("seq") or 0),
        "chain_last_state": checkpoint["chain_last_state"],
        "chain_current_plan_name": checkpoint["chain_current_plan_name"],
        "chain_current_milestone_index": checkpoint["chain_current_milestone_index"],
        "chain_completed_count": checkpoint["chain_completed_count"],
        "target_stage": target_stage,
        "latest_failure_fingerprint": latest_failure.get("fingerprint", ""),
        "active_worker_phase": active_worker.get("phase", ""),
        "active_worker_run_id": active_worker.get("run_id", ""),
        "active_worker_last_activity_at": active_worker.get("last_activity_at", ""),
        "runner_transition_pid": runner_transition.get("runner_pid"),
        "runner_transition_fresh": runner_transition.get("fresh", False),
    }
    checkpoint["progress_token"] = _digest(progress_facts)
    checkpoint["digest"] = _digest(checkpoint)
    return checkpoint


def _approval_gate(observation: Mapping[str, Any]) -> dict[str, Any] | None:
    plan_state = str(observation.get("plan_state") or "").lower()
    chain_state = str(observation.get("chain_last_state") or "").lower()
    gate_state = plan_state if plan_state in _APPROVAL_STATES else chain_state if chain_state in _APPROVAL_STATES else ""
    if not gate_state:
        return None
    return {
        "gate_state": gate_state,
        "plan_name": str(observation.get("plan_name") or ""),
        "plan_state_path": str(observation.get("plan_state_path") or ""),
        "chain_state_path": str(observation.get("chain_state_path") or ""),
        "observed_at": str(observation.get("captured_at") or utc_now()),
        "reason": "authoritative target state explicitly requires human approval or authorization",
    }


def evaluate_checkpoint(
    frozen: Mapping[str, Any], observation: Mapping[str, Any]
) -> dict[str, Any]:
    gate = _approval_gate(observation)
    if gate is not None:
        return {
            "status": GOAL_APPROVAL_REQUIRED,
            "reason": gate["reason"],
            "approval_gate": gate,
            "authoritative_progress": False,
            "blocker_cleared": False,
            "fresh_progress": False,
            "stage_advanced": False,
            "correct_worker_alive": None,
            "control_action": "await_approval",
        }

    frozen_completed = int(frozen.get("chain_completed_count") or 0)
    observed_completed = int(observation.get("chain_completed_count") or 0)
    frozen_index = int(frozen.get("chain_current_milestone_index") or 0)
    observed_index = int(observation.get("chain_current_milestone_index") or 0)
    frozen_chain_plan = str(frozen.get("chain_current_plan_name") or "")
    observed_chain_plan = str(observation.get("chain_current_plan_name") or "")
    milestone_advanced = observed_completed > frozen_completed or observed_index > frozen_index
    if milestone_advanced:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "authoritative chain milestone acceptance advanced beyond the frozen checkpoint",
            "authoritative_progress": True,
            "blocker_cleared": True,
            "fresh_progress": True,
            "stage_advanced": True,
            "correct_worker_alive": None,
            "control_action": "complete",
        }
    if frozen_chain_plan and observed_chain_plan and observed_chain_plan != frozen_chain_plan:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "authoritative chain current plan advanced beyond the frozen plan",
            "authoritative_progress": True,
            "blocker_cleared": True,
            "fresh_progress": True,
            "stage_advanced": True,
            "correct_worker_alive": None,
            "control_action": "complete",
        }

    frozen_acceptance = frozen.get("acceptance") if isinstance(frozen.get("acceptance"), Mapping) else {}
    observed_acceptance = observation.get("acceptance") if isinstance(observation.get("acceptance"), Mapping) else {}
    frozen_seq = int(frozen_acceptance.get("seq") or 0)
    observed_seq = int(observed_acceptance.get("seq") or 0)
    frozen_state = str(frozen.get("plan_state") or "").lower()
    observed_state = str(observation.get("plan_state") or "").lower()
    frozen_stage = str(frozen.get("target_stage") or frozen_state).lower()
    observed_stage = str(observation.get("target_stage") or observed_state).lower()
    frozen_rank_value = frozen.get("target_stage_rank")
    observed_rank_value = observation.get("target_stage_rank")
    frozen_rank = int(
        _STAGE_ORDER.get(frozen_stage, -1)
        if frozen_rank_value is None
        else frozen_rank_value
    )
    observed_rank = int(
        _STAGE_ORDER.get(observed_stage, -1)
        if observed_rank_value is None
        else observed_rank_value
    )
    stage_advanced = observed_rank > frozen_rank >= 0
    blocker_cleared = bool(observation.get("latest_failure_cleared"))
    later_acceptance = observed_seq > frozen_seq
    worker = observation.get("active_worker") if isinstance(observation.get("active_worker"), Mapping) else {}
    worker_applicable = bool(worker.get("phase")) and observed_stage not in {
        "review",
        "reviewed",
        "awaiting_pr_merge",
        "merged",
        "done",
        "complete",
        "completed",
    }
    correct_worker_alive = bool(worker.get("fresh")) if worker_applicable else None
    fresh_progress = later_acceptance or bool(worker.get("fresh"))
    if stage_advanced and blocker_cleared and fresh_progress and correct_worker_alive is not False:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "blocker cleared and authoritative plan stage advanced beyond the frozen repair stage",
            "authoritative_progress": True,
            "blocker_cleared": True,
            "fresh_progress": True,
            "stage_advanced": True,
            "correct_worker_alive": correct_worker_alive,
            "control_action": "complete",
            "acceptance_event": dict(observed_acceptance),
        }
    transition = (
        observation.get("runner_transition")
        if isinstance(observation.get("runner_transition"), Mapping)
        else {}
    )
    preserve_worker = bool(worker.get("fresh")) and str(worker.get("phase") or "") == frozen_stage
    preserve_transition = bool(blocker_cleared and transition.get("fresh"))
    preserve_live = preserve_worker or preserve_transition
    return {
        "status": GOAL_ACTIVE,
        "reason": (
            "correct target worker is alive with fresh progress; preserve it until the plan advances beyond the frozen stage"
            if preserve_worker
            else "matching target runner is alive during a fresh step-transition window; preserve it until the handoff resolves"
            if preserve_transition
            else "target has not satisfied blocker-clearance, fresh-progress, and beyond-stage recovery evidence"
        ),
        "authoritative_progress": False,
        "blocker_cleared": blocker_cleared,
        "fresh_progress": fresh_progress or preserve_transition,
        "stage_advanced": stage_advanced,
        "correct_worker_alive": True if preserve_transition else correct_worker_alive,
        "control_action": "preserve_live" if preserve_live else "investigate",
        "ignored_activity": "process, heartbeat, log, state-write, and subprocess completion activity is non-authoritative",
    }


def ensure_repair_goal(
    *,
    marker_dir: str | Path,
    session: str,
    workspace: str | Path,
    remote_spec: str,
    plan_name: str,
    blocker_id: str,
    request_id: str,
    owner_run_id: str = "",
    owner_manifest_path: str = "",
) -> tuple[Path, dict[str, Any]]:
    path = repair_goal_path(marker_dir, session, blocker_id)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = _load_json(path)
        if not payload:
            frozen = capture_checkpoint(
                workspace=workspace,
                plan_name=plan_name,
                remote_spec=remote_spec,
            )
            identity = {
                "session": session,
                "blocker_id": blocker_id,
                "plan_name": frozen.get("plan_name") or plan_name,
                "checkpoint_digest": frozen["digest"],
            }
            payload = {
                "schema_version": REPAIR_GOAL_SCHEMA,
                "goal_id": f"repair-goal-{_digest(identity)[:24]}",
                "status": GOAL_ACTIVE,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "target": {
                    "session": session,
                    "workspace": str(Path(workspace)),
                    "remote_spec": remote_spec,
                    "plan_name": frozen.get("plan_name") or plan_name,
                    "blocker_id": blocker_id,
                },
                "frozen_checkpoint": frozen,
                "checkpoint_digest": frozen["digest"],
                "recovery_contract": {
                    "required_beyond_stage": frozen.get("target_stage") or "",
                    "required_beyond_stage_rank": frozen.get("target_stage_rank", -1),
                    "requires_blocker_cleared": True,
                    "requires_fresh_progress": True,
                    "requires_correct_worker_when_applicable": True,
                    "success_authority": "authoritative_target_evidence",
                },
                "request_ids": [request_id] if request_id else [],
                "owners": [],
                "cycles": [],
                "terminal": False,
                "semantic_completion": False,
            }
        elif payload.get("schema_version") != REPAIR_GOAL_SCHEMA:
            raise ValueError(f"unsupported repair goal schema at {path}")
        request_ids = payload.setdefault("request_ids", [])
        if request_id and request_id not in request_ids:
            request_ids.append(request_id)
        if owner_run_id:
            owners = payload.setdefault("owners", [])
            if not any(isinstance(item, dict) and item.get("run_id") == owner_run_id for item in owners):
                owners.append(
                    {
                        "run_id": owner_run_id,
                        "manifest_path": owner_manifest_path,
                        "attached_at": utc_now(),
                        "checkpoint_digest": payload.get("checkpoint_digest"),
                    }
                )
        payload["updated_at"] = utc_now()
        _atomic_write(path, payload)
        return path, payload


def attach_repair_goal_owner(
    goal_path: str | Path,
    *,
    request_id: str,
    owner_run_id: str,
    owner_manifest_path: str,
) -> tuple[Path, dict[str, Any]]:
    """Attach a retry owner without recapturing or replacing the checkpoint."""

    path = Path(goal_path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = _load_json(path)
        if payload.get("schema_version") != REPAIR_GOAL_SCHEMA:
            raise ValueError(f"repair goal is missing or invalid: {path}")
        request_ids = payload.setdefault("request_ids", [])
        if request_id and request_id not in request_ids:
            request_ids.append(request_id)
        owners = payload.setdefault("owners", [])
        if owner_run_id and not any(
            isinstance(item, dict) and item.get("run_id") == owner_run_id
            for item in owners
        ):
            owners.append(
                {
                    "run_id": owner_run_id,
                    "manifest_path": owner_manifest_path,
                    "attached_at": utc_now(),
                    "checkpoint_digest": payload.get("checkpoint_digest"),
                }
            )
        payload["updated_at"] = utc_now()
        _atomic_write(path, payload)
        return path, payload


def evaluate_repair_goal(
    goal_path: str | Path,
    *,
    action: str,
    owner_run_id: str = "",
    owner_manifest_path: str = "",
) -> dict[str, Any]:
    path = Path(goal_path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = _load_json(path)
        if payload.get("schema_version") != REPAIR_GOAL_SCHEMA:
            raise ValueError(f"repair goal is missing or invalid: {path}")
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        observation = capture_checkpoint(
            workspace=str(target.get("workspace") or ""),
            plan_name=str(target.get("plan_name") or ""),
            remote_spec=str(target.get("remote_spec") or ""),
        )
        frozen = payload.get("frozen_checkpoint") if isinstance(payload.get("frozen_checkpoint"), dict) else {}
        contract = payload.get("recovery_contract") if isinstance(payload.get("recovery_contract"), dict) else {}
        if not contract:
            worker = observation.get("active_worker") if isinstance(observation.get("active_worker"), Mapping) else {}
            required_stage = str(
                frozen.get("target_stage")
                or worker.get("phase")
                or observation.get("target_stage")
                or frozen.get("plan_state")
                or ""
            ).lower()
            contract = {
                "required_beyond_stage": required_stage,
                "required_beyond_stage_rank": _STAGE_ORDER.get(required_stage, -1),
                "requires_blocker_cleared": True,
                "requires_fresh_progress": True,
                "requires_correct_worker_when_applicable": True,
                "success_authority": "authoritative_target_evidence",
                "migrated_from_legacy_goal_at": utc_now(),
            }
            payload["recovery_contract"] = contract
        effective_frozen = deepcopy(frozen)
        effective_frozen["target_stage"] = str(contract.get("required_beyond_stage") or "")
        contract_rank = contract.get("required_beyond_stage_rank")
        effective_frozen["target_stage_rank"] = int(
            -1 if contract_rank is None else contract_rank
        )
        evaluation = evaluate_checkpoint(effective_frozen, observation)
        owner_cycle = (
            action.startswith("owner-iteration-") or "post-dev-fix" in action
        ) and evaluation.get("control_action") != "preserve_live"
        repeated_owner_cycles = 0
        if owner_cycle and evaluation["status"] == GOAL_ACTIVE:
            token = str(observation.get("progress_token") or "")
            for prior in reversed(payload.get("cycles") or []):
                if not isinstance(prior, Mapping) or not prior.get("owner_cycle"):
                    continue
                prior_observation = prior.get("observation") if isinstance(prior.get("observation"), Mapping) else {}
                if str(prior_observation.get("progress_token") or "") != token:
                    break
                repeated_owner_cycles += 1
            repeated_owner_cycles += 1
            if repeated_owner_cycles >= _DETERMINISTIC_OWNER_REPEAT_LIMIT:
                evaluation["control_action"] = "replan"
                evaluation["circuit_breaker_required"] = True
                evaluation["deterministic_repeat_count"] = repeated_owner_cycles
                evaluation["reason"] = (
                    "deterministic owner failure repeated without a new authoritative progress token; "
                    "stop re-driving and escalate/replan"
                )
        cycle = {
            "observed_at": utc_now(),
            "action": action,
            "owner_run_id": owner_run_id,
            "owner_manifest_path": owner_manifest_path,
            "status": evaluation["status"],
            "reason": evaluation["reason"],
            "control_action": evaluation.get("control_action"),
            "owner_cycle": owner_cycle,
            "observation": observation,
        }
        cycles = payload.setdefault("cycles", [])
        cycles.append(cycle)
        if len(cycles) > 200:
            del cycles[:-200]
        if payload.get("status") not in TERMINAL_GOAL_STATUSES:
            payload["status"] = evaluation["status"]
            if evaluation["status"] in TERMINAL_GOAL_STATUSES:
                payload["terminal_at"] = cycle["observed_at"]
                payload["terminal"] = True
                payload["semantic_completion"] = (
                    evaluation["status"] == GOAL_PROGRESSED
                )
                payload["terminal_evidence"] = deepcopy(evaluation)
                payload["terminal_evidence"]["observation"] = observation
        payload["last_evaluation"] = evaluation
        payload["last_observation"] = observation
        payload["updated_at"] = utc_now()
        _atomic_write(path, payload)
        return {
            "goal_id": payload["goal_id"],
            "goal_path": str(path),
            "checkpoint_digest": payload["checkpoint_digest"],
            "status": payload["status"],
            "terminal": bool(payload.get("terminal")),
            "semantic_completion": payload["semantic_completion"],
            "evaluation": evaluation,
            "frozen_checkpoint": frozen,
            "recovery_contract": contract,
            "observation": observation,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ensure = sub.add_parser("ensure")
    ensure.add_argument("--marker-dir", required=True)
    ensure.add_argument("--session", required=True)
    ensure.add_argument("--workspace", required=True)
    ensure.add_argument("--remote-spec", required=True)
    ensure.add_argument("--plan-name", default="")
    ensure.add_argument("--blocker-id", required=True)
    ensure.add_argument("--request-id", default="")
    ensure.add_argument("--owner-run-id", default="")
    ensure.add_argument("--owner-manifest-path", default="")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--goal-path", required=True)
    evaluate.add_argument("--action", required=True)
    evaluate.add_argument("--owner-run-id", default="")
    evaluate.add_argument("--owner-manifest-path", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "ensure":
        path, payload = ensure_repair_goal(
            marker_dir=args.marker_dir,
            session=args.session,
            workspace=args.workspace,
            remote_spec=args.remote_spec,
            plan_name=args.plan_name,
            blocker_id=args.blocker_id,
            request_id=args.request_id,
            owner_run_id=args.owner_run_id,
            owner_manifest_path=args.owner_manifest_path,
        )
        result = {
            "goal_id": payload["goal_id"],
            "goal_path": str(path),
            "checkpoint_digest": payload["checkpoint_digest"],
            "status": payload["status"],
            "semantic_completion": payload["semantic_completion"],
            "frozen_checkpoint": payload["frozen_checkpoint"],
        }
    else:
        result = evaluate_repair_goal(
            args.goal_path,
            action=args.action,
            owner_run_id=args.owner_run_id,
            owner_manifest_path=args.owner_manifest_path,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GOAL_ACTIVE",
    "GOAL_APPROVAL_REQUIRED",
    "GOAL_PROGRESSED",
    "REPAIR_GOAL_SCHEMA",
    "capture_checkpoint",
    "attach_repair_goal_owner",
    "ensure_repair_goal",
    "evaluate_checkpoint",
    "evaluate_repair_goal",
    "repair_goal_path",
]
