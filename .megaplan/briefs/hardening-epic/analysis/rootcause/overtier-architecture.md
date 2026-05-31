# Root-cause lens: architectural capability for differential driver tiering

**Verdict:** Per-phase model tiering already exists and is fully wired. Per-*difficulty*
tiering exists too — but only the **execute** phase consumes it. Nothing structural blocks
extending it to the plan/critique/review *driver*; the schema already validates tier maps
for every phase. The over-tiering is a wiring gap, not an architectural limit.

## 1. Different models per phase — already independently tierable

Each phase is its own `Stage`/`Step` carrying a `slot` (the phase name), and the model is
resolved per-step at dispatch, not bound to one milestone-wide driver.

- Builder makes each phase a distinct stage with its own `_worker`/`slot`
  (`megaplan/_pipeline/builder.py:138-153`, `:205-228`).
- The slot→model lookup is per-slot: `Profile.model_for(slot)`
  (`megaplan/_pipeline/profile.py:48-57`). Profiles are keyed by phase name —
  `plan/prep/critique/revise/gate/finalize/execute/review/...`
  (`.megaplan/profiles.toml:1-13`).
- At runtime the *driver* model for a phase is resolved per-step by
  `resolve_agent_mode(step, args)` (`megaplan/workers/_impl.py:2313`), reading
  `phase_model[step]` then `config.agents[step]` then `DEFAULT_AGENT_ROUTING[step]`
  (`:2351-2386`). Called once per phase from `_run_worker` at
  `megaplan/handlers/shared.py:219-224`.

So phases are NOT bound to one driver — they are already independently selectable. What is
*missing* is any branch that picks a **cheaper driver when the phase is mechanically easy**.

## 2. The execute split (premium driver, cheap workers) — where it lives

The driver/worker split is real and one-directional today:

- `execute.py` detects `tier_models.execute`, a `dict[int,str]` mapping complexity
  tier 1-5 → worker model, and passes it down as `tier_map`
  (`megaplan/handlers/execute.py:149-154`, then `:175`/`:190`).
- The tier map only routes the per-batch **execute worker** (`tier_map` consumed in
  `megaplan/execute/batch.py:79` `_resolve_tier_spec`, mirrored in
  `megaplan/handlers/execute.py:44` `_resolve_execute_tier_spec`).
- **Why it doesn't extend to plan/critique/review:** grep confirms no other handler reads
  `tier_map`/`tier_models` — `plan.py`, `critique.py`, `review.py`, `gate.py` never
  reference it. Those phases go straight through `resolve_agent_mode`
  (`shared.py:220`), which has no tier/complexity input at all. The *driver* for every
  non-execute phase is a single static slot value.

## 3. Existing difficulty signal that could feed driver selection

Yes — finalize already adjudicates a per-task complexity tier 1-5 with required
justification and hard reject:

- `megaplan/handlers/finalize.py:264-274` — rejects any task lacking integer
  `complexity` in 1..5 or a non-empty `complexity_justification`.
- `_normalize_task_complexity` defaults missing scores to tier 4
  (`finalize.py:559-591`).

That signal is **per task**, and today only feeds the *execute worker* tier map (§2). It is
the natural input for a driver-tier decision, but no code currently aggregates it to a
milestone/phase-level driver choice.

## 4. Minimal architectural change

The schema is already broader than its consumers. `tier_models.<phase>.<tier>` is parsed and
validated for **any** phase in `VALID_PHASE_KEYS` (the full routing set), not just execute:

- `megaplan/profiles/__init__.py:360-397` `_validate_tier_models` accepts any
  `phase in VALID_PHASE_KEYS` (`:24` = `DEFAULT_AGENT_ROUTING.keys()`).
- Vendor swap already rewrites tier entries for every phase
  (`profiles/__init__.py:1261-1272`).

So the minimal change is **wiring an existing signal, not a new knob**:

1. In `resolve_agent_mode` (or a thin wrapper at `shared.py:219-224`), when
   `args.tier_models[step]` exists, select the spec by a milestone difficulty score
   instead of the static slot — exactly mirroring `execute.py:149-154`.
2. Feed it the difficulty signal: reuse the finalize complexity tiers (§3), aggregated
   per phase (e.g. max task complexity), or gate it on the M0 characterization result so a
   cheap driver is credited unless work is no-safe-recovery.

No new dataclass, no schema migration, no executor change (the executor is model-agnostic by
design — `profile.py:13-23`). It is the same `tier_map` pattern already proven on execute,
applied at the per-phase driver-resolution seam.

## 4-line summary
- Differential per-phase tiering is fully supported: each phase resolves its own model via
  `resolve_agent_mode(step)` / `Profile.model_for(slot)` — not one bound driver.
- Per-difficulty tiering already exists but is consumed only by the execute *worker*
  (`tier_models.execute`, `execute.py:149-154`); plan/critique/review drivers ignore it.
- A difficulty signal already exists (finalize complexity tier 1-5, `finalize.py:264-274`)
  and the `tier_models.<phase>` schema already validates non-execute phases.
- Minimal change = wire that signal into the per-phase driver resolution
  (`shared.py:219` / `_impl.py:2313`), reusing the existing execute tier_map pattern — no
  new knob, no executor change.
