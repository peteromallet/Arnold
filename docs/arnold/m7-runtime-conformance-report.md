# M7 Runtime Conformance And Installed Artifacts Report

## Outcome

Python-shaped workflow authoring is behaviorally equivalent to the manifest
runtime path in source, editable checkout, wheel, and sdist installs.

## Proof summary

| Claim | Evidence |
|---|---|
| Authored source → DSL → manifest → runtime execution equivalence | `tests/arnold/workflow/test_authoring_runtime_equivalence.py` compiles the M3 Python-shaped fixtures and runs them through `arnold.execution.run` with the journal-backed backend. Each fixture completes, emits the expected shape events (branch selection, bounded loop iterations, subpipeline enter/exit), and is deterministic across two runs. |
| Manifest identity / provenance stability | `test_compiled_authoring_manifest_hash_is_stable` shows recompilation yields identical `manifest_hash` and `topology_hash`, and that the runtime does not mutate the manifest hash. The Megaplan identity ledger (`docs/arnold/manifest-identity-report.json`) is unchanged after regeneration. |
| Event journals, resume cursors, suspension, loop/retry, review/rework semantics | Covered by the existing canonical execution gate (`tests/arnold/execution/test_canonical_fixture.py`) plus the new authoring fixture runs. The bounded-loop fixture exercises the same `loop_iteration` journal events and max-iteration enforcement as the explicit-DSL loop node. |
| Wheel/sdist install includes workflow source, prompt resources, component metadata | `tests/installed_wheel/test_m7_runtime_conformance.py` asserts the wheel contains `arnold_pipelines/megaplan/workflows/planning.py`, `components.py`, `__init__.py`, prompt `.py` resources, `pipeline_ids.json`, and the Megaplan `SKILL.md`. |
| Deleted legacy surfaces remain absent | The M7 wheel/sdist test asserts the wheel and sdist lack `arnold/pipelines/megaplan`, `arnold_pipelines/megaplan/_pipeline`, `arnold_pipelines/megaplan/stages`, and `arnold_pipelines/megaplan/_compatibility`. The installed venv still cannot import those modules. |
| Failure cases remain deterministic and diagnosable | Invalid authored sources continue to raise `SourceCompileError` with stable `DiagnosticCode`s (tested by `tests/arnold/workflow/test_python_authoring_fixtures.py`). |

## Test results

- `tests/arnold/workflow/test_authoring_runtime_equivalence.py`: **13 passed**
- `tests/arnold/workflow/test_canonical_megaplan_conformance.py`: **26 passed**
- `tests/installed_wheel/test_m7_runtime_conformance.py`: **1 passed**
- `tests/arnold/execution/test_canonical_fixture.py`: **10 passed**
- `tests/arnold_pipelines/megaplan/test_workflows_planning.py`: **9 passed**
- `tests/arnold_pipelines/megaplan/test_topology_golden.py`: **9 passed**

## Constraints honored

- No permanent compatibility shims were added.
- Topology parity alone was not treated as sufficient; execution equivalence was
  verified end-to-end.
- Generated ledgers remain derived artifacts only.
