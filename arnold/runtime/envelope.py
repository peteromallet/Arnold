"""Runtime-owned run envelope.

This module defines the canonical cross-cutting carrier and the
run-level identity carrier:

* :class:`RunEnvelope` — frozen cross-cutting metadata (taint, cost,
  lineage, deadline, cancellation, retry-budget, error-class, plus
  lease/fencing/capacity-grant) with a commutative/associative/idempotent
  ``join()`` semilattice, JSON round-trip, and subprocess sidecar
  handshake.
* :class:`RuntimeEnvelope` — the runtime-owned run envelope.  Holds
  plugin identity, manifest hash, schema versions, run id, artifact
  root, resume cursor, trust/quarantine state, creation time, and a
  composed :class:`RunEnvelope`.

``RunEnvelope`` is the canonical cross-cutting type; ``RuntimeEnvelope``
is the run-level identity carrier.  Both are ``frozen=True`` dataclasses
and round-trip through their respective ``to_json`` / ``from_json``
methods with structural equality.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
``schema_version`` is exposed as an integer ``ClassVar`` constant so
consumers can pin against an exact integer without instantiating.
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping, Optional, Protocol, runtime_checkable

from arnold.runtime.resume import (
    TRUST_UNKNOWN,
    ResumeCursorRef,
)

__all__ = [
    # Canonical cross-cutting carrier
    "RunEnvelope",
    "EMPTY_ENVELOPE",
    "make_envelope",
    "EnvelopeDroppedError",
    "LeaseIdConflict",
    "RunContext",
    # In-process plumbing
    "current_envelope",
    "_envelope_ctx",
    "_fanout_active_ctx",
    # Subprocess sidecar
    "ENVELOPE_ENV_VAR",
    "ENVELOPE_STDERR_TAG",
    "ENVELOPE_IN_FILENAME",
    "ENVELOPE_OUT_FILENAME",
    "write_envelope_in",
    "consume_envelope_in",
    "write_envelope_out",
    "read_envelope_out",
    "format_envelope_stderr_tag",
    "parse_envelope_stderr_tag",
    # Run-level identity carrier (existing)
    "RuntimeEnvelope",
    "RUNTIME_ENVELOPE_SCHEMA_VERSION",
]


# ============================================================================
# Canonical RunEnvelope — cross-cutting carrier lifted from megaplan
# ============================================================================


@dataclass(frozen=True)
class RunEnvelope:
    """Frozen cross-cutting metadata attached to every StepContext/StepResult.

    Fields
    ------
    taint : str
        Propagation marker (e.g. ``"clean"`` or ``"tainted"``).
    cost : float
        Accumulated cost in USD so far.
    lineage : tuple[str, ...]
        Ordered step IDs that produced this envelope.
    deadline : float | None
        POSIX timestamp after which execution should abort, or ``None``.
    cancellation : bool
        ``True`` when a cancellation signal has been received.
    retry_budget : int
        Remaining retry attempts.
    error_class : str | None
        Symbolic error class if an error has been recorded.
    lease_id : str | None
        Identifier of the capacity lease this envelope represents, if any.
        Two non-None unequal lease_ids cannot join — joining raises
        :class:`LeaseIdConflict`.
    fencing_token : int | None
        Monotonic fencing token for stale-lease detection.  Join takes the max
        (treating ``None`` as ``-1`` so any concrete token dominates).
    capacity_grant : int
        Additive capacity-grant amount in abstract units.  Join sums; the
        budget authority is responsible for downstream
        (lease_id, fencing_token) de-duplication.
    """

    taint: str = "clean"
    cost: float = 0.0
    lineage: tuple[str, ...] = ()
    deadline: float | None = None
    cancellation: bool = False
    retry_budget: int = 3
    error_class: str | None = None
    lease_id: str | None = None
    fencing_token: int | None = None
    capacity_grant: int = 0

    # ------------------------------------------------------------------
    # Semilattice join
    # ------------------------------------------------------------------

    def join(self, other: "RunEnvelope") -> "RunEnvelope":
        """Return the least-upper-bound of ``self`` and ``other``.

        Commutative, associative, and idempotent:

        * ``taint`` — ``"tainted"`` dominates ``"clean"`` (any non-clean value
          dominates a clean one; between two non-clean values the first is kept).
        * ``cost`` — summed.
        * ``lineage`` — concatenation (self first, deduplicating exact-prefix repeats).
        * ``deadline`` — minimum non-None value (tightest deadline).
        * ``cancellation`` — boolean OR.
        * ``retry_budget`` — minimum (most constrained).
        * ``error_class`` — first non-None wins; if both non-None and equal keeps it,
          otherwise ``"multiple"`` signals conflict.

        Note: ``cost`` is summed rather than max'd so the envelope tracks total
        spend across a fan-out reduction.  Commutativity holds because addition
        is commutative; the test suite verifies this directly.
        """
        if self == other:
            return self

        # taint: "tainted" dominates
        if self.taint == "clean":
            taint = other.taint
        elif other.taint == "clean":
            taint = self.taint
        else:
            taint = self.taint  # both non-clean: keep self (deterministic)

        cost = self.cost + other.cost

        # lineage: concatenate, avoid pure duplication when joining with EMPTY
        combined = self.lineage + tuple(x for x in other.lineage if x not in self.lineage)

        # deadline: tightest non-None
        if self.deadline is None:
            deadline = other.deadline
        elif other.deadline is None:
            deadline = self.deadline
        else:
            deadline = min(self.deadline, other.deadline)

        cancellation = self.cancellation or other.cancellation

        retry_budget = min(self.retry_budget, other.retry_budget)

        if self.error_class is None:
            error_class = other.error_class
        elif other.error_class is None:
            error_class = self.error_class
        elif self.error_class == other.error_class:
            error_class = self.error_class
        else:
            error_class = "multiple"

        # lease_id: equal or one-side None merges; unequal non-None conflicts.
        if self.lease_id is None:
            lease_id = other.lease_id
        elif other.lease_id is None:
            lease_id = self.lease_id
        elif self.lease_id == other.lease_id:
            lease_id = self.lease_id
        else:
            raise LeaseIdConflict(
                f"Cannot join envelopes with unequal lease_ids: "
                f"{self.lease_id!r} vs {other.lease_id!r}"
            )

        # fencing_token: max, treating None as -1.
        a = -1 if self.fencing_token is None else self.fencing_token
        b = -1 if other.fencing_token is None else other.fencing_token
        merged_ft = max(a, b)
        fencing_token = None if merged_ft == -1 else merged_ft

        # capacity_grant: additive (downstream de-dups by (lease_id, fencing_token)).
        capacity_grant = self.capacity_grant + other.capacity_grant

        return RunEnvelope(
            taint=taint,
            cost=cost,
            lineage=combined,
            deadline=deadline,
            cancellation=cancellation,
            retry_budget=retry_budget,
            error_class=error_class,
            lease_id=lease_id,
            fencing_token=fencing_token,
            capacity_grant=capacity_grant,
        )

    # ------------------------------------------------------------------
    # JSON round-trip
    # ------------------------------------------------------------------

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "taint": self.taint,
            "cost": self.cost,
            "lineage": list(self.lineage),
            "deadline": self.deadline,
            "cancellation": self.cancellation,
            "retry_budget": self.retry_budget,
            "error_class": self.error_class,
            "lease_id": self.lease_id,
            "fencing_token": self.fencing_token,
            "capacity_grant": self.capacity_grant,
        }

    # Backward-compat alias — existing callers use .to_json() expecting a dict.
    def to_json(self) -> dict[str, Any]:
        """Alias for :meth:`to_jsonable` (returns a dict, not a JSON string)."""
        return self.to_jsonable()

    @classmethod
    def from_jsonable(cls, data: dict[str, Any]) -> "RunEnvelope":
        """Construct a RunEnvelope from a dict previously produced by
        :meth:`to_jsonable`."""
        return cls(
            taint=data.get("taint", "clean"),
            cost=data.get("cost", 0.0),
            lineage=tuple(data.get("lineage", ())),
            deadline=data.get("deadline"),
            cancellation=data.get("cancellation", False),
            retry_budget=data.get("retry_budget", 3),
            error_class=data.get("error_class"),
            lease_id=data.get("lease_id"),
            fencing_token=data.get("fencing_token"),
            capacity_grant=data.get("capacity_grant", 0),
        )

    # Backward-compat alias — existing callers use .from_json().
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "RunEnvelope":
        """Alias for :meth:`from_jsonable`."""
        return cls.from_jsonable(data)


class EnvelopeDroppedError(RuntimeError):
    """Raised when an envelope is None under ``conveyance_strict_on()``.

    Only active when ``CONVEYANCE_STRICT=1`` (or inherited from
    the unified dispatch mode).  Silent when the flag is off.
    """


class LeaseIdConflict(RuntimeError):
    """Raised when joining two envelopes that carry unequal non-None lease_ids.

    Lease identifiers are exclusive — a single envelope cannot simultaneously
    represent two distinct capacity leases.  Conflicts surface at join time so
    that the budget authority sees them as hard errors rather than silent
    overwrites.
    """


# Canonical empty envelope — zero cost, no taint, no lineage.
EMPTY_ENVELOPE = RunEnvelope()


def make_envelope(
    *,
    taint: str = "clean",
    cost: float = 0.0,
    lineage: tuple[str, ...] | list[str] = (),
    deadline: float | None = None,
    cancellation: bool = False,
    retry_budget: int = 3,
    error_class: str | None = None,
    lease_id: str | None = None,
    fencing_token: int | None = None,
    capacity_grant: int = 0,
) -> RunEnvelope:
    """Convenience constructor with keyword-only args and list→tuple coercion."""
    return RunEnvelope(
        taint=taint,
        cost=cost,
        lineage=tuple(lineage),
        deadline=deadline,
        cancellation=cancellation,
        retry_budget=retry_budget,
        error_class=error_class,
        lease_id=lease_id,
        fencing_token=fencing_token,
        capacity_grant=capacity_grant,
    )


# ---------------------------------------------------------------------------
# In-process plumbing: ContextVars
# ---------------------------------------------------------------------------

#: Current envelope visible to in-process consumers (e.g. KeyPool) so they can
#: read taint/budget/lineage without threading it through every signature.
_envelope_ctx: ContextVar[Optional[RunEnvelope]] = ContextVar(
    "_envelope_ctx", default=None
)

#: True while we are inside a fan-out reduction.  Pattern code (dynamic_fanout,
#: panel_from_artifact) sets this so downstream observers can tell a per-spec
#: branch from the main line.
_fanout_active_ctx: ContextVar[bool] = ContextVar(
    "_fanout_active_ctx", default=False
)


def current_envelope() -> Optional["RunEnvelope"]:
    """Return the envelope currently visible to this task, or ``None``."""
    return _envelope_ctx.get()


# ---------------------------------------------------------------------------
# Subprocess handshake — symmetric, per-spawn, no env leakage
# ---------------------------------------------------------------------------

ENVELOPE_IN_FILENAME = ".envelope-in.json"
ENVELOPE_OUT_FILENAME = ".envelope-out.json"
ENVELOPE_ENV_VAR = "ARNOLD_ENVELOPE_IN"
ENVELOPE_STDERR_TAG = "[arnold-envelope]"


def write_envelope_in(state_dir: Path, envelope: "RunEnvelope") -> dict[str, str]:
    """Write the inbound sidecar for a subprocess and return the env override.

    Returns the dict that should be merged into the child's environment.  The
    parent is responsible for actually merging it; the child consumes via
    :func:`consume_envelope_in`.
    """
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / ENVELOPE_IN_FILENAME
    path.write_text(json.dumps(envelope.to_json()), encoding="utf-8")
    return {ENVELOPE_ENV_VAR: str(path)}


def consume_envelope_in() -> Optional["RunEnvelope"]:
    """Child-side: load the inbound envelope and pop the env var.

    Popping is mandatory — grandchildren must NOT inherit the parent's
    envelope by env-leak.  Each subprocess spawn writes a fresh sidecar.
    """
    raw_path = os.environ.pop(ENVELOPE_ENV_VAR, None)
    if not raw_path:
        return None
    try:
        data = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RunEnvelope.from_json(data)
    except (KeyError, TypeError):
        return None


def write_envelope_out(state_dir: Path, envelope: "RunEnvelope") -> Path:
    """Write outbound sidecar.  Returns the path written."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / ENVELOPE_OUT_FILENAME
    path.write_text(json.dumps(envelope.to_json()), encoding="utf-8")
    return path


