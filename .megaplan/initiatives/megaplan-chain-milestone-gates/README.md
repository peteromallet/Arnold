# Megaplan milestone conformance-gate bootstrap

This one-sprint prerequisite closes the orchestration gap found while reviewing
the Native Parity and Platformization epics. Complete it before launching
`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`.

It adds a generic, content-addressed, pre-merge `conformance_gate`; reruns the
gate against the merged tree; and proves that red or stale evidence cannot be
merged or used to advance a chain. Product semantics remain owned by each
milestone's registered transition handler; the chain owns ordering, exact
receipt delivery, idempotency, transition-receipt recording, verification, and
the prohibition on bypass.

Because the current engine cannot enforce its own new pre-merge gate, this
bootstrap uses an independent, already-available verifier rather than trusting
the implementation under test. The chain may merge automatically only after
trusted external CI and that verifier emit a content-addressed attestation for
the exact proposed tree. Branch protection/merge readiness consumes that
attestation before automatic merge; the existing `final_conformance_gate`
rechecks the landed tree and produces the completion manifest. No human PR
merge is required, and a local path that cannot produce the same independent
attestation fails closed.

It also adds an exact predecessor-artifact assertion to
`chain_completed + require_manifest`, so a dependent chain can require a named
path and matching content hash from the validated completion proof map.

Finally, it adds a typed receipt-consuming transition phase followed by
post-transition verification. Native and Platform milestones use it for suffix
selection, authority/fence switches, runtime/product binding promotion, live
effects, control demotion, and stable publication.
