"""One-time, fail-closed migration for identity-less cloud session markers.

Contract
--------
``migrate_legacy_marker_runtime`` binds a PAUSED, identity-less session marker
to its independently-verified current runtime by writing a STRONG
``runtime_binding`` form onto the marker: ``runtime_binding.current_identity``
is the normalized, content-addressed identity built from the OLD verified
runtime receipt (``content_sha256``, ``import_root`` == the old runtime root,
``source_revision`` == the old expected head), so a subsequent ordinary
``update_marker_runtime`` CAS cutover (runtime_cutover) runs against the
strong form.  It is ONE-TIME: only markers with NO runtime identity at all
(no ``runtime_binding`` AND no legacy ``editable_source_head`` /
``editable_install_sync.source`` weak form) are migrated; a marker that
already carries either form is refused (``runtime_marker_migration_not_legacy``).
All guards are exact-CAS and fail closed with ZERO marker mutation on any
mismatch: marker SHA-256, relaunch-command SHA-256, the relaunch command must
name EXACTLY ONE ``/workspace/runtime-candidates/<slug>`` root equal to the
expected legacy runtime root, the chain state must be durably paused with the
expected plan/spec, and the externally verified runtime identity must equal
both the expected legacy root and the paused chain binding's identity.
Evidence receipts are written immutably under
``<marker-dir>/runtime-marker-migrations/<session>/``.

CLI
---
Invoke as a module (the same pattern as the other cloud migration CLIs;
``PYTHONPATH`` must name the checkout the marker's runtime lives in):

``python -P -m arnold_pipelines.megaplan.cloud.legacy_marker_runtime_migration \\
    --marker <path> \\
    --expect-marker-sha256 <64-hex> \\
    --expect-relaunch-command-sha256 <64-hex> \\
    --expect-legacy-runtime-root <old runtime root> \\
    --expect-chain-runtime-sha256 <64-hex> \\
    --expect-session <session> --expect-workspace <workspace> \\
    --expect-remote-spec <chain.yaml path> --expect-current-plan <plan> \\
    --chain-state <chain state.json> \\
    --runtime-identity <identity.json> \\
    --runtime-provenance-receipt <receipt.json> \\
    --reason <reason> [--actor <actor>]``

On success it prints a JSON object with ``success: true`` plus
``marker_before_sha256`` / ``marker_after_sha256``, ``migration_id``,
``run_id``, and the immutable ``receipt_path`` / ``commit_path``.  Exit code
2 with a typed error on any refusal (marker byte-unchanged).
"""

from __future__ import annotations

import argparse
import errno
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


_DIR_FSYNC_UNSUPPORTED = frozenset(
    {
        getattr(errno, name)
        for name in (
            "EINVAL",
            "EISDIR",
            "ENOTSUP",
            "ENOSYS",
            "EROFS",
            "EPERM",
            "EACCES",
        )
        if hasattr(errno, name)
    }
)


