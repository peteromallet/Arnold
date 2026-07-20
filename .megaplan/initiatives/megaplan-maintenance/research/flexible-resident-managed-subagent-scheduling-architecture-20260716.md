# Flexible resident-managed subagent scheduling architecture

Status: research specification; no implementation or execution authority

Owner: single synthesis/delivery owner, resident run `subagent-20260716-180912-f35a37b5`

Resident runtime baseline: `235472012dc3dcada37207b39e65f7fcc8675185`

Prepared: `2026-07-16T00:00:00Z` (document date; evidence times retain their source timestamps)

## Decision summary

Broadly flexible scheduling is compatible with the current resident architecture if schedules become durable, versioned control-plane objects and each nominal firing becomes an immutable occurrence that enters the existing resident scheduler. The occurrence handler should commit a resident-managed Codex launch through the existing provenance, queue, manifest, synthesis-owner, and completion-delivery seams. It must not launch an ad hoc process or deliver output itself.

The minimum compatible path is therefore:

1. add `ScheduleDefinition` and immutable `ScheduleOccurrence` records alongside, rather than inside, the existing `ScheduledJob` record;
2. add one resident handler that materializes an authorized occurrence into the existing managed-agent launch boundary;
3. calculate recurring nominal times from the schedule definition and anchor, not from handler completion time;
4. use stable occurrence and launch keys, transactional claims/fencing where available, and the existing managed-run delivery outbox;
5. preserve the current six-hour VP sweep as a compatibility target while migrating its handler-created recurrence to the same definition/occurrence mechanism.

This is a specification, not approval to implement, launch, migrate, deploy, restart, or alter runtime behavior.

## Knowledge placement and search result

Initiative search was performed before this document was created, by rough title/slug/description and then by related ticket/document terms.

- `megaplan-maintenance` was the closest canonical initiative: its README explicitly owns the six-hour operational unblocker, watchdog supervision, and safe repair custody.
- `sequential-model-fallbacks` is related because it owns common managed-agent contracts.
- `discord-resident-delegation-delivery-corrective` is related because it owns resident ingress, immutable source custody, and Discord completion delivery.
- No initiative matched flexible resident scheduling more closely.
- Ticket CLI search for `scheduler`, `recurring`, `subagent`, and `reminder` could not complete because a pre-existing malformed ticket YAML document aborts repository-wide ticket parsing. A bounded text search of `.megaplan/tickets` found no scheduling ticket. No ticket was created.

This research therefore belongs here, under the existing maintenance initiative. It does not create or launch an initiative or chain, and it does not change the ownership boundaries of the two related initiatives.

## Evidence method and confidence labels

The pinned resident source was inspected with `git show 235472012dc3dcada37207b39e65f7fcc8675185:<path>` where runtime/source drift mattered. The live resident store and cloud evidence were read without mutation. The project checkout differs from the pinned runtime and contains unrelated concurrent work; that distinction is material to any later implementation.

Labels used below:

- **Observed**: directly supported by inspected source, configuration, test, or durable evidence.
- **Inference**: a conclusion from observed behavior that is not itself an encoded contract.
- **Recommendation**: proposed behavior for the general capability.

## Current architecture: observed behavior

### Resident scheduled jobs

**Observed.** `resident/scheduler.py` defines durable `ScheduledJob` records with `pending`, `claimed`, `fired`, `cancelled`, and `failed` status values. The registered resident job types are `cloud_check`, `deferred_turn`, `heartbeat`, `confirmation_expiry`, and `vp_todo_sweep`. The Discord resident loop polls due jobs every 10 seconds by default, claims at most 10, and treats a claim as stale after 600 seconds by default.

The database backend claims due jobs with an atomic update and `FOR UPDATE SKIP LOCKED`. The file backend lists and then updates JSON records without a store-wide transaction or file lock. Handlers run sequentially within one claimed batch. A handler exception returns the job to `pending` after a default 30-second retry while attempts remain; exhaustion records the job as `cancelled`, not as a distinct dead-letter or `failed` terminal outcome.

`idempotency_key` exists on the record and API, but the inspected file and database create/update paths do not enforce uniqueness or lookup by that key. Several handlers implement “list pending, then create” suppression, which is not an atomic compare-and-create operation.

**Inference.** A single resident worker gives practical duplicate resistance today, but multi-worker file-store execution can double-claim, and crashes between an external effect and `mark_fired` can replay a handler. The current interface is therefore at-least-once at the handler boundary, with incomplete fencing.

### Six-hour VP check-in

**Observed.** On Discord resident readiness, the runtime seeds a `vp_todo_sweep` when no pending sweep exists. Its payload carries a 21,600-second interval and its maximum attempt count is three. The handler:

1. evaluates pending VP special requests;
2. creates a provenance-bearing `scheduled_turn` inbound event when work exists;
3. invokes the resident turn boundary;
4. creates another one-shot sweep for `utc_now() + interval`, including when the runtime is disabled or no todo is due.

Thus this is fixed delay from handler execution, not a fixed-rate clock. A pending job suppresses the normal seed, but the suppression is not transactional. The scheduled turn may launch a managed Codex subagent; the scheduler does not itself own that subagent's completion delivery.

Durable store evidence under `.megaplan/resident/scheduled_jobs/` shows `job_ffafb6df846a` fired at `2026-07-16T17:56:37.919258Z` and created pending `job_8ce54c63fcc0` for `2026-07-16T23:56:38.215449Z`, with interval 21,600 and attempt count zero. Older evidence includes a sweep scheduled for `2026-07-02T14:19:00Z` that fired on `2026-07-04T22:03:00Z` after downtime.

