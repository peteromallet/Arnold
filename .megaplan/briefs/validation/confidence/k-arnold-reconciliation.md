# K — Arnold reconciliation: the confirmed shared-substrate contract

**Status:** Keystone confidence artifact for `.megaplan/briefs/pipeline-unification-EPIC.md`.
**Date:** 2026-05-28. **Method:** read Arnold's actual in-tree implementation, not just its schemas.
**Verdict in one line:** Arnold is **not inferred — it is a built-out, tested, resident service in-tree
today**, and reading its real code (not just `schemas/arnold.py` + `store/base.py`) *confirms the
pre-mortem's thesis and falsifies a load-bearing factual claim in the epic*. The right frame is a
**thin shared-services layer that both planning (DAG) and Arnold (resident loop) compose** — NOT
"planning as a pipeline pack + shared substrate."

---

## 0. First, a correction the epic and pre-mortem both got wrong

Both `.megaplan/briefs/pipeline-unification-EPIC.md` (m2 paragraph, "why v2") and `premortem/p6` assert the
resident driver is **`loop/engine.py` (743 L `MegaLoop`)**. **That is false.** `loop/engine.py` is the
**planning iterative loop** (`init_loop`/`run_plan_phase`/`run_execute_phase` — a plan→run-a-shell-
command→judge→revert loop). It is just another *planning* execution engine. It has **no** `Store`,
no `ResidentConversation`, no turns, no leases. The premise "Arnold ≈ MegaLoop" is a mis-citation.

**The actual Arnold lives in `megaplan/resident/` (~3,800 LOC, 13 modules, 5 dedicated test files).**
It is substantially built and exercised, not a sketch:
- `resident/runtime.py` — `ResidentRuntime`: the real event-driven loop (authorize → coalesce burst →
  persist inbound `Message` → `create_turn` → run agent → persist outbound → `update_turn`).
- `resident/agent_loop.py` — `OpenAICompatibleAgentRunner`: Arnold's **own** model-dispatch +
  tool-call loop (OpenAI/OpenRouter chat-completions, its own retry/timeout/tool-call budget).
- `resident/profile.py` — 1,761 L of constrained Store-backed tools (epics, checklists, sprints,
  cloud runs, control messages, plan artifacts).
- `resident/scheduler.py` — `ScheduledJobWorker`: drains `claim_due_scheduled_jobs`, polls `CloudRun`s.
- `resident/discord.py`, `auth.py`, `coalescing.py`, `cloud.py`, `cli.py` (`discord` / `scheduler-once`
  / `health` subcommands).

This changes the verdict from "inference" to "**confirmation against running code**."

---

## 1. What Arnold actually needs from a shared substrate (concrete primitives + required SHAPE)

| Primitive | Arnold's required SHAPE (resident, event-driven, transactional) | Confirmed in code |
|---|---|---|
| **Durable state** | `Store` Protocol: transactions, optimistic `revision`/`RevisionConflict`, `EpicEvent` event-sourcing, `get_epic_at_time` time-travel, `EpicLock`, in-place entity mutation of one long-lived `Epic`. **Not** a `state.json` last-writer-wins dict. | `store/base.py`; `resident/*` calls ~40 Store methods. Backends: `store/_db/*` (Supabase) + `store/_file/*`. |
| **Model dispatch** | A chat-completions tool-call loop with its **own** key/provider/timeout/tool-budget management, driven by inbound messages. **Not** slot→tier→profile phase resolution. | `OpenAICompatibleAgentRunner` — fully self-contained; imports **nothing** from `megaplan.workers`/`profiles`. |
| **Emission / progress** | `append_progress_event` + `log_system_event` + `record_tool_call`, keyed by epic/conversation/turn, written continuously while resident. | `resident/profile.py:1450`, `scheduler.py:275`. |
| **Inbox / control plane** | At-least-once delivery, `put_control_message` / `claim_pending_control_messages` / `recover_stale_control_messages`, `ScheduledJob`, `CloudRun` lifecycle, leases. | `control.py`, `resident/scheduler.py`, profile control tools. |
| **Evidence of work** | The **audit trail itself** (`BotTurn`, `ToolCall`, `ExternalRequest` pending/confirmed/orphaned, `SystemLog`) IS the evidence. **Not** git-diff or assembled-prose artifacts. | Schemas + `_record_tool_calls`, external-request ledger. |
| **Prompt assembly** | `system_prompt()` + `load_hot_context()` from the Store (recent messages/tool calls/feedback). **Not** `prompt_key`-keyed phase templates. | `MegaplanResidentProfile`, `HotContext`. |
| **Auth / multi-tenancy** | Per-subject inbound authorization, confirmation gating — **planning has no analogue**. | `resident/auth.py`. |
| **Planning-as-a-tool** | Arnold *invokes* planning as an opaque black box via the **cloud CLI** and **control messages** (`run_sprint`), then polls `CloudRun` status. It never imports the planning executor, handlers, or dispatch. | `resident/cloud.py` → `run_cloud_cli`; `profile._run_sprint_on_cloud` → `put_control_message`. |

---

## 2. Epic's planned shape vs. Arnold's need — MATCH / MISMATCH

