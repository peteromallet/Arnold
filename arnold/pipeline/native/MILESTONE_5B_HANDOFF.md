# Milestone 5B Handoff — Human-Gate Suspend/Resume Parity

**Status:** M5B complete.  Human-gate suspend/resume parity is implemented and
verified for `writing-panel-strict`.  Graph execution remains the default
production path; native execution stays behind the existing opt-in dispatch
marker (`ARNOLD_NATIVE_RUNTIME`).

---

## Scope summary

M5B delivered human-gate parity for a single mandatory proof pipeline:

* `writing-panel-strict` — native bundle with `@phase` wrappers for
  `panel_review`, `synth`, `revise`, and a native human-gate `@decision` for
  `human_decide` (`continue → panel_review`, `stop → halt`).
* Native initial suspension writes `awaiting_user.json` and
  `resume_cursor.json` with graph-compatible top-level fields plus additive
  native restoration metadata.
* Native resume accepts `human_input={"choice": "continue"}` and
  `human_input={"choice": "stop"}`, routes through declared branches,
  validates choices fail-closed, and cleans the consumed checkpoint only after
  acceptance.
* Graph/native parity coverage compares topology hash, stage sequence,
  normalized state pause contract, folded event journal, checkpoint shape,
  and artifact inventory/content hashes under deterministic mocked workers.

**Out of scope (deferred):**

* `arnold/pipelines/deliberation/*` — deliberately deferred to M6 unless an
  explicit human kickoff approval changes scope.  No deliberation files were
  converted or parity-tested in M5B.

---

## Frozen inventory matrix

| Path | Change | Notes |
|------|--------|-------|
| `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` | Modified (T9) | Graph-default `build_pipeline()` with native resource bundle; `@phase` + `@decision` native wrappers. |
| `arnold/pipeline/native/ir.py` | Modified (T2) | Additive human-gate metadata on `NativeDecision` (`human_gate`, `artifact_stage`, `choices`, `resume_input_schema`, `override_routes`). |
| `arnold/pipeline/native/decorators.py` | Modified (T2) | `@decision` accepts human-gate parameters; `get_decision_meta` returns new fields. |
| `arnold/pipeline/native/runtime.py` | Modified (T3, T5) | Native human-gate initial suspension and resume routing with durable checkpoint semantics. |
| `arnold/pipeline/native/checkpoint.py` | Modified (T3) | `persist_native_cursor` supports additive `native_extra` and restoration metadata. |
| `arnold/pipeline/native/graph_projection.py` | Modified (T7) | Projects human-gate vocabulary, override vocabulary, routes, and suspension schema. |
| `arnold/pipeline/topology.py` | Modified (T7) | Topology hashing consumes `decision_routes`, `suspension_schema`, and override vocabulary. |
| `tests/arnold/pipeline/test_resume.py` | Modified (T1) | Graph human-gate contract freeze for `awaiting_user.json`, `HumanSuspension`, `ContractResult(SUSPENDED)`, `resume_cursor.json`. |
| `tests/arnold/pipeline/native/test_decorators.py` | Modified (T2) | Human-gate decision metadata tests. |
| `tests/arnold/pipeline/native/test_runtime.py` | Modified (T3, T5, T6) | Native human-gate suspension/resume tests including continue/stop/override/invalid-choice paths. |
| `tests/arnold/pipeline/native/test_graph_projection.py` | Modified (T7, T8) | Human-gate projection and pinned topology hash tests. |
| `tests/arnold/pipeline/test_topology_hash.py` | Modified (T8) | Human-gate topology sensitivity tests. |
| `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py` | Added (T10, T11) | Deterministic graph/native parity + native end-to-end suspend/resume proof. |
| `arnold/pipeline/native/MILESTONE_5B_HANDOFF.md` | Added (T12, T13) | This file. |

---

## Deliberation deferral note

Deliberation conversion is **explicitly deferred to M6**.  The settled M5B
scope does not include `arnold/pipelines/deliberation/*`, no deliberation
pipeline has a native bundle, and there are no deliberation parity tests.

This deferral is captured here as the authoritative scope decision for the
M5B → M6 boundary.  Expanding native human-gate coverage to deliberation
requires a separate explicit approval and kickoff.

---

## Concrete default-flip blockers

The following blockers must be resolved before native execution can become the
default path for any pipeline:

1. **Remaining migrations must prove parity.**  Every pipeline that currently
   runs through the Megaplan executor needs deterministic graph/native parity
   coverage comparable to `writing-panel-strict` before its native path can be
   promoted to default.
2. **Rollback and dual-run documentation required.**  A default flip needs a
   runbook for rolling back to graph execution per-pipeline and a process for
   dual-running native beside graph in production without duplicate side effects.
3. **Megaplan context injection gap.**  Native phases receive a lightweight
   dict context; pipelines that depend on Megaplan-specific `StepContext`
   fields (`plan_dir`, `profile`, `task`, etc.) require a compatibility shim or
   redesign before native can be the default.
4. **Observability parity.**  Native `events.ndjson` is emitted only when
   `trace_dir` is set.  Production observability, metrics, and structured
   logging must match graph-executor behavior before default promotion.
5. **Human-gate override policy parity.**  Native override routes are declared
   via `@decision(override_routes=...)`.  Graph-side override handling in
   Megaplan pipelines must be reconciled with native fail-closed semantics.
6. **Composite and multi-child suspensions.**  M5B covers single-choice
   human gates.  Composite suspensions and multi-child resume cursors are not
   yet parity-proven in native.

---

## Evidence locations

| Evidence | Location |
|----------|----------|
| Cursor examples | `tests/arnold/pipeline/test_resume.py` (graph cursor freeze) and `tests/arnold/pipeline/native/test_runtime.py` `TestHumanGateSuspension` (native cursor shape). |
| Parity traces | `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py` `TestWritingPanelStrictNativeParity`. |
| Suspend/resume tests | `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py` `TestWritingPanelStrictNativeSuspendResume`; `tests/arnold/pipeline/native/test_runtime.py` `TestHumanGateSuspension`. |
| Topology coverage | `tests/arnold/pipeline/native/test_graph_projection.py` `TestHumanGateProjection`; `tests/arnold/pipeline/test_topology_hash.py` `TestHumanGateTopologySensitivity`. |
| Pinned topology hash | `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py` `EXPECTED_WRITING_PANEL_STRICT_TOPOLOGY_HASH`. |
| End-to-end graph behavior | `tests/_pipeline/test_writing_panel_e2e.py`. |

---

## Verification summary

* Focused tests: `tests/arnold/pipeline/native/test_runtime.py`,
  `tests/arnold/pipeline/test_resume.py`,
  `tests/arnold/pipeline/native/test_graph_projection.py`,
  `tests/arnold/pipeline/test_topology_hash.py`, and
  `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
  must all pass.
* Regression sweep: `tests/_pipeline/test_writing_panel_e2e.py` and
  `tests/test_pipeline_run_cli.py` must continue to pass.
* No new failures vs the recorded baseline; pre-existing unrelated failures are
  not addressed.
