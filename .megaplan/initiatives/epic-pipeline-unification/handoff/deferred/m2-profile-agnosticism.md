# m2 — Profile pack-agnosticism (the Arnold capability)

**Epic:** Pipeline Unification (`briefs/pipeline-unification-EPIC.md`). **Position:** m1 → **m2** (independent of m3–m6; delivers Arnold value earliest). **Tier/robustness:** premium · thorough/high.
**Grounding:** validated 2026-05-28 in `briefs/validation/c6-profiles.md` (claims 1–4 + the `tier_models` watch-item) and EPIC §"What the validation changed" #5.

---

## Outcome

Make **"any pack runs under the same profile contract"** literally true. Today it is false in exactly the places a *model-dispatching* pack would touch, and the demo packs (`creative`/`doc`) hide that because their steps never resolve a model — a **false proof of genericity** (c6 claim 4). After m2: a non-planning pack can (a) declare its own slots, (b) have those slots resolve to a model, and (c) dispatch a real worker — without inheriting planning's phase vocabulary or its 1..5 execute ladder, and **without a bare `__getitem__` KeyError** anywhere on the dispatch path. The proof is a shipped reference pack that actually runs a worker, not a stub.

The contract being hardened is the **system-profile + core-dispatch** path. The pipeline-local TOML path already bypasses `VALID_PHASE_KEYS` (`megaplan/profiles/__init__.py:622-630`), so it is the *escape hatch that works*; m2's job is to make the rest of the contract honour pack-declared slots and fail loud (typed `CliError`) instead of crashing.

## Scope (work items tied to current code)

1. **Decouple `VALID_PHASE_KEYS` from planning phase names.** `megaplan/profiles/__init__.py:24` hardcodes `VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())` (the 14 planning phases from `megaplan/types.py:387-402`). `_validate_profile_map` (`:272-294`, the `phase not in VALID_PHASE_KEYS` reject at `:276`) and `_validate_tier_models` (`:360-403`, same reject at `:369`) both gate on it. Parameterize both validators on a **slot-key set supplied by the loading context** (the pack's declared stage IDs) rather than the planning frozenset. Planning keeps its current set as the default arg so its own validation is byte-identical (anti-scope: do not touch planning content). This is the system-profile half of c6 claim 1.

2. **Typed, fail-loud slot resolution in `resolve_agent_mode` (14 call sites).** `megaplan/workers/_impl.py:2382`: `spec = config.get("agents", {}).get(step) or DEFAULT_AGENT_ROUTING[step]`. For an unknown pack step (`config["agents"].get(step)` → None), the `or` falls through to a bare `DEFAULT_AGENT_ROUTING[step]` → **uncaught KeyError** (c6 claim 2). Replace with a typed lookup that, on miss, either consults a **pack-supplied routing/profile table** or raises a `CliError("unknown_step_route", …)` naming the step and the known slots. The 14 production callers pass step names today and inherit the trap — enumerate and cover all of them (c6 claim 2 list): `workers/_impl.py:2489` (`run_step_with_worker`), `execute/batch.py:95`, `handlers/execute.py:58,117`, `handlers/critique.py:80,96,307`, `handlers/review.py:498,525`, `handlers/gate.py:454`, `handlers/shared.py:220`, `loop/engine.py:518`, `orchestration/tiebreaker.py:131`, `prompts/tiebreaker_orchestrator.py:133`. The change must be a behavioural no-op for the 14 planning-named callers (they still resolve via `DEFAULT_AGENT_ROUTING`) — the m1 parity gate stays green.

3. **Unbind `tier_models` from planning's 1..5 execute ladder.** The watch-item c6 calls out: `_validate_tier_models` (`profiles/__init__.py:378`) hard-rejects any tier key outside `1..5` *and* gates phase on `VALID_PHASE_KEYS` (`:369`); the ladder is consumed only at `megaplan/handlers/execute.py:152` (`tier_models.get("execute")` → `tier_map`, threaded to dispatch). Make tier validation **slot-parameterized like (1)** and stop treating `1..5` as a global invariant for non-`execute` slots / non-planning packs. Minimum: don't reject a pack's tier map for using its own slot name; planning's `execute` ladder semantics are unchanged.

4. **Bridge the one slot-agnostic abstraction into the live path.** `megaplan/_pipeline/profile.py::Profile.model_for` (`:48-57`) is genuinely slot-agnostic but **production-dead** (test-only; c6 claim 3) — the executor passes the resolved profile as a plain `dict[str,str]` via `StepContext.profile` (`_pipeline/run_cli.py:322`, `_pipeline/types.py:144`). The reference pack (item 5) consumes `ctx.profile` to resolve its declared slot to a model and dispatch. Decide (Open Q1) whether it does so via `Profile.model_for` (promote it out of test-only) or via a thin `ctx.profile[slot]` dict read + `run_step_with_worker`. Either way, **one** documented resolution path for packs results.

5. **ACCEPTANCE PACK — ship one real non-planning pack that resolves a model and dispatches a worker.** Today `grep -rn "model_for|run_step_with_worker|resolve_agent_mode|run_worker|dispatch"` over `pipelines/creative` + `pipelines/doc` returns **zero** (c6 claim 4): `CreativeStep.run` (`pipelines/creative/steps.py:25-53`) and every `doc` step (`pipelines/doc/steps.py` Outline/SectionDraft/Critique/Revise/Assembly) only `mkdir`+`write`. Add a new pack (proposed `megaplan/pipelines/scribe/`, see Open Q2) whose step (a) declares a non-planning slot (e.g. `slot="draft"`), (b) resolves it against `ctx.profile`, (c) dispatches a worker via the chosen path, and (d) writes the worker's real output as its artifact. Ship a pipeline-local `profiles/*.toml` declaring that slot. This pack is the executable assertion that the contract — not just the executor — is generic.

## Locked decisions

- **System-profile + dispatch contract is the target;** the pipeline-local TOML bypass (`profiles/__init__.py:574-634`) is the blessed escape hatch and is NOT regressed.
- **Fail-loud, typed.** Unknown-slot resolution raises `CliError`, never bare `KeyError` (c6 claim 2 fix).
- **Planning is byte-identical.** All validators default to planning's slot set; the 14 callers keep `DEFAULT_AGENT_ROUTING` behaviour. m1 parity gate is the regression oracle (EPIC cross-cutting invariant).
- **Acceptance = live dispatch.** A passing stub does not count; the reference pack must run a real worker and emit its output.

## Open questions

1. **Resolution mechanism:** promote `Profile.model_for` into the executor/pack path, OR keep `ctx.profile` as `dict[str,str]` and have packs read it directly before calling `run_step_with_worker`? (c6 sizing offers both.) Affects whether `_pipeline/profile.py` graduates from test-only.
2. **Reference-pack identity:** new minimal `scribe` pack (cleanest, no legacy stub baggage) vs. converting one existing stub step (e.g. `doc/SectionDraftStep`) into a real dispatcher? New pack is lower-risk for the contract proof; converting `doc` doubles as killing a false-proof stub. Pick one.
3. **`resolve_agent_mode` table source:** does the pack-supplied routing table live on the `Pipeline`/pack metadata, on `StepContext`, or is dispatch fully delegated to the step (which already holds `ctx.profile`)? Determines whether `resolve_agent_mode`'s signature changes at all.

## Constraints

- **No execution-model changes** — auto.py / per-phase-subprocess model is m3's hinge; m2 must not touch it (EPIC §m3, anti-scope).
- **No pack relocation** — planning stays where it is; relocation is m4.
- **No change to planning's profile *content*** (`megaplan/profiles/*.toml`).
- **m1 parity gate stays green** throughout; any observable planning behaviour change is out of scope.
- **26 ambient `MEGAPLAN_*` env reads** and `apply_profile_expansion` mutation are m5's problem — do not refactor config plumbing here beyond what slot-resolution strictly needs.

## Done criteria (testable)

1. A **system profile** can name a non-planning slot (e.g. `[profiles.x] draft = "hermes:…"`) and load without `invalid_profile`, when validated against a pack's declared slot set — and still rejects a genuinely-unknown slot with a typed error. (Unit test on parameterized `_validate_profile_map`.)
2. `resolve_agent_mode("some_unknown_pack_slot", args)` raises a typed `CliError`, **not** `KeyError`; all 14 enumerated call sites covered (or the resolver is the single chokepoint they all route through). (Test asserts `pytest.raises(CliError)`.)
3. `_validate_tier_models` accepts a pack's slot-keyed tier map and no longer hard-couples non-`execute` slots to `1..5`/`VALID_PHASE_KEYS`; planning's `execute` 1..5 ladder still validates and still threads to `handlers/execute.py:152`.
4. **Live-dispatch acceptance test:** run the reference pack end-to-end (`MEGAPLAN_MOCK_WORKERS=1` for CI determinism) and assert the step (a) read its slot from `ctx.profile`, (b) invoked the worker dispatch path, (c) wrote the worker's output (not a placeholder). A `grep -rn "run_step_with_worker|model_for|dispatch"` over the new pack returns **non-zero** matches (the inverse of c6 claim 4's zero).
5. m1 parity gate green; planning golden expectations unchanged.

