"""Execution-environment identity for megaplan workers.

This module resolves the path and git identity contract used by later
isolation/preflight code. It is intentionally side-effect free: persistence and
enforcement are layered on top by later runtime handlers.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from arnold.pipelines.megaplan.runtime.process import megaplan_engine_root
from arnold.pipelines.megaplan.types import CliError, PlanState

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
    engine_commit: str | None
    engine_signature: str
    engine_dirty: bool
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
    engine = git_provenance(resolved_engine_root)
    target = git_provenance(target_root, base_ref=_configured_base_ref(state))
    return ExecutionEnvironment(
        project_root=project_root,
        target_root=target_root,
        work_dir=work_dir,
        engine_root=resolved_engine_root,
        engine_commit=engine.head,
        engine_signature=engine.signature,
        engine_dirty=engine.dirty,
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
    """Merge resolved isolation evidence without replacing pinned provenance."""

    merged: dict[str, Any] = dict(metadata or {})
    existing = merged.get("engine_isolation")
    if not isinstance(existing, dict):
        existing = {}
    record = dict(existing)
    record.setdefault("schema_version", 1)
    record.setdefault("pinned", True)
    record.setdefault("created_phase", phase)
    record["last_observed_phase"] = phase
    for key, value in env.to_dict().items():
        if key in record and record[key] not in (None, "", value):
            drift = record.setdefault("drift", [])
            if isinstance(drift, list):
                drift.append(
                    {
                        "field": key,
                        "pinned": record[key],
                        "observed": value,
                        "phase": phase,
                    }
                )
            continue
        record.setdefault(key, value)
    merged["engine_isolation"] = record
    return merged


def isolation_engine_identity(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    return {
        "engine_root": record.get("engine_root"),
        "engine_commit": record.get("engine_commit"),
        "engine_signature": record.get("engine_signature"),
    }


def latest_engine_overlap_waiver(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    waiver_id = metadata.get("latest_engine_overlap_waiver_id")
    waivers = metadata.get("engine_overlap_waivers")
    if not isinstance(waivers, list):
        return None
    for waiver in reversed(waivers):
        if not isinstance(waiver, dict):
            continue
        if waiver_id is None or waiver.get("id") == waiver_id:
            return waiver
    return None


def preflight_phase(
    *,
    root: Path | str,
    state: PlanState,
    phase: str,
    engine_root: Path | str | None = None,
) -> ExecutionEnvironment:
    """Resolve/persist the isolation contract and fail on pinned engine drift."""

    env = resolve_execution_environment(root=root, state=state, engine_root=engine_root)
    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    _refuse_engine_pin_drift(meta, env, phase=phase)
    state["meta"] = merge_isolation_evidence(meta, env, phase=phase)
    return env


def preflight_mutating_phase(
    *,
    root: Path | str,
    state: PlanState,
    phase: str,
    engine_root: Path | str | None = None,
    now: datetime | str | None = None,
) -> ExecutionEnvironment:
    """Preflight a target-mutating phase before worker dispatch.

    Mutating phases may not run when the target/work tree overlaps the engine
    unless the latest scoped waiver is valid. A valid waiver is consumed on
    first use so later mutations must record a fresh operator decision.
    """

    env = preflight_phase(root=root, state=state, phase=phase, engine_root=engine_root)
    target_overlap = classify_path_overlap(env.target_root, env.engine_root)
    work_overlap = classify_path_overlap(env.work_dir, env.engine_root)
    if target_overlap == "disjoint" and work_overlap == "disjoint":
        return env

    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    waiver = latest_engine_overlap_waiver(meta)
    invalid_reason = _engine_overlap_waiver_invalid_reason(
        waiver,
        env,
        phase=phase,
        now=now,
    )
    if invalid_reason is not None:
        raise isolation_cli_error(
            "engine_target_overlap_requires_waiver",
            (
                "Mutating megaplan phase would grant write access to the engine. "
                "Run `megaplan override waive-engine-overlap --reason <reason>` "
                "only if this local overlap is intentional."
            ),
            env=env,
            extra={
                "phase": phase,
                "target_engine_overlap": target_overlap,
                "work_dir_engine_overlap": work_overlap,
                "latest_engine_overlap_waiver_id": waiver.get("id") if isinstance(waiver, dict) else None,
                "waiver_invalid_reason": invalid_reason,
                "waiver_action": "waive-engine-overlap",
            },
        )
    _consume_engine_overlap_waiver(meta, waiver, phase=phase, now=now)
    return env


def append_engine_overlap_waiver(
    metadata: dict[str, Any] | None,
    env: ExecutionEnvironment,
    *,
    reason: str,
    phase: str | None = None,
    source: str = "user",
    timestamp: str,
    expires_after_runs: int | None = None,
    target_root: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged: dict[str, Any] = dict(metadata or {})
    isolation = merged.get("engine_isolation")
    identity = isolation_engine_identity(isolation if isinstance(isolation, dict) else {})
    scoped_target_root = str(normalize_path(target_root)) if target_root is not None else str(env.target_root)
    run_limit = expires_after_runs if isinstance(expires_after_runs, int) and expires_after_runs > 0 else None
    basis = {
        "timestamp": timestamp,
        "reason": reason,
        "phase": phase or "",
        "source": source,
        "target_root": scoped_target_root,
        "work_dir": str(env.work_dir),
        "engine_root": str(env.engine_root),
        "engine_commit": env.engine_commit,
        "engine_signature": env.engine_signature,
        "pinned_engine_identity": identity,
        "expires_after_runs": run_limit,
    }
    digest = hashlib.sha256(
        json.dumps(basis, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    waiver = {
        "id": f"engine-overlap-waiver-{digest}",
        "action": "waive-engine-overlap",
        "timestamp": timestamp,
        "reason": reason,
        "phase": phase or None,
        "source": source,
        "scope": {
            "target_root": scoped_target_root,
            "work_dir": str(env.work_dir),
            "engine_root": str(env.engine_root),
        },
        "engine_identity": {
            "engine_commit": env.engine_commit,
            "engine_signature": env.engine_signature,
        },
        "pinned_engine_identity": identity,
        "expires_after_runs": run_limit,
        "remaining_runs": run_limit,
        "consumed_at": None,
        "consumed_by_phase": None,
        "last_consumed_at": None,
        "last_consumed_by_phase": None,
    }
    waivers = list(merged.get("engine_overlap_waivers") or [])
    if not any(isinstance(item, dict) and item.get("id") == waiver["id"] for item in waivers):
        waivers.append(waiver)
    merged["engine_overlap_waivers"] = waivers
    merged["latest_engine_overlap_waiver_id"] = waiver["id"]
    return merged, waiver


def _refuse_engine_pin_drift(metadata: dict[str, Any], env: ExecutionEnvironment, *, phase: str) -> None:
    record = metadata.get("engine_isolation")
    if not isinstance(record, dict):
        return
    drift: dict[str, dict[str, Any]] = {}
    for key, observed in (
        ("engine_root", str(env.engine_root)),
        ("engine_commit", env.engine_commit),
        ("engine_signature", env.engine_signature),
    ):
        pinned = record.get(key)
        if pinned not in (None, "", observed):
            drift[key] = {"pinned": pinned, "observed": observed}
    if drift:
        raise isolation_cli_error(
            "engine_pin_drift",
            "Megaplan engine identity changed since isolation evidence was pinned; refusing phase preflight",
            env=env,
            extra={
                "phase": phase,
                "drift": drift,
            },
        )


def _engine_overlap_waiver_invalid_reason(
    waiver: dict[str, Any] | None,
    env: ExecutionEnvironment,
    *,
    phase: str,
    now: datetime | str | None,
) -> str | None:
    if not isinstance(waiver, dict):
        return "missing"
    if waiver.get("action") != "waive-engine-overlap":
        return "wrong_action"
    if waiver.get("consumed_at"):
        remaining = waiver.get("remaining_runs")
        if not isinstance(remaining, int) or remaining <= 0:
            return "consumed"
    expires_at = waiver.get("expires_at")
    if isinstance(expires_at, str) and expires_at.strip():
        expiry = _parse_instant(expires_at)
        current = _parse_instant(now) if now is not None else datetime.now(timezone.utc)
        if expiry is None:
            return "invalid_expiry"
        if current > expiry:
            return "expired"
    waiver_phase = waiver.get("phase")
    if isinstance(waiver_phase, str) and waiver_phase and waiver_phase != phase:
        return "phase_mismatch"
    scope = waiver.get("scope")
    if not isinstance(scope, dict):
        return "scope_missing"
    expected_scope = {
        "target_root": str(env.target_root),
        "work_dir": str(env.work_dir),
        "engine_root": str(env.engine_root),
    }
    for key, expected in expected_scope.items():
        if scope.get(key) != expected:
            return f"scope_mismatch:{key}"
    identity = waiver.get("engine_identity")
    if not isinstance(identity, dict):
        return "engine_identity_missing"
    if identity.get("engine_signature") != env.engine_signature:
        return "engine_signature_mismatch"
    if identity.get("engine_commit") != env.engine_commit:
        return "engine_commit_mismatch"
    return None


def _consume_engine_overlap_waiver(
    metadata: dict[str, Any],
    waiver: dict[str, Any] | None,
    *,
    phase: str,
    now: datetime | str | None,
) -> None:
    if not isinstance(waiver, dict):
        return
    consumed_at = _format_instant(now)
    remaining = waiver.get("remaining_runs")
    if isinstance(remaining, int):
        next_remaining = max(0, remaining - 1)
        waiver["remaining_runs"] = next_remaining
        waiver["last_consumed_at"] = consumed_at
        waiver["last_consumed_by_phase"] = phase
        if next_remaining <= 0:
            waiver["consumed_at"] = consumed_at
            waiver["consumed_by_phase"] = phase
    else:
        waiver["consumed_at"] = consumed_at
        waiver["consumed_by_phase"] = phase
    waiver_id = waiver.get("id")
    waivers = metadata.get("engine_overlap_waivers")
    if isinstance(waivers, list):
        for item in waivers:
            if isinstance(item, dict) and item.get("id") == waiver_id:
                item.update(
                    {
                        "remaining_runs": waiver.get("remaining_runs"),
                        "last_consumed_at": waiver.get("last_consumed_at"),
                        "last_consumed_by_phase": waiver.get("last_consumed_by_phase"),
                        "consumed_at": waiver.get("consumed_at"),
                        "consumed_by_phase": waiver.get("consumed_by_phase"),
                    }
                )


def _parse_instant(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_instant(value: datetime | str | None) -> str:
    parsed = _parse_instant(value)
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
    from arnold.pipelines.megaplan.workers._impl import resolve_work_dir

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
