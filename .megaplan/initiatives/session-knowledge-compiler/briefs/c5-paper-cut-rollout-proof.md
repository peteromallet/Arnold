---
type: brief
slug: c5-paper-cut-rollout-proof
title: Paper-Cut Consolidation and Operational Proof
epic: session-knowledge-compiler
created_at: '2026-07-13T20:36:41.554645+00:00'
---

# C5 — Paper-Cut Consolidation and Operational Proof

## Outcome

Consolidate evidence-linked paper-cut observations into deduplicated,
prioritized improvement backlog items without erasing sources, then complete
compatibility, reconciliation, diagnostics, rollback readiness, and offline
conformance proof across every in-scope lifecycle/compiler path without
deploying, broadly enabling, restarting, or retiring a production path.

## Source and prerequisites

Resident messages `msg_d406fc21f99b`, `msg_e7b43d46d642`,
`msg_89cc57c1fa72`, and `msg_5d47dbb7a366` distinguish paper cuts from backlog
work and require consolidation that preserves source observations. Require all
L1-L3 and C1-C4 reviewed handoffs, especially
`docs/session-knowledge-compiler/handoffs/c4-promotion-governance.json`.

## In scope

- Finalize a small, non-overlapping-enough paper-cut taxonomy that aids grouping
  while retaining extensible tags. Include at least discoverability, ambiguous
  contract, missing capability, reliability/correctness, performance/cost, and
  workaround/friction evidence where supported.
- Define deterministic candidate similarity/merge keys using affected surface,
  category, symptom, applicability, and evidence. Model suggestions may propose
  merges, but acceptance must be explainable and reversible.
- Create a backlog item that links to every contributing immutable observation;
  store recurrence count, distinct sessions/actors, impact, severity/urgency,
  workaround cost, confidence, applicability, proposed outcome, and status.
- Support merge, split, relate, reject, supersede, and reopen operations without
  deleting observations or losing previous membership/history.
- Rank/prioritize with a documented deterministic policy. Confidence and volume
  do not turn a proposed improvement into performed work.
- Integrate with the existing ticket/backlog surface only through an explicit
  adapter and idempotency key; avoid duplicate ticket creation on retries.
- Add product metrics and diagnostics: eligible/checkpointed/failed/retried
  ranges, lag, source-token and model cost, schema/claim quality failures,
  correction rate, promotion decisions, contradictions, observation-to-backlog
  lineage, and compiler effect on primary-session latency/result.
- Implement disabled/shadow/canary/enabled configuration with default disabled,
  a safe threshold, direct Pro route, bounded concurrency/cost/retry, cohort,
  immediate disable, and rollback paths. Do not enable production in this sprint.
- Finish additive file/DB and mixed v1/v2/v3 compatibility, explicit upcasters,
  unsupported-version/gap behavior, and privacy/retention/deletion documentation.
- Add a scheduled read-only reconciler over lifecycle journal/source cursors,
  Store/WBC events, manifests, typed results, acceptance/custody/delivery refs,
  and compiler checkpoints. It may append gaps/observations but cannot mutate,
  retry, repair, accept, schedule, transfer custody, deliver, or infer from prose.
- Generate and prove the complete launch/producer/backend matrix for resident,
  every Megaplan phase/worker/transition, retries/fallback/rework/nesting,
  repair/meta-repair/auditor roles, plan/milestone/chain/higher workflows,
  Codex/Claude/Hermes/future fixtures, and file/DB support.
- Build a content-addressed, redacted offline replay of an existing real epic
  under its access/retention rules. Exercise duplicate, restart, concurrent,
  late, out-of-order, failure, correction, promotion proposal, search, dedup,
  terminal synthesis, and projection rebuild without resuming/mutating the epic.
- Document operator and agent usage, privacy/redaction inheritance, known limits,
  and how to audit a claim back to primary evidence.

## Out of scope

- Automatically implementing backlog items.
- Organization-wide prioritization across unrelated repositories.
- Deleting raw observations after consolidation.
- Enabling optional idle triggers by default without measured evidence.
- Production deployment, restart, broad enablement, real observation windows,
  or deletion/retirement of old launch paths without G8.

## Locked decisions

- Paper cuts are source observations; backlog items are deduplicated proposed
  work. They overlap by lineage, not by being the same record.
- Multiple observations may map to one backlog item and one observation may be
  related to multiple candidates, with explicit primary membership if needed.
