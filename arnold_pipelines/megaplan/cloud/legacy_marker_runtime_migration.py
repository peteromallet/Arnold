"""One-time, fail-closed migration for identity-less cloud session markers."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.chain.execution_binding import (
    verify_external_runtime_identity,
)
from arnold_pipelines.megaplan.cloud.runtime_cutover import (
    MARKER_RUNTIME_SCHEMA,
    marker_runtime_identity,
    normalize_runtime_identity,
)
from arnold_pipelines.megaplan.types import CliError


MIGRATION_SCHEMA = "arnold.megaplan.legacy_marker_runtime_migration.v1"
_FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_ROOT = re.compile(r"/workspace/runtime-candidates/[A-Za-z0-9._-]+")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _read_object(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            "runtime_marker_migration_invalid", f"{label} is unreadable or invalid"
        ) from exc
    if not isinstance(value, dict):
        raise CliError(
            "runtime_marker_migration_invalid", f"{label} must be an object"
        )
    return raw, value


def _write_immutable(path: Path, value: Mapping[str, Any]) -> None:
    encoded = _canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise CliError(
                    "runtime_marker_migration_evidence_collision",
                    f"immutable migration evidence differs at {path}",
                )
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _bound_chain_identity(
    state: Mapping[str, Any],
    *,
    runtime_sha256: str,
    current_plan: str,
    remote_spec: str,
) -> dict[str, Any]:
    metadata = state.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    pause = metadata.get("operator_pause")
    if (
        state.get("last_state") != "paused"
        or not isinstance(pause, Mapping)
        or pause.get("active") is not True
    ):
        raise CliError(
            "runtime_marker_migration_unsafe",
            "legacy marker migration requires a durably paused chain",
        )
    if state.get("current_plan_name") != current_plan:
        raise CliError(
            "runtime_marker_migration_chain_mismatch",
            "legacy marker migration current plan guard does not match chain state",
        )
    binding = metadata.get("execution_binding")
    binding = binding if isinstance(binding, Mapping) else {}
    if binding.get("spec_path") != remote_spec:
        raise CliError(
            "runtime_marker_migration_chain_mismatch",
            "legacy marker migration remote spec disagrees with chain binding",
        )
    runtime = binding.get("runtime_binding")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    identity = runtime.get("current_identity")
    if not isinstance(identity, Mapping):
        raise CliError(
            "runtime_marker_migration_chain_mismatch",
            "legacy marker migration chain binding has no runtime identity",
        )
    normalized = normalize_runtime_identity(identity)
    if (
        not _FULL_SHA256.fullmatch(runtime_sha256)
        or identity.get("content_sha256") != runtime_sha256
        or normalized["content_sha256"] != runtime_sha256
    ):
        raise CliError(
            "runtime_marker_migration_chain_mismatch",
            "legacy marker migration chain runtime digest is invalid or changed",
        )
    return normalized


def _validate_marker(
    marker: Mapping[str, Any],
    *,
    session: str,
    workspace: str,
    remote_spec: str,
    runtime_root: str,
    relaunch_sha256: str,
) -> str:
    if marker_runtime_identity(marker) is not None or marker.get("runtime_binding") is not None:
        raise CliError(
            "runtime_marker_migration_not_legacy",
            "marker already has a runtime identity; use ordinary runtime cutover",
        )
    expected = {"session": session, "workspace": workspace, "remote_spec": remote_spec}
    if any(marker.get(key) != value for key, value in expected.items()):
        raise CliError(
            "runtime_marker_migration_marker_mismatch",
            "legacy marker identity fields changed or are ambiguous",
        )
    pause = marker.get("operator_pause")
    if marker.get("should_run") is not False:
        raise CliError(
            "runtime_marker_migration_unsafe",
            "legacy marker migration requires should_run=false",
        )
    if not isinstance(pause, Mapping) or pause.get("active") is not True:
        raise CliError(
            "runtime_marker_migration_unsafe",
            "legacy marker migration requires marker-side operator-pause authority",
        )
    if marker.get("retired") is True:
        raise CliError("runtime_marker_migration_unsafe", "retired markers cannot be migrated")
    command = str(marker.get("relaunch_command") or "")
    if not _FULL_SHA256.fullmatch(relaunch_sha256) or _sha(command.encode()) != relaunch_sha256:
        raise CliError(
            "runtime_marker_migration_relaunch_mismatch",
            "legacy marker relaunch command hash is invalid or changed",
        )
    expected_root = str(Path(runtime_root).resolve(strict=False))
    observed_roots = {
        str(Path(item).resolve(strict=False)) for item in _RUNTIME_ROOT.findall(command)
    }
    if observed_roots != {expected_root}:
        raise CliError(
            "runtime_marker_migration_relaunch_mismatch",
            "legacy marker relaunch command does not name exactly the expected runtime candidate",
        )
    return command


def migrate_legacy_marker_runtime(
    marker_path: Path,
    *,
    expected_marker_sha256: str,
    expected_relaunch_command_sha256: str,
    expected_legacy_runtime_root: str,
    expected_chain_runtime_sha256: str,
    expected_session: str,
    expected_workspace: str,
    expected_remote_spec: str,
    expected_current_plan: str,
    chain_state_path: Path,
    runtime_identity_path: Path,
    runtime_provenance_receipt_path: Path,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Bind a paused identity-less marker to its proven current runtime."""

    required = (
        expected_session,
        expected_workspace,
        expected_remote_spec,
        expected_current_plan,
        reason,
        actor,
    )
    if any(not str(value).strip() for value in required) or not _FULL_SHA256.fullmatch(
        expected_marker_sha256
    ):
        raise CliError("runtime_marker_migration_invalid", "all exact guards are required")
    marker_path = marker_path.resolve(strict=False)
    chain_state_path = chain_state_path.resolve(strict=False)
    identity_path = runtime_identity_path.resolve(strict=False)
    receipt_path = runtime_provenance_receipt_path.resolve(strict=False)
    identity_raw, _ = _read_object(identity_path, label="runtime identity")
    receipt_raw, _ = _read_object(receipt_path, label="runtime provenance receipt")
    verified = normalize_runtime_identity(
        verify_external_runtime_identity(identity_path, receipt_path)
    )
    expected_root = str(Path(expected_legacy_runtime_root).resolve(strict=False))
    if str(Path(str(verified["import_root"])).resolve(strict=False)) != expected_root:
        raise CliError(
            "runtime_marker_migration_runtime_mismatch",
            "verified runtime identity does not match the expected legacy root",
        )
    chain_raw, chain_state = _read_object(chain_state_path, label="chain state")
    chain_identity = _bound_chain_identity(
        chain_state,
        runtime_sha256=expected_chain_runtime_sha256,
        current_plan=expected_current_plan,
        remote_spec=expected_remote_spec,
    )
    if chain_identity != verified:
        raise CliError(
            "runtime_marker_migration_runtime_mismatch",
            "verified runtime identity disagrees with the paused chain binding",
        )

    lock_path = marker_path.with_suffix(marker_path.suffix + ".runtime-cutover.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        marker_raw, marker = _read_object(marker_path, label="legacy marker")
        marker_before = _sha(marker_raw)
        if marker_before != expected_marker_sha256:
            raise CliError(
                "runtime_marker_migration_cas_mismatch",
                "legacy marker changed before migration",
            )
        _validate_marker(
            marker,
            session=expected_session,
            workspace=expected_workspace,
            remote_spec=expected_remote_spec,
            runtime_root=expected_root,
            relaunch_sha256=expected_relaunch_command_sha256,
        )
        if (
            chain_state_path.read_bytes() != chain_raw
            or identity_path.read_bytes() != identity_raw
            or receipt_path.read_bytes() != receipt_raw
        ):
            raise CliError(
                "runtime_marker_migration_cas_mismatch",
                "chain/runtime evidence changed during migration",
            )
        core = {
            "schema": MIGRATION_SCHEMA,
            "session": expected_session,
            "marker_before_sha256": marker_before,
            "relaunch_command_sha256": expected_relaunch_command_sha256,
            "chain_state_sha256": _sha(chain_raw),
            "runtime_sha256": expected_chain_runtime_sha256,
            "runtime_identity_sha256": _sha(identity_raw),
            "runtime_provenance_receipt_sha256": _sha(receipt_raw),
        }
        migration_id = _sha(_canonical(core))
        run_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"arnold.megaplan.marker-migration:{migration_id}")
        )
        evidence_root = marker_path.parent / "runtime-marker-migrations" / expected_session
        prepared_path = evidence_root / f"{migration_id}.prepared.json"
        evidence_ref = prepared_path.relative_to(marker_path.parent).as_posix()
        changed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        marker["runtime_binding"] = {
            "schema": MARKER_RUNTIME_SCHEMA,
            "current_identity": verified,
            "last_rebound_at": changed_at,
            "rebind_events": [],
            "legacy_migration": {
                "schema": MIGRATION_SCHEMA,
                "migration_id": migration_id,
                "marker_before_sha256": marker_before,
                "evidence_ref": evidence_ref,
            },
        }
        marker["editable_source_head"] = verified["source_revision"]
        marker["editable_install_sync"] = {
            "status": "content-addressed-runtime",
            "source": verified["import_root"],
            "runtime_sha256": verified["content_sha256"],
        }
        marker["run_id"] = run_id
        marker["updated_at"] = changed_at
        encoded = (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode()
        marker_after = _sha(encoded)
        prepared = {
            **core,
            "migration_id": migration_id,
            "marker_after_sha256": marker_after,
            "run_id": run_id,
            "runtime_root": verified["import_root"],
            "runtime_revision": verified["source_revision"],
            "marker_path": str(marker_path),
            "chain_state_path": str(chain_state_path),
            "actor": actor,
            "reason": reason,
            "prepared_at": changed_at,
        }
        _write_immutable(prepared_path, prepared)
        descriptor, temporary = tempfile.mkstemp(dir=marker_path.parent, prefix=marker_path.name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, marker_path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        committed_path = evidence_root / f"{migration_id}.committed.json"
        _write_immutable(
            committed_path,
            {
                "schema": f"{MIGRATION_SCHEMA}.commit",
                "migration_id": migration_id,
                "marker_after_sha256": marker_after,
                "receipt_ref": evidence_ref,
                "receipt_sha256": _sha(prepared_path.read_bytes()),
                "committed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
    return {
        "marker_path": str(marker_path),
        "marker_before_sha256": marker_before,
        "marker_after_sha256": marker_after,
        "runtime_sha256": expected_chain_runtime_sha256,
        "run_id": run_id,
        "migration_id": migration_id,
        "receipt_path": str(prepared_path),
        "commit_path": str(committed_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--expect-marker-sha256", required=True)
    parser.add_argument("--expect-relaunch-command-sha256", required=True)
    parser.add_argument("--expect-legacy-runtime-root", required=True)
    parser.add_argument("--expect-chain-runtime-sha256", required=True)
    parser.add_argument("--expect-session", required=True)
    parser.add_argument("--expect-workspace", required=True)
    parser.add_argument("--expect-remote-spec", required=True)
    parser.add_argument("--expect-current-plan", required=True)
    parser.add_argument("--chain-state", type=Path, required=True)
    parser.add_argument("--runtime-identity", type=Path, required=True)
    parser.add_argument("--runtime-provenance-receipt", type=Path, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--actor", default="operator")
    args = parser.parse_args(argv)
    result = migrate_legacy_marker_runtime(
        args.marker,
        expected_marker_sha256=args.expect_marker_sha256,
        expected_relaunch_command_sha256=args.expect_relaunch_command_sha256,
        expected_legacy_runtime_root=args.expect_legacy_runtime_root,
        expected_chain_runtime_sha256=args.expect_chain_runtime_sha256,
        expected_session=args.expect_session,
        expected_workspace=args.expect_workspace,
        expected_remote_spec=args.expect_remote_spec,
        expected_current_plan=args.expect_current_plan,
        chain_state_path=args.chain_state,
        runtime_identity_path=args.runtime_identity,
        runtime_provenance_receipt_path=args.runtime_provenance_receipt,
        reason=args.reason,
        actor=args.actor,
    )
    print(json.dumps({"success": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
