# M6: Explain, Render, And Shipped Pipeline Support

## Outcome

Make workflow behavior easy to visualize and apply the authoring model beyond the canonical Megaplan pipeline where it is ready.

## Source Material

- M1-M5 outputs.
- Shipped/example pipeline inventories from the cleanup chain.
- Existing inspect/render/explain tooling.

## Scope

Implement:

- Source-first explain output showing steps, prompts, decisions, routes, loops, policies, suspensions, and subflows.
- Rendered graph/topology views derived from authored workflow source and lowered DSL.
- Shipped/example pipeline scaffolds or migrations where the V1 grammar is sufficient.
- Documentation examples that lead with workflow `.py` files.
- Negative examples for unsupported/far-out workflows that should remain rejected in V1.

## Constraints

- Do not expand grammar just to migrate an example pipeline.
- Do not make generated files part of the user-maintained authoring contract.

## Done Criteria

- It is possible to visualize exactly what happens throughout the Megaplan workflow.
- Documentation and examples make `workflow.py` the obvious editing surface.
- Shipped pipeline support demonstrates composability without hiding complexity.
