# SuperPOM Resident Engine: Arnold + Pumpernickel All-In Plan

**Status:** Proposed implementation plan

**Repositories:** `/Users/peteromalley/Documents/Arnold` and `/Users/peteromalley/Documents/Pumpernickel`

**Target:** Replace only SuperPOM's turn engine; every other Pumpernickel bot continues unchanged
**Estimated delivery:** 8–14 engineering days plus 2–5 calendar days in shadow/canary observation

## 1. Executive decision

Use Arnold as the reusable agent-execution library. Do not duplicate its structured model/tool loop or subagent execution machinery in Pumpernickel, and do not embed Arnold's complete Megaplan resident application inside Pumpernickel.

The boundary is:

- Arnold owns provider-neutral structured agent execution, scoped tool contracts, tool-call auditing primitives, bounded subagent dispatch, and test fakes.
- Pumpernickel owns the Discord application and the SuperPOM product: identity, inbound lifecycle, turn claims, prompt, Compass phases, concrete tools, persistence, scheduling, recovery, outbound delivery, and rollout policy.

Pumpernickel remains the single owner of:

- Discord identities and gateways;
- inbound authorization, persistence, deduplication, and recovery;
- per-bot coalescing and pacing;
- users, topics, bindings, and privacy scope;
- the SuperPOM prompt and Compass domain;
- SuperPOM's provider configuration and concrete tool handlers;
- outbound delivery;
- scheduled jobs;
- turn, tool, spend, and reliability telemetry.

Add one per-bot `TurnEngineRegistry`. It selects `SuperPomResidentEngine` only for `bot_id="superpom"` and selects a thin `LegacyAgenticEngine` adapter for every other bot.

```text
Discord / scheduler / recovery / catch-up
                    |
                    v
      Existing Pumpernickel host machinery
                    |
                    v
              TurnEngineRegistry
              /                \
             /                  \
     bot_id=superpom          all other bots
           |                      |
           v                      v
 SuperPomResidentEngine     LegacyAgenticEngine
           |                      |
           | imports              | unchanged
           v                      v
 arnold.agent.tool_runtime    current _run_agentic()
           |
           v
 Pumpernickel prompt, tool adapters, outbound,
 persistence, scheduling, recovery, and telemetry
```

Pumpernickel imports Arnold as a pinned dependency. It does not launch Arnold's Discord app, use Arnold's Megaplan store, or import `arnold_pipelines.megaplan.resident.runtime`. Do not add a second Discord listener, inbound queue, coalescer, scheduler, database, or outbound sink.

## 2. Goals

The implementation must deliver all of the following:

1. Every eligible SuperPOM message wakes or joins a durable agent turn.
2. Rapid adjacent messages may continue to coalesce into one coherent turn.
3. SuperPOM retains its existing Discord identity and bot binding.
4. SuperPOM retains its current prompt, Compass, privacy scope, tools, provider chain, and pacing behavior.
5. SuperPOM executes a durable `read -> consult -> respond -> record -> schedule -> done` turn.
6. SuperPOM can dispatch bounded, audited subagents during allowed phases.
7. Subagents return findings to the parent turn and cannot send Discord messages or perform durable writes by default.
8. Scheduled, recovery, catch-up, and manually triggered SuperPOM work resolves through the same engine selector.
9. All non-SuperPOM bots continue through the current `_run_agentic()` implementation without semantic changes.
10. Operators can select `legacy`, `shadow`, `canary`, or `resident` mode for SuperPOM and roll back immediately.
11. Pumpernickel imports the generic runner/tool/subagent machinery from `arnold.agent.tool_runtime` rather than maintaining a fork.
12. Arnold's existing deployed resident remains behaviorally compatible throughout the extraction.

## 3. Non-goals

This project does not:

- migrate the other Pumpernickel bots to a new engine;
- redesign Discord transport or create a new Discord application;
- move SuperPOM to another repository or service;
- change the ownership of Compass, memories, observations, distillations, or boundaries;
- replace Pumpernickel's database or scheduler;
- introduce direct database access for subagents;
- make a repository-level Codex agent the default conversational runner;
- change the existing SuperPOM persona as part of the engine extraction;
- remove the legacy engine during the initial stabilization window;
- move Pumpernickel's `TurnEngineRegistry`, Compass phase machine, database services, or Discord lifecycle into Arnold;
- make Arnold depend on Pumpernickel;
- expose Megaplan store, cloud, escalation, redaction, CLI, or scheduler types through the new public API;
- extract the low-level `resident_chat_runtime` transport package as part of this work.

`resident_chat_runtime` and `arnold.agent.tool_runtime` solve different problems. The former is low-level Discord/coalescing transport; the latter is reusable model/tool/subagent execution. Pumpernickel may continue its current transport arrangement while this plan is implemented.

## 4. Current Pumpernickel foundations

The necessary platform behavior already exists:

- `app/bots/base.py` defines `BotSpec`, prompt rendering, phase instructions, read/write scopes, tool allowlists, provider order, and version metadata.
- `app/bots/superpom.py` defines SuperPOM's phase instructions and tool exclusions.
- `app/bots/prompts/profiles/superpom.py` defines its action-catalyst role, voice, clinical deferrals, Compass terminology, and knowledge categories.
- `app/services/agentic.py` implements the current durable phased model/tool loop.
- `app/services/tools/registry.py` exposes structured tools and enforces bot/phase restrictions.
- `app/services/tools/consult_perspective.py` already demonstrates a bounded, read-only nested consult with inherited scope and no send/write authority.
- `app/services/hot_context_solo.py` builds SuperPOM-specific context.
- `app/services/inbound.py` persists inbound messages and resolves bot/user/topic scope.
- `app/services/discord.py` owns one Discord client and gateway per bot identity.
- `app/main.py` constructs per-bot coalescers and pacers.
- `app/services/scheduled_job_handlers.py` creates agent turns from scheduled work.
- `app/services/recovery.py` requeues incomplete work by bot identity.
- messages, bot turns, scheduled jobs, and inbound idempotency already carry `bot_id`.