**Inference.** Due one-shot jobs persist across a stopped resident and run after recovery, but recurrence drifts from the actual recovery time. There is no explicit grace window, bounded catch-up count, or declared missed-run policy.

### Scheduled cloud checks

**Observed.** The admin-only `schedule_cloud_check` tool creates one-shot `cloud_check` jobs. While a checked operation remains active, the handler creates the next one-shot at its configured interval. Terminal or input-needed state stops recurrence and can notify the configured route. `cancel_cloud_check` marks a pending job cancelled; `list_cloud_checks` is read-only. This is another handler-owned recurrence loop rather than a reusable recurrence contract.

### Managed subagent launch, queue, and custody

**Observed.** `resident/subagent.py` and `docs/agentbox-resident-boundary.md` define `arnold-managed-agent-run-v2` manifests beneath `.megaplan/plans/resident-subagents/<run-id>/`, with prompt, manifest, run log, result, immutable launch provenance, work intent, correlation, custody, source records, and task digests. A stable launch key and `.launch.lock` make exact launch replays idempotent; intentional retries link through `retry_of_run_id`.

Queued successors use the same manifest. They support success dependencies, up to eight direct predecessors, bounded depth/ancestry, queue locks, execution locks, bounded exponential launch retries, fail-closed dependency checks, fan-in, restart reconciliation, and cancellation/failure propagation. Exactly one `synthesis_delivery_owner` owns an aggregated completion; internal contributors do not independently deliver.

A terminal process result does not deliver directly. A resident completion turn independently verifies it, then a `completion_delivery` outbox routes to the exact approved target. Delivery uses a stable nonce, per-manifest lock, bounded exponential retries (30 seconds through a one-hour cap, at most eight attempts), permanent-failure classification, and provider acceptance evidence. Ambiguous acceptance is recorded as `unknown`; routing is never reconstructed from a recent-message guess.

The launch tool requires an authoritative stored inbound event. A scheduled turn must name the exact todo request and task; it cannot borrow provenance from another message or a summary. The inherited work intent and immutable source envelope cannot be widened by a schedule.

### Restart reconciliation, watchdog, and audit timers

**Observed.** On resident readiness, managed queues and delivery outboxes are reconciled before normal polling. The resident loop repeats queue reconciliation and delivery sweeping approximately every 10 seconds. The resident scheduler's JSON records, managed-run manifests, and delivery outboxes survive process restart.

The cloud host independently defines persistent systemd timers:

- `megaplan-progress-audit.timer`: five minutes after boot, then every six hours, five-minute accuracy;
- `megaplan-watchdog-ensure.timer`: every minute;
- `megaplan-resident-ensure.timer`: every five minutes.

The progress-audit wrapper discovers workspaces, runs the six-hour evaluator, and writes timestamped JSON/Markdown reports plus an append-only log. Its inspected revision is evaluator-first: ordinary findings are report-only; only a coherent true-stall escalation can enter the central repair queue. The watchdog monitors chain/runtime evidence and can request bounded repair under separate custody. It is not the resident subagent scheduler.

The latest inspected report, `/workspace/audit-reports/20260716T135924Z-audit.json`, records `schema_version: 1`, `dispatch_summary.mode: report_only`, coverage/data-quality evidence, and no model run, repair, file edit, git commit, or managed-agent dispatch. Multiple reports on some dates mean report timestamps alone do not prove every invocation came from systemd; timer configuration proves intended cadence, while reports prove wrapper execution.

### Other scheduling substrates

**Observed.** Hermes cron (`arnold/agent/cron/`) supports delay/at-time one-shots, intervals, five- or six-field cron, finite repeats, pause/resume/update/remove/manual trigger, model/provider/skills, and origin delivery. It uses a JSON job file and a process-wide tick lock. Recurring jobs that are too stale are fast-forwarded; one-shots have a recovery grace. A run counts toward its repetition limit whether it succeeds or fails, and delivery errors are logged but are not an outbox state. Naive times use the host's local-time interpretation. It launches a fresh Hermes agent and does not use resident managed-run provenance or delivery custody.

Guardian (`arnold/runtime/durable_ops/scheduled_task.py`, `agentbox/guardian/`) has a stronger generic scheduled-task record: lease owner/token/expiry, heartbeat, lock version, idempotency key, retry delay, finite failure count, cancellation, and fixed-delay recurrence. Guardian idempotently registers four fixed tasks at 60/300/900/300-second intervals. Its briefing and reminder handlers currently only record that the tick was reached. It has no cron/calendar/timezone contract and is not wired to resident managed-agent launch/delivery.

**Recommendation.** Borrow Hermes schedule parsing/misfire tests and Guardian lease/fencing concepts. Do not route resident-managed Codex schedules through either subsystem, because doing so would fork source custody, authorization, synthesis ownership, and completion delivery.

## Gaps between current behavior and the goal

The current resident scheduler lacks a first-class schedule definition, cron/calendar semantics, timezone and daylight-saving rules, finite repetitions/end dates, pause/resume/update, explicit misfire and overlap policies, dependency expressions, schedule-level quotas, immutable prompt versioning, enforced idempotency keys, fencing tokens on file claims, and a dead-letter state. Cancellation is job-type-specific and normally affects only a pending job, not an already launched managed run. Recurrence is duplicated in handlers and anchored to completion time.

The managed-agent subsystem already supplies most of the difficult post-fire properties: immutable authorization provenance, exact launch idempotency, dependency queues, bounded retries, synthesis ownership, durable results, restart reconciliation, and exact-route delivery. The design should connect these systems without duplicating them.

## Proposed contracts

### Schedule definition: `arnold-resident-schedule-v1`

