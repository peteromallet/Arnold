# M5 - Native Test And Golden Trace Cleanup

## Objective

Replace the old graph-parity and graph-baseline test contract with native-truth tests and native-owned golden traces, while explicitly naming every old-contract suite that must be rewritten, narrowed, or deleted.

## Files To Change And Instructions

- `tests/arnold/pipelines/megaplan/parity_harness.py`
  Replace the graph-vs-native comparison harness with native-truth trace helpers.
- `tests/arnold/pipeline/native/parity_trace.py`
  Rewrite helper semantics around native canonical traces instead of parity with graph execution.
- `tests/parity/test_graph_projection_parity.py`
  Delete or rewrite into direct projection-contract coverage that no longer treats graph parity as the oracle.
- `tests/parity/test_no_state_carry.py`
  Fold the useful state-carry assertions into a native-truth suite.
- `tests/parity/fixtures/workflow_next_matrix.json`
  Keep only if still needed by rewritten native-truth coverage; otherwise remove it with the old parity suite.
- `tests/test_pipeline_parity.py`
  Delete or rewrite as native runtime behavior coverage.
- `tests/test_pipeline_planning_parity.py`
  Delete or rewrite as native planning behavior coverage.
- `tests/test_workflow_topology_parity.py`
  Delete or rewrite as topology-contract coverage that does not compare against the graph runtime.
- `tests/test_workflow_topology_parity_gate.py`
  Delete or rewrite as a native-contract gating test.
- `tests/editorial_parity.py`
  Delete or rewrite as behavior coverage under the native contract.
- `tests/_pipeline/test_planning_discovered_parity.py`
  Delete or rewrite as manifest/discovery behavior coverage.
- `tests/_pipeline/test_receipt_planning_parity.py`
  Delete or rewrite as receipt behavior coverage under the native path.
- `tests/arnold/pipeline/native/test_graph_parity.py`
  Remove graph-parity posture; keep only direct projection or execution contract checks that still matter.
- `tests/arnold/pipeline/native/test_runtime_parity.py`
  Rewrite around native runtime behavior rather than parity with graph execution.
- `tests/arnold/pipeline/test_model_seam_parity.py`
  Rewrite to assert the model seam behavior directly.
- `tests/arnold/pipelines/deliberation/test_native_parity.py`
  Convert to native-truth coverage for deliberation.
- `tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
  Convert to native-truth coverage for `creative`.
- `tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
  Convert to native-truth coverage for `doc`.
- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
  Convert to native-truth coverage for `epic_blitz`.
- `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
  Convert to native-truth coverage for `jokes`.
- `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
  Convert to native-truth coverage for `live_supervisor`.
- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
  Convert to native-truth coverage for `select_tournament`.
- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
  Convert to native-truth coverage for `writing_panel_strict`.
- `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py`
  Rewrite fixture expectations around native canonical behavior.
- `tests/arnold/pipelines/megaplan/test_native_parity.py`
  Rewrite the suite so native runtime is the baseline, not one side of a parity comparison.
- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
  Make native golden traces authoritative.
- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
  Collapse this into one explicit temporary legacy baseline suite or delete it if the remaining legacy assertions can live in `test_legacy_pipeline_baseline.py`.
- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
  Keep only the minimum graph-compatibility assertions that must survive until M7.
- `tests/arnold/pipelines/megaplan/test_parity_harness.py`
  Rewrite or delete alongside `parity_harness.py`.
- `tests/arnold/pipelines/megaplan/test_step_contracts_parity.py`
  Rewrite as direct step-contract coverage.
- `tests/arnold/pipelines/megaplan/data/native_parity/__init__.py`
  Rename the data package to match the new canonical golden-trace layout if it remains.
- `tests/arnold/pipelines/megaplan/data/native_parity/scenarios.py`
  Keep scenario definitions only if they still drive native canonical goldens.
- `tests/arnold/pipelines/megaplan/data/native_parity/escalate_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/execute_review_artifact_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/happy_finalize_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/override_abort_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/override_force_proceed_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/revise_loop_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/suspension_resume_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.
- `tests/arnold/pipelines/megaplan/data/native_parity/tiebreaker_golden_graph_trace.json`
  Replace with a native canonical golden or delete it.

## Verifiable Completion Criterion

- Every named old-contract suite has been either rewritten, narrowed into one deliberate legacy suite, or deleted.
- Native traces and native-owned golden fixtures are the default truth for canonical Megaplan and migrated packages.
- At the end of M5, at most one explicit legacy graph baseline suite remains, and it is named and justified.

## Native Representation Alignment

- Matrix rows affected: Plan artifact/version metadata; Golden trace regeneration guard; Behavior parity with existing Megaplan.
- Expected status change: substrate `enabled` with fixed native-truth scenarios and a regeneration guard; final report conformance still waits on composition M6.
- Proof artifacts: golden scenario manifest, semantic diff checklist, rewritten native-truth tests, and an explicit legacy-baseline inventory.
- False-pass guard: tests must fail on unreviewed regenerated goldens; green tests after overwriting trace fixtures are not proof.
- Deferrals: static topology snapshots with untaken branches and handler-purity conformance remain owned by composition M4/M6.
- Canonical paths/imports: tie each golden fixture to the canonical pipeline/import it exercises, not to removed graph-era parity helpers.

## Risks And Blockers

- Rewriting tests before M3.5 and M4 stabilize will generate noisy diffs and false confidence.
- Golden-trace regeneration can hide semantic changes if scenario coverage is not kept constant.
- Deleting old suites too fast can erase the only signal that a compatibility shim is still required for M7.

## Dependencies

- Depends on M3, M3.5, and M4.
- Must finish before M6 rewrites docs and before M7 attempts destructive purge.
