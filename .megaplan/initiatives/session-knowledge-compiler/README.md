# Durable Session Knowledge Compiler

This initiative is the canonical execution plan for the Durable Session
Knowledge Compiler and its prerequisite Neutral Managed-Agent Lifecycle
Standardization. It does not create a second initiative or make Discord the
agent runtime. `NORTHSTAR.md` is the locked end-state authority; `chain.yaml`
is the only current executable chain input.

## Current truth

The epic contains eight ordered sprint-equivalents, each estimated at roughly
two weeks of skilled human engineering including design, implementation, tests,
review, and its handoff. The first three establish a transport-neutral v3
lifecycle and migrate launch seams without moving caller policy. The final five
preserve the original compiler decomposition: capture, extraction, synthesis,
promotion, and paper-cut consolidation/operational proof.

The primary research input is
[`research/managed-agent-lifecycle-standardization-architecture-and-migration-20260716.md`](research/managed-agent-lifecycle-standardization-architecture-and-migration-20260716.md).
It was produced by durable run `subagent-20260716-155100-6d5344d7`; the raw
run manifest remains the primary run record at
`.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`
(SHA-256 `74492ebbf31a7b96f3b0214bc4bf47abd05133760477fd1251968ba6eb5a7f10`).
The curated decision in
[`decisions/neutral-managed-agent-lifecycle-and-compiler-boundary.md`](decisions/neutral-managed-agent-lifecycle-and-compiler-boundary.md)
is current planning truth. Research is evidence, not implementation status.

| Order | Milestone | Sprint outcome | Difficulty / run shape |
|---:|---|---|---|
| 1 | L1 | Additive v3 envelope, journal, projection, and backend conformance in shadow mode | 5/5, `partnered-5/full/high +prep` |
| 2 | L2 | Resident delegation and automatic managed runs dual-record v2/v3 with parity and rollback | 5/5, `partnered-5/full/high +prep` |
| 3 | L3 | Megaplan worker seams use the lifecycle while Megaplan keeps phase, gate, retry, chain, and approval ownership | 5/5, `partnered-5/full/high +prep` |
| 4 | C1 | Durable compiler observation, cursor, trigger, atomic checkpoint, and anti-recursion substrate | 5/5, `partnered-5/full/high +prep` |
| 5 | C2 | Direct-Pro bounded extraction and four evidence-linked record contracts | 5/5, `partnered-5/full/high +prep` |
| 6 | C3 | Rolling/final synthesis, append-only correction, scoped search, and five agent controls | 5/5, `partnered-5/full/high +prep` |
| 7 | C4 | Repository/revision-aware promotion, contradiction, review, supersession, and invalidation | 5/5, `partnered-5/full/high +prep` |
| 8 | C5 | Reversible paper-cut consolidation, ticket adapter, compatibility, observability, and offline conformance proof | 4/5, `partnered-5/full/high +prep` |

`partnered-5` and `full` are retained throughout because local green tests can
miss non-local authority, privacy, duplicate-start, evidence-lineage, or stale-
promotion failures. High planning depth is selected because every sprint must
reconcile multiple current runtimes and durable contracts; critique/gate/review
depth remains profile-controlled. C5 scores 4/5, but stays on the default
`partnered-5` because its producer/backend matrix can false-green while omitting
an execution seam.

## Dependency graph and handoffs

```text
L1 lifecycle contract + journal
  -> L2 resident/automatic dual recording
    -> L3 Megaplan phase migration
      -> C1 compiler capture acceptance
        -> C2 evidence extraction
          -> C3 synthesis/search/controls
            -> C4 promotion governance
              -> C5 consolidation + operational proof
```

The chain is intentionally serial. C1 design may be explored against L1/L2,
but C1 cannot be accepted until L3 proves one canonical compilation unit across
all in-scope launch seams.

| Producer | Required reviewed handoff consumed by successor |
|---|---|
| L1 | `docs/managed-agents/handoffs/l1-lifecycle-contract.json` plus schema, journal, capability, and decision-gate receipts |
| L2 | `docs/managed-agents/handoffs/l2-v2-v3-parity.json` plus seam flags, anomaly inventory, and rollback proof |
| L3 | `docs/managed-agents/handoffs/l3-megaplan-cutover.json` plus launch-seam registry and compiler coverage matrix |
| C1 | `docs/session-knowledge-compiler/handoffs/c1-accepted-checkpoints.json` with cursor/trigger/atomicity contract |
| C2 | `docs/session-knowledge-compiler/handoffs/c2-four-record-contract.json` with exact route and validation contract |
| C3 | `docs/session-knowledge-compiler/handoffs/c3-synthesis-search-controls.json` with correction/query/promotion-candidate APIs |
| C4 | `docs/session-knowledge-compiler/handoffs/c4-promotion-governance.json` with applicability/review/contradiction contract |
| C5 | `docs/session-knowledge-compiler/handoffs/c5-completion-evidence.json` mapping every North Star measure to proof |