```yaml
schema: arnold-resident-schedule-v1
schedule_id: sched_vp_six_hour_audit
revision: 1
generation: 1
state: active                 # draft | active | paused | cancelled | exhausted
owner:
  principal_id: resident_role:vp
  custody_scope: megaplan-maintenance
authorization:
  grant_id: grant_opaque
  source_envelope_digest: sha256:opaque
  approved_at: 2026-07-16T18:00:00Z
  expires_at: null
  maximum_work_intent: review
schedule:
  kind: interval              # at | delay | interval | cron | calendar | event
  every: PT6H
  anchor_at: 2026-07-16T18:00:00Z
  cadence: fixed_rate         # fixed_rate | fixed_delay
  timezone: UTC
  gap_policy: next_valid      # reject | skip | next_valid
  fold_policy: first          # first | second | both
bounds:
  max_occurrences: null
  end_at: null
policies:
  misfire: latest_once        # skip | latest_once | catch_up
  catch_up_limit: 1
  overlap: forbid             # allow | forbid | queue | replace
  concurrency_key: vp-special-request-audit
  max_active: 1
target:
  kind: resident_orchestrator_turn
  prompt_ref: resident-prompt://vp-special-request-audit/v1
  prompt_digest: sha256:opaque
  model: gpt-5.6-sol
  profile: resident-subagent-standard
  toolsets: [resident_read, resident_launch]
  work_intent: review
  task_kind: audit
delivery:
  synthesis_owner: schedule_root
  route_ref: inherited-source-route
  mode: exact_authorized_route
retry:
  launch_max_attempts: 3
  initial_backoff: PT30S
  maximum_backoff: PT1H
quota:
  max_runs_per_day: 4
  max_concurrent_runs: 1
  maximum_cost_usd_per_day: null
created_at: 2026-07-16T18:00:00Z
updated_at: 2026-07-16T18:00:00Z
```

Contract rules:

- `schedule_id` is stable; updates append a revision and increment `generation` when future occurrence identity can change.
- All instants are stored in UTC. Cron/calendar definitions additionally retain an IANA timezone and the original local-time expression. Fixed intervals are elapsed-time schedules; calendar schedules follow civil time.
- `prompt_ref` resolves only to immutable, content-addressed prompt bytes. The digest, model/profile/toolset selection, work intent, route, authorization grant, and schedule revision are copied into every occurrence and managed-run manifest.
- An authorization grant is immutable and scope-limiting. Updating a schedule to a stronger model/toolset/work intent, broader route, larger cost cap, or later authorization expiry requires a new grant; an update cannot reinterpret the original source envelope.
- `delay` is normalized at activation into an `at` instant while retaining the original relative expression for audit.
- `max_occurrences` counts terminal occurrence decisions, including policy-suppressed occurrences, unless an explicit `count_mode` is added later. Failures do not silently extend an authorization window.

### Occurrence: `arnold-resident-schedule-occurrence-v1`

```yaml
schema: arnold-resident-schedule-occurrence-v1
occurrence_id: occ_sched_vp_six_hour_audit_g1_20260717T000000Z
occurrence_key: sha256:schedule-id-generation-nominal-time
schedule_id: sched_vp_six_hour_audit
schedule_revision: 1
generation: 1
nominal_at: 2026-07-17T00:00:00Z
eligible_at: 2026-07-17T00:00:00Z
state: scheduled             # scheduled | claimed | launch_committed | launched | terminal | suppressed | cancelled | dead_letter
attempt: 0
claim:
  owner: null
  token: null
  fence: 0
  expires_at: null
decision:
  misfire: on_time
  overlap: admitted
launch:
  launch_key: sha256:occurrence-and-pinned-launch-spec
  run_id: null
  manifest_digest: null
authorization_digest: sha256:immutable-grant-and-source
created_at: 2026-07-16T18:00:00Z
updated_at: 2026-07-16T18:00:00Z
```

The unique key is `(schedule_id, generation, nominal_at)`. Materialization is an atomic insert-or-observe operation. The scheduler may retry an occurrence, but it must reuse its `occurrence_key` and `launch_key`. A managed-run manifest commit advances it to `launch_committed`; process creation may then be retried through the existing launch reconciliation. This separates “the clock fired” from “a process started” and “a result was delivered.”

### State machines

Schedule definition:

```text
draft -> active <-> paused
           |  \       |
           |   \      v
           |    -> cancelled
           v
        exhausted
```

`cancelled` and `exhausted` are terminal. Pausing prevents new claims/materialization but does not implicitly terminate a managed run already committed. Resume computes future occurrences using the declared misfire policy. Updating creates a new revision; incompatible timing updates increment generation and cancel or suppress unclaimed old-generation occurrences.

Occurrence:

```text
scheduled -> claimed -> launch_committed -> launched -> terminal
    |           |              |
    |           +-> scheduled  +-> dead_letter
    +-> suppressed
    +-> cancelled
```

Only lease expiry or a retryable pre-commit failure returns `claimed` to `scheduled`. Once the managed manifest is committed, existing managed-run reconciliation owns launch retries and terminalization. `terminal` means the managed run reached a terminal state; delivery retains its own existing `pending | delivered | retry_pending | failed | unknown | not_applicable` state. Delivery failure never causes the task to execute again.

## Scheduling semantics

### Time forms

