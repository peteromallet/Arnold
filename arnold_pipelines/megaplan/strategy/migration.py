"""Strategy migration doctor — read-only inspection and action proposals.

This module provides the **doctor/migrate inspection surface** that examines
a repository's strategy file, ticket inventory, and (optionally) store-backed
relationship records and returns structured findings, blockers, and proposed
actions **without performing any writes**.

It is the preflight contract that later CLI ``doctor`` and ``migrate apply``
commands depend on — every mutation must have visible, machine-readable
preflight evidence produced by this module.

Public API
----------

* :func:`inspect_strategy_migration` — inspect a repository and return a
  complete :class:`MigrationReport`.
* :class:`MigrationReport` — top-level structured result.
* :class:`MigrationFinding` — a single diagnostic/observation.
* :class:`MigrationAction` — a proposed (but not yet executed) write action.

Design rules
------------

* **Absent ``.megaplan/STRATEGY.md`` is a valid unadopted state**, not an error.
  The report will have ``status='ok'`` and ``safe_to_apply=False`` (no
  strategy to migrate).
* **Read-only**: no files are created, renamed, deleted, or modified.
* **Store is advisory**: when a ``Store`` instance is provided, relationship
  records are queried for additional diagnostics but the file-backed ticket
  corpus remains the authoritative source.
* **Identity is ULID-only**: duplicate/invalid frontmatter ``id`` values are
  diagnosed from the inventory; filename shape is informational only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from arnold_pipelines.megaplan.layout import (
    strategy_file_path,
    strategy_projection_file_path,
)
from arnold_pipelines.megaplan.strategy.versions import (
    CURRENT_SCHEMA_VERSION,
    StrategyVersionStatus,
    inspect_strategy_file,
)
from arnold_pipelines.megaplan.tickets.inventory import (
    TicketInventory,
    build_ticket_inventory,
)

# ---------------------------------------------------------------------------
# Finding severity
# ---------------------------------------------------------------------------

FindingSeverity = Literal["error", "warning", "info"]
"""Severity of a migration finding.

``error``:   blocks migration (e.g. duplicate ULIDs, malformed strategy).
``warning``: advisory issue (e.g. legacy filename, missing body).
``info``:    purely informational (e.g. strategy is current, no tickets).
"""

# ---------------------------------------------------------------------------
# Migration status
# ---------------------------------------------------------------------------

MigrationStatus = Literal["ok", "needs-migration", "blocked"]
"""Overall migration status.

``ok``:              no action required (current version, clean inventory,
                     or no strategy at all — unadopted).
``needs-migration``: actionable migrations detected and all blockers are
                     absent — ``safe_to_apply`` is *True*.
``blocked``:         at least one blocker prevents safe migration —
                     ``safe_to_apply`` is *False*.
