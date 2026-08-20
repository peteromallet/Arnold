# RA-CONTAIN repair pass 9 — Luna candidate

Candidate repaired from exact commit `6ef77bebb3c3b9f0ec0aeb478945619b54c815f3`.

New commit: `fd038f3aab` (`Repair RA-CONTAIN reconciliation finalization`)

## Repair

- Moved reconciliation result, receipt, tuple, digest, revision, state, TTL, and all seven policy evaluations into deterministic preflight before the final owner CAS, using one fixed evaluation instant.
- Added owner-head candidate preparation that authenticates the complete head locally while deliberately skipping backend-receipt verification for the owner-generated receipt that does not exist until CAS.
- Removed all failure-capable `status()`/`check()` validation after successful reconciliation CAS. Successful reconciliation now returns the exact prevalidated durable result directly.
- Preserved typed indeterminate handling for final-CAS uncertainty and exact/fresh signed recovery paths.
- Corrected expired active-candidate handling: reconciliation adopts and commits an authenticated candidate even after TTL expiry; subsequent `check()` remains fail-closed.
- Added regressions for expired-candidate issue response loss, active-result post-CAS transient read failure, exact replay after each issue boundary, and durable replay behavior. Existing wrong-target, durable-result-tuple, provisioning-operation, lock/expiry, genesis, nonce, rollback/fork, race, and seven-effect coverage remains in the suite.

## Verification

- `pytest -q tests/arnold_pipelines/run_authority/test_containment.py`: 48 passed.
- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py`: 79 passed.
- `python -m compileall -q arnold_pipelines/run_authority`: passed.
- `git diff --check` and staged diff check: passed.
- Ruff was run against the touched implementation/test files; it reports 65 pre-existing legacy style findings in the implementation plus one pre-existing unused test variable. No unrelated style cleanup was applied.

The worktree is clean. No deployment, SSH, cloud mutation, master-checklist edit, or formal T0.0 claim was made.