- **One-shot at time:** an RFC 3339 instant with explicit offset. Normalize to UTC.
- **One-shot delay:** an ISO 8601 duration resolved once against the accepted activation timestamp.
- **Fixed interval:** ISO 8601 elapsed duration plus UTC anchor; `fixed_rate` preserves nominal cadence, while explicitly requested `fixed_delay` schedules from terminal handler time.
- **Cron:** canonical five-field cron initially. Seconds/year extensions require a versioned grammar. Store expression, parser version, IANA timezone, gap/fold policy, and anchor.
- **Calendar:** typed local rules such as “09:00 on the first business day,” rather than forcing complex civil-time intent into cron. Holiday calendars are named, versioned dependencies.
- **Event/condition:** phase-two typed event selectors over the append-only resident/maintenance event stream. Conditions reference a versioned declarative predicate, never arbitrary code. Require event ID dedupe, debounce, cooldown, and maximum firing rate.

### Timezone and daylight saving

UTC remains the control-plane and evidence representation. A calendar or cron schedule stores an IANA zone (for example `America/New_York`) and local intent. At a spring-forward gap, `reject`, `skip`, or `next_valid` is mandatory. At a fall-back fold, `first`, `second`, or `both` is mandatory. The timezone database version used for each materialization is recorded. A timezone database update does not rewrite already materialized occurrences; future materialization uses a new schedule revision or records the changed database version.

### Missed runs and catch-up

- `skip`: suppress all missed nominal occurrences and materialize the next future one.
- `latest_once`: suppress all but the latest eligible missed occurrence and run it once. This is the recommended default for audits and notifications.
- `catch_up`: run oldest-first up to `catch_up_limit`; suppress the remainder with receipts.

Each schedule also declares a grace duration. A paused schedule does not accumulate catch-up unless configured. Recovery applies quota and overlap checks before admission, preventing restart storms.

### Overlap, concurrency, dependencies

- `allow`: admit occurrences up to `max_active`.
- `forbid`: suppress an occurrence if another in the concurrency group is active.
- `queue`: retain it until capacity is free, with a maximum queue age.
- `replace`: request cancellation of the older managed run, but only with a separately authorized run-cancellation grant; otherwise fail closed.

Concurrency is enforced at global, principal, schedule, and named-group levels before launch commit. Queue admission and launch use the same fenced reservation so concurrent workers cannot oversubscribe.

Dependencies may reference a specific managed run, the latest successful occurrence of another schedule, or a typed event watermark. Resolve them into concrete run IDs/event IDs when the occurrence becomes eligible, then reuse the existing managed successor queue. Reject cycles, unbounded “latest” ambiguity, cross-custody dependencies, and dependencies whose authorization outlives their source grant.

### Retry and dead letter

Three retry domains remain separate:

1. **Occurrence materialization/claim:** safe deterministic retries with the occurrence unique key and a bounded lease.
2. **Managed launch/execution:** existing stable launch key, manifest commit, execution lock, queue retry, and explicit intentional retry lineage.
3. **Completion delivery:** existing stable nonce and outbox retries; never re-execute because delivery failed.

Retryable pre-launch failures use exponential backoff with jitter and schedule-configured caps. Permanent authorization, prompt-digest, route, dependency, or schema failures immediately dead-letter. Exhausted transient failures enter an explicit dead-letter record containing the occurrence, attempts, receipts, and safe replay requirements. Replay creates a new authorized attempt linked to the original; it does not edit history.

## Authorization, provenance, and delivery boundaries

- Creating a schedule is authority to request future occurrences only within the immutable grant. It is not perpetual authority to widen tools, intent, destination, cost, or cancellation scope.
- The resident stores the original source-envelope digest and an immutable grant receipt. It never reconstructs a source from a channel's latest message.
- Every occurrence copies the exact schedule revision, authorization digest, principal, source/correlation/custody records, prompt digest, toolset, work intent, model/profile, and route reference into the managed-run launch request.
- External effects remain prohibited for speculative work unless a later, explicit grant authorizes them. Service administration, cross-project writes, broad messaging, repair, and `replace` cancellation are high-impact operations requiring admin or narrower dedicated approval.
- The scheduler owns timing and admission. The managed-run subsystem owns launch, queue, execution, and result durability. The synthesis owner owns the single user-facing result. The delivery outbox owns transport acceptance and retries.
- A recurring schedule needs an explicit durable delivery subscription. The compatibility default is the exact original authorized route. Retargeting, broadening to a channel, or surviving thread archival requires a new route grant; it is never guessed.

## CLI and resident API surface

Names are proposed, not implemented:

```text
megaplan resident schedule create --file schedule.yaml --dry-run
megaplan resident schedule activate <schedule-id> --grant <grant-id>
megaplan resident schedule get <schedule-id> [--history]
megaplan resident schedule list [--state active] [--owner ...]
megaplan resident schedule preview --file schedule.yaml --count 10
megaplan resident schedule update <schedule-id> --if-revision N --patch patch.yaml
megaplan resident schedule pause|resume|cancel <schedule-id> --if-revision N
megaplan resident schedule occurrences <schedule-id> [--state ...]
megaplan resident schedule replay <occurrence-id> --grant <grant-id>
megaplan resident schedule dead-letters [--schedule ...]
```

Resident tools mirror this surface with typed inputs and operation classes: preview/get/list are read; create/update/pause/resume/cancel are write; activation, replay, route expansion, execution-authority expansion, run cancellation, and quota elevation are admin or dedicated approval operations. Every mutation requires optimistic `if_revision`, an idempotency key, actor/source custody, and an audit reason. `--dry-run` validates grammar, authorization scope, next occurrence times, quota, and route without writing.

The resident internal API should expose `create_definition`, `revise_definition`, `materialize_until`, `claim_occurrences`, `commit_launch`, `suppress_occurrence`, `dead_letter_occurrence`, and `record_terminal_link`. Handlers must not directly create the next recurring job.

