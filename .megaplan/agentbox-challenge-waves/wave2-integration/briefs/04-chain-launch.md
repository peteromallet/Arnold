# Wave 2 Current-System Fit Challenge: Chain Launch Adapter

You are an independent DeepSeek reviewer. Use the AgentBox plan and local code-surface inventory below. Your lens: Whether megaplan chain/cloud mechanics are the right first operation kind and what adapter seam is needed.

Task: Challenge whether the AgentBox design fits the existing Megaplan mechanics. Focus on overlap, missing extraction seams, conflicts, and whether we should reuse, wrap, or avoid existing code. Return:
1. Verdict: STRONG FIT / FIT WITH EXTRACTION / CONFLICT / NEEDS BUILD.
2. Existing functionality that should be reused.
3. Missing seam or incompatibility that must be addressed.
4. Exact plan changes recommended.
5. Things that are already correctly handled.

Be concrete. Do not invent code not indicated by the inventory. If you need uncertainty, phrase it as a code-inspection task to add to the plan.

--- CONTEXT ---
# Updated AgentBox Plan
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

The thin Discord path is still part of v0. A slice that only works from CLI is not complete. At minimum, Peter should be able to use Discord to:

- add a Megaplan ticket;
- run an existing chain spec;
- ask what is running or blocked;
- ask for logs for an operation;
- receive the operation id when work starts;
- receive the completion DM when work finishes.

### Operator Intent Classification

Every Discord message is classified before tools run. The classification should be explicit in the Operator profile rather than left to generic agent instinct.

Core intents:

| User says | Intent | Primary tool path |
|---|---|---|
| "add a ticket about X" | `ticket_create` | Megaplan ticket create |
| "set up an epic for X" | `epic_create` | chain create with epic/milestone semantics |
| "set up a Megaplan for X" | `megaplan_create` | Megaplan plan/chain authoring path |
| "run this chain" | `chain_launch` | chain launch into operation |
| "set up a Megaplan for X and run it" | `compound_create_and_launch` | create, then launch only if create succeeds |
| "what is running?" | `status_query` | registry/status summary |
| "show logs for op-123" | `logs_query` | log/event summary |
| "merge it", "approve that" | `approval_response` | match pending approval in conversation scope |
| "clean up old worktrees", "creds test" | `maintenance` | cleanup, repo, credential, or machine-health tools |
| "help", "what can you do?" | `help` | natural-language capability summary |

Rules:

- If the request is ambiguous about Peter's intent, ask one concrete question with two or three options.
- If the request is clear but references an unclear object, use a resolver tool before asking. The resolver searches operation records, repo registry, chain/epic specs, tickets, and recent conversation references.
- Compound requests are allowed. The Operator decomposes them into ordered steps, stops on the first failed step, and reports which steps succeeded.
- Spec paths are resolved relative to the selected repo unless explicitly stated otherwise.
- If no repo is named and multiple repos could match, ask Peter which repo.

### Conversation Context

The Operator is an on-demand agent, but it must not behave like a stateless command parser. Every Operator turn receives:

- current Discord message;
- recent messages in the same DM/channel/thread scope;
- referenced operation ids from that scope;
- pending questions;
- pending approvals;
- operation registry snapshot;
- recent Guardian findings.

When the Operator asks Peter a clarifying question, it records a pending question with the conversation scope, timestamp, related operation ids, question text, and expected answer shape. The next message in that scope is first matched against pending questions and approvals before being classified as a new request.

Conversation scope is DM, channel thread, or channel message context. If a message is unrelated to the current scope or enough time has passed, the Operator treats it as a new topic.

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

Guardian v0 acceptance criteria for `megaplan_chain`:

- detect and restart a dead tmux/session when chain state is resumable;
- detect stale chains from heartbeat/event timestamps and try the existing safe resume path;
- detect repeated failure and stop after a retry cap;
- classify missing credential, merge conflict, destructive cleanup, product decision, and quality-debt cases as `needs_peter`;
- launch a repair operation or diagnostic subagent for non-trivial test/validation failures;
- record every repair attempt in `events.ndjson`;
- notify Discord only on material transitions, failed recovery, completion, or required input.

The Guardian owns ongoing completion detection for operations it supervises. Completion notifications should be emitted from operation registry and event state, not depend on an active Discord Operator turn.

### Daily Briefing

The Guardian should also produce one predictable daily briefing at a configured time, for example 08:00 local time. The daily briefing is the proactive habit-forming touchpoint; the 5-15 minute loop remains the operational monitor.

Daily briefing contents:

- completed since last briefing: operation id, repo, summary, branch/PR, validation;
- still running: operation id, kind, repo, elapsed time, current phase;
- blocked or failed: classification, evidence, what Guardian tried, what is needed;
- needs Peter: approvals, credential requests, product decisions, destructive cleanup, quality debt;
- machine health: disk, memory, stale worktrees, dirty/unpushed branches.

Routine completions may be batched into the daily briefing by preference. Failures, blockers, and approval-needed items that cannot wait should still DM immediately.

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

Approval replies should be matched to pending approval records in the same Discord scope, so Peter can answer naturally with messages like "merge it", "approve op-123", "clean it up", or "park that one". If several approvals are active, the Operator asks which one rather than guessing.

Before offering push/open PR/cleanup, the system should validate the relevant GitHub credential. If it is missing or stale, the completion DM should say so and provide the credential push/test path.

### Work Moves To GitHub And Main

Megaplan chains already push work to GitHub in many cases. AgentBox should track the branch and PR on the operation record.

After a set of operations completes, final consolidation should use the local `cleanup-loose-branches` discipline:

- survey branches, worktrees, stashes, PRs, and loose remote state;
- classify each as land, delete, or park;
- prefer landing valuable work on main;
- require explicit approval for destructive cleanup;
- clean up remote worktrees and branches after merge.

In other words, AgentBox launches and supervises the work; cleanup-loose-branches is the consolidation and housekeeping playbook.

Discord should expose `cleanup` or `consolidate` as the human path into this. The Operator runs the cleanup-loose-branches survey, posts land/delete/park recommendations, and requires explicit approval before merge, delete, reset, or remote cleanup actions.

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
   - updates status and writes a tick report.

4. Add minimal status/log CLI:
   - `agentbox status`;
   - `agentbox logs <op>`;
   - `agentbox attach <op>`.

5. Add Discord notification before full Discord Operator:
   - Guardian posts run blocked/completed/failed messages;
   - full message-triggered Operator comes after the operation registry is stable.

This avoids boiling the ocean. It proves that one persistent machine can launch a chain into a worktree, track it as an operation, and have Guardian keep checking it. Once that loop works, Discord Operator and additional agent adapters become tool-profile work.

## Broader Inventory Swarm

After the first overlap pass, a broader eight-agent DeepSeek swarm reviewed the user journey against tickets, epics, chains, watchdog, cloud, resident Discord, stores, credentials, git/PR, cleanup, and subagent mechanics. Raw outputs live under:

- `.megaplan/agentbox-everything-swarm/results/`

The swarm had some tool-access noise in its transcripts, so this section includes only findings cross-checked against local files or available local skills.

### What Already Exists

