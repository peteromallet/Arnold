# M2: AgentBox Host Provider

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone binds Arnold runtime resources to real host filesystem, git, tmux, logs, and partial-launch recovery semantics.

## Outcome

Implement the AgentBox host provider/distribution layer: repo registry, normal-checkout worktree resources, host-local tmux runner, operation path conventions, CLI inspection, and partial-launch reconciliation against Arnold operations.

## Scope

In:

- define AgentBox host config and workspace layout;
- implement repo registry for named repos on one machine;
- use normal canonical checkouts under `/workspace/repos` for v0;
- create operation-scoped git worktree resources with per-repo advisory locking;
- add host-local execution provider that runs directly on the persistent host;
- implement tmux session creation/status/attach/stop helpers as process-session resources;
- write logs/events under `/workspace/runs/<op>/`;
- implement local CLI debugging: status, logs, attach, reconcile;
- detect partial launch artifacts without deleting them.

Out:

- Megaplan chain semantics;
- Discord profile;
- Guardian scheduled worker;
- credentials;
- GitHub/cleanup automation.

## Locked Decisions

- AgentBox uses Arnold operation/resource models from M1.
- AgentBox is a separate distribution/package in this monorepo, not Megaplan internals.
- Host-local execution provider is not SSH-to-self and not Docker by default.
- V0 uses normal checkouts; bare repos are deferred until compatibility is proven.
- Orphaned worktrees/branches are surveyed/reconciled, not silently removed.

## Open Questions

- Exact host profile config path.
- Minimum extraction needed from `bakeoff/worktree.py`.
- Exact AgentBox package/module path.

## Constraints

- One worktree per operation per repo.
- No two operations mutate the same worktree.
- Worktree create/remove is locked per repo.
- No destructive cleanup in this milestone.

## Done Criteria

- Local tests/smokes create a repo worktree resource for an operation.
- Tmux session resource can launch, report status, attach/log, and stop.
- Partial-launch cases are detected and represented as operation/resource state.
- `agentbox status/logs/attach/reconcile` work against local dev roots.

## Touchpoints

- `arnold_pipelines/megaplan/bakeoff/worktree.py`
- tmux/cloud runner conventions
- Arnold operation/resource models from M1
- AgentBox CLI/config

## Anti-Scope

- No chain adapter.
- No Discord.
- No Guardian.
- No credential push.
