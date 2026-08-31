"""Authoritative identity resolution for non-worker supervision.

The shell wrappers are deliberately only projections of this module.  A
signal request is admissible only when its explicit session marker, immutable
runtime manifest and (for workers) ledger reservation still describe the same
target.  In particular, this module never selects a marker or manifest from
an environment variable or from an arbitrary JSON path supplied as data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold_pipelines.megaplan.cloud.runtime_manifest import bootstrap_manifest
from arnold_pipelines.megaplan.cloud.liveness_lease import tmux_authority_bindings
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerExecutionContextRef
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.watchdog.worker_identity import current_boot_identity, read_process_start_identity


class SignalAuthorityError(ValueError):
    """The supplied target cannot be bound to one authoritative incarnation."""


_TMUX_BINDING_KEYS = (
    "tmux_socket", "tmux_socket_fingerprint", "tmux_server_pid",
    "tmux_server_process_start_identity", "tmux_session_id",
    "tmux_owned_pane_id", "tmux_owned_pane_pid",
    "tmux_owned_pane_process_start_identity", "tmux_owned_pane_command",
    "tmux_all_panes_digest",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_digest(value: Any) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SignalAuthorityError(f"{field} is missing or invalid")
    return value.strip()


def _canonical_file(path: Path, *, label: str) -> tuple[Path, bytes]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SignalAuthorityError(f"{label} must be an existing non-symlink file")
    resolved = path.resolve(strict=True)
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise SignalAuthorityError(f"cannot read {label}: {exc}") from exc
    return resolved, data


def _marker_digest(payload: Mapping[str, Any]) -> str:
    """Digest marker content without its self-referential digest field."""
    unsigned = dict(payload)
    unsigned.pop("content_digest", None)
    unsigned.pop("marker_sha256", None)
    return _json_digest(unsigned)


def _manifest_path_within_authority(path: Path, workspace: Path) -> bool:
    """Allow the workspace-local manifest or the canonical per-epic store."""
    resolved = path.resolve(strict=False)
    roots = (workspace / ".megaplan", Path("/workspace/.megaplan"))
    return any(resolved == root or root in resolved.parents for root in roots)


@dataclass(frozen=True)
class SignalAuthorityContext:
    site_id: str
    target_kind: Literal["non_worker", "worker"]
    session: str
    marker_path: str
    marker_sha256: str
    workspace: str
    run_id: str
    manifest_path: str
    manifest_sha256: str
    runtime_id: str
    generation: int
    runtime_root: str
    expected_head: str
    ledger_root: str
    lifecycle_identity: str
    relevant_progress_identity: str
    supervisor_incarnation_identity: str
    victim_pid: int
    victim_process_start_identity: str
    worker_context: WorkerExecutionContextRef | None = None
    admission_receipt_id: str | None = None
    physical_door_id: str | None = None
    tmux_bindings: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "authority_version": 1,
            "site_id": self.site_id,
            "target_kind": self.target_kind,
            "session": self.session,
            "marker_path": self.marker_path,
            "marker_sha256": self.marker_sha256,
            "workspace": self.workspace,
            "run_id": self.run_id,
            "bootstrap_manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "runtime_id": self.runtime_id,
            "generation": self.generation,
            "runtime_root": self.runtime_root,
            "expected_head": self.expected_head,
            "ledger_root": self.ledger_root,
            "lifecycle_identity": self.lifecycle_identity,
            "relevant_progress_identity": self.relevant_progress_identity,
            "supervisor_incarnation_identity": self.supervisor_incarnation_identity,
            "victim_pid": self.victim_pid,
            "victim_process_start_identity": self.victim_process_start_identity,
        }
        if self.worker_context is not None:
            result["worker_context"] = self.worker_context.to_dict()
            result["admission_receipt_id"] = self.admission_receipt_id
            result["physical_door_id"] = self.physical_door_id
        if self.tmux_bindings:
            result.update(self.tmux_bindings)
        return result

    def validate_target_start(self) -> str:
        """Re-read the target incarnation immediately before a ledger write."""
        current = read_process_start_identity(self.victim_pid)
        if current != self.victim_process_start_identity:
            raise SignalAuthorityError("target process identity changed or is stale")
        return current or ""


def _load_marker(*, session: str, marker_path: Path, marker_dir: Path) -> tuple[dict[str, Any], str, Path]:
    session = _text(session, "session")
    root = marker_dir.expanduser().resolve(strict=False)
    if not marker_path.is_absolute():
        raise SignalAuthorityError("marker path must be absolute")
    if marker_path.name != f"{session}.json":
        raise SignalAuthorityError("marker filename is not bound to session")
    resolved, raw = _canonical_file(marker_path, label="session marker")
    if resolved.parent != root:
        raise SignalAuthorityError("marker is outside canonical session-marker directory")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SignalAuthorityError("session marker is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise SignalAuthorityError("session marker must be an object")
    if payload.get("session") != session:
        raise SignalAuthorityError("session marker identity mismatch")
    marker_digest = _marker_digest(payload)
    recorded = payload.get("content_digest", payload.get("marker_sha256"))
    if not isinstance(recorded, str) or recorded != marker_digest:
        raise SignalAuthorityError("session marker content digest is missing or invalid")
    return payload, marker_digest, resolved


def _resolve_manifest(marker: Mapping[str, Any], *, explicit: Path | None, workspace: Path) -> tuple[Path, str, Any]:
    raw_path = explicit if explicit is not None else marker.get("bootstrap_manifest_path", marker.get("manifest_path"))
    if isinstance(raw_path, Path):
        path = raw_path.expanduser()
    elif isinstance(raw_path, str) and raw_path:
        path = Path(raw_path).expanduser()
    else:
        raise SignalAuthorityError("bootstrap manifest path is missing")
    if not path.is_absolute():
        raise SignalAuthorityError("bootstrap manifest path must be absolute")
    if path.is_symlink():
        raise SignalAuthorityError("bootstrap path must not be a symlink")
    if not _manifest_path_within_authority(path, workspace):
        raise SignalAuthorityError("bootstrap path is outside marker-bound authority roots")
    try:
        # bootstrap_manifest is the sole resolver: it handles a directory
        # bootstrap, direct JSON manifest, and the canonical non-JSON pointer
        # form while applying compatibility-only demotion semantics.
        manifest = bootstrap_manifest(path)
    except Exception as exc:
        raise SignalAuthorityError(f"bootstrap manifest is invalid: {exc}") from exc
    if getattr(manifest, "compatibility_only", False):
        raise SignalAuthorityError("compatibility-only manifest cannot authorize signals")
    if path.is_dir():
        target = path / "runtime-manifest.json"
    elif path.name.endswith(".json"):
        target = path
    else:
        try:
            pointer = next(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#"))
        except (OSError, StopIteration) as exc:
            raise SignalAuthorityError("bootstrap pointer is empty or unreadable") from exc
        target = Path(pointer)
        if not target.is_absolute():
            target = path.parent / target
        if target.is_dir():
            target = target / "runtime-manifest.json"
    manifest_path, raw = _canonical_file(target, label="resolved bootstrap manifest")
    if not _manifest_path_within_authority(manifest_path, workspace):
        raise SignalAuthorityError("resolved bootstrap manifest is outside marker-bound authority roots")
    digest = _sha256(raw)
    recorded = marker.get("manifest_sha256", marker.get("bootstrap_manifest_sha256"))
    if not isinstance(recorded, str) or recorded != digest:
        raise SignalAuthorityError("bootstrap manifest content digest is missing or stale")
    if marker.get("runtime_id") != manifest.runtime_id or marker.get("generation") != manifest.generation:
        raise SignalAuthorityError("marker/runtime manifest incarnation mismatch")
    if "expected_head" in marker and marker.get("expected_head") != manifest.epic.get("expected_head"):
        raise SignalAuthorityError("marker/runtime expected head mismatch")
    return manifest_path, digest, manifest


def _resolve_progress(marker: Mapping[str, Any], workspace: Path) -> str:
    path_value = marker.get("progress_artifact")
    if not isinstance(path_value, str) or not path_value:
        raise SignalAuthorityError("operation-specific progress artifact is missing")
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SignalAuthorityError("progress artifact is missing or invalid")
    path = path.resolve(strict=True)
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise SignalAuthorityError("progress artifact is outside marker workspace") from exc
    digest = _sha256(path.read_bytes())
    expected = marker.get("progress_content_digest")
    if not isinstance(expected, str) or expected != digest:
        raise SignalAuthorityError("progress artifact content digest is missing or stale")
    identity = marker.get("progress_identity")
    if not isinstance(identity, str) or not identity:
        raise SignalAuthorityError("progress identity is missing")
    return f"{identity}:content:{digest}"


def _resolve_tmux(marker: Mapping[str, Any]) -> dict[str, Any] | None:
    """Revalidate an optional marker-owned tmux session and pane binding.

    Tmux is deliberately optional for non-tmux launches. Once a producer
    publishes any tmux field, however, a partial or stale set is not usable:
    the explicit socket/session/pane incarnation is queried again and every
    value must match before the marker can authorize a signal.
    """
    present = [key for key in _TMUX_BINDING_KEYS if key in marker]
    if not present:
        return None
    if len(present) != len(_TMUX_BINDING_KEYS):
        raise SignalAuthorityError("tmux authority binding is incomplete")
    try:
        fresh = tmux_authority_bindings(marker)
    except Exception as exc:
        raise SignalAuthorityError(f"tmux authority could not be revalidated: {exc}") from exc
    if not fresh or any(marker.get(key) != fresh.get(key) for key in _TMUX_BINDING_KEYS):
        raise SignalAuthorityError("tmux session or owned pane identity is stale or replaced")
    return dict(fresh)


def _resolve_worker_ref(marker: Mapping[str, Any], ledger: IncidentLedger, workspace: Path) -> tuple[WorkerExecutionContextRef, dict[str, Any]]:
    raw = marker.get("worker_context")
    if not isinstance(raw, Mapping):
        raise SignalAuthorityError("serialized worker execution context is missing")
    try:
        ref = WorkerExecutionContextRef.from_dict(raw)
    except (TypeError, ValueError) as exc:
        raise SignalAuthorityError(f"worker execution context is invalid: {exc}") from exc
    ledger_root = Path(ref.ledger_root).expanduser().resolve(strict=False)
    if ledger_root != workspace:
        raise SignalAuthorityError("worker ledger root is not marker-bound workspace")
    matches: list[dict[str, Any]] = []
    for event in ledger.read_nbf_events():
        payload = event.get("payload") or {}
        if payload.get("event_type") not in {"admission_reserved", "provider_route_child_reserved"}:
            continue
        if all(payload.get(key) == getattr(ref, key) for key in (
            "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id",
            "admission_receipt_id", "semantic_dispatch_fingerprint", "selected_spec", "physical_door_id",
        )):
            matches.append(payload)
    if len(matches) != 1:
        raise SignalAuthorityError("worker admission reservation is missing or ambiguous")
    return ref, matches[0]


def resolve_signal_authority(*, site_id: str, session: str, marker_path: Path, target_kind: Literal["non_worker", "worker"], victim_pid: int, marker_dir: Path, victim_process_start_identity: str | None = None, bootstrap_manifest_path: Path | None = None, allow_missing_target: bool = False) -> SignalAuthorityContext:
    """Resolve one explicit target against current authoritative sources."""
    if target_kind not in {"non_worker", "worker"}:
        raise SignalAuthorityError("target kind is invalid")
    if not isinstance(victim_pid, int) or isinstance(victim_pid, bool) or victim_pid <= 0:
        raise SignalAuthorityError("victim PID is invalid")
    site = _text(site_id, "site_id")
    marker, marker_sha, canonical_marker = _load_marker(session=session, marker_path=marker_path, marker_dir=marker_dir)
    workspace_value = _text(marker.get("workspace"), "workspace")
    workspace = Path(workspace_value).expanduser()
    if not workspace.is_absolute() or not workspace.is_dir() or workspace.is_symlink():
        raise SignalAuthorityError("marker workspace is missing or invalid")
    workspace = workspace.resolve(strict=True)
    manifest_path, manifest_sha, manifest = _resolve_manifest(marker, explicit=bootstrap_manifest_path, workspace=workspace)
    runtime_root = Path(_text(manifest.epic.get("runtime_root"), "manifest epic.runtime_root")).expanduser()
    expected_head = _text(manifest.epic.get("expected_head"), "manifest epic.expected_head")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise SignalAuthorityError("manifest epic.expected_head is not a canonical git identity")
    if not runtime_root.is_absolute() or not runtime_root.exists():
        raise SignalAuthorityError("manifest runtime root is missing")
    runtime_root = runtime_root.resolve(strict=True)
    try:
        runtime_root.relative_to(workspace)
    except ValueError as exc:
        raise SignalAuthorityError("manifest runtime root is outside marker workspace") from exc
    try:
        head = subprocess.run(
            ["git", "-C", str(runtime_root), "rev-parse", "--verify", "HEAD"],
            check=False, capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SignalAuthorityError(f"runtime repository HEAD cannot be verified: {exc}") from exc
    if head.returncode != 0 or head.stdout.strip() != expected_head:
        raise SignalAuthorityError("manifest expected_head does not match runtime repository HEAD")
    try:
        pid_start = read_process_start_identity(victim_pid)
    except Exception:
        pid_start = None
    expected = victim_process_start_identity or marker.get("victim_process_start_identity") or pid_start
    if not isinstance(expected, str) or not expected or (pid_start != expected and not (allow_missing_target and pid_start is None)):
        raise SignalAuthorityError("victim process identity is missing or stale")
    progress = _resolve_progress(marker, workspace)
    tmux = _resolve_tmux(marker)
    supervisor_pid = marker.get("supervisor_pid")
    supervisor_start = _text(marker.get("supervisor_process_start_identity"), "supervisor process-start identity")
    boot = _text(marker.get("boot_identity"), "boot identity")
    container = _text(marker.get("container_identity"), "container identity")
    if not isinstance(supervisor_pid, int) or supervisor_pid <= 0:
        raise SignalAuthorityError("supervisor PID is missing")
    try:
        current_supervisor_start = read_process_start_identity(supervisor_pid)
    except Exception:
        current_supervisor_start = None
    if current_supervisor_start != supervisor_start:
        raise SignalAuthorityError("supervisor process identity is stale or replaced")
    observed_boot = current_boot_identity()
    if not observed_boot or observed_boot != boot:
        raise SignalAuthorityError("boot identity is stale or mismatched")
    observed_container = os.environ.get("ARNOLD_CONTAINER_IDENTITY") or socket.gethostname()
    if not observed_container or observed_container != container:
        raise SignalAuthorityError("container identity is stale or mismatched")
    lifecycle = _json_digest({"version": 1, "site": site, "session": session, "run_id": _text(marker.get("run_id"), "run_id"), "marker": marker_sha, "manifest": manifest_sha, "runtime_id": manifest.runtime_id, "generation": manifest.generation})
    supervisor = _json_digest({"version": 1, "site": site, "session": session, "pid": supervisor_pid, "start": supervisor_start, "boot": boot, "container": container, "runtime_id": manifest.runtime_id, "generation": manifest.generation})
    ledger_root = workspace
    if not (ledger_root / ".megaplan" / "incident-ledger").is_dir():
        raise SignalAuthorityError("marker-bound incident ledger is missing")
    ledger = IncidentLedger(ledger_root)
    worker_ref = None
    reservation = None
    if target_kind == "worker":
        worker_ref, reservation = _resolve_worker_ref(marker, ledger, workspace)
    elif isinstance(marker.get("worker_context"), Mapping):
        raise SignalAuthorityError("worker context cannot authorize a non-worker target")
    return SignalAuthorityContext(
        site_id=site,
        target_kind=target_kind,
        session=session,
        marker_path=str(canonical_marker),
        marker_sha256=marker_sha,
        workspace=str(workspace),
        run_id=_text(marker.get("run_id"), "run_id"),
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_sha,
        runtime_id=manifest.runtime_id,
        generation=manifest.generation,
        runtime_root=str(runtime_root),
        expected_head=expected_head,
        ledger_root=str(ledger_root),
        lifecycle_identity=lifecycle,
        relevant_progress_identity=progress,
        supervisor_incarnation_identity=supervisor,
        victim_pid=victim_pid,
        victim_process_start_identity=expected,
        worker_context=worker_ref,
        admission_receipt_id=reservation.get("admission_receipt_id") if reservation else None,
        physical_door_id=reservation.get("physical_door_id") if reservation else None,
        tmux_bindings=tmux,
    )


def revalidate_signal_payload(payload: Mapping[str, Any], *, marker_dir: Path, ledger_root: Path | None = None, allow_missing_target: bool = False) -> SignalAuthorityContext:
    """Reload all authority sources for the CLI; payload fields are assertions."""
    required = ("site_id", "session", "marker_path", "target_kind", "victim_pid", "victim_process_start_identity")
    if any(key not in payload for key in required):
        raise SignalAuthorityError("signal payload lacks explicit authority context")
    context = resolve_signal_authority(
        site_id=payload["site_id"], session=payload["session"], marker_path=Path(payload["marker_path"]),
        target_kind=payload["target_kind"], victim_pid=int(payload["victim_pid"]), marker_dir=marker_dir,
        victim_process_start_identity=payload["victim_process_start_identity"],
        bootstrap_manifest_path=Path(payload["bootstrap_manifest_path"]) if payload.get("bootstrap_manifest_path") else None,
        allow_missing_target=allow_missing_target,
    )
    for key in ("lifecycle_identity", "relevant_progress_identity", "supervisor_incarnation_identity"):
        if payload.get(key) != getattr(context, key):
            raise SignalAuthorityError(f"signal payload {key} does not match authoritative context")
    authoritative = context.to_dict()
    for key in _TMUX_BINDING_KEYS:
        if key in payload and payload.get(key) != authoritative.get(key):
            raise SignalAuthorityError(f"signal payload {key} does not match authoritative tmux context")
    if ledger_root is not None and ledger_root.expanduser().resolve(strict=False) != Path(context.ledger_root):
        raise SignalAuthorityError("CLI ledger root does not match marker-bound ledger")
    return context


__all__ = ["SignalAuthorityError", "SignalAuthorityContext", "resolve_signal_authority", "revalidate_signal_payload"]
