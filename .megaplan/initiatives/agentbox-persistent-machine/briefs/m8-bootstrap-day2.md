# M8: Bootstrap And Day-2 Operations

Overall plan difficulty: 5/5; selected profile: partnered-5; because persistent-machine bootstrap, restore, service control, and break-glass paths must be correct even though most individual edits are packaging work.

## Outcome

Make AgentBox deployable and recoverable on a persistent Hetzner-style machine with boring bootstrap, SSH access, systemd services, doctor/reconcile, and backup/restore flows.

## Scope

In:

- implement or wire `agentbox bootstrap`;
- create SSH host profiles and stable aliases;
- create `/workspace` layout;
- install/check baseline packages and tools;
- install systemd units for Arnold Guardian and AgentBox Discord resident profile;
- implement `doctor`, `services`, `logs`, `restart`, `guardian pause/resume`, `notify test`, `reconcile`, and `version`;
- document backup/restore and fresh-box recovery;
- support credential re-push after restore.

Out:

- Kubernetes, Nomad, Coder, OpenHands, microVMs, or browser IDE;
- multi-tenant auth;
- bare repo migration unless already proven;
- full OS patch automation beyond documented commands.

## Locked Decisions

- Target Hetzner/CX53-class host first.
- Plain SSH works before optional Tailscale.
- Docker is optional.
- Systemd supervises Guardian and Discord services.
- Normal checkouts remain the v0 canonical repo layout.
- Bootstrap is idempotent and never deletes repos, worktrees, runs, or credentials on update.

## Open Questions

- Exact local host profile config path.
- Backup backend and versioning format.
- Whether bootstrap lives inside AgentBox CLI or wraps existing Megaplan cloud SSH provider.

## Constraints

- Status and service logs must work without Discord.
- Root SSH is only for initial bootstrap and then avoided/disabled.
- Manual intervention can be annotated through `reconcile`.
- Restore must not print secret values.

## Done Criteria

- Fresh-machine runbook reaches `doctor` success.
- Guardian and Discord services start and report status.
- `notify test` sends a Discord message when credentials exist.
- `reconcile` detects registry/tmux/worktree mismatches.
- Restore runbook covers fresh box plus credential re-push.
- Documentation includes break-glass path when Discord is down.

## Touchpoints

- Megaplan cloud SSH provider/templates
- AgentBox CLI
- systemd unit templates
- host profile/config handling
- credential/test commands
- backup/restore docs

## Anti-Scope

- No distributed orchestration.
- No team/multi-user permission model.
- No adopting external workspace platforms.
