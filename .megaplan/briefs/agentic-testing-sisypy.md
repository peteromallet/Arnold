# Agentic testing rig via sisypy

## Outcome

A `megaplan/tests/agentic/` subtree that uses the **sisypy** harness to run three agent-driven scenarios against megaplan: two that drive the existing harness (one code deliverable, one doc deliverable), and one that builds a new YAML pipeline. Each run produces a frozen evidence pack that surfaces friction and confusion signals (`invalid_transition` retries, `override` use, `Auto-downgraded` events, direct-edit bypasses).

The goal is to instrument the question: **can a user-and-agent loop drive megaplan, and create new sequences in it, without friction or confusion?** Not to grade outcome quality.

## Scope

**IN**:
1. `MegaplanAdapter(sisypy.AgenticProjectAdapter)` implementing the 8 ABC methods.
2. `megaplan_checks.py` — five friction-signal extractors against the evidence pack.
3. Three scenario YAML + brief markdown pairs.
4. `pyproject.toml` extra `test-agentic` adding `sisypy` and `pyyaml`.
5. A thin `run.py` entry: `python -m megaplan.tests.agentic.run` invokes `sisypy.run_all`.
6. A `conftest.py` that isolates `MEGAPLAN_HOME` per run.

**OUT**:
- Extending sisypy itself. If a gap is felt, document it; do not patch sisypy in this sprint.
- Publishing sisypy to PyPI.
- L3 (megaplan-vs-bare) comparison scenarios.
- Building a custom runner; use `sisypy.run_all`.
- Parallelizing scenarios (serialize in v1).
- CI integration. The PR adds `make agentic` target; wiring to CI is a follow-up.

## Locked decisions

1. **Harness**: sisypy at `/Users/peteromalley/Documents/reigh-workspace/sisypy/`, installed editable. The contract is `sisypy.AgenticProjectAdapter` (see `sisypy/adapters.py:32`) and the schemas in `sisypy/schema.py`.

2. **Reference implementation**: VibeComfy's adapter at `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/agentic/adapter.py` (843 LOC). It is the load-bearing template. Mimic its patterns for `prime`, `capture`, `project_universal_checks`, `classify_success`. Do not invent shapes that diverge from it without naming the reason.

3. **Cheap actor**: `sisypy.dispatch.HermesDispatcher` with `model: deepseek:deepseek-v4-flash`. Set `timeout_sec: 1800` per scenario in the YAML `agents[].config`.

4. **File layout** (do not rename):
   ```
   megaplan/tests/agentic/
     __init__.py
     adapter.py              ← MegaplanAdapter
     megaplan_checks.py      ← friction extractors
     conftest.py             ← MEGAPLAN_HOME isolation fixture
     run.py                  ← thin CLI: sisypy.run_all(...)
     .megaplan/briefs/
       use_execute_simple.md
       use_doc_simple.md
       create_poem_panel.md
     scenarios/
       use_execute_simple.yaml
       use_doc_simple.yaml
       create_poem_panel.yaml
   ```

5. **Five friction signals to extract** (bundle into one dict returned by `project_universal_checks`):
   - `invalid_transitions`: count of "invalid_transition" in stderr / command_log.
   - `overrides`: count of `megaplan override` invocations + the verbs used.
   - `auto_downgraded`: hits of `Auto-downgraded` in any `gate.json` under the captured plan dir.
   - `status_loops`: ≥3 consecutive `megaplan status` calls with no intervening state-mutating command.
   - `direct_edits`: any non-test `.py` file changed in the diff without a preceding `megaplan init` invocation.

6. **Success classification** (`classify_success`):
   - `AUTHORED` if any code/doc file was written.
   - `VALIDATED` if `python -c "from megaplan._pipeline.loader import load_pipeline; load_pipeline('poem-panel')"` succeeds (scenario 3 only).
   - `RUNTIME_PROVEN` if the captured `state.json` has `current_state in {"done", "reviewed"}`.

7. **Workdir convention**: derive per-run scratch dir deterministically as `<repo>/.megaplan-agentic/<run.id>/`. Do not stash on `ActorRun`. The same value is used by both `prime` and `capture`.

