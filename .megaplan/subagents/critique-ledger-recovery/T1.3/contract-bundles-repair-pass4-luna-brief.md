# T1.3 contract bundles — bounded Luna repair pass 4

Use GPT-5.6 Luna. Start from exact clean candidate
`fe1786c298361454a73754536ecf7de2f7b4bd69` (tree
`f11e71c1bbd6823a80bcba48c7bf88f655f44b8f`) in
`/private/tmp/arnold-critique-recovery-contract-bundles-20260802`.

Read the pass-4 independent report at
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-independent-review-pass4-luna-result.md`,
SHA-256 `04fdf319699a28bdef634920a26237d7a6a51b5e8fa55f590d674dee904ab144`.

This is a frozen, bounded repair. Fix only the two authoritative blocker groups
below. Do not reopen the architecture and do not attempt to defend against
arbitrary in-process `__code__` replacement; runtime integrity belongs to the
T1.8/T1.9 fenced-generation/process boundary.

## A. Capture authenticated transport identity once, at receipt

- Replace string-only/self-attested `WorkerResult.provider_transcript` custody
  with one immutable neutral-core capture/transport receipt produced at the
  adapter's provider-response boundary, before normalization or mutable worker
  projection.
- Preserve exact provider-returned bytes/frames without `errors="replace"`,
  re-encoding, reconstructed JSON, selected `final_response`, or follow-up result
  substitution. If a provider SDK exposes structured data rather than HTTP bytes,
  preserve the exact canonical SDK event/result bytes plus an adapter and schema
  identity; never label normalized text as untouched transport bytes.
- Bind physical provider, exact model/route, provider/session/conversation id,
  Arnold dispatch/session id, attempt/retry ordinal, tool/channel modes and
  adapter/runtime generation into that capture. Those fields are set by the
  adapter from the actual resolved route and response, not copied later from a
  mutable `WorkerResult` or caller arguments.
- Critique/finalize consumers must accept the immutable capture object and verify
  it. They may not manufacture a new `ProviderTranscript` from current worker
  fields. Hermes must distinguish DeepSeek/Zhipu/Fireworks/OpenRouter; Shannon
  must compare embedded event model/session with the transport receipt; Codex and
  every supported route need the equivalent exact binding.
- Cross-route/session/attempt/channel replay, same-byte substitution, follow-up
  replacement, decoding corruption and contradictory embedded identity must fail
  closed. Preserve the T2.5 rule that exact upstream provider/model cannot be
  inferred from worker labels alone.

## B. One neutral platform authority; migrate or fail-close alternate seams

- Move registry, binder, repair and preflight authority into
  `arnold.pipeline.contract_bundles`; Megaplan must be a thin compatibility
  adapter/re-export and cannot instantiate a second authority.
- Route the real `arnold.pipeline.model_seam.capture_step_output` and every
  `AgentStep`/non-Megaplan model-output path through the same raw-capture bundle
  authority, or make the unsupported path return a typed fail-closed result.
  A Python mapping/JSON string with no immutable capture may never return
  `authority_level="typed"` or semantic success.
- Inventory installed CLI/module/direct-import/compatibility aliases and prove no
  alternate registry, mapping normalizer, legacy envelope or source-only path can
  mint acceptance. This must remain reusable by all pipelines.

## Finite tests

Retain and rerun all 116 focused, 48 producer, source/wheel semantic parity and
recorded-fixture tests. Add exact regressions for both independent probes:

1. identical Hermes bytes claimed as DeepSeek/session A/attempt 0 and
   GLM/session B/attempt 99;
2. Shannon bytes embedding Sonnet/session A claimed as Opus/session B;
3. each physical Hermes route and hidden retry/follow-up;
4. byte decoding failure/replacement and structured-SDK canonical capture;
5. mapping/JSON-only `model_seam.capture_step_output` and `AgentStep` bypass;
6. neutral vs Megaplan registry/binder/repair/preflight object identity in source,
   built wheel and fresh installed process;
7. non-Megaplan producer inventory and fail-closed unsupported path.

Large wheel/broad tests are single-flight. Prove any unrelated baseline failure
against the exact parent; do not chase it. Do not touch cloud/providers/production
owners or checklist state.

Commit scoped work, leave the worktree clean, and write exact commit/tree/files,
tests, limitations and production prerequisites to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-repair-pass4-result.md`.

No formal T1.3 claim is allowed without a new independent Luna review.
