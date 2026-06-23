# Codex UX Gap Review Brief
Working directory: /Users/peteromalley/Documents/megaplan

Task: Review the AgentBox docs for gaps between the desired user experience and the current documented plan. Take a strong position. Focus on the single-user Discord-first UX: Peter messages Discord to add tickets, create epics/Megaplans/chains, run them, Guardian actively unblocks/repairs/relaunches, completion DMs happen, PR/merge/cleanup uses cleanup-loose-branches. Identify only material gaps or contradictions that should change the plan. Do not rewrite the whole plan. Return: (1) top gaps ranked by severity, (2) exact doc changes recommended, (3) any non-gaps that are already covered. Keep it under 1200 words.

--- docs/agentbox-persistent-machine-plan.md ---

# AgentBox Persistent Machine Plan

## Goal

Build a persistent remote agent machine that can host many repositories, receive selected credentials from the user's laptop, launch and supervise many concurrent coding operations, and expose the whole system through a resident Discord control plane.

This is broader than the current Megaplan Cloud worker. Megaplan Cloud is a remote runner for plans/chains. AgentBox is a remote development and agent operations machine.

The short version:

- the user can spin up Megaplan plans or chains on the machine;
- each run gets an isolated worktree, branch, tmux session, logs, and operation record;
- a **Guardian** checks all active operations every `X` minutes and safely keeps them moving;
- a **Discord Operator** starts on user messages, has access to AgentBox state/tools, and can launch or inspect work on demand;
- both actors use the same operation registry and safety/approval system.

The core constraint is:

- one persistent machine;
- many repos on that machine;
- one canonical repo checkout or bare repo per source repo;
- one git worktree per operation per repo;
- one tmux/session/process group per operation;
- one Guardian daemon supervising all known operations;
- one Discord-triggered Operator agent for interactive control;
- Discord as the primary human control surface.

## Resident Actors

AgentBox has two primary resident actors. They share the same state, tools, and safety policy, but they wake up for different reasons.

### Guardian

The Guardian is a long-running supervisor daemon. It wakes on a fixed cadence, for example every 5, 10, or 15 minutes, and checks every active operation.

Responsibilities:

- scan the operation registry;
- inspect tmux/process liveness;
- inspect Megaplan plan or chain status;
- read recent logs and structured state;
- classify operations as running, stale, blocked, failed, completed, or awaiting approval;
- restart a missing runner when the operation type has a known-safe restart path;
- advance a chain when the next step is unambiguous;
- file or update pending approvals for risky actions;
- notify Discord when a run blocks, fails, completes, or needs human input;
- update operation state and health summaries.

The Guardian should not silently make product decisions, resolve merge conflicts, delete worktrees, merge PRs, or accept quality debt. Those become explicit pending approvals.

### Discord Operator

The Discord Operator is an on-demand agent launched by Discord messages. It is the interactive control plane.

Responsibilities:

- answer "what is running?";
- launch a Megaplan plan or chain in a fresh worktree;
- launch Codex, Claude, subagent, shell, or test operations;
- inspect logs and summarize failures;
- ask the Guardian what is stuck;
- approve or reject pending actions;
- stop, restart, or clean up operations when authorized;
- inspect repo/worktree/branch state;
- push branches or open PRs when authorized.

The Operator should have access to all AgentBox data and tools, but it should still go through the same safety policy as the Guardian. Discord messages are the trigger, not a bypass.

Because this is a single-user system, the Operator does not need heavy multi-tenant ceremony. The normal path is simply: Peter sends a Discord message, the bot starts an agent with AgentBox tools and context, the agent does the work or asks a concrete follow-up, then reports back in Discord.

### Shared State

Both actors depend on the same durable records:

```text
operation id
operation kind
repo(s)
worktree(s)
branch(es)
tmux session
command
log path
current status
last check timestamp
pending approvals
Discord conversation/thread/message ids
PR/CI metadata
```

This operation registry is the center of the system. The Guardian is scheduled/autonomous; the Discord Operator is user-triggered/interactive. The handoff between them is registry-only: the Operator writes operation records and approvals; the Guardian reads them on its next tick, writes status changes and pending approvals, and notifies Discord on material transitions. There should be no direct process-to-process dependency in v1.

## User Journey

