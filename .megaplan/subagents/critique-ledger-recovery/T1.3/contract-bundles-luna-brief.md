# T1.3 implementation brief — immutable producer/consumer contract bundles

Use GPT-5.6 Luna high reasoning. Work only in:

`/private/tmp/arnold-critique-recovery-contract-bundles-20260802`

Do not touch the dirty main checkout, cloud, providers, or external services. Do not push,
merge, or deploy. You may commit the isolated branch after all tests pass.

## Incident failure being eliminated

Critique/finalizer producers, prompt contracts, transport/capture formats, parsers,
normalizers, and semantic validators drifted independently. Tool-enabled model output was
treated as prompt-only JSON; parser/normalizer failures could synthesize/discard fields and
collapse invalid critique into valid-looking zero findings. Broad retries used mutable
runtime/provider assumptions rather than one immutable producer/consumer contract.

## Required outcome

Implement a versioned content-addressed contract bundle used by the relevant production
critique/finalize/model routes. A bundle must bind, by digest:

- exact prompt/template and prompt input schema;
- transport/tool/capture schema and response framing assumptions;
- parser ABI/version and parser configuration;
- normalizer ABI/version and exact allowed transformations;
- semantic validator ABI/version and completeness policy;
- fixtures/golden inputs/outputs and their digests;
- provider/model/tool-mode assumptions and runtime compatibility constraints.

Binding behavior:

1. Producer emits the exact bundle ID/digest and output object digest. Consumer must
   require and independently recompute the same bundle; missing/unknown/mismatched/stale
   bundles fail closed before semantic acceptance.
2. No mutable `latest`, ambient prompt, provider default, import-tree guess, or fallback
   parser can satisfy the contract. Runtime/model route selection must be pinned or prove
   exact compatibility with the bundle.
3. Strict exact schemas: unknown fields, missing fields, boolean/int confusions,
   NaN/Infinity, duplicate keys/IDs, truncation, extra prose, tool/capture framing drift,
   and parser ambiguity fail typed and closed.
4. Normalization cannot synthesize required semantic fields, discard invalid mandatory
   records, turn transport/parser/producer failure into `NO_FINDING`, or rewrite valid
   content. Every transformation is explicit, bounded, and evidenced.
5. Permit at most one invalid-pointer-only repair within the same output object and exact
   same bundle. The repair request identifies only invalid JSON pointers and their
   validation errors. Repaired output must:
   - retain the same bundle ID and object identity/revision chain;
   - keep every valid field byte/canonically identical;
   - modify only the allowlisted invalid pointers;
   - not add/remove/reorder semantic records except where the invalid pointer itself
     authorizes a bounded replacement;
   - undergo full parse/schema/semantic/completeness revalidation;
   - fail terminally on a second repair, bundle change, valid-field change, or new error.
6. Bundle artifacts are immutable/content-addressed and shipped in source and installed
   wheels. Any referenced file digest mismatch fails startup/preflight; do not regenerate
   silently in production.
7. Emit machine-readable typed outcomes that T1.2 can consume distinctly from semantic
   `FINDING`/`NO_FINDING`, including producer-contract/parser/semantic/bundle mismatch.
8. Preserve provider raw bytes/digest for evidence without embedding credentials.

## Proof requirements

Add adversarial tests across the actual critique/finalizer route and installed entrypoint:

- producer/consumer bundle mismatch, missing bundle, tampered prompt/schema/parser/
  normalizer/validator/fixture/provider assumptions;
- tool-enabled vs prompt-only framing mismatch;
- required-field synthesis/discard attempts and invalid critique cannot become zero
  findings;
- same invalid pointer repaired once successfully while all valid fields remain identical;
- repair changing a valid field, changing bundle, changing record set, creating a new
  invalid pointer, or second repair is rejected;
- two processes resolving the same bundle get the same digest; source and installed wheel
  bundle/digest/help surfaces match;
- no `latest` or fallback lookup in production;
- malformed JSON edge cases and model-route/runtime compatibility failures.

Inspect existing contract/schema/model seam code and reuse accepted content-addressed
primitives where sound. Do not solve T1.2 wholesale, but wire a clean typed contract-health
boundary that T1.2 can consume. Do not weaken existing tests or alter unrelated files.

Run targeted tests, relevant broader regressions, installed-wheel tests, static checks, and
`git diff --check`. Adversarially review your own diff. Commit only when clean. Final report
must name commit, files, exact test commands/counts, installed artifact proof, remaining
integration blockers, and whether T1.3's formal criterion is genuinely met.
