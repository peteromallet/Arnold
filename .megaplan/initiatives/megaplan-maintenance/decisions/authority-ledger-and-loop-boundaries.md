# Decision: one ledger, separate loops, canonical custody

Status: proposed for human approval before M2 enforcement; editorially locked for planning.

## Stage 3 revalidation — 2026-08-10

This decision survives, but its ownership language is narrowed to current
architecture. “One ledger” means the existing Maintenance-owned incident ledger
extended with Maintenance observations and immutable owner-record references.
It is not an omnibus ledger and must not copy or replace the WBC M6A attempt/effect
store, M7 Custody lease/epoch history, Run Authority records, Native C1/C2
divergence ledger, or any owner-specific projection. The four stale duplicate
briefs are historical and are not decision inputs.

M2/M3 consume the accepted Custody M6A–M11 and Native Parity C1/C2/S1/S2R
substrate, including exact store incarnation, restore generation, and
raw-history high-water coordinates. M4 uses the existing event
trigger, repair queue, resident occurrence scheduler, and `next_three_hour`
reconciliation backstop; the six-hour name is compatibility-only. Runtime/fixer
resolution follows the Aug 7–9 manifest-first design, and source-only handoffs do
not prove installation. Maintenance contracts remain under
`arnold_pipelines/megaplan` and consume neutral `arnold.*` seams one way; they do
not fork platform stores, validators, leases, completion, or controlled writers.

## Decision

Extend the existing append-only Maintenance incident ledger into the maintenance control plane. Do not create a second operational or analytics ledger, and do not turn the Maintenance ledger into an omnibus copy of owner-specific histories. Store immutable typed Maintenance events plus references/digests/cursors and build independent projections for operational custody, verification, and efficiency analysis.

The six-hour loop is an operational unblocker. It can observe, classify, join/enqueue one deduplicated repair request, invoke only pre-approved safe policy through canonical repair custody, and schedule independent verification. It never writes plan/chain truth directly.

The 24-hour loop is an efficiency auditor. It can compute censored/cohort metrics, cluster recurrence, and append deduplicated ticket proposals. It cannot claim repair custody, change routing/profile/budget, materialize tickets without policy, or edit an active plan/chain.

Run Authority remains authoritative for grants, attempts, accepted decisions, fences, and quarantine. The canonical lifecycle TransitionWriter and repair custody remain the only plan/chain mutation authorities.

## Contract

Each event includes:

- stable event/schema identity and environment/tenant/run/chain/plan/stage/model/profile/attempt identity;
- event time, observation time, half-open window, watermark, and lateness/correction reference;
- normalized fingerprint, occurrence ID, root-cause cluster ID, severity, confidence, classifier version, alternatives;
- immutable evidence references with digest, cursor/sequence, source version, freshness, and coherence;
- wall/idle time, tokens, cost, retry/duplicate counts, accepted-output delta, and estimated avoidable portion;
- requested/taken action, owner, idempotency key, lease, fencing token, lifecycle, deadline, and human authority;
- parent/recurrence/supersession/ticket links;
- independent verifier, blocker-specific negative control, cleared fingerprint, resumed-progress proof, and delayed checkpoints.

Observation envelopes capture all read versions before deciding. Torn, stale, incomplete, or cross-environment input is typed unknown/incoherent. Lease fences increase monotonically. Replay is deterministic and append-only; late inputs produce correction events.

## Consequences

Parallelism is safe for immutable observation, validation, per-run classification, investigation, and independent cluster analysis. One synthesizer per window produces deterministic output. Repair claim/effects, TransitionWriter changes, terminal verification, cluster merge/proposal emission, ticket materialization, and human approvals are serialized and fenced.

The design favors false negatives over unauthorized intervention during cold start. Static conservative SLOs govern until 30 comparable completed samples across 5 plans exist; stronger tail/regression recommendation claims require 100 samples across 10 plans.

## Human decisions retained

Event-store backend/retention/access policy; identity and lateness fields; lease/grace durations; SLOs and cohort dimensions; cost source; repair allowlist; ticket auto-materialization; schedule timezone/offset; canary/promotion/rollback ownership; sensitive evidence handling.
