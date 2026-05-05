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
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from megaplan._core import find_plan_dir
from megaplan.store import PlanRepository
from megaplan.types import (
    AUTOMATION_TERMINAL_STATES,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_DONE,
    STATE_FAILED,
    STATE_PAUSED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)


DEFAULT_STALL_THRESHOLD = 5
DEFAULT_MAX_ITERATIONS = 200
DEFAULT_POLL_SLEEP_SECONDS = 1.0
DEFAULT_PHASE_TIMEOUT_SECONDS = 3600
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
ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")
PHASE_TIMEOUT_EXIT_CODE = 124  # conventional; matches GNU `timeout`


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
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "megaplan", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as expired:
        stdout = expired.stdout if isinstance(expired.stdout, str) else ""
        stderr = expired.stderr if isinstance(expired.stderr, str) else ""
        marker = f"\n[megaplan auto] subprocess timed out after {timeout}s"
        return PHASE_TIMEOUT_EXIT_CODE, stdout, (stderr + marker).strip()


def _status(
    plan: str,
    cwd: Path | None = None,
    *,
    timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    code, out, err = _run_megaplan(["status", "--plan", plan], cwd=cwd, timeout=timeout)
    if code != 0:
        raise RuntimeError(f"megaplan status failed (exit {code}): {err.strip() or out.strip()}")
    return json.loads(out)


def _has_valid_next(status: dict[str, Any], action: str) -> bool:
    return action in (status.get("valid_next") or [])


def _phase_command(next_step: str) -> list[str]:
    """Translate a `next_step` from status into the CLI args that run it.

    Most phases are one-to-one: next_step == command. Execute adds the
    destructive + user-approved flags because auto-mode implies both.
    """
    if next_step == "execute":
        return ["execute", "--confirm-destructive", "--user-approved"]
    return [next_step]


def _resolve_plan_dir(plan: str, cwd: Path | None) -> Path | None:
    """Best-effort resolution of legacy or canonical orphan plan roots near ``cwd``."""
    return find_plan_dir(cwd or Path.cwd(), plan)


def _last_history_step_result(plan_dir: Path | None, step: str) -> str | None:
    """Return the `result` field on the most recent history entry whose step matches.

    Used to detect when a phase completed successfully at the subprocess level
    but recorded `result: "blocked"` in state.json — the worker shipped output
    but the executor's own quality checks rejected it (e.g. done tasks missing
    files_changed). Returns None when state.json is missing/malformed or no
    matching entry exists.
    """
    if plan_dir is None:
        return None
    try:
        with (plan_dir / "state.json").open(encoding="utf-8") as handle:
            state_data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state_data, dict):
        return None
    history = state_data.get("history") or []
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("step") == step:
            result = entry.get("result")
            return result if isinstance(result, str) else None
    return None


def _read_execute_blocking_deviations(plan_dir: Path | None) -> list[str]:
    """Return the most recent execute-batch's blocking deviations (best-effort).

    The auto-driver uses these to surface *why* execute was blocked when the
    final history entry's `result` is `blocked`. Reads the highest-numbered
    execution_batch_<n>.json and pulls the `deviations` array, filtering for
    the strings that build_blocking_reasons emits (advisory deviations are
    excluded from the surfaced reason list).
    """
    if plan_dir is None:
        return []
    try:
        batches = sorted(
            (p for p in plan_dir.iterdir() if p.name.startswith("execution_batch_") and p.suffix == ".json"),
            key=lambda p: p.name,
        )
    except OSError:
        return []
    if not batches:
        return []
    try:
        with batches[-1].open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    deviations = payload.get("deviations") or []
    if not isinstance(deviations, list):
        return []
    blocking_prefixes = (
        "tasks have no executor update",
        "sense checks have no executor acknowledgment",
        "done tasks missing both files_changed and commands_run",
        "Done tasks missing sections_written",
    )
    return [
        str(d)
        for d in deviations
        if isinstance(d, str) and any(prefix in d for prefix in blocking_prefixes)
    ]


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


