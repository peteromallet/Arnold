# m2 — Shared dispatch service + Arnold reconciliation

**Epic:** Pipeline Unification (`briefs/pipeline-unification-EPIC.md` §m2). **Position:** m1 → **m2** (independent of m3/m4; depends only on m1's executor merge + parity gate). Run on a parallel branch off the m1 base. **Tier/robustness:** premium · thorough/high.
**Grounding:** `briefs/validation/c6-profiles.md` (claims 1–4 + the `tier_models` watch-item), `briefs/validation/premortem/p6-wrong-abstraction.md` (Arnold-is-not-a-pipeline), and code verified 2026-05-28.

**Guiding principle (EPIC §):** share what other tools (Arnold) actually use; do NOT generalize planning-only machinery. m2 delivers the most-shared capability — model dispatch — *and* answers whether sharing-via-pack is the right shape, by forcing Arnold's real (non-DAG) loop to pull on it.

---

## Outcome

1. **Model/profile dispatch is pack-agnostic.** A non-planning slot can be declared, validated, and resolved to a model with no inheritance of planning's 14-phase vocabulary or its 1..5 execute ladder, and with no bare `__getitem__` `KeyError` anywhere on the dispatch path (unknown slot → typed `CliError`).
2. **Dispatch is callable as a service WITHOUT a Pipeline.** A resident-style caller (the `loop/engine.py` substrate-style driver, store-based) can resolve a slot and dispatch a real worker directly — not as a `Pipeline/Stage/Edge` step.
3. **Arnold reconciliation is done, not spiked.** A written, code-grounded map enumerates which shared primitives Arnold's resident loop needs (dispatch, the `Store`, emission, evidence) and proves each is or is not reachable without the pipeline shell. Primitives with NO home become this epic's recorded backlog.
4. **Acceptance:** one real, model-DISPATCHING consumer that is NOT planning and NOT a DAG pipeline — a resident-style caller — runs a worker via the service and writes its real output. This proves the *contract*, not just the executor.

## Scope (tied to current file:line)

1. **Decouple `VALID_PHASE_KEYS` from planning phases.** `profiles/__init__.py:24` hardcodes `VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())` (the 14 planning phases, `types.py:387-402`). `_validate_profile_map` (`:272-294`, reject at `:276`) and `_validate_tier_models` (`:360-403`, reject at `:369`) both gate on it. Parameterize both validators on a **slot-key set supplied by the loading context** (default = planning's frozenset, so planning validation stays byte-identical). The pipeline-local TOML path (`:574-634`) already skips this ("allow any slot keys", `:622-630`) — it is the blessed escape hatch and is not regressed.

2. **Replace the bare `DEFAULT_AGENT_ROUTING[step]` with typed fail-loud slot resolution at the single chokepoint.** `workers/_impl.py:2382`: `spec = config.get("agents", {}).get(step) or DEFAULT_AGENT_ROUTING[step]`. For an unknown slot, the `or` falls through to a bare `DEFAULT_AGENT_ROUTING[step]` → **uncaught `KeyError`** (c6 claim 2). Replace with a lookup that, on miss, consults a **caller-supplied routing/profile table** then raises `CliError("unknown_step_route", …)` naming the slot and the known slots. Behavioural no-op for the 14 planning-named callers (they still resolve via `DEFAULT_AGENT_ROUTING`); m1 parity gate is the regression oracle. The 14 production callers of `resolve_agent_mode` all route the step name through this one resolver — enumerate and cover: `_impl.py:2489` (`run_step_with_worker`), `execute/batch.py:95`, `handlers/execute.py:58,117`, `handlers/critique.py:80,96,307`, `handlers/review.py:498,525`, `handlers/gate.py:454`, `handlers/shared.py:220`, `loop/engine.py:518`, `orchestration/tiebreaker.py:131`, `prompts/tiebreaker_orchestrator.py:133`.

3. **Unbind `tier_models` from planning's 1..5 ladder.** `_validate_tier_models:378` hard-rejects any tier key outside `1..5` and `:369` gates phase on `VALID_PHASE_KEYS`. The ladder is consumed only at `handlers/execute.py:144-155` (`tier_models.get("execute")` → `tier_map`, threaded to dispatch). Slot-parameterize tier validation like (1); stop treating `1..5` as a global invariant for non-`execute` slots / non-planning packs. Planning's `execute` ladder semantics and its thread to `handlers/execute.py:152` are unchanged.

4. **Expose dispatch as a standalone, non-pipeline service.** The seam already exists but is informal: `loop/engine.py:514-527` calls `run_step_with_worker(step, shim_state, …, resolved=resolve_agent_mode(step, normalized), prompt_override=prompt)` with a `shim_state = {"config":…, "sessions":…}` — i.e. a non-DAG caller already dispatches by handing in a *fully-rendered prompt* plus a minimal state shim. Formalize this into a documented dispatch entry callable without any `Pipeline/Stage/Edge`: `(slot, prompt, profile/routing-table, session-bag, project_dir) -> WorkerResult`. **Constraint (see Open Q3 / blocking note):** `run_step_with_worker`'s default prompt path (`_impl.py:1596`, `create_hermes_prompt(step,state,…)`; `:1743` `create_codex_prompt`) and its body reads of `state["config"]["project_dir"]` / `["mode"]` / `state["sessions"]` / `state["name"]` are planning-shaped — the service contract must be the `prompt_override` + shim-state path, NOT the prompt-building path. Do the minimum to make that path a first-class, named, tested entry; do NOT refactor the planning prompt builders (anti-scope).

5. **Bridge the one slot-agnostic abstraction OR keep `ctx.profile` as a dict — pick one (Open Q1).** `_pipeline/profile.py::Profile.model_for` (`:48-57`) is genuinely slot-agnostic but production-dead (test-only; c6 claim 3); the executor passes the profile as a plain `dict[str,str]` via `StepContext.profile` (`_pipeline/run_cli.py:322`, `_pipeline/types.py:144`). The acceptance consumer resolves its slot either via a promoted `Profile.model_for` or a thin `profile[slot]` read. One documented resolution path results.

6. **Arnold reconciliation (real work).** Produce a code-grounded map (write it into this brief's directory as `m2-arnold-reconciliation.md`) enumerating, for each primitive Arnold's resident loop needs, whether it is reachable without the pipeline shell:
   - **dispatch** — delivered by (4); confirm the resident loop can call it with a `Store`-derived prompt and no `state.json`.
   - **`Store`** — already a `Protocol` (`store/base.py:253`) with concrete backends in `store/_db`, `store/_file`, `store/multi.py`; already constructed by non-pipeline code (`control.py`, `editorial/*`, `tickets/core.py`, `_core/workflow.py`). Confirm reachable; this is the strongest evidence the substrate already exists outside packs.
   - **emission** — `Store.append_progress_event`/`list_progress_events` (`base.py:1295-1307`), `log_system_event` (`:576`). Confirm a tool can emit progress without being planning. (The shared emission hook itself is m4; m2 only verifies reachability.)
   - **evidence** — confirm whether "prove work happened" has a callable home or is pipeline-bound (m4 owns the strategy; m2 records the gap).
   - Record every primitive with NO non-pipeline home as backlog: e.g. await-event control flow, lease/transaction wiring into a dispatch turn, the resident control-message drain (`put_control_message`/`claim_pending_control_messages`, `base.py:1143-1149`).

7. **ACCEPTANCE consumer.** Make the resident-style, non-DAG caller dispatch a real worker through the service: resolve a non-planning slot, dispatch (with a `prompt_override`), and write the worker's real output as its artifact. Today every existing non-planning pack is a stub: `grep -rn "model_for|run_step_with_worker|resolve_agent_mode|run_worker|dispatch"` over `pipelines/creative` + `pipelines/doc` returns zero (c6 claim 4) — `CreativeStep.run` (`creative/steps.py:25-53`) and every `doc` step (`doc/steps.py` Outline/SectionDraft/Critique/Revise/Assembly) only `mkdir`+`write`. The acceptance consumer is the inverse of that zero. **It must be a resident-style caller, not a new DAG pack** — a converted stub pack would re-prove the executor, not the contract (p6 §2). The cleanest vehicle is a thin store-backed driver exercising the formalized entry from (4) (the `loop/engine.py` shim is the existing proof-of-shape).

## Locked decisions

- **System-profile + core-dispatch contract is the target;** the pipeline-local TOML bypass (`profiles/__init__.py:574-634`) is the blessed escape hatch and is NOT regressed.
- **Fail-loud, typed.** Unknown-slot resolution raises `CliError`, never bare `KeyError`.
- **Planning is byte-identical.** All validators default to planning's slot set; the 14 callers keep `DEFAULT_AGENT_ROUTING` behaviour. m1 parity gate is the regression oracle (EPIC cross-cutting invariant).
- **Acceptance = live, non-pipeline dispatch.** A passing stub does not count, and a new DAG pack does not count — the consumer must be a resident-style caller running a real worker and emitting its output.
- **The service contract is the `prompt_override` + shim-state path**, not the planning prompt-builder path.

## Open questions

1. **Resolution mechanism:** promote `Profile.model_for` into the service/consumer path, OR keep `ctx.profile`/the routing table as `dict[str,str]` read directly before dispatch? Affects whether `_pipeline/profile.py` graduates from test-only.
2. **Routing-table source for `resolve_agent_mode`:** does the caller-supplied routing table arrive as a new kwarg on `resolve_agent_mode`/the service entry, or is it stuffed into the existing `config["agents"]` shape it already reads at `:2382`? Determines whether the resolver signature changes at all.
3. **THE GENUINE QUESTION — does pack-ification survive the Arnold reconciliation?** p6 argues the load-bearing reusable thing is dispatch+`Store`+emission+evidence, and that the `Pipeline/Stage/Edge/halt` graph does NOT fit Arnold (resident vs. terminating, event-driven vs. static-edge, transactional `Store` vs. one `state.json` dict). m2 must answer empirically: if the acceptance consumer can dispatch a worker with zero pipeline machinery (it already nearly can — `loop/engine.py` does), the thin-services thesis is proven and the pack frame is confirmed as "catalog of DAG-shaped tools," not the universal tenant contract. If the only way to dispatch is to wrap a pipeline, m3/m4 re-scope. **Record the verdict in the reconciliation doc.**
4. **Is dispatch cleanly extractable today?** No — see blocking note. Decide how much of `run_step_with_worker`'s planning-state coupling the service entry must shed vs. tolerate via the shim. Default: tolerate via shim, do not refactor.

## Constraints

- **No execution-model change** — no auto.py port, no subprocess→in-process; that is deferred (EPIC §Deferred). m2 must not touch the per-phase-subprocess model.
- **No pack relocation** — planning stays put (m3); no new realization backends.
- **Does not touch planning's profile *content*** (`megaplan/profiles/*.toml`) or the planning prompt builders (`create_hermes_prompt`/`create_codex_prompt`).
- **m1 parity gate stays green** throughout; any observable planning behaviour change is out of scope. Behaviour changes update golden expectations in their own commit.
- **26 ambient `MEGAPLAN_*` env reads** and `apply_profile_expansion` mutation are m4's problem — do not refactor config plumbing beyond what slot-resolution strictly needs.
- **Back-compat:** unknown-phase in an existing planning profile downgrades to a warning, not a hard reject (EPIC cross-cutting).

## Done criteria (testable)

1. A **system profile** can name a non-planning slot (`[profiles.x] draft = "hermes:…"`) and load without `invalid_profile` when validated against a supplied slot set — and still rejects a genuinely-unknown slot with a typed error. (Unit test on parameterized `_validate_profile_map`.)
2. `resolve_agent_mode("some_unknown_pack_slot", args)` raises a typed `CliError("unknown_step_route", …)`, **not** `KeyError`; all 14 enumerated call sites covered (or proven to route through the single resolver). (`pytest.raises(CliError)`.)
3. `_validate_tier_models` accepts a pack's slot-keyed tier map and no longer hard-couples non-`execute` slots to `1..5`/`VALID_PHASE_KEYS`; planning's `execute` 1..5 ladder still validates and still threads to `handlers/execute.py:152`.
4. **Standalone service entry** exists and is callable with `(slot, prompt, routing/profile, sessions, project_dir)` and **no `Pipeline`/`Stage`/`Edge`/`StepContext` object**; a unit test imports and calls it directly.
5. **Non-pipeline live-dispatch acceptance test** (the load-bearing one): a resident-style, store-backed caller — NOT a DAG pipeline, NOT planning — resolves a non-planning slot and dispatches a real worker (`MEGAPLAN_MOCK_WORKERS=1` for CI determinism), and asserts it (a) resolved the slot from its routing table, (b) invoked the worker dispatch path, (c) wrote the worker's real output (not a placeholder). `grep` for `dispatch`/`run_step_with_worker`/`model_for` over the consumer returns non-zero (inverse of c6 claim 4).
6. **Arnold reconciliation doc** committed (`m2-arnold-reconciliation.md`): per-primitive reachability table (dispatch/`Store`/emission/evidence) + an explicit list of no-home primitives as backlog + a written verdict on Open Q3.
7. m1 parity gate green; planning golden expectations unchanged.

## Touchpoints

- `profiles/__init__.py` — `:24` `VALID_PHASE_KEYS`; `_validate_profile_map` `:272-294`; `_validate_tier_models` `:360-403`; pipeline-local bypass `:574-634`; `PROFILE_METADATA_KEYS` `:30-39`.
- `types.py:387-402` `DEFAULT_AGENT_ROUTING`, `:403` `KNOWN_AGENTS`.
- `workers/_impl.py` — `resolve_agent_mode` `:2313-2475` (trap at `:2382`); `run_step_with_worker` `:2478-2545` (planning-state reads + default prompt path at `:1596`/`:1743`); 14 call sites (Scope 2).
- `handlers/execute.py:144-155` (tier_map consumption).
- `loop/engine.py:489-540` (`run_loop_worker`: the existing non-DAG dispatch shim — the proof-of-shape and likely acceptance vehicle); imports at `:27`.
- `store/base.py` — `Store`/`Transaction` Protocols `:237-253`; leases `:1098-1136`; control messages `:1143-1149`; progress emission `:1295-1307`; `log_system_event` `:576`. Concrete backends: `store/_db`, `store/_file`, `store/multi.py`. Non-pipeline constructors: `control.py`, `editorial/*`, `tickets/core.py`, `_core/workflow.py`.
- `schemas/arnold.py` (`Epic`, `ResidentConversation`, `BotTurn`, `Message`, `ControlMessage`-shaped flows) — the entity surface the reconciliation maps against.
- `_pipeline/profile.py:48-57` (`Profile.model_for`, test-only); `_pipeline/types.py:133-183` (`StepContext.profile`, `Step.slot`); `_pipeline/run_cli.py:318-324` (profile → dict).
- `pipelines/creative/steps.py:25-53`, `pipelines/doc/steps.py` (the stub false-proof; do NOT convert into the acceptance consumer).

## Anti-scope

- Does **not** touch planning's profile content or prompt builders.
- **No execution-model change** (auto.py / subprocess→in-process — deferred).
- **No pack relocation** (planning → `pipelines/planning/` is m3).
- No shared-emission-hook extraction, no evidence-strategy injection, no `RunConfig`/`services` bag (all m4) — m2 only verifies their reachability for the reconciliation.
- No `HandlerContext` purity, no symmetric `Realizer` Protocol, no `capabilities` tuple (deferred).
- Not collapsing split-brain routing (`_label_for`/`_gate_next_step`/`workflow_next` — m3).
- The acceptance consumer is a resident-style caller, **not** a new DAG pack (that would re-prove the executor, not the contract).
