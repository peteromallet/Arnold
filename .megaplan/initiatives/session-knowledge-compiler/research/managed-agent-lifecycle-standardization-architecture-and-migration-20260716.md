# Neutral Managed-Agent Lifecycle Standardization

**Status:** planning/research only; no implementation, launch, service restart,
integration, push, or deployment is claimed by this document.

**Canonical initiative:** `session-knowledge-compiler`

**Evidence cut:** project checkout `72f7eec32b3fdf8f5027a415d97f0e14716773f4`;
resident runtime checkout pinned at
`c267920b6719fb35636e1da0071b5863ec5b2a0c`.

**Planning run:** `subagent-20260716-155100-6d5344d7`, whose raw manifest is
`.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`.

## Executive recommendation

Do **not** route all agents through Discord. Discord is a transport adapter with
durable inbound/outbound custody; it is neither a backend-neutral execution API
nor the owner of Megaplan phases, gates, retries, chain state, or authorization.
Instead, make both the Discord resident and Megaplan callers of one lower-level,
transport-neutral managed-agent lifecycle in Arnold:

```text
Discord ingress                         Megaplan / chain / repair policy
      |                                              |
Resident conversation + delegation       phase, gate, retry, approval decisions
      |                                              |
      +--------------- launch envelopes ------------+
                              |
                 neutral managed-agent lifecycle
          identity | custody | journal | cancel | resume
                              |
            Codex | Claude | Hermes provider adapters
                              |
               result/evidence/terminal receipts
                     /                       \
       Discord durable outbox          Megaplan state/receipts
```

The lifecycle should own execution mechanics and durable evidence only.
Megaplan must continue to own its orchestration semantics. The compiler should
consume the lifecycle journal asynchronously through deterministic inclusion
predicates, never become part of launch success, and never treat its own runs or
meta-observer prose as new source knowledge.

Use a new, additive `arnold-managed-agent-run-v3` contract. The existing
`arnold-managed-agent-run-v2` manifests remain valid evidence and migration
inputs; silently changing their meaning would put resident delivery and repair
recovery at risk.

Estimate **three two-week lifecycle migration sprints**, in addition to the
existing five compiler sprints: eight sprint-equivalents in the combined
roadmap. Contract design can overlap the compiler's M1 schema work, but M1 may
not pass its capture-completeness gate until all in-scope launch seams dual-
record with parity. If the two-sprint `sequential-model-fallbacks` initiative is
delivered first, it supplies much of the routing/profile work; the three-sprint
estimate remains the safer end-to-end estimate because durable lifecycle,
resident/repair compatibility, and phase cutover are not covered by routing
alone.

## Why this belongs here

The request changes what counts as an observable managed session, which event
stream is canonical, and how the knowledge compiler avoids duplicate and
recursive compilation. Those are core contracts of
`session-knowledge-compiler`. Two neighboring initiatives remain authoritative
for narrower concerns:

- `sequential-model-fallbacks` owns the transport-neutral profile resolver,
  fallback semantics, nested launch authority, and root-only delivery contract.
- `discord-resident-delegation-delivery-corrective` owns Discord ingress,
  immutable message provenance, durable outbox custody, and delivery recovery.
- `agentbox-persistent-machine` supplies the current resident/managed-agent
  runtime boundary but is not a better home for compiler inclusion policy.

The older ticket
`.megaplan/tickets/01KTPVVVVV002AGENTRUNTIME-agent-runtime-extraction.md` is
useful historical evidence, but its proposed package boundary predates the
current neutral `arnold.agent` package. No new initiative is warranted.

## Method and confidence labels

Every current-state statement below is based on source, checked-in state, or a
raw run manifest. **Verified** means directly observed in those sources.
**Proposed** means a target contract in this document. Documentation-only
claims were cross-checked against code where they affect the recommendation.

The project checkout and the pinned resident-runtime checkout both contained
unrelated dirty work during this research. They were inspected read-only. This
artifact is written only in the project initiative; the pinned runtime was not
modified.

## Current-state execution map

### Route inventory

