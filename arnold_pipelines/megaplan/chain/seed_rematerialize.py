"""Guarded rematerialization of a materialized milestone from a new seed bundle."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import driver_lock, plan_lock
from arnold_pipelines.megaplan.anchors import (
    AnchorCaptureRequest,
    attach_anchor_documents,
    resolve_anchor_path,
)
from arnold_pipelines.megaplan.artifacts import markdown_body
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.execution_binding import active_execution_identity
from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_KEY, AUTHORITY_SCHEMA
from arnold_pipelines.megaplan.chain.target_rebind import (
    _atomic_write,
    _assert_clean_worktree,
    _current_branch,
    _current_head,
    _guard_branch,
    _guard_git_sha,
    _guard_sha256,
    _is_ancestor,
    _json_bytes,
    _load_json_bytes,
    _transaction_lock,
    sha256_path,
)
from arnold_pipelines.megaplan.planning.source_binding import canonical_source_identity
from arnold_pipelines.megaplan.runtime.doc_assembly import extract_settled_decisions
from arnold_pipelines.megaplan.types import CliError


SEED_MANIFEST_SCHEMA = "arnold.megaplan.seed_manifest.v1"
SEED_REMATERIALIZE_SCHEMA = "arnold.megaplan.seed_rematerialize.v1"
SEED_REMATERIALIZE_ERROR = "seed_rematerialize_refused"
_REQUIRED_KINDS = frozenset({"chain_spec", "milestone_brief", "north_star", "decision"})


def _refuse(message: str, *, extra: Mapping[str, Any] | None = None) -> CliError:
    return CliError(SEED_REMATERIALIZE_ERROR, message, extra=dict(extra or {}))


def _project_asset(root: Path, value: Any, *, label: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise _refuse(f"{label} path is required")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise _refuse(f"{label} must be a safe project-relative path")
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise _refuse(f"{label} escapes the guarded project root") from exc
    return resolved


def _load_manifest(
    manifest_path: Path,
    *,
    expected_sha256: str,
    project_root: Path,
    session_id: str,
    milestone: str,
    plan: str,
    branch: str,
    head: str,
    spec_path: Path,
    milestone_spec: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected = _guard_sha256(expected_sha256, label="seed-manifest SHA-256")
    raw, manifest = _load_json_bytes(manifest_path, label="seed manifest")
    if hashlib.sha256(raw).hexdigest() != expected:
        raise _refuse("seed manifest SHA-256 changed")
    exact = {
        "schema": SEED_MANIFEST_SCHEMA,
        "session_id": session_id,
        "milestone": milestone,
        "plan": plan,
    }
    for key, value in exact.items():
        if manifest.get(key) != value:
            raise _refuse(f"seed manifest {key} does not match the guard")
    target = manifest.get("target")
    if not isinstance(target, Mapping) or target.get("branch") != branch or target.get("head") != head:
        raise _refuse("seed manifest target branch/HEAD does not match the guard")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise _refuse("seed manifest assets must be a non-empty list")
    verified: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    kinds: set[str] = set()
    for index, entry in enumerate(assets):
        if not isinstance(entry, Mapping):
            raise _refuse(f"seed manifest asset {index} must be an object")
        kind = str(entry.get("kind") or "").strip()
        path = _project_asset(project_root, entry.get("path"), label=f"asset {index}")
        relative = path.relative_to(project_root).as_posix()
        key = (kind, relative)
        if key in seen:
            raise _refuse(f"duplicate seed manifest asset {kind}:{relative}")
        seen.add(key)
        kinds.add(kind)
        if not path.is_file():
            raise _refuse(f"seed manifest asset is unavailable: {relative}")
        expected_asset_sha = _guard_sha256(
            str(entry.get("sha256") or ""),
            label=f"asset {index} SHA-256",
        )
        observed = sha256_path(path)
        if observed != expected_asset_sha:
            raise _refuse(
                f"seed manifest asset changed: {relative}",
                extra={"expected_sha256": expected_asset_sha, "observed_sha256": observed},
            )
        verified.append(
            {
                "kind": kind,
                "path": relative,
                "sha256": observed,
                "size_bytes": path.stat().st_size,
            }
        )
    missing = sorted(_REQUIRED_KINDS - kinds)
    if missing:
        raise _refuse(f"seed manifest is missing load-bearing kinds: {', '.join(missing)}")
    spec_rel = spec_path.resolve().relative_to(project_root).as_posix()
    if not any(item["kind"] == "chain_spec" and item["path"] == spec_rel for item in verified):
        raise _refuse("seed manifest chain_spec does not name the active chain spec")
    idea_path = Path(str(milestone_spec.idea))
    if not idea_path.is_absolute():
        idea_path = project_root / idea_path
    idea_rel = idea_path.resolve().relative_to(project_root).as_posix()
    if not any(
        item["kind"] == "milestone_brief" and item["path"] == idea_rel
        for item in verified
    ):
        raise _refuse("seed manifest milestone_brief does not name the active milestone brief")
    return manifest, verified


def _assert_paused_pre_execute(
    chain: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    expected_plan: str,
) -> None:
    chain_meta = chain.get("metadata")
    chain_pause = chain_meta.get(AUTHORITY_KEY) if isinstance(chain_meta, Mapping) else None
    plan_meta = plan.get("meta")
    plan_pause = plan_meta.get(AUTHORITY_KEY) if isinstance(plan_meta, Mapping) else None
    if not (
        chain.get("last_state") == "paused"
        and plan.get("current_state") == "paused"
        and isinstance(chain_pause, Mapping)
        and chain_pause.get("active") is True
        and chain_pause.get("schema_version") == AUTHORITY_SCHEMA
        and chain_pause.get("plan") == expected_plan
        and isinstance(plan_pause, Mapping)
        and plan_pause.get("schema_version") == AUTHORITY_SCHEMA
    ):
        raise _refuse("seed rematerialization requires matching durable operator pause")
    if plan.get("active_step") is not None:
        raise _refuse("seed rematerialization requires no active plan step")
    history = plan.get("history")
    for entry in history if isinstance(history, list) else []:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("step") or "").strip().lower() == "execute":
            raise _refuse("seed rematerialization is forbidden after execute history")
    execution_artifacts = sorted(
        path.relative_to(path.parent).as_posix()
        for pattern in ("execution.json", "execution_batch*.json")
        for path in Path(str(plan.get("_plan_dir") or ".")).glob(pattern)
        if path.is_file()
    )
    if execution_artifacts:
        raise _refuse(
            "seed rematerialization is forbidden after execution artifacts",
            extra={"artifacts": execution_artifacts},
        )


def _archive_plan(
    plan_dir: Path,
    archive_dir: Path,
    *,
    plan_raw: bytes,
    chain_raw: bytes,
) -> tuple[list[tuple[Path, Path]], list[dict[str, Any]], str]:
    if archive_dir.exists():
        raise _refuse(f"seed archive already exists: {archive_dir}")
    archive_dir.mkdir(parents=True)
    _atomic_write(archive_dir / "state.json", plan_raw)
    _atomic_write(archive_dir / "chain-state.json", chain_raw)
    records = [
        {
            "path": "state.json",
            "sha256": hashlib.sha256(plan_raw).hexdigest(),
            "size_bytes": len(plan_raw),
        }
        ,
        {
            "path": "chain-state.json",
            "sha256": hashlib.sha256(chain_raw).hexdigest(),
            "size_bytes": len(chain_raw),
        },
    ]
    moves: list[tuple[Path, Path]] = []
    for source in sorted(plan_dir.rglob("*")):
        if not source.is_file() or source.name == "state.json" or source.name.endswith(".lock"):
            continue
        relative = source.relative_to(plan_dir)
        destination = archive_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        moves.append((source, destination))
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256_path(destination),
                "size_bytes": destination.stat().st_size,
            }
        )
    manifest_core = {
        "schema": "arnold.megaplan.seed_snapshot.v1",
        "files": records,
    }
    manifest = {
        **manifest_core,
        "content_sha256": hashlib.sha256(
            json.dumps(manifest_core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    manifest_bytes = _json_bytes(manifest)
    _atomic_write(archive_dir / "snapshot-manifest.json", manifest_bytes)
    return moves, records, hashlib.sha256(manifest_bytes).hexdigest()


def _restore_plan_archive(
    plan_dir: Path,
    archive_dir: Path,
    moves: list[tuple[Path, Path]],
) -> None:
    for path in sorted(plan_dir.rglob("*"), reverse=True):
        if path.is_file() and path.name != "state.json" and not path.name.endswith(".lock"):
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    for source, archived in reversed(moves):
        if archived.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(archived, source)
    shutil.rmtree(archive_dir, ignore_errors=True)


def _seed_event(
    *,
    actor: str,
    reason: str,
    manifest_sha256: str,
    manifest: Mapping[str, Any],
    verified_assets: list[dict[str, Any]],
    old_plan_sha256: str,
    old_chain_sha256: str,
    archive_path: str,
    archive_manifest_sha256: str,
) -> dict[str, Any]:
    core = {
        "schema": SEED_REMATERIALIZE_SCHEMA,
        "rematerialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": actor,
        "reason": reason,
        "seed_manifest_sha256": manifest_sha256,
        "seed_manifest": dict(manifest),
        "verified_assets": verified_assets,
        "superseded_plan_state_sha256": old_plan_sha256,
        "superseded_chain_state_sha256": old_chain_sha256,
        "archive_path": archive_path,
        "archive_manifest_sha256": archive_manifest_sha256,
        "direction": "cutover",
    }
    return {
        **core,
        "content_sha256": hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _append_seed_binding(metadata: dict[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    existing = metadata.get("seed_source_binding")
    binding = dict(existing) if isinstance(existing, Mapping) else {}
    events = binding.get("events")
    events = list(events) if isinstance(events, list) else []
    events.append(dict(event))
    binding.update(
        {
            "schema": SEED_REMATERIALIZE_SCHEMA,
            "current_manifest_sha256": event["seed_manifest_sha256"],
            "current_event_sha256": event["content_sha256"],
            "events": events,
        }
    )
    metadata["seed_source_binding"] = binding
    return binding


def _rebind_execution_bundle(
    chain: dict[str, Any],
    *,
    manifest: Mapping[str, Any],
    event: Mapping[str, Any],
    active_identity: Mapping[str, Any],
) -> None:
    metadata = chain.setdefault("metadata", {})
    binding = metadata.get("execution_binding") if isinstance(metadata, dict) else None
    if not isinstance(binding, dict):
        return
    previous = binding.get("launched_identity")
    previous_bundle = str((previous or {}).get("bundle_sha256") or "")
    expected_previous = str(manifest.get("previous_bundle_sha256") or "")
    expected_active = str(manifest.get("active_bundle_sha256") or "")
    if previous_bundle != expected_previous:
        raise _refuse("seed manifest previous bundle does not match persisted execution binding")
    if active_identity.get("bundle_sha256") != expected_active:
        raise _refuse("seed manifest active bundle does not match current execution identity")
    if not active_identity.get("ready"):
        raise _refuse(
            "current execution identity is not ready",
            extra={"errors": active_identity.get("errors") or []},
        )
    events = binding.get("seed_rebind_events")
    events = list(events) if isinstance(events, list) else []
    events.append(
        {
            "schema": SEED_REMATERIALIZE_SCHEMA,
            "content_sha256": event["content_sha256"],
            "from_bundle_sha256": previous_bundle,
            "to_bundle_sha256": expected_active,
            "rematerialized_at": event["rematerialized_at"],
        }
    )
    runtime_binding = binding.get("runtime_binding")
    binding["launched_identity"] = dict(active_identity)
    binding["seed_rebind_events"] = events
    binding["last_seed_rebound_at"] = event["rematerialized_at"]
    if runtime_binding is not None:
        binding["runtime_binding"] = runtime_binding


def _verified_archive(
    archive_dir: Path,
    *,
    expected_manifest_sha256: str,
) -> tuple[bytes, dict[str, Any], bytes, dict[str, Any], list[dict[str, Any]]]:
    manifest_path = archive_dir / "snapshot-manifest.json"
    manifest_raw, manifest = _load_json_bytes(manifest_path, label="seed snapshot manifest")
    if hashlib.sha256(manifest_raw).hexdigest() != expected_manifest_sha256:
        raise _refuse("seed snapshot manifest does not match the rollback guard")
    content_sha = str(manifest.get("content_sha256") or "")
    core = {key: value for key, value in manifest.items() if key != "content_sha256"}
    observed_content = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if content_sha != observed_content:
        raise _refuse("seed snapshot manifest content digest is forged")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise _refuse("seed snapshot manifest files are malformed")
    for entry in files:
        if not isinstance(entry, Mapping):
            raise _refuse("seed snapshot manifest file entry is malformed")
        path = _project_asset(archive_dir, entry.get("path"), label="archived file")
        if not path.is_file() or sha256_path(path) != str(entry.get("sha256") or ""):
            raise _refuse(f"archived seed snapshot file is missing or forged: {entry.get('path')}")
    old_plan_raw, old_plan = _load_json_bytes(archive_dir / "state.json", label="archived plan")
    old_chain_raw, old_chain = _load_json_bytes(
        archive_dir / "chain-state.json",
        label="archived chain state",
    )
    return old_plan_raw, old_plan, old_chain_raw, old_chain, [dict(item) for item in files]


def _fresh_epoch_is_untouched(plan: Mapping[str, Any], cutover_sha: str) -> bool:
    history = plan.get("history")
    versions = plan.get("plan_versions")
    return bool(
        plan.get("current_state") == "paused"
        and plan.get("iteration") == 0
        and isinstance(versions, list)
        and not versions
        and isinstance(history, list)
        and len(history) == 1
        and isinstance(history[0], Mapping)
        and history[0].get("step") == "init"
        and history[0].get("seed_rematerialize_sha256") == cutover_sha
        and plan.get("active_step") is None
        and not plan.get("latest_failure")
    )


def _rollback_event(
    *,
    actor: str,
    reason: str,
    cutover_event: Mapping[str, Any],
    archive_manifest_sha256: str,
    current_plan_sha256: str,
    current_chain_sha256: str,
) -> dict[str, Any]:
    core = {
        "schema": SEED_REMATERIALIZE_SCHEMA,
        "direction": "rollback",
        "rematerialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": actor,
        "reason": reason,
        "seed_manifest_sha256": cutover_event["seed_manifest_sha256"],
        "cutover_event_sha256": cutover_event["content_sha256"],
        "archive_path": cutover_event["archive_path"],
        "archive_manifest_sha256": archive_manifest_sha256,
        "rolled_back_plan_state_sha256": current_plan_sha256,
        "rolled_back_chain_state_sha256": current_chain_sha256,
    }
    return {
        **core,
        "content_sha256": hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _rollback_seed_epoch(
    *,
    spec_path: Path,
    project_root: Path,
    plan_dir: Path,
    plan_path: Path,
    state_path: Path,
    chain_raw: bytes,
    chain: dict[str, Any],
    plan_raw: bytes,
    plan: dict[str, Any],
    expected_manifest_sha256: str,
    manifest_path: Path,
    expected_cutover_event_sha256: str | None,
    expected_archive_manifest_sha256: str | None,
    reason: str,
    actor: str,
    failure_injector: Callable[[str], None] | None,
) -> dict[str, Any]:
    cutover_guard = _guard_sha256(
        str(expected_cutover_event_sha256 or ""),
        label="cutover event SHA-256",
    )
    archive_guard = _guard_sha256(
        str(expected_archive_manifest_sha256 or ""),
        label="archive manifest SHA-256",
    )
    if sha256_path(manifest_path) != expected_manifest_sha256:
        raise _refuse("seed manifest SHA-256 changed before rollback")
    plan_meta = plan.get("meta")
    plan_binding = (
        plan_meta.get("seed_source_binding") if isinstance(plan_meta, Mapping) else None
    )
    chain_meta = chain.get("metadata")
    chain_binding = (
        chain_meta.get("seed_source_binding") if isinstance(chain_meta, Mapping) else None
    )
    if plan_binding != chain_binding or not isinstance(plan_binding, Mapping):
        raise _refuse("chain and plan seed bindings diverged")
    events = plan_binding.get("events")
    cutover = events[-1] if isinstance(events, list) and events else None
    if (
        not isinstance(cutover, Mapping)
        or cutover.get("direction") != "cutover"
        or cutover.get("content_sha256") != cutover_guard
        or cutover.get("seed_manifest_sha256") != expected_manifest_sha256
        or cutover.get("archive_manifest_sha256") != archive_guard
    ):
        raise _refuse("rollback guards do not exactly name the active seed cutover")
    if not _fresh_epoch_is_untouched(plan, cutover_guard):
        raise _refuse("seed rollback is unavailable after new planning or execution evidence")
    archive_value = str(cutover.get("archive_path") or "")
    archive_dir = (plan_dir.parent / archive_value).resolve(strict=False)
    archive_root = (plan_dir.parent / ".seed-rematerialize-archive").resolve(strict=False)
    try:
        archive_dir.relative_to(archive_root)
    except ValueError as exc:
        raise _refuse("seed rollback archive path escapes the custody archive") from exc
    old_plan_raw, old_plan, old_chain_raw, old_chain, snapshot_files = _verified_archive(
        archive_dir,
        expected_manifest_sha256=archive_guard,
    )
    if hashlib.sha256(old_plan_raw).hexdigest() != cutover.get(
        "superseded_plan_state_sha256"
    ):
        raise _refuse("archived predecessor plan does not match the cutover receipt")
    if hashlib.sha256(old_chain_raw).hexdigest() != cutover.get(
        "superseded_chain_state_sha256"
    ):
        raise _refuse("archived predecessor chain does not match the cutover receipt")

    rollback = _rollback_event(
        actor=actor,
        reason=reason,
        cutover_event=cutover,
        archive_manifest_sha256=archive_guard,
        current_plan_sha256=hashlib.sha256(plan_raw).hexdigest(),
        current_chain_sha256=hashlib.sha256(chain_raw).hexdigest(),
    )
    old_plan_meta = old_plan.setdefault("meta", {})
    old_chain_meta = old_chain.setdefault("metadata", {})
    if not isinstance(old_plan_meta, dict) or not isinstance(old_chain_meta, dict):
        raise _refuse("archived predecessor metadata is malformed")
    # Target rollback occurs first. Preserve its append-only project receipt
    # and observational checkout fields while restoring every planning field.
    for key in ("project_source_binding", "execution_environment", "chain_policy"):
        current_value = plan_meta.get(key) if isinstance(plan_meta, Mapping) else None
        if current_value is not None:
            old_plan_meta[key] = current_value
    for key in ("project_source_binding", "execution_environment"):
        current_value = chain_meta.get(key) if isinstance(chain_meta, Mapping) else None
        if current_value is not None:
            old_chain_meta[key] = current_value
    # Runtime rollback is deliberately performed before target/seed rollback so
    # the still-current B control interpreter can independently prove A.  Keep
    # that append-only ledger and its A current identity while restoring the
    # predecessor launch/spec bundle from the seed archive.
    current_execution = (
        chain_meta.get("execution_binding") if isinstance(chain_meta, Mapping) else None
    )
    restored_execution = old_chain_meta.get("execution_binding")
    if isinstance(current_execution, Mapping) and isinstance(restored_execution, dict):
        current_runtime = current_execution.get("runtime_binding")
        if isinstance(current_runtime, Mapping):
            restored_execution["runtime_binding"] = dict(current_runtime)
    restored_plan_binding = _append_seed_binding(old_plan_meta, cutover)
    restored_chain_binding = _append_seed_binding(old_chain_meta, cutover)
    restored_plan_binding["events"].append(rollback)
    restored_chain_binding["events"].append(rollback)
    restored_plan_binding["current_event_sha256"] = rollback["content_sha256"]
    restored_chain_binding["current_event_sha256"] = rollback["content_sha256"]
    restored_plan_binding["current_manifest_sha256"] = ""
    restored_chain_binding["current_manifest_sha256"] = ""
    old_plan["current_state"] = "paused"
    old_chain["last_state"] = "paused"
    plan_pause = old_plan_meta.get(AUTHORITY_KEY)
    chain_pause = old_chain_meta.get(AUTHORITY_KEY)
    if isinstance(plan_pause, dict):
        plan_pause["seed_rollback_sha256"] = rollback["content_sha256"]
    if isinstance(chain_pause, dict):
        chain_pause["seed_rollback_sha256"] = rollback["content_sha256"]

    backup_dir = Path(tempfile.mkdtemp(prefix=".seed-rollback-", dir=str(plan_dir.parent)))
    moved_active: list[tuple[Path, Path]] = []
    try:
        for source in sorted(plan_dir.rglob("*")):
            if not source.is_file() or source.name == "state.json" or source.name.endswith(".lock"):
                continue
            relative = source.relative_to(plan_dir)
            destination = backup_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved_active.append((source, destination))
        for entry in snapshot_files:
            relative = str(entry["path"])
            if relative in {"state.json", "chain-state.json"}:
                continue
            source = archive_dir / relative
            destination = plan_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if failure_injector is not None:
            failure_injector("after_archive_restore")
        _atomic_write(plan_path, _json_bytes(old_plan))
        if failure_injector is not None:
            failure_injector("after_rollback_plan_write")
        _atomic_write(state_path, _json_bytes(old_chain))
        if failure_injector is not None:
            failure_injector("after_rollback_chain_write")
    except BaseException:
        _atomic_write(plan_path, plan_raw)
        _atomic_write(state_path, chain_raw)
        for path in sorted(plan_dir.rglob("*"), reverse=True):
            if path.is_file() and path.name != "state.json" and not path.name.endswith(".lock"):
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        for original, backup in reversed(moved_active):
            if backup.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, original)
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)
    return {
        "direction": "rollback",
        "event": rollback,
        "seed_source_binding": restored_plan_binding,
        "archive_path": archive_value,
        "restored_files": snapshot_files,
        "plan_state_sha256": sha256_path(plan_path),
        "chain_state_sha256": sha256_path(state_path),
        "next_state_after_resume": (
            plan_pause.get("previous_current_state")
            if isinstance(plan_pause, Mapping)
            else "critiqued"
        ),
    }


def seed_rematerialize(
    spec_path: Path,
    project_root: Path,
    *,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_branch: str,
    expected_head: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    seed_manifest_path: Path,
    expected_seed_manifest_sha256: str,
    direction: str = "cutover",
    expected_cutover_event_sha256: str | None = None,
    expected_archive_manifest_sha256: str | None = None,
    reason: str,
    actor: str = "operator",
    verified_external_runtime_identity: Mapping[str, Any] | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Cut over to exact seeds or restore their archived predecessor epoch."""

    if direction not in {"cutover", "rollback"}:
        raise _refuse("seed rematerialize direction must be cutover or rollback")
    if not all(
        str(value or "").strip()
        for value in (
            expected_session_id,
            expected_current_milestone,
            expected_current_plan,
            reason,
            actor,
        )
    ):
        raise _refuse("every seed-rematerialize guard is required")
    project_root = project_root.resolve(strict=False)
    spec_path = spec_path.resolve(strict=False)
    seed_manifest_path = seed_manifest_path.resolve(strict=False)
    if project_root.name != expected_session_id:
        raise _refuse("session id does not match the guarded project root")
    try:
        spec_path.relative_to(project_root)
    except ValueError as exc:
        raise _refuse("chain spec must be inside the guarded project root") from exc
    branch = _guard_branch(expected_branch, label="expected branch")
    head = _guard_git_sha(expected_head, label="expected head")
    spec_sha = _guard_sha256(expected_spec_sha256, label="spec SHA-256")
    chain_sha = _guard_sha256(expected_chain_state_sha256, label="chain-state SHA-256")
    plan_sha = _guard_sha256(expected_plan_state_sha256, label="plan-state SHA-256")
    manifest_sha = _guard_sha256(
        expected_seed_manifest_sha256,
        label="seed-manifest SHA-256",
    )
    if sha256_path(spec_path) != spec_sha:
        raise _refuse("chain spec SHA-256 changed")

    state_path = chain_spec._state_path_for(spec_path)
    plan_dir = find_plan_dir(project_root, expected_current_plan)
    if plan_dir is None:
        raise _refuse("current plan directory is unavailable")
    plan_path = plan_dir / "state.json"

    with _transaction_lock(state_path), driver_lock(plan_dir), plan_lock(
        plan_dir,
        step="chain seed-rematerialize",
    ):
        chain_raw, chain = _load_json_bytes(state_path, label="chain state")
        plan_raw, plan = _load_json_bytes(plan_path, label="plan state")
        if hashlib.sha256(chain_raw).hexdigest() != chain_sha:
            raise _refuse("chain-state SHA-256 changed")
        if hashlib.sha256(plan_raw).hexdigest() != plan_sha:
            raise _refuse("plan-state SHA-256 changed")
        if _current_branch(project_root) != branch or _current_head(project_root) != head:
            raise _refuse("current branch/HEAD does not match the seed guard")
        _assert_clean_worktree(project_root)
        if chain.get("current_plan_name") != expected_current_plan:
            raise _refuse("current plan does not match the seed guard")
        if chain.get("last_state") != "paused":
            raise _refuse("chain is not paused")
        spec = chain_spec.load_spec(spec_path)
        index = chain.get("current_milestone_index")
        if not isinstance(index, int) or index < 0 or index >= len(spec.milestones):
            raise _refuse("current milestone index is invalid")
        milestone = spec.milestones[index]
        if milestone.label != expected_current_milestone:
            raise _refuse("current milestone does not match the seed guard")
        plan["_plan_dir"] = str(plan_dir)
        _assert_paused_pre_execute(chain, plan, expected_plan=expected_current_plan)
        plan.pop("_plan_dir", None)
        meta = plan.get("meta")
        policy = meta.get("chain_policy") if isinstance(meta, Mapping) else None
        if not isinstance(policy, Mapping) or policy.get("milestone_base_sha") != head:
            raise _refuse("plan milestone base does not match the guarded HEAD")
        source_binding = meta.get("project_source_binding") if isinstance(meta, Mapping) else None
        if isinstance(source_binding, Mapping):
            current = source_binding.get("current")
            if (
                not isinstance(current, Mapping)
                or current.get("branch") != branch
                or not isinstance(current.get("head"), str)
                or not _is_ancestor(project_root, str(current["head"]), head)
            ):
                raise _refuse("project-source binding does not cover the guarded checkout")

        if direction == "rollback":
            return _rollback_seed_epoch(
                spec_path=spec_path,
                project_root=project_root,
                plan_dir=plan_dir,
                plan_path=plan_path,
                state_path=state_path,
                chain_raw=chain_raw,
                chain=chain,
                plan_raw=plan_raw,
                plan=plan,
                expected_manifest_sha256=manifest_sha,
                manifest_path=seed_manifest_path,
                expected_cutover_event_sha256=expected_cutover_event_sha256,
                expected_archive_manifest_sha256=expected_archive_manifest_sha256,
                reason=reason,
                actor=actor,
                failure_injector=failure_injector,
            )

        manifest, verified_assets = _load_manifest(
            seed_manifest_path,
            expected_sha256=manifest_sha,
            project_root=project_root,
            session_id=expected_session_id,
            milestone=expected_current_milestone,
            plan=expected_current_plan,
            branch=branch,
            head=head,
            spec_path=spec_path,
            milestone_spec=milestone,
        )
        active_identity = active_execution_identity(spec_path)
        if isinstance(verified_external_runtime_identity, Mapping):
            active_identity["runtime"] = dict(verified_external_runtime_identity)
            active_identity["ready"] = True
            active_identity["errors"] = []
        expected_active_bundle = str(manifest.get("active_bundle_sha256") or "")
        if active_identity.get("bundle_sha256") != expected_active_bundle:
            raise _refuse("seed manifest does not bind the active chain/assets bundle")

        event_hint = hashlib.sha256(
            (manifest_sha + plan_sha + chain_sha).encode()
        ).hexdigest()[:16]
        archive_dir = (
            plan_dir.parent
            / ".seed-rematerialize-archive"
            / plan_dir.name
            / event_hint
        )
        archive_rel = archive_dir.relative_to(plan_dir.parent).as_posix()
        moves: list[tuple[Path, Path]] = []
        try:
            moves, snapshot_files, archive_manifest_sha = _archive_plan(
                plan_dir,
                archive_dir,
                plan_raw=plan_raw,
                chain_raw=chain_raw,
            )
            if failure_injector is not None:
                failure_injector("after_archive")
            event = _seed_event(
                actor=actor,
                reason=reason,
                manifest_sha256=manifest_sha,
                manifest=manifest,
                verified_assets=verified_assets,
                old_plan_sha256=plan_sha,
                old_chain_sha256=chain_sha,
                archive_path=archive_rel,
                archive_manifest_sha256=archive_manifest_sha,
            )
            old_meta = plan.get("meta")
            old_meta = old_meta if isinstance(old_meta, Mapping) else {}
            plan_pause = dict(old_meta.get(AUTHORITY_KEY) or {})
            plan_pause["previous_current_state"] = "initialized"
            plan_pause["seed_rematerialize_sha256"] = event["content_sha256"]
            plan_config = dict(plan.get("config") or {})
            brief_entry = next(
                item for item in verified_assets if item["kind"] == "milestone_brief"
            )
            brief_path = project_root / brief_entry["path"]
            idea = markdown_body(brief_path).strip()
            fresh_meta: dict[str, Any] = {
                "significant_counts": [],
                "weighted_scores": [],
                "plan_deltas": [],
                "recurring_critiques": [],
                "total_cost_usd": 0.0,
                "overrides": [],
                "notes": [],
                AUTHORITY_KEY: plan_pause,
                "chain_policy": dict(old_meta.get("chain_policy") or {}),
            }
            for key in (
                "execution_environment",
                "project_source_binding",
                "seed_source_binding",
                "worktree",
            ):
                value = old_meta.get(key)
                if value is not None:
                    fresh_meta[key] = value
            binding = _append_seed_binding(fresh_meta, event)
            fresh_plan: dict[str, Any] = {
                "schema_version": plan.get("schema_version", 1),
                "name": expected_current_plan,
                "idea": idea,
                "idea_snapshot_path": "idea_snapshot.md",
                "current_state": "paused",
                "iteration": 0,
                "created_at": plan.get("created_at") or event["rematerialized_at"],
                "config": plan_config,
                "sessions": {},
                "plan_versions": [],
                "history": [
                    {
                        "step": "init",
                        "result": "success",
                        "timestamp": event["rematerialized_at"],
                        "seed_rematerialize_sha256": event["content_sha256"],
                    }
                ],
                "meta": fresh_meta,
                "last_gate": {},
            }
            fresh_meta["canonical_source_binding"] = {
                "schema": "arnold.megaplan.canonical_source_binding.v1",
                "bound_at": event["rematerialized_at"],
                "bound": canonical_source_identity(brief_path, project_dir=project_root),
            }
            _atomic_write(plan_dir / "idea_snapshot.md", idea.encode("utf-8"))
            anchor_requests: list[AnchorCaptureRequest] = []
            if spec.anchors.north_star:
                anchor_requests.append(
                    AnchorCaptureRequest(
                        anchor_type="north_star",
                        scope="epic",
                        source_path=resolve_anchor_path(spec_path, spec.anchors.north_star),
                        source_kind="chain",
                        source_spec_path=spec_path,
                    )
                )
            if milestone.anchors.north_star:
                anchor_requests.append(
                    AnchorCaptureRequest(
                        anchor_type="north_star",
                        scope="plan",
                        source_path=resolve_anchor_path(spec_path, milestone.anchors.north_star),
                        source_kind="milestone",
                        label=milestone.label,
                        source_spec_path=spec_path,
                    )
                )
            attach_anchor_documents(
                plan_dir=plan_dir,
                state=fresh_plan,
                documents=anchor_requests,
                project_root=project_root,
            )
            imported_decisions: list[dict[str, Any]] = []
            for item in verified_assets:
                if item["kind"] == "decision":
                    decisions, warnings = extract_settled_decisions(
                        (project_root / item["path"]).read_text(encoding="utf-8")
                    )
                    if not decisions:
                        raise _refuse(
                            f"load-bearing decision asset produced no settled decisions: {item['path']}"
                        )
                    imported_decisions.extend(decisions)
                    for warning in warnings:
                        fresh_meta["notes"].append(
                            {
                                "timestamp": event["rematerialized_at"],
                                "note": warning,
                                "source": "seed-rematerialize",
                            }
                        )
            fresh_meta["imported_decisions"] = imported_decisions

            chain_meta = chain.setdefault("metadata", {})
            if not isinstance(chain_meta, dict):
                raise _refuse("chain metadata is malformed")
            chain_binding = _append_seed_binding(chain_meta, event)
            if chain_binding != binding:
                raise _refuse("chain and plan seed bindings diverged")
            _rebind_execution_bundle(
                chain,
                manifest=manifest,
                event=event,
                active_identity=active_identity,
            )
            chain_pause = chain_meta.get(AUTHORITY_KEY)
            if isinstance(chain_pause, dict):
                chain_pause["previous_plan_state"] = "initialized"
                chain_pause["previous_chain_last_state"] = "initialized"
                chain_pause["seed_rematerialize_sha256"] = event["content_sha256"]

            _atomic_write(plan_path, _json_bytes(fresh_plan))
            if failure_injector is not None:
                failure_injector("after_plan_write")
            _atomic_write(state_path, _json_bytes(chain))
            if failure_injector is not None:
                failure_injector("after_chain_write")
        except BaseException:
            _atomic_write(plan_path, plan_raw)
            _atomic_write(state_path, chain_raw)
            _restore_plan_archive(plan_dir, archive_dir, moves)
            raise

        return {
            "event": event,
            "seed_source_binding": binding,
            "archive_path": archive_rel,
            "archived_files": snapshot_files,
            "plan_state_sha256": sha256_path(plan_path),
            "chain_state_sha256": sha256_path(state_path),
            "next_state_after_resume": "initialized",
        }


__all__ = [
    "SEED_MANIFEST_SCHEMA",
    "SEED_REMATERIALIZE_ERROR",
    "SEED_REMATERIALIZE_SCHEMA",
    "seed_rematerialize",
]
