"""Machine-readable ledger traces with stable content-addressed digests.

This module provides non-authoritative trace emission for the WBC
transactional ledger. Every trace binds contract version, store/API
revision, code/config, adapter, run, attempt, tenant, and causal
identity while remaining a rebuildable projection — traces never mint
authority, leases, completion, cancellation, publication, or delivery
decisions.

Key invariants:
* Content-addressed stability — traces are deterministic. Given the
  same inputs, the same digest is always produced.
* Identity binding — every trace carries immutable identity fields
  from the underlying ``LedgerEvent`` so downstream consumers can
  join without granting authority.
* Non-authoritative — traces are computed from the same durable data
  the store already holds. A missing or corrupted trace does not
  change the store's state and never invalidates the event stream.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AdapterKind,
    AttemptEventType,
    LedgerEvent,
)

# ── Trace operation kind ──────────────────────────────────────────────────


class TraceOperation(Enum):
    """Kind of store operation a trace records.

    These are stable enumeration values — changing a member name or
    value would break content-address stability, so they should only
    be added to, never renamed or removed.
    """

    APPEND = "append"
    """An event was appended (or dedup-returned) to the ledger."""

    QUERY = "query"
    """Gaps, diagnostics, reconciliation state, or source cursors were
    read from the store."""

    RECONCILE = "reconcile"
    """A durable gate (start_verified or terminal_or_indeterminate_verified)
    was evaluated against the persisted event stream."""


# ── Trace schema version ─────────────────────────────────────────────────

LEDGER_TRACE_SCHEMA_VERSION: str = "arnold.workflow.ledger_trace.v1"
"""Schema version embedded in every trace for forward/backward compatibility."""

_STORE_VERSION: str = "arnold.workflow.attempt_ledger_store.v1"
"""Store/API revision bound into every trace."""


# ── LedgerTrace ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LedgerTrace:
    """A single machine-readable trace for a WBC ledger operation.

    Every trace is content-addressed via ``digest`` — a SHA-256
    hex digest over the canonical JSON representation (sorted keys,
    no whitespace).  Two traces with identical content will always
    produce the same digest.

    Traces are evidence, not authority.  They do not affect store
    state, append decisions, gate results, or delivery scheduling.
    They are projections that can be rebuilt from the durable event
    stream at any time.

    Identity fields bound into every trace:
    * ``contract_version`` — the ``LEDGER_SCHEMA_VERSION`` the store
      was compiled against.
    * ``store_version`` — the store/API revision string.
    * ``code_version`` / ``config_version`` — from the event's
      ``VersionSet``.
    * ``adapter_kind`` / ``adapter_version`` — from the event's
      ``RuntimeAdapter``.
    * ``run_id`` — the workflow run identifier (from ``AttemptIdentity``).
    * ``attempt_id`` — the attempt UUID (from ``AttemptIdentity``).
    * ``workflow_id`` — the tenant/workflow scope (from ``AttemptIdentity``).
    * ``parent_attempt_id`` / ``causal_lineage`` — causal identity
      from ``AttemptProvenance``.
    """

    # ── Metadata ────────────────────────────────────────────────────
    trace_schema_version: str = LEDGER_TRACE_SCHEMA_VERSION
    """Schema version for this trace format."""

    operation: TraceOperation = field(default=TraceOperation.APPEND)
    """What kind of store operation this trace describes."""

    emitted_at_ns: int = field(default_factory=time.time_ns)
    """Wall-clock nanosecond when the trace was computed."""

    # ── Content-addressed digest ─────────────────────────────────────
    digest: str = ""
    """SHA-256 hex digest of the canonical trace payload (set via
    :func:`compute_trace_digest` after construction)."""

    # ── Contract / store binding ─────────────────────────────────────
    contract_version: str = LEDGER_SCHEMA_VERSION
    """The ``LEDGER_SCHEMA_VERSION`` the store was compiled against."""

    store_version: str = _STORE_VERSION
    """Store/API revision string."""

    # ── Code / config versions ───────────────────────────────────────
    code_version: str = ""
    """Code version from the event's ``VersionSet.code_version``."""

    config_version: str = ""
    """Config version from the event's ``VersionSet.config_version``."""

    # ── Adapter identity ─────────────────────────────────────────────
    adapter_kind: str = ""
    """Runtime adapter kind (e.g. ``native``, ``container``)."""

    adapter_version: str = ""
    """Runtime adapter version string."""

    # ── Run / attempt identity ───────────────────────────────────────
    run_id: str = ""
    """Workflow run identifier from ``AttemptIdentity.run_id``."""

    attempt_id: str = ""
    """Attempt UUID from ``AttemptIdentity.attempt_id``."""

    # ── Tenant / workflow scope ──────────────────────────────────────
    workflow_id: str = ""
    """Workflow identifier serving as tenant scope."""

    # ── Causal identity ──────────────────────────────────────────────
    parent_attempt_id: str | None = None
    """Immediate predecessor attempt ID (None for initial attempt)."""

    causal_lineage: tuple[str, ...] = ()
    """Ordered list of ancestor attempt IDs (oldest first)."""

    # ── Operation-specific payload ───────────────────────────────────
    payload: dict[str, Any] = field(default_factory=dict)
    """Operation-specific trace payload (event type, sequence, query
    parameters, gate status, gap details, etc.).  This is projected
    from the durable data — it never synthesizes new authority."""

    # ── Non-authority marker ─────────────────────────────────────────
    authority: str = "evidence-only"
    """Hardcoded marker confirming this trace is evidence, not authority.

    This field is pinned to ``"evidence-only"``.  No code path may
    set it to ``"authoritative"``, ``"granting"``, ``"leasing"``, or
    any value that implies decision power.
    """

    def __post_init__(self) -> None:
        # Enforce the non-authority invariant at construction time.
        if self.authority != "evidence-only":
            raise ValueError(
                "LedgerTrace.authority must be 'evidence-only'; "
                f"got {self.authority!r}."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the trace as a deterministically-ordered dictionary.

        The returned dict uses sorted keys and stable types (lists for
        tuples).  Serializing this dict with ``json.dumps(..., sort_keys=True)``
        produces the canonical form that is hashed for the content-addressed
        digest.
        """
        return {
            "trace_schema_version": self.trace_schema_version,
            "operation": self.operation.value,
            "emitted_at_ns": self.emitted_at_ns,
            "digest": self.digest,
            "contract_version": self.contract_version,
            "store_version": self.store_version,
            "code_version": self.code_version,
            "config_version": self.config_version,
            "adapter_kind": self.adapter_kind,
            "adapter_version": self.adapter_version,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "workflow_id": self.workflow_id,
            "parent_attempt_id": self.parent_attempt_id,
            "causal_lineage": list(self.causal_lineage),
            "payload": self.payload,
            "authority": self.authority,
        }

    # Hash exclusion — ``digest`` is the hash of the trace, so it
    # cannot be part of the pre-image.  We strip it when computing the
    # canonical payload.

    def _canonical_payload(self) -> dict[str, Any]:
        """Return the dict that is hashed (timing metadata excluded).

        The ``digest`` and ``emitted_at_ns`` fields are excluded from
        the pre-image so that traces with identical semantic content
        produce the same digest regardless of when they were emitted.
        """
        d = self.to_dict()
        # Remove timing + self-referential fields from the pre-image.
        d.pop("digest", None)
        d.pop("emitted_at_ns", None)
        return d

    def _canonical_json(self) -> str:
        """Deterministic JSON serialization used as the hash pre-image."""
        return json.dumps(
            self._canonical_payload(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )


# ── Digest computation ────────────────────────────────────────────────────


def compute_trace_digest(trace: LedgerTrace) -> str:
    """Compute the SHA-256 content-addressed digest for *trace*.

    The digest is computed over the canonical JSON representation of
    the trace (sorted keys, compact separators, ``digest`` field
    excluded from the pre-image).  Two traces with identical content
    will always produce the same digest.

    Returns:
        A 64-character hex-encoded SHA-256 digest string.
    """
    canonical = trace._canonical_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_trace_with_digest(trace: LedgerTrace) -> LedgerTrace:
    """Return a copy of *trace* with ``digest`` computed and set.

    Uses ``object.__setattr__`` because ``LedgerTrace`` is frozen.
    """
    digest = compute_trace_digest(trace)
    object.__setattr__(trace, "digest", digest)
    return trace


# ── Trace constructors ────────────────────────────────────────────────────


def make_append_trace(
    event: LedgerEvent,
    *,
    is_duplicate: bool = False,
    sequence: int = 0,
    event_type_str: str = "",
) -> LedgerTrace:
    """Build an APPEND trace from a ``LedgerEvent``.

    The trace binds every identity field from the event plus
    operation-specific payload (event_type, sequence, is_duplicate,
    idempotency_key).  It then computes and sets the content-addressed
    digest.

    Args:
        event: The ``LedgerEvent`` that was appended (or dedup-returned).
        is_duplicate: ``True`` when the store returned an existing event
            for the same idempotency key.
        sequence: The event's persisted sequence number.
        event_type_str: The string value of the event type.
    """
    identity = event.identity
    provenance = event.provenance
    adapter = event.adapter
    versions = event.versions

    trace = LedgerTrace(
        operation=TraceOperation.APPEND,
        emitted_at_ns=time.time_ns(),
        contract_version=LEDGER_SCHEMA_VERSION,
        store_version=_STORE_VERSION,
        code_version=versions.code_version,
        config_version=versions.config_version,
        adapter_kind=adapter.adapter_kind.value
        if isinstance(adapter.adapter_kind, AdapterKind)
        else str(adapter.adapter_kind),
        adapter_version=adapter.adapter_version,
        run_id=identity.run_id,
        attempt_id=identity.attempt_id,
        workflow_id=identity.workflow_id,
        parent_attempt_id=provenance.parent_attempt_id,
        causal_lineage=provenance.causal_lineage,
        payload={
            "event_type": event_type_str or event.event_type.value,
            "sequence": sequence or event.sequence,
            "is_duplicate": is_duplicate,
            "idempotency_key": event.idempotency_key,
            "graph_revision": identity.graph_revision,
            "step_id": identity.step_id,
            "boundary_id": identity.boundary_id,
            "invocation_id": identity.invocation_id,
            "attempt_ordinal": identity.attempt_ordinal,
            "actor_id": provenance.actor_id,
            "tool_id": provenance.tool_id,
            "template_version": versions.template_version,
        },
    )
    return make_trace_with_digest(trace)


def make_query_trace(
    *,
    attempt_id: str,
    query_kind: str,
    run_id: str = "",
    workflow_id: str = "",
    parent_attempt_id: str | None = None,
    causal_lineage: tuple[str, ...] = (),
    adapter_kind: str = "",
    adapter_version: str = "",
    code_version: str = "",
    config_version: str = "",
    query_params: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
) -> LedgerTrace:
    """Build a QUERY trace for diagnostic/cursor/reconciliation reads.

    Query traces record that a consumer read gaps, diagnostics,
    reconciliation state, or source cursors from the store.  They
    bind the same identity fields as other traces so downstream
    consumers can join without granting authority.

    Args:
        attempt_id: The attempt being queried.
        query_kind: What was queried — e.g. ``"gaps"``,
            ``"persistence_diagnostics"``, ``"reconciliation_state"``,
            ``"source_cursor"``.
        run_id: Workflow run identifier.
        workflow_id: Workflow/tenant scope.
        parent_attempt_id: Immediate predecessor attempt ID.
        causal_lineage: Ordered ancestor attempt IDs.
        adapter_kind: Runtime adapter kind.
        adapter_version: Runtime adapter version.
        code_version: Code version from VersionSet.
        config_version: Config version from VersionSet.
        query_params: Parameters passed to the query.
        result_summary: Aggregated result metadata (not raw results).
    """
    trace = LedgerTrace(
        operation=TraceOperation.QUERY,
        emitted_at_ns=time.time_ns(),
        contract_version=LEDGER_SCHEMA_VERSION,
        store_version=_STORE_VERSION,
        code_version=code_version,
        config_version=config_version,
        adapter_kind=adapter_kind,
        adapter_version=adapter_version,
        run_id=run_id,
        attempt_id=attempt_id,
        workflow_id=workflow_id,
        parent_attempt_id=parent_attempt_id,
        causal_lineage=causal_lineage,
        payload={
            "query_kind": query_kind,
            "query_params": query_params or {},
            "result_summary": result_summary or {},
        },
    )
    return make_trace_with_digest(trace)


def make_reconcile_trace(
    *,
    attempt_id: str,
    reconcile_kind: str,
    gate_status: str,
    run_id: str = "",
    workflow_id: str = "",
    parent_attempt_id: str | None = None,
    causal_lineage: tuple[str, ...] = (),
    adapter_kind: str = "",
    adapter_version: str = "",
    code_version: str = "",
    config_version: str = "",
    detail: dict[str, Any] | None = None,
) -> LedgerTrace:
    """Build a RECONCILE trace for durable gate evaluations.

    Reconcile traces record that a durable gate (``start_verified``
    or ``terminal_or_indeterminate_verified``) was evaluated against
    the persisted event stream.  They record the gate status and any
    supporting detail without granting authority.

    Args:
        attempt_id: The attempt being reconciled.
        reconcile_kind: Which gate — ``"start_verified"`` or
            ``"terminal_or_indeterminate_verified"``.
        gate_status: The ``GateStatus`` value (``"verified"``,
            ``"incomplete"``, ``"indeterminate"``, ``"incoherent"``).
        run_id: Workflow run identifier.
        workflow_id: Workflow/tenant scope.
        parent_attempt_id: Immediate predecessor attempt ID.
        causal_lineage: Ordered ancestor attempt IDs.
        adapter_kind: Runtime adapter kind.
        adapter_version: Runtime adapter version.
        code_version: Code version from VersionSet.
        config_version: Config version from VersionSet.
        detail: Additional reconciliation detail (event counts, gap
            counts, diagnostic counts, etc.).
    """
    trace = LedgerTrace(
        operation=TraceOperation.RECONCILE,
        emitted_at_ns=time.time_ns(),
        contract_version=LEDGER_SCHEMA_VERSION,
        store_version=_STORE_VERSION,
        code_version=code_version,
        config_version=config_version,
        adapter_kind=adapter_kind,
        adapter_version=adapter_version,
        run_id=run_id,
        attempt_id=attempt_id,
        workflow_id=workflow_id,
        parent_attempt_id=parent_attempt_id,
        causal_lineage=causal_lineage,
        payload={
            "reconcile_kind": reconcile_kind,
            "gate_status": gate_status,
            "detail": detail or {},
        },
    )
    return make_trace_with_digest(trace)


# ── Serialization helpers ─────────────────────────────────────────────────


def trace_to_json(trace: LedgerTrace) -> str:
    """Serialize *trace* to a deterministic JSON string.

    Uses sorted keys, compact separators, and ``ensure_ascii=False``
    for maximum determinism across Python versions.
    """
    return json.dumps(
        trace.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def trace_from_json(data: str) -> LedgerTrace:
    """Deserialize a JSON string back into a ``LedgerTrace``.

    The ``causal_lineage`` field is converted from list back to tuple.
    The ``operation`` field is parsed from string back to ``TraceOperation``.
    The ``digest`` is NOT recomputed — the caller is responsible for
    verifying digest stability if needed.
    """
    d = json.loads(data)
    # Convert list back to tuple for causal_lineage.
    lineage = d.get("causal_lineage", [])
    if isinstance(lineage, list):
        d["causal_lineage"] = tuple(lineage)
    # Parse operation enum.
    op_raw = d.get("operation", "append")
    try:
        d["operation"] = TraceOperation(op_raw)
    except ValueError:
        # Unknown operation — keep as-is but it's a forward-compat risk.
        pass
    # Remove digest before construction — it's set via __post_init__
    # and then we set it via object.__setattr__.
    stored_digest = d.pop("digest", "")
    trace = LedgerTrace(**{k: v for k, v in d.items() if k in LedgerTrace.__dataclass_fields__})
    if stored_digest:
        object.__setattr__(trace, "digest", stored_digest)
    return trace


# M9 byte-store access traces are additive evidence and do not replace the
# content-addressed M6 ledger trace surface.
from arnold.workflow._ledger_trace_m9 import (  # noqa: E402
    FileLedgerTrace,
    LedgerTraceEvent,
)


__all__ = [
    "FileLedgerTrace",
    "LEDGER_TRACE_SCHEMA_VERSION",
    "LedgerTrace",
    "LedgerTraceEvent",
    "TraceOperation",
    "build_append_trace",
    "build_query_trace",
    "build_reconcile_trace",
    "compute_trace_digest",
    "make_trace_with_digest",
    "trace_from_json",
    "trace_to_json",
]
