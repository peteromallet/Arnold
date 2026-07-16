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
import re
import subprocess
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
_DEFAULT_RECOVERY_FOLLOWUP_SECONDS = 30
_MAX_RECOVERY_FOLLOWUP_SECONDS = 900


def next_repair_goal_retry_sequence(goal: Mapping[str, Any]) -> int:
    """Return an unused retry sequence across owners and durable reservations."""

    owners = goal.get("owners") if isinstance(goal.get("owners"), list) else []
    sequence = len(owners) + 1
    goal_id = str(goal.get("goal_id") or "")
    target = goal.get("target") if isinstance(goal.get("target"), Mapping) else {}
    workspace = Path(str(target.get("workspace") or ""))
    run_root = workspace / ".megaplan" / "plans" / "resident-subagents"
    pattern = re.compile(rf":goal:{re.escape(goal_id)}:retry:(\d+)$")
    if not goal_id or not run_root.is_dir():
        return sequence
    for manifest_path in run_root.glob("managed-automatic-repair-*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        match = pattern.search(str(manifest.get("launch_idempotency_key") or ""))
        if match:
            sequence = max(sequence, int(match.group(1)) + 1)
    return sequence


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


def _git_head(workspace: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _quality_resolution_commit_custody(
    state: Mapping[str, Any], *, workspace: Path, workspace_head: str
) -> dict[str, Any]:
    """Verify that receipt-cited local repair commits survived target checkout."""

    meta = state.get("meta") if isinstance(state.get("meta"), Mapping) else {}
    resolutions = state.get("quality_gate_resolutions") or meta.get("quality_gate_resolutions")
    resolutions = resolutions if isinstance(resolutions, list) else []
    required: list[str] = []
    for resolution in resolutions[-10:]:
        if not isinstance(resolution, Mapping) or resolution.get("resolution") != "fixed":
            continue
        evidence = resolution.get("evidence")
        evidence = evidence if isinstance(evidence, list) else []
        for item in evidence[:10]:
            match = re.search(
                r"(?:^|\s)local dev fix commit:([0-9a-fA-F]{40})(?:\s|$)",
                str(item or ""),
            )
            if match and match.group(1).lower() not in required:
                required.append(match.group(1).lower())
    missing: list[str] = []
    for commit in required:
        try:
            result = subprocess.run(
                ["git", "-C", str(workspace), "merge-base", "--is-ancestor", commit, workspace_head],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            missing.append(commit)
            continue
        if result.returncode != 0:
            missing.append(commit)
    return {
        "required_commits": required,
        "missing_commits": missing,
        "verified": not missing,
    }


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


def _recovery_followup_seconds() -> int:
    raw = os.environ.get(
        "MEGAPLAN_REPAIR_RECOVERY_FOLLOWUP_SECONDS",
        str(_DEFAULT_RECOVERY_FOLLOWUP_SECONDS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_RECOVERY_FOLLOWUP_SECONDS
    return max(0, min(value, _MAX_RECOVERY_FOLLOWUP_SECONDS))


def _artifact_reference(path: Path, *, kind: str, run_id: str) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "kind": kind,
        "path": str(path),
        "run_id": run_id,
        "exists": path.is_file(),
    }
    if not reference["exists"]:
        return reference
    try:
        stat = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        reference.update(
            {
                "size_bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(),
                "sha256": digest.hexdigest(),
            }
        )
    except OSError as exc:
        reference["read_error"] = f"{type(exc).__name__}: {exc}"
    return reference


def _failed_fixer_evidence(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return bounded manifest/transcript/artifact refs for failed repair owners."""

    references: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    owners = payload.get("owners") if isinstance(payload.get("owners"), list) else []
    for owner in owners[-5:]:
        if not isinstance(owner, Mapping):
            continue
        run_id = str(owner.get("run_id") or "").strip()
        manifest_text = str(owner.get("manifest_path") or "").strip()
        if not manifest_text:
            continue
        manifest_path = Path(manifest_text)
        candidates = (
            ("manifest", manifest_path),
            ("transcript", manifest_path.parent / "run.log"),
            ("result", manifest_path.parent / "result.md"),
        )
        for kind, path in candidates:
            identity = (kind, str(path))
            if identity in seen:
                continue
            seen.add(identity)
            references.append(_artifact_reference(path, kind=kind, run_id=run_id))
    return references


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


def _same_path(left: object, right: object) -> bool | None:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text or not right_text:
        return None
    return Path(left_text).resolve(strict=False) == Path(right_text).resolve(strict=False)


def _session_identity_observation(
    *,
    marker_dir: str | Path | None,
    session: str,
    workspace: Path,
    remote_spec: str,
) -> dict[str, Any]:
    """Fence target evidence to the exact session marker that owns the goal."""

    marker_path = Path(marker_dir) / f"{session}.json" if marker_dir and session else None
    marker = _load_json(marker_path)
    marker_session = str(marker.get("session") or "")
    session_matches = marker_session == session if marker_session else None
    workspace_matches = _same_path(marker.get("workspace"), workspace)
    remote_spec_matches = _same_path(marker.get("remote_spec"), remote_spec)
    explicit_matches = [
        value
        for value in (session_matches, workspace_matches, remote_spec_matches)
        if value is not None
    ]
    return {
        "expected_session": session,
        "marker_path": str(marker_path) if marker_path is not None else "",
        "marker_present": bool(marker),
        "marker_session": marker_session,
        "marker_workspace": str(marker.get("workspace") or ""),
        "marker_remote_spec": str(marker.get("remote_spec") or ""),
        "session_matches": session_matches,
        "workspace_matches": workspace_matches,
        "remote_spec_matches": remote_spec_matches,
        "identity_matches": all(explicit_matches) if explicit_matches else None,
    }


def capture_checkpoint(
    *,
    workspace: str | Path,
    plan_name: str = "",
    remote_spec: str = "",
    marker_dir: str | Path | None = None,
    session: str = "",
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
    workspace_head = _git_head(root)
    quality_resolution_commit_custody = _quality_resolution_commit_custody(
        state, workspace=root, workspace_head=workspace_head
    )
    session_identity = _session_identity_observation(
        marker_dir=marker_dir,
        session=session,
        workspace=root,
        remote_spec=remote_spec,
    )
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
        "session_identity": session_identity,
        "workspace_head": workspace_head,
        "quality_resolution_commit_custody": quality_resolution_commit_custody,
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
        "session_identity_matches": session_identity.get("identity_matches"),
        "quality_resolution_commits_verified": quality_resolution_commit_custody.get("verified"),
    }
    checkpoint["progress_token"] = _digest(progress_facts)
    # Productive source changes reset only the deterministic-owner breaker;
    # they never satisfy the authoritative recovery contract above.
    checkpoint["iteration_token"] = _digest(
        {"progress_token": checkpoint["progress_token"], "workspace_head": workspace_head}
    )
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
    frozen_identity = (
        frozen.get("session_identity")
        if isinstance(frozen.get("session_identity"), Mapping)
        else {}
    )
    observed_identity = (
        observation.get("session_identity")
        if isinstance(observation.get("session_identity"), Mapping)
        else {}
    )
    if (
        frozen_identity.get("identity_matches") is False
        or observed_identity.get("identity_matches") is False
    ):
        return {
            "status": GOAL_ACTIVE,
            "reason": "replacement-session evidence cannot satisfy the original repair goal",
            "authoritative_progress": False,
            "blocker_cleared": False,
            "fresh_progress": False,
            "stage_advanced": False,
            "correct_worker_alive": None,
            "control_action": "investigate",
            "replacement_session_evidence_rejected": True,
            "expected_session_identity": dict(frozen_identity),
            "observed_session_identity": dict(observed_identity),
        }

    quality_commit_custody = (
        observation.get("quality_resolution_commit_custody")
        if isinstance(observation.get("quality_resolution_commit_custody"), Mapping)
        else {}
    )
    if quality_commit_custody.get("verified") is False:
        return {
            "status": GOAL_ACTIVE,
            "reason": (
                "quality repair evidence is not contained in the current target history; "
                "publication or target-history reconciliation is required"
            ),
            "authoritative_progress": False,
            "blocker_cleared": False,
            "fresh_progress": False,
            "stage_advanced": False,
            "correct_worker_alive": None,
            "control_action": "investigate",
            "quality_resolution_commit_custody": dict(quality_commit_custody),
        }

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


def _canonical_runner_live(observation: Mapping[str, Any]) -> bool:
    identity = (
        observation.get("session_identity")
        if isinstance(observation.get("session_identity"), Mapping)
        else {}
    )
    runner = (
        observation.get("runner_transition")
        if isinstance(observation.get("runner_transition"), Mapping)
        else {}
    )
    return bool(
        identity.get("identity_matches") is not False
        and runner.get("runner_pid_live") is True
        and runner.get("fresh") is True
    )


def _continued_progress(
    candidate: Mapping[str, Any], observation: Mapping[str, Any]
) -> bool:
    if str(candidate.get("progress_token") or "") != str(
        observation.get("progress_token") or ""
    ):
        return True
    candidate_acceptance = (
        candidate.get("acceptance")
        if isinstance(candidate.get("acceptance"), Mapping)
        else {}
    )
    observed_acceptance = (
        observation.get("acceptance")
        if isinstance(observation.get("acceptance"), Mapping)
        else {}
    )
    numeric_fields = (
        "plan_history_length",
        "chain_current_milestone_index",
        "chain_completed_count",
    )
    if any(
        int(observation.get(field) or 0) > int(candidate.get(field) or 0)
        for field in numeric_fields
    ):
        return True
    if int(observed_acceptance.get("seq") or 0) > int(
        candidate_acceptance.get("seq") or 0
    ):
        return True
    candidate_plan = str(candidate.get("chain_current_plan_name") or "")
    observed_plan = str(observation.get("chain_current_plan_name") or "")
    return bool(candidate_plan and observed_plan and candidate_plan != observed_plan)


def _recovery_receipt(
    *,
    payload: Mapping[str, Any],
    frozen: Mapping[str, Any],
    candidate: Mapping[str, Any] | None,
    observation: Mapping[str, Any],
    accepted: bool,
    reasons: Sequence[str],
    followup_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": "arnold-post-fixer-recovery-acceptance-v1",
        "accepted": accepted,
        "recorded_at": utc_now(),
        "goal_id": str(payload.get("goal_id") or ""),
        "checkpoint_digest": str(payload.get("checkpoint_digest") or ""),
        "requirements": {
            "authoritative_blocker_clearance": True,
            "live_canonical_runner": True,
            "fresh_progress_beyond_checkpoint": True,
            "bounded_continued_progress": True,
            "minimum_followup_seconds": followup_seconds,
        },
        "reasons": list(reasons),
        "pre_recovery_checkpoint": deepcopy(dict(frozen)),
        "post_recovery_checkpoint": (
            deepcopy(dict(candidate)) if isinstance(candidate, Mapping) else None
        ),
        "followup_checkpoint": deepcopy(dict(observation)),
        "failed_fixer_evidence": _failed_fixer_evidence(payload),
        "escalation": {
            "required": not accepted,
            "target": "meta_repair_root_cause" if not accepted else "",
            "reason": "post_fixer_recovery_gate_failed" if not accepted else "",
        },
    }


def _record_recovery_gate_failure(
    payload: dict[str, Any], receipt: Mapping[str, Any]
) -> None:
    failures = payload.setdefault("recovery_gate_failures", [])
    fingerprint = _digest(
        {
            "checkpoint_digest": receipt.get("checkpoint_digest"),
            "reasons": receipt.get("reasons"),
            "followup_progress_token": _load_json_value(
                receipt, "followup_checkpoint", "progress_token"
            ),
        }
    )
    if not any(
        isinstance(item, Mapping) and item.get("fingerprint") == fingerprint
        for item in failures
    ):
        item = deepcopy(dict(receipt))
        item["fingerprint"] = fingerprint
        failures.append(item)
        if len(failures) > 20:
            del failures[:-20]
    payload["recovery_acceptance"] = deepcopy(dict(receipt))


def _load_json_value(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def recovery_acceptance_verification(
    goal_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Project an accepted goal receipt into the shared recovery contract."""

    receipt = (
        goal_payload.get("recovery_acceptance")
        if isinstance(goal_payload.get("recovery_acceptance"), Mapping)
        else {}
    )
    if (
        receipt.get("schema_version")
        != "arnold-post-fixer-recovery-acceptance-v1"
        or receipt.get("accepted") is not True
    ):
        return {}
    target = (
        goal_payload.get("target")
        if isinstance(goal_payload.get("target"), Mapping)
        else {}
    )
    pre = (
        receipt.get("pre_recovery_checkpoint")
        if isinstance(receipt.get("pre_recovery_checkpoint"), Mapping)
        else {}
    )
    post = (
        receipt.get("post_recovery_checkpoint")
        if isinstance(receipt.get("post_recovery_checkpoint"), Mapping)
        else {}
    )
    followup = (
        receipt.get("followup_checkpoint")
        if isinstance(receipt.get("followup_checkpoint"), Mapping)
        else {}
    )
    runner = (
        followup.get("runner_transition")
        if isinstance(followup.get("runner_transition"), Mapping)
        else {}
    )
    blocker_id = str(target.get("blocker_id") or "")
    return {
        "outcome": "progressed",
        "repair_completed_at": str(
            goal_payload.get("created_at") or pre.get("captured_at") or ""
        ),
        "original_blocker": {"blocker_id": blocker_id},
        "observation": {
            "kind": "post_fixer_recovery_gate",
            "blocker_id": blocker_id,
            "blocker_cleared": bool(followup.get("latest_failure_cleared")),
            "directly_observed": True,
            "independent": True,
            "canonical_runner_live": bool(
                runner.get("runner_pid_live") is True
                and runner.get("fresh") is True
            ),
            "fresh_progress_beyond_checkpoint": True,
            "continued_progress": _continued_progress(post, followup),
            "first_progress_observed_at": str(post.get("captured_at") or ""),
            "observed_at": str(followup.get("captured_at") or ""),
            "checkpoint_digest": receipt.get("checkpoint_digest"),
            "receipt_recorded_at": receipt.get("recorded_at"),
        },
        "pre_snapshot": deepcopy(dict(pre)),
        "post_snapshot": deepcopy(dict(followup)),
        "recovery_acceptance": deepcopy(dict(receipt)),
        "failed_fixer_evidence": deepcopy(
            receipt.get("failed_fixer_evidence") or []
        ),
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
                marker_dir=marker_dir,
                session=session,
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
                    "marker_dir": str(Path(marker_dir)),
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
                    "requires_live_canonical_runner": True,
                    "requires_bounded_continued_progress": True,
                    "minimum_followup_seconds": _recovery_followup_seconds(),
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


def reconcile_l2_replan(
    goal_path: str | Path,
    *,
    session: str,
    workspace: str | Path,
    remote_spec: str,
    blocker_id: str,
    context_digest: str,
    receipt_digest: str = "",
) -> dict[str, Any]:
    """Record a receipt-bound L2 replan epoch without replacing the checkpoint."""
    path = Path(goal_path)
    identity = {
        "session": str(session or "").strip(),
        "workspace": str(Path(workspace)),
        "remote_spec": str(remote_spec or "").strip(),
        "blocker_id": str(blocker_id or "").strip(),
    }
    digest = str(context_digest or "").strip()
    if not digest or not all(identity.values()):
        raise ValueError("L2 replan reconciliation identity is incomplete")
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = _load_json(path)
        if payload.get("schema_version") != REPAIR_GOAL_SCHEMA:
            raise ValueError(f"repair goal is missing or invalid: {path}")
        if payload.get("status") != GOAL_ACTIVE or payload.get("terminal") is True:
            raise ValueError("L2 replan reconciliation requires an active repair goal")
        target = payload.get("target") if isinstance(payload.get("target"), Mapping) else {}
        actual = {
            "session": str(target.get("session") or "").strip(),
            "workspace": str(Path(str(target.get("workspace") or ""))),
            "remote_spec": str(target.get("remote_spec") or "").strip(),
            "blocker_id": str(target.get("blocker_id") or "").strip(),
        }
        if actual != identity:
            raise ValueError("L2 replan reconciliation target identity disagrees")
        replans = payload.setdefault("l2_replans", [])
        if not isinstance(replans, list):
            raise ValueError("repair goal L2 replan ledger is invalid")
        for entry in replans:
            if isinstance(entry, Mapping) and entry.get("context_digest") == digest:
                return {
                    "goal_id": payload["goal_id"], "goal_path": str(path),
                    "checkpoint_digest": payload["checkpoint_digest"],
                    "replan_epoch": int(entry.get("epoch") or 0),
                    "status": "already_reconciled",
                }
        epoch = max((int(item.get("epoch") or 0) for item in replans if isinstance(item, Mapping)), default=0) + 1
        replans.append({
            "schema_version": "arnold-l2-replan-epoch-v1", "epoch": epoch,
            "context_digest": digest, "receipt_digest": str(receipt_digest or "").strip(),
            "reconciled_at": utc_now(), "frozen_checkpoint_digest": payload.get("checkpoint_digest"),
        })
        payload["active_replan_epoch"] = epoch
        payload["updated_at"] = utc_now()
        _atomic_write(path, payload)
        return {
            "goal_id": payload["goal_id"], "goal_path": str(path),
            "checkpoint_digest": payload["checkpoint_digest"], "replan_epoch": epoch,
            "status": "newly_reconciled",
        }


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
            marker_dir=str(target.get("marker_dir") or path.parents[2]),
            session=str(target.get("session") or ""),
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
                "requires_live_canonical_runner": True,
                "requires_bounded_continued_progress": True,
                "minimum_followup_seconds": _recovery_followup_seconds(),
                "success_authority": "authoritative_target_evidence",
                "migrated_from_legacy_goal_at": utc_now(),
            }
            payload["recovery_contract"] = contract
        else:
            contract.setdefault("requires_live_canonical_runner", True)
            contract.setdefault("requires_bounded_continued_progress", True)
            contract.setdefault(
                "minimum_followup_seconds", _recovery_followup_seconds()
            )
        effective_frozen = deepcopy(frozen)
        effective_frozen["target_stage"] = str(contract.get("required_beyond_stage") or "")
        contract_rank = contract.get("required_beyond_stage_rank")
        effective_frozen["target_stage_rank"] = int(
            -1 if contract_rank is None else contract_rank
        )
        evaluation = evaluate_checkpoint(effective_frozen, observation)
        followup_seconds = int(
            contract.get("minimum_followup_seconds")
            if contract.get("minimum_followup_seconds") is not None
            else _recovery_followup_seconds()
        )
        candidate_record = (
            payload.get("recovery_candidate")
            if isinstance(payload.get("recovery_candidate"), Mapping)
            else None
        )
        candidate_observation = (
            candidate_record.get("observation")
            if isinstance(candidate_record, Mapping)
            and isinstance(candidate_record.get("observation"), Mapping)
            else None
        )
        if evaluation["status"] == GOAL_PROGRESSED:
            if not _canonical_runner_live(observation):
                reasons = ["canonical_runner_not_live"]
                receipt = _recovery_receipt(
                    payload=payload,
                    frozen=frozen,
                    candidate=candidate_observation,
                    observation=observation,
                    accepted=False,
                    reasons=reasons,
                    followup_seconds=followup_seconds,
                )
                _record_recovery_gate_failure(payload, receipt)
                evaluation.update(
                    {
                        "status": GOAL_ACTIVE,
                        "authoritative_progress": False,
                        "control_action": "meta_repair",
                        "recovery_gate_accepted": False,
                        "recovery_gate_reasons": reasons,
                        "reason": (
                            "post-fixer recovery gate rejected candidate progress: "
                            "the exact canonical runner is not live and fresh"
                        ),
                        "failed_fixer_evidence": receipt["failed_fixer_evidence"],
                    }
                )
            elif candidate_observation is None:
                candidate_record = {
                    "schema_version": "arnold-post-fixer-recovery-candidate-v1",
                    "recorded_at": utc_now(),
                    "checkpoint_digest": payload.get("checkpoint_digest"),
                    "observation": deepcopy(observation),
                    "evaluation": deepcopy(evaluation),
                    "failed_fixer_evidence": _failed_fixer_evidence(payload),
                }
                payload["recovery_candidate"] = candidate_record
                evaluation.update(
                    {
                        "status": GOAL_ACTIVE,
                        "authoritative_progress": False,
                        "control_action": "observe_recovery",
                        "recovery_gate_accepted": False,
                        "recovery_gate_reasons": [
                            "bounded_followup_observation_pending"
                        ],
                        "reason": (
                            "candidate recovery cleared the blocker, has a live canonical "
                            "runner, and advanced beyond the frozen checkpoint; bounded "
                            "continued-progress observation is still required"
                        ),
                    }
                )
            else:
                candidate_at = _parse_time(candidate_record.get("recorded_at"))
                observed_at = _parse_time(observation.get("captured_at"))
                elapsed_seconds = (
                    max(0.0, (observed_at - candidate_at).total_seconds())
                    if candidate_at is not None and observed_at is not None
                    else 0.0
                )
                if elapsed_seconds < followup_seconds:
                    evaluation.update(
                        {
                            "status": GOAL_ACTIVE,
                            "authoritative_progress": False,
                            "control_action": "observe_recovery",
                            "recovery_gate_accepted": False,
                            "recovery_gate_reasons": [
                                "bounded_followup_observation_pending"
                            ],
                            "followup_elapsed_seconds": elapsed_seconds,
                            "followup_required_seconds": followup_seconds,
                            "reason": (
                                "candidate recovery remains live; bounded follow-up "
                                "window has not elapsed"
                            ),
                        }
                    )
                elif not _continued_progress(candidate_observation, observation):
                    reasons = ["continued_progress_not_observed"]
                    receipt = _recovery_receipt(
                        payload=payload,
                        frozen=frozen,
                        candidate=candidate_observation,
                        observation=observation,
                        accepted=False,
                        reasons=reasons,
                        followup_seconds=followup_seconds,
                    )
                    _record_recovery_gate_failure(payload, receipt)
                    evaluation.update(
                        {
                            "status": GOAL_ACTIVE,
                            "authoritative_progress": False,
                            "control_action": "meta_repair",
                            "recovery_gate_accepted": False,
                            "recovery_gate_reasons": reasons,
                            "reason": (
                                "post-fixer recovery gate rejected candidate progress: "
                                "the bounded follow-up showed no continued progress"
                            ),
                            "failed_fixer_evidence": receipt[
                                "failed_fixer_evidence"
                            ],
                        }
                    )
                else:
                    receipt = _recovery_receipt(
                        payload=payload,
                        frozen=frozen,
                        candidate=candidate_observation,
                        observation=observation,
                        accepted=True,
                        reasons=[],
                        followup_seconds=followup_seconds,
                    )
                    payload["recovery_acceptance"] = receipt
                    payload.pop("recovery_candidate", None)
                    evaluation.update(
                        {
                            "recovery_gate_accepted": True,
                            "recovery_gate_reasons": [],
                            "bounded_followup_seconds": elapsed_seconds,
                            "failed_fixer_evidence": receipt[
                                "failed_fixer_evidence"
                            ],
                            "reason": (
                                "post-fixer recovery gate verified blocker clearance, "
                                "the live canonical runner, beyond-checkpoint progress, "
                                "and continued progress across the bounded observation"
                            ),
                        }
                    )
        elif candidate_observation is not None and evaluation["status"] == GOAL_ACTIVE:
            reasons = ["candidate_recovery_regressed"]
            if evaluation.get("blocker_cleared") is not True:
                reasons.append("authoritative_blocker_not_cleared")
            if not _canonical_runner_live(observation):
                reasons.append("canonical_runner_not_live")
            receipt = _recovery_receipt(
                payload=payload,
                frozen=frozen,
                candidate=candidate_observation,
                observation=observation,
                accepted=False,
                reasons=reasons,
                followup_seconds=followup_seconds,
            )
            _record_recovery_gate_failure(payload, receipt)
            evaluation.update(
                {
                    "control_action": "meta_repair",
                    "recovery_gate_accepted": False,
                    "recovery_gate_reasons": reasons,
                    "reason": (
                        "post-fixer recovery candidate regressed before durable "
                        "acceptance; escalate with failed-fixer evidence"
                    ),
                    "failed_fixer_evidence": receipt["failed_fixer_evidence"],
                }
            )
        active_replan_epoch = int(payload.get("active_replan_epoch") or 0)
        owner_cycle = (
            action.startswith("owner-iteration-") or "post-dev-fix" in action
        ) and evaluation.get("control_action") not in {
            "preserve_live",
            "observe_recovery",
            "meta_repair",
        }
        repeated_owner_cycles = 0
        if owner_cycle and evaluation["status"] == GOAL_ACTIVE:
            token = str(observation.get("iteration_token") or observation.get("progress_token") or "")
            for prior in reversed(payload.get("cycles") or []):
                if not isinstance(prior, Mapping) or not prior.get("owner_cycle"):
                    continue
                if int(prior.get("replan_epoch") or 0) != active_replan_epoch:
                    break
                prior_observation = prior.get("observation") if isinstance(prior.get("observation"), Mapping) else {}
                prior_token = str(
                    prior_observation.get("iteration_token")
                    or prior_observation.get("progress_token")
                    or ""
                )
                if prior_token != token:
                    break
                repeated_owner_cycles += 1
            repeated_owner_cycles += 1
            if repeated_owner_cycles >= _DETERMINISTIC_OWNER_REPEAT_LIMIT:
                evaluation["control_action"] = "replan"
                evaluation["circuit_breaker_required"] = True
                evaluation["deterministic_repeat_count"] = repeated_owner_cycles
                evaluation["reason"] = (
                    "deterministic owner failure repeated without a new target or productive-change token; "
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
            "replan_epoch": active_replan_epoch,
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
            "recovery_candidate": deepcopy(payload.get("recovery_candidate")),
            "recovery_acceptance": deepcopy(payload.get("recovery_acceptance")),
            "recovery_gate_failures": deepcopy(
                (payload.get("recovery_gate_failures") or [])[-5:]
            ),
        }


def record_terminal_failure(
    goal_path: str | Path,
    *,
    outcome: str,
    phase: str,
    reason: str,
    owner_run_id: str = "",
    owner_manifest_path: str = "",
) -> dict[str, Any]:
    """Record a bounded owner failure without pretending the goal succeeded."""

    path = Path(goal_path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = _load_json(path)
        if payload.get("schema_version") != REPAIR_GOAL_SCHEMA:
            raise ValueError(f"repair goal is missing or invalid: {path}")
        frozen = (
            payload.get("frozen_checkpoint")
            if isinstance(payload.get("frozen_checkpoint"), Mapping)
            else {}
        )
        failure = {
            "recorded_at": utc_now(),
            "owner_terminal": True,
            "semantic_completion": False,
            "outcome": outcome,
            "phase": phase,
            "reason": reason,
            "owner_run_id": owner_run_id,
            "owner_manifest_path": owner_manifest_path,
            "goal_id": str(payload.get("goal_id") or ""),
            "checkpoint_digest": str(payload.get("checkpoint_digest") or ""),
            "unresolved_checkpoint": deepcopy(dict(frozen)),
            "last_evaluation": deepcopy(payload.get("last_evaluation") or {}),
            "last_observation": deepcopy(payload.get("last_observation") or {}),
            "escalation_required": True,
        }
        failures = payload.setdefault("terminal_failures", [])
        failures.append(failure)
        if len(failures) > 20:
            del failures[:-20]
        payload["last_terminal_failure"] = failure
        payload["updated_at"] = utc_now()
        _atomic_write(path, payload)
        return {
            "goal_id": payload["goal_id"],
            "goal_path": str(path),
            "checkpoint_digest": payload["checkpoint_digest"],
            "status": payload["status"],
            "semantic_completion": payload["semantic_completion"],
            "terminal_failure": failure,
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
    reconcile = sub.add_parser("reconcile-l2-replan")
    reconcile.add_argument("--goal-path", required=True)
    reconcile.add_argument("--session", required=True)
    reconcile.add_argument("--workspace", required=True)
    reconcile.add_argument("--remote-spec", required=True)
    reconcile.add_argument("--blocker-id", required=True)
    reconcile.add_argument("--context-digest", required=True)
    reconcile.add_argument("--receipt-digest", default="")
    fail = sub.add_parser("record-terminal-failure")
    fail.add_argument("--goal-path", required=True)
    fail.add_argument("--outcome", required=True)
    fail.add_argument("--phase", required=True)
    fail.add_argument("--reason", required=True)
    fail.add_argument("--owner-run-id", default="")
    fail.add_argument("--owner-manifest-path", default="")
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
    elif args.command == "evaluate":
        result = evaluate_repair_goal(
            args.goal_path,
            action=args.action,
            owner_run_id=args.owner_run_id,
            owner_manifest_path=args.owner_manifest_path,
        )
    elif args.command == "reconcile-l2-replan":
        result = reconcile_l2_replan(
            args.goal_path, session=args.session, workspace=args.workspace,
            remote_spec=args.remote_spec, blocker_id=args.blocker_id,
            context_digest=args.context_digest, receipt_digest=args.receipt_digest,
        )
    else:
        result = record_terminal_failure(
            args.goal_path,
            outcome=args.outcome,
            phase=args.phase,
            reason=args.reason,
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
    "reconcile_l2_replan",
    "ensure_repair_goal",
    "evaluate_checkpoint",
    "evaluate_repair_goal",
    "next_repair_goal_retry_sequence",
    "record_terminal_failure",
    "repair_goal_path",
]
