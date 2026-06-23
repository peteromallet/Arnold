# Codex Subagent Brief: Prepare AgentBox As Megaplan Epic

Working directory: /Users/peteromalley/Documents/megaplan

Task: Use the megaplan-prep rubric to prepare AgentBox into a launchable megaplan epic. Read the current AgentBox plan embedded below. Return a concrete chain decomposition sized to sprint-sized milestones, with per-milestone outcome/scope/locked decisions/open questions/constraints/done criteria/touchpoints/anti-scope and profile/robustness/depth/vendor choices. The epic should be ready to write into .megaplan/briefs/agentbox-persistent-machine/chain.yaml and milestone .md files. Be pragmatic: v0 must be Discord-first, first operation kind is megaplan_chain, normal checkouts for v0, use existing Megaplan Store/resident runtime/cloud supervise/watchdog/worktree/ticket/credential machinery. Do not overbuild. Return concise but complete content.

Prep rubric assumptions:
- Bigger than two weeks, so split into an epic.
- Each milestone should be roughly <= two weeks human work.
- Use profile names supported by current prep guidance: partnered-3, partnered-4, partnered-5.
- Default robustness full unless a specific milestone merits thorough.
- Depth high only where architectural/store/runner design needs it.
- Vendor codex unless there is a reason otherwise.

--- CURRENT AGENTBOX PLAN ---
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

The operation registry should be a new first-class model in the existing Megaplan Store, not a renamed `cloud_run` and not a parallel database by default. Existing cloud runs, scheduled jobs, resident conversations, progress events, control messages, confirmations, watchdog observations, and chain state are reuse inputs, but AgentBox needs one cross-kind operation record that can represent a chain, Codex run, Claude run, shell/test run, or subagent repair.

Additional required fields:

- `parent_operation_id`, for repair agents and diagnostic subagents launched by Guardian;
- `operation_scope`, for root operation vs child repair/diagnostic operation;
- `lock_version` or equivalent optimistic concurrency field, so Guardian and Operator do not clobber each other's updates;
- `pr_number`, `pr_url`, `ci_status`, `pushed_branch`, and merge/cleanup state;
- `last_event_seq`, so consumers can process `events.ndjson` incrementally.

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

Every Discord message is interpreted before tools run. This should live in the Operator profile as routing guidance, not as a heavy separate classifier service. The goal is to make the agent's behavior predictable without adding enterprise ceremony.

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

When the Operator asks Peter a clarifying question, the question and expected-answer shape are persisted as metadata on the conversation turn that sent it. On the next turn in that scope, the Operator inspects the recent conversation first: if the last Operator message asked a question and Peter's new message plausibly answers it, handle it as the answer before treating it as a new request. Avoid a separate pending-question store unless real usage proves the conversation metadata is not enough.

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

Guardian should use two cadences:

| Loop | Cadence | Scope | Actions |
|---|---:|---|---|
| Liveness tick | 30-60 seconds | running operations | check tmux/process liveness, detect exited sessions, classify obvious completed/failed states, emit fast notifications |
| Deep tick | 5-15 minutes | active operations and machine health | chain state inspection, log/event scan, stall detection, repair attempts, credential health, resource checks, daily briefing |

The liveness tick should stay deliberately shallow. It exists so completion/failure notifications do not wait for the next deep Guardian pass.

### Daily Briefing

The Guardian should also produce one predictable daily briefing at a configured time, for example 08:00 local time. The daily briefing is the proactive habit-forming touchpoint; the 5-15 minute loop remains the operational monitor.

Daily briefing contents:

- completed since last briefing: operation id, repo, summary, branch/PR, validation;
- still running: operation id, kind, repo, elapsed time, current phase;
- blocked or failed: classification, evidence, what Guardian tried, what is needed;
- needs Peter: approvals, credential requests, product decisions, destructive cleanup, quality debt;
- machine health: disk, memory, stale worktrees, dirty/unpushed branches.