| Route | Verified policy owner | Verified launch seam and backend path | Verified durable evidence/delivery | Gap relative to the target |
|---|---|---|---|---|
| Discord resident/root conversation (the conversational "you") | `ResidentRuntime`, profile/auth/query-relationship policy | Pinned `resident/agent_loop.py` runs the configured Codex CLI resident runner; this is not a delegated managed run | Resident Store records inbound, turns, messages and tool calls; `resident/discord.py` is inbound/outbound transport | It has conversation custody, but is not the universal managed-worker launcher. Its status/synthesis prose must not be re-ingested as child-agent knowledge |
| Discord delegated resident agent | Resident launch and delegation policy | Pinned `resident/subagent.py` / `subagent_worker.py` launch Codex, persist `arnold-managed-agent-run-v2`, and support exact-session follow-up | Manifest, sealed prompt, log, result, status history, lineage, authority, model session, and completion-delivery state; normal resident completion verification feeds the Discord outbox | Richest end-to-end contract, but Codex-specific and resident/Discord-shaped in launch and delivery fields |
| Megaplan prep | Prep handler / pipeline | `handlers/plan.py` calls shared worker seam | `WorkerResult`, plan state, receipts/events where emitted | No one durable run identity/journal across worker, phase, receipt, and event views |
| Megaplan plan | Plan handler / pipeline | Shared `workers/_impl.py::run_step_with_worker` | Planner session in plan state plus result/receipts | Same fragmentation; default path bypasses `ArnoldDispatcher` |
| Critique | Critique handler / auto driver | Shared worker seam, critic profile | Phase result, receipts/events, session metadata | Fresh-vs-persistent semantics live in worker logic, not a common lifecycle contract |
| Gate | Gate handler / auto driver | Shared worker seam, gatekeeper profile | Verdict/receipt/phase state | Authorization and gate outcome must remain above the launcher |
| Revise | Revise handler / auto driver | Shared worker seam, planner profile | Revised artifacts, phase result, sessions/receipts | Retries and rework are orchestrator concepts, not generic launcher policy |
| Finalize | Finalize handler / auto driver | Shared worker seam | Final artifacts and receipts | Mutating/finalizing route needs late cutover and strict parity |
| Execute | Execute handler, batch executor, auto driver | Shared worker seam; backend-specific session behavior | Execution artifacts, receipts, phase state, provider session where present | Highest authorization risk; launcher must not infer approval or execution authority |
| Review/rework | Review handler / auto driver | Shared worker seam, then Megaplan review/rework transitions | Review verdicts, phase results, chain/plan state | Rework ownership must stay in Megaplan |
| Chain milestone supervision | Chain supervisor/spec | Invokes Megaplan plans; not itself a provider adapter | Chain state, milestone retries/failure policy, execution binding | Chain identity must be linked, not absorbed by the launcher |
| Watchdog source repair | Watchdog and central repair queue | `cloud/watchdog.py` reserves an automatic managed command after policy permits it | Managed v2 manifest/log/result; non-Discord delivery is explicitly not applicable | Already close to the target, but the managed command supervises arbitrary argv and lacks the normalized semantic event/session journal |
| Automatic repair | Repair trigger/queue/repair loop | Managed run kinds include automatic repair and retry; selected Codex/Hermes worker is wrapped by `managed_agent.py` | Stable hashed run identity, launch contract, execution lock, liveness, status, parent/retry lineage | Outer controller and inner reasoning worker can be duplicate views of one repair; roles need normalization |
| Meta-repair | Meta-repair policy and wrapper | Outer meta-repair plus internal worker/retry runs | Managed v2 manifests and parent links | Must distinguish controller, observer, and actual repair worker to prevent compiler recursion/noise |
| Progress auditor | Periodic auditor controller | Managed read-only Codex run | Managed v2 lifecycle; findings route to central repair | Evaluator prose observes other runs and must be excluded from semantic compilation |
| Legacy fixer / root-cause / research agents | Respective cloud wrapper or caller | Enumerated automatic managed run kinds in `managed_agent.py` | Managed v2 lifecycle | Need stable origin/role rather than inferring semantics from free-form run kind |
| Bakeoff, tiebreaker, planning loop, execute batch | Their Megaplan caller | All converge on `run_step_with_worker` | Backend result plus caller-specific artifacts | Good consolidation seam, but still not durable lifecycle |
| Standalone subagent-launcher scripts / diagnostics | Skill or diagnostic caller | Direct Hermes, Codex, Claude, or resident-launch helpers | Tool-specific output | Explicit bypass inventory is required before duplicate paths can retire |

### What is already neutral, and what is not

**Verified:** `arnold/agent/contracts.py` defines backend-neutral
`AgentRequest`/`AgentResult` types. `arnold/agent/__init__.py` registers Codex,
Claude/Shannon, and Hermes/DeepSeek adapters, and `dispatcher.py` selects an
adapter. The Megaplan compatibility package re-exports those contracts.

**Verified:** this dispatcher is request/result dispatch, not a managed
lifecycle. It does not itself establish a durable logical run, append-only
event stream, custody transitions, cancellation/follow-up API, terminal
delivery receipt, or compiler cursor.

**Verified:** `workers/_impl.py` uses the dispatcher only when
`MEGAPLAN_USE_AGENT_DISPATCHER=1`; the default directly invokes the Hermes,
Claude/Shannon, or Codex worker. `WorkerResult` is rich—it records configured
and attempted routes, tokens/cost, actual model, provider session, trace,
rendered prompt, and fallback reasons—but it is still one caller-owned return
object.

**Verified:** phase state is distributed among phase results, receipts,
per-phase sessions, routing ledger JSONL, Store events, legacy
`events.ndjson`, artifacts, and raw backend logs. The Store event projection
explicitly maintains a legacy view. These are useful evidence sources, not one
canonical lifecycle stream.

**Verified:** `managed_agent.py` is already a generic durable process
supervisor. It reserves before launch, hashes stable identity inputs, seals
stdin, records machine origin and launch-contract hashes, takes a nonblocking
per-run execution lock, adopts or diagnoses live workers, and records terminal
states including cancellation/supersession. Its module boundary explicitly
leaves the decision to run with the watchdog, repair queue, or chain runner.
That separation is the correct foundation. Its bounded status history is not a
permanent semantic event journal, and arbitrary argv supervision is not yet a
backend conformance API.

**Verified:** the pinned resident revision builds its delegated run on managed
v2, adding immutable Discord provenance, work intent, aggregation role,
authority, exact-session follow-up, successor queues, and completion-delivery
custody. The current planning run's manifest confirms this contract in a real
run. Resident completion is verified in a new normal resident turn before an
outbound record is sent through the Discord sink; the worker does not post
directly to Discord.

### Claim-to-evidence anchors

