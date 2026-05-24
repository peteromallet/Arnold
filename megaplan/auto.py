"""Auto-driver that advances a plan through its phases without human intervention.

This is the mechanical loop that most orchestrators end up writing by hand:
read `status`, run `next_step`, repeat until terminal. All real judgment is
delegated to megaplan's existing phase logic — the driver only applies two
documented defaults:

1. Gate ESCALATE → force-proceed (caller opts out with ``--on-escalate abort``
   or ``--on-escalate fail``).
2. Same state for N consecutive iterations → bail (stall detection).

The driver is intentionally dumb. If a run needs judgment the driver can't
provide, it exits with a non-zero status and prints the state snapshot so the
caller can intervene.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from megaplan._core import find_plan_dir
from megaplan.observability.events import emit as emit_event, EventKind
from megaplan.orchestration.phase_result import (
    ExitKind,
    PhaseResult,
    read_phase_result,
)
from megaplan.store import PlanRepository
from megaplan.types import (
    AUTOMATION_TERMINAL_STATES,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FAILED,
    STATE_FINALIZED,
    STATE_PAUSED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)


DEFAULT_STALL_THRESHOLD = 5
DEFAULT_MAX_ITERATIONS = 200
DEFAULT_POLL_SLEEP_SECONDS = 1.0
DEFAULT_PHASE_TIMEOUT_SECONDS = 3600
# Backstop for when liveness heartbeats fail to report (e.g. a non-streaming
# worker path, or an undiscovered heartbeat gap). Deliberately generous: a
# false kill of a healthy phase is catastrophic and currently recovers only by
# manual state surgery, whereas over-waiting on a genuinely-dead phase only
# costs wall-clock. Tighten once a stall becomes cheaply recoverable (resume
# the resume_cursor instead of terminal-failing). The accurate per-stream
# heartbeat (workers/hermes.py) is the primary signal; this is the net.
DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS = 1800
DEFAULT_STATUS_TIMEOUT_SECONDS = 60
DEFAULT_MAX_CONTEXT_RETRIES = 2
CONTEXT_EXHAUSTION_FRAGMENT = "ran out of room in the model's context"
# When execute exits 0 but state.json's latest execute entry is `result=blocked`,
# the executor reported success-with-evidence-gaps (e.g. done tasks missing
# files_changed/commands_run). Retrying the same execute is structurally pointless
# — the model returned that shape — so we cap retries low and fail fast.
DEFAULT_MAX_BLOCKED_RETRIES = 1
# Cap on review→rework cycles before the driver bails. This mirrors the
# `execution.max_review_rework_cycles` config the review handler enforces
# internally (default 3); the auto-driver applies its own cap so that an
# unexpected-config or mis-routed rework loop cannot spin indefinitely.
DEFAULT_MAX_REVIEW_REWORK_CYCLES = 3
# How many consecutive `override add-note` failures the auto-driver will
# tolerate at a given critique fork before escalating to `override
# force-proceed`. The gate emits `override add-note` first in `valid_next`
# when a critique loop won't converge; without a human, the driver can
# only synthesize a stub note, and if even that fails twice the only
# remaining safe escape valve is force-proceed.
DEFAULT_MAX_ADD_NOTE_ATTEMPTS = 2
ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")
PHASE_TIMEOUT_EXIT_CODE = 124  # conventional; matches GNU `timeout`
PHASE_NAMES = frozenset(
    {"plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review"}
)


@dataclass
class DriverOutcome:
    """Terminal outcome reported when the loop exits."""

    status: str  # "done" | "paused" | "stalled" | "escalated" | "failed" | "aborted" | "cancelled" | "cap" | "blocked" | "cost_cap_exceeded" | "context_retry_exhausted" | "worker_blocked" | "human_required"
    plan: str
    final_state: str
    iterations: int
    reason: str = ""
    last_phase: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    total_cost_usd: float | None = None
    cost_cap_usd: float | None = None
    context_retries_used: int = 0
    max_context_retries: int | None = None
    blocked_retries_used: int = 0
    max_blocked_retries: int | None = None
    blocking_reasons: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "plan": self.plan,
                "final_state": self.final_state,
                "iterations": self.iterations,
                "reason": self.reason,
                "last_phase": self.last_phase,
                "events": self.events,
                "total_cost_usd": self.total_cost_usd,
                "cost_cap_usd": self.cost_cap_usd,
                "context_retries_used": self.context_retries_used,
                "max_context_retries": self.max_context_retries,
                "blocked_retries_used": self.blocked_retries_used,
                "max_blocked_retries": self.max_blocked_retries,
                "blocking_reasons": self.blocking_reasons,
            },
            indent=2,
        )


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid non-negative integer: {value}") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid non-negative float: {value}") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _run_megaplan(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    idle_timeout: float | None = None,
    progress_env: dict[str, str] | None = None,
    liveness_plan_dir: Path | None = None,
) -> tuple[int, str, str]:
    """Run a megaplan sub-command in its own process.

    We shell out rather than importing the handlers directly so each phase gets
    a fresh argparse/handler lifecycle. This matches how external orchestrators
    drive the CLI and avoids subtle state leakage between phases.

    ``timeout`` is seconds to wait before killing the subprocess. On timeout we
    return exit code ``PHASE_TIMEOUT_EXIT_CODE`` and append a marker to stderr
    so the driver can surface it as a phase failure without crashing the loop.
    The subprocess is killed; any grandchildren it spawned (e.g. codex) may
    need a moment to settle but will exit when their parent's pipes close.
    """
    env = None
    if progress_env:
        env = os.environ.copy()
        env.update(progress_env)
    if idle_timeout is None:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "megaplan", *args],
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as error:
            out = error.output or ""
            err = error.stderr or ""
            if isinstance(out, bytes):
                out = out.decode("utf-8", errors="replace")
            if isinstance(err, bytes):
                err = err.decode("utf-8", errors="replace")
            marker = f"\n[megaplan auto] subprocess timed out after {timeout}s"
            return PHASE_TIMEOUT_EXIT_CODE, out, (err + marker).strip()
        except FileNotFoundError as error:
            return 127, "", str(error)
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "megaplan", *args],
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as error:
        return 127, "", str(error)

    stdout_parts: list[bytes] = []
    stderr_parts: list[bytes] = []
    last_activity = time.monotonic()
    last_hard_progress = last_activity
    last_liveness_mtime = _plan_liveness_mtime(liveness_plan_dir)

    def _reader(stream: Any, parts: list[bytes]) -> None:
        nonlocal last_activity, last_hard_progress
        if stream is None:
            return
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            parts.append(chunk)
            last_activity = time.monotonic()
            last_hard_progress = last_activity

    threads = [
        threading.Thread(target=_reader, args=(proc.stdout, stdout_parts), daemon=True),
        threading.Thread(target=_reader, args=(proc.stderr, stderr_parts), daemon=True),
    ]
    for thread in threads:
        thread.start()

    started = time.monotonic()
    timed_out_reason: str | None = None
    while proc.poll() is None:
        now = time.monotonic()
        current_liveness_mtime = _plan_liveness_mtime(liveness_plan_dir)
        if (
            current_liveness_mtime is not None
            and (
                last_liveness_mtime is None
                or current_liveness_mtime > last_liveness_mtime
            )
        ):
            last_liveness_mtime = current_liveness_mtime
            last_activity = now
            last_hard_progress = now
        timeout_base = last_hard_progress if idle_timeout is not None else started
        if timeout is not None and now - timeout_base >= timeout:
            timed_out_reason = f"subprocess timed out after {timeout}s"
            break
        if idle_timeout is not None and now - last_activity >= idle_timeout:
            timed_out_reason = f"subprocess idle timed out after {idle_timeout}s without output"
            break
        time.sleep(0.2)

    if timed_out_reason is not None:
        proc.kill()
        proc.wait()
        for thread in threads:
            thread.join(timeout=1)
        stdout = b"".join(stdout_parts).decode("utf-8", errors="replace")
        stderr = b"".join(stderr_parts).decode("utf-8", errors="replace")
        marker = f"\n[megaplan auto] {timed_out_reason}"
        return PHASE_TIMEOUT_EXIT_CODE, stdout, (stderr + marker).strip()

    for thread in threads:
        thread.join(timeout=1)
    stdout = b"".join(stdout_parts).decode("utf-8", errors="replace")
    stderr = b"".join(stderr_parts).decode("utf-8", errors="replace")
    return int(proc.returncode or 0), stdout, stderr


def _plan_liveness_mtime(plan_dir: Path | None) -> float | None:
    """Return newest plan artifact mtime that proves a quiet phase is alive."""

    if plan_dir is None:
        return None
    candidates = [plan_dir / "state.json"]
    try:
        candidates.extend(plan_dir.glob("execution_batch_*.json"))
    except OSError:
        pass
    newest: float | None = None
    for path in candidates:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def _status(
    plan: str,
    cwd: Path | None = None,
    *,
    timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
    progress_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"cwd": cwd, "timeout": timeout}
    if progress_env:
        kwargs["progress_env"] = progress_env
    code, out, err = _run_megaplan(["status", "--plan", plan], **kwargs)
    if code != 0:
        raise RuntimeError(f"megaplan status failed (exit {code}): {err.strip() or out.strip()}")
    return json.loads(out)


def _has_valid_next(status: dict[str, Any], action: str) -> bool:
    return action in (status.get("valid_next") or [])


def _phase_command(next_step: str) -> list[str]:
    """Translate a `next_step` from status into the CLI args that run it.

    Most phases are one-to-one: next_step == command. Execute adds the
    destructive + user-approved flags because auto-mode implies both.

    Multi-token values like ``"override add-note"`` must be split into
    ``["override", "add-note"]`` so argparse sees the sub-subcommand —
    otherwise the whole string is passed as a single positional and
    argparse rejects it with `invalid choice`.
    """
    if next_step == "execute":
        # --retry-blocked-tasks is safe to pass on every iteration. Within a
        # single auto session, tasks that report status=blocked terminate the
        # auto loop via STATE_AWAITING_HUMAN (see eb4ac447), so re-dispatch
        # only happens on a *fresh* `megaplan auto` invocation — which is the
        # user's signal that any external prereq has been resolved and stale
        # blocked statuses should be retried instead of short-circuiting.
        # If there are no blocked tasks, the flag is a no-op.
        return [
            "execute",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
        ]
    if next_step == "feedback":
        # The auto driver must dispatch the *workflow* operation, not the
        # default "edit" operation — otherwise the handler would open $EDITOR
        # and block on human input.  "feedback workflow" scaffolds the file
        # non-interactively and transitions reviewed → done.
        return ["feedback", "workflow"]
    return shlex.split(next_step)


def _resolve_plan_dir(plan: str, cwd: Path | None) -> Path | None:
    """Best-effort resolution of legacy or canonical orphan plan roots near ``cwd``."""
    return find_plan_dir(cwd or Path.cwd(), plan)





def _latest_versioned_artifact(plan_dir: Path | None, prefix: str) -> Path | None:
    """Return the highest-numbered versioned artifact (``<prefix>v<N>.json``)."""
    if plan_dir is None:
        return None
    try:
        candidates = [
            p for p in plan_dir.iterdir()
            if p.name.startswith(prefix) and p.suffix == ".json"
        ]
    except OSError:
        return None
    if not candidates:
        return None

    def _version(path: Path) -> int:
        stem = path.stem  # drop .json
        try:
            return int(stem.split("v")[-1])
        except (ValueError, IndexError):
            return -1

    candidates.sort(key=_version)
    return candidates[-1] if candidates else None


def _read_unresolved_flag_ids(plan_dir: Path | None) -> list[str]:
    """Best-effort list of unresolved flag IDs from the latest gate signals.

    Falls back to the latest critique artifact if no gate_signals_v*.json
    exists yet (e.g. ESCALATE arrived from a non-gate path). Returns ``[]``
    on any read/parse error — callers must treat that as "no flags known"
    and synthesize a generic note rather than crashing.
    """
    sources = [
        _latest_versioned_artifact(plan_dir, "gate_signals_v"),
        _latest_versioned_artifact(plan_dir, "critique_v"),
    ]
    for path in sources:
        if path is None:
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        # gate_signals_v*.json uses key "unresolved_flags"; critique_v*.json
        # uses "flags". Either may be missing on truncated artifacts.
        for key in ("unresolved_flags", "flags"):
            flags = payload.get(key)
            if isinstance(flags, list) and flags:
                ids = [
                    str(f.get("id"))
                    for f in flags
                    if isinstance(f, dict) and isinstance(f.get("id"), str) and f.get("id")
                ]
                if ids:
                    return ids
    return []


def _synthesize_add_note_text(
    plan_dir: Path | None,
    *,
    iteration: int,
    attempt: int,
) -> str:
    """Build a non-empty `--note` string for an unattended add-note dispatch.

    The orchestrator only reaches `override add-note` when the
    critique→revise→gate loop has failed to converge and the gate has
    punted to a human. Without a human, the auto-driver records why it
    is advancing anyway: the unresolved flag IDs (if readable) and the
    iteration/attempt counters so audits can spot loops.
    """
    flag_ids = _read_unresolved_flag_ids(plan_dir)
    if flag_ids:
        # Cap the inline list — strict-notes mode rejects giant blobs.
        head = ", ".join(flag_ids[:10])
        suffix = f" (+{len(flag_ids) - 10} more)" if len(flag_ids) > 10 else ""
        flags_part = f"; unresolved=[{head}{suffix}]"
    else:
        flags_part = "; unresolved=[unknown]"
    return (
        f"auto: critique loop unresolved at iter {iteration} "
        f"(add-note attempt {attempt}){flags_part}; advancing without human"
    )


def _build_override_add_note_command(
    plan: str,
    plan_dir: Path | None,
    *,
    iteration: int,
    attempt: int,
) -> list[str]:
    """Construct the full argv for ``megaplan override add-note ...``.

    Matches the CLI contract enforced by ``cli.py::_validate_override_args``:
    requires both ``--plan`` and a non-empty ``--note``. Without ``--note``
    the subcommand fails with ``invalid_args`` and the auto-driver retries
    the same broken call until stall detection kills the run.
    """
    note = _synthesize_add_note_text(plan_dir, iteration=iteration, attempt=attempt)
    return ["override", "add-note", "--plan", plan, "--note", note]


def _sum_history_cost_usd(plan_dir: Path | None) -> float:
    if plan_dir is None:
        return 0.0

    try:
        with (plan_dir / "state.json").open(encoding="utf-8") as handle:
            state_data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return 0.0

    if not isinstance(state_data, dict):
        return 0.0

    total = 0.0
    for entry in state_data.get("history") or []:
        if not isinstance(entry, dict):
            continue
        try:
            total += float(entry.get("cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 6)


def _get_review_marker(plan_dir: Path | None) -> float | None:
    """Return a monotonically-advancing marker for the current review cycle.

    Uses ``review.json`` mtime — each completed review phase rewrites the
    file, so the mtime bumps once per review cycle. This is race-free
    enough for stall detection: the driver only checks the marker between
    iterations, and mtime granularity (~1s on APFS/ext4) is finer than the
    minimum review runtime.

    Returns ``None`` when no marker is available (plan dir missing, review
    not yet run, or stat failed) — the caller must treat ``None == None``
    as "no progress observed" and fall through to plain stall detection.
    """
    if plan_dir is None:
        return None
    review_path = plan_dir / "review.json"
    try:
        return review_path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return None


def _latest_artifact_name(plan_dir: Path | None) -> str | None:
    if plan_dir is None:
        return None
    try:
        artifact = PlanRepository.from_plan_dir(plan_dir).latest_execution_batch_artifact()
    except (OSError, RuntimeError, ValueError):
        return None
    if artifact is None:
        return None
    try:
        return artifact.relative_to(plan_dir).as_posix()
    except ValueError:
        return artifact.name


def _phase_result_signature(plan_dir: Path | None) -> tuple[int, int] | None:
    if plan_dir is None:
        return None
    try:
        stat = (plan_dir / "phase_result.json").stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _record_lifecycle_failure(
    *,
    plan_dir: Path | None,
    kind: str,
    message: str,
    current_state: str | None = None,
    phase: str | None,
    resume_cursor: dict[str, Any] | None,
    last_artifact: str | None = None,
    suggested_action: str | None = None,
    metadata: dict[str, Any] | None = None,
    progress_emitter: Any | None = None,
) -> None:
    if plan_dir is None:
        return
    if current_state is None:
        # Driver-lifecycle exit (iteration cap, stall, cost cap, etc.): record
        # the failure event for audit + resume_cursor, but preserve the plan's
        # actual current_state — the driver giving up doesn't terminate the plan.
        try:
            state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            if isinstance(state_data, dict):
                current_state = state_data.get("current_state") or STATE_BLOCKED
            else:
                current_state = STATE_BLOCKED
        except (OSError, json.JSONDecodeError, ValueError):
            current_state = STATE_BLOCKED
    failure_details: dict[str, Any] | None = None
    try:
        failure_details = PlanRepository.from_plan_dir(plan_dir).record_lifecycle_failure(
            kind=kind,
            message=message,
            current_state=current_state,
            phase=phase,
            resume_cursor=resume_cursor,
            last_artifact=last_artifact,
            suggested_action=suggested_action,
            metadata=metadata,
        )
    except (OSError, RuntimeError, ValueError):
        return
    if progress_emitter is not None and failure_details is not None:
        if current_state == STATE_BLOCKED:
            progress_emitter.execution_blocked(summary=message, **failure_details)
        else:
            progress_emitter.plan_failed(summary=message, **failure_details)


def _reconcile_latest_execution_batch(plan_dir: Path | None) -> dict[str, Any] | None:
    if plan_dir is None:
        return None
    try:
        with (plan_dir / "state.json").open(encoding="utf-8") as handle:
            state_data = json.load(handle)
        if not isinstance(state_data, dict):
            return {"reconciled": False, "reason": "state payload was not an object"}
        from megaplan.execute.core import reconcile_latest_execution_batch

        return reconcile_latest_execution_batch(plan_dir, state_data)
    except Exception as error:
        return {"reconciled": False, "reason": str(error)}


def _recover_execute_callback_failure_state(plan_dir: Path | None) -> bool:
    """Restore a successfully executed plan after an external callback failure."""
    if plan_dir is None:
        return False
    state_path = plan_dir / "state.json"
    try:
        with state_path.open(encoding="utf-8") as handle:
            state_data = json.load(handle)
        if not isinstance(state_data, dict):
            return False
        if state_data.get("current_state") != STATE_FAILED:
            return False
        latest_failure = state_data.get("latest_failure")
        if not isinstance(latest_failure, dict):
            return False
        if latest_failure.get("kind") != "phase_callback_failed":
            return False
        if latest_failure.get("phase") != "execute":
            return False
        reconciliation = latest_failure.get("metadata", {}).get("checkpoint_reconciliation")
        if not isinstance(reconciliation, dict) or reconciliation.get("reconciled") is not True:
            return False
        history = state_data.get("history")
        if not isinstance(history, list):
            return False
        last_execute = next(
            (
                entry for entry in reversed(history)
                if isinstance(entry, dict) and entry.get("step") == "execute"
            ),
            None,
        )
        if not isinstance(last_execute, dict):
            return False
        execute_result = last_execute.get("result")
        if execute_result not in {"success", "blocked"}:
            return False
        if not (plan_dir / "execution.json").exists():
            return False
        state_data["current_state"] = (
            STATE_EXECUTED if execute_result == "success" else STATE_FINALIZED
        )
        state_data.pop("active_step", None)
        state_path.write_text(json.dumps(state_data, indent=2) + "\n", encoding="utf-8")
        return True
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return False


# Output artifacts written incrementally by long-running phase workers. When
# the worker dies mid-write these files survive on disk but lack the terminal
# fields the recovery paths look for. The next dispatch must start clean —
# otherwise critique's `_recover_valid_critique_output` (and friends) can
# treat the half-written file as authoritative and short-circuit the rerun.
_PHASE_OUTPUT_QUARANTINE: dict[str, tuple[str, ...]] = {
    "critique": ("critique_output.json",),
    "plan": ("plan_output.json",),
    "revise": ("revise_output.json",),
    "gate": ("gate_output.json",),
    "finalize": ("finalize_output.json",),
    "review": ("review_output.json",),
    "execute": ("execute_output.json",),
}


def _quarantine_phase_outputs(plan_dir: Path, step: str) -> list[str]:
    """Rename half-written `<step>_output.json` files so a re-dispatched
    phase can't be fooled into "recovering" malformed worker output.

    Returns the list of artifact names quarantined (for logging).
    """
    quarantined: list[str] = []
    artifacts = _PHASE_OUTPUT_QUARANTINE.get(step)
    if not artifacts:
        return quarantined
    for name in artifacts:
        source = plan_dir / name
        if not source.exists():
            continue
        # Treat zero-byte AND structurally-empty payloads as corpses worth
        # quarantining. An output file that holds a complete payload is
        # rare in this orphan path, but we leave it alone — the handler's
        # own recover logic will accept or reject it normally.
        try:
            text = source.read_text(encoding="utf-8")
        except OSError:
            continue
        stripped = text.strip()
        if stripped not in ("", "{}", "[]"):
            try:
                payload = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                payload = None
            # Non-empty parseable dicts/lists are left in place — only the
            # genuinely-empty corpses are quarantined.
            if isinstance(payload, dict) and payload:
                continue
            if isinstance(payload, list) and payload:
                continue
        target = plan_dir / f"{name}.orphaned"
        try:
            source.replace(target)
        except OSError:
            continue
        quarantined.append(name)
    return quarantined


def _clear_orphaned_active_step(plan_dir: Path | None, expected_step: str) -> bool:
    """Strip an orphaned ``active_step`` from ``state.json`` in place.

    Returns True iff the cleanup actually wrote a change. The expected step
    name is used purely as a safety check — if state.json's ``active_step``
    no longer matches (because some other actor cleared it), we leave it
    alone rather than racing with a healthy phase.
    """
    if plan_dir is None:
        return False
    state_path = plan_dir / "state.json"
    try:
        with state_path.open(encoding="utf-8") as handle:
            state_data = json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(state_data, dict):
        return False
    current_active = state_data.get("active_step")
    if not isinstance(current_active, dict):
        return False
    recorded_step = current_active.get("step")
    if recorded_step != expected_step:
        return False
    state_data.pop("active_step", None)
    quarantined = _quarantine_phase_outputs(plan_dir, expected_step)
    if quarantined:
        meta = state_data.setdefault("meta", {})
        history = meta.setdefault("orphan_recoveries", [])
        if isinstance(history, list):
            history.append({
                "step": expected_step,
                "quarantined": list(quarantined),
            })
    try:
        state_path.write_text(json.dumps(state_data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def drive(
    plan: str,
    *,
    cwd: Path | None = None,
    stall_threshold: int = DEFAULT_STALL_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_review_rework_cycles: int = DEFAULT_MAX_REVIEW_REWORK_CYCLES,
    max_cost_usd: float | None = None,
    max_context_retries: int = DEFAULT_MAX_CONTEXT_RETRIES,
    max_blocked_retries: int = DEFAULT_MAX_BLOCKED_RETRIES,
    max_add_note_attempts: int = DEFAULT_MAX_ADD_NOTE_ATTEMPTS,
    on_escalate: str = "force-proceed",
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS,
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS,
    phase_idle_timeout: float = DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    progress_env: dict[str, str] | None = None,
    writer=sys.stdout.write,
) -> DriverOutcome:
    """Drive ``plan`` to completion.

    Returns a DriverOutcome with a terminal status. The writer is used for
    human-readable progress; structured events are collected on the outcome.
    """

    if on_escalate not in ESCALATE_ACTIONS:
        raise ValueError(f"on_escalate must be one of {ESCALATE_ACTIONS}")

    events: list[dict[str, Any]] = []
    last_state: str | None = None
    stall_count = 0
    last_phase: str | None = None
    context_retry_count = 0
    blocked_retry_count = 0
    # Consecutive `override add-note` dispatches that failed (non-zero exit).
    # Reset on any successful add-note OR when the next_step changes — only a
    # repeating add-note→fail loop should trip the escalation.
    add_note_failures = 0

    # Rework-cycle tracking. When review returns `needs_rework`, the plan
    # ping-pongs `finalized ↔ executed ↔ finalized` while execute re-runs
    # batches. From the driver's naive view that looks like a stall, but
    # every completed review rewrites `review.json`, so its mtime is a
    # reliable "forward progress" marker — each advance means a real
    # review cycle finished since we last observed the state.
    plan_dir = _resolve_plan_dir(plan, cwd)
    if plan_dir is not None:
        emit_event(EventKind.INIT, plan_dir=plan_dir, payload={"plan_name": plan})
    from megaplan.orchestration.progress import ProgressEmitter
    progress_emitter = ProgressEmitter.from_env(progress_env)
    last_review_marker = _get_review_marker(plan_dir)
    rework_cycles_observed = 0

    def _record_failure(**kwargs: Any) -> None:
        _record_lifecycle_failure(**kwargs, progress_emitter=progress_emitter)

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[auto {plan}] {msg}\n")

    def _run_phase(cmd: list[str], next_step: str) -> tuple[int, str, str, object | None]:
        before_phase_result = _phase_result_signature(plan_dir)
        run_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "timeout": phase_timeout,
            "idle_timeout": phase_idle_timeout,
            "liveness_plan_dir": plan_dir,
        }
        if progress_env:
            run_kwargs["progress_env"] = progress_env
        try:
            code, out, err = _run_megaplan(cmd, **run_kwargs)
        except TypeError as error:
            # Several unit tests monkeypatch _run_megaplan with the pre-idle-timeout
            # signature. Keep that surface compatible without weakening the real path.
            if "idle_timeout" not in str(error) and "liveness_plan_dir" not in str(error):
                raise
            run_kwargs.pop("idle_timeout", None)
            run_kwargs.pop("liveness_plan_dir", None)
            code, out, err = _run_megaplan(cmd, **run_kwargs)

        # Read the structured phase_result.json only when this command actually
        # produced it. A stale result from the previous phase must not mask a
        # current phase failure or the driver can loop on the same state forever.
        result: object | None = None
        after_phase_result = _phase_result_signature(plan_dir)
        if after_phase_result is not None and after_phase_result != before_phase_result:
            candidate = read_phase_result(plan_dir)
            if candidate is not None and getattr(candidate, "phase", None) == next_step:
                result = candidate

        if result is not None:
            return code, out, err, result

        # Synthesize a PhaseResult when the file is missing
        if code == PHASE_TIMEOUT_EXIT_CODE:
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.timeout.value,
            )
        elif "idle timed out" in (err or ""):
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.timeout.value,
            )
        elif CONTEXT_EXHAUSTION_FRAGMENT.lower() in ((out or "") + (err or "")).lower():
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.context_exhausted.value,
            )
        elif next_step not in PHASE_NAMES:
            # Non-phase commands (e.g. 'override add-note') — no synthesis
            result = None
        elif code == 0:
            # Subprocess exited cleanly but didn't write phase_result.json.
            # Synthesis as 'success' — in production all 8 handlers now emit,
            # so this branch only fires for legacy plans and test mocks.
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.success.value,
            )
        else:
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.internal_error.value,
            )

        return code, out, err, result

    def _outcome(
        status: str,
        *,
        final_state: str,
        iterations: int,
        reason: str = "",
        last_phase: str | None = None,
        blocking_reasons: list[str] | None = None,
    ) -> DriverOutcome:
        return DriverOutcome(
            status=status,
            plan=plan,
            final_state=final_state,
            iterations=iterations,
            reason=reason,
            last_phase=last_phase,
            events=events,
            total_cost_usd=_sum_history_cost_usd(plan_dir),
            cost_cap_usd=max_cost_usd,
            context_retries_used=context_retry_count,
            max_context_retries=max_context_retries,
            blocked_retries_used=blocked_retry_count,
            max_blocked_retries=max_blocked_retries,
            blocking_reasons=list(blocking_reasons or []),
        )

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        try:
            status_kwargs: dict[str, Any] = {"cwd": cwd, "timeout": status_timeout}
            if progress_env:
                status_kwargs["progress_env"] = progress_env
            status = _status(plan, **status_kwargs)
        except (RuntimeError, json.JSONDecodeError) as error:
            log(f"status lookup failed: {error}")
            _record_failure(
                plan_dir=plan_dir,
                kind="status_lookup_failed",
                message=str(error),
                current_state=None,
                phase=last_phase,
                resume_cursor={"phase": last_phase or "status", "retry_strategy": "rerun_status"},
                suggested_action="Inspect state.json and rerun status before resuming automation.",
                metadata={"iteration": iteration},
            )
            return _outcome(
                "failed",
                final_state=last_state or "unknown",
                iterations=iteration,
                reason=str(error),
                last_phase=last_phase,
            )

        state = status.get("state", "")

        if max_cost_usd is not None:
            cumulative = _sum_history_cost_usd(plan_dir)
            if cumulative > max_cost_usd:
                log(
                    f"cost cap exceeded after phase '{last_phase}': "
                    f"total_cost_usd={cumulative} > cost_cap_usd={max_cost_usd}",
                    total_cost_usd=cumulative,
                    cost_cap_usd=max_cost_usd,
                )
                _record_failure(
                    plan_dir=plan_dir,
                    kind="cost_cap_exceeded",
                    message=f"Cost cap exceeded: {cumulative} > {max_cost_usd}",
                    current_state=None,
                    phase=last_phase,
                    resume_cursor={"phase": last_phase or "status", "retry_strategy": "increase_cap_or_resume"},
                    suggested_action="Increase the cost cap or resume the plan after reviewing spend.",
                    metadata={"total_cost_usd": cumulative, "cost_cap_usd": max_cost_usd, "iteration": iteration},
                )
                return _outcome(
                    "cost_cap_exceeded",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"cost cap exceeded after phase '{last_phase}': "
                        f"{cumulative} > {max_cost_usd}"
                    ),
                    last_phase=last_phase,
                )

        next_step = status.get("next_step")
        valid_next = status.get("valid_next") or []

        log(
            f"iter {iteration} state={state} next={next_step} valid_next={valid_next}",
            iteration=iteration,
            state=state,
            next_step=next_step,
            valid_next=valid_next,
        )

        if state == STATE_FAILED and _recover_execute_callback_failure_state(plan_dir):
            log("recovered execute state after phase-complete callback failure; resuming")
            continue

        # Terminal: plan reached a final state (or automation-terminal).
        if state in AUTOMATION_TERMINAL_STATES and not (state == STATE_BLOCKED and valid_next):
            if state == STATE_AWAITING_HUMAN:
                log("plan awaiting human verification — automation stopping")
                return _outcome(
                    "awaiting_human",
                    final_state=state,
                    iterations=iteration,
                    reason="plan has criteria requiring human verification",
                    last_phase=last_phase,
                )
            if state == STATE_TIEBREAKER_PENDING:
                log("tiebreaker pending — run 'megaplan tiebreaker-run --plan <name>' to execute")
                return _outcome(
                    "tiebreaker_pending",
                    final_state=state,
                    iterations=iteration,
                    reason="gate recommended tiebreaker — researcher/challenger run needed",
                    last_phase=last_phase,
                )
            if state == STATE_TIEBREAKER_READY:
                log("tiebreaker ready — run 'megaplan tiebreaker decide --plan <name>' to resolve")
                return _outcome(
                    "tiebreaker_ready",
                    final_state=state,
                    iterations=iteration,
                    reason="tiebreaker synthesis complete — awaiting human decision",
                    last_phase=last_phase,
                )
            if state == STATE_PAUSED:
                log("plan paused — automation stopping until resumed")
                return _outcome(
                    "paused",
                    final_state=state,
                    iterations=iteration,
                    reason="plan is paused and must be resumed by the user",
                    last_phase=last_phase,
                )
            terminal_status = {
                STATE_DONE: "done",
                STATE_ABORTED: "aborted",
                STATE_FAILED: "failed",
                STATE_BLOCKED: "blocked",
                STATE_CANCELLED: "cancelled",
            }.get(state, state)
            log(f"terminal state reached: {state}")
            # Emit plan_finished or plan_aborted
            if plan_dir is not None:
                try:
                    if terminal_status == "aborted":
                        emit_event(EventKind.PLAN_ABORTED, plan_dir=plan_dir, payload={"state": state})
                    elif terminal_status == "done":
                        emit_event(EventKind.PLAN_FINISHED, plan_dir=plan_dir, payload={"state": state})
                except Exception:
                    pass
            return _outcome(
                terminal_status,
                final_state=state,
                iterations=iteration,
                reason=f"plan entered terminal state '{state}'",
                last_phase=last_phase,
            )

        active_step = status.get("active_step")
        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") == "wait"
        ):
            active_name = active_step.get("step") or next_step or "unknown"
            reason = active_step.get("recommended_action_reason") or "active step is still healthy"
            log(f"active step '{active_name}' still running — waiting: {reason}")
            if poll_sleep > 0:
                time.sleep(poll_sleep)
            iteration -= 1  # healthy wait — don't consume iteration budget
            continue

        # Orphaned active_step: the recorded worker is dead (or stale and
        # unlocked) but state.json still claims a phase is running. Without
        # this guard the driver would either spin-poll a dead phase or
        # treat the corpse as authoritative on status / health. Clear it
        # before dispatching anything, and quarantine the half-written
        # output file from that phase so a fresh dispatch can't be fooled
        # into "recovering" malformed output.
        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") in {
                "resume_or_recover",
                "rerun_same_step",
                "rerun_execute",
                "terminate_idle_step",
            }
        ):
            orphan_step = active_step.get("step") or next_step or "unknown"
            reason = (
                active_step.get("recommended_action_reason")
                or "active step is orphaned (worker dead or stale and unlocked)"
            )
            log(
                f"active step '{orphan_step}' is orphaned — clearing before dispatch: {reason}",
                orphan_step=orphan_step,
                recommended_action=active_step.get("recommended_action"),
                health=active_step.get("health"),
            )
            _clear_orphaned_active_step(plan_dir, orphan_step)

        # Review-cycle progress: a fresh review.json means a real review
        # pass completed since the last iteration. This counts as forward
        # progress even when `state` looks unchanged (finalized→executed→
        # finalized during a needs_rework loop) — reset the stall counter
        # so execute has a full rework pass before tripping stall detection.
        current_review_marker = _get_review_marker(plan_dir)
        if (
            current_review_marker is not None
            and current_review_marker != last_review_marker
        ):
            if last_review_marker is not None:
                rework_cycles_observed += 1
                log(
                    f"review.json updated — rework cycle {rework_cycles_observed} "
                    f"observed, resetting stall counter",
                    rework_cycles_observed=rework_cycles_observed,
                )
                stall_count = 0
            last_review_marker = current_review_marker

            if (
                rework_cycles_observed > max_review_rework_cycles + 1
                and state != "reviewed"
                and next_step != "feedback"
            ):
                # Review handler has its own internal cap (see
                # handlers.py::handle_review — force-proceeds to done when
                # prior_rework_count hits max_review_rework_cycles). This
                # driver cap is a belt-and-braces guard against config drift
                # or unexpected loops the handler didn't catch.
                log(
                    f"observed {rework_cycles_observed} rework cycles "
                    f"(cap={max_review_rework_cycles}) — bailing"
                )
                return _outcome(
                    "stalled",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"exceeded review rework cap "
                        f"({rework_cycles_observed} cycles > "
                        f"{max_review_rework_cycles}) — review keeps "
                        "returning needs_rework without resolving"
                    ),
                    last_phase=last_phase,
                )

        # Stall detection: same state for stall_threshold+ iterations.
        if state == last_state:
            stall_count += 1
            if stall_count >= stall_threshold:
                # Distinguish an all-blocked outcome from a generic stall.
                # When execute reports every pending task as `blocked`, the
                # problem is a poisoned session or genuinely broken env —
                # supervisors should react differently (e.g. retry with a
                # fresh session) rather than just restart and loop.
                progress = status.get("progress") or {}
                tasks_blocked = int(progress.get("tasks_blocked", 0) or 0)
                tasks_pending = int(progress.get("tasks_pending", 0) or 0)
                if tasks_blocked > 0 and tasks_pending == 0:
                    log(
                        f"all pending tasks reported status=blocked "
                        f"({tasks_blocked} blocked) — treating as poisoned outcome"
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="tasks_blocked",
                        message="all pending tasks reported blocked",
                        current_state=STATE_BLOCKED,
                        phase=last_phase,
                        resume_cursor={"phase": last_phase or "execute", "retry_strategy": "fresh_session"},
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Resume with a fresh worker session after reviewing blocked task reasons.",
                        metadata={"tasks_blocked": tasks_blocked, "iteration": iteration},
                    )
                    return _outcome(
                        "blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "all tasks reported blocked — workers may be poisoned "
                            "or the environment may genuinely be broken"
                        ),
                        last_phase=last_phase,
                    )
                log(f"stalled at state={state} for {stall_count} iterations")
                _record_failure(
                    plan_dir=plan_dir,
                    kind="stalled",
                    message=f"stalled at '{state}' for {stall_count} iterations",
                    current_state=None,
                    phase=last_phase,
                    resume_cursor={"phase": last_phase or str(next_step or "status"), "retry_strategy": "manual_review"},
                    suggested_action="Review the plan state before resuming automation.",
                    metadata={"stall_count": stall_count, "iteration": iteration},
                )
                return _outcome(
                    "stalled",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"stalled at '{state}' for {stall_count} iterations — "
                        "manual intervention required"
                    ),
                    last_phase=last_phase,
                )
        else:
            stall_count = 0
            # Emit state_transition on state change
            if plan_dir is not None and last_state is not None and state != last_state:
                try:
                    emit_event(
                        EventKind.STATE_TRANSITION,
                        plan_dir=plan_dir,
                        payload={"from": last_state, "to": state},
                    )
                except Exception:
                    pass
            last_state = state

        # Escalation: no phase to run but overrides are available.
        if not next_step:
            if _has_valid_next(status, "override force-proceed"):
                if on_escalate == "force-proceed":
                    log("gate escalated — force-proceeding (per on_escalate=force-proceed)")
                    run_kwargs: dict[str, Any] = {"cwd": cwd, "timeout": status_timeout}
                    if progress_env:
                        run_kwargs["progress_env"] = progress_env
                    code, out, err = _run_megaplan(
                        [
                            "override",
                            "force-proceed",
                            "--plan",
                            plan,
                            "--reason",
                            "megaplan auto: escalate → force-proceed",
                        ],
                        **run_kwargs,
                    )
                    if code != 0:
                        log(f"force-proceed failed (exit {code}): {err.strip() or out.strip()}")
                        # Strict-notes invariants surface as specific error
                        # codes — when we see them the right move is to
                        # surrender to the human rather than treat the
                        # subprocess failure as a generic auto-driver fault.
                        combined_text = f"{out}\n{err}"
                        strict_signals = (
                            "unabsorbed_notes_exist",
                            "escalate_requires_user_approval",
                        )
                        if any(signal in combined_text for signal in strict_signals):
                            _record_failure(
                                plan_dir=plan_dir,
                                kind="human_required",
                                message="force-proceed blocked by strict-notes",
                                current_state=STATE_BLOCKED,
                                phase="override",
                                resume_cursor={"phase": "override", "retry_strategy": "human_approval"},
                                suggested_action="Address strict notes or approve escalate before resuming.",
                                metadata={"signals": [signal for signal in strict_signals if signal in combined_text]},
                            )
                            return _outcome(
                                "human_required",
                                final_state=state,
                                iterations=iteration,
                                reason=(
                                    "force-proceed blocked by strict-notes — human "
                                    "required to address notes or approve escalate"
                                ),
                                last_phase=last_phase,
                            )
                        _record_failure(
                            plan_dir=plan_dir,
                            kind="override_failed",
                            message=f"override force-proceed exited {code}",
                            current_state=STATE_FAILED,
                            phase="override",
                            resume_cursor={"phase": "override", "retry_strategy": "rerun_override"},
                            suggested_action="Inspect override output before resuming.",
                            metadata={"exit_code": code, "stderr": err.strip(), "stdout": out.strip()[-400:]},
                        )
                        return _outcome(
                            "failed",
                            final_state=state,
                            iterations=iteration,
                            reason=f"override force-proceed exited {code}",
                            last_phase=last_phase,
                        )
                    continue
                if on_escalate == "abort":
                    log("gate escalated — aborting (per on_escalate=abort)")
                    run_kwargs = {"cwd": cwd, "timeout": status_timeout}
                    if progress_env:
                        run_kwargs["progress_env"] = progress_env
                    _run_megaplan(
                        [
                            "override",
                            "abort",
                            "--plan",
                            plan,
                            "--reason",
                            "megaplan auto: escalate → abort",
                        ],
                        **run_kwargs,
                    )
                    return _outcome(
                        "aborted",
                        final_state=state,
                        iterations=iteration,
                        reason="gate escalated and on_escalate=abort",
                        last_phase=last_phase,
                    )
                # on_escalate == "fail"
                log("gate escalated — failing (per on_escalate=fail)")
                _record_failure(
                    plan_dir=plan_dir,
                    kind="gate_escalated",
                    message="gate escalated and on_escalate=fail",
                    current_state=STATE_BLOCKED,
                    phase="gate",
                    resume_cursor={"phase": "gate", "retry_strategy": "human_decision"},
                    suggested_action="Resolve the gate escalation before resuming.",
                    metadata={"iteration": iteration},
                )
                return _outcome(
                    "escalated",
                    final_state=state,
                    iterations=iteration,
                    reason="gate escalated and on_escalate=fail — human required",
                    last_phase=last_phase,
                )
            log(f"no next_step and no override available (valid_next={valid_next})")
            _record_failure(
                plan_dir=plan_dir,
                kind="no_next_step",
                message="no next_step and no override available",
                current_state=STATE_FAILED,
                phase=None,
                resume_cursor={"phase": "status", "retry_strategy": "repair_state"},
                suggested_action="Repair state.json or workflow mapping before resuming.",
                metadata={"valid_next": valid_next, "iteration": iteration},
            )
            return _outcome(
                "failed",
                final_state=state,
                iterations=iteration,
                reason="no next_step and no override available",
                last_phase=last_phase,
            )

        # Run the next phase.
        # Special-case `override add-note`: the CLI requires a non-empty
        # ``--note`` argument, so we synthesize one from the latest gate
        # signals / critique flags. After ``max_add_note_attempts``
        # consecutive failed dispatches, fall through to ``override
        # force-proceed`` — that's the safety-net escape valve when
        # human intervention isn't available (Track B fallback).
        if next_step == "override add-note":
            if (
                max_add_note_attempts >= 0
                and add_note_failures >= max_add_note_attempts
                and _has_valid_next(status, "override force-proceed")
            ):
                log(
                    f"override add-note failed {add_note_failures} times — "
                    "escalating to override force-proceed",
                    add_note_failures=add_note_failures,
                    max_add_note_attempts=max_add_note_attempts,
                )
                cmd = [
                    "override",
                    "force-proceed",
                    "--plan",
                    plan,
                    "--reason",
                    (
                        f"megaplan auto: {add_note_failures} add-note retries "
                        "failed, forcing proceed"
                    ),
                ]
                last_phase = "override force-proceed"
                add_note_failures = 0
            else:
                cmd = _build_override_add_note_command(
                    plan,
                    plan_dir,
                    iteration=iteration,
                    attempt=add_note_failures + 1,
                )
                last_phase = next_step
        else:
            # Any non-add-note dispatch resets the add-note failure counter —
            # only a repeating add-note→fail loop should trigger escalation.
            add_note_failures = 0
            cmd = _phase_command(next_step) + ["--plan", plan]
            last_phase = next_step
        log(f"running: megaplan {' '.join(cmd)}", phase=next_step, timeout=phase_timeout)
        if plan_dir is not None:
            try:
                emit_event(EventKind.PHASE_START, plan_dir=plan_dir, phase=next_step, payload={"phase": next_step})
            except Exception:
                pass
        code, out, err, result = _run_phase(cmd, next_step)
        if next_step == "override add-note" and last_phase == "override add-note":
            if code != 0:
                add_note_failures += 1
            else:
                add_note_failures = 0
        # Context-exhaustion retry loop: detect via PhaseResult.exit_kind,
        # not by string-matching captured stdout.
        if max_context_retries > 0:
            while (
                next_step == "execute"
                and result is not None
                and getattr(result, "exit_kind", None) == ExitKind.context_exhausted.value
            ):
                if context_retry_count >= max_context_retries:
                    log(
                        f"context exhaustion retry cap reached ({max_context_retries}) — bailing",
                        context_retries_used=context_retry_count,
                        max_context_retries=max_context_retries,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="context_retry_exhausted",
                        message=f"context exhaustion retry cap reached ({context_retry_count}/{max_context_retries})",
                        current_state=None,
                        phase=next_step,
                        resume_cursor={"phase": next_step, "retry_strategy": "fresh_session"},
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Resume execute with a fresh worker context.",
                        metadata={"context_retries_used": context_retry_count, "max_context_retries": max_context_retries},
                    )
                    return _outcome(
                        "context_retry_exhausted",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            f"context exhaustion retry cap reached "
                            f"({context_retry_count}/{max_context_retries})"
                        ),
                        last_phase=last_phase,
                    )
                log(
                    "context exhaustion detected — retrying execute with "
                    f"--fresh (retry {context_retry_count + 1}/{max_context_retries})",
                    context_retries_used=context_retry_count,
                    max_context_retries=max_context_retries,
                    next_context_retry=context_retry_count + 1,
                )
                context_retry_count += 1
                if "--fresh" not in cmd:
                    cmd = [*cmd, "--fresh"]
                code, out, err, result = _run_phase(cmd, next_step)

        # Timeout detection: read from PhaseResult.exit_kind, not exit code.
        if result is not None and getattr(result, "exit_kind", None) == ExitKind.timeout.value:
            log(f"phase '{next_step}' timed out — stall detection will enforce the cap")
            _record_failure(
                plan_dir=plan_dir,
                kind="phase_timeout",
                message=f"phase '{next_step}' timed out after {phase_timeout}s",
                current_state=STATE_FAILED,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Investigate the timed-out phase and resume from the phase cursor.",
                metadata={"timeout_seconds": phase_timeout, "idle_timeout_seconds": phase_idle_timeout, "iteration": iteration},
            )
        elif result is not None and getattr(result, "exit_kind", None) == ExitKind.external_error.value:
            external_error = getattr(result, "external_error", None)
            provider = getattr(external_error, "provider", "unknown")
            error_kind = getattr(external_error, "error_kind", "unknown")
            message = getattr(external_error, "message", "")
            status_code = getattr(external_error, "status_code", None)
            retry_after_s = getattr(external_error, "retry_after_s", None)
            code_hint = f" HTTP {status_code}" if status_code is not None else ""
            retry_hint = (
                f" retry_after={retry_after_s}s"
                if retry_after_s is not None
                else ""
            )
            log(
                f"phase '{next_step}' external_error [{provider}] "
                f"{error_kind}{code_hint}{retry_hint}: {message[:200]}"
            )
            _record_failure(
                plan_dir=plan_dir,
                kind="external_error",
                message=(
                    f"phase '{next_step}' external dependency failure: "
                    f"[{provider}] {error_kind}{code_hint}{retry_hint}"
                ),
                current_state=STATE_BLOCKED,
                phase=next_step,
                resume_cursor={
                    "phase": next_step,
                    "retry_strategy": (
                        "wait_and_retry"
                        if retry_after_s is not None and retry_after_s > 0
                        else "check_provider_and_retry"
                    ),
                },
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action=(
                    f"External provider '{provider}' returned {error_kind}. "
                    "Verify API key/quota/balance and retry."
                    + (
                        f" Wait {retry_after_s}s before retrying."
                        if retry_after_s is not None
                        else ""
                    )
                ),
                metadata={
                    "provider": provider,
                    "error_kind": error_kind,
                    "status_code": status_code,
                    "retry_after_s": retry_after_s,
                    "exit_code": code,
                    "iteration": iteration,
                },
            )
        elif result is not None and getattr(result, "exit_kind", None) == ExitKind.internal_error.value:
            # Don't bail immediately — megaplan often records a partial failure
            # in state.json and the next status() reveals a recoverable valid_next.
            # Stall detection will still kill infinite loops.
            log(f"phase '{next_step}' exited with internal_error: {err.strip() or out.strip()[-400:]}")
            # plan_locked is transient contention from a concurrent auto/phase,
            # not a phase failure. Writing STATE_FAILED here turns a recoverable
            # lock-wait into a terminal state — the bug that surfaced when two
            # auto drivers raced into the same phase. Treat as a no-op; the next
            # iteration's status() will see the lock released.
            if "plan_locked" in ((err or "") + (out or "")):
                log(f"phase '{next_step}' hit plan_locked — transient contention, retrying next iteration")
            else:
                _record_failure(
                    plan_dir=plan_dir,
                    kind="phase_failed",
                    message=f"phase '{next_step}' internal_error",
                    current_state=None,
                    phase=next_step,
                    resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Inspect phase output and resume from the failed phase.",
                    metadata={"exit_code": code, "stderr": err.strip(), "stdout": out.strip()[-400:], "iteration": iteration},
                )
        elif result is None and code != 0:
            # Non-phase commands (e.g. 'override add-note') that failed —
            # preserve existing exit-code-based handling.
            log(f"command '{next_step}' exited {code}: {err.strip() or out.strip()[-400:]}")
            _record_failure(
                plan_dir=plan_dir,
                kind="phase_failed",
                message=f"command '{next_step}' exited {code}",
                current_state=None,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Inspect command output and resume from the failed phase.",
                metadata={"exit_code": code, "stderr": err.strip(), "stdout": out.strip()[-400:], "iteration": iteration},
            )

        if (
            code in (0, None)
            and on_phase_complete
            and next_step in {"plan", "critique", "gate", "finalize", "execute", "review"}
        ):
            try:
                on_phase_complete(next_step, int(code or 0), out, err)
            except Exception as error:  # pragma: no cover - defensive callback boundary
                log(f"phase-complete callback failed after '{next_step}': {error}")
                reconciliation = (
                    _reconcile_latest_execution_batch(plan_dir)
                    if next_step == "execute"
                    else None
                )
                _record_failure(
                    plan_dir=plan_dir,
                    kind="phase_callback_failed",
                    message=f"phase-complete callback failed after '{next_step}': {error}",
                    current_state=STATE_FAILED,
                    phase=next_step,
                    resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Fix the phase-complete callback and resume this phase.",
                    metadata={"iteration": iteration, "checkpoint_reconciliation": reconciliation},
                )
                return _outcome(
                    "failed",
                    final_state=state,
                    iterations=iteration,
                    reason=f"phase-complete callback failed after '{next_step}': {error}",
                    last_phase=last_phase,
                )

        # Post-execute routing: consume PhaseResult.exit_kind exclusively.
        # Delete the old pathways that read state["history"], globbed
        # execution_batch_*.json, captured stdout tails, and deviation
        # prefix-matching tables. Those surfaces still exist for user-visible
        # logging, but the driver no longer consults them for decisions.
        if next_step == "execute" and result is not None and max_blocked_retries >= 0:
            ek = getattr(result, "exit_kind", None)
            if ek == ExitKind.success.value:
                # Executor succeeded — continue to next phase without retry.
                pass
            elif ek == ExitKind.blocked_by_prereq.value:
                # Executor reported tasks blocked by prereq — exit as
                # awaiting_human. Use result.blocked_tasks directly, no
                # batch globbing or string prefix matching.
                blocked_tasks: tuple[Any, ...] = getattr(result, "blocked_tasks", ())
                if blocked_tasks:
                    blocked_summaries = [
                        (
                            f"{getattr(bt, 'task_id', '?')} "
                            f"(executor: {getattr(bt, 'notes', '')})"
                            if getattr(bt, "notes", "")
                            else getattr(bt, "task_id", "?")
                        )
                        for bt in blocked_tasks
                    ]
                    reason = (
                        "execute reported blocked tasks awaiting user action: "
                        + "; ".join(blocked_summaries)
                    )
                    log(
                        "execute reported task(s) blocked awaiting user action — "
                        "exiting as awaiting_human without consuming a retry",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocked_task_ids=[getattr(bt, "task_id", "?") for bt in blocked_tasks],
                    )
                    return _outcome(
                        "awaiting_human",
                        final_state=STATE_FINALIZED,
                        iterations=iteration,
                        reason=reason,
                        last_phase=last_phase,
                        blocking_reasons=[
                            (
                                f"task {getattr(bt, 'task_id', '?')} reported "
                                f"status=blocked by executor: {getattr(bt, 'notes', '')}"
                                if getattr(bt, "notes", "")
                                else f"task {getattr(bt, 'task_id', '?')} reported status=blocked by executor"
                            )
                            for bt in blocked_tasks
                        ],
                    )
                # No blocked tasks but still blocked_by_prereq — treat as
                # quality blocking via deviations.
                deviations_list: list[str] = [
                    getattr(dv, "message", str(dv))
                    for dv in getattr(result, "deviations", ())
                ]
                if blocked_retry_count >= max_blocked_retries:
                    log(
                        f"execute blocked by quality gates and retry cap reached "
                        f"({max_blocked_retries}) — bailing",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocking_reasons=deviations_list,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message="execute blocked_by_prereq with no blocked tasks — treating as quality block",
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "batch_index": None,
                            "retry_strategy": "fresh_session",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Review blocking deviations and resume execute with a fresh session.",
                        metadata={
                            "blocked_retries_used": blocked_retry_count,
                            "max_blocked_retries": max_blocked_retries,
                            "blocking_reasons": deviations_list,
                        },
                    )
                    return _outcome(
                        "worker_blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "execute blocked by quality gates "
                            f"after {blocked_retry_count + 1} attempt(s); "
                            f"retry cap {max_blocked_retries} reached"
                        ),
                        last_phase=last_phase,
                        blocking_reasons=deviations_list,
                    )
                blocked_retry_count += 1
                log(
                    f"execute blocked by quality gates — retrying "
                    f"({blocked_retry_count}/{max_blocked_retries})",
                    blocked_retries_used=blocked_retry_count,
                    max_blocked_retries=max_blocked_retries,
                    blocking_reasons=deviations_list,
                )
            elif ek == ExitKind.blocked_by_quality.value:
                # Quality-gate block — retry with cap, using result.deviations
                # directly (no string prefix matching).
                deviations_list = [
                    getattr(dv, "message", str(dv))
                    for dv in getattr(result, "deviations", ())
                ]
                if blocked_retry_count >= max_blocked_retries:
                    log(
                        f"execute blocked by quality gates and retry cap reached "
                        f"({max_blocked_retries}) — bailing",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocking_reasons=deviations_list,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message="execute blocked by quality gates",
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "batch_index": None,
                            "retry_strategy": "fresh_session",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Review blocking deviations and resume execute with a fresh session.",
                        metadata={
                            "blocked_retries_used": blocked_retry_count,
                            "max_blocked_retries": max_blocked_retries,
                            "blocking_reasons": deviations_list,
                        },
                    )
                    return _outcome(
                        "worker_blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "execute blocked by quality gates "
                            f"after {blocked_retry_count + 1} attempt(s); "
                            f"retry cap {max_blocked_retries} reached"
                        ),
                        last_phase=last_phase,
                        blocking_reasons=deviations_list,
                    )
                blocked_retry_count += 1
                log(
                    f"execute blocked by quality gates — retrying "
                    f"({blocked_retry_count}/{max_blocked_retries})",
                    blocked_retries_used=blocked_retry_count,
                    max_blocked_retries=max_blocked_retries,
                    blocking_reasons=deviations_list,
                )
            # timeout, context_exhausted, internal_error already handled above.

        if poll_sleep > 0:
            time.sleep(poll_sleep)

        # Emit phase_end after phase completes
        if plan_dir is not None and last_phase:
            try:
                emit_event(EventKind.PHASE_END, plan_dir=plan_dir, phase=last_phase, payload={"phase": last_phase})
            except Exception:
                pass

    # Hit iteration cap.
    log(f"hit max_iterations={max_iterations}")
    _record_failure(
        plan_dir=plan_dir,
        kind="iteration_cap",
        message=f"exceeded max_iterations={max_iterations}",
        current_state=None,
        phase=last_phase,
        resume_cursor={"phase": last_phase or "status", "retry_strategy": "manual_review"},
        suggested_action="Review automation progress before resuming.",
        metadata={"max_iterations": max_iterations},
    )
    return _outcome(
        "cap",
        final_state=last_state or "unknown",
        iterations=max_iterations,
        reason=f"exceeded max_iterations={max_iterations}",
        last_phase=last_phase,
    )


def build_auto_parser(subparsers: Any) -> None:
    auto_parser = subparsers.add_parser(
        "auto",
        help="Drive a plan to completion without human intervention",
    )
    auto_parser.add_argument("--plan", required=True, help="Plan name")
    auto_parser.add_argument(
        "--stall-threshold",
        type=int,
        default=DEFAULT_STALL_THRESHOLD,
        help=(
            f"Exit if the plan state doesn't change for this many iterations "
            f"AND no new review.json has been written (default "
            f"{DEFAULT_STALL_THRESHOLD}). Use --max-review-rework-cycles for "
            "the rework-loop limit — execute rework can span many iterations "
            "with state pinned at 'finalized', which is not a real stall."
        ),
    )
    auto_parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Hard cap on loop iterations (default {DEFAULT_MAX_ITERATIONS})",
    )
    auto_parser.add_argument(
        "--max-review-rework-cycles",
        type=int,
        default=DEFAULT_MAX_REVIEW_REWORK_CYCLES,
        help=(
            f"Cap on observed review→rework cycles before the driver bails "
            f"(default {DEFAULT_MAX_REVIEW_REWORK_CYCLES}). A rework cycle is "
            "counted each time review.json is rewritten while state appears "
            "stuck at 'finalized'. Mirrors execution.max_review_rework_cycles."
        ),
    )
    auto_parser.add_argument(
        "--max-cost-usd",
        type=_non_negative_float,
        default=None,
        help=(
            "Abort automation after cumulative state history cost exceeds this "
            "USD cap. The check runs after each phase completes (default no cap)."
        ),
    )
    auto_parser.add_argument(
        "--max-context-retries",
        type=_non_negative_int,
        default=DEFAULT_MAX_CONTEXT_RETRIES,
        help=(
            f"Fresh execute retries to allow after Codex context-window "
            f"exhaustion (default {DEFAULT_MAX_CONTEXT_RETRIES}; 0 disables)."
        ),
    )
    auto_parser.add_argument(
        "--max-blocked-retries",
        type=_non_negative_int,
        default=DEFAULT_MAX_BLOCKED_RETRIES,
        help=(
            f"How many times to retry execute after the worker reports "
            f"result=blocked (e.g. done tasks missing files_changed) before "
            f"bailing with worker_blocked (default {DEFAULT_MAX_BLOCKED_RETRIES})."
        ),
    )
    auto_parser.add_argument(
        "--max-add-note-attempts",
        type=_non_negative_int,
        default=DEFAULT_MAX_ADD_NOTE_ATTEMPTS,
        help=(
            f"Consecutive `override add-note` failures to tolerate before "
            f"escalating to `override force-proceed` (default "
            f"{DEFAULT_MAX_ADD_NOTE_ATTEMPTS}). The driver synthesizes a "
            "note from the latest gate signals; the cap protects against "
            "loops where add-note itself keeps failing."
        ),
    )
    auto_parser.add_argument(
        "--on-escalate",
        choices=ESCALATE_ACTIONS,
        default="force-proceed",
        help="What to do when the gate escalates (default force-proceed)",
    )
    auto_parser.add_argument(
        "--poll-sleep",
        type=float,
        default=DEFAULT_POLL_SLEEP_SECONDS,
        help=f"Seconds to sleep between phase transitions (default {DEFAULT_POLL_SLEEP_SECONDS})",
    )
    auto_parser.add_argument(
        "--phase-timeout",
        type=float,
        default=DEFAULT_PHASE_TIMEOUT_SECONDS,
        help=(
            f"Seconds before a single phase subprocess (plan/prep/critique/gate/finalize/execute/review) "
            f"is killed and treated as a failure (default {DEFAULT_PHASE_TIMEOUT_SECONDS}s). "
            "Stall detection still applies on top."
        ),
    )
    auto_parser.add_argument(
        "--phase-idle-timeout",
        type=float,
        default=DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
        help=(
            f"Seconds without stdout/stderr from a phase subprocess before auto kills it "
            f"as idle (default {DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS}s; set 0 to disable)."
        ),
    )
    auto_parser.add_argument(
        "--work-dir",
        default=None,
        help=(
            "Override the source-code working directory for subprocess workers "
            "(--add-dir / -C). Defaults to the current working directory."
        ),
    )
    auto_parser.add_argument(
        "--status-timeout",
        type=float,
        default=DEFAULT_STATUS_TIMEOUT_SECONDS,
        help=(
            f"Seconds before `megaplan status` / override subprocesses are killed "
            f"(default {DEFAULT_STATUS_TIMEOUT_SECONDS}s). These should always be quick; "
            "hitting this indicates serious trouble."
        ),
    )
    auto_parser.add_argument(
        "--outcome-file",
        default=None,
        help="Write the final DriverOutcome JSON to this path atomically before stdout.",
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def run_auto(root: Path, args: argparse.Namespace) -> int:
    """CLI entry point. Returns a POSIX exit code suitable for ``sys.exit``."""
    from megaplan.orchestration.progress import ProgressContext

    progress_context = ProgressContext.from_env()
    progress_env = progress_context.to_env() if progress_context is not None else None
    raw_phase_idle_timeout = getattr(
        args,
        "phase_idle_timeout",
        DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
    )
    outcome = drive(
        args.plan,
        cwd=root,
        stall_threshold=args.stall_threshold,
        max_iterations=args.max_iterations,
        max_review_rework_cycles=args.max_review_rework_cycles,
        max_cost_usd=args.max_cost_usd,
        max_context_retries=args.max_context_retries,
        max_blocked_retries=args.max_blocked_retries,
        max_add_note_attempts=args.max_add_note_attempts,
        on_escalate=args.on_escalate,
        poll_sleep=args.poll_sleep,
        phase_timeout=args.phase_timeout,
        phase_idle_timeout=(None if raw_phase_idle_timeout == 0 else raw_phase_idle_timeout),
        status_timeout=args.status_timeout,
        progress_env=progress_env,
    )
    outcome_json = outcome.to_json()
    if args.outcome_file:
        _atomic_write_text(Path(args.outcome_file), outcome_json)
    sys.stdout.write(outcome_json + "\n")
    # Exit codes: 0 done/aborted/cancelled/paused, 1 failed/unknown,
    # 2 stalled, 3 escalated, 4 iteration cap, 5 blocked, 6 cost cap exceeded,
    # 7 context retry exhausted, 8 worker_blocked.
    if outcome.status == "done":
        return 0
    if outcome.status in {"aborted", "cancelled", "paused"}:
        return 0  # user-requested/non-running stops are not phase failures
    if outcome.status == "stalled":
        return 2
    if outcome.status == "escalated":
        return 3
    if outcome.status == "cap":
        return 4
    if outcome.status == "blocked":
        return 5
    if outcome.status == "cost_cap_exceeded":
        return 6
    if outcome.status == "context_retry_exhausted":
        return 7
    if outcome.status == "worker_blocked":
        return 8
    return 1