## Observability and receipts

Append immutable events for definition creation/revision/state change, authorization acceptance/expiry, occurrence materialization, misfire decision, concurrency admission/suppression, claim/lease/fence, launch-manifest commit, managed-run link, terminal run, delivery transition, quota decision, and dead-letter/replay. Each receipt includes schedule/revision/generation, occurrence key, nominal and actual timestamps, actor, source/custody digests, policy decision, previous-event hash or sequence, and relevant manifest/outbox IDs.

Queryable projections should expose next nominal run, last admitted/suppressed/failed occurrence, active/queued count, delivery state, rolling run/token/cost use, grant expiry, dead-letter count, and materialization watermark. Metrics should include schedule lag, materialization lag, duplicate conflicts, stale claims, launch-commit latency, active/queued counts, suppression reasons, dead letters, run outcomes, delivery outcomes, quota rejects, and estimated/actual cost. Watchdog checks should alert on stale watermarks, expired claims, launch-committed occurrences without a reconciled run, terminal runs without outbox progress, and repeated deterministic failures. The watchdog may reconcile or enqueue repair only within its existing custody; it may not silently rewrite a schedule or grant.

## Quotas and cost controls

Admission checks apply hierarchical limits: global, project/custody scope, principal, model/profile, schedule, and concurrency group. Minimum controls are runs per hour/day, active/queued runs, catch-up burst, token budget per occurrence/day, cost estimate and actual daily cap, toolset allowlist, and maximum schedule lifetime. Reserve estimated capacity before launch; settle actual usage on terminal evidence. A breached cap pauses or suppresses according to declared policy and emits a receipt. No schedule may auto-elevate its cap or switch to a more expensive profile. Profile fallback, if later allowed, must be an explicit ordered, authorized, version-pinned policy.

## Architecture options

| Option | Advantages | Material problems | Verdict |
|---|---|---|---|
| Extend resident control plane with definition/occurrence records and managed-run adapter | Reuses immutable source custody, launch idempotency, queue, synthesis ownership, restart reconciliation, and delivery outbox | Requires new recurrence engine, occurrence store, fencing, quotas, and migration | **Recommended** |
| Create one systemd timer/service per schedule | OS-level persistence and familiar operations | Dynamic user schedules become host configuration; weak per-message provenance, poor multi-tenant quotas, no managed-run/outbox transaction, deployment required per change | Retain only for host-wide watchdog/auditor services |
| Route through Hermes cron | Already supports cron, intervals, finite repeats, pause/resume | Different agent, JSON custody, local-time ambiguity, delivery without resident outbox, no managed-run provenance/dependency contract | Borrow semantics/tests only |
| Move scheduling to Guardian durable operations | Leases, heartbeat, lock version, idempotency substrate | Separate store and ownership; fixed intervals only; no resident ingress/delivery or managed launch bridge | Possible later storage convergence, not minimal path |
| External workflow engine | Mature timers, retries, workflows, visibility | New infrastructure and authority plane; substantial migration/operations burden | Revisit only after scale proves resident substrate insufficient |

## Minimal compatible implementation path

1. Introduce append-only schedule definitions, occurrence uniqueness, preview/parser library, and audit receipts behind a disabled feature flag. Use the database backend for multi-worker claims; add an OS lock or single-writer assertion for file mode.
2. Add `managed_subagent_occurrence` and `resident_orchestrator_turn` adapters. The former calls the current managed launch boundary; the latter preserves the VP sweep's conditional todo behavior. Both commit an occurrence-to-run link before acknowledging fire.
3. Move the VP sweep and cloud-check recurrence calculation into definition/occurrence materialization without changing their external behavior. Preserve existing pending jobs until terminal; do not synthesize history.
4. Add interval/at/delay, then cron/calendar plus DST policies, then lifecycle mutations and bounded misfire/overlap controls.
5. Add event triggers and cross-schedule dependencies only after time-based scheduling, authorization, dedupe, restart, and delivery gates pass.

No phase is authorized by this document. Before any source change, reconcile the project tree with pinned resident runtime revision `235472012dc3dcada37207b39e65f7fcc8675185`; the inspected project versions of `resident/subagent.py`, `resident/profile.py`, and `resident/discord.py` differ from that runtime baseline.

## Compatibility and migration

- Existing `ScheduledJob` records remain readable and executable. A legacy adapter reports them as unversioned one-shot occurrences without claiming stronger guarantees.
- Seed one disabled definition for the VP sweep, compare previewed nominal times with legacy behavior, then activate only after explicit approval. During cutover, an atomic ownership marker ensures either the legacy “next one-shot” handler or the new materializer owns recurrence, never both.
- Cloud checks preserve their current API and terminal/input-needed stop conditions; their interval becomes a generated definition only after parity tests.
- Managed-run schemas, queue semantics, result paths, delivery statuses, and stable nonces remain unchanged. New occurrence fields are additive references.
- File-store mode remains supported for a single resident with a process/file lock. Multi-worker scheduling requires the transactional database backend or a newly proven atomic file protocol.
- Rollback disables new materialization, leaves committed managed runs/outboxes to reconcile, and returns compatibility targets to their legacy seed logic. It never deletes occurrences or manifests.

## Concrete examples

### Existing six-hour VP audit in the abstraction

The full definition above is the compatibility representation. Its target is deliberately `resident_orchestrator_turn`, because the observed six-hour sweep first examines VP todos and only then may launch managed subagents. Treating every tick as an unconditional Codex process would change behavior. Migration changes recurrence custody from “handler creates next job at completion + six hours” to fixed-rate nominal occurrences; preserving exact legacy drift would instead set `cadence: fixed_delay` for the first parity stage.

