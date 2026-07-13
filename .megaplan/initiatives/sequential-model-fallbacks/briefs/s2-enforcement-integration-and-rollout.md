---
type: brief
slug: s2-enforcement-integration-and-rollout
title: Tree Enforcement, Dispatcher Integration, Migration, and Rollout Readiness
epic: sequential-model-fallbacks
created_at: '2026-07-11'
---

# Sprint 2 - Enforcement, Integration, and Rollout Readiness

## Outcome and delivery contract

In days 7-10, with contingency inside the roughly two-week initiative, complete the managed-agent system: immutable ancestry and intersection-only authority, transactional tree/root budgets, all Megaplan and resident adapters, additive v1/v2 migration and restart reconciliation, deterministic adversarial conformance, observability, operator documentation, and staged rollout/rollback readiness. Production enablement remains a human decision.

Overall plan difficulty is **5/5**; use **partnered-5/full/high @codex +prep**. The sprint consumes Sprint 1's frozen contracts and fixtures; it may revise them only through one documented compatibility change applied across every track.

## Dependency and parallel execution topology

Hard chain dependency: Sprint 1 must provide verified resolver, fallback, custody/schema, and launch/result contracts. Once present, begin these tracks concurrently:

- **Track E - ancestry, authority, and budgets:** implement immutable tree identity checks, intersection-only model/reasoning/tool/sandbox/time/token/cost/attempt/tree ceilings, depth/fanout/descendant policy, root-wide visited specs, transactional reservation/commit/release/fencing, truthful usage, cancellation, crash recovery, denial/exhaustion receipts, and stale-worker fencing.
- **Track F - dispatcher integration and migration:** converge Megaplan execute/critique/prep/fanout/worker/chain/cloud/resume/preflight plus resident root/child/scheduler/repair/VP-todo paths; remove or demote parallel routing/fallback authorities; add v1/v2 readers and additive writers, backfill, shadow comparison, gated cutover, rollback, split-brain detection, restart reconciliation, scalar projections, and status/audit/trace records.
- **Track G - adversarial evidence and rollout:** build the shared cross-dispatcher fixture harness, North Star traceability matrix, concurrency/fault/replay tests, migration evidence, observability/alerts, operator configuration validation, feature flags, shadow/canary gates, rollback procedure, and the exact Discord provenance/root-completion compatibility seam.

Tracks F and G develop adapters, fixtures, and shadow comparisons against the Sprint 1 contract while Track E lands. The final convergence phase wires policy receipts into every adapter and runs the complete deterministic gate. This is one integration sprint with parallel workstreams, not three sequential former milestones.

## Ancestry, authority, and root-budget contract

- Descendant authority is the minimum/intersection of system, root/operator, parent, profile, and explicit request ceilings. It cannot expand model class/allowlist, reasoning, tools, sandbox, wall time, tokens, cost, attempts, depth, fanout, or descendants. Missing or malformed evidence rejects launch.
- Enforce defaults of depth **2** below root, at most **4** direct children per parent, and at most **8** descendants per root. Configuration may lower them. Raising requires explicit root/operator policy, validation, a distinct receipt reason, and never a child override.
- Reserve child slot, descendant count, attempt, estimated cost/tokens/time, and canonical spec identity transactionally before dispatch. Commit/release uses durable fencing and crash recovery; concurrent launchers cannot oversubscribe.
- Attempts, spend, deadline, and visited specs are root scoped across branches/processes and survive fallback, child/restart, alias, cancellation, and handoff. A visited `(canonical model spec, provider family, relevant policy revision)` cannot be retried elsewhere in the tree.
- Enforce deadlines and available provider usage before/during attempts. Unknown or late usage is conservatively charged/flagged, never optimistically refunded. Every grant, denial, exhaustion, and reconciliation emits a deterministic receipt.

## Integration, migration, and restart contract

