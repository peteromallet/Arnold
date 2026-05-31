# Resident subsystem — anatomy & maturity read

Scope: `megaplan/resident/` (13 modules, 4201 LOC) + `megaplan/schemas/arnold.py`, `megaplan/store/base.py`.
Question driving this read: is `resident` a stable enough "second pipeline shape" to design shared service-interfaces against?

---

## 1. The driver shape — async conversation/event loop, NOT a DAG-of-stages

Resident is an **async event-driven chat loop**, not a staged plan DAG. There is no
phase/stage graph, no `next_step` state machine, no per-stage dispatch. It is:
inbound event → authorize → persist → coalesce burst → one Turn → agent tool-call loop → outbound.

End-to-end trace (file:line):

1. **Inbound (transport edge).** `ResidentDiscordService.on_message` builds a
   `DiscordInboundMessage` and calls `runtime.receive(...)`.
   - `megaplan/resident/discord.py:164` (`on_message`), `:81` (`to_inbound_event`).
2. **Authorize + persist + enqueue.** `ResidentRuntime.receive`:
   - authorizes via allowlist (`runtime.py:75`), denies → `log_system_event` and return (`runtime.py:77-86`);
   - persists conversation + inbound message (`_persist_inbound_event`, `runtime.py:104-140`);
   - submits to the per-conversation coalescer (`runtime.py:90`).
   - Entry: `megaplan/resident/runtime.py:74` (`async def receive`).
3. **Coalesce burst.** `AsyncBurstCoalescer.submit` holds messages per conversation key
   until idle-delay (1.5s) or max-delay (10s), then fires `_handle_batch`.
   - `megaplan/resident/coalescing.py:53` (`submit`), `:87` (`_delayed_flush`), `:91` (`_pop_batch`).
4. **Turn assembly.** `ResidentRuntime._handle_batch`: dedupe, load conversation,
   build `system_prompt` + `hot_context`, `store.create_turn(...)` with a
   `prompt_snapshot` (system prompt + tool catalog), link messages to the turn.
   - `megaplan/resident/runtime.py:142` (`_handle_batch`), turn created `:151-163`.
5. **Agent tool-call loop.** `runner.run(request, tools)` — the inner loop. For the live
   path `OpenAICompatibleAgentRunner.run`: chat.completions in a `for step in range(...)`,
   if `tool_calls` present, execute each registered tool, append tool result message,
   re-call the model; exit when the model returns no tool calls (final text). Bounded by
   `max_tool_calls_per_turn`.
   - `megaplan/resident/agent_loop.py:169` (`OpenAICompatibleAgentRunner.run`), loop `:175-215`;
     `AgentRunner` Protocol at `:34`; deterministic `FakeAgentRunner.run` at `:85`.
6. **Outbound + bookkeeping.** Record tool calls (`runtime.py:222`), persist outbound
   message, `outbound.send(OutboundMessage(...))`, update conversation pointers, mark turn
   completed.
   - `megaplan/resident/runtime.py:187-220`; `OutboundSink.send` Protocol `runtime.py:37`;
     Discord delivery `discord.py:108` (`DiscordOutboundSink.send`).

Parallel/asynchronous side-channel (still loop-shaped, not DAG): a durable
**scheduler** polls `cloud_check` / `deferred_turn` / `heartbeat` / `confirmation_expiry`
jobs and emits follow-up outbound notifications (`scheduler.py:133` `run_due_once`,
`:170` handler table). This is how long-running cloud work re-enters the conversation
asynchronously — it is a job queue, not a pipeline graph.

Confirmed: **async event/conversation loop with a bounded inner tool-call loop + a durable job poller. No DAG-of-stages.**

---

## 2. Substrate primitives it consumes

The list a shared substrate would have to satisfy for resident:

