# Suspension Decision Routes Validation

## Outcome

Add generic Arnold pipeline validation for `Suspension.decision_routes` so adapters can declare human/resume decisions as graph data and get conformance errors before runtime.

This is the Arnold support slice for Astrid's pack workflow cleanup. It must stay generic: Arnold validates graph/resume consistency, while Astrid remains responsible for task-gate UI, executor ids, pack paths, and CLI behavior.

## Scope

In scope:

- Extend Arnold's neutral pipeline validator to check `Suspension.decision_routes` on suspended stages.
- Validate that every non-`None` route target matches an outgoing edge label or edge target contract as appropriate for the existing validator model.
- Validate that decision route keys are compatible with the suspension resume schema when the schema declares an enum of allowed human decisions.
- Preserve backward compatibility for stages without `decision_routes`.
- Preserve `None` route values for terminal/cancel/no-next-stage decisions.
- Add focused tests in the Arnold worktree for valid routes, missing route targets, schema/route mismatch, `None` routes, and backward compatibility.
- Keep diagnostics machine-readable with stable error codes.

Out of scope:

- Adding Astrid executor ids, Astrid pack metadata, task-gate events, project paths, or CLI ack behavior to Arnold.
- Retiring Megaplan's legacy `_pipeline` bridge.
- Redesigning Arnold's edge/dataflow model.
- Moving media/content validators or package-discovery metadata contracts unless a touched test proves they block this validation work.
- Creating a broad human-gate DSL in Arnold.

## Locked Decisions

- Target repo/worktree: `/Users/peteromalley/Documents/.worktrees/arnold-clean-extraction`.
- Target API: neutral `arnold.pipeline.*`.
- `Suspension.decision_routes` already exists and round-trips through JSON; this plan validates it rather than redesigning it.
- Diagnostics should live in the existing pipeline validation path, preferably alongside control-flow validation unless the codebase has a clearer existing pass for suspension/resume consistency.
- Route validation is generic graph conformance, not Astrid-specific behavior.

## Open Questions For The Planner

- In the existing validator model, should `decision_routes` values be validated against outgoing edge `label`, outgoing edge `target`, or both? The Astrid integration intends values like `"next"` / `"repeat"` as edge labels, but the planner should inspect current Arnold conventions before implementation.
- What exact JSON-schema shape should be recognized for resume decision enums? Common forms may include `{"properties": {"choice": {"enum": [...]}}}` or package-specific equivalents.
- Should schema route-key mismatches be defects or warnings when the schema is too loose to prove an enum?

## Constraints

- Do not regress existing Arnold pipeline validator tests.
- Do not introduce a dependency from `arnold.pipeline` to `arnold.pipelines.megaplan`.
- Do not make route validation require all suspensions to have `decision_routes`.
- Do not reject `None` route targets.
- Keep error codes stable and specific enough for downstream adapters to assert on them.

## Done Criteria

- `arnold.pipeline.validator.validate()` reports a defect when a suspended stage declares a non-`None` decision route that cannot map to an outgoing edge.
- `validate()` reports a defect when the suspension resume schema clearly declares an allowed decision enum and `decision_routes` contains keys outside it or omits required enum decisions, if the planner determines omission should be invalid.
- `validate()` accepts valid decision route maps such as `{"approve": "next", "reject": "repeat"}` when matching outgoing edges exist.
- `validate()` accepts terminal route values such as `{"cancel": None}`.
- Existing pipelines without `decision_routes` remain valid.
- Existing `Suspension.to_json()` / `from_json()` tests still pass.
- Focused Arnold tests pass, including:
  - `tests/arnold/pipeline/test_validator.py`
  - `tests/test_pipeline_subloop.py`
- The existing broad Arnold focused subset used by the Astrid integration remains green or any failure is explained and fixed.

## Touchpoints

- `arnold/pipeline/validator.py`
- `arnold/pipeline/types.py`
- `tests/arnold/pipeline/test_validator.py`
- `tests/test_pipeline_subloop.py`
- Any nearby resume/suspension validation tests discovered by the planner.