Recommended policies are `latest_once`, `overlap: forbid`, one active run, three launch attempts, exact-route synthesis delivery, and a four-runs-per-day cap. The prompt/version and authorization digest are pinned in every occurrence.

### One-shot delayed architecture review

```yaml
schema: arnold-resident-schedule-v1
schedule_id: sched_review_after_45m
revision: 1
generation: 1
state: active
schedule: {kind: delay, after: PT45M, accepted_at: 2026-07-16T18:00:00Z}
bounds: {max_occurrences: 1, end_at: null}
policies: {misfire: latest_once, catch_up_limit: 1, overlap: forbid, max_active: 1}
target:
  kind: resident_managed_agent
  prompt_ref: resident-prompt://architecture-review/v3
  prompt_digest: sha256:opaque
  model: gpt-5.6-codex
  profile: resident-subagent-standard
  toolsets: [repo_read]
  work_intent: speculative
delivery: {synthesis_owner: schedule_root, route_ref: inherited-source-route, mode: exact_authorized_route}
authorization: {grant_id: grant_opaque, source_envelope_digest: 'sha256:opaque', maximum_work_intent: speculative}
```

### Daily local-time evidence digest with DST policy

```yaml
schedule_id: sched_dublin_daily_digest
revision: 1
generation: 1
state: active
schedule:
  kind: calendar
  local_time: '09:00:00'
  days: [monday, tuesday, wednesday, thursday, friday]
  timezone: Europe/Dublin
  gap_policy: next_valid
  fold_policy: first
bounds: {max_occurrences: 20, end_at: 2026-08-31T23:59:59Z}
policies: {misfire: skip, overlap: forbid, max_active: 1}
target: {kind: resident_managed_agent, prompt_ref: 'resident-prompt://evidence-digest/v1', prompt_digest: 'sha256:opaque', model: gpt-5.6-codex, profile: read-only, toolsets: [repo_read], work_intent: review}
```

### Cron schedule with finite repetitions

```yaml
schedule_id: sched_new_york_weekday_triage
revision: 1
generation: 1
state: active
schedule:
  kind: cron
  expression: '0 9 * * 1-5'
  grammar: cron-5field-v1
  timezone: America/New_York
  gap_policy: skip
  fold_policy: first
bounds: {max_occurrences: 10, end_at: null}
policies: {misfire: latest_once, catch_up_limit: 1, overlap: queue, max_active: 1, maximum_queue_age: PT8H}
target: {kind: resident_managed_agent, prompt_ref: 'resident-prompt://weekday-triage/v2', prompt_digest: 'sha256:opaque', model: gpt-5.6-codex, profile: resident-subagent-standard, toolsets: [repo_read, web_read], work_intent: review}
```

### Event-triggered failure investigator

```yaml
schedule_id: sched_chain_failure_investigator
revision: 1
generation: 1
state: active
schedule:
  kind: event
  event_type: megaplan.chain.terminal
  predicate_ref: resident-predicate://failed-or-blocked/v1
  debounce: PT5M
  cooldown: PT30M
  dedupe_key: event_id
bounds: {max_occurrences: 25, end_at: 2026-09-01T00:00:00Z}
policies: {overlap: queue, max_active: 1, maximum_queue_age: PT2H}
target: {kind: resident_managed_agent, prompt_ref: 'resident-prompt://chain-failure-investigator/v1', prompt_digest: 'sha256:opaque', model: gpt-5.6-codex, profile: read-only, toolsets: [repo_read, megaplan_observe], work_intent: speculative}
```

This event form is feasible only after a typed, append-only event subscription and predicate registry exist. It must not poll mutable status labels and infer events.

## Explicit non-goals

- Replacing the managed-agent manifest, successor queue, completion verifier, synthesis-owner, or delivery-outbox lifecycle.
- Giving a scheduler authority to deliver directly, infer a destination, broaden work intent/toolsets, repair systems, restart services, or cancel a running agent without a separate grant.
- Claiming exactly-once external effects. The contract is deterministic at-least-once reconciliation with idempotent launch/delivery boundaries and explicit uncertainty.
- Supporting arbitrary executable condition predicates, mutable “latest prompt” pointers, host-local naive timestamps, or unversioned cron/timezone semantics.
- Building a general-purpose workflow engine, calendar user interface, holiday service, or cross-product orchestration platform in the minimal path.
- Reconstructing historical schedule occurrences for legacy one-shot jobs or rewriting existing audit/managed-run evidence.
- Implementing, deploying, migrating, restarting, enabling a feature flag, or creating an execution initiative as a consequence of this research.

## Failure modes and required response

| Failure | Required response |
|---|---|
| Two workers materialize the same nominal time | Unique occurrence insert; loser observes existing receipt |
| Worker dies after claim | Lease expires; fenced re-claim; stale token cannot commit |
| Worker dies after manifest commit but before marking occurrence | Stable launch key finds the manifest; reconcile link; do not create a second run |
| Process starts ambiguously | Existing execution-lock/manifest recovery; record uncertainty, never guess success |
| Prompt/model/toolset changed after activation | Digest mismatch dead-letters; require a new revision/grant |
| Authorization expires while queued | Fail closed before launch; preserve receipt; do not extend implicitly |
| Long outage creates many due times | Apply declared grace/misfire/catch-up/quota policies with suppression receipts |
| DST gap/fold or timezone database update | Apply stored policy/version; never silently choose host-local semantics |
| Overlapping run exceeds policy | Suppress or queue; `replace` only with cancellation authority |
| Dependency never succeeds | Queue-age/dependency policy terminates or dead-letters; no infinite hidden wait |
| Delivery returns ambiguous acceptance | Existing `unknown` state and stable nonce; never re-execute task |
| Route archived/revoked | Delivery fails or requires a new route grant; never retarget automatically |
| Deterministic handler failure | Circuit-break schedule, dead-letter occurrence, alert watchdog; no hot retry loop |
| File store used by multiple workers | Refuse startup or enforce proven single-writer lock |
| Clock moves | UTC monotonic polling plus nominal instants; record observed clock skew |
| Quota/cost telemetry unavailable | Enforce conservative reservation or pause; never assume zero cost |

