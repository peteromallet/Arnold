"""Guarded project-source cutover for an already materialized chain milestone.

Runtime and chain-spec bindings deliberately do not move the Git checkout that
an existing plan will mutate.  This module supplies that missing boundary.  It
is intentionally limited to a durable operator pause before execute and keeps
the launch-time chain target/base identity immutable.
"""

from __future__ import annotations

import fcntl
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, NoReturn

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import driver_lock, plan_lock
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.git_ops import _reference_census
from arnold_pipelines.megaplan.chain.operator_pause import (
    AUTHORITY_KEY,
    AUTHORITY_SCHEMA,
)
from arnold_pipelines.megaplan.cloud.operator_control import RESUME_HOLD_SCHEMA
from arnold_pipelines.megaplan.types import CliError

PROJECT_SOURCE_BINDING_SCHEMA = "arnold.megaplan.project_source_binding.v1"
PROJECT_SOURCE_REBIND_SCHEMA = "arnold.megaplan.project_source_rebind.v1"
PROJECT_SOURCE_REBIND_ERROR = "project_source_rebind_refused"

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_FULL_SHA256 = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_REF_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_PRE_EXECUTION_FORBIDDEN_STEPS = frozenset({"execute", "finalize", "review"})
_PRE_EXECUTION_FORBIDDEN_ARTIFACT_PATTERNS = (
    "execution.json",
    "execution_batch*.json",
    "finalize.json",
    "finalize_output.json",
    "finalize_snapshot.json",
    "review.json",
    "review_v*.json",
)
_STALE_GATE_ARTIFACT_PATTERNS = (
    "gate.json",
    "gate_signals.json",
    "gate_signals_v*.json",
    "phase_result.json",
)
_RESTART_GUARD_SCHEMA = "arnold.megaplan.current-attempt-restart-guard.v1"
_FULL_SHA256_RAW = re.compile(r"^[0-9a-f]{64}$")


