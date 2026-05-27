First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the pipeline ENGINE — executor, types, Step/Edge/PipelineVerdict, runtime policy

The brief's whole thesis is "everything runs through `run_pipeline`/`run_pipeline_with_policy`."
That engine must be solid enough to carry planning (the most complex flow). Stress-test it.

Investigate (cite path:line):
- `_pipeline/executor.py` (`run_pipeline` ~204, `run_pipeline_with_policy` ~303): the graph-walk
  loop, edge resolution, gate dispatch, subloop/override edge handling, error/exception paths,
  how it decides "done", how it persists, how it resumes mid-graph.
- `_pipeline/types.py`: `Step`, `Stage`, `ParallelStage`, `Edge` (kinds incl. `gate`/`subloop`/
  `override` ~16-20,76-78), `PipelineVerdict`, `Pipeline`, `StepResult`/state_patch. Are these frozen
  types actually expressive enough, or do real flows escape them via side channels?
- `runtime.py` `RuntimePolicy` (stall/cost/escalate/retry): how robust? edge cases?
- `_pipeline/steps/human_gate.py`, `ResumeCursor`: are engine resume primitives coherent?
- Are the `subloop`/`override` edge kinds actually exercised by any *discovered pack today*, or
  reserved-but-unproven (the brief claims planning's topology "already compiles" — verify the
  executor truly EXECUTES that topology correctly today, not just that it constructs).

Key question: is the executor a battle-tested engine, or a thin happy-path runner for the simple
demo pipelines (creative/doc) that will reveal correctness gaps the moment planning's gate-loop +
subloop + override + policy run through it? Find the gaps. Note any place the executor silently
diverges from what the legacy handler path does.
