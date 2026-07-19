# Epic-wide managed-agent capture architecture

Status: archived speculative research; superseded as current scheduling truth

Date: 2026-07-16

Initiative: `session-knowledge-compiler`

> Archival note (2026-07-16): this evidence was written against the superseded
> three-sprint tightening. The current eight-sprint chain and neutral-lifecycle
> decision at the initiative root are authoritative. Links below to the former
> M1-M3 inputs point to their archive; recommendations remain comparative
> evidence and are not implementation or current scheduling claims.

## Decision

**Recommendation:** extend the same Durable Session Knowledge Compiler with an
epic-scoped observation envelope, Megaplan lifecycle adapters, and layered
projections. Do not create a separate epic-capture service, authority ledger,
queue, or knowledge artifact family.

The compiler already owns evidence-linked derived knowledge, immutable
checkpoints, corrections, synthesis, and cautious promotion. Epic-wide capture
changes the scope and lineage of the evidence, not those semantics. A second
service would duplicate cursors, privacy rules, contradiction handling, and
promotion state while creating a second place that could be mistaken for run
truth. The epic synthesis is therefore another versioned compiler projection,
not a new source of truth.

The boundary is strict:

- Run Authority continues to own grants, attempts, decisions, fences, and
  quarantine.
- Workflow Boundary Contracts (WBC) continue to own supported-runtime
  execution-attempt/effect evidence and conformance.
- Custody continues to own action targets, repair occurrences, leases, epochs,
  transfer, and reconciliation.
- Megaplan continues to own planning, routing, task/rework policy, chain and
  milestone progression, and acceptance.
- The compiler owns only append-only **knowledge observations**, compilation
  checkpoints, summaries, corrections, contradictions, and promotion
  candidates derived from references to those source records.

This recommendation extended [the archived three-sprint initiative](../archive/20260716-three-sprint-tightening/README.md),
while preserving the [North Star](../NORTHSTAR.md), and consumes rather than duplicates
the ownership decisions in the
[WBC execution-attempt ledger](../../workflow-boundary-contracts/decisions/2026-07-11-kernel-execution-attempt-ledger.md)
and the
[composed Run Authority/WBC/Custody contract](../../custody-control-plane/decisions/single-authoritative-runtime-history.md).

## Evidence basis and labels

The following labels are used throughout:

- **Observation** — directly visible in inspected code, durable artifacts, or
  existing initiative records.
- **Inference** — a conclusion supported by multiple observations.
- **Recommendation** — proposed architecture, not implemented behavior.
- **Unknown** — unresolved evidence needed before implementation.

### Baselines inspected

| Baseline | Evidence state | Use |
| --- | --- | --- |
| `/workspace/arnold` | project revision `72f7eec32b3fdf8f5027a415d97f0e14716773f4`; materially dirty concurrent worktree | current project seams and in-flight source-admission/custody work |
| `/workspace/arnold-consolidation-20260714` | initiative pinned at `a3b2dffbb5d3be412ec82d749f079ebb886d450d`; clean checkout inspected at `d747fd7d43fdfa4ee7a87a1db3add62871cf44e3` | canonical tightened initiative and resident runtime |

The pinned revision is the commit titled `plan: tighten session knowledge
compiler to three sprints`. Its initiative inputs, now archived, are
[M1](../archive/20260716-three-sprint-tightening/briefs/m1-compiler-core.md),
[M2](../archive/20260716-three-sprint-tightening/briefs/m2-knowledge-use-governance.md), and
[M3](../archive/20260716-three-sprint-tightening/briefs/m3-consolidation-operational-proof.md).
They are historical evidence, not current scheduling inputs.

### Current source and lifecycle observations

1. **Observation — neutral managed runs.**
   `arnold_pipelines/megaplan/managed_agent.py` declares that the repair queue,
   watchdog, and chain runner decide whether work may run while this module owns
   execution evidence after that decision. `ManagedCommandSpec`,
   `reserve_managed_command`, `_new_manifest`, `_append_status`,
   `run_managed_command`, `_write_result`, and `transition_terminal` establish
   stable IDs, launch idempotency, `parent_run_id`, `retry_of_run_id`,
   `lineage_key`, status history, `manifest.json`, `result.json`, and `run.log`.
   The manifest is committed before process launch. Its status history is
   bounded to the latest 100 rows, so it is useful source evidence but is not a
   sufficient permanent event journal by itself.

