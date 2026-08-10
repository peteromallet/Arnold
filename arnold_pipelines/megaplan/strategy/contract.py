"""Typed contract models for the v1 strategy document.

This module defines the immutable data types that parsers, validators, and
projectors consume and produce.  Every type is frozen so downstream code
cannot accidentally mutate a parsed document.

Key design rules (enforced by absence, not comments):

* Identity is exactly ``(type, ref)`` — titles are mutable display text.
* No artifact body or lifecycle-status fields appear anywhere.
* Horizons are independent of artifact type.
* Diagnostics carry source location (path, line, column).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "megaplan-strategy-v1"
"""Canonical strategy Markdown schema version."""

PROJECTION_SCHEMA_VERSION = "megaplan-strategy-projection-v1"
"""Canonical projection JSON schema version."""

# Required stable-direction section titles (case-sensitive, in order).
REQUIRED_STABLE_SECTIONS: tuple[str, ...] = (
    "Mission",
    "Principles",
    "Architecture Direction",
    "Constraints",
    "Non-Goals",
)

# Required roadmap section titles (case-sensitive, in order).
REQUIRED_ROADMAP_SECTIONS: tuple[str, ...] = (
    "Now",
    "Next",
    "Later",
)

# ---------------------------------------------------------------------------
# Source location
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceLocation:
    """Location of a construct in a source file.

    Line and column are 1-indexed to match typical editor and parser
    conventions.
    """

    path: str
    line: int
    column: int


# ---------------------------------------------------------------------------
# Type literals
# ---------------------------------------------------------------------------

RoadmapItemType = Literal["ticket", "epic"]
"""Valid executable item types in a strategy roadmap.

Only ``ticket`` and ``epic`` are recognized.  Any other value produces a
hard diagnostic.
"""

RoadmapHorizon = Literal["Now", "Next", "Later"]
"""Valid roadmap horizon labels.

Horizons are independent of artifact type — both ``ticket`` and ``epic``
entries are accepted in any horizon.
"""

DiagnosticLevel = Literal["error", "warning"]
"""Severity level for a strategy diagnostic.

``error`` diagnostics are blocking; ``warning`` diagnostics are advisory.
"""

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyIdentity:
    """Immutable identity for a roadmap entry: ``(type, ref)``.

    This pair MUST be unique across all horizons.  Titles are mutable
    display text and are never part of identity.
    """

    type: RoadmapItemType
    ref: str


# ---------------------------------------------------------------------------
# Document fragments
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategySection:
    """A stable-direction section with its Markdown body.

    Section titles are matched case-sensitively.  The body is preserved
    as-authored and never normalized.
    """

    title: str
    body: str
    source_location: SourceLocation


@dataclass(frozen=True)
class RoadmapEntry:
    """A single roadmap bullet parsed from a horizon section.

    The entry references an external artifact via its identity; it does
    NOT duplicate the artifact's body, lifecycle status, plans, or
    completion evidence.
    """

    identity: StrategyIdentity
    display_title: str
    horizon: RoadmapHorizon
    source_location: SourceLocation


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyDiagnostic:
    """A validation diagnostic with source location.

    ``source_location`` may be ``None`` for diagnostics that are not
    tied to a specific position in the source file (e.g. "file not
    found").
    """

    level: DiagnosticLevel
    message: str
    source_location: SourceLocation | None = None


# ---------------------------------------------------------------------------
# Top-level document
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyDocument:
    """The parsed and validated strategy document.

    This is the single source of truth produced by the parser and consumed
    by validators, resolvers, and the projection serializer.

    Attributes:
        schema_version: The frontmatter ``schema_version`` value.
        stable_direction: Ordered stable-direction sections.
        roadmap: Roadmap entries grouped by horizon.  Horizon keys are
            always present (``Now``, ``Next``, ``Later``) even if the
            corresponding entry list is empty.
        diagnostics: All diagnostics collected during parsing and
            validation.  An empty list means the document is clean.
    """

    schema_version: str
    stable_direction: list[StrategySection]
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]]
    diagnostics: list[StrategyDiagnostic]
