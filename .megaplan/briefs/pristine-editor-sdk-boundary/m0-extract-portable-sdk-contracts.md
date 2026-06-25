# M0 — Extract Portable SDK Contracts

## Outcome

Every portable contract that `@reigh/editor-sdk` needs is owned by the SDK and has no import from `src/tools/video-editor/*`. `src/sdk/index.ts` no longer re-exports video-editor internals. An external SDK-consumer package fixture compiles cleanly. Doc/code discrepancies are recorded so later milestones align with canonical truth.

## Background

The SDK currently declares it must not depend on editor internals, yet it imports from `@/tools/video-editor/runtime/renderability.ts` and `@/tools/video-editor` in `src/sdk/index.ts`. This milestone fixes that contradiction before any family architecture or barrel-split work. It is the hard prerequisite the rest of the epic builds on.

## Scope (in scope)

1. **Reconcile docs/code state before churn.**
   - Read `docs/extensions/phase4-readiness.md`, `docs/extensions/reigh-extension-layer-foundation-plan.md`, and `docs/extensions/foundation-closure-assessment.md`.
   - Record every place where docs disagree with current code (e.g. stale references to `runtime/contributionFamilies.ts`, claims about `src/sdk/index.ts` existence, Phase 4 promotion status).
   - Produce `docs/extensions/pristine-sdk-boundary-audit.md` with a table of discrepancies, owner, and proposed resolution.
   - Do not rewrite all docs yet; just establish the canonical truth that later milestones will align with.

2. **Audit every import from `src/tools/video-editor/*` inside `src/sdk/**`.**
   - List files, imported symbols, and whether each symbol is truly portable or host-only.

3. **Move renderability contracts into the SDK.**
   - Create `src/sdk/rendering/renderability.ts` with data-only types:
     - `RenderRoute`
     - `DeterminismStatus`
     - `RenderBlockerReason`
     - `CapabilityFinding`
   - Create `src/sdk/rendering/artifacts.ts` with:
     - `RenderArtifact`
     - `RenderMaterial`
     - `RenderMaterialRef`
     - `RenderStorageLocator`
   - Create `src/sdk/rendering/capabilities.ts` with:
     - `ShaderMaterializerRequirementScope`
     - `shaderMissingMaterializerBlockerMessage`
   - Update `src/tools/video-editor/runtime/renderability.ts` to depend on SDK-owned contracts.

4. **Move timeline primitives needed by the SDK into SDK-owned modules.**
   - Identify which timeline patch/diff/ops/reader types the SDK re-exports only because host code needs them.
   - Move truly portable shapes (e.g. `TimelinePatch`, `TimelineDiff`, `TimelineDiffGranularity`, `TimelineProposalInput`) into `src/sdk/timeline/patch.ts` and `src/sdk/timeline/reader.ts`.
   - Keep host-only planner execution details in `src/tools/video-editor`.

5. **Move asset metadata contracts into the SDK.**
   - Move `AssetMetadata`, `AssetIntegrityMetadata`, `AssetGPSMetadata`, etc. into `src/sdk/assets/metadata.ts` if they are referenced by SDK public types.

6. **Update `src/sdk/index.ts`.**
   - Replace all `@/tools/video-editor/*` imports with SDK-local imports.
   - Keep the file as a barrel; do not do the full module split yet (that is M2).

7. **Strengthen and run the SDK import guard.**
   - Ensure `scripts/quality/check-video-editor-sdk-imports.mjs` fails if any `src/sdk/**` file imports from `src/tools/video-editor/*` or `@/tools/video-editor/*`.
   - Run the check; fix all failures.
   - Add a negative test: a deliberately introduced SDK import from video-editor internals fails the guard.

8. **Add an external packagability smoke.**
   - Create a temporary external package fixture under `scripts/quality/fixtures/sdk-consumer-package/` that:
     - depends only on `@reigh/editor-sdk` (resolved to the local SDK source via a relative path or tsconfig paths),
     - imports the full public SDK surface,
     - has no Vite app context,
     - does not use the `@/` alias to reach app internals.
   - Run `tsc --noEmit` in that fixture and fail if it emits any diagnostic from `src/sdk/**`.
   - Do not filter SDK diagnostics; `skipLibCheck` should remain true only for third-party `.d.ts`.
   - Wire the smoke into `npm run check:video-editor-sdk-imports` or `npm run test:extensions`.

9. **Add a representative family contract sanity check.**
   - Pick three families of different risk types: one metadata family (e.g. `metadataFacet`), one render-relevant family (e.g. `shader`), and one execution/process-like family (e.g. `process`).
   - For each, document in code comments:
     - what is portable vs. host-only today,
     - which SDK types are declaration-only,
     - which host behavior must remain in `src/tools/video-editor`.
   - This sanity check is documentation-only; it validates the contract extraction boundaries before M2/M3 broaden the work.

## Locked decisions

- After M0, no file under `src/sdk/**` may import from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- Host code may still import from the SDK; the dependency direction is one-way.
- Portable contracts are data-only shapes, not host behavior or React components.
- The external SDK-consumer fixture must compile with no diagnostics from SDK files.

## Open questions

- Which timeline/planner types are genuinely portable vs. execution details?
- Are there value-level exports (functions, constants) in the SDK that secretly depend on host modules?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `docs/extensions/pristine-sdk-boundary-audit.md` records doc/code discrepancies.
- [ ] `src/sdk/**` has zero imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and catches deliberate violations.
- [ ] The external SDK-consumer package fixture compiles with `tsc --noEmit` and emits no diagnostics from `src/sdk/**`.
- [ ] Representative family sanity check documents portable vs. host-only boundaries for one metadata, one render-relevant, and one execution/process-like family.
- [ ] All existing public SDK exports remain available from `@reigh/editor-sdk` with compatible types.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/sdk/index.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- New `src/sdk/rendering/*` modules
- New `src/sdk/timeline/*` modules
- New `src/sdk/assets/*` modules
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `scripts/quality/fixtures/sdk-consumer-package/` (new)
- `docs/extensions/pristine-sdk-boundary-audit.md` (new)

## Anti-scope (not in this milestone)

- Splitting `src/sdk/index.ts` into many scoped modules (M2).
- Defining the family maturity registry (M1).
- Refactoring `extensionSurface.ts` onto adapters (M3).
- Governance/docs closure and final release merge (M4).
