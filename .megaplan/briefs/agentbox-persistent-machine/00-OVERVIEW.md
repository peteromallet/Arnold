# AgentBox Persistent Machine Epic

This epic implements AgentBox: the first persistent-machine distribution of Arnold-level runtime primitives for long-running agent operations. AgentBox is controlled primarily through Discord, runs on one machine, and uses Arnold operations, typed resources, scheduled tasks, credentials, approvals, and cleanup/reconcile contracts underneath.

Package boundary:

```text
arnold runtime primitives
  <- megaplan pipeline + megaplan_chain adapter
  <- agentbox one-machine distribution
```

AgentBox is a separate package/distribution in this monorepo for v0. It should not be implemented inside Megaplan. Arnold core must not depend on AgentBox, Megaplan, Discord, tmux, systemd, Hetzner, or `/workspace`; it owns neutral runtime contracts. Megaplan owns the `megaplan_chain` adapter. AgentBox owns the host packaging, CLI, bootstrap, resident service wiring, repo/worktree/tmux provider, Discord Operator profile, and day-2 operations.

Source design document:

- `docs/agentbox-persistent-machine-plan.md`

Prepared with `megaplan-prep`:

- This is bigger than one two-week sprint, so it is split into an epic.
- Launch base is `python-shaped-workflow-authoring-cleanup`, after the python-shaped workflow-authoring M3 PR is merged and green.
- M1 starts with a post-M3 preflight: package boundaries, `OperationRegistry` naming, Store migration shape, and no dependency on python-shaped workflow internals.
- V0 is Discord-first: `add ticket`, `run chain`, `status/blocked/logs`, operation id, Guardian supervision, completion DM.
- First operation kind is `megaplan_chain`, but Megaplan is only the first adapter.
- Normal canonical checkouts are v0; bare repos are deferred.
- Arnold owns operation, scheduled-task, neutral resource, credential, approval, and cleanup/reconcile contracts.
- AgentBox packages those Arnold primitives for a one-machine host with SSH, systemd, tmux, Discord, and `/workspace`.
- Avoid naming collisions with the existing plugin dispatch `arnold.runtime.operations.OperationRegistry`; persisted runtime records should use a name like `ManagedOperation`, `DurableOperation`, or `OperationRun` unless the old dispatch registry is deliberately renamed.
- Scheduled tasks are generalized: operation liveness checks, deep supervision, daily briefings, credential checks, repo syncs, backups, cleanup reminders, and approval reminders are all scheduled-task records claimed by workers.

Milestones:

1. `m1-arnold-runtime-core` — Arnold operation/event/state/resource/scheduled-task/approval contracts.
2. `m2-agentbox-host-provider` — AgentBox host provider, repo registry, worktrees, tmux, paths.
3. `m3-megaplan-chain-adapter` — first Arnold operation kind, backed by Megaplan chain mechanics.
4. `m4-discord-thin-path` — Discord add-ticket/run-chain/status/logs.
5. `m5-guardian-v0` — Guardian worker over Arnold scheduled tasks and operation handlers.
6. `m6-credentials-preflight` — Arnold credential manifest plus AgentBox host backend.
7. `m7-completion-github-cleanup` — completion DM, PR state, cleanup/reconcile contract.
8. `m8-bootstrap-day2` — bootstrap, SSH, systemd, doctor/reconcile, restore.

Launch:

```bash
.megaplan/briefs/agentbox-persistent-machine/launch-after-python-shaped-m3.sh
```

The launch wrapper refuses to start until python-shaped workflow-authoring M3 PR #98 is merged, non-draft, based on `python-shaped-workflow-authoring-cleanup`, and contained in `origin/python-shaped-workflow-authoring-cleanup`. That is the concrete "jump off from M3" gate. Once it starts, Megaplan records the current base SHA as `current_milestone_base_sha` for M1.

Status:

```bash
python -m arnold_pipelines.megaplan chain status --spec .megaplan/briefs/agentbox-persistent-machine/chain.yaml
```
