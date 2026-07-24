"""Recurrence detection for cloud repair-loop dispatches."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from typing import Any, Mapping

from arnold_pipelines.megaplan.orchestration.phase_result import (
    is_superseded_recovered_phase_result,
)
from arnold_pipelines.megaplan.watchdog.signals import compute_signal_bundle

# ── M7 custody contract imports (shadow/report-only) ────────────────────
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    RepairOccurrenceKey,
    build_custody_target_key,
    build_repair_occurrence_key,
    occurrence_digest,
    F01_REPAIR_OCCURRENCE_FIELDS as _F01_REPAIR_OCCURRENCE_FIELDS,
)

PROBLEM_SIGNATURE_FIELDS = (
    "failure_kind",
    "current_state",
    "phase_or_step",
    "milestone_or_plan",
    "gate_recommendation",
    "blocked_task_id",
    "event_signature",
)

# ── Acceptance predicate signature fields ─────────────────────────────────
# Appended to PROBLEM_SIGNATURE_FIELDS to create distinct repair identities
# for atomic completion predicate failures versus fixer-infrastructure
# failures.  Every field defaults to "" when no acceptance context is present,
# so legacy fixer-infrastructure signatures remain byte-identical.
ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS = (
    "acceptance_predicate_kind",
    "acceptance_predicate_evidence_kind",
    "acceptance_predicate_summary",
    "acceptance_transaction_id",
    "acceptance_snapshot_hash",
    "acceptance_evidence_refs",
    "safe_recovery_action",
    "recovery_action",
)

EXTENDED_PROBLEM_SIGNATURE_FIELDS = PROBLEM_SIGNATURE_FIELDS + ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS


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


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_path(value: object) -> Path | None:
    text = _as_text(value)
    if not text:
        return None
    return Path(text)


def _has_entries(value: object) -> bool:
    if isinstance(value, list):
        return any(bool(_as_text(item)) for item in value)
    return bool(_as_text(value))


def _plan_identity(context: Mapping[str, Any]) -> str:
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    chain_state = _as_dict(context.get("chain_state_summary"))
    return _as_text(
        chain_state.get("current_plan_name")
        or plan_failure.get("plan_name")
        or _as_dict(context.get("plan_runtime_state")).get("plan_name")
    )


def _read_json_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _empty_pending_batch_task_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    if _has_entries(payload.get("files_changed")) or _has_entries(payload.get("commands_run")):
        return ()
    raw_tasks = payload.get("task_updates")
    if not isinstance(raw_tasks, list):
        raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return ()
    task_ids: list[str] = []
    for raw_task in raw_tasks:
        task = _as_dict(raw_task)
        if not task:
            return ()
        if _as_text(task.get("status")).lower() != "pending":
            return ()
        if _has_entries(task.get("files_changed")) or _has_entries(task.get("commands_run")):
            return ()
        task_id = _as_text(task.get("task_id") or task.get("id"))
        if task_id:
            task_ids.append(task_id)
    return tuple(task_ids)


def _empty_execute_batch_summary(context: Mapping[str, Any]) -> dict[str, Any]:
    attempt_context = _as_dict(context.get("execute_attempt_context"))
    plan = _plan_identity(context)
    if not plan:
        return {}
    for section_name in ("execute_batch_output", "execution_batch"):
        section = _as_dict(attempt_context.get(section_name))
        payload = _read_json_file(_as_path(section.get("path")))
        task_ids = _empty_pending_batch_task_ids(payload)
        if task_ids:
            return {
                "plan": plan,
                "section": section_name,
                "path": _as_text(section.get("path")),
                "task_ids": list(task_ids),
            }
    return {}


def _normalize_empty_batch_summary(value: object) -> dict[str, Any]:
    item = _as_dict(value)
    plan = _as_text(item.get("plan"))
    task_ids = tuple(
        _as_text(task_id)
        for task_id in _as_list(item.get("task_ids"))
        if _as_text(task_id)
    )
    if not plan or not task_ids:
        return {}
    return {
        "plan": plan,
        "task_ids": task_ids,
        "section": _as_text(item.get("section")),
        "path": _as_text(item.get("path")),
    }


def _empty_batch_summary_for_attempt(attempt: Mapping[str, Any]) -> dict[str, Any]:
    advancement_summary = _normalize_empty_batch_summary(
        _as_dict(attempt.get("advancement_snapshot")).get("execute_empty_batch")
    )
    if advancement_summary:
        return advancement_summary
    return _normalize_empty_batch_summary(
        _empty_execute_batch_summary(_as_dict(attempt.get("failure_context")))
    )


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


def _resolve_plan_dir(
    context: Mapping[str, Any],
    *,
    workspace: Path | None,
) -> Path | None:
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    state_path = _as_path(plan_failure.get("state_path"))
    if state_path is not None:
        return state_path.parent
    events_path = _as_path(context.get("plan_events_path"))
    if events_path is not None:
        return events_path.parent
    plan_name = _as_text(
        _as_dict(context.get("chain_state_summary")).get("current_plan_name")
        or plan_failure.get("plan_name")
    )
    if workspace is not None and plan_name:
        return workspace / ".megaplan" / "plans" / plan_name
    return None


def _probe_plan_activity(
    context: Mapping[str, Any],
    *,
    workspace: Path | None,
) -> dict[str, Any]:
    plan_dir = _resolve_plan_dir(context, workspace=workspace)
    if plan_dir is None or not plan_dir.exists():
        return {"available": False, "reason": "missing_plan_dir"}
    events_path = plan_dir / "events.ndjson"
    try:
        signals = compute_signal_bundle(plan_dir)
    except Exception as exc:
        return {
            "available": False,
            "reason": type(exc).__name__,
            "plan_dir": str(plan_dir),
        }
    try:
        events_mtime = events_path.stat().st_mtime if events_path.exists() else 0.0
        events_size = events_path.stat().st_size if events_path.exists() else 0
    except OSError:
        events_mtime = 0.0
        events_size = 0
    return {
        "available": True,
        "plan_dir": str(plan_dir),
        "events_path": str(events_path),
        "events_mtime": events_mtime,
        "events_size": events_size,
        "liveness": str(signals.liveness or ""),
        "liveness_reason": str(signals.liveness_reason or ""),
        "has_in_flight_llm": bool(signals.has_in_flight_llm),
        "last_event_age_seconds": signals.last_event_age_seconds,
    }


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


def _mechanical_redrive_only_context(context: Mapping[str, Any]) -> bool:
    stale_state = _as_dict(context.get("stale_state"))
    if _as_text(stale_state.get("classification")) != "NO LATEST FAILURE":
        return False
    if _as_text(stale_state.get("recommended_action")) != "mechanical re-drive only":
        return False
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    return not any(
        _as_text(plan_failure.get(key))
        for key in ("kind", "message", "state", "recorded_at", "phase")
    )


def build_problem_signature(failure_context: Mapping[str, Any]) -> dict[str, str]:
    """Return the controlled-field signature used for recurrence identity."""

    context = _as_dict(failure_context)
    if _mechanical_redrive_only_context(context):
        return {field: "" for field in PROBLEM_SIGNATURE_FIELDS}
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
        # Real error signature from events.ndjson so the deterministic-failure
        # breaker keys on the actual error, not just the coarse failure_kind.
        # Appended LAST so stored 6-field attempts yield "" here and never match
        # new 7-tuples (breaker stays conservative on first deploy).
        "event_signature": _event_signature_field(context, plan_failure),
    }


def build_acceptance_predicate_signature(
    failure_context: Mapping[str, Any],
) -> dict[str, str]:
    """Return acceptance predicate fields extracted from *failure_context*.

    When the failure originated from an atomic completion boundary the context
    carries a structured ``acceptance_predicate_failure`` block (from
    :class:`~arnold_pipelines.megaplan.orchestration.completion_contract.BlockingPredicateFailure`)
    plus the transaction and snapshot identity.  This function extracts those
    fields into a stable dict keyed by :data:`ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS`.

    Returns a dict with every field set to ``\"\"`` when no acceptance context
    is present — the signature is still shaped correctly so the
    extended-tuple comparison works for both predicate and fixer-infra
    failures.
    """
    context = _as_dict(failure_context)
    predicate_failure = _as_dict(context.get("acceptance_predicate_failure"))
    predicate_details = _as_dict(predicate_failure.get("details"))
    evidence_refs = predicate_details.get("evidence_refs")
    if isinstance(evidence_refs, list):
        evidence_refs_text = ",".join(_as_text(item) for item in evidence_refs if _as_text(item))
    else:
        evidence_refs_text = _as_text(evidence_refs)
    return {
        "acceptance_predicate_kind": _as_text(predicate_failure.get("kind")),
        "acceptance_predicate_evidence_kind": _as_text(
            predicate_failure.get("evidence_kind")
        ),
        "acceptance_predicate_summary": _as_text(predicate_failure.get("summary")),
        "acceptance_transaction_id": _as_text(
            context.get("acceptance_transaction_id")
        ),
        "acceptance_snapshot_hash": _as_text(
            context.get("acceptance_snapshot_hash")
        ),
        "acceptance_evidence_refs": evidence_refs_text,
        "safe_recovery_action": _as_text(
            predicate_details.get("safe_recovery_action")
            or context.get("safe_recovery_action")
        ),
        "recovery_action": _as_text(
            predicate_details.get("recovery_action")
            or context.get("recovery_action")
        ),
    }


def build_extended_problem_signature(
    failure_context: Mapping[str, Any],
) -> dict[str, str]:
    """Return the full problem signature including acceptance predicate fields.

    Merges :func:`build_problem_signature` (fixer-infrastructure fields) with
    :func:`build_acceptance_predicate_signature` (acceptance predicate fields).
    The result carries every key from :data:`EXTENDED_PROBLEM_SIGNATURE_FIELDS`
    so recurrence identity distinguishes predicate failures from fixer-infra
    failures.
    """
    base = build_problem_signature(failure_context)
    acceptance = build_acceptance_predicate_signature(failure_context)
    return {**base, **acceptance}


def extended_signature_tuple(signature: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the ordered tuple of extended signature values."""
    return tuple(
        _as_text(signature.get(field)) for field in EXTENDED_PROBLEM_SIGNATURE_FIELDS
    )