| Verified claim family | Primary source anchors |
|---|---|
| Neutral request/result dispatch and provider registration | `arnold/agent/contracts.py`, `dispatcher.py`, `__init__.py`, `adapters/codex.py`, `adapters/shannon.py`, `adapters/deepseek.py` |
| Dispatcher is optional for phase workers; direct providers remain default | `arnold_pipelines/megaplan/workers/_impl.py`, especially the `MEGAPLAN_USE_AGENT_DISPATCHER` branch and `run_step_with_worker` |
| Phase callers converge on the worker seam | `handlers/shared.py`, `orchestration/prep_research.py`, `orchestration/tiebreaker.py`, `execute/batch.py`, `bakeoff/channel_shadow.py`, `loop/engine.py`, and `_core/worker_fanout.py` |
| Phase/chain semantics and execution binding remain caller-owned | `auto.py`, phase handlers, `orchestration/phase_result.py`, `receipts/schema.py`, `chain/spec.py`, and `chain/execution_binding.py` |
| Store events and legacy projections are distinct views | `observability/events.py`, `observability/events_projection.py`, and `observability/routing_ledger.py` |
| Managed v2 reservation, locking, liveness, lineage, terminal state, and non-Discord automatic delivery | `managed_agent.py`, including `MANAGED_AGENT_SCHEMA`, `AUTOMATIC_RUN_KINDS`, `reserve_managed_command`, and `run_managed_command` |
| Repair/meta-repair/auditor/fixer workers use managed run kinds | `cloud/wrappers/arnold-repair-loop`, `arnold-meta-repair-loop`, `arnold-progress-auditor`, `arnold-kimi-goal-operator`, plus `cloud/watchdog.py` and repair controllers |
| Resident root conversation is separate from delegated managed execution | Pinned `resident/agent_loop.py::CodexCliAgentRunner`, `resident/runtime.py::ResidentRuntime`, and `resident/subagent.py` |
| Discord is transport/outbox delivery, not the worker backend | Pinned `resident/discord.py::ResidentDiscordService`, resident runtime/outbound sink code, and delegated `completion_delivery` state in `resident/subagent.py` |
| Real resident delegation contract | `.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`, cross-checked against the pinned resident source revision |

### Why every agent must not literally route through Discord

Repository evidence rejects that topology:

1. `resident/discord.py` adapts Discord messages to `ResidentRuntime` and sends
   durable outbound records. It is transport and custody code, not an execution
   backend abstraction.
2. Megaplan phase workers already launch independently through
   `run_step_with_worker`; automatic repair uses `managed_agent.py`; neither
   requires a Discord message to exist.
3. Managed automatic runs deliberately record non-Discord delivery as not
   applicable. Requiring Discord would fabricate transport provenance and add a
   failure dependency to unattended recovery.
4. Megaplan's `auto.py`, phase handlers, chain spec, execution binding, gates,
   review/rework, and repair policy own decisions Discord cannot safely infer.
5. The resident itself already separates delegated execution from completion
   delivery. That separation should be generalized downward, not inverted.

The correct shared element is the lower lifecycle substrate. Discord remains
one ingress and one terminal-delivery adapter.

## Proposed neutral architecture

### Layer boundaries

| Layer | Owns | Must not own |
|---|---|---|
| Discord adapter | Message/reaction ingress, immutable provider provenance, attachment references, durable outbox send/retry/provider receipt | Backend selection, Megaplan phase transitions, compiler eligibility |
| Resident | Conversation/root-turn policy, delegation intent, query relationship, aggregation/delivery-owner selection, resident completion synthesis | Generic process supervision or Megaplan semantics |
| Megaplan | Phase topology, profiles, gates, retries, persistent/orchestrated mode, chain state, iteration/review/rework, watchdog/repair policy, approvals and authorization | Provider-process details, transport-specific delivery |
| Neutral lifecycle | Envelope validation, stable run/attempt identity, reservation, backend adapter invocation, durable events/evidence, liveness, cancellation, resume/follow-up mechanics, custody and terminal receipts | Deciding whether a phase/repair is allowed, changing profiles, auto-approving work, synthesizing Discord replies |
| Backend adapter | Translate the canonical request into Codex, Claude, or Hermes provider operations; normalize session/cursor/tool/token receipts | Orchestration, authority expansion, terminal user delivery |
| Knowledge compiler | Asynchronous eligible-event consumption, immutable checkpoints, correction/synthesis/promotion workflows | Launch success, run state mutation, consuming its own semantic output as new evidence |

### Canonical launch envelope (`arnold-managed-agent-launch-v3`)

The envelope is immutable after reservation except for separately versioned
amendment events. Required fields are:

```yaml
schema: arnold-managed-agent-launch-v3
run_id: mag_<stable identifier>             # durable logical work identity
attempt_id: mat_<stable identifier>          # one provider/process attempt
launch_idempotency_key: <caller scope + immutable task revision>
root_run_id: <lineage root>
parent_run_id: <direct parent or null>
continuation_of_run_id: <prior logical run or null>
retry_of_attempt_id: <prior attempt or null>
compilation_unit_id: <one semantic unit>
origin:
  kind: <stable enum>
  system: <resident|megaplan|repair|...>
  transport: <discord|cli|scheduler|none>
  source_refs: [<immutable evidence refs>]
run_kind: <stable enum>
role: <stable enum>
subject_run_ids: [<runs observed or summarized>]
orchestrator:
  kind: <resident|megaplan_plan|megaplan_chain|repair_queue|...>
  plan_id: <optional>
  chain_run_id: <optional>
  phase: <optional>
  iteration: <optional>
  attempt: <optional orchestrator attempt>
  profile: <optional>
  mode: <persistent|orchestrated|fresh|...>
route:
  requested_backend: <codex|claude|hermes>
  requested_model: <stable model spec>
  allowed_candidates: [<ordered immutable route specs>]
  fallback_policy_ref: <caller-approved policy>
task:
  content_ref: <sealed evidence ref>
  content_digest: <digest>
  workspace_ref: <revision/worktree identity>
  intent: <speculative|review|execution>
authority:
  principal_ref: <non-secret identity ref>
  scope: [<capabilities>]
  child_ceiling: <non-expanding bound>
  approval_refs: [<immutable refs>]
privacy:
  classification: <enum>
  audience: [<authorized scopes>]
  retention_policy_ref: <policy>
delivery:
  owner_run_id: <root/synthesis owner>
  adapter: <discord_outbox|cli|megaplan|none>
  target_ref: <opaque authorized target or null>
compiler:
  policy: <include|exclude|defer_to_owner>
  reason: <stable reason code>
budgets:
  time_seconds: <optional>
  token_limit: <optional>
  cost_limit: <optional>
created_at: <UTC control-plane timestamp>
contract_digest: <canonical serialization digest>
```

`run_id` is stable across resumptions that continue the same logical task.
`attempt_id` changes for a provider/process retry. A materially revised task
gets a new `run_id` linked by `continuation_of_run_id`; callers must not hide a
new objective behind session resume. `launch_idempotency_key` prevents two
effects for the same immutable caller decision.

