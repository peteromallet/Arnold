# Turn the feedback step into a real AI-rated phase

## Goal

The `--with-feedback` flag (already shipped in commit `e7555135`) currently dispatches a mechanical scaffolder that writes an empty `feedback.md` and transitions to DONE. Replace that with a real worker phase: a model (Claude `:low` by default) reads digests of every artifact in the plan dir, rates each workflow stage 0-10 with a comment, and writes a populated `feedback.md`. User can still edit afterward — AI ratings live in parallel `ai_*` fields so user edits are distinguishable from model output.

## Why

`feedback.md` is supposed to be the corpus that flows back into rubric/profile tuning (the `--min-rating` / `--max-rating` search filters in `feedback.py` make this explicit). Empty templates that the user has to manually rate after every run never get filled in. An auto-rated draft that the user reviews/overrides is the difference between "feature shipped" and "useful data corpus."

## What's already in place (don't reinvent)

- **State machine** — `STATE_EXECUTED → review → STATE_REVIEWED → feedback → STATE_DONE`. Done.
- **`--with-feedback` flag wiring** — `megaplan/cli.py` (init parser), `megaplan/handlers/init.py` (persistence), `megaplan/_core/workflow.py` (`_with_feedback_from_state`, workflow patching). Done.
- **Existing handler dispatch** — `handle_feedback` at `megaplan/cli.py:1324` has a `workflow` operation branch (`cli.py:1386-1412`) that's currently the no-op scaffolder. Replace its body.
- **Auto driver** — `megaplan/auto.py` already routes `feedback` as a phase via `_phase_command`. Done.
- **Schema** — `megaplan/feedback.py`: `STAGES`, `_STAGE_BLURBS`, `StageFeedback(rating, comment)`, `PlanFeedback(overall, stages)`, `render_template`, `parse_feedback`, `load_feedback`. Extend, don't replace.
- **44 existing tests** in `tests/test_with_feedback.py`. Most stay valid; the workflow-mode handler test that asserts "no subprocess.run" gets revised (now it DOES call a worker — but never opens `$EDITOR`).

## What to build

### 1. Extend `feedback.py` schema with AI provenance fields

`megaplan/feedback.py`:

- Add `ai_rating: int | None` and `ai_comment: str | None` fields to `StageFeedback`. Default both `None`.
- `is_empty` should still return True when ALL four fields are unset.
- `to_dict` emits all four (`rating`, `comment`, `ai_rating`, `ai_comment`).
- Extend `render_template` to accept an optional `prefilled: PlanFeedback | None` arg. When provided, write `ai_rating:` / `ai_comment:` for each stage from the prefilled data. The user-editable `rating:` / `comment:` lines stay blank.
- Extend `parse_feedback` to parse both pairs of fields. Each section now recognizes `ai_rating:` / `ai_comment:` AND `rating:` / `comment:`.
- Add `effective_rating(stage_feedback) -> int | None` helper: returns `rating` if set, else `ai_rating`. Used by search filters so `--min-rating 7` matches AI-rated runs the user hasn't touched yet.
- Update `_filter_feedback_rows` in `cli.py:1240` to use `effective_rating` instead of hardcoded `rating` lookup.

### 2. New prompt module — `megaplan/prompts/feedback.py`

Build the prompt from per-stage artifact digests. The handler passes in the plan_dir + state; the prompt module reads what's there and assembles digests.

Structure:

```
build_feedback_prompt(plan_dir, state) -> str
```

Each digest is 2-5 sentences summarizing what the phase produced:
- **prep** (if `prep.json` exists): research scope + key findings
- **plan** (`plan_v*.md`): final plan summary, iteration count
- **critique** (`critique_output.json` / `critique_v*.json`): flag count, top issue categories
- **revise** (plan diffs across versions): what changed v1→vN
- **gate** (`gate.json`): recommendation + passed
- **finalize** (`final.md`): task count, batches
- **execute** (`execution.json`, `execution_audit.json`, `tasks/<task_key>/execution.json`): tasks done/skipped/blocked, task progress, files changed
- **review** (`review.json`): verdict, summary
- **Run meta** (always): robustness, profile, iteration count, total cost from `state["meta"]["total_cost_usd"]`, history durations per phase

Stages that didn't run (because of robustness) are listed as "did not run" and not requested for rating.

The prompt itself:

