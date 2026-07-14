---
type: implementation-note
date: 2026-07-14
status: partial-prelaunch-guard-implemented
schema: custody-control-plane-chain-binding-status-v1
---

# Chain execution binding implementation status

## Verified incident mechanism

The corrective authored bundle was C1-C6 (`chain.yaml` SHA-256
`1c7336d4...`, North Star `e6168abb...`), while the copied remote bundle at the
same path was the old S1-S4 sequence (`6b9516d6...`, North Star `902eeba4...`).
State selection used a filename derived from the spec **path**, so changed bytes
reused the progressed cursor. At **2026-07-13T15:20:06Z**, the retained log
started old `s1-operational-semantic-health` while resuming corrective plan
`c1-contract-reality-20260711-1433`; reconciliation had no cross-identity rule
to reject that pairing. An ordinary state save then replaced the observed spec
hash with the current bytes. The exact historical overwrite/relaunch command is
not recoverable because the mutable marker was replaced and no launch receipt
was retained.

## Implemented outside the milestone chain

Generic chain control now computes an immutable launch identity containing the
active `chain.yaml` SHA-256, ordered milestone label/index/brief sequence,
top-level and milestone North Star/brief hashes, the explicitly intended
initiative revision and path, and import-resolved source/editable runtime roots
and revisions. The intended revision is verified against committed initiative
spec/asset content before binding.

For chains with `driver.execution_binding: required`, progressed legacy state
without a launch identity fails closed. Ordinary state saves preserve the
immutable `launched_identity`. State load/resume and ground-truth reconciliation
recompute the active identity before normalization or cursor mutation and raise
`chain_execution_binding_drift` on disagreement. Chain status deliberately
loads without adopting drift and exposes `expected`, `active`, and exact
`drift_fields`.

The custody chain opts into this mode, requires editable/import-root equality,
and deliberately keeps `intended_initiative_revision` unresolved. Therefore it
cannot bind or start from the current dirty/unlanded initiative revision.

Regression tests recreate the WBC incident (C1 state bound to old S2-S4 while
the source declares corrective C2-C6), mutate a later brief, mutate the North
Star, remove a launch binding from progressed state, and change runtime
revision. Load/resume/reconcile stop without rewriting the stale cursor, while
status displays both identities.

## Still planned gates

The current implementation does not mint the deliberately absent prelaunch
receipt, normalize and compare cloud-uploaded local/remote bundles, implement an
operator-approved rebind event, or enforce the cumulative North Star receipt at
every milestone close/handoff. It also does not yet bind whole-tree dirty diff,
wrapper/config/template/schema digests, process identity, or expose the new
comparison in every cloud/resident status projection. Those remain blocking
acceptance work; the `contains_text` launch precondition is only a sentinel and
must not be treated as proof.

No chain, service, install, merge, deployment, or restart was performed while
adding this guard.
