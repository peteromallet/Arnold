# AgentBox Resident Boundary

This note records the package ownership boundary for the Discord thin path.
The goal is to keep the resident chat flow usable by Discord and future
Operator surfaces without moving product-specific behavior into Arnold's neutral
runtime contracts.

## Arnold-Facing Neutral Seams

Arnold-facing neutral seams are protocol and contract surfaces that can be used
without knowing about Discord, AgentBox, or Megaplan product behavior.

- `arnold_pipelines.megaplan.resident.runtime` owns the reusable resident loop:
  inbound event persistence, authorization calls, burst coalescing, agent
  dispatch, outbound delivery, and system/progress emission through protocols.
- `InboundEvent`, `OutboundMessage`, `OutboundSink`, and `EmitProtocol` are the
  neutral handoff shapes. They carry durable identity and IO boundaries, not
  Operator command policy or model-supplied actor authority.
- `arnold_pipelines.megaplan.resident.config.ResidentConfig` is the environment
  and timeout/configuration seam for resident runtimes. Transport-specific
  startup can read it, but command semantics stay outside this layer.

## Megaplan-Owned Resident Runtime Details

Megaplan owns the resident implementation details that require Megaplan store,
schema, plan, cloud, and control semantics.

- `ResidentRuntime` persists resident conversations, messages, turns, tool calls,
  and progress/system events through the Megaplan `Store`.
- `MegaplanResidentProfile` owns the Megaplan system prompt, hot-context loading,
  resident tool registry, confirmations, cloud control, export, editorial, and
  search behavior.
- Discord-specific delivery and inbound mapping live under
  `arnold_pipelines.megaplan.resident.discord`; they adapt Discord events to the
  neutral runtime seam instead of defining AgentBox or Arnold contracts.

## AgentBox-Owned Operator/Profile/Helper Integration

AgentBox owns the Operator-facing integration layer: commands, profiles, helpers,
and host/run-dir operation views that turn resident intent into AgentBox actions.

- Operator commands should call AgentBox-owned helpers for operation launch,
  status, logs, profile selection, and bounded context loading.
- AgentBox profiles decide which Operator shell and helper affordances are
  available. Megaplan resident profiles may expose thin tool wrappers, but should
  not duplicate AgentBox command policy.
- Shared status/log formatting for AgentBox operations belongs in AgentBox or an
  AgentBox-owned adapter helper. Discord tools should delegate to that view so
  CLI and Discord report the same operation state.

In short: Arnold sees neutral resident protocols, Megaplan owns the resident
runtime and Megaplan-specific tools, and AgentBox owns Operator/profile/helper
integration around operations.

## Resident-Delegated Agent Lifecycle

Discord conversation turns remain on the single Arnold path:
`ResidentDiscordService` adapts the message, `ResidentRuntime` persists and
authorizes the turn, and the configured resident runner executes it. There is no
second Discord bot loop for special requests.

The resident `launch_subagent` tool defaults to a detached Codex agent managed
by `arnold_pipelines.megaplan.resident`. Each launch creates this durable set:

- `.megaplan/plans/resident-subagents/<run-id>/manifest.json`
- `.megaplan/plans/resident-subagents/<run-id>/prompt.md`
- `.megaplan/plans/resident-subagents/<run-id>/run.log`
- `.megaplan/plans/resident-subagents/<run-id>/result.md`

The manifest schema is `arnold-resident-agent-run-v1`, with
`run_kind: resident_delegated_agent` and
`custodian: arnold.megaplan.resident`. Those identity fields distinguish this
surface from workflow-internal subagents. The supervisor seals stdin, starts
Codex with `danger-full-access`, streams the complete output to `run.log`,
captures the last response in `result.md`, and finalizes the manifest as
`completed`, `failed`, or `interrupted`. An explicitly selected Hermes backend
is retained only for legacy synchronous compatibility and must not be described
as a managed resident-agent run.