Each handoff is content-addressed, names the implementation revision and test
commands, records unresolved gaps, and is reviewed before the successor starts.
A missing or unreviewed handoff blocks the successor; prose status does not
satisfy the dependency.

## Locked decisions

- Use a new additive `arnold-managed-agent-launch-v3`, event journal, and
  rebuildable session projection. Existing v1/v2 records remain readable and
  are never silently reinterpreted.
- Discord remains ingress and durable terminal-delivery/outbox custody only.
  Non-Discord work never depends on Discord and children never deliver directly.
- The neutral lifecycle owns launch mechanics, stable logical run/attempt
  identity, journal/evidence, liveness, follow-up/cancel mechanics, execution
  custody receipts, and terminal result receipts. It does not select or approve
  work, change profiles, decide retries/rework, progress a chain, or synthesize
  a user reply.
- Megaplan retains phase topology, profiles, gates, retries, rework, execution
  binding, milestone/chain progression, approvals, and acceptance. Run
  Authority, WBC, Custody, delivery systems, and ticketing retain their current
  positive authority.
- One `run_id` represents one logical task revision; provider/process retries
  receive new `attempt_id` values. At-most-one start is enforced per attempt.
- Events are append-only and ordered within a run/stream by native sequence;
  cross-run order uses causal refs, never wall-clock guesses.
- Compilation uses deterministic `include|exclude|defer_to_owner` policy,
  `projection_of` links, immutable source-evidence keys, and one
  `compilation_unit_id` so compiler, auditor, observer, controller, delivery-
  verifier, retry, and duplicate projection prose cannot recurse or double count.
- The compiler consumes only durably persisted evidence after commit. It
  checkpoints at roughly 100,000 newly persisted eligible tokens and at
  completed, failed, cancelled, and superseded logical terminal states.
- Compiler extraction uses only `hermes:deepseek:deepseek-v4-pro` through
  provider `direct`, with bounded input/output/cost/attempts and no silent
  provider or model fallback.
- Activity, reusable knowledge, paper-cut observation, and improvement
  candidate remain four distinct append-only record families. Claim kind,
  evidence, applicability, actor, confidence, and compiler provenance remain
  explicit.

## Pre-execution decision gates

These are real authority/product choices. They must be resolved in a durable
decision record before the named milestone executes; planning completion does
not invent their answers.

| Gate / owner | Options and evidence required | Blocking effect |
|---|---|---|
| G1 package ownership — Arnold architecture owner | Prefer `arnold/agent/lifecycle/`; alternative must be a stable transport-neutral Arnold package. Require import/topology audit and ownership review. | Blocks L1 production package and public imports; schemas/fixtures may be drafted only in the approved location. |
| G2 journal authority/transactions — Store + WBC owners | Choose canonical Store/DB authority and filesystem fallback/replication semantics. Require file/DB transaction proof, WBC ledger ownership check, result/outbox atomicity analysis, and no-competing-ledger review. | Blocks L1 persistence implementation and any cutover. |
| G3 neighboring profile/fallback dependency — initiative owners | Consume an accepted `sequential-model-fallbacks` handoff if available, or implement only lifecycle-owned adapter/custody interfaces while leaving route policy external. Require revision/proof-map comparison. | Blocks L1 adapter freeze; does not allow this epic to absorb resolver/fallback policy. |
| G4 privacy/retention — privacy/security owner | Approve classifications, audience intersection, retention/deletion behavior, raw log/tool-trace readers, and promotion audiences. Require current source-store policies and deletion obligations. | Blocks L1 schema freeze and any real evidence ingestion. |
| G5 backend capability floor — runtime owner | Explicit optional capabilities (recommended) versus requiring follow-up/cancel for every enabled provider. Require Codex/Claude/Hermes capability fixtures and product needs. | Blocks L1 adapter conformance freeze and later provider cutovers. |
| G6 compilation grouping — compiler product owner | Contributors compile independently only with a distinct unit, or defer to a declared synthesis owner. Require representative nested/retry/rework fixtures and duplication analysis. | Blocks C1 eligibility policy acceptance. |
| G7 promotion review tiers — product/security owners | Define which narrow provisional claims may use automated assistance and which require human authority. Require risk-class matrix and authorization tests. | Blocks C4 acceptance/promotion writes. |
| G8 per-seam retirement — runtime + service owner | Keep dual path, cut over with rollback, or retire old start path. Require all retirement criteria, two approved observation windows, rollback rehearsal, and explicit human approval for each seam. | Never blocks implementing/shadowing the epic; blocks deleting an old launch path or broad production enablement. |

## In scope

