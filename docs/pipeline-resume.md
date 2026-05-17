# Pipeline resume — worked example

> Sprint 1 design doc. Sprint 2 implements the derivation against the
> unified `Pipeline` value; this doc nails down the contract.

The `resume_cursor.phase` field in `state.json` names a Pipeline **stage**,
not a handler module. After Sprint 2's port, the auto driver looks the
cursor up by name in `pipeline.stages` and re-enters that stage.

## The pipeline

A trivial 4-stage compose flow (matches `tests/test_pipeline_compose.py`):

```
prep ──to_critique_a──▶ critique_a ──to_critique_b──▶ critique_b ──to_finalize──▶ finalize ──done──▶ halt
```

Built in Python with public primitives:

```python
pipeline = Pipeline(
    stages={
        "prep": Stage("prep", prep_step, edges=(Edge("to_critique_a", "critique_a"),)),
        "critique_a": Stage("critique_a", critique_a, edges=(Edge("to_critique_b", "critique_b"),)),
        "critique_b": Stage("critique_b", critique_b, edges=(Edge("to_finalize", "finalize"),)),
        "finalize": Stage("finalize", finalize_step, edges=(Edge("done", "halt"),)),
    },
    entry="prep",
)
```

## state.json after critique_a completes

```json
{
  "resume_cursor": {"phase": "critique_b"},
  "prepped": true,
  "critique_a_done": true,
  "critique_a_score": 0.7
}
```

Each completed stage's `state_patch` is merged into `state` via
`state.update(dict(result.state_patch))` (defensive copy). The executor
advances `resume_cursor.phase` to the **target** of the matching outbound
edge whenever a stage completes.

## Resuming

On resume the driver reads `state["resume_cursor"]["phase"]`, looks up that
stage in `pipeline.stages` by name, and re-enters it. Stages must be
idempotent (writing artifacts under their own dir is the convention) so a
crash-and-resume mid-stage replays cleanly.

## Sprint 2: derived resume map

Today the resume contract is encoded in `_RESUME_ACTIVE_STATES`
(`megaplan/_core/workflow.py:361`) as a hand-rolled `dict[str, str]`
mapping phase → prior state. Sprint 2 derives that same shape from
`Pipeline.stages` + `Pipeline.stages.<stage>.edges`:

```python
# Sprint-2 will derive this from Pipeline.stages + edges, replacing the
# hand-rolled _RESUME_ACTIVE_STATES dict at megaplan/_core/workflow.py:361.
# Resulting type matches the existing dict[str, str] mapping phase -> prior_state.
def derive_resume_active_states(pipeline: Pipeline) -> dict[str, str]:
    prior: dict[str, str] = {}
    for node in pipeline.stages.values():
        if getattr(node, "step", None) is None:
            continue  # ParallelStage handled separately
        if node.step.kind not in {"produce", "judge"}:
            continue
        prior[node.name] = _inbound_stage_name(pipeline, node.name) or "initialized"
    return prior
```

`_inbound_stage_name(pipeline, name)` returns the name of the unique stage
whose edges target `name` (or `None` if `name` is the entry). For the
demo above the derived map is:

```
{
  "critique_a": "prep",
  "critique_b": "critique_a",
  "finalize":   "critique_b",
}
```

`prep` is the entry, so it maps to `"initialized"`. Stages whose `kind`
is `decide` are not resume points (they read prior verdicts and are
recomputed); `subloop` and `override` are reserved and not exercised in
Sprint 1.

## ParallelStage resumption

A `ParallelStage` is treated as one resume point named by its `name`. On
resume the **entire** barrier is restarted from scratch — partial
fan-out replay (re-running only the un-completed children) is **out of
scope**. The convention is acceptable because: (a) Sprint 1's demo
judges are pure deterministic functions over the fixture, so replays are
free; (b) Sprint 2's parallel critique flow keeps state via the merged
`state_patch` written when `join` returns, not via partial child writes.

If/when a future sprint needs partial-fan-out resumption, the cursor can
be widened to `{"phase": "judges", "completed_children": ["judge_a"]}`
and the executor's ParallelStage branch can skip completed children.
That's a non-breaking extension of the current contract.