2. **Observation — resident-managed agents and nested continuations.**
   `arnold_pipelines/megaplan/resident/subagent.py` uses
   `launch_codex_subagent_detached` as the durable launch boundary. It commits
   `prompt.md`, `manifest.json`, `run.log`, `result.md`, immutable launch and
   Discord provenance, query relationship, logical aggregation role, delivery
   outbox state, and optional parent/retry/lineage/continued-session fields
   before starting the supervisor. `follow_up_managed_subagent` creates a
   locked parent/child continuation lineage. `sweep_managed_agent_deliveries`
   owns retry-safe terminal delivery evidence. `resident/agent_loop.py` records
   structured tool-call audit rows and treats durable managed launches as
   custody handoffs.

3. **Observation — Megaplan phases and workers.**
   The shipped topology is prep, plan, critique, gate/revise, finalize,
   execute, and review. `runtime/inprocess_step.py:InProcessHandlerStep.run`
   exposes typed `StepResult`, verdict, state patch, and output artifacts for
   tests; production retains subprocess phase boundaries in `auto.py`.
   `workers/_impl.py:run_step_with_worker` is the shared model-worker seam and
   `WorkerResult` carries model/session identity, token usage, cost, attempt
   index, configured/attempted specs, failed-attempt reasons, and fallback
   trigger. `orchestration/phase_result.py:PhaseResult` and durable
   `phase_result.json` distinguish success, timeout, context exhaustion,
   malformed output, external error, and internal error.

4. **Observation — authoritative plan events are in transition.**
   `Store.events_for_plan` returns ordered `StoredEvent` records and
   `observability/events_projection.py` explicitly projects them into legacy
   per-plan `events.ndjson`. Separately, `cli/projection.py` reconstructs status
   from the native manifest journal and explicitly says `state.json` is not
   authority. `arnold/runtime/event_journal.py` supplies a locked append-only
   mechanism, while `arnold/workflow/execution_attempt_ledger.py` freezes the
   desired cross-runtime WBC identity and lifecycle schema. That WBC module
   explicitly remains schema-only at the pinned revision and documents missing
   transactional/outbox persistence. Universal producer adoption therefore
   must not be assumed.

5. **Observation — several convenience events are best effort.**
   `auto.py` emits `phase_start`, `phase_retry`, and `phase_end`, but catches
   event-write failures. `supervisor/chain_runner.py:run_chain` persists chain
   and supervisor state, then calls `incident_bridge.append_chain_lifecycle`
   through `_bridge_lifecycle`, which also swallows append failure. These rows
   are useful observations; they cannot be the sole authoritative capture seam.

6. **Observation — chain and milestone identity exists but is split.**
   `chain/spec.py:ChainState`, supervisor `RunRecord`s, plan state/artifacts,
   milestone acceptance receipts, and `chain/execution_binding.py` together
   carry the current milestone, plan, attempt, completion, and immutable chain
   bundle identity. `chain/execution_binding.py:active_execution_identity`
   binds chain bytes, ordered milestone labels and briefs, North Star, intended
   initiative revision, and runtime identity. `chain/epic_chain.py:EpicChainState`
   additionally has `chain_session`, child epic identity, completed records,
   and resolved workspace. No one current record is proven to carry a globally
   unique chain-run ID across every local, cloud, and resumed path.

7. **Observation — repair evidence is already causal but not one authority.**
   `managed_agent.py` directly supervises automatic repair kinds and binds
   repair claims. `cloud/incident_bridge.py` appends repair and chain evidence;
   `cloud/repair_requests.py` owns blocker-scoped claims; repair sidecars and
   manifests remain present. The custody decision explicitly forbids turning
   any one projection, incident row, marker, log, or PID into action authority.

8. **Inference.** The correct extension point is a normalized subscriber over
   already-persisted lifecycle/evidence records, plus reconciliation for gaps.
   Integrating separately with every phase or agent kind would reproduce the
   current fragmented evidence problem.

