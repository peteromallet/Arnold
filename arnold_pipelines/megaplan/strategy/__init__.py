"""Strategy contract models and constants.

This package provides the typed contract for Megaplan strategy documents
(``.megaplan/STRATEGY.md``).  The contract layer is the single source of
truth for data shapes; parsers, validators, resolvers, and projectors all
consume and produce these types.

Core types
----------

* :class:`StrategyDocument` — the top-level parsed document.
* :class:`StrategySection` — a stable-direction section.
* :class:`RoadmapEntry` — a single roadmap bullet.
* :class:`StrategyIdentity` — immutable ``(type, ref)`` pair.
* :class:`StrategyDiagnostic` — a validation diagnostic with source location.
* :class:`SourceLocation` — path, line, and column.

Constants
---------

* ``SCHEMA_VERSION`` — ``"megaplan-strategy-v1"``.
* ``PROJECTION_SCHEMA_VERSION`` — ``"megaplan-strategy-projection-v1"``.
* ``REQUIRED_STABLE_SECTIONS`` — ordered tuple of required section titles.
* ``REQUIRED_ROADMAP_SECTIONS`` — ordered tuple of required horizon titles.

Type aliases
------------

* ``RoadmapItemType`` — ``Literal["ticket", "epic"]``.
* ``RoadmapHorizon`` — ``Literal["Now", "Next", "Later"]``.
* ``DiagnosticLevel`` — ``Literal["error", "warning"]``.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.strategy.contract import (
    DiagnosticLevel,
    PROJECTION_SCHEMA_VERSION,
    REQUIRED_ROADMAP_SECTIONS,
    REQUIRED_STABLE_SECTIONS,
    SCHEMA_VERSION,
    RoadmapEntry,
    RoadmapHorizon,
    RoadmapItemType,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.parser import (
    parse_strategy,
    serialize_strategy,
)
from arnold_pipelines.megaplan.strategy.resolver import (
    resolve_strategy,
)
from arnold_pipelines.megaplan.strategy.validation import (
    validate_strategy,
)
from arnold_pipelines.megaplan.strategy.projection import (
    project_strategy,
    serialize_strategy_projection,
    write_strategy_projection,
)
from arnold_pipelines.megaplan.strategy.mutations import (
    add_roadmap_entry,
    make_roadmap_entry,
    move_roadmap_entry,
    promote_ticket_to_epic,
    remove_roadmap_entry,
    replace_roadmap_entry,
)
from arnold_pipelines.megaplan.strategy.io import (
    StrategyConflictError,
    StrategyFileState,
    format_diagnostic,
    format_diagnostics,
    load_strategy,
    load_strategy_for_write,
    load_strategy_projection,
    project_to_dict,
    project_to_json,
    strategy_file_path,
    strategy_projection_file_path,
    write_projection,
    write_strategy,
)

__all__ = [
    "DiagnosticLevel",
    "PROJECTION_SCHEMA_VERSION",
    "REQUIRED_ROADMAP_SECTIONS",
    "REQUIRED_STABLE_SECTIONS",
    "RoadmapEntry",
    "RoadmapHorizon",
    "RoadmapItemType",
    "SCHEMA_VERSION",
    "SourceLocation",
    "StrategyDiagnostic",
    "StrategyDocument",
    "StrategyIdentity",
    "StrategySection",
    "StrategyConflictError",
    "StrategyFileState",
    "add_roadmap_entry",
    "format_diagnostic",
    "format_diagnostics",
    "load_strategy",
    "load_strategy_for_write",
    "load_strategy_projection",
    "make_roadmap_entry",
    "move_roadmap_entry",
    "parse_strategy",
    "project_strategy",
    "project_to_dict",
    "project_to_json",
    "promote_ticket_to_epic",
    "remove_roadmap_entry",
    "replace_roadmap_entry",
    "resolve_strategy",
    "serialize_strategy",
    "serialize_strategy_projection",
    "strategy_file_path",
    "strategy_projection_file_path",
    "validate_strategy",
    "write_projection",
    "write_strategy",
    "write_strategy_projection",
]
