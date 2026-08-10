# Milestone 2 — Parity corpus and small pipeline pilot

## Outcome

A reproducible parity-corpus harness plus the first small Megaplan-backed pipeline running natively behind a feature flag, with byte-compatible traces (stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, topology hash) against its graph-executor twin.

## Scope (IN)

- Parity-corpus harness:
  - Capture stage sequence, `state.json` snapshots, `events.ndjson` folds, `resume_cursor.json` shapes, artifact layouts, and topology hashes from the existing graph executor.
  - Store golden traces under version control (tests/arnold/pipeline/native/parity_corpus/).
  - Diff helper that compares native and graph traces while masking run-specific identifiers (timestamps, run IDs) and stable topology hashes.
- Small pipeline pilot (default: `folder_audit`):
  - Express the chosen pipeline as a native `@pipeline` async function using `@phase` / `@decision` decorators.
  - Preserve existing handlers and contracts; reuse existing `Port`/`PortRef` vocabulary.
  - Run it behind a per-pipeline feature flag (`native_runtime: true` in envelope or pipeline manifest).
  - Assert trace/state/event/artifact parity against the graph-executor golden trace for the same inputs.
  - Prove resume from a native checkpoint: run to suspension, restart process, resume, and finish with identical final state.
- Feature-flag wiring so the converted pipeline defaults to the graph executor unless explicitly opted in.
- Update the Milestone 3 handoff document with any cursor-schema or contract-edge adjustments discovered during the pilot.

## Scope (OUT)

- Other real pipelines (`megaplan`, `vibecomfy_executor`, `creative`, `doc`, etc.).
- Megaplan-specific semantics beyond what the chosen small pipeline minimally exercises: complex override vocabularies, subloop promotion/suspension-lift, envelope joining, loop-condition guards, human gates.
- `parallel(...)` primitive.
- Changing the default execution mode.
- Removing or deprecating the graph executor or graph builders.

## Locked decisions

- The first real pilot is `folder_audit` unless the Milestone 1 handoff explicitly revises the choice; this brief can be updated before `megaplan init` if M1 discovers a better candidate.
- Parity is proven per-pipeline, not blanket: native output must match the graph-executor golden trace for the converted pipeline.
- `state.json`, `events.ndjson`, `resume_cursor.json`, and artifact layouts remain byte-compatible where exercised.
- The graph executor remains the production default for all pipelines during this milestone.

## Open questions

- What exact fixtures and mock boundaries are needed to run `folder_audit` deterministically in CI for parity capture?
- Which identifiers are stable enough to include in the golden trace, and which must the diff helper mask?
- Does the native checkpoint cursor schema from M1 need adjustment to support the small pipeline's resume shape?
- Should parity traces be captured once per release or regenerated automatically when the pipeline manifest changes?

## Constraints

- Must not break existing tests, `arnold pipelines check`, or in-flight plans.
- Must run behind a feature flag.
- Must reuse existing `evaluate_step_io_handoff()` and contract types.
- Must not change persistence formats.

## Done criteria

- Parity-corpus harness can capture and compare traces for a target pipeline.
- Golden trace for `folder_audit` (or revised pilot) is committed and reproducible.
- Native version of the pilot pipeline compiles, validates, and runs through the native runtime.
- Native and graph-executor runs produce parity-equivalent traces for the same inputs.
- Resume from a native checkpoint succeeds across a process restart and yields the same final state as an uninterrupted run.
- All existing tests still pass.
- Milestone 3 handoff document captures any schema or scope revisions.

## Touchpoints

- `arnold/pipeline/native/` (extend with any fixes discovered in M1)
- `arnold/pipelines/folder_audit/` (or revised pilot)
- `arnold/pipeline/executor.py` (reference behavior)
- `arnold/pipeline/step_io_handoff.py` (contract enforcement reuse)
- `arnold/runtime/envelope.py` (`RuntimeEnvelope`)
- `arnold/runtime/wal_fold.py` (event journal fold)
- `tests/arnold/pipeline/native/parity_corpus/` (new)
- `tests/arnold/pipelines/folder_audit/test_native_parity.py` (new)

## Anti-scope

- Do not convert the main `megaplan` pipeline.
- Do not implement override injection, subloops, or parallel panels here.
- Do not change `arnold pipelines check` CLI behavior beyond native-runtime awareness.
- Do not remove `PipelineBuilder` or `Stage`/`Edge` types.