## One generalized observation contract

All producers map to one versioned `KnowledgeObservationEnvelope`. Adapters may
leave a field explicitly `not_applicable` or `unknown(reason)`; they must never
guess identity from a basename, latest pointer, log prose, wall-clock order, or
model narrative.

### Stable identity and lineage envelope

| Group | Minimum fields and rule |
| --- | --- |
| Envelope | `schema_version`, `observation_id`, `observation_kind`, `adapter_id`, `adapter_version`, deterministic `idempotency_key` |
| Initiative/epic | canonical `initiative_id`/path, intended initiative revision, optional parent portfolio epic ID; identity must be content/revision bound rather than name-only |
| Chain run/session | immutable chain-execution-binding digest, explicit `chain_run_id`, optional cloud/resident `chain_session`; a binding identifies inputs while `chain_run_id` distinguishes reruns |
| Milestone/sprint | milestone label and index, milestone-attempt ID/ordinal, brief digest, predecessor acceptance refs |
| Plan | stable `plan_id`, plan/run revision, plan attempt or reinitialization ID, source-binding digest where present |
| Phase/step | phase name, logical step/boundary ID, contract/template version, invocation ID, step-attempt ID/ordinal; `prep/plan/critique/gate/revise/finalize/execute/review` are values, not schemas |
| Agent run | custodian/runtime kind plus stable `agent_run_id`, root agent-run ID, explicit parent agent-run ID, launch idempotency key, backend/model/route provenance; provider session ID is secondary and access-controlled |
| Retry/rework/supersession | `retry_of_attempt_id`, `rework_of_step_id`, `supersedes_id`, `superseded_by_id`, and reason; every retry is a new attempt even when the logical task is unchanged |
| Task/goal | task/subject ID, task revision, goal ID and goal/checkpoint revision, optional request/query-relationship refs; changing the objective produces a new revision, not a mutable label |
| Source evidence | source store/stream identity, native position unit, exact half-open range or event ID/sequence, durable locator, digest, schema/media type, size, availability, gaps, and typed refs to artifact/commit/test/verdict |
| Time | `occurred_at`, source `persisted_at`, observer `observed_at`, ingestion time, and optional terminal time in UTC; ordering comes from source position and causal refs, never clocks alone |
| Outcome | lifecycle outcome, semantic verdict/recommendation, claimed result, and separate acceptance state (`unreviewed`, `accepted`, `rejected`, `quarantined`, `superseded`, `indeterminate`) with exact decision refs |
| Authorization/custody | actor/tool provenance, resolved work intent, evidence access scope, Run Authority grant/fence/attempt refs, Custody target/lease/epoch refs, and declared policy decision; presence is evidence, never a grant minted by the compiler |
| Causality/correction | parent observation IDs, corrects/supersedes/contradicts IDs, source cursor, and compiler checkpoint refs |

The irreducible runtime identities are:

```text
epic_run      = initiative revision + chain binding digest + chain_run_id
milestone_run = epic_run + milestone index + milestone attempt
step_attempt  = plan revision + boundary/phase + invocation/attempt ID
agent_run     = custodian/runtime kind + stable run ID
task_revision = task/goal ID + immutable revision
source_range  = source stream + native unit + [start, end) or immutable event ID
```

Every observation need not describe all levels. A resident lookup agent may
have no plan or phase; a milestone transition may have no agent. The envelope
still uses the same fields and explicit applicability so aggregation can join
without kind-specific schemas.

### Generic observation kinds

The substrate needs a small vocabulary rather than phase-specific records:

- `source_registered`, `launch_reserved`, `attempt_started`;
- `evidence_appended`, `artifact_persisted`, `checkpoint_persisted`;
- `outcome_recorded`, `verdict_recorded`, `acceptance_recorded`;
- `retry_scheduled`, `rework_scheduled`, `supersession_recorded`;
- `transition_recorded`, `correction_recorded`, `contradiction_recorded`;
- `persistence_gap_recorded`, `reconciliation_recorded`.