| Desired capability | Existing mechanics | Notes |
|---|---|---|
| User sends Discord message and bot replies | `arnold_pipelines/megaplan/resident/discord.py`, `resident/runtime.py`, `resident/auth.py`, `resident/profile.py` | Message parsing, conversation keys, inbound/outbound events, allowlists, turns, tool calls, and recovery already exist. |
| Add a ticket from Discord | `arnold_pipelines/megaplan/tickets/*`, `megaplan-tickets` skill | Ticket CRUD, tags, file/DB storage, search, source metadata, and ticket/epic linking already exist. Need a Discord-facing tool wrapper. |
| Set up an epic/chain | `arnold_pipelines/megaplan/chain/spec.py`, `megaplan-epic` skill, chain CLI | Chain spec/state already models milestone epics. Need a Discord-friendly chain/epic authoring tool. |
| Launch Megaplan/chain remotely | `cloud bootstrap`, `cloud chain`, `resident/cloud.py`, `cloud/providers/*` | Existing cloud wrapper can start plans/chains and classify results. AgentBox should wrap this as operation creation. |
| Worktree isolation | `bakeoff/worktree.py`, `init --in-worktree`, `chain --in-worktree` | Strong substrate. Needs machine-scoped operation paths and multi-repo support. |
| Guardian repair/relaunch | `scripts/megaplan_live_watchdog.py`, `arnold_pipelines/megaplan/watchdog/*`, `cloud/supervise.py`, `resident/scheduler.py` | There is already a live watchdog and one-shot cloud supervisor. Guardian should compose these, not rewrite them. |
| Push/PR/merge path | `chain/git_ops.py`, `supervisor/pr_merge.py`, GitHub connector/CLI patterns | Chain already knows branch/PR state. Final consolidation should reuse cleanup-loose-branches discipline. |
| Cleanup/consolidation | local `cleanup-loose-branches` skill | Survey branches, worktrees, stashes, PRs, cloud workspaces, and loose state; prefer landing valuable work on main; destructive cleanup requires approval. |
| DeepSeek/subagent diagnosis | `workers/hermes.py`, `runtime/key_pool.py`, parallel review/critique code, local `subagent-launcher` skill | Existing Hermes/DeepSeek path can be used by Guardian for repair diagnosis and by Operator for delegated investigation. |
| Credential seeding | `cloud/auth.py`, `cloud/templates/entrypoint.sh.tmpl`, `cloud/template.py`, SSH/Railway providers | Codex/Hermes OAuth seeding, Claude refresh-token shim, SSH upload, and env secret upload already exist. Needs explicit AgentBox `SecretSpec`. |
| State and audit trail | `store/base.py`, file/DB stores, resident conversations, scheduled jobs, cloud runs, events | The store layer is a strong candidate for operation registry persistence, or at least the model to copy. |

### Existing Mechanics To Prefer

1. **Resident runtime over a new bot loop.** Use `ResidentDiscordService` and the resident runtime as the Discord Operator shell. Add an AgentBox tool profile instead of building a fresh bot.

2. **Tickets first, GitHub issues later.** The local ticket system is already built and linked to Megaplan epics. The Operator can add a Megaplan ticket immediately; GitHub issue mirroring can be a later integration.

3. **Chains as the epic execution backbone.** Chain specs already express milestone order, failure behavior, profile/robustness/depth, PR/merge policy, and state. Do not create a second epic runner.

4. **Watchdog plus cloud supervisor as Guardian v0.** The live watchdog scans local plans/processes; cloud supervise performs safe one-shot chain actions. Guardian should be an operation-registry loop that calls these existing engines.

5. **cleanup-loose-branches for post-run consolidation.** When operations complete, AgentBox should not invent a new "merge everything" policy. It should invoke the cleanup discipline: survey, recommend land/delete/park, and get explicit approval for destructive steps.

6. **DeepSeek subagents for ambiguous repair.** Guardian should call a subagent when it cannot classify a failure cheaply: failing tests without obvious cause, repeated chain stalls, ambiguous PR/branch state, or unclear cleanup recommendations.

### Single-User Simplifications

Because the system is for one user:

- no multi-tenant UI is needed;
- no complex role hierarchy is needed;
- Discord allowlists can be simple: Peter's user id, one guild, maybe one channel/DM;
- natural-language Discord messages are enough for v1; slash commands can come later;
- approvals should be rare and focused on completion, merge, cleanup, credentials, or accepting debt;
- Guardian should prefer autonomous repair over asking for permission on operational failures.

### Revised First Product Slice

The better first slice is:

1. **AgentBox operation registry**, backed by existing store patterns:
   - operation id, kind, repo/worktree, branch, tmux session, log path, status, Guardian tick history, Discord refs, PR refs.

2. **Discord Operator profile**, using resident runtime:
   - tools: `ticket_new`, `chain_create`, `chain_launch`, `status`, `logs`, `guardian_check`, `creds_test`;
   - natural-language messages routed by the agent to those tools.

3. **Megaplan chain operation kind**:
   - create worktree with existing helpers;
   - launch chain using existing chain/cloud mechanics;
   - record operation metadata.

4. **Guardian v0**:
   - loops every `X` minutes;
   - checks all active `megaplan_chain` operations;
   - calls existing cloud supervise/watchdog repair where applicable;
   - launches a DeepSeek diagnostic subagent for unclear failures;
   - handles dead tmux restart, stale chain resume, validation-failure repair, retry caps, and `needs_peter` escalation;
   - reports only meaningful state changes to Discord.

5. **Completion flow**:
   - DM Peter when an operation completes;
   - include summary, validation, branch/PR status, and next action;
   - use cleanup-loose-branches for consolidation after a batch of work.

6. **Discord thin path required for v0**:
   - `add a ticket`;
   - `run this chain`;
   - `what is running/blocked`;
   - `show logs`;
   - completion DM.

CLI-only launch is a useful engineering checkpoint, but it is not a complete first product slice.

## External Projects To Inspect Or Borrow From

### Rover

Repository: `https://github.com/endorhq/rover`

Useful for:

- multi-agent session model;
- isolated work environments;
- support for Claude Code, Codex, Cursor, Gemini, Qwen;
- workflow concepts around many agents on one codebase.

Likely use: reference implementation for session/worktree UX. Do not assume direct adoption until inspected.

### CCManager

Repository: `https://github.com/kbwo/ccmanager`

Useful for:

- managing many coding-agent sessions across worktrees and projects;
- busy/waiting/idle state UX;
- CLI/TUI status and cleanup flows.

Likely use: simpler reference for lifecycle/status patterns.

### OpenACP

Repository: `https://github.com/Open-ACP/OpenACP`

Useful for:

- Discord/Telegram/Slack bridge UX;
- permission and streaming patterns;
- routing chat messages to coding-agent sessions.

Likely use: inspect UX and protocol ideas. Megaplan already has a Discord resident runtime, so direct adoption may not be necessary.

### Netclode

Repository: `https://github.com/angristan/netclode`

Useful for:

- self-hosted cloud coding-agent infrastructure;
- remote machine bootstrap;
- Tailscale and persistent remote agent host ideas.

Likely use: borrow infrastructure ideas only. Its k3s/microVM/JuiceFS architecture is probably heavier than the one-machine/worktree design.

### Coder

Repository: `https://github.com/coder/coder`

Useful for:

- serious remote workspace substrate;
- templates;
- browser IDE/workspace access;
- team access and governance.

Likely use: consider later if AgentBox needs workspace UI, user auth, or managed dev environments. It is not required for the first version.

## Major Components

### 1. Machine Provisioning

Purpose: create and update the Hetzner box reproducibly.

Build:

- `agentbox bootstrap`
- install system packages: git, tmux, Python, Node, Docker optional, GitHub CLI, uv/pip
- install or configure Codex, Claude, Hermes/subagent tooling, Megaplan
- create `/workspace`
- install systemd services for manager and Discord resident
- configure SSH, firewall, non-root user, backups

Reuse:

- Megaplan Cloud SSH provider and templates
- Netclode bootstrap ideas
- Coder template ideas if workspace templates become useful later

