# Adaptive critique — operational guide

## What adaptive critique does

When adaptive critique is on, the critique handler does **not** run a fixed
list of lenses on the profile's critique model. Instead, on every iteration
it runs a dedicated **critique-evaluator** step first. The evaluator reads the
finished plan (plus the flag lifecycle, prep dossier and coverage metrics, the
inter-version plan diff, gate signals, and prior revise resolutions on
iteration ≥ 2) and emits a verdict that decides **which lenses fire** for this
plan, this iteration — justifying every lens it skips. The selected lenses are
then farmed out to the critic model from the profile's `critique` slot.

The candidate lens pool is the fixed 9-lens catalog in
`CRITIQUE_CHECKS` (`megaplan/audits/robustness.py:22`): `issue_hints`,
`correctness`, `scope`, `all_locations`, `callers`, `prerequisite_ordering`
(the 6 `core` lenses) plus `conventions`, `verification`, `criteria_quality`
(the 3 `extended` lenses). The evaluator may additionally add up to 2 bespoke
"other" custom areas on top of the catalog (`MAX_OTHER_AREAS = 2`,
`megaplan/audits/critique_evaluator.py:25`); these run like lenses but stay out
of the 9-lens coverage accounting.

Key division of labor (`megaplan/handlers/critique.py:207-216`):

- **The evaluator decides only *which* lenses fire** — not which model runs
  them. It runs on its own routing slot (`critique_evaluator`, declared per
  profile, default depth `medium`), not escalated off the critic slot.
- **The critic model comes from the profile's `critique` slot.** `partnered`
  routes critique to cheap DeepSeek; the profile `premium` (the named tier)
  routes critique to Claude; `apex` to Codex. The
  only override is the operator pin `execution.critic_model`, which forces every
  farmed-out critic to a fixed model while the evaluator still picks the lenses.