def sha256_path(path: Path) -> str:
    """Return the lowercase raw SHA-256 for *path*."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _guard_sha256(value: str, *, label: str) -> str:
    match = _FULL_SHA256.fullmatch(str(value or "").strip().lower())
    if match is None:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{label} must be a full SHA-256",
        )
    return match.group(1)


def _guard_git_sha(value: str, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if _FULL_SHA.fullmatch(normalized) is None:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{label} must be a full 40-character Git SHA",
        )
    return normalized


def _guard_ref(value: str, *, label: str) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith("refs/heads/"):
        short = normalized.removeprefix("refs/heads/")
    else:
        short = normalized
        normalized = f"refs/heads/{short}"
    if (
        not short
        or _REF_NAME.fullmatch(short) is None
        or ".." in short
        or short.endswith(".")
        or short.endswith("/")
        or "@{" in short
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{label} is not a safe branch ref")
    return normalized


def _guard_branch(value: str, *, label: str) -> str:
    normalized_ref = _guard_ref(value, label=label)
    branch = normalized_ref.removeprefix("refs/heads/")
    if (
        value != branch
        or branch.endswith(".lock")
        or branch.startswith(".")
        or "/." in branch
        or "//" in branch
        or "\\" in branch
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{label} is not a safe local branch")
    return branch


def _run_git(
    root: Path,
    args: list[str],
    *,
    check: bool = True,
    error: str,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if check and process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{error}: {detail or f'git exited {process.returncode}'}",
            extra={
                "git_args": args,
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            },
        )
    return process


def _git_text(root: Path, args: list[str], *, error: str) -> str:
    return _run_git(root, args, error=error).stdout.strip()


def _remote_advertised_sha(root: Path, ref: str) -> str:
    result = _run_git(
        root,
        ["ls-remote", "--exit-code", "--heads", "origin", ref],
        error=f"could not verify advertised ref {ref}",
    )
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    exact = [row for row in rows if len(row) == 2 and row[1] == ref]
    if len(exact) != 1 or _FULL_SHA.fullmatch(exact[0][0].lower()) is None:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"advertised ref {ref} did not resolve to exactly one full SHA",
        )
    return exact[0][0].lower()


def _fetch_advertised_ref(root: Path, ref: str, expected_sha: str) -> None:
    _run_git(
        root,
        ["fetch", "--no-tags", "--no-write-fetch-head", "origin", ref],
        error=f"could not fetch advertised ref {ref}",
    )
    observed = _run_git(
        root,
        ["cat-file", "-e", f"{expected_sha}^{{commit}}"],
        check=False,
        error=f"could not resolve fetched commit {expected_sha}",
    )
    if observed.returncode != 0:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"advertised target {expected_sha} was not fetched as a commit",
        )


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = _run_git(
        root,
        ["merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        error="could not compare source ancestry",
    )
    if result.returncode not in {0, 1}:
        detail = (result.stderr or result.stdout or "").strip()
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"could not compare source ancestry: {detail}",
        )
    return result.returncode == 0


def _current_branch(root: Path) -> str:
    branch = _git_text(root, ["branch", "--show-current"], error="could not read current branch")
    if not branch:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "detached HEAD cannot be target-rebound")
    return branch


def _current_head(root: Path) -> str:
    return _git_text(root, ["rev-parse", "HEAD"], error="could not read current HEAD").lower()


def _assert_clean_worktree(root: Path) -> None:
    dirty = _git_text(
        root,
        ["status", "--porcelain=v1", "--untracked-files=normal"],
        error="could not inspect worktree",
    )
    if dirty:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "project worktree is dirty; target rebind requires a clean checkout",
            extra={"dirty_status": dirty.splitlines()},
        )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.target-rebind-",
        dir=str(path.parent),
    )
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(payload), indent=2) + "\n").encode("utf-8")


@contextmanager
def _transaction_lock(state_path: Path) -> Iterator[None]:
    lock_path = state_path.with_suffix(".target-rebind.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"another target rebind holds {lock_path}",
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_json_bytes(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"could not read {label} at {path}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{label} must be a JSON object")
    return raw, payload


def _assert_hash(raw: bytes, expected: str, *, label: str) -> None:
    expected_hash = _guard_sha256(expected, label=label)
    observed = hashlib.sha256(raw).hexdigest()
    if observed != expected_hash:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{label} changed: observed {observed}, expected {expected_hash}",
        )


def _assert_pre_execute(plan_dir: Path, plan: Mapping[str, Any]) -> None:
    if plan.get("active_step") is not None:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "plan has an active step")
    history = plan.get("history")
    for entry in history if isinstance(history, list) else []:
        if not isinstance(entry, Mapping):
            continue
        step = str(entry.get("step") or "").strip().lower()
        if step in _PRE_EXECUTION_FORBIDDEN_STEPS:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"plan already has {step} history; target rebind is pre-execute only",
            )
    for pattern in _PRE_EXECUTION_FORBIDDEN_ARTIFACT_PATTERNS:
        matches = sorted(path.name for path in plan_dir.glob(pattern) if path.is_file())
        if matches:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "plan already has execution/finalize/review artifacts",
                extra={"artifacts": matches},
            )


def _assert_pause(
    chain: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    expected_plan: str,
) -> None:
    metadata = chain.get("metadata")
    chain_pause = metadata.get(AUTHORITY_KEY) if isinstance(metadata, Mapping) else None
    plan_meta = plan.get("meta")
    plan_pause = plan_meta.get(AUTHORITY_KEY) if isinstance(plan_meta, Mapping) else None
    if not (
        isinstance(chain_pause, Mapping)
        and chain_pause.get("active") is True
        and chain_pause.get("schema_version") == AUTHORITY_SCHEMA
        and chain_pause.get("plan") == expected_plan
        and chain.get("last_state") == "paused"
        and plan.get("current_state") == "paused"
        and isinstance(plan_pause, Mapping)
        and plan_pause.get("schema_version") == AUTHORITY_SCHEMA
    ):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "target rebind requires matching durable chain and plan operator-pause authority",
        )
def _milestone(
    spec: Any,
    chain: Mapping[str, Any],
    *,
    expected_label: str,
) -> tuple[int, Any]:
    index = chain.get("current_milestone_index")
    if not isinstance(index, int) or index < 0 or index >= len(spec.milestones):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "current milestone index is invalid")
    milestone = spec.milestones[index]
    if milestone.label != expected_label:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"current milestone {milestone.label!r} does not match {expected_label!r}",
        )
    return index, milestone


def _binding_digest(binding: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            binding,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _require_restart_sha(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if _FULL_SHA256_RAW.fullmatch(normalized) is None:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"restart custody {label} must be a full SHA-256",
        )
    return normalized


def _assert_restart_receipt(
    *,
    spec_path: Path,
    project_root: Path,
    state_path: Path,
    plan_path: Path,
    chain: Mapping[str, Any],
    plan: Mapping[str, Any],
    chain_raw: bytes,
    plan_raw: bytes,
    milestone_index: int,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    from_branch: str,
    from_head: str,
    from_milestone_base: str,
    expected_spec_sha256: str,
) -> Mapping[str, Any]:
    """Validate the one committed restart that authorizes a post-restart rebind.

    The restart receipt is the committed ChainControl event, not the mutable
    ``current_attempt_restart`` projection.  The projection selects the
    operation; strict replay and the receipt's frozen guard payload prove the
    operation and its before/after custody identities.
    """

    from arnold_pipelines.megaplan.incident.chain_control import (
        chain_id_for_spec,
        journal_for,
        state_digest_for,
    )

    metadata = chain.get("metadata")
    restart = metadata.get("current_attempt_restart") if isinstance(metadata, Mapping) else None
    if not isinstance(restart, Mapping):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "post-restart target rebind requires a restart receipt",
        )
    legacy_attestation = restart.get("legacy_attestation") if isinstance(restart, Mapping) else None
    if isinstance(legacy_attestation, Mapping):
        return _assert_legacy_restart_attestation(
            spec_path=spec_path,
            project_root=project_root,
            state_path=state_path,
            plan_path=plan_path,
            chain=chain,
            plan=plan,
            chain_raw=chain_raw,
            plan_raw=plan_raw,
            milestone_index=milestone_index,
            expected_session_id=expected_session_id,
            expected_current_milestone=expected_current_milestone,
            expected_current_plan=expected_current_plan,
            from_branch=from_branch,
            from_head=from_head,
            expected_spec_sha256=expected_spec_sha256,
            restart=restart,
            attestation=legacy_attestation,
        )
    operation_id = str(restart.get("operation_id") or "").strip().lower()
    if _FULL_SHA256_RAW.fullmatch(operation_id) is None:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt operation id is malformed",
        )

    replay = journal_for(project_root).replay_strict()
    chain_id = chain_id_for_spec(spec_path)
    operation_events = [
        event
        for event in replay.get("accepted", [])
        if isinstance(event, Mapping)
        and event.get("chain_id") == chain_id
        and event.get("operation_id") == operation_id
    ]
    committed = [
        event
        for event in operation_events
        if event.get("event_kind") == "chain_control.committed"
    ]
    authoritative = [
        event
        for event in committed
        if event.get("intent") == "restart_current_attempt"
        and isinstance(event.get("payload"), Mapping)
        and event["payload"].get("intent_kind") == "restart_current_attempt"
        and isinstance(event["payload"].get("effect"), Mapping)
        and isinstance(event["payload"]["effect"].get("restart_guard"), Mapping)
        and event["payload"]["effect"]["restart_guard"].get("schema") == _RESTART_GUARD_SCHEMA
    ]
    if len(authoritative) != 1 or len(committed) != 1:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt must resolve to exactly one authoritative committed event",
        )
    event = authoritative[0]
    event_hash = _require_restart_sha(event.get("event_hash"), label="event hash")
    if event.get("intent") != "restart_current_attempt":
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt intent is not restart_current_attempt",
        )
    if event.get("chain_id") != chain_id or event.get("operation_id") != operation_id:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt chain or operation identity does not match the projection",
        )
    if event.get("spec_identity") != str(spec_path.resolve(strict=False)):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt spec identity does not match the guarded spec",
        )
    effect_payload = event.get("payload")
    effect = effect_payload.get("effect") if isinstance(effect_payload, Mapping) else None
    if (
        not isinstance(effect_payload, Mapping)
        or effect_payload.get("intent_kind") != "restart_current_attempt"
        or not isinstance(effect, Mapping)
    ):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt committed effect is malformed",
        )
    guard = effect.get("restart_guard")
    if not isinstance(guard, Mapping) or guard.get("schema") != _RESTART_GUARD_SCHEMA:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt lacks exact source and state guards",
        )

    required = {
        "session_id",
        "spec_sha256",
        "chain_state_sha256_before",
        "plan_state_sha256_before",
        "marker_sha256",
        "state_revision_before",
        "cursor",
        "milestone",
        "retired_plan",
        "source_binding_sha256",
        "source_binding",
        "source",
        "execution_binding",
        "pre_state_digest",
        "post_state_digest",
        "chain_state_sha256_after",
        "plan_state_sha256_after",
    }
    if not required.issubset(guard):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "restart receipt lacks complete source, binding, or state guards",
        )
    if guard.get("session_id") != expected_session_id:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt session identity does not match")
    if _require_restart_sha(guard.get("spec_sha256"), label="spec SHA-256") != expected_spec_sha256:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt spec guard does not match")
    if guard.get("cursor") != milestone_index or guard.get("milestone") != expected_current_milestone:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt milestone guard does not match")
    if guard.get("retired_plan") != expected_current_plan:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt retired-plan guard does not match")
    if event.get("expected_cursor") != milestone_index or event.get("actual_cursor") != milestone_index:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt cursor evidence does not match")
    expected_revision = guard.get("state_revision_before")
    actual_revision = event.get("actual_revision")
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or event.get("expected_revision") != expected_revision
        or isinstance(actual_revision, bool)
        or not isinstance(actual_revision, int)
        or actual_revision != expected_revision + 1
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt revision evidence does not match")
    observed_revision = metadata.get("_nbf08_revision") if isinstance(metadata, Mapping) else None
    if observed_revision != actual_revision:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt has an intervening state revision")

    source = guard.get("source")
    source_binding = guard.get("source_binding")
    current_binding = metadata.get("project_source_binding") if isinstance(metadata, Mapping) else None
    if (
        not isinstance(source, Mapping)
        or source.get("branch") != from_branch
        or source.get("head") != from_head
        or source.get("head") != str(source.get("head") or "").lower()
        or not isinstance(source_binding, Mapping)
        or not isinstance(current_binding, Mapping)
        or dict(source_binding) != dict(current_binding)
        or _binding_digest(current_binding) != _require_restart_sha(
            guard.get("source_binding_sha256"), label="source binding SHA-256"
        )
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt source binding does not match")
    if from_milestone_base != from_head:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt source base does not match source HEAD")
    execution_binding = metadata.get("execution_binding") if isinstance(metadata, Mapping) else None
    if not isinstance(execution_binding, Mapping) or dict(guard.get("execution_binding") or {}) != dict(execution_binding):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt launched execution binding changed")

    pre_chain = _require_restart_sha(guard.get("chain_state_sha256_before"), label="pre chain-state SHA-256")
    pre_plan = _require_restart_sha(guard.get("plan_state_sha256_before"), label="pre plan-state SHA-256")
    marker_sha = _require_restart_sha(guard.get("marker_sha256"), label="marker SHA-256")
    post_chain = _require_restart_sha(guard.get("chain_state_sha256_after"), label="post chain-state SHA-256")
    post_plan = _require_restart_sha(guard.get("plan_state_sha256_after"), label="post plan-state SHA-256")
    if _require_restart_sha(guard.get("spec_sha256"), label="spec SHA-256") != sha256_path(spec_path):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt spec changed")
    if _require_restart_sha(effect.get("chain_state_sha256"), label="effect chain-state SHA-256") != hashlib.sha256(chain_raw).hexdigest():
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt post chain state does not match")
    if _require_restart_sha(effect.get("plan_state_sha256"), label="effect plan-state SHA-256") != hashlib.sha256(plan_raw).hexdigest():
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt post plan state does not match")
    if post_chain != hashlib.sha256(chain_raw).hexdigest() or post_plan != hashlib.sha256(plan_raw).hexdigest():
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt post-state hashes do not match")
    if _require_restart_sha(effect.get("chain_state_sha256"), label="effect chain-state SHA-256") != _require_restart_sha(guard.get("chain_state_sha256_after"), label="post chain-state SHA-256"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt chain-state hashes disagree")
    if _require_restart_sha(effect.get("plan_state_sha256"), label="effect plan-state SHA-256") != _require_restart_sha(guard.get("plan_state_sha256_after"), label="post plan-state SHA-256"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt plan-state hashes disagree")
    if _require_restart_sha(event.get("pre_state_digest"), label="pre state digest") != _require_restart_sha(guard.get("pre_state_digest"), label="pre state digest"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt pre-state digest changed")
    if _require_restart_sha(event.get("post_state_digest"), label="post state digest") != _require_restart_sha(guard.get("post_state_digest"), label="post state digest"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt post-state digest changed")
    if _require_restart_sha(event.get("post_state_digest"), label="post state digest") != state_digest_for(chain):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt post-state digest does not match current chain state")

    marker_path = project_root / ".megaplan" / "cloud-session.json"
    if marker_path.is_file():
        if hashlib.sha256(marker_path.read_bytes()).hexdigest() != marker_sha:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt marker changed")
        _, marker = _load_json_bytes(marker_path, label="session marker")
        if marker.get("session") != expected_session_id or marker.get("should_run") is not False:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt requires a paused, unoccupied session marker")
        for key in ("owner", "runner", "tmux_session", "pid", "worker_pid"):
            value = marker.get(key)
            if value not in (None, False, "", [], {}, ()):
                raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"restart receipt session marker names an occupied {key}")

    retirement = plan.get("meta", {}).get("retirement") if isinstance(plan.get("meta"), Mapping) else None
    if (
        str(plan.get("current_state") or "").strip().lower() != "aborted"
        or not isinstance(retirement, Mapping)
        or retirement.get("kind") != "retired_for_restart"
        or retirement.get("operation_id") != operation_id
        or retirement.get("cursor") != milestone_index
        or retirement.get("milestone") != expected_current_milestone
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt retired plan identity does not match")
    if pre_chain == post_chain or pre_plan == post_plan:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "restart receipt does not prove a state transition")
    return {"event_hash": event_hash, "operation_id": operation_id, "event": event, "guard": guard}


def _assert_legacy_restart_attestation(
    *,
    spec_path: Path,
    project_root: Path,
    state_path: Path,
    plan_path: Path,
    chain: Mapping[str, Any],
    plan: Mapping[str, Any],
    chain_raw: bytes,
    plan_raw: bytes,
    milestone_index: int,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    from_branch: str,
    from_head: str,
    expected_spec_sha256: str,
    restart: Mapping[str, Any],
    attestation: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate the canonical bridge for an archived restart event."""
    from arnold_pipelines.megaplan.incident.chain_control import (
        chain_id_for_spec,
        journal_for,
        state_digest_for,
    )

    legacy_operation_id = str(attestation.get("legacy_operation_id") or "").strip().lower()
    attestation_operation_id = str(attestation.get("operation_id") or "").strip().lower()
    legacy_event_hash = str(attestation.get("legacy_event_hash") or "").strip().lower()
    if not all(_FULL_SHA256_RAW.fullmatch(value or "") for value in (legacy_operation_id, attestation_operation_id, legacy_event_hash)):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation identity is malformed")
    if restart.get("operation_id") != legacy_operation_id or restart.get("restart_guard") != attestation.get("restart_guard"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation projection is inconsistent")
    archive_journal = attestation.get("archive_journal")
    archive_manifest = attestation.get("archive_manifest")
    if not isinstance(archive_journal, Mapping) or not isinstance(archive_manifest, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation archive evidence is incomplete")
    replay = journal_for(project_root).replay_strict()
    chain_id = chain_id_for_spec(spec_path)
    events = [
        event for event in replay.get("accepted", [])
        if event.get("chain_id") == chain_id and event.get("operation_id") == attestation_operation_id
    ]
    commits = [event for event in events if event.get("event_kind") == "chain_control.restart_receipt_attested"]
    if len(events) != 4 or [event.get("event_kind") for event in events] != [
        "chain_control.intent", "chain_control.authority_validated", "chain_control.claimed", "chain_control.restart_receipt_attested"
    ] or len(commits) != 1:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation must have one intent, authority, claim, and commit")
    event = commits[0]
    payload = event.get("payload")
    effect = payload.get("effect") if isinstance(payload, Mapping) else None
    if not isinstance(payload, Mapping) or payload.get("intent_kind") != "restart_current_attempt_legacy_receipt_attestation" or not isinstance(effect, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation committed effect is malformed")
    if effect.get("legacy_operation_id") != legacy_operation_id or effect.get("legacy_event_hash") != legacy_event_hash:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation legacy identity changed")
    if effect.get("archive_journal") != dict(archive_journal) or effect.get("archive_manifest") != dict(archive_manifest):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation archive evidence changed")
    guard = effect.get("restart_guard")
    legacy_guard = effect.get("legacy_restart_guard")
    if not isinstance(guard, Mapping) or not isinstance(legacy_guard, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation guards are incomplete")
    required = ("session_id", "spec_sha256", "cursor", "milestone", "retired_plan", "source", "source_binding", "execution_binding")
    if any(key not in legacy_guard for key in required):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation lacks source guard")
    if legacy_guard.get("session_id") != expected_session_id or legacy_guard.get("spec_sha256") != expected_spec_sha256:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation session/spec guard does not match")
    if legacy_guard.get("cursor") != milestone_index or legacy_guard.get("milestone") != expected_current_milestone or legacy_guard.get("retired_plan") != expected_current_plan:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation milestone guard does not match")
    source = legacy_guard.get("source")
    binding = chain.get("metadata", {}).get("project_source_binding") if isinstance(chain.get("metadata"), Mapping) else None
    if not isinstance(source, Mapping) or source.get("branch") != from_branch or source.get("head") != from_head or legacy_guard.get("source_binding") != binding:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation source binding does not match")
    if legacy_guard.get("execution_binding") != chain.get("metadata", {}).get("execution_binding"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation execution binding changed")
    if event.get("expected_revision") != legacy_guard.get("attested_state_revision_before") and event.get("expected_revision") != legacy_guard.get("state_revision_before"):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation expected revision is malformed")
    observed_revision = chain.get("metadata", {}).get("_nbf08_revision") if isinstance(chain.get("metadata"), Mapping) else None
    if event.get("actual_revision") != observed_revision or guard.get("attested_state_revision_after") != observed_revision:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation revision evidence does not match")
    if event.get("actual_cursor") != milestone_index or event.get("expected_cursor") != milestone_index:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation cursor evidence does not match")
    if event.get("post_state_digest") != state_digest_for(chain) or effect.get("chain_state_sha256") != hashlib.sha256(chain_raw).hexdigest():
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation post-state evidence does not match")
    if effect.get("plan_state_sha256") != hashlib.sha256(plan_raw).hexdigest():
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation plan-state evidence does not match")
    retirement = plan.get("meta", {}).get("retirement") if isinstance(plan.get("meta"), Mapping) else None
    if str(plan.get("current_state") or "").lower() not in {"aborted", "cancelled"} or plan.get("active_step") is not None or not isinstance(retirement, Mapping) or retirement.get("kind") != "retired_for_restart" or retirement.get("operation_id") != legacy_operation_id:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation retired plan is not terminal")
    marker_path = project_root / ".megaplan" / "cloud-session.json"
    if marker_path.is_file():
        _, marker = _load_json_bytes(marker_path, label="session marker")
        if marker.get("session") != expected_session_id or marker.get("should_run") is not False or _marker_occupied(marker) is not None:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "legacy restart attestation requires a paused, unoccupied marker")
    return {"event_hash": event.get("event_hash"), "operation_id": legacy_operation_id, "attestation_operation_id": attestation_operation_id, "event": event, "guard": legacy_guard}


def _event(
    *,
    direction: str,
    actor: str,
    reason: str,
    session_id: str,
    spec_sha256: str,
    target_spec_sha256: str,
    chain_state_sha256: str,
    plan_state_sha256: str,
    milestone_index: int,
    milestone: str,
    plan: str,
    source: Mapping[str, str],
    target: Mapping[str, str],
    invalidated_artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": PROJECT_SOURCE_REBIND_SCHEMA,
        "rebound_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "direction": direction,
        "actor": actor,
        "reason": reason,
        "session_id": session_id,
        "spec_sha256": spec_sha256,
        "target_spec_sha256": target_spec_sha256,
        "chain_state_sha256": chain_state_sha256,
        "plan_state_sha256": plan_state_sha256,
        "milestone_index": milestone_index,
        "milestone": milestone,
        "plan": plan,
        "from": dict(source),
        "to": dict(target),
        "invalidated_artifacts": invalidated_artifacts,
    }
    digest = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**core, "content_sha256": digest}


def _binding_with_event(
    existing: Any,
    *,
    event: Mapping[str, Any],
    current: Mapping[str, str],
    original: Mapping[str, str],
) -> dict[str, Any]:
    binding = dict(existing) if isinstance(existing, Mapping) else {}
    events = binding.get("rebind_events")
    events = list(events) if isinstance(events, list) else []
    events.append(dict(event))
    return {
        **binding,
        "schema": PROJECT_SOURCE_BINDING_SCHEMA,
        "current": dict(current),
        "original": dict(original),
        "last_rebound_at": event["rebound_at"],
        "rebind_events": events,
    }


def _invalidate_gate_artifacts(
    plan_dir: Path,
    *,
    event_id_hint: str,
) -> tuple[list[dict[str, str]], list[tuple[Path, Path]]]:
    paths: list[Path] = []
    for pattern in _STALE_GATE_ARTIFACT_PATTERNS:
        for path in sorted(plan_dir.glob(pattern)):
            if path.is_file() and path not in paths:
                paths.append(path)
    if not paths:
        return [], []
    archive_dir = (
        plan_dir.parent
        / ".target-rebind-invalidated"
        / plan_dir.name
        / event_id_hint
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []
    moves: list[tuple[Path, Path]] = []
    for source in paths:
        destination = archive_dir / source.name
        os.replace(source, destination)
        moves.append((source, destination))
        records.append(
            {
                "artifact": source.name,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "archive_path": destination.relative_to(plan_dir.parent).as_posix(),
            }
        )
    return records, moves


def _restore_moves(moves: list[tuple[Path, Path]]) -> None:
    for source, destination in reversed(moves):
        if destination.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(destination, source)


def _checkout_target(
    project_root: Path,
    *,
    branch: str,
    head: str,
) -> bool:
    local = _run_git(
        project_root,
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
        error=f"could not inspect local branch {branch}",
    )
    created = local.returncode == 1
    if local.returncode not in {0, 1}:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"could not inspect local branch {branch}")
    if created:
        _run_git(
            project_root,
            ["switch", "--create", branch, head],
            error=f"could not create target branch {branch}",
        )
    else:
        existing = _git_text(
            project_root,
            ["rev-parse", f"refs/heads/{branch}^{{commit}}"],
            error=f"could not resolve local branch {branch}",
        ).lower()
        if existing != head:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"local branch {branch} is {existing}, expected exact target {head}",
            )
        _run_git(project_root, ["switch", branch], error=f"could not switch to {branch}")
    return created


def _restore_git(
    project_root: Path,
    *,
    branch: str,
    head: str,
    created_branch: str | None,
) -> None:
    _run_git(project_root, ["switch", branch], error=f"could not restore branch {branch}")
    restored = _current_head(project_root)
    if restored != head:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"rollback restored branch {branch} at {restored}, expected {head}",
        )
    if created_branch:
        # Reference census (T-0027): the rollback deletes the branch created
        # by the failed cutover — never while a runtime store still
        # references this project root.  REFERENCED / DANGLING / UNKNOWN
        # refuse the delete (fail-closed — delete-on-reference or -unknown
        # never happens); only CLEAR keeps the route authority.
        census_verdict, census_reasons = _reference_census(project_root)
        if census_verdict != "CLEAR":
            detail = "; ".join(census_reasons) or census_verdict
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"rollback refused to delete created branch {created_branch}: "
                f"reference census {census_verdict} for {project_root} ({detail})",
            )
        _run_git(
            project_root,
            ["branch", "--delete", "--force", created_branch],
            error=f"could not remove rolled-back branch {created_branch}",
        )