### 2. Repo Registry

Purpose: track which repos live on the machine and where their canonical refs are stored.

Example config:

```yaml
repos:
  - name: megaplan
    url: git@github.com:peteromallet/megaplan.git
    default_branch: main
    canonical: /workspace/repos/megaplan.git
  - name: reigh-app
    url: git@github.com:org/reigh-app.git
    default_branch: main
    canonical: /workspace/repos/reigh-app.git
```

Build:

- `agentbox repo add`
- `agentbox repo sync`
- `agentbox repo status`
- `agentbox repo remove`
- stale branch and dirty worktree summaries

Reuse:

- existing git helpers from Megaplan chain/bakeoff code
- Rover/CCManager project registry ideas

### 3. Worktree Service

Purpose: create/remove/list worktrees per operation.

Build:

- create a branch and worktree for an operation;
- support multi-repo operations;
- support clean base vs carried dirty state;
- enforce safe worktree names;
- detect registered-but-missing worktrees;
- archive or remove completed worktrees.

Preferred mechanics:

```bash
git clone --bare git@github.com:org/repo.git /workspace/repos/repo.git
git --git-dir=/workspace/repos/repo.git worktree add \
  /workspace/worktrees/op-123/repo \
  -b agent/op-123 \
  origin/main
```

Reuse:

- `arnold_pipelines/megaplan/bakeoff/worktree.py`
- existing `--in-worktree` behavior from `arnold_pipelines/megaplan/cli/__init__.py`

Needed extraction:

- parameterize worktree root path instead of hardcoding `~/Documents/.megaplan-worktrees`;
- operate on named repos, not only current working directory;
- return structured metadata instead of mutating argparse only.

### 4. Credential Sync

Purpose: push selected local credentials to the remote machine.

Build:

- `agentbox creds push`
- `agentbox creds list`
- `agentbox creds test`
- `agentbox creds rotate`
- remote `/workspace/secrets` with strict permissions
- per-operation env injection

Credential classes:

- GitHub token or SSH key material;
- Codex OAuth/auth bundle;
- Claude refresh token or API key fallback;
- OpenAI/Anthropic/DeepSeek/Fireworks keys;
- Discord bot token;
- Supabase/Railway/project-specific tokens.

Reuse:

- Megaplan Cloud Codex OAuth seed logic;
- Claude refresh-token shim design from the Megaplan Cloud skill;
- Railway secret upload semantics as a reference;
- `age`, `pass`, or 1Password CLI patterns if encrypted-at-rest storage is required.

Rule: sync only explicit credentials. Do not dump the entire local environment.

### Proactive Credential Validation

Credentials should be checked before expensive work starts, not only after a run fails.

- `megaplan-chain` launch checks GitHub, Codex/Claude/Hermes credentials required by the selected profile, and any chain-declared secrets before creating the worktree.
- `codex` launch checks the Codex auth bundle.
- `claude` launch checks the Claude refresh token or API key.
- push/PR actions check GitHub auth before offering the action as ready.

If validation fails, the Operator replies in Discord with the exact missing or stale credential and the local command Peter should run. After Peter pushes credentials, the Operator should retest and resume the blocked launch or operation when safe.

Guardian should periodically run lower-priority credential health checks and surface stale or missing credentials in the daily briefing.

### 5. Operation Registry

Purpose: every launched unit of work has a durable identity and inspectable state.

Operation record:

```yaml
id: op-20260623-foo
kind: megaplan-chain
status: running
source: discord
created_at: "2026-06-23T10:00:00Z"
repos:
  - name: megaplan
    branch: agent/op-20260623-foo
    worktree: /workspace/worktrees/op-20260623-foo/megaplan
tmux_session: op-20260623-foo
log: /workspace/runs/op-20260623-foo/log.txt
events: /workspace/runs/op-20260623-foo/events.ndjson
manifest: /workspace/runs/op-20260623-foo/manifest.yaml
```

Build:

- file or SQLite-backed registry;
- operation creation;
- status updates;
- mapping from tmux session to operation;
- log/event path tracking;
- PR/branch/CI metadata.
- structured event stream path and last event sequence.

Reuse:

- Megaplan chain state model;
- Megaplan resident store patterns;
- CCManager/Rover status models;
- `.megaplan/plans` conventions where useful.

This is the product-specific core. We should expect to build it ourselves.

### 6. Process Runner

Purpose: launch, monitor, stop, restart, and attach to long-running operations.

Build:

- tmux session per operation;
- log capture to `/workspace/runs/<op>/log.txt`;
- structured event append to `/workspace/runs/<op>/events.ndjson`;
- status classifier;
- stop/restart/attach commands;
- optional resource limits later.

Reuse:

- Megaplan Cloud tmux/session/log conventions;
- Rover/CCManager agent process handling;
- systemd for long-running manager services.

### 7. Agent Adapters

Purpose: normalize how different agent or task types are launched.

Initial adapter types:

- `megaplan-chain`
- `megaplan-plan`
- `codex`
- `claude`
- `subagent`
- `test`
- `shell`

Adapter interface:

```python
class OperationAdapter:
    def prepare(operation): ...
    def command(operation): ...
    def classify(operation): ...
    def stop(operation): ...
```

Reuse:

- Megaplan worker/agent routing;
- existing subagent/Hermes conventions;
- Rover supported-agent wrappers;
- OpenACP protocol ideas.

### 8. Guardian Daemon

Purpose: continuously supervise operations and the machine.

Build:

- periodic status loop;
- classify operations as running, waiting, blocked, failed, completed, stale;
- detect dead tmux sessions;
- detect stuck logs/no heartbeat;
- detect dirty/unpushed repos;
- disk/RAM/process pressure checks;
- safe restart/continue policy;
- pending approval queue;
- Discord notifications.

Safe actions:

- summarize;
- collect logs;
- restart a known-safe missing runner;
- continue a Megaplan chain if the next step is unambiguous;
- notify Discord.

Unsafe actions requiring confirmation:

- delete worktrees;
- reset branches;
- resolve merge conflicts;
- merge PRs;
- kill unknown processes;
- push or publish sensitive branches when policy requires approval.

Reuse:

- `arnold_pipelines/megaplan/cloud/supervise.py`
- `arnold_pipelines/megaplan/supervisor/*`
- Megaplan resident scheduler
- live supervisor pipeline patterns
- `scripts/megaplan_live_watchdog.py` and `arnold_pipelines/megaplan/watchdog/*` as plugin/library mechanics, not a competing daemon

### 9. Discord Operator

Purpose: primary human interface for the machine, and an on-demand agent that can operate on AgentBox state/tools when the user sends a Discord message.

Build commands:

- `status`
- `repos`
- `help`
- `run <repo> <task>`
- `run chain <repo> <spec>`
- `logs <operation>`
- `attach <operation>` or instructions for SSH/tmux attach
- `approve <confirmation>`
- `stop <operation>`
- `restart <operation>`
- `cleanup <operation>`
- `consolidate`
- `daily` or `briefing`
- `resolve <description>`
- `creds list`
- `creds test`
- `creds push guide`
- `summarize`

Notification events:

- operation started;
- operation blocked;
- approval needed;
- operation completed;
- operation failed;
- disk/memory warning;
- dirty/unpushed branch warning.

Reuse:

- Megaplan resident Discord service;
- Megaplan resident runtime/auth/confirmation manager;
- OpenACP UX and streaming patterns;
- existing Hermes Discord send tools where useful.

### 10. Approval And Safety

Purpose: keep destructive actions explicit.

Build:

- confirmation records;
- approval expiry;
- per-user and per-channel allow lists;
- Discord approval flow;
- audit log;
- policy categories: safe, confirm, forbidden.

Reuse:

- Megaplan resident confirmation manager;
- Megaplan cloud supervisor refusal policy;
- OpenACP permission patterns.

### 11. GitHub And PR Integration

Purpose: publish operation output as reviewable work.

Build:

- push branch;
- open draft PR;
- link PR to operation;
- monitor CI;
- post status back to Discord;
- support PR update/retry.

Reuse:

- Megaplan chain git ops;
- GitHub CLI;
- GitHub connector tools;
- existing `yeet` workflow patterns.

### 12. Cleanup And Backup

Purpose: keep the persistent box from accumulating unbounded state.

Build:

- archive completed runs;
- remove completed worktrees after approval;
- prune logs/caches by policy;
- report large directories;
- backup `/workspace/runs`, `/workspace/manager`, and critical config;
- recreate machine from bootstrap + config + synced credentials.

Reuse:

- git worktree prune;
- Hetzner snapshots/backups;
- Megaplan Cloud operational gotchas;
- disk-cleanup patterns.

## CLI Surface

Local commands:

```bash
agentbox bootstrap
agentbox ssh

agentbox repo add megaplan git@github.com:peteromallet/megaplan.git
agentbox repo sync megaplan
agentbox repo status

agentbox creds push
agentbox creds test

agentbox run --repo megaplan --kind codex --task "fix the ssh cloud provider"
agentbox run --repos megaplan,reigh-app --kind shell --cmd "pytest -q"
agentbox run --repo megaplan --kind megaplan-chain --spec briefs/foo/chain.yaml

agentbox status
agentbox logs op-123
agentbox attach op-123
agentbox stop op-123
agentbox cleanup op-123
```

Discord command equivalents:

```text
/status
/repos
/run megaplan fix the ssh cloud provider
/logs op-123
/approve conf-456
/stop op-123
/cleanup op-123
```

## Implementation Phases

### Phase 1: Box Bootstrap

Deliverables:

- Hetzner VM provisioned;
- `/workspace` layout created;
- core tools installed;
- SSH access working;
- one repo cloned;
- Codex/Claude/GitHub credentials manually verified.

### Phase 2: Repo And Worktree Service

Deliverables:

- `agentbox.yaml`;
- repo registry;
- bare canonical repo support;
- operation worktree creation/removal;
- multi-repo worktree creation;
- reuse or extraction of existing Megaplan worktree helpers.

### Phase 3: Operation Registry And Runner

Deliverables:

- operation IDs;
- manifests and state files;
- tmux session launch;
- log capture;
- status/logs/attach/stop commands.

### Phase 4: Credential Sync

Deliverables:

- explicit credential manifest;
- local-to-remote push;
- remote secret env files;
- auth test command;
- Codex and Claude credential support using existing Megaplan Cloud patterns.

### Phase 5: Guardian Daemon

Deliverables:

- systemd service;
- periodic operation checks;
- dead/stale/completed classification;
- safe action policy;
- health report.

### Phase 6: Discord Operator Integration

Deliverables:

- resident Discord service connected to AgentBox tools;
- commands for status/run/logs/approve/stop;
- on-demand Operator agent launched for Discord messages;
- operation notifications;
- allow-list enforcement.

### Phase 7: Megaplan Native Integration

Deliverables:

- Megaplan chain operation adapter;
- existing cloud/chain supervisor reused for chain operations;
- branch/PR/CI state linked back to operation registry;
- Railway kept as remote-worker provider, not primary AgentBox substrate.

### Phase 8: Hardening

Deliverables:

- backups/snapshots;
- secret encryption or external password manager integration;
- cleanup policies;
- resource-pressure warnings;
- restore/recreate documentation;
- migration path from `CX53` to dedicated server.

## Open Design Decisions

1. Should canonical repos be bare mirrors or normal main checkouts?
   - Bare mirrors are cleaner for managed worktrees.
   - Normal checkouts are easier for humans to inspect.
   - Recommendation: use bare repos under `/workspace/repos/*.git`, and expose active work through worktrees only.


