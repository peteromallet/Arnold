"""Neutral retained schema registry for ContractResult payload schemas."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION_PREFIX = "sha256:"
_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
_PLAN_DIR_MARKER = (".megaplan", "plans")
MEGAPLAN_CONTRACT_SCHEMA_ROOT = "MEGAPLAN_CONTRACT_SCHEMA_ROOT"


class SchemaRegistryError(ValueError):
    """Raised when schema registry state is invalid or inconsistent."""


@dataclass(frozen=True)
class AcceptedVersionRange:
    """Inclusive logical-type history bounds for a consumer."""

    logical_type: str
    min_version: str | None = None
    max_version: str | None = None


def canonical_schema_json(schema: Mapping[str, Any]) -> str:
    """Return deterministic JSON for hashing and persisted schema blobs."""

    return json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_schema_bytes(schema: Mapping[str, Any]) -> bytes:
    """Return UTF-8 canonical JSON bytes for *schema*."""

    return canonical_schema_json(schema).encode("utf-8")


def schema_version_for(schema: Mapping[str, Any]) -> str:
    """Return the public schema version for canonical schema bytes."""

    return f"{SCHEMA_VERSION_PREFIX}{hashlib.sha256(canonical_schema_bytes(schema)).hexdigest()}"


def normalize_schema_version(schema_version: str) -> str:
    """Normalize ``sha256:<hex>`` or bare 64-hex schema versions."""

    match = _SHA256_RE.fullmatch(schema_version)
    if not match:
        raise SchemaRegistryError(f"invalid schema version {schema_version!r}")
    return f"{SCHEMA_VERSION_PREFIX}{match.group(1).lower()}"


def resolve_contract_schema_project_root(
    explicit_root: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Resolve the project root for contract schemas.

    Precedence:
    1. explicit context root supplied by the caller
    2. ``MEGAPLAN_CONTRACT_SCHEMA_ROOT`` environment override
    3. project root derived from a ``.megaplan/plans/<plan>`` path
    """

    if explicit_root is not None:
        resolved = Path(explicit_root).expanduser().resolve()
        return derive_project_root_from_plan_dir(resolved) or resolved

    env_root = os.getenv(MEGAPLAN_CONTRACT_SCHEMA_ROOT)
    if env_root:
        return Path(env_root).expanduser().resolve()

    return None


def derive_project_root_from_plan_dir(path: str | os.PathLike[str]) -> Path | None:
    """Return the project root when *path* sits under ``.megaplan/plans/<plan>``."""

    resolved = Path(path).expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        parent = candidate.parent
        grandparent = parent.parent
        if parent.name == _PLAN_DIR_MARKER[1] and grandparent.name == _PLAN_DIR_MARKER[0]:
            return grandparent.parent
    return None


def create_contract_schema_registry(
    explicit_root: str | os.PathLike[str] | None = None,
) -> ContractSchemaRegistry | None:
    """Create a registry from the resolved project root, if one is available."""

    project_root = resolve_contract_schema_project_root(explicit_root)
    if project_root is None:
        return None
    return ContractSchemaRegistry(project_root)