Stable `origin.kind` values initially include `resident_delegation`,
`megaplan_phase`, `repair_request`, `meta_repair`, `progress_audit`,
`knowledge_compiler`, `status_observer`, `delivery_verifier`,
`scheduled_maintenance`, and `manual_tool`. Stable `role` values initially
include `primary_work`, `internal_contributor`, `synthesis_owner`,
`repair_worker`, `controller`, `observer`, `auditor`, `compiler`,
`delivery_verifier`, and `projection`.

### Backend adapter contract

Each Codex, Claude, or Hermes adapter must implement the same lifecycle-facing
operations where the provider supports them:

- `prepare`: validate the request and return a sealed provider launch receipt;
- `start`: start once for an `attempt_id` and return provider/process identity;
- `observe`: stream normalized output, tool, token, and checkpoint events;
- `resume` or `follow_up`: bind to the exact provider session when supported;
- `cancel`: request cancellation and report whether it was acknowledged;
- `collect`: return normalized terminal result and immutable evidence refs;
- `capabilities`: declare support for sessions, streaming, tool traces,
  cancellation, exact token accounting, and checkpoint cursors.

Unsupported capabilities are explicit (`unsupported`), never simulated. A
fallback is a new attempt authorized by the caller's immutable route policy;
the lifecycle records it but does not decide the candidate order.

### Run manifest and custody

The v3 manifest is a materialized view of immutable launch data plus the latest
custody state. The append-only journal is authoritative. Custody transitions
are monotone and attributed:

```text
reserved -> launch_claimed -> running -> result_persisted -> terminal
                                      \-> cancel_requested -> cancelled
                                      \-> interrupted / failed / superseded
terminal -> delivery_eligible -> delivery_claimed -> delivered
                                \-> delivery_failed (retryable by adapter)
```

Execution custody and delivery custody are distinct. Only the declared
delivery owner can create terminal delivery intent. Internal contributors,
auditors, retries, and compiler workers cannot independently address the user.

## Normalized session and event schema

### Session projection (`arnold-managed-agent-session-v3`)

The query-friendly projection contains the launch envelope, current lifecycle
state, provider/session receipts, terminal result refs, delivery state, compiler
cursors, and links to all attempts. It is rebuildable from the journal. It is
not allowed to overwrite historical events.

Provider/session fields include normalized backend/model identity, provider
session ID, process identity proof, adapter version, actual route, start/end
timestamps, exit classification, exact/estimated token usage with confidence,
cost currency/source, and capability flags. Secrets are represented only by
opaque credential-channel identifiers.

### Event envelope (`arnold-managed-agent-event-v3`)

```yaml
schema: arnold-managed-agent-event-v3
event_id: <deterministic or reserved UUID>
run_id: <logical run>
attempt_id: <attempt or null>
stream: <lifecycle|model_output|tool|token|artifact|delivery|compiler>
sequence: <strictly increasing within run+stream>
event_kind: <versioned stable kind>
occurred_at: <provider/source UTC timestamp or null>
recorded_at: <custodian UTC timestamp>
caused_by_event_id: <optional>
correlation_refs: [<phase/chain/message/repair refs>]
payload_schema: <versioned payload name>
payload: <bounded typed data>
evidence_refs: [<immutable evidence refs>]
authority_snapshot_ref: <immutable ref>
privacy_snapshot_ref: <immutable ref>
idempotency_key: <producer scope + source identity>
producer: <component + version + revision>
```

Minimum event families are reservation, launch claim/start, provider session,
model output range, tool request/result, token usage, checkpoint cursor,
artifact/result persistence, cancellation, interruption/failure/supersession,
terminal classification, delivery intent/claim/receipt/failure, follow-up,
retry/fallback link, compiler checkpoint, correction, and projection repair.

### Ordering, idempotency, and deduplication

- The custodian allocates a strict `sequence` per `run_id + stream`. Ordering
  across runs is causal (`caused_by_event_id` and lineage), not inferred from
  wall clocks.
- `event_id`/`idempotency_key` uniqueness makes replay safe. A conflicting
  payload for the same key is a contract violation and generates an anomaly;
  it never overwrites the first event.
- `launch_idempotency_key` admits at most one logical launch decision.
  `attempt_id` admits at most one provider/process start effect. Reconciliation
  may adopt that effect, not launch another.
- A normalized event derived from an existing receipt records
  `projection_of`; compiler dedupe keys on the underlying evidence identity,
  not on the number of projections.
- `compilation_unit_id` groups retries, continuations, contributors, and an
  aggregation owner according to the inclusion rules below.

### Immutable evidence references

Every claim-bearing event points to an immutable reference containing store
kind, locator, content digest, byte/line/event range where applicable, media
type, schema, producing revision, recorded timestamp, and access-policy ref.
Mutable paths may be displayed as hints but are not sufficient identity.
Corrections append a new event that cites the superseded claim/evidence; source
observations remain available.

### Tokens and compiler cursors

Token accounting and compiler progress are separate:

- token events report prompt/completion/cache/tool totals, accounting source,
  exact-vs-estimated confidence, and model/tokenizer identity;
- the compiler cursor is a tuple of source stream, last source sequence,
  cumulative newly persisted token measure, checkpoint ID, and source digest;
- provider-specific cursors remain opaque evidence and are never compared as if
  they shared units;
- cursor advancement occurs only after checkpoint persistence commits;
- terminal completed, failed, cancelled, and superseded states all trigger a
  final bounded compilation attempt without changing the primary terminal
  result.

### Privacy and authorization propagation

Authority and privacy snapshots are captured at launch and referenced by every
event. Children may narrow but never expand the parent's capability or audience
ceiling. Backend adapters receive the minimum credential channel required and
must not journal secrets. Compiler readers enforce the intersection of source
audience, current reader authority, and promotion target policy. Redaction is a
derived authorized view; immutable evidence remains access-controlled rather
than destructively rewritten.

