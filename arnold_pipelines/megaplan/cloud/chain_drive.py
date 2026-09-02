"""Durable producer for a manifest-bound Megaplan chain drive.

The chain wrapper is often launched by a short-lived supervisor.  A foreground
``chain start`` therefore makes the supervisor the accidental owner of the
driver.  This module transfers ownership to AgentBox before returning to the
wrapper.  The custody receipt is deliberately written only after AgentBox has
persisted the process-session resource.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
from typing import Any, Sequence

from arnold.runtime.durable_ops import ResourceType

from agentbox.config import load_agentbox_config
from agentbox.host import HostLaunchResult, prepare_host_resources, start_host_session
from agentbox.operations import load_agentbox_operation, open_operation_store
from agentbox.tmux import inspect_session


RECEIPT_SCHEMA = "arnold.megaplan.chain_drive_launch_receipt.v1"
OPERATION_PREFIX = "megaplan-chain-drive-"


class ChainDriveError(RuntimeError):
    """Raised when durable chain-drive custody cannot be established."""


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return None


def _canonical_key(values: dict[str, Any]) -> str:
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _operation_id(key: str) -> str:
    return OPERATION_PREFIX + _sha256_bytes(key.encode("utf-8"))[:40]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _command(
    *,
    session: str,
    engine_dir: Path,
    interpreter: Path,
    spec: Path,
    project_dir: Path,
    canonical_log: Path,
    one: bool,
) -> str:
    boundary_lib = '/usr/local/bin/arnold-launch-boundary'
    boundary = (
        'if [[ -f /workspace/.cloud-hot-env ]]; then set -a; '
        '. /workspace/.cloud-hot-env; set +a; fi; '
        f'ARNOLD_LAUNCH_BOUNDARY={shlex.quote(boundary_lib)}; '
        'if [[ ! -r "$ARNOLD_LAUNCH_BOUNDARY" ]]; then '
        f'ARNOLD_LAUNCH_BOUNDARY={shlex.quote(str(engine_dir / "arnold_pipelines/megaplan/cloud/wrappers/arnold-launch-boundary"))}; '
        'fi; if [[ ! -r "$ARNOLD_LAUNCH_BOUNDARY" ]]; then '
        'echo "[megaplan-chain-drive] launch_boundary_unavailable" >&2; exit 78; fi; '
        '. "$ARNOLD_LAUNCH_BOUNDARY"; '
        f'arnold_materialize_launch_boundary {shlex.quote(session)} '
        f'{shlex.quote(str(engine_dir))} {shlex.quote(str(engine_dir))}; '
    )
    argv: list[str] = [
        "env",
        "-u",
        "PYTHONHOME",
        "PYTHONSAFEPATH=1",
        f"PYTHONPATH={engine_dir}",
        "MEGAPLAN_TRUSTED_CONTAINER=1",
        str(interpreter),
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
        str(spec),
        "--project-dir",
        str(project_dir),
    ]
    if one:
        argv.append("--one")
    return boundary + shlex.join(argv) + f" >> {shlex.quote(str(canonical_log))} 2>&1"


def _existing_process(config: Any, operation_id: str) -> Any | None:
    for resource in open_operation_store(config).list_typed_resources(operation_id):
        if resource.resource_type is ResourceType.PROCESS_SESSION:
            return resource
    return None


def _existing_process_resources(config: Any, operation_id: str) -> tuple[Any, ...]:
    return tuple(
        resource
        for resource in open_operation_store(config).list_typed_resources(operation_id)
        if resource.resource_type is ResourceType.PROCESS_SESSION
    )


def _receipt(
    *,
    session: str,
    occurrence: str,
    plan: str,
    workspace: Path,
    operation_id: str,
    operation_key: str,
    command: str,
    process_resource: Any,
    manifest: Path,
    spec: Path,
    seed: Path | None,
) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "session": session,
        "occurrence_digest": occurrence,
        "plan": plan,
        "workspace": str(workspace),
        "status": "running",
        "created_at": _utcnow(),
        "operation_id": operation_id,
        "operation_key_sha256": _sha256_bytes(operation_key.encode("utf-8")),
        "command": command,
        "command_sha256": _sha256_bytes(command.encode("utf-8")),
        "process_resource_id": process_resource.id,
        "process_resource_type": process_resource.resource_type.value,
        "process_resource": {
            "id": process_resource.id,
            "operation_id": process_resource.operation_id,
            "name": process_resource.name,
            "details": dict(process_resource.details),
        },
        "manifest_path": str(manifest),
        "manifest_sha256": _sha256_file(manifest),
        "spec_path": str(spec),
        "spec_sha256": _sha256_file(spec),
        "seed_path": str(seed) if seed else None,
        "seed_sha256": _sha256_file(seed) if seed else None,
        "custody": {
            "persist": True,
            "detached": True,
            "pty": False,
            "restart": "no",
            "ready_matcher": None,
        },
    }


def launch_chain_drive(
    *,
    session: str,
    occurrence: str,
    plan: str,
    workspace: Path,
    spec: Path,
    engine_dir: Path,
    interpreter: Path,
    manifest: Path,
    receipt_path: Path,
    canonical_log: Path,
    one: bool = False,
    seed: Path | None = None,
) -> dict[str, Any]:
    """Create or join one durable chain-drive operation."""
    if not all((session, occurrence, plan)):
        raise ChainDriveError("chain-drive custody requires session, occurrence, and plan")
    command = _command(
        session=session,
        engine_dir=engine_dir,
        interpreter=interpreter,
        spec=spec,
        project_dir=workspace,
        canonical_log=canonical_log,
        one=one,
    )
    key_values = {
        "session": session,
        "occurrence_digest": occurrence,
        "plan": plan,
        "spec_sha256": _sha256_file(spec),
        "manifest_sha256": _sha256_file(manifest),
        "manifest_revision": _manifest_revision(manifest),
        "seed_sha256": _sha256_file(seed) if seed else None,
        "command_sha256": _sha256_bytes(command.encode("utf-8")),
    }
    operation_key = _canonical_key(key_values)
    operation_id = _operation_id(operation_key)
    config = load_agentbox_config()

    existing = None
    try:
        existing = load_agentbox_operation(config, operation_id)
    except (KeyError, ValueError):
        existing = None
    if existing is not None:
        process_resources = _existing_process_resources(config, operation_id)
        if not process_resources:
            raise ChainDriveError(
                f"existing chain-drive operation {operation_id} has no process resource"
            )
        for process_resource in reversed(process_resources):
            status = inspect_session(process_resource.name)
            if status.exists:
                payload = _receipt(
                    session=session,
                    occurrence=occurrence,
                    plan=plan,
                    workspace=workspace,
                    operation_id=operation_id,
                    operation_key=operation_key,
                    command=command,
                    process_resource=process_resource,
                    manifest=manifest,
                    spec=spec,
                    seed=seed,
                )
                _atomic_write(receipt_path, payload)
                return payload

        # A supervisor/session can die after the operation is durably created.
        # Reuse that occurrence-bound operation, but record a distinct process
        # resource for the replacement session instead of returning a dead
        # resource as if it were live.
        prepared = prepare_host_resources(
            config,
            operation_id,
            operation_type="megaplan_chain",
            command=command,
            repo_names=(),
            launch_intent="megaplan_chain_drive_retry",
            metadata={
                "chain_drive_key": key_values,
                "session": session,
                "occurrence_digest": occurrence,
                "plan": plan,
                "workspace": str(workspace),
                "manifest": str(manifest),
            },
        )
        process_resource = start_host_session(
            config,
            prepared,
            command=command,
            cwd=workspace,
            process_resource_id=(
                f"{operation_id}:process-session:retry-{len(process_resources)}"
            ),
        ).process_session_resource
        if process_resource is None:
            raise ChainDriveError(
                f"replacement chain-drive operation {operation_id} returned no process resource"
            )
        payload = _receipt(
            session=session,
            occurrence=occurrence,
            plan=plan,
            workspace=workspace,
            operation_id=operation_id,
            operation_key=operation_key,
            command=command,
            process_resource=process_resource,
            manifest=manifest,
            spec=spec,
            seed=seed,
        )
        _atomic_write(receipt_path, payload)
        return payload

    prepared = prepare_host_resources(
        config,
        operation_id,
        operation_type="megaplan_chain",
        command=command,
        repo_names=(),
        launch_intent="megaplan_chain_drive",
        metadata={
            "chain_drive_key": key_values,
            "session": session,
            "occurrence_digest": occurrence,
            "plan": plan,
            "workspace": str(workspace),
            "manifest": str(manifest),
        },
    )
    result: HostLaunchResult = start_host_session(
        config, prepared, command=command, cwd=workspace
    )
    process_resource = result.process_session_resource
    if process_resource is None or process_resource.resource_type is not ResourceType.PROCESS_SESSION:
        raise ChainDriveError("AgentBox launch returned no typed process-session resource")
    payload = _receipt(
        session=session,
        occurrence=occurrence,
        plan=plan,
        workspace=workspace,
        operation_id=operation_id,
        operation_key=operation_key,
        command=command,
        process_resource=process_resource,
        manifest=manifest,
        spec=spec,
        seed=seed,
    )
    _atomic_write(receipt_path, payload)
    return payload


def _manifest_revision(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        epic = payload.get("epic", {})
        return str(epic.get("expected_head")) if epic.get("expected_head") else None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("session", "occurrence", "plan", "spec", "engine-dir", "interpreter", "manifest", "receipt", "canonical-log"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--seed", default=None)
    parser.add_argument("--one", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = launch_chain_drive(
        session=args.session,
        occurrence=args.occurrence,
        plan=args.plan,
        workspace=Path(args.project_dir),
        spec=Path(args.spec),
        engine_dir=Path(args.engine_dir),
        interpreter=Path(args.interpreter),
        manifest=Path(args.manifest),
        receipt_path=Path(args.receipt),
        canonical_log=Path(args.canonical_log),
        one=args.one,
        seed=Path(args.seed) if args.seed else None,
    )
    print(json.dumps({"success": True, "operation_id": payload["operation_id"], "receipt": args.receipt}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
