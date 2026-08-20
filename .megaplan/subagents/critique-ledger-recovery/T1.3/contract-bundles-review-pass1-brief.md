# T1.3 contract bundles — independent review pass 1

You are GPT-5.6 Luna at high reasoning. Perform a fresh adversarial review of
exact candidate commit:

`e0b91992b2d2e01f7d7d87ba5053394a972984c6`

Worktree:
`/private/tmp/arnold-critique-recovery-contract-bundles-20260802`

Do not trust the implementer or its tests. Do not edit source, amend commits,
deploy, SSH, or mutate cloud state. You may write only the review report below
and disposable test output. Inspect the exact diff and actual runtime seams.

The candidate claims immutable producer/consumer contract bundles for critique
and finalize. Attack at least these requirements:

1. Every shipped bundle immutably binds the actual prompt/producer contract,
   capture/transport framing, parser ABI/code, schema, normalizer, semantic
   validator, provider/model/tool assumptions, fixtures, and expected runtime.
2. There is no `latest`, silent regeneration, self-referential/stale digest,
   source-vs-wheel drift, or mutable lookup that can select a different bundle.
3. The producer emits a binding that the actual consumer requires and verifies;
   merely providing optional helper APIs is insufficient.
4. Provider failure, missing raw output, malformed/truncated/duplicate-key or
   non-finite JSON, tool-framing mismatch, parser/schema/semantic/completeness
   failure, and bundle mismatch can never collapse into semantic zero findings
   or an accepted finalize result.
5. `NO_FINDING` is possible only after every expected critique record is present,
   structurally valid, semantically valid, and explicitly clear.
6. The one permitted repair is exactly one attempt, only at enumerated invalid
   pointers, cannot alter any valid field/record/order/bundle/runtime binding,
   and revalidates the whole object.
7. Critique and finalize production paths—not only tests—carry typed failure and
   cannot bypass bundle validation through legacy parsing or normalization.
8. Package data, installed-wheel entrypoints, help/schemas, and fresh-process
   digest verification are complete.
9. Existing consumers remain compatible only where compatibility is intended;
   no unrelated regression or broad scope expansion is hidden in the change.

Run focused adversarial tests, installed-wheel proof, digest/tamper probes, and
the relevant Megaplan/orchestration regression. The first prior broad attempt
was interrupted by local ENOSPC; do not treat that interruption as a code
failure or as a pass. Use one test process and a dedicated temp root, and report
the complete final result.

Write:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-review-pass1-result.md`

First line exactly `PASS` or `FAIL`. For failures include minimal reproduction,
exact files/lines, and required correction. On PASS enumerate exact commands and
results. State that a local candidate review does not itself prove formal T1.3
or authorize deployment.
