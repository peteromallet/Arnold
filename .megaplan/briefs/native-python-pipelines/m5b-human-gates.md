## Handoff artifacts

- Human-gate resume-input schema, override/resume routing rules, and compatible cursor examples.
- Parity and resume evidence locations for `writing-panel-strict` and any explicitly approved second human-gate pipeline.
- Explicit M6 inventory matrix showing convert vs out-of-scope decisions and whether `deliberation` remained for M6 or was already completed here.
- Remaining blocker list for the default-flip milestone, limited to pipeline conversions and rollout concerns rather than generic suspend/resume uncertainty.

## No-go conditions

- M5A has not proven the parallel/panel runtime and projected-graph surfaces on real pipelines.
- The human-gate cursor shape, interaction envelope, or resume-input schema is still ambiguous at kickoff.
- Work is expanding into new parallel/panel primitives rather than suspend/resume parity.
- `deliberation` is being pulled in informally after implementation starts instead of by an explicit kickoff decision.

# Milestone 5B — Human-gate parity and writing-panel-strict

## Outcome

The native runtime supports human-gate suspend/resume parity, `writing-panel-strict` runs natively with parity, and the epic has a clean handoff into the final M6 conversion sweep.

## Scope (IN)

- Native human-gate suspend/resume parity:
  - Native `@decision` or helper surface that suspends with an explicit resume-input schema.
  - Resume cursor compatibility with existing `resume_cursor.json` readers and native checkpoint restoration.
  - Resume via supplied human input or explicit override, with trace/state parity against the graph executor.
- Pipeline conversion:
  - Convert `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` to a native `@pipeline`.
  - Capture graph-executor golden traces and assert native parity for stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, and topology hash.
  - Prove suspend/resume across the real human gate.
- Optional second real pipeline only by explicit re-scope at kickoff:
  - `arnold/pipelines/deliberation/` may be pulled forward if one additional real human-gate proof point is required after reviewing M5A and `writing-panel-strict`.
  - If pulled in, `deliberation` must use only the already-landed M5A parallel/panel surface plus the M5B human-gate surface; no new runtime primitive may hitchhike on that choice.

## Scope (OUT)

- `parallel(...)`, panel composition, `select-tournament`, and `epic-blitz` (handled in M5A).
- Remaining graph-backed pipeline migrations (`creative`, `doc`, `jokes`, `live_supervisor`, and any M6 sweep work).
- Flipping the default execution mode.
- Graph-builder removal.

## Locked decisions

- Human-gate suspension must preserve the existing interaction envelope and resume cursor shape used by graph-executor readers.
- `writing-panel-strict` is the mandatory proof pipeline for this milestone; `deliberation` only enters by explicit kickoff choice, not by silent scope creep.
- No new runtime primitive beyond hook/runtime/checkpoint/projection parity is allowed in M5B.
- The graph executor remains the default for production runs throughout this milestone.

## Open questions

- Is `writing-panel-strict` alone sufficient human-gate proof, or does the chain need `deliberation` converted here as a second real pipeline?
- What exact resume-input schema should be canonical for native human-gate stages?
- How should override-driven resume vs explicit human-input resume appear in parity fixtures and trace assertions?
- If `deliberation` is pulled in, are any of its panel-join semantics still missing after M5A?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes where exercised.
- Must keep the chain settings locked to `partnered-5` / `codex` / `thorough` / `high`.
- Must keep M6 sweep work out of this milestone unless `deliberation` is explicitly approved at kickoff.

## Done criteria

- Human-gate suspend/resume works end-to-end in the native runtime and produces compatible cursors.
- `writing-panel-strict` has a native implementation and passes parity tests against graph-executor golden traces.
- Resume from suspension works for `writing-panel-strict`.
- If `deliberation` was explicitly pulled in, it also has parity and suspend/resume proof with no new primitive work.
- Derived graphs containing human-gate stages validate and produce the expected topology hashes.
- All existing tests still pass.
- M6 handoff contains a frozen inventory decision matrix rather than a runtime-discovered target list.

## Touchpoints

- `arnold/pipeline/native/runtime.py` (suspend/resume execution path)
- `arnold/pipeline/native/checkpoint.py` (cursor serialization and restore)
- `arnold/pipeline/native/hooks.py` (human-gate hook integration and suspend decisions)
- `arnold/pipeline/native/ir.py` (decision metadata carried into runtime/projection)
- `arnold/pipeline/native/graph_projection.py` (human-gate topology projection)
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` (conversion)
- `arnold/pipelines/deliberation/` (optional second proof pipeline)
- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py` (new)
- `tests/arnold/pipeline/native/test_human_gate_resume.py` (new or extended)

## Anti-scope

- Do not reopen `parallel(...)` or panel-composition design here.
- Do not convert `select-tournament` or `epic-blitz` here.
- Do not start the remaining M6 pipeline sweep here.
- Do not flip the default execution mode.
- Do not pull `deliberation` in informally after kickoff.
