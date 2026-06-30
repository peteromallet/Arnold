# JoinFn Status

`JoinFn` is retained in this M6 batch because it still has production callers.

Current production references:

- `megaplan/_pipeline/pattern_dynamic.py` imports `JoinFn` and uses it for `panel_from_artifact`, `dynamic_fanout`, and the internal fanout step dataclass fields.
- `megaplan/_pipeline/pattern_joins.py` imports `JoinFn` and returns it from `majority_vote()` and `weighted_vote()`.
- `megaplan/_pipeline/patterns.py` re-exports `JoinFn` as part of the public pattern surface.

The audit did not find `JoinFn` on the M5c control-interface path. The retained alias is therefore not a control mechanism and is not evidence that planning `STATE_*` values remain load-bearing there. It remains a pattern-library callable over `StepResult` until a separate de-planning refactor replaces that public surface with a structured reduce/aggregate result.

`PromoteFn` was not widened or rewritten in this batch. Its current production callers already return routing-key shaped data through the existing subloop path, so there was no JoinFn deletion fallout to reconcile here.
