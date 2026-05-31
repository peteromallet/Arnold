# Python composition — clean break from YAML

## Goal

Replace the YAML pipeline runtime with Python composition. Single mental model. Smaller codebase. All sophistication (critique loops, gates, panels, subpipelines, modes, variants) first-class as Python primitives.

After this sprint:
- One framework: Python composition over the existing `Pipeline` / `Stage` / `ParallelStage` / `Edge` primitives.
- Two existing pipelines migrated: `planning` (refactored through new patterns) + `writing-panel-strict` (ported from YAML to Python).
- One subpipeline migrated: tiebreaker.
- ~1500 LOC of YAML machinery deleted (compiler, loader, schema, run_cli, YAML-specific step kinds, their tests).
- Megaplan version bump: 0.21.0 → 0.22.0 (breaking change).

## Context (what we learned, do not relitigate)

The path to here:

- Sprint A landed a YAML runtime with primitives. Worked for simple-topology pipelines (`writing-panel-strict`).
- Sprint B (planning migration to YAML) escalated at iter 33 after $747. Adversarial review showed it was a fake migration — forcing planning into YAML required 7 Python escape-hatches and produced a thin manifest over Python code.
- Multi-perspective scenario analysis on 6 concrete future-pipeline shapes (panel-of-7, creative workshop, debate-judge, code-review, refinement-tiebreaker, mode-variants) found 5/6 are Python-shaped (dynamic control flow, state threading). 1/6 (pure mode-variants) is YAML-shaped, but doesn't justify maintaining a dual runtime.
- **Decision**: kill the YAML runtime; commit to Python composition.

Authoritative context if needed: `.megaplan/tickets/sprint-b-redesign-needed.md`, `docs/yaml-pipelines-migration.md` (whole experiment), `.megaplan/briefs/yaml-pipelines-sprint-b1.md` + `b2.md` (the dropped briefs — DO NOT execute either).

## Locked decisions

### What to build

1. **Pattern library** in a new module `megaplan/_pipeline/patterns.py` (~250 LOC). Reusable composable functions:
   - `critique_revise_gate_loop(reviewers, prompts, max_iterations, exit_condition, ...)` — the iterate loop with all its escape semantics
   - `panel_with_retry(reviewers, merge_strategy, on_failure_sequential=True)` — parallel panel with executor-level catch-and-retry on any exception (matches legacy `parallel_critique` semantics)
   - `alternating_turns(roles, history_strategy, max_rounds, until_condition)` — two-agent (or N-agent) alternating workshop with state-threaded history
   - `subpipeline_call(pipeline_ref, when_condition, inputs_mapping)` — conditional invocation of another pipeline
   - `mode_prompts(modes_dict)` — overlay prompts based on `--mode` argument, no topology change
   - `iterate_until(stage, condition, max_iterations)` — generic iteration helper
   - `escalate_if(condition, escalation_handler)` — conditional escalation
   - `majority_vote(panel_output)` — aggregate verdicts from a panel into majority/tiebreaker decision
   - `phase_zero_gate(criteria)` — Phase 0 with objective criteria, no human sign-off
2. **`Pipeline.builder()` fluent API** in `megaplan/_pipeline/builder.py` (~150 LOC). Ergonomic sugar over the existing `Pipeline` / `Stage` / `Edge` primitives. Allows chained construction:
   ```python
   pipeline = (
       Pipeline.builder("name", description="...")
           .input("draft", file=True)
           .agent("plan", prompt="prompts/plan.md", inputs=["draft"])
           .panel("critique", reviewers=[...], inputs=["plan"], merge="structural")
           # ... etc
           .build()
   )
   ```
   Builder methods compose the pattern library functions internally where appropriate.
3. **Pipeline discovery for Python modules** (~50 LOC). Update `megaplan/_pipeline/registry.py` to discover Python pipelines from:
   - `megaplan/pipelines/<name>/` (a Python module exposing `build_pipeline()` or similar)
   - `~/.megaplan/pipelines/<name>.py` (user-installed)
   Replace the YAML-discovery code with this.

### What to refactor

4. **`megaplan/_pipeline/planning.py`** — refactor to use the new pattern library. The current explicit Stage/Edge/ParallelStage construction collapses where patterns apply. Expected: ~150 LOC of net deletion (since duplication moves into patterns.py).
5. **`megaplan/_pipeline/subloop.py`** — refactor tiebreaker subpipeline construction through the pattern library. ~50 LOC of changes.
6. **`megaplan/_pipeline/stages/*.py`** (PrepStep, PlanStep, CritiqueStep, GateStep, ReviseStep, FinalizeStep, ExecuteStep, ReviewStep) — leave alone unless the new patterns naturally subsume them. If you can collapse some, do it; otherwise stop. This is audit + tactical refactor, not a rewrite.

