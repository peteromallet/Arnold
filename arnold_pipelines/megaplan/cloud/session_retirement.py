"""Fail-closed archival retirement for one redundant paused cloud chain session.

Retirement is intentionally narrower than pause or destroy.  It never stops a
process and never removes a workspace.  Instead it proves that one exact,
already-paused session is redundant with a distinct completed session, moves
only target-scoped registry artifacts into an audit archive, and writes a
durable tombstone plus a freshly observed postcondition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from arnold_pipelines.megaplan.chain.spec import _state_path_candidates_for
from arnold_pipelines.megaplan.cloud import status_snapshot
from arnold_pipelines.megaplan.cloud.session_markers import CANONICAL_SIDECAR_SUFFIXES


RETIREMENT_SCHEMA = "arnold.megaplan.cloud-session-retirement.v1"
_SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_TERMINAL_CHAIN_STATES = {"done", "completed"}
_RUNNER_TOKENS = (
    "arnold_pipelines.megaplan chain start",
    "arnold_pipelines.megaplan epic-chain start",
    "arnold-chain",
    "mp-chain",
)
_REPAIR_TOKENS = (
    "arnold-repair-loop",
    "arnold-meta-repair-loop",
    "arnold-kimi-goal-operator",
)

TmuxProbe = Callable[[str], bool | None]
ProcessProbe = Callable[[str, Path, Path], list[dict[str, Any]]]


class RetirementBlocked(RuntimeError):
    """A safety precondition was not proven."""

    def __init__(self, code: str, message: str, *, evidence: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = evidence


def retire_session(
    *,
    marker_dir: Path,
    session: str,
    expected_marker_sha256: str,
    superseded_by: str,
    expected_superseding_marker_sha256: str,
    completion_manifest: Path,
    completion_manifest_sha256: str,
    git_repo: Path,
    base_ref: str,
    landed_commits: Sequence[str],
    reason: str,
    actor: str,
    tmux_probe: TmuxProbe | None = None,
    process_probe: ProcessProbe | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Retire one exact paused session after proving every safety gate.

    The returned record is also persisted as ``tombstone.json``.  Calling the
    operation again with the same target returns that existing record without
    mutating any additional state.
    """

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    marker_dir = marker_dir.resolve()
    session = _validated_session(session, field="session")
    superseded_by = _validated_session(superseded_by, field="superseded_by")
    if superseded_by == session:
        raise RetirementBlocked("ambiguous_identity", "target and superseding session are identical")
    expected_marker_sha256 = _validated_sha(expected_marker_sha256, "expected marker SHA-256")
    expected_superseding_marker_sha256 = _validated_sha(
        expected_superseding_marker_sha256, "expected superseding marker SHA-256"
    )
    completion_manifest_sha256 = _validated_sha(
        completion_manifest_sha256, "completion manifest SHA-256"
    )
    if not reason.strip() or not actor.strip():
        raise RetirementBlocked("incomplete_evidence", "reason and actor must be non-empty")
    if not landed_commits:
        raise RetirementBlocked("incomplete_evidence", "at least one landed commit is required")

    existing = _existing_retirement(marker_dir, session, expected_marker_sha256)
    if existing is not None:
        supersession = existing.get("supersession_evidence") or {}
        if (
            supersession.get("session") != superseded_by
            or supersession.get("marker_sha256") != expected_superseding_marker_sha256
            or supersession.get("completion_manifest_sha256") != completion_manifest_sha256
        ):
            raise RetirementBlocked(
                "ambiguous_retirement_record",
                "existing retirement record does not match the requested supersession evidence",
            )
        fresh = status_snapshot.build_cloud_status_snapshot(marker_dir=marker_dir, now=now)
        status_path = _publish_fresh_status(marker_dir, fresh)
        return {
            **existing,
            "already_retired": True,
            "status_cache_refreshed": bool(status_path),
            "status_snapshot_path": str(status_path or ""),
        }

    marker_path = marker_dir / f"{session}.json"
    canonical_marker_path = marker_dir / f"{superseded_by}.json"
    marker, marker_sha = _load_fenced_marker(
        marker_path, expected_session=session, expected_sha256=expected_marker_sha256
    )
    canonical_marker, canonical_marker_sha = _load_fenced_marker(
        canonical_marker_path,
        expected_session=superseded_by,
        expected_sha256=expected_superseding_marker_sha256,
    )

    workspace, remote_spec = _marker_paths(marker, marker_path=marker_path)
    canonical_workspace, canonical_spec = _marker_paths(
        canonical_marker, marker_path=canonical_marker_path
    )
    _validate_distinct_assets(
        workspace=workspace,
        remote_spec=remote_spec,
        canonical_workspace=canonical_workspace,
        canonical_spec=canonical_spec,
    )
    _validate_target_pause(marker)
    target_chain_state_path, target_chain_state = _load_chain_state(remote_spec)
    _validate_zero_progress_paused_state(target_chain_state, workspace=workspace)

    manifest_path = completion_manifest.resolve(strict=True)
    manifest_sha = _sha256_path(manifest_path)
    if manifest_sha != completion_manifest_sha256:
        raise RetirementBlocked(
            "completion_manifest_mismatch",
            "completion manifest SHA-256 did not match the required evidence",
            evidence={"expected": completion_manifest_sha256, "actual": manifest_sha},
        )
    if _is_within(manifest_path, workspace):
        raise RetirementBlocked(
            "shared_asset_risk", "completion evidence is stored inside the target workspace"
        )
    manifest = _load_json_object(manifest_path, code="invalid_completion_manifest")
    manifest_labels = _validate_completion_manifest(manifest)
    canonical_chain_state_path, canonical_chain_state = _load_chain_state(canonical_spec)
    _validate_completed_superseder(canonical_chain_state, manifest_labels=manifest_labels)
    landed = _validate_landed_commits(git_repo.resolve(), base_ref, landed_commits)

    target_slug = str(marker.get("chain_slug") or "").strip()
    canonical_slug = str(canonical_marker.get("chain_slug") or "").strip()
    if not target_slug or target_slug != canonical_slug:
        raise RetirementBlocked(
            "ambiguous_identity", "target and superseding chain identities do not match"
        )

    _validate_no_shared_markers(
        marker_dir,
        session=session,
        superseded_by=superseded_by,
        workspace=workspace,
        remote_spec=remote_spec,
    )
    _validate_no_shared_index_reference(marker_dir, session)
    _validate_no_repair_queue_reference(marker_dir, session)

    tmux = (tmux_probe or _tmux_is_live)(session)
    if tmux is None:
        raise RetirementBlocked("ambiguous_runtime", "tmux liveness could not be determined")
    if tmux:
        raise RetirementBlocked("active_runner", "the target owns a live tmux session")
    processes = (process_probe or _owned_processes)(session, workspace, remote_spec)
    if processes:
        raise RetirementBlocked(
            "active_process", "the target owns or may own a live process", evidence=processes
        )
    pidfile_evidence = _validate_pidfiles(marker_dir, session)

    # Re-read the two marker fences immediately before the first mutation.
    _load_fenced_marker(marker_path, expected_session=session, expected_sha256=marker_sha)
    _load_fenced_marker(
        canonical_marker_path,
        expected_session=superseded_by,
        expected_sha256=canonical_marker_sha,
    )

    retirement_id = f"ret-{marker_sha[:20]}"
    record_dir = marker_dir / "retired" / session / retirement_id
    if record_dir.exists():
        raise RetirementBlocked("ambiguous_retirement_record", f"record path already exists: {record_dir}")
    artifacts_dir = record_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=False)
    retired_at = _iso(now)
    intent = {
        "schema_version": RETIREMENT_SCHEMA,
        "retirement_id": retirement_id,
        "status": "archiving",
        "session": session,
        "retired_at": retired_at,
        "actor": actor.strip(),
        "reason": reason.strip(),
        "target_marker_sha256": marker_sha,
    }
    _atomic_write_json(record_dir / "intent.json", intent)

    candidates = _target_scoped_artifacts(marker_dir, session)
    archived: list[dict[str, Any]] = []
    # Move the marker last.  An interrupted archive therefore remains visible
    # and fail-closed until all auxiliary artifacts are safe in the archive.
    candidates.sort(key=lambda path: path == marker_path)
    for source in candidates:
        if source.is_symlink() or not source.is_file():
            raise RetirementBlocked("ambiguous_artifact", f"unsafe target artifact: {source}")
        relative = _archive_relative_path(marker_dir, source)
        destination = artifacts_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = _sha256_path(source)
        size = source.stat().st_size
        os.replace(source, destination)
        archived.append(
            {
                "source_path": str(source),
                "archive_path": str(destination),
                "sha256": digest,
                "size": size,
            }
        )

    fresh = status_snapshot.build_cloud_status_snapshot(marker_dir=marker_dir, now=now)
    matches = [
        item
        for item in fresh.get("sessions", [])
        if isinstance(item, Mapping) and item.get("session") == session
    ]
    postcondition = {
        "observed_at": retired_at,
        "fresh_snapshot_source": fresh.get("source"),
        "target_present": bool(matches),
        "target_actionable_paused": any(item.get("status") == "paused" for item in matches),
        "target_marker_present": marker_path.exists(),
        "superseding_marker_present": canonical_marker_path.exists(),
    }
    if any(postcondition[key] for key in ("target_present", "target_actionable_paused", "target_marker_present")):
        raise RetirementBlocked("postcondition_failed", "target remained actionable after archival")
    if not postcondition["superseding_marker_present"]:
        raise RetirementBlocked("postcondition_failed", "superseding marker was modified")
    status_path = _publish_fresh_status(marker_dir, fresh)
    postcondition["status_cache_refreshed"] = bool(status_path)
    postcondition["status_snapshot_path"] = str(status_path or "")
    _atomic_write_json(record_dir / "postcondition.json", postcondition)

    record = {
        "schema_version": RETIREMENT_SCHEMA,
        "retirement_id": retirement_id,
        "status": "retired",
        "session": session,
        "retired_at": retired_at,
        "actor": actor.strip(),
        "reason": reason.strip(),
        "record_path": str(record_dir / "tombstone.json"),
        "archive_dir": str(record_dir),
        "identity": {
            "marker_sha256": marker_sha,
            "workspace": str(workspace),
            "remote_spec": str(remote_spec),
            "chain_state_path": str(target_chain_state_path),
            "chain_state_sha256": _sha256_path(target_chain_state_path),
            "current_plan": target_chain_state.get("current_plan_name"),
        },
        "supersession_evidence": {
            "session": superseded_by,
            "marker_path": str(canonical_marker_path),
            "marker_sha256": canonical_marker_sha,
            "workspace": str(canonical_workspace),
            "remote_spec": str(canonical_spec),
            "chain_state_path": str(canonical_chain_state_path),
            "chain_state_sha256": _sha256_path(canonical_chain_state_path),
            "completion_manifest_path": str(manifest_path),
            "completion_manifest_sha256": manifest_sha,
            "milestones": manifest_labels,
            "git_repo": str(git_repo.resolve()),
            "base_ref": landed["base_ref"],
            "base_sha": landed["base_sha"],
            "landed_commits": landed["commits"],
        },
        "safety": {
            "durably_paused": True,
            "zero_progress": True,
            "tmux_live": False,
            "owned_processes": [],
            "pidfiles": pidfile_evidence,
            "shared_marker_assets": False,
        },
        "archived_artifacts": archived,
        "postcondition": postcondition,
    }
    tombstone_path = record_dir / "tombstone.json"
    _atomic_write_json(tombstone_path, record)
    return {
        **record,
        "tombstone_sha256": _sha256_path(tombstone_path),
        "already_retired": False,
    }


