---
type: brief
slug: m9-rebuildable-projections-and-liveness
title: Rebuildable projections, pure observers, status, and liveness cutover
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M9 — Rebuildable projections and liveness

## Outcome

Cut every status, liveness, watchdog/repair/auditor, chain/publication,
resident, cloud, retention/migration, and operator reader over to exact-version
canonical WBC queries and exact-cursor projections of the Run Authority, WBC, lifecycle,
and Custody source records or coherent evidence adapters. Every
projection is disposable/rebuildable, observers are pure, and uncertainty or
disagreement never becomes running, complete, repairable, or dispatchable.
Join the M8A work events into an honest productive-versus-replayed latency,
token, and cost ledger and expose deterministic auditor reasons.
Scope is no more than two weeks.

## In scope

- Plan/chain/status projections, canonical run-state resolution, CLI status,
  introspect/trace/doctor, status snapshots/formatters, current-target and
  human-blocker selection, watchdog/progress auditor, repair classification,
  PID/tmux/heartbeat correlation, resident/Discord/AgentBox summaries, provider
  observations, wrapper thinning, projection rebuild/lag/drift APIs.
- WBC attempt/boundary query consumers in local/resident/cloud status,
  scheduler and managed-agent completion, chain advancement/finalization/
  publication, watchdog and L1/L2/L3 repair, progress auditor, cancellation/
  resume/recovery, trace/export, and historical/mixed-version adapters.
- Operationalize retention/privacy consumers: expiry and legal-hold scheduling,
  tenant/access enforcement, encrypted reference reads and key/version audit,
  tombstone/deletion projections, migration health and compatibility expiry.
- Separate execution, runner liveness, custody, recovery, capacity,
  publication, delivery, and integrity dimensions.
- Delete and rebuild projections in tests, prove deterministic ordering/digests,
  and prevent display/degraded fallbacks from feeding control decisions.
- Derive plan, chain, cloud, repair, resident, status, and introspection views
  from a coherent declared source-cursor vector. A live active attempt may
  invalidate a stale terminal compatibility label without becoming authority or
  collapsing sibling dimensions.
- Make every positive control path bypass the projection as a bearer token: it
  must reread and validate current Run Authority grant/fence and Custody
  lease/epoch source records, then check required WBC evidence. Projections may
  deny, block, or diagnose from stale/unknown input but cannot positively authorize.
- Join task/batch/attempt/repair identity across queue, session-start, inference,
  tool, validation, retry-wait, compaction, Git, transition, repair, verify, and
  replay time/calls/tokens/dollars, plus accepted-output delta and unavailable
  reason. Preserve legitimate implementation, review, and proof separately.
- Emit deterministic exact-evidence reasons for consecutive normalized blocks,
  signature drift, unclosed custody, index mismatch, detection-SLO breach,
  executor/repair overlap, cross-session joins, projection amplification, full
  seriality, oversized rework, invalid model, and missing ledger coverage.

## Out of scope

Recovery/effect policy implementation, new product topology, production
notification policy, final compatibility deletion, or operational deployment.

## Locked decisions

Process/tmux/heartbeat/activity is correlated evidence only. Observers never
append activity or refresh liveness. Projections carry source versions,
freshness, lag, and uncertainty. RunAuthorityView, CanonicalRunState, custody,
status, and receipt projections are visibly non-authoritative as bearer tokens
and have no route back into dispatch, repair, retry, completion, cancellation,
publication, or delivery.

## Implemented adjacent slice: review/rework presentation

Source commit `07f428d361f63c465b0dafaca9783585efeaa4b9` implements the
current artifact-backed presentation semantics across the shared status
projection, cloud snapshot/formatter, resident hot context/status tree, CLI,
and `/whats-cooking`. An active execute after `needs_rework` is presented as
`reworking`; active review is `reviewing`; pending rework is `needs_rework`;
and full task weight is labeled plan bookkeeping rather than acceptance.
Approved idle-finalized and genuinely completed states retain precedence.

The focused status/resident verification recorded 170 passing tests, with
Python compilation and `git diff --check` also passing. This is an adjacent M9
consumer-consistency slice, not M9 completion: it does not claim the later WBC,
Run Authority, custody-cursor, rebuildability, or rollout evidence required by
this brief.

