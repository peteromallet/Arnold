"""Checkpoint-bound escalation evidence shared by the L2 and L3 repair paths."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_session(session: str) -> bool:
    return bool(
        session
        and session not in {".", ".."}
        and "/" not in session
        and "\\" not in session
    )


def _read_goal(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _replan_failure(goal: Mapping[str, Any]) -> Mapping[str, Any]:
    failure = _mapping(goal.get("last_terminal_failure"))
    nested = _mapping(_mapping(failure.get("last_evaluation")).get("failed_fixer_evidence"))
    if _text(nested.get("outcome")) == "replan_required":
        return nested
    if _text(failure.get("outcome")) == "replan_required":
        return failure
    evaluation = _mapping(failure.get("last_evaluation"))
    if (
        evaluation.get("control_action") == "meta_repair"
        and nested
        and nested.get("escalation_required") is True
    ):
        return nested
    return {}


def evaluate_checkpoint_escalation(
    *,
    marker_dir: Path,
    session: str,
    plan_name: str = "",
    blocker_id: str = "",
) -> dict[str, Any]:
    """Return fail-closed L2 custody derived from one durable repair goal.

    The goal path is derived from the trusted marker root and canonical session;
    queue payloads cannot nominate an arbitrary file.  Every authority-bearing
    identity must agree, and multiple matching active goals are ambiguous.
    """

    session = _text(session)
    plan_name = _text(plan_name)
    blocker_id = _text(blocker_id)
    result: dict[str, Any] = {
        "actionable": False,
        "reason": "no checkpoint-bound L2 escalation",
        "goal_path": "",
        "goal_id": "",
        "checkpoint_digest": "",
    }
    if not marker_dir.is_absolute() or not _safe_session(session):
        result["reason"] = "invalid repair-goal marker root or session"
        return result

    goal_root = marker_dir / "repair-goals" / session
    candidates: list[tuple[Path, dict[str, Any], Mapping[str, Any]]] = []
    try:
        paths = sorted(goal_root.glob("*.json"), key=lambda item: item.name)
    except OSError:
        paths = []
    for path in paths:
        goal = _read_goal(path)
        if not goal or goal.get("status") != "active":
            continue
        target = _mapping(goal.get("target"))
        if _text(target.get("session")) != session:
            continue
        if plan_name and _text(target.get("plan_name")) != plan_name:
            continue
        if blocker_id and _text(target.get("blocker_id")) != blocker_id:
            continue
        failure = _replan_failure(goal)
        if failure:
            candidates.append((path, goal, failure))

    if len(candidates) != 1:
        result["reason"] = (
            "ambiguous checkpoint-bound L2 escalation"
            if len(candidates) > 1
            else "no matching active replan escalation"
        )
        return result

    path, goal, failure = candidates[0]
    goal_id = _text(goal.get("goal_id"))
    checkpoint = _text(goal.get("checkpoint_digest"))
    failure_goal_id = _text(failure.get("goal_id"))
    failure_checkpoint = _text(failure.get("checkpoint_digest"))
    outer = _mapping(goal.get("last_terminal_failure"))
    observation = _mapping(outer.get("last_observation"))
    if not observation:
        observation = _mapping(failure.get("last_observation"))
    active_worker = _mapping(observation.get("active_worker"))
    identity_ok = bool(
        goal_id
        and checkpoint
        and failure_goal_id == goal_id
        and failure_checkpoint == checkpoint
        and failure.get("escalation_required") is True
        and failure.get("owner_terminal") is True
    )
    target_still_blocked = bool(
        _text(observation.get("plan_state")) in {"blocked", "failed"}
        and (not plan_name or _text(observation.get("plan_name")) == plan_name)
        and active_worker.get("worker_pid_live") is not True
        and active_worker.get("fresh") is not True
    )
    if not identity_ok or not target_still_blocked:
        result["reason"] = "replan evidence is stale, live-owned, or identity-inconsistent"
        return result

    result.update(
        {
            "actionable": True,
            "reason": "terminal L1 evidence requires checkpoint-bound L2 replan",
            "goal_path": str(path),
            "goal_id": goal_id,
            "checkpoint_digest": checkpoint,
            "owner_run_id": _text(failure.get("owner_run_id")),
        }
    )
    return result


def stranded_replan_reason(
    *,
    marker_dir: Path,
    session: str,
    plan_name: str = "",
    blocker_id: str = "",
) -> str:
    """Return the deterministic L3 finding for an unconsumed L1 replan."""

    evidence = evaluate_checkpoint_escalation(
        marker_dir=marker_dir,
        session=session,
        plan_name=plan_name,
        blocker_id=blocker_id,
    )
    if not evidence["actionable"]:
        return ""
    return (
        "stranded_checkpoint_replan: terminal L1 evidence requires L2 but the "
        f"durable goal remains active goal_id={evidence['goal_id']} "
        f"checkpoint={evidence['checkpoint_digest']}"
    )


__all__ = ["evaluate_checkpoint_escalation", "stranded_replan_reason"]
