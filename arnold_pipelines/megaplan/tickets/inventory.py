"""Read-only ticket artifact inventory for migration, validator, and CLI diagnostics.

This module provides a **tolerant inspection surface** that walks every
``.md`` file under ``.megaplan/tickets/`` and records per-file metadata
without mutating anything.  It is the shared identity-classification entry
point for doctor/migrate tooling, the strategy validator's artifact
cross-check, and diagnostic CLI reports.

Design rules (North Star identity)
----------------------------------

* Identity is **only** derived from frontmatter ``id`` (a ULID).  Never
  from filename or title.
* Roadmap eligibility is determined by checking whether the frontmatter ULID
  appears in the strategy roadmap — again using only the frontmatter ``id``.
* Duplicate frontmatter IDs are reported with **all** involved file paths.
* Parse errors are collected per-file and surfaced in the inventory so
  downstream consumers (doctor, migrate, validator) can decide severity.

Public API
----------

* :func:`build_ticket_inventory` — walk ``.megaplan/tickets/`` and return a
  complete :class:`TicketInventory`.
* :class:`TicketInventory` — collection of :class:`TicketInventoryEntry`
  records plus a duplicate-id index.
* :class:`TicketInventoryEntry` — per-file metadata record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.tickets.files import (
    FilenamePrefixShape,
    classify_filename_prefix,
    is_valid_ulid,
    read_ticket_frontmatter_with_errors,
    tickets_dir,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TicketInventoryEntry:
    """Per-file metadata for a single ticket ``.md`` artifact.

    Attributes
    ----------
    path:
        Absolute path to the ticket file.
    filename_prefix_shape:
        Classification of the filename prefix segment.  One of
        ``"valid-ulid"``, ``"invalid-ulid"``, or ``"non-ulid"``.
    has_id:
        Whether the frontmatter contains an ``id`` field (of any value).
    has_title:
        Whether the frontmatter contains a non-empty ``title`` field.
    has_status:
        Whether the frontmatter contains a non-empty ``status`` field.
    has_body:
        Whether the markdown body (after frontmatter) is non-empty.
    frontmatter_id:
        The raw ``id`` value from frontmatter, or *None* if absent.
    canonical_ulid_valid:
        *True* when ``frontmatter_id`` is a well-formed 26-character
        Crockford-base32 ULID.  *False* when the id is present but not a
        valid ULID.  *None* when there is no ``id`` field.
    roadmap_eligible:
        *True* when ``frontmatter_id`` is a canonical ULID **and** that ULID
        appears as a ``[ticket:<ULID>]`` entry in the current strategy
        roadmap.  *False* when the ticket is not in the roadmap.  *None*
        when the strategy file is absent (roadmap eligibility cannot be
        determined).
    parse_errors:
        Human-readable error strings from frontmatter parsing (empty when
        the file was read cleanly).  A non-empty list does not mean the
        entry is unusable — downstream consumers decide severity.
    """

    path: Path
    filename_prefix_shape: FilenamePrefixShape
    has_id: bool
    has_title: bool
    has_status: bool
    has_body: bool
    frontmatter_id: str | None
    canonical_ulid_valid: bool | None
    roadmap_eligible: bool | None
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class TicketInventory:
    """Complete read-only snapshot of every ticket artifact in a repo.

    Attributes
    ----------
    entries:
        One record per ``.md`` file found under ``.megaplan/tickets/``,
        sorted by path for deterministic output.
    duplicate_ids:
        Map from a non-unique frontmatter ``id`` string to the list of
        **all** file paths that share that id.  Empty when every ticket has
        a unique id (or no id at all).
    total_files:
        Total number of ``.md`` files discovered.
    total_with_id:
        Count of entries where ``has_id`` is *True*.
    total_valid_ulid:
        Count of entries where ``canonical_ulid_valid`` is *True*.
    total_roadmap_eligible:
        Count of entries where ``roadmap_eligible`` is *True*.
    total_with_parse_errors:
        Count of entries with at least one parse error.
    strategy_absent:
        *True* when ``.megaplan/STRATEGY.md`` does not exist (roadmap
        eligibility cannot be determined for any ticket).
    """

    entries: list[TicketInventoryEntry]
    duplicate_ids: dict[str, list[Path]]
    total_files: int
    total_with_id: int
    total_valid_ulid: int
    total_roadmap_eligible: int
    total_with_parse_errors: int
    strategy_absent: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# Regex to extract ``ticket:<ULID>`` refs from strategy roadmap bullets.
# Matches ``- [ticket:01KT50AZRMK5X890TQ565DDB5V] ...``
_TICKET_BULLET_RE = re.compile(r"^-\s*\[ticket:([0-9A-HJKMNP-TV-Z]{26})\]")


def _extract_strategy_ticket_refs(repo_root: str | Path) -> set[str] | None:
    """Extract the set of ticket ULIDs referenced in the strategy roadmap.

    Returns a set of uppercase ULID strings, or *None* when the strategy
    file is absent (so callers can distinguish "no roadmap" from
    "empty roadmap").

    This is a **lightweight regex extraction** — it does not parse or
    validate the full strategy document.  Malformed bullets are silently
    skipped so that a partially-correct roadmap does not block inventory
    of healthy ticket files.
    """
    strategy_path = Path(repo_root) / ".megaplan" / "STRATEGY.md"
    if not strategy_path.is_file():
        return None

    try:
        source = strategy_path.read_text(encoding="utf-8")
    except OSError:
        return None

    refs: set[str] = set()
    for line in source.split("\n"):
        m = _TICKET_BULLET_RE.match(line)
        if m:
            refs.add(m.group(1))

    return refs


def _build_entry(
    file_path: Path,
    roadmap_ticket_refs: set[str] | None,
) -> TicketInventoryEntry:
    """Build a single :class:`TicketInventoryEntry` from a ticket file path."""
    fm, errors = read_ticket_frontmatter_with_errors(file_path)

    # --- frontmatter field presence -------------------------------------------
    has_id = False
    has_title = False
    has_status = False
    has_body = False
    frontmatter_id: str | None = None

    if fm is not None:
        raw_id = fm.get("id")
        if raw_id is not None:
            has_id = True
            frontmatter_id = str(raw_id)

        raw_title = fm.get("title")
        if raw_title is not None and str(raw_title).strip():
            has_title = True

        raw_status = fm.get("status")
        if raw_status is not None and str(raw_status).strip():
            has_status = True

        body = fm.get("__body__", "")
        if body and body.strip():
            has_body = True

    # --- canonical ULID validity ----------------------------------------------
    canonical_ulid_valid: bool | None
    if frontmatter_id is None:
        canonical_ulid_valid = None
    else:
        canonical_ulid_valid = is_valid_ulid(frontmatter_id)

    # --- roadmap eligibility --------------------------------------------------
    # Only frontmatter ULIDs determine eligibility — never filenames or titles.
    roadmap_eligible: bool | None
    if roadmap_ticket_refs is None:
        # Strategy absent → cannot determine eligibility.
        roadmap_eligible = None
    elif frontmatter_id is not None and canonical_ulid_valid:
        roadmap_eligible = frontmatter_id in roadmap_ticket_refs
    else:
        # No valid ULID → cannot be roadmap-eligible.
        roadmap_eligible = False

    # --- filename prefix shape ------------------------------------------------
    prefix_shape = classify_filename_prefix(file_path.name)

    return TicketInventoryEntry(
        path=file_path.resolve(),
        filename_prefix_shape=prefix_shape,
        has_id=has_id,
        has_title=has_title,
        has_status=has_status,
        has_body=has_body,
        frontmatter_id=frontmatter_id,
        canonical_ulid_valid=canonical_ulid_valid,
        roadmap_eligible=roadmap_eligible,
        parse_errors=errors,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_ticket_inventory(repo_root: str | Path) -> TicketInventory:
    """Build a complete read-only inventory of every ticket artifact.

    Walks all ``.md`` files under ``.megaplan/tickets/`` and records
    per-file metadata: filename prefix shape, frontmatter field presence,
    parse errors, canonical ULID validity, and roadmap eligibility.

    Duplicate frontmatter ``id`` values are detected and reported with
    **all** involved paths.

    Parameters
    ----------
    repo_root:
        Repository root path.  ``.megaplan/tickets/`` is resolved relative
        to this root.

    Returns
    -------
    TicketInventory
        Complete inventory snapshot with entries, duplicate-id index, and
        summary counts.
    """
    repo_root = Path(repo_root)
    td = tickets_dir(repo_root)

    # --- Extract strategy ticket refs for roadmap eligibility -----------------
    roadmap_ticket_refs = _extract_strategy_ticket_refs(repo_root)
    strategy_absent = roadmap_ticket_refs is None

    # --- Walk ticket files ----------------------------------------------------
    entries: list[TicketInventoryEntry] = []

    if td.is_dir():
        for entry_path in sorted(td.iterdir()):
            if not entry_path.suffix == ".md":
                continue
            if not entry_path.is_file():
                continue
            entry = _build_entry(entry_path, roadmap_ticket_refs)
            entries.append(entry)

    # Sort deterministically by path.
    entries.sort(key=lambda e: str(e.path))

    # --- Detect duplicate frontmatter IDs -------------------------------------
    id_to_paths: dict[str, list[Path]] = {}
    for entry in entries:
        if entry.frontmatter_id is not None:
            fid = entry.frontmatter_id
            id_to_paths.setdefault(fid, []).append(entry.path)

    duplicate_ids: dict[str, list[Path]] = {}
    for fid, paths in id_to_paths.items():
        if len(paths) > 1:
            duplicate_ids[fid] = sorted(paths, key=str)

    # --- Summary counts -------------------------------------------------------
    total_files = len(entries)
    total_with_id = sum(1 for e in entries if e.has_id)
    total_valid_ulid = sum(1 for e in entries if e.canonical_ulid_valid is True)
    total_roadmap_eligible = sum(1 for e in entries if e.roadmap_eligible is True)
    total_with_parse_errors = sum(1 for e in entries if e.parse_errors)

    return TicketInventory(
        entries=entries,
        duplicate_ids=duplicate_ids,
        total_files=total_files,
        total_with_id=total_with_id,
        total_valid_ulid=total_valid_ulid,
        total_roadmap_eligible=total_roadmap_eligible,
        total_with_parse_errors=total_with_parse_errors,
        strategy_absent=strategy_absent,
    )