"""

# ---------------------------------------------------------------------------
# Finding and action kind constants
# ---------------------------------------------------------------------------

FINDING_VERSION_CURRENT: str = "version-current"
FINDING_VERSION_LEGACY: str = "version-legacy"
FINDING_VERSION_UNSUPPORTED_OLD: str = "version-unsupported-old"
FINDING_VERSION_UNSUPPORTED_NEW: str = "version-unsupported-new"
FINDING_VERSION_MISSING: str = "version-missing"
FINDING_VERSION_MALFORMED: str = "version-malformed"
FINDING_STRATEGY_ABSENT: str = "strategy-absent"
FINDING_DUPLICATE_IDS: str = "duplicate-ids"
FINDING_LEGACY_TICKET_EPICS: str = "legacy-ticket-epics"
ACTION_NORMALIZE_TICKET_EPICS: str = "normalize-ticket-epics"
FINDING_INVALID_ULID: str = "invalid-ulid"
FINDING_MISSING_ID: str = "missing-id"
FINDING_LEGACY_FILENAME: str = "legacy-filename"
FINDING_INVALID_FILENAME_ULID: str = "invalid-filename-ulid"
FINDING_PARSE_ERROR: str = "parse-error"
FINDING_NO_TICKETS_DIR: str = "no-tickets-dir"
FINDING_TICKETS_PRESENT: str = "tickets-present"
FINDING_ROADMAP_ORPHAN: str = "roadmap-orphan"
FINDING_AMBIGUOUS_EPIC_REF: str = "ambiguous-epic-ref"
FINDING_MISSING_EPIC_REF: str = "missing-epic-ref"
FINDING_STALE_TITLE: str = "stale-title"
FINDING_PROJECTION_DRIFT: str = "projection-drift"
FINDING_PROJECTION_ABSENT: str = "projection-absent"
FINDING_PROJECTION_CURRENT: str = "projection-current"
FINDING_PROJECTION_STALE: str = "projection-stale"
FINDING_STORE_ORPHAN_LINK: str = "store-orphan-link"
FINDING_STORE_FILE_MISMATCH: str = "store-file-mismatch"

ACTION_UPGRADE_VERSION: str = "upgrade-version"
ACTION_ADD_FRONTMATTER_ID: str = "add-frontmatter-id"
ACTION_RENAME_FILE: str = "rename-file"
ACTION_RESOLVE_DUPLICATE: str = "resolve-duplicate"
ACTION_FIX_PARSE_ERROR: str = "fix-parse-error"
ACTION_FIX_INVALID_FILENAME: str = "fix-invalid-filename"
ACTION_REBUILD_PROJECTION: str = "rebuild-projection"
ACTION_UPDATE_STALE_TITLE: str = "update-stale-title"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MigrationFinding:
    """A single structured observation from the migration inspection.

    Attributes
    ----------
    kind:
        Machine-readable finding identifier (one of the ``FINDING_*`` constants).
    severity:
        ``error`` (blocker), ``warning`` (advisory), or ``info`` (informational).
    message:
        Human-readable description.
    source:
        Absolute path to the file this finding relates to, or *None* if the
        finding is repo-level.
    """

    kind: str
    severity: FindingSeverity
    message: str
    source: str | None = None


@dataclass
class MigrationAction:
    """A proposed (read-only) migration action — never executed by this module.

    Attributes
    ----------
    action_id:
        Unique machine-readable action ID (stable across runs for the same
        target and kind, so CLI consumers can diff/acknowledge individual
        actions).
    kind:
        Machine-readable action kind (one of the ``ACTION_*`` constants).
    description:
        Human-readable description of what the action does.
    target:
        Absolute path to the file this action targets, or *None* for
        repo-level actions (e.g. version upgrade).
    safe:
        *True* when this action can be applied without risk of data loss or
        identity conflict.  *False* when the action requires manual
        intervention (e.g. duplicate ULID resolution).
    """

    action_id: str
    kind: str
    description: str
    target: str | None = None
    safe: bool = True


@dataclass
class MigrationReport:
    """Complete read-only migration inspection result.

    Attributes
    ----------
    status:
        Overall migration status — ``ok``, ``needs-migration``, or ``blocked``.
    version_status:
        Classified strategy version status from :func:`inspect_strategy_file`.
    schema_version:
        The raw ``schema_version`` from the strategy frontmatter, or *None*
        when the file is absent/unreadable.
    current_version:
        The canonical current schema version string.
    ticket_inventory:
        Complete ticket inventory, or *None* when ``.megaplan/tickets/`` does
        not exist.
    findings:
        Ordered list of structured findings (version issues, identity problems,
        parse errors, etc.).
    blockers:
        Human-readable list of blocking issues (empty when migration is safe).
    proposed_actions:
        Ordered list of proposed (read-only) actions.
    safe_to_apply:
        *True* when no blockers exist and at least one action is proposed.
        Always *False* for unadopted repos (absent strategy is valid but
        there is nothing to migrate).
    tickets_dir_exists:
        *True* when ``.megaplan/tickets/`` exists as a directory.
    strategy_file_path:
        Absolute path to ``.megaplan/STRATEGY.md`` (may not exist).
    """

    status: MigrationStatus
    version_status: StrategyVersionStatus
    schema_version: str | None
    current_version: str
    ticket_inventory: TicketInventory | None
    findings: list[MigrationFinding] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    proposed_actions: list[MigrationAction] = field(default_factory=list)
    safe_to_apply: bool = False
    tickets_dir_exists: bool = False
    strategy_file_path: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inspect_strategy_migration(
    repo_root: str | Path,
    store: Any | None = None,
) -> MigrationReport:
    """Inspect a repository and return a complete migration report.

    This is the **doctor/migrate** entry point.  It examines the strategy
    file, ticket inventory, and (optionally) store-backed relationships and
    returns a structured :class:`MigrationReport` with findings, blockers,
    and proposed actions.  **No files are written.**

    Parameters
    ----------
    repo_root:
        Repository root path.  ``.megaplan/STRATEGY.md`` and
        ``.megaplan/tickets/`` are resolved relative to this root.
    store:
        Optional :class:`Store` instance.  When provided, ticket-epic
        relationship records are queried for additional diagnostics.
        When *None* (default), only file-backed artifacts are inspected.

    Returns
    -------
    MigrationReport
        Complete inspection result with findings, blockers, and proposed
        actions.
    """
    repo_root = Path(repo_root)
    strategy_path = strategy_file_path(repo_root)
    tickets_dir = repo_root / ".megaplan" / "tickets"
    tickets_dir_exists = tickets_dir.is_dir()

    # ------------------------------------------------------------------
    # 1. Strategy version inspection
    # ------------------------------------------------------------------
    version_status = inspect_strategy_file(repo_root)

    schema_version: str | None = None
    if version_status not in ("absent", "malformed"):
        try:
            source = strategy_path.read_text(encoding="utf-8")
            schema_version = _extract_schema_version_light(source)
        except Exception:
            schema_version = None

    findings: list[MigrationFinding] = []
    blockers: list[str] = []
    actions: list[MigrationAction] = []

    # ------------------------------------------------------------------
    # 2. Classify version status into findings / blockers / actions
    # ------------------------------------------------------------------
    _classify_version_status(
        version_status,
        schema_version,
        strategy_path,
        findings,
        blockers,
        actions,
    )

    # ------------------------------------------------------------------
    # 3. Ticket inventory
    # ------------------------------------------------------------------
    ticket_inventory: TicketInventory | None = None
    if tickets_dir_exists:
        ticket_inventory = build_ticket_inventory(repo_root)
        _classify_ticket_inventory(
            ticket_inventory,
            findings,
            blockers,
            actions,
        )
    else:
        findings.append(
            MigrationFinding(
                kind=FINDING_NO_TICKETS_DIR,
                severity="info",
                message="No .megaplan/tickets/ directory found — nothing to inventory.",
            )
        )

    # ------------------------------------------------------------------
    # 3b. Legacy bare-string / incomplete ticket 'epics' frontmatter links
    # ------------------------------------------------------------------
    _classify_legacy_ticket_epics(
        repo_root,
        ticket_inventory,
        findings,
        actions,
    )

    # ------------------------------------------------------------------
    # 4. Epic reference diagnostics (strategy roadmap → initiative dirs)
    # ------------------------------------------------------------------
    if version_status not in ("absent", "malformed"):
        _classify_epic_refs(
            repo_root,
            findings,
            blockers,
        )

    # ------------------------------------------------------------------
    # 5. Stale title diagnostics (strategy display titles vs actual)
    # ------------------------------------------------------------------
    if version_status not in ("absent", "malformed"):
        _classify_stale_titles(
            repo_root,
            ticket_inventory,
            findings,
        )

    # ------------------------------------------------------------------
    # 6. Projection drift diagnostics (on-disk vs rebuilt from Markdown)
    # ------------------------------------------------------------------
    if version_status not in ("absent", "malformed"):
        _classify_projection_drift(
            repo_root,
            findings,
            actions,
        )

    # ------------------------------------------------------------------
    # 7. Store-backed reconciliation (file authoritative, store advisory)
    # ------------------------------------------------------------------
    if store is not None and ticket_inventory is not None:
        _classify_store_reconciliation(
            store,
            repo_root,
            ticket_inventory,
            findings,
        )

    # ------------------------------------------------------------------
    # 8. Compute overall status and safe_to_apply
    # ------------------------------------------------------------------
    has_blockers = len(blockers) > 0
    has_actions = len(actions) > 0

    if version_status == "absent":
        # Valid unadopted state — no strategy to migrate, nothing to do.
        status: MigrationStatus = "ok"
        safe_to_apply = False
    elif has_blockers:
        status = "blocked"
        safe_to_apply = False
    elif has_actions:
        status = "needs-migration"
        safe_to_apply = True
    else:
        status = "ok"
        safe_to_apply = False

    return MigrationReport(
        status=status,
        version_status=version_status,
        schema_version=schema_version,
        current_version=CURRENT_SCHEMA_VERSION,
        ticket_inventory=ticket_inventory,
        findings=findings,
        blockers=blockers,
        proposed_actions=actions,
        safe_to_apply=safe_to_apply,
        tickets_dir_exists=tickets_dir_exists,
        strategy_file_path=str(strategy_path),
    )


# ---------------------------------------------------------------------------
# Internal helpers — version classification
# ---------------------------------------------------------------------------


def _classify_version_status(
    version_status: StrategyVersionStatus,
    schema_version: str | None,
    strategy_path: Path,
    findings: list[MigrationFinding],
    blockers: list[str],
    actions: list[MigrationAction],
) -> None:
    """Translate a version status into findings, blockers, and actions."""
    path_str = str(strategy_path)

    if version_status == "absent":
        findings.append(
            MigrationFinding(
                kind=FINDING_STRATEGY_ABSENT,
                severity="info",
                message="No .megaplan/STRATEGY.md found — repository has not adopted strategy tracking yet. This is a valid state.",
                source=path_str,
            )
        )
        # No blockers — absent strategy is valid.
        return

    if version_status == "current":
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_CURRENT,
                severity="info",
                message=f"Strategy schema version is current ({schema_version}).",
                source=path_str,
            )
        )
        return

    if version_status == "legacy":
        msg = (
            f"Strategy schema version '{schema_version}' is a recognized "
            f"legacy version. Upgrade to '{CURRENT_SCHEMA_VERSION}' is available."
        )
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_LEGACY,
                severity="warning",
                message=msg,
                source=path_str,
            )
        )
        _add_upgrade_action(actions, path_str, schema_version)
        return

    if version_status == "missing-version":
        msg = "Strategy file exists but frontmatter has no schema_version field."
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_MISSING,
                severity="warning",
                message=msg,
                source=path_str,
            )
        )
        _add_upgrade_action(actions, path_str, None)
        return

    if version_status == "unsupported-old":
        # Unknown/legacy schema versions predating the supported ``legacy``
        # band are *not* eligible for automated upgrade: there is no
        # documented reversible transformation. Refuse instead of silently
        # rewriting unknown old data.
        msg = (
            f"Strategy schema version '{schema_version}' is older than "
            f"the current version '{CURRENT_SCHEMA_VERSION}' and is not "
            f"in the recognized legacy set. Automated upgrade is not "
            f"available; manual review is required."
        )
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_UNSUPPORTED_OLD,
                severity="error",
                message=msg,
                source=path_str,
            )
        )
        blockers.append(
            f"Strategy version '{schema_version}' is an unknown old version "
            f"with no documented reversible upgrade path — manual review "
            f"is required before migration."
        )
        return

    if version_status == "unsupported-new":
        msg = (
            f"Strategy schema version '{schema_version}' is newer than "
            f"the current version '{CURRENT_SCHEMA_VERSION}'. "
            f"This tool cannot downgrade."
        )
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_UNSUPPORTED_NEW,
                severity="error",
                message=msg,
                source=path_str,
            )
        )
        blockers.append(
            f"Strategy version '{schema_version}' is too new — "
            f"upgrade the tool or use a compatible version."
        )
        return

    if version_status == "malformed":
        msg = "Strategy file exists but cannot be read or has invalid YAML frontmatter."
        findings.append(
            MigrationFinding(
                kind=FINDING_VERSION_MALFORMED,
                severity="error",
                message=msg,
                source=path_str,
            )
        )
        blockers.append(
            "Strategy file is malformed — fix YAML frontmatter before migration."
        )
        return


def _add_upgrade_action(
    actions: list[MigrationAction],
    path_str: str,
    schema_version: str | None,
) -> None:
    """Add a proposed version-upgrade action."""
    desc = (
        f"Upgrade strategy schema_version from "
        f"'{schema_version or '<missing>'}' to '{CURRENT_SCHEMA_VERSION}'."
    )
    actions.append(
        MigrationAction(
            action_id=_action_id(ACTION_UPGRADE_VERSION, path_str),
            kind=ACTION_UPGRADE_VERSION,
            description=desc,
            target=path_str,
            safe=True,
        )
    )


# ---------------------------------------------------------------------------
# Internal helpers — ticket inventory classification
# ---------------------------------------------------------------------------


def _classify_ticket_inventory(
    inventory: TicketInventory,
    findings: list[MigrationFinding],
    blockers: list[str],
    actions: list[MigrationAction],
) -> None:
    """Translate a ticket inventory into findings, blockers, and actions."""

    if inventory.total_files == 0:
        findings.append(
            MigrationFinding(
                kind=FINDING_TICKETS_PRESENT,
                severity="info",
                message=".megaplan/tickets/ exists but contains no .md files.",
            )
        )
        return

    findings.append(
        MigrationFinding(
            kind=FINDING_TICKETS_PRESENT,
            severity="info",
            message=(
                f"Found {inventory.total_files} ticket file(s), "
                f"{inventory.total_with_id} with frontmatter id, "
                f"{inventory.total_valid_ulid} with valid ULID, "
                f"{inventory.total_roadmap_eligible} roadmap-eligible."
            ),
        )
    )

    has_any_issues = False

    # --- Duplicate frontmatter IDs (blocker) ---------------------------------
    if inventory.duplicate_ids:
        has_any_issues = True
        dup_list = sorted(inventory.duplicate_ids.items(), key=lambda x: x[0])
        for dup_id, paths in dup_list:
            path_strs = [str(p) for p in paths]
            msg = (
                f"Duplicate frontmatter id '{dup_id}' found in "
                f"{len(paths)} files: {', '.join(path_strs)}"
            )
            findings.append(
                MigrationFinding(
                    kind=FINDING_DUPLICATE_IDS,
                    severity="error",
                    message=msg,
                    source=path_strs[0],
                )
            )
            blockers.append(
                f"Duplicate frontmatter id '{dup_id}' — each ticket must have "
                f"a unique ULID.  Resolve by assigning a new ULID to all but "
                f"one of the conflicting files."
            )
            actions.append(
                MigrationAction(
                    action_id=_action_id(
                        ACTION_RESOLVE_DUPLICATE, str(paths[0]), dup_id
                    ),
                    kind=ACTION_RESOLVE_DUPLICATE,
                    description=(
                        f"Resolve duplicate id '{dup_id}' across "
                        f"{len(paths)} files."
                    ),
                    target=str(paths[0]),
                    safe=False,
                )
            )

    # --- Per-entry findings --------------------------------------------------
    for entry in inventory.entries:
        path_str = str(entry.path)

        # Missing frontmatter id
        if not entry.has_id:
            findings.append(
                MigrationFinding(
                    kind=FINDING_MISSING_ID,
                    severity="warning",
                    message=f"Ticket file has no frontmatter 'id' field: {entry.path.name}",
                    source=path_str,
                )
            )
            actions.append(
                MigrationAction(
                    action_id=_action_id(ACTION_ADD_FRONTMATTER_ID, path_str),
                    kind=ACTION_ADD_FRONTMATTER_ID,
                    description=f"Add a canonical ULID frontmatter id to '{entry.path.name}'.",
                    target=path_str,
                    safe=True,
                )
            )

        # Invalid ULID (present but not valid)
        if entry.has_id and entry.canonical_ulid_valid is False:
            findings.append(
                MigrationFinding(
                    kind=FINDING_INVALID_ULID,
                    severity="error",
                    message=(
                        f"Frontmatter id '{entry.frontmatter_id}' in "
                        f"'{entry.path.name}' is not a valid ULID."
                    ),
                    source=path_str,
                )
            )
            blockers.append(
                f"Invalid frontmatter ULID '{entry.frontmatter_id}' in "
                f"'{entry.path.name}' — replace with a valid 26-character "
                f"Crockford-base32 ULID."
            )

        # Legacy filename (non-ulid filename prefix with valid frontmatter ULID)
        if (
            entry.filename_prefix_shape != "valid-ulid"
            and entry.canonical_ulid_valid is True
        ):
            findings.append(
                MigrationFinding(
                    kind=FINDING_LEGACY_FILENAME,
                    severity="warning",
                    message=(
                        f"Ticket '{entry.path.name}' has a non-canonical filename "
                        f"but a valid frontmatter ULID '{entry.frontmatter_id}'. "
                        f"Consider renaming to canonical form."
                    ),
                    source=path_str,
                )
            )
            actions.append(
                MigrationAction(
                    action_id=_action_id(ACTION_RENAME_FILE, path_str),
                    kind=ACTION_RENAME_FILE,
                    description=(
                        f"Rename '{entry.path.name}' to canonical "
                        f"'{entry.frontmatter_id}-<slug>.md' format."
                    ),
                    target=path_str,
                    safe=True,
                )
            )

        # Invalid filename prefix (26 chars but not a valid ULID)
        if entry.filename_prefix_shape == "invalid-ulid":
            findings.append(
                MigrationFinding(
                    kind=FINDING_INVALID_FILENAME_ULID,
                    severity="warning",
                    message=(
                        f"Ticket filename '{entry.path.name}' has a 26-character "
                        f"prefix that is not a valid Crockford-base32 ULID."
                    ),
                    source=path_str,
                )
            )
            if entry.canonical_ulid_valid is True:
                actions.append(
                    MigrationAction(
                        action_id=_action_id(
                            ACTION_FIX_INVALID_FILENAME, path_str
                        ),
                        kind=ACTION_FIX_INVALID_FILENAME,
                        description=(
                            f"Rename '{entry.path.name}' to use the canonical "
                            f"frontmatter ULID '{entry.frontmatter_id}'."
                        ),
                        target=path_str,
                        safe=True,
                    )
                )

        # Parse errors
        if entry.parse_errors:
            for err in entry.parse_errors:
                findings.append(
                    MigrationFinding(
                        kind=FINDING_PARSE_ERROR,
                        severity="warning",
                        message=f"Parse error in '{entry.path.name}': {err}",
                        source=path_str,
                    )
                )
            actions.append(
                MigrationAction(
                    action_id=_action_id(ACTION_FIX_PARSE_ERROR, path_str),
                    kind=ACTION_FIX_PARSE_ERROR,
                    description=(
                        f"Fix YAML frontmatter parse errors in "
                        f"'{entry.path.name}'."
                    ),
                    target=path_str,
                    safe=True,
                )
            )

        # Roadmap orphan: ticket has valid ULID but is not in the strategy roadmap
        if (
            entry.roadmap_eligible is False
            and entry.canonical_ulid_valid is True
            and not inventory.strategy_absent
        ):
            findings.append(
                MigrationFinding(
                    kind=FINDING_ROADMAP_ORPHAN,
                    severity="info",
                    message=(
                        f"Ticket '{entry.path.name}' (ULID '{entry.frontmatter_id}') "
                        f"is not referenced in the strategy roadmap."
                    ),
                    source=path_str,
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers — epic reference diagnostics
# ---------------------------------------------------------------------------

# Regex to extract ``epic:<slug>`` refs from strategy roadmap bullets.
_EPIC_BULLET_RE = re.compile(r"^-\s*\[epic:([^\]]+)\]")


def _extract_strategy_epic_refs(repo_root: Path) -> set[str] | None:
    """Extract the set of epic refs (initiative slugs) from the strategy roadmap.

    Returns a set of slug strings, or *None* when the strategy file is absent.
    """
    strategy_path = strategy_file_path(repo_root)
    if not strategy_path.is_file():
        return None

    try:
        source = strategy_path.read_text(encoding="utf-8")
    except OSError:
        return None

    refs: set[str] = set()
    for line in source.split("\n"):
        m = _EPIC_BULLET_RE.match(line)
        if m:
            slug = m.group(1).strip()
            if slug:
                refs.add(slug)

    return refs


def _classify_epic_refs(
    repo_root: Path,
    findings: list[MigrationFinding],
    blockers: list[str],
) -> None:
    """Check strategy epic refs against .megaplan/initiatives/ directories.

    File artifacts (initiative directories) are authoritative.  A strategy
    epic ref that points to a missing initiative directory is a blocking error.
    """
    epic_refs = _extract_strategy_epic_refs(repo_root)
    if epic_refs is None:
        return  # strategy absent — no epic refs to check

    initiatives_dir = repo_root / ".megaplan" / "initiatives"
    strategy_path = str(strategy_file_path(repo_root))

    for slug in sorted(epic_refs):
        initiative_dir = initiatives_dir / slug
        if not initiative_dir.is_dir():
            msg = (
                f"Epic ref '[epic:{slug}]' in strategy roadmap references "
                f"a missing initiative directory: .megaplan/initiatives/{slug}/"
            )
            findings.append(
                MigrationFinding(
                    kind=FINDING_MISSING_EPIC_REF,
                    severity="error",
                    message=msg,
                    source=strategy_path,
                )
            )
            blockers.append(
                f"Missing initiative directory for epic '{slug}' — "
                f"create .megaplan/initiatives/{slug}/ or remove the "
                f"epic ref from the strategy roadmap."
            )

        # Check for ambiguous refs (slug in strategy but README.md is absent)
        readme = initiative_dir / "README.md"
        if initiative_dir.is_dir() and not readme.is_file():
            findings.append(
                MigrationFinding(
                    kind=FINDING_AMBIGUOUS_EPIC_REF,
                    severity="warning",
                    message=(
                        f"Epic ref '[epic:{slug}]' has an initiative directory "
                        f"but no README.md — title resolution is not possible."
                    ),
                    source=str(initiative_dir),
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers — stale title diagnostics
# ---------------------------------------------------------------------------


def _read_ticket_title_from_file(file_path: Path) -> str | None:
    """Read the ``title`` field from a ticket's YAML frontmatter.

    Returns *None* if the file cannot be read or has no title.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Lightweight frontmatter extraction (same pattern as extract_schema_version_light).
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
    try:
        import yaml

        metadata = yaml.safe_load(fm_text)
    except Exception:
        return None

    if not isinstance(metadata, dict):
        return None

    title = metadata.get("title")
    if title is not None and str(title).strip():
        return str(title).strip()
    return None


