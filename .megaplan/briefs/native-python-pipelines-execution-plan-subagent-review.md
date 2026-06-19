# Execution plan — 20 subagent review

I gave 20 DeepSeek subagents the stripped execution plan (without the load-bearing questions and predicted answers) plus the source ticket and relevant source files. Each subagent was asked to answer one question independently. All 20 completed.

## Results at a glance

| # | Question | Verdict | Notes |
|---|----------|---------|-------|
| E1 | Build native runtime first or prove parity first? | **Agrees** | Subagent emphasizes building the native runtime foundation first, but still coupled with parity proof; no conflict. |
| E2 | Preserve resume for in-flight plans? | **Agrees** | Legacy graph executor as read-only fallback; notes cursor-format difference is non-trivial. |
| E3 | Which pipeline to convert first? | **Diverges** | Predicted: toy → small Megaplan (`folder_audit`/`jokes`). Subagent: `vibecomfy_executor` first because it is smallest and already uses neutral `PipelineBuilder`. |
| E4 | How to prove parity? | **Agrees** | Golden traces (state/events/cursor/artifacts) plus graph-projection equivalence. |
| E5 | When to flip default? | **Agrees** | Phase 7, gated on full trace parity and in-flight compatibility. |
| E6 | Handle unsafe agent constructs? | **Agrees** | Compiler rejects non-serializable locals/dynamic constructs at build time. |
| E7 | Keep `arnold pipelines check` trustworthy? | **Agrees** | Derived graph view; separate static-possible and observed-runtime graphs. |
| E8 | Rollback strategy? | **Agrees** | Feature-flag gating; existing `flags.py` pattern; legacy executor warm. |
| E9 | External hosts / capsules compatibility? | **Agrees** | Derived `Pipeline` projection keeps neutral API unchanged. |
| E10 | Avoid scope explosion? | **Agrees** | Strict phase gating and parity-corpus gates. |
| T1 | How does runtime intercept phase calls? | **Agrees** | Decorator metadata + AST lowering into resumable state machine. |
| T2 | How is resume durable? | **Agrees in spirit** | Subagent described the current WAL-replay + cursor model rather than the native frame-stack cursor, but both reject frame pickling. |
| T3 | How are typed contracts enforced? | **Agrees** | Reuse `Port`/`PortRef`, `binding_map`, `evaluate_step_io_handoff()`. |
| T4 | Where are overrides injected? | **Agrees, richer detail** | Subagent mapped current three-layer injection (state, handler, routing) and noted native runtime must converge them. |
| T5 | How do subloops isolate scope? | **Agrees** | Child frame, copied state, isolated artifact dir, promotion-only boundary. |
| T6 | How does event/state persistence stay compatible? | **Agrees** | Same `state.json`/`events.ndjson` shape, same helpers, WAL-fold replay. |
| T7 | How is graph derived for observability? | **Agrees** | Decorators + AST → derived `Pipeline`; static-possible vs observed graphs. |
| T8 | How are loops/conditionals handled? | **Agrees, maps to current** | Subagent described current graph `loop_condition`/`resolve_edge` and how native `while`/`if` map onto it. |
| T9 | How do parallel panels work? | **Agrees** | `parallel(...)` primitive; current `ParallelStage`/`ThreadPoolExecutor` pattern; derives graph view. |
| T10 | How guarantee determinism/safe composition? | **Agrees** | Serializable locals, typed contracts, vocabulary routing, envelope semilattice, subloop isolation. |

**Score:** 19/20 agreement on the core answer, with 1 genuine divergence (E3) and several richer formulations.

## Key convergences

1. **Native runtime is a second executor, not a thin wrapper.** Subagents consistently identified that the runtime must reproduce state merge, envelope joining, override routing, subloop suspension lift, typed handoffs, etc.
2. **Parity corpus is the central gate.** Every subagent that touched execution order said no real pipeline converts until byte-compatible traces are proven.
3. **Graph becomes a derived view.** Subagents across E7, E9, and T7 independently reached the same conclusion: the `Pipeline` graph is projected from the native function for observability, not executed.
4. **Frame pickling is rejected.** T2 and T6/T10 subagents all emphasized WAL replay + serializable locals rather than resuming Python frames.

## Notable divergences / sharper formulations

- **E3 — First conversion target.** The plan says toy → small Megaplan pipeline (`folder_audit`/`jokes`). The subagent argued for `vibecomfy_executor` first because it is the smallest real pipeline, already uses the neutral `PipelineBuilder`, and avoids Megaplan-specific `_materialize_stage_step` complexity. This is a reasonable alternative; the plan should either adopt it or explain why a Megaplan-backed small pipeline is still preferred (to prove Megaplan semantics earlier).
- **T2 — Resume mechanism.** The predicted answer focused on the native runtime's frame-stack cursor. The subagent answered by describing the existing WAL-replay + flat `resume_cursor.json` mechanism. It is not wrong, but it shows that the stripped plan did not fully communicate the native-runtime cursor shape. The plan may need to make the frame-stack cursor design more prominent outside the Q&A section.
- **T4 — Override layers.** The subagent identified three existing injection layers (state log, `arg_overrides` on `GateStep`, `resolve_edge`). This is more detailed than the predicted answer and implies that the native runtime must preserve all three spellings, not just pre-invocation intercept.
- **T8 — Loops/conditionals.** The subagent described the current graph executor's `loop_condition` and `resolve_edge` in detail, then mapped native constructs to them. This suggests the stripped plan could more explicitly explain how native `while`/`if` will be lowered or validated against graph invariants.

## Implied plan updates

1. **Clarify the first conversion target.** Either adopt `vibecomfy_executor` as Phase 2 and move the small Megaplan pipeline to Phase 3, or keep the Megaplan pilot but add a rationale.
2. **Make the native cursor design visible in the stripped plan.** The frame-stack cursor, loop counters, and branch identifiers should be described outside the Q&A so subagents (and readers) do not default to the current flat cursor model.
3. **Expand override injection discussion.** Mention the three current layers and how the native runtime converges them.
4. **Add a loop/conditional mapping section.** Explain how native `while`/`if` correspond to graph `loop_condition` / `resolve_edge` / vocabulary validation.

## Raw outputs

Briefs: `/tmp/native_execution_q_briefs/`
Responses: `/private/tmp/native_execution_q_results/`
