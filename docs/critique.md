# Adaptive critique — operational guide

This page documents the layered defense added in PR #52 (May 2026) so the
silent-fallback bug class that hid the original adaptive-critique
regression cannot recur.

## Background

`partnered` / `premium` / `apex` profiles set `adaptive_critique = true`.
On every iteration the critique handler asks the *evaluator* (an Opus-tier
model) which lenses to apply, then farms the lenses out to cheaper critic
models. The evaluator picks lenses with full knowledge of the plan,
flag lifecycle, prep dossier, and prior critique results — adaptive,
plan-shaped critique instead of a static 6-lens sweep.

In May 2026 a missing `critique_evaluator` entry in
`STEP_SCHEMA_FILENAMES` made every adaptive run KeyError at dispatch. A
broad `except Exception` in `megaplan/handlers/critique.py` swallowed the
error, wrote `fallback: true` to `evaluator_verdict.json`, and fell through
to the same static lens list for every iteration of every plan. Static
lenses produced reasonable-looking output, so the bug hid in plain sight
across every adaptive profile.

## Layered defense

PR #52 adds four layers so the same bug class cannot silently disable
adaptive critique again. Each layer catches the bug at a different stage:

1. **Narrow except at the critique handler.**
   `megaplan/handlers/critique.py` now only catches `(ValueError,
   RuntimeError, OSError)` from the evaluator dispatch. Structural errors
   (`KeyError` on missing step dispatch, `ImportError` on missing module,
   `AttributeError` on misshapen payload) bubble up and fail the run loudly
   instead of silently downgrading.

2. **Loud stderr banner on fallback.** When the fallback path *does* fire
   (legitimate LLM/IO failure), the handler now prints a clear banner to
   stderr including the failing exception, the static lenses being used,
   and the recommended diagnostic command (`megaplan doctor
   --adaptive-critique`). Until PR #52 the only signal was a string buried
   in `state.meta` that nobody reads interactively.

3. **Startup validation at init.** `megaplan/handlers/init.py` calls
   `assert_adaptive_critique_wired()` whenever `adaptive_critique`
   resolves True. The probe checks that `STEP_SCHEMA_FILENAMES`,
   `SCHEMAS`, the prompt template, and `_STEP_REQUIRED_KEYS` are all wired
   for `critique_evaluator`. If any layer is broken, init raises
   `AdaptiveCritiqueMisconfiguredError` *before* planning cost is paid —
   the operator sees the misconfiguration immediately.

4. **CI guard test.** `tests/test_adaptive_critique_wired.py` parametrizes
   over every shipped profile with `adaptive_critique = true` and asserts
   the wiring probe passes for each. A PR that re-introduces the original
   bug (e.g. removes the `critique_evaluator` entry from
   `STEP_SCHEMA_FILENAMES`) fails CI before merge.

## Strict mode

`execution.strict_adaptive_critique = true` opts a run into raising
`AdaptiveCritiqueDegradedError` instead of writing `fallback: true` and
proceeding with static lenses. Use this for:

- production runs where adaptive critique is load-bearing,
- CI runs that should fail if the evaluator can't be reached,
- megaplan chain runs where downstream blocks depend on the adaptive
  critique signal.

Default is **off** for backward compatibility. The `partnered`,
`premium`, and `apex` profiles do **not** set strict mode by default —
turning it on at the profile level would break existing runs that
sometimes recover from a transient evaluator failure via the static
fallback. Strict mode is opt-in per run:

```toml
# ~/.config/megaplan/config.json (or project-level)
[execution]
strict_adaptive_critique = true
```

```bash
megaplan init --adaptive-critique --strict-adaptive-critique --idea "..."
```

## The `megaplan doctor --adaptive-critique` subcommand

```bash
megaplan doctor --adaptive-critique
```

Probes every layer of the adaptive critique wiring and reports
`[OK]` / `[FAIL]` per probe. Run it whenever you suspect adaptive
critique is silently falling back. Exits 0 on healthy, 1 on any
failure. Read-only — no LLM calls, no plan-dir state.

Example output:

```
[OK]   critique_evaluator registered in STEP_SCHEMA_FILENAMES  (→ critique_evaluator.json)
[OK]   critique_evaluator.json registered in SCHEMAS
[OK]   critique_evaluator prompt template importable
[OK]   _STEP_REQUIRED_KEYS covers selections/skipped/evaluator_model

adaptive critique wiring is healthy.
```

## Error classes

Both new errors live in `megaplan/types.py` and extend `RuntimeError`:

- **`AdaptiveCritiqueMisconfiguredError`** — raised at `init` when the
  wiring probe fails. Carries `missing: list[str]` with the failing
  probe labels.
- **`AdaptiveCritiqueDegradedError`** — raised at critique time when
  `strict_adaptive_critique = true` and a runtime-recoverable failure
  fires. Carries `reason: str` with the underlying exception text.

Both are caught by the CLI runner's `(OSError, RuntimeError, ValueError)`
catch tuple and surface as run failures with their messages intact.
