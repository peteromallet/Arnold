# Decision: Require A Kernel Execution-Attempt Ledger

Date: 2026-07-11

## Decision

Every step and attempt executed by a declared supported workflow runtime writes
one shared, append-only execution-attempt ledger. The ledger is implemented at
the existing workflow kernel and adapter seams. It reuses Run Authority grant,
attempt, claim, decision, and quarantine identity and references Megaplan
Maintenance observations and `TransitionWriter` records; it does not create a
parallel authority kernel, lifecycle writer, queue, status model, or runtime.

The supported set for this epic is `arnold.workflow`, all named Megaplan phase,
reducer, chain/publication, cloud repair/verification, and auditor adapters, and
the pinned `arnold.pipeline.native` runtime adapter used in C6. Manual activity wholly outside those
runtimes, third-party internal execution, and historical read-only runs are out
of scope. External effects initiated by a supported attempt remain in scope.

## Required Record

Each attempt has immutable workflow/run/graph revision, step/boundary,
invocation, attempt ordinal/id, parent/causal lineage, runtime adapter,
code/config/template versions, actor/tool provenance, and prerequisite authority
refs. Events use idempotency keys, per-attempt monotonic sequence, causal refs,
and a durable append position. Required transitions are start, completion,
failure, retry, suspension, resume, and cancellation, plus external-effect
intent/outcome and persistence-failure/reconciliation when applicable.

Inputs, outputs/results, verdicts, state deltas, artifacts, checkpoints, and
external effects are inline only when small and non-sensitive under a versioned
policy. Otherwise the event contains a durable retrievable reference with store
identity/locator, digest, schema/media type, size, encryption/access scope,
privacy class, retention class, and availability state. A hash proves identity
or integrity; without retained retrievable bytes it does not preserve result
data.

Retention, redaction, deletion/legal hold, tenant/workflow isolation, encryption,
least privilege, secret exclusion, and access auditing are schema-governed.
Authorized payload expiry/redaction leaves a causal tombstone and authority/
reason record without exposing removed data.

The concrete backend priority, 16 KiB inline threshold, retention classes,
default-on redaction behavior, and pinned native adapter/version vector are
fixed by `2026-07-11-unattended-execution-defaults.md`; C1 validates them rather
than reopening them for selection.

## Atomicity And Failure Semantics

Attempt start is durable before user code or external effects. Internal result,
state, and terminal publication uses a transaction where possible or a durable
outbox/prepare-commit protocol. External effects require a pre-effect intent and
idempotency/fencing key, followed by a durable outcome or explicit unknown.

Start persistence failure fails closed. Terminal/result persistence failure can
never be reported as success or silently swallowed: it produces a queryable
`persistence_failed` or `indeterminate` condition, blocks authority advance,
retains recoverable spool/outbox evidence where available, and requires explicit
reconciliation.

## Adoption And Acceptance

C1 freezes schemas, support and ownership matrices, migration assignments, and
failure tables. C2 implements and fault-tests the kernel. C3 migrates all named
Megaplan phase/reducer/cloud seams. C4 migrates chain/publication/repair/audit
and external effects. C5 completes schema governance and query/replay/audit
profiles. C6 makes the native adapter mandatory and proves universal coverage.

Temporary C1-C5 exceptions require owner, reason, visible non-conformant status,
and removal milestone. Final acceptance permits no exemption or compatibility-
only path for a supported producer. Machine-generated coverage, fault-injection,
query, replay, audit-export, and cross-runtime conformance artifacts are required.
Production-wide dispatch/autonomy remains a separate operational decision.

## Consequences

- Boundary receipts become views/evidence tied to the ledger rather than
  best-effort post-success decorations.
- Query reconstructs stable ordered causal histories under access policy.
- Replay reconstructs deterministic internal projections from pinned retained
  data; external or sensitive effects use recorded witnesses/fenced dry runs and
  are never implicitly reissued.
- Audit proof includes schema/version vector, ordering, provenance, authority,
  durable-object availability, retention/redaction state, and verifier results.
- Historical compatibility data remains readable but cannot claim supported-
  runtime conformance or authority.
