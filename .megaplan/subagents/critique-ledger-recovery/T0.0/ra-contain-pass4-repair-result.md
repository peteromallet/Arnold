# T0.0 RA-CONTAIN pass-4 repair handoff

Repair commit: `a0334cfbc9e3bfde6aa3310c45975d539153b1f5` (parent `e019cf4519f2e54aea7164390e4e5c11e5ad5517`).

Changed contract:

- Journal replay, `status()`, `check()`, issue, terminate, and recovery now require a provisioned HMAC-authenticated owner head. The head binds cursor, journal digest, and current receipt digest; missing, corrupt, stale, ahead, mismatched, or rolled-back journal/head state refuses typed and cannot authorize.
- Mutations use durable pending intent → journal append/fsync → authenticated atomic head commit. Ambiguous failures remain indeterminate. `recover()`/`reconcile()` is owner-authorized, validates the exact candidate or base, appends an auditable reconcile record, and never silently adopts state.
- One strict validator covers receipts, issue/terminate/reconcile records, replay, and current checks. Duplicate success requires complete matching request identity and active current state; divergent fields, stale CAS, and post-termination reissue are typed.
- Issue, terminate, and reconcile enforce the capability-bound owner identity. Production trust is the accepted owner/Release Authority provisioning the head and protecting the capability secret; the local adapter does not bootstrap authority from the CLI. Credentials are never emitted.

Verification:

- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority tests/cloud/test_m1_containment_acceptance.py` — 104 passed.
- 20 repeated separate-process identical/divergent race runs — 20/20 passed.
- `git diff --check` — passed.
- Repo-wide `verify_containment` search — zero references.
- `python -m compileall -q arnold_pipelines/run_authority` — passed.

Residual limitation: this is still a locally accepted interface, not a live cloud containment decision. T0.0 remains incomplete until installed through the accepted Release Authority and used by the owner with an actual cloud containment receipt.