## Open questions

- What freshness/lag SLO and bounded reread policy applies per dimension?
- Which process-birth, environment, runner-lease, and heartbeat identities are
  required to exclude unrelated, recycled, hung, or dead workers?
- What degraded/unknown wording and operator affordance avoids optimistic
  collapse without hiding actionable evidence gaps?
- Which compatibility projections are required for historical consumers and
  what are their expiry and zero-reader gates?

## Constraints

All consumers use M8 exact-version identities. No raw legacy artifact, receipt,
projection, or process fact may be parsed for authority. Projection rebuild may
not mutate underlying history/evidence. Production control behavior remains
disabled during shadow comparison and fault testing.

## Done criteria

- Deleting/rebuilding every in-scope projection produces the same ordered view
  and digest from authoritative records plus immutable evidence.
- Torn/stale/cross-environment evidence, unrelated/recycled processes, hung or
  dead workers, stale markers, and projection lag yield explicit unknown/stale
  dimensions and zero authority-increasing action.
- Observer-purity tests prove reads do not emit progress, activity, lifecycle,
  delivery, or repair evidence.
- Positive-authorization trap tests inject internally consistent forged/stale
  Run Authority, WBC, custody, and status projections and prove no action occurs
  until current source grant/fence and lease/epoch records are reread and joined.
- Resident, cloud, CLI, watchdog, and auditor views agree for identical inputs;
  disagreement emits structured drift and blocks action.
- The captured Strategy review-rework state is `executing attempt 2` at every
  supported surface with 100% reducer cursor/hash agreement; a same-basename
  unrelated session never joins its evidence.
- Reconciled work-ledger totals distinguish productive from replayed/avoidable
  categories, expose unknown denominators, and never label Strategy M4's
  2h03m17s implementation or required review as orchestration waste.
- Each deterministic reason fixture fires exactly once with exact evidence IDs;
  an idle pinned-runtime projection canary has zero false stalls and rebuild
  digest parity before control consumers are promoted.
- Generated reader inventory has zero unapproved raw authority reader and every
  expiring compatibility projection is non-authoritative.
- Every consumer row in `research/wbc-boundary-adoption-matrix.md` uses the
  exact M6A query API, treats gaps/persistence/migration uncertainty as typed
  indeterminate or incoherent, and has a negative test proving raw receipts,
  prose/tokens, mutable JSON, filenames, markers, and implicit-latest schemas
  cannot produce positive status or action authority.
- Retention/privacy/encryption/migration tests operate on stored payloads and
  mixed-version data, including legal hold, cross-tenant denial, missing key,
  expiry/tombstone, interrupted migration and explicitly unbackfillable legacy
  history; metadata validation alone cannot pass.

## Touchpoints

Run-state resolver/classifiers, plan/chain/status projections, observability,
CLI/introspection, cloud status/current-target/human blockers/watchdog/wrappers,
repair classifiers, resident status/Discord, AgentBox guardian/services,
provider observations, compatibility formatters, and tests.

## Anti-scope

Do not create another snapshot authority, collapse dimensions into one
optimistic state, treat freshness as progress, or make an observer look like a
runner. Do not repair projection disagreement by rewriting source history.

## Stop and rollback conditions

Stop on reducer nondeterminism, cursor/hash disagreement, false liveness,
observer mutation, projection rebuild mismatch, cross-session join, or work
ledger totals that hide unknowns or misclassify legitimate workload. Rollback
returns consumers to the last proved projection version in view-only mode while
preserving new evidence/reconciliation; no raw fallback may authorize action.

## Handoff and dependencies

Dependency: M8A feasibility/executor evidence plus M8 producer/adopter registry,
M6A query/migration/data-policy APIs and exact-version traces. Handoff to M10:
projection schemas/builders/digests, reader registry, freshness/lag policy,
drift and deterministic-reason evidence, joined latency/work ledger, observer-
purity proof, false-liveness fixtures, compatibility expiry map, and rollout
shadow/idle-canary comparisons.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. False liveness and
optimistic projections have non-local dispatch/repair consequences and can pass
isolated view tests while violating global authority invariants.
