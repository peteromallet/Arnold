"""Detached completion worker for the canonical tmux resident restart.

The worker must not share the resident pane's process group.  The guarded
``tmux respawn-pane -k`` necessarily terminates the resident, its model
subprocess, and the CLI command that requested the restart.  Running this
transaction in a new session lets it verify the replacement process and make
the already-durable notification eligible for delivery.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

from agentbox.reset_notifications import (
    ResetNotificationError,
    ResetNotificationReservation,
    mark_reset_failed,
    mark_reset_succeeded,
)
from agentbox.services import _wait_for_tmux_resident


def complete_tmux_restart(
    *,
    pane_id: str,
    old_pane_pid: int,
    reservation: ResetNotificationReservation,
    service_name: str,
    unit: str,
    grace_seconds: float,
) -> dict[str, Any]:
    """Replace the pane, verify its new resident, and finalize the outbox."""

    if grace_seconds > 0:
        time.sleep(grace_seconds)
    result = subprocess.run(
        ["tmux", "respawn-pane", "-k", "-t", pane_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        payload = {
            "ok": False,
            "service": service_name,
            "unit": unit,
            "backend": "tmux",
            "error": "failed to respawn the guarded Discord resident tmux pane",
            "error_output": result.stderr,
            "pane_id": pane_id,
            "old_pane_pid": old_pane_pid,
        }
        mark_reset_failed(reservation, restart_evidence=payload)
        return payload

    health = _wait_for_tmux_resident(pane_id, old_pane_pid=old_pane_pid)
    payload = {
        "ok": bool(health.get("ok")),
        "service": service_name,
        "unit": unit,
        "backend": "tmux",
        "output": result.stdout,
        "error_output": result.stderr,
        "pane_id": pane_id,
        "old_pane_pid": old_pane_pid,
        "health": health,
    }
    if payload["ok"]:
        mark_reset_succeeded(reservation, restart_evidence=payload)
    else:
        payload["error"] = health.get("error", "replacement resident failed health verification")
        mark_reset_failed(reservation, restart_evidence=payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pane-id", required=True)
    parser.add_argument("--old-pane-pid", required=True, type=int)
    parser.add_argument("--notification-id", required=True)
    parser.add_argument("--notification-path", required=True, type=Path)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--grace-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    reservation = ResetNotificationReservation(
        notification_id=args.notification_id,
        path=args.notification_path,
        provenance_mode="detached_worker",
    )
    try:
        result = complete_tmux_restart(
            pane_id=args.pane_id,
            old_pane_pid=args.old_pane_pid,
            reservation=reservation,
            service_name=args.service_name,
            unit=args.unit,
            grace_seconds=max(0.0, args.grace_seconds),
        )
    except (OSError, ResetNotificationError, ValueError) as exc:
        try:
            mark_reset_failed(
                reservation,
                restart_evidence={
                    "ok": False,
                    "service": args.service_name,
                    "unit": args.unit,
                    "backend": "tmux",
                    "error": "detached restart worker failed",
                    "error_class": exc.__class__.__name__,
                },
            )
        except (OSError, ResetNotificationError, ValueError):
            pass
        return 1
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
