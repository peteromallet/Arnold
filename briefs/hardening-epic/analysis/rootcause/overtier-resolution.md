# Root cause — Model resolution / where the driver model is chosen

**Lens:** how a milestone's `profile`/`vendor`/`depth` becomes the concrete
model run on every orchestration turn, and why premium ran on every turn
regardless of difficulty.

## 1. profile/vendor/depth → concrete model (the trace)

**chain.yaml → CLI flags.** Each milestone's `profile`/`vendor`/`depth` are
parsed (`megaplan/chain/__init__.py:202–217`) and forwarded verbatim as
`--profile / --vendor / --depth` to the per-milestone `megaplan` subprocess:

```python
# megaplan/chain/__init__.py:825-830
if profile:
    args.extend(["--profile", profile])
if vendor:
    args.extend(["--vendor", vendor])
if depth:
    args.extend(["--depth", depth])
```

**profile → per-phase model map.** `apply_profile_expansion` loads the profile
TOML, resolves vendor/depth, and expands the profile's **phase keys** into
`--phase-model` entries on `args` (`megaplan/profiles/__init__.py:1506,
1544–1546, 1668/1705 phase_models.append`). The profile is a flat phase→spec
table — e.g. `premium.toml:33–46`:

```toml
plan = "claude:low"   prep = "claude:low"   critique = "claude:low"
revise = "claude:low" gate = "claude:low"   finalize = "claude:low"
execute = "claude:low" ...
```

`--vendor codex` flips every `claude:low` slot to `codex:low`; `--depth`
rewrites only the author-side phases. The result is one fixed spec **per phase
name**.

**phase spec → agent+model.** Every phase handler calls
`worker_module.resolve_agent_mode(step, args)`
(`megaplan/workers/_impl.py:2313`). It looks up the entry whose key equals the
**step/phase name** in `args.phase_model` and parses it into agent/model/effort
(`_impl.py:2351–2360`). The only input is the phase name — there is no
per-turn or per-difficulty signal.

## 2. Resolved once per plan, or per phase? → **per phase, fixed spec.**

The model is resolved **once per phase invocation** from a **single fixed
profile spec**, then reused for every agent turn inside that phase. The phase
spec (`claude:low`) is the same on turn 1 and turn 20. Proof: `resolve_agent_mode`
keys solely off `step` + the static `args.phase_model` map (`_impl.py:2345–2386`);
nothing in that path consults task count, difficulty, or turn index.

## 3. Why premium runs on EVERY turn regardless of difficulty

Because the flat profile spec is the **only** routing input for orchestration
phases. The harness has exactly ONE difficulty-aware routing mechanism, and it
is scoped to `execute` alone:

- The `[profiles.*.tier_models.execute]` table (`premium.toml:48–53`,
  `variable-codex.toml:43–48`) maps complexity tier 1–5 → model.
- It is consumed **only** in the execute batch dispatcher
  (`megaplan/execute/batch.py:527–537`):

```python
if tier_map:
    batch_complexity = compute_batch_complexity(finalize_data, batch_task_ids)
    tier_spec = tier_map.get(batch_complexity)
    if tier_spec:
        tier_agent, tier_mode, tier_model = _resolve_tier_spec(args, tier_spec)
        agent, mode, model = tier_agent, tier_mode, tier_model
```

`tier_map` is read from `tier_models["execute"]` and nowhere else
(`megaplan/handlers/execute.py:149–154`). The driver phases — **plan, prep,
critique, critique_evaluator, revise, gate, finalize, review, tiebreakers** —
have no `tier_models` table and never call `_resolve_tier_spec`. They take their
flat profile spec unconditionally. On a `premium` milestone every one of those
is `claude:low` (premium Claude), so every orchestration turn of a mechanical
milestone runs premium — even when the milestone's whole job is a grep.

The model is effectively fixed at milestone init: the profile is chosen in
chain.yaml and frozen into `state.config.profile` (recovered by
`apply_profile_expansion` at `megaplan/profiles/__init__.py:1532–1533`); from
there every phase deterministically re-derives the same fixed spec.

## 4. The single injection point that is missing

`worker_module.resolve_agent_mode(step, args)`
(**megaplan/workers/_impl.py:2313**) is the one chokepoint every phase routes
through. Execute alone *pre-empts* it via the tier table + `_resolve_tier_spec`
(`execute/batch.py:79–98, 527–537`) using `compute_batch_complexity`
(`megaplan/_core/io.py:133`). A symmetric "tier this phase by its assessed
difficulty" hook — generalising `tier_models` beyond `execute`, or a
per-milestone difficulty score consulted in `resolve_agent_mode` /
`apply_profile_expansion` before the flat phase spec is written — is exactly
where difficulty-aware driver routing *could* live but currently does not. As
built, profile selection is the only knob, and it is per-milestone, not
per-turn or per-difficulty.