For operations launched from Discord, immediate completion DM is mandatory. The daily briefing can summarize those completions later, but it should not be the only completion signal. Routine completions from non-interactive/background operations may be batched into the daily briefing by preference. Failures, blockers, and approval-needed items that cannot wait should still DM immediately.

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

## Safety Policy

All AgentBox actions fall into one of three categories. Guardian and Operator enforce the same table.

**Safe by default:**

- create operation records, worktrees, branches, tmux sessions;
- launch chains, plans, Codex, Claude, subagent, test, and shell operations when requested or policy-authorized;
- read logs, state, registry, repo status, and machine health;
- restart dead tmux sessions or resume stale chains when the operation kind has a known-safe path;
- push branches and open/update draft PRs when operation policy permits;
- classify/report operation state;
- run diagnostic or repair subagents for unclear operational failures, within concurrency budget;
- run credential health checks;
- compile daily briefings.

**Confirm with Peter:**

- merge PRs to main;
- delete worktrees or branches;
- accept failing validation or known quality debt as complete;
- resolve ambiguous product decisions;
- rotate or expose credentials;
- stop an operation that is actively running unless Peter directly requested the stop;
- consolidate/land loose branches after the cleanup-loose-branches survey.

**Forbidden in v1:**

- delete the operation registry or its Store backing database/files;
- mutate another operation's worktree or branch outside a declared parent/child operation relationship;
- push directly to main;
- run broad destructive commands outside `/workspace`;
- silently rotate, print, or exfiltrate credentials.

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
    /megaplan
    /reigh-app
    /reigh-worker

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
    store.sqlite
    config.yaml
```

Example concurrency budget:

```yaml
concurrency:
  max_active_operations: 16
  max_concurrent_subagents: 3
  max_concurrent_worktree_writes_per_repo: 1