def _validated_session(value: str, *, field: str) -> str:
    value = value.strip()
    if not _SESSION_RE.fullmatch(value):
        raise RetirementBlocked("ambiguous_identity", f"{field} is not a safe exact session name")
    return value


def _validated_sha(value: str, field: str) -> str:
    value = value.strip().lower()
    if not _SHA256_RE.fullmatch(value):
        raise RetirementBlocked("incomplete_evidence", f"{field} must be 64 lowercase hex characters")
    return value


def _load_fenced_marker(path: Path, *, expected_session: str, expected_sha256: str) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise RetirementBlocked("missing_marker", f"canonical marker is unavailable: {path}")
    actual_sha = _sha256_path(path)
    if actual_sha != expected_sha256:
        raise RetirementBlocked(
            "marker_changed",
            f"marker SHA-256 changed for {expected_session}",
            evidence={"expected": expected_sha256, "actual": actual_sha},
        )
    marker = _load_json_object(path, code="invalid_marker")
    if marker.get("session") != expected_session:
        raise RetirementBlocked(
            "ambiguous_identity", f"marker session does not exactly equal {expected_session!r}"
        )
    if marker.get("run_kind") != "chain":
        raise RetirementBlocked("ambiguous_identity", "retirement supports chain markers only")
    return marker, actual_sha