### Compatibility and versioning

- Keep v1/v2 readers and fixtures. Introduce v3 writers behind per-seam flags.
- Use additive payload versions and an explicit capability negotiation field;
  unknown event kinds are retained and ignored safely by older consumers.
- Dual records cross-link by immutable `projection_of` refs. Backfill may
  normalize known facts but must mark absent lineage, tokens, or authority as
  `unknown`; it must not invent them.
- A manifest schema version and an event payload schema version evolve
  independently.
- The compiler records the reader/policy version used for every checkpoint, so
  changed exclusion policy can be replayed without mutating old output.

## Deterministic compilation and anti-recursion policy

### Canonical predicate

A lifecycle event is eligible for semantic knowledge compilation only if all
of the following are true:

```text
known_schema(event)
AND event.stream in {model_output, tool, artifact, terminal}
AND session.compiler.policy == include
AND session.role in {primary_work, internal_contributor, repair_worker}
AND session.origin.kind NOT IN {
  knowledge_compiler, status_observer, progress_audit, delivery_verifier
}
AND event.projection_of is null
AND evidence_authorized(event)
AND canonical_evidence_owner(event) == session.compilation_unit_id
AND NOT already_compiled(source_evidence_key, policy_version)
```

Lifecycle metadata for excluded sessions may still be retained for operations.
"Excluded" here means excluded as semantic source material, not erased.

`source_evidence_key` is the immutable source stream/range digest, not a path,
summary ID, or rendered view. This is the final guard against compiling the same
underlying run from manifest, log, receipt, Store event, and status page.

### Exclusion and ownership matrix

| Actor/view | Semantic compiler policy | Deterministic reason |
|---|---|---|
| Discord resident/root conversational agent ("you") | Exclude from per-managed-agent compilation | The resident conversation/Store is the canonical user-dialog source; treating its root synthesis as a child run duplicates delegated results and delivery prose. A future conversation compiler requires a separate explicit policy |
| Broad "what is happening" or status-report generation | Exclude | `origin.kind=status_observer` or `role=observer/projection`; consume the referenced primary events instead |
| Knowledge-compiler extractor/synthesizer/promotion runs | Exclude and never trigger themselves | `origin.kind=knowledge_compiler` or `role=compiler`; compiler output may be corrected/promoted through typed compiler events but cannot re-enter source selection |
| Progress auditor | Exclude generated session prose | `origin.kind=progress_audit` or `role=auditor`; an accepted finding points to primary evidence, which is compiled under the subject run once |
| Watchdog, repair trigger, queue controller | Exclude controller/status prose | `role=controller`; their custody events remain operational evidence |
| Actual repair reasoning/change worker | Include, subject to authority | `role=repair_worker`; compile its own evidence once. The outer controller refers to it and is not a second compilation unit |
| Meta-repair observer/diagnostic controller | Exclude by default | `origin.kind=meta_repair AND role in {controller, observer}`; only a separately identified worker that performs primary repair is eligible |
| Synthesis/delivery owner | One owner per aggregation group | If it synthesizes internal contributors, contributors use `defer_to_owner` and the owner's `compilation_unit_id` is canonical. Delivery-verifier prose is always excluded |
| Internal contributor with independently reusable task | Include as its own unit only when the launch envelope declares a distinct `compilation_unit_id` | The parent synthesis references, rather than re-ingests, child evidence keys |
| Retry/fallback attempt | Do not create a second semantic unit | Same `run_id`/`compilation_unit_id`; new `attempt_id`; compile non-overlapping source ranges and synthesize once at logical terminal |
| Follow-up/continuation with unchanged objective | Continue the unit | Same task revision and `run_id`; cursor resumes from source sequence |
| Follow-up with materially changed objective | New linked unit | New immutable task digest and `run_id`, with `continuation_of_run_id`; prevents hidden scope changes and permits distinct knowledge |
| Nested subagent | Include only when managed, authorized, and assigned a distinct primary/contributor unit | Child authority is bounded by parent; parent aggregate excludes duplicated child source ranges |
| Manifest, raw log, receipt, Store event, legacy event projection for one run | Compile only the canonical evidence owner | All derived views carry `projection_of`; dedupe by source evidence key |
| Terminal Discord reply / completion verification | Exclude | `role=delivery_verifier`; it is a user-facing projection of already captured evidence |

### Trigger behavior

The compiler subscribes after durable event commit. It checkpoints at roughly
100,000 newly persisted eligible tokens and at logical terminal states, as the
existing North Star requires. Excluded sessions never contribute to the token
threshold. A compiler failure produces its own excluded operational run and
alert; it cannot fail, delay, retry, or change the managed work or delivery.

## Migration plan

### Sprint L1 — contract, journal, and backend conformance (two weeks)

**Goal:** establish v3 without changing an execution route.

- Approve stable origin/run-kind/role enums, authority/privacy vocabulary,
  evidence refs, lineage, compilation-unit rules, and package ownership.
- Add the proposed neutral lifecycle interface above the existing
  `arnold.agent` request/result adapters and the managed v2 supervisor.
- Implement a journal and session projection in shadow mode; normalize existing
  resident and automatic managed v2 evidence without changing launch behavior.
- Define Codex, Claude, and Hermes capability/conformance fixtures, including
  sessions, unsupported operations, cancellation races, token uncertainty,
  fallback attempts, and tool traces.
- Teach compiler M1 design to consume v3 journal sequences, not file mtimes or
  transport records.

**Gate L1:** deterministic schema fixtures round-trip; replay is idempotent;
v2 remains readable; fake adapters pass one-start, cancellation, terminal, and
evidence-integrity tests; shadow journal failure cannot affect the original run.

### Sprint L2 — resident and automatic-run dual recording (two weeks)

**Goal:** prove compatibility on routes already closest to managed lifecycle.

- Adapt resident delegated launch/follow-up/cancel/result/delivery to emit v3
  alongside its existing v2 manifest and outbox contract.