The work is therefore a small Arnold library extraction plus a Pumpernickel engine seam and SuperPOM adapter—not a second resident host.

## 5. Target ownership and dependency boundary

```text
arnold.agent.tool_runtime             Pumpernickel
-------------------------------       ---------------------------------
structured agent runner               TurnEngineRegistry
chat-completion client protocol       SuperPOM phase coordinator
generic tool registry/contracts  <--- concrete Pumpernickel tool adapters
tool-call limits and audit records     BotSpec/prompt/Compass
subagent request/policy/dispatcher <--- scope and capability policy
fake runner/client/dispatcher          Discord/DB/scheduler/recovery
                                       outbound idempotency and rollout
```

The dependency direction is one-way:

```text
Pumpernickel -> arnold.agent.tool_runtime
Arnold Megaplan resident -> arnold.agent.tool_runtime
arnold.agent.tool_runtime -X-> Pumpernickel
arnold.agent.tool_runtime -X-> arnold_pipelines.megaplan
```

The public package must be import-light and application-neutral. Importing `arnold.agent.tool_runtime` must not initialize Arnold's CLI, global Hermes tool registry, Discord stack, cloud runtime, Megaplan configuration, or database services.

## 6. Arnold public API to add

Add an API under the already-installable Arnold distribution:

```text
arnold/agent/tool_runtime/
  __init__.py
  contracts.py
  registry.py
  runner.py
  backends.py
  subagents.py
```

### 6.1 Contracts

The public types should include:

- `ToolLoopRequest` and `ToolLoopResult`;
- `ToolContext` carrying opaque, application-supplied metadata;
- `ToolInput`, `ToolResult`, and `ToolCallRecord`;
- `ToolSpec` and `ToolRegistry`;
- `ModelStep`, `ToolCall`, and the `ToolCallingBackend` protocol;
- `StructuredToolRunner` with iteration, tool-call, timeout, and output limits;
- `SubagentRequest`, `SubagentResult`, `SubagentPolicy`, and `SubagentDispatcher` protocol.

These types must not mention `ResidentConfig`, `ModelTier`, `StepInvocation`, Megaplan subjects, cloud operations, Pumpernickel users/topics, or a concrete provider SDK.

### 6.2 Generic tool registry

Move the reusable semantics of Arnold's current resident `ToolRegistration` and `ToolRegistry` into `arnold.agent.tool_runtime.registry`:

- Pydantic input/output models;
- `handler(ToolContext, ToolInput)` async contract, with an adapter for Arnold's existing one-argument handlers;
- JSON-schema export for the model;
- duplicate-name rejection;
- input and output validation;
- timeout/error normalization;
- per-call audit records;
- explicit context passing safe under concurrent turns.

Do not carry the Megaplan-specific `ToolOperationKind` literal into the public API. Use an application-defined string plus neutral safety metadata such as `read_only`/`side_effecting`, or make operation classification opaque to the runner. Pumpernickel remains the authority for phase, bot, user, topic, privacy, and read-before-write checks.

### 6.3 Structured runner

Extract the generic core of `arnold_pipelines/megaplan/resident/agent_loop.py::OpenAICompatibleAgentRunner` into `arnold.agent.tool_runtime.runner`:

- repeated assistant/tool rounds;
- forced structured tool availability where configured;
- Pydantic validation;
- bounded iterations and total tool calls;
- model-call and tool-call timeouts;
- tool result serialization;
- final text extraction;
- deterministic audit capture;
- cancellation propagation;
- injected client, clock, audit sink, and optional budget hook.

The runner must use an injected `ToolCallingBackend`. It must not import `ResidentConfig`, the Megaplan model seam, or `StepInvocation`. An `OpenAICompatibleBackend` may live in `backends.py`; provider fallback and product-specific model selection remain adapter/configuration concerns. A `before_dispatch` hook preserves Arnold's budget enforcement without importing Megaplan into the public package.

Do not use the current Codex CLI resident runner for SuperPOM. It describes tools in a prompt but does not make Pumpernickel's structured handlers the exclusive callable capability surface.

### 6.4 Bounded subagent dispatch

Provide two bounded paths behind the same public contracts:

- `StructuredSubagentDispatcher` uses the same structured runner with a restricted registry, removes delegation from child tools, and enforces maximum depth;
- `ArnoldAgentSubagentDispatcher` is an async wrapper around an injected existing `arnold.agent.AgentDispatcher` for one-shot Hermes/Codex children.

Both run behind explicit policy:

- async facade over Arnold's dispatcher;
- read-only default;
- explicit model, adapter, capability, and project-root allowlists;
- max depth, children, concurrency, timeout, and budget limits;
- cancellation and structured terminal results;
- injected lifecycle/audit hooks;
- no direct Discord or application database capability.

Do not promote the current Megaplan resident launcher unchanged. It hard-codes the `subagent-launcher` script path, accepts `ResidentConfig`, and defaults to broad `file,web,terminal` access. The Arnold-agent dispatcher should call the stable `arnold.agent.dispatch` seam (or accept its dispatcher protocol), not a Megaplan-relative subprocess script. The existing restricted nested-agent implementation in `agentbox/resident_profile.py` is the stronger precedent for structured child isolation.

### 6.5 Existing Arnold resident compatibility

