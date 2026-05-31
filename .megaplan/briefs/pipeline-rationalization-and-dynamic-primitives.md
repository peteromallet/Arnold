# Pipeline rationalization + dynamic primitives

## Goal

Take the Python composition framework that the current `python-composition-cleanbreak` sprint is delivering and rationalize what's currently a confused "mode" layer into clean pipelines + add dynamic primitives needed for the next class of pipelines users will want to build.

**Three changes, one sprint:**

1. **Split `doc`, `creative` out as their own pipelines.** They were modes-within-planning that don't fit planning's task-shaped flow. They get natural shapes.
2. **Remove `metaplan` and `joke` modes.** `metaplan` is just an alias for `doc`; `joke` is `creative --form joke`. They were never real modes.
3. **Add dynamic primitives** so a pipeline can have one stage that generates reviewer prompts/personas at runtime that downstream stages consume. Specifically: dynamic-fanout into panels.

After this sprint: `planning`, `doc`, `creative`, `writing-panel-strict`, `doc-critique`, `judges` are real first-class pipelines. `tiebreaker` stays as a subpipeline. `--mode` exists only where natural (none of the above, after this sprint). New pipelines can fan out to dynamically-generated reviewer panels.

## Prerequisites

1. **`python-composition-cleanbreak` sprint complete** (commit on `python-composition` branch, merged to main). This sprint depends on:
   - `Pipeline.builder()` fluent API
   - The pattern library (`critique_revise_gate_loop`, `panel_with_retry`, etc.)
   - `mode_prompts()` pattern (will be reused for any remaining mode-like overlays)
   - Pipeline discovery for Python modules
   - YAML runtime deleted
   - `planning` + `writing-panel-strict` already using the new patterns

Verify with `git log --oneline main | head -5` for the merge commit before kicking off.

## Locked decisions

Direct quotes from the analysis that drove this sprint:

### What each mode actually is (current state, locked diagnosis)

- **`code` mode**: the natural planning shape. Brief → plan tasks → critique → revise → gate → execute (run tasks, write code) → review. Tasks are first-class.
- **`doc` mode**: forced fit. Has its own prompt files (`prep_doc.py`, `execute_doc.py`, `review_doc.py`) — other phases share code defaults. Reinterprets "execute task" as "write doc section." Natural shape would be `outline → section drafts → critique → revise → final assembly`, no task batches.
- **`metaplan` mode**: literally an **alias for `doc`** per `cli.py:2094` ("metaplan is an alias for doc") and `bakeoff/orchestrator.py:47` (coerces metaplan → doc). Vestigial.
- **`joke` mode**: literally a shim — `execute_joke.py` is `partial(_execute_creative_prompt, form=get_form("joke"))`. It's `creative` + `form=joke`. Not a separate mode.
- **`creative` mode**: fundamentally different machinery. Has its own prompts (`critique_creative.py`, `execute_creative.py`, `revise_creative.py`), the `forms/` registry (joke, poem, stance, provocations, directors_notes), provocations content type, stance validation, director's notes sidecar. Form selection (`--form joke|poem`) is a real second axis.

### What we're building

1. **`megaplan/pipelines/doc.py`** — new pipeline using the patterns library. Natural shape: outline → section drafts → critique → revise → assembly. Moves `prompts/prep_doc.py`, `prompts/execute_doc.py`, `prompts/review_doc.py` to live near this pipeline. Removes the "doc-mode-within-planning" wiring.

