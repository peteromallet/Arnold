"""Strategy version negotiation — classification without authority assumption.

This module defines the version policy for ``.megaplan/STRATEGY.md`` and
provides **inspection-only** paths that classify a strategy file's version
state **without** treating it as a valid authoritative document.

The inspection surface exists solely for doctor/migrate tooling.  Normal
strict commands (validate, add, move, remove, project, etc.) must route
through :func:`arnold_pipelines.megaplan.strategy.io.load_strategy` which
remains fail-closed: absent files and unsupported versions are hard errors
for normal authority commands.

Public API
----------

Version classification
    * :class:`StrategyVersionStatus` — literal enum of classified version states.
    * :func:`classify_version` — classify a (version_string, file_exists) pair.
    * :func:`inspect_strategy_file` — inspect a repo's strategy file on disk
      and return its version status without full parsing.

Constants
    * ``CURRENT_SCHEMA_VERSION`` — ``"megaplan-strategy-v1"`` (canonical).
    * ``SUPPORTED_VERSIONS`` — frozen set of known/recognized version strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from arnold_pipelines.megaplan.layout import strategy_file_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION: str = "megaplan-strategy-v1"
"""Canonical current schema version — the only version treated as authoritative."""

# All known/released schema version strings.  This is the *recognition* set;
# only ``CURRENT_SCHEMA_VERSION`` is treated as authoritative.
SUPPORTED_VERSIONS: frozenset[str] = frozenset({CURRENT_SCHEMA_VERSION})
"""Frozen set of all schema versions recognized by this version of the tool.

Migrations may add older version strings here so doctor can distinguish
'legacy' from 'unsupported-old', but only CURRENT_SCHEMA_VERSION is
treated as valid authority by strict commands.
"""

# Versions known to be *older* than the current version (for legacy
# classification).  Empty until a v2 or later schema is defined.
LEGACY_VERSIONS: frozenset[str] = frozenset()
"""Versions that predate the current version.  Entries here are classified as
'legacy' rather than 'unsupported-old'."""

# Versions known to be *newer* than the current version (for unsupported-new
# classification).  Currently empty.
FUTURE_VERSIONS: frozenset[str] = frozenset()
"""Versions known to postdate the current version.  Entries here are classified
as 'unsupported-new' rather than 'unsupported-old'."""

# ---------------------------------------------------------------------------
# Version status literal
# ---------------------------------------------------------------------------

# The inspection-only classification of a strategy file's version state.
# These are *not* authority judgments — they are informational labels for
# doctor/migrate tooling.
StrategyVersionStatus = Literal[
    "absent",          # .megaplan/STRATEGY.md does not exist (unadopted repo)
    "missing-version", # file exists but frontmatter has no schema_version
    "legacy",          # recognized old version (in LEGACY_VERSIONS)
    "current",         # matches CURRENT_SCHEMA_VERSION
    "unsupported-old", # older than current, not in LEGACY_VERSIONS
    "unsupported-new", # newer than current, not in SUPPORTED_VERSIONS
    "malformed",       # file exists but can't be read or has invalid YAML
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_version(
    schema_version: str | None,
    file_exists: bool,
) -> StrategyVersionStatus:
    """Classify a (version_string, file_exists) pair into a version status.

    This is the pure classification function — it does not touch the
    filesystem.  Use :func:`inspect_strategy_file` for a disk-aware
    inspection.

    Parameters
    ----------
    schema_version:
        The ``schema_version`` value extracted from the frontmatter, or
        ``None`` if the frontmatter was missing or unparseable.
    file_exists:
        Whether the strategy file exists on disk.

    Returns
    -------
    StrategyVersionStatus
        One of the seven literal status values.
    """
    if not file_exists:
        return "absent"

    if schema_version is None:
        return "malformed"

    sv = schema_version.strip()
    if not sv:
        return "missing-version"

    if sv == CURRENT_SCHEMA_VERSION:
        return "current"

    if sv in LEGACY_VERSIONS:
        return "legacy"

    if sv in SUPPORTED_VERSIONS:
        # Recognized but not current — currently unreachable since
        # SUPPORTED_VERSIONS only contains CURRENT_SCHEMA_VERSION, but this
        # arm handles future expansions safely.
        return "legacy"

    if sv in FUTURE_VERSIONS:
        return "unsupported-new"

    # Heuristic: compare version strings to distinguish old vs new when
    # the version is not in any known set.
    # The convention is "megaplan-strategy-vN" — we extract the trailing
    # integer if present.
    current_ver_num = _extract_version_number(CURRENT_SCHEMA_VERSION)
    observed_ver_num = _extract_version_number(sv)

    if observed_ver_num is not None and current_ver_num is not None:
        if observed_ver_num < current_ver_num:
            return "unsupported-old"
        if observed_ver_num > current_ver_num:
            return "unsupported-new"

    # Fallback: if we can't extract version numbers, treat unknown as
    # unsupported-old (conservative — oldest possible interpretation).
    return "unsupported-old"


def inspect_strategy_file(
    repo_root: str | Path,
) -> StrategyVersionStatus:
    """Inspect the strategy file on disk and return its version status.

    This is an **inspection-only** path for doctor/migrate tooling.  It
    extracts the ``schema_version`` from the frontmatter (without full
    parsing of sections or roadmap entries) and classifies the version
    state.  It never treats an absent or unsupported-version file as a
    valid authority source.

    Parameters
    ----------
    repo_root:
        Repository root path.  ``.megaplan/STRATEGY.md`` is resolved
        relative to this root.

    Returns
    -------
    StrategyVersionStatus
        The classified version status of the strategy file.
    """
    path = strategy_file_path(repo_root)

    if not path.is_file():
        return "absent"

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "malformed"

    schema_version = _extract_frontmatter_version(source)

    # If we couldn't extract a version at all, the file is malformed.
    if schema_version is None:
        return "malformed"

    return classify_version(schema_version, file_exists=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter_version(source: str) -> str | None:
    """Extract the ``schema_version`` value from YAML frontmatter.

    Returns ``None`` if the frontmatter is missing, unclosed, or contains
    invalid YAML.  This is a lightweight parse — it does not validate
    sections or roadmap bullets.
    """
    lines = source.split("\n")

    # Must start with '---'
    if not lines or lines[0].strip() != "---":
        return None

    # Find closing '---'
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    # Parse YAML between fences
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
        return ""  # explicit missing → classify as "missing-version"

    return str(raw)


def _extract_version_number(version_string: str) -> int | None:
    """Extract the trailing integer from a ``megaplan-strategy-vN`` string.

    Returns ``None`` if the version string does not match the expected
    pattern.
    """
    import re
    m = re.search(r"v(\d+)$", version_string)
    if m is None:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None
