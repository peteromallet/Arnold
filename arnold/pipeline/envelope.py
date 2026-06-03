"""RunEnvelope — per-step cross-cutting metadata carried through the pipeline."""

from __future__ import annotations

import json
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


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

    def to_json(self) -> dict[str, Any]:
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

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "RunEnvelope":
        return cls(
            taint=data["taint"],
            cost=data["cost"],
            lineage=tuple(data["lineage"]),
            deadline=data.get("deadline"),
            cancellation=data["cancellation"],
            retry_budget=data["retry_budget"],
            error_class=data.get("error_class"),
            lease_id=data.get("lease_id"),
            fencing_token=data.get("fencing_token"),
            capacity_grant=data.get("capacity_grant", 0),
        )


class EnvelopeDroppedError(RuntimeError):
    """Raised when an envelope is None under ``conveyance_strict_on()``.

    Only active when ``CONVEYANCE_STRICT=1`` (or inherited from
    ``ARNOLD_UNIFIED_DISPATCH``).  Silent when the flag is off.
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

# Public API for arnold.pipeline internal use.
#: Current envelope visible to in-process consumers (e.g. KeyPool) so they can
#: read taint/budget/lineage without threading it through every signature.
_envelope_ctx: ContextVar[Optional[RunEnvelope]] = ContextVar(
    "_envelope_ctx", default=None
)

# Public API for arnold.pipeline internal use.
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
ENVELOPE_ENV_VAR = "ARNOLD_ENVELOPE_IN"  # primary; "MEGAPLAN_ENVELOPE_IN" accepted as fallback
ENVELOPE_STDERR_TAG = "[arnold-envelope]"


def write_envelope_in(plan_dir: Path, envelope: "RunEnvelope") -> dict[str, str]:
    """Write the inbound sidecar for a subprocess and return the env override.

    Returns the dict that should be merged into the child's environment.  The
    parent is responsible for actually merging it; the child consumes via
    :func:`consume_envelope_in`.
    """

    plan_dir = Path(plan_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)
    path = plan_dir / ENVELOPE_IN_FILENAME
    path.write_text(json.dumps(envelope.to_json()), encoding="utf-8")
    return {ENVELOPE_ENV_VAR: str(path)}


def consume_envelope_in() -> Optional["RunEnvelope"]:
    """Child-side: load the inbound envelope and pop the env var.

    Popping is mandatory — grandchildren must NOT inherit the parent's
    envelope by env-leak.  Each subprocess spawn writes a fresh sidecar.
    """

    # Try ARNOLD_ENVELOPE_IN first, fall back to MEGAPLAN_ENVELOPE_IN for
    # backward compatibility during the transition window.
    raw_path = os.environ.pop("ARNOLD_ENVELOPE_IN", None)
    if raw_path is None:
        raw_path = os.environ.pop("MEGAPLAN_ENVELOPE_IN", None)
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


def write_envelope_out(plan_dir: Path, envelope: "RunEnvelope") -> Path:
    """Write outbound sidecar.  Returns the path written."""

    plan_dir = Path(plan_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)
    path = plan_dir / ENVELOPE_OUT_FILENAME
    path.write_text(json.dumps(envelope.to_json()), encoding="utf-8")
    return path


def read_envelope_out(plan_dir: Path) -> Optional["RunEnvelope"]:
    """Parent-side: read the child's outbound sidecar if present."""

    path = Path(plan_dir) / ENVELOPE_OUT_FILENAME
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

__all__ = [
    "RunEnvelope",
    "EMPTY_ENVELOPE",
    "ENVELOPE_ENV_VAR",
    "ENVELOPE_IN_FILENAME",
    "ENVELOPE_OUT_FILENAME",
    "ENVELOPE_STDERR_TAG",
    "EnvelopeDroppedError",
    "LeaseIdConflict",
    "consume_envelope_in",
    "current_envelope",
    "format_envelope_stderr_tag",
    "make_envelope",
    "parse_envelope_stderr_tag",
    "read_envelope_out",
    "write_envelope_in",
    "write_envelope_out",
]