## Rollout stages and gates

0. **Contract-only:** schemas, parser/preview, state-machine property tests, no writes or worker registration.
1. **Shadow materialization:** compute and audit would-be occurrences beside legacy VP/cloud loops; no launches.
2. **One-shot canary:** explicitly authorized read-only one-shots, single worker, exact delivery route, kill/restart testing.
3. **Interval compatibility:** migrate one VP sweep behind an atomic ownership marker; compare lag, duplicates, and delivery.
4. **Lifecycle and policy:** pause/resume/update/cancel, quotas, misfire, overlap, dead letters, operator views.
5. **Cron/calendar:** IANA timezone and daylight-saving conformance matrix.
6. **Event/dependency:** typed events and existing successor queues, after all prior gates hold.
7. **Scale:** database multi-worker claims, capacity testing, and only then reconsider an external workflow engine.

Each stage requires explicit execution approval, reversible migration, zero unexplained duplicate launches/deliveries, and successful rollback rehearsal. This research grants none of those approvals.

## Acceptance criteria

1. Creating the same definition with the same idempotency key produces one schedule; a conflicting body is rejected.
2. For 100,000 generated nominal times across supported schedule kinds, `(schedule_id, generation, nominal_at)` is unique and deterministic under the pinned parser/timezone database.
3. Concurrent workers and crash injection at every claim/commit boundary produce exactly one managed manifest per occurrence and at most one admitted process execution.
4. A restart after any durable transition converges without losing a due occurrence, duplicating a launch, widening authority, or duplicating an accepted delivery.
5. Misfire `skip`, `latest_once`, and bounded `catch_up` match their contract under outages from one poll interval through 30 days and never exceed quotas.
6. Gap/fold tests cover at least UTC, a no-DST zone, `America/New_York`, `Europe/Dublin`, and a half-hour-offset DST zone for five years around transitions.
7. Pause prevents new claims; resume applies the declared misfire policy; update obeys optimistic revision/generation rules; cancel prevents future materialization. Already committed runs follow the explicit cancellation policy.
8. Expired, tampered, cross-custody, broadened-toolset, broadened-intent, broadened-route, and digest-mismatched launches fail closed with immutable receipts and no process.
9. Existing managed dependency, synthesis-owner, retry, result, and delivery tests pass unchanged; scheduled completions route exactly once to the authorized destination or end in an explicit `failed`/`unknown` delivery state.
10. Retry exhaustion produces an inspectable dead letter; delivery exhaustion never reruns the task.
11. Hierarchical concurrency and daily run/token/cost caps hold under parallel admission and catch-up storms; unavailable accounting fails according to the declared conservative policy.
12. Legacy VP sweep and cloud-check behavior remain available during migration, with an enforced single recurrence owner and a tested rollback.
13. Watchdog detects a stale materialization watermark, expired claim, orphan launch commit, stuck outbox, and deterministic failure loop within declared SLOs without rewriting authority.
14. Audit projections can trace schedule -> revision/grant -> occurrence -> managed run/queue -> result -> synthesis owner -> delivery receipt without consulting mutable chat history.

## Test strategy

- **Unit:** schedule grammar and normalization, interval/calendar generation, revision/generation rules, unique keys, prompt/grant digests, state transitions, backoff/jitter bounds, quotas, dependency cycle detection, misfire/overlap policies, and redaction.
- **Property/fuzz:** determinism, no duplicate nominal times, monotonic materialization watermark, arbitrary pause/update/restart sequences, cron parser bounds, and state-machine transition invariants.
- **Timezone/DST:** golden cases for gaps/folds, non-hour offsets, leap days, month ends, timezone database version changes, and explicit-offset one-shots.
- **Store concurrency:** database transaction/`SKIP LOCKED` tests; file single-writer refusal/lock tests; stale lease/fence tests with many workers.
- **Integration:** occurrence -> managed manifest -> queue/dependency -> worker -> result -> completion verifier -> delivery outbox using existing resident fixtures and exact source custody.
- **Crash/restart:** kill after occurrence insert, claim, launch key reservation, manifest commit, process spawn, terminal result, synthesis commit, transport request, and provider acceptance. Verify convergence and stable identifiers.
- **Authorization/provenance:** missing/tampered/expired grants, mixed-message bursts, source-summary substitution, cross-project dependency, work-intent/toolset/route/cost expansion, and unauthorized replacement cancellation.
- **Delivery:** transient/permanent/ambiguous transport outcomes, archived routes, stable nonce, retry cap, and single-owner aggregation.
- **Compatibility:** shadow VP and cloud schedules against legacy next-run decisions; ensure only one recurrence owner during cutover and rollback.
- **Watchdog/observability:** stale and orphan fixtures, deterministic retry-loop detection, receipt-chain integrity, metric cardinality limits, and redaction of message bodies/credentials.

## Unresolved decisions

