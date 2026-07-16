# Flexible resident-managed scheduling implementation and operator handoff

Status: implemented on the pinned resident-runtime line; deployment evidence is appended after local integration.

Requirements source: `Flexible resident-managed subagent scheduling architecture`, indexed by the Megaplan Maintenance front door in the project checkout and owned by durable resident run `subagent-20260716-180912-f35a37b5`.

Raw architecture-run evidence:

- `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-180912-f35a37b5/manifest.json`
- `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-180912-f35a37b5/prompt.md`
- `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-180912-f35a37b5/run.log`
- `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-180912-f35a37b5/result.md`
- `/workspace/arnold/.megaplan/initiatives/megaplan-maintenance/research/flexible-resident-managed-subagent-scheduling-architecture-20260716.md`

## Delivered scope

`arnold_pipelines.megaplan.resident.schedules` implements the versioned `arnold-resident-schedule-v1` definition and immutable `arnold-resident-schedule-occurrence-v1` record. Definition revisions are append-only; future-affecting timing changes increment generation. Occurrences are written once, while claims, fences, policy decisions, launch links, terminal reconciliation, and dead letters are append-only hash-linked receipts projected at read time.

The resident supports explicit-offset `at`, normalized `delay`, fixed-rate and fixed-delay `interval`, versioned five-field `cron`, typed local-time `calendar`, and typed append-only `event` selectors. Cron/calendar use IANA zones, record the system tzdb version on each occurrence, and require explicit gap/fold behavior. Event selectors allow only exact declarative field predicates, stable event IDs, dedupe, debounce, and cooldown; arbitrary executable predicates are rejected by construction.

The normal resident scheduler sweep materializes and claims schedule occurrences before legacy scheduled jobs. A resident-managed-agent occurrence calls the existing `launch_subagent_task` boundary with the immutable authorization/source envelope and a pinned schedule context. That context contributes to the existing stable launch key and is copied into the managed-run manifest. Existing manifest/execution locks, successor dependencies, synthesis ownership, result durability, completion verifier, and exact-route delivery outbox remain authoritative. Terminal manifest state is reconciled back into the occurrence without re-executing on delivery failure.

The `resident_orchestrator_turn` adapter supports no-effect probes and schedule-owned VP todo sweeps. A VP occurrence commits one idempotent legacy job carrying the occurrence custody; the existing VP handler performs its conditional todo/provenance turn and the schedule-owned marker prevents that handler from creating a second recurrence owner. The occurrence reconciles from the legacy job terminal receipt.

Lifecycle operations are exposed at `megaplan resident schedule`: create/dry-run, preview, get/history, list, update with optimistic revision, activate, pause, resume, cancel, occurrences, typed event ingestion, dead-letter listing, replay under a new grant, and run-once. Mutation receipts retain actor, source digest, revision/generation, nominal time, previous event hash, and policy decision. `resident health` projects schedule/occurrence counts, stale claims, orphan launch commits, and next nominal times.

Recovery uses one OS-flocked file writer, deterministic occurrence keys, bounded claims with monotonically increasing fences, stable managed launch keys, exponential pre-launch retry, explicit dead letters, restart materialization/reconciliation, and replay that requires a new immutable grant. Duplicate definition and event retries return the prior object; conflicting idempotency bodies fail closed.

Admission enforces schedule, concurrency-group, principal, custody-scope, model, and global active-run caps. It also enforces hourly/daily schedule run caps, catch-up bounds, overlap policy, finite occurrence/end/lifetime bounds, and exact authorization route/work-intent limits. Token/cost caps fail closed until authoritative usage accounting is available; schedules cannot elevate or fall back to a costlier profile automatically.

## Conservative decisions

- File mode is an explicitly single-writer v1 contract protected by an OS lock. Database multi-worker scheduling remains disabled rather than claiming unproved transactional parity.
- Fixed-rate is the default interval cadence; fixed-delay remains available when drift is intentional. No automatic VP sweep cutover occurred, so legacy recurrence cannot split-brain.
- Gap/fold choices are mandatory persisted policy. Defaults are fail-closed gap rejection and first-fold selection; definitions should state them explicitly.
- Terminal occurrence decisions, including suppression and dead letter, count toward `max_occurrences`.
- Ordinary revisions may not mutate owner/custody. Authorization changes require a new `grant_id`, and all replacements are revalidated against work-intent and route constraints.
- `replace` overlap is rejected because it needs separate run-cancellation authority. Queue/forbid/allow are supported.
- Event support is intentionally declarative and typed. Cross-schedule “latest success” dependency expressions and holiday calendars remain deferred; concrete managed-run predecessor IDs are supported through the existing successor queue.
- The original Discord route is retained exactly. Archived or revoked routes fail in the existing delivery outbox and are never guessed or broadened.

## Rollback and compatibility

Existing `ScheduledJob` records and handlers remain unchanged. With no active definitions the only runtime change is an empty, locked schedule scan before each legacy scheduler batch. Paused/cancelled definitions do not materialize. Rollback removes the scheduler callback or pauses definitions; already committed managed runs and delivery outboxes continue normal reconciliation. Occurrences and receipts are never deleted or rewritten.

## Verification and deployment record

Base revision was `235472012dc3dcada37207b39e65f7fcc8675185`. The implementation was rebased over concurrent target work and committed as `c236b642dba787ea964574265cf062a9bb2cf65d`, then atomically fast-forwarded from target revision `69b11f4f8f950ea63b2e8df0a6a6d51e2fb68603`. The isolated worktree is `/workspace/.megaplan-worktrees/resident-scheduling-foundation`; the dirty launch checkouts were not edited.

Reviewed verification:

- `git diff --check` and changed-module compilation passed.
- Focused schedule/managed-launch/restart/delivery suite: 80 passed.
- Post-rebase schedule, VP reconciliation, managed queue/restart/delivery suite: 121 passed.
- Full resident suite: 443 passed; one unrelated live-followup subprocess-count test failed only in the long aggregate and passed both isolated reruns. No scheduling assertion failed.

The editable install was rebound to the clean integrated worktree and a fresh process from `/tmp` imported `arnold_pipelines` and `agentbox` from it. The first guarded restart receipt (`reset-fbeea38b0f8c4adbb3958d14dc264f86`) succeeded but the replacement process exposed a stale runtime source. A second receipt (`reset-107f9fff5ae1448f97576cfec490432a`) requested the correct source/revision and also succeeded, while `/proc` proved a later duplicate `MEGAPLAN_RUNTIME_SRC` export still won at process start. Both hot-environment assignments were reconciled to the integrated worktree; neither PID nor command acknowledgement was treated as deployment success.

The final evidence-only commit containing this record is the exact deployment revision. Its fresh guarded restart receipt, replacement-process environment, service-ready log, installed import/revision probe, representative no-effect schedules, supported cancellations, final target ancestry, and custody JSON are recorded at `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-182958-b17b2e69/git-custody-evidence.json` and adjacent deployment evidence. The runtime is accepted only if all of those sources agree.
