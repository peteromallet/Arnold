# Neutral Managed-Agent Lifecycle and Compiler Boundary

Status: accepted for epic planning; implementation decisions G1-G8 remain gated

Date: 2026-07-16

## Provenance

This decision curates the primary architecture research at
[`../research/managed-agent-lifecycle-standardization-architecture-and-migration-20260716.md`](../research/managed-agent-lifecycle-standardization-architecture-and-migration-20260716.md),
produced by durable run `subagent-20260716-155100-6d5344d7`. The raw durable
run record is
`.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`
(SHA-256 `74492ebbf31a7b96f3b0214bc4bf47abd05133760477fd1251968ba6eb5a7f10`).
The research evidence cut compared project revision `72f7eec32b3fdf8f5027a415d97f0e14716773f4`
with pinned resident runtime revision `c267920b6719fb35636e1da0071b5863ec5b2a0c`.
Implementation must re-inventory the selected target revision; neither research
nor planning prose is runtime proof.

This decision also preserves the still-valid evidence/authority substance of
[`../research/epic-wide-managed-agent-capture-architecture-20260716.md`](../research/epic-wide-managed-agent-capture-architecture-20260716.md)
and the original product intent in
[`../research/conversation-audit-20260713.md`](../research/conversation-audit-20260713.md).

## Decision

Use one lower-level, transport-neutral managed-agent lifecycle as the durable
execution/evidence substrate called by resident delegation, Megaplan workers,
and automatic managed-run controllers. Discord is an ingress and terminal-
delivery adapter, not the lifecycle. Megaplan and other callers retain every
policy decision above launch mechanics.

Introduce additive schemas:

- `arnold-managed-agent-launch-v3`: immutable logical-run/task-revision,
  attempt, lineage, origin/role, orchestrator correlation, route-policy ref,
  authority/privacy, delivery owner, compiler policy, budgets, workspace/evidence
  refs, and a canonical digest;
- `arnold-managed-agent-event-v3`: append-only per-run/per-stream sequence,
  typed lifecycle/output/tool/token/artifact/delivery/compiler events, causal
  refs, idempotency, evidence refs, authority/privacy snapshots, and producer
  revision; and
- `arnold-managed-agent-session-v3`: a query projection rebuildable from the
  journal, including all attempts, provider capabilities/session receipts,
  terminal/result/delivery refs, and compiler cursors.

One `run_id` identifies one immutable logical task revision. Every actual
provider/process start receives an `attempt_id`; retry/fallback is a new attempt
authorized by caller policy, never a lifecycle policy decision. One attempt may
start at most once. A changed task digest creates a new run linked by
`continuation_of_run_id`.

Adapters expose `prepare`, `start`, `observe`, `resume|follow_up`, `cancel`,
`collect`, and `capabilities`. Unsupported operations are explicit. The
lifecycle records the caller-approved route/fallback decision but cannot select
or broaden it.

## Ownership boundary

| Owner | Retained authority | Lifecycle/Compiler consumption rule |
|---|---|---|
| Discord corrective | immutable ingress provenance, message lifecycle, durable acknowledgement/terminal outbox, retries, provider delivery receipt | lifecycle references opaque transport provenance; only the declared root/delivery owner may create delivery intent |
| Resident | root-turn/conversation policy, delegation intent, relationship/aggregation and completion synthesis | calls the lifecycle; does not reimplement process supervision |
| Megaplan | phases, profiles, fallback/retry/rework, gates, modes, execution binding, chain/milestone progression, approvals and acceptance | supplies immutable policy/correlation refs and consumes results/receipts |
| Run Authority | grants, fences, claims/decisions and quarantine | lifecycle validates and references current grants; never mints them |
| WBC | execution-attempt/effect evidence, boundary contracts/receipts/findings and supported-runtime conformance | lifecycle journals/projections do not compete with the WBC ledger; exact refs or declared gaps only |
| Custody | action target/occurrence, lease/epoch, transfer/reclaim and reconciliation authority | lifecycle execution/delivery receipts bind to current custody; projections never authorize |
| Backend adapter | provider translation and capability/evidence normalization | cannot expand authority, decide orchestration, or deliver to the user |
| Knowledge compiler | eligible evidence consumption, checkpoints, four records, synthesis/correction/search, promotion candidates and paper-cut consolidation | asynchronous and non-mutating; derived records never become execution authority |
| Ticket system | actionable issue identity/status and ticket authority | compiler uses an idempotent adapter; adapter failure cannot gate compilation or delivery |

## Journal, identity, and evidence rules

- Custodian sequence is strict within `run_id + stream`; causality joins streams
  and runs. Occurrence, persistence, capture, ingestion, decision, and terminal
  timestamps remain separate UTC facts.
- Launch and event idempotency conflicts append anomalies and never overwrite
  the first accepted record. Reconciliation adopts an already-started effect.
- Immutable evidence refs contain store kind, locator, digest, exact native
  range/event, schema/media type, producer revision, recorded time, and access-
  policy ref. Mutable paths are hints only.
- V1/v2 readers and fixtures remain. V3 writers begin behind per-seam flags.
  Dual records carry `projection_of`; backfill records unknown instead of
  fabricating lineage, tokens, authority, privacy, or delivery.
- Execution custody and delivery custody remain distinct. Discord outbox retry,
  chain retry, repair retrigger, and provider retry use different idempotency
  domains.

## Compiler inclusion decision