| Primitive | How resident does it today | Type / class |
|---|---|---|
| **Dispatch** (model call + tool loop) | `AgentRunner` Protocol; live = OpenAI-compatible chat/tool-call loop, fake = scripted | `AgentRunner` (Protocol), `OpenAICompatibleAgentRunner`, `FakeAgentRunner` — `agent_loop.py:34,151,67` |
| **Durable state** | Single `Store` Protocol for conversations, turns, messages, tool calls, scheduled jobs, cloud runs; `FileStore` (dev) / `DBStore` (prod) | `megaplan.store.Store` (Protocol, `store/base.py:253`); `ResidentConversation`, `BotTurn`, `Message`, `ToolCall` (`schemas/arnold.py:119,96,137,155`) |
| **Emission / events** | System events + progress events written to store; outbound chat messages | `store.log_system_event` (`base.py:576`), `store.append_progress_event` (`base.py:1295`, `ProgressEventInput`); `OutboundMessage` + `OutboundSink` (`runtime.py:29,37`) |
| **Evidence / audit** | Per-tool-call audit record + full prompt snapshot on the turn | `ToolCallAuditRecord` (`tool_schemas.py:37`), persisted via `store.record_tool_call` (`base.py:553`); `prompt_snapshot` / `state_at_turn` on `BotTurn` |
| **Config** | One pydantic model, env-driven, no `state.json`/profile files | `ResidentConfig` (`config.py:20`, `from_env` `:65`) |
| **Tools** | Name-addressed registry of pydantic-typed, operation-kind-tagged tools (35 registered) | `ToolRegistry` / `ToolRegistration` (`tool_registry.py:26,17`); `ToolInput`/`ToolResult`/`ToolOperationKind` (`tool_schemas.py`); profile registers 35 via `MegaplanResidentProfile.tools()` (`profile.py:370`) |
| **Scheduling** | Durable store-backed job queue with claim/fire/retry/cancel + handler table | `ScheduledJobWorker`, `StoreScheduledJobBackend`, `ResidentJobHandlers` (`scheduler.py:119,55,157`); `make_store_scheduler` (`:402`); jobs via `store.claim_due_scheduled_jobs` (`base.py:1240`) |
| **Auth / identity** | Allowlist authorizer + exact-phrase confirmation for high-impact actions, durable via scheduled jobs | `ResidentAuthorizer` (`auth.py:106`), `AuthorizationSubject` (`:52`), `ConfirmationManager` / `StoreBackedConfirmationManager` (`:143,216`) |

Profile/policy layer: `MegaplanResidentProfile` (`profile.py:303`) supplies `system_prompt()`,
`load_hot_context()`, and `tools()` — the resident analogue of a "profile", but it is a
tool-catalog + prompt provider, NOT the planning `profiles.*` dispatch config.

---

## 3. What it does NOT use — confirmed parallel silo

Grep of `megaplan/resident/` imports (excluding `megaplan.store`, `megaplan.schemas`,
`megaplan.types`):
- Imports only: `megaplan.control.ControlTargetResolver`, `megaplan.editorial.{body,checklist,gating,sprints}`, `megaplan.store.export`, and `megaplan.cloud.cli.{build_cloud_parser,run_cloud_cli}` (the cloud CLI is shelled into in-process by `CloudCliBackend`, `cloud.py:46`).
- **No** import of planning's dispatch, profiles, key-pool, or `state.json` machinery.
  Grep for `state.json | key_pool | KeyPool | profiles. | state_machine | orchestration | handlers. | Pipeline | DAG | dispatch` across resident returns only its own docstrings/identifiers — zero references to planning internals.
- Its own dispatch is `OpenAICompatibleAgentRunner` (its own OpenAI client builder, its own
  API-key env resolution `agent_loop.py:306`), entirely separate from the planning harness's
  routing/key-pool.
- Its state lives in the **shared `Store`** (conversations/turns/jobs/cloud_runs tables),
  not in plan `state.json`.

So resident is a parallel silo that reuses the **store + editorial + cloud-CLI** primitives
but has its own dispatch, config, scheduling, auth, and tool registry.

