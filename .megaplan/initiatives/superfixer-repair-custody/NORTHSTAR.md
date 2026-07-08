---
superseded_by: custody-control-plane
---

# Superfixer Repair Custody North Star

The superfixer must not lose custody of repairable work.

When a cloud plan or chain becomes blocked, the system should be able to answer, from durable evidence rather than derived labels alone:

- whether the blocker is repairable, human-gated, terminal, or a broken-superfixer condition
- which canonical blocker identity is being handled
- which repair request exists for it
- whether a repair attempt has been claimed, dispatched, is running, or has ended
- which actor owns the repair attempt
- what evidence proves recovery, retryable failure, terminal failure, or human requirement

The target architecture keeps plan state, repair queue records, repair attempts, watchdog reports, and L3 audits in one coherent custody story. A repairable blocker must not be accepted in one layer and invisible to another. `manual_review` must not be a dispatch policy. Unknown or ambiguous blockers must fail safe rather than silently auto-repairing.

The first milestone is intentionally narrow: establish the repair-custody core. It should not expand into full lock-service extraction, full auditor redesign, or broad deployment hardening unless those are necessary to prove the custody contract.
