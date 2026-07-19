---
type: decision
date: 2026-07-16
schema: custody-control-plane-actionable-record-decision-v1
status: proposed
owner: custody-control-plane
source_research: ../research/actionable-failure-identity-custody-audit-20260716.md
---

# Canonical actionable-record and claimability contract

## Decision

Adopt a single versioned `ActionableRecordV2` envelope at every boundary that
can cause automated repair, rework, retry, escalation, or a human claim. No
consumer may accept a record as actionable unless the persisted envelope is
self-contained and claimable.

Required fields:

- `schema_version`, `contract_id`, `contract_hash`
- `finding_id`, `finding_version`, `producer_id`, `producer_runtime_revision`
- `action_target_id`, `occurrence_id`, `request_id`
- `run_id`, `session_id`, `subject_id`, `phase_or_step`
- `failure_kind`, `severity`, `actionability`
- non-empty typed `evidence_refs` with immutable digest/cursor and observed-at
- `target_snapshot_hash`, `runtime_identity`, `source_revision`
- `retry_policy_id`, `retry_budget`, `dispatch_intent`
- `causal_parent_ids`, optional predecessor occurrence, provenance envelope
- `created_at` for audit only; timestamps never participate in identity

`action_target_id` is derived from immutable target coordinates and contract
version. `occurrence_id` adds run/session, target snapshot, predicate/evidence
digest, and causal predecessor. `request_id` derives from occurrence and retry
policy. Claim, attempt, and decision identities derive from their canonical
parents plus ordinal/fence, never from free text or time.

## Enforcement

- Producers must call one constructor/validator before persistence.
- Persistence validates schema and recomputes all hashes before returning
  `accepted`.
- `accepted` implies `claimable=true`; otherwise persistence returns a typed
  `quarantined` decision with reasons and telemetry.
- Coalescing is legal only when `occurrence_id` and action target match.
  Cross-session coalescing is forbidden unless an explicit shared-target
  policy and join record names every session.
- Consumers read identity from the record. Current-state lookup only verifies
  freshness or supersession; it never fills missing identity.
- Projections remain rebuildable and non-authoritative. Unknown schema,
  incomplete producer coverage, duplicate identities, or missing evidence are
  `UNKNOWN/INCOHERENT`, not zero or healthy.
- Every accepted claim has a fenced custody epoch and every attempt has exactly
  one terminal decision. Replay is idempotent by semantic decision identity.

## Compatibility

Legacy v1 markers remain read-only. A compatibility reader classifies each as:

- `v1_proven_claimable`: all v2 fields can be derived from immutable evidence
  captured at original write time; emit a content-addressed migration receipt.
- `v1_quarantined_missing_identity`: required identity cannot be proven; never
  synthesize from current mutable state.
- `v1_terminal_read_only`: historical terminal record retained for audit.

There is no `v1_assume_claimable`. Shadow comparison precedes enforcement;
mixed-version consumers prefer v2 and never merge v1/v2 by prose signature.

## Ownership boundary

M6 owns inventory and contract freeze. M6A owns schema/store/migration. M8 owns
producer adoption, including critique/review/execute/watchdog/resident/cloud.
M9 owns projections/telemetry. M10 owns replay/recovery/effects. M11 owns
cross-runtime conformance and legacy-writer retirement. The concrete
workflow-boundary M6 owner implements the original superfixer incident; this
decision does not create a competing repair queue or runtime writer.
