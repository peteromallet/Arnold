from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping


Severity = Literal["error", "warning", "info"]

SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})


def _validate_severity(severity: str) -> None:
    if severity not in SEVERITIES:
        allowed = ", ".join(sorted(SEVERITIES))
        raise ValueError(f"severity must be one of {allowed}; got {severity!r}")


@dataclass(slots=True)
class PortIssue:
    code: str
    message: str
    severity: Severity = "error"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    recommendation: str | None = None

    def __post_init__(self) -> None:
        _validate_severity(self.severity)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PortArtifact:
    kind: str
    path: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NodePackSuggestion:
    pack_name: str
    repo: str | None = None
    matched_classes: list[str] = field(default_factory=list)
    missing_classes: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AssetCandidate:
    name: str
    source: str
    url: str | None = None
    subdir: str | None = None
    node_id: str | None = None
    class_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AssetCheckResult:
    url: str
    ok: bool
    status_code: int | None = None
    final_url: str | None = None
    elapsed_ms: int | None = None
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PortReport:
    source: str
    provenance: dict[str, Any] = field(default_factory=dict)
    source_hash: str | None = None
    workflow_id: str | None = None
    workflow_shape: dict[str, Any] = field(default_factory=dict)
    node_counts: dict[str, int] = field(default_factory=dict)
    output_mode: str | None = None
    diagnostics: list[PortIssue] = field(default_factory=list)
    artifacts: list[PortArtifact] = field(default_factory=list)
    node_pack_suggestions: list[NodePackSuggestion] = field(default_factory=list)
    asset_candidates: list[AssetCandidate] = field(default_factory=list)
    asset_checks: list[AssetCheckResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.has_errors

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.diagnostics)

    def add_issue(
        self,
        code: str,
        message: str,
        *,
        severity: Severity = "error",
        node_id: str | None = None,
        class_type: str | None = None,
        detail: Mapping[str, Any] | None = None,
        recommendation: str | None = None,
    ) -> PortIssue:
        issue = PortIssue(
            code=code,
            message=message,
            severity=severity,
            node_id=node_id,
            class_type=class_type,
            detail=dict(detail or {}),
            recommendation=recommendation,
        )
        self.diagnostics.append(issue)
        return issue

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload
