# T1.3 immutable contract bundles — independent Luna review pass 2

You are a fresh GPT-5.6 Luna read-only adversarial reviewer. Review exactly
commit `97904d0fd8cba80c316f9607d3ac80381da77343` in:

`/private/tmp/arnold-critique-recovery-contract-bundles-20260802`

Do not edit the worktree, commit, master checklist, cloud, provider, or runtime.
Write only the final review artifact to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-review-pass2-result.md`

Read the complete pass-1 FAIL report and repair result. Independently reproduce
all six prior blockers and attack the stronger end-to-end invariant:

1. Production must parse and validate exact raw transport/capture bytes before
   semantic interpretation; missing, truncated, duplicate-key, non-finite,
   appended-prose, wrong-frame, and provider-error cases can never become
   `NO_FINDING` or an admitted payload.
2. Producer and consumer must bind the exact raw digest, parsed/admitted object
   digest, bundle, provider, model, tool mode, runtime identity, object revision,
   and repair attempt. No optional/default identity may weaken comparison.
3. The object accepted at the binding boundary is immutable thereafter.
   Critique/finalize projections, recovery, adapters, workers, and sidecar writes
   cannot replace or mutate it. The sole pointer-only repair cannot alter any
   already-valid field, runtime/bundle, or whole-object semantics.
4. Every route/manifest container is deeply immutable and omission-resistant.
   Bundle hashes identify the actual shipped executable enforcement code—not
   merely attacker-chosen labels or incomplete references—and installed-wheel
   parity/tamper detection proves the same bytes.
5. Missing/unknown/wrong model and provider/tool/runtime drift fail closed.
6. One public schema/validation registry governs both routes without a shadow
   legacy normalizer/synthesis path.

Also inspect beyond the new focused tests: real Hermes/Shannon/Codex adapter
paths, tool-enabled captures, retry/recovery seams, atomic sidecar durability,
fresh-process imports, minimum supported dependencies, and source-versus-wheel
behavior. Probe mutable aliases/copies, post-bind nested mutation, forged
bindings, digest collisions by canonicalization differences, alternate provider
capture shapes, and exception-to-zero-finding conversions. Check that the
solution is a reusable contract mechanism with Megaplan-specific bundles, not a
hard-coded bypass that other Arnold pipelines cannot adopt.

Run focused and relevant broader tests, static/diff checks, isolated wheel proof,
and minimal independent attacks using controlled scratch. Return hard `PASS` or
`FAIL` with ranked exact file:line evidence and commands. A local PASS does not
mark formal T1.3 complete or authorize deployment; state remaining integration/
owner evidence explicitly.
