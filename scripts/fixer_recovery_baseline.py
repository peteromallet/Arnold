#!/usr/bin/env python3
"""Capture the T-0601 coherent predeploy baseline envelope (collector, read-only).

The baseline snapshots the exact live state that the T-0610 deploy must be
verified against: one content-addressed coherent envelope across the chain
spec/store, cloud-session markers, the runtime manifest + launch wrapper,
the repair queue (requests/decisions/claims/attempts), schedules, reconcile
receipts/refs, and the initiative inputs (chain.yaml, NORTHSTAR.md, briefs).

Guarantees (fail-closed):

* **Collector mode is the default.** Without ``--out`` the script performs
  zero writes: no file is created, modified, or removed, and no git command
  mutates anything (``for-each-ref`` is read-only).  The envelope is printed
  to stdout.  ``--out`` is an explicit opt-in that writes the envelope once,
  atomically (tmp file + rename, so a crash can never leave a torn envelope
  at the destination).
* **Half-open cursored windows.** Every captured file is stat-ed before and
  after its read; the window covers ``[start, end)`` per file, ``stable`` is
  true only when the endpoint cursors are byte-identical, a torn window is
  flagged, and windows never overlap (every path belongs to exactly one
  window).  Re-capturing unchanged state yields the identical envelope
  (replayable, watermarkable).
* **Canonical router.** The repair queue may contain ONLY canonical
  request/join/reclaim actions (plus the canonical attempt receipt and the
  advisory claims-index records).  Every decision/claim/attempt must resolve
  to a captured request, and every claim must resolve to an accepted
  decision.  Anything else is a typed violation.

Run from the repository root.  Defaults point at the live box layout for the
pinned G13 session/plan (chain store + plan state under the epic worktree
``/workspace/megaplan-maintenance/Arnold/.megaplan/...``, per-epic runtime
manifest at ``/workspace/.megaplan/megaplan-maintenance.json``, session
markers under ``/workspace/.megaplan/cloud-sessions``); every path is
overridable so rehearsals and tests can capture a private fixture tree.

The collector pins EXACTLY one live session/plan:

* ``--session`` and ``--plan`` are REQUIRED and must match the captured
  lineage.  Only markers whose filename carries the session name are read
  (other sessions' top-level markers are ignored), and any marker in that
  set declaring a different session identity fails the capture (leak
  detection).  The session is then classified ``current`` vs ``stale`` from
  marker liveness (latest activity timestamp, file mtime, or an explicit
  stopped/dead status) against a threshold.
* The chain capture resolves EXACTLY the named chain record
  (``chain-c511d8baf7d7.json`` or the chain resolvable from the plan state /
  chain spec) instead of globbing the whole store.
* The ledger capture is scoped to the NAMED plan's ``state.json`` and fails
  when that plan's state is missing or does not declare the plan identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a core dependency
    yaml = None


BASELINE_SCHEMA = "arnold.megaplan.fixer_recovery_baseline.v1"
WINDOW_SCHEMA = "arnold.megaplan.fixer_recovery_window.v1"
ROUTER_SCHEMA = "arnold.megaplan.fixer_recovery_router.v1"

# The ONLY canonical repair-custody actions a predeploy-ready queue may carry.
CANONICAL_ACTIONS = frozenset({"request", "join", "reclaim"})

# Canonical record kinds -> (category, action).  ``repair_request`` enqueues
# (request), ``repair_request_decision`` accepts/joins the request (join).
# Attempts are the canonical execution RECEIPT of a repair (not a custody
# action); claim records (kind suffix ``_claim``) and the claims-index alias
# records are handled explicitly in :func:`classify_queue_record`.
KIND_ACTION: Mapping[str, tuple[str, str]] = {
    "repair_request": ("action", "request"),
    "repair_request_decision": ("action", "join"),
}
RECEIPT_KINDS = frozenset({"repair_request_attempt"})
CLAIM_KIND_SUFFIX = "_claim"
CLAIM_ALIAS_SCHEMA = "claim-alias/v1"

# Retired launch-path selectors (T-0013 / G5).  A hit in any captured launch
# path file or in the process environment fails the predeploy gate.
RETIRED_SELECTOR_TOKENS = (
    "MEGAPLAN_SUPERVISOR_SOURCE",
    "MEGAPLAN_LAUNCH_RUNTIME_SRC",
    "MEGAPLAN_RUNTIME_SRC",
    "SYNC_BRANCH",
)
# T-0301: per-epic/per-runtime editable venv residue must be gone.
PIP_EDITABLE_RESIDUE = "pip install -e"
RUNTIME_VENV_DIR_NAME = ".venv"

# Ledger-bypass provenance markers: a plan ``state.json`` must either declare
# canonical writer provenance (one of these markers in its metadata/history)
# or be referenced by a canonical CAS record (``*_state_sha256`` /
# ``*_cursor_sha256`` / ``*_authority_sha256`` values inside a captured queue
# record).  Anything else may have been written raw, outside the canonical
# TransitionWriter, and fails the predeploy gate.
CANONICAL_WRITER_MARKERS = (
    "megaplan.chain.wbc.",
    "transition_writer",
    "canonical_writer",
    "occurrence_join",
    "occurrence_adopt",
)
_LEDGER_CAS_KEY_RE = re.compile(r"(state|cursor|authority).*sha256|sha256.*(state|cursor|authority)", re.IGNORECASE)

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Lineage fields: keys that carry a git revision/head/commit identity but are
# NOT content digests (keys containing "sha" are content addresses).
_LINEAGE_KEY_RE = re.compile(r"(^|_)(revision|head|commit)(_|$)", re.IGNORECASE)

CHAIN_STORE_PATTERN = "chain-*.json"
QUEUE_JSON_SUFFIXES = (".json",)
MARKER_JSON_SUFFIXES = (".json",)

# G13 pinned live target: the exact cloud session and plan the predeploy
# gate authorizes T-0610 against.
DEFAULT_SESSION = "megaplan-maintenance"
DEFAULT_PLAN = "m1-containment-and-truthful-20260811-0640"
DEFAULT_CHAIN_RECORD = "chain-c511d8baf7d7.json"
DEFAULT_SESSION_STALE_AFTER_SECONDS = 86400.0

# Marker keys whose values (ISO-8601 timestamps) count as session liveness.
SESSION_LIVENESS_KEYS = (
    "updated_at",
    "last_seen",
    "last_activity",
    "last_heartbeat",
    "heartbeat",
    "renewed_at",
    "liveness_claimed_at",
    "claimed_at",
    "lease_updated_at",
    "lease_renewed_at",
    "lease_expires_at",
    "expires_at",
)
# A marker whose ``status`` is one of these is NOT a live session, no matter
# how fresh its timestamps are (a stopped supervisor/lease is a stopped
# session).
SESSION_STALE_STATUSES = frozenset(
    {"stopped", "stopping", "dead", "exited", "terminated", "finalized", "failed"}
)

# Reconcile branch families whose refs are part of the reconcile source.
DEFAULT_RECONCILE_REFS = (
    "refs/heads/fixer/*",
    "refs/heads/reconcile/*",
    "refs/heads/editible-install",
)


class BaselineError(ValueError):
    """The collector cannot produce a coherent baseline from the given state."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _cursor(path: Path) -> dict[str, int]:
    """Read-only stat cursor for one file (the window endpoint token)."""
    stat = path.stat()
    return {
        "mtime_ns": int(stat.st_mtime_ns),
        "size": int(stat.st_size),
        "ino": int(stat.st_ino),
    }


