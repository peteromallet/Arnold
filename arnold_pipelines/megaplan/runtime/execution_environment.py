"""Execution-environment context for megaplan workers.

This module resolves the current project, target, work, and engine paths used
by runtime isolation code. The engine checkout is live process context, not a
plan-pinned identity.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
from arnold_pipelines.megaplan.types import CliError, PlanState

PathOverlap = Literal[
    "equal",
    "left_contains_right",
    "right_contains_left",
    "disjoint",
]


@dataclass(frozen=True, slots=True)
class GitProvenance:
    """Best-effort git identity for a repository-like path."""

    head: str | None
    base: str | None
    base_ref: str | None
    dirty: bool
    signature: str
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExecutionEnvironment:
    """Resolved absolute execution contract for a megaplan run."""

    project_root: Path
    target_root: Path
    work_dir: Path
    engine_root: Path
    target_head: str | None
    target_base: str | None
    target_base_ref: str | None
    target_fallback_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("project_root", "target_root", "work_dir", "engine_root"):
            data[key] = str(data[key])
        return data


def normalize_path(path: Path | str) -> Path:
    """Return an absolute, symlink-normalized path without requiring existence."""

    return Path(path).expanduser().resolve(strict=False)


def classify_path_overlap(left: Path | str, right: Path | str) -> PathOverlap:
    """Classify overlap using path components, avoiding string-prefix traps."""

    left_path = normalize_path(left)
    right_path = normalize_path(right)
    if left_path == right_path:
        return "equal"
    try:
        right_path.relative_to(left_path)
    except ValueError:
        pass
    else:
        return "left_contains_right"
    try:
        left_path.relative_to(right_path)
    except ValueError:
        return "disjoint"
    return "right_contains_left"


def paths_overlap(left: Path | str, right: Path | str) -> bool:
    return classify_path_overlap(left, right) != "disjoint"


def isolation_cli_error(
    code: str,
    message: str,
    *,
    env: ExecutionEnvironment | None = None,
    extra: dict[str, Any] | None = None,
) -> CliError:
    """Build a CliError with the resolved path contract attached."""

    details: dict[str, Any] = {}
    if env is not None:
        details.update(env.to_dict())
    if extra:
        details.update(extra)
    return CliError(code, message, extra=details)


def resolve_execution_environment(
    *,
    root: Path | str,
    state: PlanState,
    engine_root: Path | str | None = None,
) -> ExecutionEnvironment:
    """Resolve absolute path and git provenance for the current run."""

    project_root = normalize_path(root)
    target_root = _target_root_from_state(state, fallback=project_root)
    work_dir = _resolve_work_dir(state)
    resolved_engine_root = normalize_path(engine_root or megaplan_engine_root())
    target = git_provenance(target_root, base_ref=_configured_base_ref(state))
    return ExecutionEnvironment(
        project_root=project_root,
        target_root=target_root,
        work_dir=work_dir,
        engine_root=resolved_engine_root,
        target_head=target.head,
        target_base=target.base,
        target_base_ref=target.base_ref,
        target_fallback_reason=target.fallback_reason,
    )


def merge_isolation_evidence(
    metadata: dict[str, Any] | None,
    env: ExecutionEnvironment,
    *,
    phase: str,
) -> dict[str, Any]:
    """Merge current execution-environment evidence for operator/debug context."""

    merged: dict[str, Any] = dict(metadata or {})
    existing = merged.get("execution_environment")
    if not isinstance(existing, dict):
        existing = {}
    record = dict(existing)
    record.setdefault("schema_version", 1)
    record.setdefault("created_phase", phase)
    record["last_observed_phase"] = phase
    for key, value in env.to_dict().items():
        record[key] = value
    merged["execution_environment"] = record
    return merged


def preflight_phase(
    *,
    root: Path | str,
    state: PlanState,
    phase: str,
    engine_root: Path | str | None = None,
) -> ExecutionEnvironment:
    """Resolve/persist current execution context."""

    env = resolve_execution_environment(root=root, state=state, engine_root=engine_root)
    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    state["meta"] = merge_isolation_evidence(meta, env, phase=phase)
    return env


def preflight_mutating_phase(
    *,
    root: Path | str,
    state: PlanState,
    phase: str,
    engine_root: Path | str | None = None,
    now: Any | None = None,
) -> ExecutionEnvironment:
    """Preflight a target-mutating phase before worker dispatch."""

    del now
    env = preflight_phase(root=root, state=state, phase=phase, engine_root=engine_root)
    from arnold_pipelines.megaplan.chain.target_rebind import (
        assert_plan_project_source_binding,
    )

    assert_plan_project_source_binding(
        env.target_root,
        state,
        operation=f"{phase} preflight",
    )
    return env


def persist_plan_isolation_evidence(
    *,
    root: Path | str,
    state: PlanState,
    phase: str,
    engine_root: Path | str | None = None,
) -> ExecutionEnvironment:
    """Attach isolation evidence to plan metadata and return the resolved env."""

    env = resolve_execution_environment(root=root, state=state, engine_root=engine_root)
    meta = state.setdefault("meta", {})
    if isinstance(meta, dict):
        state["meta"] = merge_isolation_evidence(meta, env, phase=phase)
    return env


def git_provenance(path: Path | str, *, base_ref: str | None = None) -> GitProvenance:
    """Return stable git provenance, even when git metadata is unavailable."""

    repo = normalize_path(path)
    head_result = _git(repo, ["rev-parse", "HEAD"])
    head = head_result if head_result else None
    dirty = bool(_git(repo, ["status", "--porcelain"]))
    if head is None:
        reason = "git_metadata_unavailable"
        signature = _fallback_signature(repo, reason)
        return GitProvenance(
            head=None,
            base=None,
            base_ref=None,
            dirty=False,
            signature=signature,
            fallback_reason=reason,
        )

    selected_base_ref = base_ref or _discover_base_ref(repo)
    base: str | None = None
    fallback_reason: str | None = None
    if selected_base_ref:
        base = _git(repo, ["merge-base", "HEAD", selected_base_ref])
        if base is None:
            fallback_reason = f"merge_base_unavailable:{selected_base_ref}"
    else:
        fallback_reason = "base_ref_unavailable"

    status = _git(repo, ["status", "--porcelain=v1"]) or ""
    signature = _git_signature(head=head, status=status, fallback_reason=fallback_reason)
    return GitProvenance(
        head=head,
        base=base,
        base_ref=selected_base_ref,
        dirty=bool(status),
        signature=signature,
        fallback_reason=fallback_reason,
    )


def _target_root_from_state(state: PlanState, *, fallback: Path) -> Path:
    config = state.get("config") if isinstance(state, dict) else None
    if isinstance(config, dict):
        project_dir = config.get("project_dir")
        if project_dir:
            return normalize_path(str(project_dir))
    return fallback


def _resolve_work_dir(state: PlanState) -> Path:
    from arnold_pipelines.megaplan.workers._impl import resolve_work_dir

    return normalize_path(resolve_work_dir(state))


def _configured_base_ref(state: PlanState) -> str | None:
    config = state.get("config") if isinstance(state, dict) else None
    meta = state.get("meta") if isinstance(state, dict) else None
    for source in (config, meta):
        if not isinstance(source, dict):
            continue
        for key in ("target_base_ref", "base_ref", "base_branch"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _discover_base_ref(repo: Path) -> str | None:
    for ref in ("origin/main", "origin/master", "main", "master"):
        if _git(repo, ["rev-parse", "--verify", "--quiet", ref]) is not None:
            return ref
    return None


def _git(repo: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_signature(*, head: str, status: str, fallback_reason: str | None) -> str:
    payload = "\0".join([head, status, fallback_reason or ""])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fallback_signature(path: Path, reason: str) -> str:
    payload = f"{path}\0{reason}"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