2. **`megaplan/pipelines/creative.py`** — new pipeline absorbing all of: `prompts/critique_creative.py`, `prompts/execute_creative.py`, `prompts/revise_creative.py`, the `forms/` registry (joke, poem, stance validation, provocations, director's notes). `--form` becomes a first-class input on the pipeline, validated against the registered forms.

3. **Remove `metaplan` from CLI choices**. It was an alias; CLI rejects it with a clear migration message: "use `--mode doc` (now deprecated; use `megaplan run doc <brief>` instead)."

4. **Remove `joke` from CLI choices**. CLI rejects with: "joke is a creative form; use `megaplan run creative <brief> --form joke`."

5. **Deprecate `--mode` on `megaplan plan`** for one release cycle. Behavior:
   - `megaplan plan --mode code <brief>` → works, no warning (it's the default).
   - `megaplan plan --mode doc <brief>` → prints deprecation warning + redirects to `megaplan run doc <brief>` (same exit semantics).
   - `megaplan plan --mode creative <brief>` → prints deprecation warning + redirects to `megaplan run creative <brief>`.
   - `megaplan plan --mode metaplan <brief>` → prints deprecation warning + redirects to `megaplan run doc <brief>`.
   - `megaplan plan --mode joke <brief>` → prints deprecation warning + redirects to `megaplan run creative <brief> --form joke`.
   - Next release: drop `--mode` entirely.

6. **Add dynamic primitives to the pattern library**:
   - `panel_from_artifact(artifact_ref, base_template, ...)` — read N reviewers from an upstream JSON artifact; specialize the base_template per reviewer.
   - `dynamic_fanout(generator_stage, base_prompt)` — generator stage produces reviewer specs; fanout consumes them.
   - `weighted_vote(panel_output, weights)` — variant of `majority_vote` with reviewer weighting.
   - `iterate_until_consensus(panel, min_agreement=0.8)` — common loop exit when reviewers agree.
   - `paired_round(advocates, sees_other=True)` — debate-style round where each advocate sees the other's argument.

7. **Document the dynamic-prompt-generation pattern** in `docs/pipelines.md` as a worked example: "design 5 personas in a generator stage → critique panel reads them and runs 5 specialized reviewers → synth → revise." Concrete code (~30 LOC of Python).

8. **`tiebreaker` subpipeline stays as-is.** Already a subpipeline, not a mode. Already Python after the current sprint. Don't restructure.

### Where modes live in the new architecture (locked)

Modes are inline Python dicts inside the pipeline file via the `mode_prompts({...})` pattern. No separate registry. No YAML schema. After this sprint:
- `planning` has no modes (was code-only effectively after extracting doc/creative).
- `doc` may have variants if useful (`brief`, `formal`, etc.) — defer; ship without modes.
- `creative` has `--form joke|poem|...` as a first-class input (NOT a mode — different machinery per form, validated against the forms registry).
- Other pipelines: declare modes only if same topology + different prompts genuinely fits.

## Scope (in)

### Code

- `megaplan/pipelines/doc.py` (NEW) — full pipeline using patterns library. ~120 LOC.
- `megaplan/pipelines/creative.py` (NEW) — full pipeline with form dispatch. ~180 LOC including form-specific config.
- `megaplan/pipelines/doc/prompts/` (NEW directory) — move `prep_doc.py`, `execute_doc.py`, `review_doc.py` here. The Python prompts stay Python; just relocate.
- `megaplan/pipelines/creative/prompts/` (NEW directory) — move `critique_creative.py`, `execute_creative.py`, `revise_creative.py`, plus `forms/` machinery here. Forms (`joke.py`, `poem.py`, `stance.py`, `provocations.py`, `directors_notes.py`) live alongside.
- `megaplan/_pipeline/patterns.py` (EXTEND) — add `panel_from_artifact`, `dynamic_fanout`, `weighted_vote`, `iterate_until_consensus`, `paired_round`. ~200 LOC of pattern functions + tests.
- `megaplan/cli.py` — remove `metaplan`/`joke` from `--mode` choices; add deprecation handler for `--mode doc|creative` that redirects.
- `megaplan/_pipeline/planning.py` — strip mode-overlay logic that was specific to doc/creative/joke/metaplan. Keep code as the only mode (effectively no mode).
- `megaplan/bakeoff/orchestrator.py:45-57` — remove the metaplan alias and the doc-mode coercion.
- Update `megaplan/_pipeline/registry.py` so `doc` and `creative` are discovered and registered as Python pipelines.

### Tests

- `tests/pipelines/test_doc_pipeline.py` (NEW) — doc pipeline end-to-end with mocked worker.
- `tests/pipelines/test_creative_pipeline.py` (NEW) — creative pipeline with form dispatch.
- `tests/_pipeline/test_dynamic_primitives.py` (NEW) — `panel_from_artifact`, `dynamic_fanout`, `weighted_vote`, `iterate_until_consensus`, `paired_round`.
- `tests/test_mode_deprecation.py` (NEW) — `--mode doc|creative|metaplan|joke` deprecation warnings + redirects work correctly.
- Update existing tests that referenced doc/creative/joke/metaplan modes; they now call `megaplan run <pipeline>`.

### Docs

- `docs/pipelines.md` — extend with: (a) the dynamic-prompt-generation worked example, (b) doc and creative pipelines documented in their own sections, (c) "How modes work in the new system" section, (d) deprecation migration table.
- `docs/megaplan-decision.md` — verify mode references match new reality (might already be clean; audit).
- `CHANGELOG.md` — entry for the breaking changes (mode removal, redirect-to-pipeline behavior).

### Version

- Megaplan 0.22.0 → 0.23.0. Document breaking changes.

## Scope (out — anti-scope)

- **No new patterns beyond the named ones**. If the dynamic-primitives implementation surfaces an obvious missing pattern, add it; otherwise don't go fishing.
- **No restructuring of `planning`** beyond removing the doc/creative/joke/metaplan mode wiring.
- **No new pipelines** besides `doc` and `creative` extraction. (Panel-of-7, debate, etc. are future Sprint E+.)
- **No new schema** — pipelines are still Python, no YAML.
- **No changes to `tiebreaker`, `doc-critique`, `judges`, `writing-panel-strict`** beyond what their consumers force.
- **No `--mode` removal in this release** — deprecate now, drop next release. Don't break existing scripts in one step.
- **No new CLI commands**. `megaplan run <pipeline> [args]` is the existing surface.

## Open questions

These are the things the planner will need to resolve during execution; flag them up front so the answer isn't invented:

1. **Where exactly do per-pipeline prompts live on disk?** `megaplan/pipelines/<name>/prompts/` is the obvious answer; verify whether the existing prompt-loading machinery (PromptRegistry) supports per-pipeline subdirectories or needs a small update.
2. **Does `doc` need its own subpipeline mechanism for tiebreaker** (or any subpipeline)? Inherit from planning's tiebreaker subpipeline if so; design from scratch only if planning's doesn't fit.
3. **`forms/` machinery scope**: should `forms/joke.py` etc. move into `megaplan/pipelines/creative/forms/`, or stay in `megaplan/forms/` as a shared module? Lean toward MOVE (it's creative-specific) unless other pipelines depend on the registry.
4. **`primary_criterion` for creative mode**: currently a state config field used by `execute_creative.py`. Decide: does it become a `creative` pipeline input, a form-specific field, or get removed?

## Constraints

- **Backwards-compat for one release**: existing `megaplan plan --mode doc|creative|metaplan|joke` invocations must redirect cleanly with a deprecation warning. Scripts using `--mode` continue working until 0.24.
- **Forms registry must continue working**: any tool/test that imports from `megaplan.forms` must keep working OR get a clear deprecation path.
- **All existing tests pass** after the rationalization. Tests that exercise mode-specific behavior get rewritten to exercise the new pipeline-specific behavior; semantics preserved.
- **One real-model smoke run for each new pipeline** (`doc`, `creative`) on a representative brief. Manual review acceptable; not gated by automated check.

## Done criteria

1. `megaplan list pipelines` shows `doc` and `creative` alongside existing `planning`, `writing-panel-strict`, `doc-critique`, `judges`.
2. `megaplan run doc <brief>` runs the doc pipeline end-to-end. Natural outline → drafts → critique → revise → assembly flow.
3. `megaplan run creative <brief> --form joke` runs the creative pipeline with joke-form prompts. `--form poem` and other registered forms also work.
4. `megaplan plan --mode doc <brief>` runs the doc pipeline AND prints a deprecation warning pointing at `megaplan run doc <brief>`. Same for `--mode creative|metaplan|joke`.
5. `megaplan plan --mode metaplan <brief>` and `megaplan plan --mode joke <brief>` redirect appropriately (metaplan → doc; joke → creative --form joke).
6. The five new patterns (`panel_from_artifact`, `dynamic_fanout`, `weighted_vote`, `iterate_until_consensus`, `paired_round`) have unit tests proving their core behavior.
7. `docs/pipelines.md` has a worked example of the dynamic-prompt-generation pattern (the user's scenario: small prompt designs 5 critique personas → panel uses them).
8. All existing tests still pass. The bakeoff orchestrator's `metaplan`-alias code is gone.
9. Megaplan version bumped to 0.23.0 with a changelog entry covering: new doc/creative pipelines, removed metaplan/joke modes, deprecated `--mode` flag, new dynamic primitives.
10. **Smoke test #1**: a real-model `megaplan run doc <fixture-brief>` completes; output is a reasonable document.
11. **Smoke test #2**: a real-model `megaplan run creative <fixture-brief> --form poem` completes; output is a poem.

## Touchpoints

- `megaplan/pipelines/doc.py` (NEW)
- `megaplan/pipelines/creative.py` (NEW)
- `megaplan/pipelines/doc/prompts/` (NEW dir, prompts relocated)
- `megaplan/pipelines/creative/prompts/` + `creative/forms/` (NEW dirs, code relocated)
- `megaplan/_pipeline/patterns.py` (EXTEND with 5 new primitives)
- `megaplan/cli.py` (mode deprecation handler)
- `megaplan/_pipeline/planning.py` (strip doc/creative/joke/metaplan mode wiring)
- `megaplan/bakeoff/orchestrator.py:45-57` (remove metaplan alias)
- `megaplan/_pipeline/registry.py` (register doc + creative)
- `megaplan/forms/*` (relocate or shim)
- `megaplan/prompts/prep_doc.py`, `execute_doc.py`, `review_doc.py`, `critique_creative.py`, `execute_creative.py`, `revise_creative.py`, `critique_joke.py`, `execute_joke.py`, `revise_joke.py` (relocate)
- `tests/pipelines/test_doc_pipeline.py` (NEW)
- `tests/pipelines/test_creative_pipeline.py` (NEW)
- `tests/_pipeline/test_dynamic_primitives.py` (NEW)
- `tests/test_mode_deprecation.py` (NEW)
- `docs/pipelines.md` (EXTEND — dynamic primitives section, doc/creative pipeline docs, mode deprecation table)
- `CHANGELOG.md` (entry)
- `pyproject.toml` + `megaplan/__init__.py::__version__` (0.22.0 → 0.23.0)

## Profile recommendation

**`directed/full/medium @codex +prep`** (Tier 2 with codex, full robustness, medium depth, prep enabled).

### Why directed (Tier 2)

Per the megaplan-decision rubric: "Drop down to `directed` when the *planning* is the hard part — the implementation is mechanical once mapped out. Drop down further to `solo` when the plan is obvious."

The design choices for this sprint are **all locked in this brief** (from the analysis conversation). What needs real thinking is the *plan* — auditing where each prompt/form/machinery lives today, sequencing the relocations so nothing breaks mid-refactor, and getting the deprecation redirects right. Once the plan exists, execute is mostly mechanical (move files, write new pipeline shells using existing patterns, delete dead wiring, update tests).

`partnered` would be over-spec — we already have premium-tier reasoning baked into the brief itself. `premium` would be way over-spec.

### Why codex

Consistent with the current `python-composition-cleanbreak` sprint, which is using `all-codex` and converging well. Avoids relying on Shannon's tmux machinery — uses `run_codex_step` path, which has been the more reliable codepath. The cache fix is live for both backends now, but codex is what's been validated end-to-end this week.

### Why full robustness

Home base. Not security-critical, not a kernel-invariant change. Cross-cutting (CLI + pipelines + tests + docs) but well-tested by construction. `light` would skip too much; `thorough` is over-spec.

### Why medium depth

The brief is long and the sequencing matters (deprecation paths, prompt relocations, registry updates). `high` would be appropriate for the plan phase of a novel architectural decision, but the decisions are made — the plan just needs to organize the work. `medium` gives the planner enough to think clearly about sequencing without over-spending on author-side phases that are doing mostly mechanical decomposition.

### Why with-prep

The planner needs to audit:
- Current state of `forms/` machinery (what depends on it, what its shape is)
- How `prep_doc.py`, `execute_doc.py`, etc. integrate with the planning runtime (so the relocation doesn't break invariants)
- Whether the existing `PromptRegistry` supports per-pipeline subdirectories or needs an update
- Where in `cli.py` the `--mode` deprecation handler should live (after looking at the current arg-parsing flow)

That's exactly what `prep` is for. Without it, the planner will guess at these and the critique will have to surface them. Better to research first.

### CLI invocation

```bash
megaplan init .megaplan/briefs/pipeline-rationalization-and-dynamic-primitives.md \
  --profile directed \
  --depth medium \
  --robustness full \
  --with-prep \
  --vendor codex \
  --auto-start --auto-approve \
  --in-worktree pipeline-rationalization \
  --worktree-from main \
  --name pipeline-rationalization
```

**Run order**: wait for `python-composition-cleanbreak` sprint to complete (state=done, merged to main). Verify with `git log --oneline main | head -5`. Then kick off this sprint.

### Mid-flight escalation guidance

If during execution:
- The planner can't cleanly relocate forms/ without breaking external imports → escalate to `partnered` mid-run with `megaplan override set-profile`.
- The deprecation handler turns out to be more complex than CLI redirect (e.g., needs full state-passing) → consider splitting the deprecation work into its own follow-up; mark this sprint complete without it and file a ticket.
- Tests surface an unexpected coupling between `doc`/`creative` modes and `planning` (something other than prompts) → that's an architectural surprise; escalate.

## Sizing

- **Calendar**: 2-3 days of agent harness time
- **Cost**: $20-50 estimated (directed + full + medium, codex)
- **Code**: ~500-700 LOC net new, ~200 LOC deletions (mode wiring + bakeoff alias coercion)

## Shorthand

`directed/full/medium @codex +prep`
