# RA-CONTAIN pass-8 repair

Commit: `6ef77bebb3` (`Repair RA-CONTAIN reconciliation target binding`)

Implemented only the two confirmed blockers:

- Authenticated `transition_target` fields now bind pending/indeterminate heads and occurrences. Reconcile validates the signed target and durable/adopted result before nonce reservation or CAS, including issue/terminate recovery, durable reconcile recovery, response-loss retry, wrong targets, and result mismatch. Reconcile records now carry strict authenticated `exact_tuple` fields.
- Canonical envelope type/operation validation rejects every signed `provision` envelope whose operation is `issue`, `terminate`, or `reconcile`, before anchor/journal/nonce mutation.

Tests/checks:

- `pytest -q tests/arnold_pipelines/run_authority/test_containment.py` — 46 passed
- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py` — 77 passed
- Ruff fatal/undefined-name subset, `compileall`, and `git diff --check` — passed
- Worktree clean after commit

The repository has no formatter configuration and retains pre-existing Black/Ruff style findings and unrelated mypy findings; no unrelated reformatting was introduced. This is a local review candidate only: no deployment, cloud mutation, checklist edit, or formal T0.0 completion is claimed.
