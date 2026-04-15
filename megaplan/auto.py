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
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from megaplan.types import (
    AUTOMATION_TERMINAL_STATES,
    STATE_AWAITING_HUMAN,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
    TERMINAL_STATES,
)


DEFAULT_STALL_THRESHOLD = 5
DEFAULT_MAX_ITERATIONS = 200
DEFAULT_POLL_SLEEP_SECONDS = 1.0
DEFAULT_PHASE_TIMEOUT_SECONDS = 3600
DEFAULT_STATUS_TIMEOUT_SECONDS = 60
ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")
PHASE_TIMEOUT_EXIT_CODE = 124  # conventional; matches GNU `timeout`


@dataclass
class DriverOutcome:
    """Terminal outcome reported when the loop exits."""

    status: str  # "done" | "stalled" | "escalated" | "failed" | "aborted" | "cap" | "blocked"
    plan: str
    final_state: str
    iterations: int
    reason: str = ""
    last_phase: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

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
            },
            indent=2,
        )


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
            ["megaplan", *args],
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


def drive(
    plan: str,
    *,
    cwd: Path | None = None,
    stall_threshold: int = DEFAULT_STALL_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    on_escalate: str = "force-proceed",
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS,
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS,
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
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

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[auto {plan}] {msg}\n")

    for iteration in range(1, max_iterations + 1):
        try:
            status = _status(plan, cwd=cwd, timeout=status_timeout)
        except (RuntimeError, json.JSONDecodeError) as error:
            log(f"status lookup failed: {error}")
            return DriverOutcome(
                status="failed",
                plan=plan,
                final_state=last_state or "unknown",
                iterations=iteration,
                reason=str(error),
                last_phase=last_phase,
                events=events,
            )

        state = status.get("state", "")
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
                return DriverOutcome(
                    status="awaiting_human",
                    plan=plan,
                    final_state=state,
                    iterations=iteration,
                    reason="plan has criteria requiring human verification",
                    last_phase=last_phase,
                    events=events,
                )
            if state == STATE_TIEBREAKER_PENDING:
                log("tiebreaker pending — run 'megaplan tiebreaker-run --plan <name>' to execute")
                return DriverOutcome(
                    status="tiebreaker_pending",
                    plan=plan,
                    final_state=state,
                    iterations=iteration,
                    reason="gate recommended tiebreaker — researcher/challenger run needed",
                    last_phase=last_phase,
                    events=events,
                )
            if state == STATE_TIEBREAKER_READY:
                log("tiebreaker ready — run 'megaplan tiebreaker decide --plan <name>' to resolve")
                return DriverOutcome(
                    status="tiebreaker_ready",
                    plan=plan,
                    final_state=state,
                    iterations=iteration,
                    reason="tiebreaker synthesis complete — awaiting human decision",
                    last_phase=last_phase,
                    events=events,
                )
            log(f"terminal state reached: {state}")
            return DriverOutcome(
                status="done" if state == "done" else "aborted",
                plan=plan,
                final_state=state,
                iterations=iteration,
                reason=f"plan entered terminal state '{state}'",
                last_phase=last_phase,
                events=events,
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
                    return DriverOutcome(
                        status="blocked",
                        plan=plan,
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "all tasks reported blocked — workers may be poisoned "
                            "or the environment may genuinely be broken"
                        ),
                        last_phase=last_phase,
                        events=events,
                    )
                log(f"stalled at state={state} for {stall_count} iterations")
                return DriverOutcome(
                    status="stalled",
                    plan=plan,
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"stalled at '{state}' for {stall_count} iterations — "
                        "manual intervention required"
                    ),
                    last_phase=last_phase,
                    events=events,
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
                        return DriverOutcome(
                            status="failed",
                            plan=plan,
                            final_state=state,
                            iterations=iteration,
                            reason=f"override force-proceed exited {code}",
                            last_phase=last_phase,
                            events=events,
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
                    return DriverOutcome(
                        status="aborted",
                        plan=plan,
                        final_state=state,
                        iterations=iteration,
                        reason="gate escalated and on_escalate=abort",
                        last_phase=last_phase,
                        events=events,
                    )
                # on_escalate == "fail"
                log("gate escalated — failing (per on_escalate=fail)")
                return DriverOutcome(
                    status="escalated",
                    plan=plan,
                    final_state=state,
                    iterations=iteration,
                    reason="gate escalated and on_escalate=fail — human required",
                    last_phase=last_phase,
                    events=events,
                )
            log(f"no next_step and no override available (valid_next={valid_next})")
            return DriverOutcome(
                status="failed",
                plan=plan,
                final_state=state,
                iterations=iteration,
                reason="no next_step and no override available",
                last_phase=last_phase,
                events=events,
            )

        # Run the next phase.
        cmd = _phase_command(next_step) + ["--plan", plan]
        log(f"running: megaplan {' '.join(cmd)}", phase=next_step, timeout=phase_timeout)
        last_phase = next_step
        code, out, err = _run_megaplan(cmd, cwd=cwd, timeout=phase_timeout)
        if code == PHASE_TIMEOUT_EXIT_CODE:
            log(f"phase '{next_step}' timed out after {phase_timeout}s — stall detection will enforce the cap")
        elif code != 0:
            # Don't bail immediately — megaplan often records a partial failure
            # in state.json and the next status() reveals a recoverable valid_next.
            # Stall detection will still kill infinite loops.
            log(f"phase '{next_step}' exited {code}: {err.strip() or out.strip()[-400:]}")
        if poll_sleep > 0:
            time.sleep(poll_sleep)

    # Hit iteration cap.
    log(f"hit max_iterations={max_iterations}")
    return DriverOutcome(
        status="cap",
        plan=plan,
        final_state=last_state or "unknown",
        iterations=max_iterations,
        reason=f"exceeded max_iterations={max_iterations}",
        last_phase=last_phase,
        events=events,
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
        help=f"Exit if the plan state doesn't change for this many iterations (default {DEFAULT_STALL_THRESHOLD})",
    )
    auto_parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Hard cap on loop iterations (default {DEFAULT_MAX_ITERATIONS})",
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


def run_auto(root: Path, args: argparse.Namespace) -> int:
    """CLI entry point. Returns a POSIX exit code suitable for ``sys.exit``."""
    outcome = drive(
        args.plan,
        cwd=root,
        stall_threshold=args.stall_threshold,
        max_iterations=args.max_iterations,
        on_escalate=args.on_escalate,
        poll_sleep=args.poll_sleep,
        phase_timeout=args.phase_timeout,
        status_timeout=args.status_timeout,
    )
    sys.stdout.write(outcome.to_json() + "\n")
    if outcome.status == "done":
        return 0
    if outcome.status == "aborted":
        return 0  # user-requested abort is not a failure
    if outcome.status == "stalled":
        return 2
    if outcome.status == "escalated":
        return 3
    if outcome.status == "cap":
        return 4
    # rc=3 is already claimed by 'escalated'; use rc=5 for all-blocked so the
    # supervisor can distinguish "workers said every task is blocked" from a
    # generic stall or escalation.
    if outcome.status == "blocked":
        return 5
    return 1