- **m2: dispatch-as-a-service via `prompt_override`, decouple `VALID_PHASE_KEYS`, fix
  `resolve_agent_mode`/`DEFAULT_AGENT_ROUTING`/`tier_models`.** → **MISMATCH (does not serve Arnold).**
  Arnold already dispatches models via its own runner and uses **zero** of these symbols (grep across
  `resident/` for `resolve_agent_mode`, `run_step_with_worker`, `apply_profile_expansion`,
  `tier_models`, `DEFAULT_AGENT_ROUTING`, `VALID_PHASE_KEYS` = **NONE**). Pack-agnostic dispatch is a
  genuine **planning-internal** cleanup; the claim that it is "the Arnold capability" is unsupported.
  m2's acceptance test ("one resident-style caller that dispatches a model") would be satisfied by
  re-pointing Arnold's *existing* runner — i.e. it tests a contract Arnold doesn't consume.
- **m4: one shared post-step emission hook.** → **PARTIAL MATCH, wrong granularity.** Arnold needs
  emission, but **continuous, per-turn/per-tool**, not "post-*step*" tied to a DAG node. The shared
  thing is the Store's `append_progress_event`/`log_system_event` sink (which Arnold already calls),
  not a step-completion hook. Consolidate the *sink*, don't frame it around steps.
- **m4: injected evidence strategy (git-vs-prose, mode-keyed).** → **MISMATCH.** Arnold's evidence is
  its transactional audit ledger; neither git nor prose-assembly applies. A `mode`-keyed code/prose
  switch is a **planning-only** axis.
- **m4: `RunConfig` + `services` bag kwarg on handlers; hoist `MEGAPLAN_*` env.** → **MISMATCH.**
  Arnold has its own `ResidentConfig` (Pydantic) and never calls planning handlers. The 26 env vars
  are planning's ambient config.
- **m3: planning as a discovered pack; collapse next-step encodings onto graph edges.** → **N/A to
  Arnold.** Pure planning-internal; Arnold has no stages/edges/`halt`.

**The one real match:** the **`Store` Protocol** — already a Protocol, already dual-backed, already
Arnold's state substrate. The epic *under-emphasizes* this (it is buried as a cross-cutting
"touchpoint," not a milestone), and over-invests in dispatch/evidence/RunConfig that Arnold won't use.

## 3. Planning-only generality mislabeled as "shared"
- Pack-agnostic **dispatch** (m2) — valuable cleanup, but planning-only; Arnold has its own runner.
- **Evidence strategy** (m4) — git/prose is a planning axis; Arnold's evidence is the audit trail.
- **`RunConfig`/`services`/env hoist** (m4) — planning's config plumbing; Arnold uses `ResidentConfig`.
- The **pack/Stage/Edge mechanism** (m3) — by construction never touches Arnold.

## 4. Primitives Arnold needs that the epic does NOT plan to share (the gaps)
1. **`Store` as the first-class durable-state service** with transactions/revisions/leases/event-
   sourcing — present in code but **not elevated to a shared-substrate milestone**; the epic treats
   `state.json` and `Store` as separate worlds rather than file-backend-of-Store.
2. **Control-plane / inbox** (`ControlMessage`, `ScheduledJob`, `CloudRun`, stale-claim recovery) — the
   confirmed integration seam between Arnold and planning; the epic never names it as shared substrate.
3. **Resident loop seam** (event coalescing, turn lifecycle, abandoned-turn recovery) — no home in the
   epic.
4. **Auth / confirmation / multi-tenancy** — Arnold-only; epic silent.
5. **The continuous emission sink** (vs. post-step hook) — needs reframing as a Store sink.

## 5. VERDICT (strong position)
**"Planning as a pipeline pack + shared substrate" is the WRONG framing. Adopt the thin
shared-services layer (pre-mortem §4).** The evidence is no longer a paper steelman: Arnold is
*built*, *tested*, and **already composes exactly the thin-services shape** — it reuses the `Store`
and the control/cloud plane and **nothing else**, and it brought its own dispatch, config, prompt
assembly, and evidence. Every joint the epic plans to "share via the pack frame" (dispatch, evidence,
RunConfig, emission-as-step-hook) is a joint Arnold **does not touch**. The genuinely load-bearing
shared substance is exactly two things — **the `Store` Protocol** and **the control/cloud handoff
plane** — both of which already exist and neither of which requires a `Pipeline`. The epic should be
re-scoped: **m1** (parity/versioning/contracts) stays; **m2** keep pack-agnostic dispatch but **relabel
it planning-internal cleanup, drop the Arnold-acceptance framing**; promote **`Store`-as-shared-state
+ the control/cloud plane** to the real shared-substrate milestone; **m3/m4** become explicitly
planning-only (fine, but not "platform"). Planning composes the services into a DAG (keep the Pipeline
runtime — good for DAGs); Arnold composes them into a resident loop. Neither is privileged.

## Residual uncertainty (what code alone cannot tell us)
- **Arnold's roadmap/maturity intent:** code shows a substantial, tested resident service, but not
  whether it is shipped/live, abandoned, or mid-build — `last_edited` clustering (May 13) and only 5
  test files suggest active-but-early. Whether Arnold's *future* features (e.g. richer planning
  invocation, new transports) would pull on planning dispatch is unknowable here. **Ask Peter.**
- **Intended coupling direction:** code shows Arnold→planning via cloud CLI + control messages (loose,
  black-box). Whether the epic *wants* a tighter in-process coupling later (which would change the
  dispatch verdict) is a product decision, not a code fact.
- **Second tenant beyond Arnold:** the guiding principle tests scope against "will Arnold use it." If a
  *third*, DAG-shaped tool is the real target for the m2/m4 generality, those milestones could be
  justified on different grounds — but no such tenant exists in-tree.
