"""Execution attempt ledger schema for workflow boundary contracts.

This module freezes the ``ExecutionAttemptLedger`` schema contract under
``arnold.workflow``. It defines the identity, ordering, provenance, and
append-position core of ordered attempt history for every supported runtime.

Each attempt records:

* Immutable workflow/run/graph-revision, step/boundary, invocation,
  attempt ordinal/id.
* Parent/causal lineage and actor/tool provenance.
* Runtime adapter identity and code/config/template version anchoring.
* Grant/decision references from Run Authority.
* Monotonic per-attempt sequence, causal predecessor, and durable append
  position.
* Idempotency key for each event.
* Occurred and observed timestamps (clocks alone never establish ordering).

Required event types: started, completed, failed, retry_scheduled, suspended,
resumed, cancelled, external_effect_intent, external_effect_outcome,
persistence_failed, reconciliation.

Ledger events carry typed payload references for the following semantic
categories (each with inline data, durable ref, content digest, and
schema version):

* ``InputPayload`` — declared inputs to a step/boundary.
* ``OutputPayload`` — declared outputs from a step/boundary.
* ``ResultPayload`` — phase/scalar result payloads.
* ``VerdictPayload`` — semantic-health verdicts and audit judgments.
* ``StateDeltaPayload`` — expected/observed state deltas for a boundary.
* ``ArtifactPayload`` — artifact handoff and promotion payloads.
* ``CheckpointPayload`` — resume anchors and in-progress witnesses.
* ``AuthorityPayload`` — authority decisions, grants, and transition intents.
* ``ExternalEffectPayload`` — pre-effect intent and outcome evidence for
  external side effects.

Persistence-failure and reconciliation diagnostics are captured via:

* ``PersistenceFailureDiagnostic`` — failure mode, recovery evidence spool
  reference, quarantined authority advance indicator, and observed error.
* ``ReconciliationDiagnostic`` — reconciliation target (the failed event),
  outcome, recovered evidence refs, and explicit authority disposition.

This is schema-only — no I/O, mutation, or runtime effects.

.. _ledger-primitive-gaps:

Current Primitive Gaps
----------------------

The following gaps exist in the current ledger primitives and must be
addressed by future C2-C6 migration work. They are documented here so
consumers and reviewers do not mistake their absence for design intent.

NDJSON Sequence Gaps
~~~~~~~~~~~~~~~~~~~~

The current ``LedgerPosition`` uses integer ``sequence`` and
``append_position`` fields. These are not backed by a real persistent
sequence generator. When the ledger is materialized to NDJSON storage
(one JSON object per line, appended), sequence gaps can arise from:

1. **Append-without-flush**: A runtime writes an event to NDJSON but
   crashes before the fsync/close. The file may contain a truncated
   line or a partial write at EOF. The next restart sees the gap but
   has no durable record of whether the event was fully committed.

2. **Concurrent append races**: If two runtime instances share the same
   NDJSON file without a file-level lock or append-index coordination,
   interleaved writes can produce unparseable lines and apparent
   sequence gaps.

3. **Rotated/missing segment files**: If the NDJSON log is rotated
   (e.g., by logrotate or a retention job) without updating the
   ledger's segment manifest, events in the rotated segment appear
   missing, producing a sequence gap.

**Mitigation path (C4-C5)**: Replace bare NDJSON appends with a
write-ahead log (WAL) or append-blob store that provides atomic
append-with-checksum, segment manifests, and gap-detection on open.
Until then, consumers MUST treat sequence gaps as ``indeterminate``
and MUST NOT silently skip them.

Missing Transaction / Outbox Migration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The North Star mandates that internal state/result publication uses
one transaction where the store permits, or a durable outbox /
prepare-commit protocol with deterministic reconciliation. The current
ledger schema has no representation for:

1. **Transaction boundaries**: There is no ``transaction_begin`` /
   ``transaction_commit`` / ``transaction_abort`` event type. The
   ledger cannot express that a group of events were written atomically.

2. **Outbox records**: There is no ``OutboxRecord`` type linking a
   ledger event to an outbox message that must be delivered to a
   downstream consumer. The outbox pattern (write event + outbox message
   in one transaction, then deliver from outbox) is not modeled.

3. **Prepare-commit protocol**: There is no ``prepare`` / ``commit`` /
   ``rollback`` event vocabulary for two-phase commit across the ledger
   and an external store.

**Mitigation path (C4-C6)**: Add ``transaction_begin``,
``transaction_commit``, and ``transaction_abort`` event types. Add an
``OutboxRecord`` dataclass with message identity, delivery target,
idempotency key, and delivery status. Add ``prepare`` and ``commit``
event types for two-phase scenarios. Until then, consumers MUST treat
every ledger event as independently durable and MUST NOT assume
atomicity across events.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from arnold.workflow.durable_refs import DurableRef


# ── Digest helpers (shared with durable_refs) ──────────────────────────────

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_digest(value: str) -> str:
    """Validate a canonical digest string."""
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ValueError(
            f"digest must be 'sha256:' followed by 64 lowercase hex chars, "
            f"got {value!r}"
        )
    return value


# ── Enums ─────────────────────────────────────────────────────────────────


class AttemptEventType(StrEnum):
    """Stable event types for the execution attempt ledger.

    These cover the full lifecycle of a supported attempt from dispatch
    through terminal outcome, including external effects and persistence
    failure states.
    """

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    EXTERNAL_EFFECT_INTENT = "external_effect_intent"
    EXTERNAL_EFFECT_OUTCOME = "external_effect_outcome"
    PERSISTENCE_FAILED = "persistence_failed"
    RECONCILIATION = "reconciliation"


class AttemptOutcome(StrEnum):
    """Terminal outcome of an execution attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    CANCELLED = "cancelled"