---

## 4. Maturity / stability verdict

**Test coverage:** 5 test files, **29 test functions**:
- `test_resident_agent_loop.py` (5) — fake tool loop, timeout, missing tool, call-limit, and the live `OpenAICompatibleAgentRunner` path via a monkeypatched fake OpenAI client (tool loop logic covered; no real API hit).
- `test_resident_runtime_profile.py` (8) — idempotent turn+outbound, auth denial before persistence, Discord target normalization, editorial/control tool validation, durable cloud-check tools, bounded search results, repo-register confirmation, plan-artifact/export/reconcile guards.
- `test_resident_scheduler.py` (5) — notify-once-across-restart, reschedule without dup pending, retry-then-cancel, housekeeping handlers, CLI health + scheduler-once on durable store.
- `test_resident_config_auth.py` (5) — config env loading (+Arnold whitelist fallback), denial+redaction, cloud-start admin+confirmation, restart-survival of confirmations.
- `test_resident_cloud_tools.py` (6) — payload classification, argv repo overrides, status persistence+progress, start requires exact confirmation, archive-logs guard, repo-arg forwarding.

Coverage is broad and behavior-level: idempotency, auth gates, durable restart-survival,
coalescing, and the tool loop are all exercised. The fake-runner seam means it is
deterministically testable without a model.

**TODO / FIXME / NotImplemented:** **0** across the whole package. No stubs, no `raise NotImplementedError`, no placeholder handlers.

**Runnable CLI:** Yes. Wired into the main parser — `megaplan/cli/parser.py:1083` registers
the `resident` subcommand; `megaplan/cli/__init__.py:1435-1447` dispatches to
`run_resident_cli`. Subcommands: `discord` (with `--dry-run`), `scheduler-once`, `health`
(`resident/cli.py:23-37`). `health` and `scheduler-once` run against a real durable store
and are covered by tests.

**Git activity:** The entire subsystem landed in **3 commits on 2026-05-06** (`e41a1443` add,
`1471fd1e` log adapter events, `2d019232` expand operator tools), all in one feature drop.
`git log --follow` on `runtime.py` shows a single commit. **No commits have touched
`megaplan/resident/` in the ~3 weeks since** (today 2026-05-28); the May-13/16 file mtimes
are filesystem touches with no corresponding commits, and the working tree is clean for the
package. So it is **shipped-and-frozen**, not actively churning — and also not iterated-on
since landing.

**Half-built vs shipped:** Shipped. Clean Protocol seams (`AgentRunner`, `OutboundSink`,
`Store`, `CloudToolBackend`, `ScheduledJobBackend`), pydantic-typed boundaries everywhere,
zero TODOs, dev+prod store wiring, idempotency keys on every write, durable confirmations and
scheduled jobs with restart-survival tests. The one "lighter" spot: live model dispatch is
only tested via a fake OpenAI client (no integration test against a real provider), and the
Discord transport itself is thin glue (untested live, by nature).

### Verdict: design-against-it = **YES, with one caveat**

The shape is a clean, internally-consistent, fully-typed **async conversation loop over a
small set of Protocol seams** — exactly the kind of second pipeline shape worth designing a
shared substrate against. Its primitive set (dispatch / state / events / evidence / config /
tools / scheduling / auth) is explicit and Protocol-bounded, and it deliberately reuses the
shared `Store` while keeping its own dispatch — i.e. it already demonstrates the
substrate/silo split a shared interface would formalize.

Caveat: it has been **frozen since a single 2026-05-06 landing** with no subsequent
iteration. The shape is stable because nothing has stressed it, not because it has been
battle-hardened across changes. There is no live-provider integration test, and it has not
yet been exercised by a second consumer. Treat its **seam set as a binding constraint**
(they are well-chosen), but expect the **concrete signatures to still move** the first time a
shared substrate forces planning and resident to share one dispatch/state/event interface.
Bind to the Protocols, not to today's exact method shapes.
