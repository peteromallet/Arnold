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

The final implementation SHA, integrated target SHA, diff/check suite, installed editable source/revision, supported deployment receipt, service health, and disposable no-effect schedule probe are recorded in the delegation custody receipt and deployment evidence produced with this handoff.
