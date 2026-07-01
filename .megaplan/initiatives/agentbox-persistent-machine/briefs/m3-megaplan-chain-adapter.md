# M3: Megaplan Chain Adapter

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone proves the first Arnold operation adapter without letting Megaplan accidentally define the whole framework.

## Outcome

Implement `megaplan_chain` as the first Arnold operation adapter, owned by Megaplan and registered for AgentBox use. It uses AgentBox host resources for worktrees/tmux/logs and existing Megaplan chain/cloud/supervisor logic for chain behavior.

## Scope

In:

- implement `megaplan_chain` operation handler against the Arnold handler contract;
- expose adapter registration/discovery in a way AgentBox can opt into, for example `agentbox[megaplan]`;
- launch an existing chain spec in an AgentBox worktree resource;
- connect chain status/classification to operation state;
- reuse/extract chain status, sync refresh, tmux restart, and PR-state logic where appropriate;
- support CLI `agentbox run --repo <repo> --kind megaplan_chain --spec <path>`;
- support logs and status through Arnold operation resources;
- map Megaplan chain completion/failure/stale states to Arnold operation states.

Out:

- Discord launch path;
- Guardian scheduling loop;
- credentials;
- cleanup;
- other operation kinds.

## Locked Decisions

- Megaplan-specific semantics stay in the `megaplan_chain` adapter.
- Arnold core remains pipeline-agnostic.
- AgentBox host provider owns tmux/worktree/log resources.
- AgentBox discovers/registers this adapter; it does not own Megaplan chain semantics.
- The adapter does not create a second chain runner.

## Open Questions

- Cleanest seam around `cloud_supervise_tick()` versus provider-independent chain classification.
- Whether the adapter should invoke chain Python entrypoints directly or shell through CLI in v0.
- Exact mapping from ChainState fields to Arnold operation status.

## Constraints

- No direct push to main.
- No destructive cleanup.
- No autonomous code-patching repair.
- No bare repo dependency.

## Done Criteria

- A `megaplan_chain` operation can launch from CLI.
- Operation status reflects running/completed/failed/stale chain outcomes.
- Logs and events are attached to the operation.
- Tests/fakes cover successful launch, missing spec, chain failure, and partial launch.

## Touchpoints

- Megaplan chain CLI/state/spec code
- `cloud/supervise.py`
- `chain/git_ops.py` only where status metadata is needed
- AgentBox host provider from M2
- Arnold operation core from M1

## Anti-Scope

- No Discord integration.
- No Guardian autonomous loop.
- No credentials beyond existing local environment assumptions.
