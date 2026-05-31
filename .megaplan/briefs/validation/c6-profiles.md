# C6 Validation — Profile system pack-agnosticism (F3 foundation blocker)

Validated against CURRENT code (2026-05-28), not the drifted 2026-05-23 brief cites.

## Thesis under test
"Any pack runs under the same profile contract" is IMPOSSIBLE today because the
profile system is planning-specific. Verdict: **THESIS CONFIRMED** for the
*system-profile* path; with the important nuance that a *pipeline-local* escape
hatch already exists but the demo packs prove nothing because they never resolve
a model.

---

## Claim 1 — `VALID_PHASE_KEYS` is hardcoded to planning phase names

CONFIRMED.

`megaplan/profiles/__init__.py:24`:
```python
VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())
```

`DEFAULT_AGENT_ROUTING` is defined in `megaplan/types.py:387-402` and is exactly the
planning phase set: `plan, prep, critique, critique_evaluator, revise, gate,
feedback, finalize, execute, loop_plan, loop_execute, review,
tiebreaker_researcher, tiebreaker_challenger`.

`_validate_profile_map` (`profiles/__init__.py:272-294`) rejects any key not in
`VALID_PHASE_KEYS`:
```python
if phase not in VALID_PHASE_KEYS:
    _raise_invalid_profile(..., f"unknown phase '{phase}'. Valid phases: ...")
```
`_validate_tier_models` (line 369) enforces the same restriction on `tier_models`.

So a SYSTEM profile (`megaplan/profiles/*.toml`, `~/.megaplan/profiles.toml`,
`<proj>/.megaplan/profiles.toml`) physically cannot name a non-planning slot like
`outline` or `section_draft` — it fails to load with `invalid_profile`.

### NUANCE — pipeline-local profiles bypass this
`_load_pipeline_local_profiles` (`profiles/__init__.py:574-634`) deliberately
SKIPS `VALID_PHASE_KEYS` validation ("allow any slot keys", line 622-630); it only
validates that the agent token is in `KNOWN_AGENTS`. So a pack CAN ship
`pipelines/<name>/profiles/*.toml` with arbitrary slot names. The genericity hole
is therefore specifically in the SYSTEM-profile contract and in the model-resolution
path (claims 2 & 4), not in pipeline-local TOML parsing.

---

## Claim 2 — `resolve_agent_mode` does a bare `DEFAULT_AGENT_ROUTING[step]` __getitem__

CONFIRMED.

`megaplan/workers/_impl.py:2382` (inside `resolve_agent_mode`, defined at line 2313):
```python
spec = config.get("agents", {}).get(step) or DEFAULT_AGENT_ROUTING[step]
```
This is reached on the default-routing fallback branch (no `--phase-model`, no
`--hermes`, no explicit `--agent`). For an unknown pack step name (e.g. `outline`)
that is not in `DEFAULT_AGENT_ROUTING`, `config["agents"].get(step)` returns None,
so the `or` falls through to `DEFAULT_AGENT_ROUTING[step]` → **KeyError** (uncaught
here; not a `CliError`). This is the planning-shaped assumption baked into the
core dispatch resolver.

### Call-site count
`resolve_agent_mode` is called from these PRODUCTION sites (step name passed in):
- `workers/_impl.py:2489` (`run_step_with_worker`, the main dispatch entry)
- `execute/batch.py:95`
- `handlers/execute.py:58`, `:117`
- `handlers/critique.py:80`, `:96`, `:307`
- `handlers/review.py:498`, `:525`
- `handlers/gate.py:454`
- `handlers/shared.py:220`
- `loop/engine.py:518`
- `orchestration/tiebreaker.py:131`
- `prompts/tiebreaker_orchestrator.py:133`

→ **14 production call sites**, all passing planning step names today. Every one
inherits the KeyError-on-unknown-step behaviour. None of them is reachable from the
YAML-pipeline executor (the demo packs never call `resolve_agent_mode` — see claim 4),
which is precisely why the bug is latent rather than already firing.

---

## Claim 3 — `_pipeline/profile.py` `Profile.model_for()` is slot-agnostic AND test-only (production-dead)

CONFIRMED on both counts.

`megaplan/_pipeline/profile.py:48-57`: `Profile.model_for(slot, default=None)` is a
plain `self.slots.get(slot)` lookup with a `KeyError` fallback — genuinely
slot-agnostic, no planning assumptions, no `VALID_PHASE_KEYS` coupling. `load_profile`
(line 74), `list_profile_names`, `empty_profile`, `_from_env` likewise.

Importers of `Profile` / `model_for` / `load_profile`:
- `tests/test_pipeline_integration.py:23,155-156`
- `tests/test_pipeline_mode_e2e.py:33,55,87,151,194,245-265`
- `tests/test_pipeline_elegance.py:65`

