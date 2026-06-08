"""Runtime-owned run envelope.

This module defines two frozen carriers and one schema-version constant:

* :class:`CrossCuttingEnvelope` — structural mirror of the existing
  neutral run envelope cross-cutting fields (taint, cost, lineage,
  deadline, cancellation, retry-budget, error-class).  Carrying these as
  a sub-record on :class:`RuntimeEnvelope` keeps M2a focused on shape
  parity; M3 owns lease/fencing/capacity-grant semantics and they are
  intentionally absent here.
* :class:`RuntimeEnvelope` — the runtime-owned run envelope.  Holds
  plugin identity, manifest hash, schema versions, run id, artifact
  root, resume cursor, trust/quarantine state, creation time, and a
  composed :class:`CrossCuttingEnvelope`.

Both types are ``frozen=True`` dataclasses and round-trip through
:meth:`RuntimeEnvelope.to_json` /
:meth:`RuntimeEnvelope.from_json` with structural equality.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
``schema_version`` is exposed as an integer ``ClassVar`` constant so
consumers can pin against an exact integer without instantiating.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, Mapping

from arnold.runtime.resume import (
    TRUST_UNKNOWN,
    ResumeCursorRef,
)

__all__ = [
    "CrossCuttingEnvelope",
    "RuntimeEnvelope",
    "RUNTIME_ENVELOPE_SCHEMA_VERSION",
]


# Module-level mirror of the schema-version constant.  Kept in lockstep
# with :attr:`RuntimeEnvelope.schema_version` so importers can pin the
# version without instantiating the envelope.
RUNTIME_ENVELOPE_SCHEMA_VERSION: int = 1


@dataclass(frozen=True)
class CrossCuttingEnvelope:
    """Cross-cutting run-envelope sub-record.

    Structurally mirrors the neutral run-envelope cross-cutting fields
    that already live in the existing pipeline envelope: taint, cost,
    lineage, deadline, cancellation, retry-budget, error-class.

    Lease/fencing/capacity-grant fields are intentionally NOT present:
    those are M3 hinge concerns and remain owned by their existing
    home until M3 lands their real semantics.  Per the M2a brief, the
    runtime envelope must not pre-empt the M3 grant schema.
    """

    taint: tuple[str, ...] = ()
    cost: Mapping[str, Any] = field(default_factory=dict)
    lineage: tuple[str, ...] = ()
    deadline: str | None = None
    cancellation: str | None = None
    retry_budget: Mapping[str, Any] = field(default_factory=dict)
    error_class: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "taint": list(self.taint),
            "cost": dict(self.cost),
            "lineage": list(self.lineage),
            "deadline": self.deadline,
            "cancellation": self.cancellation,
            "retry_budget": dict(self.retry_budget),
            "error_class": self.error_class,
        }

    @classmethod
    def from_jsonable(cls, blob: Mapping[str, Any]) -> "CrossCuttingEnvelope":
        if not isinstance(blob, Mapping):
            raise TypeError(
                "CrossCuttingEnvelope.from_jsonable expected a mapping, "
                f"got {type(blob).__name__}"
            )
        return cls(
            taint=tuple(blob.get("taint", ()) or ()),
            cost=dict(blob.get("cost", {}) or {}),
            lineage=tuple(blob.get("lineage", ()) or ()),
            deadline=blob.get("deadline"),
            cancellation=blob.get("cancellation"),
            retry_budget=dict(blob.get("retry_budget", {}) or {}),
            error_class=blob.get("error_class"),
        )


@dataclass(frozen=True)
class RuntimeEnvelope:
    """Runtime-owned run envelope.

    ``schema_version`` is exposed both as an instance field (so the
    persisted envelope carries the version) and as a class-level
    constant (``RuntimeEnvelope.schema_version``) so consumers can pin
    the integer without instantiating.

    ``trust_state`` defaults to ``"unknown"``; the resume migration
    contract transitions it to a trust label (``"trusted"``,
    ``"quarantined-manifest-mismatch"``, …).

    Lease/fencing/capacity-grant fields are intentionally absent —
    those are M3 hinge concerns.
    """

    # Class-level schema version constant — pinnable without instantiation.
    schema_version: ClassVar[int] = RUNTIME_ENVELOPE_SCHEMA_VERSION

    plugin_id: str = ""
    manifest_hash: str = ""
    plugin_state_schema_version: int = 0
    run_id: str = ""
    artifact_root: str = ""
    resume_cursor: ResumeCursorRef | None = None
    trust_state: str = TRUST_UNKNOWN
    created_at: str = ""
    cross_cutting: CrossCuttingEnvelope = field(default_factory=CrossCuttingEnvelope)

    # ----- JSON round-trip ------------------------------------------------

    def to_json(self) -> str:
        """Serialise to a JSON string.  Sorted keys for determinism."""
        return json.dumps(self._to_jsonable(), sort_keys=True)

    def _to_jsonable(self) -> dict[str, Any]:
        cursor_blob: dict[str, Any] | None
        if self.resume_cursor is None:
            cursor_blob = None
        else:
            cursor_blob = {
                "plugin_id": self.resume_cursor.plugin_id,
                "run_id": self.resume_cursor.run_id,
                "cursor": dict(self.resume_cursor.cursor),
            }
        return {
            "schema_version": int(self.schema_version),
            "plugin_id": self.plugin_id,
            "manifest_hash": self.manifest_hash,
            "plugin_state_schema_version": int(self.plugin_state_schema_version),
            "run_id": self.run_id,
            "artifact_root": self.artifact_root,
            "resume_cursor": cursor_blob,
            "trust_state": self.trust_state,
            "created_at": self.created_at,
            "cross_cutting": self.cross_cutting.to_jsonable(),
        }

    @classmethod
    def from_json(cls, raw: str) -> "RuntimeEnvelope":
        """Deserialise from a JSON string.  Round-trip equality is tested."""
        blob = json.loads(raw)
        if not isinstance(blob, Mapping):
            raise TypeError(
                f"RuntimeEnvelope.from_json expected an object, "
                f"got {type(blob).__name__}"
            )
        return cls._from_jsonable(blob)

    @classmethod
    def _from_jsonable(cls, blob: Mapping[str, Any]) -> "RuntimeEnvelope":
        # Pin the persisted schema_version against the class constant; a
        # mismatch indicates a migration step the caller must run first.
        persisted_version = blob.get("schema_version")
        if persisted_version is not None and int(persisted_version) != cls.schema_version:
            raise ValueError(
                f"RuntimeEnvelope schema_version mismatch: "
                f"persisted={persisted_version!r}, expected={cls.schema_version!r}"
            )
        cursor_blob = blob.get("resume_cursor")
        resume_cursor: ResumeCursorRef | None
        if isinstance(cursor_blob, Mapping):
            resume_cursor = ResumeCursorRef(
                plugin_id=str(cursor_blob.get("plugin_id", "")),
                run_id=str(cursor_blob.get("run_id", "")),
                cursor=dict(cursor_blob.get("cursor", {}) or {}),
            )
        else:
            resume_cursor = None
        cross_blob = blob.get("cross_cutting")
        if isinstance(cross_blob, Mapping):
            cross_cutting = CrossCuttingEnvelope.from_jsonable(cross_blob)
        else:
            cross_cutting = CrossCuttingEnvelope()
        return cls(
            plugin_id=str(blob.get("plugin_id", "")),
            manifest_hash=str(blob.get("manifest_hash", "")),
            plugin_state_schema_version=int(blob.get("plugin_state_schema_version", 0)),
            run_id=str(blob.get("run_id", "")),
            artifact_root=str(blob.get("artifact_root", "")),
            resume_cursor=resume_cursor,
            trust_state=str(blob.get("trust_state", TRUST_UNKNOWN)),
            created_at=str(blob.get("created_at", "")),
            cross_cutting=cross_cutting,
        )
