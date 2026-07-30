# Megaplan Milestone Conformance Gates — North Star

Megaplan chains must be able to stop a milestone before its changes become
merge-eligible when required content-addressed conformance evidence is missing,
red, stale, or bound to different source. A successful pre-merge gate is
recomputed after merge so the accepted receipt names the authoritative merge
commit and tree.

The capability is generic orchestration infrastructure. It does not know about
Megaplan Native Parity, `.pype`, GO-FORMAT, GO-0, or any product-specific
receipt. A chain declares a typed `conformance_gate` with fixed validator and
evidence inputs; the driver invokes it without a shell, validates its receipt,
and blocks readiness, auto-merge, milestone completion, and downstream
advancement on failure.

The same generic contract lets a dependent chain require exact proof-artifact
paths from a predecessor completion manifest. Launch verifies the manifest row
and current content hash together; `contains_text` and standalone `exists`
checks are never evidence of that relationship.

For milestones that change live authority, the chain also owns one typed
post-validation transition slot. After post-merge readiness validation, a
non-shell receipt-consuming handler performs one declared atomic transition;
the chain then runs a separate post-transition verifier before it can mark the
milestone complete or advance. A milestone with a declared transition cannot
skip it, and a validator cannot perform the transition itself.

This bootstrap does not pretend a milestone-end verdict retroactively ordered
earlier actions. Irreversible authority or effect cutovers occur only in the
declared transition slot; the registered product handler consumes the exact
receipt supplied by the chain, and the chain verifies the after-state. Where
proof must stay effect-inert, proof and cutover remain different milestones.

The bootstrap also cannot safely self-host the capability it is adding. Trusted
external CI and an independent verifier must attest the exact proposed tree
before the existing automatic merge path is allowed to proceed. The verifier
must be organizationally and mechanically separate from the implementation
under test. The existing post-merge `final_conformance_gate` then rebinds the
proof to the landed tree and supplies the completion-manifest input. This is a
non-self-hosting trust boundary, but it is not a human PR/merge gate.
