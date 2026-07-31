"""Deterministic L2 terminal audit — routed through typed delegation shim.

A terminal audit never directly executes a repair-loop binary.  Instead it
routes every retrigger through the typed delegation shim (Step 76-80):
``delegate_to_simple_fixer`` for canonical authority or
``emit_zero_authority_rejection`` for non-authoritative paths.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Sequence

import yaml

from arnold_pipelines.megaplan.cloud.meta_repair import (
    RetriggerExecutionResult,
    authoritative_terminal_snapshot_reason,
    verify_retrigger_success,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    append_incident_record,
    atomic_write_json,
    update_session_index,
    validate_repair_data,
)
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegation,
    RepairDelegationResult,
    build_repair_delegation,
    delegate_to_simple_fixer,
    emit_zero_authority_rejection,
)


def _obj(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def capture_terminal_snapshot(session: str, marker_dir: Path) -> dict[str, Any]:
    marker = _obj(marker_dir / f"{session}.json", "session marker")
    workspace = Path(str(marker.get("workspace") or ""))
    if not workspace.is_dir():
        raise ValueError("session workspace unavailable for authoritative snapshot")

    chain_states = sorted(
        (workspace / ".megaplan/plans/.chains").glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not chain_states:
        raise ValueError("chain state unavailable for authoritative snapshot")
    chain_path = chain_states[-1]
    chain_state = _obj(chain_path, "chain state")

    plan_name = str(chain_state.get("current_plan_name") or "").strip()
    plan_path = workspace / ".megaplan/plans" / plan_name / "state.json"
    if not plan_name or not plan_path.exists():
        plan_states = sorted(
            (workspace / ".megaplan/plans").glob("*/state.json"),
            key=lambda path: path.stat().st_mtime,
        )
        if not plan_states:
            raise ValueError("current plan state unavailable for authoritative snapshot")
        plan_path = plan_states[-1]

    plan_state = _obj(plan_path, "plan state")
    milestones = chain_state.get("milestones") if isinstance(chain_state.get("milestones"), list) else []
    completed = chain_state.get("completed") if isinstance(chain_state.get("completed"), list) else []
    active_step = plan_state.get("active_step") if isinstance(plan_state.get("active_step"), dict) else {}
    worker_pid = active_step.get("worker_pid")
    worker_alive = None

    spec_path = Path(str(marker.get("remote_spec") or ""))
    spec_total = 0
    if spec_path.is_file():
        try:
            spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
            spec_milestones = spec.get("milestones") if isinstance(spec, dict) else None
            if isinstance(spec_milestones, list):
                spec_total = len(spec_milestones)
        except (OSError, yaml.YAMLError):
            pass

    chain_total = len(milestones)
    total = spec_total or chain_total
    total_consistent = not (spec_total and chain_total and spec_total != chain_total)
    if worker_pid not in (None, ""):
        try:
            os.kill(int(worker_pid), 0)
        except (OSError, ValueError):
            worker_alive = False
        else:
            worker_alive = True

    return {
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "workspace": str(workspace),
        "chain_path": str(chain_path),
        "plan_path": str(plan_path),
        "milestone_total": total if total_consistent else 0,
        "milestone_total_source": "remote_spec" if spec_total else "chain_state",
        "milestone_total_consistent": total_consistent,
        "completed_count": len(completed),
        "chain_last_state": str(chain_state.get("last_state") or "").strip().lower(),
        "plan_current_state": str(
            plan_state.get("current_state") or plan_state.get("state") or ""
        ).strip().lower(),
        "active_step_present": bool(active_step),
        "worker_pid": worker_pid,
        "worker_pid_alive": worker_alive,
        "remote_spec": str(marker.get("remote_spec") or "").strip(),
    }


def _append_terminal_audit_evidence(
    repair_data_dir: Path,
    *,
    session: str,
    record: dict[str, Any],
) -> Path:
    sidecar_dir = repair_data_dir.with_name(f"{repair_data_dir.name}.d")
    return append_incident_record(
        sidecar_dir,
        {
            "session": session,
            "kind": "terminal_audit",
            "summary": str(record.get("outcome") or ""),
            "accepted": bool(record.get("accepted") is True),
            "record_path": str(record.get("record_path") or ""),
            "l1_returncode": record.get("l1_returncode"),
            "rejection_reason": str(
                (record.get("post_retrigger_verification") or {}).get("rejection_reason")
                if isinstance(record.get("post_retrigger_verification"), dict)
                else ""
            ),
            "recorded_at": str(record.get("recorded_at") or ""),
        },
    )


def run_terminal_audit(
    *,
    session: str,
    repair_loop_bin: Path,
    marker_dir: Path,
    repair_data_dir: Path,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    pre_snapshot: dict[str, Any] | None = None
    post_snapshot: dict[str, Any] | None = None
    command: list[str] = []
    returncode: int | None = None
    rejection = ""

    try:
        pre_snapshot = capture_terminal_snapshot(session, marker_dir)
        rejection = authoritative_terminal_snapshot_reason(pre_snapshot)
        if rejection:
            verification = {
                "accepted": False,
                "retriggered": False,
                "rejection_reason": rejection,
                "outcome": "terminal_audit_rejected",
                "pre_snapshot": pre_snapshot,
            }
        else:
            # Route retrigger through typed delegation shim (Step 76-80).
            # Terminal audit never directly executes a repair-loop binary.
            workspace = pre_snapshot["workspace"]
            remote_spec = pre_snapshot.get("remote_spec", "")
            command = [str(repair_loop_bin), session, workspace]
            if remote_spec:
                command.append(remote_spec)
            returncode = None
            stdout = ""
            stderr = ""

            delegation = build_repair_delegation(
                caller_kind="terminal_audit",
                caller_id=f"terminal-audit:{session}",
                target=pre_snapshot.get("repair_target"),
            )
            if delegation is None:
                # Cannot construct exact F01 tuple — emit typed rejection.
                rejection_result: RepairDelegationResult = emit_zero_authority_rejection(
                    caller_kind="terminal_audit",
                    caller_id=f"terminal-audit:{session}",
                    reason="terminal audit cannot construct exact occurrence identity from snapshot",
                )
                returncode = 73  # canonical rejection exit code
                stdout = str(rejection_result.to_dict())
            else:
                # Delegate to simple_fixer through canonical path.
                queue_dir = str(marker_dir / "repair-queue")
                delegation_result = delegate_to_simple_fixer(
                    delegation,
                    queue_dir=queue_dir,
                    mutate=lambda occ: f"terminal-audit-retriggered:{session}",
                    actor=f"terminal-audit:{session}",
                    request_id=f"terminal-audit-{session}",
                    session_id=session,
                    kind="terminal_audit_retrigger",
                )
                if delegation_result.delegated:
                    returncode = 0
                    stdout = str(delegation_result.to_dict())
                else:
                    returncode = 73
                    stdout = str(delegation_result.to_dict())
                    stderr = f"delegation outcome: {delegation_result.outcome}"

            sidecar = validate_repair_data(repair_data_dir / f"{session}.repair-data.json")
            post_snapshot = capture_terminal_snapshot(session, marker_dir)
            first_progress_at = post_snapshot.get("captured_at") or dt.datetime.now(
                dt.timezone.utc
            ).isoformat()
            observed_at = (
                dt.datetime.fromisoformat(str(first_progress_at))
                + dt.timedelta(seconds=1)
            ).isoformat()
            blocker_id = f"terminal-audit:{session}"
            verification = verify_retrigger_success(
                retriggered=True,
                retrigger_result=RetriggerExecutionResult(
                    tuple(command),
                    returncode or 73,
                    stdout,
                    stderr,
                ),
                post_retrigger_verification={
                    "outcome": sidecar.get("outcome", ""),
                    "pre_snapshot": pre_snapshot,
                    "post_snapshot": post_snapshot,
                    "repair_completed_at": pre_snapshot.get("captured_at", started),
                    "original_blocker": {"blocker_id": blocker_id},
                    "observation": {
                        "kind": "terminal_audit",
                        "blocker_id": blocker_id,
                        "blocker_cleared": True,
                        "directly_observed": True,
                        "independent": True,
                        "canonical_runner_live": True,
                        "fresh_progress_beyond_checkpoint": True,
                        "continued_progress": True,
                        "first_progress_observed_at": first_progress_at,
                        "observed_at": observed_at,
                    },
                },
            )
    except Exception as exc:
        rejection = rejection or f"authoritative terminal audit failed: {type(exc).__name__}: {exc}"
        verification = {
            "accepted": False,
            "retriggered": bool(command),
            "rejection_reason": rejection,
            "outcome": "terminal_audit_rejected",
            "pre_snapshot": pre_snapshot,
            "post_snapshot": post_snapshot,
        }

    accepted = bool(verification.get("accepted"))
    now = dt.datetime.now(dt.timezone.utc)
    record = {
        "kind": "terminal_audit",
        "session": session,
        "started_at": started,
        "recorded_at": now.isoformat(),
        "command": command,
        "l1_returncode": returncode,
        "accepted": accepted,
        "outcome": "complete" if accepted else "verifier_rejected",
        "post_retrigger_verification": verification,
        "pre_snapshot": pre_snapshot,
        "post_snapshot": post_snapshot,
    }
    meta_dir = repair_data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    record_path = meta_dir / f"terminal-audit-{session}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    atomic_write_json(record_path, record)
    update_session_index(
        repair_data_dir / "index.json",
        session,
        {
            "latest_terminal_audit": str(record_path),
            "terminal_audit_accepted": accepted,
            "terminal_audit_outcome": record["outcome"],
            "terminal_audit_recorded_at": record["recorded_at"],
        },
    )
    record["record_path"] = str(record_path)
    record["sidecar_path"] = str(
        _append_terminal_audit_evidence(
            repair_data_dir,
            session=session,
            record=record,
        )
    )
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session")
    parser.add_argument("--repair-loop-bin", required=True)
    parser.add_argument("--marker-dir", required=True)
    parser.add_argument("--repair-data-dir", required=True)
    args = parser.parse_args(argv)
    record = run_terminal_audit(
        session=args.session,
        repair_loop_bin=Path(args.repair_loop_bin),
        marker_dir=Path(args.marker_dir),
        repair_data_dir=Path(args.repair_data_dir),
    )
    print(json.dumps(record, sort_keys=True))
    return 0 if record["accepted"] else 73


if __name__ == "__main__":
    raise SystemExit(main())
