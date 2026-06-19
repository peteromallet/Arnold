**Prep Recommendation**

1. **Outcome**: Deliver a native Python pipeline runtime where decorated `async` pipelines execute as resumable state-machine programs, while graph projection preserves validation, observability, capsules, and legacy compatibility.

2. **Scope sizing**: Split into an epic. This is not one ~2-week megaplan.
   Milestones:
   1. Native foundation: decorators, compiler skeleton, checkpoint cursor, runtime loop, graph projection, toy parity pipeline.
   2. Parity corpus and first real pilot, preferably `vibecomfy_executor`, then one Megaplan-shaped toy.
   3. Megaplan semantics: overrides, state merge, WAL, contracts, subloops, loop guards.
   4. Main `megaplan` conversion behind a flag with trace parity.
   5. Parallel/human-gate primitives and remaining pipeline migrations.
   6. Default flip, legacy fallback, cleanup, docs.

3. **Overall plan difficulty**: **5/5**. This is an executor replacement with resume semantics, cursor compatibility, graph projection, contracts, override ordering, and in-flight plan safety; a bad plan could pass ordinary tests while breaking non-local runtime invariants.

4. **Profile**: `partnered-5`.

5. **Robustness**: `thorough`.

6. **Depth**: `high`.

7. **Vendor/modifiers**: `@codex +prep --in-worktree`.

8. **Exact CLI for first milestone**:

```bash
python -m arnold.pipelines.megaplan init /Users/peteromalley/Documents/megaplan/.megaplan/briefs/native-python-pipelines-execution-plan.md \
  --profile partnered-5 \
  --robustness thorough \
  --depth high \
  --vendor codex \
  --with-prep \
  --in-worktree native-python-runtime-m1-foundation \
  --prep-direction "Treat this as epic milestone 1 only: design and implement the native foundation behind a feature flag. Scope to decorators, compiler/state-machine skeleton, checkpoint/frame-stack cursor, runtime dispatch loop, contract bridge, graph projection, and a test-only proving pipeline. Do not convert live Megaplan. Explicitly resolve the first real pilot target divergence: evaluate vibecomfy_executor versus folder_audit/jokes and record the chosen next milestone handoff."
```

9. **Prep-direction guidance**: Prep must narrow the current broad execution plan into a milestone-1 brief with hard anti-scope. It should map existing executor, cursor, contract, WAL, override, and graph-check touchpoints; make the native frame-stack cursor visible outside Q&A; and produce a written handoff for milestone 2.

10. **Top risks**:
   - Durable resume is the load-bearing problem: CPython frames cannot resume after death, so AST/state-machine lowering and serializable locals must be designed correctly first.
   - Semantic parity can drift invisibly across `state.json`, `events.ndjson`, cursor shape, contract handoffs, override routing, and envelope joins.
   - Graph projection can lie unless the supported Python subset, static possible graph, observed runtime graph, and topology hash rules are locked down early.
tokens used
24,557
**Prep Recommendation**

1. **Outcome**: Deliver a native Python pipeline runtime where decorated `async` pipelines execute as resumable state-machine programs, while graph projection preserves validation, observability, capsules, and legacy compatibility.

2. **Scope sizing**: Split into an epic. This is not one ~2-week megaplan.
   Milestones:
   1. Native foundation: decorators, compiler skeleton, checkpoint cursor, runtime loop, graph projection, toy parity pipeline.
   2. Parity corpus and first real pilot, preferably `vibecomfy_executor`, then one Megaplan-shaped toy.
   3. Megaplan semantics: overrides, state merge, WAL, contracts, subloops, loop guards.
   4. Main `megaplan` conversion behind a flag with trace parity.
   5. Parallel/human-gate primitives and remaining pipeline migrations.
   6. Default flip, legacy fallback, cleanup, docs.

3. **Overall plan difficulty**: **5/5**. This is an executor replacement with resume semantics, cursor compatibility, graph projection, contracts, override ordering, and in-flight plan safety; a bad plan could pass ordinary tests while breaking non-local runtime invariants.

4. **Profile**: `partnered-5`.

5. **Robustness**: `thorough`.

6. **Depth**: `high`.

7. **Vendor/modifiers**: `@codex +prep --in-worktree`.

8. **Exact CLI for first milestone**:

```bash
python -m arnold.pipelines.megaplan init /Users/peteromalley/Documents/megaplan/.megaplan/briefs/native-python-pipelines-execution-plan.md \
  --profile partnered-5 \
  --robustness thorough \
  --depth high \
  --vendor codex \
  --with-prep \
  --in-worktree native-python-runtime-m1-foundation \
  --prep-direction "Treat this as epic milestone 1 only: design and implement the native foundation behind a feature flag. Scope to decorators, compiler/state-machine skeleton, checkpoint/frame-stack cursor, runtime dispatch loop, contract bridge, graph projection, and a test-only proving pipeline. Do not convert live Megaplan. Explicitly resolve the first real pilot target divergence: evaluate vibecomfy_executor versus folder_audit/jokes and record the chosen next milestone handoff."
```

9. **Prep-direction guidance**: Prep must narrow the current broad execution plan into a milestone-1 brief with hard anti-scope. It should map existing executor, cursor, contract, WAL, override, and graph-check touchpoints; make the native frame-stack cursor visible outside Q&A; and produce a written handoff for milestone 2.

10. **Top risks**:
   - Durable resume is the load-bearing problem: CPython frames cannot resume after death, so AST/state-machine lowering and serializable locals must be designed correctly first.
   - Semantic parity can drift invisibly across `state.json`, `events.ndjson`, cursor shape, contract handoffs, override routing, and envelope joins.
   - Graph projection can lie unless the supported Python subset, static possible graph, observed runtime graph, and topology hash rules are locked down early.
