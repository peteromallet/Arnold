"""Read-only admission for an already recovered, pre-chain runtime.

The cloud bootstrap normally rejects every existing authority file.  A failed
pre-chain recovery is the one deliberately supported exception: it leaves a
runtime and a marker behind, but no chain state or live runner.  This module is
called by the source-bound runtime probe and only verifies that exception.  It
does not write marker, manifest, journal, or liveness data.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    ManifestError,
    RuntimeManifest,
)
from arnold_pipelines.megaplan.cloud.liveness_lease import fence_path, lease_path
from arnold_pipelines.megaplan.incident.chain_control import (
    SCHEMA_VERSION,
    canonical_json,
    chain_id_for_spec,
    compute_event_hash,
    journal_for,
    payload_digest_for,
)


_OCCUPANCY_KEYS = (
    "owner",
    "runner",
    "tmux_session",
    "chain_pid",
    "worker_pid",
    "fixer_owner",
    "fixer_pid",
)
_RECOVERY_SCHEMA = "arnold.megaplan.failed-prechain-recovery.v1"
_SHA40 = set("0123456789abcdef")


def _fail(message: str, code: int = 78) -> None:
    print(f"chain_runtime_recovery_admission: {message}", file=sys.stderr)
    raise SystemExit(code)


def _read_regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError:
        _fail(f"{label} is unavailable")
    if not stat.S_ISREG(info.st_mode):
        _fail(f"{label} is not a regular file")
    try:
        return path.read_bytes()
    except OSError:
        _fail(f"{label} is unreadable")
    raise AssertionError("unreachable")


def _json(path: Path, label: str) -> tuple[bytes, Mapping[str, Any]]:
    raw = _read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail(f"{label} is not valid JSON")
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a JSON object")
    return raw, value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _full_sha(value: Any, label: str, length: int) -> str:
    if not isinstance(value, str):
        _fail(f"{label} is not a full hexadecimal SHA")
    text = value
    if len(text) != length or any(ch not in _SHA40 for ch in text):
        _fail(f"{label} is not a full hexadecimal SHA")
    return text


def _required(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        _fail(f"{label} is missing")
    return mapping[key]


def _required_text(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = _required(mapping, key, label)
    if not isinstance(value, str) or not value:
        _fail(f"{label} is missing")
    return value


def _required_mapping(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
) -> Mapping[str, Any]:
    value = _required(mapping, key, label)
    if not isinstance(value, Mapping):
        _fail(f"{label} is malformed")
    return value


def _required_list(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
    *,
    nonempty: bool = False,
) -> list[Any]:
    value = _required(mapping, key, label)
    if not isinstance(value, list) or (nonempty and not value):
        _fail(f"{label} is malformed")
    return value


def _required_int(mapping: Mapping[str, Any], key: str, label: str) -> int:
    value = _required(mapping, key, label)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{label} is malformed")
    return value


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        _fail(f"{label} mismatch")


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} is missing")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        _fail(f"{label} is malformed")
    if parsed.tzinfo is None:
        _fail(f"{label} has no timezone")
    return value


def _regular_lock_path(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def _pid_dead(value: Any, label: str) -> None:
    if value in (None, "", 0, "0"):
        return
    try:
        pid = int(value)
    except (TypeError, ValueError):
        _fail(f"{label} is malformed")
    if pid <= 0:
        _fail(f"{label} is malformed")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    except PermissionError:
        _fail(f"{label} may still be live")
    except OSError:
        return
    _fail(f"{label} is still live")


def _parse_expiry(value: Any) -> _dt.datetime:
    if not isinstance(value, str) or not value.strip():
        _fail("liveness lease expiry is missing")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        _fail("liveness lease expiry is malformed")
    if parsed.tzinfo is None:
        _fail("liveness lease expiry has no timezone")
    return parsed.astimezone(_dt.timezone.utc)


def _archive_identity(
    path: Path,
    archive: Mapping[str, Any],
    *,
    operation: str,
    old_sha: str,
) -> tuple[tuple[Any, ...], ...]:
    _require_equal(
        _required_text(archive, "schema", "recovery archive schema"),
        _RECOVERY_SCHEMA,
        "recovery archive schema",
    )
    _require_equal(
        _full_sha(
            _required(archive, "operation_id", "recovery archive operation"),
            "recovery archive operation",
            64,
        ),
        operation,
        "recovery archive operation",
    )
    _require_equal(
        _full_sha(
            _required(archive, "source_head", "recovery archive source head"),
            "recovery archive source head",
            40,
        ),
        old_sha,
        "recovery archive source head",
    )
    status = _required_list(
        archive,
        "status",
        "recovery archive source status",
        nonempty=True,
    )
    if any(not isinstance(item, str) or len(item) < 4 for item in status):
        _fail("recovery archive source status is malformed")
    fingerprint = _required_list(
        archive,
        "worktree_fingerprint",
        "recovery archive worktree fingerprint",
        nonempty=True,
    )
    fingerprint_rows: list[tuple[str, str]] = []
    for row in fingerprint:
        if not isinstance(row, Mapping):
            _fail("recovery archive worktree fingerprint is malformed")
        relative = _required_text(row, "path", "archive fingerprint path")
        code = _required_text(row, "status", "archive fingerprint status")
        kind = _required_text(row, "kind", "archive fingerprint kind")
        if kind == "file":
            _full_sha(
                _required(row, "sha256", "archive fingerprint file digest"),
                "archive fingerprint file digest",
                64,
            )
            if _required_int(row, "size", "archive fingerprint file size") < 0:
                _fail("archive fingerprint file size is malformed")
        elif kind == "symlink":
            _required_text(row, "target", "archive fingerprint symlink target")
        elif kind == "other":
            _required_int(row, "mode", "archive fingerprint mode")
        elif kind != "directory":
            _fail("archive fingerprint kind is malformed")
        fingerprint_rows.append((code, relative))
    status_rows = [(item[:2], item[3:].rstrip("/")) for item in status]
    if len(set(fingerprint_rows)) != len(fingerprint_rows) or sorted(
        fingerprint_rows
    ) != sorted(status_rows):
        _fail("recovery archive status/fingerprint identity mismatch")

    entries = _required_list(
        archive,
        "entries",
        "recovery archive entries",
        nonempty=True,
    )
    _timestamp(
        _required(archive, "created_at", "recovery archive creation time"),
        "recovery archive creation time",
    )
    root = path.parent.resolve(strict=False)
    identities: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            _fail("recovery archive entry is malformed")
        relative = _required_text(item, "path", "recovery archive entry path")
        if relative in seen:
            _fail("recovery archive entry path is duplicated")
        seen.add(relative)
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            _fail("recovery archive entry escapes custody")
        target = root / relative_path
        kind = item["kind"] if "kind" in item else "file"
        if kind == "symlink":
            expected_target = _required_text(
                item,
                "target",
                "recovery archive symlink target",
            )
            if not target.is_symlink() or os.readlink(target) != expected_target:
                _fail("recovery archive symlink entry is missing or changed")
            identities.append((relative, kind, expected_target))
            continue
        if kind != "file":
            _fail("recovery archive entry kind is malformed")
        raw = _read_regular(target, "recovery archive entry")
        digest = _full_sha(
            _required(item, "sha256", "recovery archive entry digest"),
            "recovery archive entry digest",
            64,
        )
        size = _required_int(item, "size", "recovery archive entry size")
        if size < 0 or len(raw) != size or _sha(raw) != digest:
            _fail("recovery archive entry is missing or changed")
        identities.append((relative, kind, digest, size))
    if not identities or identities[0][0] != "tracked.diff":
        _fail("recovery archive tracked diff is missing")
    return tuple(sorted(identities))


def _manifest_identity(
    manifest: Mapping[str, Any],
    *,
    slug: str,
    recovered_runtime: str,
    new_sha: str,
    old_sha: str,
    generation: int,
    engine_runtime: str,
    reason: str,
    canonical_origin: str,
) -> str:
    try:
        parsed = RuntimeManifest.from_dict(manifest)
    except (ManifestError, TypeError, ValueError) as exc:
        _fail(f"runtime manifest is schema-invalid: {type(exc).__name__}")
    if parsed.compatibility_only:
        _fail("runtime manifest is compatibility-only")
    _required_text(manifest, "runtime_id", "runtime manifest runtime identity")
    _required_text(manifest, "owner", "runtime manifest owner identity")
    _require_equal(parsed.schema, "1", "runtime manifest schema")
    _require_equal(parsed.epic_id, slug, "runtime manifest epic identity")
    _require_equal(parsed.state, "active", "runtime manifest state")
    _require_equal(parsed.generation, generation, "runtime manifest generation")

    base = _required_mapping(manifest, "base", "runtime manifest base")
    epic = _required_mapping(manifest, "epic", "runtime manifest epic")
    indirection = _required_mapping(
        manifest,
        "indirection",
        "runtime manifest indirection",
    )
    branch = _required_text(epic, "branch", "runtime manifest branch")
    for mapping, key, expected, label in (
        (base, "commit", new_sha, "runtime manifest base commit"),
        (base, "origin_url", canonical_origin, "runtime manifest base origin"),
        (epic, "worktree_path", recovered_runtime, "runtime manifest worktree"),
        (epic, "runtime_root", recovered_runtime, "runtime manifest runtime root"),
        (epic, "expected_head", new_sha, "runtime manifest expected head"),
        (epic, "origin_url", canonical_origin, "runtime manifest epic origin"),
        (indirection, "host_path", recovered_runtime, "runtime manifest host path"),
        (indirection, "verified_head", new_sha, "runtime manifest verified head"),
    ):
        _require_equal(_required_text(mapping, key, label), expected, label)
    _required_text(base, "ref", "runtime manifest base ref")
    for key in ("venv_path", "repair_bin", "deps_lockfile"):
        _required_text(epic, key, f"runtime manifest epic {key}")
    _required_mapping(
        epic,
        "dependency_generation",
        "runtime manifest dependency generation",
    )

    promotions = _required_list(
        manifest,
        "promotions",
        "runtime manifest promotions",
        nonempty=True,
    )
    promotion = promotions[-1]
    if not isinstance(promotion, Mapping):
        _fail("runtime manifest recovery promotion is malformed")
    expected_promotion = {
        "previous_generation": generation - 1,
        "previous_commit": old_sha,
        "previous_runtime_root": engine_runtime,
        "reason": reason,
    }
    for key, expected in expected_promotion.items():
        _require_equal(
            _required(promotion, key, f"runtime manifest promotion {key}"),
            expected,
            f"runtime manifest promotion {key}",
        )
    _required_text(
        promotion,
        "previous_venv_path",
        "runtime manifest previous venv",
    )
    _required_text(
        promotion,
        "previous_repair_bin",
        "runtime manifest previous repair binary",
    )
    promotion_at = _timestamp(
        _required(promotion, "at", "runtime manifest promotion time"),
        "runtime manifest promotion time",
    )
    timestamps = _required_mapping(
        manifest,
        "timestamps",
        "runtime manifest timestamps",
    )
    _require_equal(
        _required_text(timestamps, "updated", "runtime manifest updated time"),
        promotion_at,
        "runtime manifest promotion/update time",
    )
    return branch


def _event_id_for(event: Mapping[str, Any]) -> str:
    payload = _required_mapping(event, "payload", "journal event payload")
    digest = payload_digest_for(payload)
    return hashlib.sha256(
        canonical_json(
            [
                _required_text(event, "event_kind", "journal event kind"),
                _required_text(event, "operation_id", "journal operation"),
                str(
                    _required_int(
                        event, "physical_sequence", "journal physical sequence"
                    )
                ),
                digest,
            ]
        )
    ).hexdigest()


def _strict_recovery_event(
    events_path: Path,
    *,
    operation: str,
    expected_spec: str,
    session: str,
    old_sha: str,
    new_sha: str,
    reviewed_source: str,
    engine_runtime: str,
    generation: int,
    marker_sha: str,
    manifest_sha: str,
    manifest_before_sha: str,
    archive_sha: str,
    archive_path: Path,
    receipt_path: Path,
    expected_workspace: str,
    recovered_runtime: str,
    actor: str,
) -> dict[str, Any]:
    """Replay and bind the exact successful recovery transaction lineage."""
    try:
        replay = journal_for(events_path.parent.parent.parent).replay_strict()
    except Exception as exc:  # noqa: BLE001 - the probe must fail closed
        _fail(f"chain-control journal replay failed: {type(exc).__name__}")
    if not isinstance(replay, Mapping):
        _fail("strict journal replay is malformed")
    if _required(replay, "torn_tail", "strict journal tail state") is not False:
        _fail("strict journal has a torn tail")
    accepted = _required_list(replay, "accepted", "strict journal replay")
    events = [
        event
        for event in accepted
        if isinstance(event, Mapping) and event.get("operation_id") == operation
    ]
    expected_kinds = (
        "chain_control.intent",
        "chain_control.authority_validated",
        "chain_control.claimed",
        "chain_control.committed",
    )
    if tuple(event.get("event_kind") for event in events) != expected_kinds:
        _fail("strict journal has no unique complete recovery transaction")
    intent_event, authority_event, claimed_event, committed = events
    operations = _required_mapping(
        replay,
        "operations",
        "strict journal operation index",
    )
    if (
        _required(
            operations,
            operation,
            "strict journal recovery result",
        )
        != committed
    ):
        _fail("strict journal recovery result is not its committed event")
    expected_chain = chain_id_for_spec(Path(expected_spec))
    source_identity = {
        "old_sha": old_sha,
        "new_sha": new_sha,
        "reviewed_source": reviewed_source,
        "chain_workspace": expected_workspace,
        "engine_runtime": engine_runtime,
    }
    context = {"session": session, **source_identity}
    intent_payload = _required_mapping(
        intent_event,
        "payload",
        "recovery intent payload",
    )
    retry_keys = (
        "retry_after_operation_id",
        "retry_after_event_hash",
        "retry_after_evidence",
    )
    present_retry = [key for key in retry_keys if key in intent_payload]
    if present_retry and len(present_retry) != len(retry_keys):
        _fail("recovery retry lineage is incomplete")
    retry_context: dict[str, str] = {}
    linked_receipts = [str(archive_path)]
    operation_preimage = (
        f"failed_prechain_recovery\0{session}\0{manifest_before_sha}\0"
        f"{old_sha}\0{new_sha}"
    )
    if present_retry:
        predecessor = _full_sha(
            _required_text(
                intent_payload, retry_keys[0], "retry predecessor operation"
            ),
            "retry predecessor operation",
            64,
        )
        predecessor_hash = _full_sha(
            _required_text(
                intent_payload, retry_keys[1], "retry predecessor event hash"
            ),
            "retry predecessor event hash",
            64,
        )
        predecessor_evidence = _required_text(
            intent_payload,
            retry_keys[2],
            "retry predecessor evidence",
        )
        retry_context = {
            retry_keys[0]: predecessor,
            retry_keys[1]: predecessor_hash,
            retry_keys[2]: predecessor_evidence,
        }
        linked_receipts.append(predecessor_evidence)
        operation_preimage += f"\0retry-after\0{predecessor}"
    if hashlib.sha256(operation_preimage.encode()).hexdigest() != operation:
        _fail("recovery operation identity is not deterministic")

    expected_payloads: tuple[Mapping[str, Any], ...] = (
        {
            "intent_kind": "failed_prechain_recovery",
            "expected_revision": None,
            **context,
            **retry_context,
        },
        {"intent_kind": "failed_prechain_recovery", **context, **retry_context},
        {
            "intent_kind": "failed_prechain_recovery",
            "claim": "single-use",
            **context,
            **retry_context,
        },
    )
    for event, expected_payload in zip(events[:3], expected_payloads):
        if event["payload"] != expected_payload:
            _fail("recovery journal intent identity is contradictory")

    event_ids = []
    event_hashes = []
    ledger_id = _required_text(events[0], "ledger_id", "journal ledger identity")
    for index, event in enumerate(events):
        event_id = _full_sha(
            _required(event, "event_id", "journal event identity"),
            "journal event identity",
            64,
        )
        event_hash = _full_sha(
            _required(event, "event_hash", "journal event hash"),
            "journal event hash",
            64,
        )
        if event_id != _event_id_for(event):
            _fail("journal event identity is not deterministic")
        event_ids.append(event_id)
        event_hashes.append(event_hash)
        if _required(event, "schema_version", "journal schema") != SCHEMA_VERSION:
            _fail("recovery journal schema mismatch")
        if _required_text(
            event,
            "payload_digest",
            "journal payload digest",
        ) != payload_digest_for(event["payload"]):
            _fail("journal payload digest mismatch")
        for digest_key in ("previous_physical_digest", "previous_evidence_digest"):
            _full_sha(
                _required(event, digest_key, f"journal {digest_key}"),
                f"journal {digest_key}",
                64,
            )
        recomputed_hash = compute_event_hash(
            authority_mode=_required_text(
                event, "authority_mode", "journal authority mode"
            ),
            ledger_id=_required_text(event, "ledger_id", "journal ledger identity"),
            chain_id=_required_text(event, "chain_id", "journal chain identity"),
            physical_sequence=_required_int(
                event, "physical_sequence", "journal physical sequence"
            ),
            evidence_sequence=_required_int(
                event, "evidence_sequence", "journal evidence sequence"
            ),
            semantic_sequence=_required_int(
                event, "semantic_sequence", "journal semantic sequence"
            ),
            event_id=event_id,
            event_kind=_required_text(event, "event_kind", "journal event kind"),
            operation_id=_required_text(event, "operation_id", "journal operation"),
            causation_id=_required_text(event, "causation_id", "journal causation"),
            correlation_id=_required_text(
                event, "correlation_id", "journal correlation"
            ),
            recovery_id=_required_text(
                event, "recovery_id", "journal recovery identity"
            ),
            previous_physical_digest=event["previous_physical_digest"],
            previous_evidence_digest=event["previous_evidence_digest"],
            payload=event["payload"],
        )
        if recomputed_hash != event_hash:
            _fail("journal event hash mismatch")
        _timestamp(
            _required(event, "created_at", "journal event creation time"),
            "journal event creation time",
        )
        expected_cause = operation if index == 0 else event_ids[index - 1]
        common = {
            "operation_id": operation,
            "causation_id": expected_cause,
            "correlation_id": operation,
            "recovery_id": "none",
            "chain_id": expected_chain,
            "parent_chain_id": None,
            "child_id": None,
            "run_id": None,
            "actor": {"id": actor, "class": "operator"},
            "authority_mode": "file",
            "ledger_id": ledger_id,
            "intent": "failed_prechain_recovery",
            "semantic_effect": "no_change",
            "expected_cursor": None,
            "expected_revision": None,
            "actual_cursor": None,
            "actual_revision": None,
            "pre_state_digest": None,
            "post_state_digest": None,
            "config_identity": None,
            "runtime_identity": None,
            "failure_class": None,
            "claim_class": "required",
        }
        for key, value in common.items():
            if _required(event, key, f"journal {key}") != value:
                _fail(f"recovery journal {key} mismatch")
        expected_outcome = "committed" if index == 3 else None
        if _required(event, "outcome", "journal outcome") != expected_outcome:
            _fail("recovery journal outcome mismatch")
        expected_source = source_identity if index in (0, 3) else None
        expected_spec_value = expected_spec if index in (0, 3) else None
        if (
            _required(event, "source_identity", "journal source identity")
            != expected_source
        ):
            _fail("recovery journal source identity mismatch")
        if (
            _required(event, "spec_identity", "journal spec identity")
            != expected_spec_value
        ):
            _fail("recovery journal spec identity mismatch")
        expected_links = linked_receipts if index == 3 else []
        if (
            _required(event, "linked_receipts", "journal linked receipts")
            != expected_links
        ):
            _fail("recovery journal receipt linkage mismatch")
        if (
            index
            and _required(
                event,
                "previous_evidence_digest",
                "journal evidence predecessor",
            )
            != event_hashes[index - 1]
        ):
            _fail("recovery journal evidence lineage mismatch")
        if index:
            prior = events[index - 1]
            if (
                event["physical_sequence"] != prior["physical_sequence"] + 1
                or event["evidence_sequence"] != prior["evidence_sequence"] + 1
                or event["semantic_sequence"] != prior["semantic_sequence"]
            ):
                _fail("recovery journal sequence lineage mismatch")
    if len(set(event_ids)) != 4 or len(set(event_hashes)) != 4:
        _fail("recovery journal event identities are not unique")

    if _required(committed, "outcome", "committed recovery outcome") != "committed":
        _fail("recovery journal operation is not committed")
    _required_mapping(
        _required_mapping(committed, "payload", "committed recovery payload"),
        "effect",
        "committed recovery effect",
    )
    expected_effect = {
        "source_old_sha": old_sha,
        "source_new_sha": new_sha,
        "staged_runtime": recovered_runtime,
        "manifest_generation": generation,
        "archive_manifest": {
            "path": str(archive_path),
            "sha256": archive_sha,
        },
        "receipt": str(receipt_path),
        "marker_sha256": marker_sha,
        "manifest_sha256": manifest_sha,
        "chain_state": "absent",
        "linked_receipts": [str(archive_path), str(receipt_path)],
    }
    if committed["payload"] != {
        "intent_kind": "failed_prechain_recovery",
        "effect": expected_effect,
    }:
        _fail("committed recovery effect is contradictory")
    return dict(committed)


def _git_identity(
    runtime: Path,
    *,
    expected_head: str,
    expected_branch: str,
    canonical_origin: str | None,
) -> tuple[str, ...]:
    def git(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(runtime), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            _fail("recovered runtime Git command is unavailable")
        if result.returncode != 0:
            _fail("recovered runtime is not a usable Git checkout")
        return result.stdout.strip()

    if not runtime.is_dir() or runtime.is_symlink() or not (runtime / ".git").exists():
        _fail("recovered runtime is not a Git checkout")
    head = git("rev-parse", "--verify", "HEAD")
    tree = git("rev-parse", "--verify", "HEAD^{tree}")
    if head != expected_head:
        _fail("recovered runtime HEAD/tree does not match manifest")
    _full_sha(tree, "recovered runtime tree", 40)
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        _fail("recovered runtime checkout is dirty")
    if not expected_branch:
        _fail("recovered runtime manifest branch is missing")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != expected_branch:
        _fail("recovered runtime is not attached to its declared branch")
    origin = git("remote", "get-url", "origin")
    if not canonical_origin:
        _fail("recovered runtime canonical origin is missing")
    if origin != canonical_origin:
        _fail("recovered runtime origin does not exactly match canonical origin")
    return head, tree, origin, branch


def validate_committed_recovery_evidence(*, marker_path: Path,
        manifest_path: Path, workspace_path: Path, spec_path: Path,
        operation_id: str, expected_session: str, expected_old_sha: str,
        expected_new_sha: str, expected_marker_sha: str,
        expected_manifest_sha: str, expected_engine_after: str,
        expected_generation: int,
        expected_engine_before: str | None = None,
        expected_spec_sha: str | None = None) -> Mapping[str, Any]:
    """Validate one committed recovery without admitting a runtime.

    This shared evidence validator is used by the collapsed-root bridge. It
    owns the immutable operation/receipt/journal/custody joins; callers own
    current liveness and Git-cleanliness checks.
    """
    marker_raw, marker = _json(marker_path, "session marker")
    manifest_raw, manifest = _json(manifest_path, "runtime manifest")
    operation_id = _full_sha(operation_id, "recovery operation", 64)
    expected_old_sha = _full_sha(expected_old_sha, "recovery old head", 40)
    expected_new_sha = _full_sha(expected_new_sha, "recovery reviewed head", 40)
    marker_sha = _full_sha(expected_marker_sha, "marker digest", 64)
    manifest_sha = _full_sha(expected_manifest_sha, "manifest digest", 64)
    if expected_spec_sha is not None:
        spec_sha = _full_sha(expected_spec_sha, "spec digest", 64)
        spec_raw = _read_regular(spec_path, "chain spec")
        if _sha(spec_raw) != spec_sha:
            _fail("recovery evidence chain spec digest mismatch")
    if _sha(marker_raw) != marker_sha or _sha(manifest_raw) != manifest_sha:
        _fail("recovery evidence current marker/manifest digest mismatch")
    recovery = marker.get("failed_prechain_recovery")
    if not isinstance(recovery, Mapping) or recovery.get("schema") not in (None, _RECOVERY_SCHEMA):
        _fail("recovery evidence record is missing or schema-invalid")
    if (marker.get("session") != expected_session
            or marker.get("workspace") != str(workspace_path)
            or marker.get("remote_spec") != str(spec_path)
            or marker.get("should_run") is not True):
        _fail("recovery evidence session/workspace identity mismatch")
    if recovery.get("operation_id") != operation_id:
        _fail("recovery evidence operation identity mismatch")
    engine_before = str(expected_engine_before or recovery.get("engine_runtime_before") or "")
    if not engine_before or engine_before == expected_engine_after:
        _fail("recovery evidence does not prove a distinct pre-collapse engine root")
    if not Path(engine_before).is_absolute() or not Path(expected_engine_after).is_absolute():
        _fail("recovery evidence engine roots are not absolute")
    if (recovery.get("old_sha") != expected_old_sha
            or recovery.get("new_sha") != expected_new_sha
            or recovery.get("chain_workspace") != str(workspace_path)
            or recovery.get("engine_runtime_before") != engine_before
            or recovery.get("engine_runtime_after") != expected_engine_after):
        _fail("recovery evidence source/root identity mismatch")
    if recovery.get("manifest_generation") != expected_generation:
        _fail("recovery evidence generation mismatch")
    archive_binding = recovery.get("archive_manifest")
    if not isinstance(archive_binding, Mapping):
        _fail("recovery evidence custody binding is missing")
    archive_path = Path(str(archive_binding.get("path") or ""))
    if (not archive_path.is_absolute() or archive_path.name != "manifest.json"
            or archive_path.parent.name != operation_id):
        _fail("recovery evidence custody path is not operation-scoped")
    archive_raw = _read_regular(archive_path, "recovery archive manifest")
    archive_sha = _full_sha(archive_binding.get("sha256"), "archive manifest digest", 64)
    if _sha(archive_raw) != archive_sha:
        _fail("recovery archive digest mismatch")
    try:
        archive = json.loads(archive_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"recovery custody archive is invalid: {type(exc).__name__}")
    if not isinstance(archive, Mapping):
        _fail("recovery custody archive is not an object")
    _archive_identity(archive_path, archive, operation=operation_id, old_sha=expected_old_sha)
    receipt_path = archive_path.parent / "recovery-receipt.json"
    receipt_raw, receipt = _json(receipt_path, "recovery receipt")
    receipt_marker = receipt.get("marker")
    receipt_manifest = receipt.get("manifest")
    receipt_source = receipt.get("source")
    receipt_engine = receipt.get("engine_runtime")
    if (receipt.get("schema") != _RECOVERY_SCHEMA
            or receipt.get("operation_id") != operation_id
            or receipt.get("session") != expected_session
            or receipt.get("chain_id") != chain_id_for_spec(spec_path)
            or receipt.get("outcome") != "recovered"
            or not all(isinstance(value, Mapping) for value in
                       (receipt_marker, receipt_manifest, receipt_source, receipt_engine))):
        _fail("recovery receipt identity joins are incomplete")
    launch_outcome = marker.get("launch_outcome")
    if not isinstance(launch_outcome, Mapping) or receipt.get("launch_outcome") != launch_outcome:
        _fail("recovery receipt launch outcome is not joined to the marker")
    receipt_marker_before = _full_sha(receipt_marker.get("before_sha256"), "recovery marker before digest", 64)
    receipt_manifest_before = _full_sha(receipt_manifest.get("before_sha256"), "recovery manifest before digest", 64)
    if receipt_marker_before == marker_sha or receipt_manifest_before == manifest_sha:
        _fail("recovery receipt before/after identities did not change")
    if (receipt_marker.get("path") != str(marker_path)
            or receipt_marker.get("after_sha256") != marker_sha
            or receipt_manifest.get("path") != str(manifest_path)
            or receipt_manifest.get("before_sha256") != receipt_manifest_before
            or receipt_manifest.get("after_sha256") != manifest_sha
            or receipt_manifest.get("generation") != expected_generation
            or receipt_source.get("path") != recovery.get("reviewed_source")
            or receipt_source.get("old_sha") != expected_old_sha
            or receipt_source.get("new_sha") != expected_new_sha
            or receipt_engine.get("old_path") != engine_before
            or receipt_engine.get("new_path") != expected_engine_after
            or receipt.get("staged_runtime") != str(workspace_path)
            or receipt.get("workspace") != str(workspace_path)):
        _fail("recovery receipt identity joins are contradictory")
    preserved = Path(str(receipt.get("preserved_failed_workspace") or ""))
    if not preserved.is_dir() or preserved.is_symlink():
        _fail("recovery receipt failed-workspace custody is unavailable")
    receipt_archive = receipt.get("archive_manifest")
    if not isinstance(receipt_archive, Mapping) or (
            receipt_archive.get("path") != str(archive_path)
            or receipt_archive.get("sha256") != archive_sha):
        _fail("recovery receipt custody binding is contradictory")
    source_path = Path(str(receipt_source.get("path") or ""))
    if not source_path.is_absolute() or not source_path.is_dir() or source_path.is_symlink():
        _fail("recovery receipt source provenance is unavailable")
    try:
        source_check = subprocess.run(
            ["git", "-C", str(source_path), "cat-file", "-e", f"{expected_new_sha}^{{commit}}"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        _fail("recovery source provenance Git is unavailable")
    if source_check.returncode != 0:
        _fail("recovery source provenance does not contain reviewed head")
    events = workspace_path / ".megaplan" / "incident-ledger" / "events.jsonl"
    _read_regular(events, "chain-control journal")
    _manifest_identity(
        manifest,
        slug=_required_text(manifest, "epic_id", "runtime manifest epic identity"),
        recovered_runtime=str(workspace_path),
        new_sha=expected_new_sha,
        old_sha=expected_old_sha,
        generation=expected_generation,
        engine_runtime=engine_before,
        reason=_required_text(recovery, "reason", "recovery reason"),
        canonical_origin=_required_text(
            _required_mapping(manifest, "base", "runtime manifest base"),
            "origin_url", "runtime manifest base origin",
        ),
    )
    event = _strict_recovery_event(
        events, operation=operation_id, expected_spec=str(spec_path),
        session=expected_session, old_sha=expected_old_sha,
        new_sha=expected_new_sha,
        reviewed_source=str(receipt_source.get("path")),
        engine_runtime=engine_before, generation=expected_generation,
        marker_sha=marker_sha, manifest_sha=manifest_sha,
        manifest_before_sha=receipt_manifest_before,
        archive_sha=archive_sha, archive_path=archive_path,
        receipt_path=receipt_path, expected_workspace=str(workspace_path),
        recovered_runtime=str(workspace_path),
        actor=_required_text(recovery, "actor", "recovery actor"),
    )
    return {"marker": marker, "manifest": manifest, "receipt": receipt,
            "archive": archive, "event": event, "receipt_raw": receipt_raw}


def _admit(
    *,
    manifest_path: Path,
    marker_path: Path,
    state_path: Path,
    runtime_src: str,
    session: str,
    slug: str,
    expected_spec: str | None,
    expected_workspace: str | None,
    canonical_origin: str | None = None,
) -> None:
    # First distinguish an ordinary existing runtime (exit 77 means the shell
    # caller should retain the historical generic authority refusal).
    if not marker_path.exists():
        raise SystemExit(77)
    marker_raw, marker = _json(marker_path, "session marker")
    recovery = marker.get("failed_prechain_recovery")
    if recovery is None:
        raise SystemExit(77)
    if not isinstance(recovery, Mapping):
        _fail("failed-prechain recovery record is malformed")
    if not all(
        isinstance(value, str) and value
        for value in (
            session,
            slug,
            runtime_src,
            expected_spec,
            expected_workspace,
            canonical_origin,
        )
    ):
        _fail("recovery admission requires every external identity")
    assert expected_spec is not None
    assert expected_workspace is not None
    assert canonical_origin is not None
    for value, label in (
        (str(manifest_path), "runtime manifest path"),
        (str(marker_path), "session marker path"),
        (str(state_path), "chain state path"),
        (runtime_src, "engine runtime path"),
        (expected_spec, "chain spec path"),
        (expected_workspace, "chain workspace path"),
    ):
        if not Path(value).is_absolute():
            _fail(f"{label} is not absolute")

    # These are sidecar locks.  In particular, never open the absent chain
    # state itself with O_CREAT: absence is part of the admission contract.
    workspace = expected_workspace
    workspace_path = Path(workspace)
    lease = lease_path(session, marker_dir=marker_path.parent)
    fence = fence_path(session, marker_dir=marker_path.parent)
    lease_lock = marker_path.parent / f"{session}.liveness-publisher.lock"
    fence_lock = marker_path.parent / f".{session}.liveness-fence.lock"
    ledger_lock = (
        workspace_path / ".megaplan" / "incident-ledger" / ".recovery-admission.lock"
    )
    lock_paths = [
        _regular_lock_path(manifest_path, ".lock"),
        _regular_lock_path(marker_path, ".runtime-cutover.lock"),
        _regular_lock_path(state_path, ".runtime-recovery.lock"),
        lease_lock,
        fence_lock,
        ledger_lock,
    ]
    with ExitStack() as stack:
        handles = []
        for lock_path in sorted({p.resolve(strict=False) for p in lock_paths}, key=str):
            try:
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                handle = stack.enter_context(lock_path.open("a+", encoding="utf-8"))
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handles.append(handle)
            except OSError:
                _fail("recovery admission lock is unavailable")

        # Re-read under the final lock boundary.  The initial read is only a
        # routing hint and is never used as authority.
        marker_raw, marker = _json(marker_path, "session marker")
        manifest_raw, manifest = _json(manifest_path, "runtime manifest")
        if state_path.exists():
            _fail("chain state exists")
        recovery = _required_mapping(
            marker,
            "failed_prechain_recovery",
            "failed-prechain recovery record",
        )
        _require_equal(
            _required_text(marker, "session", "session marker identity"),
            session,
            "session marker identity",
        )
        _require_equal(
            _required_text(marker, "remote_spec", "session marker spec identity"),
            expected_spec,
            "session marker spec identity",
        )
        _require_equal(
            _required_text(marker, "workspace", "session marker workspace identity"),
            expected_workspace,
            "session marker workspace identity",
        )
        declared_manifests = [
            marker[key]
            for key in ("bootstrap_manifest_path", "manifest_path")
            if key in marker and marker[key] is not None
        ]
        if not declared_manifests:
            _fail("session marker manifest identity is missing")
        for key in ("bootstrap_manifest_path", "manifest_path"):
            if (
                key in marker
                and marker[key] is not None
                and marker[key] != str(manifest_path)
            ):
                _fail("session marker manifest identity mismatch")
        if marker.get("should_run") is not True:
            _fail("recovered marker is not runnable")
        if marker.get("operator_pause") not in (None, ""):
            _fail("operator pause is active")
        for key in _OCCUPANCY_KEYS:
            if marker.get(key) not in (None, "", 0, "0"):
                _fail(f"marker still has live occupancy: {key}")
        if marker.get("provider_receipt") not in (None, ""):
            _fail("provider has already dispatched")
        for key in ("pid", "supervisor_pid"):
            _pid_dead(marker.get(key), f"marker {key}")
        outcome = marker.get("launch_outcome")
        if not isinstance(outcome, Mapping):
            _fail("historical launch was not a failed pre-chain attempt")
        if _required_text(
            outcome, "status", "historical launch status"
        ) != "failed" or _required_text(
            outcome, "code", "historical launch code"
        ) not in {"failed", "launch_not_advanced"}:
            _fail("historical launch was not a failed pre-chain attempt")
        history = _required_list(
            marker,
            "launch_outcome_history",
            "historical launch outcome history",
            nonempty=True,
        )
        if history[-1] != outcome:
            _fail("historical launch outcome history mismatch")

        _require_equal(
            _required_text(recovery, "schema", "recovery schema"),
            _RECOVERY_SCHEMA,
            "recovery schema",
        )
        operation = _full_sha(
            _required(recovery, "operation_id", "recovery operation"),
            "recovery operation",
            64,
        )
        old_sha = _full_sha(
            _required(recovery, "old_sha", "recovery old head"),
            "recovery old head",
            40,
        )
        new_sha = _full_sha(
            _required(recovery, "new_sha", "recovery head"),
            "recovery head",
            40,
        )
        reviewed_source = _required_text(
            recovery,
            "reviewed_source",
            "recovery reviewed source",
        )
        engine_runtime = _required_text(
            recovery,
            "engine_runtime_before",
            "recovery engine runtime before",
        )
        if (
            not Path(reviewed_source).is_absolute()
            or not Path(engine_runtime).is_absolute()
        ):
            _fail("recovery source/engine identity is not absolute")
        reason = _required_text(recovery, "reason", "recovery reason")
        actor = _required_text(recovery, "actor", "recovery actor")
        for key, expected, label in (
            ("chain_workspace", expected_workspace, "recovered workspace identity"),
            ("engine_runtime_before", runtime_src, "recovery engine identity"),
            (
                "engine_runtime_after",
                expected_workspace,
                "recovered runtime identity",
            ),
        ):
            _require_equal(_required_text(recovery, key, label), expected, label)
        generation = _required_int(
            recovery,
            "manifest_generation",
            "recovery manifest generation",
        )
        if generation <= 0:
            _fail("recovery manifest generation is malformed")

        expected_branch = _manifest_identity(
            manifest,
            slug=slug,
            recovered_runtime=expected_workspace,
            new_sha=new_sha,
            old_sha=old_sha,
            generation=generation,
            engine_runtime=engine_runtime,
            reason=reason,
            canonical_origin=canonical_origin,
        )
        recovery_manifest = _required_mapping(
            recovery,
            "archive_manifest",
            "recovery archive manifest",
        )
        archive_text = _required_text(
            recovery_manifest,
            "path",
            "recovery archive manifest path",
        )
        archive_path = Path(archive_text)
        if (
            not archive_path.is_absolute()
            or archive_path.name != "manifest.json"
            or archive_path.parent.name != operation
        ):
            _fail("recovery archive manifest path is not operation-scoped")
        archive_raw = _read_regular(archive_path, "recovery archive manifest")
        archive_sha = _full_sha(
            _required(recovery_manifest, "sha256", "archive manifest digest"),
            "archive manifest digest",
            64,
        )
        if _sha(archive_raw) != archive_sha:
            _fail("recovery archive manifest digest mismatch")
        _, archive = _json(archive_path, "recovery archive manifest")
        archive_identity = _archive_identity(
            archive_path,
            archive,
            operation=operation,
            old_sha=old_sha,
        )

        receipt_path = archive_path.parent / "recovery-receipt.json"
        receipt_raw, receipt = _json(receipt_path, "recovery receipt")
        _require_equal(
            _required_text(receipt, "schema", "recovery receipt schema"),
            _RECOVERY_SCHEMA,
            "recovery receipt schema",
        )
        for key, expected, label in (
            ("operation_id", operation, "recovery receipt operation"),
            ("session", session, "recovery receipt session"),
            (
                "chain_id",
                chain_id_for_spec(Path(expected_spec)),
                "recovery receipt chain",
            ),
            (
                "staged_runtime",
                expected_workspace,
                "recovery receipt staged runtime",
            ),
            (
                "preserved_failed_workspace",
                str(archive_path.parent / "failed-workspace"),
                "recovery receipt failed workspace",
            ),
            ("workspace", expected_workspace, "recovery receipt workspace"),
            ("outcome", "recovered", "recovery receipt outcome"),
        ):
            _require_equal(_required_text(receipt, key, label), expected, label)
        if not Path(receipt["preserved_failed_workspace"]).is_dir():
            _fail("recovery receipt failed workspace is unavailable")
        _timestamp(
            _required(receipt, "created_at", "recovery receipt creation time"),
            "recovery receipt creation time",
        )
        receipt_manifest = _required_mapping(
            receipt,
            "manifest",
            "recovery receipt manifest",
        )
        receipt_marker = _required_mapping(
            receipt,
            "marker",
            "recovery receipt marker",
        )
        manifest_before_sha = _full_sha(
            _required(
                receipt_manifest, "before_sha256", "recovery manifest before digest"
            ),
            "recovery manifest before digest",
            64,
        )
        manifest_after_sha = _full_sha(
            _required(receipt_manifest, "after_sha256", "recovery manifest digest"),
            "recovery manifest digest",
            64,
        )
        if (
            _required_text(receipt_manifest, "path", "recovery receipt manifest path")
            != str(manifest_path)
            or manifest_after_sha != _sha(manifest_raw)
            or _required_int(
                receipt_manifest, "generation", "recovery receipt manifest generation"
            )
            != generation
        ):
            _fail("recovery receipt manifest binding mismatch")
        marker_before_sha = _full_sha(
            _required(receipt_marker, "before_sha256", "recovery marker before digest"),
            "recovery marker before digest",
            64,
        )
        recovered_marker_sha = _full_sha(
            _required(receipt_marker, "after_sha256", "recovery marker digest"),
            "recovery marker digest",
            64,
        )
        if (
            manifest_before_sha == manifest_after_sha
            or marker_before_sha == recovered_marker_sha
        ):
            _fail("recovery receipt before/after identities did not change")
        _require_equal(
            _required_text(receipt_marker, "path", "recovery receipt marker path"),
            str(marker_path),
            "recovery receipt marker binding",
        )
        receipt_source = _required_mapping(
            receipt,
            "source",
            "recovery receipt source",
        )
        for key, expected, label in (
            ("path", reviewed_source, "recovery receipt source path"),
            ("old_sha", old_sha, "recovery receipt source old head"),
            ("new_sha", new_sha, "recovery receipt source new head"),
        ):
            _require_equal(_required_text(receipt_source, key, label), expected, label)
        receipt_engine = _required_mapping(
            receipt,
            "engine_runtime",
            "recovery receipt engine runtime",
        )
        _require_equal(
            {
                "old_path": _required_text(
                    receipt_engine, "old_path", "recovery receipt old engine"
                ),
                "new_path": _required_text(
                    receipt_engine, "new_path", "recovery receipt new engine"
                ),
            },
            {"old_path": runtime_src, "new_path": expected_workspace},
            "recovery receipt engine runtime",
        )
        receipt_archive = _required_mapping(
            receipt,
            "archive_manifest",
            "recovery receipt archive manifest",
        )
        _require_equal(
            {
                "path": _required_text(
                    receipt_archive, "path", "recovery receipt archive path"
                ),
                "sha256": _full_sha(
                    _required(
                        receipt_archive, "sha256", "recovery receipt archive digest"
                    ),
                    "recovery receipt archive digest",
                    64,
                ),
            },
            {"path": str(archive_path), "sha256": archive_sha},
            "recovery receipt archive binding",
        )
        _require_equal(
            _required_mapping(
                receipt, "launch_outcome", "recovery receipt launch outcome"
            ),
            outcome,
            "recovery receipt launch outcome",
        )

        events = workspace_path / ".megaplan" / "incident-ledger" / "events.jsonl"
        events_raw = _read_regular(events, "chain-control journal")
        event = _strict_recovery_event(
            events,
            operation=operation,
            expected_spec=expected_spec,
            session=session,
            old_sha=old_sha,
            new_sha=new_sha,
            reviewed_source=reviewed_source,
            engine_runtime=engine_runtime,
            generation=generation,
            marker_sha=recovered_marker_sha,
            manifest_sha=_sha(manifest_raw),
            manifest_before_sha=manifest_before_sha,
            archive_sha=archive_sha,
            archive_path=archive_path,
            receipt_path=receipt_path,
            expected_workspace=workspace,
            recovered_runtime=expected_workspace,
            actor=actor,
        )
        # The current marker must still be exactly the marker committed by
        # recovery.  A later launch attempt cannot be silently adopted.
        if recovered_marker_sha != _sha(marker_raw):
            _fail("recovery receipt marker digest does not match current marker")

        runtime_identity = _git_identity(
            workspace_path,
            expected_head=new_sha,
            expected_branch=expected_branch,
            canonical_origin=canonical_origin,
        )

        lease_raw, lease_payload = _json(lease, "liveness lease")
        if (
            lease_payload.get("session") != session
            or lease_payload.get("status") != "stopped"
        ):
            _fail("liveness lease is not stopped for this session")
        if expected_workspace and lease_payload.get("workspace") not in (
            None,
            expected_workspace,
        ):
            _fail("liveness lease workspace mismatch")
        if expected_spec and lease_payload.get("remote_spec") not in (
            None,
            expected_spec,
        ):
            _fail("liveness lease spec mismatch")
        if _parse_expiry(lease_payload.get("expires_at")) >= _dt.datetime.now(
            _dt.timezone.utc
        ):
            _fail("liveness lease has not expired")
        if lease_payload.get("marker_binding") not in (
            None,
            f"sha256:{recovered_marker_sha}",
            recovered_marker_sha,
        ):
            _fail("liveness lease marker binding mismatch")
        for key in (
            "pid",
            "publisher_pid",
            "target_pid",
            "owner_pid",
            "runner_pid",
            "worker_pid",
        ):
            _pid_dead(lease_payload.get(key), f"liveness lease {key}")

        fence_raw, fence_payload = _json(fence, "liveness fence")
        if fence_payload.get("session") != session:
            _fail("liveness fence session mismatch")
        if fence_payload.get("owner") not in (None, "", 0, "0") or fence_payload.get(
            "status"
        ) not in (None, "stopped", "released", "expired"):
            _fail("liveness fence still has an owner")
        for key in (
            "pid",
            "publisher_pid",
            "target_pid",
            "owner_pid",
            "runner_pid",
            "worker_pid",
        ):
            _pid_dead(fence_payload.get(key), f"liveness fence {key}")
        try:
            tmux = subprocess.run(
                ["tmux", "has-session", "-t", session],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            _fail("tmux liveness cannot be determined")
        if tmux.returncode == 0:
            _fail("tmux session is still live")
        if tmux.returncode != 1:
            _fail("tmux liveness cannot be determined")

        # A final byte check catches a concurrent writer that ignored the
        # advisory locks.  No admission path writes any of these authorities.
        if _read_regular(marker_path, "session marker") != marker_raw:
            _fail("session marker changed during admission")
        if _read_regular(lease, "liveness lease") != lease_raw:
            _fail("liveness lease changed during admission")
        if _read_regular(fence, "liveness fence") != fence_raw:
            _fail("liveness fence changed during admission")
        if _read_regular(manifest_path, "runtime manifest") != manifest_raw:
            _fail("runtime manifest changed during admission")
        if _read_regular(receipt_path, "recovery receipt") != receipt_raw:
            _fail("recovery receipt changed during admission")
        if _read_regular(archive_path, "recovery archive manifest") != archive_raw:
            _fail("recovery archive changed during admission")
        if _read_regular(events, "chain-control journal") != events_raw:
            _fail("chain-control journal changed during admission")
        _, archive_after = _json(archive_path, "recovery archive manifest")
        if (
            _archive_identity(
                archive_path,
                archive_after,
                operation=operation,
                old_sha=old_sha,
            )
            != archive_identity
        ):
            _fail("recovery archive evidence changed during admission")
        if state_path.exists():
            _fail("chain state appeared during admission")
        if (
            _git_identity(
                workspace_path,
                expected_head=new_sha,
                expected_branch=expected_branch,
                canonical_origin=canonical_origin,
            )
            != runtime_identity
        ):
            _fail("recovered runtime Git authority changed during admission")
        # Keep the computed values live so this code remains an explicit
        # authority attestation rather than a discarded probe.
        if not runtime_identity or not event:
            _fail("recovered runtime authority attestation is incomplete")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("marker")
    parser.add_argument("state")
    parser.add_argument("runtime_src")
    parser.add_argument("session")
    parser.add_argument("slug")
    parser.add_argument("spec", nargs="?", default="")
    parser.add_argument("workspace", nargs="?", default="")
    parser.add_argument("canonical_origin", nargs="?", default="")
    args = parser.parse_args(argv)
    _admit(
        manifest_path=Path(args.manifest),
        marker_path=Path(args.marker),
        state_path=Path(args.state),
        runtime_src=args.runtime_src,
        session=args.session,
        slug=args.slug,
        expected_spec=args.spec or None,
        expected_workspace=args.workspace or None,
        canonical_origin=args.canonical_origin or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
