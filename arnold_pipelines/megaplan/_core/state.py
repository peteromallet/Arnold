"""Plan state management — load, save, history, sessions, failure recording.

Reserved top-level key (M2 / T2b)
---------------------------------

``'_state_meta'`` is a reserved top-level key on ``PlanState`` owned by
the :mod:`megaplan._pipeline` typed-port substrate. Its shape is::

    {'versions': {<key>: <int>, ...}}

Each entry in ``versions`` is the monotonically-increasing CAS version
for the like-named top-level state key, used by
:func:`megaplan.state_delta.apply_delta` to detect stale writes and
raise :class:`megaplan.state_delta.StateDeltaConflict`. Callers
outside the typed-port substrate MUST NOT mutate ``_state_meta`` directly.
"""

from __future__ import annotations

import copy
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

from arnold_pipelines.megaplan.fallback_chains import fallback_observability_fields
from arnold_pipelines.megaplan.types import (
    ActivePhase,
    AgentSpec,
    CliError,
    HistoryEntry,
    PlanState,
    PlanVersionRecord,
    format_agent_spec,
)
from arnold_pipelines.megaplan.planning.state import (
    CANONICAL_PLAN_STATES,
    STATE_CRITIQUED,
    STATE_FINALIZED,
    STATE_INITIALIZED,
    STATE_AWAITING_HUMAN,
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
    from arnold_pipelines.megaplan.workers import WorkerResult


DEFAULT_ACTIVE_STEP_STALE_SECONDS = DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS

# M4 authority boundary: state.json is no longer an independent authority for
# manifest-backed callers.  It survives only as a migration input or a read-only
# sunset projection.  New code should derive status/trace/resume/inspect from
# manifest journal events and artifact bindings.
STATE_JSON_AUTHORITY = False


def is_state_json_authority() -> bool:
    """Return whether state.json is currently treated as independent authority."""
    return STATE_JSON_AUTHORITY


def load_state_as_projection(plan_dir: Path) -> dict[str, Any] | None:
    """Load ``state.json`` as a read-only sunset projection only.

    This function is intentionally read-only and never used for resume,
    status, trace, or control-transition authority in manifest-backed callers.
    """
    state_path = plan_dir / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else {}


def _heartbeat_persist_interval_seconds() -> float:
    raw = os.environ.get("MEGAPLAN_HEARTBEAT_PERSIST_INTERVAL_S")
    if raw:
        try:
            value = float(raw)
            if value >= 0:
                return value
        except ValueError:
            pass
    return 30.0


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
        from arnold_pipelines.megaplan._core.io import read_plan_state_cached
        state = read_plan_state_cached(plan_dir, mode="authority")
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
    from arnold_pipelines.megaplan.fallback_chains import decode_phase_model_value
    from arnold_pipelines.megaplan.types import parse_agent_spec

    if not isinstance(state, dict):
        return
    phase_models = state.get("config", {}).get("phase_model") or []
    if not isinstance(phase_models, list):
        return
    for entry in phase_models:
        if not isinstance(entry, str) or "=" not in entry:
            continue
        try:
            phase, chain = decode_phase_model_value(entry)
        except ValueError as exc:
            raise CliError(
                "corrupt_phase_model",
                f"Plan '{plan_dir.name}' has a malformed persisted routing pin "
                f"entry {entry!r}. {str(exc)}",
            ) from exc
        for index, spec in enumerate(chain.specs):
            try:
                parse_agent_spec(spec)
            except (CliError, ValueError) as exc:
                location = f"phase '{phase}'" if len(chain.specs) == 1 else f"phase '{phase}' chain[{index}]"
                raise CliError(
                    "corrupt_phase_model",
                    f"Plan '{plan_dir.name}' has a malformed persisted routing pin "
                    f"for {location}: {spec!r}. {str(exc)} "
                    f"Fix it with `megaplan override set-model --phase {phase} "
                    f"--model <model>` (or `set-vendor`) before resuming.",
                ) from exc


def _all_finalize_user_actions_satisfied(plan_dir: Path, state: dict[str, Any]) -> bool:
    """Return True when every finalize user-action gate has been satisfied."""

    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return False
    try:
        finalize = read_json(finalize_path)
    except Exception:
        return False
    if not isinstance(finalize, dict):
        return False
    user_actions = finalize.get("user_actions")
    if not isinstance(user_actions, list) or not user_actions:
        return False

    try:
        from arnold_pipelines.megaplan.resolutions import effective_user_action_resolutions

        resolutions = effective_user_action_resolutions(plan_dir, state)
    except Exception:
        return False

    required_action_ids: list[str] = []
    for action in user_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id") or action.get("action_id")
        if isinstance(action_id, str) and action_id:
            required_action_ids.append(action_id)
    if not required_action_ids:
        return False
    for action_id in required_action_ids:
        resolution = resolutions.get(action_id)
        if not isinstance(resolution, dict):
            return False
        if (resolution.get("state") or resolution.get("resolution")) != "satisfied":
            return False
    return True


def _reconcile_satisfied_user_action_gate(plan_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Move stale awaiting-human user-action gates back to finalized."""

    if state.get("current_state") not in {STATE_AWAITING_HUMAN, "awaiting_human"}:
        return state
    clarification = state.get("clarification")
    if isinstance(clarification, dict) and clarification.get("source") == "prep":
        return state
    if not _all_finalize_user_actions_satisfied(plan_dir, state):
        return state

    def _transition(current: dict[str, Any]) -> bool:
        if current.get("current_state") not in {STATE_AWAITING_HUMAN, "awaiting_human"}:
            return False
        if not _all_finalize_user_actions_satisfied(plan_dir, current):
            return False
        current["current_state"] = STATE_FINALIZED
        current["latest_failure"] = None
        current.pop("active_step", None)
        current.pop("resume_cursor", None)
        current.setdefault("meta", {})
        if isinstance(current["meta"], dict):
            current["meta"].setdefault("state_reconciliations", []).append(
                {
                    "kind": "satisfied_user_action_gate",
                    "from_state": state.get("current_state"),
                    "to_state": STATE_FINALIZED,
                    "timestamp": now_utc(),
                }
            )
        return True

    return write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_transition)


def _approved_review_outcome_is_done(plan_dir: Path) -> bool:
    review_path = plan_dir / "review.json"
    if not review_path.exists():
        return False
    try:
        review = read_json(review_path)
    except Exception:
        return False
    if not isinstance(review, dict):
        return False
    outcome = review.get("outcome")
    if not isinstance(outcome, dict):
        return False
    result = outcome.get("result")
    if result not in {"success", "force_proceeded"}:
        return False
    if outcome.get("state") != "done":
        return False
    verdict = review.get("review_verdict")
    return verdict in {"approved", "needs_rework"}


def _reconcile_completed_review(plan_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Move stale executed state to done when review.json already finalized the run."""

    if state.get("current_state") != "executed":
        return state
    if not _approved_review_outcome_is_done(plan_dir):
        return state

    def _transition(current: dict[str, Any]) -> bool:
        if current.get("current_state") != "executed":
            return False
        if not _approved_review_outcome_is_done(plan_dir):
            return False
        current["current_state"] = "done"
        current["latest_failure"] = None
        current.pop("active_step", None)
        current.pop("resume_cursor", None)
        current.setdefault("meta", {})
        if isinstance(current["meta"], dict):
            current["meta"].setdefault("state_reconciliations", []).append(
                {
                    "kind": "completed_review",
                    "from_state": state.get("current_state"),
                    "to_state": "done",
                    "timestamp": now_utc(),
                }
            )
        return True

    return write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_transition)


def _finalize_phase_completed_successfully(plan_dir: Path, state: dict[str, Any]) -> bool:
    history = state.get("history")
    if not isinstance(history, list) or not history:
        return False
    last_entry = history[-1]
    if not isinstance(last_entry, dict):
        return False
    if last_entry.get("step") != "finalize" or last_entry.get("result") != "success":
        return False

    from arnold_pipelines.megaplan.orchestration.phase_result import read_phase_result

    try:
        phase_result = read_phase_result(plan_dir)
    except Exception:
        return False
    return bool(
        phase_result is not None
        and getattr(phase_result, "phase", None) == "finalize"
        and getattr(phase_result, "exit_kind", None) == "success"
    )


def _reconcile_failed_no_next_after_finalize(
    plan_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Recover failed status-projection loops after a successful finalize.

    A live finalize can complete successfully, transition state to ``finalized``,
    and then immediately hit the status route's ``no_next_step`` failure path.
    That leaves ``state.json`` in ``failed`` even though the durable phase
    evidence says finalize succeeded and execute should be next.
    """

    if state.get("current_state") != "failed":
        return state
    resume_cursor = state.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        return state
    if resume_cursor.get("phase") != "status" or resume_cursor.get("retry_strategy") != "repair_state":
        return state
    latest_failure = state.get("latest_failure")
    if latest_failure is not None:
        if not isinstance(latest_failure, dict) or latest_failure.get("kind") != "no_next_step":
            return state
    if not _finalize_phase_completed_successfully(plan_dir, state):
        return state

    def _transition(current: dict[str, Any]) -> bool:
        if current.get("current_state") != "failed":
            return False
        current_resume = current.get("resume_cursor")
        if not isinstance(current_resume, dict):
            return False
        if (
            current_resume.get("phase") != "status"
            or current_resume.get("retry_strategy") != "repair_state"
        ):
            return False
        current_failure = current.get("latest_failure")
        if current_failure is not None:
            if not isinstance(current_failure, dict) or current_failure.get("kind") != "no_next_step":
                return False
        if not _finalize_phase_completed_successfully(plan_dir, current):
            return False
        current["current_state"] = STATE_FINALIZED
        current["latest_failure"] = None
        current.pop("active_step", None)
        current.pop("resume_cursor", None)
        current.setdefault("meta", {})
        if isinstance(current["meta"], dict):
            current["meta"].setdefault("state_reconciliations", []).append(
                {
                    "kind": "failed_no_next_after_finalize",
                    "from_state": state.get("current_state"),
                    "to_state": STATE_FINALIZED,
                    "timestamp": now_utc(),
                }
            )
        return True

    return write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_transition)


def load_plan_from_dir(plan_dir: Path) -> tuple[Path, PlanState]:
    from arnold_pipelines.megaplan._core.io import read_plan_state_cached
    state = read_plan_state_cached(plan_dir, mode="authority")
    if isinstance(state, dict) and (
        state.get("current_state") in {"clarified", "evaluated"}
        or "last_evaluation" in state
        or "last_gate" not in state
    ):
        state = write_plan_state(plan_dir, mode="legacy-migration")
    if isinstance(state, dict):
        state = _reconcile_satisfied_user_action_gate(plan_dir, state)
        state = _reconcile_completed_review(plan_dir, state)
        state = _reconcile_failed_no_next_after_finalize(plan_dir, state)
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
    "reversible",
]

PlanStateMutation = Callable[[dict[str, Any]], bool | None]


def plan_state_lock_path(plan_dir: Path) -> Path:
    if plan_dir.parent.name == "plans":
        return plan_dir.parent.parent / ".state-locks" / f"{plan_dir.name}.lock"
    return plan_dir.parent / ".state-locks" / f"{plan_dir.name}.lock"


@contextmanager
def plan_state_lock(plan_dir: Path) -> Iterator[None]:
    """Serialize short read/modify/write cycles for ``state.json``."""
    from arnold.runtime.state_persistence import plan_state_lock as _rt_plan_state_lock

    lock_path = plan_state_lock_path(plan_dir)
    with _rt_plan_state_lock(lock_path):
        yield


#: Reserved top-level keys that are passed through ``write_plan_state`` without
#: schema validation. ``_state_meta`` holds the CAS version map
#: (``{"versions": {key: int}}``) maintained by ``apply_delta``.
_PERSIST_RESERVED_KEYS: frozenset[str] = frozenset({"_state_meta"})


def _validate_plan_state_for_persist(state: dict[str, Any], *, plan_dir: Path) -> None:
    # Reserved keys (e.g. ``_state_meta``) round-trip transparently — they are
    # not subject to schema-level validation.
    for _reserved in _PERSIST_RESERVED_KEYS:
        state.get(_reserved)  # touch only; allow-listed for persist
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


_STATE_VERSIONS_DIRNAME = ".state-versions"


class RestorableBoundaryViolation(RuntimeError):
    """Raised when a ``restorable_boundary`` is entered from a composition
    context where snapshot-then-replace cannot be reversed cheaply: under the
    ``subprocess_isolated`` driver (the child owns its own state.json copy and
    a parent-side restore would race the child) or under an active fan-out
    spec (``_fanout_active_ctx`` is True; siblings would observe a torn
    rollback).

    This error precedes any Governor ``BudgetExceeded`` raised by the same
    operation — the boundary is checked at ``__enter__`` time, before the
    work begins.
    """


def _state_versions_dir(plan_dir: Path) -> Path:
    return plan_dir / _STATE_VERSIONS_DIRNAME


def _snapshot_unlocked(plan_dir: Path) -> str | None:
    """Whole-blob copy of ``state.json`` to ``.state-versions/<id>.json``.

    Assumes the caller already holds ``plan_state_lock(plan_dir)``. Returns
    the snapshot id, or ``None`` when there is no on-disk state to capture.

    The directory name ``.state-versions`` is distinct from the executor's
    sibling forensic-backup path (``state.json.corrupt-executor-backup``);
    the two namespaces do not collide.
    """

    state_path = plan_dir / "state.json"
    if not state_path.exists():
        return None
    snapshot_id = uuid.uuid4().hex
    versions_dir = _state_versions_dir(plan_dir)
    versions_dir.mkdir(parents=True, exist_ok=True)
    dest = versions_dir / f"{snapshot_id}.json"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(state_path.read_bytes())
    os.replace(tmp, dest)
    return snapshot_id


def snapshot(plan_dir: Path) -> str | None:
    """Capture ``state.json`` under ``plan_state_lock``.

    Returns the snapshot id (a hex uuid) or ``None`` when no state file
    exists. The blob lives at ``<plan_dir>/.state-versions/<id>.json``.
    """

    with plan_state_lock(plan_dir):
        return _snapshot_unlocked(plan_dir)


def restore(plan_dir: Path, snapshot_id: str) -> dict[str, Any]:
    """Atomically restore ``state.json`` from the recorded snapshot.

    Raises ``CliError('missing_snapshot', ...)`` when the snapshot file is
    absent. Returns the restored state dict.
    """

    versions_dir = _state_versions_dir(plan_dir)
    src = versions_dir / f"{snapshot_id}.json"
    with plan_state_lock(plan_dir):
        if not src.exists():
            raise CliError(
                "missing_snapshot",
                f"reversible restore: snapshot {snapshot_id} not found at {src}",
                extra={"plan": plan_dir.name, "snapshot_id": snapshot_id},
            )
        restored = read_json(src)
        if not isinstance(restored, dict):
            raise CliError(
                "invalid_state_shape",
                f"reversible restore: snapshot {snapshot_id} is not a JSON object",
                extra={"path": str(src), "root_type": type(restored).__name__},
            )
        atomic_write_json(plan_dir / "state.json", restored)
    return restored


@contextmanager
def restorable_boundary(operation: str) -> Iterator[None]:
    """Boundary that refuses to enter under composition contexts where a
    snapshot/restore round-trip would race or tear other observers.

    Raises :class:`RestorableBoundaryViolation` (loud, NOT silent) when
    either:
      * ``current_substrate() == 'subprocess_isolated'`` — the child owns its
        own ``state.json`` copy and a parent-side restore would race it.
      * ``_fanout_active_ctx.get(False)`` is ``True`` — sibling spec replicas
        would observe a torn rollback.

    The check fires at ``__enter__``, *before* any Governor budget check the
    same operation might perform, so the boundary error precedes
    ``BudgetExceeded``.
    """

    # Lazy imports avoid a state.py -> drivers / pipeline import cycle at
    # module-load time (state.py is imported very early in the stack).
    from arnold_pipelines.megaplan.drivers import current_substrate
    from arnold.runtime.envelope import _fanout_active_ctx

    substrate = current_substrate()
    fanout_active = _fanout_active_ctx.get(False)
    if substrate == "subprocess_isolated" or fanout_active:
        raise RestorableBoundaryViolation(
            f"restorable_boundary({operation!r}) refused: "
            f"substrate={substrate!r}, fanout_active={fanout_active!r}"
        )
    yield


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
    preserve_disk_non_meta: bool = False,
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
                    try:
                        from arnold_pipelines.megaplan.feature_flags import typed_ports_on
                        from arnold_pipelines.megaplan.state_delta import StateDelta, apply_delta
                        _flag_on = typed_ports_on()
                    except Exception:
                        _flag_on = False
                    if _flag_on:
                        next_state = dict(existing)
                        for owned_key in executor_owned_keys:
                            if owned_key in state:
                                _versions = (
                                    next_state.get("_state_meta", {}).get("versions", {})
                                )
                                _current = int(_versions.get(owned_key, 0))
                                next_state, _ = apply_delta(
                                    next_state,
                                    StateDelta(
                                        op="replace",
                                        key=owned_key,
                                        value=state[owned_key],
                                        version=_current,
                                    ),
                                )
                    else:
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
                        should_write = False
                        try:
                            if state_path.exists():
                                os.utime(state_path, None)
                        except OSError:
                            pass
            elif mode == "merge-meta-list":
                if state is None:
                    raise TypeError("state is required for merge-meta-list mode")
                # Meta-list appends are often issued by short-lived override
                # commands while another override or phase transition is also
                # saving state. Normal phase saves must keep the in-memory state
                # transition as authority; otherwise a successful phase can
                # preserve an older on-disk lifecycle state forever. Meta-only
                # writers can opt into preserving disk non-meta fields so a
                # stale note snapshot cannot roll back a just-applied transition.
                next_state = (
                    dict(existing)
                    if preserve_disk_non_meta and state_path.exists()
                    else dict(state)
                )
                disk_meta = existing.get("meta") if isinstance(existing.get("meta"), dict) else {}
                memory_meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
                base_meta = next_state.get("meta") if isinstance(next_state.get("meta"), dict) else {}
                meta = dict(base_meta)
                next_state["meta"] = meta
                for field in (merge_fields or _DEFAULT_MERGE_FIELDS):
                    key_func = _FIELD_KEY_FUNCS.get(field)
                    if key_func is None:
                        continue
                    meta[field] = _merge_meta_lists(
                        disk_meta.get(field, []),
                        memory_meta.get(field, []),
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
            elif mode == "reversible":
                if state is None:
                    raise TypeError("state is required for reversible mode")
                # Snapshot-then-replace: capture current on-disk blob (if any)
                # under the held lock, then atomically replace. The snapshot id
                # is recorded under ``next_state['_state_meta']['last_snapshot']``
                # so callers can restore() it explicitly. A missing prior
                # state.json yields snapshot_id=None — the anti-silent-no-op
                # invariant requires the meta key to be present either way.
                snapshot_id = _snapshot_unlocked(plan_dir)
                next_state = dict(state)
                meta = next_state.get("_state_meta")
                if not isinstance(meta, dict):
                    meta = {}
                else:
                    meta = dict(meta)
                meta["last_snapshot"] = snapshot_id
                next_state["_state_meta"] = meta
            else:
                raise ValueError(f"unknown plan state write mode: {mode}")

        if mutation is not None and mode != "legacy-migration":
            mutation_changed = mutation(next_state)
            if mutation_changed is False:
                should_write = False
        next_state.setdefault("schema_version", 0)
        if validate_current_state:
            _validate_plan_state_for_persist(next_state, plan_dir=plan_dir)
        if should_write:
            atomic_write_json(state_path, next_state)
            snapshot = copy.deepcopy(next_state)
        else:
            snapshot = None
    # Lock released — emit shadow-WAL only when an on-disk write actually happened.
    if snapshot is not None:
        from arnold_pipelines.megaplan.observability.events import emit_state_wal
        emit_state_wal(plan_dir, snapshot)
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
    waiver_id = entry.get("waiver_id", "")
    if not isinstance(waiver_id, str):
        waiver_id = str(waiver_id)
    digest = hashlib.sha256((note + "|" + reason + "|" + waiver_id).encode("utf-8")).hexdigest()[:16]
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
    preserve_disk_non_meta: bool = False,
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
        preserve_disk_non_meta=preserve_disk_non_meta,
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
    worker_channel: str | None = None,
    auth_channel: str | None = None,
    auth_metadata: dict[str, Any] | None = None,
) -> None:
    from arnold_pipelines.megaplan.workers import update_session_state

    result = update_session_state(
        step,
        agent,
        session_id,
        mode=mode,
        refreshed=refreshed,
        model=model,
        worker_channel=worker_channel,
        auth_channel=auth_channel,
        auth_metadata=auth_metadata,
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
    configured_specs: str | list[str] | tuple[str, ...] | None = None,
    attempt_index: int = 0,
    attempted_specs: str | list[str] | tuple[str, ...] | None = None,
    failed_attempt_reasons: list[str] | tuple[str, ...] | None = None,
    fallback_trigger: str | None = None,
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
    selected_spec = configured_specs or format_agent_spec(AgentSpec(agent=agent, model=model))
    active_step.update(
        fallback_observability_fields(
            selected_spec or agent,
            attempt_index=attempt_index,
            attempted_specs=attempted_specs,
            failed_attempt_reasons=failed_attempt_reasons,
            fallback_trigger=fallback_trigger,
        )
    )
    if mode == "persistent":
        from arnold_pipelines.megaplan.workers import session_key_for

        session = state.get("sessions", {}).get(session_key_for(step, agent, model), {})
        session_id = session.get("id")
        if isinstance(session_id, str) and session_id:
            active_step["session_id"] = session_id
    state["active_step"] = active_step
    from arnold_pipelines.megaplan.orchestration.phase_result import generate_invocation_id

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
    # M4 T15 — first journaled model-spend seam.  Under EFFECT_LEDGER=1, route
    # the cost-attribution write through journal_then_execute so the intent is
    # durably journaled BEFORE the in-memory accumulation; off-path is
    # byte-identical.
    def _accumulate() -> None:
        state["history"].append(entry)
        state["meta"].setdefault("total_cost_usd", 0.0)
        state["meta"]["total_cost_usd"] = round(
            float(state["meta"]["total_cost_usd"]) + float(entry.get("cost_usd", 0.0)),
            6,
        )

    try:
        from arnold_pipelines.megaplan.feature_flags import effect_ledger_on
        from arnold_pipelines.megaplan.observability.effect_enforcement import journal_then_execute
        from arnold_pipelines.megaplan.observability.effect_ledger import Effect, ReplayClass
    except Exception:
        _accumulate()
        return
    if not effect_ledger_on():
        _accumulate()
        return
    cost = float(entry.get("cost_usd", 0.0) or 0.0)
    step = str(entry.get("step", "") or "")
    key = f"model_spend:{step}:{cost}:{len(state.get('history', []))}"
    eff = Effect(
        replay_class=ReplayClass.idempotent_keyed,
        idempotency_key=key,
        provenance={"module": "arnold_pipelines.megaplan._core.state", "fn": "append_history"},
    )
    journal_then_execute(eff, _accumulate, phase="execute")


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
    # T14: route metadata (omitted for flat profiles / pre-calibration paths).
    tier_routing_source: str | None = None,
    tier_projected: int | None = None,
    tier_counterfactual_tag: str | None = None,
    tier_low_confidence: bool = False,
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
        entry.update(
            fallback_observability_fields(
                getattr(worker, "configured_specs", None) or agent,
                attempt_index=int(getattr(worker, "attempt_index", 0) or 0),
                attempted_specs=getattr(worker, "attempted_specs", None),
                failed_attempt_reasons=getattr(worker, "failed_attempt_reasons", None),
                fallback_trigger=getattr(worker, "fallback_trigger", None),
            )
        )
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
    # T14: route metadata — only present when tier routing is active.
    if tier_routing_source is not None:
        entry["tier_routing_source"] = tier_routing_source
    if tier_projected is not None:
        entry["tier_projected"] = tier_projected
    if tier_counterfactual_tag is not None:
        entry["tier_counterfactual_tag"] = tier_counterfactual_tag
    if tier_low_confidence:
        entry["tier_low_confidence"] = tier_low_confidence
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
