# Add `--with-feedback` flag to `megaplan init`

## Goal

Add a `--with-feedback` flag on `megaplan init` that mirrors the shape of `--with-prep`. When set, the workflow grows one extra step after `review`: a `feedback` step that scaffolds `feedback.md` for the user and transitions the plan to `done`. The auto driver runs this end-to-end with no human gating — `feedback.md` is just left on disk for the user to fill in whenever (or ignore).

This is a state-machine surgery + CLI flag wiring job. The existing `--with-prep` implementation is the exact template — mirror it for the post-review side.

## Why

Today `feedback.md` is a passive artifact, only created when the user explicitly runs `megaplan feedback edit --plan <name>` after a plan is already `done`. That means feedback collection is opt-in *after the fact* and most runs never get rated. `--with-feedback` makes scaffolding part of the standard pipeline: the file is waiting for the user at the end of every run that asked for it, with zero workflow disruption.

## Existing pieces (don't reinvent)

- **`--with-prep` flag** — `megaplan/cli.py:1496-1507`. The shape to copy.
- **Persistence pattern** — `megaplan/handlers/init.py:165-166` reads `args.with_prep` and writes `state["config"]["with_prep"] = True`.
- **Workflow patching** — `megaplan/_core/workflow.py:191-200` (`_with_prep_from_state`) + `:221-237` (`_workflow_for_robustness` accepts `with_prep` and reinstates the default `STATE_INITIALIZED → prep` transition that light/standard/tiny otherwise override away).
- **Feedback module** — `megaplan/feedback.py`. `render_template` + `feedback_path` + `load_feedback` already exist. Don't touch the parsing/scaffolding logic.
- **Feedback CLI handler** — `megaplan/cli.py:1321` (`handle_feedback`). Currently dispatches `edit` / `show` / `search` operations; `edit` opens `$EDITOR`. We need a new non-interactive workflow-mode path.
- **Auto driver phase dispatch** — `megaplan/auto.py:312` (`_phase_command`). Uses `shlex.split(next_step)` for the fallback, so `"feedback"` is already callable as `megaplan feedback` with no change.

## What to change

### 1. CLI flag

`megaplan/cli.py:1496` — add `--with-feedback` on the `init` subparser, right after `--with-prep`. Mirror help text:

> Force the visible feedback phase into the workflow regardless of `--robustness`. By default no feedback step runs; this flag adds a `feedback` step between `review` and `done` that scaffolds `feedback.md` (a per-stage ratings template) for the user to fill in afterward. Runs non-interactively under `megaplan auto` — never blocks on human input.

### 2. Persistence

`megaplan/handlers/init.py:165` — add a parallel `if getattr(args, "with_feedback", False): state["config"]["with_feedback"] = True` block right next to the existing `with_prep` one.

### 3. New state `STATE_REVIEWED`

`megaplan/types.py` — add `STATE_REVIEWED = "reviewed"` alongside the other `STATE_*` constants. Export it from wherever the other workflow states are re-exported.

### 4. Workflow patch

`megaplan/_core/workflow.py`:

- Add `_with_feedback_from_state(state)` next to `_with_prep_from_state` (line 191). Read `config.get("with_feedback", False)`.
- Thread `with_feedback: bool = False` through `_workflow_for_robustness` (line 221) alongside `with_prep`.
- When `with_feedback` is set, patch:
  - `merged[STATE_EXECUTED] = [Transition("review", STATE_REVIEWED)]`
  - `merged[STATE_REVIEWED] = [Transition("feedback", STATE_DONE)]`
  
  Apply this AFTER the robustness overrides merge, the same way `with_prep` reinstates `STATE_INITIALIZED → prep` at line 235. This is critical: light/tiny set `STATE_EXECUTED: []` (line 108) to skip review, so we have to undo that override after the merge.
- Thread `with_feedback=_with_feedback_from_state(state)` into both `workflow_transition` (line 280) and `workflow_next` (line 295), matching the existing `with_prep` calls.
- Update `workflow_includes_step` (line 262) to take `with_feedback` too. Callers in `handlers/execute.py:150` and `handlers/review.py` will need it.

### 5. Light/tiny short-circuit fix

`megaplan/handlers/execute.py:150` currently force-jumps `STATE_EXECUTED → STATE_DONE` when `workflow_includes_step(robustness, "review")` is false. Extend this so it doesn't fire when feedback is in the workflow — i.e. add `or workflow_includes_step(robustness, "feedback", with_feedback=...)`. Read `with_feedback` off `state["config"]` the same way the surrounding code reads `with_prep`-style flags.

`megaplan/handlers/review.py:223,250` — currently both return `STATE_DONE`. When `with_feedback` is set, return `STATE_REVIEWED` instead. Read the flag off `state["config"]`.

