# Durable Session Knowledge Compiler

Build a small, automatic, evidence-linked compiler for every managed execution
and agent session. It turns new persisted evidence into durable activity,
reusable knowledge, paper-cut observations, and improvement candidates without
changing execution authority, scheduling, acceptance, custody, delivery, or
the managed session's outcome and terminal-delivery path.
`NORTHSTAR.md` remains the end-state authority.

## Current truth

The current plan is **three ordered implementation sprints**, each estimated at
roughly two skilled-human weeks. This is a planning estimate, not a delivery
guarantee. The canonical chain entry point is `chain.yaml`, which resolves to
`chain-v3-20260716.yaml`; only the three briefs directly under `briefs/` are
current execution inputs.

The accepted architecture is the initiative-local
[managed execution observation and lineage decision](decisions/managed-execution-observation-lineage.md).
It generalizes the same compiler across resident, Megaplan, repair, backend,
chain, and higher-workflow evidence. This is current planning truth, not a
claim that the compiler or any adapter has been implemented.

| Sprint | Vertical outcome | Estimate | Dependency |
|---|---|---:|---|
| M1 | Persisted evidence to an accepted four-record checkpoint | ~2 weeks | Current Store, scheduler, managed-session, and direct Hermes seams |
| M2 | Synthesis, correction, scoped retrieval, five controls, and promotion lifecycle | ~2 weeks | M1 accepted-checkpoint and evidence contracts |
| M3 | Paper-cut backlog, compatibility, operational controls, cross-backend conformance, and closeout proof | ~2 weeks | M1-M2 end-to-end path |

Three sprints are sufficient because each is a tested vertical slice through
existing repository seams. The former 11-sprint plan treated schemas, leases,
extraction, synthesis, search, promotion, contradiction, rollout, and
conformance as independent platforms. They are coupled parts of one modest
append-only feature and do not require separate services, stores, handoff-only
phases, or a new retrieval platform.

## Scope coverage

This ledger distinguishes requested outcomes from optional machinery. Every
required outcome is assigned to a current sprint and concrete acceptance
evidence.

