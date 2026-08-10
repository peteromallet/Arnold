# Workflow Boundary Contracts integration annex

This annex is binding for all five critique-ledger sprints. It distinguishes the
landed WBC substrate from proposed critique-ledger behavior and prevents a
second authority or execution ledger.

## Boundary ownership

| Boundary | Canonical owner | Critique-ledger role |
|---|---|---|
| Supported-runtime attempt/effect evidence, payload references, receipts, persistence, retention/redaction, and compatibility boundaries | WBC kernel execution-attempt ledger and payload policy | Reference exact attempt/event/payload identities; never rewrite or re-authorize them. |
| Critic occurrences, semantic finding identities, disposition/reopen events, bounded history briefings, and derived projections | Critique ledger | Append immutable/domain records over WBC custody; projections remain rebuildable and non-authoritative. |
| Critic selection | Existing Megaplan evaluator | Select critics and optionally accept curator proposals; the ledger does not take routing authority. |
| Flag lifecycle, revision action, gate verdict, finalize/execute admission | Existing Megaplan flag/revise/gate/finalize owners | Consume ledger projections and bind exact revisions; retain current decision authority. |
| Session/project knowledge | Session Knowledge Compiler | Optional later projection/retention consumer only; not the first implementation's finding authority. |

CL1 must produce one source-to-owner matrix with one mutating writer for each
artifact. Any overlap or unknown writer blocks CL2.

## Schemas and envelopes

Minimum versioned logical records:

1. `CritiqueOccurrenceEnvelope`: immutable plan/run/iteration/phase/attempt,
   producer/domain/instructions/model, context mode (`blind|history_aware`),
   plan/brief/repo/runtime hashes, evidence scope, raw artifact/durable reference,
   finding assertions, parse status, and explicit `no_additional_findings`.
2. `FindingReconciliationEvent`: prior ledger revision, occurrence refs,
   evaluator/curator attempt, semantic finding ID, relationship
   (`new|duplicate|refinement|regression|reopened|split|merged|unrelated`),
   domains, rationale, confidence/unknown, and evidence refs.
3. `FindingDispositionEvent`: disposition, severity kept orthogonal, rationale,
   evidence/evidence limits, revision action or non-action, remaining questions,
   accountable scope/owner where applicable, and reopen predicates.
4. `DomainBriefingEnvelope`: selected domain, evaluator verdict, current/prior
   instructions, included/excluded finding refs with reasons, cross-domain refs,
   budget/overflow decision, exact input-set hash, ledger revision, and plan/
   evidence freshness vector.
5. `LedgerRevisionManifest`: ordered included event refs, schema/version vector,
   previous revision hash, completeness map, build/result hash, and WBC receipt
   refs. Projections are rebuildable and never substitute for these inputs.

Use WBC inline/reference policy rather than inventing storage rules. Free-form
prompts/completions and private evidence use governed durable refs; a hash
without retrievable retained bytes is insufficient. Schema evolution is
additive and versioned. Unknown fields are preserved or rejected according to
the declared compatibility profile, never silently dropped.

## Identity, custody, completeness, and freshness

- Keep current content-derived producer occurrence identity and producer-local
  IDs as immutable provenance. Add a separately named evaluator-assigned
  semantic finding identity; never pretend they are the same key.
- Bind every event to workflow/run/plan/iteration/critic attempt plus WBC attempt
  and durable append position where available. Retries get distinct attempt and
  occurrence IDs; idempotent replay of the same accepted event appends once.
- Every selected/failed producer has an outcome row. Every parseable occurrence
  has exactly one reconciliation row for the ledger revision. Missing, duplicate,
  stale, or unmapped rows block a history-aware briefing and truthful gate.
- Freshness vector includes exact plan/brief hashes, repository/runtime revision,
  relevant evidence hashes, evaluator verdict, prior ledger revision, selected
  domain instructions, and briefing input-set hash.
- Any relevant input change rebuilds the briefing and evaluates reopen
  predicates. Clock age is diagnostic only; content/causal identity decides
  freshness.
- Model semantic judgments may be revised only by later append-only events.
  Deterministic validators enforce shape, coverage, hashes, ordering, and
  evidence availability—not semantic sameness.

## Disposition migration

The first schema must represent `acted_on/addressed_pending_verification`,
`ignored/wont_fix`, `deferred`, `rejected_invalid|rejected_out_of_scope`,
`duplicate`, `accepted_risk|accepted_tradeoff`, `unknown|uncertain`, and
`resolved_verified`. Existing `open`, `addressed`, and `verified` flag states and
gate settled decisions are compatibility inputs, not a complete replacement.

Historical critique artifacts are read-only. The one-time migration creates explicit
`legacy_unknown` occurrences/projections when semantic relationships,
instructions, or reopen conditions were never recorded. It must not backfill
invented duplicates or resolutions. The target reader accepts the cutover
schema, rejects unsupported future/corrupt inputs, and never silently drops
fields. Old readers remain only as pre-cutover recovery material and are
retired after CL5 verifies the coordinated switch.

## Persistence and replay