```

Guardian must check the subagent budget before launching diagnostic or repair child operations. If capacity is exhausted, it records `awaiting_capacity` and retries later rather than spawning a storm. Worktree create/remove should take a per-repo advisory lock, especially if bare repos are used as canonical stores.

Each operation gets its own isolated worktree and branch. No two agents mutate the same checkout.

Every operation should write both raw and structured logs:

- `log.txt` captures stdout/stderr and agent output for human inspection.
- `events.ndjson` is the machine-readable event stream used by Guardian and Operator. It should include lifecycle, phase, heartbeat, action, outcome, approval, PR, and notification events.

V0 uses normal canonical checkouts under `/workspace/repos`. Bare repositories under `/workspace/repos/*.git` are an optional hardening/scale improvement only after existing Megaplan worktree helpers are proven bare-aware.

Crash-safety rule: every state transition must be queryable in the Store and reflected in the per-operation event history. Prefer adding first-class AgentBox operation/event models to the existing Megaplan Store rather than creating a parallel database. `events.ndjson` is the per-operation replay/debug log; Store state is the queryable current-state view used by Guardian and Operator.

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

Before building the worktree service, do a focused extraction audit of `arnold_pipelines/megaplan/bakeoff/worktree.py` and the CLI worktree setup paths:

- which functions already accept an explicit repo path;
- which functions assume the current working directory;
- which functions assume a normal checkout rather than a bare repo;
- where worktree roots are hardcoded;
- which helpers can be made pure git primitives;
- which orchestration code should remain in Megaplan CLI.

Target outcome: parameterized worktree helpers that can operate on `repo_name`, canonical repo path, target worktree path, base ref, and branch without depending on the process cwd.

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

The first extraction target should be a `megaplan_chain` operation adapter that wraps existing cloud/chain behavior without forcing Guardian through the cloud provider API:

```python
class MegaplanChainAdapter(OperationAdapter):
    def launch(record): ...
    def classify(record): ...
    def supervise_tick(record): ...
    def restart(record): ...
```

This adapter should extract or wrap chain status, tmux restart, sync refresh, and PR-state logic from `cloud_supervise_tick()`, but take an AgentBox operation record as input. If an existing helper requires `provider.ssh_exec`, either add a local execution provider for AgentBox or split the helper into provider-independent classification plus provider-specific command execution.

Call this the **host-local execution provider**. It is different from the existing Docker-compose-oriented local cloud provider. It runs directly on the persistent machine, creates tmux sessions, writes logs/events under `/workspace/runs`, and never SSHes back into the same host.

Tmux/session naming must be parameterized by operation id. Any hardcoded `"agent"` or `"megaplan-chain"` session assumptions need an extraction task before multiple concurrent operations can be safe.

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

9. **Extraction seams are the critical implementation work.** The resident runtime, cloud supervise, watchdog, worktree helpers, and credential seeding are real assets, but they are scoped to conversations, cloud runs, plans, or current repos. AgentBox should add thin extraction layers before building new behavior on top of them.

10. **Avoid duplicate scheduling loops.** Resident scheduler remains for resident jobs and Discord/cloud checks. Guardian owns operation supervision. The live watchdog does not run as a separate timer in v1. If a scheduled job path is reused for Guardian ticks, it must be scoped by job kind so resident jobs and Guardian operations do not race each other.

### First Slice

Build the smallest Discord-first loop that proves the architecture with real Megaplan chains. CLI commands are allowed as internal scaffolding, but a CLI-only loop is not a complete v0.

1. **Thin operation registry**
   - `id`, `kind`, `repo`, `worktree`, `branch`, `tmux_session`, `log_path`, `events_path`, `status`, `last_check`, `discord_refs`, `metadata`;
   - append-only event history plus queryable current state;
   - optimistic update or simple file/SQLite lock.

2. **One operation kind: `megaplan_chain`**
   - launch an existing chain spec in a fresh worktree;
   - use normal canonical checkouts first unless bare-repo compatibility is proven against existing Megaplan helpers;
   - extract only the chain/worktree/tmux seams needed to make that path work.

3. **Resident Discord thin path**
   - Peter can `add a ticket`;
   - Peter can `run this chain`;
   - Peter can ask `what is running?`, `what is blocked?`, and `show logs`;
   - the bot replies with operation id when work starts.

4. **Guardian v0**
   - liveness tick plus deep tick;
   - detect dead/stale chain sessions;
   - restart/resume known-safe chain states;
   - cap retries;
   - classify `needs_peter`;
   - DM on failed recovery, blocker, and completion.

5. **Completion and cleanup**
   - Discord-launched operations always get an immediate completion DM;
   - the daily briefing may summarize completions later, but should not replace completion DMs;
   - expose `agentbox cleanup survey` or equivalent so Discord `cleanup/consolidate` is a real remote capability, not just a reference to a local skill.

Post-v0 operation kinds are Codex, Claude, shell, tests, and subagent repair. They should not block the first Discord-to-chain-to-Guardian loop.

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

5. **cleanup-loose-branches for post-run consolidation.** When operations complete, AgentBox should not invent a new "merge everything" policy. It should productize the cleanup-loose-branches algorithm as a remote-safe `agentbox cleanup survey` command/tool: survey, recommend land/delete/park, and get explicit approval for destructive steps.

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
   - tools: `ticket_new`, `chain_create`, `chain_launch`, `status`, `logs`, `guardian_check`, `resolve`, `help`, `creds_list`, `creds_test`;
   - natural-language messages routed by the agent to those tools.

   The resident runtime already persists conversations, coalesces message bursts, and loads hot context. AgentBox needs an Operator profile on top of that, plus pending-question metadata on resident conversation turns and intent routing on the coalesced message batch before tool dispatch.

3. **Megaplan chain operation kind**:
   - create worktree with existing helpers;
   - launch chain using existing chain/cloud mechanics;
   - record operation metadata;
   - use an extracted `megaplan_chain` adapter rather than calling cloud CLI glue directly from Guardian.

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

### Extraction Checklist Before Implementation

These are the high-value code-inspection tasks before writing the first AgentBox module:

1. **Resident runtime:** confirm the coalescing boundary and where to inject Operator intent classification, pending-question matching, and approval matching.
2. **Store:** decide whether operation registry lives in the existing store interface or a sibling `agentbox` store module, but keep it first-class and cross-kind.
3. **Worktrees:** parameterize current helpers for explicit repo path, root path, branch, and bare-vs-normal repo behavior.
4. **Cloud supervise:** split provider-independent chain classification from provider-specific SSH/Railway execution, or add a host-local execution provider for AgentBox.
5. **Tmux runner:** extract session-name, log-path, env, launch, restart, attach, and stop helpers that take operation id and worktree path.
6. **Watchdog:** add an operation-record source so Guardian can ask watchdog logic to inspect known operations instead of scanning arbitrary plan directories.
7. **Credentials:** extract `seed_codex_oauth()` into a shared credential seeding module with `SecretSpec` and health checks.
8. **Git/PR:** map operation id to branch, PR, CI, merge, and cleanup state in the registry before automation starts acting on branches.

## External Projects To Inspect Or Borrow From

The default is not to fork external systems into v0. AgentBox already has a local Megaplan substrate for Discord, tickets, chains, cloud supervision, watchdogs, credentials, and worktrees. External projects are useful mainly as focused audits before locking specific UX/state decisions.

### Build Vs Borrow Matrix

| Component | Decision | Source to use | Why |
|---|---|---|---|
| Discord bridge/runtime | Reuse local code | `resident/discord.py`, `resident/runtime.py`, `resident/auth.py` | Already handles Discord conversations, coalescing, allowlists, confirmations, tool calls. OpenACP is reference only. |
| Ticket creation | Reuse local code | `tickets/*`, `handlers/tickets.py`, store ticket APIs | Existing Megaplan ticket model is enough for v0. |
| Epic/chain execution | Reuse local code | `chain/spec.py`, chain CLI/state, `cloud/supervise.py` | Chains are the Megaplan execution backbone. Do not create a second epic runner. |
| Operation registry | Build | New AgentBox model using store patterns | Existing `cloud_runs`/watchdog records are too scoped. Need cross-kind operation state. |
| Worktree service | Extract locally first | `bakeoff/worktree.py`, CLI `--in-worktree` paths | Existing helpers are close. Inspect Rover/CCManager only for naming/lifecycle ideas. |
| Process runner | Extract locally first | cloud tmux wrappers, host-local execution provider, tmux conventions | Need operation-id session naming, logs, attach/stop/restart. External tools are references. |
| Guardian | Build thin loop, reuse plugins | `cloud/supervise.py`, `watchdog/*`, resident scheduler patterns | AgentBox-specific loop over registry; reuse chain/watchdog classifiers. |
| Credential sync | Extract locally first | `cloud/auth.py`, cloud template secret handling | `seed_codex_oauth()` proves selective seeding. Generalize into `SecretSpec`. |
| Cleanup/consolidation | Productize local skill | `cleanup-loose-branches` skill → `agentbox cleanup survey` | Must become a remote command/Operator tool with approval gates. |
| Subagent repair | Post-v0 adapter | `workers/hermes.py`, `subagent-launcher` conventions | Useful after core loop; v0 can diagnose/escalate without autonomous patch storms. |
| Remote workspace platform | Do not adopt in v0 | Coder, OpenHands, Open SWE, Netclode | Too broad/heavy for one-machine Discord-first workflow. Inspect only if future scope expands. |

External inspection tasks:

1. **CCManager / CC-Manager lifecycle audit:** inspect busy/waiting/idle/completed state transitions and worktree cleanup behavior before finalizing operation statuses.
2. **Rover session/worktree UX audit:** inspect worktree naming, session isolation, supported-agent wrapping, and cleanup conventions before hardening the worktree service.
3. **OpenACP Discord bridge audit:** inspect message streaming, chat-session routing, and permission UX; borrow ideas only, because Megaplan resident runtime remains the implementation base.
4. **Netclode/Coder/OpenHands/Open SWE architecture audit:** keep as future references for remote workspace, sandbox, and async-agent architecture. Do not use as v0 dependencies.

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
    canonical: /workspace/repos/megaplan
  - name: reigh-app
    url: git@github.com:org/reigh-app.git
    default_branch: main
    canonical: /workspace/repos/reigh-app
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

V0 mechanics:

```bash
git clone git@github.com:org/repo.git /workspace/repos/repo
git -C /workspace/repos/repo worktree add \
  /workspace/worktrees/op-123/repo \
  -b agent/op-123 \
  origin/main
```

Future bare-repo mechanics can replace this after compatibility is proven.

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

### 7. Operation Handlers

Purpose: normalize only the dispatch point for different operation kinds. Do not build a plugin framework in v0.

Initial adapter types:

- `megaplan-chain`
- `megaplan-plan`
- `codex`
- `claude`
- `subagent`
- `test`
- `shell`

Start with a flat handler table:

```python
OPERATION_HANDLERS = {
    "megaplan_chain": handle_megaplan_chain,
}
```

Each handler owns its own launch/classify/restart details and returns a status delta plus any pending approvals. Extract shared helpers only after a second operation kind proves what is actually common.

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

## Setup And Onboarding Runbooks

The plan needs two boring, repeatable paths: setting up a fresh machine and adding a new repo later. These should be usable from the laptop, with AgentBox doing the remote setup over SSH.

### Fresh Machine Setup

Command:

```bash
agentbox bootstrap --host root@<hetzner-ip> --name agentbox-main
```

Expected behavior:

1. Create or verify a non-root `agentbox` user.
2. Install baseline packages:
   - git;
   - tmux;
   - Python/uv;
   - Node/npm;
   - GitHub CLI;
   - ripgrep;
   - build-essential/toolchain packages;
   - Docker only if explicitly enabled.
3. Create the workspace layout:
   - `/workspace/repos`;
   - `/workspace/worktrees`;
   - `/workspace/runs`;
   - `/workspace/secrets`;
   - `/workspace/manager`.
4. Install or update Megaplan/AgentBox code.
5. Install Codex, Claude, and Hermes/subagent launch tooling.
6. Write `/workspace/manager/agentbox.yaml`.
7. Install systemd units:
   - `agentbox-guardian.service`;
   - `agentbox-discord.service`;
   - optional timer for backup/cleanup reports.
8. Configure SSH hardening and firewall basics.
9. Run a health check:
   - can SSH as `agentbox`;
   - can read/write `/workspace`;
   - can run `git`, `tmux`, `python`, `node`, `gh`;
   - can start and stop a test tmux operation;
   - can send a Discord test message if bot credentials are already present.

The bootstrap should be idempotent. Running it again should update packages/config/services without deleting repos, worktrees, runs, or credentials.

### SSH And Machine Access

There should be a standardized access path. After bootstrap, Peter should not need to remember raw IPs, root usernames, or one-off SSH flags.

Local host profile:

```yaml
hosts:
  agentbox-main:
    host: 1.2.3.4
    user: agentbox
    ssh_key: ~/.ssh/agentbox_main_ed25519
    workspace: /workspace
    tailscale_name: agentbox-main
```

Commands:

```bash
agentbox ssh agentbox-main
agentbox exec agentbox-main -- tmux ls
agentbox doctor agentbox-main
agentbox tunnel agentbox-main --remote 8080 --local 8080
```

Expected behavior:

1. `agentbox bootstrap` creates or verifies a dedicated SSH key for the machine.
2. The public key is installed for the non-root `agentbox` user.
3. Root SSH is used only for initial bootstrap and then disabled or avoided.
4. `~/.ssh/config` gets a stable alias, for example:

   ```sshconfig
   Host agentbox-main
     HostName 1.2.3.4
     User agentbox
     IdentityFile ~/.ssh/agentbox_main_ed25519
     IdentitiesOnly yes
     ServerAliveInterval 30
   ```

5. `agentbox ssh agentbox-main` shells into `/workspace` by default.
6. `agentbox exec` runs non-interactive remote commands with the same host profile and logs command metadata locally.
7. `agentbox doctor` verifies SSH, disk, systemd services, GitHub auth, Discord auth, and tool availability.
8. Optional Tailscale can provide a stable private hostname, but plain SSH over the Hetzner IP should work first.

Credential rule: SSH keys are access credentials, not runtime secrets. They live in the local SSH agent/keychain and are installed as public keys on the box. Agent runtime secrets still flow through `agentbox creds push/test`, not through ad hoc shell history or copied `.env` files.

### Break-Glass And Day-2 Operations

Discord is the primary UI, but the machine must remain operable when Discord, credentials, or the resident service is broken.

Commands:

```bash
agentbox status agentbox-main
agentbox services agentbox-main
agentbox logs agentbox-main --service guardian
agentbox restart agentbox-main --service discord
agentbox guardian pause agentbox-main
agentbox guardian resume agentbox-main
agentbox notify test agentbox-main
agentbox reconcile agentbox-main
agentbox version agentbox-main
agentbox upgrade agentbox-main
```

Expected behavior:

1. `status` works over SSH and does not require Discord.
2. `services` shows systemd state for Guardian, Discord resident, timers, and recent failures.
3. `logs` tails service logs and operation logs with redaction.
4. `guardian pause/resume` lets Peter stop autonomous repair while preserving read-only status.
5. `notify test` verifies Discord outbound delivery.
6. `reconcile` scans operation records, tmux sessions, worktrees, branches, and run directories, then reports mismatches.
7. `upgrade` updates code, runs migrations, reloads systemd units, and verifies rollback information.

Manual SSH intervention should be recorded. If Peter edits a worktree, kills tmux, fixes credentials, or rebases manually, `agentbox reconcile` should add an event annotation so Guardian does not misclassify the change as corruption.

### Operation State Machine

The registry needs a small explicit state machine.

Suggested states:

- `created`
- `preflight_failed`
- `launching`
- `running`
- `stale`
- `repairing`
- `awaiting_capacity`
- `needs_peter`
- `completed`
- `failed`
- `cancelled`
- `cleanup_pending`
- `archived`

Rules:

- terminal states are `completed`, `failed`, `cancelled`, and `archived`;
- every transition writes an event with actor, reason, prior state, next state, and idempotency key;
- Guardian owns transitions from `running/stale/repairing` into `needs_peter`, `completed`, or `failed`;
- Operator owns user-requested transitions such as stop, approve, cleanup, or relaunch;
- after restart, Guardian reconciles registry state with tmux/worktree/log reality before acting.

### Partial Launch Recovery

Every launch step should be idempotent and reconcilable.

Failure examples:

- worktree exists but operation record was not written;
- operation record exists but tmux session was never created;
- tmux session started but Discord reply failed;
- branch exists but worktree creation failed;
- event was written but registry update failed.

Recovery behavior:

1. `agentbox reconcile` detects the mismatch.
2. Guardian marks the operation `needs_peter` or retries only if the safe next step is obvious.
3. Orphaned worktrees/branches are never deleted automatically; they are routed through cleanup survey.

### Credential Push

Command:

```bash
agentbox creds push --host agentbox-main
agentbox creds test --host agentbox-main
```

Expected behavior:

1. Read an explicit local credential manifest.
2. Copy only named credentials, never the whole environment.
3. Write credentials under `/workspace/secrets` with strict permissions.
4. Install runtime copies where tools expect them, for example Codex/Claude/Hermes auth files.
5. Run health checks for GitHub, Discord, Codex, Claude, and provider API keys.
6. Report missing/stale credentials with the exact local command to fix them.

Credential audit requirements:

- list secrets by name/status only, never value;
- record source, destination, permissions, last pushed, last tested, and consumers;
- log every secret test/injection as an audit event;
- redact known secret patterns from logs and Discord output;
- explicitly forbid copying arbitrary `.env` files unless each key is named in the credential manifest.

### Add A New Repo

Command:

```bash
agentbox repo add reigh-app git@github.com:org/reigh-app.git --default-branch main
agentbox repo sync reigh-app
agentbox repo test reigh-app
```

Expected behavior:

1. Add the repo to `/workspace/manager/agentbox.yaml`.
2. Clone or update the canonical checkout under `/workspace/repos/reigh-app`.
3. Verify remote access with the configured GitHub SSH key/token.
4. Fetch default branch and tags.
5. Record repo metadata:
   - repo name;
   - remote URL;
   - default branch;
   - canonical path;
   - allowed operation kinds;
   - optional setup/test commands.
6. Create a disposable test worktree under `/workspace/worktrees/repo-test-<id>/reigh-app`.
7. Run configured repo health checks, such as dependency install smoke test or `git status`.
8. Remove the disposable test worktree.
9. Make the repo visible to Discord:
   - `/repos` lists it;
   - `run this chain in reigh-app ...` can resolve it;
   - Guardian includes it in dirty/stale branch summaries.

For v0, canonical repos can be normal checkouts. Bare repos are a target optimization after compatibility is proven.

Repo trust and mutation policy:

- only repos in the repo registry can be used by Discord-launched operations;
- default branch and protected branch names are explicit per repo;
- operations never push directly to protected branches;
- repo-specific setup/test commands must be declared before Guardian can run them automatically;
- submodules and Git LFS are detected during `repo test` and reported if unsupported;
- dirty canonical checkouts block new worktree creation until reconciled;
- multi-repo operations must record all repos up front and cannot silently add another repo mid-run.

### Remove Or Retire A Repo

Command:

```bash
agentbox repo retire reigh-app
```

Expected behavior:

1. Refuse if active operations reference the repo.
2. Summarize unmerged branches, worktrees, stashes, and PRs.
3. Route cleanup through `agentbox cleanup survey`.
4. Remove the repo from the active registry only after Peter approves the cleanup/park decision.

### Backup And Restore

Backups should make host migration boring.

Back up:

- `/workspace/manager` store/config;
- repo registry;
- operation records and event logs;
- run manifests and summaries;
- credential manifest metadata, but not necessarily secret values unless explicitly enabled;
- systemd unit templates and AgentBox version.

Do not rely only on full-machine snapshots. A restore should work onto a fresh box from bootstrap plus backup artifacts plus credential re-push.

Restore runbook:

```bash
agentbox bootstrap --host root@<new-ip> --name agentbox-main
agentbox restore agentbox-main --backup <backup-id>
agentbox creds push --host agentbox-main
agentbox doctor agentbox-main
agentbox reconcile agentbox-main
```

Acceptance criteria:

- `doctor` passes;
- repos sync;
- prior completed operations remain inspectable;
- active operations are either resumed safely or marked `needs_peter`;
- no secret values are printed during restore;
- Discord receives a restore summary.

## Implementation Phases

### Phase 1: Box Bootstrap And Thin Discord Shell

Deliverables:

- Hetzner VM provisioned;
- `/workspace` layout created;
- core tools installed;
- SSH access working;
- one repo cloned as a normal canonical checkout;
- Codex/Claude/GitHub/Discord credentials manually verified;
- resident Discord service running with allowlist;
- `status/help` Discord command path connected to a stub AgentBox tool profile.

### Phase 2: V0 Registry, Chain Runner, And Worktree Path

Deliverables:

- thin operation registry;
- append-only events and raw logs;
- `megaplan_chain` operation record;
- normal-checkout worktree creation for one repo;
- tmux launch with operation-id session naming;
- `agentbox status/logs/attach` CLI for debugging;
- Discord `run this chain` creates an operation and returns operation id.

Do not require bare repo support in this phase. Add bare repos only after a focused compatibility audit proves existing helpers are safe with them.

### Phase 3: Guardian V0

Deliverables:

- systemd Guardian service;
- 30-60 second liveness tick;
- 5-15 minute deep tick;
- dead/stale/completed classification for `megaplan_chain`;
- safe restart/resume path;
- retry cap;
- `needs_peter` status;
- immediate Discord completion/blocker/failure DMs.

V0 Guardian should not require autonomous code-patching repair subagents. It can launch diagnostics if cheap and bounded, but the core acceptance is restart/resume/classify/notify.

### Phase 4: Ticket, Logs, And Completion UX

Deliverables:

- Discord `add a ticket`;
- Discord `what is running?`, `what is blocked?`, `show logs`;
- completion DM format with summary, validation, branch, and next action;
- pending approval matching through resident confirmation/conversation metadata;
- `cleanup/consolidate` command stub that can at least report completed-but-unconsolidated operations.

### Phase 5: Credential Sync And Preflight

Deliverables:

- explicit credential manifest;
- local-to-remote push;
- remote secret env files;
- `creds list/test/push guide`;
- pre-launch credential gate for `megaplan_chain`;
- GitHub auth check before push/PR actions;
- Codex and Claude credential support using existing Megaplan Cloud patterns.

### Phase 6: Cleanup And GitHub Consolidation

Deliverables:

- `agentbox cleanup survey` remote command backed by cleanup-loose-branches discipline;
- branch/PR/CI state linked back to operation registry;
- draft PR creation/update policy for completed chains;
- merge/delete/reset approval gates;
- cleanup after merge.

### Phase 7: Additional Operation Kinds

Deliverables:

- Codex operation adapter;
- Claude operation adapter;
- shell/test operation adapter;
- subagent diagnostic/repair child operation adapter;
- concurrency budgets enforced across main and child operations.

### Phase 8: Hardening And Optional Bare Repos

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
   - Recommendation: use normal checkouts in v0; revisit bare repos after the worktree helper compatibility audit.

2. Should state be SQLite or files?
   - Files are easier to inspect and align with Megaplan.
   - SQLite is better for concurrent Guardian/Discord/process updates.
   - Recommendation: start with SQLite plus per-operation manifest files.

3. Should secrets be encrypted at rest on the box?
   - Strictly, Linux permissions are enough for a single-user prototype.
   - For durable use, use `age`, `pass`, or 1Password CLI.
   - Recommendation: start with permissioned files, design the interface so encrypted storage can replace the backend.

4. Should AgentBox be a separate package or live inside Megaplan?
   - It reuses Megaplan heavily but is broader than Megaplan.
   - Recommendation: start inside this repo while extracting internal seams. If it stabilizes as generic infrastructure, split later.

5. Should Docker be used for operations?
   - Worktrees alone are enough for the initial model.
   - Docker can help for tests or untrusted code later.
   - Recommendation: do not require Docker per operation in v1.

## Summary

The most important finding is that Megaplan already has real worktree machinery. The AgentBox plan should not rebuild that. It should promote the current command-scoped worktree behavior into a machine-scoped operation system.

Build the missing layers:

- repo registry;
- operation registry;
- tmux process runner;
- credential sync;
- Guardian daemon;
- Discord Operator tools;
- cleanup and backup.

Reuse aggressively from:

- Megaplan `bakeoff.worktree`;
- Megaplan `init/chain --in-worktree`;
- Megaplan resident Discord/runtime;
- Megaplan cloud supervisor;
- Rover/CCManager/OpenACP as external references.

The result is a persistent AgentBox: one machine, many repos, many isolated worktrees, many concurrent agents, one Guardian, one Discord Operator, and a shared operation registry underneath both.
