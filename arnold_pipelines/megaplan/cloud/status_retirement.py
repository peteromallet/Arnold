"""Identity-fenced retirement for stale deleted-workspace status projections.

This operation does not retire a chain, declare completion, or delete evidence.
It writes a tombstone for one exact marker revision after proving that the
marker-owned workspace is absent and no runner remains.  Status readers ignore
only that exact marker hash; any later marker change becomes visible again.
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


STATUS_RETIREMENT_SCHEMA = "arnold.megaplan.deleted-workspace-status-retirement.v1"
_SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
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


class StatusRetirementBlocked(RuntimeError):
    """A status-only retirement precondition was not proven."""

    def __init__(self, code: str, message: str, *, evidence: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.evidence = evidence


def status_retirement_matches(*, marker_dir: Path, marker_path: Path, session: str) -> bool:
    """Return true only when a valid tombstone fences this exact marker bytestring."""

    if not _SESSION_RE.fullmatch(session):
        return False
    try:
        marker_sha = _sha256_path(marker_path)
    except OSError:
        return False
    record_path = _record_dir(marker_dir, session, marker_sha) / "tombstone.json"
    if record_path.is_symlink() or not record_path.is_file():
        return False
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, Mapping):
        return False
    identity = record.get("identity")
    return bool(
        record.get("schema_version") == STATUS_RETIREMENT_SCHEMA
        and record.get("status") == "retired"
        and record.get("retirement_kind") == "deleted-workspace-status-only"
        and record.get("session") == session
        and isinstance(identity, Mapping)
        and identity.get("marker_sha256") == marker_sha
        and identity.get("marker_path") == str(marker_path)
    )


def retire_deleted_workspace_status(
    *,
    marker_dir: Path,
    session: str,
    expected_marker_sha256: str,
    reason: str,
    actor: str,
    tmux_probe: TmuxProbe | None = None,
    process_probe: ProcessProbe | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Tombstone one exact deleted-workspace marker in the status read model only."""

    marker_dir = marker_dir.resolve()
    session = _validated_session(session)
    expected_marker_sha256 = _validated_sha(expected_marker_sha256)
    if not reason.strip() or not actor.strip():
        raise StatusRetirementBlocked("incomplete_evidence", "reason and actor must be non-empty")
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    marker_path = marker_dir / f"{session}.json"
    record_dir = _record_dir(marker_dir, session, expected_marker_sha256)
    record_path = record_dir / "tombstone.json"
    if not marker_path.exists() and record_path.is_file():
        existing = _validated_existing_record(
            record_path, session=session, expected_marker_sha256=expected_marker_sha256
        )
        fresh, status_path = _refresh_status(marker_dir, observed_at)
        return {
            **existing,
            "already_retired": True,
            "tombstone_sha256": _sha256_path(record_path),
            "status_cache_refreshed": bool(status_path),
            "status_snapshot_path": str(status_path or ""),
            "fresh_target_present": _target_present(fresh, session),
        }
    marker, marker_sha = _load_fenced_marker(marker_path, session, expected_marker_sha256)
    workspace, remote_spec = _missing_marker_paths(marker, marker_path)

    existing = None
    if record_path.is_file():
        existing = _validated_existing_record(
            record_path, session=session, expected_marker_sha256=marker_sha
        )

    tmux_live = (tmux_probe or _tmux_is_live)(session)
    if tmux_live is None:
        raise StatusRetirementBlocked("ambiguous_runtime", "tmux liveness could not be determined")
    if tmux_live:
        raise StatusRetirementBlocked("active_runner", "the target owns a live tmux session")
    processes = (process_probe or _owned_processes)(session, workspace, remote_spec)
    if processes:
        raise StatusRetirementBlocked(
            "active_process", "the target owns or may own a live process", evidence=processes
        )
    pidfiles = _validate_pidfiles(marker_dir, session)

    # Re-read the identity fence immediately before the sole durable mutation.
    _load_fenced_marker(marker_path, session, marker_sha)
    retired_at = str((existing or {}).get("retired_at") or _iso(observed_at))
    record: dict[str, Any] = {
        "schema_version": STATUS_RETIREMENT_SCHEMA,
        "retirement_id": record_dir.name,
        "retirement_kind": "deleted-workspace-status-only",
        "status": "retiring",
        "session": session,
        "retired_at": retired_at,
        "actor": actor.strip(),
        "reason": reason.strip(),
        "record_path": str(record_path),
        "identity": {
            "marker_path": str(marker_path),
            "marker_sha256": marker_sha,
            "run_kind": marker.get("run_kind"),
            "chain_slug": marker.get("chain_slug"),
            "workspace": str(workspace),
            "remote_spec": str(remote_spec),
        },
        "safety": {
            "workspace_absent": True,
            "remote_spec_absent": True,
            "tmux_live": False,
            "owned_processes": [],
            "pidfiles": pidfiles,
        },
        "preservation": {
            "marker_preserved": True,
            "initiative_mutated": False,
            "completion_asserted": False,
            "unfinished_work_landed_asserted": False,
        },
    }
    _atomic_write_json(record_path, record)

    archived = _archive_active_projection(
        marker_dir=marker_dir,
        record_dir=record_dir,
        session=session,
        marker_path=marker_path,
    )
    repair_evidence = _repair_evidence(marker_dir, session)
    record["status"] = "retired"
    record["preservation"]["active_projection_archived"] = archived
    record["preservation"]["repair_evidence_preserved"] = repair_evidence
    _atomic_write_json(record_path, record)

    fresh, status_path = _refresh_status(marker_dir, observed_at)
    target_present = _target_present(fresh, session)
    if target_present:
        raise StatusRetirementBlocked(
            "postcondition_failed", "retired marker remained in the fresh status projection"
        )
    archived_marker = record_dir / "artifacts" / marker_path.name
    record["postcondition"] = {
        "observed_at": retired_at,
        "fresh_snapshot_source": fresh.get("source"),
        "target_present": False,
        "marker_present": marker_path.is_file(),
        "archived_marker_present": archived_marker.is_file(),
        "marker_sha256": _sha256_path(archived_marker),
        "status_cache_refreshed": bool(status_path),
        "status_snapshot_path": str(status_path or ""),
    }
    _atomic_write_json(record_path, record)
    return {
        **record,
        "already_retired": False,
        "tombstone_sha256": _sha256_path(record_path),
    }


