# North Star: Durable Knowledge from Every Managed Agent

## Locked destination

Every eligible managed execution—resident delegation, Megaplan worker,
implementation/review agent, retry/rework, nested contributor, and actual repair
worker—runs through one transport-neutral, backend-neutral managed-agent
lifecycle and automatically leaves a durable, searchable, correction-friendly
knowledge record. Discord remains an ingress and terminal-delivery adapter;
Megaplan remains the orchestration and acceptance owner; existing authority,
custody, WBC, privacy, and delivery systems remain authoritative.

The lifecycle gives every logical task revision a stable run identity, every
provider/process start a distinct at-most-once attempt identity, and every
durable fact an append-only journal event with immutable evidence, causal
lineage, authority/privacy scope, and explicit capability status. Codex, Claude,
Hermes, and future adapters expose the same lifecycle contract without
pretending unsupported follow-up, cancellation, token, or tool-trace features.

The knowledge compiler consumes committed lifecycle evidence asynchronously. It
creates immutable checkpoints at roughly 100,000 newly persisted eligible
tokens and at logical terminal states, while keeping activity, reusable
knowledge, paper-cut observations, and improvement candidates distinct. It can
fail without changing, delaying, retrying, or misreporting the primary work or
its delivery.

This is a knowledge compiler, not a lossy chat summary and not a new authority
plane. Raw transcripts, tool events, journals, manifests, logs, receipts,
commits, files, and tests remain primary; derived records make evidence useful
without replacing it.

## Load-bearing invariants

1. **Caller policy stays with its owner.** The lifecycle never decides whether
   work is authorized, which Megaplan phase runs, which profile/fallback policy
   applies, whether a gate passes, whether to retry/rework, whether a chain
   advances, or who may deliver.
2. **Discord is not the runtime.** Discord owns immutable transport provenance
   and durable inbound/outbound delivery. Non-Discord execution and automatic
   recovery have no Discord dependency; internal agents never deliver directly.
3. **Logical runs and attempts are distinct.** One immutable task revision has
   one `run_id`; retries/fallbacks have new `attempt_id` values; a changed
   objective has a new linked run. One attempt starts at most once, including
   across crashes, adoption, reconciliation, and shadow recording.
4. **The journal is append-only.** Native per-stream sequence and causal refs
   define order. Timestamps record occurrence/persistence/observation/ingestion
   semantics but never invent a total order. Projections are rebuildable views.
5. **Compatibility is additive.** Existing managed v1/v2 evidence remains
   readable. V3 dual records cross-link to their source; unknown legacy lineage,
   tokens, privacy, authority, or capability stays unknown and is never guessed.
6. **Authority and privacy only narrow.** Children and derived records cannot
   exceed parent/source authority or audience. Credentials and secrets are not
   journaled. Reads enforce the intersection of evidence, current reader, and
   promotion-target policy.
7. **Evidence remains primary.** Every substantive lifecycle or knowledge claim
   resolves to immutable source evidence and exact range/event identity.
   Mutable paths, PIDs, names, clocks, logs, projections, and prose are not
   positive authority.
8. **Compilation is deterministic and non-recursive.** Stable origin/role,
   `include|exclude|defer_to_owner`, `projection_of`, source-evidence keys, and
   `compilation_unit_id` ensure one semantic unit per underlying work unit.
   Compiler, auditor, status observer, controller, projection, and delivery-
   verifier prose never compiles itself.
9. **Incremental work is durable and idempotent.** Each checkpoint covers an
   immutable range. Cursor advancement and all four validated records are one
   logical commit. Duplicate triggers, retries, partial writes, late events,
   out-of-order delivery, concurrent claims, and restarts never skip or double
   count a source range.
10. **Meaningful boundaries trigger compilation.** Compile after roughly
    100,000 newly persisted eligible tokens and on completed, failed, cancelled,
    and superseded logical terminal states, including below-threshold ranges.
    Idle compilation remains an explicit disabled policy until justified.
11. **Compilation is harmlessly asynchronous.** Capture performs no model or
    network work on the primary result/delivery path. Compiler/store/model/
    authorization/ticket failure is visible and retryable but never changes
    execution, approval, acceptance, custody, result, or delivery.
