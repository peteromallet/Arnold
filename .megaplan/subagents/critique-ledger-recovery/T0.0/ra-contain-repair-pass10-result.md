# RA-CONTAIN repair pass 10 — Luna candidate

Repaired from exact clean candidate `fd038f3aab9da495dda0b59a448dd8ef78fe54ee`.

New clean commit: `6ec8066041687fa45c3e2b71760ec7874f8d027a`
(`Repair RA-CONTAIN final CAS and stale reconciliation`).

## Repair

- Centralized committed-head preparation and final-CAS response validation for
  issue/terminate transitions, normal reconciliation finalization, and durable
  reconciliation resume. Every returned head is authenticated, including its
  backend receipt, and compared field-for-field with the prepared candidate
  across owner identity, state, sequence, revision, operation, tuple-bound
  transition metadata, cursor, journal/result digests, request digest, and
  candidate fields. The backend-generated receipt is independently verified.
- Handled `StaleCAS` separately. A stale response is accepted only when an
  authenticated current owner head is the exact prepared committed candidate
  and the exact durable record/result is present. Conflicting stale heads are
  propagated as typed `StaleCAS`; they are not converted to generic
  uncertainty or overwritten.
- Hardened indeterminate acknowledgement: the current authenticated head must
  still be the expected transition or exact attempted candidate before the
  indeterminate marker can advance it. Read failure remains typed indeterminate
  and does not mutate an unverified/conflicting head. Existing response-loss
  and exact/fresh signed reconciliation convergence behavior remains intact.
- Added regressions for true no-op/unchanged final CAS, altered response,
  missing receipt, exact already-committed `StaleCAS`, conflicting `StaleCAS`,
  stale reconciliation read failure, owner/journal/nonce mutation boundaries,
  and restart recovery. Existing response-loss, expired-candidate adoption,
  and fail-closed policy checks remain covered.

## Verification

- `pytest -q tests/arnold_pipelines/run_authority/test_containment.py` — **55 passed**
- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py` — **86 passed**
  (the prior 48 focused and 79 dependency-closure tests remain included)
- `python -m compileall -q arnold_pipelines/run_authority` — passed
- `git diff --check` — passed
- Scoped Ruff fatal/undefined-name check on the touched implementation/tests — passed
- Worktree is clean at the new commit.

No deployment, SSH, cloud mutation, master-checklist edit, or formal T0.0 claim
was made. This is only a candidate for another independent review; accepted
Release Authority provisioning and production deployment remain out of scope.