class AdapterKind(StrEnum):
    """Runtime adapter kind for execution attempts."""

    NATIVE = "arnold.pipeline.native"
    MEGAPLAN_PHASE = "megaplan.phase"
    MEGAPLAN_REDUCER = "megaplan.reducer"
    MEGAPLAN_CHAIN = "megaplan.chain"
    MEGAPLAN_AUDITOR = "megaplan.auditor"
    MEGAPLAN_CLOUD_REPAIR = "megaplan.cloud_repair"
    MEGAPLAN_VERIFICATION = "megaplan.verification"


class PersistenceStatus(StrEnum):
    """Persistence status for a ledger event or attempt."""

    DURABLE = "durable"
    PERSISTENCE_FAILED = "persistence_failed"
    INDETERMINATE = "indeterminate"


# ── Schema version constants ──────────────────────────────────────────────

LEDGER_SCHEMA_VERSION: str = "arnold.workflow.execution_attempt_ledger.v1"

# The set of event types that represent terminal attempt states.
_TERMINAL_EVENT_TYPES: frozenset[AttemptEventType] = frozenset(
    {
        AttemptEventType.COMPLETED,
        AttemptEventType.FAILED,
        AttemptEventType.CANCELLED,
    }
)

# Lifecycle ordering: which event types must precede others.
# Each entry maps an event type to the set of event types that MUST have
# occurred before it in the same attempt stream.
_LIFECYCLE_PRECEDENCE: Mapping[AttemptEventType, frozenset[AttemptEventType]] = (
    MappingProxyType(
        {
            AttemptEventType.STARTED: frozenset(),
            AttemptEventType.COMPLETED: frozenset({AttemptEventType.STARTED}),
            AttemptEventType.FAILED: frozenset({AttemptEventType.STARTED}),
            AttemptEventType.RETRY_SCHEDULED: frozenset({AttemptEventType.STARTED}),
            AttemptEventType.SUSPENDED: frozenset({AttemptEventType.STARTED}),
            AttemptEventType.RESUMED: frozenset({AttemptEventType.SUSPENDED}),
            AttemptEventType.CANCELLED: frozenset({AttemptEventType.STARTED}),
            AttemptEventType.EXTERNAL_EFFECT_INTENT: frozenset(
                {AttemptEventType.STARTED}
            ),
            AttemptEventType.EXTERNAL_EFFECT_OUTCOME: frozenset(
                {AttemptEventType.EXTERNAL_EFFECT_INTENT}
            ),
            AttemptEventType.PERSISTENCE_FAILED: frozenset(),
            AttemptEventType.RECONCILIATION: frozenset(
                {AttemptEventType.PERSISTENCE_FAILED}
            ),
        }
    )
)


# ── Typed payload references ─────────────────────────────────────────────


class PayloadSchemaVersion(StrEnum):
    """Schema versions for typed ledger payload references."""

    INPUT_V1 = "arnold.workflow.ledger.input_payload.v1"
    OUTPUT_V1 = "arnold.workflow.ledger.output_payload.v1"
    RESULT_V1 = "arnold.workflow.ledger.result_payload.v1"
    VERDICT_V1 = "arnold.workflow.ledger.verdict_payload.v1"
    STATE_DELTA_V1 = "arnold.workflow.ledger.state_delta_payload.v1"
    ARTIFACT_V1 = "arnold.workflow.ledger.artifact_payload.v1"
    CHECKPOINT_V1 = "arnold.workflow.ledger.checkpoint_payload.v1"
    AUTHORITY_V1 = "arnold.workflow.ledger.authority_payload.v1"
    EXTERNAL_EFFECT_V1 = "arnold.workflow.ledger.external_effect_payload.v1"


