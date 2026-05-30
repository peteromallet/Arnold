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
    """

    taint: str = "clean"
    cost: float = 0.0
    lineage: tuple[str, ...] = ()
    deadline: float | None = None
    cancellation: bool = False
    retry_budget: int = 3
    error_class: str | None = None

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

        return RunEnvelope(
            taint=taint,
            cost=cost,
            lineage=combined,
            deadline=deadline,
            cancellation=cancellation,
            retry_budget=retry_budget,
            error_class=error_class,
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
        )


class EnvelopeDroppedError(RuntimeError):
    """Raised when an envelope is None under ``conveyance_strict_on()``.

    Only active when ``CONVEYANCE_STRICT=1`` (or inherited from
    ``MEGAPLAN_UNIFIED_DISPATCH``).  Silent when the flag is off.
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
ENVELOPE_ENV_VAR = "MEGAPLAN_ENVELOPE_IN"
ENVELOPE_STDERR_TAG = "[megaplan-envelope]"


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