8. **Primitive surface for scenario 3**: ONLY `agent`, `panel`, `gate`, `human_gate` exist in `megaplan/_pipeline/schema.py` on main. Do NOT reference `iterate_until_consensus`, `dynamic_fanout`, `weighted_vote`, `panel_from_artifact`, or `paired_round` — those are Sprint D primitives that never merged. The brief for scenario 3 must constrain the agent to existing kinds.

9. **Scenario 3 template**: `megaplan/pipelines/writing-panel-strict/pipeline.yaml` is the structural model — `agent` to draft, `panel` to fan out reviewers, `agent` to synthesize, `agent` to revise, `human_gate` (or `gate`) to loop. The brief should NOT show the agent this file; discovery is part of the test.

## The three brief markdowns (verbatim — these are deliverables, not work to interpret)

### `.megaplan/briefs/use_execute_simple.md`

```markdown
# Add `--no-color` to `megaplan status`

I want `megaplan status` to accept a `--no-color` flag that strips ANSI escape codes
from its output. This is a small, well-scoped change.

Please drive this through megaplan — pick whatever profile and robustness you think
fit. I trust your judgment on the dials. The change should include a test.

Done = the flag works, a test passes, and the megaplan run reaches state `done` or
`reviewed`.
```

### `.megaplan/briefs/use_doc_simple.md`

```markdown
# Write a "blocked-recovery" runbook

I want a one-page operator runbook at `docs/ops/blocked-recovery.md` covering what
to do when a megaplan run goes into the `blocked` state. It should walk through
reading `valid_next` and the recovery decision tree.

Please drive this through megaplan — pick whatever profile and robustness fit a doc
deliverable. The doc should be a real reference, not a stub.

Done = the file exists, covers the decision tree, and the megaplan run reaches
state `done` or `reviewed`.
```

### `.megaplan/briefs/create_poem_panel.md`

```markdown
# New megaplan pipeline: poem-panel

Create a new built-in megaplan pipeline named `poem-panel` that:

1. Takes a topic string as input.
2. Generates a draft poem.
3. Sends the draft to three critics with distinct perspectives:
   formalist, emotional reader, contrarian.
4. Synthesizes their feedback.
5. Revises the poem.
6. Loops back to step 3 until either a quality gate passes or 5 iterations elapse.

Constraints:
- Use ONLY existing pipeline primitive kinds. Read the schema to find them.
- Do NOT add new step kinds or modify `megaplan/cli.py`.
- Land the pipeline under `megaplan/pipelines/poem-panel/`.
- After creating it, smoke-run: `megaplan run poem-panel --topic "tide pools"`.

Done = `megaplan run --list` shows `poem-panel`; `load_pipeline("poem-panel")`
succeeds; the smoke run produces a final poem.
```

## Open questions (the planner must resolve, not punt)

1. **How does the scratch dir get plumbed?** Sisypy's `ActorRun` does not carry a workdir field. The planner must specify whether to (a) derive it from `run.id` deterministically (`<repo>/.megaplan-agentic/<run.id>/`), (b) stash on a custom `ActorRun.extras` (sisypy may not support extras on `ActorRun`), or (c) store on `self` in the adapter keyed by `run.id`. Locked decision #7 says (a); the planner verifies sisypy doesn't require otherwise.

2. **Does `MEGAPLAN_HOME` fully isolate?** Run a smoke probe early: `MEGAPLAN_HOME=/tmp/x megaplan list` should NOT list plans from `~/.megaplan/`. If it leaks (some code paths hard-code `~/.megaplan/`), patch the adapter to also chdir into a tmp repo clone, OR document the leak and run scenarios serially.

3. **What goes in `report.md`?** Sisypy expects each actor run to produce a markdown report. Megaplan's actor (the cheap agent) drives the harness but doesn't naturally emit a final report. The cheap-agent prompt template (used by `HermesDispatcher`) must be told: "After your work, write a markdown summary of what you did, where the deliverable lives, and any commands that returned errors." This goes in `report.md`.

4. **Friction-signal regex specifics**: turn the five signal names in locked decision #5 into precise regexes against `stdout.log`, `stderr.log`, `command_log.jsonl`, and the captured megaplan files. Reference the relevant strings in megaplan source.

## Constraints