@dataclass(frozen=True)
class _TypedPayloadBase:
    """Base for typed ledger payload references.

    Every typed payload carries one of:
    - ``inline_data``: a small canonical payload suitable for inline storage.
    - ``ref``: a ``DurableRef`` for large or sensitive payloads.
    - Both ``inline_data`` and ``ref`` are ``None``: the payload is
      represented by its content digest only (integrity evidence, not
      result preservation — validated separately).

    At least one of ``inline_data``, ``ref``, or ``content_digest`` must
    be provided. A typed payload with only a content digest is integrity
    evidence and MAY be rejected by payload policy validators.
    """

    inline_data: dict[str, Any] | None = None
    ref: DurableRef | None = None
    content_digest: str | None = None

    def __post_init__(self) -> None:
        if self.content_digest is not None:
            _require_digest(self.content_digest)

        # At least one of inline_data, ref, or content_digest must be present.
        if (
            self.inline_data is None
            and self.ref is None
            and self.content_digest is None
        ):
            raise ValueError(
                f"{type(self).__name__}: at least one of inline_data, ref, "
                f"or content_digest must be provided"
            )

        # inline_data and ref are mutually exclusive for a well-formed payload.
        if self.inline_data is not None and self.ref is not None:
            raise ValueError(
                f"{type(self).__name__}: inline_data and ref are mutually "
                f"exclusive — choose one payload representation"
            )

    @property
    def is_inline(self) -> bool:
        """True when the payload is carried inline."""
        return self.inline_data is not None

    @property
    def is_reference(self) -> bool:
        """True when the payload is carried via a durable reference."""
        return self.ref is not None

    @property
    def is_digest_only(self) -> bool:
        """True when only a content digest is available (integrity evidence)."""
        return (
            self.inline_data is None
            and self.ref is None
            and self.content_digest is not None
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        result: dict[str, Any] = {}
        if self.inline_data is not None:
            result["inline_data"] = self.inline_data
        if self.ref is not None:
            result["ref"] = self.ref.to_dict()
        if self.content_digest is not None:
            result["content_digest"] = self.content_digest
        return result


# ── Concrete typed payload classes ──────────────────────────────────────


@dataclass(frozen=True)
class InputPayload(_TypedPayloadBase):
    """Typed payload for declared inputs to a step/boundary.

    Schema: ``arnold.workflow.ledger.input_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.INPUT_V1.value


@dataclass(frozen=True)
class OutputPayload(_TypedPayloadBase):
    """Typed payload for declared outputs from a step/boundary.

    Schema: ``arnold.workflow.ledger.output_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.OUTPUT_V1.value


@dataclass(frozen=True)
class ResultPayload(_TypedPayloadBase):
    """Typed payload for phase/scalar result payloads.

    Schema: ``arnold.workflow.ledger.result_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.RESULT_V1.value


@dataclass(frozen=True)
class VerdictPayload(_TypedPayloadBase):
    """Typed payload for semantic-health verdicts and audit judgments.

    Schema: ``arnold.workflow.ledger.verdict_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.VERDICT_V1.value


@dataclass(frozen=True)
class StateDeltaPayload(_TypedPayloadBase):
    """Typed payload for expected/observed state deltas for a boundary.

    Schema: ``arnold.workflow.ledger.state_delta_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.STATE_DELTA_V1.value


@dataclass(frozen=True)
class ArtifactPayload(_TypedPayloadBase):
    """Typed payload for artifact handoff and promotion payloads.

    Schema: ``arnold.workflow.ledger.artifact_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.ARTIFACT_V1.value


@dataclass(frozen=True)
class CheckpointPayload(_TypedPayloadBase):
    """Typed payload for resume anchors and in-progress witnesses.

    Schema: ``arnold.workflow.ledger.checkpoint_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.CHECKPOINT_V1.value


@dataclass(frozen=True)
class AuthorityPayload(_TypedPayloadBase):
    """Typed payload for authority decisions, grants, and transition intents.

    Schema: ``arnold.workflow.ledger.authority_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.AUTHORITY_V1.value


@dataclass(frozen=True)
class ExternalEffectPayload(_TypedPayloadBase):
    """Typed payload for pre-effect intent and outcome evidence.

    Schema: ``arnold.workflow.ledger.external_effect_payload.v1``
    """

    schema_version: str = PayloadSchemaVersion.EXTERNAL_EFFECT_V1.value


# ── Identity ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AttemptIdentity:
    """Immutable identity for a single execution attempt.

    This is the composite key that uniquely identifies one attempt within
    a workflow run. The graph_revision pins the exact topology/manifest
    revision under which this attempt was dispatched.
    """

    workflow_id: str
    run_id: str
    graph_revision: str
    step_id: str | None = None
    boundary_id: str | None = None
    invocation_id: str | None = None
    attempt_ordinal: int = 1
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise ValueError("AttemptIdentity.workflow_id must be non-empty")
        if not self.run_id.strip():
            raise ValueError("AttemptIdentity.run_id must be non-empty")
        if not self.graph_revision.strip():
            raise ValueError("AttemptIdentity.graph_revision must be non-empty")
        if self.attempt_ordinal < 1:
            raise ValueError(
                f"AttemptIdentity.attempt_ordinal must be >= 1, "
                f"got {self.attempt_ordinal}"
            )
        if not self.attempt_id.strip():
            raise ValueError("AttemptIdentity.attempt_id must be non-empty")
        # Validate attempt_id is a valid UUID.
        try:
            uuid.UUID(self.attempt_id)
        except (ValueError, AttributeError):
            raise ValueError(
                f"AttemptIdentity.attempt_id must be a valid UUID, "
                f"got {self.attempt_id!r}"
            )

    @property
    def is_boundary_scoped(self) -> bool:
        """True when this attempt is scoped to a specific boundary."""
        return self.boundary_id is not None and self.boundary_id.strip() != ""

    @property
    def is_step_scoped(self) -> bool:
        """True when this attempt is scoped to a specific step."""
        return self.step_id is not None and self.step_id.strip() != ""

    @property
    def composite_key(self) -> str:
        """Return a stable composite key for this attempt identity."""
        parts = [
            self.workflow_id,
            self.run_id,
            self.graph_revision,
            str(self.attempt_ordinal),
            self.attempt_id,
        ]
        raw = "|".join(parts)
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "graph_revision": self.graph_revision,
            "attempt_ordinal": self.attempt_ordinal,
            "attempt_id": self.attempt_id,
        }
        if self.step_id is not None:
            payload["step_id"] = self.step_id
        if self.boundary_id is not None:
            payload["boundary_id"] = self.boundary_id
        if self.invocation_id is not None:
            payload["invocation_id"] = self.invocation_id
        return payload


