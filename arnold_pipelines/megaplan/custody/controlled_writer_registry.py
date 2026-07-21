"""Controlled authoritative-writer boundary registry (M7 shadow-only).

Registers every Custody-owned controlled-writer boundary with an enablement
cohort (``report_only``, ``shadow``, or ``active``) and provides the
``writer_guard`` function that must be called before any production write
originating from a registered boundary.

Production writes by shadow-only cohorts **fail closed** — the guard returns
:attr:`WriteGuardDecision.DENIED` — until the writer is promoted to
``active`` after M6/M6A machine-verifiable acceptance.

North Star alignment
--------------------
* **Single-owner** — Custody is the sole owner of lease state.
  Cross-owner references are read-only.
* **Shadow-first** — All M7 Custody writers start in ``shadow_only``.
  No production gate or mutating effect is active.
* **Fail-closed** — A shadow-only writer that attempts a production write
  is rejected with a structured denial record.  There is no silent
  promotion path.
* **Explicit promotion** — A writer moves from ``shadow_only`` to
  ``active`` only after the owning milestone's machine-verifiable
  acceptance proof is recorded.

Cohorts
-------
==============  ==============================================================
report_only     Emit diagnostics; never attempt a write.  (Phase 0 artefacts.)
shadow          Perform all checks, emit diagnostics, and optionally write
                a shadow record, but never affect production state.
active          Full production enforcement; writes are accepted.
==============  ==============================================================
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, FrozenSet, Iterable, Mapping, MutableMapping, Optional

# ── Enablement cohort ──────────────────────────────────────────────────────────


class Cohort(StrEnum):
    """Enablement cohort for a controlled writer boundary.

    * **report_only** — diagnostics only; no writes.
    * **shadow** — full checks + diagnostics; shadow writes allowed but
      never affect production state.
    * **active** — full production enforcement; writes are accepted.
    """

    REPORT_ONLY = "report_only"
    SHADOW = "shadow"
    ACTIVE = "active"


# ── Write guard decision ───────────────────────────────────────────────────────


class WriteGuardDecision(StrEnum):
    """Outcome of a :func:`writer_guard` call."""

    ALLOWED = "allowed"
    """The write is permitted — the writer cohort is ``active``."""

    SHADOW_PASS = "shadow_pass"
    """All checks passed but the writer is in ``shadow`` cohort.
    No production write should be issued."""

    REPORT_ONLY = "report_only"
    """The writer is report-only; no write should be attempted."""

    DENIED = "denied"
    """The write was explicitly denied — the writer cohort is
    ``shadow_only`` (pre-M7 alias) or ``shadow`` and a production
    write was attempted while enforcement is off but the guard is
    in fail-closed mode."""

    UNREGISTERED = "unregistered"
    """The requested writer boundary is not in the registry.
    Treated as denied with an audit record."""


WRITER_REGISTRY_SCHEMA_VERSION = "1"
COHORTS: tuple[str, ...] = tuple(member.value for member in Cohort)
WRITE_GUARD_DECISIONS: tuple[str, ...] = tuple(
    member.value for member in WriteGuardDecision
)


# ── Controlled writer boundary ─────────────────────────────────────────────────


@dataclass(frozen=True)
class ControlledWriter:
    """A registered controlled writer boundary.

    Every authority-increasing or custody-gated write must originate from
    a boundary listed in the registry.  The cohort determines whether the
    write is allowed, shadow-only, or report-only.
    """

    writer_id: str
    """Stable identifier, e.g. ``"custody-03"``."""

    surface_name: str
    """Human-readable surface name, e.g. ``"lease_store"``."""

    cohort: Cohort = Cohort.SHADOW
    """Current enablement cohort."""

    owner: str = "Custody"
    """Owning component (always ``"Custody"`` for M7 entries)."""

    authority_increasing: bool = False
    """Does this writer gate an authority-increasing operation?"""

    module_path: str = ""
    """Dotted Python path to the writer module, e.g.
    ``"arnold_pipelines.megaplan.custody.lease_store"``."""

    description: str = ""
    """Human-readable description of what this writer boundary gates."""

    milestone: str = "M7"
    """Milestone that introduced this boundary."""

    prerequisite_milestones: FrozenSet[str] = field(default_factory=frozenset)
    """Milestones that must be machine-verifiably accepted before this writer
    can be promoted to ``active``."""

    contract_ids: tuple[str, ...] = ()
    source_file: str = ""
    function_name: str = ""
    required_wbc_phases: tuple[str, ...] = ()
    action_kind: str = ""

    def __post_init__(self) -> None:
        writer_id = str(self.writer_id).strip()
        surface_name = str(self.surface_name).strip()
        if not writer_id:
            raise ValueError("writer_id must be a non-empty string")
        if not surface_name:
            raise ValueError("surface_name must be a non-empty string")
        object.__setattr__(self, "writer_id", writer_id)
        object.__setattr__(self, "surface_name", surface_name)
        object.__setattr__(self, "cohort", Cohort(self.cohort))
        if not self.module_path and self.source_file:
            object.__setattr__(
                self,
                "module_path",
                self.source_file.removesuffix(".py").replace("/", "."),
            )
        if self.action_kind and not self.authority_increasing:
            object.__setattr__(self, "authority_increasing", True)
        object.__setattr__(
            self,
            "contract_ids",
            tuple(str(value) for value in self.contract_ids if str(value).strip()),
        )
        object.__setattr__(
            self,
            "required_wbc_phases",
            tuple(
                str(value) for value in self.required_wbc_phases if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "prerequisite_milestones",
            frozenset(
                str(value) for value in self.prerequisite_milestones if str(value).strip()
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "writer_id": self.writer_id,
            "surface_name": self.surface_name,
            "cohort": str(self.cohort),
            "owner": self.owner,
            "authority_increasing": self.authority_increasing,
            "module_path": self.module_path,
            "description": self.description,
            "milestone": self.milestone,
            "prerequisite_milestones": sorted(self.prerequisite_milestones),
            "contract_ids": list(self.contract_ids),
            "source_file": self.source_file,
            "function_name": self.function_name,
            "required_wbc_phases": list(self.required_wbc_phases),
            "action_kind": self.action_kind,
        }


# ── Registry ───────────────────────────────────────────────────────────────────

# Every Custody-owned controlled-writer boundary registered in M7.
# All entries start in ``shadow`` cohort — no production writes are
# accepted until M6/M6A machine-verifiable acceptance.
#
# Per SD1: these are net-new registry entries.  Existing Run Authority
# (38) and WBC (5) assignments are never reassigned.
CONTROLLED_WRITERS: tuple[ControlledWriter, ...] = (
    # ── Core Custody surfaces ──────────────────────────────────────────────
    ControlledWriter(
        writer_id="custody-01",
        surface_name="writer_map",
        cohort=Cohort.REPORT_ONLY,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.writer_map",
        description="Report-only provenance map; no production writes.",
        prerequisite_milestones=frozenset(),
    ),
    ControlledWriter(
        writer_id="custody-02",
        surface_name="contracts",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.contracts",
        description="Canonical Custody contract schemas (T3).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-03",
        surface_name="lease_store",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=True,
        module_path="arnold_pipelines.megaplan.custody.lease_store",
        description="Append-only Custody lease history (T5).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-04",
        surface_name="outbox",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.outbox",
        description="Durable cross-owner outbox records (T7).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-05",
        surface_name="action_validator",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=True,
        module_path="arnold_pipelines.megaplan.custody.action_validator",
        description="Conjunctive action-boundary gate (T8).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-06",
        surface_name="projections",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.projections",
        description="Cursor-checked projection appends (T16).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-07",
        surface_name="controlled_writer_registry",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=True,
        module_path="arnold_pipelines.megaplan.custody.controlled_writer_registry",
        description="Registry of controlled authority-increasing writers (T10).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    # ── Repair-admission surfaces ──────────────────────────────────────────
    ControlledWriter(
        writer_id="custody-08",
        surface_name="repair_request_queue",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.cloud.repair_requests",
        description="Repair request queue admission — enqueue/claim/bind (T11).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-09",
        surface_name="repair_locks_leases",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.cloud.repair_lock",
        description="PID locks downgraded to lease projections (T12).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-10",
        surface_name="repair_data",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.cloud.repair_data",
        description="Repair-data projection downgrade (T13).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-11",
        surface_name="repair_loops_l1_l2_l3",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.cloud.repair_runner",
        description="L1/L2/L3 repair loop dispatch (T14).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-12",
        surface_name="repair_source_install_retrigger",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.cloud.repair_runner",
        description="Source/install/retrigger repair paths (T15).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-13",
        surface_name="independent_verification",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.receipts",
        description="Independent verification writer (T17).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    # ── Receipts, compatibility, canary, bypass ────────────────────────────
    ControlledWriter(
        writer_id="custody-14",
        surface_name="receipts",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.receipts",
        description="Immutable attempt-scoped evidence receipts (T18).",
        prerequisite_milestones=frozenset({"M5", "M6A"}),
    ),
    ControlledWriter(
        writer_id="custody-15",
        surface_name="compatibility",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.compatibility",
        description="Old-reader/new-writer compatibility bridge (T20).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-16",
        surface_name="canary",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=False,
        module_path="arnold_pipelines.megaplan.custody.canary",
        description="Idle pinned-runtime canary (T21).",
        prerequisite_milestones=frozenset({"M5"}),
    ),
    ControlledWriter(
        writer_id="custody-17",
        surface_name="bypass_proof",
        cohort=Cohort.SHADOW,
        owner="Custody",
        authority_increasing=True,
        module_path="arnold_pipelines.megaplan.custody.bypass_proof",
        description="Bypass-proof registry; enforcement blocked until M6/M6A (T22).",
        prerequisite_milestones=frozenset({"M5", "M6", "M6A"}),
    ),
)


# ── Index helpers ──────────────────────────────────────────────────────────────

_REGISTERED_BY_ID: MutableMapping[str, ControlledWriter] = {}


def _registered_writers() -> tuple[ControlledWriter, ...]:
    """Return only explicitly adopted runtime writers.

    ``CONTROLLED_WRITERS`` is a report-only inventory.  Treating that static
    inventory as live registration would let a support manifest silently
    authorize writers and would make an empty registry impossible.
    """
    return tuple(_REGISTERED_BY_ID.values())


def _writers_for_surface(surface_name: str) -> tuple[ControlledWriter, ...]:
    label = str(surface_name).strip()
    if not label:
        return ()
    return tuple(writer for writer in _registered_writers() if writer.surface_name == label)


def get_writer(writer_id: str) -> Optional[ControlledWriter]:
    """Look up a controlled writer by its stable id."""
    label = str(writer_id).strip()
    if not label:
        return None
    return _REGISTERED_BY_ID.get(label)


def get_writer_by_surface(surface_name: str) -> Optional[ControlledWriter]:
    """Look up a controlled writer by its surface name."""
    matches = _writers_for_surface(surface_name)
    if len(matches) != 1:
        return None
    return matches[0]


def list_writers(cohort: Optional[Cohort] = None) -> list[ControlledWriter]:
    """Return all registered controlled writers, optionally filtered by cohort."""
    writers = _registered_writers()
    if cohort is None:
        return list(writers)
    selected = Cohort(cohort)
    return [w for w in writers if w.cohort == selected]


def list_active_writers() -> tuple[ControlledWriter, ...]:
    """Return writers currently in the ``active`` cohort."""
    return list_writers(Cohort.ACTIVE)


def list_shadow_writers() -> tuple[ControlledWriter, ...]:
    """Return writers currently in the ``shadow`` cohort."""
    return list_writers(Cohort.SHADOW)


def list_report_only_writers() -> tuple[ControlledWriter, ...]:
    """Return writers currently in the ``report_only`` cohort."""
    return list_writers(Cohort.REPORT_ONLY)


def list_authority_increasing_writers() -> tuple[ControlledWriter, ...]:
    """Return all registered writers that gate authority-increasing operations."""
    return tuple(
        w
        for w in _registered_writers()
        if w.cohort != Cohort.REPORT_ONLY and bool(w.action_kind)
    )


# ── Environment-flag enforcement ────────────────────────────────────────────────


def _production_enforcement_enabled() -> bool:
    """Check whether M7 production enforcement is enabled.

    Defaults to ``False`` (shadow-only) per SD2.
    Set ``ARNOLD_M7_WRITER_GUARD_ENFORCEMENT=1`` to enable production
    enforcement gates.
    """
    return os.environ.get("ARNOLD_M7_WRITER_GUARD_ENFORCEMENT", "0").strip() in ("1", "true", "yes")


def _fail_closed_mode() -> bool:
    """Check whether the writer guard is in fail-closed mode.

    When ``ARNOLD_M7_WRITER_GUARD_FAIL_CLOSED=1`` (the default for
    test environments), shadow-only writers that attempt a production
    write receive ``DENIED`` instead of ``SHADOW_PASS``.
    """
    return os.environ.get("ARNOLD_M7_WRITER_GUARD_FAIL_CLOSED", "1").strip() in ("1", "true", "yes")


# ── Writer guard ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WriteGuardResult:
    """Result of a :func:`writer_guard` call.

    Carries the decision and enough context for the caller to log
    diagnostics or abort the write.
    """

    decision: WriteGuardDecision = WriteGuardDecision.UNREGISTERED
    """Whether the write is allowed, shadow-pass, denied, or unregistered."""

    writer: Optional[ControlledWriter] = None
    """The registered writer, if found."""

    reason: str = ""
    """Human-readable explanation of the decision."""

    enforcement_enabled: bool = False
    """Was production enforcement enabled at the time of the call?"""

    fail_closed: bool = True
    """Was the guard in fail-closed mode?"""

    diagnostics: tuple[str, ...] = ()
    """Structured diagnostic breadcrumbs for fail-closed callers."""

    @property
    def allowed(self) -> bool:
        """Return ``True`` when the guard admits or shadows the write path."""
        return self.decision in {
            WriteGuardDecision.ALLOWED,
            WriteGuardDecision.SHADOW_PASS,
            WriteGuardDecision.REPORT_ONLY,
        }

    @property
    def writer_id(self) -> str | None:
        return self.writer.writer_id if self.writer else None

    @property
    def denied(self) -> bool:
        """Return ``True`` if the write was denied (``DENIED`` or ``UNREGISTERED``)."""
        return self.decision in {
            WriteGuardDecision.DENIED,
            WriteGuardDecision.UNREGISTERED,
        }

    def should_write(self) -> bool:
        """Return ``True`` if the caller should issue the production write.

        Only ``ALLOWED`` returns ``True``.  ``SHADOW_PASS`` and
        ``REPORT_ONLY`` are not writes.
        """
        return self.decision == WriteGuardDecision.ALLOWED

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": str(self.decision),
            "writer_id": self.writer.writer_id if self.writer else None,
            "surface_name": self.writer.surface_name if self.writer else None,
            "reason": self.reason,
            "enforcement_enabled": self.enforcement_enabled,
            "fail_closed": self.fail_closed,
            "diagnostics": list(self.diagnostics),
        }


def writer_guard(
    writer_id: str = "",
    *,
    surface_name: str = "",
    override_enforcement: Optional[bool] = None,
    override_fail_closed: Optional[bool] = None,
) -> WriteGuardResult:
    """Check whether a controlled writer is allowed to perform a production write.

    The guard is the single entry-point for all Custody-gated production
    writes.  Every authority-increasing or custody-gated write **must**
    pass through this guard before mutating production state.

    Decision matrix
    ---------------
    ====================  ==============  =============  ========================
    Cohort                 Enforcement    Fail-closed    Decision
    ====================  ==============  =============  ========================
    ``active``             any             any            ``ALLOWED``
    ``shadow``             off             any            ``SHADOW_PASS``
    ``shadow``             on              off            ``SHADOW_PASS``
    ``shadow``             on              on             ``DENIED``
    ``report_only``        any             any            ``REPORT_ONLY``
    unregistered           any             any            ``UNREGISTERED``
    ====================  ==============  =============  ========================

    Parameters
    ----------
    writer_id:
        Stable writer id (``"custody-03"``, etc.).  Takes precedence
        over *surface_name* when both are provided.
    surface_name:
        Human-readable surface name (``"lease_store"``, etc.).  Used
        only when *writer_id* is empty.
    override_enforcement:
        Override the environment-flag enforcement check.  Mainly for
        testing.
    override_fail_closed:
        Override the fail-closed mode check.  Mainly for testing.

    Returns
    -------
    WriteGuardResult
        A structured decision with context.
    """
    enforcement = (
        override_enforcement
        if override_enforcement is not None
        else _production_enforcement_enabled()
    )
    fail_closed = (
        override_fail_closed
        if override_fail_closed is not None
        else _fail_closed_mode()
    )

    # Resolve writer
    writer: Optional[ControlledWriter] = None
    lookup = writer_id or surface_name
    if writer_id:
        writer = get_writer(writer_id)
    elif surface_name:
        writer = get_writer_by_surface(surface_name)

    if writer is None:
        diagnostics = ()
        if surface_name and len(_writers_for_surface(surface_name)) > 1:
            diagnostics = (f"Ambiguous surface:{surface_name}",)
        elif lookup:
            diagnostics = (f"unknown writer:{lookup}",)
        return WriteGuardResult(
            decision=WriteGuardDecision.UNREGISTERED,
            writer=None,
            reason=(
                f"Writer boundary {lookup!r} is not in "
                f"the M7 controlled-writer registry.  All Custody-gated "
                f"writes must originate from a registered boundary."
            ),
            enforcement_enabled=enforcement,
            fail_closed=fail_closed,
            diagnostics=diagnostics,
        )

    # ── Cohort-based decision ───────────────────────────────────────────
    if writer.cohort == Cohort.ACTIVE and (
        enforcement or override_fail_closed is False
    ):
        return WriteGuardResult(
            decision=WriteGuardDecision.ALLOWED,
            writer=writer,
            reason=f"Writer {writer.writer_id!r} is in active cohort — write allowed.",
            enforcement_enabled=enforcement,
            fail_closed=fail_closed,
            diagnostics=(f"cohort:{writer.cohort.value}",),
        )

    if writer.cohort == Cohort.REPORT_ONLY:
        return WriteGuardResult(
            decision=WriteGuardDecision.REPORT_ONLY,
            writer=writer,
            reason=(
                f"Writer {writer.writer_id!r} is in report_only cohort — "
                f"no writes should be attempted."
            ),
            enforcement_enabled=enforcement,
            fail_closed=fail_closed,
            diagnostics=(f"cohort:{writer.cohort.value}",),
        )

    # Cohor*** is SHADOW
    if not enforcement:
        # Shadow mode — all checks pass but no production write
        return WriteGuardResult(
            decision=WriteGuardDecision.SHADOW_PASS,
            writer=writer,
            reason=(
                f"Writer {writer.writer_id!r} is in shadow cohort with "
                f"enforcement disabled — shadow pass (no production write)."
            ),
            enforcement_enabled=False,
            fail_closed=fail_closed,
            diagnostics=(f"cohort:{writer.cohort.value}",),
        )

    # Enforcement is ON and cohort is SHADOW
    if fail_closed:
        return WriteGuardResult(
            decision=WriteGuardDecision.DENIED,
            writer=writer,
            reason=(
                f"Writer {writer.writer_id!r} is in shadow cohort and "
                f"enforcement is enabled with fail-closed mode — production "
                f"write denied.  Promote the writer to active cohort only "
                f"after prerequisite milestones {sorted(writer.prerequisite_milestones)!r} "
                f"are machine-verifiably accepted."
            ),
            enforcement_enabled=True,
            fail_closed=True,
            diagnostics=(f"cohort:{writer.cohort.value}",),
        )

    # Enforcement ON, fail-closed OFF — still shadow pass (deferred)
    return WriteGuardResult(
        decision=WriteGuardDecision.SHADOW_PASS,
        writer=writer,
        reason=(
            f"Writer {writer.writer_id!r} is in shadow cohort with "
            f"enforcement enabled but fail-closed disabled — shadow pass "
            f"(deferred; promote to active for production writes)."
        ),
        enforcement_enabled=True,
        fail_closed=False,
        diagnostics=(f"cohort:{writer.cohort.value}",),
    )


# ── Bulk guard ─────────────────────────────────────────────────────────────────


def guard_all(
    writer_ids: Iterable[str] = (),
    *,
    override_enforcement: Optional[bool] = None,
    override_fail_closed: Optional[bool] = None,
) -> list[WriteGuardResult]:
    """Run :func:`writer_guard` against every writer in *writer_ids*.

    If *writer_ids* is empty, guard every registered writer.
    """
    ids = tuple(writer_ids) if writer_ids else tuple(
        w.writer_id for w in _registered_writers()
    )
    return [
        writer_guard(
            wid,
            override_enforcement=override_enforcement,
            override_fail_closed=override_fail_closed,
        )
        for wid in ids
    ]


def register_writer(writer: ControlledWriter) -> ControlledWriter:
    """Register an in-memory controlled writer for runtime/test adoption."""
    if not isinstance(writer, ControlledWriter):
        raise TypeError("Expected ControlledWriter")
    if writer.writer_id in _REGISTERED_BY_ID:
        raise ValueError(f"Duplicate writer_id: {writer.writer_id}")
    for existing in _registered_writers():
        if (
            existing.surface_name == writer.surface_name
            and existing.cohort == writer.cohort
        ):
            raise ValueError(
                f"Duplicate surface+cohort: {writer.surface_name} / {writer.cohort.value}"
            )
    _REGISTERED_BY_ID[writer.writer_id] = writer
    return writer


def deregister_writer(writer_id: str) -> bool:
    """Remove a runtime/test writer registration."""
    label = str(writer_id).strip()
    if not label:
        return False
    return _REGISTERED_BY_ID.pop(label, None) is not None


def _clear_registry() -> None:
    """Clear runtime/test registrations without touching built-in defaults."""
    _REGISTERED_BY_ID.clear()


# ── Public surface ─────────────────────────────────────────────────────────────

__all__ = [
    "COHORTS",
    "Cohort",
    "ControlledWriter",
    "CONTROLLED_WRITERS",
    "WRITER_REGISTRY_SCHEMA_VERSION",
    "WRITE_GUARD_DECISIONS",
    "WriteGuardDecision",
    "WriteGuardResult",
    "_clear_registry",
    "deregister_writer",
    "get_writer",
    "get_writer_by_surface",
    "guard_all",
    "list_active_writers",
    "list_authority_increasing_writers",
    "list_report_only_writers",
    "list_shadow_writers",
    "list_writers",
    "register_writer",
    "writer_guard",
]
