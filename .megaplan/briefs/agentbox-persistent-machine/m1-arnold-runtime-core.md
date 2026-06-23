# M1: Arnold Runtime Core For AgentBox

Overall plan difficulty: 5/5; selected profile: partnered-5; because a bad Arnold-level operation/schedule/resource model would force every future pipeline to fake fields or build a parallel runtime.

## Outcome

Add Arnold-level runtime contracts for long-running operations: durable operation model, event model, state machine, typed resources, scheduled tasks, approval linkage, and operation-handler contract skeleton. AgentBox is the first consumer, not the owner of these primitives.

## Scope

In:

- run a post-python-shaped-M3 preflight before implementation: confirm the base includes merged M3, required checks are green, and there is no unresolved churn around policy slots, suspension semantics, route labels, or loop semantics;
- confirm AgentBox M1 does not depend on python-shaped workflow internals such as authored workflow source, generated DSL internals, or Megaplan planning topology files;
- define Arnold operation identity, state, parent/child relationships, retries, status transitions, and optimistic update/locking;
- define operation event model and per-operation debug/replay artifacts;
- define typed operation resources such as `git_worktree`, `process_session`, `log`, `data_volume`, and `external_service`;
- define Arnold scheduled task model with owner, cadence/cron, jitter, lease, last result, next run, failure count, and payload;
- link operation approvals to existing resident confirmation/approval machinery;
- define a minimal operation-handler protocol such as `launch`, `tick`, `resume`, `summarize`, `cleanup_descriptor`;
- define only neutral resource/handler extension points needed by host providers;
- add package-boundary documentation showing Arnold core, Megaplan adapter, and AgentBox distribution dependencies.

Out:

- concrete Megaplan chain launch;
- concrete Discord tool profile;
- Guardian worker implementation;
- credential push implementation;
- GitHub cleanup implementation;
- concrete host/tmux/worktree provider implementation;
- remote bootstrap.

## Locked Decisions

- Arnold owns operation, scheduled-task, neutral resource, approval, and reconcile-state contracts.
- AgentBox packages those contracts for a one-machine persistent host.
- Megaplan owns the first operation adapter, `megaplan_chain`.
- Store state is the queryable current-state view; per-operation files/events are debug/replay artifacts.
- Normal canonical checkouts are v0 AgentBox resources, not Arnold schema assumptions.
- Avoid colliding with the existing plugin dispatch `arnold.runtime.operations.OperationRegistry`; persisted operation records should be named deliberately, for example `ManagedOperation`, `DurableOperation`, or `OperationRun`.
- AgentBox may start after python-shaped M3 is merged; it should not wait for M4+ but must avoid depending on M4 authored-workflow migration surfaces.

## Open Questions

- Exact module/package placement for Arnold runtime core.
- Exact Store model names and migration shape.
- Minimum file-store parity needed in this milestone.
- How much of existing `CloudRun`, `ScheduledJob`, `ProgressEvent`, and `ControlMessage` can be reused directly versus adapted.
- Whether any resident runtime interfaces need to move up to Arnold before M4.

## Constraints

- Do not create an AgentBox-only database or runtime model.
- Do not bake tmux/worktree/Megaplan fields into the core operation schema; use typed resources.
- Do not put AgentBox host, CLI, Discord, systemd, or Hetzner code in Arnold core.
- Do not put `megaplan_chain` behavior in Arnold core; it belongs in the Megaplan adapter milestone.
- Do not inspect or depend on python-shaped authored workflow source, generated DSL internals, or Megaplan planning topology in this milestone.
- Do not build a plugin discovery framework.
- Scheduled tasks must have lease/idempotency semantics from the start.

## Done Criteria

- Tests cover operation create/update/list/load.
- Tests cover valid/invalid state transitions.
- Tests cover optimistic update/lock conflict behavior.
- Tests cover scheduled task claim/lease/complete/fail behavior.
- Tests cover typed resource serialization and querying.
- Existing resident confirmation storage remains the approval base.
- A package-boundary ADR or doc section records Arnold/Megaplan/AgentBox ownership and dependency direction.
- The preflight result is recorded, including the merged M3 base SHA and any remaining sequencing risks.

## Touchpoints

- `arnold_pipelines/megaplan/store/*`
- resident Store models for conversations, scheduled jobs, cloud runs, confirmations, progress events, control messages
- new Arnold runtime/core modules as appropriate
- package-boundary documentation

## Anti-Scope

- No Discord UX implementation.
- No Guardian loop.
- No Megaplan chain adapter implementation.
- No credential sync.
- No external workspace platform adoption.
