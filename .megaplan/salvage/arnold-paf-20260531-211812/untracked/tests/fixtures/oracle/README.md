# Oracle Trace Fixtures

Synthetic-but-recorded transition traces for the M5a node-library oracle gate
(`tests/_pipeline/test_oracle_gate.py`).

## Provenance

Both fixtures were **recorded** (not hand-authored) by driving the exact
composed pipeline that the oracle-gate test constructs:

```python
critique_revise_gate_loop(
    critique_step=..., gate_step=..., revise_step=...,
    on_proceed="halt", on_iterate="revise",
    on_tiebreaker="tiebreaker_panel", on_escalate="escalate_sub",
)
+ escalate_via_subpipeline(condition=..., deadlock_pipeline=..., promote=...)
+ majority_vote(default_on_tie="tiebreaker")
```

under `MEGAPLAN_UNIFIED_DISPATCH=1`.

The stub Step verdicts that force each path:

| Path | Gate `verdict.recommendation` | Trace recorded |
|------|------------------------------|----------------|
| Escalate | `"escalate"` | `escalate_trace.json` |
| Tiebreaker | `"tiebreaker"` | `tiebreaker_trace.json` |

### Escalate trace

The gate Step emits `"escalate"` → the executor's `kind="gate"` dispatch
matches the `"escalate"`-recommendation edge targeting `escalate_sub` →
the `escalate_via_subpipeline` subloop runs its child pipeline (a single
step that writes `current_state="critiqued"`) and promotes to `"proceed"`
→ the escalate stage's normal `"proceed"` edge targets `"halt"`.

### Tiebreaker trace

The gate Step emits `"tiebreaker"` → the executor's `kind="gate"` dispatch
matches the `"tiebreaker"`-recommendation edge targeting `tiebreaker_panel`
→ the `ParallelStage` runs two reviewer Steps (one `"proceed"`, one
`"iterate"`) → the `majority_vote(default_on_tie="tiebreaker")` join
detects a tie and returns `recommendation="tiebreaker"` → the panel's
normal `"tiebreaker"` edge targets `"halt"`.

## Format

Each fixture is a JSON array of `[stage_name, edge.label, edge.kind, edge.recommendation]` tuples
in execution order. `null` represents `None` (edge has no recommendation).

## Regeneration

The fixtures can be regenerated at any time by running the
`_build_composed_pipeline` function from
`tests/_pipeline/test_oracle_gate.py` with the desired
`gate_recommendation` and recording the resulting trace. Because all
stub Steps are deterministic (no external dependencies, no model calls),
regenerated traces are identical to the committed fixtures barring a
change to the dispatch logic in `megaplan._pipeline.executor`.