def _marker_paths(marker: Mapping[str, Any], *, marker_path: Path) -> tuple[Path, Path]:
    workspace_text = str(marker.get("workspace") or "").strip()
    spec_text = str(marker.get("remote_spec") or "").strip()
    if not workspace_text or not spec_text:
        raise RetirementBlocked("incomplete_evidence", f"marker lacks workspace/spec custody: {marker_path}")
    workspace = Path(workspace_text)
    remote_spec = Path(spec_text)
    if not workspace.is_absolute() or not remote_spec.is_absolute():
        raise RetirementBlocked("ambiguous_identity", "workspace and remote spec must be absolute")
    workspace = workspace.resolve(strict=True)
    remote_spec = remote_spec.resolve(strict=True)
    if not workspace.is_dir() or not remote_spec.is_file() or remote_spec.is_symlink():
        raise RetirementBlocked("incomplete_evidence", "workspace/spec custody is unavailable")
    if not _is_within(remote_spec, workspace):
        raise RetirementBlocked("shared_asset_risk", "remote spec is outside its session workspace")
    return workspace, remote_spec


def _validate_distinct_assets(*, workspace: Path, remote_spec: Path, canonical_workspace: Path, canonical_spec: Path) -> None:
    if workspace == canonical_workspace or remote_spec == canonical_spec:
        raise RetirementBlocked("shared_asset_risk", "target shares workspace or spec with superseding session")