- Adapt watchdog, repair, meta-repair, progress auditor, legacy fixer, and
  research run wrappers to v3 roles without moving any permission decision.
- Add aggregation-owner, observer/auditor, controller/worker, and compiler
  exclusion classifications. Backfill only verified v2 facts.
- Compare v2 state, process identity, logs/results, terminal classification,
  lineage, and delivery receipts to v3 projections.

**Gate L2:** no duplicate provider starts; resident follow-up binds to the same
session; root-only Discord delivery remains idempotent; repair restart/adoption
and non-Discord delivery remain unchanged; every meta-observer exclusion test
passes; rollback to v2-only recording is one seam flag.

### Sprint L3 — Megaplan phase migration and retirement gates (two weeks)

**Goal:** make the lifecycle canonical for Megaplan workers without changing
Megaplan behavior.

- Wrap `run_step_with_worker` in v3 reservation/journaling while preserving
  `WorkerResult`, profiles, fallback policy, session rules, and caller receipts.
- Dual-record phase/iteration/attempt/plan/chain correlations. Reconcile Store
  events, phase results, receipts, routing ledger, and legacy event projections
  as derived views.
- Cut over in risk order: prep/plan/critique/gate; revise; finalize/execute;
  review/rework; then batch/bakeoff/tiebreaker and approved standalone seams.
- Exercise persistent and orchestrated modes, chain retry/failure policies,
  watchdog recovery, review rework, and approval boundaries.
- Retire duplicate launch paths only after the criteria below are met.

**Gate L3:** identical phase artifacts/verdicts and route/fallback decisions
under shadow comparison; no phase or chain state owned by the lifecycle;
complete terminal/journal coverage; safe per-seam rollback; compiler M1 capture
tests see one compilation unit per logical run.

### Dependency on the existing compiler M1–M5

| Existing compiler milestone | Lifecycle dependency |
|---|---|
| M1 durable capture/cursors/triggers | Co-design with L1; final acceptance depends on L3 coverage and anti-recursion fixtures |
| M2 extraction/four record schemas | Depends on stable v3 evidence refs, roles, privacy, and source cursor; direct DeepSeek Pro remains an extractor route, not the lifecycle architecture |
| M3 synthesis/correction/search/UX | Depends on compilation-unit lineage and projection dedupe |
| M4 promotion/contradictions | Depends on authority/audience propagation and immutable correction evidence |
| M5 paper-cut backlog/rollout | Uses accepted repair/auditor findings by referenced primary evidence, not observer prose; rollout waits for retirement gates |

The critical path is L1 → L2 → L3 → M1 acceptance → M2 → M3 → M4 → M5.
M1 implementation experiments may overlap L1/L2, but their output remains
provisional until phase-worker coverage passes L3.

## Shadow parity, failure isolation, rollback, and observability

### Shadow/dual-record method

Shadow mode records one real execution in old and new evidence formats. It must
never invoke a second model. A parity reconciler compares normalized facts:
identity, caller/task digest, configured and actual route, process/session,
start/terminal state, token/cost confidence, evidence digest, lineage,
authority/privacy, result, delivery owner, and provider delivery receipt.

Expected differences are explicit capability gaps. Missing or conflicting
facts are anomalies with raw refs; they are not silently patched.

### Failure isolation and rollback

- Before cutover, v3 recorder/projection/compiler errors are nonfatal to the
  original launch and delivery. Durable anomaly evidence is required.
- After a seam's cutover, reservation is fail-closed before provider start so an
  untracked process cannot be created. Once start occurs, reconciliation adopts
  the same attempt rather than relaunching.
- Per-origin and per-run-kind flags select old launch plus shadow, v3 launch plus
  dual write, or old-only rollback. Backend routing flags are separate from
  lifecycle flags.
- Rollback never deletes v3 evidence and never rewinds compiler cursors. Readers
  can continue to project mixed v2/v3 history.
- Discord outbox retry, chain retry, repair retrigger, and provider retry remain
  separate mechanisms with distinct idempotency keys.

### Required telemetry

Track launch reservations, start-effect dedupe, orphan/adoption outcomes,
event-sequence gaps, journal lag, projection lag, v2/v3 parity mismatches,
terminal-state coverage, cancellation latency, follow-up/session binding,
adapter capability failures, token confidence, compiler eligible/excluded
counts by reason, duplicate evidence suppression, checkpoint lag, delivery
claim/receipt latency, and unauthorized-read denials.

Every operational dashboard/status report is a projection and therefore
excluded from semantic compilation.

### Retirement criteria for duplicate paths

A launch seam may retire its old start path only when:

1. its backend conformance suite passes for all enabled providers;
2. at least one representative full Megaplan chain exercises every phase,
   retry/rework, persistent/orchestrated mode, and terminal outcome in dual
   record without an unexplained parity mismatch;
3. resident follow-up, cancellation, completion verification, and Discord
   delivery recovery pass restart tests;
4. automatic repair/meta-repair/auditor recovery passes process-adoption and
   duplicate-suppression tests;
5. two consecutive release observation windows have zero duplicate starts,
   lost terminal results, or duplicate user deliveries;
6. compiler fixtures prove no self-compilation, observer recursion, or duplicate
   logical units;
7. rollback has been rehearsed from the new canonical path;
8. a human explicitly approves retirement for that seam.

Old schemas/readers and historical evidence remain supported after launch-code
retirement according to an approved retention window.

## Concrete change surface (future implementation only)

No file in this list is changed by this research artifact.

### Neutral runtime and schemas

- `arnold/agent/contracts.py`, `dispatcher.py`, `__init__.py`
- `arnold/agent/adapters/codex.py`, `shannon.py`, `deepseek.py`
- `arnold_pipelines/megaplan/agent_runtime/contracts.py`, `adapters.py`,
  `process_fanout.py`
