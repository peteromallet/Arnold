# M3: Executor Convergence

## Outcome

Arnold has one blessed executor path. The production-capable Megaplan walker is purified into the generic executor behind hook interfaces instead of being replaced by a weaker parallel runner.

## Scope

In scope:

- Compare `arnold/pipeline/executor.py` with `arnold/pipelines/megaplan/_pipeline/executor.py`.
- Identify production features currently only in the Megaplan executor: activation, I/O contracts, state merge, governor, typed ports, suspension, policy hooks, and observability.
- Move generic behavior into the canonical Arnold executor behind injected hooks.
- Keep Megaplan lifecycle and planning policy in Megaplan-specific hooks/adapters.
- Add a thin runner API, such as `run_step`, `next_steps`, and `run_pipeline`, that delegates to the canonical executor and existing step machinery.
- Keep the legacy executor path as a compatibility shim until parity is proven.

Out of scope:

- Building a second independent runner.
- Deleting `auto.py` before dual-green replay.
- Moving Megaplan gate vocabulary into Arnold.

## Locked Decisions

- The canonical executor is `arnold.pipeline`-owned.
- Megaplan-specific behavior is injected, not imported by the generic executor.
- Parity gates decide when compatibility shims can be deleted.

## Done Criteria

- `evidence_pack` runs on the canonical executor.
- Megaplan runner calls delegate through the canonical executor for the targeted path.
- Pipeline parity tests byte-match existing artifacts where byte matching is meaningful.
- Where timestamps/IDs differ, semantic comparison tests prove equivalence.
- No new generic executor imports from `arnold.pipelines.megaplan`.