# ── Provenance ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AttemptProvenance:
    """Parent/causal lineage and actor/tool provenance for an attempt.

    The causal_lineage is an ordered list of ancestor attempt IDs (oldest
    first, direct parent last). The parent_attempt_id is the immediate
    predecessor in the attempt chain (None for the initial attempt).
    """

    parent_attempt_id: str | None = None
    causal_lineage: tuple[str, ...] = ()
    actor_id: str | None = None
    tool_id: str | None = None
    provenance_version: str = "arnold.workflow.attempt_provenance.v1"

    def __post_init__(self) -> None:
        # Validate parent/causal lineage consistency.
        if self.causal_lineage:
            if self.parent_attempt_id is None:
                raise ValueError(
                    "AttemptProvenance.causal_lineage is non-empty but "
                    "parent_attempt_id is None"
                )
            if self.parent_attempt_id != self.causal_lineage[-1]:
                raise ValueError(
                    f"AttemptProvenance.parent_attempt_id "
                    f"{self.parent_attempt_id!r} does not match last entry "
                    f"in causal_lineage {self.causal_lineage[-1]!r}"
                )
        elif self.parent_attempt_id is not None:
            raise ValueError(
                "AttemptProvenance.parent_attempt_id is set but "
                "causal_lineage is empty"
            )

        # Validate all lineage entries.
        for i, ancestor_id in enumerate(self.causal_lineage):
            try:
                uuid.UUID(ancestor_id)
            except (ValueError, AttributeError):
                raise ValueError(
                    f"AttemptProvenance.causal_lineage[{i}] must be a valid "
                    f"UUID, got {ancestor_id!r}"
                )

    @property
    def is_initial_attempt(self) -> bool:
        """True when this is the initial attempt (no parent)."""
        return self.parent_attempt_id is None

    @property
    def lineage_depth(self) -> int:
        """Number of ancestors in the causal lineage."""
        return len(self.causal_lineage)

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "provenance_version": self.provenance_version,
            "lineage_depth": len(self.causal_lineage),
        }
        if self.parent_attempt_id is not None:
            payload["parent_attempt_id"] = self.parent_attempt_id
        if self.causal_lineage:
            payload["causal_lineage"] = list(self.causal_lineage)
        if self.actor_id is not None:
            payload["actor_id"] = self.actor_id
        if self.tool_id is not None:
            payload["tool_id"] = self.tool_id
        return payload


# ── Runtime adapter ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeAdapter:
    """Runtime adapter identity for an execution attempt.

    Pins the adapter kind and version that dispatched this attempt.
    """

    adapter_kind: AdapterKind
    adapter_version: str

    def __post_init__(self) -> None:
        if not self.adapter_version.strip():
            raise ValueError("RuntimeAdapter.adapter_version must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_kind": self.adapter_kind.value,
            "adapter_version": self.adapter_version,
        }


# ── Version anchoring ────────────────────────────────────────────────────