This is intentionally single-user and Discord-first. The goal is not an enterprise control panel. The goal is for Peter to talk to Discord and have the machine do the right thing with the existing Megaplan mechanics.

### Start Work From Discord

Typical messages:

```text
add a ticket to megaplan about cloud chain cleanup
set up an epic for AgentBox Guardian v0
set up a megaplan for fixing the cloud ssh provider and run it
run this chain in megaplan: briefs/agentbox/chain.yaml
what is running?
what is blocked?
show logs for op-123
```

Expected behavior:

1. Discord receives the message.
2. The Discord Operator starts an agent turn with access to AgentBox tools and context.
3. The Operator decides whether the request is a ticket, a Megaplan, an epic, a chain launch, a status question, or a maintenance task.
4. If work should run, it creates an operation record, creates or selects the right worktree, launches the process, and replies with the operation id.
5. Guardian takes over ongoing supervision.

The user should not need to know the exact CLI command most of the time. The Operator can choose the right Megaplan/ticket/epic/chain command from the message.

The desired product journey is Discord-first. The engineering order can still prove the operation registry and Guardian loop with a thin Discord path before the full natural-language Operator profile is complete.

### Guardian Finds A Blocker

The Guardian's default behavior should be active repair, not passive reporting.

When it finds a stuck, failed, or blocked operation, it should:

1. inspect current operation state;
2. read logs and structured plan/chain state;
3. classify the likely cause;
4. try the known safe recovery path;
5. if needed, launch a repair agent or subagent to diagnose and patch the issue;
6. relaunch or resume the operation;
7. record what it did;
8. notify Discord only when useful.

Examples:

- Dead tmux session with resumable chain state: restart the chain session.
- Chain state says stale/stalled but no active worker exists: clear or resume according to existing chain rules.
- Tests failed from a concrete code issue: launch a repair operation in the same worktree or a child worktree, then resume.
- Missing credential: notify Peter with the exact missing credential and the `agentbox creds push/test` command.
- Merge conflict, ambiguous product decision, or destructive cleanup: stop and ask.

The Guardian should be biased toward "figure out what's wrong and fix it" for operational failures. It should only ask Peter when the next step requires product judgement, credential input, destructive cleanup, or accepting quality debt.

If uncertainty is about machine state, Guardian or Operator should inspect logs/state or launch a diagnostic subagent first. If uncertainty is about Peter's intent or a product decision, the Operator should ask Peter directly with concrete options.

### Completion And Approval

The main approval event is completion, not every intermediate action.

When a Megaplan, chain, or epic completes, the system should DM Peter:

```text
op-123 completed.
Repo: megaplan
Branch: agent/op-123
Summary: ...
Validation: ...
Next: push/open PR/cleanup?
```

For ordinary successful runs, the system can push the branch and open/update a PR if that is already part of the operation policy. The approval boundary is mostly:

- merge to main;
- delete/cleanup worktrees or branches;
- accept failing validation or quality debt;
- resolve ambiguous product decisions;
- expose or rotate credentials.

### Work Moves To GitHub And Main

Megaplan chains already push work to GitHub in many cases. AgentBox should track the branch and PR on the operation record.

After a set of operations completes, final consolidation should use the local `cleanup-loose-branches` discipline:

- survey branches, worktrees, stashes, PRs, and loose remote state;
- classify each as land, delete, or park;
- prefer landing valuable work on main;
- require explicit approval for destructive cleanup;
- clean up remote worktrees and branches after merge.

In other words, AgentBox launches and supervises the work; cleanup-loose-branches is the consolidation and housekeeping playbook.

## Recommendation

Use a Hetzner VM or dedicated server as the primary target. Keep Railway support for simpler one-off hosted runners, but do not force the full resident-machine model into Railway's persistent-container model.

Start with a Hetzner `CX53`-class box for the prototype:

- 16 vCPU
- 32 GB RAM
- 320 GB disk
- enough to validate several concurrent agents, tests, and repos

If the workload saturates shared CPU or disk, move the same bootstrap to a dedicated or auction server. The design should make host migration boring.

## Target Layout

```text
/workspace
  /repos
    /megaplan.git
    /reigh-app.git
    /reigh-worker.git

  /worktrees
    /op-20260623-foo
      /megaplan
      /reigh-app
    /op-20260623-bar
      /megaplan

  /runs
    /op-20260623-foo
      manifest.yaml
      state.json
      log.txt
      events.ndjson

  /secrets
    agentbox.env
    codex-auth.json
    claude-refresh-token.env

  /manager
    agentbox.db
    config.yaml
```