Convert the current Megaplan resident modules into compatibility adapters:

- `resident/agent_loop.py` supplies Megaplan config, model budgeting, and CLI-specific runners around `arnold.agent.tool_runtime`;
- `resident/tool_registry.py` and neutral schemas re-export or adapt the public registry/types while preserving existing imports;
- Megaplan-specific operation kinds remain local;
- `resident/subagent.py` preserves current behavior through a compatibility adapter until intentionally migrated;
- `agentbox/resident_profile.py` replaces dynamic resident-symbol imports with the public contracts and proves the restricted structured-subagent path;
- `resident/runtime.py`, store, profile, Discord, escalation, scheduler, and cloud behavior do not move.

This is an internal refactor with a new public surface, not a behavior rewrite of the live resident.

### 6.6 Packaging and consumer contract

The Arnold wheel already includes the `arnold` package, so this does not require a second repository or a sibling-path import. Publish the new surface as a minor Arnold version and have Pumpernickel initially pin the exact reviewed Git commit/lock entry. Move to a compatible range such as `>=0.24,<0.25` only after a tagged release and consumer contract tests.

The intended Pumpernickel imports are narrow:

```python
from arnold.agent.tool_runtime import (
    ArnoldAgentSubagentDispatcher,
    StructuredSubagentDispatcher,
    StructuredToolRunner,
    SubagentPolicy,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)
```

Installing the complete Arnold distribution may add deployment weight. Measure image size, dependency resolution, import time, and startup time during the adapter proof. Do not fork the code to avoid that cost. If it is material, publish this unchanged API from the Arnold repository as a smaller `arnold-agent-runtime` distribution in a follow-up; Pumpernickel's imports and adapters should not need to change.

## 7. Target Pumpernickel module boundary

Add a local engine package:

```text
app/services/turn_engines/
  __init__.py
  base.py
  registry.py
  legacy.py
  superpom_resident.py
  services.py
  arnold_adapters.py
  shadow.py
```

Responsibilities:

- `base.py`: Pumpernickel-specific `TurnRequest`, `TurnResult`, `TurnEngine`, and host-service protocols.
- `registry.py`: bot-ID engine registration, default selection, engine-mode selection, and stable canary routing.
- `legacy.py`: a minimal adapter over the existing `_run_agentic()` behavior.
- `superpom_resident.py`: the durable SuperPOM phase machine.
- `services.py`: scoped adapters for hot context, tools, outbound, scheduling, and audit.
- `arnold_adapters.py`: adapts Pumpernickel providers, tool registry, scope, and audit to `arnold.agent.tool_runtime`; configures Arnold's bounded dispatcher using `consult_perspective` safety.
- `shadow.py`: read-only service wrappers and comparison capture.

Keep the application `TurnEngine` contract local: it describes Pumpernickel turn lifecycle and should not be forced into Arnold. Import the lower-level structured runner, generic tool contracts, audit primitives, and subagent contracts from `arnold.agent.tool_runtime`. Do not recreate those in Pumpernickel.

## 8. Pumpernickel engine contracts

The exact types may evolve, but they need these semantics:

```python
@dataclass(frozen=True)
class TurnRequest:
    turn_id: UUID
    bot_id: str
    user: User
    topic_id: UUID
    trigger_kind: Literal[
        "inbound", "scheduled", "recovery", "catch_up", "manual"
    ]
    triggering_message_ids: tuple[UUID, ...]
    trigger_metadata: Mapping[str, Any]
    idempotency_key: str


@dataclass(frozen=True)
class TurnResult:
    status: Literal["completed", "withheld", "failed", "retryable"]
    final_phase: str
    outbound_message_ids: tuple[UUID, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TurnEngine(Protocol):
    engine_id: str
    engine_version: str

    async def handle_turn(
        self,
        request: TurnRequest,
        services: TurnServices,
    ) -> TurnResult: ...
```

`TurnServices` exposes only scoped application behavior and Arnold adapters:

- hot-context loading;
- an Arnold `StructuredToolRunner` configured with a Pumpernickel `ToolCallingBackend`;
- a scoped Arnold tool registry backed by Pumpernickel's tool executor;
- an Arnold `SubagentDispatcher` configured by Pumpernickel policy;
- outbound sending;
- scheduling;
- turn and phase audit;
- time and configuration.

The engine must not own the database pool, Discord client, scheduler loop, recovery loop, or application lifespan.

## 9. Engine registry and dispatch

Use one registry rather than adding `if bot_id == "superpom"` throughout the application:

```python
registry = TurnEngineRegistry(default=LegacyAgenticEngine(...))
registry.register("superpom", SuperPomResidentEngine(...))
```

Preserve the public functions in `app/services/agentic.py`, but have them construct a `TurnRequest` and resolve the engine. The legacy adapter calls the existing `_run_agentic()` implementation.

Dispatch must cover every entry point, not only Discord burst completion:

- paced inbound turns from `app/main.py`;
- unpaced burst completion from `app/main.py`;
- `run_agentic_turn()`;
- `run_agentic_turn_with_metadata()`;
- `run_agentic_job()`;
- `run_agentic_turn_with_pool()`;
- `run_agentic_job_with_pool()`;
- scheduled check-ins, watch items, deferred turns, OOB reviews, and scheduled tasks;
- startup and periodic recovery;
- reconnect catch-up;
- admin/manual and evaluation entry points.

Required selection rules:

- every known non-SuperPOM bot resolves to the legacy adapter;
- an unknown bot resolves to legacy or fails according to current behavior, never silently to SuperPOM;
- only SuperPOM consults `SUPERPOM_TURN_ENGINE`;
- the selected engine ID/version is recorded when the turn opens;
- retries use the engine/version stored on the original turn unless an explicit compatibility rule says otherwise.

## 10. Every-message behavior

"Every message triggers an agent turn" means every eligible, nonduplicate Discord message is persisted and guaranteed to be claimed by a turn. It does not require a separate model call for every chat bubble.

Recommended behavior:

1. Discord receives an eligible non-bot message.
2. Existing whitelist and binding rules authorize it.
3. The message is persisted with `bot_id="superpom"` and transport-message idempotency.
4. It enters SuperPOM's existing per-bot coalescer.
5. Rapid adjacent messages form one ordered burst.
6. One parent turn atomically claims all messages in that burst.
7. The engine selector chooses the configured SuperPOM engine.
8. The turn reaches one deterministic terminal state.

Invariants:

- no eligible message remains permanently unclaimed;
- one inbound message cannot belong to two active turns;
- duplicates do not create a second turn or outbound response;
- a crash before outbound may safely retry;
- a crash after outbound cannot resend the response;
- incomplete post-send recording/scheduling resumes without another user-facing response;
- catch-up work bypasses live typing/reaction delays;
- messages arriving while a turn is running form subsequent ordered work rather than racing the active response.

Literal one-message/one-model-turn behavior may be added as a SuperPOM-only coalescer setting, but it is not the recommended default because it raises cost and makes crossed replies more likely while a user is still typing.

## 11. SuperPOM resident phase machine

```text
read -> consult? -> respond -> record -> schedule -> done
          |            |          |
          |            |          +-- resumable post-send work
          |            +-- outbound idempotency boundary
          +-- optional bounded subagents
```

The parent engine owns phase progression. The model cannot widen the phase toolset or skip mandatory invariants.

### 11.1 Read

- Load the user's Compass/orientation items first every turn.
- Then load only the memories, observations, distillations, boundaries, recent messages, and cross-topic signals needed for this request.
- Preserve current user/topic visibility and partner-sharing rules.
- Expose only read tools.
- Do not send user-facing output or perform durable writes.
- Treat empty and sufficient read results as terminal for that query; do not repeat reads indefinitely.

### 11.2 Consult

- Skip by default.
- Use when an independent perspective materially improves a difficult response.
- Allow bounded subagent dispatch and read-only structured domain tools.
- Do not send or write.
- Return findings to the parent phase context.
- A failed or timed-out consult degrades gracefully; it does not automatically fail the parent turn.

### 11.3 Respond

- Produce the user-facing response, reaction, multipart reply, or intentional silence.
- Preserve SuperPOM's sharp, direct, nonjudgmental voice.
- Mirror only enough to connect the situation to the user's stated Compass, then move toward the smallest useful next step.
- Use existing Pumpernickel outbound services and pacing.
- Establish the durable outbound idempotency boundary.
- Do not perform durable domain writes.

### 11.4 Record

- Persist only information useful in future turns.
- Preserve the existing distinctions among Compass headings, memories, observations, distillations, and boundaries.
- Preserve read-before-write requirements.
- Update or reinforce existing state instead of creating duplicates.
- Directly stated Compass material uses the current user-stated source semantics.
- Inferred material follows the current proposal/review policy.
- A failure after outbound is post-send incomplete work; it must never cause response replay.

### 11.5 Schedule

- Create or update follow-ups only when clearly useful.
- Read existing check-ins/tasks when duplication is plausible.
- Use Pumpernickel's scheduler and idempotency.
- Do not send additional response text from this phase.

### 11.6 Done

- Close the turn with its final engine, phase, tool, subagent, outbound, latency, spend, and warning metadata.
- Release claims according to current Pumpernickel transaction semantics.

## 12. Tool enforcement

Use Arnold's structured runner to conduct model/tool rounds, with a Pumpernickel adapter supplying the permitted tools for each phase:

```text
allowed_tools = BotSpec.tool_allowlist
              INTERSECT phase_allowed_tools
              INTERSECT bot/user/topic scope
              INTERSECT runtime safety policy
```

Arnold owns the generic loop, schema round-trip, limits, timeout, and normalized audit event. The existing Pumpernickel tool executor remains authoritative for:

- schema validation;
- phase permission;
- read/write classification;
- bot/user/topic scope;
- authorization;
- auditing;
- redaction;
- result normalization.

The engine must not call tool handlers or database operations directly to bypass a rejection. Repository-level shell/filesystem access is not part of the default SuperPOM conversational capability.

## 13. Subagent delegation

Expose Arnold's bounded `SubagentDispatcher` to SuperPOM as a structured `delegate_task` capability. Configure it through a Pumpernickel adapter that extends the existing `consult_perspective` safety model. Do not begin with broad `file,web,terminal` defaults.

Allow delegation only during `read` and `consult` and only when the SuperPOM profile/config enables it.

### 13.1 Required policy

- maximum delegation depth: 1;
- maximum children per parent turn;
- maximum concurrent children per user and process;
- model/provider allowlist;
- timeout and retry policy;
- token, tool-call, and cost ceilings;
- inherited `bot_id`, `user_id`, `topic_id`, and privacy scope;
- read-only structured domain capabilities by default;
- no Discord send, edit, delete, reaction, or typing capability;
- no durable-write or scheduling capability by default;
- no raw database pool, service-role credential, environment-secret, or unrestricted filesystem access;
- cancellation or terminal abandonment when the parent ends, where supported;
- sanitized structured result returned to the parent;
- failure returned as a result rather than thrown through the entire parent turn.

### 13.2 Audit requirements

Record:

- invocation ID and parent turn ID;
- bot/user/topic scope;
- sanitized task digest and protected full task according to existing privacy policy;
- model and provider;
- granted capabilities;
- start/end timestamps and terminal status;
- tool-call count;
- redacted result or error;
- token/cost metadata;
- whether a replay reused an existing completed invocation.

If the current audit schema cannot represent this cleanly, add a dedicated `subagent_invocations` table in the next available migration.

## 14. Persistence and migrations

Pumpernickel already has bot-scoped inbound idempotency and records bot/topic identity across its main turn surfaces. Keep that model.

Add only the provenance and shadow/delegation storage that operations genuinely require.

### 14.1 Parent-turn provenance

Ensure `bot_turns` records, either in queryable existing metadata or additive columns:

- `engine_id`;
- `engine_version`;
- `engine_mode` (`legacy`, `shadow`, `canary`, `resident`);
- current and terminal phase;
- trigger kind;
- prompt version;
- bot-spec version;
- hot-context builder version;
- tool-schema version;
- outbound delivery state;
- warnings/failure classification.

### 14.2 Shadow runs

Prefer a dedicated protected `engine_shadow_runs` table keyed to the authoritative legacy turn. Store:

- proposed resident response;
- proposed phase/tool/subagent plan;
- latency and cost;
- errors and policy violations;
- comparison scores;
- optional reviewer verdict;
- retention/deletion timestamps.

Shadow runs must never claim messages, send, react, schedule, or perform durable writes.

### 14.3 Subagent invocations

If added, `subagent_invocations` must have:

- foreign key to the parent turn;
- bot/user/topic scope;
- lifecycle status;
- engine/model/provider/capability metadata;
- protected request/result fields;
- duration, token, tool, and cost fields;
- indexes for parent turn, `(bot_id, created_at)`, and status;
- the same RLS, encryption, redaction, retention, and service-role posture as comparable internal turn artifacts.

### 14.4 Migration requirements

- use the next available migration number;
- make initial changes additive;
- provide static migration tests;
- provide a live migration test against a disposable database;
- update insert/select code and operational queries together;
- document rollback or forward-fix behavior;
- do not delete or rewrite existing turns.

## 15. Scheduler and recovery

Pumpernickel remains the only scheduler and recovery authority.

Scheduled jobs must carry `bot_id`, `topic_id`, user scope, trigger kind, and an idempotency key. When a job becomes an agent turn, it resolves the same engine registry as inbound messages.

Recovery rules:

- a pre-send failure can retry under the existing policy;
- delivered outbound suppresses future duplicate sends;
- post-send `record` or `schedule` work resumes from its durable checkpoint;
- timed-out subagents become terminal invocation records;
- parent turns may continue without failed optional subagents;
- recovery resolves the stored engine/version for in-flight turns;
- changing the feature flag to legacy affects new turns and does not reinterpret an existing resident turn;
- catch-up and recovery retain existing no-live-pacing behavior.

## 16. Configuration

Add explicit settings with safe defaults:

```text
SUPERPOM_TURN_ENGINE=legacy|shadow|canary|resident
SUPERPOM_RESIDENT_CANARY_USER_IDS=
SUPERPOM_RESIDENT_CANARY_PERCENT=0
SUPERPOM_SUBAGENTS_ENABLED=false
SUPERPOM_SUBAGENT_MODELS=
SUPERPOM_SUBAGENT_MAX_PER_TURN=2
SUPERPOM_SUBAGENT_MAX_CONCURRENCY=2
SUPERPOM_SUBAGENT_TIMEOUT_S=60
SUPERPOM_SUBAGENT_MAX_TOOL_CALLS=4
SUPERPOM_SUBAGENT_DAILY_COST_CAP_USD=
```

Mode semantics:

- **legacy:** current engine only.
- **shadow:** legacy remains authoritative; resident receives read-only services and produces comparison data only.
- **canary:** stable selected users use resident; all others use legacy.
- **resident:** resident engine is authoritative for SuperPOM.

Canary selection must be stable by user/binding, never rerolled randomly per turn. Subagents have an independent kill switch.

## 17. Observability and controls

Every relevant log line should include redacted/canonical forms of:

- `turn_id`;
- `bot_id`;
- `engine_id` and version;
- engine mode;
- trigger kind;
- user/topic scope;
- current phase.

Add metrics for:

- turns started, completed, failed, and retried by engine/mode;
- messages waiting unclaimed;
- inbound-to-start latency;
- time by phase;
- time to first outbound;
- post-send completion latency;
- tools called and rejected;
- subagents dispatched, completed, timed out, cancelled, and failed;
- provider fallback rate;
- tokens/cost by parent and child;
- duplicate-send prevention;
- shadow divergence and policy violations.

Operator controls must support:

- showing the current SuperPOM engine mode;
- disabling subagents independently;
- switching new SuperPOM turns to legacy;
- inspecting stuck phases and child invocations;
- draining/recovering in-flight work;
- confirming that every non-SuperPOM bot is still legacy.

## 18. Implementation workstreams

### Workstream 0: decisions and baseline (0.5–1 day)

1. Record the current test baseline and deployed SuperPOM behavior.
2. Capture representative golden conversations and tool traces.
3. Capture scheduled, catch-up, provider-failure, and recovery fixtures.
4. Lock burst semantics, initial subagent policy, cost limits, shadow retention, and promotion thresholds.

**Exit:** baseline fixtures and decisions are durable and reviewable.

### Workstream 1: Arnold public tool runtime (3–5 days)

1. Add `arnold.agent.tool_runtime` contracts, registry, runner, backends, and subagent dispatchers.
2. Invert provider, configuration, model resolution, budget, clock, and audit dependencies.
3. Add an OpenAI-compatible backend and deterministic fakes.
4. Adapt the Megaplan resident's structured runner and registry behind compatibility wrappers.
5. Adapt `agentbox/resident_profile.py` to the public registry/runner and restricted child dispatcher.
6. Keep the Codex CLI runner and Megaplan VP launcher local for now.
7. Add isolation, behavior, compatibility, wheel-install, and public-import tests.
8. Version and document the supported API.

**Exit:** Arnold's current resident and AgentBox tests remain green, the clean wheel imports the public API, and no public runtime module imports Megaplan/application code.

### Workstream 2: pin Arnold and prove the Pumpernickel adapter (0.5–1 day)

1. Pin Pumpernickel to the reviewed Arnold commit in its lock/dependency configuration.
2. Add a contract smoke test importing every public symbol used by Pumpernickel.
3. Implement the Pumpernickel `ToolCallingBackend` and tool-registry adapters.
4. Prove one fake SuperPOM read-only tool round without Discord, scheduling, or writes.
5. Measure dependency/install/startup impact; record a follow-up to split `arnold-agent-runtime` only if the full Arnold distribution is operationally unacceptable.

**Exit:** Pumpernickel consumes Arnold through a pinned public API and executes a scoped fake turn without copied loop code.

### Workstream 3: engine registry with legacy default (1–2 days)

1. Add local contracts and `TurnEngineRegistry`.
2. Wrap current `_run_agentic()` in `LegacyAgenticEngine` without rewriting it.
3. Route every conversational, scheduled, recovery, catch-up, manual, and evaluation entry point through the registry.
4. Record engine provenance.
5. Keep every bot, including SuperPOM, on legacy.

**Exit:** the complete Pumpernickel suite passes with no behavioral change.

### Workstream 4: SuperPOM resident engine (3–4 days)

1. Adapt the existing SuperPOM `BotSpec`, prompt, hot context, scopes, provider chain, and tool executor.
2. Implement the durable phase machine.
3. Preserve Compass-first reads and phase-specific tool authority.
4. Establish the outbound idempotency boundary.
5. Checkpoint and resume post-send phases.
6. Support inbound, scheduled, recovery, catch-up, and manual triggers.
7. Add deterministic fake-model tests for every transition.

**Exit:** isolated SuperPOM resident tests pass with no authority violations.

### Workstream 5: bounded subagents (1–2 days)

1. Configure Arnold's public dispatcher using the safe policy demonstrated by `consult_perspective`.
2. Add a Pumpernickel `delegate_task` adapter to SuperPOM read/consult phases only.
3. Enforce scope, capability, depth, count, timeout, concurrency, model, tool, token, and cost limits.
4. Persist invocation lifecycle.
5. Test success, rejection, timeout, cancellation, replay, and graceful failure.

**Exit:** delegation is useful, bounded, and auditable.

### Workstream 6: shadow and comparison (1–2 days)

1. Add engine-mode configuration.
2. Add hard read-only/no-outbound/no-schedule shadow services.
3. Capture comparison artifacts.
4. Add comparison metrics and review queries.
5. Run sampled shadow traffic, then 100% SuperPOM shadow.

**Exit:** shadow has zero side effects and produces actionable comparisons.

### Workstream 7: canary, cutover, and operations (1–2 days plus soak)

1. Add stable user-based canary selection.
2. Canary inbound SuperPOM turns.
3. Exercise crash/restart, provider failure, child timeout, and rollback in the deployed environment.
4. Canary scheduled SuperPOM jobs after inbound stability.
5. Promote SuperPOM to resident mode.
6. Retain legacy rollback through at least one stable release window.

**Exit:** SuperPOM is resident by default, rollback is proven, other bots remain legacy.

## 19. Test plan

### 19.1 Arnold public runtime

- public package imports without loading `arnold_pipelines`, Discord, store, scheduler, or global Hermes tools;
- registry registration, duplicate rejection, filtering, and unknown-tool behavior;
- Pydantic input/output validation and malformed model arguments;
- sync-adapted and async handlers;
- explicit tool-context isolation across concurrent turns;
- repeated/multiple tool calls, total cap, model timeout, tool timeout, and cancellation;
- normalized errors, final response, usage, and audit metadata;
- OpenAI-compatible message/tool translation against a fake client;
- structured children receive a restricted registry with delegation removed;
- Arnold-agent children enforce read-only metadata, allowlists, depth, timeout, and failure-as-result;
- existing Megaplan resident and AgentBox suites pass unchanged through compatibility adapters;
- built wheel installs in a clean environment and imports the documented API.

### 19.2 Registry and regressions

- SuperPOM resolves according to its feature mode.
- Every other known bot resolves to legacy.
- Unknown-bot behavior matches the current application contract.
- Paced and unpaced paths both dispatch correctly.
- Scheduled, deferred, recovery, catch-up, manual, pool-specific, and evaluation entry points dispatch correctly.
- All non-SuperPOM prompt, tool, outbound, scheduler, and recovery tests remain unchanged and green.

### 19.3 SuperPOM behavior

- Compass is the first domain read every turn.
- Read/consult phases cannot write or send.
- Respond cannot perform durable domain writes.
- Record/schedule cannot emit another conversational response.
- Response precedes record/schedule.
- user-stated and inferred orientation follow current source/review rules.
- Compass, memory, observation, distillation, and boundary data remain distinct.
- cross-user/topic access is rejected.
- schedule creation checks plausible duplicates.
- reactions, multipart replies, and intentional silence complete correctly.
- clinical/safety scenarios preserve the existing SuperPOM contract.
- provider fallback and circuit-breaker behavior remain bounded.

### 19.4 Message and recovery

