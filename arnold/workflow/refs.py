"""Stable workflow reference primitives.

These dataclasses are the contract-level coordinates used to name workflow
nodes, edges, authored source spans, structured values, and runtime cursors.
They do not import product pipelines or runtime implementations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _require_ref_segment(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be non-empty")
    if not _REF_SEGMENT_RE.fullmatch(value):
        raise ValueError(f"{name} contains characters outside the ref alphabet: {value!r}")
    return value


def canonical_alias(alias: str) -> str:
    """Return a validated human workflow alias.

    The alias is intentionally not folded or slugified. A workflow author's
    ``Pipeline.id`` remains the human-visible name, and runtime identity is
    disambiguated by pairing this alias with a manifest hash.
    """

    if not _ALIAS_RE.fullmatch(alias):
        raise ValueError(
            "workflow alias must start with a letter and contain only letters, "
            "digits, '_', '.', or '-'"
        )
    return alias


def _canonical_manifest_hash(manifest_hash: str) -> str:
    normalized = manifest_hash.lower()
    if not _HASH_RE.fullmatch(normalized):
        raise ValueError("manifest_hash must be 'sha256:' followed by 64 lowercase hex characters")
    return normalized


@dataclass(frozen=True, order=True)
class NodeRef:
    """Stable reference to a workflow manifest node."""

    id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref_segment("node id", self.id))

    @property
    def key(self) -> str:
        return f"node:{self.id}"

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class EdgeRef:
    """Stable reference to a directed manifest edge."""

    source: NodeRef
    target: NodeRef
    label: str = "default"

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _require_ref_segment("edge label", self.label))

    @property
    def key(self) -> str:
        return f"edge:{self.source.id}->{self.target.id}:{self.label}"

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class SourceSpan:
    """Authored source span for diagnostics and replay provenance."""

    path: str
    start_line: int
    start_column: int = 1
    end_line: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("source path must be non-empty")
        if self.start_line < 1:
            raise ValueError("start_line must be >= 1")
        if self.start_column < 1:
            raise ValueError("start_column must be >= 1")
        if self.end_line is not None and self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        if self.end_column is not None and self.end_column < 1:
            raise ValueError("end_column must be >= 1")

    @property
    def key(self) -> str:
        end_line = self.end_line if self.end_line is not None else self.start_line
        end_column = self.end_column if self.end_column is not None else self.start_column
        return f"source:{self.path}:{self.start_line}:{self.start_column}-{end_line}:{end_column}"

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class SourceRef:
    """Stable reference to an authored source element."""

    id: str
    span: SourceSpan | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref_segment("source id", self.id))

    @property
    def key(self) -> str:
        if self.span is None:
            return f"source-ref:{self.id}"
        return f"source-ref:{self.id}@{self.span.key}"

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class ValueRef:
    """Stable reference to a named value emitted or consumed by a node."""

    node: NodeRef
    name: str
    schema_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_ref_segment("value name", self.name))
        if self.schema_hash is not None:
            object.__setattr__(self, "schema_hash", _canonical_manifest_hash(self.schema_hash))

    @property
    def key(self) -> str:
        base = f"value:{self.node.id}.{self.name}"
        if self.schema_hash is None:
            return base
        return f"{base}@{self.schema_hash}"

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class ManifestCoordinate:
    """Runtime coordinate derived from human alias plus manifest hash."""

    alias: str
    manifest_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alias", canonical_alias(self.alias))
        object.__setattr__(self, "manifest_hash", _canonical_manifest_hash(self.manifest_hash))

    @property
    def key(self) -> str:
        return f"workflow:{self.alias}@{self.manifest_hash}"

    def cursor(
        self,
        *,
        node: NodeRef | None = None,
        edge: EdgeRef | None = None,
        value: ValueRef | None = None,
        reentry_id: str | None = None,
    ) -> "ManifestCursor":
        return ManifestCursor(
            coordinate=self,
            node=node,
            edge=edge,
            value=value,
            reentry_id=reentry_id,
        )

    def __str__(self) -> str:
        return self.key


@dataclass(frozen=True, order=True)
class ManifestCursor:
    """Runtime cursor into a specific workflow manifest coordinate."""

    coordinate: ManifestCoordinate
    node: NodeRef | None = None
    edge: EdgeRef | None = None
    value: ValueRef | None = None
    reentry_id: str | None = None

    def __post_init__(self) -> None:
        if self.reentry_id is not None:
            object.__setattr__(self, "reentry_id", _require_ref_segment("reentry_id", self.reentry_id))

    @property
    def key(self) -> str:
        parts = [self.coordinate.key]
        if self.node is not None:
            parts.append(str(self.node))
        if self.edge is not None:
            parts.append(str(self.edge))
        if self.value is not None:
            parts.append(str(self.value))
        if self.reentry_id is not None:
            parts.append(f"reentry:{self.reentry_id}")
        return "#".join(parts)

    def __str__(self) -> str:
        return self.key


def manifest_coordinate(alias: str, manifest_hash: str) -> ManifestCoordinate:
    """Build the canonical runtime coordinate for a workflow manifest."""

    return ManifestCoordinate(alias=alias, manifest_hash=manifest_hash)
