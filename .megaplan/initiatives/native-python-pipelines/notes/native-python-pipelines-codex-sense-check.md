# Codex sense check — native Python pipelines plan

Run via `codex exec --sandbox read-only` on the plan + subagent review + source ticket and key source files.

## Response

The plan is directionally right, but it underestimates the runtime migration.

What feels well-supported: using explicit decorator metadata over type hints is correct. The existing `Port` / `PortRef` / `Stage` / `Pipeline` surfaces already carry the contract metadata a native layer needs, and `validator.py` is duck-typed enough that a bridge-derived graph is plausible. Keeping `build_pipeline() -> Pipeline` as the transition boundary is also the right call; registry/discovery is built around callable builders, and `vibecomfy_executor` already proves neutral graph → Megaplan graph conversion is workable. Deferring parallel/human-gate pipelines is also correct.

The biggest risk is checkpoint/resume. The plan talks about serializing generator locals and resuming at the next `yield from`; that is not a small implementation detail. Python generator frames are not a durable process-restart abstraction, and Megaplan’s executor currently does much more than “resume at stage”: state merge to disk, event/replay behavior, suspension cursor persistence, resume re-verification, envelope joining, activation events, governor/policy checks, typed port binding, loop conditions, and `_materialize_stage_step` invocation injection. A native runtime has to reproduce those semantics, not just validate handoffs and walk phases.

The graph bridge is also underspecified. Decorator metadata can define stages and contracts, but AST-derived branch discovery for real Python control flow will be brittle. A hand-built reference graph test is useful, but it does not prove runtime trace equivalence. The stronger invariant is: for the same inputs, the native run emits the same stage sequence, state shape, event journal semantics, artifacts, and resume cursor behavior as the bridged graph.

The phased order is mostly sensible, with one change: after `vibecomfy_executor`, convert one small Megaplan-executor-backed pipeline before the full Megaplan planning pipeline. Going directly from a simple neutral pipeline to the main Megaplan loop is too steep. The current later phases put “small pipelines” after Megaplan; I would move one representative small pipeline before Megaplan as a runtime-parity proving ground.

The first commit is appropriately scoped only if “runtime” means a thin test-only authoring/bridge skeleton, not the real resumable executor. A first PR with decorators, metadata capture, bridge output, `pipelines check`, and a reference-graph assertion is good. I would add one tiny synthetic run test, but not real pipeline conversion.

The single biggest thing I would validate before implementation: design and prove durable resume semantics without relying on serialized Python frame locals. Make the native pipeline compile to explicit resumable phase states, or keep execution on the generated graph until native resume parity is proven. That decision determines whether this migration is solid architecture or a fragile second executor.
