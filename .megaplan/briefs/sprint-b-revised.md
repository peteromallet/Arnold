# Sprint B Revised — Planning parity verification + executor override gap

**Status**: Supersedes the three YAML-era Sprint B briefs (`yaml-pipelines-sprint-b.md`,
`yaml-pipelines-sprint-b1.md`, `yaml-pipelines-sprint-b2.md`). The YAML runtime
experiment was killed in megaplan 0.22.0 (see `python-composition-cleanbreak.md`).
Python composition with `Pipeline.builder()`, `patterns.py`, and `registry.py` is
the framework.

The original Sprint B plan escalated at iter 33 ($747 spent) with state=blocked.
That plan is parked at
`~/Documents/.megaplan-worktrees/yaml-pipelines-migration/.megaplan/plans/yaml-pipelines-sprint-b/`.
**Do NOT re-run it.** The contradictions it hit are resolved below.

---

## The 5 architectural decisions — resolved

### 1. YAML vs Python PipelineBuilder direction

**Resolution: Python PipelineBuilder. YAML runtime is dead and deleted.**

The cleanbreak (`python-composition-cleanbreak.md`) committed megaplan to Python
composition. The codebase has `Pipeline.builder()` (builder.py, 454 LOC), 14
pattern functions in `patterns.py` (870 LOC), module-based pipeline discovery in
`registry.py`, and `docs/pipelines.md` documenting the framework.

`docs/yaml-pipelines-migration.md` carries a header annotation: "Experiment
outcome — Python composition replaced YAML. See docs/pipelines.md."

No YAML machinery remains. No `compiler.py`, `schema.py`, `loader.py`, or YAML
step kinds. The `pipeline.yaml` stubs are gone.

### 2. Planning parity and cutover strategy

**Resolution: Planning IS already Python. Parity = verify, not migrate.**

`compile_planning_pipeline()` in `megaplan/_pipeline/planning.py` already uses the
pattern library (`critique_revise_gate_loop`, `phase_zero_gate`) and composes the
same 9 stages (`prep → plan → critique → gate → revise → finalize → execute →
review → tiebreaker`) with the same `PrepStep`, `PlanStep`, `CritiqueStep`,
`GateStep`, etc. It is registered as the `"planning"` built-in in `registry.py`.

What remains is **verification**: a trace-parity test confirming the refactored
pipeline invokes handlers in the same order, makes the same edge selections, and
produces the same state transitions. One real-model smoke run on a representative
brief.

There is no flag flip, no runtime-selection field, no drain period, and no
"delete planning.py" ceremony. The refactored `planning.py` IS the canonical
planning pipeline. The legacy `WORKFLOW = {...}` dict in
`megaplan/_core/workflow_data.py` stays as a bootstrap source until the
`workflow_dict_from_pipeline()` inversion replaces it — that is a separate,
follow-up concern.

### 3. `Verdict.override` dispatch in `run_pipeline_with_policy`

**Resolution: Fix the gap. Add override dispatch to `run_pipeline_with_policy`.**

Current state in `megaplan/_pipeline/executor.py`:

| Runner | Lines | Checks `Verdict.override`? |
|---|---|---|
| `run_pipeline` | 270–273 | **Yes** — calls `find_override_edge(node.edges, result.verdict.override)` |
| `run_pipeline_with_policy` | 377–397 | **No** — only checks `verdict.recommendation`, then normal label fallback |

The `find_override_edge` helper already exists in `megaplan/_pipeline/override.py`
and is imported by `run_pipeline`. The fix is a ~6-line addition to
`run_pipeline_with_policy`: insert an override check block before the
recommendation check at line 379, mirroring the pattern at lines 270–273.

```python
# Insert before line 379 in run_pipeline_with_policy:
from megaplan._pipeline.override import find_override_edge  # already imported at top of run_pipeline

edge = None
rec = None
if result.verdict is not None and result.verdict.override is not None:
    edge = find_override_edge(node.edges, result.verdict.override)
if edge is None and result.verdict is not None and result.verdict.recommendation is not None:
    # ... existing recommendation dispatch continues unchanged
```