- Neutral v3 launch/session/event contracts; append-only journal and projections;
  v1/v2 dual-read/dual-record compatibility; Codex/Claude/Hermes capability
  conformance; resident, repair/auditor, and Megaplan seam migration in shadow
  and reversible cutover-ready form.
- Stable workflow -> epic/chain -> milestone -> plan -> phase/step -> attempt ->
  agent-run lineage; origin/role taxonomy; authority/privacy snapshots;
  immutable evidence refs; cancellation/follow-up/result/delivery receipts.
- Compiler trigger/cursor/checkpoint persistence, four record schemas, bounded
  extraction, synthesis, correction, scoped retrieval, five agent controls,
  reviewed promotion, contradictions, and reversible backlog consolidation.
- Complete launch-seam and producer/backend matrices; file/DB compatibility;
  read-only reconciliation; deterministic replay; content-safe diagnostics;
  safe disable/rollback; a redacted, non-mutating offline real-epic proof.

## Out of scope and anti-scope

- No chain/plan launch, code implementation, push, remote merge, deployment,
  service restart, production enablement, or old-path retirement is performed by
  these planning assets.
- Do not route all agents through Discord or create a parallel Discord/resident
  loop, authority ledger, event bus, queue/lease service, database, scheduler,
  promotion service, delivery system, or ticket authority.
- Do not let lifecycle/launcher code decide Megaplan policy, grant authority,
  self-approve, retry/rework a plan, progress a chain, transfer custody, or
  deliver a user-visible result.
- Do not treat PIDs, clocks, mutable status, logs, projections, transcripts,
  tool output, or fluent agent prose as positive authority.
- Do not launch twice in shadow mode, fabricate unsupported provider features,
  guess legacy lineage/privacy/tokens, compile observer/compiler/delivery prose,
  auto-promote authoritative knowledge, auto-adjudicate contradictions, delete
  observations, auto-implement backlog work, or build a general RAG platform.

## Epic done criteria

The epic is complete only when all eight reviewed handoffs exist and tests prove:

- every in-scope launch seam has one immutable envelope/logical run identity,
  one-start attempts, terminal/orphan diagnosis, safe restart adoption, exact
  authority/privacy lineage, and explicit provider capability evidence;
- Megaplan artifacts, verdicts, routes, retries, modes, chain behavior,
  approval/acceptance, and Discord/root-only delivery remain equivalent and
  owned by their original components under shadow comparison;
- compiler inclusion produces one semantic unit per underlying work unit with
  no compiler/auditor/status/controller/delivery recursion or duplicate views;
- threshold and every terminal trigger commit exactly one four-record checkpoint
  through the exact direct-Pro route; failures never advance the cursor or
  alter primary execution/acceptance/custody/result/delivery;
- rolling/final synthesis, correction, scoped search, all five controls,
  repository/revision-aware promotion, contradiction handling, and paper-cut
  consolidation preserve complete evidence and supersession lineage;
- mixed v1/v2/v3 history, file/DB backends, late/out-of-order/duplicate/concurrent
  events, rollback, and projection rebuild pass; the complete producer/backend
  matrix has no silent gaps; and the redacted offline replay is non-mutating.

Production deployment, broad enablement, two real release observation windows,
and per-seam retirement approvals remain operational follow-ons. Their absence
does not permit the implementation chain to claim a retired or deployed path.

## Canonical index and history

- `NORTHSTAR.md` — locked product destination, invariants, success measures, and
  anti-scope.
- `chain.yaml` — current eight-milestone executable chain specification.
- `briefs/` — exactly eight current self-contained milestone briefs.
- `decisions/neutral-managed-agent-lifecycle-and-compiler-boundary.md` — current
  architecture, ownership, gates, and sequencing decision.
- `notes/megaplan-prep-20260716.md` — current sizing and per-sprint run-dial record.
- `handoff/epic-handoff-contract.md` — cross-milestone artifact requirements.
- `research/managed-agent-lifecycle-standardization-architecture-and-migration-20260716.md`
  — primary research from durable run `subagent-20260716-155100-6d5344d7`.
- `research/epic-wide-managed-agent-capture-architecture-20260716.md` and
  `research/conversation-audit-20260713.md` — comparative architecture and
  original product provenance.
- `archive/` — superseded initialized-five, eleven-sprint, and three-sprint
  planning records. None is a current execution input.

Historical chain `chain-c256f171485f` initialized only its old M1 planning state
and completed no implementation. It is not a predecessor, resume source, or
completion signal. Any future authorized run starts fresh from `chain.yaml`.

## Launch boundary

This revision changes planning assets only. It does not claim any lifecycle or
compiler implementation, initialize or start Megaplan, resume the historical
chain, execute a model worker, push, open/merge a remote PR, deploy, enable,
restart, or retire anything. The chain stops on failure/escalation and keeps
`driver.auto_approve: false`; any future execution requires separate authority.
