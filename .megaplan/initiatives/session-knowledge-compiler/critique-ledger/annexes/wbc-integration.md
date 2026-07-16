# Workflow Boundary Contracts integration annex

This annex is binding for all six critique-ledger sprints. It distinguishes the
landed WBC substrate from proposed critique-ledger behavior and prevents a
second authority or execution ledger.

## Boundary ownership

| Boundary | Canonical owner | Critique-ledger role |
|---|---|---|
| Supported-runtime attempt/effect start, terminal result, ordering, payload reference, retention/redaction | WBC kernel execution-attempt ledger and payload policy | Reference exact attempt/event/payload identities; never rewrite or re-authorize them. |
| Boundary declaration, evidence/receipt, compatibility, conformance, boundary-semantic mismatch | WBC | Emit/consume declared critique-loop boundary envelopes and map failures to WBC semantic findings without making them critique dispositions. |
| Critic producer output and per-round zero-loss custody | Megaplan critique custody | Extend compatibly with context mode, ledger/briefing inputs, and immutable occurrence references. |
| Critic selection and semantic relationship/disposition judgment | Critique evaluator, optionally assisted by a curator | Produce append-only model judgments; never mutate lifecycle, gate authority, or raw occurrences. |
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

## Disposition compatibility and migration

The first schema must represent `acted_on/addressed_pending_verification`,
`ignored/wont_fix`, `deferred`, `rejected_invalid|rejected_out_of_scope`,
`duplicate`, `accepted_risk|accepted_tradeoff`, `unknown|uncertain`, and
`resolved_verified`. Existing `open`, `addressed`, and `verified` flag states and
gate settled decisions are compatibility inputs, not a complete replacement.

Historical critique artifacts are read-only. Migration creates explicit
`legacy_unknown` occurrences/projections when semantic relationships,
instructions, or reopen conditions were never recorded. It must not backfill
invented duplicates or resolutions. Mixed-version readers must handle old-only,
dual-written, new-only, partial, future-version, corrupted, and rolled-back
runs. Old readers retain their existing artifacts until CL6 proves retirement
criteria; deletion is outside this epic without separate approval.

## Persistence and replay

- Append attempt/occurrence evidence through the landed WBC ledger/object-store
  interfaces when they satisfy CL1's contract; keep plan-local critique artifacts
  as compatibility views and raw evidence.
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
an explicit unknown disposition. Shadow failures leave ordinary runtime behavior
unchanged and emit diagnostics. Canary failures disable ledger consumption and
fall back to the validated legacy path while retaining append-only evidence.

## Observability

Emit per plan/round/domain, with content-safe identifiers:

- selected/skipped critics and reasons; blind/history-aware counts;
- attempts, parse failures, custody loss, reconciliation coverage, stale or
  rebuilt briefings, overflow/splits, and durable-reference availability;
- new/duplicate/refinement/regression/reopen/no-additional outcomes;
- disposition counts/age/evidence coverage and unsupported-closure rejects;
- prompt/context tokens, latency, cost, model/profile/schema/version vectors;
- duplicate revision actions, new-family recall, false merge/closure/reopen
  adjudications, gate outcome deltas, fallback/disable/rollback events.

Metrics are projections from immutable evidence and never authorize progression.
Dashboards must separate current behavior, shadow candidate, and canary behavior.

## Test strategy

1. Schema/golden tests for every envelope, disposition, relationship, context
   mode, no-additional result, unknown field/version, and tombstone.
2. Property/fault tests for duplicate/out-of-order/partial writes, crash points,
   retries, concurrent attempts, stale inputs, missing objects, truncation, and
   idempotent replay.
3. Existing critique custody, parallel reducer, evaluator validation, flag,
   revise, gate, finalize, WBC ledger/evidence/compatibility/conformance tests.
4. Producer-driven boundary fixtures for evaluator → critic → reconciler →
   reviser → gate in healthy, unavailable, malformed, and rollback cases.
5. M6 corpus oracle tests, including the five-occurrence blocked-handoff family,
   accepted replay limitation, failed producer, and exact-text false zero.
6. Mixed-version matrix for legacy-only, dual-write, new-only, downgrade,
   rollback, future-version, redacted, and unavailable evidence.
7. Negative authority tests proving shadow/replay/evaluator/ledger code performs
   zero lifecycle, gate, queue, Git/provider, delivery, or external-effect writes.

## Shadow, canary, rollout, and rollback gates

Shadow is report-only and default-off for ordinary users until CL5. Promotion
to canary requires the acceptance thresholds in `../validation/m6-end-to-end.md`,
zero authority leakage, reviewed false-merge/closure samples, complete WBC
conformance, a rollback rehearsal, and named runtime/product/contract owners.

Canary is allowlisted by new plan/run identity, never by mutable name alone. It
preserves both legacy and candidate inputs/outputs and can disable independently
at selection, briefing, reconciliation, reviser, and gate consumption boundaries.
Automatic rollback triggers include occurrence loss, unsupported closure,
significant-finding suppression, stale briefing use, schema/receipt failure,
novel-recall threshold breach, persistent latency/token budget breach, or gate
behavior divergence outside approved policy.

Rollback disables candidate consumption and restores the last validated legacy
path; it does not delete occurrence/reconciliation evidence or rewrite gate
history. Old reader/artifact retirement, broad enablement, deployment, and
service restart require separate authority after two accepted observation
windows and are not done criteria for this planning chain.