# Local Code Surface Inventory
scripts/simulate_watchdog_end_to_end.py:2:"""End-to-end simulation of the live watchdog repair + relaunch + recheck flow.
scripts/simulate_watchdog_end_to_end.py:4:This script creates a synthetic blocked plan, runs the watchdog against it with a
scripts/simulate_watchdog_end_to_end.py:5:fake megaplan CLI, and verifies the watchdog:
scripts/simulate_watchdog_end_to_end.py:52:events_path = Path(plan_dir) / "events.ndjson"
scripts/simulate_watchdog_end_to_end.py:67:    events_path.parent.mkdir(parents=True, exist_ok=True)
scripts/simulate_watchdog_end_to_end.py:68:    with events_path.open("a") as f:
scripts/simulate_watchdog_end_to_end.py:81:if cmd == "watchdog-worker":
scripts/simulate_watchdog_end_to_end.py:83:    # Keep this process alive so the watchdog sees a live megaplan-correlated
scripts/simulate_watchdog_end_to_end.py:109:    # Start a fake worker process so the next watchdog scan sees a live process.
scripts/simulate_watchdog_end_to_end.py:113:        [sys.executable, str(Path(__file__).resolve()), "watchdog-worker", str(plan_dir)],
scripts/simulate_watchdog_end_to_end.py:161:    events = [
scripts/simulate_watchdog_end_to_end.py:165:    (plan_dir / "events.ndjson").write_text(
scripts/simulate_watchdog_end_to_end.py:166:        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
scripts/simulate_watchdog_end_to_end.py:172:def _run_watchdog(args: list[str], env: dict[str, str]) -> dict[str, object]:
scripts/simulate_watchdog_end_to_end.py:173:    """Run the watchdog CLI and return the combined report."""
scripts/simulate_watchdog_end_to_end.py:175:        [sys.executable, "-B", str(REPO_ROOT / "scripts" / "megaplan_live_watchdog.py"), *args],
scripts/simulate_watchdog_end_to_end.py:183:        raise RuntimeError(f"watchdog failed with rc={result.returncode}")
scripts/simulate_watchdog_end_to_end.py:205:        log_path = tmp / "watchdog.log"
scripts/simulate_watchdog_end_to_end.py:216:        print("\n=== Running watchdog (repair + 10s recheck) ===")
scripts/simulate_watchdog_end_to_end.py:217:        report = _run_watchdog(
arnold_pipelines/megaplan/store/plan_repository.py:87:            from arnold_pipelines.megaplan.observability.events_projection import ensure_events_projection
arnold_pipelines/megaplan/store/plan_repository.py:89:            ensure_events_projection(repo.plan_dir, store=store, plan_id=repo.plan_name)
arnold_pipelines/megaplan/store/base.py:477:    def list_epic_events(
arnold_pipelines/megaplan/store/base.py:488:    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
arnold_pipelines/megaplan/store/base.py:494:    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
arnold_pipelines/megaplan/store/base.py:506:    def events_for_plan(self, plan_id: str) -> Iterator[StoredEvent]:
arnold_pipelines/megaplan/store/base.py:617:    def load_hot_context(self, epic_id: str | None) -> HotContext:
arnold_pipelines/megaplan/store/base.py:877:    def create_ticket(
arnold_pipelines/megaplan/store/base.py:914:    def link_ticket_to_epic(
arnold_pipelines/megaplan/store/base.py:1210:    def upsert_resident_conversation(
arnold_pipelines/megaplan/store/base.py:1267:    def claim_due_scheduled_jobs(
arnold_pipelines/megaplan/store/base.py:1279:    def list_scheduled_jobs(
arnold_pipelines/megaplan/store/base.py:1310:    def list_cloud_runs(
arnold_pipelines/megaplan/store/base.py:1328:    def list_progress_events(
arnold_pipelines/megaplan/cloud/preflight.py:36:    "claude": ("bun", "claude", "tmux"),
arnold_pipelines/megaplan/cloud/preflight.py:37:    "shannon": ("bun", "claude", "tmux"),
arnold_pipelines/megaplan/cloud/preflight.py:38:    "codex": ("codex", "tmux"),
arnold_pipelines/megaplan/observability/fold.py:1:"""Pure fold-over-events projection for plan state.
arnold_pipelines/megaplan/observability/fold.py:5:- ``read_events(plan_dir)`` — return all events from events.ndjson in seq order.
arnold_pipelines/megaplan/observability/fold.py:6:- ``fold_events(events)`` — pure, I/O-free last-snapshot-wins replay over
arnold_pipelines/megaplan/observability/fold.py:7:  STATE_WRITTEN events; ignores all other event kinds.
arnold_pipelines/megaplan/observability/fold.py:18:_NDJSON_FILE = "events.ndjson"
arnold_pipelines/megaplan/observability/fold.py:21:def read_events(plan_dir: Path) -> List[dict]:
arnold_pipelines/megaplan/observability/fold.py:22:    """Return all events from ``plan_dir/events.ndjson`` in seq order.
arnold_pipelines/megaplan/observability/fold.py:28:    from arnold_pipelines.megaplan.observability.events_projection import ensure_events_projection
arnold_pipelines/megaplan/observability/fold.py:30:    ensure_events_projection(Path(plan_dir))
arnold_pipelines/megaplan/observability/fold.py:48:def fold_events(events: List[dict]) -> Dict[str, Any]:
arnold_pipelines/megaplan/observability/fold.py:49:    """Pure, I/O-free last-snapshot-wins projection over STATE_WRITTEN events.
arnold_pipelines/megaplan/observability/fold.py:51:    Replays only ``kind == "state_written"`` events in seq order and returns
arnold_pipelines/megaplan/observability/fold.py:55:    Returns an empty dict if no STATE_WRITTEN events are present.
arnold_pipelines/megaplan/observability/fold.py:59:    state_written_events = [
arnold_pipelines/megaplan/observability/fold.py:60:        e for e in events if e.get("kind") == "state_written"
arnold_pipelines/megaplan/observability/fold.py:62:    state_written_events.sort(key=lambda e: e.get("seq", 0))
arnold_pipelines/megaplan/observability/fold.py:65:    for event in state_written_events:
arnold_pipelines/megaplan/observability/fold.py:74:    """Rebuild plan state from the shadow-WAL events.ndjson.
arnold_pipelines/megaplan/observability/fold.py:76:    Thin alias for ``fold_events(read_events(plan_dir))`` — the canonical
arnold_pipelines/megaplan/observability/fold.py:80:    return fold_events(read_events(Path(plan_dir)))
arnold_pipelines/megaplan/observability/fold.py:88:    """Assert ``fold_events(read_events(...))`` equals the live ``state.json``.
arnold_pipelines/megaplan/observability/fold.py:104:        When ``None`` (default), events are read from ``plan_dir``. When set,
arnold_pipelines/megaplan/observability/fold.py:105:        events are read from ``recorded_trace_dir`` and folded against the
arnold_pipelines/megaplan/observability/fold.py:110:    folded = fold_events(read_events(Path(event_source)))
arnold_pipelines/megaplan/observability/fold.py:124:            "assert_fold_equiv: fold(events) != live state.json\n"
arnold_pipelines/megaplan/observability/fold.py:132:def lift_driver_events_to_wal(events: List[dict]) -> List[dict]:
arnold_pipelines/megaplan/observability/fold.py:133:    """Lift driver-level events into shadow-WAL ``STATE_WRITTEN`` form.
arnold_pipelines/megaplan/observability/fold.py:137:    ``msg`` lines for non-transition events such as ``phase`` runs). This
arnold_pipelines/megaplan/observability/fold.py:141:    ``fold_events`` / ``rebuild_state_from_wal``.
arnold_pipelines/megaplan/observability/fold.py:143:    Non-transition driver events (phase commands, terminal markers, completion
arnold_pipelines/megaplan/observability/fold.py:144:    verdicts) are skipped — only events that carry a driver ``state`` snapshot
arnold_pipelines/megaplan/observability/fold.py:149:    for ev in events:
arnold_pipelines/megaplan/observability/fold.py:204:    events = corpus.get("events") or []
arnold_pipelines/megaplan/observability/fold.py:206:        isinstance(ev, dict) and "state" in ev for ev in events
arnold_pipelines/megaplan/observability/fold.py:220:    lift: Callable[[List[dict]], List[dict]] = lift_driver_events_to_wal,
arnold_pipelines/megaplan/observability/fold.py:221:    fold: Callable[[List[dict]], Dict[str, Any]] = fold_events,
arnold_pipelines/megaplan/observability/fold.py:232:    ``corpus_filename`` sibling, lifts the driver events into shadow-WAL form,
arnold_pipelines/megaplan/observability/fold.py:266:        events = corpus.get("events") or []
arnold_pipelines/megaplan/observability/fold.py:267:        wal_events = lift(events)
arnold_pipelines/megaplan/observability/fold.py:268:        folded = fold(wal_events)
arnold_pipelines/megaplan/observability/doctor.py:28:from arnold_pipelines.megaplan.observability.events import EventKind, read_events
arnold_pipelines/megaplan/observability/doctor.py:309:    events = list(read_events(plan_dir))
arnold_pipelines/megaplan/observability/doctor.py:314:    for ev in events:
arnold_pipelines/megaplan/observability/doctor.py:339:                for e in events
arnold_pipelines/megaplan/observability/doctor.py:354:    events = list(read_events(plan_dir))
arnold_pipelines/megaplan/observability/doctor.py:356:    for ev in events:
arnold_pipelines/megaplan/cloud/supervise.py:172:def cloud_supervise_tick(
arnold_pipelines/megaplan/cloud/supervise.py:192:        _tmux_chain_restart_command,
arnold_pipelines/megaplan/cloud/supervise.py:479:                restart_cmd = _tmux_chain_restart_command(
arnold_pipelines/megaplan/cloud/supervise.py:546:                restart_cmd = _tmux_chain_restart_command(
arnold_pipelines/megaplan/cloud/supervise.py:678:                restart_cmd = _tmux_chain_restart_command(
arnold_pipelines/megaplan/handlers/override.py:301:def _emit_routed_override_events(
arnold_pipelines/megaplan/handlers/override.py:309:        from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/handlers/override.py:486:    _emit_routed_override_events(args.override_action, plan_dir=plan_dir, state=persisted_state, args=args)
arnold_pipelines/megaplan/handlers/override.py:645:    # Emit observability events
arnold_pipelines/megaplan/handlers/override.py:647:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:680:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:1001:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:1046:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:1251:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:1337:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/handlers/override.py:1707:        from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/store/db.py:139:    "upsert_resident_conversation",
arnold_pipelines/megaplan/store/db.py:143:    "claim_due_scheduled_jobs",
arnold_pipelines/megaplan/store/db.py:165:    "create_ticket",
arnold_pipelines/megaplan/store/db.py:167:    "link_ticket_to_epic",
scripts/megaplan_live_watchdog.py:25:from arnold_pipelines.megaplan.watchdog.discovery import DEFAULT_SCAN_ROOTS
scripts/megaplan_live_watchdog.py:26:from arnold_pipelines.megaplan.watchdog.log import DEFAULT_LOG_PATH, log_event, setup_logging
scripts/megaplan_live_watchdog.py:27:from arnold_pipelines.megaplan.watchdog.registry import Observation, WatchdogRegistry
scripts/megaplan_live_watchdog.py:28:from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner
scripts/megaplan_live_watchdog.py:29:from arnold_pipelines.megaplan.watchdog.retry import RetryLoop, RetryOutcome
scripts/megaplan_live_watchdog.py:30:from arnold_pipelines.megaplan.watchdog.snapshot import build_snapshot
scripts/megaplan_live_watchdog.py:33:DEFAULT_REGISTRY_PATH = "~/.megaplan/watchdog/registry.ndjson"
scripts/megaplan_live_watchdog.py:97:        help="Path to the watchdog log file.",
arnold_pipelines/megaplan/observability/cost.py:1:"""``megaplan cost`` — plan cost breakdown from events.ndjson and state.json.
arnold_pipelines/megaplan/observability/cost.py:15:from arnold_pipelines.megaplan.observability.events import EventKind, read_events
arnold_pipelines/megaplan/observability/cost.py:90:def _aggregate(events: list[dict], meta_cost: float) -> dict:
arnold_pipelines/megaplan/observability/cost.py:91:    """Run the full cost + token aggregation over *events*.
arnold_pipelines/megaplan/observability/cost.py:99:    events_cost: float = 0.0
arnold_pipelines/megaplan/observability/cost.py:119:    # ── single pass over events ────────────────────────────────────────
arnold_pipelines/megaplan/observability/cost.py:120:    for ev in events:
arnold_pipelines/megaplan/observability/cost.py:141:            # running events_cost sum (before reconciliation)
arnold_pipelines/megaplan/observability/cost.py:142:            events_cost += cost
arnold_pipelines/megaplan/observability/cost.py:195:    # Take the larger of events_cost vs meta_cost so we never undercount.
arnold_pipelines/megaplan/observability/cost.py:196:    if meta_cost > events_cost:
arnold_pipelines/megaplan/observability/cost.py:200:        total_cost = events_cost
arnold_pipelines/megaplan/observability/cost.py:201:        cost_source = "events"
arnold_pipelines/megaplan/observability/cost.py:234:        "events_cost": events_cost,
arnold_pipelines/megaplan/observability/cost.py:348:            "\n⚠  Token counts are *estimates* — some LLM_CALL_END events "
arnold_pipelines/megaplan/observability/cost.py:418:    Read-only invariant: this handler only reads events.ndjson and
arnold_pipelines/megaplan/observability/cost.py:429:    # Read cost-related events once (no new ndjson parser).
arnold_pipelines/megaplan/observability/cost.py:430:    events = list(
arnold_pipelines/megaplan/observability/cost.py:431:        read_events(
arnold_pipelines/megaplan/observability/cost.py:449:    agg = _aggregate(events, meta_cost)
arnold_pipelines/megaplan/cloud/template.py:60:  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
arnold_pipelines/megaplan/cloud/template.py:62:  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${AUTO_COMMAND}"
arnold_pipelines/megaplan/cloud/template.py:69:  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
arnold_pipelines/megaplan/cloud/template.py:71:  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${CHAIN_COMMAND}"
arnold_pipelines/megaplan/cloud/template.py:75:_IDLE_RUNNER = Template("""tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l" """)
arnold_pipelines/megaplan/observability/routing_ledger.py:129:        from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/store/file.py:300:        events_path = self._events_path(epic_id)
arnold_pipelines/megaplan/store/file.py:303:            transaction.add_event(events_path, record)
arnold_pipelines/megaplan/store/file.py:309:            event_logs=[journal_event_log(events_path, [record])],
arnold_pipelines/megaplan/store/file.py:341:    def _events_path(self, epic_id: str) -> Path:
arnold_pipelines/megaplan/store/file.py:342:        return self._epic_dir(epic_id) / "events.jsonl"
arnold_pipelines/megaplan/store/file.py:389:    def _progress_events_dir(self) -> Path:
arnold_pipelines/megaplan/store/file.py:390:        return self.root / "progress_events"
arnold_pipelines/megaplan/store/file.py:395:    def _scheduled_jobs_dir(self) -> Path:
arnold_pipelines/megaplan/store/file.py:396:        return self.root / "scheduled_jobs"
arnold_pipelines/megaplan/store/file.py:460:        return self._progress_events_dir() / f"{event_id}.json"
arnold_pipelines/megaplan/store/file.py:466:        return self._scheduled_jobs_dir() / f"{job_id}.json"
arnold_pipelines/megaplan/store/file.py:835:    def _progress_events(self) -> list[ProgressEvent]:
arnold_pipelines/megaplan/store/file.py:836:        return self._iter_models(self._progress_events_dir(), ProgressEvent)
arnold_pipelines/megaplan/store/file.py:841:    def _scheduled_jobs(self) -> list[ScheduledJob]:
arnold_pipelines/megaplan/store/file.py:842:        return self._iter_models(self._scheduled_jobs_dir(), ScheduledJob)
arnold_pipelines/megaplan/handlers/init.py:586:            "events": outcome.events,
arnold_pipelines/megaplan/store/_db/conversations.py:273:    def load_hot_context(self, epic_id: str | None) -> HotContext:
arnold_pipelines/megaplan/observability/introspect.py:22:from arnold_pipelines.megaplan.observability.events import EventKind, read_events
arnold_pipelines/megaplan/observability/introspect.py:233:    events: list[dict],
arnold_pipelines/megaplan/observability/introspect.py:263:    for ev in events:
arnold_pipelines/megaplan/observability/introspect.py:271:    for ev in events:
arnold_pipelines/megaplan/observability/introspect.py:295:        return "quiet", "no events recorded yet"
arnold_pipelines/megaplan/observability/introspect.py:480:    # Read all events
arnold_pipelines/megaplan/observability/introspect.py:481:    events = list(read_events(plan_dir))
arnold_pipelines/megaplan/observability/introspect.py:484:    liveness, liveness_reason = _compute_liveness(events, plan_dir, state, now_ts)
arnold_pipelines/megaplan/observability/introspect.py:513:    subprocess_events = [
arnold_pipelines/megaplan/observability/introspect.py:514:        e for e in events
arnold_pipelines/megaplan/observability/introspect.py:519:        "events_count": len(subprocess_events),
arnold_pipelines/megaplan/observability/introspect.py:520:        "most_recent": subprocess_events[-1] if subprocess_events else None,
arnold_pipelines/megaplan/observability/introspect.py:595:    event_kinds_seen = sorted(set(e.get("kind") for e in events))
arnold_pipelines/megaplan/observability/introspect.py:597:        "total": len(events),
arnold_pipelines/megaplan/observability/introspect.py:598:        "first_ts": events[0].get("ts_utc") if events else None,
arnold_pipelines/megaplan/observability/introspect.py:599:        "last_ts": events[-1].get("ts_utc") if events else None,
arnold_pipelines/megaplan/observability/introspect.py:606:    for ev in events:
arnold_pipelines/megaplan/observability/introspect.py:611:    for ev in events:
arnold_pipelines/megaplan/observability/introspect.py:622:        for e in events
arnold_pipelines/megaplan/auto.py:47:from arnold_pipelines.megaplan.observability.events import (
arnold_pipelines/megaplan/auto.py:50:    read_events,
arnold_pipelines/megaplan/auto.py:187:    events: list[dict[str, Any]] = field(default_factory=list)
arnold_pipelines/megaplan/auto.py:209:                "events": self.events,
arnold_pipelines/megaplan/auto.py:2324:        for event in read_events(plan_dir):
arnold_pipelines/megaplan/auto.py:2412:    human-readable progress; structured events are collected on the outcome.
arnold_pipelines/megaplan/auto.py:2418:    events: list[dict[str, Any]] = []
arnold_pipelines/megaplan/auto.py:2473:        events.append({"msg": msg, **fields})
arnold_pipelines/megaplan/auto.py:2572:            events=events,
arnold_pipelines/megaplan/auto.py:2673:                events.append({"msg": message, "phase": "execute", "plan": plan})
arnold_pipelines/megaplan/auto.py:2675:            events.append(
arnold_pipelines/megaplan/auto.py:3690:            events.append(
arnold_pipelines/megaplan/auto.py:3728:                events.append(
arnold_pipelines/megaplan/observability/composition_obs.py:40:    events: List[dict] = field(default_factory=list)
arnold_pipelines/megaplan/observability/composition_obs.py:43:        self.events.append({"kind": kind, "payload": dict(payload or {})})
arnold_pipelines/megaplan/observability/composition_obs.py:66:    The legacy ``trace.read_events`` + ``find_plan_dir`` path stays live
arnold_pipelines/megaplan/observability/composition_obs.py:70:    return list(obs.events)
arnold_pipelines/megaplan/cloud/cli.py:22:from arnold_pipelines.megaplan.cloud.auth import seed_codex_oauth
arnold_pipelines/megaplan/cloud/cli.py:118:        help="List active cloud chain tmux sessions on the shared runner",
arnold_pipelines/megaplan/cloud/cli.py:130:        help="Attach to the remote tmux session",
arnold_pipelines/megaplan/cloud/cli.py:134:        help="Override the remote tmux session name for providers that support sessions",
arnold_pipelines/megaplan/cloud/cli.py:151:        help="List active cloud chain tmux sessions on the shared runner",
arnold_pipelines/megaplan/cloud/cli.py:244:                seed_result = seed_codex_oauth(spec, provider, writer=seed_messages.append)
arnold_pipelines/megaplan/cloud/cli.py:541:def _tmux_launch_status(result, *, session_name: str = "megaplan-chain") -> str:
arnold_pipelines/megaplan/cloud/cli.py:578:    tmux_result,
arnold_pipelines/megaplan/cloud/cli.py:609:        "tmux": {
arnold_pipelines/megaplan/cloud/cli.py:611:            "status": _tmux_launch_status(tmux_result, session_name=ctx.session_name),
arnold_pipelines/megaplan/cloud/cli.py:712:    session name or chain tmux session name.
arnold_pipelines/megaplan/cloud/cli.py:804:    events = seed_result.get("events", [])
arnold_pipelines/megaplan/cloud/cli.py:806:    for event in events:
arnold_pipelines/megaplan/cloud/cli.py:810:        return "no oauth seed events"
arnold_pipelines/megaplan/cloud/cli.py:924:    Both ``_run_chain_wrapper`` and ``cloud_supervise_tick`` use this helper
arnold_pipelines/megaplan/cloud/cli.py:987:def _tmux_chain_launch_command(
arnold_pipelines/megaplan/cloud/cli.py:1000:    """Return a single shell command that ensures a tmux session is running the chain.
arnold_pipelines/megaplan/cloud/cli.py:1034:        f"if tmux has-session -t {shlex.quote(name)} 2>/dev/null; then "
arnold_pipelines/megaplan/cloud/cli.py:1043:        f"tmux new-session -d -s {shlex.quote(name)} -c {shlex.quote(workspace)} {shlex.quote(chain_cmd)}; "
arnold_pipelines/megaplan/cloud/cli.py:1049:def _tmux_chain_restart_command(
arnold_pipelines/megaplan/cloud/cli.py:1058:    """Return a shell command that kills any existing tmux session and starts a
arnold_pipelines/megaplan/cloud/cli.py:1080:        f"if tmux has-session -t {shlex.quote(name)} 2>/dev/null; then "
arnold_pipelines/megaplan/cloud/cli.py:1082:        f"tmux kill-session -t {shlex.quote(name)} 2>/dev/null; "
arnold_pipelines/megaplan/cloud/cli.py:1088:        f"tmux new-session -d -s {shlex.quote(name)} -c {shlex.quote(workspace)} {shlex.quote(chain_cmd)}; "
arnold_pipelines/megaplan/cloud/cli.py:1170:    alive = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
arnold_pipelines/megaplan/cloud/cli.py:1338:    seed_codex_oauth(spec, provider)
arnold_pipelines/megaplan/cloud/cli.py:1380:        _tmux_chain_launch_command(
arnold_pipelines/megaplan/cloud/cli.py:1396:            (result.stderr or result.stdout or "remote tmux launch failed").strip(),
arnold_pipelines/megaplan/cloud/cli.py:1406:        tmux_result=result,
arnold_pipelines/megaplan/cloud/cli.py:1508:    implemented in :func:`cloud_supervise_tick`.
arnold_pipelines/megaplan/cloud/cli.py:1511:    from arnold_pipelines.megaplan.cloud.supervise import cloud_supervise_tick  # noqa: F811
arnold_pipelines/megaplan/cloud/cli.py:1513:    report = cloud_supervise_tick(root, args, spec, provider)
arnold_pipelines/megaplan/cloud/cli.py:1541:proc = subprocess.run(["tmux", "list-sessions", "-F", "#S"], text=True, capture_output=True)
arnold_pipelines/megaplan/cloud/cli.py:1826:    SSH attach session names or chain tmux session names.  For Railway the
arnold_pipelines/megaplan/cloud/cli.py:2032:            proc = ssh_meth(f"tmux has-session -t {session_esc} 2>/dev/null && echo alive || echo dead")
arnold_pipelines/megaplan/cloud/cli.py:2034:                runner = {"status": "alive", "session": resolved_session, "detail": "tmux session present"}
arnold_pipelines/megaplan/cloud/cli.py:2036:                runner = {"status": "dead", "session": resolved_session, "detail": "tmux session absent"}
arnold_pipelines/megaplan/observability/__init__.py:5:- ``read_events()``: generator for readers (introspect, trace, doctor).
arnold_pipelines/megaplan/observability/__init__.py:6:- ``spawned()``: context manager for subprocess lifecycle events.
arnold_pipelines/megaplan/observability/__init__.py:9:from arnold_pipelines.megaplan.observability.events import (
arnold_pipelines/megaplan/observability/__init__.py:14:    read_events,
arnold_pipelines/megaplan/observability/__init__.py:23:from arnold_pipelines.megaplan.observability.events_projection import (
arnold_pipelines/megaplan/observability/__init__.py:24:    ensure_events_projection,
arnold_pipelines/megaplan/observability/__init__.py:25:    project_events,
arnold_pipelines/megaplan/observability/__init__.py:26:    project_events_ndjson,
arnold_pipelines/megaplan/observability/__init__.py:41:    read_evaluand_events,
arnold_pipelines/megaplan/observability/__init__.py:52:    "read_events",
arnold_pipelines/megaplan/observability/__init__.py:59:    "ensure_events_projection",
arnold_pipelines/megaplan/observability/__init__.py:60:    "project_events",
arnold_pipelines/megaplan/observability/__init__.py:61:    "project_events_ndjson",
arnold_pipelines/megaplan/observability/__init__.py:77:    "read_evaluand_events",
arnold_pipelines/megaplan/handlers/gate.py:1014:            from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/quality_resolutions.py:3:Durable, append-only events stored in ``state.json`` under
arnold_pipelines/megaplan/quality_resolutions.py:26:    latest_events_by_key,
arnold_pipelines/megaplan/quality_resolutions.py:163:    resolution_events: list[dict[str, Any]] | None,
arnold_pipelines/megaplan/quality_resolutions.py:166:    return latest_events_by_key(
arnold_pipelines/megaplan/quality_resolutions.py:167:        resolution_events,
arnold_pipelines/megaplan/store/_db/assets.py:215:    def create_ticket(
arnold_pipelines/megaplan/store/_db/assets.py:342:    def link_ticket_to_epic(
arnold_pipelines/megaplan/execute/batch.py:533:            from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/execute/batch.py:2040:    from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/execute/batch.py:2076:    from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/execute/batch.py:2129:    from arnold_pipelines.megaplan.observability.events import EventKind, emit
arnold_pipelines/megaplan/observability/events.py:3:Every plan gets one ``events.ndjson`` file in its plan directory.
arnold_pipelines/megaplan/observability/events.py:4:The writer uses a sidecar ``.events.seq`` counter protected by ``fcntl.flock``
arnold_pipelines/megaplan/observability/events.py:10:    from arnold_pipelines.megaplan.observability.events import emit, EventKind
arnold_pipelines/megaplan/observability/events.py:50:    "_envelope_ctx_events", default=None
arnold_pipelines/megaplan/observability/events.py:64:        "observability.events: emit() invoked with no RunEnvelope in "
arnold_pipelines/megaplan/observability/events.py:222:_SEQ_FILE = ".events.seq"
arnold_pipelines/megaplan/observability/events.py:223:_INIT_TS_FILE = ".events.init_ts"

# File List
arnold_pipelines/megaplan/store/base.py
arnold_pipelines/megaplan/store/_file/tickets.py
arnold_pipelines/megaplan/supervisor/ladder.py
arnold_pipelines/megaplan/supervisor/state.py
arnold_pipelines/megaplan/supervisor/pr_merge.py
arnold_pipelines/megaplan/supervisor/driver.py
arnold_pipelines/megaplan/supervisor/outcomes.py
arnold_pipelines/megaplan/supervisor/model.py
arnold_pipelines/megaplan/supervisor/chain_runner.py
arnold_pipelines/megaplan/supervisor/__init__.py
arnold_pipelines/megaplan/supervisor/bakeoff_runner.py
arnold_pipelines/megaplan/supervisor/bakeoff_binding.py
arnold_pipelines/megaplan/handlers/tickets.py
arnold_pipelines/megaplan/data/cloud_skill.md
arnold_pipelines/megaplan/data/tickets_skill.md
arnold_pipelines/megaplan/resident/scheduler.py
arnold_pipelines/megaplan/resident/cli.py
arnold_pipelines/megaplan/resident/coalescing.py
arnold_pipelines/megaplan/resident/runtime.py
arnold_pipelines/megaplan/resident/__init__.py
arnold_pipelines/megaplan/resident/tool_schemas.py
arnold_pipelines/megaplan/resident/discord.py
arnold_pipelines/megaplan/resident/profile.py
arnold_pipelines/megaplan/resident/agent_loop.py
arnold_pipelines/megaplan/resident/tool_registry.py
arnold_pipelines/megaplan/resident/cloud.py
arnold_pipelines/megaplan/resident/config.py
arnold_pipelines/megaplan/resident/auth.py
arnold_pipelines/megaplan/watchdog/tmux_scan.py
arnold_pipelines/megaplan/watchdog/snapshot.py
arnold_pipelines/megaplan/watchdog/processes.py
arnold_pipelines/megaplan/watchdog/orphans.py
arnold_pipelines/megaplan/watchdog/repair_runner.py
arnold_pipelines/megaplan/watchdog/retry.py
arnold_pipelines/megaplan/watchdog/__init__.py
arnold_pipelines/megaplan/watchdog/registry.py
arnold_pipelines/megaplan/watchdog/log.py
arnold_pipelines/megaplan/watchdog/discovery.py
arnold_pipelines/megaplan/watchdog/signals.py
arnold_pipelines/megaplan/watchdog/correlate.py
arnold_pipelines/megaplan/cloud/preflight.py
arnold_pipelines/megaplan/cloud/supervise.py
arnold_pipelines/megaplan/skills/megaplan-tickets/SKILL.md
arnold_pipelines/megaplan/chain/hinge_gate.py
arnold_pipelines/megaplan/chain/m5_eval_gates.py
arnold_pipelines/megaplan/chain/ci_hook.py
arnold_pipelines/megaplan/chain/spec.py
arnold_pipelines/megaplan/chain/__init__.py
arnold_pipelines/megaplan/chain/m3_dual_green.py
arnold_pipelines/megaplan/chain/git_ops.py
arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl
arnold_pipelines/megaplan/cloud/templates/healthserver.py
arnold_pipelines/megaplan/cloud/templates/cloud.yaml.tmpl
arnold_pipelines/megaplan/cloud/templates/chain.yaml.example
arnold_pipelines/megaplan/cloud/templates/__init__.py
arnold_pipelines/megaplan/cloud/templates/docker-compose.yaml.tmpl
arnold_pipelines/megaplan/cloud/templates/Dockerfile
arnold_pipelines/megaplan/cloud/templates/railway.toml.tmpl
arnold_pipelines/megaplan/cloud/template.py
arnold_pipelines/megaplan/cloud/redact.py
arnold_pipelines/megaplan/cloud/cli.py
arnold_pipelines/megaplan/cloud/spec.py
arnold_pipelines/megaplan/cloud/__init__.py
arnold_pipelines/megaplan/bakeoff/worktree.py
arnold_pipelines/megaplan/cloud/auth.py
arnold_pipelines/megaplan/skills/megaplan-cloud/SKILL.md
arnold_pipelines/megaplan/cloud/providers/base.py
arnold_pipelines/megaplan/cloud/providers/ssh.py
arnold_pipelines/megaplan/cloud/providers/__init__.py
arnold_pipelines/megaplan/cloud/providers/railway.py
arnold_pipelines/megaplan/cloud/providers/local.py
arnold_pipelines/megaplan/cloud/wrappers/mp-chain
arnold_pipelines/megaplan/cloud/wrappers/mp-heartbeat
arnold_pipelines/megaplan/cloud/wrappers/mp-supervise
arnold_pipelines/megaplan/cloud/wrappers/arnold-run
arnold_pipelines/megaplan/cloud/wrappers/__init__.py
arnold_pipelines/megaplan/cloud/wrappers/mp-run
arnold_pipelines/megaplan/cloud/wrappers/arnold-supervise
arnold_pipelines/megaplan/cloud/wrappers/arnold-chain
arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
arnold_pipelines/megaplan/workers/hermes.py
arnold_pipelines/megaplan/tickets/identity.py
arnold_pipelines/megaplan/tickets/core.py
arnold_pipelines/megaplan/tickets/__init__.py
arnold_pipelines/megaplan/tickets/registry.py
arnold_pipelines/megaplan/tickets/files.py
arnold_pipelines/megaplan/pipelines/live_supervisor/pipelines.py
arnold_pipelines/megaplan/pipelines/live_supervisor/SKILL.md
arnold_pipelines/megaplan/pipelines/live_supervisor/model.py
arnold_pipelines/megaplan/pipelines/live_supervisor/rules.py
arnold_pipelines/megaplan/pipelines/live_supervisor/__init__.py
arnold_pipelines/megaplan/pipelines/live_supervisor/repair_agent.py
arnold_pipelines/megaplan/pipelines/live_supervisor/steps.py