@dataclass(frozen=True)
class VersionSet:
    """Code, config, and template version anchoring for an attempt.

    These pin the exact versions of the code, configuration, and template
    used when the attempt was dispatched. At least one version must be
    provided.
    """

    code_version: str | None = None
    config_version: str | None = None
    template_version: str | None = None

    def __post_init__(self) -> None:
        if not any(
            [
                self.code_version is not None and self.code_version.strip(),
                self.config_version is not None and self.config_version.strip(),
                self.template_version is not None and self.template_version.strip(),
            ]
        ):
            raise ValueError(
                "VersionSet must have at least one of code_version, "
                "config_version, or template_version"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.code_version is not None:
            payload["code_version"] = self.code_version
        if self.config_version is not None:
            payload["config_version"] = self.config_version
        if self.template_version is not None:
            payload["template_version"] = self.template_version
        return payload


# ── Grant / decision references ──────────────────────────────────────────


@dataclass(frozen=True)
class GrantRef:
    """Reference to a Run Authority grant and optional decision.

    Every attempt must reference the capability grant under which it was
    dispatched. A decision may be recorded when authority is exercised.
    """

    grant_id: str
    decision_id: str | None = None

    def __post_init__(self) -> None:
        if not self.grant_id.strip():
            raise ValueError("GrantRef.grant_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"grant_id": self.grant_id}
        if self.decision_id is not None:
            payload["decision_id"] = self.decision_id
        return payload


# ── Ledger position ──────────────────────────────────────────────────────


@dataclass(frozen=True, order=True)
class LedgerPosition:
    """Durable append position in the attempt's ordered event stream.

    Each event in an attempt stream has a monotonic sequence number and a
    durable append position. The causal_predecessor_sequence links to the
    immediately preceding event in the same attempt (0 for the first event).
    """

    sequence: int
    append_position: int
    causal_predecessor_sequence: int = 0

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError(
                f"LedgerPosition.sequence must be >= 1, got {self.sequence}"
            )
        if self.append_position < 0:
            raise ValueError(
                f"LedgerPosition.append_position must be >= 0, "
                f"got {self.append_position}"
            )
        if self.causal_predecessor_sequence < 0:
            raise ValueError(
                f"LedgerPosition.causal_predecessor_sequence must be >= 0, "
                f"got {self.causal_predecessor_sequence}"
            )
        if self.causal_predecessor_sequence >= self.sequence:
            raise ValueError(
                f"LedgerPosition.causal_predecessor_sequence "
                f"({self.causal_predecessor_sequence}) must be < sequence "
                f"({self.sequence})"
            )

    @property
    def is_first_event(self) -> bool:
        """True when this is the first event in the attempt stream."""
        return self.causal_predecessor_sequence == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "append_position": self.append_position,
            "causal_predecessor_sequence": self.causal_predecessor_sequence,
        }


# ── Ledger event ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LedgerEvent:
    """A single event in an execution attempt's ordered ledger stream.

    Every event carries an idempotency key, immutable identity, provenance,
    version anchoring, grant reference, monotonic position, and dual
    timestamps. An event without an idempotency key cannot be safely
    retried.

    The payload may be:
    - ``None`` for events that carry no additional data.
    - A ``dict`` for inline small payloads (subject to size policy).
    - A ``DurableRef`` for large or sensitive payloads.

    Clocks alone never establish ordering — the sequence and causal
    predecessor are authoritative.
    """

    idempotency_key: str
    event_type: AttemptEventType
    identity: AttemptIdentity
    provenance: AttemptProvenance
    adapter: RuntimeAdapter
    versions: VersionSet
    grant_ref: GrantRef
    sequence: int
    causal_predecessor_sequence: int
    append_position: int
    occurred_at: str
    observed_at: str
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE
    outcome: AttemptOutcome | None = None
    payload: dict[str, Any] | DurableRef | None = None
    payload_policy_ref: str | None = None
    event_schema_version: str = LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Idempotency key must be non-empty.
        if not self.idempotency_key.strip():
            raise ValueError("LedgerEvent.idempotency_key must be non-empty")

        # Validate enums.
        object.__setattr__(
            self, "event_type", AttemptEventType(self.event_type)
        )
        object.__setattr__(
            self, "adapter", RuntimeAdapter(
                AdapterKind(self.adapter.adapter_kind),
                self.adapter.adapter_version,
            )
            if not isinstance(self.adapter, RuntimeAdapter)
            else self.adapter
        )
        object.__setattr__(
            self, "persistence_status",
            PersistenceStatus(self.persistence_status),
        )
        if self.outcome is not None:
            object.__setattr__(self, "outcome", AttemptOutcome(self.outcome))

        # Validate sequence ordering.
        if self.sequence < 1:
            raise ValueError(
                f"LedgerEvent.sequence must be >= 1, got {self.sequence}"
            )
        if self.causal_predecessor_sequence < 0:
            raise ValueError(
                f"LedgerEvent.causal_predecessor_sequence must be >= 0, "
                f"got {self.causal_predecessor_sequence}"
            )
        if self.causal_predecessor_sequence >= self.sequence:
            raise ValueError(
                f"LedgerEvent.causal_predecessor_sequence "
                f"({self.causal_predecessor_sequence}) must be < sequence "
                f"({self.sequence})"
            )
        if self.append_position < 0:
            raise ValueError(
                f"LedgerEvent.append_position must be >= 0, "
                f"got {self.append_position}"
            )

        # Validate timestamps are non-empty.
        if not self.occurred_at.strip():
            raise ValueError("LedgerEvent.occurred_at must be non-empty")
        if not self.observed_at.strip():
            raise ValueError("LedgerEvent.observed_at must be non-empty")

        # Outcome constraint: terminal event types should have an outcome.
        if (
            self.event_type in _TERMINAL_EVENT_TYPES
            and self.persistence_status == PersistenceStatus.DURABLE
            and self.outcome is None
        ):
            raise ValueError(
                f"LedgerEvent with terminal event_type "
                f"{self.event_type.value} must have an outcome when "
                f"persistence_status is durable"
            )

        # Persistence-failed events must have persistence_failed or
        # indeterminate status.
        if self.event_type == AttemptEventType.PERSISTENCE_FAILED:
            if self.persistence_status not in (
                PersistenceStatus.PERSISTENCE_FAILED,
                PersistenceStatus.INDETERMINATE,
            ):
                raise ValueError(
                    f"LedgerEvent with event_type persistence_failed must "
                    f"have persistence_status of persistence_failed or "
                    f"indeterminate, got {self.persistence_status.value}"
                )

        # External effect intent must have a payload with the effect ref.
        if self.event_type == AttemptEventType.EXTERNAL_EFFECT_INTENT:
            if self.payload is None and self.payload_policy_ref is None:
                raise ValueError(
                    "LedgerEvent with event_type external_effect_intent "
                    "must have a payload or payload_policy_ref"
                )

    @property
    def position(self) -> LedgerPosition:
        """Return the ledger position for this event."""
        return LedgerPosition(
            sequence=self.sequence,
            append_position=self.append_position,
            causal_predecessor_sequence=self.causal_predecessor_sequence,
        )

    @property
    def is_first_event(self) -> bool:
        """True when this is the first event in the attempt stream."""
        return self.causal_predecessor_sequence == 0

    @property
    def is_terminal(self) -> bool:
        """True when this event represents a terminal attempt state."""
        return self.event_type in _TERMINAL_EVENT_TYPES

    @property
    def is_persistence_compromised(self) -> bool:
        """True when persistence has failed or is indeterminate."""
        return self.persistence_status in (
            PersistenceStatus.PERSISTENCE_FAILED,
            PersistenceStatus.INDETERMINATE,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "idempotency_key": self.idempotency_key,
            "event_type": self.event_type.value,
            "event_schema_version": self.event_schema_version,
            "identity": self.identity.to_dict(),
            "provenance": self.provenance.to_dict(),
            "adapter": self.adapter.to_dict(),
            "versions": self.versions.to_dict(),
            "grant_ref": self.grant_ref.to_dict(),
            "sequence": self.sequence,
            "causal_predecessor_sequence": self.causal_predecessor_sequence,
            "append_position": self.append_position,
            "occurred_at": self.occurred_at,
            "observed_at": self.observed_at,
            "persistence_status": self.persistence_status.value,
        }
        if self.outcome is not None:
            payload["outcome"] = self.outcome.value
        if self.payload is not None:
            if isinstance(self.payload, DurableRef):
                payload["payload"] = self.payload.to_dict()
            else:
                payload["payload"] = self.payload
        if self.payload_policy_ref is not None:
            payload["payload_policy_ref"] = self.payload_policy_ref
        return payload


# ── Persistence-failure diagnostic ───────────────────────────────────────


class PersistenceFailureMode(StrEnum):
    """Failure modes for persistence operations in the ledger."""

    WRITE_FAILED = "write_failed"
    STORE_UNAVAILABLE = "store_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    PARTIAL_WRITE = "partial_write"
    UNKNOWN = "unknown"


class ReconciliationOutcome(StrEnum):
    """Outcomes of reconciliation attempts after persistence failure."""

    RECOVERED = "recovered"
    PARTIALLY_RECOVERED = "partially_recovered"
    UNRECOVERABLE = "unrecoverable"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class PersistenceFailureDiagnostic:
    """Diagnostic captured when a ledger persistence operation fails.

    This is recorded alongside (or within) a ``persistence_failed`` event.
    It captures the failure mode, recovery evidence, quarantined authority
    advance status, and the observed error.

    The ``recovery_evidence_ref`` is a durable reference to spool/outbox
    evidence that MAY allow the runtime to recover. If ``None``, no
    recovery evidence was preserved.
    """

    failure_mode: PersistenceFailureMode
    target_event_sequence: int
    observed_error: str
    recovery_evidence_ref: DurableRef | None = None
    quarantined_authority_advance: bool = False
    quarantine_reason: str | None = None
    diagnostic_schema_version: str = (
        "arnold.workflow.ledger.persistence_failure_diagnostic.v1"
    )

    def __post_init__(self) -> None:
        if self.target_event_sequence < 1:
            raise ValueError(
                "PersistenceFailureDiagnostic.target_event_sequence "
                f"must be >= 1, got {self.target_event_sequence}"
            )
        if not self.observed_error.strip():
            raise ValueError(
                "PersistenceFailureDiagnostic.observed_error must be non-empty"
            )
        if self.quarantined_authority_advance and (
            self.quarantine_reason is None
            or not self.quarantine_reason.strip()
        ):
            raise ValueError(
                "PersistenceFailureDiagnostic.quarantine_reason must be set "
                "when quarantined_authority_advance is True"
            )

    @property
    def has_recovery_evidence(self) -> bool:
        """True when recovery evidence (spool/outbox) is available."""
        return self.recovery_evidence_ref is not None

    @property
    def is_recoverable(self) -> bool:
        """True when the failure mode suggests recovery is possible."""
        return self.failure_mode in (
            PersistenceFailureMode.WRITE_FAILED,
            PersistenceFailureMode.STORE_UNAVAILABLE,
            PersistenceFailureMode.PARTIAL_WRITE,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "failure_mode": self.failure_mode.value,
            "target_event_sequence": self.target_event_sequence,
            "observed_error": self.observed_error,
            "quarantined_authority_advance": self.quarantined_authority_advance,
            "diagnostic_schema_version": self.diagnostic_schema_version,
        }
        if self.recovery_evidence_ref is not None:
            payload["recovery_evidence_ref"] = (
                self.recovery_evidence_ref.to_dict()
            )
        if self.quarantine_reason is not None:
            payload["quarantine_reason"] = self.quarantine_reason
        return payload


# ── Reconciliation diagnostic ───────────────────────────────────────────


@dataclass(frozen=True)
class ReconciliationDiagnostic:
    """Diagnostic captured when a persistence failure is reconciled.

    This is recorded alongside (or within) a ``reconciliation`` event.
    It references the failed event, describes the reconciliation outcome,
    and captures recovered evidence references and explicit authority
    disposition.

    The ``reconciled_event_sequence`` identifies the persistence_failed
    event that this reconciliation addresses. ``recovered_evidence_refs``
    lists durable references to evidence recovered during reconciliation.
    """

    reconciled_event_sequence: int
    outcome: ReconciliationOutcome
    outcome_detail: str
    recovered_evidence_refs: tuple[DurableRef, ...] = ()
    authority_disposition: str | None = None
    diagnostic_schema_version: str = (
        "arnold.workflow.ledger.reconciliation_diagnostic.v1"
    )

    def __post_init__(self) -> None:
        if self.reconciled_event_sequence < 1:
            raise ValueError(
                "ReconciliationDiagnostic.reconciled_event_sequence "
                f"must be >= 1, got {self.reconciled_event_sequence}"
            )
        if not self.outcome_detail.strip():
            raise ValueError(
                "ReconciliationDiagnostic.outcome_detail must be non-empty"
            )

    @property
    def is_fully_recovered(self) -> bool:
        """True when reconciliation fully recovered the failed event."""
        return self.outcome == ReconciliationOutcome.RECOVERED

    @property
    def has_recovered_evidence(self) -> bool:
        """True when one or more evidence refs were recovered."""
        return len(self.recovered_evidence_refs) > 0

    @property
    def requires_intervention(self) -> bool:
        """True when manual intervention is required."""
        return self.outcome in (
            ReconciliationOutcome.REQUIRES_MANUAL_INTERVENTION,
            ReconciliationOutcome.UNRECOVERABLE,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "reconciled_event_sequence": self.reconciled_event_sequence,
            "outcome": self.outcome.value,
            "outcome_detail": self.outcome_detail,
            "diagnostic_schema_version": self.diagnostic_schema_version,
        }
        if self.recovered_evidence_refs:
            payload["recovered_evidence_refs"] = [
                ref.to_dict() for ref in self.recovered_evidence_refs
            ]
        if self.authority_disposition is not None:
            payload["authority_disposition"] = self.authority_disposition
        return payload


# ── ExecutionAttemptLedger ────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutionAttemptLedger:
    """Ordered, append-only record of what a supported runtime attempted.

    This is the container for one attempt's complete event stream. Events
    are stored in append order and must form a valid causal chain.

    The ledger is schema-only: it validates event identity, ordering,
    provenance, and append-position invariants without performing any I/O
    or mutation.
    """

    attempt_id: str
    events: tuple[LedgerEvent, ...] = ()
    ledger_schema_version: str = LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.attempt_id.strip():
            raise ValueError(
                "ExecutionAttemptLedger.attempt_id must be non-empty"
            )
        # Validate that all events reference this attempt_id.
        for i, event in enumerate(self.events):
            if event.identity.attempt_id != self.attempt_id:
                raise ValueError(
                    f"ExecutionAttemptLedger.events[{i}] has attempt_id "
                    f"{event.identity.attempt_id!r} but ledger has "
                    f"{self.attempt_id!r}"
                )

    @property
    def event_count(self) -> int:
        """Total number of events in the ledger."""
        return len(self.events)

    @property
    def first_event(self) -> LedgerEvent | None:
        """The first event in the attempt stream, or None if empty."""
        return self.events[0] if self.events else None

    @property
    def last_event(self) -> LedgerEvent | None:
        """The last event in the attempt stream, or None if empty."""
        return self.events[-1] if self.events else None

    @property
    def is_empty(self) -> bool:
        """True when the ledger has no events."""
        return len(self.events) == 0

    @property
    def terminal_event(self) -> LedgerEvent | None:
        """The terminal event if one exists, or None."""
        for event in reversed(self.events):
            if event.is_terminal:
                return event
        return None

    def event_by_sequence(self, sequence: int) -> LedgerEvent | None:
        """Return the event at the given sequence number, or None."""
        for event in self.events:
            if event.sequence == sequence:
                return event
        return None

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        return {
            "attempt_id": self.attempt_id,
            "ledger_schema_version": self.ledger_schema_version,
            "event_count": len(self.events),
            "events": [event.to_dict() for event in self.events],
        }


# ── Validators ────────────────────────────────────────────────────────────


def validate_ledger_event_identity(event: LedgerEvent) -> list[str]:
    """Validate the identity fields of a ledger event.

    Checks that workflow_id, run_id, graph_revision, attempt_ordinal,
    and attempt_id are populated and well-formed.
    """
    issues: list[str] = []

    identity = event.identity
    if not identity.workflow_id.strip():
        issues.append("LedgerEvent.identity.workflow_id is empty")
    if not identity.run_id.strip():
        issues.append("LedgerEvent.identity.run_id is empty")
    if not identity.graph_revision.strip():
        issues.append("LedgerEvent.identity.graph_revision is empty")
    if identity.attempt_ordinal < 1:
        issues.append(
            f"LedgerEvent.identity.attempt_ordinal must be >= 1, "
            f"got {identity.attempt_ordinal}"
        )
    if not identity.attempt_id.strip():
        issues.append("LedgerEvent.identity.attempt_id is empty")

    # Validate attempt_id is a valid UUID.
    try:
        uuid.UUID(identity.attempt_id)
    except (ValueError, AttributeError):
        issues.append(
            f"LedgerEvent.identity.attempt_id {identity.attempt_id!r} "
            f"is not a valid UUID"
        )

    return issues


def validate_ledger_event_ordering(
    events: Sequence[LedgerEvent],
) -> list[str]:
    """Validate the monotonic ordering and causal chain of ledger events.

    Checks:
    - Sequence numbers are strictly monotonic.
    - Append positions are strictly monotonic.
    - Causal predecessor links form a valid chain.
    - No duplicate sequence numbers.
    - The first event has causal_predecessor_sequence == 0.
    - Lifecycle precedence constraints are satisfied.
    """
    issues: list[str] = []

    if not events:
        return issues

    seen_sequences: set[int] = set()
    prev_sequence: int = 0
    prev_append: int = -1
    seen_event_types: set[AttemptEventType] = set()

    for i, event in enumerate(events):
        # Duplicate sequence check.
        if event.sequence in seen_sequences:
            issues.append(
                f"Duplicate sequence number {event.sequence} at event {i}"
            )
        seen_sequences.add(event.sequence)

        # Monotonic sequence.
        if event.sequence <= prev_sequence:
            issues.append(
                f"Sequence not strictly monotonic: event {i} has sequence "
                f"{event.sequence} after {prev_sequence}"
            )
        prev_sequence = event.sequence

        # Monotonic append position.
        if event.append_position <= prev_append:
            issues.append(
                f"Append position not strictly monotonic: event {i} has "
                f"append_position {event.append_position} after "
                f"{prev_append}"
            )
        prev_append = event.append_position

        # First event must have causal_predecessor_sequence == 0.
        if i == 0 and event.causal_predecessor_sequence != 0:
            issues.append(
                f"First event must have causal_predecessor_sequence == 0, "
                f"got {event.causal_predecessor_sequence}"
            )

        # Causal predecessor must reference a real earlier event.
        if event.causal_predecessor_sequence > 0:
            found = any(
                e.sequence == event.causal_predecessor_sequence
                for e in events[:i]
            )
            if not found:
                issues.append(
                    f"Event {i} references causal_predecessor_sequence "
                    f"{event.causal_predecessor_sequence} which does not "
                    f"exist in earlier events"
                )

        # Lifecycle precedence.
        required_predecessors = _LIFECYCLE_PRECEDENCE.get(event.event_type)
        if required_predecessors:
            missing = required_predecessors - seen_event_types
            if missing:
                missing_str = ", ".join(sorted(m.value for m in missing))
                issues.append(
                    f"Event {i} ({event.event_type.value}) requires "
                    f"preceding event types: {missing_str}"
                )

        seen_event_types.add(event.event_type)

    return issues


def validate_ledger_event_provenance(event: LedgerEvent) -> list[str]:
    """Validate the provenance fields of a ledger event.

    Checks:
    - Parent/causal lineage consistency.
    - Lineage entries are valid UUIDs when present.
    - Actor/tool provenance is documented for non-initial attempts.
    """
    issues: list[str] = []

    provenance = event.provenance

    # Parent/lineage consistency.
    if provenance.causal_lineage:
        if provenance.parent_attempt_id is None:
            issues.append(
                "Provenance has causal_lineage but parent_attempt_id is None"
            )
        elif provenance.parent_attempt_id != provenance.causal_lineage[-1]:
            issues.append(
                f"Provenance parent_attempt_id "
                f"{provenance.parent_attempt_id!r} does not match last "
                f"lineage entry {provenance.causal_lineage[-1]!r}"
            )
    elif provenance.parent_attempt_id is not None:
        issues.append(
            "Provenance has parent_attempt_id but causal_lineage is empty"
        )

    # Validate lineage UUIDs.
    for j, ancestor_id in enumerate(provenance.causal_lineage):
        try:
            uuid.UUID(ancestor_id)
        except (ValueError, AttributeError):
            issues.append(
                f"Provenance.causal_lineage[{j}] {ancestor_id!r} is not "
                f"a valid UUID"
            )

    return issues


def validate_ledger_event_grant(event: LedgerEvent) -> list[str]:
    """Validate the grant/decision reference of a ledger event.

    Every event must have a non-empty grant_id. Decision references are
    optional but must be non-empty if present.
    """
    issues: list[str] = []

    if not event.grant_ref.grant_id.strip():
        issues.append("LedgerEvent.grant_ref.grant_id is empty")

    if (
        event.grant_ref.decision_id is not None
        and not event.grant_ref.decision_id.strip()
    ):
        issues.append(
            "LedgerEvent.grant_ref.decision_id is present but empty"
        )

    return issues


def validate_ledger_event_timestamps(event: LedgerEvent) -> list[str]:
    """Validate the occurred_at and observed_at timestamps.

    Both must be non-empty. Clocks alone never establish ordering — these
    are metadata, not causal anchors.
    """
    issues: list[str] = []

    if not event.occurred_at.strip():
        issues.append("LedgerEvent.occurred_at is empty")
    if not event.observed_at.strip():
        issues.append("LedgerEvent.observed_at is empty")

    return issues


def validate_ledger_event_adapter(event: LedgerEvent) -> list[str]:
    """Validate the runtime adapter reference of a ledger event."""
    issues: list[str] = []

    if not event.adapter.adapter_version.strip():
        issues.append("LedgerEvent.adapter.adapter_version is empty")

    # Adapter kind must be a valid enum value.
    try:
        AdapterKind(event.adapter.adapter_kind)
    except ValueError:
        issues.append(
            f"LedgerEvent.adapter.adapter_kind "
            f"{event.adapter.adapter_kind!r} is not a valid AdapterKind"
        )

    return issues


def validate_ledger_event_idempotency(event: LedgerEvent) -> list[str]:
    """Validate the idempotency key of a ledger event."""
    issues: list[str] = []

    if not event.idempotency_key.strip():
        issues.append("LedgerEvent.idempotency_key is empty")

    return issues


def validate_ledger_event(event: LedgerEvent) -> list[str]:
    """Run all per-event validators and return consolidated issues."""
    issues: list[str] = []
    issues.extend(validate_ledger_event_identity(event))
    issues.extend(validate_ledger_event_provenance(event))
    issues.extend(validate_ledger_event_grant(event))
    issues.extend(validate_ledger_event_timestamps(event))
    issues.extend(validate_ledger_event_adapter(event))
    issues.extend(validate_ledger_event_idempotency(event))
    return issues


def validate_ledger(ledger: ExecutionAttemptLedger) -> list[str]:
    """Validate a complete execution attempt ledger.

    Runs per-event validation on every event and cross-event ordering
    validation on the full event stream.
    """
    issues: list[str] = []

    # Per-event validation.
    for i, event in enumerate(ledger.events):
        event_issues = validate_ledger_event(event)
        for issue in event_issues:
            issues.append(f"Event {i}: {issue}")

    # Cross-event ordering validation.
    ordering_issues = validate_ledger_event_ordering(ledger.events)
    issues.extend(ordering_issues)

    # Validate that all events' identity.attempt_id matches the ledger.
    for i, event in enumerate(ledger.events):
        if event.identity.attempt_id != ledger.attempt_id:
            issues.append(
                f"Event {i} attempt_id {event.identity.attempt_id!r} "
                f"does not match ledger attempt_id {ledger.attempt_id!r}"
            )

    return issues


# ── Public API ────────────────────────────────────────────────────────────

__all__ = [
    "AdapterKind",
    "ArtifactPayload",
    "AttemptEventType",
    "AttemptIdentity",
    "AttemptOutcome",
    "AttemptProvenance",
    "AuthorityPayload",
    "CheckpointPayload",
    "ExecutionAttemptLedger",
    "ExternalEffectPayload",
    "GrantRef",
    "InputPayload",
    "LEDGER_SCHEMA_VERSION",
    "LedgerEvent",
    "LedgerPosition",
    "OutputPayload",
    "PayloadSchemaVersion",
    "PersistenceFailureDiagnostic",
    "PersistenceFailureMode",
    "PersistenceStatus",
    "ReconciliationDiagnostic",
    "ReconciliationOutcome",
    "ResultPayload",
    "RuntimeAdapter",
    "StateDeltaPayload",
    "VerdictPayload",
    "VersionSet",
    "validate_ledger",
    "validate_ledger_event",
    "validate_ledger_event_adapter",
    "validate_ledger_event_grant",
    "validate_ledger_event_identity",
    "validate_ledger_event_idempotency",
    "validate_ledger_event_ordering",
    "validate_ledger_event_provenance",
    "validate_ledger_event_timestamps",
]
