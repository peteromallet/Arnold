# S1 — Pre-merge content-addressed milestone conformance gates

## Objective

Certify an externally implemented generic `conformance_gate`, exact
predecessor-artifact assertion, and receipt-consuming transition phase. The
gate runs against exact proposed source before PR readiness/auto-merge and
again after merge. A declared transition runs only after the post-merge
readiness receipt and is followed by its own verifier before milestone
completion.

This is an orchestration primitive, not a product-specific GO gate and not an
arbitrary command hook.

## Bootstrap safety

This milestone cannot use the behavior it is certifying to authorize its own
implementation merge. Before this chain launches, its implementation PR must:

- run the complete bootstrap contract suite as required external PR CI against
  the exact proposed tree;
- receive independent review of the chain ordering, unsafe-input negatives,
  and auto-merge-blocking mutations before manual merge; and
- emit a trusted, content-addressed
  `.megaplan/initiatives/megaplan-chain-milestone-gates/.megaplan/evidence/bootstrap-pr-attestation.json`
  binding PR/head/merge commit and tree, CI check identity/result/suite digest,
  reviewer/approval identity, and the implementation diff.

The bootstrap validator verifies that attestation against the configured
trusted CI/reviewer authority and current merge tree. A missing, forged, stale,
wrong-tree, non-green, or self-approved attestation fails. This closes the
current runner's local/no-PR bypass: local certification is allowed only after
the externally reviewed PR has already landed. A green post-merge result cannot
excuse missing pre-merge CI or independent review.

## Required behavior

1. Extend the typed chain schema so `milestones[].validate` accepts
   `conformance_gate` on any milestone while retaining
   `final_conformance_gate` compatibility.
2. Give the gate a fixed, non-shell invocation contract. It names a validator,
   conformance index, traceability index, proof map, repository root, and
   receipt output. Paths resolve inside the checkout and arguments are passed
   as an argv list.
3. Before PR readiness or auto-merge, run the gate against the proposed commit
   and tree. Missing inputs, nonzero exit, malformed output, a red verdict,
   stale source/evidence, an unconsumed proof row, or receipt-binding mismatch
   blocks merge eligibility and downstream advancement.
4. After merge and base refresh, rerun the same gate against merge HEAD. The
   accepted receipt must bind the merge commit/tree plus the exact validator,
   conformance, traceability, proof-map, schema, and evidence digests.
5. In local/no-PR operation, run before milestone completion against the exact
   commit that would be recorded. Never mark the milestone complete first.
6. Preserve idempotent retry and resume. A receipt from another attempt,
   branch, tree, proof-map incarnation, validator version, or restored/truncated
   evidence registry cannot satisfy the gate.
7. Require `validation_policy: required` to have at least one explicit typed
   validation, and fail rather than treating the metadata flag as enforcement.
8. Keep final completion-manifest production content-addressed and include all
   accepted intermediate-gate receipts named by the chain proof map.
9. Extend `chain_completed + require_manifest` with a typed
   `required_proof_artifacts` list. For every declared path, launch validation
   must find exactly one matching proof-artifact row in the predecessor
   completion manifest and verify that the current artifact hash equals the
   manifest hash. A text search or independent existence check cannot satisfy
   this relationship.
10. Add optional `milestones[].transition` with this fixed schema:
    `kind: receipt_consuming_transition`, stable `transition_id`, non-shell
    handler path, exact `input_receipts` (including a required
    `current_validation` token), output receipt path, and one typed `verify`
    block. Ordering is fixed: pre-merge validation → merge → post-merge
    readiness validation → transition → post-transition verification →
    milestone completion/advance.
    `input_receipts` entries are exactly `current_validation`,
    `milestone_validation:<label>`, or a project-relative immutable receipt
    path; labels/paths resolve without globbing and every resolved hash enters
    the transition receipt.
11. Invoke the transition handler as an argv list with repository root,
    transition ID, exact current validation receipt, each additional input
    receipt, and output-receipt path. The handler must atomically apply or
    report idempotent already-applied state. Its receipt binds handler digest,
    merge commit/tree, every input hash, idempotency key, old/new authority or
    registry snapshots, store/registry incarnation, result, and timestamp.
12. The post-transition verifier consumes the transition receipt and exact
    after-state evidence. Missing/skipped/partial/red/stale/unbound/replayed
    transitions block completion. Validators cannot mutate product authority;
    transition handlers cannot declare their own verification green.

## Required tests

- parser accepts intermediate `conformance_gate` and rejects unknown kinds,
  malformed fields, unsafe paths, shell strings, and misplaced final-only
  validation;
- a red pre-merge gate prevents readiness and auto-merge;
- a green pre-merge receipt cannot be reused after the proposed tree changes;
- a post-merge mismatch or failure stops the chain and cannot record the
  milestone complete;
- missing, extra, red, stale, unbound, unconsumed, cross-incarnation,
  self-certified, and pre-receipt-proof-map-hash mutations fail;
- retries cannot reuse another attempt's receipt;
- `required_proof_artifacts` rejects a missing row, duplicate row, path alias,
  stale hash, current-file mismatch, and a manifest from another chain;
- a milestone declaring `transition` cannot complete or advance without one
  accepted transition receipt and a green post-transition verifier;
- wrong current/prior receipt, wrong merge tree, transition-handler drift,
  partial mutation, stale authority snapshot, cross-incarnation input,
  replayed transition, and handler-self-verification all fail;
- idempotent retry after an accepted atomic transition returns the original
  transition identity and cannot apply the change twice;
- local/no-PR and review/auto-merge paths enforce the same source/evidence
  binding; and
- the existing final-conformance path remains compatible.

## Boundaries

- Do not execute arbitrary shell commands from chain YAML.
- Do not let validators mutate product authority, effects, or live stores.
- Do not treat a milestone-end gate as proof that an earlier cutover happened
  after the receipt. The cutover must run in the declared transition phase,
  consume the exact receipt supplied there, and pass post-transition
  verification; when proof must be effect-inert, proof and cutover are separate
  milestones.
- Do not add any Native Parity-specific rule to the chain engine.

## Deliverables and handoff

Produce and certify the schema/runtime implementation, source-ordering tests,
receipt, transition and `required_proof_artifacts` schemas, validator fixtures,
conformance and traceability indexes, proof map, and
content-addressed completion manifest. The manifest must bind the external
pre-merge CI run, independent review disposition, and post-merge backstop
receipt. The handoff must name the exact
`conformance_gate` schema/version that downstream chain specs may use.

Do not close if a failing gate can be merged, if validation first occurs after
auto-merge, if the bootstrap itself was auto-merged or lacked its required
external pre-merge verification, if the merged tree is not rebound, or if a
declared transition can be skipped/partially applied/self-verified, local
execution can fabricate or omit the trusted PR attestation, or a product
cutover could claim temporal ordering solely from milestone completion.
