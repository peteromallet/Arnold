r"""Strategy migration **apply** — the only mutation path.

This module implements ``strategy migrate --apply``.  It performs *only* the
two supported, reversible rewrite classes and refuses to do anything else:

1. **Strategy version upgrade** — set ``schema_version`` to
   :data:`~arnold_pipelines.megaplan.strategy.versions.CURRENT_SCHEMA_VERSION`
   for *eligible* strategy files.  Eligible means the version status is
   ``legacy`` (a recognized older version) or ``missing-version`` (the
   frontmatter has no ``schema_version`` field).  Unknown pre-v1 versions
   (``unsupported-old``), too-new versions (``unsupported-new``), and
   malformed files are **never** upgraded — they are left untouched and, where
   applicable, reported as blockers by the read-only inspector.

2. **Ticket epics normalization** — rewrite supported *legacy* ``epics``
   frontmatter links into explicit dict links.  A legacy entry is either a
   bare string (``"my-epic"``) or a dict that is missing one or more of
   ``kind`` / ``provenance`` / ``linked_at``.  Each such entry is normalised to
   a full explicit dict that preserves the original ``epic_id`` ref (never
   inventing an ID) and deterministically fills the missing fields.  Invalid
   entries and already-explicit entries are preserved untouched.

Safety guarantees
-----------------

* **No ticket renames.**  Every rewrite is in-place on the existing path.
* **No invented IDs.**  ``epic_id`` values are preserved verbatim from the
  source entry.
* **Byte-for-byte backups.**  Before any mutation the original file bytes are
  copied under ``.megaplan/backups/strategy-migration/<timestamp>/`` mirroring
  the repo-relative path, and a ``manifest.json`` records each backed-up file
  with its SHA-256 digest and byte length.
* **Atomic writes.**  Each rewrite is written to a temp file in the target's
  directory and ``os.replace``\ d into place — readers never observe a
  half-written file, and no ``.tmp`` file is left behind on failure.
* **Blocker-gated.**  If the read-only inspector reports any blocker the apply
  is refused and no files are written.
* **Idempotent.**  A second run immediately after a successful apply is a
  no-op (version is current, epics are explicit).

Public API
----------

* :func:`apply_strategy_migration` — inspect then apply supported rewrites.
* :func:`compute_apply_plan` — inspect and report the supported rewrites that
  *would* be applied without writing anything (used for dry-run/preview).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.layout import strategy_file_path
from arnold_pipelines.megaplan.strategy.migration import inspect_strategy_migration
from arnold_pipelines.megaplan.strategy.versions import CURRENT_SCHEMA_VERSION
from arnold_pipelines.megaplan.tickets.relationships import (
    KIND_ASSOCIATED,
    KIND_RESOLVES_ON_COMPLETE,
    RELATIONSHIP_KINDS,
)

# --------------------------------------------------------------------------- #
# Supported rewrite classes
# --------------------------------------------------------------------------- #

# Version statuses eligible for the in-place version upgrade.  ``unsupported-old``
# is deliberately excluded — the gate settled that unknown pre-v1 versions must
# not be auto-upgraded.
ELIGIBLE_VERSION_STATES: tuple[str, ...] = ("legacy", "missing-version")

REWRITE_UPGRADE_VERSION: str = "upgrade-strategy-version"
REWRITE_NORMALIZE_EPICS: str = "normalize-ticket-epics"

# Fields every explicit (post-migration) epics dict entry must carry.
_EPICS_REQUIRED_FIELDS: tuple[str, ...] = ("kind", "provenance", "linked_at")

_BACKUP_BASE = Path(".megaplan") / "backups" / "strategy-migration"


# --------------------------------------------------------------------------- #
# Structured plan / result
# --------------------------------------------------------------------------- #


@dataclass
class PlannedRewrite:
    """A single supported rewrite that would be (or was) applied."""

    kind: str
    path: str  # repo-relative path

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path}


@dataclass
class ApplyPlan:
    """The supported rewrites computed for a repository (no writes)."""

    version_status: str
    do_version_upgrade: bool
    rewrites: list[PlannedRewrite] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def has_rewrites(self) -> bool:
        return bool(self.rewrites)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def compute_apply_plan(
    repo_root: str | Path,
    store: Any | None = None,
) -> ApplyPlan:
    """Inspect *repo_root* and return the supported rewrites without writing.

    Combines the read-only :func:`inspect_strategy_migration` report with an
    independent scan of ticket files for legacy epics links.  Returns a
    structured :class:`ApplyPlan`.
    """
    repo_root = Path(repo_root)
    report = inspect_strategy_migration(repo_root, store)

    plan = ApplyPlan(version_status=report.version_status,
                     do_version_upgrade=report.version_status in ELIGIBLE_VERSION_STATES,
                     blockers=list(report.blockers))

    # Strategy version upgrade (eligible states only).
    if plan.do_version_upgrade:
        spath = strategy_file_path(repo_root)
        if spath.is_file():
            try:
                src = spath.read_text(encoding="utf-8")
            except OSError:
                src = None
            if src is not None:
                new_src = rewrite_strategy_version(src, CURRENT_SCHEMA_VERSION)
                if new_src is not None and new_src != src:
                    plan.rewrites.append(
                        PlannedRewrite(REWRITE_UPGRADE_VERSION,
                                       str(spath.relative_to(repo_root)))
                    )

    # Ticket epics normalization.
    tickets_dir = repo_root / ".megaplan" / "tickets"
    if tickets_dir.is_dir():
        for md in sorted(tickets_dir.rglob("*.md")):
            try:
                src = md.read_text(encoding="utf-8")
            except OSError:
                continue
            if rewrite_ticket_epics(src) is not None:
                plan.rewrites.append(
                    PlannedRewrite(REWRITE_NORMALIZE_EPICS,
                                   str(md.relative_to(repo_root)))
                )

    return plan


def apply_strategy_migration(
    repo_root: str | Path,
    store: Any | None = None,
) -> dict[str, Any]:
    """Inspect then apply the supported reversible rewrites.

    See the module docstring for the full safety contract.  Returns a stable
    JSON-serializable dictionary describing what happened (or why it was
    refused).
    """
    repo_root = Path(repo_root)
    plan = compute_apply_plan(repo_root, store)

    # --- Blocker gate -------------------------------------------------------
    if plan.blocked:
        return {
            "success": False,
            "applied": False,
            "blocked": True,
            "error": "blocked",
            "blockers": plan.blockers,
            "rewrites": [],
            "version_status": plan.version_status,
        }

    # --- No-op when nothing to do (idempotent) ------------------------------
    if not plan.has_rewrites:
        return {
            "success": True,
            "applied": False,
            "blocked": False,
            "rewrites": [],
            "reason": "no-supported-rewrites",
            "version_status": plan.version_status,
        }

    # --- Compute new file contents ------------------------------------------
    targets: list[tuple[str, Path, str]] = []  # (kind, abspath, new_text)
    for rw in plan.rewrites:
        abspath = repo_root / rw.path
        try:
            src = abspath.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"Cannot read {rw.path} for migration apply: {exc}"
            ) from exc
        if rw.kind == REWRITE_UPGRADE_VERSION:
            new_src = rewrite_strategy_version(src, CURRENT_SCHEMA_VERSION)
        else:
            new_src = rewrite_ticket_epics(src)
        if new_src is None or new_src == src:
            # Became a no-op between plan and apply (e.g. concurrent edit) — skip.
            continue
        targets.append((rw.kind, abspath, new_src))

    if not targets:
        return {
            "success": True,
            "applied": False,
            "blocked": False,
            "rewrites": [],
            "reason": "no-supported-rewrites",
            "version_status": plan.version_status,
        }

    # --- Backups + manifest (before any mutation) ---------------------------
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = repo_root / _BACKUP_BASE / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict[str, Any]] = []
    for kind, abspath, _new_text in targets:
        original_bytes = abspath.read_bytes()
        digest = hashlib.sha256(original_bytes).hexdigest()
        rel = abspath.relative_to(repo_root)
        backup_path = backup_root / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        # Byte-for-byte backup copy of the pre-mutation file.
        backup_path.write_bytes(original_bytes)
        manifest_entries.append({
            "kind": kind,
            "path": str(rel),
            "backup_path": str(backup_path.relative_to(repo_root)),
            "sha256": digest,
            "bytes": len(original_bytes),
        })

    # --- Atomic rewrites ----------------------------------------------------
    files_changed: list[str] = []
    for kind, abspath, new_text in targets:
        _atomic_write_text(abspath, new_text)
        files_changed.append(str(abspath.relative_to(repo_root)))

    # --- Manifest (written last, after all mutations succeeded) -------------
    manifest = {
        "timestamp": timestamp,
        "tool": "megaplan strategy migrate --apply",
        "version_target": CURRENT_SCHEMA_VERSION,
        "rewrites": manifest_entries,
    }
    manifest_path = backup_root / "manifest.json"
    _atomic_write_text(manifest_path,
                       json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    return {
        "success": True,
        "applied": True,
        "blocked": False,
        "rewrites": [rw.to_dict() for rw in plan.rewrites],
        "version_status": plan.version_status,
        "backup_dir": str(backup_root.relative_to(repo_root)),
        "manifest_path": str(manifest_path.relative_to(repo_root)),
        "files_changed": files_changed,
        "timestamp": timestamp,
    }


# --------------------------------------------------------------------------- #
# Rewrite primitives (pure: source text -> new source text or None)
# --------------------------------------------------------------------------- #


def rewrite_strategy_version(source: str, new_version: str) -> str | None:
    """Return *source* with ``schema_version`` set to *new_version*.

    Surgical line edit: replaces the existing ``schema_version:`` value within
    the frontmatter, or inserts the key immediately after the opening ``---``
    fence when absent.  Every other line (frontmatter or body) is preserved.

    Returns ``None`` when the file has no parseable frontmatter fence.
    """
    lines = source.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    sv_re = re.compile(r"^(\s*schema_version\s*:\s*)(.*)$")
    for i in range(1, end_idx):
        m = sv_re.match(lines[i])
        if m:
            lines[i] = f"{m.group(1)}{new_version}"
            return "\n".join(lines)

    # Key absent — insert as the first frontmatter key.
    lines.insert(1, f"schema_version: {new_version}")
    return "\n".join(lines)


def rewrite_ticket_epics(source: str) -> str | None:
    """Return *source* with supported legacy epics links normalised.

    Re-serialises the frontmatter block, replacing the ``epics`` list with a
    normalised form where every supported legacy entry (bare string or dict
    missing ``kind``/``provenance``/``linked_at``) becomes an explicit dict.
    Invalid entries and already-explicit entries are preserved.

    Returns ``None`` when there is no frontmatter fence, no ``epics`` list,
    or nothing needs normalising.
    """
    parsed = _split_frontmatter(source)
    if parsed is None:
        return None
    fm_text, body_text, has_body = parsed

    import yaml

    try:
        record = yaml.safe_load(fm_text)
    except Exception:
        return None
    if not isinstance(record, dict):
        return None

    epics_raw = record.get("epics")
    if not isinstance(epics_raw, list) or not epics_raw:
        return None
    if not _epics_needs_normalization(epics_raw):
        return None

    record["epics"] = [_normalize_epics_entry(e) for e in epics_raw]
    safe = _to_yaml_safe(record)
    new_fm = yaml.dump(
        safe,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()

    if has_body:
        return f"---\n{new_fm}\n---\n{body_text}"
    return f"---\n{new_fm}\n---"


# --------------------------------------------------------------------------- #
# Epics normalization helpers
# --------------------------------------------------------------------------- #


def _epics_needs_normalization(epics_raw: list[Any]) -> bool:
    """True if any entry is a bare string or a dict missing required fields."""
    for entry in epics_raw:
        if _entry_needs_normalization(entry):
            return True
    return False


def _entry_needs_normalization(entry: Any) -> bool:
    if isinstance(entry, str):
        return bool(entry)  # bare non-empty string → legacy
    if isinstance(entry, dict):
        eid = entry.get("epic_id")
        if not (isinstance(eid, str) and eid):
            return False  # invalid/missing epic_id — unsupported, preserve
        return not all(f in entry for f in _EPICS_REQUIRED_FIELDS)
    return False


def _normalize_epics_entry(entry: Any) -> dict[str, Any]:
    """Normalise a single epics entry to an explicit dict.

    Preserves ``epic_id`` verbatim (never invents an ID) and deterministically
    fills ``kind`` / ``provenance`` / ``linked_at`` when missing, mirroring the
    read semantics in :mod:`arnold_pipelines.megaplan.tickets.relationships`.
    Entries that are already explicit or unsupported are returned unchanged.
    """
    if isinstance(entry, str) and entry:
        return {
            "epic_id": entry,
            "resolves_on_complete": False,
            "kind": KIND_ASSOCIATED,
            "provenance": None,
            "linked_at": None,
        }
    if isinstance(entry, dict):
        eid = entry.get("epic_id")
        if not (isinstance(eid, str) and eid):
            return entry  # unsupported — preserve verbatim
        resolves = bool(entry.get("resolves_on_complete"))
        kind = entry.get("kind")
        if not (isinstance(kind, str) and kind in RELATIONSHIP_KINDS):
            kind = KIND_RESOLVES_ON_COMPLETE if resolves else KIND_ASSOCIATED
        prov = entry.get("provenance")
        if not (isinstance(prov, str) and prov):
            prov = None
        linked_at = entry.get("linked_at")
        if linked_at is None:
            linked_at = None  # deterministic fill — no invented timestamp
        else:
            linked_at = _to_yaml_safe(linked_at)
        return {
            "epic_id": eid,
            "resolves_on_complete": resolves,
            "kind": kind,
            "provenance": prov,
            "linked_at": linked_at,
        }
    # Unsupported type (None, int, list, …) — preserve verbatim.
    return entry  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #


def _split_frontmatter(source: str) -> tuple[str, str, bool] | None:
    """Split *source* into (frontmatter_yaml, body_text, has_body).

    Returns ``None`` when there is no opening/closing ``---`` fence.
    """
    lines = source.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    fm_text = "\n".join(lines[1:end_idx])
    body_lines = lines[end_idx + 1:]
    body_text = "\n".join(body_lines)
    has_body = bool(body_text)
    return fm_text, body_text, has_body


def _to_yaml_safe(obj: Any) -> Any:
    """Recursively convert datetime/date values to ISO-format strings.

    This keeps the re-serialised frontmatter free of YAML timestamp tags and
    matches the canonical ticket serialisation (isoformat).
    """
    if isinstance(obj, dict):
        return {k: _to_yaml_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_yaml_safe(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def _atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically via a temp file + ``os.replace``.

    The temp file lives in the target's directory (so the rename is atomic on
    the same filesystem) and is removed on any error.
    """
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