def _cursor_le(cursor: Mapping[str, int], other: Mapping[str, int]) -> bool:
    return (cursor["mtime_ns"], cursor["size"], cursor["ino"]) <= (
        other["mtime_ns"],
        other["size"],
        other["ino"],
    )


def _sorted_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted({Path(path).expanduser().resolve(strict=False) for path in paths})


def _parse_utc(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware UTC datetime (or None)."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class BaselineConfig:
    """Every source path the envelope captures; all overridable for tests."""

    workspace: Path = Path("/workspace")
    initiative_dir: Path = Path(
        "/workspace/megaplan-maintenance/Arnold/.megaplan/initiatives/megaplan-maintenance"
    )
    chain_store: Path = Path(
        "/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains"
    )
    marker_dirs: tuple[Path, ...] = (Path("/workspace/.megaplan/cloud-sessions"),)
    runtime_manifest: Path = Path("/workspace/.megaplan/megaplan-maintenance.json")
    repair_queue: Path = Path("/workspace/.megaplan/repair-queue")
    plan_state_dir: Path = Path(
        "/workspace/megaplan-maintenance/Arnold/.megaplan/plans/"
        "m1-containment-and-truthful-20260811-0640"
    )
    schedule_dirs: tuple[Path, ...] = (
        Path("/workspace/arnold/.megaplan/resident/scheduled_jobs"),
        Path("/workspace/arnold/.megaplan/resident/schedules/heads"),
        Path("/workspace/.megaplan/ops/schedules"),
        Path("/workspace/.megaplan/schedule-inputs"),
    )
    # Schedule dirs whose absence FAILS the capture.  Empty tuple = the FIRST
    # schedule dir is the required one (the pinned megaplan-maintenance
    # resident schedule); every other dir is optional and an absence is
    # recorded (not a failure).
    required_schedule_dirs: tuple[Path, ...] = ()
    reconcile_dir: Path = Path("/workspace/.megaplan/reconcile-receipts")
    reconcile_refs: tuple[str, ...] = DEFAULT_RECONCILE_REFS
    git_root: Path = Path("/workspace/megaplan-maintenance/Arnold")
    session: str = DEFAULT_SESSION
    plan: str = DEFAULT_PLAN
    chain_record: str = DEFAULT_CHAIN_RECORD
    session_stale_after: float = DEFAULT_SESSION_STALE_AFTER_SECONDS
    collector: bool = True
    now: str = field(default_factory=_utc_now)


def _chain_spec_path(config: BaselineConfig) -> Path:
    return config.initiative_dir / "chain.yaml"


def _resolve_required_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_dir():
        raise BaselineError(f"{label}: required directory is missing: {resolved}")
    return resolved


def _resolve_required_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        raise BaselineError(f"{label}: required file is missing: {resolved}")
    return resolved


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineError(f"{label}: unreadable JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BaselineError(f"{label}: expected a JSON object at {path}")
    return payload


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    if yaml is None:  # pragma: no cover - pyyaml is a core dependency
        raise BaselineError(f"{label}: pyyaml is required to parse {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise BaselineError(f"{label}: unreadable YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BaselineError(f"{label}: expected a YAML mapping at {path}")
    return payload


def _capture_files(
    source: str,
    paths: Iterable[Path],
    *,
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read *paths* inside one half-open ``[start, end)`` cursored window.

    Each file is stat-ed before and after its read.  A file whose endpoint
    cursors differ (``stable`` False) makes the whole window ``torn``: the
    capture observed a writer mid-mutation and is not atomic proof.  The
    window covers ``[start, end)``; the end cursor is the exclusive horizon
    (the watermark a later capture resumes from).
    """
    records: list[dict[str, Any]] = []
    for path in _sorted_paths(paths):
        try:
            start = _cursor(path)
            data = path.read_bytes()
            end = _cursor(path)
        except OSError as exc:
            raise BaselineError(f"{label}: cannot read {path}: {exc}") from exc
        stable = start == end
        records.append(
            {
                "path": str(path),
                "content_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "start": start,
                "end": end,
                "stable": stable,
            }
        )
    torn = any(not record["stable"] for record in records)
    ordered = all(_cursor_le(record["start"], record["end"]) for record in records)
    window: dict[str, Any] = {
        "schema": WINDOW_SCHEMA,
        "source": source,
        "start": {"mtime_ns": 0, "size": 0, "ino": 0},
        "end": {"mtime_ns": 0, "size": 0, "ino": 0},
        "torn": torn,
        "ordered": ordered,
        "file_count": len(records),
    }
    if records:
        window["start"] = min(
            (record["start"] for record in records),
            key=lambda cursor: (cursor["mtime_ns"], cursor["size"], cursor["ino"]),
        )
        window["end"] = max(
            (record["end"] for record in records),
            key=lambda cursor: (cursor["mtime_ns"], cursor["size"], cursor["ino"]),
        )
    return records, window


# ── source captures ─────────────────────────────────────────────────────────


def _resolve_brief_path(
    config: BaselineConfig, initiative_dir: Path, idea: str
) -> Path:
    """Resolve a chain.yaml milestone ``idea`` exactly like the chain engine.

    Live ``chain.yaml`` specs use REPO-RELATIVE idea paths — the chain
    engine resolves them as ``git_root / idea``
    (``chain/__init__.py: _resolve_idea_path``), e.g.
    ``.megaplan/initiatives/megaplan-maintenance/briefs/m1.md``.  Simpler
    specs (and the original fixture) keep briefs next to ``chain.yaml``, i.e.
    ``initiative_dir / idea``.  Try the chain-engine form first, then the
    initiative-relative form; fail only if BOTH miss.
    """
    idea_path = Path(idea).expanduser()
    if idea_path.is_absolute():
        candidates = [idea_path]
    else:
        candidates = [
            config.git_root.expanduser().resolve(strict=False) / idea_path,
            initiative_dir / idea_path,
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve(strict=False)
    raise BaselineError(
        "initiative: milestone brief missing: "
        + " (also tried: ".join(str(candidate) for candidate in candidates)
        + ")"
    )


def capture_initiative(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture chain.yaml, NORTHSTAR.md, and the chain-referenced briefs."""
    initiative_dir = config.initiative_dir.expanduser().resolve(strict=False)
    if not initiative_dir.is_dir():
        raise BaselineError(f"initiative: required directory is missing: {initiative_dir}")
    chain_spec = _resolve_required_file(_chain_spec_path(config), "initiative")
    north_star = _resolve_required_file(initiative_dir / "NORTHSTAR.md", "initiative")

    spec = _read_yaml(chain_spec, "initiative")
    driver = spec.get("driver") if isinstance(spec.get("driver"), dict) else {}
    initiative_revision = str(driver.get("intended_initiative_revision") or "").strip()
    if not _FULL_SHA_RE.match(initiative_revision):
        raise BaselineError(
            "initiative: chain.yaml driver.intended_initiative_revision must be a "
            f"40-hex git SHA, got {initiative_revision!r}"
        )

    brief_paths: list[Path] = [north_star]
    milestones = spec.get("milestones")
    if isinstance(milestones, list):
        for milestone in milestones:
            if not isinstance(milestone, dict):
                continue
            idea = str(milestone.get("idea") or "").strip()
            if not idea:
                continue
            brief_paths.append(_resolve_brief_path(config, initiative_dir, idea))
    brief_paths.append(chain_spec)

    files, window = _capture_files("initiative", brief_paths, label="initiative")
    source: dict[str, Any] = {
        "source": "initiative",
        "initiative_dir": str(initiative_dir),
        "initiative_revision": initiative_revision,
        "chain_spec_path": str(chain_spec),
        "north_star_path": str(north_star),
        "files": files,
        "missing": [],
    }
    return source, window


def _chain_id_from(record: Any) -> str | None:
    """A chain id (bare hex/slug) declared by plan state or a chain spec."""
    if not isinstance(record, dict):
        return None
    candidates: list[Any] = []
    for key in ("chain_id", "chain", "chain_record", "chain_ref", "chain_name"):
        if key in record:
            candidates.append(record.get(key))
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        for key in ("chain_id", "chain"):
            if key in metadata:
                candidates.append(metadata.get(key))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().removeprefix("chain-")
    return None


def _resolve_chain_record(
    config: BaselineConfig, chain_store: Path, candidates: Sequence[Path]
) -> Path | None:
    """The single chain record the envelope may capture.

    Prefers the exact named record (``config.chain_record``); otherwise
    resolves the chain for the pinned plan from the plan state or the chain
    spec, and finally falls back to a lone candidate in the store.
    """
    named = (chain_store / config.chain_record).expanduser().resolve(strict=False)
    if named.is_file():
        return named

    plan_state = (config.plan_state_dir / "state.json").expanduser().resolve(strict=False)
    if plan_state.is_file():
        try:
            state = json.loads(plan_state.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            state = None
        chain_id = _chain_id_from(state)
        if chain_id:
            candidate = (chain_store / f"chain-{chain_id}.json").expanduser().resolve(strict=False)
            if candidate.is_file():
                return candidate

    spec_path = _chain_spec_path(config)
    if spec_path.is_file():
        spec = _read_yaml(spec_path, "chain") if yaml is not None else None
        chain_id = _chain_id_from(spec)
        if chain_id:
            candidate = (chain_store / f"chain-{chain_id}.json").expanduser().resolve(strict=False)
            if candidate.is_file():
                return candidate

    if len(candidates) == 1:
        return candidates[0]
    return None


def capture_chain(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture EXACTLY the pinned plan's chain store record.

    Other ``chain-*.json`` records in the store are deliberately not
    captured: the envelope's chain lineage must be the single record for the
    pinned plan (``config.chain_record`` or the record resolvable from the
    plan state / chain spec).
    """
    chain_store = _resolve_required_dir(config.chain_store, "chain")
    candidates = sorted(chain_store.rglob(CHAIN_STORE_PATTERN))
    if not candidates:
        raise BaselineError(
            f"chain: no {CHAIN_STORE_PATTERN} records under {chain_store}"
        )
    resolved = _resolve_chain_record(config, chain_store, candidates)
    if resolved is None:
        raise BaselineError(
            f"chain: named record {config.chain_record!r} missing under "
            f"{chain_store} and no chain record could be resolved for plan "
            f"{config.plan!r}"
        )
    files, window = _capture_files("chain", [resolved], label="chain")
    parsed = [_read_json(Path(record["path"]), "chain") for record in files]
    source: dict[str, Any] = {
        "source": "chain",
        "chain_store": str(chain_store),
        "chain_record": resolved.name,
        "chain_record_path": str(resolved),
        "resolved_from": "named" if resolved.name == config.chain_record else "plan",
        "chain_spec_path": str(_chain_spec_path(config)),
        "files": files,
        "missing": [],
        "lineage_shas": _extract_lineage_shas(parsed),
    }
    return source, window


def _content_session(path: Path) -> str | None:
    """The session identity DECLARED by a marker's content, if any."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    for key in ("session", "session_id", "session_name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _session_identity(path: Path, session: str) -> str:
    """The session identity of one marker file.

    A content-declared identity wins.  Files without one (liveness leases,
    chain-health sidecars) belong to the session whose name appears in their
    filename.
    """
    declared = _content_session(path)
    if declared is not None:
        return declared
    if session in path.name:
        return session
    return path.stem


def _lease_expiry(value: Any) -> datetime | None:
    """Parse a lease expiry as ISO-8601 or Unix epoch seconds (or None)."""
    parsed = _parse_utc(value)
    if parsed is not None:
        return parsed
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _classify_session(
    config: BaselineConfig,
    parsed: Sequence[dict[str, Any]],
    files: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify the pinned session ``current`` vs ``stale``.

    Liveness is the LATEST of: any marker timestamp under a liveness key
    (``updated_at`` / ``last_seen`` / lease renewals / ``liveness_claimed_at``,
    nested), or the marker file mtime (a real write happened at least that
    recently).  An explicit stopped/dead ``status`` anywhere in the lineage is
    stale regardless of timestamps.

    A CURRENT lease is the strongest liveness signal: a parked session whose
    marker has not been touched within the stale window is still ``current``
    while its lease is unexpired (the lease IS the liveness).  Lease expiry is
    read from ``lease_expires_at`` / ``expires_at`` values (ISO-8601 or Unix
    epoch seconds) anywhere in the captured markers/lease sidecars.
    """
    now = _parse_utc(config.now) or datetime.now(timezone.utc)
    latest: datetime | None = None
    latest_source = ""
    stale_statuses: list[str] = []
    lease_expires_at: datetime | None = None

    def consider(value: Any, source: str) -> None:
        nonlocal latest, latest_source
        parsed_dt = _parse_utc(value)
        if parsed_dt is None:
            return
        if latest is None or parsed_dt > latest:
            latest, latest_source = parsed_dt, source

    for record, payload in zip(files, parsed):
        path = str(record["path"])

        def walk(value: Any, prefix: str) -> None:
            nonlocal lease_expires_at
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in SESSION_LIVENESS_KEYS:
                        consider(item, f"{path}:{key}")
                    if key in ("lease_expires_at", "expires_at"):
                        expiry = _lease_expiry(item)
                        if expiry is not None and (
                            lease_expires_at is None or expiry > lease_expires_at
                        ):
                            lease_expires_at = expiry
                    if key == "status" and isinstance(item, str):
                        status = item.strip().lower()
                        if status in SESSION_STALE_STATUSES:
                            stale_statuses.append(f"{path}:{item.strip()}")
                    walk(item, f"{prefix}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{prefix}[{index}]")

        walk(payload, path)
        try:
            mtime = datetime.fromtimestamp(
                Path(path).stat().st_mtime, tz=timezone.utc
            )
            consider(mtime.isoformat(), f"{path}:mtime")
        except OSError:
            pass

    lease_alive = lease_expires_at is not None and lease_expires_at > now
    if latest is None:
        status = "unknown"
    elif stale_statuses:
        status = "stale"
    elif lease_alive or (now - latest).total_seconds() <= config.session_stale_after:
        status = "current"
    else:
        status = "stale"

    return {
        "status": status,
        "latest_activity": latest.isoformat() if latest is not None else None,
        "latest_source": latest_source,
        "threshold_seconds": config.session_stale_after,
        "stale_statuses": sorted(set(stale_statuses)),
        "lease_alive": lease_alive,
        "lease_expires_at": (
            lease_expires_at.isoformat() if lease_expires_at is not None else None
        ),
        "based_on": config.now,
    }


def capture_session(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture ONLY the pinned session's cloud-session markers.

    Only markers whose filename carries the session name are read (other
    sessions' top-level markers are deliberately not captured).  Every marker
    in that set must declare the pinned session identity (by content, or by
    filename for identity-less lease/health sidecars); a marker declaring a
    DIFFERENT session would leak a foreign identity into the captured
    lineage and fails the capture.  The captured lineage must contain at
    least one marker whose CONTENT declares the pinned session, and the
    session is classified current vs stale from its liveness.
    """
    marker_dirs = [
        path.expanduser().resolve(strict=False) for path in config.marker_dirs
    ]
    if not marker_dirs:
        raise BaselineError("session: no marker dirs configured")
    paths: list[Path] = []
    leaks: list[dict[str, str]] = []
    missing: list[str] = []
    for marker_dir in marker_dirs:
        if not marker_dir.is_dir():
            missing.append(str(marker_dir))
            continue
        for path in sorted(marker_dir.glob("*.json")):
            if not path.is_file():
                continue
            if config.session not in path.name:
                # Another session's top-level marker: not part of this
                # session's lineage and deliberately not captured.
                continue
            identity = _session_identity(path, config.session)
            if identity == config.session:
                paths.append(path)
            else:
                leaks.append({"path": str(path), "identity": identity})
    if missing or leaks or not paths:
        problems = []
        if missing:
            problems.append("required marker dirs missing: " + ", ".join(missing))
        if leaks:
            problems.append(
                "extra sessions leak into the captured lineage: "
                + ", ".join(
                    f"{leak['path']} (identity={leak['identity']!r})"
                    for leak in leaks
                )
            )
        if not paths:
            problems.append(f"no markers for session {config.session!r}")
        raise BaselineError("session: " + "; ".join(problems))
    files, window = _capture_files("session", paths, label="session")
    parsed = [_read_json(Path(record["path"]), "session") for record in files]
    if not any(
        _content_session(Path(record["path"])) == config.session
        for record in files
    ):
        raise BaselineError(
            f"session: no marker declares session identity {config.session!r} "
            "(only filename sidecars were captured)"
        )
    sessions = sorted({_session_identity(Path(record["path"]), config.session) for record in files})
    if sessions != [config.session]:
        raise BaselineError(
            f"session: identity mismatch: expected {[config.session]!r}, "
            f"captured {sessions!r}"
        )
    source: dict[str, Any] = {
        "source": "session",
        "marker_dirs": [str(path) for path in marker_dirs],
        "sessions": sessions,
        "classification": _classify_session(config, parsed, files),
        "files": files,
        "missing": missing,
        "lineage_shas": _extract_lineage_shas(parsed),
    }
    return source, window


def _extract_lineage_shas(values: Any) -> list[str]:
    """Collect 40-hex git SHAs held under lineage keys (revision/head/commit).

    Keys containing ``sha`` are content digests (problem signatures, CAS
    vectors, frozen specs) and are intentionally excluded — they are not
    engine/lineage identity.
    """
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    isinstance(key, str)
                    and "sha" not in key.lower()
                    and _LINEAGE_KEY_RE.search(key)
                    and isinstance(item, str)
                    and _FULL_SHA_RE.match(item.strip())
                ):
                    found.append(item.strip())
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(values)
    return sorted(set(found))


def _record_field(record: Mapping[str, Any], name: str) -> Any:
    """Read *name* from the top level or the standard nested locations."""
    if name in record:
        return record[name]
    for container_name in ("metadata", "repair_identity", "authority"):
        container = record.get(container_name)
        if isinstance(container, dict) and name in container:
            return container[name]
    return None


def classify_queue_record(record: Mapping[str, Any]) -> tuple[str, str]:
    """Classify one queue record as ``(category, action)``.

    Categories: ``action`` (must be one of request/join/reclaim), ``receipt``
    (the canonical attempt record), ``index`` (advisory claims-index aliases).
    Any other shape is a ``violation``.
    """
    schema = str(record.get("schema") or "")
    kind = str(record.get("kind") or "").strip()
    if schema == CLAIM_ALIAS_SCHEMA:
        return "index", "index"
    if kind in KIND_ACTION:
        return KIND_ACTION[kind]
    if kind in RECEIPT_KINDS:
        return "receipt", "attempt"
    if kind.endswith(CLAIM_KIND_SUFFIX):
        explicit = str(record.get("action") or "").strip()
        if explicit in CANONICAL_ACTIONS:
            return "action", explicit
        return "action", "join"
    return "violation", kind or "unknown"


def capture_queue(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Capture the repair queue and route it through the canonical router.

    Returns ``(source, window, router, parsed)``.  The router allows ONLY the
    canonical request/join/reclaim actions, plus the canonical attempt
    receipt and advisory claims-index records; every decision/claim/attempt
    must reference a captured request, and every claim must reference an
    accepted decision.  ``parsed`` maps captured path -> parsed record (used
    by the ledger CAS-reference check).
    """
    queue_root = _resolve_required_dir(config.repair_queue, "queue")
    requests_dir = queue_root / "requests"
    if not requests_dir.is_dir():
        raise BaselineError(f"queue: required requests dir missing: {requests_dir}")

    paths: list[Path] = []
    for item in sorted(queue_root.rglob("*")):
        if not item.is_file() or not item.name.endswith(QUEUE_JSON_SUFFIXES):
            continue
        paths.append(item)
    if not any(str(path).startswith(str(requests_dir)) for path in paths):
        raise BaselineError(f"queue: no repair requests under {requests_dir}")

    files, window = _capture_files("queue", paths, label="queue")
    parsed = {
        str(Path(record["path"])): _read_json(Path(record["path"]), "queue")
        for record in files
    }

    requests: dict[str, str] = {}  # request_id -> path
    for path, record in parsed.items():
        if str(record.get("kind") or "") == "repair_request":
            request_id = str(_record_field(record, "request_id") or "").strip()
            if not request_id:
                raise BaselineError(f"queue: repair_request without request_id at {path}")
            requests[request_id] = path

    actions: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    index_records: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    decisions_by_request: dict[str, list[dict[str, Any]]] = {}

    for path, record in sorted(parsed.items()):
        category, action = classify_queue_record(record)
        entry: dict[str, Any] = {"path": path, "kind": str(record.get("kind") or ""), "action": action}
        request_id = str(_record_field(record, "request_id") or "").strip()
        if request_id:
            entry["request_id"] = request_id
        if category == "violation":
            violations.append(
                {"path": path, "reason": "non_canonical_action", "kind": action}
            )
            continue
        if category == "action":
            if action not in CANONICAL_ACTIONS:
                violations.append(
                    {"path": path, "reason": "non_canonical_action", "action": action}
                )
                continue
            actions.append(entry)
            if request_id and request_id not in requests:
                violations.append(
                    {"path": path, "reason": "missing_request_reference", "request_id": request_id}
                )
            if str(record.get("kind") or "") == "repair_request_decision":
                decisions_by_request.setdefault(request_id, []).append(record)
        elif category == "receipt":
            receipts.append(entry)
            if request_id and request_id not in requests:
                violations.append(
                    {"path": path, "reason": "missing_request_reference", "request_id": request_id}
                )
        else:
            index_records.append(entry)

    for claim in actions:
        kind = str(claim.get("kind") or "")
        if not kind.endswith(CLAIM_KIND_SUFFIX):
            continue
        request_id = str(claim.get("request_id") or "")
        accepted = any(
            str(decision.get("decision") or "").strip() == "accepted"
            for decision in decisions_by_request.get(request_id, [])
        )
        if not accepted:
            violations.append(
                {
                    "path": claim["path"],
                    "reason": "claim_without_accepted_decision",
                    "request_id": request_id,
                }
            )

    router: dict[str, Any] = {
        "schema": ROUTER_SCHEMA,
        "canonical_only": not violations,
        "actions": actions,
        "receipts": receipts,
        "index_records": index_records,
        "violations": violations,
    }
    source: dict[str, Any] = {
        "source": "queue",
        "queue_root": str(queue_root),
        "files": files,
        "missing": [],
    }
    return source, window, router, parsed


def capture_runtime(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture the runtime manifest and its launch wrapper."""
    manifest_path = _resolve_required_file(config.runtime_manifest, "runtime")
    manifest = _read_json(manifest_path, "runtime")

    epic = manifest.get("epic") if isinstance(manifest.get("epic"), dict) else {}
    indirection = (
        manifest.get("indirection") if isinstance(manifest.get("indirection"), dict) else {}
    )
    base = manifest.get("base") if isinstance(manifest.get("base"), dict) else {}

    runtime_root = Path(str(epic.get("runtime_root") or "")).expanduser().resolve(strict=False)
    venv_path = str(epic.get("venv_path") or "").strip()
    expected_head = str(epic.get("expected_head") or "").strip()
    verified_head = str(indirection.get("verified_head") or "").strip()
    base_commit = str(base.get("commit") or "").strip()
    editable_install_path = str(base.get("editable_install_path") or "").strip()

    repair_bin = str(epic.get("repair_bin") or "").strip()
    wrapper_path = Path(repair_bin).expanduser().resolve(strict=False) if repair_bin else None
    capture_paths: list[Path] = [manifest_path]
    if wrapper_path is not None:
        if not wrapper_path.is_file():
            raise BaselineError(f"runtime: repair_bin wrapper missing: {wrapper_path}")
        capture_paths.append(wrapper_path)

    files, window = _capture_files("runtime", capture_paths, label="runtime")

    dependency_generation = epic.get("dependency_generation")
    if dependency_generation is not None and not isinstance(dependency_generation, dict):
        raise BaselineError("runtime: epic.dependency_generation must be an object when present")

    parsed: dict[str, Any] = {
        "runtime_id": str(manifest.get("runtime_id") or ""),
        "schema": str(manifest.get("schema") or ""),
        "generation": manifest.get("generation"),
        "epic_id": str(manifest.get("epic_id") or ""),
        "state": str(manifest.get("state") or ""),
        "owner": str(manifest.get("owner") or ""),
        "epic": {
            "branch": str(epic.get("branch") or ""),
            "worktree_path": str(epic.get("worktree_path") or ""),
            "runtime_root": str(runtime_root),
            "expected_head": expected_head,
            "venv_path": venv_path,
            "repair_bin": repair_bin,
            "deps_lockfile": str(epic.get("deps_lockfile") or ""),
            "dependency_generation": dependency_generation,
        },
        "indirection": {
            "verified_head": verified_head,
            "host_path": str(indirection.get("host_path") or ""),
        },
        "base": {
            "commit": base_commit,
            "editable_install_path": editable_install_path,
        },
    }

    wrapper_record = None
    wrapper_sha256: str | None = None
    if wrapper_path is not None:
        wrapper_record = next(
            record
            for record in files
            if Path(record["path"]).expanduser().resolve(strict=False) == wrapper_path
        )
        wrapper_sha256 = wrapper_record["content_sha256"]

    generation_interpreter_present = False
    if isinstance(dependency_generation, dict):
        interpreter = str(dependency_generation.get("interpreter_path") or "").strip()
        generation_interpreter_present = bool(
            interpreter and Path(interpreter).expanduser().is_file()
        )

    source: dict[str, Any] = {
        "source": "runtime",
        "manifest_path": str(manifest_path),
        "content_sha256": next(
            record["content_sha256"]
            for record in files
            if Path(record["path"]).expanduser().resolve(strict=False) == manifest_path
        ),
        "parsed": parsed,
        "wrapper": (
            {
                "path": str(wrapper_path),
                "content_sha256": wrapper_sha256,
                "present": True,
            }
            if wrapper_path is not None
            else {"path": "", "content_sha256": None, "present": False}
        ),
        "runtime_venv_present": bool(
            runtime_root and (runtime_root / RUNTIME_VENV_DIR_NAME).is_dir()
        ),
        "generation_interpreter_present": generation_interpreter_present,
        "files": files,
        "missing": [],
    }
    return source, window


def capture_schedule(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture every schedule store file (scheduled jobs, heads, ops).

    Absent OPTIONAL schedule dirs are recorded in ``missing`` (not a
    failure) — the live box does not provision every default store (e.g.
    ``resident/schedules/heads``, ``schedule-inputs``).  Only a REQUIRED
    schedule dir (the pinned megaplan-maintenance resident store) failing to
    resolve is a failure.  A present-but-unreadable store is still a failure
    (``_capture_files`` raises).
    """
    schedule_dirs = [
        path.expanduser().resolve(strict=False) for path in config.schedule_dirs
    ]
    if not schedule_dirs:
        raise BaselineError("schedule: no schedule dirs configured")
    required_dirs = [
        path.expanduser().resolve(strict=False)
        for path in (config.required_schedule_dirs or schedule_dirs[:1])
    ]
    paths: list[Path] = []
    missing: list[str] = []
    for schedule_dir in schedule_dirs:
        if not schedule_dir.is_dir():
            missing.append(str(schedule_dir))
            continue
        paths.extend(path for path in sorted(schedule_dir.rglob("*")) if path.is_file())
    required_missing = [str(path) for path in required_dirs if not path.is_dir()]
    if required_missing:
        raise BaselineError(
            "schedule: required schedule dirs are missing: " + ", ".join(required_missing)
        )
    files, window = _capture_files("schedule", paths, label="schedule")
    source: dict[str, Any] = {
        "source": "schedule",
        "schedule_dirs": [str(path) for path in schedule_dirs],
        "files": files,
        "missing": missing,
    }
    return source, window


def _git_for_each_ref(git_root: Path, patterns: Sequence[str]) -> list[dict[str, Any]]:
    """Read-only ref resolution; never mutates the repository."""
    command = [
        "git",
        "-C",
        str(git_root),
        "for-each-ref",
        "--format=%(refname)%00%(objectname)",
    ] + list(patterns)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    refs: list[dict[str, Any]] = []
    if result.returncode != 0:
        return refs
    for line in result.stdout.splitlines():
        if not line:
            continue
        refname, sep, objectname = line.partition("\x00")
        if not sep:
            continue
        refs.append({"refname": refname, "objectname": objectname.strip()})
    return sorted(refs, key=lambda item: item["refname"])


def capture_reconcile(config: BaselineConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture reconcile receipts and the reconcile/fixer/legacy branch refs."""
    git_root = config.git_root.expanduser().resolve(strict=False)
    if not git_root.is_dir():
        raise BaselineError(f"reconcile: git root missing: {git_root}")

    receipt_paths: list[Path] = []
    reconcile_dir = config.reconcile_dir.expanduser().resolve(strict=False)
    if reconcile_dir.is_dir():
        receipt_paths.extend(
            path for path in sorted(reconcile_dir.rglob("*")) if path.is_file()
        )
    files, window = _capture_files("reconcile", receipt_paths, label="reconcile")

    resolved_refs = _git_for_each_ref(git_root, config.reconcile_refs)
    refs: list[dict[str, Any]] = []
    for pattern in config.reconcile_refs:
        matches = [ref for ref in resolved_refs if _ref_matches(ref["refname"], pattern)]
        if matches:
            refs.extend(matches)
        else:
            refs.append({"refname": pattern, "objectname": "", "present": False})
    refs = sorted(refs, key=lambda item: item["refname"])

    source: dict[str, Any] = {
        "source": "reconcile",
        "reconcile_dir": str(reconcile_dir),
        "git_root": str(git_root),
        "reconcile_refs": list(config.reconcile_refs),
        "files": files,
        "refs": refs,
        "missing": [] if reconcile_dir.is_dir() else [str(reconcile_dir)],
    }
    return source, window


def _ref_matches(refname: str, pattern: str) -> bool:
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        return refname.startswith(prefix + "/")
    return refname == pattern


def _writer_marker_hit(value: str) -> bool:
    return any(marker in value for marker in CANONICAL_WRITER_MARKERS)


def _declares_writer_provenance(record: Mapping[str, Any]) -> bool:
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        for key in ("writer", "updated_by", "transition_writer"):
            value = metadata.get(key)
            if isinstance(value, str) and _writer_marker_hit(value):
                return True
    history = record.get("history")
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict):
            for key in ("writer_id", "writer", "actor"):
                value = last.get(key)
                if isinstance(value, str) and _writer_marker_hit(value):
                    return True
    return False


def _cas_references(record: Mapping[str, Any], state_sha256: str) -> bool:
    """True when *record* carries *state_sha256* under a CAS vector key."""
    hex_digest = state_sha256.removeprefix("sha256:")
    if not _FULL_SHA256_RE.match(hex_digest):
        return False

    def walk(value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and _LEDGER_CAS_KEY_RE.search(key):
                    if isinstance(item, str) and (
                        item == state_sha256 or item == hex_digest
                    ):
                        return True
                if walk(item):
                    return True
        elif isinstance(value, list):
            for item in value:
                if walk(item):
                    return True
        return False

    return walk(record)


# Plan-name keys whose values identify which plan a captured state belongs to.
PLAN_NAME_KEYS = ("name", "plan", "plan_name", "plan_id", "plan_ref", "plan_key")
# Chain-linkage keys: a state declaring one must agree with the pinned chain
# (the megaplan-maintenance session identity).  Absence is tolerated — not
# every state schema carries a chain field — but a declared contradiction is
# an identity mismatch.
CHAIN_LINKAGE_KEYS = ("chain", "chain_name", "chain_id", "chain_ref")


def _collect_strings(value: Any, keys: frozenset[str]) -> list[str]:
    """Every non-empty string under a *keys* field, recursively."""
    found: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if (
                    isinstance(key, str)
                    and key in keys
                    and isinstance(child, str)
                    and child.strip()
                ):
                    found.append(child.strip())
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found


def _plan_identity_holds(
    config: BaselineConfig, plan_state_dir: Path, parsed: Mapping[str, Any]
) -> bool:
    """The captured state must belong to the pinned plan.

    The directory name is only the capture SCOPE; identity is proven from
    content.  Every captured ``state.json`` must declare the pinned plan in a
    plan-name field (the state's own ``name``), and any chain linkage a state
    declares must agree with the pinned chain (the session identity).  A
    foreign ``state.json`` swapped into the correctly named directory
    declares a different plan name (or none) and fails identity instead of
    short-circuiting on the directory name.
    """
    plan_names = [
        name
        for state in parsed.values()
        for name in _collect_strings(state, frozenset(PLAN_NAME_KEYS))
    ]
    if not plan_names or any(name != config.plan for name in plan_names):
        return False
    for state in parsed.values():
        chain_ids = _collect_strings(state, frozenset(CHAIN_LINKAGE_KEYS))
        if chain_ids and any(chain != config.session for chain in chain_ids):
            return False
    return True


def capture_ledger(config: BaselineConfig, queue_parsed: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture the pinned plan's ``state.json`` files and prove canonical
    writer provenance.

    The ledger is scoped to the NAMED plan's state directory; a missing plan
    state dir, a missing ``state.json``, or a captured state that does not
    declare the pinned plan identity fails the capture (fail-closed).

    A captured state.json is PROVEN when it declares canonical writer
    provenance (a TransitionWriter / occurrence-join / adoption marker in its
    metadata or latest history entry) OR when its digest appears under a CAS
    vector key (``*_state_sha256`` / ``*_cursor_sha256`` /
    ``*_authority_sha256``) inside a captured queue record.  Any other state
    file may have been written raw, outside the canonical writer, and is a
    ledger-bypass violation (fail-closed).
    """
    plan_state_dir = config.plan_state_dir.expanduser().resolve(strict=False)
    if not plan_state_dir.is_dir():
        raise BaselineError(
            f"ledger: plan state dir missing: {plan_state_dir} (plan {config.plan!r})"
        )
    state_paths = [
        path
        for path in sorted(plan_state_dir.rglob("state.json"))
        if path.is_file()
    ]
    if not state_paths:
        raise BaselineError(
            f"ledger: no state.json under {plan_state_dir} (plan {config.plan!r})"
        )
    files, window = _capture_files("ledger", state_paths, label="ledger")
    parsed = {
        str(Path(record["path"])): _read_json(Path(record["path"]), "ledger")
        for record in files
    }
    if not _plan_identity_holds(config, plan_state_dir, parsed):
        raise BaselineError(
            f"ledger: plan identity mismatch: expected {config.plan!r}; "
            f"captured state under {plan_state_dir} does not declare it"
        )

    violations: list[dict[str, Any]] = []
    for record in files:
        path = Path(record["path"])
        state = parsed[str(path)]
        proven = _declares_writer_provenance(state)
        provenance = "writer_metadata" if proven else ""
        if not proven:
            for queue_record in queue_parsed.values():
                if _cas_references(queue_record, record["content_sha256"]):
                    proven = True
                    provenance = "cas_reference"
                    break
        if not proven:
            violations.append(
                {
                    "path": str(path),
                    "reason": "unproven_state_write",
                    "content_sha256": record["content_sha256"],
                }
            )
        record["proven"] = proven
        record["provenance"] = provenance

    source: dict[str, Any] = {
        "source": "ledger",
        "plan": config.plan,
        "plan_state_dir": str(plan_state_dir),
        "plan_dir_name": plan_state_dir.name,
        "files": files,
        "violations": violations,
        "missing": [],
    }
    return source, window


def _scan_launch_path(
    launch_files: Iterable[dict[str, Any]],
    tokens: Sequence[str],
) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for record in launch_files:
        try:
            data = Path(record["path"]).read_bytes()
        except OSError:
            continue
        for token in tokens:
            if token.encode("utf-8") in data:
                hits.append({"path": record["path"], "token": token})
    return hits


def _build_envelope(
    config: BaselineConfig,
    sources: Mapping[str, dict[str, Any]],
    windows: Mapping[str, dict[str, Any]],
    router: dict[str, Any],
    ledger: dict[str, Any],
    initiative_revision: str,
    engine_lineage: list[str],
) -> dict[str, Any]:
    # Overlap enforcement: every captured path belongs to exactly one window.
    path_windows: dict[str, list[str]] = {}
    for source, window in windows.items():
        if source == "ledger":
            files = ledger.get("files", [])
        else:
            files = sources[source].get("files", [])
        for record in files:
            path_windows.setdefault(str(Path(record["path"]).expanduser().resolve(strict=False)), []).append(source)
    overlaps = [
        {"path": path, "windows": sorted(w_names)}
        for path, w_names in path_windows.items()
        if len(w_names) > 1
    ]
    windows_index = {
        source: {
            "schema": WINDOW_SCHEMA,
            "source": source,
            "start": window["start"],
            "end": window["end"],
            "torn": window["torn"],
            "ordered": window["ordered"],
            "file_count": window["file_count"],
        }
        for source, window in windows.items()
    }

    launch_files = [
        *sources["runtime"].get("files", []),
        *sources["schedule"].get("files", []),
    ]
    selector_hits = _scan_launch_path(launch_files, RETIRED_SELECTOR_TOKENS)
    editable_residue = _scan_launch_path(launch_files, (PIP_EDITABLE_RESIDUE,))

    coherent = (
        all(not window["torn"] for window in windows.values())
        and all(window["ordered"] for window in windows.values())
        and not overlaps
        and router["canonical_only"]
    )

    root = {
        "lineage": {
            "engine": sorted(set(engine_lineage)),
            "initiative_revision": initiative_revision,
        },
        "coherent": coherent,
    }
    payload = {
        "schema": BASELINE_SCHEMA,
        "collector_mode": bool(config.collector),
        "pinned": {
            "session": config.session,
            "plan": config.plan,
            "chain_record": config.chain_record,
        },
        "initiative": sources["initiative"],
        "sources": {
            "chain": sources["chain"],
            "session": sources["session"],
            "runtime": sources["runtime"],
            "queue": sources["queue"],
            "schedule": sources["schedule"],
            "reconcile": sources["reconcile"],
        },
        "ledger": ledger,
        "windows": windows_index,
        "overlaps": overlaps,
        "router": router,
        "selectors": {
            "retired": list(RETIRED_SELECTOR_TOKENS),
            "hits": selector_hits,
        },
        "editable_residue": {
            "scanned": PIP_EDITABLE_RESIDUE,
            "hits": editable_residue,
        },
        "root": root,
    }
    content_sha256 = _digest(payload)
    root["content_sha256"] = content_sha256
    return {
        "schema": BASELINE_SCHEMA,
        "baseline_id": content_sha256,
        "captured_at": config.now,
        "collector_mode": bool(config.collector),
        **payload,
    }


def capture_baseline(config: BaselineConfig) -> dict[str, Any]:
    """Capture the coherent envelope.  Read-only unless ``--out`` was chosen."""
    initiative, initiative_window = capture_initiative(config)
    chain, chain_window = capture_chain(config)
    session, session_window = capture_session(config)
    runtime, runtime_window = capture_runtime(config)
    queue, queue_window, router, queue_parsed = capture_queue(config)
    schedule, schedule_window = capture_schedule(config)
    reconcile, reconcile_window = capture_reconcile(config)
    ledger, ledger_window = capture_ledger(config, queue_parsed=queue_parsed)

    engine_lineage: list[str] = []
    manifest = runtime["parsed"]
    engine_lineage.extend(
        value
        for value in (
            manifest["epic"]["expected_head"],
            manifest["indirection"]["verified_head"],
            manifest["base"]["commit"],
        )
        if _FULL_SHA_RE.match(value)
    )
    engine_lineage.extend(chain.get("lineage_shas", []))
    engine_lineage.extend(session.get("lineage_shas", []))

    return _build_envelope(
        config,
        sources={
            "initiative": initiative,
            "chain": chain,
            "session": session,
            "runtime": runtime,
            "queue": queue,
            "schedule": schedule,
            "reconcile": reconcile,
        },
        windows={
            "initiative": initiative_window,
            "chain": chain_window,
            "session": session_window,
            "runtime": runtime_window,
            "queue": queue_window,
            "schedule": schedule_window,
            "reconcile": reconcile_window,
            "ledger": ledger_window,
        },
        router=router,
        ledger=ledger,
        initiative_revision=initiative["initiative_revision"],
        engine_lineage=engine_lineage,
    )


def _add_path_flag(parser: argparse.ArgumentParser, *names: str, default: Any, help_text: str) -> None:
    parser.add_argument(*names, default=default, help=help_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        required=True,
        help=f"exact live cloud session to pin (default config: {DEFAULT_SESSION!r})",
    )
    parser.add_argument(
        "--plan",
        required=True,
        help=f"exact live plan to pin (default config: {DEFAULT_PLAN!r})",
    )
    parser.add_argument(
        "--chain-record",
        default=DEFAULT_CHAIN_RECORD,
        help=f"exact chain store record to capture (default: {DEFAULT_CHAIN_RECORD})",
    )
    parser.add_argument("--workspace", default="/workspace", help="live workspace root")
    parser.add_argument(
        "--initiative-dir",
        default="/workspace/megaplan-maintenance/Arnold/.megaplan/initiatives/megaplan-maintenance",
        help="initiative directory containing chain.yaml + NORTHSTAR.md + briefs",
    )
    parser.add_argument(
        "--chain-store",
        default="/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains",
        help="chain store directory (chain-*.json records)",
    )
    parser.add_argument("--marker-dir", action="append", default=[], help="cloud-session marker dir (repeatable)")
    parser.add_argument(
        "--runtime-manifest",
        default="/workspace/.megaplan/megaplan-maintenance.json",
        help="per-epic runtime manifest (workspace level)",
    )
    parser.add_argument("--repair-queue", default="/workspace/.megaplan/repair-queue")
    parser.add_argument(
        "--plan-state-dir",
        default="/workspace/megaplan-maintenance/Arnold/.megaplan/plans/"
        "m1-containment-and-truthful-20260811-0640",
        help="the pinned plan's state directory",
    )
    parser.add_argument(
        "--session-stale-after",
        type=float,
        default=DEFAULT_SESSION_STALE_AFTER_SECONDS,
        help="seconds of inactivity after which the pinned session is stale",
    )
    parser.add_argument("--schedule-dir", action="append", default=[], help="schedule store dir (repeatable)")
    parser.add_argument(
        "--required-schedule-dir",
        action="append",
        default=[],
        help="schedule store dir whose absence FAILS the capture (repeatable; "
        "default: the first --schedule-dir is the required one)",
    )
    parser.add_argument("--reconcile-dir", default="/workspace/.megaplan/reconcile-receipts")
    parser.add_argument("--reconcile-ref", action="append", default=[], help="reconcile ref pattern (repeatable)")
    parser.add_argument("--git-root", default="/workspace/megaplan-maintenance/Arnold")
    parser.add_argument("--out", default=None, help="optional envelope path (explicit write; collector mode by default)")
    return parser


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = BaselineConfig(
        workspace=Path(args.workspace),
        initiative_dir=Path(args.initiative_dir),
        chain_store=Path(args.chain_store),
        marker_dirs=tuple(Path(path) for path in args.marker_dir)
        or (Path(args.workspace) / ".megaplan" / "cloud-sessions",),
        runtime_manifest=Path(args.runtime_manifest),
        repair_queue=Path(args.repair_queue),
        plan_state_dir=Path(args.plan_state_dir),
        schedule_dirs=tuple(Path(path) for path in args.schedule_dir)
        or (
            Path("/workspace/arnold/.megaplan/resident/scheduled_jobs"),
            Path("/workspace/arnold/.megaplan/resident/schedules/heads"),
            Path("/workspace/.megaplan/ops/schedules"),
            Path("/workspace/.megaplan/schedule-inputs"),
        ),
        required_schedule_dirs=tuple(Path(path) for path in args.required_schedule_dir),
        reconcile_dir=Path(args.reconcile_dir),
        reconcile_refs=tuple(args.reconcile_ref) or DEFAULT_RECONCILE_REFS,
        git_root=Path(args.git_root),
        session=args.session,
        plan=args.plan,
        chain_record=args.chain_record,
        session_stale_after=args.session_stale_after,
        collector=args.out is None,
    )
    envelope = capture_baseline(config)
    rendered = json.dumps(envelope, indent=2, sort_keys=True)
    if args.out:
        _atomic_write(
            Path(args.out).expanduser().resolve(strict=False), rendered + "\n"
        )
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
