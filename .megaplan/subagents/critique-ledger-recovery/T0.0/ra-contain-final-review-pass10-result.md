# RA-CONTAIN independent review pass 10

`FAIL`

Reviewed exact commit `fd038f3aab9da495dda0b59a448dd8ef78fe54ee`.
This artifact was transcribed by the root orchestrator from the fresh GPT-5.6
Luna review result because its enforced read-only sandbox rejected the authorized
artifact write. The reviewer did not modify the worktree or cloud state.

## Blocking findings

1. **Final CAS result is ignored.** At
   `arnold_pipelines/run_authority/containment.py:1201-1207` and `:1302-1317`,
   a backend can return an unchanged/no-effect head without raising. The
   independent probe observed `reconcile()` return an `active` result while the
   owner head remained `indeterminate` with `operation=issue`. This is false
   success.
2. **A genuine final `StaleCAS` loses its type.** The normal finalization path's
   generic handler at `containment.py:1204-1207` converts a conflicting
   `StaleCAS` to `StorageError` and marks generic uncertainty. It must distinguish
   exact already-committed replay, genuine stale conflict, and ambiguous effect.

## Passing evidence

The independent expiry/adoption probe passed: an expired authenticated candidate
is reconciled, later policy checks fail closed, and exact replay returns the same
durable result. Tuple binding, seven effects, fixed-time validation, rollback
checks, replay/recovery, and production fail-closed construction also survived
inspection/probes. Dependency closure reported `12 passed`. The focused suite
could not start inside the read-only review sandbox because Python could not
create a temporary directory; the implementer had separately reported 48/79
passing tests.

## Required correction

Validate the exact returned owner head and backend receipt against the prepared
candidate. A no-effect/malformed/different response cannot be success. On
`StaleCAS`, read and accept only an exact already-committed candidate; otherwise
propagate the typed conflict without overwriting it as generic uncertainty.
Response loss or an unverifiable post-effect result must remain typed
indeterminate and converge through exact replay/fresh signed reconciliation.

This is not formal T0.0 evidence and authorizes no cloud mutation.