Each operation gets its own isolated worktree and branch. No two agents mutate the same checkout.

Every operation should write both raw and structured logs:

- `log.txt` captures stdout/stderr and agent output for human inspection.
- `events.ndjson` is the machine-readable event stream used by Guardian and Operator. It should include lifecycle, phase, heartbeat, action, outcome, approval, PR, and notification events.

## Existing Megaplan Pieces To Reuse

### Worktree Mechanics

Megaplan already has the basic worktree substrate:

- `megaplan init --in-worktree NAME`
- `megaplan chain start --in-worktree NAME`
- `--worktree-from`
- `--clean-worktree`
- `--carry-dirty`
- `--fresh` for chain worktrees
- worktree metadata persisted into plan state

The shared primitives live in:

- `arnold_pipelines/megaplan/bakeoff/worktree.py`

Useful functions include:

- `validate_worktree_name`
- `ensure_no_inprogress_op`
- `resolve_ref`
- `branch_exists`
- `worktree_registered`
- `create_named_worktree`
- `create_worktree`
- `remove_worktree`
- dirty-state carry helpers

Current limitation: these are command-scoped and current-repo scoped. AgentBox needs them promoted into a machine-scoped operation service.

### Discord Resident Runtime

Megaplan already has Discord-facing resident infrastructure:

- `arnold_pipelines/megaplan/resident/discord.py`
- `arnold_pipelines/megaplan/resident/runtime.py`
- `arnold_pipelines/megaplan/resident/auth.py`
- `arnold_pipelines/megaplan/resident/cloud.py`
- `arnold_pipelines/megaplan/resident/cli.py`

Current limitation: the resident tooling is oriented around Megaplan cloud operations. AgentBox needs tools for repo/worktree/process operations too.

### Cloud And Supervisor Logic

Megaplan already has useful remote-runner and supervision code:

- `arnold_pipelines/megaplan/cloud/providers/ssh.py`
- `arnold_pipelines/megaplan/cloud/providers/railway.py`
- `arnold_pipelines/megaplan/cloud/supervise.py`
- `arnold_pipelines/megaplan/supervisor/*`
- `arnold_pipelines/megaplan/chain/git_ops.py`

Current limitation: cloud supervision is chain-centric. AgentBox needs a generic operation registry so a Megaplan chain, Codex run, Claude run, test run, or subagent swarm are all first-class operations.

### Credential Seeding

Megaplan Cloud already has credential handling patterns:

- Codex OAuth seeding in `arnold_pipelines/megaplan/cloud/auth.py`
- cloud skill documentation for Claude refresh-token auth
- `cloud.yaml` `secrets:` upload semantics

Current limitation: this is provider/deploy oriented. AgentBox needs a local-to-remote credential sync command with test/rotate/list behavior.

## Subagent Overlap Audit

Six DeepSeek subagents reviewed the plan against local Megaplan excerpts. Raw outputs live under:

- `.megaplan/agentbox-overlap-swarm/results-self/`

The useful conclusion is that AgentBox should not start as a greenfield system. A large amount of the chain/worktree/Discord/cloud-supervision substrate already exists, but it is command-scoped, chain-scoped, or provider-scoped. AgentBox should add a machine-scoped operation registry and wrap the existing functionality as plugins.

### Reuse Map

| AgentBox component | Existing overlap | Reuse verdict |
|---|---|---|
| Repo/worktree service | `arnold_pipelines/megaplan/bakeoff/worktree.py`, `_setup_init_worktree`, `_setup_chain_worktree` | Strong. Extract/generalize path and repo lookup. |
| Operation registry | `ChainLaunchContext`, cloud session markers, chain provenance, `ChainState` | Partial. Good fields exist, but no unified registry. |
| Process runner | cloud tmux launch/status conventions, provider `ssh_exec`, attach/logs interfaces | Partial. Transport exists; per-operation stop/restart/log paths need adding. |
| Guardian | `cloud/supervise.py`, resident scheduler, supervisor package | Strong for chains. Wrap as a chain-operation plugin before generalizing. |
| Discord Operator | `resident/discord.py`, `resident/runtime.py`, `resident/auth.py`, confirmation manager, outbound sink | Strong skeleton. Needs AgentBox tool profile. |
| Credential sync | `cloud/auth.py`, entrypoint OAuth restore, Claude refresh-token shim, SSH upload | Strong pattern. Generalize from OAuth seeds to explicit secret specs. |
| Megaplan chain launch | `cloud chain`, `cloud bootstrap`, `cloud status --chain`, `cloud supervise --chain`, `resident/cloud.py` | Strong. First operation kind should be Megaplan chain. |

