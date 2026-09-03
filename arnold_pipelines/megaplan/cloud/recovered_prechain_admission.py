"""Read-only admission for an already recovered, pre-chain runtime.

The cloud bootstrap normally rejects every existing authority file.  A failed
pre-chain recovery is the one deliberately supported exception: it leaves a
runtime and a marker behind, but no chain state or live runner.  This module is
called by the source-bound runtime probe and only verifies that exception.  It
does not write marker, manifest, journal, or liveness data.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Mapping


_OCCUPANCY_KEYS = (
    "owner", "runner", "tmux_session", "chain_pid", "worker_pid",
    "fixer_owner", "fixer_pid",
)
_RECOVERY_SCHEMA = "arnold.megaplan.failed-prechain-recovery.v1"
_SHA40 = set("0123456789abcdef")
def _fail(message: str, code: int = 78) -> None:
    print(f"chain_runtime_recovery_admission: {message}", file=sys.stderr)
    raise SystemExit(code)


def _read_regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError:
        _fail(f"{label} is unavailable")
    if not stat.S_ISREG(info.st_mode):
        _fail(f"{label} is not a regular file")
    try:
        return path.read_bytes()
    except OSError:
        _fail(f"{label} is unreadable")
    raise AssertionError("unreachable")


def _json(path: Path, label: str) -> tuple[bytes, Mapping[str, Any]]:
    raw = _read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail(f"{label} is not valid JSON")
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a JSON object")
    return raw, value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _full_sha(value: Any, label: str, length: int) -> str:
    text = str(value or "").lower()
    if len(text) != length or any(ch not in _SHA40 for ch in text):
        _fail(f"{label} is not a full hexadecimal SHA")
    return text


def _regular_lock_path(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def _pid_dead(value: Any, label: str) -> None:
    if value in (None, "", 0, "0"):
        return
    try:
        pid = int(value)
    except (TypeError, ValueError):
        _fail(f"{label} is malformed")
    if pid <= 0:
        _fail(f"{label} is malformed")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    except PermissionError:
        _fail(f"{label} may still be live")
    except OSError:
        return
    _fail(f"{label} is still live")


def _parse_expiry(value: Any) -> _dt.datetime:
    if not isinstance(value, str) or not value.strip():
        _fail("liveness lease expiry is missing")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        _fail("liveness lease expiry is malformed")
    if parsed.tzinfo is None:
        _fail("liveness lease expiry has no timezone")
    return parsed.astimezone(_dt.timezone.utc)


def _event_has_recovery(events_path: Path, *, operation: str, new_sha: str,
                        generation: int, marker_sha: str, manifest_sha: str) -> bool:
    raw = _read_regular(events_path, "chain-control journal")
    found = False
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail("chain-control journal contains invalid JSON")
        if not isinstance(event, Mapping):
            _fail("chain-control journal contains a non-object event")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        if event.get("operation_id") != operation:
            continue
        if event.get("event_kind") not in {"chain_control.committed", "committed"}:
            continue
        if payload.get("outcome") not in {"committed", "recovered"} and event.get("outcome") not in {"committed", "recovered"}:
            continue
        effect = payload.get("effect")
        if not isinstance(effect, Mapping):
            effect = event.get("effect")
        if not isinstance(effect, Mapping):
            continue
        # Recovery versions have used both explicit source_new_sha and a
        # nested source object.  Accept only exact values, never assertions.
        source = effect.get("source")
        observed_new = effect.get("source_new_sha")
        if isinstance(source, Mapping):
            observed_new = source.get("new_sha", observed_new)
        if observed_new != new_sha:
            continue
        if effect.get("manifest_generation") != generation:
            continue
        if effect.get("manifest_sha256") != manifest_sha:
            continue
        if effect.get("marker_sha256") not in {marker_sha, None}:
            continue
        found = True
    return found


def _admit(*, manifest_path: Path, marker_path: Path, state_path: Path,
           runtime_src: str, session: str, slug: str,
           expected_spec: str | None, expected_workspace: str | None) -> None:
    # First distinguish an ordinary existing runtime (exit 77 means the shell
    # caller should retain the historical generic authority refusal).
    if not marker_path.exists():
        raise SystemExit(77)
    marker_raw, marker = _json(marker_path, "session marker")
    recovery = marker.get("failed_prechain_recovery")
    if recovery is None:
        raise SystemExit(77)
    if not isinstance(recovery, Mapping):
        _fail("failed-prechain recovery record is malformed")

    # These are sidecar locks.  In particular, never open the absent chain
    # state itself with O_CREAT: absence is part of the admission contract.
    workspace = str(marker.get("workspace") or expected_workspace or "")
    if not workspace:
        _fail("recovered marker has no chain workspace")
    workspace_path = Path(workspace)
    lease = marker_path.parent / f"{session}.liveness-lease.json"
    fence = marker_path.parent / f".{session}.liveness-fence.json"
    lease_lock = marker_path.parent / f"{session}.liveness-publisher.lock"
    fence_lock = marker_path.parent / f".{session}.liveness-fence.lock"
    ledger_lock = workspace_path / ".megaplan" / "incident-ledger" / ".recovery-admission.lock"
    lock_paths = [
        _regular_lock_path(manifest_path, ".lock"),
        _regular_lock_path(marker_path, ".runtime-cutover.lock"),
        _regular_lock_path(state_path, ".runtime-recovery.lock"),
        lease_lock,
        fence_lock,
        ledger_lock,
    ]
    with ExitStack() as stack:
        handles = []
        for lock_path in sorted({p.resolve(strict=False) for p in lock_paths}, key=str):
            try:
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                handle = stack.enter_context(lock_path.open("a+", encoding="utf-8"))
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handles.append(handle)
            except OSError:
                _fail("recovery admission lock is unavailable")

        # Re-read under the final lock boundary.  The initial read is only a
        # routing hint and is never used as authority.
        marker_raw, marker = _json(marker_path, "session marker")
        manifest_raw, manifest = _json(manifest_path, "runtime manifest")
        if state_path.exists():
            _fail("chain state exists")
        if marker.get("session") != session:
            _fail("session marker identity mismatch")
        if expected_spec and marker.get("remote_spec") != expected_spec:
            _fail("session marker spec identity mismatch")
        if expected_workspace and marker.get("workspace") != expected_workspace:
            _fail("session marker workspace identity mismatch")
        for key in ("bootstrap_manifest_path", "manifest_path"):
            if marker.get(key) not in (None, str(manifest_path)):
                _fail("session marker manifest identity mismatch")
        if marker.get("should_run") is not True:
            _fail("recovered marker is not runnable")
        if marker.get("operator_pause") not in (None, ""):
            _fail("operator pause is active")
        for key in _OCCUPANCY_KEYS:
            if marker.get(key) not in (None, "", 0, "0"):
                _fail(f"marker still has live occupancy: {key}")
        if marker.get("provider_receipt") not in (None, ""):
            _fail("provider has already dispatched")
        for key in ("pid", "supervisor_pid"):
            _pid_dead(marker.get(key), f"marker {key}")
        outcome = marker.get("launch_outcome")
        if not isinstance(outcome, Mapping) or outcome.get("status") != "failed" or outcome.get("code") not in {"failed", "launch_not_advanced"}:
            _fail("historical launch was not a failed pre-chain attempt")

        operation = _full_sha(recovery.get("operation_id"), "recovery operation", 64)
        new_sha = _full_sha(recovery.get("new_sha"), "recovery head", 40)
        if recovery.get("schema") not in (None, _RECOVERY_SCHEMA):
            _fail("recovery schema mismatch")
        if recovery.get("engine_runtime_after") != runtime_src:
            _fail("recovered runtime identity mismatch")
        if expected_workspace and recovery.get("chain_workspace") != expected_workspace:
            _fail("recovered workspace identity mismatch")
        try:
            generation = int(recovery.get("manifest_generation"))
        except (TypeError, ValueError):
            _fail("recovery manifest generation is malformed")
        if generation <= 0:
            _fail("recovery manifest generation is malformed")

        epic = manifest.get("epic")
        if not isinstance(epic, Mapping) or manifest.get("schema") != "1":
            _fail("runtime manifest is schema-invalid")
        if slug and manifest.get("epic_id") != slug:
            _fail("runtime manifest epic identity mismatch")
        if epic.get("runtime_root") != runtime_src or epic.get("expected_head") != new_sha:
            _fail("runtime manifest does not match recovered runtime")
        if manifest.get("generation") != generation:
            _fail("runtime manifest generation mismatch")
        recovery_manifest = recovery.get("archive_manifest")
        if not isinstance(recovery_manifest, Mapping):
            _fail("recovery archive manifest is missing")
        archive_path = Path(str(recovery_manifest.get("path") or ""))
        archive_raw = _read_regular(archive_path, "recovery archive manifest")
        archive_sha = _full_sha(recovery_manifest.get("sha256"), "archive manifest digest", 64)
        if _sha(archive_raw) != archive_sha:
            _fail("recovery archive manifest digest mismatch")
        _, archive = _json(archive_path, "recovery archive manifest")
        if archive.get("operation_id") not in (None, operation):
            _fail("recovery archive belongs to another operation")

        receipt_path = archive_path.parent / "recovery-receipt.json"
        _, receipt = _json(receipt_path, "recovery receipt")
        if receipt.get("operation_id") != operation or receipt.get("outcome") != "recovered":
            _fail("recovery receipt identity/outcome mismatch")
        receipt_manifest = receipt.get("manifest")
        receipt_marker = receipt.get("marker")
        if not isinstance(receipt_manifest, Mapping) or not isinstance(receipt_marker, Mapping):
            _fail("recovery receipt lacks identity bindings")
        if receipt_manifest.get("path") != str(manifest_path) or receipt_manifest.get("after_sha256") != _sha(manifest_raw) or receipt_manifest.get("generation") != generation:
            _fail("recovery receipt manifest binding mismatch")
        recovered_marker_sha = _full_sha(receipt_marker.get("after_sha256"), "recovery marker digest", 64)
        if receipt_marker.get("path") != str(marker_path):
            _fail("recovery receipt marker binding mismatch")
        receipt_source = receipt.get("source")
        if not isinstance(receipt_source, Mapping) or receipt_source.get("new_sha") != new_sha:
            _fail("recovery receipt source binding mismatch")
        if receipt.get("workspace") not in (None, workspace) or (receipt.get("engine_runtime") or {}).get("new_path") not in (None, runtime_src):
            _fail("recovery receipt runtime binding mismatch")

        events = workspace_path / ".megaplan" / "incident-ledger" / "events.jsonl"
        if not _event_has_recovery(events, operation=operation, new_sha=new_sha,
                                   generation=generation, marker_sha=recovered_marker_sha,
                                   manifest_sha=_sha(manifest_raw)):
            _fail("committed recovery journal evidence is missing or contradictory")

        lease_raw, lease_payload = _json(lease, "liveness lease")
        if lease_payload.get("session") != session or lease_payload.get("status") != "stopped":
            _fail("liveness lease is not stopped for this session")
        if expected_workspace and lease_payload.get("workspace") not in (None, expected_workspace):
            _fail("liveness lease workspace mismatch")
        if expected_spec and lease_payload.get("remote_spec") not in (None, expected_spec):
            _fail("liveness lease spec mismatch")
        if _parse_expiry(lease_payload.get("expires_at")) >= _dt.datetime.now(_dt.timezone.utc):
            _fail("liveness lease has not expired")
        if lease_payload.get("marker_binding") not in (None, f"sha256:{recovered_marker_sha}", recovered_marker_sha):
            _fail("liveness lease marker binding mismatch")
        for key in ("pid", "publisher_pid", "target_pid", "owner_pid", "runner_pid", "worker_pid"):
            _pid_dead(lease_payload.get(key), f"liveness lease {key}")

        fence_raw, fence_payload = _json(fence, "liveness fence")
        if fence_payload.get("session") != session:
            _fail("liveness fence session mismatch")
        if fence_payload.get("owner") not in (None, "", 0, "0") or fence_payload.get("status") not in (None, "stopped", "released", "expired"):
            _fail("liveness fence still has an owner")
        for key in ("pid", "publisher_pid", "target_pid", "owner_pid", "runner_pid", "worker_pid"):
            _pid_dead(fence_payload.get(key), f"liveness fence {key}")
        try:
            tmux = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True, text=True, check=False)
        except OSError:
            _fail("tmux liveness cannot be determined")
        if tmux.returncode == 0:
            _fail("tmux session is still live")
        if tmux.returncode != 1:
            _fail("tmux liveness cannot be determined")

        # A final byte check catches a concurrent writer that ignored the
        # advisory locks.  No admission path writes any of these authorities.
        if _read_regular(marker_path, "session marker") != marker_raw:
            _fail("session marker changed during admission")
        if _read_regular(lease, "liveness lease") != lease_raw:
            _fail("liveness lease changed during admission")
        if _read_regular(fence, "liveness fence") != fence_raw:
            _fail("liveness fence changed during admission")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("marker")
    parser.add_argument("state")
    parser.add_argument("runtime_src")
    parser.add_argument("session")
    parser.add_argument("slug")
    parser.add_argument("spec", nargs="?", default="")
    parser.add_argument("workspace", nargs="?", default="")
    args = parser.parse_args(argv)
    _admit(
        manifest_path=Path(args.manifest), marker_path=Path(args.marker),
        state_path=Path(args.state), runtime_src=args.runtime_src,
        session=args.session, slug=args.slug,
        expected_spec=args.spec or None, expected_workspace=args.workspace or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