- **Total new LOC ≤ 700** (Python only; YAML and markdown excluded). Adapter ≤ 400 LOC, friction extractors ≤ 200 LOC, run.py + conftest.py ≤ 100 LOC.
- **No edits to existing megaplan/ source files** except `pyproject.toml` (add the `test-agentic` extra).
- **Cheap actor only**: every scenario uses `deepseek:deepseek-v4-flash`. Do not introduce cross-vendor or premium-model scenarios in this sprint.
- **Deterministic checks first**: every friction signal is a Python function over the evidence pack. No LLM grading required for v1.
- **Acceptance must be runnable without network access to anything other than the cheap-actor API**.

## Done criteria

1. `pip install -e ".[test-agentic]"` succeeds on a fresh checkout (assuming sisypy is editable-installed from `/Users/peteromalley/Documents/reigh-workspace/sisypy`).
2. `python -m megaplan.tests.agentic.run` runs all three scenarios serially and exits cleanly.
3. Each scenario produces an evidence pack under `<repo>/.megaplan-agentic/<run_id>/evidence/`.
4. Each evidence pack contains at minimum: `brief.md`, `report.md`, `stdout.log`, `stderr.log`, and a `project_specific/` subdir with megaplan plan files.
5. At least one scenario, when run against an actor that is given the megaplan skill docs, surfaces a non-zero count on at least one friction signal. If all three scenarios pass perfectly with zero friction signals, the checks are too lax — sharpen and re-run.
6. Adapter passes a smoke test: instantiate `MegaplanAdapter(repo_root=<repo>)` and call each of the 8 ABC methods with a stub `Scenario` + `ActorRun`. No method raises `NotImplementedError`.

## Touchpoints

**New files** (entire delta is additive):
- `megaplan/tests/agentic/__init__.py`
- `megaplan/tests/agentic/adapter.py`
- `megaplan/tests/agentic/megaplan_checks.py`
- `megaplan/tests/agentic/conftest.py`
- `megaplan/tests/agentic/run.py`
- `megaplan/tests/agentic/briefs/*.md` (3 files)
- `megaplan/tests/agentic/scenarios/*.yaml` (3 files)

**Modified files**:
- `pyproject.toml` — add `[project.optional-dependencies] test-agentic` section.

**Read-only references** (do NOT modify):
- `/Users/peteromalley/Documents/reigh-workspace/sisypy/adapters.py` — ABC contract.
- `/Users/peteromalley/Documents/reigh-workspace/sisypy/schema.py` — dataclasses.
- `/Users/peteromalley/Documents/reigh-workspace/sisypy/dispatch.py` — HermesDispatcher.
- `/Users/peteromalley/Documents/reigh-workspace/sisypy/evidence.py` — capture API.
- `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/agentic/adapter.py` — reference adapter.
- `megaplan/pipelines/writing-panel-strict/pipeline.yaml` — primitive composition template (do not read in the test brief, but read it as the planner).

## Anti-scope

- **Do not extend sisypy.** If a sisypy gap is felt (e.g., no workdir on `ActorRun`, no capture-on-timeout), document it in a one-line `# TODO(sisypy):` comment and work around it. A sisypy PR is a follow-up sprint.
- **Do not add L3 (megaplan-vs-bare) scenarios.** Single-arm scenarios only.
- **Do not write a custom runner.** Use `sisypy.run_all`.
- **Do not parallelize.** Serial execution in v1.
- **Do not add CI wiring.** A `make agentic` target plus README usage is enough.
- **Do not introduce new megaplan primitives** to make scenario 3 cleaner. The test specifically measures whether the agent can compose existing primitives.
- **Do not publish sisypy** or change its imports beyond what `pip install -e` requires.
- **Do not write the rubric in code** beyond the YAML `assessment:` sections. Sisypy reads the YAML; we don't need a parallel grading harness.
- **Do not generate the three briefs from a template.** Each is a deliverable; the planner copies them verbatim from this brief into `.megaplan/briefs/`.

## Verification commands (planner should include in execute)

```bash
# Install
pip install -e ".[test-agentic]"
pip install -e /Users/peteromalley/Documents/reigh-workspace/sisypy

# Adapter smoke
python -c "from megaplan.tests.agentic.adapter import MegaplanAdapter; \
  from pathlib import Path; \
  a = MegaplanAdapter(name='megaplan', repo_root=Path.cwd()); \
  print(a.name, a.repo_root)"

# Run all three scenarios
python -m megaplan.tests.agentic.run

# Inspect one pack
ls .megaplan-agentic/*/evidence/*/
```