NO production module imports the `_pipeline.profile` module. The two grep hits in
production (`run_cli.py`, `profiles/__init__.py`) are the substring `_pipeline` +
the word `profile` on unrelated lines — `run_cli.py:178-183` imports
`resolve_pipeline_profile` from `megaplan.profiles` (the planning loader), and
`profiles/__init__.py` references the pipeline-profiles *directory path*. The
production YAML executor uses the resolved profile as a plain `dict[str,str]`
(`run_cli.py:322`, `StepContext.profile=resolved_profile`), never the `Profile`
class. So `Profile.model_for` is **production-dead** — the one slot-agnostic
abstraction is exercised only by tests.

---

## Claim 4 — creative/doc pack steps are STUBS that never resolve a model

CONFIRMED. This is the "false proof-of-genericity."

`megaplan/pipelines/creative/steps.py` (`CreativeStep.run`, lines 25-53): renders a
prompt to markdown, writes `v{n}.md` + `prompt_v{n}.md`, records the artifact path.
It declares `slot: str | None = None` (line 20) but NEVER reads it and NEVER
dispatches a worker.

`megaplan/pipelines/doc/steps.py` (`OutlineStep`, `SectionDraftStep`, `CritiqueStep`,
`ReviseStep`, `AssemblyStep`): each `run` just `mkdir`s and writes an empty/JSON
file. All carry `slot: str | None = None` and none calls a worker.

Hard confirmation: `grep -rn "model_for|run_step_with_worker|resolve_agent_mode|
run_claude_step|run_codex_step|run_worker|dispatch"` over both pipeline dirs returns
**zero matches** (exit 1). The packs "work with arbitrary profiles" ONLY because
they never resolve a model — the profile dict passed via `ctx.profile` is inert.
The brief's characterization is exactly right.

---

## ASSESSMENT — work to make profiles genuinely pack-agnostic; is it a pre-Phase-0/Body-1 blocker?

**Yes, correctly a foundation (pre-Phase-0 / Body-1) blocker.** A pack that actually
dispatches a model — which any real non-planning pack must — would hit two hard
walls: (a) it cannot express its slots in a system profile (`VALID_PHASE_KEYS`
rejection, claim 1), and (b) the moment its step calls into the core dispatch
resolver it KeyErrors on `DEFAULT_AGENT_ROUTING[step]` (claim 2). The only working
abstraction, `Profile.model_for`, is fenced off in test-only code (claim 3). The
demo packs hide all of this by never resolving a model (claim 4), so "it works"
today is an artifact of stubs, not a real contract.

**Sizing (rough, medium confidence):**
- *Decouple `VALID_PHASE_KEYS`*: make slot validation per-pack (validate against the
  pack's declared stage IDs, not the planning frozenset) for the system-profile path,
  or formally bless the pipeline-local path as the only profile source for non-planning
  packs. Small-to-medium: `profiles/__init__.py` already has the pipeline-local
  bypass; the work is making system-profile loading pack-parameterized and updating
  the validators (`_validate_profile_map`, `_validate_tier_models`) to take a
  slot-key set. ~0.5–1 day.
- *Make dispatch slot-resolution non-KeyError*: route pack steps through
  `Profile.model_for` (promote `_pipeline/profile.py` out of test-only into the
  executor) OR give `resolve_agent_mode` a pack-supplied routing table with a
  fail-loud-but-typed error instead of bare `__getitem__`. Touches the dispatch
  resolver + 14 call sites' assumptions, plus a real (non-stub) pack step to prove
  it. Medium: ~1–2 days incl. a genuine end-to-end pack that dispatches.
- *Replace the false-proof demo packs* with at least one pack whose step actually
  calls `ctx.profile.model_for(slot)` and dispatches a worker — this is the
  acceptance test for the whole F3 claim. ~0.5 day.

Total ~2–3.5 days of focused work; it is genuinely upstream of any feature that
assumes "any pack runs under the same profile contract," so gating Body-1 on it is
correct.

**Is the brief right that the demo packs are a false proof-of-genericity?** Yes,
unambiguously. They never resolve a model, so they exercise none of the
planning-coupled machinery (`VALID_PHASE_KEYS`, `DEFAULT_AGENT_ROUTING`,
`resolve_agent_mode`). They prove the *executor* is generic, not the *profile
contract*.

### Unknown-unknown / watch-item
The recent commits "profile default" and "codex execute tier map pins models"
touched `tier_models` (`profiles/__init__.py:360-403`, `_swap_premium_spec`
capability map at `:1195-1236`). `tier_models` is ALSO `VALID_PHASE_KEYS`-gated
(line 369) AND hardcodes a planning-specific `execute` tier ladder — a second,
separately-coupled surface a pack-agnostic refactor must also unbind (tier maps are
keyed by planning phase + a 1..5 tier that is meaningful only for the execute
complexity adjudication). Not in the brief's enumerated list; budget for it.
