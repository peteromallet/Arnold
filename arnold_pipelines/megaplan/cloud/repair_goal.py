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
    checkpoint = {
        "captured_at": utc_now(),
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
    }
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
        }

    frozen_completed = int(frozen.get("chain_completed_count") or 0)
    observed_completed = int(observation.get("chain_completed_count") or 0)
    frozen_index = int(frozen.get("chain_current_milestone_index") or 0)
    observed_index = int(observation.get("chain_current_milestone_index") or 0)
    frozen_chain_plan = str(frozen.get("chain_current_plan_name") or "")
    observed_chain_plan = str(observation.get("chain_current_plan_name") or "")
    if observed_completed > frozen_completed or observed_index > frozen_index:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "authoritative chain milestone acceptance advanced beyond the frozen checkpoint",
            "authoritative_progress": True,
        }
    if frozen_chain_plan and observed_chain_plan and observed_chain_plan != frozen_chain_plan:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "authoritative chain current plan advanced beyond the frozen plan",
            "authoritative_progress": True,
        }

    frozen_acceptance = frozen.get("acceptance") if isinstance(frozen.get("acceptance"), Mapping) else {}
    observed_acceptance = observation.get("acceptance") if isinstance(observation.get("acceptance"), Mapping) else {}
    frozen_seq = int(frozen_acceptance.get("seq") or 0)
    observed_seq = int(observed_acceptance.get("seq") or 0)
    frozen_state = str(frozen.get("plan_state") or "").lower()
    observed_state = str(observation.get("plan_state") or "").lower()
    state_is_beyond_frozen = observed_state and observed_state != frozen_state and observed_state not in _BLOCKED_STATES
    if observed_seq > frozen_seq and state_is_beyond_frozen:
        return {
            "status": GOAL_PROGRESSED,
            "reason": "a later authoritative state-transition receipt moved the plan beyond the frozen state",
            "authoritative_progress": True,
            "acceptance_event": dict(observed_acceptance),
        }
    if (
        observed_state in _TERMINAL_TARGET_STATES
        and frozen_state not in _TERMINAL_TARGET_STATES
        and observed_seq > frozen_seq
    ):
        return {
            "status": GOAL_PROGRESSED,
            "reason": "the target reached terminal accepted state after the frozen checkpoint",
            "authoritative_progress": True,
            "acceptance_event": dict(observed_acceptance),
        }
    return {
        "status": GOAL_ACTIVE,
        "reason": "target has not produced authoritative acceptance progress beyond the frozen checkpoint",
        "authoritative_progress": False,
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
        evaluation = evaluate_checkpoint(frozen, observation)
        cycle = {
            "observed_at": utc_now(),
            "action": action,
            "owner_run_id": owner_run_id,
            "owner_manifest_path": owner_manifest_path,
            "status": evaluation["status"],
            "reason": evaluation["reason"],
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