def _update_plan(
    plan: dict[str, Any],
    *,
    binding: Mapping[str, Any],
    target_head: str,
    event_sha256: str,
) -> None:
    meta = plan.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        plan["meta"] = meta
    policy = meta.setdefault("chain_policy", {})
    if not isinstance(policy, dict):
        policy = {}
        meta["chain_policy"] = policy
    policy["milestone_base_sha"] = target_head
    meta["project_source_binding"] = dict(binding)
    execution = meta.get("execution_environment")
    if isinstance(execution, dict):
        execution["target_head"] = target_head
        execution["last_observed_phase"] = "target_rebind"
    for key in ("gate_artifact_recovery", "gate_feasibility", "replan_feasibility"):
        meta.pop(key, None)
    plan.pop("active_step", None)
    plan.pop("latest_failure", None)
    plan["last_gate"] = {}
    plan["resume_cursor"] = {
        "phase": "critique",
        "retry_strategy": "fresh_critique_after_project_source_rebind",
        "project_source_rebind_sha256": event_sha256,
    }
    plan_pause = meta.get(AUTHORITY_KEY)
    if isinstance(plan_pause, dict):
        # A source rebind invalidates the relationship between the latest plan
        # version and its critique-custody receipt.  Returning directly to gate
        # can therefore loop forever when, for example, plan_v4 exists but only
        # critique_custody_v3.json survived the cutover.  Always reacquire
        # critique custody from the rebound source before gating.
        plan_pause["previous_current_state"] = "planned"
        plan_pause["project_source_rebind_sha256"] = event_sha256


def _update_chain(
    chain: dict[str, Any],
    *,
    binding: Mapping[str, Any],
    target_head: str,
    event_sha256: str,
) -> None:
    metadata = chain.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        chain["metadata"] = metadata
    metadata["project_source_binding"] = dict(binding)
    execution = metadata.get("execution_environment")
    if isinstance(execution, dict):
        execution["target_head"] = target_head
        execution["last_observed_phase"] = "target_rebind"
    chain_pause = metadata.get(AUTHORITY_KEY)
    if isinstance(chain_pause, dict):
        chain_pause["previous_plan_state"] = "planned"
        chain_pause["previous_chain_last_state"] = "planned"
        chain_pause["project_source_rebind_sha256"] = event_sha256