class ContractSchemaRegistry:
    """File-backed, content-addressed registry rooted at ``.contract_schemas``."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        root_path = Path(root)
        self.root = root_path / ".contract_schemas"
        self.sha256_dir = self.root / "sha256"
        self.index_path = self.root / "index.json"

    def register(self, logical_type: str, schema: Mapping[str, Any]) -> str:
        """Retain *schema* and append its version to *logical_type* history."""

        if not logical_type:
            raise SchemaRegistryError("logical_type must be non-empty")
        version = schema_version_for(schema)
        digest = normalize_schema_version(version).removeprefix(SCHEMA_VERSION_PREFIX)
        blob_path = self.sha256_dir / f"{digest}.json"
        blob_bytes = canonical_schema_bytes(schema)

        self._write_blob_if_absent(blob_path, blob_bytes)
        index = self._read_index()
        history = list(index.get(logical_type, ()))
        if version not in history:
            history.append(version)
            index[logical_type] = history
            self._write_json_atomic(self.index_path, index)
        return version

    def get_schema(self, schema_version: str) -> dict[str, Any]:
        """Return a retained schema by hash, reading from disk each time."""

        version = normalize_schema_version(schema_version)
        digest = version.removeprefix(SCHEMA_VERSION_PREFIX)
        blob_path = self.sha256_dir / f"{digest}.json"
        try:
            with blob_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as exc:
            raise SchemaRegistryError(f"schema blob not found for {version}") from exc
        if not isinstance(data, dict):
            raise SchemaRegistryError(f"schema blob for {version} is not an object")
        if schema_version_for(data) != version:
            raise SchemaRegistryError(f"schema blob hash mismatch for {version}")
        return data

    def latest(self, logical_type: str) -> str | None:
        """Return the latest registered version for *logical_type*."""

        history = self.history(logical_type)
        return history[-1] if history else None

    def history(self, logical_type: str) -> tuple[str, ...]:
        """Return retained version history for *logical_type* from current index."""

        values = self._read_index().get(logical_type, ())
        return tuple(normalize_schema_version(value) for value in values)

    def accepts_version(
        self,
        logical_type: str,
        schema_version: str,
        accepted_range: AcceptedVersionRange,
    ) -> bool:
        """Return whether *schema_version* is accepted for *logical_type* history."""

        return accepts_version(logical_type, schema_version, accepted_range, registry=self)

    def _write_blob_if_absent(self, blob_path: Path, blob_bytes: bytes) -> None:
        if blob_path.exists():
            existing = blob_path.read_bytes()
            if existing != blob_bytes:
                raise SchemaRegistryError(f"pre-existing schema blob mismatch: {blob_path}")
            return
        self._write_bytes_atomic(blob_path, blob_bytes)

    def _read_index(self) -> dict[str, list[str]]:
        try:
            with self.index_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            raise SchemaRegistryError("schema registry index must be an object")
        index: dict[str, list[str]] = {}
        for logical_type, versions in raw.items():
            if not isinstance(logical_type, str) or not isinstance(versions, list):
                raise SchemaRegistryError("schema registry index has invalid history shape")
            index[logical_type] = [normalize_schema_version(v) for v in versions if isinstance(v, str)]
        return index

    def _write_json_atomic(self, path: Path, value: Mapping[str, Any]) -> None:
        data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        self._write_bytes_atomic(path, data)

    def _write_bytes_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


def accepts_version(
    logical_type: str,
    schema_version: str,
    accepted_range: AcceptedVersionRange,
    *,
    registry: ContractSchemaRegistry,
) -> bool:
    """Return whether *schema_version* falls within *accepted_range* for *logical_type*.

    Resolution is hash-first, but acceptance is still constrained to the requested
    logical type's own history and inclusive registration-order bounds.
    """

    if not logical_type:
        raise SchemaRegistryError("logical_type must be non-empty")
    if accepted_range.logical_type != logical_type:
        raise SchemaRegistryError("accepted_range logical_type must match logical_type")

    resolved_version = normalize_schema_version(schema_version)
    registry.get_schema(resolved_version)

    history = registry.history(logical_type)
    if resolved_version not in history:
        return False

    min_version = (
        normalize_schema_version(accepted_range.min_version)
        if accepted_range.min_version is not None
        else None
    )
    max_version = (
        normalize_schema_version(accepted_range.max_version)
        if accepted_range.max_version is not None
        else None
    )

    if min_version is not None and min_version not in history:
        raise SchemaRegistryError(
            f"min_version {min_version} is not registered for logical_type {logical_type!r}"
        )
    if max_version is not None and max_version not in history:
        raise SchemaRegistryError(
            f"max_version {max_version} is not registered for logical_type {logical_type!r}"
        )

    resolved_index = history.index(resolved_version)
    min_index = history.index(min_version) if min_version is not None else 0
    max_index = history.index(max_version) if max_version is not None else len(history) - 1
    if min_index > max_index:
        raise SchemaRegistryError("accepted_range min_version must not exceed max_version")
    return min_index <= resolved_index <= max_index