- `arnold_pipelines/megaplan/managed_agent.py`
- Proposed neutral package (name requires approval), preferably
  `arnold/agent/lifecycle/`, containing envelope/event schemas, journal,
  projection, custody, backend capability interface, reconciliation, and CLI

### Megaplan seams that become callers, not owners

- `arnold_pipelines/megaplan/workers/_impl.py` and backend worker modules
- Phase handlers and `auto.py`, including isolated/in-process driver boundary
- `orchestration/phase_result.py` and `phase_result_classify.py`
- `receipts/schema.py` and receipt writer; `observability/events.py`,
  `events_projection.py`, and `routing_ledger.py`
- `chain/spec.py`, `chain/execution_binding.py`, and chain supervisor only for
  correlation refs—not lifecycle policy
- Execute batch, bakeoff, tiebreaker, planning-loop, and human-diagnostic seams

### Resident and automatic managed callers

- Pinned/project `resident/subagent.py`, `subagent_worker.py`, `runtime.py`,
  `agent_loop.py`, `discord.py`, `scheduler.py`, `profile.py`, `provenance.py`,
  `query_relationship.py`, and `currently_running.py`
- `cloud/watchdog.py`, repair trigger/loop wrappers, `cloud/meta_repair.py`,
  progress-auditor controller/escalation, repair request/contract/revalidation,
  legacy fixer and root-cause wrappers

### CLIs

- Existing `managed_agent.py` reserve/run/status/cancel-style entry points
- Resident subagent launch/follow-up/status/delivery commands
- Megaplan `auto`, phase, and `chain` commands as correlation/policy callers
- Proposed neutral `arnold agent run|status|events|follow-up|cancel` surface;
  it must require an envelope or a caller that creates one and must not grant
  authority by CLI convenience

### Test suites and fixtures

- `tests/test_managed_agent.py`
- `tests/resident/test_launch_subagent.py`, `test_subagent_followup.py`,
  `test_subagent_terminal_delivery_contract.py`, and Discord follow-up/reply tests
- Worker/fallback/session tests under `tests/arnold_pipelines/megaplan/` and
  `tests/test_workers_shannon_session.py`
- Phase result, auto-driver, receipt/event projection, chain execution-binding,
  chain authority, retry, worktree, and completion-gate tests
- Cloud watchdog/repair/meta-repair/progress-auditor custody and recovery tests
- Store backend/layout tests, plus new cross-backend journal replay and access
  authorization conformance fixtures
- New deterministic compiler eligibility fixtures covering every row in the
  exclusion matrix and duplicate-view/retry/nesting cases

## Acceptance criteria

The migration is acceptable only when all of these are demonstrated:

- One immutable envelope and one logical run identity cover every in-scope
  resident delegation, Megaplan phase worker, and automatic managed worker.
- Codex, Claude, and Hermes pass the same required lifecycle conformance suite;
  capability differences are explicit and tested.
- Each provider/process attempt starts at most once, survives supervisor restart
  through adoption/reconciliation, and has a terminal or diagnosed orphan state.
- Logs, output ranges, tool traces where available, tokens/cost confidence,
  sessions/cursors, artifacts, cancellation, follow-up, custody, and terminal
  delivery are durably linked by immutable evidence refs.
- Megaplan phase/profile/gate/retry/mode/chain/review/watchdog/authorization
  outcomes remain byte- or semantically equivalent under parity tests and are
  decided only by Megaplan components.
- Discord retains immutable inbound/outbound custody and is not a dependency for
  non-Discord execution or automatic recovery.
- Compiler selection produces one semantic unit for one underlying logical work
  unit, with no compiler/auditor/status/delivery recursion.
- Privacy and authority can only narrow down lineage; unauthorized compiler or
  delivery reads fail closed and are auditable.
- Old path rollback, mixed-version read, replay, and projection rebuild are
  exercised before retirement.

## Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Treating dispatcher neutrality as lifecycle completeness | Lost custody/events despite one API | Separate backend dispatch from durable lifecycle and test both |
| Changing v2 in place | Resident delivery or repair recovery regressions | Add v3; retain v2 readers and dual records |
| Launcher absorbs Megaplan policy | Gates/retries/authority drift | Immutable caller policy refs; lifecycle records decisions but cannot make them |
| Shadow mode launches twice | Cost, side effects, duplicate delivery | One old execution, two record projections; start-effect idempotency assertions |
| Multiple views compile twice | Contradictory/noisy knowledge | `projection_of`, source evidence keys, compilation-unit ownership |
| Observer/compiler recursion | Infinite low-value sessions and token growth | Stable roles/origins and deny-first deterministic predicates |
| Provider capability mismatch | False session/cancel/token guarantees | Capability declaration and explicit `unsupported` evidence |
| Split stores or partial writes | Cursor gaps and orphan results | Append-only journal, projection rebuild, commit-before-cursor, reconciliation |
| Privacy leakage through compiler/promotion | Cross-audience disclosure | Immutable authority/privacy snapshots and intersection checks on every read |
| Dirty/pinned tree divergence | Plan targets the wrong resident contract | Reconcile project vs pinned revision before implementation; never copy dirty initiative state blindly |
| Standalone bypasses remain | Incomplete "all managed agents" claim | Maintain a launch-seam registry; retirement gate requires zero unclassified starts |

## Open decisions requiring human approval

1. **Package ownership:** approve neutral Arnold ownership, preferably
   `arnold/agent/lifecycle`, versus another stable package name. It should not
   live under Discord or a Megaplan phase package.
2. **Schema boundary:** approve new v3 rather than changing managed v2 in place.
3. **Canonical journal store:** choose Store/database authority and filesystem
   fallback/replication semantics, including transaction boundaries with result
   and outbox records.
4. **Compilation grouping:** approve when resident internal contributors defer
   to a synthesis owner versus form independently reusable units.
5. **Repair knowledge:** approve inclusion of actual repair-worker evidence and
   exclusion of controller/auditor/meta-observer prose.
