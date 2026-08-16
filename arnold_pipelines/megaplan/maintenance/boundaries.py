"""Read-only controlled-writer inventory boundary and typed M7 bypass findings.

This module implements the M7 mutation boundary for Maintenance code:

* it reads ``evidence/controlled-writer-registry.json`` WITHOUT any mutation
  capability — the registry model is frozen, declarative, and data-only;
* it exposes a typed :class:`M7BypassFinding` for any Maintenance request to
  write plan or chain truth.  The finding names the M7 seam, carries the M7
  handoff resolution from the strict registry (T5), and remains inert data:
  it never invokes ``write_plan_state``, ``save_chain_state``,
  ``TransitionWriter``, or any raw plan/chain writer.

The module deliberately does NOT import any lifecycle state writer.  The
forbidden writer names appear only as inert string constants in the finding
(``writer_call_counts`` is always all-zero, ``mutation_attempted`` is always
``False``), so there is no code path that could call a plan/chain writer
from Maintenance.

All models are frozen, forbid unknown fields, and round-trip through the
single canonical codec (``canonical_dumps`` / ``strict_loads``).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.handoffs import (
    HandoffRegistry,
    HandoffResolution,
    default_handoff_registry,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    canonical_digest,
    strict_loads,
)

#: The M7 seam this boundary names: the controlled-writer inventory gate.
M7_SEAM: str = (
    "M7 controlled-writer inventory (evidence/controlled-writer-registry.json)"
)

#: Inert names of the lifecycle/raw writers this boundary must never invoke.
#: These are data-only constants — the module never imports or calls them.
FORBIDDEN_DIRECT_WRITERS: tuple[str, ...] = (
    "write_plan_state",
    "save_chain_state",
    "TransitionWriter",
    "raw plan/chain writers",
)

#: Writer-id prefixes identifying plan-truth writers in the inventory.
_PLAN_WRITER_PREFIX: str = "writer.arnold_pipelines.megaplan.plan"
#: Writer-id prefixes identifying chain-truth writers in the inventory.
_CHAIN_WRITER_PREFIX: str = "writer.arnold_pipelines.megaplan.chain"


# ---------------------------------------------------------------------------
# Data-only controlled-writer registry (no mutation capability)
# ---------------------------------------------------------------------------


class ControlledWriterRow(BaseModel):
    """One declarative controlled-writer row (data only, never executable)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    writer_id: StrictStr
    writer_path: StrictStr
    writer_category: StrictStr
    surface_types: tuple[str, ...] = ()
    owner: StrictStr | None = None
    current_contract: StrictStr | None = None
    target_contract: StrictStr | None = None
    boundary_conditions: StrictStr | None = None
    fail_closed: StrictStr | None = None
    proof: StrictStr | None = None
    rollback_policy: StrictStr | None = None
    mixed_version_policy: StrictStr | None = None
    retirement_gate: StrictStr | None = None
    evidence_ref: StrictStr | None = None
    is_authority: bool = False
    inventory_category: StrictStr | None = None
    row_hash: StrictStr | None = None

    @field_validator("writer_id", "writer_path", "writer_category")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("controlled-writer identity fields must be non-empty")
        return value


class ControlledWriterRegistry(BaseModel):
    """Frozen, declarative, read-only controlled-writer inventory.

    Loaded from ``evidence/controlled-writer-registry.json``.  The registry
    exposes no write, mutate, or execute method of any kind.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # ``schema_identity`` maps to the inventory's ``schema`` key; the alias
    # avoids shadowing pydantic's BaseModel ``schema`` attribute while
    # keeping canonical round-trips byte-stable.
    schema_identity: StrictStr = Field(
        validation_alias="schema", serialization_alias="schema"
    )
    generated_at: StrictStr
    generator: StrictStr
    source_inventory: StrictStr
    writer_count: int
    category_counts: dict[str, int] = Field(default_factory=dict)
    writer_categories: tuple[str, ...] = ()
    fail_closed_default: StrictStr | None = None
    composite_hash: StrictStr | None = None
    row_hash_algorithm: StrictStr | None = None
    row_hash_coverage: StrictStr | None = None
    rows: tuple[ControlledWriterRow, ...] = ()

    @field_validator("writer_count")
    @classmethod
    def _validate_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"writer_count must be >= 0, got {value}")
        return value

    @model_validator(mode="after")
    def _check_writer_count(self) -> ControlledWriterRegistry:
        if len(self.rows) != self.writer_count:
            raise ValueError(
                f"controlled-writer registry declares writer_count={self.writer_count} "
                f"but carries {len(self.rows)} rows"
            )
        return self

    def rows_for(self, kind: str) -> tuple[ControlledWriterRow, ...]:
        """Return the inventory rows matching a plan/chain truth writer kind.

        Plan-truth writers match the ``writer.arnold_pipelines.megaplan.plan``
        id prefix; chain-truth writers match the ``...chain`` prefix.  The
        returned rows are declarative data only.
        """
        prefix = (
            _PLAN_WRITER_PREFIX if kind == "plan" else _CHAIN_WRITER_PREFIX
        )
        return tuple(
            sorted(
                (row for row in self.rows if row.writer_id.startswith(prefix)),
                key=lambda row: row.writer_id,
            )
        )

    def registry_digest(self) -> str:
        """Canonical digest of the inventory (content-addressed)."""
        return canonical_digest(self)


def load_controlled_writer_registry(path: str | Path) -> ControlledWriterRegistry:
    """Strict-load the controlled-writer inventory from a JSON file.

    Uses the single canonical strict decoder; missing or unknown fields fail
    with a typed
    :class:`~arnold_pipelines.megaplan.maintenance.identity.MaintenanceCodecError`.
    """
    text = Path(path).read_text(encoding="utf-8")
    return strict_loads(ControlledWriterRegistry, text)


@lru_cache(maxsize=1)
def default_controlled_writer_registry() -> ControlledWriterRegistry:
    """Return the repository's controlled-writer inventory (lazily loaded)."""
    project_root = Path(__file__).resolve().parents[3]
    return load_controlled_writer_registry(
        project_root / "evidence" / "controlled-writer-registry.json"
    )