def _read_initiative_title(repo_root: Path, slug: str) -> str | None:
    """Read the title from an initiative README.md (first ``# Title`` heading).

    Returns *None* if the README does not exist or has no title.
    """
    readme = repo_root / ".megaplan" / "initiatives" / slug / "README.md"
    if not readme.is_file():
        return None

    try:
        lines = readme.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip() or None

    return None


def _classify_stale_titles(
    repo_root: Path,
    inventory: TicketInventory | None,
    findings: list[MigrationFinding],
) -> None:
    """Compare strategy roadmap display titles to actual artifact titles.

    File artifacts are authoritative — the strategy's display title is
    advisory.  A mismatch is a warning (stale display title).
    """
    strategy_path = strategy_file_path(repo_root)
    if not strategy_path.is_file():
        return

    try:
        source = strategy_path.read_text(encoding="utf-8")
    except OSError:
        return

    # Extract ticket ref → display title from strategy roadmap.
    _TICKET_REF_RE = re.compile(
        r"^-\s*\[ticket:([0-9A-HJKMNP-TV-Z]{26})\]\s+(.*)$"
    )
    _EPIC_REF_RE = re.compile(r"^-\s*\[epic:([^\]]+)\]\s+(.*)$")

    strategy_ticket_titles: dict[str, str] = {}
    strategy_epic_titles: dict[str, str] = {}

    for line in source.split("\n"):
        m = _TICKET_REF_RE.match(line)
        if m:
            strategy_ticket_titles[m.group(1)] = m.group(2).strip()
            continue
        m = _EPIC_REF_RE.match(line)
        if m:
            strategy_epic_titles[m.group(1).strip()] = m.group(2).strip()

    # Compare ticket display titles (only if we have an inventory).
    if inventory is not None:
        for entry in inventory.entries:
            if not entry.frontmatter_id or not entry.canonical_ulid_valid:
                continue
            strategy_title = strategy_ticket_titles.get(entry.frontmatter_id)
            if strategy_title is None:
                continue  # not in roadmap — no title to compare

            actual_title = _read_ticket_title_from_file(entry.path)
            if actual_title is not None and actual_title != strategy_title:
                findings.append(
                    MigrationFinding(
                        kind=FINDING_STALE_TITLE,
                        severity="warning",
                        message=(
                            f"Stale display title for ticket '{entry.frontmatter_id}': "
                            f"strategy says '{strategy_title}', "
                            f"ticket title is '{actual_title}'."
                        ),
                        source=str(entry.path),
                    )
                )

    # Compare epic display titles.
    for slug, strategy_title in sorted(strategy_epic_titles.items()):
        actual_title = _read_initiative_title(repo_root, slug)
        if actual_title is not None and actual_title != strategy_title:
            findings.append(
                MigrationFinding(
                    kind=FINDING_STALE_TITLE,
                    severity="warning",
                    message=(
                        f"Stale display title for epic '{slug}': "
                        f"strategy says '{strategy_title}', "
                        f"initiative title is '{actual_title}'."
                    ),
                    source=str(strategy_path),
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers — projection drift diagnostics
# ---------------------------------------------------------------------------


def _classify_projection_drift(
    repo_root: Path,
    findings: list[MigrationFinding],
    actions: list[MigrationAction],
) -> None:
    """Detect projection drift by comparing on-disk projection to rebuilt.

    The projection JSON is disposable — it is rebuilt from the authoritative
    Markdown.  Drift means the on-disk projection is stale or foreign.
    """
    projection_path = strategy_projection_file_path(repo_root)
    strategy_path = strategy_file_path(repo_root)

    if not strategy_path.is_file():
        return  # No strategy → nothing to project

    if not projection_path.is_file():
        findings.append(
            MigrationFinding(
                kind=FINDING_PROJECTION_ABSENT,
                severity="info",
                message=(
                    "No strategy projection found at "
                    f"{projection_path}. It can be rebuilt from STRATEGY.md."
                ),
                source=str(strategy_path),
            )
        )
        # Absent projection is not an action — it is normal for a repo
        # that hasn't yet generated the projection.  Only drift (on-disk
        # projection exists but differs from rebuilt) warrants an action.
        return

    # Rebuild the projection from the authoritative Markdown.
    try:
        rebuilt = _rebuild_projection(repo_root)
    except Exception:
        # If we can't rebuild, we can't compare — projection drift is unknown.
        findings.append(
            MigrationFinding(
                kind=FINDING_PROJECTION_STALE,
                severity="warning",
                message=(
                    "Cannot rebuild projection from STRATEGY.md — "
                    "the strategy file may be malformed. "
                    "The on-disk projection may be stale."
                ),
                source=str(strategy_path),
            )
        )
        return

    if rebuilt is None:
        return  # Could not parse strategy

    # Read on-disk projection.
    try:
        on_disk_raw = projection_path.read_text(encoding="utf-8")
        on_disk = json.loads(on_disk_raw)
    except (OSError, json.JSONDecodeError):
        findings.append(
            MigrationFinding(
                kind=FINDING_PROJECTION_STALE,
                severity="warning",
                message=(
                    "On-disk projection is unreadable or invalid JSON. "
                    "It should be rebuilt from STRATEGY.md."
                ),
                source=str(projection_path),
            )
        )
        actions.append(
            MigrationAction(
                action_id=_action_id(ACTION_REBUILD_PROJECTION, str(projection_path)),
                kind=ACTION_REBUILD_PROJECTION,
                description="Rebuild unreadable projection from STRATEGY.md.",
                target=str(projection_path),
                safe=True,
            )
        )
        return

    # Compare normalized JSON.
    on_disk_norm = json.dumps(on_disk, sort_keys=True, indent=2)
    rebuilt_norm = json.dumps(rebuilt, sort_keys=True, indent=2)

    if on_disk_norm == rebuilt_norm:
        findings.append(
            MigrationFinding(
                kind=FINDING_PROJECTION_CURRENT,
                severity="info",
                message="Strategy projection is current (matches rebuilt from Markdown).",
                source=str(projection_path),
            )
        )
    else:
        findings.append(
            MigrationFinding(
                kind=FINDING_PROJECTION_DRIFT,
                severity="warning",
                message=(
                    "Strategy projection is stale — on-disk projection "
                    "differs from the projection rebuilt from STRATEGY.md. "
                    "Rebuild the projection to restore consistency."
                ),
                source=str(projection_path),
            )
        )
        actions.append(
            MigrationAction(
                action_id=_action_id(ACTION_REBUILD_PROJECTION, str(projection_path)),
                kind=ACTION_REBUILD_PROJECTION,
                description="Rebuild stale projection from STRATEGY.md.",
                target=str(projection_path),
                safe=True,
            )
        )


def _rebuild_projection(repo_root: Path) -> dict[str, Any] | None:
    """Rebuild the strategy projection from the authoritative Markdown.

    Returns the projection dict, or *None* if the strategy cannot be parsed.
    """
    try:
        from arnold_pipelines.megaplan.strategy.io import load_strategy

        document = load_strategy(str(repo_root))
    except Exception:
        return None

    try:
        from arnold_pipelines.megaplan.strategy.projection import project_strategy

        return project_strategy(document)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Internal helpers — store reconciliation (file authoritative, store advisory)
# ---------------------------------------------------------------------------


def _classify_store_reconciliation(
    store: Any,
    repo_root: Path,
    inventory: TicketInventory,
    findings: list[MigrationFinding],
) -> None:
    """Cross-reference store-backed rows against file artifacts.

    File artifacts are authoritative.  Store rows are advisory diagnostics.
    This function reports:

    * **Orphan store links**: store links where the ticket_id or epic_id
      does not correspond to any file artifact.
    * **File-vs-store mismatches**: informational findings about store
      rows that mirror file-backed relationships.
    """
    # Build a set of known ticket ULIDs from the inventory.
    known_ticket_ids: set[str] = set()
    for entry in inventory.entries:
        if entry.frontmatter_id and entry.canonical_ulid_valid:
            known_ticket_ids.add(entry.frontmatter_id)

    # Build a set of known initiative slugs from the filesystem.
    initiatives_dir = repo_root / ".megaplan" / "initiatives"
    known_epic_ids: set[str] = set()
    if initiatives_dir.is_dir():
        for child in initiatives_dir.iterdir():
            if child.is_dir():
                known_epic_ids.add(child.name)

    # Query all store links (no filter — get everything).
    try:
        all_links = store.list_ticket_epic_links()
    except Exception:
        # Store interaction failure is non-blocking.
        return

    if not all_links:
        return

    link_count = 0
    orphan_count = 0

    for link in all_links:
        link_count += 1
        ticket_id = getattr(link, "ticket_id", None)
        epic_id = getattr(link, "epic_id", None)

        ticket_orphan = ticket_id and ticket_id not in known_ticket_ids
        epic_orphan = epic_id and epic_id not in known_epic_ids

        if ticket_orphan or epic_orphan:
            orphan_count += 1
            parts: list[str] = []
            if ticket_orphan:
                parts.append(
                    f"ticket '{ticket_id}' not found in file inventory"
                )
            if epic_orphan:
                parts.append(
                    f"epic '{epic_id}' not found in .megaplan/initiatives/"
                )
            findings.append(
                MigrationFinding(
                    kind=FINDING_STORE_ORPHAN_LINK,
                    severity="warning",
                    message=(
                        f"Orphan store link: {', '.join(parts)}. "
                        f"Store row is advisory; file artifacts are authoritative."
                    ),
                    source=None,
                )
            )

    # Summary finding for store links.
    if link_count > 0:
        findings.append(
            MigrationFinding(
                kind="store-relationship",
                severity="info",
                message=(
                    f"Found {link_count} store-backed epic link(s) "
                    f"({orphan_count} orphan(s)). "
                    f"File artifacts are authoritative; store rows are advisory."
                ),
                source=None,
            )
        )


# ---------------------------------------------------------------------------
# Internal helpers — misc
# ---------------------------------------------------------------------------


def _extract_schema_version_light(source: str) -> str | None:
    """Lightweight schema_version extraction from YAML frontmatter.

    Returns *None* if the frontmatter is missing or invalid.
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
    try:
        import yaml

        metadata = yaml.safe_load(fm_text)
    except Exception:
        return None

    if not isinstance(metadata, dict):
        return None

    raw = metadata.get("schema_version")
    if raw is None:
        return None

    return str(raw)


def _action_id(kind: str, target: str, suffix: str = "") -> str:
    """Build a stable, machine-readable action ID."""
    import hashlib

    raw = f"{kind}:{target}:{suffix}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{kind}-{digest}"