6. **Retention/privacy:** approve classifications, retention periods, deletion
   obligations, promotion audiences, and authorized raw-log/tool-trace readers.
7. **Backend capability floor:** decide whether exact follow-up/cancellation is
   mandatory for a provider or an explicit optional capability.
8. **Migration and retirement:** authorize per-seam cutovers and eventual old
   launch-path deletion only after gates; this research grants none of that
   authority.
9. **Roadmap coupling:** approve three lifecycle sprints and whether they precede
   or overlap compiler M1/L1 work; decide how to account for overlap with
   `sequential-model-fallbacks`.
10. **Tree reconciliation:** select the implementation baseline after comparing
    the project checkout with pinned resident runtime revision
    `c267920b6719fb35636e1da0071b5863ec5b2a0c` and concurrent dirty work.

## Recommended sequence

1. Approve the layer/ownership decision and stable taxonomy.
2. Reconcile the implementation baseline and land the additive schema/journal
   contract with conformance fixtures only.
3. Shadow-normalize current v2 resident and automatic runs; prove exclusions and
   restart/delivery parity.
4. Wrap the shared Megaplan worker seam, preserving `WorkerResult` and every
   orchestration decision; cut over by risk tier.
5. Close compiler M1 only after all eligible seams have complete v3 streams and
   deterministic non-recursion tests.
6. Continue compiler M2–M5 against the normalized evidence contract.
7. Retire duplicate start paths one at a time with human approval; retain
   historical readers and evidence.

## Evidence inspected

### Canonical initiative and related initiative records

- `.megaplan/initiatives/session-knowledge-compiler/README.md`, `NORTHSTAR.md`,
  `research/conversation-audit-20260713.md`, `notes/megaplan-prep-20260713.md`,
  `briefs/m1.md` through `briefs/m5.md`, and `chain.yaml`
- `.megaplan/initiatives/agentbox-persistent-machine/README.md`, `NORTHSTAR.md`,
  `briefs/resident-agent-custody-and-hot-context.md`,
  `briefs/m3-megaplan-chain-adapter.md`, `briefs/m4-discord-thin-path.md`, and
  `notes/00-OVERVIEW.md`
- `.megaplan/initiatives/sequential-model-fallbacks/README.md`,
  `decisions/managed-agent-contract-boundaries.md`, and
  `research/managed-agent-current-state-20260711.md`
- `.megaplan/initiatives/discord-resident-delegation-delivery-corrective/README.md`
  and `NORTHSTAR.md`
- `.megaplan/initiatives/megaplan-maintenance/handoff/unify-automatic-repair-resident-agent-tracking-20260713.md`
- `.megaplan/tickets/01KTPVVVVV002AGENTRUNTIME-agent-runtime-extraction.md`
- `docs/agentbox-resident-boundary.md`

### Runtime/source evidence

- Neutral dispatch: `arnold/agent/contracts.py`, `dispatcher.py`, `__init__.py`,
  and `adapters/{codex,shannon,deepseek}.py`
- Phase workers/orchestration: `arnold_pipelines/megaplan/workers/_impl.py`, phase
  handlers, `auto.py`, `orchestration/phase_result.py`, `receipts/schema.py`,
  `observability/events.py`, `events_projection.py`, `routing_ledger.py`,
  `chain/spec.py`, and `chain/execution_binding.py`
- Durable automatic runtime: `arnold_pipelines/megaplan/managed_agent.py`,
  watchdog/repair/meta-repair/progress-auditor modules and wrappers
- Project resident modules and the same modules at pinned runtime
  `/workspace/arnold-consolidation-20260714` revision
  `c267920b6719fb35636e1da0071b5863ec5b2a0c`
- Current raw run manifest:
  `.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`
- Historical compiler chain/run evidence indexed by the initiative:
  `.megaplan/plans/.chains/chain-c256f171485f.json` and plan
  `.megaplan/plans/m1-durable-capture-cursors-20260713-2045/`

The pinned runtime also contained the same-topic, unintegrated draft
`/workspace/arnold-consolidation-20260714/.megaplan/initiatives/session-knowledge-compiler/research/epic-wide-managed-agent-capture-architecture-20260716.md`.
It was treated only as comparative raw evidence because its initiative baseline
and sprint count differ from this project's canonical five-sprint plan; all
current-state conclusions in this document were checked against source.

### Commands used

The read-only evidence pass used these command families (with bounded `sed`
ranges or targeted `rg` expressions):

```text
git status --short --branch
git rev-parse HEAD
rg --files .megaplan/initiatives .megaplan/tickets docs arnold arnold_pipelines tests
rg -n '<launch/session/managed-agent/repair/auditor/event/schema terms>' <scoped paths>
sed -n '<bounded range>p' <indexed documents and source modules>
cmp / diff <project module> <pinned-runtime module>
python -P - <<'PY'  # selective, non-secret JSON manifest field inspection
```

No chain, model worker, service, migration, test that launches an agent, push,
deployment, or external delivery was run.

## Self-review

- **Completeness:** inventories resident, all named Megaplan phases, chain,
  repair/meta-repair/auditor, and additional worker seams; includes schema,
  migration, tests, rollback, risks, decisions, and file/CLI/test surfaces.
- **Internal consistency:** v3 is additive; one logical run may have multiple
  attempts; orchestration, execution custody, delivery custody, and compilation
  are distinct.
- **Non-recursion:** compiler, status, auditor, delivery-verifier, controller,
  projection, retry, nested, and synthesis-owner cases have deterministic rules.
- **Backend neutrality:** Codex, Claude, and Hermes share a lifecycle contract
  with explicit capabilities; Discord appears only at ingress/delivery.
- **Megaplan semantics:** phases, profiles, gates, retries, modes, chain state,
  review/rework, watchdog policy, and authorization remain Megaplan-owned.
- **Initiative compliance:** one canonical research artifact is indexed from
  `session-knowledge-compiler`; no file is written under `.megaplan/briefs`, and
  no new initiative is created.