def _validate_target_pause(marker: Mapping[str, Any]) -> None:
    pause = marker.get("operator_pause")
    if marker.get("should_run") is not False or not isinstance(pause, Mapping) or pause.get("active") is not True:
        raise RetirementBlocked("not_durably_paused", "target is not under an active durable operator pause")
    if not str(pause.get("reason") or "").strip() or not str(pause.get("paused_at") or "").strip():
        raise RetirementBlocked("incomplete_evidence", "durable pause evidence is incomplete")


def _load_chain_state(remote_spec: Path) -> tuple[Path, dict[str, Any]]:
    candidates = [path for path in _state_path_candidates_for(remote_spec) if path.is_file()]
    if len(candidates) != 1:
        raise RetirementBlocked(
            "ambiguous_identity",
            "exactly one chain state artifact must resolve",
            evidence=[str(path) for path in candidates],
        )
    path = candidates[0].resolve()
    return path, _load_json_object(path, code="invalid_chain_state")


def _validate_zero_progress_paused_state(chain_state: Mapping[str, Any], *, workspace: Path) -> None:
    if str(chain_state.get("last_state") or "").lower() != "paused":
        raise RetirementBlocked("not_durably_paused", "target chain state is not paused")
    if chain_state.get("completed") not in ([], None) or int(chain_state.get("current_milestone_index") or 0) != 0:
        raise RetirementBlocked("nonzero_progress", "retirement is limited to zero-progress duplicate chains")
    plan = str(chain_state.get("current_plan_name") or "").strip()
    if not plan or "/" in plan:
        raise RetirementBlocked("incomplete_evidence", "target current plan identity is unavailable")
    plan_state_path = workspace / ".megaplan" / "plans" / plan / "state.json"
    plan_state = _load_json_object(plan_state_path, code="missing_plan_state")
    if str(plan_state.get("current_state") or "").lower() != "paused":
        raise RetirementBlocked("not_durably_paused", "target plan state is not paused")


def _validate_completion_manifest(manifest: Mapping[str, Any]) -> list[str]:
    if manifest.get("schema") != "arnold.megaplan.chain_completion_manifest.v1":
        raise RetirementBlocked("invalid_completion_manifest", "unsupported completion manifest schema")
    milestones = manifest.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise RetirementBlocked("incomplete_evidence", "completion manifest has no milestones")
    labels: list[str] = []
    for item in milestones:
        if not isinstance(item, Mapping) or item.get("status") != "done":
            raise RetirementBlocked("incomplete_evidence", "every manifest milestone must be done")
        label = str(item.get("label") or "").strip()
        if not label or label in labels:
            raise RetirementBlocked("ambiguous_identity", "manifest milestone labels are missing or duplicated")
        labels.append(label)
    return labels


