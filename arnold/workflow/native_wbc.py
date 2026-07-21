"""Neutral append-only WBC evidence helper for native Arnold runtime surfaces.

This module lets neutral Arnold runtime/driver code emit durable evidence
without importing ``megaplan`` ownership logic.  It records append-only
NDJSON events under ``<artifact_root>/.native_wbc/`` while explicitly
preserving topology and manifest ownership outside the WBC payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import uuid
from typing import Any, Mapping

import fcntl

NATIVE_WBC_SCHEMA = "arnold.workflow.native_wbc.v1"
_NATIVE_WBC_ROOT = ".native_wbc"

__all__ = [
    "NATIVE_WBC_SCHEMA",
    "NativeWbcAttempt",
    "begin_native_wbc_attempt",
    "native_wbc_dir",
]


def native_wbc_dir(
    evidence_root: str | Path,
    *,
    producer_family: str,
    surface: str,
) -> Path:
    """Return the directory holding append-only evidence for one surface."""

    return (
        Path(evidence_root)
        / _NATIVE_WBC_ROOT
        / _sanitize_segment(producer_family)
        / _sanitize_segment(surface)
    )


@dataclass
class NativeWbcAttempt:
    """Append-only attempt recorder for one neutral runtime boundary."""

    evidence_root: Path | None
    producer_family: str
    surface: str
    attempt_id: str
    run_id: str = ""
    plugin_id: str = ""
    manifest_hash: str = ""
    topology_owner: str = "native_topology"
    manifest_owner: str = "native_manifest"
    subject: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    _closed: bool = field(default=False, init=False, repr=False)

    def start(self, payload: Mapping[str, Any] | None = None) -> None:
        self._append("started", payload or {})

    def effect(self, name: str, payload: Mapping[str, Any] | None = None) -> None:
        self._append_named("effect", name, payload)

    def effect_intent(self, name: str, payload: Mapping[str, Any] | None = None) -> None:
        self._append_named("effect_intent", name, payload)

    def effect_outcome(
        self,
        name: str,
        *,
        status: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        body = {"status": status}
        if payload:
            body["payload"] = _jsonable(dict(payload))
        self._append_named("effect_outcome", name, body)

    def resume(self, name: str, payload: Mapping[str, Any] | None = None) -> None:
        self._append_named("resume", name, payload)

    def reconciliation(
        self,
        name: str,
        *,
        outcome: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        body = {"outcome": outcome}
        if payload:
            body["payload"] = _jsonable(dict(payload))
        self._append_named("reconciliation", name, body)

    def terminal(
        self,
        *,
        status: str,
        outcome: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if self._closed:
            return
        body = {
            "status": status,
            "outcome": outcome,
            "payload": _jsonable(dict(payload or {})),
        }
        self._append("terminal", body)
        self._closed = True

    def _append(self, event: str, payload: Mapping[str, Any]) -> None:
        if self.evidence_root is None:
            return
        directory = native_wbc_dir(
            self.evidence_root,
            producer_family=self.producer_family,
            surface=self.surface,
        )
        directory.mkdir(parents=True, exist_ok=True)
        seq_path = directory / ".events.seq"
        events_path = directory / "events.ndjson"
        sequence = _next_sequence(seq_path)
        record = {
            "schema": NATIVE_WBC_SCHEMA,
            "sequence": sequence,
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "attempt_id": self.attempt_id,
            "event": event,
            "producer_family": self.producer_family,
            "surface": self.surface,
            "run_id": self.run_id,
            "plugin_id": self.plugin_id,
            "manifest_hash": self.manifest_hash,
            "ownership": {
                "topology_owner": self.topology_owner,
                "manifest_owner": self.manifest_owner,
                "wbc_controls_topology": False,
                "wbc_controls_manifest": False,
            },
            "authority": {
                "grants_authority": False,
                "leases_authority": False,
            },
            "subject": _jsonable(dict(self.subject)),
            "metadata": _jsonable(dict(self.metadata)),
            "payload": _jsonable(dict(payload)),
        }
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")

    def _append_named(
        self,
        event: str,
        name: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        body = {"name": name}
        if payload:
            body["payload"] = _jsonable(dict(payload))
        self._append(event, body)


def begin_native_wbc_attempt(
    evidence_root: str | Path | None,
    *,
    producer_family: str,
    surface: str,
    run_id: str = "",
    plugin_id: str = "",
    manifest_hash: str = "",
    topology_owner: str = "native_topology",
    manifest_owner: str = "native_manifest",
    subject: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    attempt_id: str | None = None,
    start_payload: Mapping[str, Any] | None = None,
) -> NativeWbcAttempt:
    """Create an attempt and durably append its ``started`` event."""

    root = Path(evidence_root) if evidence_root not in {None, ""} else None
    attempt = NativeWbcAttempt(
        evidence_root=root,
        producer_family=producer_family,
        surface=surface,
        attempt_id=attempt_id or uuid.uuid4().hex,
        run_id=run_id,
        plugin_id=plugin_id,
        manifest_hash=manifest_hash,
        topology_owner=topology_owner,
        manifest_owner=manifest_owner,
        subject=dict(subject or {}),
        metadata=dict(metadata or {}),
    )
    attempt.start(start_payload)
    return attempt


def _next_sequence(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            raw = handle.read().strip()
            current = int(raw) if raw else 0
            nxt = current + 1
            handle.seek(0)
            handle.truncate()
            handle.write(str(nxt))
            handle.flush()
            return nxt
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _sanitize_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    return cleaned.strip("._") or "unknown"


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "to_json"):
        try:
            return _jsonable(value.to_json())
        except Exception:
            return repr(value)
    if hasattr(value, "__dict__"):
        try:
            return _jsonable(vars(value))
        except Exception:
            return repr(value)
    return repr(value)