def read_envelope_out(state_dir: Path) -> Optional["RunEnvelope"]:
    """Parent-side: read the child's outbound sidecar if present."""
    path = Path(state_dir) / ENVELOPE_OUT_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunEnvelope.from_json(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def format_envelope_stderr_tag(envelope: "RunEnvelope") -> str:
    """Tagged-stderr fallback line for when sidecar IO is unavailable."""
    return f"{ENVELOPE_STDERR_TAG}{json.dumps(envelope.to_json())}"


def parse_envelope_stderr_tag(stderr: str) -> Optional["RunEnvelope"]:
    """Parse a tagged-stderr envelope line if present in ``stderr``."""
    for line in stderr.splitlines():
        if line.startswith(ENVELOPE_STDERR_TAG):
            try:
                data = json.loads(line[len(ENVELOPE_STDERR_TAG):])
                return RunEnvelope.from_json(data)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return None


# ============================================================================
# RunContext Protocol — read-only cross-cutting surface
# ============================================================================


@runtime_checkable
class RunContext(Protocol):
    """Read-only cross-cutting state visible to generic pipeline steps.

    ``RunEnvelope`` satisfies this structurally — steps can read cost,
    taint, lineage, deadline, cancellation, and retry_budget through the
    protocol without seeing the full ``join()`` semilattice.
    """

    taint: str
    cost: float
    lineage: tuple[str, ...]
    deadline: float | None
    cancellation: bool
    retry_budget: int


# ============================================================================
# Run-level identity carrier (existing — M2a / M3d)
# ============================================================================


# Module-level mirror of the schema-version constant.  Kept in lockstep
# with :attr:`RuntimeEnvelope.schema_version` so importers can pin the
# version without instantiating the envelope.
RUNTIME_ENVELOPE_SCHEMA_VERSION: int = 2


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

    The composed ``cross_cutting`` field now holds a full
    :class:`RunEnvelope` (including lease/fencing/capacity-grant
    fields).  The M3 hinge semantics are carried through the
    RunEnvelope semilattice rather than being absent from the
    runtime carrier.
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
    cross_cutting: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)

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
            cross_cutting = RunEnvelope.from_jsonable(cross_blob)
        else:
            cross_cutting = EMPTY_ENVELOPE
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