| Original requested outcome / requirement | Sprint | Acceptance evidence |
|---|---|---|
| Cover every resident-managed root/subagent and continuation; every Megaplan phase/step implementation and review worker; retry, fallback, rework, supersession, and nested lineage; authoritative repair/meta-repair/watchdog/auditor lifecycle evidence; plan/milestone/chain/child-epic and higher-workflow transitions; and Hermes, Codex, Claude, and future execution backends | M1/M3 | Generated producer/backend coverage matrix binds every required kind to a durable source seam and test; missing kinds remain explicit gaps rather than disappearing |
| Preserve stable workflow -> epic/chain -> sprint/milestone -> plan -> phase/step -> attempt -> agent-run identity with root/parent/causal links, distinct occurrence/persistence/capture/ingestion times, native ordering, and separate lifecycle/acceptance state | M1 | Envelope and adapter fixtures reject guessed identity, causal cycles, cross-run drift, orphan joins, clock-only ordering, and conflated outcome/acceptance |
| Keep execution authority, WBC evidence authority, scheduling/acceptance, custody, and delivery with their current owners; primary records, logs, projections, transcripts, and agent prose remain typed evidence with declared source priority rather than compiler authority | M1/M3 | Authority/custody matrices and negative tests prove the compiler cannot grant, schedule, accept, retry, transfer custody, deliver, or infer authoritative status from prose/PIDs |
| Compile at roughly 100,000 **newly persisted** tokens and on completed, failed, cancelled, and superseded terminal states, including terminal ranges below threshold | M1 | Threshold, below-threshold, all-terminal, late-event, reset, retry, and out-of-order tests |
| Durable immutable checkpoints, atomic cursor advancement, idempotency, restart/concurrency safety, visible retryable failure, and no impact on primary completion/delivery | M1 | Duplicate, restart, concurrent claim, partial-write, model/schema/store failure, and terminal-isolation tests |
| Separate activity, reusable knowledge, paper-cut observation, and improvement-candidate records | M1 | Versioned schema and file/DB round-trip fixtures prove four distinct record types committed atomically |
| Preserve observed/performed/inferred/proposed/unverified claim kind, evidence links, applicability, actor, confidence, and reproducible compiler provenance | M1 | Deterministic validation rejects missing kinds, proposal-as-performed, unauthorized/out-of-range evidence, partial output, and secret-bearing provenance |
| Use bounded extraction through canonical `hermes:deepseek:deepseek-v4-pro` with provider `direct`, with no silent fallback and transcript content treated as data | M1 | Route metadata, bounded fake integration, injection, cost/size, chunk/gap, unsafe-fallback, and retry tests |
| Versioned rolling synthesis and terminal final synthesis, with append-only claim/synthesis correction and complete lineage | M2 | Multi-checkpoint, terminal-below-threshold, rebuild, correction, supersession, active-view, and history tests |
| Build correctable projections from per-agent-run checkpoints through attempt, phase/step, plan, milestone, epic/chain, workflow, and reviewed cross-epic knowledge without lossy rewriting | M2 | Late, corrected, rejected, quarantined, superseded, concurrent, and reworked inputs deterministically rebuild new versions while every source and decision remains traceable |
| Near-invisible automatic operation plus `record-learning`, `record-friction`, `correct-summary`, `search-session-knowledge`, and `propose-promotion` | M2 | Positive/negative schema, actor, authorization, pagination, no-tool automatic path, and no-bulk-prompt-injection tests |
| Scoped evidence-aware search across records and syntheses without presenting proposed, unverified, stale, or out-of-scope material as current fact | M2 | Repository/session/revision authorization, pagination, applicability, active/superseded, and leakage tests |
| Explicit evidence-linked project promotion with repository/version/commit/path applicability, authority-proportionate review, contradiction preservation, supersession, and invalidation | M2 | Accept/reject/more-evidence/narrow, strong-review, contradiction/adjudication, divergence/rebase/stale, supersession, and invalidation tests |
| Consolidate recurring paper cuts into explainable, reversible, prioritized backlog work without deleting observations; integrate idempotently with existing tickets | M3 | Merge/split/relate/reopen/ranking/lineage and duplicate-ticket/adapter-failure tests |
| Backward-compatible file/DB storage, additive schema/adapter evolution, inherited privacy/redaction/access rules, bounded context/cost/concurrency/retries, diagnostics, safe retry, disable/rollback, and read-only reconciliation | M3 | Additive migration/upcast, old-store load, unsupported-version, metrics-no-content, rollout-state, rollback/re-enable, reconciler non-mutation, operator/agent docs, and full failure matrix |
| Prove the design against a real epic without mutating, resuming, deploying, or restarting it | M3 | Content-addressed redacted custody-control-plane replay yields equivalent projections under duplicate, restart, concurrent, late, and out-of-order ingestion with explicit gaps |

## Boundaries and explicit deferrals

Required scope stays in the three sprints. The following machinery is not a
required product outcome and is deliberately deferred or excluded:

- Idle compilation remains a disabled policy hook until measured cost/noise
  justifies opt-in enablement; threshold and terminal triggers fully cover the
  requested default behavior.
- Reuse existing Store transactions, scheduler claims, structured-worker
  routing, authorization, observability, and ticket APIs. Do not create a
  sidecar database, standalone queue/lease service, event bus, promotion
  service, or parallel review authority merely to implement this feature.
- Execution authorization, scheduling, task/rework decisions, acceptance,
  custody/repair dispatch, and delivery remain outside the compiler. The
  read-only reconciler may append observations or gaps but may not repair,
  retry, accept, transfer custody, or mutate a source run.
- Start with bounded Store-backed structured/text retrieval. A vector database,
  general RAG/document platform, global ontology, and cross-project clustering
  are non-goals; the requested scoped search remains covered.
- Contradiction detection may surface deterministic, explainable candidates;
  automatic semantic adjudication, self-approved authoritative promotion, and
  autonomous code changes are excluded. Human/declared review produces the
  requested safe outcome.
- Broad production enablement, deployment, restart, long soak operation,
  automatic implementation of backlog items, and organization-wide priority
  policy are operational follow-ons, not planning or implementation acceptance.