Resident agents, phase workers, repair workers, nested children, and milestone
transitions differ only in adapter mapping and which envelope fields apply.

## Capture architecture and seams

### Three layers

1. **Generic capture substrate.** A Store-backed append API validates the
   envelope, enforces deterministic idempotency, records source cursors and
   privacy metadata, and builds disposable projections. It contains no
   Megaplan phase names and no initiative-specific extraction prompt.

2. **Megaplan adapters.** Thin adapters map native workflow journals, plan
   Store events, phase results, worker receipts, chain/supervisor state,
   managed-agent manifests, resident Store/audit records, repair claims, and
   acceptance receipts into the generalized envelope. They reference source
   records; they do not copy lifecycle authority or reinterpret outcomes.

3. **Knowledge policy.** This initiative owns the approximately 100,000-newly-
   persisted-token and terminal triggers, four output record schemas, claim
   kinds, bounded direct-Pro extraction, synthesis/correction/search,
   promotion, paper-cut consolidation, cost limits, and retention-aware
   derived-record policy. Other products can consume the capture substrate
   without inheriting this policy.

### Sidecar, subscriber, or hook

Use a combination, with different trust levels:

- **Lifecycle subscriber — primary seam.** After a source lifecycle/event/
  artifact transaction is durable, publish or enqueue a compact observation in
  the same Store transaction/outbox where supported. At managed launch, use the
  manifest-before-process boundary. At terminal transition, reference the
  persisted result and acceptance decision. When the WBC transactional API is
  operational, consume it as the preferred supported-runtime source rather
  than forking it.
- **Post-step hook — trigger only.** `on_phase_complete`, handler completion,
  and milestone-transition hooks may enqueue compilation immediately after an
  accepted source record exists. They are latency optimizations and cannot be
  authoritative because current callbacks and convenience emits can fail or be
  skipped.
- **Observer/reconciler — recovery seam.** A read-only scheduled observer scans
  source cursors, native journals, Store event streams, managed manifests,
  result artifacts, and chain/supervisor acceptance records. It fills missed
  observations, ingests late events, and emits explicit gaps. It never changes
  the primary run and does not infer success from logs, PIDs, or prose.

This is a logical sidecar inside existing Store/scheduler boundaries, not a
standalone service or database. No LLM call, broad transcript read, semantic
search, or cross-epic aggregation occurs synchronously on the primary path.

### Best current seams by producer

| Producer | Source evidence | Recommended capture seam |
| --- | --- | --- |
| Native/manifest workflow node | native manifest journal node/control/artifact events and bound artifact refs | subscribe after journal append; reconcile by source sequence |
| Megaplan plan phase | Store `StoredEvent` stream, typed phase payload/result, `phase_result.json`, result/verdict/acceptance refs | subscribe after Store/handler commit; use `auto.py` post-phase hook only to enqueue |
| Model phase worker | `WorkerResult`, routing record, provider trace/transcript ref, usage/cost metadata, output artifact | adapter at `run_step_with_worker` result persistence; never treat raw model prose as verdict |
| Resident-managed agent | committed resident manifest, prompt digest, launch provenance, tool-call audit, result and delivery outbox | adapter immediately after manifest/result/delivery persistence; scan manifests for reconciliation |
| Automatic/repair managed agent | `ManagedCommandSpec` launch contract, managed manifest/status/result, repair claim/occurrence and incident refs | adapter after reserve/start/terminal persistence; join but do not own repair custody |
| Nested subagent/follow-up | child launch manifest plus explicit parent/root/retry/follow-up IDs and inherited immutable provenance | require launch-bound parent/root IDs; reject ambiguous or orphan joins |
| Retry/rework | new attempt/run record, `retry_of`, rework task/step ref, prior acceptance/supersession decision | record a new attempt and causal edge; never overwrite the earlier attempt |
| Milestone/chain transition | chain execution binding, `ChainState`, supervisor `RunRecord`/decision, acceptance receipt, completion manifest | capture after state and acceptance persistence; incident `chain_lifecycle` is corroboration only |
| Epic/child-epic transition | `EpicChainState`, child chain state, handoff verification, chain session/workspace | capture after epic state commit with child causal refs |

