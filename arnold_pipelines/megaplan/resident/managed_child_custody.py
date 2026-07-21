"""Append-only custody evidence for resident-managed child runs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any


MANAGED_CHILD_CUSTODY_EVENT_SCHEMA = "arnold-resident-managed-child-custody-event-v1"
_EVENT_KINDS = frozenset({"start", "terminal", "effect", "delivery_custody"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def managed_child_custody_path(
    manifest_path: Path, manifest: Mapping[str, Any] | None = None
) -> Path:
    declared = (
        str(manifest.get("custody_evidence_path") or "")
        if isinstance(manifest, Mapping)
        else ""
    )
    if declared:
        return Path(declared).resolve()
    return (manifest_path.parent / "managed-child-custody.jsonl").resolve()


def ensure_managed_child_custody_fields(
    manifest_path: Path, manifest: dict[str, Any]
) -> Path:
    path = managed_child_custody_path(manifest_path, manifest)
    manifest["custody_evidence_path"] = str(path)
    return path


def managed_child_delivery_projection(manifest: Mapping[str, Any]) -> dict[str, Any]:
    aggregation = (
        manifest.get("aggregation") if isinstance(manifest.get("aggregation"), Mapping) else {}
    )
    delivery = (
        manifest.get("completion_delivery")
        if isinstance(manifest.get("completion_delivery"), Mapping)
        else {}
    )
    run_id = str(manifest.get("run_id") or "")
    aggregation_role = str(aggregation.get("role") or "unknown")
    delivery_owner_run_id = str(
        aggregation.get("delivery_owner_run_id")
        or (run_id if aggregation_role == "synthesis_delivery_owner" else "")
    )
    delivery_status = str(delivery.get("status") or "")
    return {
        "aggregation_key": str(aggregation.get("key") or ""),
        "aggregation_role": aggregation_role,
        "delivery_owner_run_id": delivery_owner_run_id or None,
        "delivery_target_source_record_id": str(
            aggregation.get("delivery_target_source_record_id") or ""
        )
        or None,
        "delivery_status": delivery_status or None,
        "parent_owned_delivery": bool(
            aggregation_role != "synthesis_delivery_owner"
            or delivery_status in {"suppressed", "superseded"}
        ),
        "reply_target_source_record_id": (
            str(
                ((delivery.get("reply_target") or {}) if isinstance(delivery, Mapping) else {}).get(
                    "source_record_id"
                )
                or ""
            )
            or None
        ),
    }


def emit_managed_child_custody_event(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    *,
    event_kind: str,
    surface: str,
    evidence: str,
    at: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if event_kind not in _EVENT_KINDS:
        raise ValueError(f"unsupported managed-child custody event_kind: {event_kind}")
    occurred_at = at or utc_now()
    launch_provenance = (
        manifest.get("launch_provenance")
        if isinstance(manifest.get("launch_provenance"), Mapping)
        else {}
    )
    delivery = managed_child_delivery_projection(manifest)
    event: dict[str, Any] = {
        "schema_version": MANAGED_CHILD_CUSTODY_EVENT_SCHEMA,
        "event_kind": event_kind,
        "surface": surface,
        "evidence": evidence,
        "occurred_at": occurred_at,
        "run_id": str(manifest.get("run_id") or manifest_path.parent.name),
        "lineage_root_run_id": str(
            manifest.get("lineage_root_run_id")
            or manifest.get("root_run_id")
            or manifest.get("run_id")
            or manifest_path.parent.name
        ),
        "parent_run_id": str(manifest.get("parent_run_id") or "") or None,
        "custody_id": str(manifest.get("custody_id") or "") or None,
        "status": str(manifest.get("status") or "") or None,
        "terminal_outcome": str(manifest.get("terminal_outcome") or "") or None,
        "source_record_id": str(launch_provenance.get("source_record_id") or "") or None,
        "resident_conversation_id": str(
            launch_provenance.get("resident_conversation_id") or ""
        )
        or None,
        "conversation_key": str(launch_provenance.get("conversation_key") or "") or None,
        "discord_message_id": str(launch_provenance.get("discord_message_id") or "") or None,
        "reply_to_message_id": str(launch_provenance.get("reply_to_message_id") or "") or None,
        "delivery_custody": delivery,
        "details": dict(details or {}),
    }
    digest = hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    event["event_id"] = digest[:24]
    path = managed_child_custody_path(manifest_path, manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = manifest_path.parent / ".managed-child-custody.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        with path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(event, sort_keys=True) + "\n")
    return event
