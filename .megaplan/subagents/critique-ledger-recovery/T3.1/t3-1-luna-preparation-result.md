# T3.1 atomic predeploy evidence recheck — Luna preparation

Verdict: **NOT RUN; preparation only.** No cloud contact or completion claim.

## Bound inputs

Rehash accepted T0.2 `manifest.json` SHA-256 `c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791` and T0.4 `inventory.json` SHA-256 `2984a983ae7a307d02b6d36cb53ab42122e5d9ad63d5d5eb0ff8d0c89ff5bff8`; rerun their independent verifiers, not narrative summaries. Bind independently supplied expected candidate commit/tree, build/wheel/sdist/RECORD/container/runtime/interpreter/lock/import-root/wrapper/schema/route digests, T2.6 decision/revision/fence/TTL/revocation head, both ticket blobs, and current T1/T2 review ledger.

## One atomic command contract

Implement one owner-installed `release-authority predeploy-check --expected-manifest <digest> --output <attempt-local-dir>` command. Under one read snapshot/lock it must:

1. verify T0.2/T0.4 bytes, every referenced object, independent receipt and unresolved-gap policy;
2. read authoritative target filesystem capacity: free bytes and inodes, reserved headroom, mount/device identity, quota, writable+fsyncable attempt/WAL/scratch directories, SQLite/WAL checkpoint/integrity and backup-restore probe;
3. verify exact clean integrated Git commit/tree and accepted T2.6 source universe with no current hard fail, stale/revoked/mixed receipt or unclassified delta;
4. rebuild/re-hash or verify immutable build, wheel/sdist/RECORD, container image, installed runtime, interpreter, locks, `.pth`/import roots, wrappers/services, schemas/migrations, contract bundle and model routes against the expected vector;
5. prove production adapters remain fenced until deploy grant and no old writer can mutate the selected generation;
6. reread all identities immediately before commit, then atomically emit a signed Release-Authority-owned receipt.

No shell pipeline of independent green checks may substitute for this transaction. The receipt binds command/schema digest, host/boot/mount clocks, candidate/vector, T0 digests, capacity measurements+thresholds, owner decision/fence/revocation heads, evidence-query window, every subreceipt, result and expiry. Recommended TTL: 10 minutes, monotonic and UTC bounds; deploy must start and revalidate inside TTL. Receipt grants only entry to T3.2.

## Failure and UNKNOWN semantics

Missing/unreadable/corrupt object, changed mount, low bytes/inodes, quota ambiguity, failed fsync/WAL/restore, dirty/different tree, mixed build/runtime, old writer, stale/revoked decision, hard-fail review, indeterminate provider/store observation, clock uncertainty or timeout yields typed `REJECTED` or `UNKNOWN`; both prohibit deployment. UNKNOWN is preserved and reconciled by its owner, never retried into PASS or inferred from absence.

## Finite negative matrix

Reject: one-byte T0 artifact change; missing off-volume object; swapped T0.4 source; inode exhaustion with ample bytes; byte exhaustion; wrong mount; WAL corruption/lock/checkpoint failure; unwritable scratch; forged backup restore; candidate/tree race; dirty worktree; wheel/RECORD/container/import-root mismatch; wrong interpreter/lock/schema/route; stale/revoked T2.6; current HARD FAIL; mixed receipt revision; old live writer; expired/future receipt; wall-clock rollback; signer/verifier identity substitution; lost response after receipt commit (UNKNOWN until exact owner replay); any second attempt with changed candidate.

Positive test uses a disposable filesystem/store/vector, independently rehashes the emitted receipt, and proves one atomic result under concurrent candidate/capacity/revocation changes.

## Mandatory reruns

Any candidate commit/tree, dependency lock, build artifact, image, runtime, import root, wrapper, schema, migration, route/bundle, T0 artifact, capacity/mount, owner fence/revision/key/revocation head, hard-fail ledger or receipt expiry invalidates the receipt and requires the entire atomic command again. Subcheck reuse is forbidden.

Current T3.1 cannot run: no accepted integrated candidate/T2.6 decision or owner-installed production Release Authority exists. This read-only preparation inspected existing accepted T0 hashes and recovery-plan requirements; no code, Git, cloud, provider, process, owner or checklist state was mutated. Report SHA-256 is external.
