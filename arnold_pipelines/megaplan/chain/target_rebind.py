"""Guarded project-source cutover for an already materialized chain milestone.

Runtime and chain-spec bindings deliberately do not move the Git checkout that
an existing plan will mutate.  This module supplies that missing boundary.  It
is intentionally limited to a durable operator pause before execute and keeps
the launch-time chain target/base identity immutable.
"""

from __future__ import annotations

import fcntl
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
from typing import Any, Callable, Iterator, Mapping

from arnold_pipelines.megaplan._core.io import find_plan_dir
from arnold_pipelines.megaplan._core.state import driver_lock, plan_lock
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.operator_pause import (
    AUTHORITY_KEY,
    AUTHORITY_SCHEMA,
)
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
        "phase": "gate",
        "retry_strategy": "fresh_after_project_source_rebind",
        "project_source_rebind_sha256": event_sha256,
    }
    plan_pause = meta.get(AUTHORITY_KEY)
    if isinstance(plan_pause, dict):
        plan_pause["previous_current_state"] = "critiqued"
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
        chain_pause["previous_plan_state"] = "critiqued"
        chain_pause["previous_chain_last_state"] = "critiqued"
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
            assert_execution_binding,
        )

        assert_execution_binding(
            spec_path,
            chain_spec.ChainState.from_dict(chain),
            operation="chain target-rebind",
        )
        milestone_index, milestone = _milestone(
            spec,
            chain,
            expected_label=expected_current_milestone,
        )
        if chain.get("current_plan_name") != expected_current_plan:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "current plan does not match the guard")
        if plan.get("name") not in {None, expected_current_plan}:
            raise CliError(PROJECT_SOURCE_REBIND_ERROR, "plan state name does not match the guard")
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
        if observed_base != from_milestone_base or observed_base != from_head:
            raise CliError(
                PROJECT_SOURCE_REBIND_ERROR,
                "plan milestone base does not exactly match the guarded source HEAD",
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
        if existing_chain_binding != existing_plan_binding:
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
            _update_plan(
                plan,
                binding=binding,
                target_head=to_head,
                event_sha256=event["content_sha256"],
            )
            _update_chain(
                chain,
                binding=binding,
                target_head=to_head,
                event_sha256=event["content_sha256"],
            )
            _atomic_write(plan_path, _json_bytes(plan))
            if failure_injector is not None:
                failure_injector("after_plan_write")
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
    "sha256_path",
    "target_rebind",
]
