"""Guarded retirement of a paused chain's unfinished current attempt."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_KEY, AUTHORITY_SCHEMA
from arnold_pipelines.megaplan.chain.target_rebind import (
    _load_json_bytes,
    _guard_sha256,
    sha256_path,
)
from arnold_pipelines.megaplan.types import CliError


RESTART_ERROR = "current_attempt_restart_refused"
RESTART_SCHEMA = "arnold.megaplan.current-attempt-restart.v1"
LEGACY_ATTESTATION_SCHEMA = "arnold.megaplan.current-attempt-restart-legacy-attestation.v1"
LEGACY_ATTESTATION_INTENT = "restart_current_attempt_legacy_receipt_attestation"
LEGACY_ATTESTATION_EVENT_KIND = "chain_control.restart_receipt_attested"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_OCCUPANCY_KEYS = ("owner", "runner", "tmux_session", "pid", "worker_pid")
_HISTORY_STEPS = frozenset({"execute", "finalize", "review"})
_ARTIFACT_PATTERNS = (
    "execution.json",
    "execution_batch*.json",
    "finalize.json",
    "finalize_output.json",
    "finalize_snapshot.json",
    "review.json",
    "review_v*.json",
)


def _refuse(message: str, *, extra: Mapping[str, Any] | None = None) -> CliError:
    return CliError(RESTART_ERROR, message, extra=dict(extra or {}))


def _conflict(message: str) -> Any:
    from arnold_pipelines.megaplan.incident.chain_control import ChainControlCasConflict

    return ChainControlCasConflict(message)


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise _refuse(f"{label} is required")
    return text


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _refuse(f"{label} must be an integer")
    return value


def _marker_occupied(marker: Mapping[str, Any]) -> str | None:
    for key in _OCCUPANCY_KEYS:
        value = marker.get(key)
        if value is None or value is False:
            continue
        if isinstance(value, (str, bytes, list, tuple, dict, set)) and not value:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return key
    return None


def _binding_digest(binding: Any) -> str:
    return hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _current_head(root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip().lower()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise _refuse("could not read current project-source HEAD") from exc
    if _FULL_SHA.fullmatch(value) is None:
        raise _refuse("current project-source HEAD is not a full Git SHA")
    return value


def _source_guard(chain: Mapping[str, Any]) -> dict[str, Any]:
    metadata = chain.get("metadata")
    binding = metadata.get("project_source_binding") if isinstance(metadata, Mapping) else None
    if not isinstance(binding, Mapping):
        raise _refuse("project-source binding is unavailable for restart custody")
    current = binding.get("current")
    if not isinstance(current, Mapping):
        raise _refuse("project-source binding current identity is unavailable for restart custody")
    branch = current.get("branch")
    head = current.get("head")
    if not isinstance(branch, str) or not branch.strip():
        raise _refuse("project-source binding current branch is unavailable for restart custody")
    if not isinstance(head, str) or _FULL_SHA.fullmatch(head.lower()) is None:
        raise _refuse("project-source binding current head is unavailable for restart custody")
    execution = metadata.get("execution_binding") if isinstance(metadata, Mapping) else None
    if not isinstance(execution, Mapping):
        raise _refuse("execution binding is unavailable for restart custody")
    return {
        "source_binding": dict(binding),
        "source": {"branch": branch, "head": head.lower()},
        "execution_binding": dict(execution),
    }


def _matching_retirement(
    plan: Mapping[str, Any],
    *,
    operation_id: str,
    expected_current_plan: str,
    expected_cursor: int,
    expected_current_milestone: str,
) -> bool:
    if str(plan.get("current_state") or "").strip().lower() != "aborted":
        return False
    if plan.get("name") not in {None, expected_current_plan}:
        return False
    meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else None
    retirement = meta.get("retirement") if isinstance(meta, Mapping) else None
    return (
        isinstance(retirement, Mapping)
        and retirement.get("kind") == "retired_for_restart"
        and retirement.get("operation_id") == operation_id
        and retirement.get("cursor") == expected_cursor
        and retirement.get("milestone") == expected_current_milestone
    )


def _matching_restart_record(
    metadata: Mapping[str, Any],
    *,
    operation_id: str,
    expected_current_plan: str,
    expected_cursor: int,
    expected_current_milestone: str,
) -> bool:
    restart = metadata.get("current_attempt_restart")
    return (
        isinstance(restart, Mapping)
        and restart.get("schema") == RESTART_SCHEMA
        and restart.get("operation_id") == operation_id
        and restart.get("retired_plan") == expected_current_plan
        and restart.get("cursor") == expected_cursor
        and restart.get("milestone") == expected_current_milestone
    )


def _assert_spec_and_paths(spec_path: Path, project_root: Path) -> tuple[Path, Path]:
    spec_path = spec_path.expanduser().resolve(strict=False)
    project_root = project_root.expanduser().resolve(strict=False)
    try:
        spec_path.relative_to(project_root)
    except ValueError as exc:
        raise _refuse("chain spec must be inside the guarded project/session root") from exc
    return spec_path, project_root


def _assert_snapshot(
    *,
    spec_path: Path,
    project_root: Path,
    spec: Any,
    chain_raw: bytes,
    chain: Mapping[str, Any],
    plan_raw: bytes,
    plan: Mapping[str, Any],
    marker_raw: bytes,
    marker: Mapping[str, Any],
    plan_dir: Path,
    expected_session_id: str,
    expected_cursor: int,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    expected_state_revision: int,
    expected_marker_sha256: str,
    expected_binding_sha256: str,
    expected_source_head: str,
    operation_id: str,
) -> tuple[int, Any]:
    _guard_sha256(expected_spec_sha256, label="spec SHA-256")
    chain_hash = _guard_sha256(expected_chain_state_sha256, label="chain-state SHA-256")
    plan_hash = _guard_sha256(expected_plan_state_sha256, label="plan-state SHA-256")
    marker_hash = _guard_sha256(expected_marker_sha256, label="marker SHA-256")
    binding_hash = _guard_sha256(expected_binding_sha256, label="project-source binding SHA-256")
    metadata = chain.get("metadata")
    if not isinstance(metadata, Mapping):
        raise _refuse("chain metadata is missing")
    matching_retirement = _matching_retirement(
        plan,
        operation_id=operation_id,
        expected_current_plan=expected_current_plan,
        expected_cursor=expected_cursor,
        expected_current_milestone=expected_current_milestone,
    )
    matching_restart = _matching_restart_record(
        metadata,
        operation_id=operation_id,
        expected_current_plan=expected_current_plan,
        expected_cursor=expected_cursor,
        expected_current_milestone=expected_current_milestone,
    )
    if not matching_restart and hashlib.sha256(chain_raw).hexdigest() != chain_hash:
        raise _conflict("chain state changed since the restart guards were computed")
    if not matching_retirement and hashlib.sha256(plan_raw).hexdigest() != plan_hash:
        raise _conflict("plan state changed since the restart guards were computed")
    if hashlib.sha256(marker_raw).hexdigest() != marker_hash:
        raise _conflict("session marker changed since the restart guards were computed")
    if sha256_path(spec_path) != _guard_sha256(expected_spec_sha256, label="spec SHA-256"):
        raise _conflict("chain spec changed since the restart guards were computed")

    if project_root.name != expected_session_id:
        raise _refuse(f"session {project_root.name!r} does not match {expected_session_id!r}")
    if marker.get("session") != expected_session_id:
        raise _refuse("session marker session does not match the guarded project session")
    if marker.get("should_run") is not False:
        raise _refuse("current-attempt restart requires marker should_run to be false")
    occupied = _marker_occupied(marker)
    if occupied is not None:
        raise _refuse(f"session marker names an occupied {occupied}")
    if plan.get("active_step") is not None:
        raise _refuse("current-attempt restart requires no active plan step")

    pause = metadata.get(AUTHORITY_KEY)
    if not (
        isinstance(pause, Mapping)
        and pause.get("active") is True
        and pause.get("schema_version") == AUTHORITY_SCHEMA
        and chain.get("last_state") == "paused"
    ):
        raise _refuse("current-attempt restart requires an active durable operator pause")
    if pause.get("plan") not in {None, expected_current_plan}:
        raise _refuse("durable operator pause does not name the guarded current plan")

    revision = metadata.get("_nbf08_revision")
    if not matching_restart and (isinstance(revision, bool) or revision != expected_state_revision):
        raise _conflict(
            f"chain state revision does not match the guard: observed {revision!r}, expected {expected_state_revision}"
        )
    cursor = chain.get("current_milestone_index")
    if cursor != expected_cursor:
        raise _conflict(
            f"current milestone cursor does not match the guard: observed {cursor!r}, expected {expected_cursor}"
        )
    if chain.get("current_plan_name") != expected_current_plan:
        if not (matching_restart and not chain.get("current_plan_name")):
            raise _conflict("current plan does not match the restart guard")
    if plan.get("name") not in {None, expected_current_plan}:
        raise _refuse("plan state name does not match the restart guard")

    if not isinstance(cursor, int) or isinstance(cursor, bool) or cursor < 0 or cursor >= len(spec.milestones):
        raise _refuse("current milestone cursor is outside the chain spec")
    milestone = spec.milestones[cursor]
    if milestone.label != expected_current_milestone:
        raise _refuse(
            f"current milestone {milestone.label!r} does not match {expected_current_milestone!r}"
        )
    completed = chain.get("completed")
    if not isinstance(completed, list):
        raise _refuse("chain completed prefix is malformed")
    if any(isinstance(item, Mapping) and item.get("label") == expected_current_milestone for item in completed):
        raise _refuse("current milestone is already completed")

    restart = metadata.get("current_attempt_restart")
    if restart is not None and not matching_restart:
        raise _refuse("chain already carries a different current-attempt restart record")

    current_state = str(plan.get("current_state") or "").strip().lower()
    if current_state in {"done", "aborted", "cancelled"} and not matching_retirement:
        raise _refuse(f"current plan is already terminal ({current_state})")

    history = plan.get("history")
    has_history = any(
        isinstance(entry, Mapping)
        and str(entry.get("step") or "").strip().lower() in _HISTORY_STEPS
        for entry in (history if isinstance(history, list) else [])
    )
    artifacts = sorted(
        path.name
        for pattern in _ARTIFACT_PATTERNS
        for path in plan_dir.glob(pattern)
        if path.is_file()
    )
    if not has_history and not artifacts:
        raise _refuse("current plan is pre-execute; finalize/execute history is required")

    binding = metadata.get("project_source_binding")
    if _binding_digest(binding) != binding_hash:
        raise _conflict("project-source binding changed since the restart guards were computed")
    if isinstance(binding, Mapping):
        current = binding.get("current")
        source_head = current.get("head") if isinstance(current, Mapping) else None
        if not isinstance(source_head, str) or _FULL_SHA.fullmatch(source_head.lower()) is None:
            raise _refuse("project-source binding current.head is missing or malformed")
        observed_head = source_head.lower()
    else:
        observed_head = _current_head(project_root)
    if observed_head != expected_source_head.lower():
        raise _conflict(
            f"project-source HEAD does not match the guard: observed {observed_head}, expected {expected_source_head}"
        )
    return cursor, milestone


def _event_hash(root: Path, operation_id: str) -> str | None:
    from arnold_pipelines.megaplan.incident.chain_control import journal_for

    try:
        replay = journal_for(root).replay_strict()
    except Exception:
        return None
    for event in reversed(replay.get("accepted") or []):
        if event.get("operation_id") == operation_id and event.get("event_kind") == "chain_control.committed":
            value = event.get("event_hash")
            if isinstance(value, str):
                return value
    return None


def _receipt(
    *,
    outcome: str,
    operation_id: str,
    retired_plan: str,
    cursor: int,
    milestone: str,
    chain_state_sha256: str,
    plan_state_sha256: str,
    event_hash: str | None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "operation_id": operation_id,
        "retired_plan": retired_plan,
        "cursor": cursor,
        "milestone": milestone,
        "chain_state_sha256": chain_state_sha256,
        "plan_state_sha256": plan_state_sha256,
        "event_hash": event_hash,
    }


def restart_current_attempt(
    spec_path: Path,
    project_root: Path,
    *,
    marker_path: Path,
    expected_session_id: str,
    expected_cursor: int,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    expected_state_revision: int,
    expected_marker_sha256: str,
    expected_binding_sha256: str,
    expected_source_head: str,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Retire exactly the paused unfinished current plan, without replaying it."""

    expected_session_id = _require_text(expected_session_id, "expected session id")
    expected_current_milestone = _require_text(expected_current_milestone, "expected current milestone")
    expected_current_plan = _require_text(expected_current_plan, "expected current plan")
    reason = _require_text(reason, "reason")
    actor = _require_text(actor, "actor")
    expected_cursor = _require_int(expected_cursor, "expected cursor")
    expected_state_revision = _require_int(expected_state_revision, "expected state revision")
    expected_source_head = _require_text(expected_source_head, "expected source head").lower()
    if _FULL_SHA.fullmatch(expected_source_head) is None:
        raise _refuse("expected source head must be a full 40-character Git SHA")
    expected_spec_sha256 = _guard_sha256(expected_spec_sha256, label="spec SHA-256")
    expected_chain_state_sha256 = _guard_sha256(
        expected_chain_state_sha256, label="chain-state SHA-256"
    )
    expected_plan_state_sha256 = _guard_sha256(
        expected_plan_state_sha256, label="plan-state SHA-256"
    )
    expected_marker_sha256 = _guard_sha256(expected_marker_sha256, label="marker SHA-256")
    expected_binding_sha256 = _guard_sha256(
        expected_binding_sha256, label="project-source binding SHA-256"
    )
    spec_path, project_root = _assert_spec_and_paths(spec_path, project_root)
    marker_path = marker_path.expanduser().resolve(strict=False)
    state_path = chain_spec._state_path_for(spec_path)
    plan_dir = find_plan_dir(project_root, expected_current_plan)
    if plan_dir is None:
        raise _refuse("current plan directory is unavailable")
    plan_path = plan_dir / "state.json"
    try:
        from arnold_pipelines.megaplan.incident.chain_control import (
            _stable_id,
            apply_chain_lifecycle,
            chain_id_for_spec,
            journal_for,
            cas_chain_state_effect,
        )
        chain_id = chain_id_for_spec(spec_path)
        operation_id = _stable_id(
            "restart-current-attempt",
            chain_id,
            str(expected_state_revision),
            str(expected_cursor),
            expected_current_plan,
            expected_plan_state_sha256,
        )
    except Exception as exc:
        raise _refuse(f"could not establish restart operation identity: {exc}") from exc

    # A committed operation is the only path allowed to skip the normal guards.
    journal = journal_for(project_root)
    try:
        existing = journal.operation_result(operation_id)
    except Exception as exc:
        raise _refuse(f"could not inspect restart journal: {exc}") from exc
    if existing is not None and existing.get("event_kind") == "chain_control.committed":
        replay_result = apply_chain_lifecycle(
            spec_path,
            project_root,
            intent_kind="restart_current_attempt",
            actor={"id": actor, "class": "operator"},
            state_paths=[plan_path, marker_path],
            operation_id=operation_id,
            expected_revision=expected_state_revision,
            expected_cursor=expected_cursor,
        )
        payload = existing.get("payload") if isinstance(existing.get("payload"), Mapping) else {}
        effect = payload.get("effect") if isinstance(payload.get("effect"), Mapping) else {}
        return _receipt(
            outcome="replay",
            operation_id=operation_id,
            retired_plan=expected_current_plan,
            cursor=expected_cursor,
            milestone=expected_current_milestone,
            chain_state_sha256=str(effect.get("chain_state_sha256") or sha256_path(state_path)),
            plan_state_sha256=str(effect.get("plan_state_sha256") or sha256_path(plan_path)),
            event_hash=(replay_result.get("replay_event") or {}).get("event_hash"),
        )

    try:
        chain_raw, chain = _load_json_bytes(state_path, label="chain state")
        plan_raw, plan = _load_json_bytes(plan_path, label="plan state")
        marker_raw, marker = _load_json_bytes(marker_path, label="session marker")
        spec = chain_spec.load_spec(spec_path)
        _assert_snapshot(
            spec_path=spec_path,
            project_root=project_root,
            spec=spec,
            chain_raw=chain_raw,
            chain=chain,
            plan_raw=plan_raw,
            plan=plan,
            marker_raw=marker_raw,
            marker=marker,
            plan_dir=plan_dir,
            expected_session_id=expected_session_id,
            expected_cursor=expected_cursor,
            expected_current_milestone=expected_current_milestone,
            expected_current_plan=expected_current_plan,
            expected_spec_sha256=expected_spec_sha256,
            expected_chain_state_sha256=expected_chain_state_sha256,
            expected_plan_state_sha256=expected_plan_state_sha256,
            expected_state_revision=expected_state_revision,
            expected_marker_sha256=expected_marker_sha256,
            expected_binding_sha256=expected_binding_sha256,
            expected_source_head=expected_source_head,
            operation_id=operation_id,
        )
        source_guard = _source_guard(chain)
    except CliError as exc:
        if exc.code == "current_attempt_restart_refused":
            raise
        raise _refuse(str(exc)) from exc
    except Exception as exc:
        raise _refuse(f"could not read restart guards: {exc}") from exc

    def effect(txn: Any) -> dict[str, Any]:
        chain_raw_now, chain_now = _load_json_bytes(state_path, label="chain state")
        plan_raw_now, plan_now = _load_json_bytes(plan_path, label="plan state")
        marker_raw_now, marker_now = _load_json_bytes(marker_path, label="session marker")
        _assert_snapshot(
            spec_path=spec_path,
            project_root=project_root,
            spec=spec,
            chain_raw=chain_raw_now,
            chain=chain_now,
            plan_raw=plan_raw_now,
            plan=plan_now,
            marker_raw=marker_raw_now,
            marker=marker_now,
            plan_dir=plan_dir,
            expected_session_id=expected_session_id,
            expected_cursor=expected_cursor,
            expected_current_milestone=expected_current_milestone,
            expected_current_plan=expected_current_plan,
            expected_spec_sha256=expected_spec_sha256,
            expected_chain_state_sha256=expected_chain_state_sha256,
            expected_plan_state_sha256=expected_plan_state_sha256,
            expected_state_revision=expected_state_revision,
            expected_marker_sha256=expected_marker_sha256,
            expected_binding_sha256=expected_binding_sha256,
            expected_source_head=expected_source_head,
            operation_id=operation_id,
        )
        if not _matching_retirement(
            plan_now,
            operation_id=operation_id,
            expected_current_plan=expected_current_plan,
            expected_cursor=expected_cursor,
            expected_current_milestone=expected_current_milestone,
        ):
            retired = dict(plan_now)
            retired["current_state"] = "aborted"
            retired["active_step"] = None
            meta = dict(retired.get("meta") or {})
            meta["retirement"] = {
                "kind": "retired_for_restart",
                "retired_at": _now_z(),
                "actor": actor,
                "reason": reason,
                "cursor": expected_cursor,
                "milestone": expected_current_milestone,
                "operation_id": operation_id,
            }
            retired["meta"] = meta
            write_plan_state(plan_dir, mode="replace", state=retired)

        chain_metadata = chain_now.get("metadata") if isinstance(chain_now.get("metadata"), Mapping) else {}
        if _matching_restart_record(
            chain_metadata if isinstance(chain_metadata, Mapping) else {},
            operation_id=operation_id,
            expected_current_plan=expected_current_plan,
            expected_cursor=expected_cursor,
            expected_current_milestone=expected_current_milestone,
        ):
            return {
                "pre_state_digest": expected_chain_state_sha256,
                "post_state_digest": sha256_path(state_path),
                "actual_revision": (chain_now.get("metadata") or {}).get("_nbf08_revision"),
                "actual_cursor": expected_cursor,
                "retired_plan": expected_current_plan,
                "milestone": expected_current_milestone,
                "plan_state_sha256": sha256_path(plan_path),
                "chain_state_sha256": sha256_path(state_path),
            }

        next_chain = dict(chain_now)
        next_metadata = dict(next_chain.get("metadata") or {})
        next_metadata["current_attempt_restart"] = {
            "schema": RESTART_SCHEMA,
            "retired_plan": expected_current_plan,
            "cursor": expected_cursor,
            "milestone": expected_current_milestone,
            "reason": reason,
            "actor": actor,
            "operation_id": operation_id,
            "plan_state_sha256_before": expected_plan_state_sha256,
            "marker_sha256": expected_marker_sha256,
        }
        next_chain["metadata"] = next_metadata
        next_chain["current_plan_name"] = None
        chain_effect = cas_chain_state_effect(
            txn,
            spec_path,
            next_chain,
            expected_revision=expected_state_revision,
        )
        return {
            **chain_effect,
            "retired_plan": expected_current_plan,
            "milestone": expected_current_milestone,
            "plan_state_sha256": sha256_path(plan_path),
            "chain_state_sha256": sha256_path(state_path),
            "restart_guard": {
                "schema": "arnold.megaplan.current-attempt-restart-guard.v1",
                "session_id": expected_session_id,
                "spec_sha256": expected_spec_sha256,
                "chain_state_sha256_before": expected_chain_state_sha256,
                "plan_state_sha256_before": expected_plan_state_sha256,
                "marker_sha256": expected_marker_sha256,
                "state_revision_before": expected_state_revision,
                "cursor": expected_cursor,
                "milestone": expected_current_milestone,
                "retired_plan": expected_current_plan,
                "source_binding_sha256": expected_binding_sha256,
                "pre_state_digest": chain_effect.get("pre_state_digest"),
                "post_state_digest": chain_effect.get("post_state_digest"),
                "chain_state_sha256_after": sha256_path(state_path),
                "plan_state_sha256_after": sha256_path(plan_path),
                **source_guard,
            },
        }

    result = apply_chain_lifecycle(
        spec_path,
        project_root,
        intent_kind="restart_current_attempt",
        state_paths=[plan_path, marker_path],
        actor={"id": actor, "class": "operator"},
        operation_id=operation_id,
        expected_revision=expected_state_revision,
        expected_cursor=expected_cursor,
        effect=effect,
        intent_context={
            "retired_plan": expected_current_plan,
            "milestone": expected_current_milestone,
            "reason": reason,
        },
    )
    if result.get("outcome") == "cas_conflict":
        error = result.get("error")
        raise _refuse(str(error or "restart guards changed under the transaction lock"))
    if result.get("outcome") != "committed":
        error = result.get("error")
        if isinstance(error, Exception):
            raise _refuse(str(error)) from error
        raise _refuse(f"restart did not commit: {result.get('outcome')}")
    effect_result = result.get("effect") if isinstance(result.get("effect"), Mapping) else {}
    return _receipt(
        outcome="committed",
        operation_id=operation_id,
        retired_plan=expected_current_plan,
        cursor=expected_cursor,
        milestone=expected_current_milestone,
        chain_state_sha256=str(effect_result.get("chain_state_sha256") or sha256_path(state_path)),
        plan_state_sha256=str(effect_result.get("plan_state_sha256") or sha256_path(plan_path)),
        event_hash=_event_hash(project_root, operation_id),
    )


