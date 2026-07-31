# Retired characterization crosswalk

This records why two module-wide-skipped characterization suites were deleted
and where each live assertion family is enforced. The retired suites described
obsolete execution models; keeping them skipped created inventory debt without
protecting current behavior.

| Retired assertion family | Current authoritative coverage | Disposition |
| --- | --- | --- |
| Twelve-step pipeline identity, order, routes, capabilities, and compiled shape | `tests/arnold_pipelines/megaplan/test_workflows_planning.py`, `test_workflows_planning_lowered_topology.py`, and `test_topology_golden.py` | Superseded by the current authored/lowered topology and byte-locked manifest coverage. |
| Authored `.pypeline` source location and lowering of nested wrappers | `test_workflows_planning.py` and `test_workflows_planning_lowered_topology.py` | Preserved against the canonical source and current visible child topology. |
| Auto-driver terminal, retry, blocked, resume, timeout, callback, and iteration-cap branches | `tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`, `test_s6_auto_event_consumption.py`, and `tests/orchestration/test_phase_result.py` | Superseded by focused live-driver contracts that exercise current receipts and transitions. |
| Authorization, stale-fence, custody, and recovery denial paths absent from the pre-authority corpus | `tests/run_authority/`, `tests/custody/`, `tests/m9/`, and `tests/m10/` | Current model adds stronger fail-closed assertions; the old golden traces could not represent these contracts. |
| Golden regeneration and volatile normalization helpers local to the retired auto-driver corpus | None | Test-harness implementation only, not a product contract; no live assertion was lost. |

The deleted executable modules were
`tests/characterization/test_auto_drive.py` and
`tests/characterization/test_pipeline_golden.py`. The committed auto-drive
corpus remains because the chain hinge, CI hook, supervisor replay corpus, and
oracle fixtures consume selected records as compatibility inputs; retiring the
obsolete generator test does not retire those live consumers.
