"""Fail-closed operator trigger for one canonical blocked-plan repair.

This command is intentionally narrower than the watchdog.  It resolves one
cloud session through the normal current-target resolver, verifies the exact
frozen plan/evidence cursor supplied by the operator, enqueues the same repair
request shape used by terminal lifecycle handling, and asks
``arnold-repair-trigger`` to process only that request ID.

It never edits plan or chain state, and a deterministic receipt prevents the
same evidence cursor from being manually dispatched twice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud import feature_flags, repair_requests
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target


RECEIPT_SCHEMA = "arnold-manual-repair-trigger-v1"
RECEIPT_DIR_NAME = "manual-triggers"
ALLOWED_PLAN_STATES = frozenset({"blocked", "failed"})


class ManualRepairTriggerError(RuntimeError):
    """The requested one-shot repair could not be dispatched safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualRepairTriggerError(f"required JSON is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ManualRepairTriggerError(f"required JSON is not an object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ManualRepairTriggerError(f"cannot fingerprint plan state: {path}") from exc


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _blocked_task_id(metadata: Mapping[str, Any]) -> str:
    for key in ("blocked_task_ids", "task_ids"):
        values = metadata.get(key)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            for value in values:
                task_id = _text(value)
                if task_id:
                    return task_id
    return ""


def _evidence_cursor(state: Mapping[str, Any], failure: Mapping[str, Any]) -> dict[str, Any]:
    candidates = (
        failure.get("evidence_cursor"),
        _mapping(failure.get("metadata")).get("evidence_cursor"),
        _mapping(state.get("resume_cursor")).get("evidence_cursor"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {}


def _receipt_id(*, session: str, plan: str, history_index: int, artifact_hash: str) -> str:
    encoded = json.dumps(
        [session, plan, history_index, artifact_hash],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise ManualRepairTriggerError(
                f"manual trigger receipt already exists for this evidence cursor: {path}"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True)
            handle.write("\n")
        return

    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _dispatch_event(stdout: str, request_id: str) -> dict[str, Any] | None:
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("event") == "repair_trigger_dispatch"
            and payload.get("request_id") == request_id
        ):
            return payload
    return None


def trigger_once(
    *,
    session: str,
    plan: str,
    expected_history_index: int,
    expected_artifact_hash: str,
    marker_dir: Path,
    queue_root: Path,
    repair_data_dir: Path | None = None,
    trigger_bin: Path = Path("/usr/local/bin/arnold-repair-trigger"),
    target_resolver: Callable[..., dict[str, Any]] = resolve_current_target,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Validate, enqueue, and dispatch one exact canonical repair request."""

    session = _text(session)
    plan = _text(plan)
    artifact_hash = _text(expected_artifact_hash)
    if not session or not plan or expected_history_index < 0 or not artifact_hash:
        raise ManualRepairTriggerError(
            "session, plan, non-negative history index, and artifact hash are required"
        )
    if not feature_flags.mutation_authorized(feature_flags.MUTATION_PATH_L1):
        raise ManualRepairTriggerError(
            "L1 mutation is not authorized; set invocation-scoped ARNOLD_AUTONOMY=1 and "
            "ARNOLD_REPAIR_TRIGGER_ENABLED=1"
        )
    if not trigger_bin.is_file() or not os.access(trigger_bin, os.X_OK):
        raise ManualRepairTriggerError(f"canonical repair trigger is unavailable: {trigger_bin}")

    queue_root = repair_requests.validate_queue_root(queue_root)
    target = target_resolver(
        session,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    current_refs = _mapping(target.get("current_refs"))
    evidence_state = _mapping(target.get("evidence_state"))
    stale_evidence = target.get("stale_evidence")
    if target.get("target_session") != session:
        raise ManualRepairTriggerError("resolver target session disagrees with the requested session")
    if target.get("authoritative_source") != "chain_state":
        raise ManualRepairTriggerError("current target is not chain-state authoritative")
    if evidence_state.get("mutation_eligible") is not True:
        raise ManualRepairTriggerError("current-target evidence is not mutation eligible")
    if isinstance(stale_evidence, list) and stale_evidence:
        raise ManualRepairTriggerError("current-target resolver reported stale evidence")
    if _text(current_refs.get("current_plan_name")) != plan:
        raise ManualRepairTriggerError("requested plan is not the resolver's current plan")

    plan_summary = _mapping(target.get("plan_state"))
    plan_path = Path(_text(plan_summary.get("path")))
    if not plan_path.is_absolute() or plan_path.name != "state.json":
        raise ManualRepairTriggerError("resolver did not provide an absolute plan state path")
    if _sha256_file(plan_path) != _text(plan_summary.get("fingerprint")):
        raise ManualRepairTriggerError("plan state changed after current-target resolution")
    state = _read_json_object(plan_path)
    if _text(state.get("name")) != plan:
        raise ManualRepairTriggerError("plan state identity disagrees with the requested plan")
    current_state = _text(state.get("current_state"))
    if current_state not in ALLOWED_PLAN_STATES:
        raise ManualRepairTriggerError(f"plan state {current_state!r} is not repair-trigger eligible")
    failure = _mapping(state.get("latest_failure"))
    if not failure:
        raise ManualRepairTriggerError("blocked plan has no latest_failure evidence")
    cursor = _evidence_cursor(state, failure)
    observed_index = cursor.get("history_index")
    observed_hash = _text(cursor.get("review_artifact_hash"))
    if observed_index != expected_history_index or observed_hash != artifact_hash:
        raise ManualRepairTriggerError("frozen evidence cursor does not match current plan state")

    workspace = Path(_text(current_refs.get("workspace")))
    remote_spec = _text(current_refs.get("remote_spec"))
    run_kind = _text(current_refs.get("run_kind")) or "chain"
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ManualRepairTriggerError("resolver workspace is unavailable")
    metadata = _mapping(failure.get("metadata"))
    problem_signature = {
        "failure_kind": _text(failure.get("kind")) or "terminal_blocked",
        "current_state": current_state,
        "phase_or_step": _text(failure.get("phase")),
        "milestone_or_plan": plan,
        "gate_recommendation": _text(failure.get("suggested_action")),
        "blocked_task_id": _blocked_task_id(metadata),
    }
    root_cause_hint = _text(failure.get("message")) or "plan entered a blocked terminal state"
    request_id = repair_requests.request_id_for(
        session=session,
        problem_signature=problem_signature,
        root_cause_hint=root_cause_hint,
    )
    receipt_id = _receipt_id(
        session=session,
        plan=plan,
        history_index=expected_history_index,
        artifact_hash=artifact_hash,
    )
    receipt_path = queue_root / RECEIPT_DIR_NAME / f"{receipt_id}.json"
    started_at = _utc_now()
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "dispatching",
        "started_at": started_at,
        "session": session,
        "plan": plan,
        "evidence_cursor": {
            "history_index": expected_history_index,
            "review_artifact_hash": artifact_hash,
        },
        "plan_state_fingerprint": _text(plan_summary.get("fingerprint")),
        "request_id": request_id,
        "queue_root": str(queue_root),
        "trigger_bin": str(trigger_bin),
    }
    _write_json_atomic(receipt_path, receipt, exclusive=True)

    try:
        queued = repair_requests.enqueue_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir,
            session=session,
            source="manual_terminal_failure_retrigger",
            workspace=workspace,
            run_kind=run_kind,
            target={
                "plan_dir": str(plan_path.parent),
                "plan_name": plan,
                "workspace_path": str(workspace),
                "remote_spec": remote_spec,
                "evidence_cursor": dict(cursor),
            },
            problem_signature=problem_signature,
            root_cause_hint=root_cause_hint,
        )
        queued_request = _mapping(queued.get("request"))
        if _text(queued_request.get("request_id")) != request_id:
            raise ManualRepairTriggerError("canonical queue returned a different request identity")
        if queued.get("status") not in {"queued", "coalesced"}:
            raise ManualRepairTriggerError(f"repair request was not accepted: {queued.get('status')}")

        command = [
            str(trigger_bin),
            "--marker-dir",
            str(marker_dir),
            "--queue-root",
            str(queue_root),
            "--request-id",
            request_id,
        ]
        if repair_data_dir is not None:
            command.extend(["--repair-data-dir", str(repair_data_dir)])
        completed = command_runner(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        event = _dispatch_event(completed.stdout or "", request_id)
        dispatched = bool(
            completed.returncode == 0
            and event is not None
            and event.get("status") == "dispatched"
        )
        receipt.update(
            {
                "status": "dispatched" if dispatched else "dispatch_failed",
                "completed_at": _utc_now(),
                "request_status": queued.get("status"),
                "request_path": queued.get("path"),
                "trigger_returncode": completed.returncode,
                "dispatch_event": event or {},
            }
        )
        _write_json_atomic(receipt_path, receipt)
        if not dispatched:
            raise ManualRepairTriggerError(
                f"canonical trigger did not establish a dispatch; receipt: {receipt_path}"
            )
    except Exception as exc:
        if receipt.get("status") == "dispatching":
            receipt.update(
                {
                    "status": "dispatch_failed",
                    "completed_at": _utc_now(),
                    "error_kind": type(exc).__name__,
                }
            )
            _write_json_atomic(receipt_path, receipt)
        raise

    return {
        "status": "dispatched",
        "session": session,
        "plan": plan,
        "request_id": request_id,
        "managed_run_id": _text(_mapping(receipt.get("dispatch_event")).get("managed_run_id")),
        "managed_manifest_path": _text(
            _mapping(receipt.get("dispatch_event")).get("managed_manifest_path")
        ),
        "receipt_path": str(receipt_path),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--expected-history-index", type=int, required=True)
    parser.add_argument("--expected-artifact-hash", required=True)
    parser.add_argument(
        "--marker-dir",
        type=Path,
        default=Path(
            os.getenv("CLOUD_WATCHDOG_MARKER_DIR", "/workspace/.megaplan/cloud-sessions")
        ),
    )
    parser.add_argument(
        "--queue-root",
        type=Path,
        default=Path(
            os.getenv("ARNOLD_REPAIR_QUEUE_ROOT", "/workspace/.megaplan/repair-queue")
        ),
    )
    parser.add_argument(
        "--repair-data-dir",
        type=Path,
        default=(Path(value) if (value := os.getenv("CLOUD_WATCHDOG_REPAIR_DATA_DIR")) else None),
    )
    parser.add_argument(
        "--trigger-bin",
        type=Path,
        default=Path(
            os.getenv(
                "ARNOLD_MANUAL_REPAIR_TRIGGER_BIN",
                "/usr/local/bin/arnold-repair-trigger",
            )
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = trigger_once(
            session=args.session,
            plan=args.plan,
            expected_history_index=args.expected_history_index,
            expected_artifact_hash=args.expected_artifact_hash,
            marker_dir=args.marker_dir,
            queue_root=args.queue_root,
            repair_data_dir=args.repair_data_dir,
            trigger_bin=args.trigger_bin,
        )
    except ManualRepairTriggerError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