An event is eligible for semantic compilation only when its schema and stream
are known, its launch policy is `include`, its role is eligible primary work,
its origin is not compiler/status/auditor/delivery projection, it is not a
projection of another view, the evidence is authorized, the session is the
canonical evidence owner for its `compilation_unit_id`, and the immutable source
range has not already been compiled under the policy version.

- Resident root conversation and terminal reply: excluded; they are canonical
  conversation/delivery projections, not child work.
- Compiler, status observer, progress auditor, delivery verifier, queue/watchdog
  controller, and meta-repair observer prose: excluded; their operational events
  remain available.
- Actual repair reasoning/change worker: included under its own bounded evidence.
- Retry/fallback: same logical unit, distinct attempt, non-overlapping ranges.
- Continuation with unchanged task digest: same run/unit; changed objective: new
  linked run/unit.
- Internal contributor: distinct unit only when declared independently reusable;
  otherwise `defer_to_owner` and the synthesis owner is canonical.
- Manifest/log/receipt/Store/legacy projections of one source: one canonical
  evidence owner and `projection_of` deduplication.

Compiler capture occurs only after source persistence. Roughly 100,000 newly
persisted eligible tokens or a completed/failed/cancelled/superseded logical
terminal state creates eligibility. Cursor progress is native stream sequence +
source digest + checkpoint, not a comparison of unrelated provider cursors.

## Migration and sequencing decision

The critical path is L1 -> L2 -> L3 -> C1 -> C2 -> C3 -> C4 -> C5.

- **L1:** freeze approved v3 vocabulary/package/store contracts, implement the
  journal/projection in shadow mode, normalize known v2 evidence, and establish
  Codex/Claude/Hermes conformance without changing a launch route.
- **L2:** dual-record resident delegation/follow-up/cancel/result/delivery and
  watchdog/repair/meta-repair/auditor/fixer routes; prove no duplicate starts,
  root-only delivery, restart adoption, exclusions, parity, and one-flag rollback.
- **L3:** wrap the shared Megaplan worker seam; preserve `WorkerResult`, phase
  artifacts/verdicts, route/fallback/session rules, gates, retries/rework,
  chain/acceptance/approval, and migrate in risk order with rollback.
- **C1-C5:** retain the original compiler split—capture/cursors, four-record
  extraction, synthesis/search/controls, promotion/contradictions, and paper-cut
  consolidation/operational proof—against the normalized lifecycle evidence.

C1 may prototype against L1/L2, but its capture-completeness acceptance is
blocked until L3's launch-seam registry and anti-recursion matrix pass.

## Decision gates

The following remain open and must have named approval evidence before use:

1. **G1 package ownership (Arnold architecture owner):** approve preferred
   `arnold/agent/lifecycle/` or another stable neutral Arnold package. Blocks L1
   implementation/import freeze.
2. **G2 journal authority/transactions (Store and WBC owners):** approve
   Store/DB authority, filesystem fallback/replication, and result/outbox/WBC
   transaction boundaries without a competing ledger. Blocks L1 persistence.
3. **G3 profile/fallback dependency (initiative owners):** bind to an accepted
   `sequential-model-fallbacks` handoff or restrict this epic to lifecycle-owned
   interfaces. Blocks L1 adapter freeze and prevents scope absorption.
4. **G4 privacy/retention (privacy/security owner):** approve classifications,
   audiences, raw evidence readers, retention/deletion, and promotion targets.
   Blocks schema freeze and real ingestion.
5. **G5 backend capability floor (runtime owner):** approve explicit optional
   capabilities or a stricter provider minimum using conformance evidence.
   Blocks adapter freeze/cutover.
6. **G6 compilation grouping (compiler product owner):** approve independent
   contributor units versus `defer_to_owner` rules using nested/retry fixtures.
   Blocks C1 eligibility acceptance.
7. **G7 promotion review tiers (product/security owners):** approve automated-
   assistance and mandatory-human risk classes. Blocks C4 accepted promotions.
8. **G8 per-seam retirement (runtime/service owner):** after conformance,
   representative full-chain parity, resident/repair restart proof, compiler
   non-recursion, rollback rehearsal, two approved observation windows, and
   explicit human approval, decide keep/dual/cutover/retire. Blocks only actual
   old-path deletion or broad enablement.

Every gate record must name owner, selected option, evidence refs, scope,
effective revision, date, and consequences. Missing approval is a typed blocker;
the planner may not convert a recommendation into approval.

## Rollback and retirement

Shadow mode records one real execution in old and new formats; it never invokes
a second model. Before cutover, v3 record/projection/compiler failure is nonfatal
and creates anomaly evidence. After an approved seam cutover, reservation fails
closed before start; after start, reconciliation adopts instead of relaunching.

Per-origin flags select old+shadow, v3+dual record, or old-only rollback.
Backend routing flags remain separate. Rollback preserves v3 evidence and
compiler cursors. Historical readers remain through an approved retention
window. Implementation completion may prove retirement readiness, but no old
start path is deleted and no production path is enabled without G8.

## Consequences

- The eight-sprint epic is longer than the superseded three-sprint tightening
  because lifecycle migration is a prerequisite product contract, not merely
  more compiler adapters.
- The older five compiler concerns remain explicit and reviewable rather than
  being compressed into three overloaded implementation slices.
- Neighboring initiatives remain authoritative for profile/fallback/nested
  custody and Discord delivery; this epic consumes their versioned handoffs.
- Operational dashboards, auditors, and projections can be comprehensive
  without becoming semantic source material or positive authority.
- Production deployment, restart, enablement, observation windows, and path
  retirement remain separate operational acts beyond this planning revision.