def _full_sha256(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise _refuse(f"{label} must be a full SHA-256")
    return normalized


def _archive_manifest_value(manifest: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in manifest:
            return manifest[name]
    files = manifest.get("files")
    if isinstance(files, list):
        for row in files:
            if not isinstance(row, Mapping):
                continue
            path = str(row.get("path") or row.get("name") or "")
            if path.endswith("events.jsonl"):
                for name in names:
                    if name in row:
                        return row[name]
    return None


def _archive_journal(
    events_path: Path,
    *,
    expected_events_sha256: str,
    manifest_path: Path,
    expected_manifest_sha256: str,
    expected_operation_id: str,
    expected_event_hash: str,
    expected_chain_id: str,
    expected_physical_sequence_start: int | None = None,
) -> dict[str, Any]:
    """Read an immutable legacy journal without treating it as live authority.

    Archived journals often live below a different directory than the live
    ledger.  The envelope's original ledger id is therefore used for replay;
    the archive path is never made writable or installed as the live ledger.
    """
    events_path = events_path.expanduser().resolve(strict=False)
    manifest_path = manifest_path.expanduser().resolve(strict=False)
    events_sha = _full_sha256(expected_events_sha256, label="archived journal SHA-256")
    manifest_sha = _full_sha256(expected_manifest_sha256, label="archive manifest SHA-256")
    if not events_path.is_file():
        raise _refuse("archived restart journal is unavailable")
    if not manifest_path.is_file():
        raise _refuse("archive manifest is unavailable")
    if hashlib.sha256(events_path.read_bytes()).hexdigest() != events_sha:
        raise _refuse("archived restart journal SHA-256 does not match")
    manifest_raw = manifest_path.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != manifest_sha:
        raise _refuse("archive manifest SHA-256 does not match")
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _refuse("archive manifest is not valid JSON") from exc
    if not isinstance(manifest, Mapping):
        raise _refuse("archive manifest must be a JSON object")
    bound_events_sha = _archive_manifest_value(
        manifest,
        ("events_sha256", "journal_sha256", "archive_journal_sha256", "events_digest"),
    )
    if str(bound_events_sha or "").strip().lower() != events_sha:
        raise _refuse("archive manifest does not bind the supplied journal")
    bound_path = _archive_manifest_value(manifest, ("events_path", "journal_path", "archive_journal_path"))
    if bound_path is not None and Path(str(bound_path)).name != events_path.name:
        raise _refuse("archive manifest names a different journal")
    for value, label in (
        (expected_operation_id, "legacy restart operation id"),
        (expected_event_hash, "legacy committed event hash"),
    ):
        _full_sha256(value, label=label)

    # Build a read-only replay facade over the supplied file.  Replaying with
    # its original ledger id verifies the physical and evidence hash chains;
    # no archive-side sequence or event file is changed.
    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlJournal,
        ChainControlHold,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    archive_root = events_path.parent.parent if events_path.parent.name == "incident-ledger" else events_path.parent
    ledger = IncidentLedger(archive_root)
    ledger._ledger_dir = events_path.parent
    ledger._journal._ndjson_path = events_path
    ledger._journal._seq_path = events_path.parent / ".events.seq"
    original_ledger_id = next(
        (
            item.record.get("payload", {}).get("ledger_id")
            for item in __import__("arnold_pipelines.megaplan.incident.chain_control", fromlist=["read_physical_lines"]).read_physical_lines(events_path)
            if not item.torn
            and isinstance(item.record.get("payload"), Mapping)
            and str(item.record.get("kind") or "").startswith("chain_control.")
            and item.record.get("payload", {}).get("ledger_id")
        ),
        None,
    )
    if not isinstance(original_ledger_id, str) or not original_ledger_id.strip():
        raise _refuse("archived journal has no original ledger identity")
    manifest_ledger_id = manifest.get("ledger_id")
    if manifest_ledger_id is not None and manifest_ledger_id != original_ledger_id:
        raise _refuse("archive manifest ledger identity does not match the journal")
    archive_journal = ChainControlJournal(ledger)
    archive_journal.ledger_id = original_ledger_id
    try:
        replay = archive_journal.replay_strict()
    except ChainControlHold as exc:
        raise _refuse(f"archived journal strict replay failed: {exc}") from exc
    events = [
        event
        for event in replay.get("accepted", [])
        if event.get("chain_id") == expected_chain_id
        and event.get("operation_id") == expected_operation_id
    ]
    kinds = [str(event.get("event_kind") or "") for event in events]
    expected_kinds = [
        "chain_control.intent",
        "chain_control.authority_validated",
        "chain_control.claimed",
        "chain_control.committed",
    ]
    if kinds != expected_kinds:
        raise _refuse("archived restart operation must have one intent, authority, claim, and commit")
    if len({event.get("event_id") for event in events}) != 4:
        raise _refuse("archived restart operation contains duplicate event identities")
    physical = [event.get("physical_sequence") for event in events]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in physical):
        raise _refuse("archived restart operation has malformed physical sequence")
    if physical != list(range(physical[0], physical[0] + 4)):
        raise _refuse("archived restart operation is not a contiguous physical sequence")
    if expected_physical_sequence_start is not None and physical[0] != expected_physical_sequence_start:
        raise _refuse("archived restart operation physical sequence does not match the guard")
    committed = events[-1]
    if committed.get("event_hash") != str(expected_event_hash).strip().lower():
        raise _refuse("archived restart committed event hash does not match")
    payload = committed.get("payload")
    effect = payload.get("effect") if isinstance(payload, Mapping) else None
    if not isinstance(payload, Mapping) or payload.get("intent_kind") != "restart_current_attempt" or not isinstance(effect, Mapping):
        raise _refuse("archived restart committed effect is malformed")
    guard = effect.get("restart_guard")
    if not isinstance(guard, Mapping):
        raise _refuse("archived restart committed effect lacks its restart guard")
    return {
        "manifest": dict(manifest),
        "manifest_sha256": manifest_sha,
        "events_sha256": events_sha,
        "journal_path": str(events_path),
        "manifest_path": str(manifest_path),
        "ledger_id": original_ledger_id,
        "events": events,
        "committed": committed,
        "effect": dict(effect),
        "guard": dict(guard),
        "physical_sequence": physical,
    }


def _committed_event(journal: Any, operation_id: str, event_kind: str) -> dict[str, Any] | None:
    """Return the terminal event for an operation, not its initial intent.

    ``ChainControlJournal.operation_result`` intentionally exposes the first
    operation envelope for replay-key validation.  A custom committed event
    therefore cannot be found through that helper alone; legacy attestation
    replay needs the actual terminal event kind.
    """
    replay = journal.replay_strict()
    for event in reversed(replay.get("accepted") or []):
        if event.get("operation_id") == operation_id and event.get("event_kind") == event_kind:
            return event
    return None


def _assert_legacy_projection(
    *,
    spec_path: Path,
    project_root: Path,
    marker_path: Path,
    state_path: Path,
    plan_path: Path,
    expected_session_id: str,
    expected_cursor: int,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    expected_state_revision: int,
    expected_marker_sha256: str,
    expected_binding_sha256: str,
    expected_source_head: str,
    operation_id: str,
) -> tuple[bytes, dict[str, Any], bytes, dict[str, Any], bytes, dict[str, Any], dict[str, Any]]:
    chain_raw, chain = _load_json_bytes(state_path, label="chain state")
    plan_raw, plan = _load_json_bytes(plan_path, label="retired plan state")
    marker_raw, marker = _load_json_bytes(marker_path, label="session marker")
    expected_spec_sha256 = _full_sha256(expected_spec_sha256, label="spec SHA-256")
    expected_chain_state_sha256 = _full_sha256(expected_chain_state_sha256, label="chain-state SHA-256")
    expected_plan_state_sha256 = _full_sha256(expected_plan_state_sha256, label="plan-state SHA-256")
    expected_marker_sha256 = _full_sha256(expected_marker_sha256, label="marker SHA-256")
    expected_binding_sha256 = _full_sha256(expected_binding_sha256, label="project-source binding SHA-256")
    if hashlib.sha256(chain_raw).hexdigest() != expected_chain_state_sha256:
        raise _conflict("chain state changed since the legacy restart guards were computed")
    if hashlib.sha256(plan_raw).hexdigest() != expected_plan_state_sha256:
        raise _conflict("retired plan state changed since the legacy restart guards were computed")
    if hashlib.sha256(marker_raw).hexdigest() != expected_marker_sha256:
        raise _conflict("session marker changed since the legacy restart guards were computed")
    if sha256_path(spec_path) != expected_spec_sha256:
        raise _conflict("chain spec changed since the legacy restart guards were computed")
    if project_root.name != expected_session_id or marker.get("session") != expected_session_id:
        raise _refuse("legacy restart session identity does not match")
    if marker.get("should_run") is not False or _marker_occupied(marker) is not None:
        raise _refuse("legacy restart promotion requires a paused, unoccupied session marker")
    if not isinstance(chain.get("metadata"), Mapping):
        raise _refuse("chain metadata is missing")
    metadata = chain["metadata"]
    if chain.get("last_state") != "paused" or chain.get("current_plan_name") is not None:
        raise _refuse("legacy restart promotion requires the paused retired-plan boundary")
    if chain.get("current_milestone_index") != expected_cursor:
        raise _conflict("chain cursor does not match the legacy restart guard")
    revision = metadata.get("_nbf08_revision")
    if isinstance(revision, bool) or revision != expected_state_revision:
        raise _conflict("chain state revision does not match the legacy restart guard")
    pause = metadata.get(AUTHORITY_KEY)
    if not (isinstance(pause, Mapping) and pause.get("active") is True and pause.get("schema_version") == AUTHORITY_SCHEMA):
        raise _refuse("legacy restart promotion requires an active durable operator pause")
    restart = metadata.get("current_attempt_restart")
    if not (isinstance(restart, Mapping) and restart.get("schema") == RESTART_SCHEMA and restart.get("operation_id") == operation_id and restart.get("retired_plan") == expected_current_plan and restart.get("cursor") == expected_cursor and restart.get("milestone") == expected_current_milestone):
        raise _refuse("current attempt restart projection does not match the legacy operation")
    if "legacy_attestation" in restart:
        raise _refuse("legacy restart operation has already been attested")
    if plan.get("name") not in {None, expected_current_plan} or str(plan.get("current_state") or "").lower() not in {"aborted", "cancelled"} or plan.get("active_step") is not None:
        raise _refuse("retired plan state is not a terminal inactive restart projection")
    retirement = (plan.get("meta") or {}).get("retirement") if isinstance(plan.get("meta"), Mapping) else None
    if not (isinstance(retirement, Mapping) and retirement.get("kind") == "retired_for_restart" and retirement.get("operation_id") == operation_id and retirement.get("cursor") == expected_cursor and retirement.get("milestone") == expected_current_milestone):
        raise _refuse("retired plan metadata does not match the legacy operation")
    binding = metadata.get("project_source_binding")
    if not isinstance(binding, Mapping) or _binding_digest(binding) != expected_binding_sha256:
        raise _conflict("project-source binding changed since the legacy restart guards were computed")
    current = binding.get("current")
    if not isinstance(current, Mapping) or str(current.get("head") or "").lower() != expected_source_head.lower():
        raise _conflict("project-source head does not match the legacy restart guard")
    if _current_head(project_root) != expected_source_head.lower():
        raise _conflict("checked-out source HEAD does not match the legacy restart guard")
    try:
        from arnold_pipelines.megaplan.chain import spec as chain_spec
        spec = chain_spec.load_spec(spec_path)
    except Exception as exc:
        raise _refuse(f"could not load legacy restart spec: {exc}") from exc
    if not (0 <= expected_cursor < len(spec.milestones)) or spec.milestones[expected_cursor].label != expected_current_milestone:
        raise _refuse("legacy restart milestone does not match the frozen spec")
    return chain_raw, dict(chain), plan_raw, dict(plan), marker_raw, dict(marker), dict(binding)


def promote_legacy_restart_receipt(
    spec_path: Path,
    project_root: Path,
    *,
    marker_path: Path,
    expected_session_id: str,
    expected_cursor: int,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    expected_state_revision: int,
    expected_marker_sha256: str,
    expected_binding_sha256: str,
    expected_source_head: str,
    expected_operation_id: str,
    archived_journal_path: Path,
    expected_archived_journal_sha256: str,
    archive_manifest_path: Path,
    expected_archive_manifest_sha256: str,
    expected_legacy_event_hash: str,
    reason: str,
    actor: str = "operator",
    expected_state_digest: str | None = None,
    expected_physical_sequence_start: int | None = None,
) -> dict[str, Any]:
    """Promote one archived restart receipt into the live chain boundary.

    This operation is deliberately distinct from ``restart_current_attempt``:
    it never touches the retired plan's artifacts and never reruns the old
    attempt.  It only adds a canonical, content-addressed attestation and
    advances the chain revision by exactly one.
    """
    spec_path, project_root = _assert_spec_and_paths(spec_path, project_root)
    marker_path = marker_path.expanduser().resolve(strict=False)
    state_path = chain_spec._state_path_for(spec_path)
    plan_dir = find_plan_dir(project_root, expected_current_plan)
    if plan_dir is None:
        raise _refuse("retired plan directory is unavailable")
    plan_path = plan_dir / "state.json"
    expected_operation_id = _full_sha256(expected_operation_id, label="legacy restart operation id")
    expected_legacy_event_hash = _full_sha256(expected_legacy_event_hash, label="legacy committed event hash")
    expected_source_head = _require_text(expected_source_head, "expected source head").lower()
    if _FULL_SHA.fullmatch(expected_source_head) is None:
        raise _refuse("expected source head must be a full Git SHA")
    if isinstance(expected_state_revision, bool) or not isinstance(expected_state_revision, int) or expected_state_revision < 1:
        raise _refuse("expected state revision must be a positive integer")
    if expected_state_digest is not None:
        _full_sha256(expected_state_digest, label="state digest")
    from arnold_pipelines.megaplan.incident.chain_control import (
        _stable_id,
        apply_chain_lifecycle,
        chain_id_for_spec,
        cas_chain_state_effect,
    )
    chain_id = chain_id_for_spec(spec_path)
    archive = _archive_journal(
        archived_journal_path,
        expected_events_sha256=expected_archived_journal_sha256,
        manifest_path=archive_manifest_path,
        expected_manifest_sha256=expected_archive_manifest_sha256,
        expected_operation_id=expected_operation_id,
        expected_event_hash=expected_legacy_event_hash,
        expected_chain_id=chain_id,
        expected_physical_sequence_start=expected_physical_sequence_start,
    )
    new_operation_id = _stable_id(
        "legacy-restart-receipt-attestation",
        chain_id,
        expected_operation_id,
        expected_legacy_event_hash,
        archive["events_sha256"],
        archive["manifest_sha256"],
    )
    journal = __import__("arnold_pipelines.megaplan.incident.chain_control", fromlist=["journal_for"]).journal_for(project_root)
    # A committed attestation is the only permitted fast path.  Revalidate
    # its immutable identity and revision, then append only the normal
    # chain-control replay evidence; never run the promotion effect again.
    try:
        existing_chain_raw, existing_chain = _load_json_bytes(state_path, label="chain state")
        existing_restart = (existing_chain.get("metadata") or {}).get("current_attempt_restart") if isinstance(existing_chain.get("metadata"), Mapping) else None
        existing_attestation = existing_restart.get("legacy_attestation") if isinstance(existing_restart, Mapping) else None
        if (
            isinstance(existing_attestation, Mapping)
            and existing_attestation.get("operation_id") == new_operation_id
            and existing_attestation.get("legacy_operation_id") == expected_operation_id
            and existing_attestation.get("legacy_event_hash") == expected_legacy_event_hash
            and existing_attestation.get("archive_journal", {}).get("sha256") == archive["events_sha256"]
            and existing_attestation.get("archive_manifest", {}).get("sha256") == archive["manifest_sha256"]
            and (existing_chain.get("metadata") or {}).get("_nbf08_revision") == expected_state_revision
        ):
            existing = _committed_event(journal, new_operation_id, LEGACY_ATTESTATION_EVENT_KIND)
            if existing is not None:
                result = apply_chain_lifecycle(
                    spec_path, project_root, intent_kind=LEGACY_ATTESTATION_INTENT,
                    actor={"id": actor, "class": "operator"}, operation_id=new_operation_id,
                    # Replay keys are bound to the revision at which the
                    # attestation was committed.  The live projection is one
                    # revision newer, but replay is evidence-only and must not
                    # attempt a second state CAS.
                    expected_revision=existing.get("expected_revision"), expected_cursor=expected_cursor,
                    state_paths=[plan_path, marker_path],
                )
                return {"outcome": "replay", "operation_id": new_operation_id, "event_hash": (result.get("replay_event") or {}).get("event_hash"), "legacy_operation_id": expected_operation_id, "legacy_event_hash": expected_legacy_event_hash}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    chain_raw, chain, plan_raw, plan, marker_raw, marker, binding = _assert_legacy_projection(
        spec_path=spec_path,
        project_root=project_root,
        marker_path=marker_path,
        state_path=state_path,
        plan_path=plan_path,
        expected_session_id=expected_session_id,
        expected_cursor=expected_cursor,
        expected_current_milestone=expected_current_milestone,
        expected_current_plan=expected_current_plan,
        expected_spec_sha256=expected_spec_sha256,
        expected_chain_state_sha256=expected_chain_state_sha256,
        expected_plan_state_sha256=expected_plan_state_sha256,
        expected_state_revision=expected_state_revision,
        expected_marker_sha256=expected_marker_sha256,
        expected_binding_sha256=expected_binding_sha256,
        expected_source_head=expected_source_head,
        operation_id=expected_operation_id,
    )
    if expected_state_digest is not None:
        from arnold_pipelines.megaplan.incident.chain_control import state_digest_for
        if state_digest_for(chain) != expected_state_digest:
            raise _conflict("chain state digest does not match the legacy restart guard")
    legacy_guard = archive["guard"]
    if legacy_guard.get("state_revision_before") != expected_state_revision - 1 or legacy_guard.get("actual_revision") not in {None, expected_state_revision}:
        # Older receipts put the actual revision on the envelope, not guard;
        # the envelope is checked below as the authoritative value.
        if archive["committed"].get("expected_revision") != expected_state_revision - 1 or archive["committed"].get("actual_revision") != expected_state_revision:
            raise _refuse("archived restart revision evidence does not match the live revision")
    if archive["committed"].get("expected_revision") != expected_state_revision - 1 or archive["committed"].get("actual_revision") != expected_state_revision:
        raise _refuse("archived restart revision evidence does not match the live revision")
    for key, expected in (("cursor", expected_cursor), ("milestone", expected_current_milestone), ("retired_plan", expected_current_plan)):
        if legacy_guard.get(key) != expected:
            raise _refuse(f"archived restart guard {key} does not match the live projection")
    if legacy_guard.get("source", {}).get("head") != expected_source_head:
        raise _refuse("archived restart source head does not match the live projection")
    if legacy_guard.get("source_binding") != binding:
        raise _refuse("archived restart source binding does not match the live projection")
    if legacy_guard.get("execution_binding") != chain.get("metadata", {}).get("execution_binding"):
        raise _refuse("archived restart execution binding does not match the live projection")
    if legacy_guard.get("chain_state_sha256_after") not in {None, expected_chain_state_sha256} or legacy_guard.get("plan_state_sha256_after") not in {None, expected_plan_state_sha256}:
        raise _refuse("archived restart post-state hashes do not match the live projection")
    existing = _committed_event(journal, new_operation_id, LEGACY_ATTESTATION_EVENT_KIND)
    if existing is not None:
        result = apply_chain_lifecycle(
            spec_path,
            project_root,
            intent_kind=LEGACY_ATTESTATION_INTENT,
            actor={"id": actor, "class": "operator"},
            operation_id=new_operation_id,
            expected_revision=existing.get("expected_revision"),
            expected_cursor=expected_cursor,
            state_paths=[plan_path, marker_path],
        )
        return {"outcome": "replay", "operation_id": new_operation_id, "event_hash": (result.get("replay_event") or {}).get("event_hash"), "legacy_operation_id": expected_operation_id, "legacy_event_hash": expected_legacy_event_hash}

    def effect(txn: Any) -> dict[str, Any]:
        current_raw, current = _load_json_bytes(state_path, label="chain state")
        _, current_plan = _load_json_bytes(plan_path, label="retired plan state")
        _, current_marker = _load_json_bytes(marker_path, label="session marker")
        _assert_legacy_projection(
            spec_path=spec_path, project_root=project_root, marker_path=marker_path,
            state_path=state_path, plan_path=plan_path,
            expected_session_id=expected_session_id, expected_cursor=expected_cursor,
            expected_current_milestone=expected_current_milestone, expected_current_plan=expected_current_plan,
            expected_spec_sha256=expected_spec_sha256, expected_chain_state_sha256=expected_chain_state_sha256,
            expected_plan_state_sha256=expected_plan_state_sha256, expected_state_revision=expected_state_revision,
            expected_marker_sha256=expected_marker_sha256, expected_binding_sha256=expected_binding_sha256,
            expected_source_head=expected_source_head, operation_id=expected_operation_id,
        )
        if expected_state_digest is not None:
            from arnold_pipelines.megaplan.incident.chain_control import state_digest_for
            if state_digest_for(current) != expected_state_digest:
                raise _conflict("chain state digest changed under the attestation lock")
        current_digest = __import__("arnold_pipelines.megaplan.incident.chain_control", fromlist=["state_digest_for"]).state_digest_for(current)
        next_chain = dict(current)
        next_metadata = dict(next_chain.get("metadata") or {})
        next_revision = expected_state_revision + 1
        # Compute the exact JSON bytes ChainStateAdapter will write so the
        # modern guard is content-addressed before the CAS happens.
        next_restart = dict(next_metadata["current_attempt_restart"])
        modern_guard = dict(legacy_guard)
        modern_guard.update({
            "attestation_operation_id": new_operation_id,
            "attested_state_revision_before": expected_state_revision,
            "attested_state_revision_after": next_revision,
            "attestation_pre_state_digest": current_digest,
            "attestation_spec_sha256": _full_sha256(expected_spec_sha256, label="spec SHA-256"),
        })
        attestation = {
            "schema": LEGACY_ATTESTATION_SCHEMA,
            "operation_id": new_operation_id,
            "legacy_operation_id": expected_operation_id,
            "legacy_event_hash": expected_legacy_event_hash,
            "archive_journal": {"path": archive["journal_path"], "sha256": archive["events_sha256"], "physical_sequence": archive["physical_sequence"]},
            "archive_manifest": {"path": archive["manifest_path"], "sha256": archive["manifest_sha256"]},
            "cursor": expected_cursor,
            "milestone": expected_current_milestone,
            "retired_plan": expected_current_plan,
            "restart_guard": modern_guard,
            "legacy_restart_guard": legacy_guard,
            "reason": reason,
            "actor": actor,
        }
        next_restart["legacy_attestation"] = attestation
        next_restart["restart_guard"] = modern_guard
        next_metadata["current_attempt_restart"] = next_restart
        next_chain["metadata"] = next_metadata
        next_chain["current_plan_name"] = None
        next_chain["metadata"]["_nbf08_revision"] = next_revision
        modern_guard["attestation_chain_state_sha256_before"] = hashlib.sha256(current_raw).hexdigest()
        chain_effect = cas_chain_state_effect(txn, spec_path, next_chain, expected_revision=expected_state_revision)
        return {
            **chain_effect,
            "actual_revision": next_revision,
            "actual_cursor": expected_cursor,
            "legacy_operation_id": expected_operation_id,
            "legacy_event_hash": expected_legacy_event_hash,
            "archive_journal": {"path": archive["journal_path"], "sha256": archive["events_sha256"], "physical_sequence": archive["physical_sequence"]},
            "archive_manifest": {"path": archive["manifest_path"], "sha256": archive["manifest_sha256"]},
            "restart_guard": modern_guard,
            "legacy_restart_guard": legacy_guard,
            "chain_state_sha256": sha256_path(state_path),
            "plan_state_sha256": sha256_path(plan_path),
            "attestation_operation_id": new_operation_id,
        }

    result = apply_chain_lifecycle(
        spec_path, project_root, intent_kind=LEGACY_ATTESTATION_INTENT,
        actor={"id": actor, "class": "operator"}, operation_id=new_operation_id,
        expected_revision=expected_state_revision, expected_cursor=expected_cursor,
        state_paths=[plan_path, marker_path], effect=effect,
        committed_event_kind=LEGACY_ATTESTATION_EVENT_KIND,
        linked_receipts=[archive["journal_path"], archive["manifest_path"]],
        intent_context={"legacy_operation_id": expected_operation_id, "legacy_event_hash": expected_legacy_event_hash},
    )
    if result.get("outcome") != "committed":
        error = result.get("error")
        if isinstance(error, Exception):
            raise _refuse(str(error)) from error
        raise _refuse(f"legacy restart attestation did not commit: {result.get('outcome')}")
    event = result.get("event") if isinstance(result.get("event"), Mapping) else {}
    return {"outcome": "committed", "operation_id": new_operation_id, "legacy_operation_id": expected_operation_id, "legacy_event_hash": expected_legacy_event_hash, "event_hash": event.get("event_hash"), "effect": result.get("effect")}


__all__ = [
    "RESTART_ERROR", "RESTART_SCHEMA", "LEGACY_ATTESTATION_SCHEMA",
    "LEGACY_ATTESTATION_INTENT", "LEGACY_ATTESTATION_EVENT_KIND",
    "restart_current_attempt", "promote_legacy_restart_receipt",
]
