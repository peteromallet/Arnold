---
type: brief
slug: m3-consolidation-operational-proof
title: Paper-Cut Consolidation and Operational Proof
epic: session-knowledge-compiler
created_at: '2026-07-16T12:30:00+00:00'
---

# M3 — Paper-Cut Consolidation and Operational Proof

## Outcome

Complete the requested product: consolidate immutable friction observations
into reversible prioritized backlog work, add the minimum safe operating and
migration controls, and prove the full contract across every required producer
class and representative Store/execution backends without enabling, deploying,
resuming, or mutating a real epic.

## In scope

- Keep a small extensible taxonomy covering discoverability, ambiguous contract,
  missing capability, reliability/correctness, performance/cost, and workaround/
  friction where evidenced.
- Generate deterministic, explainable grouping candidates from surface,
  category, symptom, applicability, and evidence. Persist every observation
  link plus recurrence/distinct-session count, impact, urgency, workaround cost,
  confidence, applicability, proposed outcome, status, score inputs, and history.
- Support merge, split, relate, reject, supersede, and reopen without deleting
  observations. Adapt idempotently to the existing ticket authority; adapter
  failure never gates compilation or session delivery.
- Finish additive file/DB compatibility and old-store loading. Inherit source
  retention/redaction/access boundaries and document deletion limitations rather
  than creating a parallel privacy policy.
- Version envelopes and adapters independently; add explicit upcasters and
  unsupported-version/gap behavior. Breaking identity changes create a new
  major version and migration observation rather than rewriting history.
- Add a scheduled read-only reconciler over native source cursors, journals,
  Store events, manifests, typed results, and acceptance/custody records. It may
  append missing observations or gaps but cannot mutate, retry, repair, accept,
  schedule, transfer custody, deliver, or infer authority from logs/PIDs/prose.
- Add disabled/shadow/canary/enabled configuration; exact route, threshold,
  cohort, concurrency, input/output/cost, attempts, timeout, retry, immediate
  disable, and rollback controls. Idle stays disabled absent measured opt-in.
- Expose content-safe metrics and diagnostics for eligibility, checkpoint,
  failure/retry, lag, cost, validation quality, correction, promotion,
  contradiction, backlog lineage, and primary-result/latency isolation; provide
  bounded authorized retry that distinguishes failure classes.
- Generate and prove a complete matrix for resident roots/descendants; all
  prep/plan/critique/gate/revise/finalize/execute/review phase/step workers and
  implementation/review roles; retries/fallback/rework; nested/concurrent
  children; authoritative repair/meta-repair/watchdog/auditor lifecycle rows;
  plan/milestone/chain/child-epic/higher-workflow transitions; Hermes, Codex,
  Claude, and a future-backend fixture; and file/DB where supported.
- Cover every trigger, exact extraction route, four records, layered run-to-
  workflow synthesis/correction/search, five controls, promotion/contradiction,
  consolidation/ticketing, restart/crash/late/concurrent failure, schema
  evolution, reconciliation, disable/rollback, privacy/authorization, and
  primary execution/acceptance/custody/result/delivery isolation.
- Build a content-addressed, redacted offline replay of the existing
  `custody-control-plane` epic under its access/retention rules. Register legacy
  unknowns and expected gaps without inference; replay normal, duplicate,
  restart, concurrent, late, and out-of-order delivery without resuming or
  changing the source chain.
- Document agent controls, operator status/retry/disable/rollback, known limits,
  rollout gates, and how to trace any claim or backlog item to primary evidence.

## Locked constraints

- Consolidation never erases or rewrites observations; priority is reproducible
  and does not turn proposed work into performed work.
- Exact extraction remains `hermes:deepseek:deepseek-v4-pro` via `direct`; no
  silent fallback, unbounded costs, or source content in metrics/logs.
- Rollback preserves accepted checkpoints. Budget, adapter, compiler, or
  rollback failure never changes primary completion/delivery.
- Source logs, mutable projections, transcripts, tool output, and agent/model
  prose remain evidence rather than authority; reconciliation is non-mutating.
- No deployment, restart, broad enablement, automatic backlog implementation,
  global prioritization/clustering, unrelated refactor, or mandatory idle trigger.

## Acceptance evidence

- Equivalent observations consolidate once with all sources; split restores
  separate items and history. Merge/split/relate/reject/supersede/reopen,
  deterministic scoring, authorization, lineage, duplicate membership/ticket,
  and adapter-failure tests pass.
- Additive migrations and legacy file/DB fixtures pass without rewriting accepted
  history; envelope/adapter upcast, unsupported/ambiguous-version, and
  authorization/redaction/deletion/tombstone behavior is documented and tested.
- Every rollout state, cohort/budget/retry bound, disabled idle, safe retry,
  metrics-no-content, disable, rollback, and re-enable path is tested. Forced
  model/schema/store/auth/ticket/budget failures are diagnosable and harmless.
- The generated conformance matrix has no missing required producer, role,
  transition, or backend row. Every row names its authoritative source or
  corroborating status, adapter, fixture, and test; unknown seams are durable
  gaps and prevent false completion.
- Real-epic offline replay yields content-equivalent active projections under
  normal, duplicate, restart, concurrent, late, and out-of-order ingestion,
  with no source mutation, cursor corruption, duplicate observation/record/
  ticket, evidence loss, authorization leakage, unsafe provider fallback, or
  primary execution/acceptance/custody/result/delivery change.
- Forced reconciler failure and adversarial logs/PIDs/prose prove it neither
  mutates sources nor fabricates authority. Synchronous capture performs no
  model/network call and meets the bounded enqueue overhead defined by the
  accepted architecture decision.
- Documentation maps every North Star success measure and README scope-ledger
  row to exact commands/tests/evidence and lists remaining operational rollout
  gates; historical initialized planning is not counted as implementation proof.

## Dependencies and risks

Requires M1-M2 landed contracts and focused suites. Reuse the existing ticket,
configuration, observability, privacy, scheduler, Store, native journal, WBC,
chain/acceptance, custody, and managed-agent surfaces according to their actual
authority. Rollout cost/latency, privacy amplification, source drift, and
backend variance are the principal risks; keep widening evidence-gated and
treat shadow/canary, soak, deployment, and enablement as external operational
gates.

## Estimate and non-goals

Approximately two skilled-human weeks, including integration hardening, docs,
and conformance review; estimate only, not a guarantee. Difficulty 4/5, profile
`partnered-4`, robustness `full`, depth `high`, directed prep enabled. Do not
launch a chain, deploy, restart, push, enable production, auto-fix backlog items,
or build any cross-project knowledge platform.
