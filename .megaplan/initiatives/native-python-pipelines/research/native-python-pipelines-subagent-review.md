# Native-Python pipelines — 10 subagent review

I gave each of the 10 load-bearing questions from `native-python-pipelines-plan.md` to an independent DeepSeek subagent. Each subagent was given the plan document, the source ticket, and pointers to specific source files, but was **not shown the predicted answer**. It was asked to explore the codebase and form its own answer.

All 10 completed successfully (total agent time ~933s, wall time ~212s with 5 workers).

## Results at a glance

| # | Question | Verdict | Notes |
|---|----------|---------|-------|
| 1 | How does a phase declare I/O? | **Agrees** | Decorator metadata using existing `Port`/`PortRef`. Suggested contract-helper pattern (`contract.consumer_port`). |
| 2 | How are typed contracts enforced at runtime? | **Agrees, richer detail** | Identified two existing enforcement paths (build-time `validator.py`, runtime `executor.py`/`_evaluate_cursor_handoff`) and recommended calling `evaluate_step_io_handoff()` directly from the native runtime. |
| 3 | How does checkpoint/resume work inside loops / subloops? | **Agrees, richer detail** | Listed concrete fields to serialize (yield-point identity, iteration counter, local-variable snapshot, pipeline frame identity) and mapped them to existing files (`resume.py`, `wal_fold.py`, `subloop.py`, `types.py`). |
| 4 | Where exactly do overrides get injected? | **Agrees** | Pre-invocation intercept inside `@decision` wrapper; cites `routing.py` and `planning/operations.py`. |
| 5 | How is the graph derived for `arnold pipelines check`? | **Agrees, richer detail** | Decorators authoritative; AST is conditional-branch proof. Walked through how `if`/`while` map to `Edge`/`loop_condition`. |
| 6 | How do parallel panels / fan-out map to native Python? | **Agrees, richer detail** | Proposed `yield from parallel(...)` with static and dynamic forms, `join` callable, `max_workers`. Correctly identified which pipelines need it immediately vs. which can defer. |
| 7 | How does the CLI decide native vs. graph? | **Agrees, richer detail** | `build_pipeline() -> Pipeline` remains the stable contract; native-only runner is an end-state opt-in after observability/resume parity. |
| 8 | How do external hosts / capsules interact? | **Agrees, richer detail** | Confirmed `arnold.pipeline.run_pipeline` surface and capsule's static/runtime hash requirements. Emphasized bridge is load-bearing for external consumers even though they don't call it directly. |
| 9 | How do subloops compose without leaking checkpoint scope? | **Agrees, richer detail** | Frames are stacked, never merged; only promotion result crosses boundary; copied state and isolated artifact dirs. |
| 10 | How do we avoid breaking in-flight plans? | **Agrees, richer detail** | Immutable compatibility surface: `runtime_envelope`, top-level state keys, artifact layout, manifest hash. Gave a 9-step migration checklist. |

## Key convergences

1. **Decorator metadata is the single source of truth.** Every subagent concluded that `@phase(consumes=..., produces=...)` should use the existing `Port`/`PortRef` vocabulary, not Python type hints or runtime inference.
2. **The bridge is load-bearing during transition.** Subagents 5, 7, and 8 independently reached the same conclusion: the native layer must produce a normal `Pipeline` graph so `arnold pipelines check`, `arnold run`, dashboards, and capsules keep working unchanged.
3. **Resume/observability parity gates the native-only runner.** Multiple subagents warned that switching to a native-only runner requires identical `state.json`, event journal, artifact layout, and derived graph introspection.
4. **Subloop isolation mirrors `SubloopStep`.** Subagent 9 found the same pattern the plan predicted: separate artifact dir, copied state, promotion-only boundary, stacked cursors.

## Notable new details / sharper formulations

- **Contract enforcement is already split into neutral modules.** Subagent 2 traced the exact functions (`evaluate_step_io_handoff`, `resolve_step_io_policy`, `classify_step_io_contract`) and noted they are already pipeline-agnostic — the native runtime can call them directly rather than reimplement.
- **Checkpoint format can be an evolution, not a replacement.** Subagent 3 proposed enriching the existing `resume_cursor.json` with `iteration` and `frame_id` rather than inventing a new format.
- **Override injection is a pre-invocation intercept, not post-step routing.** Subagent 4 framed this more precisely than the predicted answer: the wrapper short-circuits before the handler runs, preserving handler internals untouched.
- **Parallel primitive should be a single `parallel(...)` callable.** Subagent 6 sketched a concrete API (`yield from parallel(pessimist=..., optimist=..., join=...)`) and noted it should be built in Phase 5 after the core runtime is proven.
- **Migration checklist has testable checkpoints.** Subagent 10 produced a concrete table including manifest-hash comparison, event-journal replay, and resuming a live graph-driven `state.json` under the native runtime.

## Divergences / open questions

- **No subagent disagreed with the predicted answers.** The only differences were depth and framing.
- **One subtle risk surfaced twice:** AST derivation of conditional branches could drift from the actual Python control flow. Subagent 5 and the predicted answer both flag this, but neither proposed a concrete verification mechanism beyond "run the validator." This is worth an explicit test corpus that asserts the derived graph matches the runtime trace for each native pipeline.
- **Type hints vs. decorator metadata.** Subagent 1 explicitly warned against making type hints authoritative because the existing contract metadata (schema versions, taint, cardinality) cannot be expressed in Python types. This aligns with the plan but is worth writing into an ADR/authoring convention so future contributors don't drift toward PEP 484 overloading.

## Recommended next steps

1. **Capture the bridge contract as an ADR.** The unanimous finding that `build_pipeline() -> Pipeline` is the stable transition contract should be documented and enforced (e.g., a registry check that every pipeline module exposes it).
2. **Add a native-runtime proof-of-concept PR** with one test-only `@pipeline`, as suggested in the plan. Use it to validate that `arnold pipelines check`, a synthetic run, and a synthetic resume all work end-to-end.
3. **Build the AST-to-graph verifier early.** Before converting real pipelines, add a test helper that compiles a native function with the bridge and asserts the derived `Pipeline` matches a hand-built reference graph.
4. **Keep the migration checklist.** Subagent 10's checklist is more detailed than the original predicted answer. Consider adopting it as the acceptance criteria for each pipeline migration.

## Raw outputs

The subagent briefs and full `.txt` responses are at:

- Briefs: `/tmp/native_q_briefs/`
- Responses: `/private/tmp/native_q_results/`
- Report: `/private/tmp/native_q_results/_report.json`
