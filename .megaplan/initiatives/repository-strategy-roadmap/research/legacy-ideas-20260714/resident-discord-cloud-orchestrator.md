# Resident Discord Cloud Orchestrator for Megaplan

Build a resident Discord-facing orchestration layer into this megaplan repo, using the proven architectural patterns from `/Users/peteromalley/Documents/Veas` while keeping megaplan as the planning/execution engine.

## Goal

Create a single Discord bot surface that can:

- Talk with the user to shape epics.
- Persist epic/conversation/orchestration state durably.
- Use megaplan editorial APIs to create, read, and update epics, bodies, checklists, and sprints.
- Trigger sprint/plan execution on megaplan cloud runners.
- Check in on cloud runs periodically.
- Resume, inspect, or report on cloud work based on conversation and scheduled monitoring.
- Ask the user when human input is needed, such as gate approval, failed runs, blocked runs, or ambiguous epic-shaping questions.

The result should feel like a resident operator: the user can talk naturally in Discord, the bot maintains state, starts cloud work, checks on it, and reports back without requiring the user to keep a local terminal open.

## Settled Decisions

- **SD-001** — Megaplan remains the planning and execution engine; the new layer is a resident chat/orchestration shell. _load_bearing: true_
  Rationale: Megaplan already owns plan lifecycle, editorial APIs, cloud provider commands, control messages, and progress events. The resident layer should coordinate those capabilities, not duplicate or replace them.

- **SD-002** — Take architectural patterns from Veas, not Veas' mediation domain logic. _load_bearing: true_
  Rationale: Veas has useful resident-service patterns: Discord ingestion, burst coalescing, bot turn/tool-call audit, DB-backed scheduled jobs, stale-claim recovery, health/admin surfaces, and phase separation. Its relationship-mediation prompts, partner model, OOB rules, and domain tables should not be imported.

- **SD-003** — DB is the orchestration truth for conversations, bot turns, tool calls, scheduled checks, control messages, and progress events. _load_bearing: true_
  Rationale: Long-running chat/cloud orchestration must survive process restarts and support audit/recovery. Scheduled monitoring and cloud-trigger commands should be durable rows, not in-memory state.

- **SD-004** — Plan execution can initially remain filesystem/cloud-volume based; do not force full DB-native plan execution in this feature. _load_bearing: true_
  Rationale: Current `PlanRepository`, workers, artifacts, and cloud runners expect real plan directories under `.megaplan/plans`. Moving all plan artifacts into DB is a larger migration and should not block the resident orchestrator.

- **SD-005** — Mirror or summarize cloud progress back into DB through existing progress/control concepts where practical. _load_bearing: true_
  Rationale: The Discord agent needs a durable, queryable view of remote state. Cloud plan artifacts may remain remote, but status/progress, run metadata, and important outcomes should be reflected in DB tables or store-backed events.

- **SD-006** — Expose cloud operations as constrained tools, not as arbitrary shell by default. _load_bearing: true_
  Rationale: The bot should have tools such as `cloud_status`, `cloud_start_chain`, `cloud_bootstrap`, `cloud_resume`, `cloud_logs`, and `schedule_cloud_check`. Arbitrary remote command execution should be gated or omitted from the first version.

- **SD-007** — Scheduled cloud check-ins should be deterministic infrastructure. _load_bearing: true_
  Rationale: The agent can decide to schedule a check, but a worker should claim due jobs and run status checks. The LLM should not be responsible for remembering timers.

- **SD-008** — Preserve a clean boundary between shared resident runtime, megaplan bot profile/tools, and megaplan engine. _load_bearing: true_
  Rationale: The eventual shared base should know about transports, scheduling, turns, tool calls, recovery, and outbound delivery, but not epics, mediation, sprints, partners, gates, or cloud providers.

## Reference Code To Inspect

From Veas:

- `/Users/peteromalley/Documents/Veas/app/main.py`
- `/Users/peteromalley/Documents/Veas/app/services/scheduled_jobs.py`
- `/Users/peteromalley/Documents/Veas/app/services/scheduled_job_handlers.py`
- `/Users/peteromalley/Documents/Veas/app/bots/mediator.py`
- `/Users/peteromalley/Documents/Veas/tool_schemas.py`, especially scheduled-task schemas
- `/Users/peteromalley/Documents/Veas/resident_chat_runtime/*`, especially Discord/coalescing/runtime pieces

From megaplan:

- `megaplan/agent/gateway/platforms/discord.py`
- `megaplan/agent/gateway/run.py`
- `megaplan/control.py`
- `megaplan/progress.py`
- `megaplan/editorial/*`
- `megaplan/store/*`
- `megaplan/cloud/cli.py`
- `megaplan/cloud/providers/*`
- `megaplan/cloud/templates/entrypoint.sh.tmpl`
- `megaplan/cloud/wrappers/mp-supervise`
- `megaplan/cloud/wrappers/mp-heartbeat`
- `docs/cloud.md`