def _event_signature_field(context: Mapping[str, Any], plan_failure: Mapping[str, Any]) -> str:
    phase_result_signature = _phase_result_signature_field(context, plan_failure)
    if phase_result_signature:
        return phase_result_signature
    events_path = _as_text(
        plan_failure.get("events_path")
        or plan_failure.get("plan_events_path")
        or context.get("plan_events_path")
    )
    if not events_path:
        return ""
    try:
        from arnold_pipelines.megaplan.observability.events import event_signature_summary
    except ImportError:
        return ""
    try:
        top = event_signature_summary(events_path=events_path, top_n=1)
    except Exception:
        return ""
    if not top:
        return ""
    first = top[0]
    kind = _as_text(first.get("kind"))
    reason = _as_text(first.get("reason"))
    return f"{kind}/{reason}" if kind else ""


def _phase_result_signature_field(
    context: Mapping[str, Any],
    plan_failure: Mapping[str, Any],
) -> str:
    state = _as_dict(context.get("plan_runtime_state"))
    phase_result = _as_dict(_as_dict(context.get("execute_attempt_context")).get("phase_result"))
    if not phase_result:
        plan_dir = _resolve_plan_dir(context, workspace=_as_path(context.get("workspace")))
        if plan_dir is not None:
            state_path = plan_dir / "state.json"
            if state_path.exists():
                disk_state = _read_json_file(state_path)
                if disk_state:
                    merged_state = dict(disk_state)
                    merged_state.update(state)
                    state = merged_state
            phase_result_path = plan_dir / "phase_result.json"
            try:
                loaded = json.loads(phase_result_path.read_text(encoding="utf-8"))
            except Exception:
                loaded = {}
            phase_result = _as_dict(loaded)
    if not state:
        state = _as_dict(context.get("plan_runtime_state"))
    if not phase_result:
        return ""
    exit_kind = _as_text(phase_result.get("exit_kind"))
    phase = _as_text(phase_result.get("phase")) or _as_text(plan_failure.get("phase"))
    if not exit_kind:
        return ""
    if is_superseded_recovered_phase_result(
        phase=phase,
        exit_kind=exit_kind,
        state=state,
    ):
        return ""
    blocked_tasks = [
        _as_text(_as_dict(item).get("task_id") or _as_dict(item).get("id"))
        for item in _as_list(phase_result.get("blocked_tasks"))
    ]
    blocked_tasks = [item for item in blocked_tasks if item]
    if blocked_tasks:
        detail = blocked_tasks[0]
    else:
        detail = _phase_result_deviation_token(_as_list(phase_result.get("deviations")))
    parts = ["phase_result", phase, exit_kind, detail]
    return "/".join(part for part in parts if part)


