# Task: produce the unified authority-and-efficiency prevention epic plan

Act as the sole synthesis and delivery owner for the current Discord request. This is planning-only work: do not launch, resume, restart, deploy, merge, push, or mutate any live chain/runtime.

## User outcome

Produce a thorough, implementation-ready plan that combines both recent latency/root-cause syntheses and prevents the entire observed category of failures from recurring. Integrate correctness, custody, recovery, and projection guarantees into Run Authority wherever that is the proper owner, while also solving the adjacent planning/executor efficiency issues that do not belong in Run Authority.

## Required evidence

Read and reconcile at minimum:

- `.megaplan/plans/resident-subagents/subagent-20260714-101421-463e5e9c/result.md` (combined synthesis; follow its cited contributor result paths where needed).
- `.megaplan/plans/resident-subagents/subagent-20260714-101356-39ea719f/result.md` (Transaction Spine investigation).
- `.megaplan/plans/resident-subagents/subagent-20260714-101356-fc5f6cae/result.md` (Strategy Roadmap investigation).
- `.megaplan/initiatives/runauthority-epic/NORTHSTAR.md`, its architecture/main-plan decisions, briefs, completion manifest, proof map, and current completion evidence.
- The existing canonical continuation initiative `.megaplan/initiatives/custody-control-plane/`, especially `NORTHSTAR.md`, `chain.yaml`, migration matrix, ownership decisions, and briefs m6-m11.
- Relevant authority/repair/efficiency contracts in `.megaplan/initiatives/megaplan-maintenance/` and `.megaplan/initiatives/workflow-boundary-contracts/`, without inventing a competing authority layer.

## Required plan qualities

1. Reuse `custody-control-plane`; do not create another initiative.
2. State one durable North Star and an explicit ownership matrix: Run Authority vs TransitionWriter/repair custody vs WBC vs Maintenance vs planner/compiler vs executor vs observability/auditor.
3. Map every synthesis finding to: root cause, canonical owner, concrete control, milestone, measurable acceptance proof, rollout gate, rollback/fail-closed behavior, and legacy path deletion gate.
4. Cover at least: attempt-bound repair identity and exact signatures; fencing/quarantine; immutable attempts and adoptable repair receipts; one authoritative reducer and rebuildable projections; event-driven recovery with p95 unblock under five minutes plus six-hour backstop; bounded invalid-ref retries; DAG feasibility/parallelism gates; complexity/oversized-task controls; deterministic validation outside model calls; executor circuit breakers; productive-vs-replayed work/token/cost ledger; deterministic auditor reasons; mixed-version behavior; canary and genuine blocked-run acceptance.
5. Preserve the distinction between legitimate workload and avoidable orchestration latency.
6. Decompose into dependency-ordered, roughly sprint-sized milestones. Prefer extending/revising m6-m11 if they already cover the scope; add milestones only where genuinely necessary. Each milestone needs outcome, scope/anti-scope, dependencies/handoff, concrete verification, and stop/rollback conditions.
7. Include staged rollout: shadow evidence/telemetry, deterministic replay tests, idle projection canary, repair/worker canary, controlled deployment, and a genuine blocked-run recovery acceptance test.
8. Include explicit non-goals and unknowns, especially exact projection I/O cost, compaction time, and productive-versus-replayed work baselines.
9. Define completion so local tests or nominal manifests alone cannot claim success: require content-addressed evidence, installed-runtime provenance, canary/live proof, no legacy authority bypasses, and deletion/retirement evidence.

## Durable outputs

Update the canonical `custody-control-plane` planning assets under `.megaplan/initiatives/custody-control-plane/` as necessary. At minimum, write a concise synthesis/traceability document under `research/` or `decisions/` and ensure `NORTHSTAR.md`, `chain.yaml`, and affected milestone briefs accurately encode the unified plan. Preserve unrelated dirty work. Validate YAML and initiative layout with the canonical CLI/tests available.

In your final result, give the user a concise but thorough summary: relationship of the two issues, ownership split, milestone sequence, prevention guarantees, rollout/proof gates, important unknowns, and exactly which durable planning artifacts were updated. Be honest about planning vs implementation: no control is deployed merely because the plan exists.

Overall planning difficulty: 5/5. Use high architectural rigor because a superficially passing plan could preserve authority bypasses, stale repair attachment, or misleading projections.
