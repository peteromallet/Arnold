"""Plan state management — load, save, history, sessions, failure recording."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator

import fcntl

from megaplan.types import (
    ActiveStep,
    CliError,
    HistoryEntry,
    PlanState,
    PlanVersionRecord,
    TERMINAL_STATES,
)
from .phase_runtime import DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS, phase_stale_seconds

from .io import (
    atomic_write_json,
    atomic_write_text,
    current_iteration_raw_artifact,
    find_plan_dir,
    now_utc,
    plan_search_roots,
    plans_root,
    read_json,
)

if TYPE_CHECKING:
    from megaplan.workers import WorkerResult


DEFAULT_ACTIVE_STEP_STALE_SECONDS = DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS


# ---------------------------------------------------------------------------
# Plan resolution
# ---------------------------------------------------------------------------

def active_plan_dirs(root: Path) -> list[Path]:
    by_name: dict[str, Path] = {}
    for candidate_root in plan_search_roots(root):
        if not candidate_root.exists():
            continue
        for child in candidate_root.iterdir():
            if child.is_dir() and (child / "state.json").exists():
                by_name.setdefault(child.name, child)
    return [by_name[name] for name in sorted(by_name)]


def resolve_plan_dir(root: Path, requested_name: str | None) -> Path:
    plan_dirs = active_plan_dirs(root)
    if requested_name:
        plan_dir = find_plan_dir(root, requested_name)
        if plan_dir is not None:
            return plan_dir
        raise CliError("missing_plan", f"Plan '{requested_name}' does not exist")
    if not plan_dirs:
        raise CliError("missing_plan", "No plans found. Run init first.")
    active = []
    for plan_dir in plan_dirs:
        state = read_json(plan_dir / "state.json")
        if state.get("current_state") not in TERMINAL_STATES:
            active.append(plan_dir)
    if len(active) == 1:
        return active[0]
    if len(plan_dirs) == 1:
        return plan_dirs[0]
    names = [path.name for path in active or plan_dirs]
    raise CliError(
        "ambiguous_plan",
        "Multiple plans exist; pass --plan explicitly",
        extra={"plans": names},
    )


def load_plan(root: Path, requested_name: str | None) -> tuple[Path, PlanState]:
    plan_dir = resolve_plan_dir(root, requested_name)
    return load_plan_from_dir(plan_dir)


def load_plan_from_dir(plan_dir: Path) -> tuple[Path, PlanState]:
    state = read_json(plan_dir / "state.json")
    migrated = False
    if state.get("current_state") == "clarified":
        state["current_state"] = "initialized"
        migrated = True
    elif state.get("current_state") == "evaluated":
        state["current_state"] = "critiqued"
        state["last_gate"] = {}
        migrated = True
    if "last_evaluation" in state:
        del state["last_evaluation"]
        migrated = True
    if "last_gate" not in state:
        state["last_gate"] = {}
        migrated = True
    if migrated:
        atomic_write_json(plan_dir / "state.json", state)
    return plan_dir, state


def _parse_utc_timestamp(timestamp: str | None) -> datetime | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def active_step_is_stale(
    active_step: ActiveStep | None,
    *,
    configured_timeout_seconds: int = DEFAULT_ACTIVE_STEP_STALE_SECONDS,
) -> bool:
    if not isinstance(active_step, dict):
        return False
    step = active_step.get("step")
    if not isinstance(step, str) or not step:
        return False
    started_at = _parse_utc_timestamp(active_step.get("started_at"))
    if started_at is None:
        return False
    age_seconds = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
    return age_seconds >= phase_stale_seconds(
        step,
        configured_timeout_seconds=configured_timeout_seconds,
    )


def plan_lock_path(plan_dir: Path) -> Path:
    return plan_dir / ".plan.lock"


def plan_lock_is_held(plan_dir: Path) -> bool:
    lock_path = plan_lock_path(plan_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    return False


def _build_plan_locked_details(plan_dir: Path, *, step: str) -> dict[str, object]:
    state_path = plan_dir / "state.json"
    details: dict[str, object] = {"plan": plan_dir.name, "step": step}
    if not state_path.exists():
        return details
    try:
        state = read_json(state_path)
    except Exception:
        return details
    if not isinstance(state, dict):
        return details
    active_step = state.get("active_step")
    if isinstance(active_step, dict):
        details["active_step"] = dict(active_step)
    return details


@contextmanager
def plan_lock(plan_dir: Path, *, step: str) -> Iterator[None]:
    lock_path = plan_lock_path(plan_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            details = _build_plan_locked_details(plan_dir, step=step)
            active_step = details.get("active_step")
            if isinstance(active_step, dict):
                message = (
                    f"Cannot run '{step}' because plan '{plan_dir.name}' already has an active "
                    f"'{active_step.get('step')}' step via {active_step.get('agent')}."
                )
            else:
                message = f"Cannot run '{step}' because plan '{plan_dir.name}' is locked by another process."
            raise CliError("plan_locked", message, extra=details) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def load_plan_locked(root: Path, requested_name: str | None, *, step: str) -> Iterator[tuple[Path, PlanState]]:
    plan_dir = resolve_plan_dir(root, requested_name)
    with plan_lock(plan_dir, step=step):
        yield load_plan_from_dir(plan_dir)


def save_state(plan_dir: Path, state: PlanState) -> None:
    atomic_write_json(plan_dir / "state.json", state)


# ---------------------------------------------------------------------------
# Merge-on-save for append-only meta fields
# ---------------------------------------------------------------------------
#
# Workflow phases (revise/critique/gate/plan/finalize/execute/review) hold a
# non-blocking ``plan_lock`` for the entire 5–15 minute duration of a worker
# run. Override commands (``override add-note``, ``override abort``,
# ``override replan``, ``override set-robustness``, ``override force-proceed``)
# intentionally bypass the lock so the user is not blocked for many minutes
# while a phase runs.
#
# This creates a window where an override can write to ``state.json`` while
# a phase has already loaded its in-memory ``state`` snapshot. When the phase
# eventually calls ``save_state``, it would overwrite the override's append
# with stale data — silently losing the operator's note or override record.
#
# The two append-only meta fields are ``meta.notes`` and ``meta.overrides``.
# Everything else in state.json is only mutated by the lock-holder. So the
# fix is targeted: when saving from the lock-holding side, re-read the
# on-disk ``meta.notes`` and ``meta.overrides``, take the union with the
# in-memory copies (de-duped by content), and only then write.

_DEFAULT_MERGE_FIELDS: tuple[str, ...] = ("notes", "overrides")


def _note_merge_key(entry: Any) -> tuple[str, str]:
    """Stable de-dup key for a ``meta.notes`` entry.

    Notes are ``{"timestamp": str, "note": str}``. The hash digest of the note
    body collapses literal duplicates while still distinguishing notes that
    happen to share a timestamp.
    """
    if not isinstance(entry, dict):
        encoded = json.dumps(entry, sort_keys=True, default=str).encode("utf-8")
        return ("", hashlib.sha256(encoded).hexdigest()[:16])
    timestamp = entry.get("timestamp", "")
    note = entry.get("note", "")
    if not isinstance(timestamp, str):
        timestamp = str(timestamp)
    if not isinstance(note, str):
        note = json.dumps(note, sort_keys=True, default=str)
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest()[:16]
    return (timestamp, digest)


def _override_merge_key(entry: Any) -> tuple[str, str, str]:
    """Stable de-dup key for a ``meta.overrides`` entry.

    Overrides are ``{"timestamp": str, "action": str, ...}`` with optional
    ``note`` / ``reason`` payload. We dedupe by ``(timestamp, action,
    hash(note + reason))`` so two distinct override invocations sharing only
    a timestamp still survive.
    """
    if not isinstance(entry, dict):
        encoded = json.dumps(entry, sort_keys=True, default=str).encode("utf-8")
        return ("", "", hashlib.sha256(encoded).hexdigest()[:16])
    timestamp = entry.get("timestamp", "")
    action = entry.get("action", "")
    note = entry.get("note", "")
    reason = entry.get("reason", "")
    if not isinstance(timestamp, str):
        timestamp = str(timestamp)
    if not isinstance(action, str):
        action = str(action)
    if not isinstance(note, str):
        note = json.dumps(note, sort_keys=True, default=str)
    if not isinstance(reason, str):
        reason = json.dumps(reason, sort_keys=True, default=str)
    digest = hashlib.sha256((note + "|" + reason).encode("utf-8")).hexdigest()[:16]
    return (timestamp, action, digest)


_FIELD_KEY_FUNCS: dict[str, Any] = {
    "notes": _note_merge_key,
    "overrides": _override_merge_key,
}


def _timestamp_sort_key(entry: Any) -> str:
    if isinstance(entry, dict):
        timestamp = entry.get("timestamp", "")
        if isinstance(timestamp, str):
            return timestamp
        return str(timestamp)
    return ""


def _merge_meta_lists(
    on_disk: Any,
    in_memory: Any,
    *,
    key_func: Any,
) -> list[Any]:
    """Union two append-only lists, de-duped by ``key_func`` and sorted by
    timestamp ascending. Insertion order of unique entries is otherwise
    preserved when timestamps collide."""

    def _coerce(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []

    seen: set[Any] = set()
    merged: list[Any] = []
    # On-disk first so concurrent writes by a short-hold writer (e.g. an
    # override invocation) take precedence as the canonical record. Then
    # add anything new from the in-memory copy.
    for entry in _coerce(on_disk) + _coerce(in_memory):
        key = key_func(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    merged.sort(key=_timestamp_sort_key)
    return merged


def save_state_merge_meta(
    plan_dir: Path,
    state: PlanState,
    *,
    merge_fields: Iterable[str] = _DEFAULT_MERGE_FIELDS,
) -> None:
    """Save ``state`` to ``state.json``, merging append-only meta fields with
    whatever is currently on disk.

    Use this from any code path where another process (typically an
    ``override`` command) might have appended to ``meta.notes`` or
    ``meta.overrides`` between the time ``state`` was loaded and now.

    For fields not in ``merge_fields``, the in-memory value wins as usual.
    """
    state_path = plan_dir / "state.json"
    on_disk_meta: dict[str, Any] = {}
    if state_path.exists():
        try:
            existing = read_json(state_path)
        except Exception:
            existing = None
        if isinstance(existing, dict):
            disk_meta = existing.get("meta")
            if isinstance(disk_meta, dict):
                on_disk_meta = disk_meta

    state.setdefault("meta", {})
    for field in merge_fields:
        key_func = _FIELD_KEY_FUNCS.get(field)
        if key_func is None:
            # Unknown merge field: skip rather than guess at semantics.
            continue
        in_memory_value = state["meta"].get(field, [])
        on_disk_value = on_disk_meta.get(field, [])
        merged = _merge_meta_lists(
            on_disk_value,
            in_memory_value,
            key_func=key_func,
        )
        state["meta"][field] = merged

    atomic_write_json(state_path, state)


def apply_session_update(
    state: PlanState,
    step: str,
    agent: str,
    session_id: str | None,
    *,
    mode: str,
    refreshed: bool,
) -> None:
    from megaplan.workers import update_session_state

    result = update_session_state(
        step,
        agent,
        session_id,
        mode=mode,
        refreshed=refreshed,
        existing_sessions=state["sessions"],
    )
    if result is not None:
        key, entry = result
        state["sessions"][key] = entry


def set_active_step(
    state: PlanState,
    *,
    step: str,
    agent: str,
    mode: str,
    model: str | None = None,
    run_id: str | None = None,
) -> str:
    resolved_run_id = run_id or str(uuid.uuid4())
    started_at = now_utc()
    attempt = 1 + sum(
        1
        for entry in state.get("history", [])
        if isinstance(entry, dict) and entry.get("step") == step
    )
    active_step: ActiveStep = {
        "step": step,
        "agent": agent,
        "mode": mode,
        "run_id": resolved_run_id,
        "started_at": started_at,
        "attempt": attempt,
        "last_activity_at": started_at,
        "last_activity_kind": "started",
    }
    if model:
        active_step["model"] = model
    if mode == "persistent":
        from megaplan.workers import session_key_for

        session = state.get("sessions", {}).get(session_key_for(step, agent, model), {})
        session_id = session.get("id")
        if isinstance(session_id, str) and session_id:
            active_step["session_id"] = session_id
    state["active_step"] = active_step
    from megaplan.phase_result import generate_invocation_id

    state.setdefault("meta", {})["current_invocation_id"] = generate_invocation_id()
    return resolved_run_id


def touch_active_step(
    plan_dir: Path,
    *,
    run_id: str | None,
    kind: str,
    detail: str | None = None,
) -> None:
    """Persist lightweight liveness for the active step.

    This intentionally reads the current on-disk state and updates only the
    matching ``active_step``. That preserves concurrent metadata appends and
    avoids the long-running worker writing an old in-memory snapshot over
    operator changes.
    """
    if not run_id:
        return
    state_path = plan_dir / "state.json"
    try:
        state = read_json(state_path)
    except Exception:
        return
    if not isinstance(state, dict):
        return
    active_step = state.get("active_step")
    if not isinstance(active_step, dict) or active_step.get("run_id") != run_id:
        return
    active_step["last_activity_at"] = now_utc()
    active_step["last_activity_kind"] = kind
    if detail:
        active_step["last_activity_detail"] = detail[-500:]
    state["active_step"] = active_step
    atomic_write_json(state_path, state)


def clear_active_step(state: PlanState, *, run_id: str | None = None) -> None:
    active_step = state.get("active_step")
    if run_id is not None and isinstance(active_step, dict) and active_step.get("run_id") != run_id:
        return
    state.pop("active_step", None)


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def append_history(state: PlanState, entry: HistoryEntry) -> None:
    state["history"].append(entry)
    state["meta"].setdefault("total_cost_usd", 0.0)
    state["meta"]["total_cost_usd"] = round(
        float(state["meta"]["total_cost_usd"]) + float(entry.get("cost_usd", 0.0)),
        6,
    )


def make_history_entry(
    step: str,
    *,
    duration_ms: int,
    cost_usd: float,
    result: str,
    worker: WorkerResult | None = None,
    agent: str | None = None,
    mode: str | None = None,
    output_file: str | None = None,
    artifact_hash: str | None = None,
    finalize_hash: str | None = None,
    raw_output_file: str | None = None,
    message: str | None = None,
    flags_count: int | None = None,
    flags_addressed: list[Any] | None = None,
    recommendation: str | None = None,
    approval_mode: str | None = None,
    environment: dict[str, bool] | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> HistoryEntry:
    entry: HistoryEntry = {
        "step": step,
        "timestamp": now_utc(),
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "result": result,
    }
    if total_tokens > 0:
        entry["prompt_tokens"] = prompt_tokens
        entry["completion_tokens"] = completion_tokens
        entry["total_tokens"] = total_tokens
    if worker is not None and agent is not None and mode is not None:
        entry["session_mode"] = mode
        entry["session_id"] = worker.session_id
        entry["agent"] = agent
    if output_file is not None:
        entry["output_file"] = output_file
    if artifact_hash is not None:
        entry["artifact_hash"] = artifact_hash
    if finalize_hash is not None:
        entry["finalize_hash"] = finalize_hash
    if raw_output_file is not None:
        entry["raw_output_file"] = raw_output_file
    if message is not None:
        entry["message"] = message
    if flags_count is not None:
        entry["flags_count"] = flags_count
    if flags_addressed is not None:
        entry["flags_addressed"] = flags_addressed
    if recommendation is not None:
        entry["recommendation"] = recommendation
    if approval_mode is not None:
        entry["approval_mode"] = approval_mode
    if environment is not None:
        entry["environment"] = environment
    return entry


def store_raw_worker_output(plan_dir: Path, step: str, iteration: int, content: str) -> str:
    filename = current_iteration_raw_artifact(plan_dir, step, iteration).name
    atomic_write_text(plan_dir / filename, content)
    return filename


def record_step_failure(
    plan_dir: Path,
    state: PlanState,
    *,
    step: str,
    iteration: int,
    error: CliError,
    duration_ms: int = 0,
) -> None:
    raw_output = str(error.extra.get("raw_output") or error.message)
    raw_name = store_raw_worker_output(plan_dir, step, iteration, raw_output)
    append_history(
        state,
        make_history_entry(
            step,
            duration_ms=duration_ms,
            cost_usd=0.0,
            result="error",
            raw_output_file=raw_name,
            message=error.message,
        ),
    )
    clear_active_step(state)
    # Phases hold the lock for many minutes; merge meta to avoid clobbering
    # concurrent ``override add-note`` / ``override`` appends.
    save_state_merge_meta(plan_dir, state)


# ---------------------------------------------------------------------------
# Plan version helpers
# ---------------------------------------------------------------------------

def latest_plan_record(state: PlanState) -> PlanVersionRecord:
    plan_versions = state["plan_versions"]
    if not plan_versions:
        raise CliError("missing_plan_version", "No plan version exists yet")
    return plan_versions[-1]


def latest_plan_path(plan_dir: Path, state: PlanState) -> Path:
    return plan_dir / latest_plan_record(state)["file"]


def latest_plan_meta_path(plan_dir: Path, state: PlanState) -> Path:
    record = latest_plan_record(state)
    meta_name = record["file"].replace(".md", ".meta.json")
    return plan_dir / meta_name