```
You are a retrospective evaluator. Your job is to rate the quality of each
phase of a completed megaplan run.

This rating feeds into rubric tuning. Be honest. Errors of leniency cost
more than errors of severity — if a phase produced mediocre output that
later phases worked around, mark it ~5, not ~8.

Rate quality only, not cost-effectiveness. A great run that burned $50 is
still a 9 if the output is excellent. A cheap run with sloppy output is
not a 9 because it was cheap.

Scale (0-10):
- 10: textbook; no notes.
- 8: solid; minor polish only.
- 6: workable but with real issues — wasted iterations, missed flags,
     over/under-engineering.
- 4: degraded; the phase didn't do its job, downstream had to compensate.
- 2: actively harmful; produced output that hurt later stages.
- 0: complete failure.

Per-stage rubric:
- prep: did research surface useful info, or was it filler?
- plan: did the plan structure the work appropriately?
- critique: did it catch real issues, or stamp / over-flag?
- revise: did revise actually address critique flags?
- gate: was the decision well-calibrated?
- finalize: did the final plan land cleanly?
- execute: did the executor follow the plan? Add/remove unnecessary scope?
- review: did review catch real issues, or rubber-stamp?

Overall: weighted impression of run quality.

Each comment must be one sentence — what specifically drove the rating.

[digests follow]

Respond with strict JSON only:
{"overall": {"rating": int, "comment": str},
 "stages": {"<stage>": {"rating": int, "comment": str}, ...}}

Only include stages that actually ran.
```

### 3. Handler — `handle_feedback` workflow branch

Replace the body at `megaplan/cli.py:1386-1412`. New flow:

1. Verify `current_state == STATE_REVIEWED`. (Already done; keep.)
2. If `feedback.md` exists AND any user fields (`rating:` / `comment:`) are populated AND `--force` is NOT set: skip the AI pass entirely. Just transition to DONE. (Respects manual override.)
3. Otherwise: build prompt via `build_feedback_prompt(plan_dir, state)`, dispatch through the standard worker path used by other prompt-based phases (critique/review are the references). The phase model resolves through the same profile/slot mechanism — see (5).
4. Parse the model's JSON response. On parse failure or schema violation: log a warning, write a feedback.md with EMPTY `ai_*` fields (so user can still rate manually), transition to DONE. Don't fail the phase — feedback failure must never sink an otherwise-done plan.
5. Render `feedback.md` via the extended `render_template(name, idea=..., prefilled=parsed_feedback)`.
6. Atomic write. Transition state to DONE.
7. Return `StepResponse` with `feedback_path`, `feedback_present: True`, `ai_filled: bool`, `state: "done"`.

`--force` flag: add to the `feedback` subparser. Means "regenerate `ai_*` fields even if `feedback.md` already exists; never touch user `rating:`/`comment:` fields." When --force is set on a `feedback.md` that has user fields, preserve them — only overwrite `ai_*`.

### 4. Worker dispatch

Look at how `handle_critique` or `handle_review` dispatch their worker calls. Same pattern: resolve phase model from profile, build worker, call, get text back, parse. The new phase name is `feedback`. Use the existing infrastructure — `megaplan/workers.py` and friends.

### 5. Profile slots

Every profile in `megaplan/profiles/` gets a `feedback` key. Default model: Claude at `:low` across every tier. Exact specs:

- `basic.toml`: `feedback = "claude:low"`
- `led.toml`: `feedback = "claude:low"`
- `thoughtful.toml`: `feedback = "claude:low"`
- `premium.toml` (claude variant): `feedback = "claude:low"`
- `premium.toml` (codex variant): `feedback = "claude:low"` (intentional — feedback is fixed-vendor for cross-run comparability)
- `super-premium.toml` / `poirot.toml` / `standard.toml` (vendor-locked): `feedback = "claude:low"`
- `all-claude.toml`: `feedback = "claude"` (matches the no-suffix convention)
- `all-codex.toml`: `feedback = "claude:low"` (cross-vendor — feedback is independent of run vendor)
- Detective-cluster legacy profiles (`marlowe-*`, `spade-*`, `holmes-*`, `watson-*`, `nancy`): `feedback = "claude:low"`
- All-deepseek profiles, `all-open`: `feedback = "claude:low"` (only premium phase in an otherwise-open run; the cost is acceptable because feedback runs once per `--with-feedback` plan)

**`--vendor` flag does NOT affect feedback** — feedback stays Claude regardless of which premium vendor is doing plan/critique/etc. This is the cross-comparability principle: a `thoughtful @claude` run and a `thoughtful @codex` run should be rated by the same evaluator.

