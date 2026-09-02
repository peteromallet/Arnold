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


def _assert_spec_and_paths(spec_path: Path, project_root: Path) -> tuple[Path, Path]:
    spec_path = spec_path.expanduser().resolve(strict=False)
    project_root = project_root.expanduser().resolve(strict=False)
    try:
        spec_path.relative_to(project_root)
    except ValueError as exc:
        raise _refuse("chain spec must be inside the guarded project/session root") from exc
    if project_root.name != _require_text(project_root.name, "session"):
        raise _refuse("project session root has no name")
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
    if hashlib.sha256(chain_raw).hexdigest() != chain_hash:
        raise _conflict("chain state changed since the restart guards were computed")
    if hashlib.sha256(plan_raw).hexdigest() != plan_hash:
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

    metadata = chain.get("metadata")
    if not isinstance(metadata, Mapping):
        raise _refuse("chain metadata is missing")
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
    if isinstance(revision, bool) or revision != expected_state_revision:
        raise _conflict(
            f"chain state revision does not match the guard: observed {revision!r}, expected {expected_state_revision}"
        )
    cursor = chain.get("current_milestone_index")
    if cursor != expected_cursor:
        raise _conflict(
            f"current milestone cursor does not match the guard: observed {cursor!r}, expected {expected_cursor}"
        )
    if chain.get("current_plan_name") != expected_current_plan:
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
    if restart is not None:
        raise _refuse("chain already carries a different current-attempt restart record")

    current_state = str(plan.get("current_state") or "").strip().lower()
    if current_state in {"done", "aborted", "cancelled"}:
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


__all__ = ["RESTART_ERROR", "RESTART_SCHEMA", "restart_current_attempt"]
