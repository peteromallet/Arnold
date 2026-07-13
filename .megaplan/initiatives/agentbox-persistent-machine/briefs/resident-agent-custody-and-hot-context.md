# Resident Agent Custody and Hot Context

## Goal

Make Discord resident delegation an Arnold-owned, durable execution surface with enough permissions for nested Codex work, while keeping it visibly distinct from subagents created inside ordinary Arnold workflow runs.

## Contract

- Discord replies continue through `ResidentDiscordService` → `ResidentRuntime` → the configured Arnold resident runner; no parallel bot loop is introduced.
- A delegated background Codex agent is launched by the resident-owned supervisor with `danger-full-access`, sealed stdin, an explicit model and reasoning effort, and a target project directory.
- Every delegated run has an `arnold-resident-agent-run-v1` manifest plus `prompt.md`, streaming `run.log`, and `result.md` under `.megaplan/plans/resident-subagents/<run-id>/`.
- Manifests identify `run_kind: resident_delegated_agent` and `custodian: arnold.megaplan.resident`, distinguishing these runs from workflow-internal subagents.
- Resident hot context exposes all observed running delegated agents and a bounded recently completed/interrupted list, including absolute manifest, full-log, result, and target-workspace paths.
- Running state is checked against the live wrapper command and manifest path so PID reuse cannot falsely report an agent as active.
- Existing `arnold-subagent-run-v1` manifests remain readable during migration.

## Acceptance

- A resident-launched Codex agent has live streaming logs and a separately captured final result.
- Discord can answer “what agents are running?” from `resident_agents` without conflating cloud chains or workflow-internal subagents.
- The hot context includes full log locations for running and recent agents across sibling `/workspace` checkouts.
- Focused resident launcher, profile/hot-context, Discord, and runtime tests pass.

