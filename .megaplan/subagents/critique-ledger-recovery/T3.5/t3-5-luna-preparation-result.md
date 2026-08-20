# T3.5 production recovery and rollback canaries — Luna preparation

Verdict: **NOT RUN; preparation only.** No cloud contact, canary or completion claim.

## Preconditions and bounded authority

Consume exact accepted T1.5 singleton `simple_fixer`, T1.8 generation/rollback, T1.9 launch/stop transaction, T2.3 canary contract, fresh T3.1 receipt, T3.2 old-writer fence and unexpired T3.4 live-vector attestation. Release Authority issues one short-lived canary grant naming exact generation, tuple, occurrence, actions, effect budget, expected transitions, rollback/forward-fix vector, observer and pre-issued stop capability. Custody issues one occurrence/lease/epoch. WBC derives one parent GLEK and stable child GLEKs before effects. No watchdog, investigator, meta-repair, alternate scheduler or ad-hoc shell path is authorized.

## Minimal production sequence

1. Revalidate every precondition, fence/revision/epoch/lease/GLEK and live vector immediately before start.
2. Create exactly one synthetic, isolated, reversible recovery occurrence that exercises the production owner/store/runtime path but cannot target the real v2 session or user data.
3. Suppress the immediate trigger once; prove the three-hour reconciler claims the same occurrence and starts the same singleton fixer. For bounded test time, use an owner-authorized clock/test hook, never edit timestamps/state.
4. At each durable boundary inject response loss: occurrence claim, WBC start, provider/effect acceptance, fixer result, owner transition, notification, and completion receipt. Replay exact identities only. Applied/ack-lost becomes `INDETERMINATE`, no redispatch; owner observation may adopt the exact effect.
5. Prove immediate and delayed paths converge to one accepted result, one effect per child GLEK, no managed child/alternate fixer, and one incident-card transition.
6. Execute compatible rollback through the signed T1.8 transaction: fence new generation, checkpoint, CAS selector, attest target/schema/read compatibility and old-writer rejection, then run one read-only health probe.
7. If rollback is incompatible or an accepted active generation is damaged, do not force it: use the separately signed forward-fix vector and prove selector/runtime/owner convergence.
8. Restore the approved recovery generation through a new scoped transaction, attest it twice, revoke canary authority and expire the occurrence.

## Success, notification and abort

Success requires canonical signed receipts for every owner transition, one occurrence/fixer/effect set, exact adoption of acknowledged-unknown effects, zero redispatch, exact pre/post live vectors, rollback or forward-fix proof, restored generation, no old writer, no unresolved GLEK, and independent observation over a bounded health window. Rollback success is state/vector equality plus schema/store readability and writer fencing—not merely command exit zero.

Notify only on meaningful incident state-version transitions: at most one initial card, in-place observation updates, and one resolved transition. Two observers/200 scans must yield at most one provider-accepted notification. UNKNOWN updates the card without repeated DM. Notification loss/ack loss uses its stable child GLEK and is never blindly resent.

Abort before further mutation on expired/revoked grant, stale fence/epoch/lease, vector drift, extra writer, collision, storage reserve failure, missing stop capability, mixed receipt, schema incompatibility, failed independent observer or any UNKNOWN owner/effect not exactly reconcilable. Invoke the pre-issued stop/fence capability; preserve state/evidence. Never marker-edit, shell-kill, retry another model/fixer, relabel UNKNOWN, or continue to T3.6.

## Finite fault matrix

Inject crash/response loss before and after every step above; immediate/delayed race; two processes; stale lease/epoch/fence; duplicate occurrence/GLEK; provider applied/ack-lost; notification chunk loss; ENOSPC/EIO; selector CAS race; old writer restart; rollback target substitution; rollback schema mismatch; damaged accepted generation; forged observer/receipt; stop response loss; clock/TTL expiry. Each yields one canonical success/adoption or typed UNKNOWN/abort with zero duplicate effect.

## Evidence bundle

```text
grant-stop-and-budget.json
precondition-vector.json
occurrence-custody.json
wbc-parent-child-manifest.json
immediate-delayed-convergence.json
response-loss-matrix.json
fixer-receipt.json
notification-receipt.json
rollback-or-forward-fix-intent.json
selector-and-store-checkpoints.json
rollback-or-forward-fix-result.json
restored-live-vector.json
two-observer-health.json
revocation-and-final-status.json
independent-verifier-receipt.json
```

Every artifact binds candidate commit/tree, installed generation, RA revision/fence, Custody epoch/lease, GLEKs, monotonic/UTC window and prior artifact digests. Producer claims cannot self-verify.

Current execution is blocked by unaccepted prerequisite implementations/evidence and absent owner-installed production interfaces. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is external.
