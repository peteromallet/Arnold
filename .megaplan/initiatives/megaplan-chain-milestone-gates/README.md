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
bootstrap is deliberately non-self-hosted: prepare its implementation PR
outside `megaplan chain`, require trusted external CI and independent review,
and merge it manually. Only then run this one-milestone chain to verify the
signed/content-addressed PR attestation, exercise the landed behavior, and
produce the completion manifest. Local/no-PR execution without that attestation
fails before launch. Its current `final_conformance_gate` is a post-merge
backstop, not authorization for the implementation merge.

It also adds an exact predecessor-artifact assertion to
`chain_completed + require_manifest`, so a dependent chain can require a named
path and matching content hash from the validated completion proof map.

Finally, it adds a typed receipt-consuming transition phase followed by
post-transition verification. Native and Platform milestones use it for suffix
selection, authority/fence switches, runtime/product binding promotion, live
effects, control demotion, and stable publication.
