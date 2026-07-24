# Milestone 6 Handoff — Native Pipeline Migrations

**Status:** M6 complete.  The frozen target list (`creative`, `doc`, `jokes`,
`live_supervisor`, `deliberation`) has been migrated to the
graph-default/native-bundle pattern and parity/resume coverage has been added.
Graph execution remains the default production path; native execution stays
behind the existing opt-in dispatch marker (`ARNOLD_NATIVE_RUNTIME=1` and
`state.meta.executor == "native"`).

---

## Scope summary

M6 delivered native resource bundles for every frozen target pipeline while
keeping each canonical `build_pipeline()` graph builder unchanged:

* `jokes` — native phases for `draft`, `tighten`, `emit`; parity and
  resume-after-`draft` coverage.
* `creative` — native phases mirroring `STAGE_SPECS`; parity for `joke` and
  `poem` forms and resume after `execute_creative`.
* `live_supervisor` — native phases for `classify`, `diagnose`,
  `repair_decision`, `recheck_emit`; parity/resume after `repair_decision`.
* `doc` — native phases for `outline`, `section_drafts`, `critique`, `revise`,
  `assembly`; dynamic fanout preserved inside the `section_drafts` native phase;
  parity for 0/1/3 sections and resume before/after `section_drafts`.
* `deliberation` — native bundle attached only when `profile` and `workers` are
  provided; human-gate `@decision` for `human_gate` with
  `answers_collected → draft_plan`; profile-driven layer panels wrapped as native
  phases; parity through human-gate resume and after a layer-panel barrier.

**Shared harness support added:**

* `tests/arnold/pipelines/megaplan/parity_harness.py` — `GraphTrace`,
  `compute_topology_hash_from_builder()`, and `compare_native_to_graph()` with
  all seven parity dimensions.
* `docs/arnold/pipelines/native-conversion-runbook.md` — repeatable pattern for
  future migrations.

**Out of scope (preserved):**

* `planning` and `evidence_pack` pipelines remain out of migration scope.
* No default execution flip; graph executor is still the default.
* No new pipelines were added to the M6 inventory.

---

## Frozen inventory matrix

| Path | Change | Notes |
|------|--------|-------|
| `arnold/pipelines/megaplan/pipelines/jokes/__init__.py` | Modified (T3) | Graph-default builder with attached native bundle; `@phase` wrappers delegate to `JokeStep`. |
| `arnold/pipelines/megaplan/pipelines/creative/__init__.py` | Modified (T4) | Graph-default builder with attached native bundle; `@phase` wrappers delegate to `CreativeStep`. |
| `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py` | Modified (T5) | Graph-default builder with attached native bundle; `@phase` wrappers delegate to supervisor steps; `driver = "in_process"` preserved. |
| `arnold/pipelines/megaplan/pipelines/doc/__init__.py` | Modified (T6) | Graph-default builder with attached native bundle; `section_drafts` phase wraps existing graph `dynamic_fanout(...)`. |
| `arnold/pipelines/megaplan/prompts/__init__.py` | Modified (T6) | Lazy prompt adapters to break an import-time circular dependency when importing the doc builder. |
| `arnold/pipelines/deliberation/pipelines.py` | Modified (T7) | Native bundle attached only when `profile`/`workers` present; human-gate `@decision`; profile panels wrapped in native phases. |
| `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py` | Added (T3) | Topology, full-run parity, resume-after-draft, bundle attachment. |
| `tests/arnold/pipelines/megaplan/test_creative_native_parity.py` | Added (T4) | Joke/poem parity, form/state threading, bundle attachment, resume after `execute_creative`. |
| `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py` | Added (T5) | Topology, full parity, resume after `repair_decision`, `recheck_after` normalization. |
| `tests/arnold/pipelines/megaplan/test_doc_native_parity.py` | Added (T6) | 0/1/3 section widths, dynamic fanout parity, resume before/after `section_drafts`. |
| `tests/arnold/pipelines/deliberation/test_native_parity.py` | Added (T7, T8) | Bundle attachment, missing-profile error, human-gate metadata, full parity after resume, layer-panel barrier resume. |
| `tests/arnold/pipelines/megaplan/parity_harness.py` | Modified (T2) | M6 graph/native trace comparison helpers and smoke tests. |
| `tests/arnold/pipelines/megaplan/test_parity_harness.py` | Modified (T2) | Smoke tests against `writing-panel-strict`. |
| `docs/arnold/pipelines/native-conversion-runbook.md` | Added (T10) | Accepted conversion pattern and dynamic-fanout/profile-panel guidance. |
| `arnold/pipeline/native/MILESTONE_6_HANDOFF.md` | Added (T11) | This file. |

---

## Concrete default-flip blockers (M7 input)

The following blockers must be resolved before native execution can become the
default path for any migrated pipeline:

1. **Default-flip coordination.**  A global toggle (environment variable or
   profile setting) must choose native by default while preserving a per-run
   graph override and a documented rollback path.
2. **Rollback and dual-run documentation.**  M7 needs a runbook for rolling back
   to graph execution per-pipeline and a process for dual-running native beside
   graph without duplicate side effects.
3. **Megaplan context injection gap.**  Native phases receive a lightweight dict
   context; pipelines that depend on Megaplan-specific `StepContext` fields
   (`plan_dir`, `profile`, `task`, etc.) require a compatibility shim before
   native can be the default.
4. **Observability parity.**  Native `events.ndjson` is emitted only when
   `trace_dir` is set.  Production observability, metrics, and structured logging
   must match graph-executor behavior before default promotion.
5. **Graph-born resume concerns.**  Graph-native mixed resumes (graph-born cursor
   resumed by native runtime and vice versa) need explicit contract coverage.
6. **Docs/skills refresh.**  User-facing docs and agent skills still describe the
   graph-first mental model; they need updates if/when native becomes default.

---

## Evidence locations

| Evidence | Location |
|----------|----------|
| Shared parity harness | `tests/arnold/pipelines/megaplan/parity_harness.py` |
| Harness smoke tests | `tests/arnold/pipelines/megaplan/test_parity_harness.py` `TestSmokeAgainstWritingPanelStrict` |
| Jokes parity/resume | `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py` |
| Creative parity/resume | `tests/arnold/pipelines/megaplan/test_creative_native_parity.py` |
| Live supervisor parity/resume | `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py` |
| Doc dynamic-fanout parity/resume | `tests/arnold/pipelines/megaplan/test_doc_native_parity.py` |
| Deliberation parity/resume | `tests/arnold/pipelines/deliberation/test_native_parity.py` |
| Conversion runbook | `docs/arnold/pipelines/native-conversion-runbook.md` |
| CLI validation | `arnold pipelines check creative`, `deliberation`, `doc`, `jokes`, `live-supervisor` |

---

## Verification summary

* Focused parity/resume suites for all five migrated pipelines pass.
* Existing pipeline tests for `jokes`, `creative`, `live_supervisor`, `doc`, and
  deliberation import-leak boundary continue to pass.
* Native runtime suite (`tests/arnold/pipeline/native/`) passes.
* Executor selection and package authoring contract tests pass.
* `arnold pipelines check` passes for all migrated targets except the
  pre-existing `megaplan` dataflow defects.
* No default execution flip, no graph executor removal, and no extra pipelines
  added to M6 scope.
