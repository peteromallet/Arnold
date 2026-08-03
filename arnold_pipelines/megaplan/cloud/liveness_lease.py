"""Container-neutral runner liveness leases.

The Discord resident and an isolated chain runner intentionally live in
different PID/tmux namespaces.  A PID miss in the resident is therefore not a
death observation.  The runner publishes this short-lived, identity-bound
lease into the shared workspace; observers validate it without probing the
foreign namespace.

The lease is a liveness fact only.  It grants no repair, relaunch, completion,
or notification authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "arnold.megaplan.runner_liveness_lease.v1"
DEFAULT_MARKER_DIR = Path("/workspace/.megaplan/cloud-sessions")
DEFAULT_INTERVAL_S = 5.0
DEFAULT_TTL_S = 20.0
MAX_LEASE_SPAN_S = 120.0
MAX_FUTURE_SKEW_S = 5.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def marker_binding(marker: Mapping[str, Any]) -> str:
    """Digest only immutable launch identity, not mutable status projections."""
    return _digest(
        {
            "session": str(marker.get("session") or ""),
            "workspace": str(marker.get("workspace") or ""),
            "remote_spec": str(marker.get("remote_spec") or ""),
            "run_kind": str(marker.get("run_kind") or ""),
            "identity_digest": str(marker.get("identity_digest") or ""),
            "started_at": str(marker.get("started_at") or ""),
        }
    )


def lease_path(session: str, *, marker_dir: Path = DEFAULT_MARKER_DIR) -> Path:
    return marker_dir / f"{session}.liveness-lease.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _proc_start_identity(pid: int) -> str | None:
    try:
        # Field 22 is starttime.  Parse after the final ')' because comm may
        # itself contain spaces or parentheses.
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        tail = raw.rsplit(")", 1)[1].strip().split()
        start_ticks = tail[19]
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        return f"{boot_id}:{start_ticks}"
    except (OSError, IndexError):
        # macOS and other non-/proc test hosts: bind to the kernel-reported
        # process start string.  Production Linux always uses boot-id+ticks.
        try:
            os.kill(pid, 0)
            proc = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            started = proc.stdout.strip()
            if proc.returncode == 0 and started:
                host = socket.gethostname()
                return f"portable-{hashlib.sha256(host.encode()).hexdigest()[:16]}:{started}"
        except (OSError, subprocess.SubprocessError):
            pass
        return None


def _process_is_runnable(pid: int) -> bool:
    """False for dead/zombie or externally stopped processes.

    An embedded publisher freezes with its owner automatically.  This explicit
    state check also keeps the standalone migration sidecar from renewing a
    lease for a SIGSTOP-paused target.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        state = raw.rsplit(")", 1)[1].strip().split()[0]
        return state not in {"T", "t", "Z", "X", "x"}
    except (OSError, IndexError):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def _namespace_id(kind: str, pid: int | str = "self") -> str:
    try:
        return os.readlink(f"/proc/{pid}/ns/{kind}")
    except OSError:
        return "unknown"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class LivenessLeasePublisher:
    """Renew a lease while one exact local process incarnation remains alive."""

    def __init__(
        self,
        session: str,
        *,
        marker_dir: Path = DEFAULT_MARKER_DIR,
        target_pid: int | None = None,
        interval_s: float = DEFAULT_INTERVAL_S,
        ttl_s: float = DEFAULT_TTL_S,
    ) -> None:
        self.session = session
        self.marker_dir = Path(marker_dir)
        self.target_pid = int(target_pid or os.getpid())
        self.interval_s = max(0.2, float(interval_s))
        self.ttl_s = min(MAX_LEASE_SPAN_S, max(self.interval_s * 2, float(ttl_s)))
        self.target_start_identity = _proc_start_identity(self.target_pid)
        if self.target_start_identity is None:
            raise RuntimeError(f"target process {self.target_pid} is not locally observable")
        self.lease_id = str(uuid.uuid4())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sequence = 0

    @property
    def path(self) -> Path:
        return lease_path(self.session, marker_dir=self.marker_dir)

    def _target_matches(self) -> bool:
        return (
            _proc_start_identity(self.target_pid) == self.target_start_identity
            and _process_is_runnable(self.target_pid)
        )

    def _payload(self, *, live: bool) -> dict[str, Any]:
        marker = _read_json(self.marker_dir / f"{self.session}.json")
        if str(marker.get("session") or "") != self.session:
            raise RuntimeError(f"canonical session marker missing for {self.session}")
        now = _utcnow()
        expires = now + timedelta(seconds=self.ttl_s) if live else now
        self._sequence += 1
        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "session": self.session,
            "marker_binding": marker_binding(marker),
            "workspace": str(marker.get("workspace") or ""),
            "remote_spec": str(marker.get("remote_spec") or ""),
            "lease_id": self.lease_id,
            "sequence": self._sequence,
            "status": "live" if live else "stopped",
            "generated_at": _iso(now),
            "expires_at": _iso(expires),
            "runner_container_id": socket.gethostname(),
            "pid_namespace_id": _namespace_id("pid"),
            "time_namespace_id": _namespace_id("time"),
            "host_boot_id": self.target_start_identity.split(":", 1)[0],
            "target_pid": self.target_pid,
            "target_process_start_identity": self.target_start_identity,
            "publisher_pid": os.getpid(),
            "publisher_process_start_identity": _proc_start_identity(os.getpid()),
            "authority": "runner-owned-liveness-only",
        }
        payload["record_digest"] = _digest(payload)
        return payload

    def publish_once(self, *, live: bool = True) -> None:
        if live and not self._target_matches():
            raise RuntimeError("bound target process incarnation is no longer live")
        _atomic_json(self.path, self._payload(live=live))

    def _run(self) -> None:
        while not self._stop.is_set() and self._target_matches():
            try:
                self.publish_once()
            except Exception:
                # A transient write failure must not kill the runner.  The old
                # lease expires and observers degrade to unknown.
                pass
            self._stop.wait(self.interval_s)

    def start(self) -> "LivenessLeasePublisher":
        self.publish_once()
        self._thread = threading.Thread(
            target=self._run,
            name=f"megaplan-liveness-{self.session}",
            daemon=True,
        )
        self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_s + 0.5))
        # Terminalize only our own lease generation.
        current = _read_json(self.path)
        if current.get("lease_id") == self.lease_id:
            try:
                self.publish_once(live=False)
            except Exception:
                pass