### Key Findings

1. **The operation registry is the missing center.** Existing chain state, cloud markers, and session provenance are close, but there is no cross-operation record that ties together operation id, kind, repo, worktree, tmux session, log path, status, approvals, Discord ids, PR metadata, and Guardian last-check time.

2. **Guardian should start as a scheduler over operation plugins.** Do not rewrite `cloud/supervise.py`. Wrap `cloud_supervise_tick()` as the first classifier/action plugin for `megaplan_chain` operations. Add more plugins later for Codex, Claude, shell, tests, and subagent swarms.

3. **Discord Operator should reuse the resident runtime.** `ResidentDiscordService`, `DiscordInboundMessage`, `DiscordOutboundSink`, allowlists, authorization subjects, and confirmation storage already match the shape. The new work is an `AgentBoxOperatorProfile` with tools like `status`, `run`, `logs`, `approve`, `stop`, `cleanup`, `repos`, and `creds test`.

4. **SSH transport exists, but AgentBox should run locally on the box.** Current SSH provider often wraps commands in Docker. AgentBox needs a local execution path for Guardian running on the Hetzner host, while still keeping SSH for bootstrap and remote control from the laptop.

5. **Bare repos are an open risk.** Existing worktree helpers assume a normal repo/main worktree in places such as registered-worktree discovery and removal. Either start with normal canonical checkouts or add bare-aware variants before committing to `/workspace/repos/*.git`.

6. **Secrets should use explicit specs.** `seed_codex_oauth()` already proves the pattern of copying selected local auth files to persistent and runtime destinations. AgentBox should generalize this into `SecretSpec(local_path, persistent_dest, runtime_dest, permissions, health_check)` rather than dumping local environment variables.

7. **Guardian and Discord Operator must be separate processes at first.** The Discord service owns an asyncio client loop, while Guardian is a periodic supervisor. Run them as separate systemd services sharing the same operation store to avoid event-loop coupling.

8. **The live watchdog should be reused as a Guardian plugin/library.** Do not run a separate watchdog daemon beside Guardian in v1. Guardian owns the cadence and operation registry; watchdog discovery/repair/retry/snapshot mechanics feed Guardian's per-operation inspection and repair step.

### First Slice Recommended By The Swarm

Build the smallest loop that proves the architecture with real Megaplan chains:

1. Add an operation registry:
   - one JSON or SQLite record per operation;
   - fields for `id`, `kind`, `repos`, `worktrees`, `branch`, `tmux_session`, `log_path`, `status`, `last_check`, `pending_approvals`, `discord_refs`, and `metadata`.

2. Add a single operation kind: `megaplan_chain`.
   - launch by wrapping existing `cloud chain` / chain start behavior;
   - create a fresh worktree with existing worktree helpers;
   - record tmux session and log path.

3. Add Guardian v0:
   - systemd service or long-running process;
   - loops every `X` minutes over active operations;
   - for `megaplan_chain`, calls existing `cloud_supervise_tick()` or equivalent extracted helper;
--- docs/agentbox-load-bearing-questions.md ---

# AgentBox Load-Bearing Questions

This document captures the questions that, if answered well from human, agent, and technical perspectives, lead to the current AgentBox design. Each answer is the current predicted design answer before subagent validation.

The validation swarm should receive the questions without these answers and independently derive its answer from the AgentBox plan and repo context.

## Human Perspective

### H1. What is the smallest interaction Peter should need to start useful work?

**Predicted Answer:** Peter should be able to send a natural Discord message such as 'add a ticket', 'set up an epic', 'run this Megaplan', or 'what is blocked?'. The Discord Operator translates that into existing Megaplan/ticket/chain actions and replies with an operation id or a concrete follow-up.

### H2. When should the system ask Peter instead of acting?