This makes both runners use the same three-tier dispatch: override → gate
recommendation → normal label. The escalate-policy resolution (lines 385–392)
continues to fire only on recommendation-based escalate, which is correct —
override edges are human-invoked escape hatches and should not be re-interpreted
by escalate policy.

### 4. Handler LOC/budget constraints

**Resolution: Handler budget is obsolete. Python composition has no "escape hatches."**

The original constraint #12 ("max 3 stages may use `handler:`") was a YAML-era
concept — it limited how many pipeline YAML stages could escape declarative
topology to run arbitrary Python. With Python composition, there is no `handler:`
field and no YAML schema. Every stage is Python.

The `InProcessHandlerStep` that wraps `handle_*` functions (e.g. `handle_gate`,
`handle_critique`) is one `Step` implementation among many — same status as
`AgentStep`, `PanelReviewerStep`, or `SubloopStep`. The planning pipeline uses
the stages it needs. No budget applies. No "escape hatch" tracking is needed.

The handler audit in `docs/yaml-pipelines-migration.md` Appendix (L208–242)
remains a useful reference for understanding which handlers carry heavy side-work,
but it is not a constraint on the Python planning pipeline.

### 5. Old plan/worktree parking

**Resolution: Parked and ignored. Do not re-run.**

| Artifact | Status |
|---|---|
| Old Sprint B plan dir | `~/Documents/.megaplan-worktrees/yaml-pipelines-migration/.megaplan/plans/yaml-pipelines-sprint-b/` — `state=blocked` |
| Last real plan | `plan_v31.md` (26.5% delta from prior; v32–v33 were cache replays) — reference material only |
| Old briefs | `.megaplan/briefs/yaml-pipelines-sprint-b.md`, `-b1.md`, `-b2.md` — superseded by this brief |
| Worktree branch | `yaml-pipelines-migration` — remove when convenient |
| Old gate rationale | `state.json → meta.last_gate` — the 5 decisions are resolved above |

---

## Recommended execution sequence

### Phase 1: Fix the override gap (~30 min)

1. Add `Verdict.override` dispatch to `run_pipeline_with_policy` in
   `megaplan/_pipeline/executor.py`. Mirror the block from `run_pipeline`
   (lines 270–273): `find_override_edge` → gate recommendation → normal label.
2. Add a targeted unit test: `run_pipeline_with_policy` follows a
   `kind="override"` edge when a Step returns
   `Verdict(override="force_proceed")`.
3. Run existing test suites: `pytest tests/_pipeline/ -x -q`.

### Phase 2: Trace-parity test (1–2 days)

1. Create a representative parity input at
   `megaplan/pipelines/planning/tests/parity/representative/brief.md`.
   Mine `.megaplan/plans/` for a real brief that triggers at least one iterate
   cycle; or write one fresh.
2. Write `tests/parity/test_planning_trace_parity.py`:
   - Runs `compile_planning_pipeline()` in mock mode against the brief.
   - Asserts: handler invocation order, edge selections at gates, state
     transitions (`current_state` trajectory), artifact paths produced.
   - Compares against a committed `expected_trace.yaml`.
3. Commit both the brief and the expected trace.
4. Wire into CI so it runs on every PR touching `_pipeline/` or `planning.py`.

### Phase 3: Real-model smoke run (manual, 1–2 hours)

1. Run `megaplan plan <brief>` (dispatches through `compile_planning_pipeline()`
   via `registry.get("planning")`) on a small representative brief.
2. Confirm: reaches `state=done`, produces sensible artifacts, no new error
   categories.
3. Manual review acceptable. Not gated by automated CI check.

### Phase 4: Cleanup (optional, ≤1 day)

1. Remove the parked `yaml-pipelines-migration` worktree if it still exists:
   `git worktree remove ~/Documents/.megaplan-worktrees/yaml-pipelines-migration`
2. Add a "superseded by sprint-b-revised.md" header annotation to
   `.megaplan/briefs/yaml-pipelines-sprint-b.md` and its siblings.
3. Archive or delete the old Sprint B plan directory.

---

## Acceptance criteria