def _record_dir(marker_dir: Path, session: str, marker_sha: str) -> Path:
    return marker_dir / "retired-status" / session / f"ret-{marker_sha[:20]}"


def _validated_existing_record(
    path: Path, *, session: str, expected_marker_sha256: str
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise StatusRetirementBlocked("ambiguous_retirement_record", f"unsafe tombstone: {path}")
    record = _load_json_object(path, code="invalid_retirement_record")
    identity = record.get("identity")
    if not (
        record.get("schema_version") == STATUS_RETIREMENT_SCHEMA
        and record.get("retirement_kind") == "deleted-workspace-status-only"
        and record.get("session") == session
        and isinstance(identity, Mapping)
        and identity.get("marker_sha256") == expected_marker_sha256
    ):
        raise StatusRetirementBlocked(
            "ambiguous_retirement_record", "existing tombstone does not match the exact target"
        )
    return record


def _validated_session(value: str) -> str:
    value = value.strip()
    if not _SESSION_RE.fullmatch(value):
        raise StatusRetirementBlocked("ambiguous_identity", "session is not a safe exact name")
    return value


def _validated_sha(value: str) -> str:
    value = value.strip().lower()
    if not _SHA256_RE.fullmatch(value):
        raise StatusRetirementBlocked(
            "incomplete_evidence", "expected marker SHA-256 must be 64 lowercase hex characters"
        )
    return value


def _load_fenced_marker(
    path: Path, session: str, expected_sha256: str
) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise StatusRetirementBlocked("missing_marker", f"canonical marker is unavailable: {path}")
    actual_sha = _sha256_path(path)
    if actual_sha != expected_sha256:
        raise StatusRetirementBlocked(
            "marker_changed",
            f"marker SHA-256 changed for {session}",
            evidence={"expected": expected_sha256, "actual": actual_sha},
        )
    marker = _load_json_object(path, code="invalid_marker")
    if marker.get("session") != session or marker.get("run_kind") != "chain":
        raise StatusRetirementBlocked(
            "ambiguous_identity", "marker does not identify the exact requested chain session"
        )
    return marker, actual_sha


def _missing_marker_paths(marker: Mapping[str, Any], marker_path: Path) -> tuple[Path, Path]:
    workspace_text = str(marker.get("workspace") or "").strip()
    spec_text = str(marker.get("remote_spec") or "").strip()
    if not workspace_text or not spec_text:
        raise StatusRetirementBlocked(
            "incomplete_evidence", f"marker lacks workspace/spec custody: {marker_path}"
        )
    workspace = Path(workspace_text)
    remote_spec = Path(spec_text)
    if not workspace.is_absolute() or not remote_spec.is_absolute():
        raise StatusRetirementBlocked("ambiguous_identity", "workspace and remote spec must be absolute")
    workspace = workspace.resolve(strict=False)
    remote_spec = remote_spec.resolve(strict=False)
    if not _is_within(remote_spec, workspace):
        raise StatusRetirementBlocked("shared_asset_risk", "remote spec is outside its session workspace")
    if workspace.is_symlink() or workspace.exists():
        raise StatusRetirementBlocked(
            "workspace_present", "status-only retirement requires a provably absent workspace"
        )
    if remote_spec.is_symlink() or remote_spec.exists():
        raise StatusRetirementBlocked(
            "workspace_present", "status-only retirement requires a provably absent remote spec"
        )
    return workspace, remote_spec


def _archive_active_projection(
    *, marker_dir: Path, record_dir: Path, session: str, marker_path: Path
) -> list[dict[str, Any]]:
    paths = [path for path in sorted(marker_dir.glob(f"{session}*")) if path.is_file()]
    paths.sort(key=lambda path: path == marker_path)
    archived: list[dict[str, Any]] = []
    for source in paths:
        if source.is_symlink():
            raise StatusRetirementBlocked("ambiguous_artifact", f"unsafe target artifact: {source}")
        destination = record_dir / "artifacts" / source.name
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
    archived_marker = record_dir / "artifacts" / marker_path.name
    if not archived_marker.is_file() or _sha256_path(archived_marker) != _sha256_path_from_records(
        archived, marker_path
    ):
        raise StatusRetirementBlocked("postcondition_failed", "marker archival was not durable")
    return archived


def _sha256_path_from_records(records: Sequence[Mapping[str, Any]], source: Path) -> str:
    matches = [str(item.get("sha256") or "") for item in records if item.get("source_path") == str(source)]
    if len(matches) != 1 or not _SHA256_RE.fullmatch(matches[0]):
        raise StatusRetirementBlocked("postcondition_failed", "marker archive receipt is unavailable")
    return matches[0]


def _repair_evidence(marker_dir: Path, session: str) -> list[dict[str, Any]]:
    paths: list[Path] = []
    repair_data = marker_dir / "repair-data" / f"{session}.repair-data.json"
    if repair_data.exists():
        paths.append(repair_data)
    evidence: list[dict[str, Any]] = []
    for path in paths:
        if path.is_file() and not path.is_symlink():
            evidence.append(
                {"path": str(path), "sha256": _sha256_path(path), "size": path.stat().st_size}
            )
    return evidence


def _validate_pidfiles(marker_dir: Path, session: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for path in sorted(marker_dir.glob(f"{session}.*.pid")):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise StatusRetirementBlocked("ambiguous_runtime", f"unreadable pidfile: {path}") from exc
        live = Path(f"/proc/{pid}").exists()
        evidence.append({"path": str(path), "pid": pid, "live": live})
        if live:
            raise StatusRetirementBlocked("active_process", f"pidfile names a live process: {path}")
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
            cmdline = (
                proc_dir.joinpath("cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
                .strip()
            )
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


def _refresh_status(marker_dir: Path, now: datetime) -> tuple[dict[str, Any], Path | None]:
    from arnold_pipelines.megaplan.cloud import status_snapshot

    fresh = status_snapshot.build_cloud_status_snapshot(marker_dir=marker_dir, now=now)
    path = None
    if marker_dir == status_snapshot.DEFAULT_MARKER_DIR.resolve():
        path = status_snapshot.write_cloud_status_snapshot(fresh)
    return fresh, path


def _target_present(snapshot: Mapping[str, Any], session: str) -> bool:
    return any(
        isinstance(item, Mapping) and item.get("session") == session
        for item in snapshot.get("sessions", [])
    )


def _load_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatusRetirementBlocked(code, f"JSON evidence unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise StatusRetirementBlocked(code, f"JSON evidence is not an object: {path}")
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker-dir", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--expect-marker-sha256", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--actor", default="operator")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = retire_deleted_workspace_status(
            marker_dir=Path(args.marker_dir),
            session=args.session,
            expected_marker_sha256=args.expect_marker_sha256,
            reason=args.reason,
            actor=args.actor,
        )
    except StatusRetirementBlocked as exc:
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