**Predicted Answer:** It should ask only for product judgement, missing credentials, destructive cleanup, accepting quality debt, merge conflict choices, or final merge/delete decisions. Routine operational recovery should be attempted autonomously.

### H3. What does Peter need to know when work starts?

**Predicted Answer:** The bot should report the operation id, repo/worktree/branch, what it launched, where logs are, and that Guardian is watching it. It should avoid dumping implementation detail unless asked.

### H4. What does Peter need to know while work is running?

**Predicted Answer:** Only meaningful state changes: blocked, repaired, failed after retries, completed, needs credential, or needs judgement. Routine heartbeats should be available on request, not noisy by default.

### H5. What should happen when Guardian finds a blocker?

**Predicted Answer:** Guardian should diagnose, try known-safe repair, use DeepSeek/subagents for ambiguous failures, relaunch/resume, and only DM Peter when it cannot proceed safely or when the state materially changes.

### H6. What is the completion moment?

**Predicted Answer:** Completion is when a plan/chain/epic reaches its done state with validation summarized and branch/PR status known. At that point Peter gets a DM with summary, validation, branch/PR link, and suggested next action.

### H7. What is the approval model for a single-user system?

**Predicted Answer:** There should be little ceremony. Approval is needed for merge-to-main, destructive cleanup, accepting failing validation/debt, credential exposure/rotation, or product decisions. Everything else should run under Peter's pre-authorized intent.

### H8. How should work move from remote worktree to main?

**Predicted Answer:** Completed work should be pushed to GitHub/PR using existing chain/git mechanics where possible. Periodic consolidation should invoke the cleanup-loose-branches discipline to land valuable loose work and delete only with explicit approval.

### H9. How much UI is needed?

**Predicted Answer:** Discord plus a small CLI is enough. No dashboard is required for v1. The operation registry should support future UI, but the human product should be conversational first.

### H10. What should failure feel like to Peter?

**Predicted Answer:** The system should say what failed, what it tried, what evidence it used, and what exact decision/input it needs. It should not make Peter inspect raw logs unless asked.

### H11. How should Peter discover current state?

**Predicted Answer:** A Discord message like 'what is running?', 'what is blocked?', or 'summarize AgentBox' should return a concise table grouped by running/blocked/completed/needs-me.

### H12. What is out of scope for the human journey v1?

**Predicted Answer:** Multi-user roles, complex dashboards, slash-command completeness, team access, Kubernetes-style isolation, and enterprise audit UX are out of scope.

## Agent Perspective

### A1. What context does the Discord Operator need at turn start?

**Predicted Answer:** It needs the user message, conversation history/hot context, operation registry snapshot, repo registry, available tools, safety policy, and recent Guardian findings.

### A2. What tools must the Operator have first?

**Predicted Answer:** Ticket create/search, chain/megaplan launch, status, logs, Guardian check, credential test, and maybe repo list. Stop/cleanup/push/merge can exist behind confirmation.

### A3. How should the Operator decide between ticket, Megaplan, chain, and epic?

**Predicted Answer:** It should classify intent: small deferred issue -> ticket; bounded implementation -> Megaplan; sequenced multi-milestone work -> chain/epic; existing spec -> chain launch; status/debug request -> query/Guardian tools.

### A4. What is the Guardian's agentic loop?

**Predicted Answer:** Observe operation -> classify -> choose safe action -> act or launch repair subagent -> recheck -> record evidence -> notify on material transition.

### A5. When should Guardian launch a DeepSeek/subagent?

**Predicted Answer:** When local heuristics cannot explain a failure, when tests fail non-trivially, when a chain stalls repeatedly, when cleanup/branch state is ambiguous, or when a proposed recovery risks losing work.

### A6. How should agents avoid trampling each other?

**Predicted Answer:** Every operation uses its own worktree, branch, tmux session, log path, and operation record. Shared mutation goes through the registry and git worktree/branch safety checks.

### A7. How should agents handle logs?

**Predicted Answer:** Summarize logs by default, link/tail on request, and store raw logs under the operation. Guardian should extract the decisive error and the recovery attempt history.

### A8. What should be recorded for every agent action?

**Predicted Answer:** Operation id, actor type, tool/action, input summary, output summary, log path, status transition, timestamps, and any pending approval or rationale.

### A9. How should an agent know an action is unsafe?

