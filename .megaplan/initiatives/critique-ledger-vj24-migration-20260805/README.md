# Critique Ledger VJ24 migration prerequisite

This is the bounded prerequisite sprint for the stalled Critique Ledger v3
occurrence. It delivers the missing occurrence-to-child migration primitive so
the quarantined r5/VJ24 parent can have one authority-approved continuation.
It does not resume or mutate r5 while the primitive is being built.

Sol's adversarial review is recorded at
`.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-direction-review.md`.
The launch-specific cutline is recorded at
`.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-launch-cutline.md`.
The implementation venue is deliberately local-first: the clean pushed
selector-contract worktree is the shortest place to author and test the
primitive. The cloud run is retained for durable orchestration and host-side
verification, not as a prerequisite for writing code. The active cloud plan
has an operator note narrowing it to the typed migration/selector contract,
real owner adapters, deterministic CAS/idempotency tests, and effect-free
prepare; it must not touch r5 or launch a child. The cloud plan was subsequently
aborted before implementation because the candidate lacked a real Run Authority
journal writer/CAS and its selector tests were not VJ24-complete.