## Dependencies and risks

- **Source truth varies by backend.** M1 inventories capabilities and preserves
  native offsets rather than forcing byte/event/token positions into one unit.
- **Authority adoption varies by producer.** WBC, native journals, Store
  events, manifests, acceptance receipts, and repair/custody records are not
  universally adopted. M1 records declared source priority and gaps rather
  than creating a competing ledger or promoting convenience events.
- **Chain and parent identity can be incomplete.** M1 must bind an explicit
  chain-run identity and propagate managed parent/root context where supported;
  unresolved legacy joins remain visible and fail closed for derivation.
- **File/DB atomicity may differ.** M1 must prove one logical commit or fail
  closed without advancing the cursor.
- **Model output can overstate evidence.** M1 uses claim-kind/evidence validation,
  bounded inputs, injection-resistant framing, explicit gaps, and no unsafe
  provider fallback.
- **Promotion can become stale after repository movement.** M2 binds accepted
  knowledge to deterministic applicability and preserves contradiction/drift
  evidence rather than silently selecting a winner.
- **M2 is the densest sprint.** Its scope stays feasible by one append-only
  lifecycle model and one shared query/authorization path; if implementation
  evidence disproves the estimate, split within M2 without changing product
  scope or pretending partial completion.
- **Rollout can create cost or latency pressure.** M3 keeps compilation
  asynchronous, bounded, reversible, observable, and initially disabled/shadow
  controlled.

## End-to-end success criteria

The initiative is complete only when a representative managed session crosses
the token threshold or terminates, produces exactly one accepted evidence-linked
four-record checkpoint through the exact direct-Pro route, updates rolling/final
synthesis, remains searchable and correctable through all five controls, can
form a reviewed revision-applicable promotion with preserved contradictions,
and can consolidate repeated paper cuts into one reversible ticket-backed item.
The same proof must cover restart/duplicate/partial failure, old stores, file/DB
where supported, the complete producer/backend matrix, native ordering and
causal lineage, read-only reconciliation, authorization/privacy, schema
evolution, disable/rollback, and zero change to primary execution, acceptance,
custody, result, or delivery.

## History and initialized-plan custody

Historical chain `chain-c256f171485f` initialized plan
`m1-durable-capture-cursors-20260713-2045` on 2026-07-13. It was never
implemented and is not complete. Its exact five-milestone inputs remain under
`archive/20260713-initialized-five-milestone/`.

The later 11-sprint mechanical resize is preserved under
`archive/20260716-eleven-sprint-resize/`. It was also planning only and is
superseded for future execution. Neither archived chain is a predecessor,
completion signal, or resume source. Any future authorized run must start from
root `chain.yaml` with fresh chain state.

## Canonical index

- `NORTHSTAR.md` — unchanged durable product destination and invariants.
- `chain.yaml` — canonical current chain front door.
- `chain-v3-20260716.yaml` — current three-sprint versioned chain.
- `briefs/` — the three current sprint briefs.
- `decisions/managed-execution-observation-lineage.md` — accepted current
  architecture, ownership boundary, lineage, adapter coverage, projections,
  and non-mutating proof strategy.
- `notes/tightening-20260716.md` — scope ledger, architecture challenge,
  deferrals, estimates, and custody decision.
- `research/epic-wide-managed-agent-capture-architecture-20260716.md` — the
  hash-preserved resident architecture source; curated into the decision above
  and retained as evidence rather than current runtime truth.
- `research/conversation-audit-20260713.md` — authoritative original discussion
  reconstruction and provenance.
- `notes/megaplan-prep-20260713.md` — historical five-milestone sizing record,
  retained as provenance and superseded for current scheduling.
- `archive/` — initialized five-milestone and later 11-sprint planning evidence;
  neither archive is current truth.

## Launch boundary

These are planning and architecture assets only. No compiler, adapter,
projection, or reconciler implementation exists by virtue of this integration.
No chain or plan was launched or resumed, and no product code, push, PR,
deployment, service restart, or external state change is authorized by this
revision. `driver.auto_approve` is `false`; failure or escalation stops the
chain.