- one message is durably claimed by one parent turn;
- rapid messages form one ordered burst;
- duplicate Discord events do not duplicate turns or replies;
- messages arriving during an active turn become ordered subsequent work;
- crash before outbound retries safely;
- crash after outbound does not resend;
- post-send record/schedule resumes correctly;
- catch-up does not use live pacing;
- feature rollback does not corrupt in-flight resident work.

### 19.5 Subagents

- allowed read-only delegation succeeds;
- wrong-phase delegation is rejected;
- outbound, write, schedule, secret, raw DB, and cross-scope access are absent;
- recursive delegation is rejected;
- child count, concurrency, timeout, token/tool, model, and cost caps are enforced;
- timeout/failure returns a structured result and parent continues;
- completed replay-safe invocation is reused;
- request/result protection and audit persistence are verified.

### 19.6 Shadow and canary

- shadow cannot claim, send, react, write, or schedule;
- legacy remains authoritative in shadow;
- canary selection is stable;
- comparison artifacts link to the authoritative legacy turn;
- emergency flags affect new turns without corrupting in-flight work;
- telemetry distinguishes engine and mode.

### 19.7 Existing suites to emphasize

Run the full Pumpernickel suite, with particular attention to existing tests covering:

- SuperPOM prompt and registration;
- SuperPOM pacing;
- hot-context and Compass behavior;
- tool allowlists and scope negatives;
- agentic lifecycle and recovery;
- inbound idempotency and queue hardening;
- scheduled jobs and per-bot scheduler dispatch;
- Discord gateway, outbound, pacing, and reconnect catch-up;
- provider fallback;
- Sisypy/agentic scenario structure.

## 20. Rollout gates

### Gate A: transparent registry

- registry covers every turn/job entry point;
- all bots are legacy;
- full suite and baseline comparisons pass;
- engine provenance is operationally visible.

### Gate B: SuperPOM shadow

- zero shadow side effects;
- zero scope violations;
- no unclaimed-message growth;
- acceptable response/tool-plan divergence;
- latency and cost within agreed budgets.

### Gate C: inbound canary

- no duplicate outbound;
- restart/recovery exercises pass;
- subagent failures degrade gracefully;
- accepted SuperPOM scenarios are at least equivalent to legacy;
- all other bot metrics remain at baseline.

### Gate D: scheduled canary

- scheduled SuperPOM turns resolve resident only when intended;
- job idempotency and recovery pass;
- no duplicate check-ins or follow-ups.

### Gate E: resident default

- SuperPOM resident mode is authoritative;
- rollback has been executed successfully;
- legacy remains available for the stabilization window;
- runbooks, dashboards, and operational ownership are complete.

## 21. Rollback

Primary rollback:

```text
SUPERPOM_TURN_ENGINE=legacy
SUPERPOM_SUBAGENTS_ENABLED=false
```

Requirements:

- engine selection occurs when a new turn is created;
- existing turns retain stored engine/version and finish or recover deterministically;
- new database changes are additive;
- no migration destroys or rewrites existing turns;
- subagents can be disabled without disabling the parent resident engine;
- deployment documentation states whether settings require process restart;
- a live rollback drill is required before resident-default promotion.

## 22. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| Public API accidentally imports Megaplan internals | Pumpernickel becomes coupled to Arnold deployment code | Zero-leak import test and dependency-injected provider/budget/config hooks |
| Extraction changes the live Arnold resident | Production regression | Compatibility wrappers, unchanged external constructors, full resident/AgentBox regression suite |
| Arnold and Pumpernickel drift across commits | Runtime breakage during deploy | Exact commit pin, consumer contract test, semver only after a tagged stable API |
| Full Arnold dependency is too heavy | Larger Pumpernickel image/startup surface | Import-light module now; split the same API into `arnold-agent-runtime` later only if measured impact warrants it |
| SuperPOM is reduced to a prompt swap | Compass and staged behavior disappear | Preserve phase machine, context, tools, and scope as first-class behavior |
| Dispatcher added only to Discord path | Scheduled/recovery turns remain inconsistent | Route all public turn and job entry points through one registry |
| Legacy adapter subtly rewrites behavior | Other bots regress | Thin adapter, legacy default, golden/full-suite comparison before SuperPOM registration |
| Both engines have authority in shadow | Duplicate messages or state | Hard read-only/no-outbound/no-schedule shadow services |
| Post-send retry replays response | Duplicate Discord reply | Durable outbound boundary and resumable post-send phases |
| Subagent leaks private data | Cross-user/topic disclosure | Inherited scope, structured read-only tools, no raw DB/Discord/secrets |
| Recursive or expensive delegation | Latency and spend runaway | Depth/count/concurrency/time/token/tool/model/cost caps |
| Engine upgrade strands recovery | Stuck turns | Store engine/version per turn and define compatibility policy |
| Literal per-message turns cross replies | Poor conversational UX | Preserve burst coalescing by default |
| Repository agent bypasses tools | Unenforced capability boundary | Use Arnold's structured runner with Pumpernickel handlers, not ambient shell access |
| Big-bang cutover hides drift | User-visible regressions | Legacy -> shadow -> inbound canary -> scheduled canary -> resident |

## 23. Estimate

For one engineer familiar with both repositories:

| Work | Estimate |
|---|---:|
| Baseline and decisions | 0.5–1 day |
| Arnold public runtime, adapters, compatibility, and release | 3–5 days |
| Pumpernickel Arnold dependency and adapter proof | 0.5–1 day |
| Engine registry and legacy adapter | 1–2 days |
| SuperPOM resident engine | 3–4 days |
| Bounded subagents | 1–2 days |
| Shadow/comparison | 1–2 days |
| Canary, operations, and cutover | 1–2 days |
| **Expected total with overlap** | **8–14 working days** |