def target_rebind(
    spec_path: Path,
    project_root: Path,
    *,
    direction: str,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    from_branch: str,
    from_head: str,
    from_milestone_base: str,
    from_ref: str,
    to_branch: str,
    to_head: str,
    to_ref: str,
    expected_spec_sha256: str,
    expected_target_spec_sha256: str | None = None,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    reason: str,
    actor: str = "operator",
    verified_external_runtime_identity: Mapping[str, Any] | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Cut over or roll back a paused, pre-execute milestone project source."""

    if direction not in {"cutover", "rollback"}:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "direction must be cutover or rollback")
    if not all(
        str(value or "").strip()
        for value in (
            expected_session_id,
            expected_current_milestone,
            expected_current_plan,
            from_branch,
            to_branch,
            reason,
            actor,
        )
    ):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "every target-rebind guard is required")

    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    try:
        spec_path.relative_to(project_root)
    except ValueError as exc:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "chain spec must be inside the guarded project/session root",
        ) from exc
    if project_root.name != expected_session_id:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"session {project_root.name!r} does not match {expected_session_id!r}",
        )
    from_head = _guard_git_sha(from_head, label="from head")
    from_branch = _guard_branch(from_branch, label="from branch")
    from_milestone_base = _guard_git_sha(
        from_milestone_base,
        label="from milestone base",
    )
    to_head = _guard_git_sha(to_head, label="to head")
    to_branch = _guard_branch(to_branch, label="to branch")
    from_ref = _guard_ref(from_ref, label="from ref")
    to_ref = _guard_ref(to_ref, label="to ref")
    spec_sha = _guard_sha256(expected_spec_sha256, label="spec SHA-256")
    target_spec_sha = _guard_sha256(
        expected_target_spec_sha256 or expected_spec_sha256,
        label="target spec SHA-256",
    )
    chain_hash = _guard_sha256(
        expected_chain_state_sha256,
        label="chain-state SHA-256",
    )
    plan_hash = _guard_sha256(
        expected_plan_state_sha256,
        label="plan-state SHA-256",
    )
    if sha256_path(spec_path) != spec_sha:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "chain spec SHA-256 changed")

    state_path = chain_spec._state_path_for(spec_path)
    plan_dir = find_plan_dir(project_root, expected_current_plan)
    if plan_dir is None:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "current plan directory is unavailable")
    plan_path = plan_dir / "state.json"

    with _transaction_lock(state_path), driver_lock(plan_dir), plan_lock(
        plan_dir,
        step="chain target-rebind",
    ):
        chain_raw, chain = _load_json_bytes(state_path, label="chain state")
        plan_raw, plan = _load_json_bytes(plan_path, label="plan state")
        _assert_hash(chain_raw, chain_hash, label="chain-state SHA-256")
        _assert_hash(plan_raw, plan_hash, label="plan-state SHA-256")
        spec = chain_spec.load_spec(spec_path)
        from arnold_pipelines.megaplan.chain.execution_binding import (
            active_execution_identity,
            assert_execution_binding,
            execution_binding_report,
        )

        chain_state = chain_spec.ChainState.from_dict(chain)
        if isinstance(verified_external_runtime_identity, Mapping):
            external_active = active_execution_identity(spec_path)
            external_active["runtime"] = dict(verified_external_runtime_identity)
            external_active["ready"] = True
            external_active["errors"] = []
            external_report = execution_binding_report(
                spec_path,
                chain_state,
                active_identity=external_active,
            )
            if (
                direction != "rollback"
                and external_report.get("status") not in {"match", "reconcile_required"}
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "external control runtime does not satisfy the immutable execution binding",
                )
            runtime_report = external_report.get("runtime_binding") or {}
            if runtime_report.get("required") and runtime_report.get("status") != "match":
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "external control runtime does not satisfy the rebound runtime binding",
                )
        else:
            assert_execution_binding(
                spec_path,
                chain_state,
                operation="chain target-rebind",
            )
        milestone_index, milestone = _milestone(
            spec,
            chain,
            expected_label=expected_current_milestone,
        )
        restart_boundary = chain.get("current_plan_name") is None
        restart_receipt: Mapping[str, Any] | None = None
        if restart_boundary:
            metadata = chain.get("metadata")
            restart = metadata.get("current_attempt_restart") if isinstance(metadata, Mapping) else None
            if not (
                isinstance(restart, Mapping)
                and restart.get("schema") == "arnold.megaplan.current-attempt-restart.v1"
                and restart.get("retired_plan") == expected_current_plan
                and restart.get("cursor") == milestone_index
                and restart.get("milestone") == expected_current_milestone
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "target rebind without a current plan requires a matching "
                    "current-attempt restart boundary",
                )
            chain_pause = metadata.get(AUTHORITY_KEY) if isinstance(metadata, Mapping) else None
            if not (
                isinstance(chain_pause, Mapping)
                and chain_pause.get("active") is True
                and chain_pause.get("schema_version") == AUTHORITY_SCHEMA
                and chain.get("last_state") == "paused"
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "post-restart target rebind requires an active durable chain pause",
                )
            plan_meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else None
            retirement = plan_meta.get("retirement") if isinstance(plan_meta, Mapping) else None
            if (
                str(plan.get("current_state") or "").strip().lower() != "aborted"
                or plan.get("active_step") is not None
                or not (
                    isinstance(retirement, Mapping)
                    and retirement.get("kind") == "retired_for_restart"
                    and retirement.get("cursor") == milestone_index
                    and retirement.get("milestone") == expected_current_milestone
                )
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "post-restart target rebind requires the retired plan to be "
                    "terminal with matching retirement metadata",
                )
            restart_receipt = _assert_restart_receipt(
                spec_path=spec_path,
                project_root=project_root,
                state_path=state_path,
                plan_path=plan_path,
                chain=chain,
                plan=plan,
                chain_raw=chain_raw,
                plan_raw=plan_raw,
                milestone_index=milestone_index,
                expected_session_id=expected_session_id,
                expected_current_milestone=expected_current_milestone,
                expected_current_plan=expected_current_plan,
                from_branch=from_branch,
                from_head=from_head,
                from_milestone_base=from_milestone_base,
                expected_spec_sha256=spec_sha,
            )
        elif chain.get("current_plan_name") != expected_current_plan:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "current plan does not match the guard")
        if plan.get("name") not in {None, expected_current_plan}:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "plan state name does not match the guard")
        if not restart_boundary:
            _assert_pause(chain, plan, expected_plan=expected_current_plan)
            _assert_pre_execute(plan_dir, plan)
        _assert_clean_worktree(project_root)

        current_branch = _current_branch(project_root)
        current_head = _current_head(project_root)
        if current_branch != from_branch or current_head != from_head:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "current branch/HEAD does not match the guarded source",
                extra={
                    "observed_branch": current_branch,
                    "observed_head": current_head,
                    "expected_branch": from_branch,
                    "expected_head": from_head,
                },
            )
        meta = plan.get("meta")
        policy = meta.get("chain_policy") if isinstance(meta, Mapping) else None
        observed_base = policy.get("milestone_base_sha") if isinstance(policy, Mapping) else None
        if not restart_boundary and (observed_base != from_milestone_base or observed_base != from_head):
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "plan milestone base does not exactly match the guarded source HEAD",
            )
        if restart_boundary and restart_receipt is None:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "post-restart target rebind requires a validated restart receipt",
            )

        from_advertised = _remote_advertised_sha(project_root, from_ref)
        if from_advertised != from_head:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"advertised source {from_ref} is {from_advertised}, expected {from_head}",
            )
        to_advertised = _remote_advertised_sha(project_root, to_ref)
        if to_advertised != to_head:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"advertised target {to_ref} is {to_advertised}, expected {to_head}",
            )
        _fetch_advertised_ref(project_root, to_ref, to_head)
        existing_chain_binding = (
            chain.get("metadata", {}).get("project_source_binding")
            if isinstance(chain.get("metadata"), Mapping)
            else None
        )
        existing_plan_binding = (
            meta.get("project_source_binding") if isinstance(meta, Mapping) else None
        )
        if not restart_boundary and existing_chain_binding != existing_plan_binding:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "chain and plan project-source bindings diverged",
            )

        source = {
            "branch": from_branch,
            "head": from_head,
            "milestone_base_sha": from_milestone_base,
            "advertised_ref": from_ref,
            "advertised_sha": from_advertised,
        }
        target = {
            "branch": to_branch,
            "head": to_head,
            "milestone_base_sha": to_head,
            "advertised_ref": to_ref,
            "advertised_sha": to_advertised,
        }
        if direction == "cutover":
            if not milestone.branch or milestone.branch != to_branch:
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    f"cutover target branch must equal configured milestone branch {milestone.branch!r}",
                )
            if existing_chain_binding:
                current_binding = existing_chain_binding.get("current")
                original_binding = existing_chain_binding.get("original")
                existing_events = existing_chain_binding.get("rebind_events")
                last_existing_event = (
                    existing_events[-1]
                    if isinstance(existing_events, list) and existing_events
                    else None
                )
                if not (
                    isinstance(current_binding, Mapping)
                    and current_binding.get("branch") == from_branch
                    and current_binding.get("head") == from_head
                    and isinstance(original_binding, Mapping)
                    and original_binding.get("branch") == from_branch
                    and original_binding.get("head") == from_head
                    and isinstance(last_existing_event, Mapping)
                    and last_existing_event.get("direction") == "rollback"
                ):
                    raise CliError(
                        PROJECT_SOURCE_REBIND_ERROR,
                        "cutover requires no binding or an exact prior rollback to the original source",
                    )
            if not _is_ancestor(project_root, from_head, to_head) or from_head == to_head:
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "cutover target must be a strict fast-forward of the current source",
                )
            original = (
                dict(existing_chain_binding["original"])
                if isinstance(existing_chain_binding, Mapping)
                and isinstance(existing_chain_binding.get("original"), Mapping)
                else source
            )
        else:
            if not isinstance(existing_chain_binding, Mapping):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "rollback requires an existing project-source binding",
                )
            current = existing_chain_binding.get("current")
            original_binding = existing_chain_binding.get("original")
            events = existing_chain_binding.get("rebind_events")
            last_event = events[-1] if isinstance(events, list) and events else None
            if (
                not isinstance(current, Mapping)
                or current.get("branch") != from_branch
                or current.get("head") != from_head
                or not isinstance(original_binding, Mapping)
                or original_binding.get("branch") != to_branch
                or original_binding.get("head") != to_head
                or not isinstance(last_event, Mapping)
                or last_event.get("direction") != "cutover"
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "rollback guards do not exactly invert the active cutover",
                )
            original = dict(original_binding)

        invalidated: list[dict[str, str]] = []
        preview_event = _event(
            direction=direction,
            actor=actor,
            reason=reason,
            session_id=expected_session_id,
            spec_sha256=spec_sha,
            target_spec_sha256=target_spec_sha,
            chain_state_sha256=chain_hash,
            plan_state_sha256=plan_hash,
            milestone_index=milestone_index,
            milestone=expected_current_milestone,
            plan=expected_current_plan,
            source=source,
            target=target,
            invalidated_artifacts=[],
        )
        moves: list[tuple[Path, Path]] = []
        created_branch: str | None = None
        try:
            created = _checkout_target(project_root, branch=to_branch, head=to_head)
            created_branch = to_branch if created else None
            if sha256_path(spec_path) != target_spec_sha:
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "target checkout chain spec does not match the guarded target hash",
                )
            target_spec = chain_spec.load_spec(spec_path)
            if (
                milestone_index >= len(target_spec.milestones)
                or target_spec.milestones[milestone_index].label
                != expected_current_milestone
                or target_spec.milestones[milestone_index].branch
                != (to_branch if direction == "cutover" else from_branch)
            ):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "target chain spec changed the guarded current milestone identity or branch",
                )
            post_checkout_plan_raw, _ = _load_json_bytes(
                plan_path,
                label="plan state after checkout",
            )
            post_checkout_chain_raw, _ = _load_json_bytes(
                state_path,
                label="chain state after checkout",
            )
            _assert_hash(
                post_checkout_plan_raw,
                plan_hash,
                label="plan-state SHA-256 after checkout",
            )
            _assert_hash(
                post_checkout_chain_raw,
                chain_hash,
                label="chain-state SHA-256 after checkout",
            )
            if failure_injector is not None:
                failure_injector("after_git_switch")
            if not restart_boundary:
                invalidated, moves = _invalidate_gate_artifacts(
                    plan_dir,
                    event_id_hint=preview_event["content_sha256"][:16],
                )
            event = _event(
                direction=direction,
                actor=actor,
                reason=reason,
                session_id=expected_session_id,
                spec_sha256=spec_sha,
                target_spec_sha256=target_spec_sha,
                chain_state_sha256=chain_hash,
                plan_state_sha256=plan_hash,
                milestone_index=milestone_index,
                milestone=expected_current_milestone,
                plan=expected_current_plan,
                source=source,
                target=target,
                invalidated_artifacts=invalidated,
            )
            binding = _binding_with_event(
                existing_chain_binding,
                event=event,
                current=target,
                original=original,
            )
            if not restart_boundary:
                _update_plan(
                    plan,
                    binding=binding,
                    target_head=to_head,
                    event_sha256=event["content_sha256"],
                )
                _atomic_write(plan_path, _json_bytes(plan))
                if failure_injector is not None:
                    failure_injector("after_plan_write")
            _update_chain(
                chain,
                binding=binding,
                target_head=to_head,
                event_sha256=event["content_sha256"],
            )
            _atomic_write(state_path, _json_bytes(chain))
            if failure_injector is not None:
                failure_injector("after_chain_write")
            if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "target rebind postcondition branch/HEAD diverged",
                )
        except BaseException:
            rollback_errors: list[str] = []
            if not restart_boundary:
                try:
                    _atomic_write(plan_path, plan_raw)
                except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
                    rollback_errors.append(f"plan state restore failed: {exc}")
            try:
                _atomic_write(state_path, chain_raw)
            except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(f"chain state restore failed: {exc}")
            try:
                _restore_moves(moves)
            except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(f"artifact restore failed: {exc}")
            try:
                _restore_git(
                    project_root,
                    branch=from_branch,
                    head=from_head,
                    created_branch=created_branch,
                )
            except Exception as exc:  # pragma: no cover - catastrophic Git failure
                rollback_errors.append(f"Git restore failed: {exc}")
            if rollback_errors:
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    "target rebind failed and rollback was incomplete",
                    extra={"rollback_errors": rollback_errors},
                )
            raise

        return {
            "direction": direction,
            "event": event,
            "project_source_binding": binding,
            "branch": to_branch,
            "head": to_head,
            "plan_state_sha256": sha256_path(plan_path),
            "chain_state_sha256": sha256_path(state_path),
        }


def cutover_paused_checkout(
    spec_path: Path,
    project_root: Path,
    *,
    marker_path: Path,
    aborted_plan_path: Path,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_cursor: int,
    expected_completed_prefix: list[Mapping[str, Any]],
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    expected_marker_sha256: str,
    expected_spec_sha256: str,
    expected_chain_revision: Any,
    expected_hold: Mapping[str, Any],
    expected_runtime_identity: Mapping[str, Any],
    from_branch: str,
    from_head: str,
    from_milestone_base: str,
    from_ref: str,
    to_branch: str,
    to_head: str,
    to_milestone_base: str,
    to_ref: str,
    expected_target_spec_sha256: str | None = None,
    reason: str,
    actor: str = "operator",
    operation_id: str | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Cut over a paused/null-plan C2 checkout and attest its source.

    Unlike ``target_rebind`` this operation accepts the persisted aborted-C2
    shape, never rewrites the aborted plan, and never creates a plan or
    dispatches work.  Git and authority files are changed only inside the
    existing chain-control transaction and are recovered from its intent.
    """
    from arnold_pipelines.megaplan.cloud.runtime_cutover import (
        marker_runtime_identity,
        normalize_runtime_identity,
    )
    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlHold,
        ChainStateAdapter,
        canonical_json,
        chain_id_for_spec,
        _incomplete_operation_statuses,
        journal_for,
        physical_digest_after,
        read_physical_lines,
        sha256_hex,
        state_digest_for,
    )

    def refuse(message: str, **details: Any) -> NoReturn:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, message, extra=details)

    if not reason.strip() or not actor.strip() or not expected_session_id.strip():
        refuse("reason, actor, and session are required")
    if expected_cursor != 6 or len(expected_completed_prefix) != 6:
        refuse("cutover requires the exact six-milestone completed prefix")
    if not isinstance(expected_hold, Mapping) or not isinstance(expected_runtime_identity, Mapping):
        refuse("hold and runtime identity guards are required")
    spec_path = spec_path.resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    marker_path = marker_path.resolve(strict=False)
    aborted_plan_path = aborted_plan_path.resolve(strict=False)
    if expected_session_id != project_root.name:
        refuse("session must equal the canonical project-root name")
    chain_path = chain_spec._state_path_for(spec_path)
    for path in (spec_path, chain_path, marker_path, aborted_plan_path):
        try:
            path.relative_to(project_root)
        except ValueError as exc:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "authority paths must be inside project root") from exc
    if not all(path.exists() for path in (spec_path, chain_path, aborted_plan_path, marker_path)):
        refuse("required cutover authority file is unavailable")

    from_branch = _guard_branch(from_branch, label="from branch")
    from_head = _guard_git_sha(from_head, label="from head")
    from_milestone_base = _guard_git_sha(from_milestone_base, label="from milestone base")
    from_ref = _guard_ref(from_ref, label="from ref")
    to_branch = _guard_branch(to_branch, label="to branch")
    to_head = _guard_git_sha(to_head, label="to head")
    to_milestone_base = _guard_git_sha(to_milestone_base, label="to milestone base")
    to_ref = _guard_ref(to_ref, label="to ref")
    expected_spec_sha256 = _guard_sha256(expected_spec_sha256, label="spec SHA-256")
    expected_chain_state_sha256 = _guard_sha256(expected_chain_state_sha256, label="chain-state SHA-256")
    expected_plan_state_sha256 = _guard_sha256(expected_plan_state_sha256, label="plan-state SHA-256")
    expected_marker_sha256 = _guard_sha256(expected_marker_sha256, label="marker SHA-256")
    target_spec_sha256 = _guard_sha256(
        expected_target_spec_sha256 or expected_spec_sha256,
        label="target spec SHA-256",
    )

    chain_raw, chain = _load_json_bytes(chain_path, label="chain state")
    plan_raw, plan = _load_json_bytes(aborted_plan_path, label="aborted C2 plan")
    marker_raw, marker = _load_json_bytes(marker_path, label="session marker")
    _assert_hash(plan_raw, expected_plan_state_sha256, label="plan-state SHA-256")
    spec = chain_spec.load_spec(spec_path)
    if expected_cursor >= len(spec.milestones) or spec.milestones[expected_cursor].label != expected_current_milestone:
        refuse("current milestone does not match the guarded C2 successor")
    persisted_prefix = chain.get("completed")
    if not isinstance(persisted_prefix, list) or len(persisted_prefix) != 6 or not all(isinstance(item, Mapping) for item in persisted_prefix):
        refuse("persisted completed prefix is not the exact six-milestone authority")
    canonical_prefix = [dict(item) for item in persisted_prefix]
    if canonical_prefix != [dict(item) for item in expected_completed_prefix]:
        refuse("guarded completed prefix does not match persisted authority")
    if any(item.get("status") != "completed" for item in canonical_prefix):
        refuse("persisted completed prefix records must carry completed status")
    if [item.get("label") for item in canonical_prefix] != [str(item.label) for item in spec.milestones[:6]]:
        refuse("persisted completed prefix is not canonical")
    if any(set(item) - {"label", "status", "artifacts"} for item in canonical_prefix):
        refuse("persisted completed prefix contains non-canonical fields")
    for item in canonical_prefix:
        artifacts = item.get("artifacts")
        if isinstance(artifacts, Mapping):
            has_artifacts = bool(artifacts)
        elif isinstance(artifacts, list):
            has_artifacts = bool(artifacts) and all(isinstance(entry, Mapping) for entry in artifacts)
        else:
            has_artifacts = False
        if not has_artifacts:
            refuse("completed prefix predecessor artifacts are required")
    from arnold_pipelines.megaplan.chain.current_attempt import _assert_artifact_hashes
    _assert_artifact_hashes(project_root, canonical_prefix)
    # Derive the id before inspecting the live checkout so a retry with the
    # original pre-state guards can replay after the checkout has moved.
    early_source = {"branch": from_branch, "head": from_head, "milestone_base_sha": from_milestone_base, "advertised_ref": from_ref, "advertised_sha": from_head}
    # The target SHA is an input identity; remote observation is deliberately
    # deferred until every local action-off/authority guard has passed.
    early_target_advertised = to_head
    early_target = {"branch": to_branch, "head": to_head, "milestone_base_sha": to_milestone_base, "advertised_ref": to_ref, "advertised_sha": early_target_advertised}
    chain_id = chain_id_for_spec(spec_path)
    early_guard_material = {"schema": "arnold.megaplan.paused-checkout-cutover.v1", "session": expected_session_id, "milestone": expected_current_milestone, "cursor": expected_cursor, "chain_id": chain_id, "chain_sha256": expected_chain_state_sha256, "plan_sha256": expected_plan_state_sha256, "marker_sha256": expected_marker_sha256, "spec_sha256": expected_spec_sha256, "target_spec_sha256": target_spec_sha256, "chain_revision": expected_chain_revision, "prefix": canonical_prefix, "hold": dict(expected_hold), "runtime": normalize_runtime_identity(expected_runtime_identity), "source": early_source, "target": early_target}
    early_operation_id = "c2-checkout-cutover-" + sha256_hex(canonical_json(early_guard_material))
    journal = journal_for(project_root)
    early_replay = journal.replay_strict()
    # Replay/refusal still requires the stable authority identities; mutable
    # pre-state hashes may legitimately differ after a committed cutover.
    replay_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    replay_hold = marker.get("operator_resume_hold")
    if chain.get("chain_session") != expected_session_id or replay_meta.get("chain_id") != chain_id:
        refuse("replay authority session or chain ID diverges")
    if marker.get("should_run") is not False or not isinstance(replay_hold, Mapping) or replay_hold != dict(expected_hold):
        refuse("replay authority hold or action-off state diverges")
    if marker_runtime_identity(marker) != normalize_runtime_identity(expected_runtime_identity):
        refuse("replay runtime identity diverges")
    pending_intent = next(
        (event for event in reversed(early_replay.get("accepted", []))
         if event.get("event_kind") == "chain_control.intent"
         and isinstance(event.get("payload"), Mapping)
         and isinstance(event["payload"].get("effect"), Mapping)
         and event["payload"]["effect"].get("source") == early_source
         and event["payload"]["effect"].get("target") == early_target),
        None,
    )
    # Replays may carry refreshed observational hashes; retain the original
    # operation identity from its durable intent when source/target identities
    # are unchanged.
    if pending_intent is not None and isinstance(pending_intent.get("operation_id"), str):
        early_operation_id = str(pending_intent["operation_id"])
    replay_identity_from_intent = pending_intent is not None
    early_existing = next(
        (event for event in reversed(early_replay.get("accepted", []))
         if event.get("operation_id") == early_operation_id
         and event.get("event_kind") == "chain_control.source_checkout_cutover"),
        None,
    )
    live_spec_sha256 = sha256_path(spec_path)
    target_replay = pending_intent is not None or early_existing is not None
    if (live_spec_sha256 == target_spec_sha256
            and target_spec_sha256 != expected_spec_sha256
            and not target_replay):
        refuse("chain spec SHA-256 changed")
    if live_spec_sha256 not in (expected_spec_sha256, target_spec_sha256):
        refuse("chain spec SHA-256 changed")
    foreign_incomplete = {
        operation: kind
        for operation, kind in _incomplete_operation_statuses(early_replay, chain_id).items()
        if operation != early_operation_id
    }
    if foreign_incomplete:
        refuse("a foreign journal operation is incomplete", operations=foreign_incomplete)
    # Complete local authority closure before any branch/head observation or
    # remote Git operation.  Replay and recovery below may read Git only after
    # this same action-off boundary has passed.
    chain_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    plan_name = plan.get("name")
    if not isinstance(plan_name, str) or not plan_name.strip():
        refuse("canonical aborted plan name is required")
    if chain.get("current_milestone_index") != expected_cursor or chain.get("current_plan_name") is not None or chain.get("last_state") != "paused":
        refuse("chain is not paused at cursor 6 with a null current plan")
    if chain.get("chain_session") != expected_session_id or chain_meta.get("chain_id") != chain_id:
        refuse("canonical session or chain ID identity diverges")
    expected_chain_spec_sha256 = target_spec_sha256 if live_spec_sha256 == target_spec_sha256 else expected_spec_sha256
    if chain_meta.get("chain_spec_sha256") != expected_chain_spec_sha256:
        refuse("chain spec identity diverges")
    if plan.get("current_state") != "aborted" or plan.get("active_step") is not None:
        refuse("aborted C2 plan is not immutable and inactive")
    canonical_plan_path = find_plan_dir(project_root, plan_name)
    if canonical_plan_path is None or aborted_plan_path != (canonical_plan_path / "state.json").resolve(strict=False):
        refuse("aborted plan path is not the canonical plan authority")
    pause = marker.get("operator_pause")
    hold = marker.get("operator_resume_hold")
    if marker.get("should_run") is not False or not isinstance(pause, Mapping) or pause.get("active") is not True or pause.get("schema_version") != AUTHORITY_SCHEMA or pause.get("plan") != plan_name or not isinstance(hold, Mapping) or hold.get("active") is not True:
        refuse("marker is not paused, held, and action-off")
    if chain_meta.get(AUTHORITY_KEY) != dict(pause):
        refuse("chain and marker pause authorities do not match")
    resume_authority = hold.get("resume_authority")
    if (hold.get("schema_version") != RESUME_HOLD_SCHEMA or hold.get("session") != expected_session_id or hold.get("spec") != str(spec_path) or hold.get("workspace") != str(project_root) or not isinstance(resume_authority, Mapping) or resume_authority.get("schema_version") != AUTHORITY_SCHEMA or resume_authority.get("plan") != plan_name):
        refuse("canonical active hold identity is required")
    if dict(hold) != dict(expected_hold):
        refuse("active hold does not match guard")
    if marker_runtime_identity(marker) != normalize_runtime_identity(expected_runtime_identity):
        refuse("marker runtime identity does not match guard")
    if any(marker.get(field) not in (None, "", False) for field in ("owner", "active_owner", "owner_pid", "chain_owner", "owner_id")):
        refuse("an active owner is present")
    expected_prefix = canonical_prefix
    if chain.get("completed") != expected_prefix or any(item.get("status") != "completed" for item in expected_prefix):
        refuse("completed six-milestone prefix is not canonical")
    if [item.get("label") for item in expected_prefix] != [str(item.label) for item in spec.milestones[:6]]:
        refuse("guarded completed prefix is not canonical")
    if any(set(item) - {"label", "status", "artifacts"} for item in expected_prefix):
        refuse("completed prefix contains non-canonical caller fields")
    from arnold_pipelines.megaplan.chain.current_attempt import _assert_artifact_hashes
    _assert_artifact_hashes(project_root, expected_prefix)
    chain_policy = chain_meta.get("chain_policy") if isinstance(chain_meta.get("chain_policy"), Mapping) else None
    if not isinstance(chain_policy, Mapping) or chain_policy.get("milestone_base_sha") != from_milestone_base or chain_policy.get("milestone_base_sha") != from_head:
        refuse("source milestone base is not derived from chain authority")
    target_milestone = spec.milestones[expected_cursor]
    if target_milestone.branch not in (None, to_branch):
        refuse("target milestone branch does not match guarded target branch")
    for binding_name, binding in (("chain", chain_meta.get("project_source_binding")), ("marker", marker.get("project_source_binding")), ("plan", (plan.get("meta") or {}).get("project_source_binding") if isinstance(plan.get("meta"), Mapping) else None)):
        if binding is not None and not isinstance(binding, Mapping):
            refuse(f"existing {binding_name} source binding is malformed")
        if isinstance(binding, Mapping):
            admission = binding.get("admission") if isinstance(binding.get("admission"), Mapping) else {}
            committed_replay = binding.get("current") == early_target and admission.get("operation_id") == early_operation_id
            if ((binding.get("current") != early_source and not committed_replay)
                    or binding.get("original") not in (None, early_source)
                    or (binding.get("rebind_events") not in (None, []) and not committed_replay)):
                refuse(f"existing {binding_name} source binding diverges from guarded source")
    if early_existing is not None and early_existing.get("event_kind") == "chain_control.source_checkout_cutover":
        payload = early_existing.get("payload") if isinstance(early_existing.get("payload"), Mapping) else {}
        effect = payload.get("effect") if isinstance(payload.get("effect"), Mapping) else {}
        if not replay_identity_from_intent and effect.get("guard_digest") != sha256_hex(canonical_json(early_guard_material)):
            refuse("committed cutover guard digest differs")
        if live_spec_sha256 != target_spec_sha256:
            refuse("chain spec SHA-256 changed")
        if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
            refuse("committed cutover checkout diverged")
        return {"outcome": "replay", "operation_id": early_operation_id, "receipt": dict(early_existing), "external_effect": False}
    # A process may disappear after both projections were written but before
    # the terminal event was acknowledged.  Complete that exact intent before
    # applying any pre-state hash or Git-side effect.
    if pending_intent is not None:
        pending_payload = pending_intent.get("payload") if isinstance(pending_intent.get("payload"), Mapping) else {}
        pending_effect = pending_payload.get("effect") if isinstance(pending_payload.get("effect"), Mapping) else {}
        pending_post_chain = pending_effect.get("post_chain")
        pending_post_marker = pending_effect.get("post_marker")
        if isinstance(pending_post_chain, Mapping) and isinstance(pending_post_marker, Mapping):
            pending_meta = pending_post_chain.get("metadata") if isinstance(pending_post_chain.get("metadata"), Mapping) else {}
            pending_hold = pending_post_marker.get("operator_resume_hold")
            pending_runtime = marker_runtime_identity(pending_post_marker)
            pending_at_target = _current_branch(project_root) == to_branch and _current_head(project_root) == to_head
            if pending_at_target and live_spec_sha256 != target_spec_sha256:
                refuse("chain spec SHA-256 changed")
            if (pending_at_target
                    and state_digest_for(chain) == pending_effect.get("post_chain_digest")
                    and marker == dict(pending_post_marker)
                    and pending_post_chain.get("chain_session") == expected_session_id
                    and pending_meta.get("chain_id") == chain_id
                    and pending_post_chain.get("completed") == canonical_prefix
                    and pending_hold == dict(expected_hold)
                    and pending_runtime == normalize_runtime_identity(expected_runtime_identity)):
                with journal.transaction(chain_ids=[chain_id], state_paths=[chain_path, marker_path, spec_path, aborted_plan_path], operation_id=early_operation_id, actor={"id": actor, "class": "operator"}) as txn:
                    terminal = journal.operation_result(early_operation_id)
                    if terminal is not None and terminal.get("event_kind") == "chain_control.source_checkout_cutover":
                        return {"outcome": "replay", "operation_id": early_operation_id, "receipt": dict(terminal), "external_effect": False}
                    committed = journal.append_under_lock(
                        txn, event_kind="chain_control.source_checkout_cutover", chain_id=chain_id,
                        operation_id=early_operation_id, causation_id=str(pending_intent.get("event_id") or early_operation_id),
                        correlation_id=early_operation_id, payload={"schema": pending_effect.get("schema"), "effect": dict(pending_effect)},
                        semantic_effect="metadata_only", claim_class="required", actor={"id": actor, "class": "operator"},
                        outcome="committed", intent="cutover-paused-checkout", expected_cursor=expected_cursor,
                        expected_revision=expected_chain_revision, actual_cursor=expected_cursor,
                        actual_revision=pending_post_chain.get("metadata", {}).get("_nbf08_revision"),
                        pre_state_digest=pending_effect.get("pre_chain_digest"), post_state_digest=pending_effect.get("post_chain_digest"),
                        source_identity=pending_effect.get("source"), spec_identity=str(spec_path),
                        linked_receipts=[str(pending_intent.get("event_id") or early_operation_id)],
                    )
                    return {"outcome": "recovered", "operation_id": early_operation_id, "receipt": committed, "external_effect": False}
    _assert_hash(chain_raw, expected_chain_state_sha256, label="chain-state SHA-256")
    _assert_hash(marker_raw, expected_marker_sha256, label="marker SHA-256")
    # A caller may repeat with refreshed observational file hashes after the
    # first commit.  The committed source/target tuple remains the stronger
    # idempotency identity than those mutable observations.
    for event in reversed(early_replay.get("accepted", [])):
        if event.get("event_kind") != "chain_control.source_checkout_cutover":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        effect = payload.get("effect") if isinstance(payload.get("effect"), Mapping) else {}
        if effect.get("source") == early_source and effect.get("target") == early_target:
            if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
                refuse("committed cutover checkout diverged")
            return {"outcome": "replay", "operation_id": str(event.get("operation_id") or early_operation_id), "receipt": dict(event), "external_effect": False}
    current_branch = _current_branch(project_root)
    current_head = _current_head(project_root)
    if (current_branch != from_branch or current_head != from_head) and not (
        pending_intent is not None and current_branch == to_branch and current_head == to_head
    ):
        refuse("current checkout branch/HEAD does not match guarded source")
    # All authority/action-off checks must precede ls-remote, fetch, ancestry,
    # and checkout effects.  The path is part of the same authority closure.
    chain_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    if chain.get("current_milestone_index") != expected_cursor or chain.get("current_plan_name") is not None or chain.get("last_state") != "paused":
        refuse("chain is not paused at cursor 6 with a null current plan")
    if chain_meta.get("_nbf08_revision") != expected_chain_revision:
        refuse("chain revision does not match guard")
    if plan.get("current_state") != "aborted" or plan.get("active_step") is not None:
        refuse("aborted C2 plan is not immutable and inactive")
    plan_name = str(plan.get("name") or aborted_plan_path.parent.name)
    pause = marker.get("operator_pause")
    hold = marker.get("operator_resume_hold")
    if marker.get("should_run") is not False or not isinstance(pause, Mapping) or pause.get("active") is not True or pause.get("schema_version") != AUTHORITY_SCHEMA or pause.get("plan") != plan_name or not isinstance(hold, Mapping) or hold.get("active") is not True:
        refuse("marker is not paused, held, and action-off")
    if chain.get("chain_session") != expected_session_id:
        refuse("chain session identity is required and does not match guard")
    if chain_meta := (chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}):
        if chain_meta.get("chain_id") != chain_id:
            refuse("chain ID identity is required and does not match the guarded spec")
    else:
        refuse("chain metadata authority is unavailable")
    if chain_meta.get("operator_pause") != marker.get("operator_pause"):
        refuse("chain and marker pause authorities do not match")
    resume_authority = hold.get("resume_authority") if isinstance(hold, Mapping) else None
    if (not isinstance(hold, Mapping) or hold.get("schema_version") != RESUME_HOLD_SCHEMA or hold.get("session") != expected_session_id or hold.get("spec") != str(spec_path) or not isinstance(resume_authority, Mapping) or resume_authority.get("schema_version") != AUTHORITY_SCHEMA or resume_authority.get("plan") != plan_name):
        refuse("canonical active hold identity is required")
    canonical_plan_path = find_plan_dir(project_root, plan_name) / "state.json"
    if aborted_plan_path != canonical_plan_path.resolve(strict=False):
        refuse("aborted plan path is not the canonical plan authority")
    if any(item.get("status") != "completed" for item in canonical_prefix):
        refuse("completed prefix records must carry completed status")
    try:
        from arnold_pipelines.megaplan.chain.current_attempt import _assert_artifact_hashes
        _assert_artifact_hashes(project_root, canonical_prefix)
    except CliError:
        raise
    if chain_meta.get("chain_policy", {}).get("milestone_base_sha") not in (None, from_milestone_base):
        refuse("source milestone base does not match chain policy")
    existing_binding = chain_meta.get("project_source_binding")
    if existing_binding is not None and not isinstance(existing_binding, Mapping):
        refuse("existing chain source binding is malformed")
    if isinstance(existing_binding, Mapping) and existing_binding.get("current") not in (None, early_source):
        refuse("existing chain source binding diverges from guarded source")
    marker_binding = marker.get("project_source_binding")
    if marker_binding is not None and not isinstance(marker_binding, Mapping):
        refuse("existing marker source binding is malformed")
    if isinstance(marker_binding, Mapping) and marker_binding.get("current") not in (None, early_source):
        refuse("existing marker source binding diverges from guarded source")
    plan_meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else {}
    plan_binding = plan_meta.get("project_source_binding")
    if plan_binding is not None and not isinstance(plan_binding, Mapping):
        refuse("existing plan source binding is malformed")
    if isinstance(plan_binding, Mapping) and plan_binding.get("current") not in (None, early_source):
        refuse("existing plan source binding diverges from guarded source")
    if dict(hold) != dict(expected_hold) or hold.get("session") != expected_session_id:
        refuse("active hold does not match guard")
    observed_runtime = marker_runtime_identity(marker)
    if observed_runtime is None or observed_runtime != normalize_runtime_identity(expected_runtime_identity):
        refuse("marker runtime identity does not match guard")
    execution_binding = chain_meta.get("execution_binding")
    launched = execution_binding.get("launched_identity") if isinstance(execution_binding, Mapping) else None
    launched_runtime = launched.get("runtime") if isinstance(launched, Mapping) else None
    if isinstance(launched_runtime, Mapping) and normalize_runtime_identity(launched_runtime) != normalize_runtime_identity(expected_runtime_identity):
        refuse("chain launched runtime identity does not match guard")
    for field, expected in (("editable_source_branch", from_branch), ("editable_source_head", from_head)):
        observed = marker.get(field)
        if observed not in (None, "") and str(observed) != expected:
            refuse(f"marker {field} does not match guarded source")
    if chain.get("completed") != canonical_prefix:
        refuse("completed six-milestone prefix does not match guard")
    if [item.get("label") for item in canonical_prefix] != [str(item.label) for item in spec.milestones[:6]]:
        refuse("guarded completed prefix is not canonical")
    if any(marker.get(field) not in (None, "", False) for field in ("owner", "active_owner", "owner_pid", "chain_owner", "owner_id")):
        refuse("an active owner is present")
    _assert_clean_worktree(project_root)
    if _remote_advertised_sha(project_root, from_ref) != from_head:
        refuse("advertised source does not match guarded source HEAD")
    target_advertised = _remote_advertised_sha(project_root, to_ref)
    if target_advertised != to_head:
        refuse("advertised target does not match guarded target HEAD")
    _fetch_advertised_ref(project_root, to_ref, to_head)
    if not _is_ancestor(project_root, from_head, to_head) or from_head == to_head:
        refuse("target checkout must be a strict fast-forward of guarded source")
    if not _is_ancestor(project_root, to_milestone_base, to_head):
        refuse("target milestone base is not an ancestor of target HEAD")

    chain_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    if chain.get("current_milestone_index") != expected_cursor or chain.get("current_plan_name") is not None or chain.get("last_state") != "paused":
        refuse("chain is not paused at cursor 6 with a null current plan")
    if chain_meta.get("_nbf08_revision") != expected_chain_revision:
        refuse("chain revision does not match guard")
    if plan.get("current_state") != "aborted" or plan.get("active_step") is not None:
        refuse("aborted C2 plan is not immutable and inactive")
    plan_name = str(plan.get("name") or aborted_plan_path.parent.name)
    pause = marker.get("operator_pause")
    hold = marker.get("operator_resume_hold")
    if marker.get("should_run") is not False or not isinstance(pause, Mapping) or pause.get("active") is not True or pause.get("schema_version") != AUTHORITY_SCHEMA or pause.get("plan") != plan_name or not isinstance(hold, Mapping) or hold.get("active") is not True:
        refuse("marker is not paused, held, and action-off")
    source = {"branch": from_branch, "head": from_head, "milestone_base_sha": from_milestone_base, "advertised_ref": from_ref, "advertised_sha": from_head}
    target = {"branch": to_branch, "head": to_head, "milestone_base_sha": to_milestone_base, "advertised_ref": to_ref, "advertised_sha": target_advertised}
    chain_id = chain_id_for_spec(spec_path)
    guard_material = {"schema": "arnold.megaplan.paused-checkout-cutover.v1", "session": expected_session_id, "milestone": expected_current_milestone, "cursor": expected_cursor, "chain_id": chain_id, "chain_sha256": expected_chain_state_sha256, "plan_sha256": expected_plan_state_sha256, "marker_sha256": expected_marker_sha256, "spec_sha256": expected_spec_sha256, "target_spec_sha256": target_spec_sha256, "chain_revision": expected_chain_revision, "prefix": canonical_prefix, "hold": dict(expected_hold), "runtime": normalize_runtime_identity(expected_runtime_identity), "source": source, "target": target}
    guard_digest = sha256_hex(canonical_json(guard_material))
    derived_operation_id = "c2-checkout-cutover-" + guard_digest
    if operation_id is not None and operation_id != derived_operation_id:
        refuse("operation identity does not match guarded inputs")
    operation_id = derived_operation_id
    journal = journal_for(project_root)
    replay = journal.replay_strict()
    existing = next(
        (event for event in reversed(replay.get("accepted", []))
         if event.get("operation_id") == operation_id
         and event.get("event_kind") == "chain_control.source_checkout_cutover"),
        None,
    )
    if existing is not None and existing.get("event_kind") == "chain_control.source_checkout_cutover":
        payload = existing.get("payload") if isinstance(existing.get("payload"), Mapping) else {}
        effect = payload.get("effect") if isinstance(payload.get("effect"), Mapping) else {}
        if effect.get("guard_digest") != guard_digest:
            refuse("committed cutover guard digest differs")
        if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
            refuse("committed cutover checkout diverged")
        return {"outcome": "replay", "operation_id": operation_id, "receipt": dict(existing), "external_effect": False}

    event_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    event = {"schema": PROJECT_SOURCE_REBIND_SCHEMA, "operation": "cutover-paused-checkout", "operation_id": operation_id, "actor": actor, "reason": reason, "session_id": expected_session_id, "chain_id": chain_id, "milestone": expected_current_milestone, "cursor": expected_cursor, "from": source, "to": target, "guard_digest": guard_digest, "rebound_at": event_time}
    event["content_sha256"] = sha256_hex(canonical_json(event))
    binding = {"schema": PROJECT_SOURCE_BINDING_SCHEMA, "current": target, "original": source, "admission": {"schema": "arnold.megaplan.paused-checkout-admission.v1", "operation_id": operation_id, "guard_digest": guard_digest}, "rebind_events": [event], "last_rebound_at": event_time}
    post_chain = copy.deepcopy(chain)
    post_meta = dict(post_chain.get("metadata") or {})
    post_meta.update({"chain_id": chain_id, "chain_spec_sha256": target_spec_sha256, "project_source_binding": binding})
    post_chain["chain_session"] = expected_session_id
    post_chain["metadata"] = post_meta
    post_chain["current_milestone_index"] = expected_cursor
    post_chain["current_plan_name"] = None
    post_chain["last_state"] = "paused"
    post_meta["_nbf08_revision"] = int(expected_chain_revision) + 1
    post_chain["metadata"] = post_meta
    post_marker = copy.deepcopy(marker)
    post_marker["project_source_binding"] = binding
    post_marker["editable_source_branch"] = to_branch
    post_marker["editable_source_head"] = to_head
    sync = post_marker.get("editable_install_sync")
    if isinstance(sync, dict):
        sync["status"] = "content-addressed-source-cutover"
        sync["source"] = str(project_root)
    effect = {"schema": "arnold.megaplan.paused-checkout-cutover.v1", "guard_digest": guard_digest, "pre_chain_digest": state_digest_for(chain), "pre_chain_sha256": expected_chain_state_sha256, "pre_marker_sha256": expected_marker_sha256, "plan_sha256": expected_plan_state_sha256, "post_chain": post_chain, "post_chain_digest": state_digest_for(post_chain), "post_marker": post_marker, "post_marker_sha256": hashlib.sha256(_json_bytes(post_marker)).hexdigest(), "source": source, "target": target, "zero_dispatch": True, "preserved_plan_sha256": expected_plan_state_sha256}
    prior_branch, prior_head = from_branch, from_head
    created_branch: str | None = None
    try:
        with journal.transaction(chain_ids=[chain_id], state_paths=[chain_path, marker_path, spec_path, aborted_plan_path], expected_revision=expected_chain_revision, operation_id=operation_id, actor={"id": actor, "class": "operator"}) as txn:
            locked_chain_raw, locked_chain = _load_json_bytes(chain_path, label="chain state")
            locked_plan_raw, _ = _load_json_bytes(aborted_plan_path, label="aborted C2 plan")
            locked_marker_raw, _ = _load_json_bytes(marker_path, label="session marker")
            _assert_hash(locked_chain_raw, expected_chain_state_sha256, label="locked chain-state SHA-256")
            _assert_hash(locked_plan_raw, expected_plan_state_sha256, label="locked plan-state SHA-256")
            _assert_hash(locked_marker_raw, expected_marker_sha256, label="locked marker SHA-256")
            if not journal.is_bound(chain_id):
                physical = [item for item in read_physical_lines(journal.ledger.events_path) if not item.torn]
                last = next((item for item in reversed(physical) if not str(item.record.get("kind") or "").startswith("chain_control.")), None)
                tip = -1 if last is None else last.record.get("seq")
                digest = "0" * 64 if last is None else physical_digest_after(journal.ledger_id, physical, upto_seq=int(tip))
                journal.append_under_lock(txn, event_kind="chain_control.genesis_accepted", chain_id=chain_id, operation_id="genesis-" + chain_id, causation_id="genesis-" + chain_id, correlation_id="genesis-" + chain_id, payload={"prefix_tip_seq": tip, "prefix_digest": digest, "authority_mode": "file", "schema_version": "nbf08-chain-control-v1"}, semantic_effect="no_change", claim_class="required", actor={"id": actor, "class": "operator"}, outcome="committed", spec_identity=str(spec_path), source_identity=binding)
            intent = pending_intent or journal.append_under_lock(txn, event_kind="chain_control.intent", chain_id=chain_id, operation_id=operation_id, causation_id=operation_id, correlation_id=operation_id, payload={"schema": effect["schema"], "effect": effect}, semantic_effect="no_change", claim_class="required", actor={"id": actor, "class": "operator"}, intent="cutover-paused-checkout", outcome="pending", expected_cursor=expected_cursor, expected_revision=expected_chain_revision, source_identity=source, spec_identity=str(spec_path), pre_state_digest=effect["pre_chain_digest"], post_state_digest=effect["post_chain_digest"])
            if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
                created_branch = to_branch if _checkout_target(project_root, branch=to_branch, head=to_head) else None
            if _current_branch(project_root) != to_branch or _current_head(project_root) != to_head:
                refuse("target checkout postcondition diverged")
            if sha256_path(spec_path) != target_spec_sha256:
                refuse("target chain spec SHA-256 does not match its guard")
            target_spec = chain_spec.load_spec(spec_path)
            if target_spec.milestones[expected_cursor].label != expected_current_milestone or target_spec.milestones[expected_cursor].branch not in (None, to_branch):
                refuse("target spec milestone or branch closure diverged")
            if failure_injector is not None:
                failure_injector("after_git_switch")
            final_chain_raw, _ = _load_json_bytes(chain_path, label="final chain state")
            final_plan_raw, _ = _load_json_bytes(aborted_plan_path, label="final aborted C2 plan")
            final_marker_raw, _ = _load_json_bytes(marker_path, label="final marker")
            _assert_hash(final_chain_raw, expected_chain_state_sha256, label="final chain-state SHA-256")
            _assert_hash(final_plan_raw, expected_plan_state_sha256, label="final plan-state SHA-256")
            _assert_hash(final_marker_raw, expected_marker_sha256, label="final marker SHA-256")
            ChainStateAdapter(txn, chain_path).cas_write(post_chain, expected_revision=expected_chain_revision)
            _atomic_write(marker_path, _json_bytes(post_marker))
            if failure_injector is not None:
                failure_injector("after_state_write")
            committed = journal.append_under_lock(txn, event_kind="chain_control.source_checkout_cutover", chain_id=chain_id, operation_id=operation_id, causation_id=str(intent.get("event_id") or operation_id), correlation_id=operation_id, payload={"schema": effect["schema"], "effect": effect}, semantic_effect="metadata_only", claim_class="required", actor={"id": actor, "class": "operator"}, outcome="committed", intent="cutover-paused-checkout", expected_cursor=expected_cursor, expected_revision=expected_chain_revision, actual_cursor=expected_cursor, actual_revision=post_chain["metadata"]["_nbf08_revision"], pre_state_digest=effect["pre_chain_digest"], post_state_digest=effect["post_chain_digest"], source_identity=source, spec_identity=str(spec_path), linked_receipts=[str(intent.get("event_id") or operation_id)])
            return {"outcome": "committed", "operation_id": operation_id, "receipt": committed, "project_source_binding": binding, "external_effect": False}
    except ChainControlHold:
        raise
    except Exception:
        # Keep the journal intent as the recovery authority.  If both
        # projections and the checkout already equal the recorded post-state,
        # preserve them so a later invocation can append the terminal receipt;
        # otherwise roll back the incomplete external effect.
        try:
            post_chain_raw, post_chain_now = _load_json_bytes(chain_path, label="post chain state")
            post_marker_raw, post_marker_now = _load_json_bytes(marker_path, label="post marker")
            post_state_present = (
                _current_branch(project_root) == to_branch
                and _current_head(project_root) == to_head
                and state_digest_for(post_chain_now) == effect["post_chain_digest"]
                and post_marker_now == effect["post_marker"]
            )
            if not post_state_present:
                if _current_branch(project_root) != prior_branch or _current_head(project_root) != prior_head:
                    _restore_git(project_root, branch=prior_branch, head=prior_head, created_branch=created_branch)
                _atomic_write(chain_path, chain_raw)
                _atomic_write(marker_path, marker_raw)
        except Exception:
            pass
        raise