def _record_lifecycle_failure(
    *,
    plan_dir: Path | None,
    kind: str,
    message: str,
    current_state: str,
    phase: str | None,
    resume_cursor: dict[str, Any] | None,
    last_artifact: str | None = None,
    suggested_action: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if plan_dir is None:
        return
    try:
        PlanRepository.from_plan_dir(plan_dir).record_lifecycle_failure(
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
    on_escalate: str = "force-proceed",
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS,
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS,
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
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

    # Rework-cycle tracking. When review returns `needs_rework`, the plan
    # ping-pongs `finalized ↔ executed ↔ finalized` while execute re-runs
    # batches. From the driver's naive view that looks like a stall, but
    # every completed review rewrites `review.json`, so its mtime is a
    # reliable "forward progress" marker — each advance means a real
    # review cycle finished since we last observed the state.
    plan_dir = _resolve_plan_dir(plan, cwd)
    last_review_marker = _get_review_marker(plan_dir)
    rework_cycles_observed = 0

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[auto {plan}] {msg}\n")

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

    for iteration in range(1, max_iterations + 1):
        try:
            status = _status(plan, cwd=cwd, timeout=status_timeout)
        except (RuntimeError, json.JSONDecodeError) as error:
            log(f"status lookup failed: {error}")
            _record_lifecycle_failure(
                plan_dir=plan_dir,
                kind="status_lookup_failed",
                message=str(error),
                current_state=STATE_FAILED,
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
                _record_lifecycle_failure(
                    plan_dir=plan_dir,
                    kind="cost_cap_exceeded",
                    message=f"Cost cap exceeded: {cumulative} > {max_cost_usd}",
                    current_state=STATE_BLOCKED,
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

        # Terminal: plan reached a final state (or automation-terminal).
        if state in AUTOMATION_TERMINAL_STATES:
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
            return _outcome(
                terminal_status,
                final_state=state,
                iterations=iteration,
                reason=f"plan entered terminal state '{state}'",
                last_phase=last_phase,
            )

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

            if rework_cycles_observed > max_review_rework_cycles:
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
                    _record_lifecycle_failure(
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
                _record_lifecycle_failure(
                    plan_dir=plan_dir,
                    kind="stalled",
                    message=f"stalled at '{state}' for {stall_count} iterations",
                    current_state=STATE_BLOCKED,
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
            last_state = state

        # Escalation: no phase to run but overrides are available.
        if not next_step:
            if _has_valid_next(status, "override force-proceed"):
                if on_escalate == "force-proceed":
                    log("gate escalated — force-proceeding (per on_escalate=force-proceed)")
                    code, out, err = _run_megaplan(
                        [
                            "override",
                            "force-proceed",
                            "--plan",
                            plan,
                            "--reason",
                            "megaplan auto: escalate → force-proceed",
                        ],
                        cwd=cwd,
                        timeout=status_timeout,
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
                            _record_lifecycle_failure(
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
                        _record_lifecycle_failure(
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
                    _run_megaplan(
                        [
                            "override",
                            "abort",
                            "--plan",
                            plan,
                            "--reason",
                            "megaplan auto: escalate → abort",
                        ],
                        cwd=cwd,
                        timeout=status_timeout,
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
                _record_lifecycle_failure(
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
            _record_lifecycle_failure(
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
        cmd = _phase_command(next_step) + ["--plan", plan]
        log(f"running: megaplan {' '.join(cmd)}", phase=next_step, timeout=phase_timeout)
        last_phase = next_step
        code, out, err = _run_megaplan(cmd, cwd=cwd, timeout=phase_timeout)
        if max_context_retries > 0:
            while (
                next_step == "execute"
                and code != 0
                and CONTEXT_EXHAUSTION_FRAGMENT.lower() in ((out or "") + (err or "")).lower()
            ):
                if context_retry_count >= max_context_retries:
                    log(
                        f"context exhaustion retry cap reached ({max_context_retries}) — bailing",
                        context_retries_used=context_retry_count,
                        max_context_retries=max_context_retries,
                    )
                    _record_lifecycle_failure(
                        plan_dir=plan_dir,
                        kind="context_retry_exhausted",
                        message=f"context exhaustion retry cap reached ({context_retry_count}/{max_context_retries})",
                        current_state=STATE_BLOCKED,
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
                code, out, err = _run_megaplan(cmd, cwd=cwd, timeout=phase_timeout)
        if code == PHASE_TIMEOUT_EXIT_CODE:
            log(f"phase '{next_step}' timed out after {phase_timeout}s — stall detection will enforce the cap")
            _record_lifecycle_failure(
                plan_dir=plan_dir,
                kind="phase_timeout",
                message=f"phase '{next_step}' timed out after {phase_timeout}s",
                current_state=STATE_FAILED,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Investigate the timed-out phase and resume from the phase cursor.",
                metadata={"timeout_seconds": phase_timeout, "iteration": iteration},
            )
        elif code != 0:
            # Don't bail immediately — megaplan often records a partial failure
            # in state.json and the next status() reveals a recoverable valid_next.
            # Stall detection will still kill infinite loops.
            log(f"phase '{next_step}' exited {code}: {err.strip() or out.strip()[-400:]}")
            _record_lifecycle_failure(
                plan_dir=plan_dir,
                kind="phase_failed",
                message=f"phase '{next_step}' exited {code}",
                current_state=STATE_FAILED,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Inspect phase output and resume from the failed phase.",
                metadata={"exit_code": code, "stderr": err.strip(), "stdout": out.strip()[-400:], "iteration": iteration},
            )

        if on_phase_complete and next_step in {"plan", "critique", "gate", "finalize", "execute", "review"}:
            try:
                on_phase_complete(next_step, int(code or 0), out, err)
            except Exception as error:  # pragma: no cover - defensive callback boundary
                log(f"phase-complete callback failed after '{next_step}': {error}")
                _record_lifecycle_failure(
                    plan_dir=plan_dir,
                    kind="phase_callback_failed",
                    message=f"phase-complete callback failed after '{next_step}': {error}",
                    current_state=STATE_FAILED,
                    phase=next_step,
                    resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Fix the phase-complete callback and resume this phase.",
                    metadata={"iteration": iteration},
                )
                return _outcome(
                    "failed",
                    final_state=state,
                    iterations=iteration,
                    reason=f"phase-complete callback failed after '{next_step}': {error}",
                    last_phase=last_phase,
                )

        # Worker-blocked detection: execute exited 0 (or returned partial work)
        # but state.json's latest execute history entry has `result: "blocked"`.
        # Without this guard the driver would re-run execute every iteration
        # (state stays `finalized`) until stall-threshold finally kills it —
        # which we observed in IRL bake-offs with hermes-based executors.
        if next_step == "execute" and code in (0, None) and max_blocked_retries >= 0:
            execute_result = _last_history_step_result(plan_dir, "execute")
            if execute_result == "blocked":
                deviations = _read_execute_blocking_deviations(plan_dir)
                if blocked_retry_count >= max_blocked_retries:
                    log(
                        f"execute blocked by quality gates and retry cap reached "
                        f"({max_blocked_retries}) — bailing",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocking_reasons=deviations,
                    )
                    _record_lifecycle_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message="execute returned result=blocked from quality gates",
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
                            "blocking_reasons": deviations,
                        },
                    )
                    return _outcome(
                        "worker_blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "execute returned result=blocked from quality gates "
                            f"after {blocked_retry_count + 1} attempt(s); "
                            f"retry cap {max_blocked_retries} reached"
                        ),
                        last_phase=last_phase,
                        blocking_reasons=deviations,
                    )
                blocked_retry_count += 1
                log(
                    f"execute blocked by quality gates — retrying "
                    f"({blocked_retry_count}/{max_blocked_retries})",
                    blocked_retries_used=blocked_retry_count,
                    max_blocked_retries=max_blocked_retries,
                    blocking_reasons=deviations,
                )

        if poll_sleep > 0:
            time.sleep(poll_sleep)

    # Hit iteration cap.
    log(f"hit max_iterations={max_iterations}")
    _record_lifecycle_failure(
        plan_dir=plan_dir,
        kind="iteration_cap",
        message=f"exceeded max_iterations={max_iterations}",
        current_state=STATE_BLOCKED,
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
    outcome = drive(
        args.plan,
        cwd=root,
        stall_threshold=args.stall_threshold,
        max_iterations=args.max_iterations,
        max_review_rework_cycles=args.max_review_rework_cycles,
        max_cost_usd=args.max_cost_usd,
        max_context_retries=args.max_context_retries,
        max_blocked_retries=args.max_blocked_retries,
        on_escalate=args.on_escalate,
        poll_sleep=args.poll_sleep,
        phase_timeout=args.phase_timeout,
        status_timeout=args.status_timeout,
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
