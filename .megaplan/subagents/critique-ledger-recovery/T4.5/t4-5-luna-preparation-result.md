# T4.5 CAS chain selection away from v2 — Luna preparation

Verdict: **NO SELECTION CHANGE; preparation only.**

## Canonical CAS subject

Consume the exact v2 tuple from T0.4/T4.1 and accepted T4.2 RA revoke, T4.3 Custody tombstone/epoch and T4.4 WBC reconciliation. Subject is the authoritative chain-selection owner record—not marker YAML, workspace state, process status or projection—and binds selection namespace/key, selected session/initiative/spec/chain/plan, source/runtime generation, record revision/hash, RA fence/revision and Custody epoch.

Expected old value is exactly `critique-ledger-accountability-v2-20260728` with its immutable spec/workspace/plan/runtime identities and observed selection revision. Expected new value is either an explicit owner-defined `NONE/QUARANTINED` sentinel or an already accepted successor identity; never a guessed v3, reused v2 key, marker path or mutable workspace. The operation must name both values before mutation.

## Transaction

1. Independently reread the selection owner and all T4 prerequisite heads; fail on mismatch/UNKNOWN.
2. Append one idempotent `DESELECT_QUARANTINED_CHAIN` intent binding expected old record, new sentinel/identity, reason, fence, epoch and rollback policy.
3. CAS exact record revision/hash and old tuple to the declared new value; concurrently verify v2 RA deny and Custody tombstone remain current.
4. Persist canonical owner receipt before acknowledgement and reread by idempotency key.
5. Projection reducer derives `selected=false`, `should_run=false`, `effects_admissible=false`, quarantine/revocation references and any unresolved WBC ambiguity from owner records.

The v2 marker is hashed before/after and must remain byte-identical. It may continue to contain historical fields; consumers must use the authoritative projection. No direct marker edit, rename, delete, touch, rebind or generated-state rewrite is allowed.

## Response loss, races and stale writers

Response loss after CAS is UNKNOWN; query selection owner by idempotency key and adopt the exact committed result. Never issue a different selector write. Concurrent selector change: exact same intent adopts; different successor/sentinel or revision conflicts and requires owner adjudication. No last-writer-wins.

Every stale v2 writer—resident, chain runner, fixer, watchdog, wrapper, source/editable/installed import, old container or cached process—must reread RA fence + Custody epoch/tombstone + selection revision immediately before write/effect and reject. A stale writer cannot reselect v2, overwrite the projection, edit marker or publish status. PID restart/reuse and restored old database snapshots also reject.

## Finite tests and receipt

Test exact success; wrong old tuple/revision/hash/fence/epoch; missing T4 prerequisite; two same/different CAS contenders; response loss before/after intent/CAS/receipt; projection crash/rebuild; forged projection; marker edit attempt; marker byte drift; stale cached selector; old source/editable/wheel/wrapper/container writer; watchdog relaunch; restored pre-CAS owner store; successor collision; unknown new sentinel; rollback attempting to resurrect tombstoned v2. Unrelated selections remain unchanged.

Signed receipt binds schema, intent/idempotency, namespace/key, exact old/new records, prior/new revisions/hashes, tuple/spec/workspace/plan/runtime digests, T4 prerequisite heads, RA/Custody joins, marker pre/post hash equality, projection input/output digest, CAS/WAL proof, signer/key/revocation head, timestamps and ambiguity. Independent verifier reads owner state separately, replays projection and probes stale-writer rejection.

Current execution is blocked by T4.1–T4.4 and absent accepted selection-owner CAS/projection interfaces. No code, Git, cloud, provider, process, owner, marker or checklist state was mutated. This report is the sole write; SHA-256 is external.