**Predicted Answer:** Tool metadata and safety policy should mark actions as safe, confirm, or forbidden. Merge, delete, reset, accept debt, credential operations, and ambiguous product choices require explicit confirmation.

### A10. How should the Operator respond if it is unsure?

**Predicted Answer:** It should inspect state or launch a narrow diagnostic subagent before asking Peter. If still blocked, ask one concrete question with evidence.

### A11. What is the handoff between Operator and Guardian?

**Predicted Answer:** Operator creates or mutates operation records and launches work; Guardian owns ongoing supervision. Operator can ask Guardian for an immediate check or override/approve a pending action.

### A12. What agent behavior is explicitly undesirable?

**Predicted Answer:** Passive reporting of recoverable failures, untracked shell commands outside operation records, shared checkout mutation, noisy updates, and asking Peter questions that can be answered from local state.

## Technical Perspective

### T1. What is the central data model?

**Predicted Answer:** A durable operation registry tying id, kind, repo(s), worktree(s), branch(es), tmux session, command, logs, status, Guardian tick history, pending approvals, Discord refs, and PR/CI metadata.

### T2. Which existing subsystem should back persistence?

**Predicted Answer:** Reuse or mirror the existing Store patterns for conversations, scheduled jobs, cloud runs, events, and external requests. SQLite plus per-operation manifests is a good v1.

### T3. What is the first operation kind?

**Predicted Answer:** megaplan_chain, because cloud chain/status/supervise, chain state, worktree support, and git/PR behavior already exist.

### T4. How should worktrees be represented technically?

**Predicted Answer:** Use existing worktree helpers but parameterize repo lookup and root path. Start with normal canonical checkouts if bare repo support creates risk; add bare-aware helpers later.

### T5. Where should Guardian run?

**Predicted Answer:** On the persistent machine as a systemd service or long-running process using local exec, not from the laptop via repeated SSH. SSH remains for bootstrap/control.

### T6. Should Guardian and Discord Operator be one process?

**Predicted Answer:** No for v1. Discord owns an asyncio client loop; Guardian is a periodic supervisor. Run separate services sharing the operation store.

### T7. How should existing cloud supervise fit?

**Predicted Answer:** Wrap cloud_supervise_tick or an extracted equivalent as the megaplan_chain plugin. Do not rewrite its chain-specific policy.

### T8. How should the live watchdog fit?

**Predicted Answer:** Use watchdog discovery/repair/retry/snapshot mechanics for local process/tmux repair and fold its findings into Guardian tick history.

### T9. How should credentials be synced?

**Predicted Answer:** Generalize cloud OAuth seeding into explicit SecretSpec records: local source, persistent destination, runtime destination, permissions, and health check. Do not dump the whole environment.

### T10. What is the process runner abstraction?

**Predicted Answer:** A runner creates tmux session/process group, captures logs, reports liveness, supports attach/stop/restart where safe, and is always tied to an operation record.

### T11. How should PR/merge cleanup work technically?

**Predicted Answer:** Reuse chain git_ops/supervisor PR mechanics for push/PR. Use cleanup-loose-branches as the post-run consolidation protocol for branches/worktrees/stashes/remotes/cloud workspaces.

### T12. What is the minimal vertical slice?

**Predicted Answer:** Operation registry + Discord Operator status/launch tools + megaplan_chain launch in worktree + Guardian v0 periodic supervise/repair + completion DM.

## Validation Protocol

For each question, launch one subagent with only the question plus the current AgentBox plan and relevant context. Compare the returned answer against the predicted answer above. Record: aligned, partial, divergent, or stronger-than-predicted, with rationale.

## Validation Results

A 36-agent DeepSeek validation swarm answered each question without seeing the predicted answers. Raw outputs live under:

- `.megaplan/agentbox-load-bearing-swarm/results/`

All 36 agents completed successfully. Overall verdict: the predicted design is stable. Most answers independently converged on the same core: Discord-first user intent, one operation registry, per-operation worktrees, Guardian as an autonomous repair loop, Discord Operator as the interactive agent, Megaplan chain as the first operation kind, separate Guardian/Operator processes, and cleanup-loose-branches for post-run consolidation.

### Strong Confirmations