def _phase_result_deviation_token(deviations: list[Any]) -> str:
    for item in deviations:
        deviation = _as_dict(item)
        kind = _as_text(deviation.get("kind"))
        message = _as_text(deviation.get("message"))
        code_match = re.search(r"\bAWF\d{3}(?:_[A-Z0-9_]+)?\b", message)
        if code_match:
            return f"{kind}:{code_match.group(0)}" if kind else code_match.group(0)
        if kind:
            return kind
    return ""


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
    plan_activity = _probe_plan_activity(context, workspace=workspace_path)
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
        "plan_activity": plan_activity,
        "execute_empty_batch": _empty_execute_batch_summary(context),
        "canonical_cursor": {
            "plan": _plan_identity(context),
            "completed_count": _as_int(chain_state.get("completed_count")),
            "current_milestone_index": _as_int(chain_state.get("current_milestone_index")),
            "current_state": _as_text(
                plan_runtime.get("current_state")
                or plan_failure.get("current_state")
                or chain_state.get("last_state")
                or chain_state.get("current_state")
            ),
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
    prev_cursor = _as_dict(prev.get("canonical_cursor")) or prev
    curr_cursor = _as_dict(curr.get("canonical_cursor")) or curr
    prev_plan = _as_text(prev_cursor.get("plan") or prev.get("milestone_or_plan"))
    curr_plan = _as_text(curr_cursor.get("plan") or curr.get("milestone_or_plan"))
    # Recurrence belongs to one canonical plan occurrence.  Activity telemetry
    # and external delivery state (events, Git, PR, CI) are diagnostic only and
    # cannot reset its epoch.  A plan identity change also cannot retroactively
    # prove that the prior occurrence advanced.
    if not prev_plan or not curr_plan or prev_plan != curr_plan:
        return False
    prev_completed = _as_int(prev_cursor.get("completed_count"))
    curr_completed = _as_int(curr_cursor.get("completed_count"))
    if prev_completed is not None and curr_completed is not None and curr_completed > prev_completed:
        return True
    prev_index = _as_int(prev_cursor.get("current_milestone_index"))
    curr_index = _as_int(curr_cursor.get("current_milestone_index"))
    if prev_index is not None and curr_index is not None and curr_index > prev_index:
        return True
    if _as_text(prev_cursor.get("current_state")).lower() not in {"done", "complete", "completed"}:
        if _as_text(curr_cursor.get("current_state")).lower() in {"done", "complete", "completed"}:
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
        last_advancement_at = dispatched_at
    else:
        last_advancement_at = _as_text(previous.get("last_advancement_at"))
        if not last_advancement_at and bool(previous.get("advancement_since_last_dispatch")):
            # Backward compatibility for pre-epoch progress sidecars that
            # recorded advancement but did not yet persist the explicit epoch.
            last_advancement_at = _as_text(previous.get("updated_at"))
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
        "last_advancement_at": last_advancement_at,
        "window_seconds": int(window_seconds),
        "min_dispatches": int(min_dispatches),
        "layer2_recurrence": no_advance_count >= int(min_dispatches),
    }


