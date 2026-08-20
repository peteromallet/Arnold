# T3.2 fence old writers and effects — Luna preparation

Verdict: **NOT EXECUTED; preparation only.** No completion claim.

## Scope and inventory

The transaction targets every writer/effect path selected by the accepted T2.6/T3.1 release vector: resident/supervisor/watchdog/systemd/tmux runners; chain/plan/repair/fixer/diagnostic/notification workers; source checkout, editable `.pth`, installed wheel, wrappers and direct `python -m` imports; old containers/images/services; Run Authority, Custody, WBC, SQLite/WAL/JSONL/projection writers; Discord/webhook/Git/PR/model/cloud/deploy adapters; queued/retrying/in-flight effects; child message chunks; and unknown provider outcomes. Exact PID/start-time/cmdline/executable/import-root/container/runtime-generation/owner IDs/leases/epochs/GLEKs are derived from authoritative stores plus T0.4, never process names alone.

## Owner transaction

One Release-Authority-scoped cutover transaction, bound to the T3.1 receipt and rollback vector:

1. CAS Run Authority generation into `FENCING`; deny new grants/effects for every old generation while preserving reads.
2. Custody stops new claims, expires/revokes old leases and increments epoch; record exact occurrence/holder disposition. Unknown holders remain blocking.
3. WBC denies new starts under old fence/epoch and reconciles every old GLEK: terminal accepted remains terminal; rejected remains rejected; started/no-ack becomes `INDETERMINATE` and no-redispatchable; chunk children join their parent.
4. Quiesce owner-installed launchers/services/wrappers/containers through their supported stop capabilities; never shell-kill as authority.
5. Attest zero old writers by two independent observations separated by a bounded drain interval, including process/open-file/socket/container/service/store-head/provider queries.
6. CAS state to `FENCED` only if all owner receipts and observations match; otherwise `UNKNOWN`/abort before generation switch.

Ordering is fail-closed: RA deny precedes Custody revoke; both precede WBC reconciliation and stop effects. No owner infers another owner's success. Response loss after any owner commit is UNKNOWN until exact idempotent replay/reconciliation returns the canonical receipt; never resend the real-world effect.

## Evidence and rollback

Emit one signed bundle binding prior/current RA revision/fence, every lease/epoch, every GLEK/outcome, launcher/service stop receipt, installed/source/wrapper/container identities, two observation windows, T3.1/candidate/runtime/rollback digests, ambiguity list and expiry. Rollback may restore the old runtime selector only if schemas are compatible and a new explicit RA grant, fresh Custody epoch/leases and fresh WBC attempts are issued. Revoked leases/GLEKs are never resurrected; indeterminate effects remain unresolved. If backward compatibility is unsafe, forward-fix only.

## Finite negative matrix

Prove zero calls/writes for: stale RA revision/fence; stale lease/epoch; old GLEK; cached in-process authority; old editable `.pth`; direct source import; copied wrapper; `python -m`; old venv interpreter; old container/image; supervisor/watchdog restart; queued repair/fixer; notification chunk; Git/model/provider retry; PID reuse; forged stop receipt; missing open-file/socket observation; concurrent claim during fence; response loss at each owner boundary; provider-applied/ack-lost; ENOSPC before receipt; rollback attempting to reuse revoked identities. Any unknown/unseen writer or ambiguous effect blocks `FENCED`.

Positive concurrency test starts all surfaces, races the fence, and proves exactly pre-linearization effects have canonical receipts, post-fence effects make zero calls, and two independent observers reproduce the same zero-writer set.

## T3.2 versus T4

T3.2 is a generic generation cutover fence for all old writers/effects so deployment is safe. It does not permanently quarantine session `critique-ledger-accountability-v2-20260728`, supersede its authority history, reconcile its every historical occurrence, CAS chain selection away, or project `should_run=false`; those tuple-specific retirement actions remain T4.1–T4.6. T3.2 preserves the v2 evidence and leaves it read-only/denied, not deleted or rewritten.

Current execution is blocked by missing accepted T1 owner implementations, T2.6 decision, T3.1 receipt and owner-installed production interfaces. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is recorded externally.