| Area | Validation outcome |
|---|---|
| Central model | Agents independently identified the operation registry as the load-bearing center. |
| First operation kind | Agents converged on `megaplan_chain` as the correct first kind. |
| Guardian location | Agents agreed Guardian should run locally on the AgentBox machine, not from the laptop over SSH. |
| Process split | Agents agreed Guardian and Discord Operator should be separate services sharing state. |
| Cloud supervise | Agents agreed existing cloud supervise should be wrapped as the `megaplan_chain` plugin, not rewritten. |
| Discord UI | Agents agreed Discord is the primary UI; no dashboard is needed for v1. |
| Approval model | Agents agreed on narrow approval gates: merge, destructive cleanup, credentials, quality debt, product judgement. |
| Completion | Agents clarified completion is a handoff point, not full closure: work is done, but consolidation/merge/cleanup may remain. |

### Useful Deviations And Design Adjustments

1. **Operator uncertainty needs two paths.**
   - Predicted: inspect state or launch a diagnostic subagent before asking Peter.
   - Validation: if the Discord request itself is ambiguous, ask Peter directly with concrete options.
   - Resolution: use both. If uncertainty is about local state, inspect first. If uncertainty is about Peter's intent or product choice, ask directly.

2. **First Operator tools should be split into MVP and product target.**
   - Predicted: ticket, chain/megaplan launch, status, logs, Guardian check, credential test.
   - Validation: minimum control loop is `status`, `run`, `logs`, `stop`; ticket/epic tools can sit behind `run` or come next.
   - Resolution: product journey remains ticket/epic/megaplan from Discord. Engineering slice can start with `status`, `run`, `logs`, plus one ticket/chain launch path.

3. **Structured event logs are more load-bearing than initially stated.**
   - Predicted: logs and action records should exist.
   - Validation: every operation should have raw `log.txt` plus structured `events.ndjson`, with lifecycle, phase, heartbeat, action, and outcome events.
   - Resolution: make `events.ndjson` part of the operation contract, not an optional artifact.

4. **Watchdog should be absorbed as a Guardian plugin/library, not run as a second daemon.**
   - Predicted: reuse watchdog mechanics.
   - Validation: running watchdog beside Guardian risks duplicate scans and racey repairs.
   - Resolution: Guardian owns the loop; watchdog discovery/repair/retry/snapshot logic becomes an inspection/repair plugin.

5. **Bare repo target remains contested.**
   - Predicted: start with normal canonical checkouts if bare repo helper behavior is risky; add bare-aware variants later.
   - Validation: one agent argued bare repos are the correct technical representation from first principles.
   - Resolution: target architecture can still be bare repos, but first slice may use normal canonical checkouts unless the existing helpers are made bare-aware first.

6. **MVP slice versus desired user journey must be explicit.**
   - Predicted: Discord-first is part of the desired journey.
   - Validation: some agents treated full message-triggered Operator as phase 2 after registry stability.
   - Resolution: distinguish the desired product journey from the engineering order. The product is Discord-first; the implementation may prove registry/Guardian with a thin Discord path first.

7. **Handoff is registry-only.**
   - Predicted: Operator creates operations, Guardian supervises.
   - Validation: make this explicit as producer/consumer via the operation registry, with no direct IPC or synchronous coupling.
   - Resolution: add this to the plan.

### No Design Change

Some deviations were wording or scope differences rather than contradictions:

- Several agents recommended PR creation can be automatic while merge remains approval-gated. This matches the existing plan.
- Several agents emphasized cleanup-loose-branches after batches of completed work. This matches the plan and should remain the consolidation mechanism.
- One Human Perspective answer for "what does Peter need to know when work starts" answered the broader autonomy boundary instead of the start notification. Useful, but not a replacement for the predicted answer.

### Final Shape After Validation

The validated design is:

1. Peter talks to Discord in natural language.
2. Discord Operator turns that into ticket/epic/megaplan/chain/status/log actions.
3. Every launched unit becomes an operation record.
4. Operations run in isolated worktrees and tmux sessions.
5. Guardian loops over operation records every `X` minutes.
6. Guardian uses existing chain/cloud/watchdog mechanics to repair and relaunch.
7. Guardian launches DeepSeek/subagents only when deterministic repair cannot classify/fix the issue.
8. Completion DMs Peter with summary, validation, branch/PR state, and next action.
9. Push/PR can be automated by policy; merge/destructive cleanup/quality debt require approval.
10. Batch consolidation uses cleanup-loose-branches.