def _attempt_is_after_epoch(
    attempt: Mapping[str, Any],
    epoch: datetime | None,
) -> bool:
    if epoch is None:
        return True
    when = _parse_when(attempt.get("dispatched_at") or attempt.get("timestamp"))
    if when is None:
        return True
    return when > epoch


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
    snapshot = _as_dict(session_snapshot)
    advancement_epoch = _parse_when(snapshot.get("last_advancement_at"))
    prior_attempts = [
        attempt
        for attempt in (attempts or [])
        if isinstance(attempt, Mapping)
        and _attempt_is_after_epoch(attempt, advancement_epoch)
    ]
    matching_attempt_ids: list[int] = []
    for attempt in prior_attempts:
        prior_signature = _as_dict(attempt.get("problem_signature"))
        if signature_tuple(prior_signature) != current_key:
            continue
        attempt_id = _as_int(attempt.get("attempt_id"))
        if attempt_id is not None:
            matching_attempt_ids.append(attempt_id)
    no_advance_count = _as_int(snapshot.get("no_advance_count")) or 0
    min_dispatches = _as_int(snapshot.get("min_dispatches")) or 0
    layer1_detected = bool(matching_attempt_ids)
    layer2_detected = no_advance_count >= min_dispatches > 0
    attempt_number = max(len(matching_attempt_ids) + 1, no_advance_count or 1)

    # Layer 3: deterministic-failure breaker. Trips when the immediately-prior
    # attempt recorded the SAME signature as the current one (iteration N ==
    # iteration N-1). A repeat means another mechanical re-drive with the same
    # inputs cannot help — the loop should stop early and escalate. Only fires
    # on a non-empty signature so the breaker never trips on bootstrap/garbage.
    prior_by_id = sorted(
        (
            attempt for attempt in prior_attempts if _as_int(attempt.get("attempt_id")) is not None
        ),
        key=lambda a: _as_int(a["attempt_id"]),  # type: ignore[index]
    )
    same_signature_detected = False
    if prior_by_id and any(current_key):
        last_signature = _as_dict(prior_by_id[-1].get("problem_signature"))
        if last_signature and signature_tuple(last_signature) == current_key:
            same_signature_detected = True

    empty_batch_streak: list[dict[str, Any]] = []
    current_empty_batch = _normalize_empty_batch_summary(
        _as_dict(_as_dict(snapshot.get("current")).get("execute_empty_batch"))
    )
    if current_empty_batch:
        empty_batch_streak.append(current_empty_batch)
        seen_task_sets = {current_empty_batch["task_ids"]}
        for attempt in reversed(prior_by_id):
            prior_empty_batch = _empty_batch_summary_for_attempt(attempt)
            if not prior_empty_batch:
                break
            if prior_empty_batch["plan"] != current_empty_batch["plan"]:
                break
            task_ids = prior_empty_batch["task_ids"]
            if task_ids in seen_task_sets:
                break
            seen_task_sets.add(task_ids)
            empty_batch_streak.append(prior_empty_batch)
    empty_batch_threshold = max(_as_int(snapshot.get("min_dispatches")) or 3, 2)
    empty_batch_detected = len(empty_batch_streak) >= empty_batch_threshold
    layer3_detected = same_signature_detected or empty_batch_detected

    return {
        "detected": layer1_detected or layer2_detected,
        "deterministic_failure_breaker": layer3_detected,
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
        "layer3": {
            "detected": layer3_detected,
            "consecutive_same_signature": same_signature_detected,
            "empty_batch_streak": {
                "detected": empty_batch_detected,
                "count": len(empty_batch_streak),
                "min_dispatches": empty_batch_threshold,
                "task_id_batches": [
                    list(item["task_ids"]) for item in empty_batch_streak
                ],
            },
            "breaker_signature": normalized_signature if layer3_detected else {},
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# M7 custody helpers — RepairOccurrenceKey construction from failure context
# ═══════════════════════════════════════════════════════════════════════════

#: Known T7 outbox surface identifiers (Custody-04 outbox module).
_T7_OUTBOX_SURFACE_PREFIXES: tuple[str, ...] = (
    "outbox:",
    "custody-outbox:",
    "custody-04:",
)

#: Known T12 admission surface identifiers (future Custody admission).
_T12_ADMISSION_SURFACE_PREFIXES: tuple[str, ...] = (
    "admission:",
    "custody-admission:",
    "repair-admission:",
)


def is_t7_outbox_reference(ref: str) -> bool:
    """Return True if *ref* identifies a T7 outbox record.

    T7 outbox references are owned by the Custody outbox module and carry
    ``outbox:``, ``custody-outbox:``, or ``custody-04:`` prefixes.

    This is a read-only classifier — it does not mutate any state.
    """
    if not isinstance(ref, str) or not ref.strip():
        return False
    cleaned = ref.strip()
    return any(cleaned.startswith(prefix) for prefix in _T7_OUTBOX_SURFACE_PREFIXES)


def is_t12_admission_reference(ref: str) -> bool:
    """Return True if *ref* identifies a T12 admission surface record.

    T12 admission references are owned by the repair admission surface and
    carry ``admission:``, ``custody-admission:``, or ``repair-admission:``
    prefixes.

    This is a read-only classifier — it does not mutate any state.
    """
    if not isinstance(ref, str) or not ref.strip():
        return False
    cleaned = ref.strip()
    return any(cleaned.startswith(prefix) for prefix in _T12_ADMISSION_SURFACE_PREFIXES)


def validate_t7_t12_cross_binding(
    *,
    occurrence_key: RepairOccurrenceKey | None = None,
    wbc_attempt_reference: str = "",
    source_surface: str = "",
) -> list[str]:
    """Return a list of cross-binding violation descriptions.

    Rejects any attempt to bind T7 outbox references to T12 admission
    surface identifiers and vice versa.  Stale T7→T12 binding would allow
    an outbox record to be mistaken for an admission decision, which
    violates the single-owner boundary.

    Returns an empty list when no violation is detected.
    """
    violations: list[str] = []
    if occurrence_key is None:
        return violations

    # Classify the source surface if not explicitly provided.
    effective_source = source_surface.strip() if source_surface else ""
    if not effective_source:
        if is_t7_outbox_reference(occurrence_key.wbc_attempt_reference):
            effective_source = "outbox"
        elif is_t12_admission_reference(occurrence_key.wbc_attempt_reference):
            effective_source = "admission"

    # Check wbc_attempt_reference for cross-binding.
    wbc_ref = (wbc_attempt_reference or occurrence_key.wbc_attempt_reference).strip()
    if wbc_ref:
        if effective_source == "outbox" and is_t12_admission_reference(wbc_ref):
            violations.append(
                f"T7 outbox source cannot bind T12 admission reference: {wbc_ref!r}"
            )
        elif effective_source == "admission" and is_t7_outbox_reference(wbc_ref):
            violations.append(
                f"T12 admission source cannot bind T7 outbox reference: {wbc_ref!r}"
            )

    # Check the occurrence digest for cross-surface contamination.
    digest = occurrence_key.occurrence_digest
    if digest:
        if effective_source == "outbox" and "admission:" in digest:
            violations.append(
                f"occurrence_digest carries T12 admission marker: {digest!r}"
            )
        elif effective_source == "admission" and "outbox:" in digest:
            violations.append(
                f"occurrence_digest carries T7 outbox marker: {digest!r}"
            )

    return violations


def build_custody_target_key_from_failure_context(
    failure_context: Mapping[str, Any],
    *,
    chain_identity: str = "",
) -> CustodyTargetKey | None:
    """Construct a :class:`CustodyTargetKey` from a repair failure context.

    Extracts F01 fields from the same failure_context dict already consumed
    by :func:`build_problem_signature`.  Legacy problem-signature
    normalization is preserved; this helper adds the M7 CustodyTargetKey
    shape alongside the existing signature path.

    Returns ``None`` when any required F01 field cannot be resolved.
    """
    context = _as_dict(failure_context)
    chain_state = _as_dict(context.get("chain_state_summary"))
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    plan_runtime = _as_dict(context.get("plan_runtime_state"))
    execute_attempt = _as_dict(context.get("execute_attempt_context"))
    signature = build_problem_signature(context)

    environment = _first_non_empty(
        _as_text(chain_state.get("environment")),
        _as_text(signature.get("environment")),
    )
    session = _first_non_empty(
        _as_text(chain_state.get("session")),
        _as_text(signature.get("session")),
    )
    chain = _first_non_empty(
        _as_text(chain_state.get("chain_name")),
        _as_text(signature.get("chain")),
    )
    plan_revision = _first_non_empty(
        _as_text(chain_state.get("plan_revision")),
        _as_text(signature.get("plan_revision")),
    )
    phase = _first_non_empty(
        _as_text(plan_failure.get("phase")),
        _as_text(signature.get("phase_or_step")),
    )
    task = _first_non_empty(
        _as_text(plan_failure.get("blocked_task_id")),
        _as_text(plan_failure.get("task_id")),
        _as_text(signature.get("blocked_task_id")),
    )
    attempt = _first_non_empty(
        _as_text(chain_state.get("attempt")),
        _as_text(signature.get("attempt")),
    )
    normalized_failure_kind = _first_non_empty(
        _as_text(plan_failure.get("kind")),
        _as_text(signature.get("failure_kind")),
    )
    blocker_or_phase_result_hash = _first_non_empty(
        _as_text(chain_state.get("fingerprint")),
        _as_text(signature.get("target_fingerprint")),
    )
    fence = _first_non_empty(
        _as_text(chain_state.get("fence")),
        _as_text(signature.get("fence")),
    )

    return build_custody_target_key(
        environment=environment,
        session=session,
        chain=chain,
        plan_revision=plan_revision,
        phase=phase,
        task=task,
        attempt=attempt,
        normalized_failure_kind=normalized_failure_kind,
        blocker_or_phase_result_hash=blocker_or_phase_result_hash,
        fence=fence,
        chain_identity=chain_identity,
    )


def build_repair_occurrence_key_from_failure_context(
    failure_context: Mapping[str, Any],
    *,
    chain_identity: str = "",
    run_id: str = "",
    run_revision: str = "",
    coordinator_attempt_id: str = "",
    fence_token: int = 0,
    wbc_attempt_reference: str = "",
    source_surface: str = "",
) -> RepairOccurrenceKey | None:
    """Construct a full M7 :class:`RepairOccurrenceKey` from failure context.

    Builds a :class:`CustodyTargetKey` from the failure context, then wraps
    it with the current coordinator fence token, run identity, WBC attempt
    reference, and a deterministic occurrence digest over the F01 fields +
    fence token + chain identity.

    The returned key structurally includes the fence token and occurrence
    digest required for M7 identity while preserving the read-only adapter
    pattern used by existing problem-signature normalization.

    Returns ``None`` when the target key cannot be constructed or when
    T7/T12 cross-binding is detected.

    Keyword Args:
        failure_context: The full failure context dict (same as build_problem_signature).
        chain_identity: Optional chain identity string.
        run_id: Run Authority run identifier.
        run_revision: Run Authority run revision.
        coordinator_attempt_id: Coordinator attempt identifier.
        fence_token: Current coordinator fence token (non-negative int).
        wbc_attempt_reference: WBC attempt reference string.
        source_surface: ``'outbox'`` for T7, ``'admission'`` for T12, or ``''``.
    """
    target = build_custody_target_key_from_failure_context(
        failure_context,
        chain_identity=chain_identity,
    )
    if target is None:
        return None

    context = _as_dict(failure_context)
    chain_state = _as_dict(context.get("chain_state_summary"))

    resolved_run_id = _first_non_empty(
        run_id,
        _as_text(chain_state.get("run_id")),
    )
    resolved_run_revision = _first_non_empty(
        run_revision,
        _as_text(chain_state.get("run_revision")),
    )
    resolved_attempt = _first_non_empty(
        coordinator_attempt_id,
        _as_text(chain_state.get("coordinator_attempt_id")),
    )
    resolved_fence_token = (
        fence_token
        if fence_token > 0
        else _as_int(chain_state.get("fence_token"))
        or 0
    )
    resolved_wbc_ref = _first_non_empty(
        wbc_attempt_reference,
        _as_text(chain_state.get("wbc_attempt_reference")),
    )

    occurrence_key = build_repair_occurrence_key(
        target=target,
        run_id=resolved_run_id,
        run_revision=resolved_run_revision,
        coordinator_attempt_id=resolved_attempt,
        fence_token=resolved_fence_token,
        wbc_attempt_reference=resolved_wbc_ref,
    )
    if occurrence_key is None:
        return None

    # T7/T12 cross-binding rejection.
    violations = validate_t7_t12_cross_binding(
        occurrence_key=occurrence_key,
        wbc_attempt_reference=resolved_wbc_ref,
        source_surface=source_surface,
    )
    if violations:
        return None

    return occurrence_key


def _first_non_empty(*values: str) -> str:
    """Return the first non-empty string value, or ''."""
    for v in values:
        if v and v.strip():
            return v.strip()
    return ""