### 6. Workflow-mode `handle_feedback`

`megaplan/cli.py:1321` (`handle_feedback`). Today the function dispatches on `args.operation` ∈ {`edit`, `show`, `search`}, defaulting to `edit`. When called from `megaplan auto`, no operation is passed and the auto driver expects a phase that:

1. Loads the plan state (`load_plan`).
2. Verifies `current_state == STATE_REVIEWED`. If not, error out cleanly (this branch only fires in workflow mode).
3. Scaffolds `feedback.md` from the template if it doesn't exist (reuses `render_template` + atomic write, same as today's `edit` path).
4. **Does NOT open `$EDITOR`. Does NOT prompt. Does NOT block.**
5. Transitions state to `STATE_DONE` and persists.
6. Returns a normal `StepResponse` with the `state` set to `done`, `feedback_path` populated, and a short summary message ("scaffolded feedback.md — fill in whenever").

The dispatch rule: when `getattr(args, "operation", None)` is None AND the plan's `current_state == STATE_REVIEWED`, take the workflow path. Otherwise fall through to existing `edit`/`show`/`search` behavior.

Alternatively: add a hidden `--workflow` operation choice that the auto driver passes. The argparse default for `operation` is currently `"edit"`, so the cleanest path is probably making the auto driver pass `--operation workflow` (or similar) explicitly. Pick whichever shape stays cleanest given the existing argparse setup — both are fine.

### 7. Auto driver

`megaplan/auto.py` — `_phase_command` already handles `"feedback"` via `shlex.split`, so no change there if we route through default args. If we adopt the explicit operation flag in (6), update `_phase_command` to emit `["feedback", "<operation-name>"]` (or `["feedback", "--workflow"]`) when `next_step == "feedback"`.

Also: verify the terminal-state handling at `auto.py:879` (the `STATE_DONE` mapping) still trips correctly after the new step lands — once feedback completes, state is `done` and auto should exit cleanly with `status="done"`.

### 8. Tests

Add tests covering:

- **Workflow shape** — assert `workflow_includes_step(robustness, "feedback", with_feedback=True)` is True at every robustness level (tiny, light, standard, robust, superrobust); False when `with_feedback=False`.
- **State transitions** — given `STATE_EXECUTED` with `with_feedback=True`, `workflow_transition(state, "review")` returns `STATE_REVIEWED`; from `STATE_REVIEWED`, `"feedback"` returns `STATE_DONE`.
- **Persistence** — `init` with `--with-feedback` writes `config.with_feedback = True`.
- **Handler** — calling `handle_feedback` in workflow mode on a plan in `STATE_REVIEWED` scaffolds the file, transitions to `STATE_DONE`, and does NOT call `subprocess.run` (no editor).
- **Light/tiny + with-feedback** — at robustness=`light` with `with_feedback=True`, the execute handler's short-circuit does NOT fire; review runs; feedback runs; plan reaches `done`. Same for `tiny`.
- **Auto end-to-end** — `megaplan auto` on a `--with-feedback` plan reaches terminal state `done` with `feedback.md` present and no human-required outcome.

### 9. Docs

- Update `megaplan/cli.py` help text for the flag (covered above).
- If there's user-facing docs for `--with-prep` (search `docs/` and the rubric file), add a parallel paragraph for `--with-feedback`.

## Out of scope

- Don't change the `feedback.md` template format or the parser.
- Don't change the existing `edit`/`show`/`search` operations — they stay interactive.
- Don't add a "pause for human" / `STATE_AWAITING_HUMAN` variant. Explicitly rejected — the workflow runs to `done` non-interactively.
- Don't push parsed feedback to the DB at workflow-time. That sync already happens on the next interactive `feedback edit` invocation.
- Don't auto-open `feedback.md` after auto completes. The file's there; user opens it themselves.

## Invariants to preserve

- `--with-prep` semantics must keep working unchanged (no regressions at any robustness level).
- `feedback` as a CLI subcommand (`feedback edit/show/search`) keeps its current UX. Only the workflow-mode dispatch is new.
- `STAGES` in `megaplan/feedback.py` already lists `review` — leave it. The new `feedback` workflow step is about scaffolding the file, not about adding a stage to it.
- Light/tiny robustness without `--with-feedback` keeps short-circuiting EXECUTED → DONE. The new check only fires when feedback is actually in the workflow.

## Acceptance

- `megaplan init <idea> --project-dir . --with-feedback --robustness <any>` succeeds.
- `megaplan auto --plan <name>` on that plan reaches terminal `done` without prompting, and `feedback.md` exists in the plan dir at the end.
- All existing tests pass.
- New tests above pass.
