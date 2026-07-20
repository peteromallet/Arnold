"""Neutral durable lifecycle for resident and automatic managed agents.

The repair queue, watchdog, and chain runner remain the authorities that decide
*whether* work may run.  This module owns the execution evidence after that
decision: a stable identity, manifest/history, process liveness, logs, result,
lineage, and a truthful terminal state.

It deliberately supervises the real process.  Callers must not create one of
these manifests as a projection for a process launched elsewhere.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any


MANAGED_AGENT_SCHEMA = "arnold-managed-agent-run-v2"
MANAGED_AGENT_CUSTODIAN = "arnold.megaplan.managed_agent"
LEGACY_RESIDENT_SCHEMA = "arnold-resident-agent-run-v1"
LEGACY_RESIDENT_CUSTODIAN = "arnold.megaplan.resident"
DEFAULT_RUN_ROOT = Path(".megaplan/plans/resident-subagents")
ACTIVE_STATUSES = frozenset({"reserved", "launching", "running", "adopting"})
TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "interrupted", "cancelled", "superseded", "unknown"}
)
AUTOMATIC_RUN_KINDS = frozenset(
    {
        "automatic_repair",
        "automatic_meta_repair",
        "automatic_meta_repair_worker",
        "automatic_repair_retry",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def stable_managed_run_id(run_kind: str, identity_key: str) -> str:
    digest = hashlib.sha256(f"{run_kind}\0{identity_key}".encode("utf-8")).hexdigest()[:20]
    return f"managed-{run_kind.replace('_', '-')}-{digest}"


def _append_status(
    manifest: dict[str, Any],
    status: str,
    *,
    evidence: str,
    **extra: Any,
) -> None:
    at = utc_now()
    manifest["status"] = status
    manifest["updated_at"] = at
    history = list(manifest.get("status_history") or [])
    event = {"status": status, "at": at, "evidence": evidence}
    event.update({key: value for key, value in extra.items() if value is not None})
    history.append(event)
    manifest["status_history"] = history[-100:]


def _pid_live(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        state = stat.rsplit(") ", 1)[1].split()[0]
        if state == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def _pid_start_ticks(pid: object) -> str:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return ""
    try:
        # /proc/<pid>/stat field 22 is stable across exec and changes on PID reuse.
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return ""


def _pid_matches(pid: object, expected_sha256: str, expected_start_ticks: str = "") -> bool:
    if not _pid_live(pid):
        return False
    if expected_start_ticks:
        return _pid_start_ticks(pid) == expected_start_ticks
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    observed = hashlib.sha256(raw).hexdigest()
    return not expected_sha256 or observed == expected_sha256


def is_managed_manifest(payload: Mapping[str, Any]) -> bool:
    schema = payload.get("schema_version")
    custodian = payload.get("custodian")
    if schema == MANAGED_AGENT_SCHEMA:
        return custodian == MANAGED_AGENT_CUSTODIAN
    return schema == LEGACY_RESIDENT_SCHEMA and custodian == LEGACY_RESIDENT_CUSTODIAN


def observed_status(payload: Mapping[str, Any], manifest_path: Path) -> tuple[str, bool]:
    status = str(payload.get("status") or "unknown")
    if status not in ACTIVE_STATUSES:
        return status, False
    supervisor_pid = payload.get("pid")
    worker_pid = payload.get("worker_pid")
    supervisor_live = _pid_matches(
        supervisor_pid,
        str(payload.get("supervisor_cmdline_sha256") or ""),
        str(payload.get("supervisor_start_ticks") or ""),
    )
    worker_live = _pid_matches(
        worker_pid,
        str(payload.get("worker_cmdline_sha256") or ""),
        str(payload.get("worker_start_ticks") or ""),
    )
    live = supervisor_live or worker_live
    return (status if live else "interrupted"), live


def managed_run_roots(
    *, project_root: str | Path, workspace_root: str | Path | None = "/workspace"
) -> set[Path]:
    roots = {Path(project_root).resolve() / DEFAULT_RUN_ROOT}
    workspace = Path(workspace_root).resolve() if workspace_root else None
    if workspace and workspace.is_dir():
        roots.update(workspace.glob("*/.megaplan/plans/resident-subagents"))
        roots.update(workspace.glob("*/*/.megaplan/plans/resident-subagents"))
    return roots


@dataclass(frozen=True)
class ManagedCommandSpec:
    run_kind: str
    identity_key: str
    project_dir: Path
    argv: tuple[str, ...]
    task_kind: str
    difficulty: int
    model: str
    reasoning_effort: str
    route_class: str
    backend: str
    command_display: str
    links: Mapping[str, Any]
    parent_run_id: str | None = None
    retry_of_run_id: str | None = None
    lineage_key: str | None = None
    run_root: Path | None = None
    stdin_path: Path | None = None
    tee_output: bool = True


def _root_for(spec: ManagedCommandSpec) -> Path:
    root = spec.run_root or DEFAULT_RUN_ROOT
    return root.resolve() if root.is_absolute() else spec.project_dir.resolve() / root


def _command_hash(argv: Sequence[str]) -> str:
    return hashlib.sha256(json.dumps(list(argv), separators=(",", ":")).encode()).hexdigest()


def _latest_lineage_run(root: Path, lineage_key: str, current_run_id: str) -> str | None:
    candidates: list[tuple[str, str]] = []
    for path in root.glob("*/manifest.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_id = str(payload.get("run_id") or path.parent.name)
        if run_id == current_run_id or payload.get("lineage_key") != lineage_key:
            continue
        candidates.append((str(payload.get("created_at") or ""), run_id))
    return max(candidates)[1] if candidates else None


def _new_manifest(spec: ManagedCommandSpec, manifest_path: Path) -> dict[str, Any]:
    run_id = manifest_path.parent.name
    created_at = utc_now()
    retry_of = spec.retry_of_run_id
    if retry_of is None and spec.lineage_key:
        retry_of = _latest_lineage_run(manifest_path.parent.parent, spec.lineage_key, run_id)
    result_path = manifest_path.parent / "result.json"
    log_path = manifest_path.parent / "run.log"
    payload: dict[str, Any] = {
        "schema_version": MANAGED_AGENT_SCHEMA,
        "custodian": MANAGED_AGENT_CUSTODIAN,
        "run_id": run_id,
        "run_kind": spec.run_kind,
        "backend": spec.backend,
        "model": spec.model,
        "reasoning_effort": spec.reasoning_effort,
        "route_class": spec.route_class,
        "task_kind": spec.task_kind,
        "difficulty": spec.difficulty,
        "project_dir": str(spec.project_dir.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "log_path": str(log_path.resolve()),
        "full_log_path": str(log_path.resolve()),
        "result_path": str(result_path.resolve()),
        "launch_idempotency_key": spec.identity_key,
        "command_display": spec.command_display,
        "command_sha256": _command_hash(spec.argv),
        "links": dict(spec.links),
        "lineage_key": spec.lineage_key,
        "parent_run_id": spec.parent_run_id,
        "retry_of_run_id": retry_of,
        "created_at": created_at,
        "updated_at": created_at,
        "completion_delivery": {
            "transport": "non_discord",
            "status": "not_applicable",
            "attempt_count": 0,
            "evidence": "automatic_internal_run_has_no_inbound_reply_contract",
        },
        "status": "reserved",
        "status_history": [
            {"status": "reserved", "at": created_at, "evidence": "manifest_committed_before_process_launch"}
        ],
    }
    return {key: value for key, value in payload.items() if value is not None}


def reserve_managed_command(spec: ManagedCommandSpec) -> tuple[Path, dict[str, Any], bool]:
    root = _root_for(spec)
    root.mkdir(parents=True, exist_ok=True)
    run_id = stable_managed_run_id(spec.run_kind, spec.identity_key)
    run_dir = root / run_id
    manifest_path = run_dir / "manifest.json"
    with (root / ".launch.lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        if manifest_path.exists():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("launch_idempotency_key") != spec.identity_key:
                raise RuntimeError(f"managed run identity collision: {run_id}")
            return manifest_path, payload, False
        run_dir.mkdir(parents=False, exist_ok=False)
        payload = _new_manifest(spec, manifest_path)
        atomic_write_manifest(manifest_path, payload)
        Path(str(payload["result_path"])).touch()
        Path(str(payload["log_path"])).touch()
        return manifest_path, payload, True


def _bind_repair_claim(manifest: dict[str, Any]) -> None:
    links = manifest.get("links")
    if not isinstance(links, dict):
        return
    queue_dir = str(links.get("repair_queue_dir") or "")
    blocker_id = str(links.get("blocker_id") or "")
    request_id = str(links.get("repair_request_id") or "")
    if not queue_dir or not blocker_id or not request_id:
        return
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        active_repair_claim_lock_dir,
        bind_managed_run_to_active_claim,
        owner_metadata_path,
    )

    bound = bind_managed_run_to_active_claim(
        queue_dir,
        blocker_id=blocker_id,
        request_id=request_id,
        managed_run_id=str(manifest["run_id"]),
        managed_manifest_path=str(manifest["manifest_path"]),
        expected_owner_pid=int(os.environ.get("CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID") or 0) or None,
        new_owner_pid=os.getpid(),
    )
    if not bound:
        raise RuntimeError("repair claim could not be fenced to managed run")
    claim_dir = active_repair_claim_lock_dir(queue_dir, blocker_id)
    manifest["repair_claim"] = {
        "kind": "active_repair_request_claim",
        "request_id": request_id,
        "blocker_id": blocker_id,
        "claim_lock_dir": str(claim_dir),
        "owner_metadata_path": str(owner_metadata_path(claim_dir)),
        "fenced_managed_run_id": str(manifest["run_id"]),
        "owner_pid": os.getpid(),
        "bound_at": utc_now(),
    }


def _emit_attempt(manifest: Mapping[str, Any]) -> tuple[str, str] | None:
    links = manifest.get("links")
    if not isinstance(links, Mapping):
        return None
    incident_id = str(links.get("incident_id") or "")
    if not incident_id:
        return None
    if manifest.get("incident_claim_event_id") and manifest.get("incident_attempt_event_id"):
        return (
            str(manifest["incident_claim_event_id"]),
            str(manifest["incident_attempt_event_id"]),
        )
    from arnold_pipelines.megaplan.cloud import incident_bridge

    evidence = [{
        "kind": "managed_agent_execution",
        "run_id": manifest.get("run_id"),
        "manifest_path": manifest.get("manifest_path"),
        "repair_request_id": links.get("repair_request_id"),
        "blocker_id": links.get("blocker_id"),
    }]
    actor = "meta_repair" if str(manifest.get("run_kind") or "").startswith("automatic_meta") else "immediate_repair"
    claim_event = incident_bridge.append_managed_repair_claim(
        incident_id=incident_id,
        claim_id=f"managed:{manifest.get('run_id')}",
        actor=actor,
        summary=f"managed {manifest.get('run_kind')} accepted execution custody",
        evidence=evidence,
        session_id=str(links.get("cloud_session") or "") or None,
        problem_id=str(links.get("problem_id") or "") or None,
        next_expected_event=(
            "meta_repair.repair_attempt"
            if actor == "meta_repair"
            else "immediate_repair.repair_attempt"
        ),
        links={"managed_agent": str(manifest.get("manifest_path"))},
        root=str(manifest.get("project_dir") or "."),
    )
    claim_event_id = str(
        claim_event.get("event_id")
        or dict(claim_event.get("payload") or {}).get("event_id")
        or ""
    )
    kwargs = dict(
        incident_id=incident_id,
        summary=f"managed {manifest.get('run_kind')} execution started",
        attempt_id=str(manifest.get("run_id")),
        outcome="attempted",
        evidence=evidence,
        session_id=str(links.get("cloud_session") or "") or None,
        problem_id=str(links.get("problem_id") or "") or None,
        parent_event_ids=[claim_event_id] if claim_event_id else [],
        links={"managed_agent": str(manifest.get("manifest_path"))},
        root=str(manifest.get("project_dir") or "."),
    )
    if manifest.get("run_kind") == "automatic_meta_repair":
        attempt_event = incident_bridge.append_meta_repair_attempt(**kwargs)
    else:
        attempt_event = incident_bridge.append_immediate_repair_attempt(**kwargs)
    attempt_event_id = str(
        attempt_event.get("event_id")
        or dict(attempt_event.get("payload") or {}).get("event_id")
        or ""
    )
    return claim_event_id, attempt_event_id


def _write_result(manifest: Mapping[str, Any]) -> None:
    result = {
        "schema_version": 1,
        "run_id": manifest.get("run_id"),
        "run_kind": manifest.get("run_kind"),
        "status": manifest.get("status"),
        "terminal_outcome": manifest.get("terminal_outcome"),
        "returncode": manifest.get("returncode"),
        "finished_at": manifest.get("finished_at"),
        "error_class": manifest.get("error_class"),
    }
    path = Path(str(manifest["result_path"]))
    atomic_write_manifest(path, result)


def _wait_for_adopted_worker(manifest_path: Path, manifest: dict[str, Any]) -> int:
    _append_status(manifest, "adopting", evidence="restart_found_live_worker")
    manifest["pid"] = os.getpid()
    atomic_write_manifest(manifest_path, manifest)
    worker_pid = manifest.get("worker_pid")
    while _pid_matches(
        worker_pid,
        str(manifest.get("worker_cmdline_sha256") or ""),
        str(manifest.get("worker_start_ticks") or ""),
    ):
        time.sleep(1)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _append_status(manifest, "unknown", evidence="adopted_worker_exited_without_wait_status")
    manifest["terminal_outcome"] = "unknown_after_adoption"
    manifest["finished_at"] = utc_now()
    manifest["returncode"] = 1
    atomic_write_manifest(manifest_path, manifest)
    _write_result(manifest)
    return 1


def run_managed_command(spec: ManagedCommandSpec, *, run_id_file: Path | None = None) -> int:
    manifest_path, manifest, created = reserve_managed_command(spec)
    if run_id_file is not None:
        run_id_file.parent.mkdir(parents=True, exist_ok=True)
        run_id_file.write_text(str(manifest["run_id"]) + "\n", encoding="utf-8")
    execution_handle = (manifest_path.parent / ".execution.lock").open("a+b")
    try:
        fcntl.flock(execution_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        execution_handle.close()
        return 0
    try:
        return _run_managed_command_locked(spec, manifest_path, manifest, created)
    finally:
        fcntl.flock(execution_handle.fileno(), fcntl.LOCK_UN)
        execution_handle.close()


def _run_managed_command_locked(
    spec: ManagedCommandSpec,
    manifest_path: Path,
    manifest: dict[str, Any],
    created: bool,
) -> int:
    status = str(manifest.get("status") or "unknown")
    if not created:
        observed, live = observed_status(manifest, manifest_path)
        if live and _pid_matches(
            manifest.get("worker_pid"),
            str(manifest.get("worker_cmdline_sha256") or ""),
            str(manifest.get("worker_start_ticks") or ""),
        ):
            if _pid_matches(
                manifest.get("pid"),
                str(manifest.get("supervisor_cmdline_sha256") or ""),
                str(manifest.get("supervisor_start_ticks") or ""),
            ):
                return 0
            return _wait_for_adopted_worker(manifest_path, manifest)
        if status in TERMINAL_STATUSES:
            return int(manifest.get("returncode") or (0 if status == "completed" else 1))
        _append_status(manifest, "launching", evidence="restart_reconciled_dead_supervisor_same_run")
        manifest["restart_count"] = int(manifest.get("restart_count") or 0) + 1
    else:
        _append_status(manifest, "launching", evidence="supervisor_start")

    manifest["pid"] = os.getpid()
    manifest["supervisor_start_ticks"] = _pid_start_ticks(os.getpid())
    try:
        raw = Path(f"/proc/{os.getpid()}/cmdline").read_bytes()
        manifest["supervisor_cmdline_sha256"] = hashlib.sha256(raw).hexdigest()
    except OSError:
        pass
    manifest["started_at"] = manifest.get("started_at") or utc_now()
    atomic_write_manifest(manifest_path, manifest)

    child: subprocess.Popen[bytes] | None = None
    interrupted: int | None = None

    def stop(signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = signum
        if child is not None and child.poll() is None:
            child.terminate()

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        _bind_repair_claim(manifest)
        atomic_write_manifest(manifest_path, manifest)
        emitted = _emit_attempt(manifest)
        if emitted is not None:
            manifest["incident_claim_event_id"], manifest["incident_attempt_event_id"] = emitted
            atomic_write_manifest(manifest_path, manifest)
        env = os.environ.copy()
        env["ARNOLD_MANAGED_AGENT_RUN_ID"] = str(manifest["run_id"])
        env["ARNOLD_MANAGED_AGENT_MANIFEST"] = str(manifest_path)
        if spec.run_kind == "automatic_repair" and env.get("CLOUD_WATCHDOG_REPAIR_REQUEST_ID"):
            env["CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID"] = str(os.getpid())
        child_stdin = spec.stdin_path.open("rb") if spec.stdin_path is not None else subprocess.DEVNULL
        child = subprocess.Popen(
            list(spec.argv),
            cwd=str(spec.project_dir),
            stdin=child_stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        if spec.stdin_path is not None:
            child_stdin.close()
        raw_cmdline = b"\0".join(os.fsencode(item) for item in spec.argv) + b"\0"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["worker_pid"] = child.pid
        manifest["worker_start_ticks"] = _pid_start_ticks(child.pid)
        manifest["worker_started_at"] = utc_now()
        manifest["worker_cmdline_sha256"] = hashlib.sha256(raw_cmdline).hexdigest()
        _append_status(manifest, "running", evidence="worker_process_started")
        atomic_write_manifest(manifest_path, manifest)
        log_path = Path(str(manifest["log_path"]))
        with log_path.open("ab") as log:
            assert child.stdout is not None
            while True:
                chunk = child.stdout.read(65536)
                if not chunk:
                    break
                log.write(chunk)
                log.flush()
                if spec.tee_output:
                    try:
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
                    except BrokenPipeError:
                        pass
        returncode = child.wait()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        control_terminal = str(manifest.get("status") or "")
        terminal = (
            control_terminal
            if control_terminal in {"cancelled", "superseded"}
            else (
                "interrupted"
                if interrupted is not None
                else ("completed" if returncode == 0 else "failed")
            )
        )
        _append_status(manifest, terminal, evidence="worker_process_waited", returncode=returncode)
        manifest["returncode"] = returncode
        manifest["terminal_outcome"] = terminal
        manifest["finished_at"] = utc_now()
        if interrupted is not None:
            manifest["signal"] = interrupted
        atomic_write_manifest(manifest_path, manifest)
        _write_result(manifest)
        return returncode
    except BaseException as exc:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        control_terminal = str(manifest.get("status") or "")
        terminal = (
            control_terminal
            if control_terminal in {"cancelled", "superseded"}
            else ("interrupted" if interrupted is not None else "failed")
        )
        _append_status(manifest, terminal, evidence="supervisor_exception")
        manifest["returncode"] = 128 + interrupted if interrupted is not None else 1
        manifest["terminal_outcome"] = terminal
        manifest["error"] = "managed process supervisor failed"
        manifest["error_class"] = exc.__class__.__name__
        manifest["finished_at"] = utc_now()
        atomic_write_manifest(manifest_path, manifest)
        _write_result(manifest)
        return int(manifest["returncode"])
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def transition_terminal(manifest_path: Path, status: str, *, reason: str) -> dict[str, Any]:
    if status not in {"cancelled", "superseded"}:
        raise ValueError("terminal transition must be cancelled or superseded")
    with (manifest_path.parent / ".transition.lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if str(payload.get("status")) in TERMINAL_STATUSES:
            return payload
        for field in ("worker_pid", "pid"):
            pid = payload.get(field)
            prefix = "worker" if field == "worker_pid" else "supervisor"
            if _pid_matches(
                pid,
                str(payload.get(f"{prefix}_cmdline_sha256") or ""),
                str(payload.get(f"{prefix}_start_ticks") or ""),
            ):
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except OSError:
                    pass
        _append_status(payload, status, evidence="explicit_control_plane_transition", reason=reason)
        payload["terminal_outcome"] = status
        payload["returncode"] = 143
        payload["finished_at"] = utc_now()
        atomic_write_manifest(manifest_path, payload)
        _write_result(payload)
        return payload


def _parse_links(values: Sequence[str]) -> dict[str, Any]:
    links: dict[str, Any] = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"link must be KEY=VALUE: {value!r}")
        links[key.strip()] = raw
    return links


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m arnold_pipelines.megaplan.managed_agent")
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--run-kind", required=True)
    run.add_argument("--identity-key", required=True)
    run.add_argument("--project-dir", required=True)
    run.add_argument("--run-root")
    run.add_argument("--task-kind", required=True)
    run.add_argument("--difficulty", type=int, required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--reasoning-effort", required=True)
    run.add_argument("--route-class", required=True)
    run.add_argument("--backend", required=True)
    run.add_argument("--command-display", required=True)
    run.add_argument("--parent-run-id")
    run.add_argument("--retry-of-run-id")
    run.add_argument("--lineage-key")
    run.add_argument("--run-id-file")
    run.add_argument("--stdin-file")
    run.add_argument("--link", action="append", default=[])
    run.add_argument("command", nargs=argparse.REMAINDER)
    transition = sub.add_parser("transition")
    transition.add_argument("manifest")
    transition.add_argument("status", choices=("cancelled", "superseded"))
    transition.add_argument("--reason", required=True)
    identity = sub.add_parser("identity")
    identity.add_argument("run_kind")
    identity.add_argument("identity_key")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.action == "identity":
        print(stable_managed_run_id(args.run_kind, args.identity_key))
        return 0
    if args.action == "transition":
        transition_terminal(Path(args.manifest), args.status, reason=args.reason)
        return 0
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("managed command is required after --")
    if not 1 <= args.difficulty <= 10:
        raise SystemExit("difficulty must be D1-D10")
    spec = ManagedCommandSpec(
        run_kind=args.run_kind,
        identity_key=args.identity_key,
        project_dir=Path(args.project_dir).resolve(),
        argv=tuple(command),
        task_kind=args.task_kind,
        difficulty=args.difficulty,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        route_class=args.route_class,
        backend=args.backend,
        command_display=args.command_display,
        links=_parse_links(args.link),
        parent_run_id=args.parent_run_id,
        retry_of_run_id=args.retry_of_run_id,
        lineage_key=args.lineage_key,
        run_root=Path(args.run_root).resolve() if args.run_root else None,
        stdin_path=Path(args.stdin_file).resolve() if args.stdin_file else None,
    )
    return run_managed_command(
        spec,
        run_id_file=Path(args.run_id_file) if args.run_id_file else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTIVE_STATUSES",
    "AUTOMATIC_RUN_KINDS",
    "DEFAULT_RUN_ROOT",
    "LEGACY_RESIDENT_CUSTODIAN",
    "LEGACY_RESIDENT_SCHEMA",
    "MANAGED_AGENT_CUSTODIAN",
    "MANAGED_AGENT_SCHEMA",
    "ManagedCommandSpec",
    "TERMINAL_STATUSES",
    "atomic_write_manifest",
    "is_managed_manifest",
    "managed_run_roots",
    "observed_status",
    "reserve_managed_command",
    "run_managed_command",
    "stable_managed_run_id",
    "transition_terminal",
]
