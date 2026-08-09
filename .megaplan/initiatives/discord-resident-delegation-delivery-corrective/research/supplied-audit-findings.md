# Supplied Audit Findings

## Audit signal

The corrective epic is grounded in four supplied findings:

1. Provenance is path-dependent, and burst attribution can select the wrong request/reply target.
2. Inbound turns and acknowledgements are not restart-safe.
3. Launch idempotency does not prevent duplicate execution or duplicate side effects.
4. Delivery state and recovery logic are fragmented across runtime records, delegated-agent manifests, cursors, and sweeps.

## Corrective interpretation

These are one lifecycle-integrity problem rather than four isolated bugs. A patch that repairs only terminal reply lookup still leaves inbound loss and duplicate execution possible. A launcher-only idempotency check still leaves stale workers and outbound sends unfenced. A new outbox without one authoritative ledger adds another source of truth. The epic therefore establishes a single lifecycle identity, transaction and state-machine boundary first, then routes inbound custody, delegation, acknowledgement, terminal delivery, recovery, and migration through it.

## Evidence standard

Implementation must demonstrate correctness under process death, replay, duplicate callbacks, reordered burst members, concurrent workers, provider timeouts, and legacy-state recovery. Green happy-path tests or mutable cursor inspection alone do not close the findings.