`state.json`, `events.ndjson`, mutable status summaries, logs, and model prose
remain useful evidence or compatibility views. They are not promoted to
authority. If a Store/native journal and its file projection disagree, the
compiler records the contradiction/gap and follows the declared source binding.

## Aggregation and knowledge lifecycle

Aggregation is a provenance DAG, not repeated lossy rewriting:

```text
raw source evidence
  -> immutable normalized observations
  -> per-agent-run checkpoints
  -> step-attempt summary and acceptance view
  -> milestone/sprint synthesis
  -> epic-run synthesis
  -> reviewed cross-epic promotion candidates
  -> reusable project/cross-epic knowledge
```

1. **Per-run checkpoint.** Compile one exact source range plus bounded prior
   accepted context into the four existing record types. Persist the input
   observation IDs, source ranges, gaps, route, schema, and compiler version.
2. **Step synthesis.** Combine checkpoints for one step attempt and its child
   agents. Retain every retry/rework attempt; the active projection identifies
   the accepted or current attempt without deleting rejected work.
3. **Milestone synthesis.** Combine accepted step summaries and explicitly
   contextualize rejected, quarantined, superseded, unresolved, and
   contradictory evidence. A milestone transition triggers synthesis only
   after the transition/acceptance record is durable.
4. **Epic synthesis.** Combine versioned milestone syntheses under one chain
   binding and chain run. A corrected or late milestone produces a new epic
   synthesis version with exact supersession lineage.
5. **Cross-epic knowledge.** Emit candidates, not facts. Promotion requires
   repository/revision/path applicability, source access, contradiction review,
   and authority proportionate to the claim. Cross-epic search must expose
   claim kind, acceptance, applicability, and provenance on every result.

Corrections append `corrects`/`supersedes` edges. Contradictions preserve both
sides and any adjudication. Acceptance is independent from lifecycle outcome:
a worker may complete while its claim is rejected, and a failed attempt may
still contain accepted reusable knowledge or friction evidence.

## Failure, concurrency, privacy, and evolution

### Idempotency and replay

- Observation idempotency is derived from source kind, source store/stream,
  immutable event ID or native position/range, source digest, and adapter major
  version. Replaying a source produces no duplicate observation.
- A duplicate launch with the same launch idempotency contract rejoins the same
  run. A changed launch contract or retry creates a new attempt with explicit
  lineage. Duplicate process IDs, names, or timestamps are never identity.
- Compilation checkpoint idempotency includes ordered observation IDs/source
  ranges, policy/schema/compiler generation, trigger kind, and bounded-context
  digest. The successful cursor advances only with the complete validated
  checkpoint transaction.

### Crashes, restarts, and late events

- Source persistence precedes observation enqueue. A failed enqueue leaves the
  primary result unchanged and creates a visible coverage gap on reconciliation.
- A crash after enqueue but before compilation replays safely from the source
  cursor. A crash during compilation leaves the last-successful cursor fixed.
- Late and out-of-order events are ordered within their native source stream and
  joined through causal parents. Ingestion time cannot reorder history.
- Supersession is append-only. Late results from cancelled/superseded attempts
  remain evidence but cannot become the active accepted projection without a
  new authority decision.

### Concurrent agents

Partition ordering by source stream/agent attempt; do not invent a global
clock order. Cross-stream joins require explicit parent, task, step, milestone,
or causal observation refs. Concurrent children can be synthesized once their
declared join boundary is accepted or terminal; missing children remain named
gaps rather than silently omitted.

### Privacy, secrets, and bounded context

- Derived-record authorization is the intersection of all referenced evidence
  scopes. The compiler cannot widen read, search, promotion, or delivery rights.
- Prefer durable references over content copying. Secrets, credentials, sealed
  stdin, raw environment values, private provider session IDs, and unredacted
  prompts never appear in generic envelope metadata, metrics, or logs.
- Apply source retention, redaction, encryption, deletion, and legal-hold rules.
  Redaction/deletion leaves an authorized tombstone and invalidates affected
  derived active views without erasing historical causality.
