FAIL

Independent review of exact candidate commit `6ef77bebb3c3b9f0ec0aeb478945619b54c815f3` in `/private/tmp/arnold-critique-recovery-ra-contain-20260802`. Source was not edited, no commit was amended, and no cloud or SSH state was touched.

## Pass-8 blockers

Both pass-8 blockers are refuted on this candidate, including the required pre-mutation ordering.

1. Wrong signed reconcile targets are rejected before nonce reservation, journal writes, or owner-head CAS. `_validate_reconcile_target()` compares the signed target with the authenticated unresolved `transition_target` at `arnold_pipelines/run_authority/containment.py:1035-1043`; `reconcile()` calls it at `1368-1370`, before identity lookup and all mutation paths at `1395-1410`. Durable-record recovery also validates the durable tuple/result at `1375-1379` and `1391-1394`. The target is carried into pending and indeterminate heads/occurrences and covered by the authenticated head revision at `1173-1182`, `1158-1171`, and `_head_revision()` at `424-425`.

   Regressions pass in `tests/arnold_pipelines/run_authority/test_containment.py:352-492`: unresolved issue, unresolved terminate, durable reconcile response-loss recovery, and a mismatched adopted durable result all leave the head, journal counts, and nonce map unchanged. The final-CAS response-loss recovery tests at `540-573` also recover by exact replay and by a fresh signed reconciliation.

2. A signed `envelope_type="provision"` with `operation` equal to `issue`, `terminate`, or `reconcile` is rejected before provisioning mutations. `ENVELOPE_TYPE_OPERATIONS` and `_verify_envelope()` enforce the exact operation at `containment.py:49-53` and `329-336`; provisioning calls that verifier before directory/lock/anchor/journal work at `770-807`. The regression at `tests/arnold_pipelines/run_authority/test_containment.py:79-97` confirms no head, nonce, or journal mutation.

## Remaining blocker: post-CAS reconciliation failure

`reconcile()` still performs failure-capable validation after the final owner CAS. `_finish_reconcile_checks()` calls `status()` and then `check()` for all seven effects at `containment.py:1307-1322`. The active-receipt path re-raises `PolicyRefusal` (`1310-1316`) after `_finish_pending()` has already written the journal and committed the owner head (`1195-1206`). The calls occur after mutation in the durable and normal reconciliation paths at `1382-1387`, `1391-1398`, and `1403-1411`.

Minimal reproduction, run against the candidate without source edits:

```text
issue receipt: ttl_seconds=0.05
issue final CAS: commits, then loses its response
sleep: 0.08 seconds
reconcile: raises PolicyRefusal("receipt expired")
owner head afterward: state=committed, operation=reconcile
journal cursor afterward: 2
exact retry: raises PolicyRefusal("receipt expired") again
```

The probe used a test backend that throws only after the issue's final CAS, then reconciled after the legitimate TTL expiry. Observed output was:

```text
first raises PolicyRefusal receipt expired
exact-retry raises PolicyRefusal receipt expired
committed committed reconcile journal_cursor 2
```

This is a real post-CAS failure, not merely a malformed-result test: `_validate_reconcile_result()` at `1045-1058` verifies receipt shape, digest, revision, and tuple but does not validate TTL; the final CAS then succeeds and the later `check()` rejects the expired active receipt. The durable identity/replay path does not provide a successful response because it repeats `_finish_reconcile_checks()`.

Required correction: make every failure-capable reconciliation check deterministic and complete before the final owner CAS, using one fixed evaluation time, or make post-CAS checks non-throwing and return the already-authenticated durable result. If an unavoidable post-CAS read/validation error remains, it must be represented by the existing indeterminate recovery protocol and be recoverable to an honest durable response; `reconcile()` must not commit and then report failure indefinitely on exact replay. Add a regression that forces expiry (and a transient post-CAS read failure) and asserts the required recovery/response contract.

## Independent boundary checks

- State-specific head schemas, target/occurrence equality, digest/revision coverage, and rollback/fork detection are enforced at `containment.py:648-731`, `934-1033`, and `1173-1206`; the schema and rollback tests pass at `tests/arnold_pipelines/run_authority/test_containment.py:803-848`.
- Journal replay binds reconcile records to exact tuples and validates active/terminated results and empty-result shape at `containment.py:967-989`. `_validate_reconcile_record()` and `_validate_reconcile_result()` enforce base/candidate result tuple matching before mutation at `1060-1069` and `1391-1405`.
- Nonce/idempotency identities are checked against canonical request digests and durable journal results at `1083-1126`; process-safe local locking/race coverage passes at `tests/arnold_pipelines/run_authority/test_containment.py:851-877`. This does not cure the post-CAS error above.
- The policy surface is exactly one read class plus six denied effects (`resume`, `repair`, `execute`, `publish`, `notify`, `deployment`) at `40-47`, `1417-1424`, and CLI effect choices near `1470`; the focused tests exercise all seven.
- Production owner absence remains fail-closed: production construction/provisioning raises `ReleaseAuthorityUnavailable` at `756-758` and `770-774`, and the CLI rejects non-test mode at `1482-1484`.

## Verification

Commands and results:

```text
pytest -q tests/arnold_pipelines/run_authority/test_containment.py
46 passed in 2.15s

pytest -q tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py
77 passed in 2.18s

git diff --check HEAD^ HEAD
passed
```

The local pass of the focused suite does not prove formal T0.0, does not establish the complete containment theorem, and does not authorize containment or any cloud mutation.