def observe_liveness_lease(
    marker: Mapping[str, Any],
    *,
    marker_dir: Path = DEFAULT_MARKER_DIR,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate the current runner lease; never convert invalidity into death."""
    session = str(marker.get("session") or "")
    path = lease_path(session, marker_dir=Path(marker_dir))
    raw = _read_json(path)
    base = {"state": "unknown", "live": False, "path": str(path), "reason": "lease absent"}
    if not raw:
        return base
    if raw.get("schema") != SCHEMA:
        return {**base, "state": "degraded", "reason": "unsupported lease schema"}
    supplied_digest = raw.get("record_digest")
    unsigned = dict(raw)
    unsigned.pop("record_digest", None)
    if supplied_digest != _digest(unsigned):
        return {**base, "state": "degraded", "reason": "lease digest mismatch"}
    if raw.get("session") != session or raw.get("marker_binding") != marker_binding(marker):
        return {**base, "state": "degraded", "reason": "lease launch identity mismatch"}
    generated = _parse_iso(raw.get("generated_at"))
    expires = _parse_iso(raw.get("expires_at"))
    if generated is None or expires is None:
        return {**base, "state": "degraded", "reason": "lease timestamp invalid"}
    observed = now or _utcnow()
    if generated > observed + timedelta(seconds=MAX_FUTURE_SKEW_S):
        return {**base, "state": "degraded", "reason": "lease generated in future"}
    if expires > generated + timedelta(seconds=MAX_LEASE_SPAN_S):
        return {**base, "state": "degraded", "reason": "lease span exceeds bound"}
    if raw.get("status") != "live" or expires <= observed:
        return {**base, "state": "expired", "reason": "runner lease expired or stopped"}
    return {
        "state": "live",
        "live": True,
        "path": str(path),
        "reason": "fresh identity-bound runner lease",
        "runner_container_id": raw.get("runner_container_id"),
        "pid_namespace_id": raw.get("pid_namespace_id"),
        "lease_id": raw.get("lease_id"),
        "sequence": raw.get("sequence"),
        "expires_at": raw.get("expires_at"),
    }


def start_from_environment() -> LivenessLeasePublisher | None:
    session = str(os.environ.get("ARNOLD_REPAIR_SESSION") or "").strip()
    if not session:
        return None
    marker_dir = Path(
        os.environ.get("ARNOLD_REPAIR_MARKER_DIR") or str(DEFAULT_MARKER_DIR)
    )
    try:
        return LivenessLeasePublisher(session, marker_dir=marker_dir).start()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a runner-owned liveness lease")
    parser.add_argument("publish", nargs="?")
    parser.add_argument("--session", required=True)
    parser.add_argument("--marker-dir", type=Path, default=DEFAULT_MARKER_DIR)
    parser.add_argument("--target-pid", type=int, default=os.getppid())
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--ttl", type=float, default=DEFAULT_TTL_S)
    args = parser.parse_args(argv)
    publisher = LivenessLeasePublisher(
        args.session,
        marker_dir=args.marker_dir,
        target_pid=args.target_pid,
        interval_s=args.interval,
        ttl_s=args.ttl,
    )
    try:
        publisher.start()
        while publisher._target_matches():
            time.sleep(min(1.0, publisher.interval_s))
    finally:
        publisher.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