def _binding_from_metadata(metadata: Any) -> Mapping[str, Any] | None:
    binding = metadata.get("project_source_binding") if isinstance(metadata, Mapping) else None
    return binding if isinstance(binding, Mapping) else None


def assert_plan_project_source_binding(
    project_root: Path,
    plan: Mapping[str, Any],
    *,
    operation: str,
) -> None:
    """Fail closed if a target-bound plan no longer contains its source."""

    metadata = plan.get("meta")
    binding = _binding_from_metadata(metadata)
    if binding is None:
        return
    current = binding.get("current")
    if not isinstance(current, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{operation}: source binding is malformed")
    branch = current.get("branch")
    head = current.get("head")
    if not isinstance(branch, str) or not isinstance(head, str):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{operation}: source binding is incomplete")
    observed_branch = _current_branch(project_root)
    observed_head = _current_head(project_root)
    if observed_branch != branch or not _is_ancestor(project_root, head, observed_head):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{operation}: checkout does not preserve the bound project source",
            extra={
                "bound_branch": branch,
                "bound_head": head,
                "observed_branch": observed_branch,
                "observed_head": observed_head,
            },
        )


def assert_chain_project_source_binding(
    project_root: Path,
    chain_state: Any,
    *,
    plan_name: str,
    operation: str,
) -> None:
    """Apply the chain-side branch/ancestor guard when a binding is present."""

    metadata = getattr(chain_state, "metadata", None)
    binding = _binding_from_metadata(metadata)
    if binding is None:
        return
    current = binding.get("current")
    if not isinstance(current, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{operation}: source binding is malformed")
    event_plan = None
    events = binding.get("rebind_events")
    if isinstance(events, list) and events and isinstance(events[-1], Mapping):
        event_plan = events[-1].get("plan")
    if event_plan not in {None, plan_name}:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{operation}: source binding owns another plan")
    plan_dir = find_plan_dir(project_root, plan_name)
    if plan_dir is None:
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, f"{operation}: plan directory is unavailable")
    _, plan = _load_json_bytes(plan_dir / "state.json", label="plan state")
    plan_binding = _binding_from_metadata(plan.get("meta"))
    if plan_binding != binding:
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"{operation}: chain and plan project-source bindings diverged",
        )
    assert_plan_project_source_binding(project_root, plan, operation=operation)