Allow 2–5 additional calendar days for shadow/canary observation. The Arnold portion is approximately 3–5 days; a brittle move-only extraction could be faster, but is explicitly not the target. Parallel work can begin on Pumpernickel's legacy registry and baseline while the Arnold API stabilizes.

## 24. Expected file map

Likely Arnold touch points:

- `arnold/agent/tool_runtime/__init__.py` — new public exports
- `arnold/agent/tool_runtime/contracts.py` — new
- `arnold/agent/tool_runtime/registry.py` — new
- `arnold/agent/tool_runtime/runner.py` — new
- `arnold/agent/tool_runtime/backends.py` — new
- `arnold/agent/tool_runtime/subagents.py` — new
- `arnold_pipelines/megaplan/resident/agent_loop.py` — compatibility adapter; CLI runner stays local
- `arnold_pipelines/megaplan/resident/tool_registry.py` — compatibility adapter/re-exports
- `arnold_pipelines/megaplan/resident/tool_schemas.py` — neutral re-exports plus local Megaplan operation kinds
- `agentbox/resident_profile.py` — consume public runtime and restricted child dispatcher
- `arnold/agent/__init__.py` and API documentation — link/document the subpackage without conflicting broad aliases
- `pyproject.toml` and changelog/release notes — minor version bump and supported API statement
- new tests under `tests/arnold/agent/tool_runtime/`
- existing tests under `tests/resident/` and `tests/agentbox/`
- a clean built-wheel import smoke test

Likely Pumpernickel touch points:

- `app/services/turn_engines/__init__.py` — new
- `app/services/turn_engines/base.py` — new
- `app/services/turn_engines/registry.py` — new
- `app/services/turn_engines/legacy.py` — new
- `app/services/turn_engines/superpom_resident.py` — new
- `app/services/turn_engines/services.py` — new
- `app/services/turn_engines/arnold_adapters.py` — new
- `app/services/turn_engines/shadow.py` — new
- `app/services/agentic.py`
- `app/services/tools/consult_perspective.py`
- `app/services/tools/registry.py`
- `app/services/inbound.py`
- `app/services/scheduled_job_handlers.py`
- `app/services/recovery.py`
- `app/services/turn_audit.py`
- `app/services/hot_context_solo.py`
- `app/main.py`
- `app/config.py`
- `pyproject.toml` and lockfile — exact Arnold commit/version pin
- the next available additive migration, if engine/shadow/subagent data requires it
- existing and new tests under `tests/`
- deployment/runbook documentation and environment examples

Prompt/persona files should change only if tests reveal that orchestration instructions cannot be cleanly injected without doing so:

- `app/bots/base.py`
- `app/bots/superpom.py`
- `app/bots/prompts/profiles/superpom.py`

## 25. Decisions to lock before implementation

1. **Turn granularity:** recommended—every eligible message wakes/enqueues work, rapid messages coalesce into one model turn.
2. **Prompt authority:** recommended—current SuperPOM profile remains authoritative; add orchestration context rather than rewriting it.
3. **Runner:** decided—Arnold's public `StructuredToolRunner`, supplied with Pumpernickel provider and tool adapters.
4. **Subagents:** choose initial model allowlist, domain tools, timeout, child/concurrency limits, and daily spend ceiling. Default to no web/filesystem/terminal.
5. **Scheduled cutover:** recommended—inbound resident canary first, scheduled resident canary second.
6. **Shadow privacy:** define encryption/redaction, access, retention, deletion, and sampling.
7. **Promotion thresholds:** define maximum policy violations, failure rate, p95 latency, cost, and acceptable quality divergence.
8. **Legacy stabilization window:** choose how long legacy remains available after resident promotion.

## 26. Definition of done

The project is complete when:

- Arnold exposes a documented, import-light `arnold.agent.tool_runtime` with no Megaplan/application dependencies;
- Arnold's existing resident and AgentBox behavior remains compatible and their full relevant suites pass;
- Pumpernickel pins and contract-tests the reviewed Arnold API rather than copying its loop/subagent code;
- one registry controls all Pumpernickel conversational and non-chat turn entry points;
- legacy remains the default for every non-SuperPOM bot;
- only SuperPOM selects the resident engine;
- every eligible SuperPOM message/burst, scheduled job, catch-up, recovery, and manual trigger reaches the correct engine;
- SuperPOM preserves Compass-first behavior, phase order, tool enforcement, privacy, prompt, pacing, and durable knowledge semantics;
- bounded subagents work and are auditable;
- duplicate-delivery, crash-before-send, crash-after-send, and post-send-resume tests pass;
- shadow and both canary stages pass their gates;
- resident mode is the production SuperPOM default;
- live rollback to legacy is proven;
- the complete Pumpernickel suite passes;
- all other bots retain their existing behavior and operational baselines;
- dashboards, alerts, environment documentation, migrations, and runbooks are complete.

## 27. Immediate next actions

1. Capture Arnold resident/AgentBox and Pumpernickel SuperPOM baselines.
2. Implement `arnold.agent.tool_runtime` with dependency-inverted backends and policy hooks.
3. Put the current Arnold resident and AgentBox behind compatibility adapters; run their complete regression suites and wheel smoke test.
4. Commit/tag the Arnold API and pin that exact revision in Pumpernickel.
5. Prove the Pumpernickel provider/tool adapter with a fake scoped tool turn.
6. Implement the local Pumpernickel engine registry and legacy adapter; route all entry points while every bot stays legacy.
7. Implement SuperPOM resident phases and bounded delegation behind shadow mode.
8. Complete shadow, canary, recovery, rollback, and non-SuperPOM regression gates before cutover.
