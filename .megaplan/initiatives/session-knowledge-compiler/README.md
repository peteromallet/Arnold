# Durable Session Knowledge Compiler

Build a small, automatic, evidence-linked compiler for every managed agent
session. It turns new persisted session evidence into durable activity,
reusable knowledge, paper-cut observations, and improvement candidates without
changing the managed session's outcome or terminal-delivery path.
`NORTHSTAR.md` remains the end-state authority.

## Current truth

The current plan is **three ordered implementation sprints**, each estimated at
roughly two skilled-human weeks. This is a planning estimate, not a delivery
guarantee. The canonical chain entry point is `chain.yaml`, which resolves to
`chain-v3-20260716.yaml`; only the three briefs directly under `briefs/` are
current execution inputs.

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
| Cover every managed agent/subagent with canonical identity and exact evidence ranges; primary transcripts, tool events, logs, manifests, files, commits, and tests remain authoritative | M1 | Resident and automatic-repair fixtures resolve exact half-open ranges; invalid or ambiguous references fail validation |
| Compile at roughly 100,000 **newly persisted** tokens and on completed, failed, cancelled, and superseded terminal states, including terminal ranges below threshold | M1 | Threshold, below-threshold, all-terminal, late-event, reset, retry, and out-of-order tests |
| Durable immutable checkpoints, atomic cursor advancement, idempotency, restart/concurrency safety, visible retryable failure, and no impact on primary completion/delivery | M1 | Duplicate, restart, concurrent claim, partial-write, model/schema/store failure, and terminal-isolation tests |
| Separate activity, reusable knowledge, paper-cut observation, and improvement-candidate records | M1 | Versioned schema and file/DB round-trip fixtures prove four distinct record types committed atomically |
| Preserve observed/performed/inferred/proposed/unverified claim kind, evidence links, applicability, actor, confidence, and reproducible compiler provenance | M1 | Deterministic validation rejects missing kinds, proposal-as-performed, unauthorized/out-of-range evidence, partial output, and secret-bearing provenance |
| Use bounded extraction through canonical `hermes:deepseek:deepseek-v4-pro` with provider `direct`, with no silent fallback and transcript content treated as data | M1 | Route metadata, bounded fake integration, injection, cost/size, chunk/gap, unsafe-fallback, and retry tests |
| Versioned rolling synthesis and terminal final synthesis, with append-only claim/synthesis correction and complete lineage | M2 | Multi-checkpoint, terminal-below-threshold, rebuild, correction, supersession, active-view, and history tests |
| Near-invisible automatic operation plus `record-learning`, `record-friction`, `correct-summary`, `search-session-knowledge`, and `propose-promotion` | M2 | Positive/negative schema, actor, authorization, pagination, no-tool automatic path, and no-bulk-prompt-injection tests |
| Scoped evidence-aware search across records and syntheses without presenting proposed, unverified, stale, or out-of-scope material as current fact | M2 | Repository/session/revision authorization, pagination, applicability, active/superseded, and leakage tests |
| Explicit evidence-linked project promotion with repository/version/commit/path applicability, authority-proportionate review, contradiction preservation, supersession, and invalidation | M2 | Accept/reject/more-evidence/narrow, strong-review, contradiction/adjudication, divergence/rebase/stale, supersession, and invalidation tests |
| Consolidate recurring paper cuts into explainable, reversible, prioritized backlog work without deleting observations; integrate idempotently with existing tickets | M3 | Merge/split/relate/reopen/ranking/lineage and duplicate-ticket/adapter-failure tests |
| Backward-compatible file/DB storage, inherited privacy/redaction/access rules, bounded cost/concurrency/retries, diagnostics, safe retry, disable/rollback, and representative backend proof | M3 | Additive migration, old-store load, metrics-no-content, rollout-state, rollback/re-enable, resident plus repair-backend conformance, operator/agent docs, and full failure matrix |

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
where supported, resident and automatic-repair paths, authorization/privacy,
disable/rollback, and zero change to primary-session result or delivery.

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
- `notes/tightening-20260716.md` — scope ledger, architecture challenge,
  deferrals, estimates, and custody decision.
- `research/conversation-audit-20260713.md` — authoritative original discussion
  reconstruction and provenance.
- `notes/megaplan-prep-20260713.md` — historical five-milestone sizing record,
  retained as provenance and superseded for current scheduling.
- `archive/` — initialized five-milestone and later 11-sprint planning evidence;
  neither archive is current truth.

## Launch boundary

These are planning assets only. No chain or plan was launched or resumed, and
no product code, push, PR, deployment, service restart, or external state change
is authorized by this revision. `driver.auto_approve` is `false`; failure or
escalation stops the chain.