The `critique_evaluator` slot is a vendor-neutral premium slot: it uses the
symbolic agent spec `premium` (e.g., `premium:low`) in unlocked profiles and
`DEFAULT_AGENT_ROUTING`, and resolves to the operator's selected vendor
(`--vendor claude` or `--vendor codex`) at runtime. See
[docs/configuration.md#agent-routing](configuration.md#agent-routing) for the
full routing precedence.

This is megaplan's "cheapest capable model per task" philosophy applied to
critique: premium-grade *judgment* goes into deciding and directing the
critique, while the lens-by-lens grinding can run cheap.

## When adaptive critique is on vs off

Adaptive critique is resolved per-run at `init`
(`megaplan/handlers/init.py:132-146`) with this precedence:

1. explicit `--adaptive-critique` CLI flag, then
2. an explicit `[execution] adaptive_critique` user-config setting, then
3. the profile's `adaptive_critique` metadata field, then
4. the global default, which is **`False`** (`megaplan/types.py:787`).

The shipped profiles set the field as follows (each profile's `.toml`):

| Profile | `adaptive_critique` | Source |
|---|---|---|
| `partnered` | **on** | `profiles/partnered.toml:42` |
| `premium` | **on** | `profiles/premium.toml:32` |
| `apex` | **on** | `profiles/apex.toml:36` |
| `solo` | **off** (field omitted → global default `False`) | `profiles/solo.toml` |
| `directed` | **off** (field omitted → global default `False`) | `profiles/directed.toml` |
| `all-claude`, `all-codex`, `all-deepseek-*`, `all-open`, `all-fireworks-deepseek`, `arnold-openrouter`, `variable*` | **off** (field omitted) | respective `.toml` |

So the docs' historical claim — "on for partnered/premium/apex, off for
solo/directed" — is still accurate, and the single-vendor / open-only profiles
are likewise off. Open-only profiles omit the field deliberately: there is no
premium model in those tiers to direct with, and defaulting it on would force a
premium evaluator key into an otherwise key-free setup. Force it on for any
profile with `--adaptive-critique`, or pin `[execution] adaptive_critique` in
config to override the per-profile default in either direction.

Creative mode never takes the adaptive path even when the flag resolves on
(`megaplan/handlers/critique.py:70`).

## Relationship to the robustness dial

The robustness level (`bare`/`light`/`full`/`thorough`/`extreme`) and adaptive
critique are largely independent dials:

- **`bare`** skips critique entirely — the workflow routes `plan → finalize`
  directly (`megaplan/handlers/critique.py:64-69`).
- **`light`** runs critique once but skips the separate `gate` phase; the
  handler writes a minimal `ITERATE` gate and routes straight to one revision
  pass (`megaplan/handlers/critique.py:478-494`).
- **`full`/`thorough`/`extreme`** run the full `critique → gate → revise` loop.

What robustness sets for **non-adaptive** runs is the *static* lens pool
(`checks_for_robustness`, `megaplan/audits/robustness.py:232`): `full` runs the
6 `core` lenses, `thorough`/`extreme` run all 9, `light`/`bare` run none.

When adaptive critique is **on**, the robustness count does **not** apply: the
evaluator selects the lenses from the full 9-lens catalog per iteration, so the
"6 at full / 9 at thorough" static numbers are overridden by the evaluator's
per-plan selection. Robustness still governs the surrounding workflow shape
(whether `gate`/`review`/prep/parallel critique run), just not the lens count.

## Critique vs the gate — they are different phases

The **critique** phase and the **gate** phase are distinct steps with separate
handlers. Critique runs the lenses and records flags (`STATE_PLANNED →
critique → STATE_CRITIQUED`). The **gate** is a separate downstream step
(`megaplan/handlers/gate.py`, `STATE_CRITIQUED → gate → STATE_GATED`,
`megaplan/_core/workflow_data.py:56-66`) that reads the accumulated critique
flags and signals and decides whether to PROCEED, ITERATE, ESCALATE, or call a
TIEBREAKER. The critique-evaluator (which picks lenses) is **not** the gate;
it runs *inside* the critique phase, before the critics, and only chooses which
lenses fire. `light` robustness skips the gate phase but still runs critique.

## Failure handling — retry, then block (no static fallback)

Adaptive critique is the **only** critique path once it is on: there is no
static-lens fallback within an adaptive run
(`megaplan/handlers/critique.py:156-302`). If the evaluator step fails, the
handler retries **once** (`_MAX_EVAL_ATTEMPTS = 2`). If both attempts fail it
writes a `blocked: true` `evaluator_verdict.json` and raises
`critique_evaluator_failed`, blocking the milestone loudly rather than
degrading to a hand-curated lens set. One transient failure (flaky API,
malformed first parse) is absorbed by the retry; a persistent wiring fault
surfaces as a hard error.

The raw evaluator response is persisted (per-iteration `*_v{n}` copies plus a
canonical "latest" pointer) before validation, so a rejected or deduped verdict
is inspectable post-hoc.

## History & safeguards

> Background, kept for context. The behavior above is current.

In May 2026 a missing `critique_evaluator` entry in `STEP_SCHEMA_FILENAMES`
made every adaptive run `KeyError` at dispatch. A broad `except Exception` in
the critique handler swallowed the error, wrote `fallback: true` to
`evaluator_verdict.json`, and silently fell through to a static lens list for
every iteration of every plan. Static lenses produced reasonable-looking
output, so the regression hid in plain sight across every adaptive profile.

The response (PR #52) hardened the path against that *class* of silent failure.
The current code goes further than the original "narrow the except, then fall
back" fix: the adaptive path now has **no static fallback at all** — it
retries once and blocks (see above). The remaining safeguards are:

1. **Startup wiring validation.** `megaplan/handlers/init.py:153-156` calls
   `assert_adaptive_critique_wired()` whenever `adaptive_critique` resolves
   True. The probe (`probe_adaptive_critique_wiring`,
   `megaplan/audits/critique_evaluator.py:596`) checks that
   `STEP_SCHEMA_FILENAMES`, `SCHEMAS`, the prompt template, and
   `_STEP_REQUIRED_KEYS` are all wired for `critique_evaluator`. If any layer is
   broken, init raises `AdaptiveCritiqueMisconfiguredError` *before* any
   planning cost is paid.

2. **The `megaplan doctor --adaptive-critique` subcommand.** Probes every layer
   of the wiring and reports `[OK]`/`[FAIL]` per probe. Read-only — no LLM
   calls, no plan-dir state. Exits 0 on healthy, 1 on any failure.

   ```
   [OK]   critique_evaluator registered in STEP_SCHEMA_FILENAMES  (→ critique_evaluator.json)
   [OK]   critique_evaluator.json registered in SCHEMAS
   [OK]   critique_evaluator prompt template importable
   [OK]   _STEP_REQUIRED_KEYS covers selections/skipped/evaluator_model

   adaptive critique wiring is healthy.
   ```

3. **CI guard test.** `tests/test_adaptive_critique_wired.py` parametrizes over
   every shipped profile with `adaptive_critique = true` and asserts the wiring
   probe passes for each, so a PR that re-introduces the original bug fails CI
   before merge.

## Error classes

`megaplan/types.py` defines two errors that extend `RuntimeError`:

- **`AdaptiveCritiqueMisconfiguredError`** — raised at `init` when the wiring
  probe fails. Carries `missing: list[str]` with the failing probe labels.
- **`AdaptiveCritiqueDegradedError`** — defined for the strict-mode story
  (`execution.strict_adaptive_critique`), but **not currently raised by the
  critique handler**, which now retries-then-blocks unconditionally rather than
  falling back to static lenses. See the note below.

> **Note on `strict_adaptive_critique`.** The `--strict-adaptive-critique` flag
> and `[execution] strict_adaptive_critique` config setting still exist and are
> plumbed through `init` into plan config, but because the adaptive path no
> longer has a static fallback, the handler blocks on evaluator failure
> regardless of the strict flag — and `AdaptiveCritiqueDegradedError` is never
> raised. The strict-mode machinery is effectively vestigial. Whether to remove
> it or restore a strict-vs-lenient distinction is a code decision, not a docs
> one.
