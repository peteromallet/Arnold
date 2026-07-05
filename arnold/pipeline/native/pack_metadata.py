"""Native pack metadata models — manifest, lockfile, and interface hashing.

These types describe the wire format for shared-library packs:
export entries (step and workflow), dependency declarations, pack
manifests, lockfile entries, and lockfiles.  They carry plain
``to_dict()`` / ``from_dict()`` serialization so callers can
round-trip through JSON-compatible dictionaries without an
intermediate schema layer.

**Design constraints (settled)**

* Dependency declarations live *solely* in :class:`PackManifest`;
  :class:`~arnold.pipeline.native.ir.NativeProgram` does **not** carry
  separate dependency metadata.
* Stable IDs and declared input/output schemas from the native
  decorator surface are canonical — this module does not introduce a
  second identity or schema mechanism.
* Interface hashes are deterministic over ``(stable_id, canonical
  inputs_schema, canonical outputs_schema)`` using SHA-256.
* ``body_hash`` is optional opt-in; when ``None``, body-only changes
  are non-breaking.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


# ── Helpers ────────────────────────────────────────────────────────────


def _canonical_json(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact, no ASCII escapes)."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _normalize_schema(schema: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalised JSON-round-tripped copy of *schema*, or ``None``.

    This ensures that two semantically equivalent schema dicts (e.g. with
    different key ordering) produce the same canonical JSON string for hashing.
    """
    if schema is None:
        return None
    if not schema:
        return {}
    return json.loads(_canonical_json(schema))


# ── Interface hash ─────────────────────────────────────────────────────


def compute_interface_hash(
    *,
    stable_id: str,
    inputs_schema: Mapping[str, Any] | None = None,
    outputs_schema: Mapping[str, Any] | None = None,
) -> str:
    """Compute a deterministic interface hash from stable identity and canonical schemas.

    The hash is ``sha256:`` + hex digest of the SHA-256 of a canonical JSON
    payload containing the stable ID and the normalised input/output schemas.

    Parameters
    ----------
    stable_id:
        The stable semantic identity of the exported unit.  Must be non-empty.
    inputs_schema:
        The declared input schema metadata, or ``None``.
    outputs_schema:
        The declared output schema metadata, or ``None``.

    Returns
    -------
    str
        A ``sha256:<hex>`` string that is deterministic for the same
        ``(stable_id, inputs_schema, outputs_schema)`` triple.

    Raises
    ------
    ValueError
        If *stable_id* is empty.
    """
    if not stable_id:
        raise ValueError("stable_id must be non-empty for interface hash computation")

    payload = {
        "stable_id": stable_id,
        "inputs_schema": _normalize_schema(inputs_schema),
        "outputs_schema": _normalize_schema(outputs_schema),
    }
    serialized = _canonical_json(payload)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ── Export entry ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportEntry:
    """A single exported unit from a pack — a step or a workflow.

    Carries the stable identity, declared interface schemas, and an
    optional body hash for opt-in body-change detection.
    """

    stable_id: str
    """Stable semantic identity declared on the decorator (e.g. ``__step_id__``
    or ``__workflow_id__``).  Required — every export must have a stable ID."""

    kind: str
    """Export kind: ``'step'`` for a ``@step``-decorated callable, ``'workflow'``
    for a ``@workflow``-decorated callable."""

    name: str
    """Human-readable name of the exported unit (the function name)."""

    description: str = ""
    """Optional human-readable description."""

    inputs_schema: Mapping[str, Any] | None = None
    """Declared input schema metadata (same shape as ``@step(inputs=...)``)."""

    outputs_schema: Mapping[str, Any] | None = None
    """Declared output schema metadata (same shape as ``@step(outputs=...)``)."""

    body_hash: str | None = None
    """Optional opaque hash of the implementation body.

    When ``None`` (the default), body-only changes are non-breaking and
    callers should not use this field in compatibility checks.  When set,
    it carries a hash produced by the pack author to opt into body-change
    detection (e.g. ``sha256:<hex>`` of the canonical source).
    """

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain JSON-compatible dictionary.

        Returns
        -------
        dict
            A dictionary with all fields, omitting ``None`` values for
            optional fields to keep the wire format compact.
        """
        result: dict[str, Any] = {
            "stable_id": self.stable_id,
            "kind": self.kind,
            "name": self.name,
        }
        if self.description:
            result["description"] = self.description
        if self.inputs_schema is not None:
            result["inputs_schema"] = _normalize_schema(self.inputs_schema)
        if self.outputs_schema is not None:
            result["outputs_schema"] = _normalize_schema(self.outputs_schema)
        if self.body_hash is not None:
            result["body_hash"] = self.body_hash
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExportEntry:
        """Deserialize from a plain dictionary.

        Parameters
        ----------
        data:
            A dictionary previously produced by :meth:`to_dict`.

        Returns
        -------
        ExportEntry
            A new instance with the deserialized fields.

        Raises
        ------
        KeyError
            If a required key (``stable_id``, ``kind``, ``name``) is missing.
        """
        return cls(
            stable_id=data["stable_id"],
            kind=data["kind"],
            name=data["name"],
            description=data.get("description", ""),
            inputs_schema=data.get("inputs_schema"),
            outputs_schema=data.get("outputs_schema"),
            body_hash=data.get("body_hash"),
        )


# ── Dependency spec ────────────────────────────────────────────────────


@dataclass(frozen=True)
class DependencySpec:
    """A dependency declaration in a :class:`PackManifest`.

    Declares that the pack depends on another pack identified by *stable_id*,
    with an optional version range specifier.
    """

    stable_id: str
    """Stable semantic identity of the dependency pack."""

    version: str = "*"
    """Version range specifier (e.g. ``'>=1.0,<2.0'``, ``'1.2.3'``, or ``'*'``
    for any version).  Defaults to ``'*'``."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        result: dict[str, Any] = {"stable_id": self.stable_id}
        if self.version != "*":
            result["version"] = self.version
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DependencySpec:
        """Deserialize from a plain dictionary.

        Raises
        ------
        KeyError
            If ``stable_id`` is missing.
        """
        return cls(
            stable_id=data["stable_id"],
            version=data.get("version", "*"),
        )


