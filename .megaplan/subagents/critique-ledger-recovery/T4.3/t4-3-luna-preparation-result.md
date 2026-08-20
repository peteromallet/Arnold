# T4.3 advance Custody fence/epoch and retire v2 leases — Luna preparation

Verdict: **NO LEASE MUTATION; preparation only.**

## Subject and invariant

Consume exact T0.4 v2 tuple/lease inventory, accepted T4.1 quarantine and T4.2 RA revoke receipt. Subject includes target key, occurrence, every lease/holder/incarnation, current Custody head/epoch/fence, RA revision/fence, WBC generation/GLEKs, process identity and unresolved ambiguity. The invariant is monotonic retirement: old leases become revoked/expired under a strictly greater epoch/fence and the poisoned target key receives a durable tombstone. It is never plain-released, deleted, reset, made unclaimed, or reused for v3.

## Atomic Custody transaction

1. Under owner lock, reread exact RA/T4.1/T4.2 and current Custody head; reject mixed target or stale expected head.
2. Append one idempotent `RETIRE_TARGET_EPOCH` intent binding all known leases/holders and a no-reuse tombstone reason.
3. CAS epoch `E -> E+1` and fence generation `F -> F+1`; atomically mark every prior lease/renewal token revoked or expired and install target-key tombstone `{retired_at_epoch, quarantine_decision, nonreusable=true}`.
4. Persist canonical receipt before acknowledgement. Reread by idempotency key and exact head.
5. Project stale-holder denials to RA/WBC/launch consumers; projections do not create authority.

No gap may expose the key as claimable. Any pre-advance lease/process/renewal/release token fails with typed `STALE_EPOCH`/`TARGET_RETIRED` before owner or effect mutation. A live old process cannot renew, release-and-reclaim, transfer, resume, repair, execute, publish or notify. New successor work uses a fresh target key/occurrence/epoch namespace.

## UNKNOWN and concurrency

Response loss after intent or CAS is UNKNOWN; query Custody by idempotency key and adopt the exact committed receipt. Never repeat with a different epoch or plain-release. If head shows neither exact prior nor exact committed successor, quarantine remains and manual owner reconciliation is required. WBC applied/ack-lost outcomes remain INDETERMINATE/no-redispatch; epoch advance does not settle effects (T4.4).

Race tests: two retires; retire vs renew; retire vs release; retire vs claim/reclaim/transfer; stale process restart/PID reuse; concurrent RA revoke; response loss before/after intent/CAS/receipt; crash between lease marking and tombstone (must be impossible transactionally); deleted/corrupt tombstone; ABA epoch/key reuse; restored old database snapshot; forged current epoch; wrong tuple sharing target label. Exactly one canonical advance wins; every other operation deterministically adopts or rejects, never succeeds under old identity.

## Receipt and verification

Signed Custody receipt binds schema, intent/idempotency, exact tuple/target-key digest, prior/new head+epoch+fence, ordered prior lease/holder/token set and terminal dispositions, tombstone bytes/digest, T4.1/T4.2/RA heads, signer/key/revocation head, transaction/WAL/commit proof, UTC+monotonic window, result and ambiguity. Independent verifier reads the authoritative store from a separate read-only connection, replays the transaction, proves `new>old`, all old tokens reject, tombstone survives restart/backup restore, target key cannot be claimed, and unrelated keys remain usable.

Current execution is blocked by incomplete T4.1/T4.2 and absent accepted owner-installed Custody transaction. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is external.
