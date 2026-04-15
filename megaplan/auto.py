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

from megaplan.types import TERMINAL_STATES


DEFAULT_STALL_THRESHOLD = 5
DEFAULT_MAX_ITERATIONS = 200
DEFAULT_POLL_SLEEP_SECONDS = 1.0
ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")


@dataclass
class DriverOutcome:
    """Terminal outcome reported when the loop exits."""

    status: str  # "done" | "stalled" | "escalated" | "failed" | "aborted" | "cap"
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


def _run_megaplan(args: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a megaplan sub-command in its own process.

    We shell out rather than importing the handlers directly so each phase gets
    a fresh argparse/handler lifecycle. This matches how external orchestrators
    drive the CLI and avoids subtle state leakage between phases.
    """
    proc = subprocess.run(
        ["megaplan", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _status(plan: str, cwd: Path | None = None) -> dict[str, Any]:
    code, out, err = _run_megaplan(["status", "--plan", plan], cwd=cwd)
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
            status = _status(plan, cwd=cwd)
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

        # Terminal: plan reached a final state.
        if state in TERMINAL_STATES:
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
        log(f"running: megaplan {' '.join(cmd)}", phase=next_step)
        last_phase = next_step
        code, out, err = _run_megaplan(cmd, cwd=cwd)
        if code != 0:
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


def run_auto(root: Path, args: argparse.Namespace) -> int:
    """CLI entry point. Returns a POSIX exit code suitable for ``sys.exit``."""
    outcome = drive(
        args.plan,
        cwd=root,
        stall_threshold=args.stall_threshold,
        max_iterations=args.max_iterations,
        on_escalate=args.on_escalate,
        poll_sleep=args.poll_sleep,
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
    return 1