1. Whether initial recurrence should preserve legacy fixed-delay drift or move the VP sweep immediately to fixed-rate nominal cadence.
2. Database-first multi-worker support versus an explicitly single-writer file-mode contract.
3. The cron grammar/version and timezone database upgrade policy.
4. Exact gap/fold defaults; the spec requires explicit stored values but product defaults need approval.
5. Whether repetition limits count suppressed occurrences, admitted runs, or successful runs; this document recommends terminal occurrence decisions.
6. The durable grant issuer, revocation propagation SLO, and maximum lifetime for recurring authority.
7. The default long-lived delivery route when an original Discord thread is archived or access changes.
8. Cost source of truth and fail-closed reservation policy when usage pricing/telemetry is unavailable.
9. Whether `replace` overlap is needed at all; it adds materially stronger cancellation authority.
10. Holiday/business-calendar ownership and versioning.
11. Retention and compaction of occurrence/receipt/dead-letter history without weakening auditability.
12. Whether the existing `ScheduledJob` table should eventually become a projection over the richer durable-operations substrate.

## Sizing and decomposition (planning estimate only)

This is likely six to nine engineer-weeks for a production-safe single-worker capability and ten to fourteen for database-backed multi-worker, cron/calendar, event triggers, quotas, migration, and operational hardening. A realistic decomposition is:

- contracts, parser/preview, receipts, and state-machine tests: 1–2 weeks;
- occurrence store, idempotency, leases/fencing, and restart recovery: 2–3 weeks;
- managed-run adapter, authorization, synthesis/delivery integration: 1–2 weeks;
- lifecycle, overlap/misfire, quotas, dead letters, and operator API: 2–3 weeks;
- cron/calendar/DST and event/dependency support: 2–3 weeks;
- shadow migration, watchdog dashboards, fault injection, rollout/rollback: 2–3 weeks.

These ranges overlap with parallel staffing but not with independent delivery ownership. They identify work packages; they do not imply execution approval or justify creating a chain.

## Evidence inventory

Pinned resident runtime source, revision `235472012dc3dcada37207b39e65f7fcc8675185`:

- `arnold_pipelines/megaplan/resident/scheduler.py`
- `arnold_pipelines/megaplan/resident/discord.py`
- `arnold_pipelines/megaplan/resident/subagent.py`
- `arnold_pipelines/megaplan/store/base.py`
- `arnold_pipelines/megaplan/store/_file/operations.py`
- `arnold_pipelines/megaplan/store/_db/operations.py`
- `arnold_pipelines/megaplan/schemas/sprint1.py`
- `arnold_pipelines/megaplan/resident/tool_registry.py`
- `arnold_pipelines/megaplan/resident/auth.py`
- `docs/agentbox-resident-boundary.md`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.timer`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.service`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-watchdog-ensure.timer`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-resident-ensure.timer`
- `arnold_pipelines/megaplan/cloud/six_hour_auditor.py`
- `arnold/runtime/durable_ops/scheduled_task.py`
- `agentbox/guardian/scheduler.py`
- `agentbox/guardian/worker.py`
- `agentbox/guardian/briefing.py`
- `arnold/agent/cron/jobs.py`
- `arnold/agent/cron/scheduler.py`

Focused test evidence inspected:

- `tests/resident/test_scheduler_notifications.py`
- `tests/resident/test_vp_todo_sweep_handler.py`
- `tests/resident/test_subagent_queue.py`
- `tests/resident/test_subagent_followup.py`
- `tests/resident/test_subagent_restart_persistence.py`
- `tests/resident/test_subagent_terminal_delivery_contract.py`
- `tests/resident/test_timezone_localization.py`
- `tests/cloud/test_six_hour_auditor.py`
- watchdog tests located by `tests/**/test*watchdog*.py`

Durable/live evidence read without mutation:

- project store `.megaplan/resident/scheduled_jobs/*.json`
- project store `.megaplan/resident/system_logs/*.json`
- synthesis run `.megaplan/plans/resident-subagents/subagent-20260716-180912-f35a37b5/{manifest.json,prompt.md,run.log,result.md}`
- managed runs `.megaplan/plans/resident-subagents/*/{manifest.json,prompt.md,run.log,result.md}`
- `/workspace/audit-reports/20260716T135924Z-audit.{json,md}` and adjacent reports
- `/workspace/audit-report.log`
- `/workspace/watchdog-report.json`
- `/usr/local/bin/arnold-progress-auditor`
- `/workspace/.megaplan/cloud-sessions/*/markers/`
- `/workspace/.megaplan/cloud-sessions/*/repair-data/`
- resident bounded context routes for root, todos, runtime, and agents/recent/running

Related canonical knowledge inspected:

- `.megaplan/initiatives/megaplan-maintenance/README.md`
- `.megaplan/initiatives/megaplan-maintenance/research/resident-six-hour-and-daily-architecture-synthesis-20260711.md`
- `.megaplan/initiatives/megaplan-maintenance/decisions/authority-ledger-and-loop-boundaries.md`
- `.megaplan/initiatives/megaplan-maintenance/research/megaplan-live-watchdog-supervisor.md`
- `.megaplan/initiatives/discord-resident-delegation-delivery-corrective/README.md`
- `.megaplan/initiatives/sequential-model-fallbacks/README.md`
- `.megaplan/initiatives/sequential-model-fallbacks/decisions/durable-resident-subagent-successor-queues.md`

## Verification record

The research used read-only source/store/context inspection. No services were restarted, no scheduler or resident commands that mutate state were invoked, no runtime files/configuration were changed, and no chain/initiative/ticket was created or launched. Structured YAML examples were parsed after authoring; repository diff and status were reviewed with scope limited to this research document and its README index entry. Any later implementation must repeat tests against a reconciled source/runtime tree, because the project checkout and pinned resident runtime differ.
