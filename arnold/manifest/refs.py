"""Stable workflow reference primitives.

These dataclasses are the contract-level coordinates used to name workflow
nodes, edges, authored source spans, structured values, and runtime cursors.
They do not import product pipelines or runtime implementations.
"""

from __future__ import annotations

import importlib
import inspect
import re
from dataclasses import dataclass
from typing import Any

_ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_PYTHON_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


class RefDiagnosticError(ValueError):
    """Raised when a workflow ref would capture unstable runtime identity."""


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


def _diagnostic_prefix(*, node_id: str | None, field: str | None) -> str:
    parts: list[str] = []
    if node_id is not None:
        parts.append(f"node {node_id!r}")
    if field is not None:
        parts.append(f"field {field!r}")
    if not parts:
        return ""
    return " ".join(parts) + ": "


def _unstable_ref_error(reason: str, *, node_id: str | None, field: str | None) -> RefDiagnosticError:
    remediation = (
        "use an importable module-level function or class/static function and pass "
        "its 'module:qualname' reference instead of a live Python object"
    )
    return RefDiagnosticError(f"{_diagnostic_prefix(node_id=node_id, field=field)}{reason}; {remediation}")


def _require_python_dotted(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be non-empty")
    if "<locals>" in value or "<lambda>" in value:
        raise ValueError(f"{name} must name an importable module-level or class/static function")
    if not _PYTHON_DOTTED_RE.fullmatch(value):
        raise ValueError(f"{name} must be a dotted Python identifier path")
    return value


def _resolve_importable(module: str, qualname: str) -> Any:
    target: Any = importlib.import_module(module)
    for segment in qualname.split("."):
        target = getattr(target, segment)
    return target


@dataclass(frozen=True, order=True)
class ImportRef:
    """Durable ``module:qualname`` reference to an importable symbol."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "module", _require_python_dotted("import module", self.module))
        object.__setattr__(self, "qualname", _require_python_dotted("import qualname", self.qualname))
        if self.module == "__main__":
            raise ValueError("import module must be a stable importable module, not '__main__'")

    @property
    def key(self) -> str:
        return f"import:{self.module}:{self.qualname}"

    @property
    def spec(self) -> str:
        return f"{self.module}:{self.qualname}"

    def resolve(self) -> Any:
        """Resolve the referenced symbol without invoking it."""

        return _resolve_importable(self.module, self.qualname)

    def validate_importable(self) -> "ImportRef":
        self.resolve()
        return self

    def validate_callable(
        self,
        *,
        node_id: str | None = None,
        field: str | None = None,
    ) -> "ImportRef":
        resolved = self.resolve()
        if inspect.ismethod(resolved):
            raise _unstable_ref_error("bound methods are not stable workflow refs", node_id=node_id, field=field)
        if not inspect.isfunction(resolved):
            if callable(resolved):
                raise _unstable_ref_error(
                    "callable instances are not stable workflow refs",
                    node_id=node_id,
                    field=field,
                )
            raise _unstable_ref_error("live objects are not stable workflow refs", node_id=node_id, field=field)
        if resolved.__name__ == "<lambda>":
            raise _unstable_ref_error("lambdas are not stable workflow refs", node_id=node_id, field=field)
        if resolved.__closure__:
            raise _unstable_ref_error("closures are not stable workflow refs", node_id=node_id, field=field)
        if "<locals>" in resolved.__qualname__:
            raise _unstable_ref_error(
                "ambiguous local functions are not stable workflow refs",
                node_id=node_id,
                field=field,
            )
        return self

    @classmethod
    def parse(cls, value: str) -> "ImportRef":
        module, separator, qualname = value.partition(":")
        if not separator:
            raise ValueError("import ref must use 'module:qualname' format")
        return cls(module=module, qualname=qualname)

    @classmethod
    def from_callable(
        cls,
        target: Any,
        *,
        node_id: str | None = None,
        field: str | None = None,
    ) -> "ImportRef":
        """Build a stable import ref from an accepted function object.

        Accepted objects are module-level functions and functions exposed through
        a class, including static methods. Bound methods, callable instances,
        lambdas, closures, local functions, and arbitrary live objects are
        rejected so manifests never depend on process-local object identity.
        """

        if isinstance(target, cls):
            return target.validate_importable()
        if isinstance(target, str):
            try:
                return cls.parse(target).validate_callable(node_id=node_id, field=field)
            except Exception as exc:  # noqa: BLE001 - convert to node/field diagnostic.
                raise _unstable_ref_error(
                    f"invalid import ref {target!r}: {exc}",
                    node_id=node_id,
                    field=field,
                ) from exc
        if inspect.ismethod(target):
            raise _unstable_ref_error("bound methods are not stable workflow refs", node_id=node_id, field=field)
        if not inspect.isfunction(target):
            if callable(target):
                raise _unstable_ref_error(
                    "callable instances are not stable workflow refs",
                    node_id=node_id,
                    field=field,
                )
            raise _unstable_ref_error("live objects are not stable workflow refs", node_id=node_id, field=field)
        if target.__name__ == "<lambda>":
            raise _unstable_ref_error("lambdas are not stable workflow refs", node_id=node_id, field=field)
        if target.__closure__:
            raise _unstable_ref_error("closures are not stable workflow refs", node_id=node_id, field=field)
        if "<locals>" in target.__qualname__:
            raise _unstable_ref_error(
                "ambiguous local functions are not stable workflow refs",
                node_id=node_id,
                field=field,
            )
        module = target.__module__
        if module == "__main__":
            raise _unstable_ref_error(
                "functions from '__main__' are not stable workflow refs",
                node_id=node_id,
                field=field,
            )
        ref = cls(module=module, qualname=target.__qualname__)
        try:
            resolved = ref.resolve()
        except Exception as exc:  # noqa: BLE001 - import systems raise diverse errors.
            raise _unstable_ref_error(
                f"callable is not importable as {ref.spec!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
        if resolved is not target:
            raise _unstable_ref_error(
                f"callable identity does not match imported {ref.spec!r}",
                node_id=node_id,
                field=field,
            )
        return ref

    def __str__(self) -> str:
        return self.spec


@dataclass(frozen=True, order=True)
class HookRef:
    """Durable reference to a workflow hook/predicate/reducer function."""

    import_ref: ImportRef

    def __post_init__(self) -> None:
        self.import_ref.validate_callable()

    @property
    def key(self) -> str:
        return f"hook:{self.import_ref.spec}"

    @property
    def spec(self) -> str:
        return self.import_ref.spec

    def resolve(self) -> Any:
        """Resolve the hook function without invoking it."""

        return self.import_ref.resolve()

    @classmethod
    def parse(cls, value: str) -> "HookRef":
        return cls(ImportRef.parse(value).validate_callable())

    @classmethod
    def from_callable(
        cls,
        target: Any,
        *,
        node_id: str | None = None,
        field: str | None = None,
    ) -> "HookRef":
        return cls(ImportRef.from_callable(target, node_id=node_id, field=field))

    def __bool__(self) -> bool:
        raise TypeError("HookRef is an inert reference and has no runtime truthiness")

    def __str__(self) -> str:
        return self.spec


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