# ── Pack manifest ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class PackManifest:
    """A pack manifest describing exported units and declared dependencies.

    This is the top-level metadata document for a shared-library pack.
    It carries the pack identity, exported step/workflow entries, and
    dependency declarations.  Dependency resolution and lockfile
    generation consume the manifest but do **not** modify it.
    """

    name: str
    """Human-readable pack name."""

    version: str
    """Pack version (semver string, e.g. ``'1.0.0'``)."""

    description: str = ""
    """Optional human-readable description."""

    stable_id: str | None = None
    """Optional pack-level stable identity.  When ``None``, callers should
    use the pack ``name`` for identity purposes."""

    exports: tuple[ExportEntry, ...] = ()
    """Exported step and workflow entries in declaration order."""

    dependencies: tuple[DependencySpec, ...] = ()
    """Declared dependency specs in declaration order."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain JSON-compatible dictionary."""
        result: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
        }
        if self.description:
            result["description"] = self.description
        if self.stable_id is not None:
            result["stable_id"] = self.stable_id
        if self.exports:
            result["exports"] = [e.to_dict() for e in self.exports]
        if self.dependencies:
            result["dependencies"] = [d.to_dict() for d in self.dependencies]
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PackManifest:
        """Deserialize from a plain dictionary.

        Raises
        ------
        KeyError
            If ``name`` or ``version`` is missing.
        """
        return cls(
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            stable_id=data.get("stable_id"),
            exports=tuple(
                ExportEntry.from_dict(e) for e in data.get("exports", [])
            ),
            dependencies=tuple(
                DependencySpec.from_dict(d) for d in data.get("dependencies", [])
            ),
        )


# ── Lockfile entry ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class LockfileEntry:
    """A single resolved, pinned dependency entry in a :class:`PackLockfile`.

    Records the exact version and interface hash at pin time so that
    dependents do not auto-upgrade when the exported unit changes.
    """

    stable_id: str
    """Stable semantic identity of the pinned dependency."""

    version: str
    """Exact pinned version (semver string, e.g. ``'1.2.3'``)."""

    interface_hash: str
    """The deterministic interface hash captured at pin time
    (``sha256:<hex>`` from :func:`compute_interface_hash`)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "stable_id": self.stable_id,
            "version": self.version,
            "interface_hash": self.interface_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LockfileEntry:
        """Deserialize from a plain dictionary.

        Raises
        ------
        KeyError
            If ``stable_id``, ``version``, or ``interface_hash`` is missing.
        """
        return cls(
            stable_id=data["stable_id"],
            version=data["version"],
            interface_hash=data["interface_hash"],
        )


# ── Pack lockfile ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class PackLockfile:
    """A lockfile recording pinned dependency resolutions.

    Associates a manifest identity with a set of :class:`LockfileEntry`
    pins.  The runtime provenance module consumes this to validate that
    resolved dependencies match the pinned interface hashes before
    execution.
    """

    manifest_stable_id: str | None = None
    """Stable identity of the manifest this lockfile was generated from."""

    manifest_version: str | None = None
    """Version of the manifest at pin time."""

    entries: tuple[LockfileEntry, ...] = ()
    """Pinned dependency entries in stable-ID order."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain JSON-compatible dictionary."""
        result: dict[str, Any] = {}
        if self.manifest_stable_id is not None:
            result["manifest_stable_id"] = self.manifest_stable_id
        if self.manifest_version is not None:
            result["manifest_version"] = self.manifest_version
        if self.entries:
            result["entries"] = [e.to_dict() for e in self.entries]
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PackLockfile:
        """Deserialize from a plain dictionary."""
        return cls(
            manifest_stable_id=data.get("manifest_stable_id"),
            manifest_version=data.get("manifest_version"),
            entries=tuple(
                LockfileEntry.from_dict(e) for e in data.get("entries", [])
            ),
        )


__all__ = [
    "DependencySpec",
    "ExportEntry",
    "LockfileEntry",
    "PackLockfile",
    "PackManifest",
    "compute_interface_hash",
]
