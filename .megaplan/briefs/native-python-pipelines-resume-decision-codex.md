# Resume architecture decision — Codex (GPT-5.5, high reasoning)

Prompt: `/tmp/codex_resume_decision.md` (unbiased framing of Option A vs Option B).

## Response

**Recommendation: start with Option A, with a hard bridge contract.** Native Python should be authoring sugar in the first phase: decorators collect metadata, the bridge emits the existing `Stage`/`Edge`/`Pipeline`, and the current executors keep running the graph.

Option B should not be first. It would require reproducing resume, state merge, event/journal behavior, suspension cursors, typed handoff enforcement, subloop promotion, loop guards, governor/policy behavior, invocation materialization, and observability. That is a second executor. Worse, you still need graph output for `check/list/describe`, dashboards, capsules, and external hosts.

### 1. First Phase

Ship **A now, B later only behind parity tests**. Keep `build_pipeline() -> Pipeline` as the stable surface. A native `@pipeline` function may become the source authoring form, but runtime execution remains graph-based.

This best satisfies the hard constraint: existing in-flight plans remain resumable after conversion. If stage names, edges, artifact layout, cursor shape, and state schema stay identical, old runs can resume under the same executor semantics.

### 2. 6–12 Month Consequences

**Option A enables:**
- Faster migration with low operational risk.
- Native-looking authoring for simple and medium pipelines.
- Continued compatibility with `arnold.pipeline.run_pipeline()`, `RuntimeEnvelope`, CLI discovery, dashboard graph views, and capsules.
- Incremental conversion: `vibecomfy_executor`, one small Megaplan-backed pipeline, then main Megaplan.
- A strong parity corpus: bridge graph equals reference graph, runtime trace equals old graph trace.

**Option A forecloses for now:**
- Arbitrary Python runtime control flow.
- Runtime-dependent dynamic topology.
- Persisting live locals or reconstructing native frames.
- Removing the graph executor soon.

**Option B enables:**
- True Python-as-runtime semantics.
- Explicit resumable phase states.
- Cleaner future support for Pythonic loops, nested calls, and possibly dynamic fan-out.

**Option B forecloses or endangers:**
- Safe near-term migration.
- Easy in-flight resume compatibility.
- Single-runtime simplicity during transition.
- Trustworthy observability unless graph derivation is still built.

The practical hybrid is: **A is the product path; B is an R&D path gated by proving it can replay old graph semantics byte-for-byte where it matters.**

### 3. Biggest Risk

The biggest A risk is that the bridge-derived graph diverges from the Python function authors think they wrote. If AST branch inference becomes clever, dashboards and checks can lie.

Mitigation: make decorator metadata authoritative, keep the supported authoring grammar narrow, and require tests for every converted pipeline:
- bridge graph matches a hand-built reference graph;
- stage sequence matches the old pipeline;
- state shape, cursor, event/journal fold, artifacts, and terminal status match;
- a paused old graph-driven run resumes after conversion.

### 4. Do Not Do In First PR

- Do not convert real pipelines.
- Do not implement durable native resume.
- Do not serialize generator locals.
- Do not infer arbitrary Python control flow.
- Do not add parallel panels, human gates, subpipeline suspension semantics, or native-only CLI dispatch.
- Do not change `RuntimeEnvelope`, `state.json`, `resume_cursor.json`, artifact layout, or executor selection.

### 5. Smallest POC

Add `arnold.pipeline.native` with `@pipeline`, `@phase`, `@decision`, metadata capture, and a bridge that emits a normal `Pipeline`.

Use one test-only native pipeline:

```
prep -> decide -> (revise -> decide loop | finalize)
```

Prove:
- `validate()` / `arnold pipelines check` accepts the bridge graph;
- the generated graph equals a reference graph;
- existing graph executor runs it;
- typed handoff enforcement is reused;
- a synthetic resume cursor re-enters the expected stage through the existing executor.

That POC de-risks the decision without committing to a second runtime.