- Treat transcript, tool, and model content as untrusted data. Bound extraction
  to the new range, prior accepted run summary, directly relevant parent/step
  context, explicit gaps, and size/token/cost limits. Never inject the whole
  epic corpus into an agent prompt.

### Schema evolution

Use a versioned envelope, versioned adapters, and additive optional fields.
Persist raw source refs and adapter version so projections can be rebuilt with
upcasters. Breaking identity changes create a new major version and explicit
migration observation; they never rewrite old event IDs or reinterpret an old
record through an implicit latest schema.

## Tight three-sprint mapping

This extension fits the current vertical slices; it does not reopen the
archived eleven-sprint decomposition.

| Current sprint | Epic-wide addition | Acceptance handoff |
| --- | --- | --- |
| [M1 — compiler core](../archive/20260716-three-sprint-tightening/briefs/m1-compiler-core.md) | Add the generalized envelope and source-range contract; make epic/milestone/plan/phase/agent/task/authority fields additive; implement generic Store append/idempotency plus initial native-plan and managed-agent adapter families; keep threshold/terminal extraction and four-record acceptance unchanged | one accepted checkpoint can cite an exact agent/phase attempt inside an exact epic run, including child/retry lineage, without another store or cursor |
| [M2 — knowledge use](../archive/20260716-three-sprint-tightening/briefs/m2-knowledge-use-governance.md) | Add step, milestone, and epic synthesis projections to the same append-only correction/contradiction/query lifecycle; apply acceptance/applicability filters; keep cross-epic reuse behind the existing reviewed promotion path | a corrected/reworked milestone rebuilds a new epic synthesis while preserving old versions and every source/decision ref |
| [M3 — operational proof](../archive/20260716-three-sprint-tightening/briefs/m3-consolidation-operational-proof.md) | Complete chain/epic, resident, repair, nested, retry/rework, and late-event adapter conformance; add observer reconciliation, privacy/rollout diagnostics, and a real-epic replay/canary fixture; preserve harmless async behavior | coverage matrix and proving fixture demonstrate all required producer classes, failure isolation, disable/rollback, and no primary-result/delivery change |

### Explicit deferrals

- standalone event bus, sidecar database, remote compiler service, or separate
  epic knowledge service;
- automatic semantic adjudication, automatic authoritative promotion, or
  autonomous execution from compiled knowledge;
- vector database, general RAG platform, global ontology, organization-wide
  ranking, or automatic cross-project clustering;
- mandatory idle compilation, broad enablement, deployment, restart, long soak,
  and historical full-corpus backfill;
- redesign of Run Authority, WBC, Custody, chain scheduling, repair dispatch, or
  resident delivery ownership.

## Migration and rollout with one real epic

Use the existing `custody-control-plane` epic as the proving fixture because its
durable history exercises chain/milestone transitions, phase work, managed
repair agents, retries, acceptance receipts, and authority/custody boundaries.
Do not resume or mutate that chain for the test.

1. **Content-addressed offline replay.** Under the fixture's existing access and
   retention policy, record a redacted manifest of the exact source revision,
   chain binding/state, plan event ranges, managed manifests, result/verdict/
   acceptance refs, and expected gaps. Keep large/private payloads by reference.
2. **Legacy registration.** Register old sources with native positions and
   `legacy` capability flags. Do not rewrite artifacts or infer missing parent,
   token, acceptance, or custody fields. Unknown stays unknown.
3. **Shadow projection.** Replay observations twice, in normal and deliberately
   duplicated/out-of-order delivery, and compare content-addressed projections.
   Compiler output remains disabled or isolated from search/promotion.
4. **Canary policy.** Under later implementation authority, enable asynchronous
   compilation only for that epic/cohort while primary work remains independent.
   Compare observation coverage, lag, cost, privacy, and result/delivery latency
   against the shadow baseline.
5. **Widen only on evidence.** Progress from disabled to shadow to canary to
   enabled configuration. Rollback stops new compilation but preserves accepted
   checkpoints. Broad production enablement remains a separate operational
   decision.

## Measurable acceptance proof

The extension is accepted only when all of the following pass:

