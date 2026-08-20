# T4.2 revoke v2 grants and effect admission — Luna preparation

Verdict: **NO REVOCATION; preparation only.**

## Exact subject

The subject is the immutable tuple identified by T0.4 and the accepted T4.1 quarantine decision: session `critique-ledger-accountability-v2-20260728`, initiative/spec/chain/plan identities, source/runtime generation, branch/worktree/workspace/marker identities, every old RA grant/revision/fence, Custody occurrence/lease/epoch, WBC parent/child GLEK, launcher/fixer/diagnostic/notification/publication identity and unresolved provider effect. Names or marker status alone are not identity.

T4.2 consumes—but does not create—the VERY HARD T4.1 tuple quarantine. It revokes grants/effect admission. It does not advance Custody epoch/leases (T4.3), reconcile all GLEKs (T4.4), CAS chain selection (T4.5), or freeze evidence resources (T4.6).

## Owner transaction

1. Independently resolve the exact T4.1 decision, T0.4 target set and current RA/Custody/WBC heads; reject missing/extra/mixed targets.
2. Under one RA transaction, append a tuple-scoped revocation superseding every old grant and install a monotonic deny fence. Bind expected revision, quarantine decision, operation set, reason, termination and audit/reopen capability.
3. Immediately reread the RA head and require exact canonical revocation receipt.
4. Project the deny fence to every admission consumer; projections are disposable and never the authority.
5. Probe all operation surfaces with stale/current old identities and prove rejection before Custody/WBC/provider calls.

## Operation matrix

`resume`, `repair`, `execute`, `publish`, `notify`, `model`, `Git/PR`, `deploy`, diagnostic launch, fixer trigger, watchdog/supervisor relaunch and child-message chunks are `INADMISSIBLE_REVOKED_TUPLE`. Read-only status/evidence/owner reconciliation remains admissible. Stop/fence/revoke operations remain admissible only with their pre-issued current capabilities. No auto-approval, manual-review boolean, marker, retry tier or new wrapper may override the deny.

Every effect admission joins exact RA revision/fence + T4.1 decision, current Custody epoch/lease, WBC GLEK/generation and installed runtime. T4.2 may observe the old Custody epoch but cannot mint T4.3's successor. Any missing/stale/unknown join rejects before effect.

## UNKNOWN, response loss and projections

Response loss after revocation commit is `UNKNOWN`; query RA by idempotency key and adopt the exact receipt. Never issue another semantically different revoke or permit effects meanwhile. Existing provider-applied/ack-lost WBC outcomes remain `INDETERMINATE` and no-redispatchable; revocation neither relabels nor resends them. Projection shows `effects_admissible=false`, exact authoritative decision/revision and ambiguity, but must not claim leases advanced, GLEKs reconciled, marker retired or session completed.

## Finite negatives

Prove zero downstream calls for: stale grant/fence; pre-revocation cached authority; current old lease/epoch; old parent/child GLEK; direct Python call; `python -m`; editable/source import; installed wheel; copied wrapper; systemd/tmux/watchdog; old container/image; environment-selected source; marker `should_run`; manual-review clear; auto-approval; alternate model tier; diagnostic/fixer path; notification retry/chunk; Git/PR/publish; two concurrent revokes; lost response before/after commit; forged projection; partial target set; wrong tuple sharing a name; expired/revoked signer; restart/PID reuse. Unrelated tuples must remain unaffected.

## Receipt

Emit one signed RA receipt binding schema, decision/idempotency IDs, exact tuple and target-set digest, T4.1 decision, prior/new RA heads, all superseded grants, deny operations, allowed read/reconciliation operations, signer/key/revocation head, timestamps/TTL, projection digest, probe matrix, downstream call counts, ambiguity list and reopen capability digest. Independent verifier rehashes raw RA state and probes installed/source/wrapper/container routes.

Execution is currently blocked by incomplete T4.1 and absent accepted installed owner interfaces. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is external.