def _fsync_directory(path: Path) -> None:
    """Flush *path*'s own directory entries (its children) to stable storage.

    Crash durability: an ``fsync`` on a file alone does not order a newly
    linked or replaced DIRECTORY ENTRY before a host/power failure — the
    entry itself lives in the containing directory, so that directory must
    be fsynced too.  Filesystems that cannot fsync directories raise the
    standard unsupported-errno set, which is tolerated; every other failure
    is fatal.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError as exc:
        if exc.errno not in _DIR_FSYNC_UNSUPPORTED:
            raise
        return
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if exc.errno not in _DIR_FSYNC_UNSUPPORTED:
            raise
    finally:
        os.close(descriptor)


def _write_immutable(path: Path, value: Mapping[str, Any]) -> None:
    encoded = _canonical(value)
    # Track which ancestor directories are about to be created: a newly
    # created directory's OWN name is not durable until its parent is
    # fsynced, so every created ancestor gets a directory fsync below.
    missing_ancestors: list[Path] = []
    ancestor = path.parent
    while not ancestor.exists():
        missing_ancestors.append(ancestor)
        ancestor = ancestor.parent
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
    # Crash durability: the receipt's directory entry — and the entry of
    # every directory created to hold it — must be fsynced, or a host/power
    # crash can lose the receipt while the marker replacement survives.
    _fsync_directory(path.parent)
    for created in missing_ancestors:
        _fsync_directory(created.parent)


#: Exact-CAS invocation guards every prepared/committed evidence record must
#: bind: session, the pre-migration marker digest, the relaunch digest, the
#: chain-state / runtime / runtime-identity / provenance digests, the resolved
#: marker and chain-state paths, and the verified legacy runtime root.
_GUARD_KEYS = (
    "session",
    "marker_before_sha256",
    "relaunch_command_sha256",
    "chain_state_sha256",
    "runtime_sha256",
    "runtime_identity_sha256",
    "runtime_provenance_receipt_sha256",
    "marker_path",
    "chain_state_path",
    "runtime_root",
)


def _invocation_guards(
    *,
    session: str,
    marker_before_sha256: str,
    relaunch_command_sha256: str,
    chain_state_sha256: str,
    runtime_sha256: str,
    runtime_identity_sha256: str,
    runtime_provenance_receipt_sha256: str,
    marker_path: str,
    chain_state_path: str,
    runtime_root: str,
) -> dict[str, str]:
    """The exact-CAS guard digest set for the CURRENT invocation.

    ``marker_before_sha256`` is the invocation's expected pre-migration
    marker digest — NOT the digest of whatever marker happens to be on disk
    now (a step-3 crash leaves the STRONG after-image there).
    """
    return {
        "session": session,
        "marker_before_sha256": marker_before_sha256,
        "relaunch_command_sha256": relaunch_command_sha256,
        "chain_state_sha256": chain_state_sha256,
        "runtime_sha256": runtime_sha256,
        "runtime_identity_sha256": runtime_identity_sha256,
        "runtime_provenance_receipt_sha256": runtime_provenance_receipt_sha256,
        "marker_path": marker_path,
        "chain_state_path": chain_state_path,
        "runtime_root": runtime_root,
    }


def _record_guards_match(
    record: Mapping[str, Any], expected: Mapping[str, Any]
) -> bool:
    """True only when *record* (a prepared or committed evidence receipt)
    binds EVERY exact-CAS invocation guard in *expected* to the value the
    current run expects.  Fail closed: a record missing any bound guard, or
    disagreeing on any one of them, never matches."""
    for key, value in expected.items():
        recorded = record.get(key)
        if not isinstance(recorded, str) or not recorded:
            return False
        if key == "runtime_root":
            if str(Path(recorded).resolve(strict=False)) != value:
                return False
        elif recorded != value:
            return False
    return True


def _committed_receipt(
    prepared: Mapping[str, Any], *, receipt_ref: str, receipt_sha256: str
) -> dict[str, Any]:
    """The committed receipt for a prepared record.

    It repeats every exact-CAS guard digest the prepared record carried
    (marker before-image, relaunch, chain-state, runtime, runtime-identity,
    provenance, session, marker/chain-state paths, runtime root) so a later
    finalize can validate guards against the committed record ALONE — even
    after the prepared file is gone.
    """
    return {
        "schema": f"{MIGRATION_SCHEMA}.commit",
        "migration_id": prepared["migration_id"],
        "marker_before_sha256": prepared["marker_before_sha256"],
        "marker_after_sha256": prepared["marker_after_sha256"],
        "relaunch_command_sha256": prepared["relaunch_command_sha256"],
        "chain_state_sha256": prepared["chain_state_sha256"],
        "runtime_sha256": prepared["runtime_sha256"],
        "runtime_identity_sha256": prepared["runtime_identity_sha256"],
        "runtime_provenance_receipt_sha256": prepared[
            "runtime_provenance_receipt_sha256"
        ],
        "session": prepared["session"],
        "marker_path": prepared["marker_path"],
        "chain_state_path": prepared["chain_state_path"],
        "runtime_root": prepared["runtime_root"],
        "receipt_ref": receipt_ref,
        "receipt_sha256": receipt_sha256,
        "committed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


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
    launched_identity = binding.get("launched_identity")
    launched_identity = (
        launched_identity if isinstance(launched_identity, Mapping) else {}
    )
    if (
        metadata.get("chain_spec_path") != remote_spec
        or launched_identity.get("spec_path") != remote_spec
    ):
        raise CliError(
            "runtime_marker_migration_chain_mismatch",
            "legacy marker migration remote spec disagrees with canonical chain "
            "and launched execution bindings",
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


def _finalize_migration_receipt(
    marker_path: Path,
    marker: Mapping[str, Any],
    *,
    evidence_root: Path,
    marker_sha256: str,
    guards: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Idempotently finalize a migration whose committed receipt is missing.

    The migration writes the prepared receipt, then the marker replacement
    (``os.replace``), then the committed receipt.  If the process dies
    between the replacement and the committed receipt, a retry sees a
    strong-bound marker instead of the expected identity-less before-image.

    This recognizes the EXACT prepared after-image (the strong marker the
    migration would have written), validates EVERY exact-CAS invocation
    guard + evidence digest against the prepared record, emits the missing
    committed receipt, and returns the same success payload the original run
    would have produced; a marker matching a prior committed receipt is
    already committed and succeeds without any write.  Returns ``None`` when
    the marker matches no migration receipt under the current guards (the
    caller refuses with zero writes).
    """
    marker_path = marker_path.resolve(strict=False)
    resolved_marker = str(marker_path)
    try:
        prepared_paths = sorted(evidence_root.glob("*.prepared.json"))
        committed_paths = sorted(evidence_root.glob("*.committed.json"))
    except OSError:
        return None

    # Step-3 crash retry: the marker IS the exact prepared after-image.
    for path in prepared_paths:
        _, prepared = _read_object(path, label="migration prepared receipt")
        if (
            prepared.get("schema") == MIGRATION_SCHEMA
            and prepared.get("marker_after_sha256") == marker_sha256
            and _record_guards_match(prepared, guards)
        ):
            committed_path = evidence_root / f"{prepared['migration_id']}.committed.json"
            if committed_path.exists():
                _, existing = _read_object(
                    committed_path, label="migration committed receipt"
                )
                if (
                    existing.get("migration_id") != prepared["migration_id"]
                    or existing.get("marker_after_sha256")
                    != prepared["marker_after_sha256"]
                    or not _record_guards_match(existing, guards)
                ):
                    raise CliError(
                        "runtime_marker_migration_evidence_collision",
                        f"immutable migration evidence differs at {committed_path}",
                    )
            else:
                _write_immutable(
                    committed_path,
                    _committed_receipt(
                        prepared,
                        receipt_ref=path.relative_to(marker_path.parent).as_posix(),
                        receipt_sha256=_sha(path.read_bytes()),
                    ),
                )
            return {
                "marker_path": resolved_marker,
                "marker_before_sha256": prepared["marker_before_sha256"],
                "marker_after_sha256": prepared["marker_after_sha256"],
                "runtime_sha256": prepared["runtime_sha256"],
                "run_id": prepared["run_id"],
                "migration_id": prepared["migration_id"],
                "receipt_path": str(path),
                "commit_path": str(committed_path),
            }

    # Already committed: the marker matches a prior committed after-image.
    for path in committed_paths:
        _, committed = _read_object(path, label="migration committed receipt")
        if (
            committed.get("schema") == f"{MIGRATION_SCHEMA}.commit"
            and committed.get("marker_after_sha256") == marker_sha256
            and _record_guards_match(committed, guards)
        ):
            binding = marker.get("runtime_binding")
            binding = binding if isinstance(binding, Mapping) else {}
            legacy_migration = binding.get("legacy_migration")
            legacy_migration = (
                legacy_migration if isinstance(legacy_migration, Mapping) else {}
            )
            current_identity = binding.get("current_identity")
            current_identity = (
                current_identity if isinstance(current_identity, Mapping) else {}
            )
            marker_before = legacy_migration.get("marker_before_sha256")
            runtime_sha256 = current_identity.get("content_sha256")
            if not _FULL_SHA256.fullmatch(str(marker_before or "")) or not _FULL_SHA256.fullmatch(
                str(runtime_sha256 or "")
            ):
                raise CliError(
                    "runtime_marker_migration_invalid",
                    "committed marker lacks a valid migration digest",
                )
            if legacy_migration.get("migration_id") != committed.get("migration_id"):
                raise CliError(
                    "runtime_marker_migration_invalid",
                    "committed marker disagrees with its migration receipt",
                )
            receipt_ref = committed.get("receipt_ref")
            receipt_path = (
                marker_path.parent / receipt_ref
                if isinstance(receipt_ref, str) and receipt_ref
                else marker_path.parent / f"{committed['migration_id']}.prepared.json"
            )
            # Cross-check the linked prepared receipt when it still exists:
            # both evidence records must agree under the same exact guards.
            if receipt_path.exists():
                _, linked = _read_object(
                    receipt_path, label="migration prepared receipt"
                )
                if (
                    linked.get("migration_id") != committed.get("migration_id")
                    or linked.get("marker_after_sha256")
                    != committed.get("marker_after_sha256")
                    or not _record_guards_match(linked, guards)
                ):
                    raise CliError(
                        "runtime_marker_migration_evidence_collision",
                        f"prepared receipt disagrees with the committed receipt at {receipt_path}",
                    )
            return {
                "marker_path": resolved_marker,
                "marker_before_sha256": marker_before,
                "marker_after_sha256": committed["marker_after_sha256"],
                "runtime_sha256": runtime_sha256,
                "run_id": marker.get("run_id"),
                "migration_id": committed["migration_id"],
                "receipt_path": str(receipt_path),
                "commit_path": str(path),
            }
    return None


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
    guards = _invocation_guards(
        session=expected_session,
        marker_before_sha256=expected_marker_sha256,
        relaunch_command_sha256=expected_relaunch_command_sha256,
        chain_state_sha256=_sha(chain_raw),
        runtime_sha256=expected_chain_runtime_sha256,
        runtime_identity_sha256=_sha(identity_raw),
        runtime_provenance_receipt_sha256=_sha(receipt_raw),
        marker_path=str(marker_path),
        chain_state_path=str(chain_state_path),
        runtime_root=expected_root,
    )

    lock_path = marker_path.with_suffix(marker_path.suffix + ".runtime-cutover.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        marker_raw, marker = _read_object(marker_path, label="legacy marker")
        marker_before = _sha(marker_raw)
        if marker_runtime_identity(marker) is not None or marker.get("runtime_binding") is not None:
            # A strong-bound marker is either the exact after-image of THIS
            # migration (step-3 crash retry, or already committed) or a
            # foreign mutation.  Recognize the receipts; refuse everything
            # else with zero writes — the identity-present refusal must NOT
            # fire for the exact prepared after-image.
            finalized = _finalize_migration_receipt(
                marker_path,
                marker,
                evidence_root=marker_path.parent
                / "runtime-marker-migrations"
                / expected_session,
                marker_sha256=marker_before,
                guards=guards,
            )
            if finalized is not None:
                return finalized
            if marker_before == expected_marker_sha256:
                raise CliError(
                    "runtime_marker_migration_not_legacy",
                    "marker already has a runtime identity; use ordinary runtime cutover",
                )
            raise CliError(
                "runtime_marker_migration_not_legacy",
                "marker is strong-bound but matches no migration receipt; "
                "refusing foreign mutation",
            )
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
        committed_path = evidence_root / f"{migration_id}.committed.json"
        evidence_ref = prepared_path.relative_to(marker_path.parent).as_posix()

        # Crash retry inside the prepared-receipt → marker-replacement window:
        # a previous attempt may have committed the prepared receipt and then
        # died BEFORE ``os.replace`` (marker-tempfile or replace failure).
        # The prepared receipt is immutable; REUSE it — never recompute
        # time-dependent after-image bytes, which would collide with the
        # receipt at a later wall-clock time — after validating EVERY
        # invocation guard against it.
        reused_prepared: Mapping[str, Any] | None = None
        if prepared_path.exists():
            _, reused_prepared = _read_object(
                prepared_path, label="migration prepared receipt"
            )
            if not _record_guards_match(reused_prepared, guards):
                raise CliError(
                    "runtime_marker_migration_evidence_collision",
                    "existing prepared receipt disagrees with the current exact guards",
                )
            if committed_path.exists():
                raise CliError(
                    "runtime_marker_migration_not_legacy",
                    "marker was reverted after its migration committed; "
                    "refusing foreign mutation",
                )
            prepared_at = reused_prepared.get("prepared_at")
            if not isinstance(prepared_at, str) or not prepared_at:
                raise CliError(
                    "runtime_marker_migration_invalid",
                    "prepared receipt lacks a valid prepared_at timestamp",
                )
            changed_at = prepared_at
        else:
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
        if reused_prepared is not None:
            if marker_after != reused_prepared.get("marker_after_sha256"):
                raise CliError(
                    "runtime_marker_migration_evidence_collision",
                    "reconstructed after-image disagrees with the existing "
                    "prepared receipt",
                )
            prepared_record = reused_prepared
        else:
            prepared_record = {
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
            _write_immutable(prepared_path, prepared_record)
        descriptor, temporary = tempfile.mkstemp(dir=marker_path.parent, prefix=marker_path.name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, marker_path)
            # Crash durability: the marker replacement is not durable until
            # its containing directory is fsynced — otherwise the strong
            # after-image can vanish (or the old marker persist) while the
            # evidence receipts survive, inverting the retry contract.
            _fsync_directory(marker_path.parent)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        _write_immutable(
            committed_path,
            _committed_receipt(
                prepared_record,
                receipt_ref=evidence_ref,
                receipt_sha256=_sha(prepared_path.read_bytes()),
            ),
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
