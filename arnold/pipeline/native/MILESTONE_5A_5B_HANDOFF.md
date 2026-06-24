# Milestone 5A/5B Handoff - Parallel Surface Complete, Human Gates Next

## Outcome

M5A landed the bounded native `parallel(...)` declaration surface, native panel
composition on top of that same primitive, projection of compiled native
parallel blocks into graph `ParallelStage` nodes, and native-projected
implementations for the two approved real pipelines:

- `select-tournament` now builds from a native `@pipeline` declaration in
  `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`.
- `epic-blitz` now builds from a native `@pipeline` declaration in
  `arnold/pipelines/megaplan/pipelines/epic_blitz.py`.

There is no remaining parallel-surface blocker deferred to M5B. M5B should
focus only on human-gate suspend/resume parity and the mandatory
`writing-panel-strict` conversion.

## Parallel Contract

`parallel(...)` is exported from `arnold.pipeline.native` and declared in
`arnold/pipeline/native/decorators.py`. It accepts a literal list or tuple of
`@phase` callables plus optional `reducer=` and `name=` keywords.

Static cardinality is part of the contract:

- empty branch sets are rejected;
- duplicate branches are rejected;
- non-callable and non-`@phase` branches are rejected;
- dynamic/non-literal branch collections are rejected by the compiler;
- `name=` must be a string literal when supplied;
- `reducer=` must resolve to a callable when supplied.

The compiler records each block as `ParallelInstruction` metadata in
`arnold/pipeline/native/ir.py`: stable block name, ordered branch names,
ordered branch callables, optional reducer, and `merge_pc`. The instruction
stream uses `NativeInstruction(op="parallel", parallel_index=...)` as the
resumable marker for that metadata.

Branch isolation is provided by the projected graph execution surface:
`ParallelStage` workers receive isolated context/state snapshots, reject known
unsafe in-process handler steps, collect child results in declaration order,
and reduce at the fan-in barrier. The neutral native runtime still treats the
parallel marker as the M5A sequential-baseline no-op while executing the
inlined branch bodies in declaration order; converted production pipelines use
the native declaration plus graph projection for the actual parallel stage
surface.

The only runtime gate remains `ARNOLD_NATIVE_RUNTIME`. No separate
`ARNOLD_NATIVE_PARALLEL` flag exists or is needed.

## Reducer Vocabulary

Reducers are callable joins, not string labels:

- no reducer: projection installs `_default_parallel_join`, which merges child
  `StepResult.outputs` into one downstream result;
- custom reducer: `ParallelInstruction.reducer` is preserved as
  `ParallelStage.join`;
- `native_panel(...)`: a thin wrapper over `parallel(...)` that builds a
  reducer prefixing reviewer outputs as `{reviewer_id}.{label}`;
- `select-tournament`: uses `join_candidate_scores` for
  `score_candidates -> pairwise_bracket`;
- `epic-blitz`: expresses high, mid, and low reviewer panels with
  `native_panel(...)`; production specialization keeps the existing
  `panel_parallel(..., merge_strategy="none")` semantics so wildcard inputs
  such as `high_panel.*`, `mid_panel.*`, and `low_panel.*` preserve legacy
  artifact lookup and reviewer ordering.

## Checkpoint Boundaries

The durable boundary for M5A proof is the fan-in barrier after a whole
parallel/panel stage has completed and before the next public stage starts.
The parity tests suspend at that boundary and resume through the graph resume
path:

- `select-tournament`: suspend before `pairwise_bracket` after
  `score_candidates`; expected cursor is
  `{"stage": "pairwise_bracket", "input": null}`;
- `epic-blitz`: suspend before `high_revise` after `high_panel`; expected
  cursor is `{"stage": "high_revise", "input": null}`.

Resume from inside an active branch is not part of M5A and should not be
reopened in M5B unless human-gate work explicitly needs it. M5B owns human
gate suspension and resume-input compatibility, not generic parallel branch
checkpointing.

## Projection And Topology

`arnold/pipeline/native/graph_projection.py` now projects compiled parallel
markers into `ParallelStage` objects. Branch phase PCs are absorbed into the
parallel stage, branch typed ports are unioned onto that stage, edges target
the merge-point successor or `halt`, and stage names are stable:

- `key_mode="pc"`: `{pipeline}__{block_name}__pc{pc}`;
- `key_mode="phase"`: the parallel block name, e.g. `score_candidates`,
  `high_panel`, `mid_panel`, `low_panel`.

Pinned topology evidence lives in:

| Surface | Expected hash | Evidence |
| --- | --- | --- |
| simple native parallel | `sha256:dcaa4e51611cff5e5bc334c66d98c3898697695facd78555ebedf4e99da7caae` | `tests/arnold/pipeline/native/test_graph_projection.py` |
| phase-keyed simple native parallel | `sha256:111211e838814c447fcd8535205b71f46d91c2e88d22fa132b63bf9a11faa8b3` | `tests/arnold/pipeline/native/test_graph_projection.py` |
| typed native parallel | `sha256:4c5023b0ae3f8c086227e8c393da23c989562bc147264e945b17a1ec5459e979` | `tests/arnold/pipeline/native/test_graph_projection.py` |
| sequential + native parallel | `sha256:33a5b6d75f4d2bff5664496e2d85a37e4b70a55465293d38aa66a5d1d4b0dac3` | `tests/arnold/pipeline/native/test_graph_projection.py` |
| `select-tournament` | `sha256:a1b1b0acb5c63b9131eb5dc05eac2144ff14b8f6aebfa9d808a6faab685a1454` | `tests/arnold/pipelines/megaplan/test_graph_baseline.py` |
| `epic-blitz` | `sha256:f3c882259d646bde6460724377f4ef41ad9d0c6883743e669c346632931aa712` | `tests/arnold/pipelines/megaplan/test_graph_baseline.py` |

Topology hashes remain `sha256:<64 lowercase hex>` strings. If a pipeline
shape intentionally changes, update the corresponding baseline and parity
assertions in the same change.

## Pipeline Composition Notes

### `select-tournament`

The native declaration is:

```python
for branch in parallel(
    [
        _native_candidate_score_0,
        _native_candidate_score_1,
        _native_candidate_score_2,
        _native_candidate_score_3,
    ],
    reducer=join_candidate_scores,
    name="score_candidates",
):
    state = yield branch(ctx)
state = yield _native_pairwise_bracket(ctx)
state = yield _native_winner(ctx)
```

`build_pipeline()` compiles/projects the declaration with `key_mode="phase"`,
then specializes the projected graph back to concrete Megaplan steps. Public
stage order is locked as:

```text
score_candidates -> pairwise_bracket -> winner
```

Typed ports remain:

- `candidate_scores` produced by `score_candidates` and consumed by
  `pairwise_bracket`;
- `bracket_result` produced by `pairwise_bracket` and consumed by `winner`;
- `winner_result` produced by `winner`.

The private `_build_legacy_graph_pipeline(...)` remains only for parity
baselines.

### `epic-blitz`

The native declaration uses `native_panel(...)` three times:

```text
high_panel -> high_revise -> mid_panel -> mid_revise -> low_panel -> readiness -> halt
```

Panel reviewer ids and prompt paths are preserved from the legacy graph:

- `high_panel`: `existing_system_reuse`, `conceptual_fit`,
  `missing_abstraction`, `epic_decomposition`, `strategic_risk`;
- `mid_panel`: `codebase_convention_fit`, `data_artifact_model`,
  `orchestration_semantics`, `agent_model_assignment`, `blast_radius`;
- `low_panel`: `implementation_feasibility`, `testability`, `edge_cases`,
  `cli_ux_details`, `migration_backcompat`.

Revision/readiness inputs preserve wildcard fan-in:

- `high_revise`: `draft`, `high_panel.*`;
- `mid_revise`: `high_revise`, `mid_panel.*`;
- `readiness`: `mid_revise`, `low_panel.*`.

`build_pipeline()` validates native projection order and entry before returning
the specialized graph. The terminal readiness stage keeps `done -> halt`.
Default metadata remains `default_profile="@epic-blitz:standard"` with
`driver=("graph", "dispatch+emit")`.

## Parity And Resume Evidence

The real-pipeline evidence files are:

- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`

Both compare graph-executor and native-projected execution for:

- topology hash;
- public stage sequence;
- normalized final state;
- folded `state_written` event journal;
- narrowed resume cursor shape;
- artifact inventory and normalized content hashes.

Artifact surfaces covered by parity include:

- `select-tournament`: `score_candidates/candidate_0.json` through
  `candidate_3.json`, `score_candidates/v1.json`, `pairwise_bracket/v1.json`,
  `winner/v1.json`, and `state.json`;
- `epic-blitz`: `draft.md`, every high/mid/low panel reviewer `v1.md`,
  `high_revise/v1.md`, `mid_revise/v1.md`, `readiness/v1.md`, and
  `state.json`.

The resume cases prove barrier suspend/resume equivalence against a full native
run for state, event fold, and artifact inventory.

## M5B Remainder

M5B is now narrowed to human-gate work only:

1. Define the native human-gate suspend/resume surface and canonical
   resume-input schema.
2. Preserve existing graph-reader cursor compatibility for human-gate resumes,
   including explicit human input and override-driven resume behavior.
3. Convert `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` to a
   native `@pipeline` while preserving:
   `panel_review -> synth -> revise -> human_decide`,
   `human_decide` choices `continue` and `stop`,
   `continue -> panel_review`, and `stop -> halt`.
4. Add parity and real human-gate suspend/resume evidence for
   `writing-panel-strict`.
5. Pull `arnold/pipelines/deliberation/` into M5B only by explicit kickoff
   decision. If it is pulled in, it must use the already-landed M5A
   parallel/panel surface and the M5B human-gate surface; no new parallel
   primitive may be added there.

Out of scope for M5B: redesigning `parallel(...)`, adding a second panel
engine, converting `select-tournament` or `epic-blitz` again, flipping the
default execution mode, graph-builder removal, or starting the M6 pipeline
sweep.

## Verification Commands

```bash
pytest tests/arnold/pipeline/native/test_graph_projection.py tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py -v --tb=short
```