- Consolidation never rewrites or erases observations.
- Priority is evidence-backed and reproducible; proposals remain proposed.
- Compiler failure, cost limits, disablement, or backlog adapter failure must not
  change primary managed-session completion/delivery.
- Default extraction remains the exact direct DeepSeek Pro route established in
  C2; no silent provider/model substitution.
- Reconciliation and every status/dashboard are projections; neither can
  authorize, retry, accept, repair, transfer custody, deliver, or become semantic
  source material.

## Open questions for the planner

- What minimal scoring formula balances recurrence, user/agent impact,
  workaround cost, reach, confidence, and effort without fake precision?
- Which existing Megaplan ticket fields can represent lineage and which require
  a separate adapter/index?
- What shadow/canary cohort and budget demonstrate acceptable extraction quality
  and overhead before broader automatic operation?
- Should idle compilation remain disabled after rollout, or can measurement
  justify an opt-in policy?
- What retention/redaction and deletion-request behavior applies to derived
  records when primary source evidence is governed externally?
- Which existing real epic is authorized and sufficiently complete for a
  redacted offline replay, and what gaps must remain explicit?
- **G8, runtime/service owner:** choose keep dual path, approved cutover, or
  eventual retirement per seam only after operational criteria. This sprint may
  produce readiness evidence but cannot infer approval or perform retirement.

## Constraints

- Preserve all C1–C4 idempotency, evidence, correction, authorization, and
  applicability contracts.
- Rollout must be reversible and must not require rewriting checkpoints.
- Metrics must not expose transcript content or credentials.
- Backlog adapters must be idempotent and fail independently of compilation.
- Keep the default cost bounded; avoid a high-frequency 10k-token trigger.

## Touchpoints

C1–C4 compiler/search/store APIs and L1-L3 lifecycle registry; ticket core/store
and initiative/ticket CLI surfaces; file/DB migrations; read-only reconciliation;
configuration/observability/event/cost modules; scheduler/worker concurrency;
real-epic fixture tooling; documentation; and end-to-end tests spanning resident,
every Megaplan worker class, repair/auditor roles, managed-agent lifecycle, Store,
tickets, privacy, provider routing, compatibility, rollback, and replay.

## Measurable done criteria

- Three equivalent observations consolidate into one backlog item with all
  source links intact; a later split restores separate items without rewriting
  observations or history.
- Duplicate/retry processing creates neither duplicate memberships nor duplicate
  external tickets.
- Priority calculation is documented, deterministic, and covered for recurrence,
  impact, workaround, confidence, and applicability changes.
- End-to-end tests cover threshold and terminal compilation, four outputs,
  synthesis/correction/search, promotion proposal, contradiction handling,
  paper-cut consolidation, and primary-session isolation on compiler failure.
- Durable evidence shows direct `hermes:deepseek:deepseek-v4-pro` resolution for
  the bounded extractor in the rollout path.
- Operators can observe lag/failure/cost/lineage, disable new compilation, retry
  failed ranges safely, and roll back without losing accepted checkpoints.
- Documentation lets an agent use all five explicit surfaces and lets a reviewer
  trace any synthesis, promotion, or backlog item to primary evidence.
- Complete matrix has no silent or unclassified supported row; every row names
  source authority/corroboration, adapter, fixture, test, compiler policy,
  rollback, and retirement status. Unknown rows block completion.
- Mixed-version/file/DB replay and forced reconciler/model/schema/store/auth/
  ticket/budget failures rebuild equivalent projections and never mutate or
  change primary execution/acceptance/custody/result/delivery.
- The redacted real-epic offline replay is content-equivalent under normal,
  duplicate, restart, concurrent, late, and out-of-order ingestion and records
  explicit legacy gaps without resuming or changing the source.
- `docs/session-knowledge-compiler/handoffs/c5-completion-evidence.json` maps
  every North Star measure, README scope row, decision gate, handoff, matrix row,
  command, and proof artifact and clearly separates implementation completion
  from deployment/enablement/retirement.

## Anti-scope

Do not auto-fix backlog items, delete observations, replace existing ticket
authority, or enable unbounded/global cross-project clustering. Do not optimize
away provenance for storage or ranking convenience. Do not deploy, restart,
broadly enable, run production observation windows, or retire old paths.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 4/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. The truth
contracts are fixed, but an incomplete producer/backend matrix, mutating
reconciler, or irreversible consolidation can false-green the epic; the default
high profile is therefore retained.
