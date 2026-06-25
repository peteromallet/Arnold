# M3: Control Flow And Policy Lowering

## Outcome

Add the control-flow forms needed for the real Megaplan planning workflow while keeping the language restricted and manifest-first.

## Source Material

- M1 grammar/contract.
- M2 compiler core.
- `docs/arnold/python-shaped-authoring-contract.md`
- Existing `arnold_pipelines.megaplan.pipeline.build_pipeline()` and current Megaplan tests/goldens.
- Current explicit-node Megaplan pipeline shape and manifest fixtures.

## Scope

Implement and test:

- `if` / `elif` / `else` decision branches over declared decision outputs.
- Route labels and stable condition references.
- `while True` backedges for critique/revise and review/rework loops.
- Guarded/bounded loop policy where already representable in `WorkflowPolicy.loop`.
- Workflow-level policy references for timeout, retry, model routing, robustness, reprompt, approval, and suspension where those are existing manifest concepts.
- Subworkflow imports/references only as typed components with manifest-lowerable semantics.
- Negative diagnostics for ambiguous loops, unsupported mutation, unreachable control paths, and non-literal routing decisions.

## Constraints

- Do not support general Python control flow.
- Do not hide tiebreaker, override, review/rework, or loop limits inside opaque handlers when they materially affect topology.
- Do not invent new execution behavior for subflows.

## Done Criteria

- The canonical Megaplan planning topology can be represented by source-level control flow.
- The compiler can render exact DSL nodes/routes/policies for loop-heavy fixtures.
- Unsupported or ambiguous control flow fails loudly in source terms.
