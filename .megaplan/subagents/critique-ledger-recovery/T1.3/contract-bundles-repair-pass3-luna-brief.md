# GPT-5.6 Luna implementation — T1.3 repair pass 3

Continue from exact clean commit `ddb764b30cedf3774ff5ca665a85a62090607b21`
in `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`. Start only
when a mutating-lane slot is free. Read the full recovery-plan T1.3 contract and
the pass-2 result. Preserve all pass-2 fixes and proofs. The pass-2 verdict is
`FAIL`; close both remaining invariants rather than relabeling them.

1. **Untouched transcript is the sole producer parser authority.** Hermes and
   Shannon must carry the exact provider response bytes/frame plus authenticated
   provider/model/tool/session/attempt/channel/capture metadata through the
   worker/adapter seam. The public neutral binder must perform the only parse,
   duplicate-key/non-finite/frame/encoding validation, object derivation, and
   raw/object digest binding. A normalized worker object, reconstructed JSON,
   legacy envelope, capture projection, mocked field, or post-processed state
   cannot stand in for raw provider bytes or mint acceptance. Preserve the raw
   transcript even on provider, parser, and contract failure. Add realistic
   recorded fixtures for Hermes and Shannon plus Codex compatibility; test raw/
   normalized disagreement, duplicate keys, truncation, prose framing, tool
   envelopes, response loss, wrong provider/model/channel/attempt, retries, and
   installed/source parity.
2. **Neutral platform-wide authority.** Move/extract the immutable contract
   bundle registry, canonical framing/binding, health/result types, repair
   boundary, and preflight contract into an Arnold core package with no Megaplan
   policy dependency. Keep thin compatibility imports if required, but they must
   delegate to one captured canonical authority and cannot fork/rebind it.
   Inventory every Arnold pipeline/model seam and migrate all output-admission
   consumers or make unsupported producer paths fail closed. Non-Megaplan
   pipelines must not parse/normalize/model-accept around the shared boundary.
   Enforce exact provider/model/tool routes and immutable executable-artifact
   identity from installed entrypoints; environment/import/monkeypatch/path/
   compatibility aliases cannot select a second registry or parser.

Add neutral-core unit tests, Megaplan compatibility tests, real producer fixture
tests, alternate-pipeline bypass scans, fresh-process rebind/tamper tests,
installed-wheel and materialized entrypoint parity, and the complete existing
T1.3 focused/dependency suite. Large tests/wheels must be single-flight and
reproducible scratch removed after evidence capture.

Do not contact providers/cloud or mutate runtime/owner/checklist state. Commit
only scoped work, leave the worktree clean, and write exact commit/tree/files/
tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-repair-pass3-result.md`.
Do not claim formal completion without a fresh independent Luna review and
release-owner/integration evidence.
