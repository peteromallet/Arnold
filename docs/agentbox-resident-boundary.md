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

## Resident-managed scheduling boundary

`arnold_pipelines.megaplan.resident.schedules` owns durable timing and admission.
It stores append-only definition revisions, immutable occurrence identities, and
hash-linked transition receipts in the resident store. The resident scheduler
materializes due time/event occurrences and uses fenced claims; it does not
start an ad-hoc process or send a result itself.

An admitted `resident_managed_agent` target enters `launch_subagent_task` with
its pinned schedule revision, occurrence key, prompt/grant digests, source
envelope, work intent, model/profile/toolset selection, dependencies, and exact
route. The normal managed manifest/queue/execution/synthesis/completion-outbox
lifecycle remains authoritative. A delivery retry or unknown provider outcome
never causes the schedule task to execute again.

Version 1 deliberately supports one file-store writer guarded by an OS lock.
Database multi-worker scheduling is rejected until transactional occurrence
insert, admission reservation, and fenced claims have parity. Legacy
`ScheduledJob` handlers continue in parallel; no VP/cloud recurrence migrates
without an explicit single-owner cutover.

## Resident-Delegated Agent Lifecycle

Discord conversation turns remain on the single Arnold path:
`ResidentDiscordService` adapts the message, `ResidentRuntime` persists and
authorizes the turn, and the configured resident runner executes it. There is no
second Discord bot loop for special requests.

The resident `launch_subagent` tool defaults to provider-aware routing and a
detached agent managed by `arnold_pipelines.megaplan.resident`. Each launch
creates this durable set:

- `.megaplan/plans/resident-subagents/<run-id>/manifest.json`
- `.megaplan/plans/resident-subagents/<run-id>/prompt.md`
- `.megaplan/plans/resident-subagents/<run-id>/run.log`
- `.megaplan/plans/resident-subagents/<run-id>/result.md`

The manifest schema is `arnold-managed-agent-run-v2`, with
`run_kind: resident_delegated_agent` and
`custodian: arnold.megaplan.managed_agent`. Those identity fields distinguish this
surface from workflow-internal subagents. The supervisor selects Hermes,
Codex, or Claude from the model spec, records the resolved provider route,
starts that provider with the configured agent permissions, captures
diagnostics in `run.log` and the final response in `result.md`, and finalizes
the manifest as `completed`, `failed`, or `interrupted`. Explicit compatible
backend overrides remain supported; conflicting backend/model pairs fail before
a manifest is created. Claude uses its provider-managed automatic permission
mode under root because its CLI correctly rejects unsafe permission bypass in
that environment. An explicitly selected, non-background Hermes launch is
retained only for legacy synchronous compatibility.

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
provenance fails the delegation before process launch. Launch retries converge
only when provenance, task digest, canonical description, relationship,
aggregation role, and synthesis group all match; an intentional retry must name
`retry_of_run_id`.

### Semantic request descriptions and synthesis groups

Every resident-managed launch supplies one purpose-built semantic `description`.
The normalized, redacted value is persisted with `request_summary_line` and is
reused in the delegated prompt, resident-agent hot context, launch
acknowledgement, completion verification, and terminal delivery header. Raw
inbound content remains in its immutable message record and digest; legacy
manifests without a description may use only the explicitly labeled
`immutable_inbound_source_fallback` path.

Immutable Discord reply ancestry establishes a follow-up directly. The
resident may also submit a high-confidence semantic judgment naming an exact
earlier inbound `source_record_id`; the runtime revalidates conversation,
author, ordering, and existing ancestry before persisting that inference.
Nearby messages or lexical similarity alone never establish a relationship.

Request relationships do not control delivery cardinality by themselves.
Independent launches have independent delivery identities. A multi-agent batch
must instead declare one explicit `synthesis_group`: contributors use
`internal_contributor`, exactly one later run uses
`synthesis_delivery_owner`, and that owner receives the contributors' manifest
and result paths. `internal_contributor` is only an aggregation role. Each
launch also records an `execution_contract.outcome_contract` and independent
delivery policy. Analytical fragments may remain suppressed. A repair, deploy,
integration, activation, proof, or other independently meaningful execution
result remains independently deliverable unless the launch records an explicit
`delivery_suppression_override_reason`. A delivered group cannot acquire a
second owner, while a newer follow-up has a new current request/delivery target
even when it shares a relationship root.

New manifests and resident projections expose three authoritative dimensions:
`lifecycle.work.status` (including `worker_completed`),
`lifecycle.delivery.status`, and `lifecycle.request.status` (including the
separate `request_delivered` boolean). Worker completion never validates whole
request delivery. A contributor can issue a truthful bounded terminal update
while its synthesis owner remains open for a later combined conclusion.

### Resident-managed follow-up and continuation

Use the isolated resident seam to add work to an existing managed agent session:

```bash
python -P -m arnold_pipelines.megaplan.resident.subagent follow-up \
  --run-id subagent-YYYYMMDD-HHMMSS-XXXXXXXX \
  --message "The bounded follow-up message" \
  --idempotency-key stable-caller-retry-key
```

`--message-file` is available instead of `--message`. The command requires the
immutable `ARNOLD_RESIDENT_DELEGATION_CONTEXT` inherited by the calling resident
process; there is deliberately no CLI flag for constructing `discord_origin` or
overriding custody. The caller may be a later Discord message, but its validated
conversation/channel/DM ownership must match the target session. Missing,
malformed, cross-conversation, or ambiguous provenance fails closed.

Every accepted message is written under the lineage root's `followups/`
directory as an immutable message file plus an
`arnold-resident-agent-followup-v1` evidence record. A child managed-run
manifest is committed with `parent_run_id`, `lineage_root_run_id`,
`followup_id`, `parent_manifest_path`, and the caller's inherited launch
provenance. Repeating the same idempotency key with the same message and custody
returns that child; reusing it with different content or custody is rejected.

An active Codex CLI session is never resumed concurrently. Its continuation
supervisor waits on the exact parent manifest and matching supervisor process,
then resumes the uniquely recovered persistent session after the parent becomes
terminal. A terminal parent is resumed immediately. Multiple follow-ups form a
single locked parent/child chain, so there is one writer to the model session at
a time; branched lineages or session IDs claimed by unrelated lineages are
rejected as ambiguous.

Acceptance is not completion. The follow-up evidence state
`continuation_started` proves the resident committed the message and started its
continuation supervisor. The child manifest's
`session_dispatch.status: accepted` with evidence
`codex_resume_process_started` proves the resume process accepted the message.
Only the child run's ordinary terminal manifest/result and completion-delivery
records may be used to claim model completion or Discord delivery.

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
`delivery_attention_count` provide the bounded operational roll-up. Queue
dependency state is projected from current predecessor manifests, never from
embedded predecessor snapshots. `resident_agents.attention` and
`context_root.attention.agent_delivery` surface deterministic actions for
completed suppressed execution results, hidden all-success outcomes, unrelated
execution fan-in, failed predecessors that mask success, and abnormally waiting
delivery owners. Legacy manifests remain readable and receive an explicitly
labeled compatibility projection.
