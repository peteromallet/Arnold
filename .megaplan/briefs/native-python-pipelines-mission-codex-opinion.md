# Mission-aligned architecture — Codex second opinion

Prompt: `/tmp/codex_mission_opinion.md`

## Response

1. **Pick a hybrid: Option A now, Option B only after parity.**

Native Python should become the authoring source of truth, but the first runtime target should be the existing `Pipeline` graph. Treat the graph as compiled IR, not as the thing humans write.

Option B is the desired end-state feel, but not the right first product path. The current executors carry too much real semantics: resume cursors, WAL replay, typed handoff checks, loop guards, state merge, envelope joins, suspension, override routing, subloop promotion, activation events, policy/governor behavior. Rebuilding that as a direct Python-frame runtime would create a second executor before there is a parity corpus.

2. **Smallest viable first step**

Add `arnold.pipeline.native` with `@pipeline`, `@phase`, and `@decision` metadata, plus a bridge that emits today’s `Stage` / `Edge` / `Pipeline`.

The first PR should prove a tiny native function can compile into a graph that:

- passes `validator.py`;
- runs through the existing executor;
- preserves stage names, edges, ports, decision vocabulary, and typed handoff enforcement;
- has a reference-graph test comparing generated graph to hand-built graph;
- has a synthetic resume test that re-enters a known stage through the existing resume path.

No real pipeline conversion in PR one.

3. **Defer vs require**

Defer:

- direct native runtime execution;
- serializing Python locals or generator frames;
- arbitrary AST control-flow inference;
- dynamic topology;
- parallel panels;
- human gates;
- nested subpipeline suspension semantics;
- real Megaplan conversion;
- changes to `state.json`, `resume_cursor.json`, `RuntimeEnvelope`, artifacts, or WAL formats.

Require:

- explicit decorator metadata using existing `Port` / `PortRef`;
- `build_pipeline() -> Pipeline` remains the public contract;
- graph bridge is deterministic;
- unsupported Python constructs fail loudly;
- tests assert graph shape and executor behavior;
- no new runtime enforcement path.

4. **Biggest risk**

The biggest risk is author illusion: the Python function looks more expressive than the bridge can safely compile. If the bridge silently approximates control flow, observability and resume become lies.

Mitigation: keep the supported grammar narrow. Decorator metadata is authoritative. AST is allowed only as a verifier or simple branch extractor, not as clever magic. Every converted pipeline must have graph-shape parity and runtime-trace parity tests.

5. **Proof pipeline**

Pick a **toy pipeline** first, not `folder_audit` or `vibecomfy_executor`.

The proof should be:

```text
prep -> decide -> revise -> decide -> finalize
              \-> finalize
```

It needs one typed producer/consumer handoff, one decision vocabulary, one guarded loop edge, and one resume cursor into the middle. That proves the architecture without dragging in real agent behavior, filesystem audits, or Megaplan’s full planning loop.

After that, convert `vibecomfy_executor` as the first real pipeline because it already uses the neutral graph and typed ports. Then use `folder_audit` or another small Megaplan-backed pipeline before touching the canonical Megaplan planner.
