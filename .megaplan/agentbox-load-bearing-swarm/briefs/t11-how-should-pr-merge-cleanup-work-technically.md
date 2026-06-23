You are an independent DeepSeek validation subagent for the AgentBox design.

Perspective: Technical
Question: How should PR/merge cleanup work technically?

Do not assume the predicted answer. You are not being shown it. Use the AgentBox plan below as context and answer the question from first principles. If local repo mechanics are relevant, infer from the plan's cited existing components. Your job is to decide what the answer SHOULD be for this design.

Return under 700 words with:
- Direct answer
- Rationale
- Existing mechanics this depends on, if any
- Risks or caveats
- One concrete design implication

--- AGENTBOX PLAN CONTEXT ---
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

This operation registry is the center of the system. The Guardian is scheduled/autonomous; the Discord Operator is user-triggered/interactive.

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
   - reports only meaningful state changes to Discord.

5. **Completion flow**:
   - DM Peter when an operation completes;
   - include summary, validation, branch/PR status, and next action;
   - use cleanup-loose-branches for consolidation after a batch of work.

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
manifest: /workspace/runs/op-20260623-foo/manifest.yaml
```

Build:

- file or SQLite-backed registry;
- operation creation;
- status updates;
- mapping from tmux session to operation;
- log/event path tracking;
- PR/branch/CI metadata.

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

### 9. Discord Operator

Purpose: primary human interface for the machine, and an on-demand agent that can operate on AgentBox state/tools when the user sends a Discord message.

Build commands:

- `status`
- `repos`
- `run <repo> <task>`
- `run chain <repo> <spec>`
- `logs <operation>`
- `attach <operation>` or instructions for SSH/tmux attach
- `approve <confirmation>`
- `stop <operation>`
- `restart <operation>`
- `cleanup <operation>`
- `creds test`
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

