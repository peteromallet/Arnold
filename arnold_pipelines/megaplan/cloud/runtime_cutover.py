"""CAS-protected cloud marker updates for content-addressed runtime cutovers."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.types import CliError


MARKER_RUNTIME_SCHEMA = "arnold.megaplan.marker_runtime_binding.v1"
MARKER_RUNTIME_REBIND_SCHEMA = "arnold.megaplan.marker_runtime_rebind.v1"
DEFAULT_OBSOLETE_FIELDS = ("engine_ref_check", "launch_command")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identity_core(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: identity.get(key)
        for key in (
            "import_root",
            "source_revision",
            "editable_root",
            "editable_revision",
            "direct_url",
            "pth",
            "imports",
        )
    }


def normalize_runtime_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    value = _identity_core(identity)
    value["content_sha256"] = _sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return value


def marker_runtime_identity(marker: Mapping[str, Any]) -> dict[str, Any] | None:
    binding = marker.get("runtime_binding")
    if isinstance(binding, Mapping) and isinstance(binding.get("current_identity"), Mapping):
        return normalize_runtime_identity(binding["current_identity"])
    sync = marker.get("editable_install_sync")
    sync = sync if isinstance(sync, Mapping) else {}
    source = str(sync.get("source") or "").strip()
    revision = str(marker.get("editable_source_head") or "").strip()
    if not source or len(revision) != 40:
        return None
    # Legacy markers did not retain direct_url/.pth/import facts. This minimal
    # identity is still content-addressed and makes the first migration auditable.
    return normalize_runtime_identity(
        {
            "import_root": source,
            "source_revision": revision,
            "editable_root": source,
            "editable_revision": revision,
            "direct_url": {},
            "pth": [],
            "imports": {},
        }
    )


def update_marker_runtime(
    marker_path: Path,
    *,
    expected_marker_sha256: str,
    expected_previous_runtime_sha256: str,
    active_runtime_identity: Mapping[str, Any],
    relaunch_command: str,
    reason: str,
    actor: str = "operator",
    direction: str = "cutover",
    source_branch: str = "",
    clear_fields: tuple[str, ...] = DEFAULT_OBSOLETE_FIELDS,
) -> dict[str, Any]:
    """Atomically update runtime custody only when marker and runtime guards match."""

    if direction not in {"cutover", "rollback"}:
        raise CliError("runtime_marker_invalid", "direction must be cutover or rollback")
    if len(expected_marker_sha256) != 64 or len(expected_previous_runtime_sha256) != 64:
        raise CliError("runtime_marker_invalid", "marker/runtime SHA-256 guards are required")
    if not relaunch_command.strip() or not reason.strip() or not actor.strip():
        raise CliError("runtime_marker_invalid", "relaunch command, reason, and actor are required")
    active = normalize_runtime_identity(active_runtime_identity)
    if not active.get("import_root") or len(str(active.get("source_revision") or "")) != 40:
        raise CliError("runtime_marker_invalid", "active runtime identity is incomplete")

    marker_path = marker_path.resolve(strict=False)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = marker_path.with_suffix(marker_path.suffix + ".runtime-cutover.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            before_bytes = marker_path.read_bytes()
        except OSError as exc:
            raise CliError("runtime_marker_missing", f"cannot read marker: {marker_path}") from exc
        observed_sha = _sha256(before_bytes)
        if observed_sha != expected_marker_sha256:
            raise CliError(
                "runtime_marker_cas_mismatch",
                f"marker changed: expected {expected_marker_sha256}, observed {observed_sha}",
            )
        try:
            marker = json.loads(before_bytes)
        except json.JSONDecodeError as exc:
            raise CliError("runtime_marker_invalid", "marker is not valid JSON") from exc
        if not isinstance(marker, dict):
            raise CliError("runtime_marker_invalid", "marker must be a JSON object")
        previous = marker_runtime_identity(marker)
        if previous is None:
            raise CliError("runtime_marker_invalid", "marker has no content-addressable runtime")
        if previous["content_sha256"] != expected_previous_runtime_sha256:
            raise CliError("runtime_marker_runtime_mismatch", "previous runtime SHA-256 does not match")

        changed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        event_core = {
            "schema": MARKER_RUNTIME_REBIND_SCHEMA,
            "changed_at": changed_at,
            "actor": actor,
            "reason": reason,
            "direction": direction,
            "from_runtime_sha256": previous["content_sha256"],
            "to_runtime_sha256": active["content_sha256"],
            "marker_before_sha256": observed_sha,
        }
        event = {
            **event_core,
            "content_sha256": _sha256(
                json.dumps(event_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
        }
        old_binding = marker.get("runtime_binding")
        old_binding = old_binding if isinstance(old_binding, Mapping) else {}
        events = old_binding.get("rebind_events")
        events = list(events) if isinstance(events, list) else []
        events.append(event)
        marker["runtime_binding"] = {
            "schema": MARKER_RUNTIME_SCHEMA,
            "current_identity": active,
            "last_rebound_at": changed_at,
            "rebind_events": events,
        }
        marker["editable_source_head"] = active["source_revision"]
        if source_branch:
            marker["editable_source_branch"] = source_branch
        else:
            marker.pop("editable_source_branch", None)
        marker["editable_install_sync"] = {
            "status": "content-addressed-runtime",
            "source": active["import_root"],
            "runtime_sha256": active["content_sha256"],
        }
        marker["relaunch_command"] = relaunch_command
        marker["updated_at"] = changed_at
        for field in clear_fields:
            marker.pop(field, None)

        encoded = (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(prefix=marker_path.name + ".", dir=str(marker_path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, marker_path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return {
            "marker_path": str(marker_path),
            "marker_before_sha256": observed_sha,
            "marker_after_sha256": _sha256(encoded),
            "event": event,
            "runtime_binding": marker["runtime_binding"],
            "cleared_fields": list(clear_fields),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--expect-marker-sha256", required=True)
    parser.add_argument("--from-runtime-sha256", required=True)
    parser.add_argument("--runtime-identity", type=Path, required=True)
    parser.add_argument("--relaunch-command-file", type=Path, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--actor", default="operator")
    parser.add_argument("--direction", choices=("cutover", "rollback"), default="cutover")
    parser.add_argument("--source-branch", default="")
    parser.add_argument("--clear-field", action="append", default=list(DEFAULT_OBSOLETE_FIELDS))
    args = parser.parse_args(argv)
    identity = json.loads(args.runtime_identity.read_text(encoding="utf-8"))
    result = update_marker_runtime(
        args.marker,
        expected_marker_sha256=args.expect_marker_sha256,
        expected_previous_runtime_sha256=args.from_runtime_sha256,
        active_runtime_identity=identity,
        relaunch_command=args.relaunch_command_file.read_text(encoding="utf-8").strip(),
        reason=args.reason,
        actor=args.actor,
        direction=args.direction,
        source_branch=args.source_branch,
        clear_fields=tuple(dict.fromkeys(args.clear_field)),
    )
    print(json.dumps({"success": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
