"""Plan state management — load, save, history, sessions, failure recording."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, Literal

import fcntl

from megaplan.types import (
    ActivePhase,
    CANONICAL_PLAN_STATES,
    CliError,
    HistoryEntry,
    PlanState,
    PlanVersionRecord,
    STATE_CRITIQUED,
    STATE_INITIALIZED,
    TERMINAL_STATES,
    validate_plan_current_state,
)
from .phase_runtime import DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS, phase_stale_seconds

from .io import (
    atomic_write_json,
    atomic_write_text,
    current_iteration_raw_artifact,
    find_plan_dir,
    now_utc,
    plan_search_roots,
    read_json,
)

if TYPE_CHECKING:
    from megaplan.workers import WorkerResult


DEFAULT_ACTIVE_STEP_STALE_SECONDS = DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS


def _heartbeat_persist_interval_seconds() -> float:
    """How often an ``active-step-heartbeat`` write may re-serialize the full
    ``state.json`` content (refreshing ``active_step.last_activity_at``).

    The phase-idle/stall monitor (``megaplan auto``) reads the *content* field
    ``active_step.last_activity_at`` out of ``state.json`` — not the file mtime
    — to decide liveness, so the persisted timestamp must stay fresher than the
    smallest realistic idle threshold (chains tune this as low as ~40s). We
    coalesce the costly full-state serialize to at most once per this interval
    (default 30s, comfortably under 40s) while every beat still bumps the file
    mtime cheaply via ``os.utime`` for any mtime-based watchdog. This collapses
    a ~24KB ``json.dumps`` from roughly once-per-2s to once-per-interval on a
    long stream without weakening either liveness signal.
    """
    raw = os.environ.get("MEGAPLAN_HEARTBEAT_PERSIST_INTERVAL_S")
    if raw:
        try:
            value = float(raw)
            if value >= 0:
                return value
        except ValueError:
            pass
    return 30.0


# Last wall-clock time we performed a *full* heartbeat content write, keyed by
# resolved state.json path. In-process per worker; the worker is the only
# heartbeat writer for its own run (run_id-guarded), so no cross-process lock
# is needed and a stale entry only ever costs one extra write.
_last_heartbeat_persist_at: dict[str, float] = {}

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


def _validate_persisted_phase_models(plan_dir: Path, state: Any) -> None:
    """Surface a corrupt persisted ``config.phase_model`` pin loudly at load.

    Specfix: a plan once persisted a malformed routing spec
    (``critique=codex:claude:sonnet``) that ``parse_agent_spec`` accepted
    silently and that rode through three sprints. ``parse_agent_spec`` now
    rejects such specs at the chokepoint; this load-time check ensures an
    *already-corrupt* on-disk plan fails loudly on the next load/resume
    instead of mis-dispatching. No migration is attempted — the operator
    fixes the pin via ``megaplan override set-model`` / ``set-vendor``.
    """
    from megaplan.types import parse_agent_spec

    if not isinstance(state, dict):
        return
    phase_models = state.get("config", {}).get("phase_model") or []
    if not isinstance(phase_models, list):
        return
    for entry in phase_models:
        if not isinstance(entry, str) or "=" not in entry:
            continue
        phase, spec = entry.split("=", 1)
        try:
            parse_agent_spec(spec)
        except CliError as exc:
            raise CliError(
                "corrupt_phase_model",
                f"Plan '{plan_dir.name}' has a malformed persisted routing pin "
                f"for phase '{phase}': {spec!r}. {exc.message} "
                f"Fix it with `megaplan override set-model --phase {phase} "
                f"--model <model>` (or `set-vendor`) before resuming.",
            ) from exc


def load_plan_from_dir(plan_dir: Path) -> tuple[Path, PlanState]:
    state = read_json(plan_dir / "state.json")
    if isinstance(state, dict) and (
        state.get("current_state") in {"clarified", "evaluated"}
        or "last_evaluation" in state
        or "last_gate" not in state
    ):
        state = write_plan_state(plan_dir, mode="legacy-migration")
    _validate_persisted_phase_models(plan_dir, state)
    return plan_dir, state


def _parse_utc_timestamp(timestamp: str | None) -> datetime | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def active_phase_name(active_step: dict[str, Any] | None) -> str | None:
    if not isinstance(active_step, dict):
        return None
    phase = active_step.get("phase") or active_step.get("step")
    return phase if isinstance(phase, str) and phase else None


def active_step_is_stale(
    active_step: ActivePhase | None,
    *,
    configured_timeout_seconds: int = DEFAULT_ACTIVE_STEP_STALE_SECONDS,
) -> bool:
    if not isinstance(active_step, dict):
        return False
    step = active_phase_name(active_step)
    if not step:
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
                    f"'{active_phase_name(active_step)}' step via {active_step.get('agent')}."
                )
            else:
                message = f"Cannot run '{step}' because plan '{plan_dir.name}' is locked by another process."
            raise CliError("plan_locked", message, extra=details) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def load_plan_locked(
    root: Path, requested_name: str | None, *, step: str
) -> Iterator[tuple[Path, PlanState]]:
    plan_dir = resolve_plan_dir(root, requested_name)
    with plan_lock(plan_dir, step=step):
        yield load_plan_from_dir(plan_dir)


def driver_lock_path(plan_dir: Path) -> Path:
    """Path of the per-plan ``auto`` driver-lifetime lockfile.

    Distinct from ``plan_lock_path`` (``.plan.lock``), which is a SHORT per-step
    lock the driver acquires and releases around each individual phase. The
    driver lock is held for the WHOLE ``auto`` process so two ``megaplan auto``
    invocations on the same plan can't interleave at step boundaries and contend
    over plan state (the dueling-drivers zero-progress plateau).
    """
    return plan_dir / ".auto-driver.lock"


def _read_lock_pid(lock_path: Path) -> int | None:
    """Best-effort read of the pid recorded in a driver lockfile."""
    try:
        text = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return int(text.split()[0])
    except (ValueError, IndexError):
        return None


def _pid_is_live(pid: int) -> bool:
    """True if ``pid`` names a live process this user can signal.

    ``os.kill(pid, 0)`` raises ``ProcessLookupError`` for a dead pid and
    ``PermissionError`` for a live pid owned by another user (still live). pid
    <= 0 targets a process group / every process and must never be treated as a
    specific live holder.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def driver_lock(plan_dir: Path) -> Iterator[None]:
    """Acquire the per-plan ``auto`` driver-lifetime advisory lock.

    Uses a non-blocking ``fcntl.flock`` on ``.auto-driver.lock`` — the same
    primitive ``plan_lock`` uses — held for the lifetime of this context. On
    contention:

    * If the recorded holder pid is LIVE, refuse with a ``driver_locked``
      ``CliError`` naming the pid, so a second ``megaplan auto`` on the same plan
      can't start and create the dueling-drivers plateau.
    * If the holder pid is DEAD (stale lock — the kernel already released the
      ``flock`` when that process exited, so ``flock`` itself won't block here;
      the pid file is just informational), we proceed and reclaim it.

    The kernel drops the advisory lock automatically when the holding process
    exits — including a crash — so a genuinely dead holder never wedges a new
    driver even though its pidfile lingers.
    """
    lock_path = driver_lock_path(plan_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            # flock is held by a LIVE process (the kernel released it if the
            # holder had exited). Report which pid, falling back to "another
            # process" if the pidfile is unreadable.
            holder_pid = _read_lock_pid(lock_path)
            if holder_pid is not None and _pid_is_live(holder_pid):
                message = (
                    f"Cannot start 'auto' for plan '{plan_dir.name}': another live "
                    f"megaplan auto driver (pid {holder_pid}) already holds it. "
                    f"Running two drivers on one plan contends over plan state and "
                    f"stalls progress. Stop pid {holder_pid} first, or wait for it "
                    f"to finish."
                )
            else:
                message = (
                    f"Cannot start 'auto' for plan '{plan_dir.name}': another "
                    f"megaplan auto driver already holds it."
                )
            handle.close()
            raise CliError(
                "driver_locked",
                message,
                extra={"plan": plan_dir.name, "holder_pid": holder_pid},
            ) from exc
        # We hold the lock. Record our pid (truncate any stale pid first) so a
        # later contender can name us / detect our liveness.
        try:
            handle.seek(0)
            handle.truncate(0)
            handle.write(f"{os.getpid()}\n")
            handle.flush()
        except OSError:
            pass
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        if not handle.closed:
            handle.close()


def save_state(plan_dir: Path, state: PlanState) -> None:
    write_plan_state(plan_dir, mode="replace", state=state)


PlanStateWriteMode = Literal[
    "replace",
    "executor-key-merge",
    "patch-key",
    "patch-many",
    "active-step-heartbeat",
    "merge-meta-list",
    "legacy-migration",
    "copy-time-rewrite",
]

PlanStateMutation = Callable[[dict[str, Any]], bool | None]


def plan_state_lock_path(plan_dir: Path) -> Path:
    if plan_dir.parent.name == "plans":
        return plan_dir.parent.parent / ".state-locks" / f"{plan_dir.name}.lock"
    return plan_dir.parent / ".state-locks" / f"{plan_dir.name}.lock"


@contextmanager
def plan_state_lock(plan_dir: Path) -> Iterator[None]:
    """Serialize short read/modify/write cycles for ``state.json``."""

    lock_path = plan_state_lock_path(plan_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_plan_state_for_persist(state: dict[str, Any], *, plan_dir: Path) -> None:
    current_state = state.get("current_state")
    if current_state is None:
        return
    try:
        validate_plan_current_state(current_state)
    except ValueError as exc:
        raise CliError(
            "invalid_plan_state",
            f"Refusing to persist plan state with invalid current_state={current_state!r}",
            extra={
                "plan": plan_dir.name,
                "current_state": current_state,
                "allowed_states": sorted(CANONICAL_PLAN_STATES),
            },
        ) from exc


def _read_state_for_write(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        state = read_json(state_path)
    except json.JSONDecodeError as exc:
        raise CliError(
            "corrupt_state_write",
            f"M3B_HALT_CORRUPT_STATE_WRITE: failed to read plan state for write at {state_path}: {exc}",
            extra={"path": str(state_path)},
        ) from exc
    except UnicodeDecodeError as exc:
        raise CliError(
            "corrupt_state_write",
            f"M3B_HALT_CORRUPT_STATE_WRITE: failed to decode plan state for write at {state_path}: {exc}",
            extra={"path": str(state_path)},
        ) from exc
    if not isinstance(state, dict):
        raise CliError(
            "invalid_state_shape",
            "M3B_HALT_INVALID_STATE_SHAPE: "
            f"plan state at {state_path} must be a JSON object, got {type(state).__name__}",
            extra={"path": str(state_path), "root_type": type(state).__name__},
        )
    return state


def _apply_legacy_state_migration(state: dict[str, Any]) -> bool:
    migrated = False
    if state.get("current_state") == "clarified":
        state["current_state"] = STATE_INITIALIZED
        migrated = True
    elif state.get("current_state") == "evaluated":
        state["current_state"] = STATE_CRITIQUED
        state["last_gate"] = {}
        migrated = True
    if "last_evaluation" in state:
        del state["last_evaluation"]
        migrated = True
    if "last_gate" not in state:
        state["last_gate"] = {}
        migrated = True
    return migrated


def _apply_copy_time_rewrite(
    state: dict[str, Any],
    *,
    project_dir: str | None,
) -> bool:
    config = state.get("config")
    if not isinstance(config, dict):
        config = {}
        state["config"] = config
    original = config.get("project_dir")
    changed = config.get("project_dir") != project_dir
    if "archived_project_dir" not in config:
        config["archived_project_dir"] = original
        changed = True
    config["project_dir"] = project_dir
    return changed


def write_plan_state(
    plan_dir: Path,
    *,
    mode: PlanStateWriteMode,
    state: dict[str, Any] | None = None,
    patch: dict[str, Any] | None = None,
    key: str | None = None,
    value: Any = None,
    executor_owned_keys: Iterable[str] | None = None,
    merge_fields: Iterable[str] | None = None,
    run_id: str | None = None,
    kind: str | None = None,
    detail: str | None = None,
    project_dir: str | None = None,
    mutation: PlanStateMutation | None = None,
    validate_current_state: bool = True,
) -> dict[str, Any]:
    """Read, modify, validate, and atomically replace a plan ``state.json``.

    The dedicated state lock covers the whole sequence. Blob/artifact helpers
    intentionally stay outside this API; this is only for live plan-run state.
    """

    state_path = plan_dir / "state.json"
    should_write = True
    with plan_state_lock(plan_dir):
        if mode == "replace":
            if state is None:
                raise TypeError("state is required for replace mode")
            next_state = dict(state)
        else:
            existing = _read_state_for_write(state_path)
            if mode == "executor-key-merge":
                if state is None:
                    raise TypeError("state is required for executor-key-merge mode")
                if state_path.exists() and executor_owned_keys is not None:
                    next_state = dict(existing)
                    for owned_key in executor_owned_keys:
                        if owned_key in state:
                            next_state[owned_key] = state[owned_key]
                elif state_path.exists():
                    next_state = {**dict(state), **existing}
                else:
                    next_state = dict(state)
            elif mode == "patch-key":
                if key is None:
                    raise TypeError("key is required for patch-key mode")
                next_state = dict(existing)
                next_state[key] = value
            elif mode == "patch-many":
                if patch is None:
                    raise TypeError("patch is required for patch-many mode")
                next_state = dict(existing)
                next_state.update(patch)
            elif mode == "active-step-heartbeat":
                next_state = dict(existing)
                active_step = next_state.get("active_step")
                if (
                    not run_id
                    or not isinstance(active_step, dict)
                    or active_step.get("run_id") != run_id
                ):
                    should_write = False
                else:
                    active_step = dict(active_step)
                    active_step["last_activity_at"] = now_utc()
                    active_step["last_activity_kind"] = kind or "heartbeat"
                    if detail:
                        active_step["last_activity_detail"] = detail[-500:]
                    next_state["active_step"] = active_step
                    # Liveness fast-path: a heartbeat only refreshes the
                    # ephemeral ``active_step.last_activity_*`` fields — never
                    # anything the resume/recovery point depends on. Re-
                    # serializing the entire (~24KB) state on every ~2s beat
                    # burned most of a core in json.dumps on long streams.
                    # Coalesce the full content write to at most once per
                    # ``_heartbeat_persist_interval_seconds`` (keeps the
                    # content field — which the auto-driver's stall monitor
                    # reads — fresh enough), and on the skipped beats just bump
                    # the file mtime cheaply for any mtime-based watchdog.
                    interval = _heartbeat_persist_interval_seconds()
                    key = str(state_path)
                    now_mono = time.monotonic()
                    last = _last_heartbeat_persist_at.get(key)
                    due = (
                        interval <= 0
                        or last is None
                        or (now_mono - last) >= interval
                    )
                    if due:
                        _last_heartbeat_persist_at[key] = now_mono
                    else:
                        # Skip the costly full re-serialize; still signal
                        # liveness via mtime so an mtime-keyed monitor (and the
                        # io.py staging/idle checks) see the process as alive.
                        should_write = False
                        try:
                            if state_path.exists():
                                os.utime(state_path, None)
                        except OSError:
                            pass
            elif mode == "merge-meta-list":
                if state is None:
                    raise TypeError("state is required for merge-meta-list mode")
                next_state = dict(state)
                disk_meta = existing.get("meta") if isinstance(existing.get("meta"), dict) else {}
                meta = next_state.setdefault("meta", {})
                if not isinstance(meta, dict):
                    meta = {}
                    next_state["meta"] = meta
                for field in (merge_fields or _DEFAULT_MERGE_FIELDS):
                    key_func = _FIELD_KEY_FUNCS.get(field)
                    if key_func is None:
                        continue
                    meta[field] = _merge_meta_lists(
                        disk_meta.get(field, []),
                        meta.get(field, []),
                        key_func=key_func,
                    )
            elif mode == "legacy-migration":
                next_state = dict(existing)
                should_write = _apply_legacy_state_migration(next_state)
                if mutation is not None:
                    mutation_changed = mutation(next_state)
                    should_write = should_write or bool(mutation_changed)
            elif mode == "copy-time-rewrite":
                next_state = dict(existing)
                should_write = _apply_copy_time_rewrite(next_state, project_dir=project_dir)
            else:
                raise ValueError(f"unknown plan state write mode: {mode}")

        if mutation is not None and mode != "legacy-migration":
            mutation_changed = mutation(next_state)
            if mutation_changed is False:
                should_write = False
        if validate_current_state:
            _validate_plan_state_for_persist(next_state, plan_dir=plan_dir)
        if should_write:
            atomic_write_json(state_path, next_state)
        return next_state


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
# Append-only operator meta fields can be written while a phase holds the plan
# lock. Re-read them on save, take the union with the in-memory copies
# (de-duped by content), and only then write.

_DEFAULT_MERGE_FIELDS: tuple[str, ...] = (
    "notes",
    "overrides",
    "user_action_resolutions",
    "quality_gate_resolutions",
)


def _note_merge_key(entry: Any) -> tuple[str, str]:
    """Stable de-dup key for a ``meta.notes`` entry.

    Notes are ``{"timestamp": str, "note": str}``. The hash digest of the note
    body collapses literal duplicates while still distinguishing notes that
    happen to share a timestamp.
    """
    if not isinstance(entry, dict):
        encoded = json.dumps(entry, sort_keys=True, default=str).encode("utf-8")
        return ("", hashlib.sha256(encoded).hexdigest()[:16])
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
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
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
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


def _resolution_merge_key(entry: Any) -> tuple[str, str, str, str]:
    """Stable de-dup key for a ``meta.user_action_resolutions`` entry.

    Resolution events are ``{"action_id": str, "timestamp": str,
    "resolution": str, "reason": str, ...}``.  We dedupe by ``(action_id,
    timestamp, resolution, hash(reason))`` so two distinct resolution events
    that happen to share a timestamp still survive.
    """
    if not isinstance(entry, dict):
        encoded = json.dumps(entry, sort_keys=True, default=str).encode("utf-8")
        return ("", "", "", hashlib.sha256(encoded).hexdigest()[:16])
    action_id = entry.get("action_id", "")
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
    resolution = entry.get("resolution", "")
    reason = entry.get("reason", "")
    digest_payload = {
        "debt_note": entry.get("debt_note", ""),
        "evidence": entry.get("evidence", []),
        "fallback_mode": entry.get("fallback_mode", ""),
        "instructions": entry.get("instructions", ""),
        "phase": entry.get("phase", ""),
        "reason": reason,
    }
    if not isinstance(action_id, str):
        action_id = str(action_id)
    if not isinstance(timestamp, str):
        timestamp = str(timestamp)
    if not isinstance(resolution, str):
        resolution = str(resolution)
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return (action_id, timestamp, resolution, digest)


def _quality_resolution_merge_key(entry: Any) -> tuple[str, str, str, str]:
    """Stable de-dup key for a ``meta.quality_gate_resolutions`` entry."""
    if not isinstance(entry, dict):
        encoded = json.dumps(entry, sort_keys=True, default=str).encode("utf-8")
        return ("", "", "", hashlib.sha256(encoded).hexdigest()[:16])
    blocker_id = entry.get("blocker_id", "")
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
    resolution = entry.get("resolution", "")
    evidence = entry.get("evidence", [])
    debt_note = entry.get("debt_note", "")
    phase = entry.get("phase", "")
    if not isinstance(blocker_id, str):
        blocker_id = str(blocker_id)
    if not isinstance(timestamp, str):
        timestamp = str(timestamp)
    if not isinstance(resolution, str):
        resolution = str(resolution)
    digest_payload = {
        "debt_note": debt_note,
        "evidence": evidence,
        "fallback_mode": entry.get("fallback_mode", ""),
        "phase": phase,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return (blocker_id, timestamp, resolution, digest)


_FIELD_KEY_FUNCS: dict[str, Any] = {
    "notes": _note_merge_key,
    "overrides": _override_merge_key,
    "user_action_resolutions": _resolution_merge_key,
    "quality_gate_resolutions": _quality_resolution_merge_key,
}


def _timestamp_sort_key(entry: Any) -> str:
    if isinstance(entry, dict):
        timestamp = entry.get("timestamp") or entry.get("created_at") or ""
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
    merged = write_plan_state(
        plan_dir,
        mode="merge-meta-list",
        state=state,
        merge_fields=merge_fields,
    )
    state.clear()
    state.update(merged)


def apply_session_update(
    state: PlanState,
    step: str,
    agent: str,
    session_id: str | None,
    *,
    mode: str,
    refreshed: bool,
    model: str | None = None,
) -> None:
    from megaplan.workers import update_session_state

    result = update_session_state(
        step,
        agent,
        session_id,
        mode=mode,
        refreshed=refreshed,
        model=model,
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
    active_step: ActivePhase = {
        "phase": step,
        "agent": agent,
        "mode": mode,
        "run_id": resolved_run_id,
        "worker_pid": os.getpid(),
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
    from megaplan.orchestration.phase_result import generate_invocation_id

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
    try:
        write_plan_state(
            plan_dir,
            mode="active-step-heartbeat",
            run_id=run_id,
            kind=kind,
            detail=detail,
        )
    except Exception:
        return


def clear_active_step(state: PlanState, *, run_id: str | None = None) -> None:
    active_step = state.get("active_step")
    if (
        run_id is not None
        and isinstance(active_step, dict)
        and active_step.get("run_id") != run_id
    ):
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
    # Tier routing observability fields (omitted for flat profiles).
    batch_complexity: int | None = None,
    tier_model_spec: str | None = None,
    tier_model_resolved: str | None = None,
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
    # Tier routing observability — only present when tier routing is active.
    if batch_complexity is not None:
        entry["batch_complexity"] = batch_complexity
    if tier_model_spec is not None:
        entry["tier_model_spec"] = tier_model_spec
    if tier_model_resolved is not None:
        entry["tier_model_resolved"] = tier_model_resolved
    return entry


def store_raw_worker_output(
    plan_dir: Path, step: str, iteration: int, content: str
) -> str:
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