## Touchpoints

- `megaplan/profiles/__init__.py` — `:24` `VALID_PHASE_KEYS`; `_validate_profile_map` `:272-294`; `_validate_tier_models` `:360-403`; `PROFILE_METADATA_KEYS` `:30-39`.
- `megaplan/types.py:387-402` (`DEFAULT_AGENT_ROUTING`), `:403` (`KNOWN_AGENTS`).
- `megaplan/workers/_impl.py` — `resolve_agent_mode` `:2313-2475` (trap at `:2382`); `run_step_with_worker` `:2478-2489`; worker entries `run_claude_step` `:1657`, `run_codex_step` `:1688`.
- 14 call sites (c6 claim 2 list) — see Scope item 2.
- `megaplan/handlers/execute.py:144-155` (tier_map consumption).
- `megaplan/_pipeline/profile.py:48-57` (`Profile.model_for`, currently test-only).
- `megaplan/_pipeline/types.py:133-183` (`StepContext.profile`, `Step` protocol `slot`); `megaplan/_pipeline/run_cli.py:318-324` (profile → `ctx.profile` as plain dict).
- `megaplan/pipelines/creative/steps.py:25-53`, `megaplan/pipelines/doc/steps.py` (the stub steps / false proof); `megaplan/pipelines/creative/__init__.py` (registration shape for the new pack); `megaplan/_pipeline/registry.py:53` (`_BUILTIN_NAMES`, discovery).

## Anti-scope

- Does **not** touch planning's profile content.
- **No execution-model changes** (auto.py, subprocess→in-process is m3).
- **No pack relocation** (planning → `pipelines/planning/` is m4).
- No `HandlerContext` / typed-config work (m5); no env-var hoisting; no realization backends (m6).
- Not collapsing the split-brain routing (`_label_for`/`_gate_next_step`, m4).