def publish_bound_project_source_branch(
    project_root: Path,
    chain_state: Any,
    *,
    plan_name: str,
    milestone_branch: str,
) -> str:
    """Publish a bound milestone branch without recreating it from chain base.

    The generic milestone checkout may fork a missing remote branch from the
    chain base or rebase an existing branch onto it.  Both are forbidden after
    target rebind.  This path permits only an ordinary fast-forward publication
    whose local and remote heads already contain the bound source.
    """

    assert_chain_project_source_binding(
        project_root,
        chain_state,
        plan_name=plan_name,
        operation=f"publish milestone branch {milestone_branch}",
    )
    binding = _binding_from_metadata(getattr(chain_state, "metadata", None))
    if binding is None:  # pragma: no cover - caller only routes bound states here
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "project-source binding is missing")
    current = binding.get("current")
    if not isinstance(current, Mapping):
        raise CliError(PROJECT_SOURCE_REBIND_ERROR, "project-source binding is malformed")
    bound_branch = current.get("branch")
    bound_head = current.get("head")
    if bound_branch != milestone_branch or not isinstance(bound_head, str):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "configured milestone branch does not match the bound project source",
        )
    local_head = _current_head(project_root)
    remote_ref = f"refs/heads/{milestone_branch}"
    advertised = _run_git(
        project_root,
        ["ls-remote", "--exit-code", "--heads", "origin", remote_ref],
        check=False,
        error=f"could not inspect remote milestone branch {milestone_branch}",
    )
    if advertised.returncode == 2 and not advertised.stdout.strip():
        _run_git(
            project_root,
            ["push", "--no-verify", "-u", "origin", milestone_branch],
            error=f"could not publish bound milestone branch {milestone_branch}",
        )
    elif advertised.returncode == 0:
        rows = [line.split() for line in advertised.stdout.splitlines() if line.strip()]
        exact = [row for row in rows if len(row) == 2 and row[1] == remote_ref]
        if len(exact) != 1 or _FULL_SHA.fullmatch(exact[0][0].lower()) is None:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"remote milestone branch {milestone_branch} is ambiguous",
            )
        remote_head = exact[0][0].lower()
        _fetch_advertised_ref(project_root, remote_ref, remote_head)
        if not _is_ancestor(project_root, bound_head, remote_head):
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                f"remote milestone branch {milestone_branch} drops bound source {bound_head}",
            )
        if remote_head != local_head:
            if not _is_ancestor(project_root, remote_head, local_head):
                raise CliError(
                    PROJECT_SOURCE_REBIND_ERROR,
                    f"remote milestone branch {milestone_branch} is not a fast-forward ancestor of local HEAD",
                )
            _run_git(
                project_root,
                ["push", "--no-verify", "origin", milestone_branch],
                error=f"could not fast-forward bound milestone branch {milestone_branch}",
            )
    else:
        detail = (advertised.stderr or advertised.stdout or "").strip()
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            f"could not inspect remote milestone branch {milestone_branch}: {detail}",
        )
    published = _remote_advertised_sha(project_root, remote_ref)
    if published != local_head or not _is_ancestor(project_root, bound_head, published):
        raise CliError(
            PROJECT_SOURCE_REBIND_ERROR,
            "published milestone branch does not exactly match the bound local HEAD",
        )
    return published


__all__ = [
    "PROJECT_SOURCE_BINDING_SCHEMA",
    "PROJECT_SOURCE_REBIND_ERROR",
    "PROJECT_SOURCE_REBIND_SCHEMA",
    "assert_chain_project_source_binding",
    "assert_plan_project_source_binding",
    "publish_bound_project_source_branch",
    "cutover_paused_checkout",
    "sha256_path",
    "target_rebind",
]
