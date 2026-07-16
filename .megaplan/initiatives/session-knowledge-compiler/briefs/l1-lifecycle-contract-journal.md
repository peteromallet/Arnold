---
type: brief
slug: l1-lifecycle-contract-journal
title: Neutral Lifecycle Contract, Journal, and Backend Conformance
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# L1 — Neutral Lifecycle Contract, Journal, and Backend Conformance

## Outcome

Establish an additive v3 managed-agent lifecycle contract, append-only journal,
rebuildable session projection, and Codex/Claude/Hermes capability suite in
shadow-only form. No existing caller changes its launch behavior, orchestration,
authorization, terminal result, or delivery path in this milestone.

## Source and prerequisite

Use `NORTHSTAR.md`, the accepted neutral-lifecycle decision, the primary
managed-agent research from durable run `subagent-20260716-155100-6d5344d7`,
and the reviewed G1-G5 decision records. Re-inventory the actual implementation
target; research paths and the prep baseline are evidence, not a substitute for
source verification.

## In scope

- Resolve and record G1 package ownership, G2 journal/transaction authority, G3
  neighboring fallback/profile handoff, G4 privacy/retention, and G5 backend
  capability floor before freezing implementation contracts.
- Inventory every current launcher, dispatcher, managed v1/v2 manifest, Store/
  WBC attempt/effect record, result/outbox transaction, authority/custody ref,
  and relevant file/DB backend. Produce a machine-readable launch-seam registry
  with authoritative, corroborating, legacy, unknown, and not-applicable labels.
- Define strict additive `arnold-managed-agent-launch-v3`, event payload, session
  projection, evidence-ref, capability, anomaly, and compatibility schemas.
- Establish stable run/attempt/task-revision, root/parent/continuation/retry,
  origin/run-kind/role, orchestrator correlation, compilation-unit, route-policy,
  authority/privacy, delivery-owner, budget, workspace, and digest rules.
- Implement append-only per-run/per-stream sequence allocation, deterministic
  event/idempotency conflicts, causal refs, projection rebuild, mixed v1/v2/v3
  reads, and cross-links to WBC/authority/custody evidence without competing
  positive authority.
- Add neutral adapter interfaces for `prepare`, `start`, `observe`,
  `resume|follow_up`, `cancel`, `collect`, and `capabilities`; unsupported
  operations stay explicit. Fallback order remains caller-owned.
- Shadow-normalize representative resident and automatic managed v2 records
  after their original persistence. Shadow failure emits an anomaly and cannot
  change or retry the source run.
- Add deterministic fake/provider conformance fixtures for Codex, Claude, and
  Hermes covering one-start, sessions, output/tool/token evidence, cancellation
  races, terminal/orphan state, fallback attempt links, unsupported features,
  credential non-disclosure, and exact/estimated token confidence.
- Define compiler-facing stream/range/cursor and `projection_of` semantics so C1
  consumes v3 journal sequences rather than mtimes, prose, or transport records.

## Out of scope

- Migrating resident, repair/auditor, or Megaplan launch seams (L2/L3).
- Making v3 canonical for a production route, changing provider selection,
  altering v2 meaning, or retiring a path.
- Compiler checkpoint/extraction/product implementation (C1-C5).
- Production deployment, enablement, service restart, or real evidence backfill.

## Locked decisions

- V3 is additive; v1/v2 stay readable and unknown legacy fields remain unknown.
- One logical immutable task revision maps to one `run_id`; each provider/process
  start maps to one at-most-once `attempt_id`.
- Journal events are authoritative only for lifecycle facts assigned to the
  lifecycle. They reference rather than replace WBC, Run Authority, Custody,
  caller acceptance, or delivery authority.
- Native sequence and causal refs order events. Wall clocks do not create
  identity or a total order.
- Shadow mode records one execution twice; it never invokes a second model.
- Adapter capabilities are evidence, not simulated compatibility.

## Decision gates and open questions

- **G1, Arnold architecture owner:** approve preferred
  `arnold/agent/lifecycle/` or another stable neutral package using import and
  ownership evidence. Missing approval blocks package/public API work.
- **G2, Store + WBC owners:** approve DB/file authority, fallback/replication,
  and result/outbox/WBC transaction boundaries. Missing approval blocks journal
  persistence.
- **G3, initiative owners:** bind to an accepted `sequential-model-fallbacks`
  handoff or freeze only lifecycle interfaces. Missing choice blocks adapter
  contract freeze and forbids absorbing resolver/fallback policy.
- **G4, privacy/security owner:** approve classifications, audience intersection,
  retention/deletion, raw evidence readers, and promotion audiences. Missing
  approval blocks schema freeze/real ingestion.
- **G5, runtime owner:** approve explicit optional capabilities (recommended) or
  a strict provider floor based on conformance fixtures. Missing choice blocks
  adapter freeze.
- The planner may resolve internal naming, serialization, and fixture layout
  once these decisions are recorded; it may not infer their approvals.

## Constraints

- Reuse existing Store/WBC/authority/custody mechanisms; no parallel authority
  ledger, event bus, sidecar database, standalone queue/lease service, or secrets
  in journal/provenance.
- Preserve current v2 manifest bytes/semantics and all caller results/delivery.
- Unit tests have no hidden network/model dependency.
- Schema and manifest payload versions evolve independently; unknown additive
  event kinds are retained and safely ignored by older readers.

## Touchpoints

Investigate before editing: `arnold/agent/contracts.py`, dispatcher and provider
adapters; the approved lifecycle package; `arnold_pipelines/megaplan/managed_agent.py`;
Megaplan agent-runtime compatibility modules; Store file/DB/migration modules;
WBC execution-attempt/effect interfaces; Run Authority/Custody validators; and
managed-agent, Store, backend, replay, privacy, and conformance tests.

## Measurable done criteria

- G1-G5 receipts are durable and referenced by the frozen contract.
- Schemas round-trip deterministically; canonical digests are stable; malformed,
  privilege-expanding, secret-bearing, cyclic/orphan/conflicting identity, and
  idempotency-conflict fixtures fail closed.
- Mixed v1/v2/v3 read and projection rebuild tests preserve known facts and
  explicit unknowns without rewriting source history.
- Fake Codex/Claude/Hermes adapters pass common one-start, terminal, evidence,
  restart/adoption, cancellation, capability, and token-confidence suites.
- Shadow normalization makes zero provider/model starts and forced journal/
  projection failure leaves the original run/result/delivery unchanged.
- WBC/Run Authority/Custody/acceptance/delivery ownership negative tests prove
  lifecycle records/projections alone cannot authorize or advance an action.
- `docs/managed-agents/handoffs/l1-lifecycle-contract.json` satisfies the epic
  handoff schema and is reviewed for L2.

## Anti-scope

Do not route agents through Discord, change Megaplan profiles/gates/retries,
perform real migration/cutover, invent authority from logs/PIDs/prose, add a
general workflow ledger, or implement the knowledge product.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. A wrong package,
transaction, identity, or ownership boundary can pass local tests while causing
duplicate effects, privacy leakage, or competing authority.
