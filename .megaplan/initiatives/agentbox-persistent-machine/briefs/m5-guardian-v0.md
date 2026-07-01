# M5: Guardian V0

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone turns scheduled Arnold operation checks into autonomous behavior and must avoid duplicate schedulers, races, and noisy notifications.

## Outcome

Add Arnold Guardian v0: a worker that claims due scheduled tasks, supervises Arnold operations through handlers, and sends material notifications for AgentBox operations.

## Scope

In:

- implement Guardian as a scheduled-task worker;
- schedule operation liveness ticks and deep supervision ticks;
- schedule daily briefing and credential/repo/check reminders where stubbed;
- inspect `megaplan_chain` operations through the adapter;
- classify dead, stale, completed, failed, and `needs_peter` operations;
- restart/resume known-safe chain states;
- cap retry attempts;
- send completion/blocker/failure DMs through existing resident outbound paths;
- reuse cloud supervise/watchdog logic as libraries where practical.

Out:

- autonomous code-patching repair agents;
- operation kinds beyond `megaplan_chain`;
- destructive cleanup;
- merge conflict resolution;
- quality-debt acceptance.

## Locked Decisions

- Guardian is Arnold-level; AgentBox packages/configures one Guardian service.
- Scheduled check-ins are Arnold scheduled tasks, not ad hoc sleep loops.
- Guardian and Discord Operator are separate processes sharing Store.
- Watchdog does not run as a competing daemon in v0.

## Open Questions

- Default retry caps per failure cause.
- Which watchdog helpers can accept operation-record inputs with minimal refactor.
- Exact DM format for repeated failures and restored operations.

## Constraints

- Notifications only on material transitions, failed recovery, completion, or required input.
- No silent destructive action.
- No direct IPC dependency on the Discord Operator.
- Guardian must continue checking other operations if one operation's inspection times out.

## Done Criteria

- Tests cover scheduled task claim/lease/run/complete/fail paths.
- Tests/fakes cover dead resumable tmux restart.
- Tests/fakes cover stale chain resume.
- Tests/fakes cover repeated failure reaching retry cap.
- Tests/fakes cover `needs_peter` classification.
- Completion DM is emitted without an active Operator turn.
- Guardian can be paused/resumed without losing operation state.

## Touchpoints

- Arnold scheduled task model from M1
- `cloud/supervise.py`
- `supervisor/*`
- `watchdog/*`
- resident outbound sink/runtime
- Megaplan chain adapter from M3

## Anti-Scope

- No autonomous patching repair subagents except cheap bounded diagnostics if already safe.
- No separate meta-watchdog daemon.
- No additional operation kinds.
