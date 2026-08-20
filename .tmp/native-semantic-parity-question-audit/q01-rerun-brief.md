# Q1 Rerun: Compiler expressiveness and parallel_map lowering

You are a DeepSeek subagent doing a focused, evidence-cited sense-check for `/Users/peteromalley/Documents/Arnold`.

The prior broad Q1 run failed to emit a final answer. Do NOT wander. Inspect only what is needed and then answer directly.

Question:
What does `parallel_map` in `arnold_pipelines/megaplan/workflows/workflow.pypeline` lower to today: a real fanout IR, or metadata passthrough that the manifest backend ignores? More broadly, does the source compiler/runtime support suspension points, dynamic fanout over runtime lists, and loop policies with typed exits, i.e. the constructs S2-S5 of the native semantic parity plan require?

Plan assumption tested:
Extraction sprints are mostly semantic extraction, not compiler/runtime feature development. If this is false, S2-S5 need compiler-feature predecessor tasks.

Required output, under 900 words:
1. Verdict: agrees with current plan, weakens it, or contradicts it.
2. Direct answer on `parallel_map` lowering today.
3. Direct answer on source/compiler/runtime support for: suspension points, dynamic fanout over runtime lists, loop policies with typed exits.
4. Exact file:line evidence.
5. Specific amendment needed, if any.

Focus files/areas:
- `arnold_pipelines/megaplan/workflows/workflow.pypeline`
- `arnold_pipelines/megaplan/workflows/planning.py`
- `arnold_pipelines/megaplan/runtime/manifest_backend.py`
- `arnold/workflow/source_compiler.py`
- `arnold/workflow/compiler.py`
- `arnold/workflow/dsl.py`
- relevant tests under `tests/`

Hard rule: no status claim without file:line evidence. If uncertain, say exactly what remains unproven.
