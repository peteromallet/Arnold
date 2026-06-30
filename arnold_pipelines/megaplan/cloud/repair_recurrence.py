"""Recurrence detection for cloud repair-loop dispatches."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from typing import Any, Mapping

PROBLEM_SIGNATURE_FIELDS = (
    "failure_kind",
    "current_state",
    "phase_or_step",
    "milestone_or_plan",
    "gate_recommendation",
    "blocked_task_id",
)


def atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a JSON file used by the repair loop."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_path(value: object) -> Path | None:
    text = _as_text(value)
    if not text:
        return None
    return Path(text)


def _parse_when(value: object) -> datetime | None:
    text = _as_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


def _run_command(args: list[str], *, cwd: Path, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _probe_pr_state(workspace: Path | None, pr_number: object) -> dict[str, Any]:
    pr = _as_int(pr_number)
    if pr is None:
        return {"available": False, "reason": "no_pr_number"}
    if workspace is None:
        return {"available": False, "pr_number": pr, "reason": "no_workspace"}
    try:
        proc = _run_command(
            ["gh", "pr", "view", str(pr), "--json", "state,mergedAt"],
            cwd=workspace,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "pr_number": pr, "reason": type(exc).__name__}
    if proc.returncode != 0:
        return {
            "available": False,
            "pr_number": pr,
            "reason": "gh_pr_view_failed",
            "stderr": _as_text(proc.stderr)[-500:],
        }
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": False, "pr_number": pr, "reason": "invalid_gh_json"}
    state = _as_text(payload.get("state")).lower()
    merged_at = _as_text(payload.get("mergedAt"))
    return {
        "available": True,
        "pr_number": pr,
        "state": state,
        "merged_at": merged_at,
        "merged": state == "merged" or bool(merged_at),
    }


def _candidate_base_refs(chain_state: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("target_base_ref", "base_ref", "target_base", "base_branch"):
        value = _as_text(chain_state.get(key))
        if value:
            refs.append(value)
            if key == "base_branch" and not value.startswith("origin/"):
                refs.append(f"origin/{value}")
    return list(dict.fromkeys(refs))


def _probe_git_progress(workspace: Path | None, chain_state: Mapping[str, Any]) -> dict[str, Any]:
    if workspace is None:
        return {"available": False, "reason": "no_workspace"}
    try:
        inside = _run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=workspace)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": type(exc).__name__}
    if inside.returncode != 0 or inside.stdout.strip().lower() != "true":
        return {"available": False, "reason": "not_git_worktree"}
    try:
        head = _run_command(["git", "rev-parse", "HEAD"], cwd=workspace)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": type(exc).__name__}
    if head.returncode != 0:
        return {"available": False, "reason": "git_head_failed", "stderr": _as_text(head.stderr)[-500:]}
    base_errors: list[str] = []
    for base_ref in _candidate_base_refs(chain_state):
        try:
            ahead = _run_command(["git", "rev-list", "--count", f"{base_ref}..HEAD"], cwd=workspace)
        except (OSError, subprocess.TimeoutExpired) as exc:
            base_errors.append(f"{base_ref}:{type(exc).__name__}")
            continue
        if ahead.returncode != 0:
            base_errors.append(f"{base_ref}:{_as_text(ahead.stderr)[-120:]}")
            continue
        return {
            "available": True,
            "head": head.stdout.strip(),
            "base_ref": base_ref,
            "ahead_count": _as_int(ahead.stdout.strip()),
        }
    reason = "no_base_ref" if not _candidate_base_refs(chain_state) else "git_rev_list_failed"
    return {"available": False, "head": head.stdout.strip(), "reason": reason, "errors": base_errors[-3:]}


def _first_blocked_task_id(execute_attempt_context: Mapping[str, Any]) -> str:
    context = _as_dict(execute_attempt_context)
    for section_name, key in (
        ("execution_batch", "blocked_or_deferred_tasks"),
        ("execute_batch_output", "blocked_or_deferred_tasks"),
        ("finalize", "skipped_or_deferred_tasks"),
    ):
        section = _as_dict(context.get(section_name))
        for task in _as_list(section.get(key)):
            if not isinstance(task, dict):
                continue
            task_id = _as_text(task.get("task_id") or task.get("id"))
            if task_id:
                return task_id
    return ""


def _history_last_step(execute_attempt_context: Mapping[str, Any]) -> str:
    context = _as_dict(execute_attempt_context)
    history = _as_dict(context.get("plan_history"))
    last_entries = _as_list(history.get("last_entries"))
    for entry in reversed(last_entries):
        if not isinstance(entry, dict):
            continue
        step = _as_text(entry.get("step"))
        if step:
            return step
    return ""


def build_problem_signature(failure_context: Mapping[str, Any]) -> dict[str, str]:
    """Return the controlled-field signature used for recurrence identity."""

    context = _as_dict(failure_context)
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    chain_state = _as_dict(context.get("chain_state_summary"))
    plan_runtime = _as_dict(context.get("plan_runtime_state"))
    last_gate = _as_dict(context.get("last_gate"))
    execute_attempt = _as_dict(context.get("execute_attempt_context"))
    return {
        "failure_kind": _as_text(
            plan_failure.get("kind")
            or context.get("failure_classification")
            or chain_state.get("last_state")
        ),
        "current_state": _as_text(
            plan_runtime.get("current_state")
            or plan_failure.get("current_state")
            or chain_state.get("last_state")
            or chain_state.get("current_state")
        ),
        "phase_or_step": _as_text(
            plan_failure.get("phase")
            or _history_last_step(execute_attempt)
        ),
        "milestone_or_plan": _as_text(
            chain_state.get("current_milestone_label")
            or chain_state.get("current_plan_name")
            or plan_failure.get("plan_name")
        ),
        "gate_recommendation": _as_text(last_gate.get("recommendation")),
        "blocked_task_id": _first_blocked_task_id(execute_attempt),
    }


def signature_tuple(signature: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(_as_text(signature.get(field)) for field in PROBLEM_SIGNATURE_FIELDS)


def build_advancement_snapshot(
    failure_context: Mapping[str, Any],
    *,
    run_kind: str = "",
    workspace: str | Path | None = None,
    logger: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    context = _as_dict(failure_context)
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    chain_state = _as_dict(context.get("chain_state_summary"))
    plan_runtime = _as_dict(context.get("plan_runtime_state"))
    workspace_path = _as_path(workspace) or _as_path(context.get("workspace"))
    pr_check = _probe_pr_state(workspace_path, chain_state.get("pr_number"))
    git_check = _probe_git_progress(workspace_path, chain_state)
    external_available = bool(pr_check.get("available")) or bool(git_check.get("available"))
    fallback_reason = ""
    if not external_available:
        fallback_reason = (
            "external advancement checks unavailable "
            f"(pr={pr_check.get('reason')}; git={git_check.get('reason')}); "
            "falling back to state-file milestone counters"
        )
        _log(logger, fallback_reason)
    return {
        "run_kind": _as_text(run_kind or context.get("run_kind")),
        "completed_count": _as_int(chain_state.get("completed_count")),
        "current_milestone_index": _as_int(chain_state.get("current_milestone_index")),
        "current_state": _as_text(
            plan_runtime.get("current_state")
            or plan_failure.get("current_state")
            or chain_state.get("last_state")
            or chain_state.get("current_state")
        ),
        "phase": _as_text(plan_failure.get("phase")),
        "milestone_or_plan": _as_text(
            chain_state.get("current_milestone_label")
            or chain_state.get("current_plan_name")
            or plan_failure.get("plan_name")
        ),
        "pr_number": _as_int(chain_state.get("pr_number")),
        "external_checks": {
            "pr": pr_check,
            "git": git_check,
            "state_fallback": {
                "used": not external_available,
                "reason": fallback_reason,
            },
        },
    }


def has_advancement(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> bool:
    if not previous:
        return False
    prev = _as_dict(previous)
    curr = _as_dict(current)
    curr_external = _as_dict(curr.get("external_checks"))
    curr_pr = _as_dict(curr_external.get("pr"))
    if bool(curr_pr.get("available")) and bool(curr_pr.get("merged")):
        return True

    prev_external = _as_dict(prev.get("external_checks"))
    prev_git = _as_dict(prev_external.get("git"))
    curr_git = _as_dict(curr_external.get("git"))
    if bool(prev_git.get("available")) and bool(curr_git.get("available")):
        prev_head = _as_text(prev_git.get("head"))
        curr_head = _as_text(curr_git.get("head"))
        prev_ahead = _as_int(prev_git.get("ahead_count"))
        curr_ahead = _as_int(curr_git.get("ahead_count"))
        if curr_head and prev_head and curr_head != prev_head:
            if prev_ahead is None or curr_ahead is None or curr_ahead >= prev_ahead:
                return True
        if prev_ahead is not None and curr_ahead is not None and curr_ahead > prev_ahead:
            return True

    external_available = any(
        bool(_as_dict(checks.get(name)).get("available"))
        for checks in (prev_external, curr_external)
        for name in ("pr", "git")
    )
    if external_available:
        return False

    prev_completed = _as_int(prev.get("completed_count"))
    curr_completed = _as_int(curr.get("completed_count"))
    if prev_completed is not None and curr_completed is not None and curr_completed > prev_completed:
        return True
    prev_index = _as_int(prev.get("current_milestone_index"))
    curr_index = _as_int(curr.get("current_milestone_index"))
    if prev_index is not None and curr_index is not None and curr_index > prev_index:
        return True
    if _as_text(prev.get("current_state")).lower() not in {"done", "complete", "completed"}:
        if _as_text(curr.get("current_state")).lower() in {"done", "complete", "completed"}:
            return True
    return False


def update_session_repair_snapshot(
    previous_snapshot: Mapping[str, Any] | None,
    current_snapshot: Mapping[str, Any],
    *,
    dispatched_at: str,
    min_dispatches: int = 3,
    window_seconds: int = 21600,
) -> dict[str, Any]:
    previous = _as_dict(previous_snapshot)
    current = _as_dict(current_snapshot)
    previous_dispatch_snapshot = _as_dict(previous.get("last_dispatch_snapshot"))
    advanced = has_advancement(previous_dispatch_snapshot, current)
    recent_dispatches: list[str]
    if advanced:
        recent_dispatches = [dispatched_at]
    else:
        cutoff = (_parse_when(dispatched_at) or datetime.now(timezone.utc)) - timedelta(
            seconds=max(int(window_seconds), 0)
        )
        recent_dispatches = []
        for value in _as_list(previous.get("no_advance_dispatches")):
            when = _parse_when(value)
            if when is not None and when >= cutoff:
                recent_dispatches.append(_as_text(value))
        recent_dispatches.append(dispatched_at)
    no_advance_count = len(recent_dispatches)
    return {
        "updated_at": dispatched_at,
        "current": current,
        "last_dispatch_snapshot": current,
        "no_advance_dispatches": recent_dispatches,
        "no_advance_count": no_advance_count,
        "advancement_since_last_dispatch": advanced,
        "window_seconds": int(window_seconds),
        "min_dispatches": int(min_dispatches),
        "layer2_recurrence": no_advance_count >= int(min_dispatches),
    }


def evaluate_recurrence(
    current_signature: Mapping[str, Any],
    attempts: list[Mapping[str, Any]] | None,
    session_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_signature = {
        field: _as_text(_as_dict(current_signature).get(field))
        for field in PROBLEM_SIGNATURE_FIELDS
    }
    current_key = signature_tuple(normalized_signature)
    prior_attempts = attempts or []
    matching_attempt_ids: list[int] = []
    for attempt in prior_attempts:
        if not isinstance(attempt, Mapping):
            continue
        prior_signature = _as_dict(attempt.get("problem_signature"))
        if signature_tuple(prior_signature) != current_key:
            continue
        attempt_id = _as_int(attempt.get("attempt_id"))
        if attempt_id is not None:
            matching_attempt_ids.append(attempt_id)
    snapshot = _as_dict(session_snapshot)
    no_advance_count = _as_int(snapshot.get("no_advance_count")) or 0
    min_dispatches = _as_int(snapshot.get("min_dispatches")) or 0
    layer1_detected = bool(matching_attempt_ids)
    layer2_detected = no_advance_count >= min_dispatches > 0
    attempt_number = max(len(matching_attempt_ids) + 1, no_advance_count or 1)
    return {
        "detected": layer1_detected or layer2_detected,
        "attempt_number": attempt_number,
        "problem_signature": normalized_signature,
        "layer1": {
            "detected": layer1_detected,
            "matching_attempt_ids": matching_attempt_ids,
            "repeat_count": len(matching_attempt_ids),
        },
        "layer2": {
            "detected": layer2_detected,
            "no_advance_dispatch_count": no_advance_count,
            "min_dispatches": min_dispatches,
            "window_seconds": _as_int(snapshot.get("window_seconds")) or 0,
        },
    }
