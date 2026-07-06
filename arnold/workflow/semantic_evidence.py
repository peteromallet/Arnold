"""Structured semantic evidence records for workflow source checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.workflow.refs import SourceSpan


@dataclass(frozen=True)
class SemanticEvidence:
    """Evidence that a workflow source construct satisfies a semantic row."""

    row_id: str
    source_span: SourceSpan
    construct_type: str
    diagnostic_code: str | None = None
    evidence_kind: str | None = None
    refs: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "refs", dict(self.refs))
        object.__setattr__(self, "details", dict(self.details))