def _validate_completed_superseder(chain_state: Mapping[str, Any], *, manifest_labels: Sequence[str]) -> None:
    if str(chain_state.get("last_state") or "").lower() not in _TERMINAL_CHAIN_STATES:
        raise RetirementBlocked("incomplete_evidence", "superseding chain is not terminal-complete")
    if chain_state.get("current_plan_name") not in (None, ""):
        raise RetirementBlocked("incomplete_evidence", "superseding chain still names a current plan")
    completed = chain_state.get("completed")
    if not isinstance(completed, list):
        raise RetirementBlocked("incomplete_evidence", "superseding chain completed evidence is unavailable")
    completed_labels = [str(item.get("label") or "") for item in completed if isinstance(item, Mapping)]
    if completed_labels != list(manifest_labels):
        raise RetirementBlocked(
            "completion_evidence_mismatch",
            "superseding chain and completion manifest milestone labels differ",
            evidence={"chain": completed_labels, "manifest": list(manifest_labels)},
        )


def _validate_landed_commits(repo: Path, base_ref: str, commits: Sequence[str]) -> dict[str, Any]:
    if not (repo / ".git").exists() or not base_ref.strip():
        raise RetirementBlocked("incomplete_evidence", "git repository/base reference is unavailable")
    base_sha = _git(repo, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    landed: list[str] = []
    for commit in commits:
        full = _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", full, base_sha],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RetirementBlocked("unlanded_commit", f"commit is not an ancestor of {base_ref}: {commit}")
        landed.append(full)
    return {"base_ref": base_ref, "base_sha": base_sha, "commits": landed}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RetirementBlocked("incomplete_evidence", f"git evidence failed: git {' '.join(args)}")
    return value


def _validate_no_shared_markers(marker_dir: Path, *, session: str, superseded_by: str, workspace: Path, remote_spec: Path) -> None:
    conflicts: list[dict[str, str]] = []
    for path in sorted(marker_dir.glob("*.json")):
        if path.name in {f"{session}.json", f"{superseded_by}.json"} or any(
            path.name.endswith(suffix) for suffix in CANONICAL_SIDECAR_SUFFIXES
        ):
            continue
        try:
            value = _load_json_object(path, code="invalid_sibling_marker")
        except RetirementBlocked as exc:
            raise RetirementBlocked("ambiguous_identity", f"unreadable sibling marker: {path}") from exc
        other_workspace = str(value.get("workspace") or "").strip()
        other_spec = str(value.get("remote_spec") or "").strip()
        if other_workspace == str(workspace) or other_spec == str(remote_spec):
            conflicts.append({"path": str(path), "session": str(value.get("session") or "")})
    if conflicts:
        raise RetirementBlocked("shared_asset_risk", "another session marker shares target assets", evidence=conflicts)


def _validate_no_shared_index_reference(marker_dir: Path, session: str) -> None:
    index = marker_dir / "repair-data" / "index.json"
    if not index.exists():
        return
    payload = _load_json_object(index, code="invalid_repair_index")
    if _contains_exact_value(payload, session):
        raise RetirementBlocked("shared_asset_risk", "shared repair index still references target session")


def _validate_no_repair_queue_reference(marker_dir: Path, session: str) -> None:
    queue = marker_dir.parent / "repair-queue"
    if not queue.is_dir():
        return
    matches: list[str] = []
    for path in queue.rglob("*"):
        if not path.is_file():
            continue
        if session in path.name:
            matches.append(str(path))
            continue
        if path.suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if _contains_exact_value(payload, session):
                matches.append(str(path))
    if matches:
        raise RetirementBlocked("active_repair_custody", "repair queue references target session", evidence=matches)


def _validate_pidfiles(marker_dir: Path, session: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for path in sorted(marker_dir.glob(f"{session}.*.pid")):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise RetirementBlocked("ambiguous_runtime", f"unreadable target pidfile: {path}") from exc
        live = Path(f"/proc/{pid}").exists()
        evidence.append({"path": str(path), "pid": pid, "live": live})
        if live:
            raise RetirementBlocked("active_process", f"target pidfile names a live process: {path}")
    return evidence


def _tmux_is_live(session: str) -> bool | None:
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"={session}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    return result.returncode == 0


def _owned_processes(session: str, workspace: Path, remote_spec: Path) -> list[dict[str, Any]]:
    owned: list[dict[str, Any]] = []
    excluded = _process_ancestry(os.getpid())
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        if pid in excluded:
            continue
        try:
            cmdline = proc_dir.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            cwd = proc_dir.joinpath("cwd").resolve(strict=True)
        except (OSError, RuntimeError):
            cmdline = ""
            cwd = None
        cwd_owned = isinstance(cwd, Path) and _is_within(cwd, workspace)
        command_owned = (
            (str(remote_spec) in cmdline or str(workspace) in cmdline)
            and any(token in cmdline for token in _RUNNER_TOKENS)
        ) or (session in cmdline and any(token in cmdline for token in _REPAIR_TOKENS))
        if cwd_owned or command_owned:
            owned.append({"pid": pid, "cwd": str(cwd or ""), "command": cmdline[:500]})
    return sorted(owned, key=lambda item: item["pid"])


def _process_ancestry(pid: int) -> set[int]:
    result: set[int] = set()
    current = pid
    while current > 0 and current not in result:
        result.add(current)
        try:
            fields = Path(f"/proc/{current}/stat").read_text(encoding="utf-8").split()
            current = int(fields[3])
        except (OSError, ValueError, IndexError):
            break
    return result


def _target_scoped_artifacts(marker_dir: Path, session: str) -> list[Path]:
    paths = [marker_dir / f"{session}.json"]
    paths.extend(marker_dir / f"{session}{suffix}" for suffix in CANONICAL_SIDECAR_SUFFIXES)
    repair_data = marker_dir / "repair-data"
    paths.extend(
        [
            repair_data / f"{session}.repair-data.json",
            repair_data / f"{session}.needs-human.json",
        ]
    )
    return [path for path in paths if path.exists()]


def _archive_relative_path(marker_dir: Path, source: Path) -> Path:
    try:
        return source.relative_to(marker_dir)
    except ValueError as exc:
        raise RetirementBlocked("shared_asset_risk", f"artifact escapes marker directory: {source}") from exc


def _existing_retirement(marker_dir: Path, session: str, marker_sha: str) -> dict[str, Any] | None:
    root = marker_dir / "retired" / session
    records = sorted(root.glob("*/tombstone.json")) if root.is_dir() else []
    matches: list[dict[str, Any]] = []
    for path in records:
        try:
            record = _load_json_object(path, code="invalid_retirement_record")
        except RetirementBlocked:
            continue
        if record.get("session") == session and (
            record.get("identity") or {}
        ).get("marker_sha256") == marker_sha:
            matches.append(record)
    if len(matches) > 1:
        raise RetirementBlocked("ambiguous_retirement_record", "multiple retirement records match target")
    if len(matches) == 1:
        path = Path(str(matches[0].get("record_path") or ""))
        return {**matches[0], "tombstone_sha256": _sha256_path(path)}
    return None


def _contains_exact_value(value: Any, expected: str) -> bool:
    if isinstance(value, Mapping):
        return any(str(key) == expected or _contains_exact_value(item, expected) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_exact_value(item, expected) for item in value)
    return isinstance(value, str) and value == expected


def _load_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RetirementBlocked(code, f"JSON evidence unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise RetirementBlocked(code, f"JSON evidence is not an object: {path}")
    return value


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _publish_fresh_status(marker_dir: Path, fresh: Mapping[str, Any]) -> Path | None:
    """Publish the derived read model only for the canonical on-box registry."""

    if marker_dir != status_snapshot.DEFAULT_MARKER_DIR.resolve():
        return None
    return status_snapshot.write_cloud_status_snapshot(fresh)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker-dir", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--expect-marker-sha256", required=True)
    parser.add_argument("--superseded-by", required=True)
    parser.add_argument("--expect-superseding-marker-sha256", required=True)
    parser.add_argument("--completion-manifest", required=True)
    parser.add_argument("--completion-manifest-sha256", required=True)
    parser.add_argument("--git-repo", required=True)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--landed-commit", action="append", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--actor", default="operator")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = retire_session(
            marker_dir=Path(args.marker_dir),
            session=args.session,
            expected_marker_sha256=args.expect_marker_sha256,
            superseded_by=args.superseded_by,
            expected_superseding_marker_sha256=args.expect_superseding_marker_sha256,
            completion_manifest=Path(args.completion_manifest),
            completion_manifest_sha256=args.completion_manifest_sha256,
            git_repo=Path(args.git_repo),
            base_ref=args.base_ref,
            landed_commits=args.landed_commit,
            reason=args.reason,
            actor=args.actor,
        )
    except RetirementBlocked as exc:
        print(
            json.dumps(
                {"success": False, "error": exc.code, "message": str(exc), "evidence": exc.evidence},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps({"success": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