1. A generated coverage matrix contains resident-managed, every named Megaplan
   phase, retry/rework, nested child/follow-up, automatic repair, milestone,
   chain, and epic-transition rows, each bound to a real source seam and test.
2. The real-epic fixture replay produces byte/content-equivalent active
   projections under normal, duplicate, restart, concurrent, late, and
   out-of-order ingestion. Every duplicate maps to one observation ID.
3. Every source stream has non-overlapping contiguous compiled ranges or an
   explicit durable gap. No successful checkpoint advances across a failed,
   unauthorized, ambiguous, or partially persisted range.
4. Parent/root/retry/rework/supersession/task/goal relations resolve exactly.
   Orphans, cycles, cross-run binding drift, wrong custody epoch/fence, and
   duplicate launch-contract conflicts fail closed for derivation.
5. All eight phase values and all terminal outcomes are captured below the
   token threshold. A terminal transition yields one idempotent final synthesis
   only after its source range and acceptance state are persisted.
6. Forced observer, queue, extractor, schema, Store, and search failures leave
   primary agent/phase/chain outcome and resident terminal delivery unchanged.
   The synchronous path performs no model/network call; benchmarked p95 enqueue
   overhead is at most 25 ms and at most 1% of phase wall time on the fixture.
7. Accepted, rejected, quarantined, superseded, indeterminate, corrected, and
   contradictory attempts all remain traceable. Only applicable accepted active
   claims render as current knowledge.
8. Every derived claim resolves to authorized durable evidence or an explicit
   retained tombstone. Secret fixtures and unauthorized searches yield zero
   leaked content in envelopes, summaries, metrics, logs, and search results.
9. Envelope major-version and adapter-version replay/upcast tests rebuild the
   same v1 active view; unsupported or ambiguous versions remain visible and
   uncompiled rather than guessed.
10. Disable/rollback/re-enable tests stop new compilation, preserve accepted
    checkpoints and cursors, and create neither duplicate observations nor
    duplicate ticket/promotion effects.

## Risks and unknowns

- **Unknown — WBC operational readiness.** The pinned WBC execution-attempt
  ledger is schema-only and explicitly lacks production transaction/outbox
  storage. M1 must inventory the landed state before choosing it as a live
  source. The compiler may adapt current Store/native journals meanwhile but
  must not create a competing WBC ledger.
- **Unknown — one chain-run identity.** Chain binding identifies immutable
  inputs, and some epic/cloud paths carry `chain_session`, but universal unique
  chain-run identity across local/cloud/resume paths is not proven. Add or bind
  one at the chain launch boundary rather than deriving it from a path.
- **Unknown — nested parent completeness.** Resident continuations persist
  parent/root lineage, while arbitrary managed children can omit
  `parent_run_id`. The launch adapter must propagate current managed-run context
  explicitly or record an orphan gap; no log-based inference.
- **Unknown — exact token accounting.** `WorkerResult` carries usage when
  providers expose it, but exact persisted usage and counter-reset behavior are
  not proven for every backend. Retain tagged fallback capability and never
  equate token, byte, and event positions.
- **Unknown — universal phase acceptance evidence.** Structured phase results,
  Store/native events, Run Authority decisions, and chain acceptance receipts
  coexist. The M1 seam inventory must identify the accepted decision record for
  every producer before an active summary can claim acceptance.
- **Risk — observer overreach.** Reconciliation could accidentally turn logs,
  mutable state, or model conclusions into truth. Enforce source-priority and
  explicit-gap rules in schema tests.
- **Risk — privacy amplification.** Epic synthesis joins more scopes than a
  single session. Authorization intersection, by-reference payloads, bounded
  context, and promotion review are required before any cross-run query.

## Final conclusion

Epic-wide capture is the same compiler operating over a wider, explicit lineage
graph. The smallest safe design is one generic append-only observation
substrate, thin Megaplan adapters at persisted lifecycle seams, initiative-owned
knowledge policy, layered correctable projections, and a read-only reconciler.
It gives every resident, phase, retry/rework, nested, repair, and transition
agent one contract without granting the compiler execution authority or adding
a second service. The work fits M1/M2/M3 as capture, aggregation/governance, and
cross-backend operational proof respectively.