12. **Outputs remain distinct.** Activity, reusable knowledge, paper-cut
    observation, and improvement candidate are separate versioned records with
    claim kind, evidence, actor, applicability, confidence, and provenance.
13. **Claims identify their truth status.** `observed`, `performed`, `inferred`,
    `proposed`, and `unverified` remain explicit. Proposed work never renders as
    performed and derived fluency never becomes authority.
14. **History is correctable, never rewritten.** Checkpoints, syntheses,
    corrections, contradictions, promotion decisions, and backlog membership
    are append-only. Active views may supersede but cannot erase history.
15. **Promotion is cautious.** Session knowledge becomes active project
    knowledge only through explicit evidence, repository/revision/path
    applicability, independent authorization, contradiction handling, and
    review strength proportionate to risk.
16. **Observations survive consolidation.** Repeated paper cuts may create one
    reversible prioritized ticket-backed item, but every source observation,
    membership change, scoring input, and evidence link remains addressable.
17. **The normal UX is nearly invisible.** Automatic compilation is default;
    `record-learning`, `record-friction`, `correct-summary`,
    `search-session-knowledge`, and `propose-promotion` add intent without
    mandatory bookkeeping or bulk corpus injection.

## Canonical derived records

- **Activity record:** goals, scope, actions actually performed, artifacts,
  commands/tests, results, failures, and unresolved work.
- **Reusable knowledge:** evidence-backed facts, decisions, techniques,
  constraints, and applicability that may help later work.
- **Paper-cut observation:** a source-preserving report of confusion, friction,
  workaround, reliability, performance/cost, discoverability, ambiguity, or a
  missing capability encountered in the run.
- **Improvement candidate:** proposed work linked to one or more observations,
  with impact, confidence, applicability, status, and review lineage.

## Measurable end-state proof

- A generated launch-seam matrix covers resident delegation and continuations;
  every Megaplan prep/plan/critique/gate/revise/finalize/execute/review worker,
  retries/rework and chain correlation; automatic repair/meta-repair/auditor
  roles; Codex, Claude, Hermes, and a future-adapter fixture—with no unclassified
  provider start.
- Conformance tests prove one-start attempts, restart adoption, cancel/follow-up
  capability truth, terminal/orphan diagnosis, immutable evidence, authority/
  privacy narrowing, v1/v2/v3 compatibility, parity, rollback, and no duplicate
  root/user delivery.
- Megaplan artifacts, verdicts, routes, profiles, fallback decisions, retries,
  modes, chain state, reviews, approvals, and acceptance remain equivalent and
  Megaplan-owned under migration.
- Compiler selection emits one semantic unit per logical work unit with no
  observer/compiler/delivery recursion or duplicate projection/range.
- Threshold and every terminal trigger atomically produce one complete four-
  record checkpoint through `hermes:deepseek:deepseek-v4-pro` via `direct`;
  forced failures leave cursor and primary work unchanged.
- Rolling/final synthesis, corrections, scoped search, five controls,
  repository/revision-aware promotion, contradiction adjudication, and
  reversible paper-cut consolidation retain full evidence and version lineage.
- File/DB and mixed-version replay, duplicate/concurrent/late/out-of-order/crash
  cases, read-only reconciliation, safe disable/rollback, and a redacted offline
  real-epic replay rebuild equivalent projections without source mutation.

## Anti-scope

- No universal Discord execution path, parallel resident loop, second authority
  ledger, generic event bus, sidecar database, standalone queue/lease service,
  promotion authority, delivery system, ticket authority, or scheduler.
- No lifecycle ownership of Megaplan planning, profiles, gates, retries,
  approvals, acceptance, chain progression, or user-facing synthesis.
- No double launch in shadow mode, guessed legacy precision, fabricated backend
  capabilities, secret-bearing provenance, or model/network call on the primary
  execution/delivery path.
- No compiler/auditor/status/controller/delivery self-ingestion, autonomous
  promotion/adjudication/code change, deletion of observations, general RAG or
  global ontology, production deployment/restart/enablement, or old-path
  retirement without its separate evidence and authority gates.