## Desired Architecture

Add a resident megaplan runtime inside this repo, likely under a new package such as `megaplan/resident/` or `megaplan/agent/resident_megaplan/`, with a small reusable runtime boundary and a megaplan-specific bot profile.

Conceptual layers:

1. Resident runtime:
   - Discord transport and/or adapter reuse.
   - Message persistence.
   - Burst coalescing.
   - Bot turn and tool-call audit.
   - Outbound delivery.
   - Scheduled jobs.
   - Startup recovery for stale claimed jobs.
   - Health/admin surfaces if compatible with existing repo style.

2. Megaplan bot profile:
   - System prompt/instructions for epic shaping and cloud orchestration.
   - Tool registry for safe megaplan operations.
   - Conversation behavior: ask clarifying questions in shaping mode; use tools to persist decisions; trigger cloud only when an executable sprint/plan exists or the user asks.

3. Megaplan tools:
   - Epic tools:
     - `create_epic`
     - `select_epic`
     - `read_epic`
     - `edit_epic_body`
     - `add_checklist_items`
     - `update_checklist_item`
     - `create_or_update_sprints`
     - `queue_sprints`
     - `transition_epic_state`
   - Cloud tools:
     - `cloud_status`
     - `cloud_status_chain`
     - `cloud_start_chain`
     - `cloud_bootstrap`
     - `cloud_resume`
     - `cloud_logs`
     - `schedule_cloud_check`
     - `cancel_cloud_check`
     - `list_cloud_checks`
   - Gate/control tools:
     - `approve_gate`
     - `reject_gate`
     - `run_sprint_on_cloud`

## Runtime Flow

Epic shaping flow:

1. User messages Discord.
2. Resident runtime coalesces bursts.
3. Megaplan bot profile loads hot context: active epic, recent messages, open questions, checklist, sprints, cloud watches.
4. Agent asks clarifying questions when the user intent is ambiguous.
5. Agent writes stable decisions into epic body/checklist/sprints through editorial/store APIs.
6. When the epic reaches planned/queued sprint readiness, the bot can offer or accept commands to run a sprint.

Cloud run flow:

1. User asks to run a sprint, plan, or chain.
2. Bot validates an executable target from DB/store state.
3. Bot writes a durable control/run record and starts cloud work through provider-backed cloud APIs or the existing cloud CLI behavior.
4. Bot schedules a cloud check job if the work is long-running.
5. Scheduler claims due check jobs, calls cloud status/log tools, updates DB, and decides whether to stay silent, notify, resume, or ask the user.
6. On blocked/failed/gate-needed/completed states, Discord receives a concise status message with actionable options.

## What Should Not Happen

- Do not copy Veas mediation prompts, partner tables, OOB checks, or relationship-specific logic.
- Do not require plans to execute fully from DB in the first implementation.
- Do not make the Discord agent depend on an in-memory timer for check-ins.
- Do not expose unrestricted remote shell execution as the main cloud interface.
- Do not break existing `megaplan cloud` CLI workflows.
- Do not break existing local file-backed plan workflows.

## Implementation Expectations

This is a cross-cutting feature. The plan should be careful and staged:

1. Identify the minimal resident runtime pieces to build or reuse from existing `megaplan/agent/gateway`.
2. Define any new DB/store models needed for scheduled jobs, resident bot turns, cloud run records, and cloud watch jobs.
3. Add a scheduler with stale-claim recovery similar to Veas.
4. Add a megaplan tool registry/profile that calls existing editorial, control, progress, and cloud provider code.
5. Add tests for store/model behavior, scheduler claiming/recovery, tool wrappers, and cloud status/check decisions.
6. Keep the initial cloud execution artifact path filesystem-based, but persist run metadata and progress summaries.

## Success Criteria

- A Discord resident runtime can accept a user message and dispatch it through a megaplan-specific bot profile without importing Veas domain code.
- The bot profile has a defined and tested tool surface for epic shaping and cloud orchestration.
- A DB/store-backed scheduled job worker can claim due cloud check jobs safely, including stale-claim recovery.
- Cloud checks can inspect current cloud status/chain status and classify at least: running, blocked, failed, gate-needed, completed, and unknown.
- A cloud run/check record is durable and recoverable after process restart.
- Existing `megaplan cloud` commands and existing local plan workflows continue to pass focused regression tests.
- The plan explicitly preserves the filesystem/cloud-volume plan execution model for the first version while leaving room for later DB-native artifacts.
