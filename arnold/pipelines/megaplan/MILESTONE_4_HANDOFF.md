# Milestone 4 Handoff — Megaplan Native Pipeline Parity

**Status:** M4 complete.  The Megaplan planning pipeline is now declared via the
native `@pipeline` compiler, projected into a graph that matches the legacy
hand-built topology, and executable by both the legacy graph executor and the
native runtime.

---

## What M4 Delivered

1. **Canonical native declaration** (`arnold/pipelines/megaplan/pipeline.py`)
   - `megaplan(ctx)` is a `@pipeline("megaplan")` generator describing the full
     planning flow: prep → plan → critique → gate → (revise loop / tiebreaker)
     → finalize → execute → review.
   - `build_pipeline()` compiles the declaration, projects it via
     `project_graph(key_mode="phase")`, and returns the native-derived graph
     when its topology hash matches the Step 3 baseline.
   - Phase wrappers (`_native_prep`, `_native_plan`, …) adapt the neutral
     native dict context to the existing Megaplan `StepContext` and delegate
     to the legacy step classes, so no step logic was rewritten.

2. **Compiler / projection fixes**
   - `arnold/pipeline/native/compiler.py` and `graph_projection.py` now honor
     per-function metadata (`__native_projection_*__`) for merging duplicate
     phase PCs into public stages, attaching decision vocabulary/routes, and
     preserving custom edges and loop guards.
   - `_coerce_step_result` preserves StepResult-shaped objects that already
     carry an `envelope` (e.g. Megaplan `StepResult`), instead of stripping it.

3. **Executor interoperability**
   - `arnold/pipeline/executor.py` gained native-runtime opt-in dispatch:
     when `ARNOLD_NATIVE_RUNTIME=1` and the state carries `meta.executor = "native"`,
     execution routes to `run_native_pipeline` or a runner adapter discovered in
     `Pipeline.resource_bundles`.
   - `arnold/pipelines/megaplan/_pipeline/executor.py` now accepts both Megaplan
     and generic Arnold `Stage` instances, so the native-derived generic pipeline
     can run through the legacy graph executor unchanged.
   - `arnold/pipelines/megaplan/_pipeline/_bridge.py` routes resume cursors:
     native-born cursors force the native runtime, graph-born cursors force the
     graph executor, corrupt native cursors fail closed.

4. **Megaplan native runner / hooks**
   - `arnold/pipelines/megaplan/native_runner.py` wires Megaplan-specific hooks,
     schema registry, and step-IO policy into the neutral native runtime.
   - `arnold/pipelines/megaplan/native_hooks.py` implements the nine real
     native hook callbacks with Megaplan semantics.

---

## Topology Baseline

```python
_EXPECTED_TOPOLOGY_HASH = (
    "sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30"
)
```

The hash is computed from stage names, edges, decision/override vocabularies,
and declared typed ports.  The native-derived pipeline matches this hash exactly.

---

## Test Baseline

Run the M4-relevant suites in the engine worktree:

```bash
# Neutral native substrate
python -m pytest tests/arnold/pipeline/native -q

# Generic executor + selection
python -m pytest tests/arnold/pipeline/test_executor_selection.py -q

# Megaplan parity + port declarations + golden traces
python -m pytest tests/arnold/pipelines/megaplan -q
```

### Current results (engine worktree, post-M4 fix)

| Suite | Result |
|-------|--------|
| `tests/arnold/pipeline` | 1882 passed |
| `tests/arnold/pipelines/megaplan` | 416 passed |
| `tests/arnold/pipelines` (non-megaplan) | 261 passed, 2 skipped |

No M4-related failures remain.

---

## Known Limitations (Expected)

- Override routing (`override_force_proceed`, `override_abort`) and native
  suspension/resume cursor persistence are exercised by the golden-trace tests
  in "blocked" scenarios only.  Full live override/suspension parity is M5a/M5b
  work.
- The native-derived `build_pipeline()` step field is a `_NativePhaseStep`
  wrapper rather than the raw legacy step instance.  Tests that previously
  asserted exact step equality have been updated to assert wrapper identity
  and stage topology instead.

---

## Next: M5a–M7

- **M5a** — Live Megaplan smoke test through the native runtime.
- **M5b** — Roll through remaining Arnold pipelines one at a time (run, fix,
  repeat) until each executes end-to-end under the native path.
- **M6** — Hardening, edge-case fixes, and documentation.
- **M7** — Epic closeout, final acceptance, and merge to `native-python-pipelines`.