- All named Megaplan and resident dispatch paths consume the same Sprint 1 resolver, fallback, custody, launcher, and result contracts. Adapter-specific routing tables, retry classifiers, ambient fallback, mutable-path custody, or result parsing lose authority.
- Preserve legacy scalar fields as selected/actual-attempt projections while additive records expose configured/attempted/selected specs, canonical receipts, ancestry/provenance hashes, mutation evidence, reservations/usage, limit decisions, results, and migration state.
- Implement explicit dual read, additive write, backfill, shadow/observe comparison, feature-gated cutover, rollback, and split-authority detection for `arnold-resident-agent-run-v1`, legacy profiles/state, and relevant Megaplan records. Do not destructively rewrite or fabricate custody/privilege.
- Reconcile launch intent, spawn, attempt, mutation evidence, reservation, result intent/result, cancellation, and root-completion states after kill/restart. Preserve attempts, visited specs, consumed/uncertain usage, deadlines, immutable fields, and completed results; fence stale processes and deduplicate completion authority.
- Status/audit/trace exposes deterministic resolution and fallback hashes, immutable task/provenance refs, ancestry, limits/reservations/usage, denials, results, legacy-incomplete proof, migration authority, and reconciliation without secrets or new full Discord-content retention.
- At the Discord boundary, consume its immutable request provenance and submit exactly one generic root completion intent/result to its lifecycle/delivery API. Only a root can cross this seam. This initiative never writes Discord transport outboxes or owns acknowledgement, delivery, attachment, retry, dead-letter, or provider reconciliation.

## Adversarial acceptance matrix

The final traceability matrix must map every North Star invariant to a named deterministic test and evidence artifact covering:

- scalar profile/phase/tier/prep/state compatibility, selected identities, and four-value `AgentMode` unpacking;
- exact D1-D10 mapping; missing D5, explicit D5, risk-promoted D5, invalid D inputs, override precedence, and profile/catalog revisioning;
- byte-identical resolver/fallback receipts for identical inputs in worker, fanout, resident root, and managed-child adapters;
- every retry class/provider-family rule, exhaustion and root visited-spec/attempt limits, plus no fallback after every possible or unknown mutation signal;
- complete root/child bytes and hashes at depth two, tamper rejection, immutable ancestry and request/Discord provenance, managed-launch-only claims, durable structured results, and root-only delivery;
- depth 2, fanout 4, descendants 8, wall-time/token/cost/attempt enforcement and reservation reconciliation under concurrent launch, crash, cancellation, replay, fallback, and resume;
- descendant model/reasoning/tool/sandbox/budget intersection and proof that missing/malformed/legacy inputs never expand privilege;
- v1 dual read, incomplete-custody projection, backfill, shadow divergence, cutover, rollback, stale-worker fencing, split-authority detection, and no fabricated evidence;
- deterministic reconciliation at every persistence/side-effect boundary without timing-only sleeps, process-liveness guesses, or live-provider dependence for core correctness.

## Required handoff and operational evidence

Produce:

- `docs/managed-agents/tree-policy-and-budget-v1.md` with policy receipt schema and concurrency/fault fixtures;
- `docs/managed-agents/migration-and-operations-v2.md`, migration/restart fixtures, and dispatcher parity report;
- `docs/managed-agents/conformance-and-rollout-v2.md`, a complete North Star traceability matrix, named proof artifacts, status/metric/alert definitions, and final operator decision records.

Focused and broader relevant suites must pass without weakened assertions or excluded legacy fixtures. Rollout documentation must define flags, shadow mode, canary gates, rollback, stuck reservation/result and split-authority alerts, provider/model catalog revisioning, and numeric limit validation.

## Human and coordination gates

- Before changing the Discord seam, compare the current `discord-resident-delegation-delivery-corrective` schemas/decisions. Any insufficiency becomes an additive compatible interface requirement coordinated with that owner, not copied transport logic.
- Production rollout stays disabled/shadowed until an operator supplies and validates the provider/model catalog, environment/root-class dollar/token/time ceilings, any explicit structural-limit increase, canary population, and cutover date.
- The sprint may implement and test flags/canary/rollback machinery, but it does not launch this chain, start cloud work, or enable production rollout.

## Touchpoints

- managed launcher/store/ledger, fallback attempt kernel, resolver ceiling types, cancellation/reaper/restart, receipts and structured results
- Megaplan profile/state/worker/fanout/execute/critique/prep/chain/cloud/preflight/status/audit surfaces
- resident root/child manifest/launcher/worker/provenance/scheduler/repair/VP-todo/recovery/config/status surfaces
- managed-agent conformance, compatibility, migration, concurrency, fault-injection, Discord-boundary, and broader relevant suites

## Anti-scope

Do not rely on prompt or process-local counters, silently raise limits, refund unknown usage, dual-write competing authorities indefinitely, delete legacy evidence, fabricate v1 hashes, directly send Discord/user replies, absorb Discord transport ownership, use timing-only correctness evidence, require live provider failures, launch the chain/cloud work, or enable production rollout.