Discord-origin launches additionally commit immutable routing custody before
the worker starts. `launch_provenance`, top-level `correlation_id` / `custody_id`
/ `source_record_id`, the compatibility `discord_origin` projection, and
`completion_delivery.reply_target` must all identify the same resident message,
conversation, Discord message, channel/DM, and thread. The envelope is passed
through the normal tool runner, the Codex CLI compatibility process, managed
children, cloud chain sessions, plan/chain state, and repair records. It is an
allow-listed routing projection only; message content, authors, credentials,
HTTP bodies, and arbitrary model metadata are not retained.
Cloud session markers retain the same projection; watchdog-started ordinary
repair and meta-repair wrappers validate and re-export it before launching any
superfixer/model child. A malformed marker therefore blocks repair delegation
instead of creating an uncorrelated run.

Reaching a delegated terminal state does not deliver `result.md` as proof. The
continuous resident sweep first claims `resident_completion_turn` in the same
managed-run manifest and invokes the configured resident runner as a normal
managed turn. That turn is recorded in the canonical turn/message store, reads
the original task plus manifest/log/result evidence, checks actual project
state proportionately, and classifies the outcome as `success`, `partial`,
`failed`, `unknown`, or `blocked`. Only its redacted user-facing summary is
materialized into the completion outbox. Runner failure produces an honest
`unknown` summary; it never promotes the delegated final prose to verified
truth. The stable trigger id, claim lease, resident turn id, summary digest, and
bounded retry state prevent duplicate verifier turns across ordinary sweeps and
restart recovery.

`completion_delivery` is the durable terminal outbox. Its `outbox_id`,
`idempotency_key`, stable Discord nonce, attempt identity, bounded state history,
and provider message IDs are the delivery evidence. Operator-visible custody is:

- `pending`: committed or claimed for a provider attempt;
- `delivered`: Discord message IDs were persisted;
- `retry_pending`: a retryable failure has a scheduled backoff;
- `failed`: malformed/deleted/forbidden custody or an exhausted retry budget;
- `unknown`: a legacy or provider outcome cannot safely be reconciled;
- `not_applicable`: the launch was explicitly non-Discord.

A restart that finds an in-flight claim first appends `unknown` evidence, then
reuses the same nonce for the recovery attempt. HTTP 404/401/403 and malformed
targets fail permanently; timeouts, network failures, rate limits, and server
errors retry with bounded exponential backoff. Never re-target from a
conversation cursor, the latest message, or agent final text. Ambiguous burst
provenance fails the delegation before process launch. Launch retries with the
same provenance/delegation/task key return the existing manifest; an intentional
retry must name `retry_of_run_id`.

Startup delivery sweeps additively backfill legacy manifests only when an exact
inbound resident record resolves the Discord snowflake. Malformed Discord hints
become `failed`; missing legacy Discord custody becomes `unknown`; manifests
with no Discord hint become explicit `not_applicable`. No migration guesses a
reply target.

Resident hot context exposes these runs under `resident_agents`. `running`
contains only manifests whose supervisor PID still matches that exact manifest;
`recent` is a bounded newest-first list of terminal or observed-interrupted
runs. Every row includes absolute `manifest_path`, `full_log_path`,
`result_path`, and `project_dir` fields. Scheduled VP special requests pass the
to-do item id as `request_id`, leave the item pending while its managed agent is
running, and reconcile the durable result on a later sweep.

For operator diagnosis, inspect `resident_agents` first, then open the row's
manifest and full log. A persisted `running` state reported as observed
`interrupted` means the recorded supervisor no longer matches a live process;
it is not evidence that a workflow-internal subagent is active.
For delivery incidents, inspect `completion_delivery.status`, `state_history`,
`error_history`, `last_error_category`, `last_http_status`, and persisted
Discord message IDs. `resident_agents.delivery_status_counts` and
`delivery_attention_count` provide the bounded operational roll-up.