# ---------------------------------------------------------------------------
# Typed M7 bypass finding
# ---------------------------------------------------------------------------


class M7BypassFindingKind(str, Enum):
    """Closed kinds of direct plan/chain mutation requests."""

    PLAN_WRITE = "plan_write"
    CHAIN_WRITE = "chain_write"


class M7BypassFinding(BaseModel):
    """Typed, inert finding for a Maintenance request to write plan/chain truth.

    The finding names the M7 seam, carries the M7 handoff resolution (from
    the strict registry), and lists the matching controlled-writer inventory
    rows as data.  It is guaranteed inert: ``mutation_attempted`` is always
    ``False`` and every forbidden writer's call count is zero.  This module
    never imports or invokes ``write_plan_state``, ``save_chain_state``,
    ``TransitionWriter``, or a raw plan/chain writer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    finding_id: StrictStr
    kind: M7BypassFindingKind
    request: StrictStr
    seam: StrictStr = M7_SEAM
    m7_handoff: HandoffResolution
    matching_writers: tuple[ControlledWriterRow, ...] = ()
    forbidden_writers: tuple[str, ...] = FORBIDDEN_DIRECT_WRITERS
    writer_call_counts: dict[str, int] = Field(default_factory=dict)
    mutation_attempted: Literal[False] = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("finding_id", "request")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("finding_id/request must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _enforce_inert(self) -> M7BypassFinding:
        if self.mutation_attempted:
            raise ValueError("an M7 bypass finding can never attempt mutation")
        for writer in self.forbidden_writers:
            if self.writer_call_counts.get(writer, 0) != 0:
                raise ValueError(
                    f"an M7 bypass finding must report zero call counts for "
                    f"{writer!r}; direct lifecycle/raw writers are never invoked"
                )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the finding (replayable, data-only)."""
        return canonical_digest(self)


def bypass_finding(
    kind: M7BypassFindingKind | str,
    request: str,
    *,
    finding_id: str | None = None,
    registry: ControlledWriterRegistry | None = None,
    handoff_registry: HandoffRegistry | None = None,
) -> M7BypassFinding:
    """Return a typed M7 bypass finding for a plan/chain write request.

    Resolves the M7 handoff through the strict registry (pending human
    approval stays an explicit blocker — never an accepted seam), attaches
    the matching controlled-writer rows as data, and guarantees zero writer
    call counts.  No mutation is ever attempted.
    """
    kind_value = M7BypassFindingKind(kind)
    inventory = (
        registry
        if registry is not None
        else default_controlled_writer_registry()
    )
    handoffs = (
        handoff_registry
        if handoff_registry is not None
        else default_handoff_registry()
    )
    m7 = handoffs.resolve("M7")
    plan_chain_kind = "plan" if kind_value is M7BypassFindingKind.PLAN_WRITE else "chain"
    matching = inventory.rows_for(plan_chain_kind)
    resolved_id = finding_id or (
        f"m7-bypass:{kind_value.value}:{plan_chain_kind}:"
        f"{inventory.registry_digest()[:16]}"
    )
    return M7BypassFinding(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        finding_id=resolved_id,
        kind=kind_value,
        request=request,
        seam=M7_SEAM,
        m7_handoff=m7,
        matching_writers=matching,
        forbidden_writers=FORBIDDEN_DIRECT_WRITERS,
        writer_call_counts={
            writer: 0 for writer in FORBIDDEN_DIRECT_WRITERS
        },
        mutation_attempted=False,
    )


def plan_write_finding(
    request: str,
    *,
    finding_id: str | None = None,
    registry: ControlledWriterRegistry | None = None,
    handoff_registry: HandoffRegistry | None = None,
) -> M7BypassFinding:
    """Typed M7 bypass finding for a request to write PLAN truth."""
    return bypass_finding(
        M7BypassFindingKind.PLAN_WRITE,
        request,
        finding_id=finding_id,
        registry=registry,
        handoff_registry=handoff_registry,
    )


def chain_write_finding(
    request: str,
    *,
    finding_id: str | None = None,
    registry: ControlledWriterRegistry | None = None,
    handoff_registry: HandoffRegistry | None = None,
) -> M7BypassFinding:
    """Typed M7 bypass finding for a request to write CHAIN truth."""
    return bypass_finding(
        M7BypassFindingKind.CHAIN_WRITE,
        request,
        finding_id=finding_id,
        registry=registry,
        handoff_registry=handoff_registry,
    )


__all__ = [
    "ControlledWriterRegistry",
    "ControlledWriterRow",
    "FORBIDDEN_DIRECT_WRITERS",
    "M7BypassFinding",
    "M7BypassFindingKind",
    "M7_SEAM",
    "bypass_finding",
    "chain_write_finding",
    "default_controlled_writer_registry",
    "load_controlled_writer_registry",
    "plan_write_finding",
]