| # | Criterion |
|---|---|
| AC1 | `run_pipeline_with_policy` dispatches `Verdict.override` edges identically to `run_pipeline`. |
| AC2 | Trace-parity test passes in CI: 3 consecutive green runs on `tests/parity/test_planning_trace_parity.py`. |
| AC3 | One real-model smoke run: `megaplan plan` on a representative brief reaches `state=done`. |
| AC4 | All existing test suites pass (`tests/_pipeline/`, `tests/parity/`, planning tests). |
| AC5 | `find_override_edge` is the single dispatch path for override edges in both `run_pipeline` and `run_pipeline_with_policy`. |
| AC6 | The old Sprint B plan remains parked. No attempt to re-run it. |

---

## Non-goals (explicit anti-scope)

- **Do NOT** build a 5–6 input real-model parity corpus or compute ±15% cost stats.
- **Do NOT** delete `planning.py` — it IS the canonical planning pipeline.
- **Do NOT** add new step kinds, new pattern functions, or new primitive types.
- **Do NOT** touch `parallel_critique.py` (absorbed or deleted in the cleanbreak).
- **Do NOT** touch handler internals (`handle_critique`, `handle_gate`, etc.).
- **Do NOT** re-run the old Sprint B plan.
- **Do NOT** add `pre_handler`, `HandlerStepSpec`, `runtime-audit`, or any
  YAML-era concept — those are dead.
- **Do NOT** add a `pipeline_runtime` field to `state.json` — no runtime
  selection, no legacy/YAML split.
- **Do NOT** change `WORKFLOW` dict in `workflow_data.py` — that inversion is a
  separate, follow-up concern.

---

## What NOT to rerun

- The old Sprint B plan at
  `~/Documents/.megaplan-worktrees/yaml-pipelines-migration/.megaplan/plans/yaml-pipelines-sprint-b/`
  — parked, blocked, $747 spent. The 5 contradictions it hit are resolved above.
- `yaml-pipelines-sprint-b1.md` and `yaml-pipelines-sprint-b2.md` — superseded.
  Their scope (executor prereqs, runtime-selection cutover) was either absorbed
  into the cleanbreak or rendered obsolete by the YAML→Python switch.
- Any YAML pipeline compilation, loading, or `megaplan run <yaml-pipeline>`
  dispatch. The YAML runtime is dead.

---

## Touchpoints

| File | Action |
|---|---|
| `megaplan/_pipeline/executor.py` | Add override dispatch to `run_pipeline_with_policy` (~6 lines) |
| `tests/parity/test_planning_trace_parity.py` | **New** — trace-parity test |
| `megaplan/pipelines/planning/tests/parity/representative/brief.md` | **New** — parity input |
| `megaplan/pipelines/planning/tests/parity/representative/expected_trace.yaml` | **New** — golden trace |
| `.megaplan/briefs/yaml-pipelines-sprint-b.md` | Optional: annotate "superseded by sprint-b-revised.md" |
| `.megaplan/briefs/yaml-pipelines-sprint-b1.md` | Optional: annotate "superseded" |
| `.megaplan/briefs/yaml-pipelines-sprint-b2.md` | Optional: annotate "superseded" |

---

## Remaining human decisions

None blocking. The 5 architectural decisions are resolved above. If any of the
following surface during execution, escalate:

1. The trace-parity test reveals a real behavioral divergence between the
   refactored `planning.py` and the legacy path that cannot be fixed with a
   ≤20-line patch. (Expected: no divergence — same handlers, same topology.)
2. The real-model smoke run fails to reach `state=done` or produces artifacts
   indicating a regression. (Expected: clean pass — the refactored planning
   pipeline has been live since 0.22.0.)

---

## Sizing

| Item | Estimate |
|---|---|
| Production code change | ~10 LOC (override gap fix in executor.py) |
| Test code | ~200 LOC (trace-parity test + expected trace YAML) |
| Calendar | 1 day of focused work |
| Cost | $0 for code fix; $5–20 for one real-model smoke run (all-codex/medium) |

## Profile recommendation

Manual work — no megaplan harness needed. The override gap fix is a targeted
code change. The trace-parity test is conventional Python test writing. The
smoke run is a single `megaplan plan` invocation.

If a harness is desired for the smoke run:
```bash
megaplan plan megaplan/pipelines/planning/tests/parity/representative/brief.md \
  --profile all-codex --depth medium --robustness full
```