- Append attempt/occurrence evidence through the landed WBC ledger/object-store
  interfaces when they satisfy CL1's contract; keep plan-local critique artifacts
  as raw/import/recovery evidence, not a parallel live view after cutover.
- Persist start before dispatch. Commit accepted producer result, occurrence
  envelope, durable payload ref, and receipt through a transaction or durable
  prepare/outbox protocol. Terminal persistence failure is
  `persistence_failed|indeterminate`, never clean success.
- Reconciliation and disposition events append after all selected attempts are
  terminal or explicitly unavailable. The ledger manifest publishes only after
  coverage validation; projections publish from that accepted revision.
- Replay is read-only and deterministic for retained internal records. It
  rebuilds cumulative/domain projections and comparison reports without issuing
  critic calls, external effects, lifecycle transitions, or gate decisions.
- Content redaction/expiry leaves governed tombstones with identity, reason,
  authority, and availability. Replay surfaces unavailable evidence as unknown
  and reevaluates affected closure/disposition confidence.

## Evaluator routing and role-flow envelopes

The evaluator consumes the current plan/brief/repository vector, last plan diff,
prior gate rationale, accepted ledger revision, domain catalog, mandatory floors,
budget, and WBC-backed evidence availability. It emits selected/skipped domains,
why, triggering findings/surfaces, blind/history-aware mode, instructions,
evidence targets, budgets, and the expected briefing revision.

Blind outputs are occurrences only; they cannot directly drive revise or gate.
The mandatory reconciliation step consumes all blind/history-aware attempts and
the prior ledger. The reviser consumes the accepted cumulative projection and
returns one structured action/non-action per requested finding. The gate consumes
the same accepted revision plus revision actions and verification results, and
must distinguish no novelty, no blocker, no known finding, and no adjacent text
match. Every handoff gets a declared WBC boundary receipt and schema validation.

## Failure behavior

Fail closed before critic dispatch on stale/unavailable required briefing inputs,
schema incompatibility, missing ownership, or failed start persistence. A blind
pass may still run only when explicitly selected and its WBC start contract is
valid; it cannot conceal the blocked history-aware pass.

Fail closed before revise/gate on dropped attempts, unmapped occurrences,
incomplete disposition coverage, stale evidence, unsupported closure, silent
budget truncation, projection/replay mismatch, or terminal persistence failure.
Do not downgrade these to `no_additional_findings`. Semantic uncertainty becomes
an explicit unknown disposition. During cutover, any integrity failure keeps
admission closed and invokes the single whole-cutover recovery procedure; there
is no partial boundary fallback.

## Minimum integrity evidence

Retain only evidence needed to prove custody and diagnose a failed cutover, with
content-safe identifiers:

- selected/skipped critics and reasons; blind/history-aware counts;
- attempts, parse failures, custody loss, reconciliation coverage, stale or
  rebuilt briefings, overflow/splits, and durable-reference availability;
- new/duplicate/refinement/regression/reopen/no-additional outcomes;
- disposition counts/age/evidence coverage and unsupported-closure rejects;
- prompt/context tokens and model/profile/schema/source vectors; and
- cutover revision, import/backup/restore hashes, smoke verdicts, and retired
  writer/reader inventory.

These records are projections from immutable evidence and never authorize
progression. No rollout dashboard or long-lived comparison telemetry is required.

## Test strategy

1. Schema/golden tests for every envelope, disposition, relationship, context
   mode, no-additional result, unknown field/version, and tombstone.
2. Property/fault tests for duplicate/out-of-order/partial writes, crash points,
   retries, concurrent attempts, stale inputs, missing objects, truncation, and
   idempotent replay.
3. Existing critique custody, parallel reducer, evaluator validation, flag,
   revise, gate, finalize, WBC ledger/evidence/compatibility/conformance tests.
4. Producer-driven boundary fixtures for evaluator → critic → reconciler →
   reviser → gate in healthy, unavailable, malformed, and recovery cases.
5. M6 corpus oracle tests, including the five-occurrence blocked-handoff family,
   accepted replay limitation, failed producer, and exact-text false zero.
6. One-time legacy import, target-version, future/corrupt rejection, redacted,
   unavailable, backup, and isolated whole-cutover restore fixtures.
7. Negative authority tests proving replay/evaluator/ledger code performs
   zero lifecycle, gate, queue, Git/provider, delivery, or external-effect writes.

## Coordinated cutover and bounded recovery

CL5 may cut over only when CL1–CL4 handoffs match the exact source revision,
M6 and full semantic-loop checks pass, WBC receipts and payload references are
complete, and a content-addressed backup plus isolated restore proof exist.
Quiesce admission, account for in-flight attempts, import once, switch every
critique-loop consumer together, run the bounded smoke checks, then retire the
replaced readers/writers/fallbacks.

Occurrence loss, unsupported closure, stale briefing use, schema/receipt or
payload-reference failure, replay mismatch, or false clean custody keeps
admission closed. Recovery restores the complete verified pre-cutover bundle
and prior runtime/config revision, then verifies projection hashes and WBC
receipts before any resume. It preserves append-only failure evidence and never
creates a supported mixed state or component-level rollback path.