### What to port

7. **`writing-panel-strict` from YAML to Python**. Create `megaplan/pipelines/writing_panel_strict.py` with `build_pipeline()` function using the builder API. Keep prompts (`prompts/*.md`) where they are; the Python module just references them. Delete `pipeline.yaml`. ~100 LOC.

### What to delete

8. **Delete the YAML runtime entirely**:
   - `megaplan/_pipeline/compiler.py`
   - `megaplan/_pipeline/schema.py`
   - `megaplan/_pipeline/loader.py`
   - `megaplan/_pipeline/preflight.py` (if it's YAML-specific; audit first)
   - `megaplan/_pipeline/run_cli.py` — simplify to dispatch Python pipelines, OR delete entirely if `megaplan run` becomes just `megaplan plan` or a thin wrapper
   - `megaplan/_pipeline/steps/agent.py`, `panel.py`, `human_gate.py` — the YAML-specific step kinds. Their semantics are now in patterns.py and the executor; delete the wrappers.
   - `megaplan/_pipeline/pre_handlers.py` if it exists (was proposed for B1; check)
   - `megaplan/pipelines/planning/pipeline.yaml` (Sprint A's parked stub)
   - `megaplan/pipelines/writing-panel-strict/pipeline.yaml` (replaced by Python)
9. **Delete YAML-specific tests**:
   - `tests/_pipeline/test_loader.py`
   - `tests/_pipeline/test_schema.py`
   - `tests/_pipeline/test_yaml_steps.py`
   - The YAML-pipeline-specific portions of `tests/_pipeline/test_writing_panel_e2e.py` (rewrite to target the Python version)
   - `tests/profiles/test_pipeline_profiles.py` if it tests YAML-specific profile resolution; otherwise keep
   - `tests/handlers/test_session_cache_noop.py` — keep the test logic, drop any YAML-pipeline fixtures
10. **Delete adjacent YAML support**:
    - YAML-related entries in `megaplan/cli.py` (the `megaplan run <yaml-pipeline>` dispatch)
    - YAML mentions in `megaplan/_pipeline/registry.py`
    - YAML mentions in `megaplan/_pipeline/resume.py` (if any — keep the resume mechanism itself for `human_gate`, just drop YAML-specific paths)

### What to keep

11. **The executor + primitives stay**: `megaplan/_pipeline/executor.py`, `types.py` (`Pipeline`, `Stage`, `ParallelStage`, `Edge`). Both `planning.py` and the new builder use them directly.
12. **The `_human_gate` step semantics stay** but become a Python primitive, not a YAML step kind. Either keep `megaplan/_pipeline/steps/human_gate.py` and have it called from Python composition, OR fold its logic into the builder.
13. **The `cache_hit_suspected` no-op detector** stays in `_write_plan_version` (it's still useful).
14. **The session-cache fix** stays (commits `2d8d5bdc` + merge).
15. **The `--in-worktree` flag** stays.
16. **All existing handlers** (`handle_critique`, `handle_gate`, etc.) stay — they're not part of the YAML system, they're the actual phase logic.

### Documentation

17. **Write `docs/pipelines.md`** (~200 LOC) — "Defining a pipeline in megaplan." Cover:
    - The conceptual model (stages + edges + patterns)
    - Builder API basics
    - Each pattern function with a one-paragraph explanation + example
    - The 6 scenario shapes from the discovery work as worked examples
    - How to write a user-installed pipeline (drop in `~/.megaplan/pipelines/foo.py`)
18. **Annotate `docs/yaml-pipelines-migration.md`** with a header note: "Experiment outcome — Python composition replaced YAML. See docs/pipelines.md."
19. **Update `docs/megaplan-decision.md`** (the rubric skill) — remove or replace any references to YAML pipelines.
20. **Update CLAUDE.md** if it references the YAML pipeline shape.

### Version bump

21. **Megaplan 0.21.0 → 0.22.0**. Update `pyproject.toml` and `megaplan/__init__.py::__version__`. Write a changelog entry calling out:
    - YAML pipeline runtime removed
    - Python composition framework introduced
    - Pattern library available at `megaplan/_pipeline/patterns.py`
    - Builder API at `megaplan.Pipeline.builder()`
    - Migration: any external YAML pipelines (none known) must rewrite as Python modules

## Done criteria

1. `megaplan plan <brief>` and `megaplan run writing-panel-strict <brief>` (or equivalent) both work end-to-end on representative inputs. Behavior identical to today's planning + writing-panel-strict.
2. All existing test suites pass. Targeted tests for each new pattern function pass.
3. The YAML runtime is **fully deleted** — `grep -rn "import.*loader\|import.*schema\|import.*compiler" megaplan/` returns no results from outside the deleted files. `find megaplan/pipelines -name '*.yaml'` returns empty.
4. `megaplan list pipelines` shows `planning` and `writing-panel-strict` (Python pipelines) and any other registered modules.
5. `docs/pipelines.md` exists with examples for all 6 future-pipeline scenarios (panel-of-7, creative workshop, debate, code-review, refinement+tiebreaker, mode-variants). These are documentation examples, NOT runnable pipelines — they're showing the patterns.
6. Megaplan version is 0.22.0. Changelog entry exists.
7. **Smoke test**: a fresh `megaplan plan` real-model run on a small brief completes successfully. Confirms the refactor preserved planning behavior.
8. **Smoke test #2**: `megaplan run writing-panel-strict` on the existing fixture brief completes successfully. Confirms the YAML→Python port preserved behavior.

## Anti-scope

- **Do NOT build new pipelines** (panel-of-7, creative workshop, etc.). Those are example documentation only. They become real Sprint C+ work, not this sprint.
- **Do NOT change handler internals** (`handle_critique`, `handle_gate`, etc.). They're consumers of the pipeline framework, not part of it.
- **Do NOT change the cache-fix machinery** (no-op detector, cost guard). It works; leave it.
- **Do NOT keep YAML "for simple cases"**. Clean break. One framework.
- **Do NOT add a YAML → Python migration tool**. No external YAML pipelines exist; nobody needs the bridge.
- **Do NOT redesign the executor** (`run_pipeline`, `run_pipeline_with_policy`). Use as-is.
- **Do NOT touch `_pipeline/stages/*.py`** unless the new patterns naturally subsume them. Tactical only.

## Touchpoints

- `megaplan/_pipeline/patterns.py` (NEW)
- `megaplan/_pipeline/builder.py` (NEW)
- `megaplan/_pipeline/registry.py` (refactor for Python discovery)
- `megaplan/_pipeline/planning.py` (refactor through patterns)
- `megaplan/_pipeline/subloop.py` (refactor)
- `megaplan/pipelines/writing_panel_strict.py` (NEW — replaces YAML)
- `megaplan/_pipeline/compiler.py`, `schema.py`, `loader.py`, `run_cli.py`, `preflight.py?`, `steps/agent.py|panel.py|human_gate.py` (DELETE or absorb)
- `megaplan/cli.py` (drop YAML dispatch in `megaplan run`)
- `megaplan/__init__.py` (version + maybe expose `Pipeline.builder` at top level)
- `tests/_pipeline/` (delete YAML tests; add pattern tests; rewrite writing-panel E2E)
- `tests/profiles/`, `tests/handlers/`, etc. — audit + clean
- `docs/pipelines.md` (NEW)
- `docs/yaml-pipelines-migration.md` (annotate)
- `docs/megaplan-decision.md` (update references)
- `pyproject.toml`, `CHANGELOG.md` (version + entry)
- `CLAUDE.md` (if it references YAML)

## Constraints

- ~750 LOC of new + refactored code (mostly extraction + builder).
- ~1500 LOC of deletions across YAML machinery + tests.
- **Net repo change: ~-750 LOC** (codebase shrinks).
- The Python pipeline framework keeps zero schema validation gates — it relies on Python's import-time errors + type checking.
- The new builder + patterns should pass `mypy --strict` on the new modules.

## Profile recommendation

`all-codex / full / high`. This is largely mechanical extraction + refactoring; the architectural decisions are made in this brief. Codex at high effort handles the schema gymnastics + careful deletion sequence. `full` robustness is enough — confined-blast-radius work with good test coverage.

```bash
megaplan init .megaplan/briefs/python-composition-cleanbreak.md \
  --profile all-codex --depth high --robustness full \
  --with-prep \
  --auto-start --auto-approve \
  --in-worktree python-composition \
  --worktree-from main \
  --name python-composition-cleanbreak
```

`--with-prep` because the planner needs to audit `planning.py`'s actual structure, identify which patterns apply where, and decide the precise API shape before generating the implementation plan.

## Sizing

- Calendar: 2-3 days of agent harness time
- Cost: $50-150
- Code: ~+750 LOC new, ~−1500 LOC deletions, net −750 LOC

## After it lands

- One pipeline framework (Python composition with reusable patterns)
- Two pipelines (planning + writing-panel-strict) both using it
- `docs/pipelines.md` documents the patterns + 6 example shapes for future pipelines
- Megaplan 0.22.0 ships with a breaking change clearly called out
- Future complex pipelines become 50-100 LOC Python files using the builder + patterns