**`--critic` flag does NOT extend to feedback** — feedback isn't a critic-family phase even though it looks adjacent. Kimi/cross critic still overrides critique+review only.

**`--depth` flag DOES affect feedback** — same as other author/critic phases, depth rewrites the `:low` suffix to whatever was passed. (Asymmetry principle: feedback is sense-check-style, so probably plateau at `:low`, but honor the flag for the rare case someone wants `:medium`.)

Actually — feedback should probably NOT scale with `--depth` either. It's a calibration phase; if the depth differs across runs, the ratings aren't comparable. Lock at `:low`, ignore `--depth`. Make this explicit in the help text. Use `--phase-model feedback=claude:medium` as the surgical escape hatch if someone really needs it.

### 6. Filter helper update

`megaplan/cli.py:1240` (`_filter_feedback_rows`) currently reads `fb["overall"]["rating"]`. After the schema extension, it should read `effective_rating(fb["overall"])` — falling back to `ai_rating` when `rating` is None. Same for the `--stage` filter at `cli.py:1259`.

### 7. Tests

Revise existing tests in `tests/test_with_feedback.py`:

- Workflow tests (state transitions) — no change.
- Handler test that asserts "no subprocess.run" → revise to "no $EDITOR launched" (the worker call IS a subprocess but it's a model worker, not an interactive editor).

Add new tests in `tests/test_feedback_phase.py`:

- **Schema** — `StageFeedback` with only `ai_rating` set serializes correctly; `effective_rating` falls back appropriately.
- **Template** — `render_template(..., prefilled=fb)` produces a file with `ai_rating:` lines populated and `rating:` lines blank.
- **Parser** — round-trips `ai_*` fields. User-edited `rating:` doesn't clobber existing `ai_rating:`.
- **Prompt builder** — `build_feedback_prompt(plan_dir, state)` produces a prompt that mentions every stage that ran and omits stages that didn't.
- **Handler with mocked worker** — happy path: worker returns valid JSON → feedback.md gets populated `ai_*` fields, state transitions to DONE.
- **Handler with malformed worker output** — parse fails → empty `ai_*` template written, state still transitions to DONE, no exception.
- **Handler with existing user-edited feedback** — `--force` rewrites `ai_*` only, leaves user `rating:` / `comment:` intact.
- **Handler idempotency** — second run without `--force` on a populated feedback.md is a no-op.
- **Filter with AI ratings** — `--min-rating 7` matches a plan with `ai_rating: 8` and no user rating.

## Out of scope

- Don't change the workflow state machine or the `--with-feedback` flag wiring (already shipped).
- Don't add a free-form "what would I do differently" paragraph. The per-stage `comment:` fields are the qualitative output channel.
- Don't make the rating cost-aware. The model sees total cost in the run-meta digest as context but is explicitly told NOT to factor it into ratings.
- Don't auto-push parsed AI feedback to the DB. The existing `_push_feedback_to_db` path fires on interactive `feedback edit` only; that's fine. (Optional extension: push on workflow-mode completion too. Discuss before doing.)
- Don't re-run `feedback` automatically on later plan edits. Once feedback ran for a `done` plan, it's done unless `--force`.

## Invariants

- `feedback.md` schema stays backward-compatible. Old files with only `rating:` / `comment:` still parse correctly and the new `ai_*` fields default to `None`.
- A feedback phase failure (worker error, parse failure, schema violation) NEVER sinks the plan — write an empty `ai_*` template and transition to DONE.
- The mechanical scaffolder behavior is preserved when the worker dispatch fails: user still gets a `feedback.md` they can fill in by hand.
- Existing `feedback edit/show/search` operations stay interactive — only the workflow-mode dispatch changes.

## Acceptance

- `megaplan init <idea> --project-dir . --with-feedback --profile thoughtful` initializes correctly.
- `megaplan auto --plan <name>` runs feedback as a real phase, dispatches a Claude:low worker, parses output, writes a populated `feedback.md` with `ai_rating` / `ai_comment` per stage and Overall.
- `megaplan feedback show --plan <name>` shows the AI ratings.
- User edits `feedback.md`, fills `rating:` on a stage → `megaplan feedback show` reflects the user value (via `effective_rating`).
- `megaplan feedback search --min-rating 7` matches AI-rated runs the user hasn't touched.
- Existing 44 tests in `test_with_feedback.py` still pass (revised where needed).
- All new tests in `test_feedback_phase.py` pass.
