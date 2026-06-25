# M0 — Extract Portable SDK Contracts

## Outcome

Every portable contract that `@reigh/editor-sdk` needs is owned by the SDK and has no import from `src/tools/video-editor/*`. `src/sdk/index.ts` no longer re-exports video-editor internals. `npm run check:video-editor-sdk-imports` becomes the first required gate and passes.

## Background

The SDK currently declares it must not depend on editor internals, yet it imports from `@/tools/video-editor/runtime/renderability.ts` and `@/tools/video-editor` in `src/sdk/index.ts`. This milestone fixes that contradiction before any family architecture or barrel-split work. It is the hard prerequisite the rest of the epic builds on.

## Scope (in scope)

1. **Audit every import from `src/tools/video-editor/*` inside `src/sdk/**`.**
   - List files, imported symbols, and whether each symbol is truly portable or host-only.

2. **Move renderability contracts into the SDK.**
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

3. **Move timeline primitives needed by the SDK into SDK-owned modules.**
   - Identify which timeline patch/diff/ops/reader types the SDK re-exports only because host code needs them.
   - Move truly portable shapes (e.g. `TimelinePatch`, `TimelineDiff`, `TimelineDiffGranularity`, `TimelineProposalInput`) into `src/sdk/timeline/patch.ts` and `src/sdk/timeline/reader.ts`.
   - Keep host-only planner execution details in `src/tools/video-editor`.

4. **Move asset metadata contracts into the SDK.**
   - Move `AssetMetadata`, `AssetIntegrityMetadata`, `AssetGPSMetadata`, etc. into `src/sdk/assets/metadata.ts` if they are referenced by SDK public types.

5. **Update `src/sdk/index.ts`.**
   - Replace all `@/tools/video-editor/*` imports with SDK-local imports.
   - Keep the file as a barrel; do not do the full module split yet (that is M2).

6. **Strengthen and run the SDK import guard.**
   - Ensure `scripts/quality/check-video-editor-sdk-imports.mjs` fails if any `src/sdk/**` file imports from `src/tools/video-editor/*` or `@/tools/video-editor/*`.
   - Run the check; fix all failures.
   - Add a negative test: a deliberately introduced SDK import from video-editor internals fails the guard.

## Locked decisions

- After M0, no file under `src/sdk/**` may import from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- Host code may still import from the SDK; the dependency direction is one-way.
- Portable contracts are data-only shapes, not host behavior or React components.

## Open questions

- Which timeline/planner types are genuinely portable vs. execution details?
- Are there value-level exports (functions, constants) in the SDK that secretly depend on host modules?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `src/sdk/**` has zero imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and catches deliberate violations.
- [ ] All existing public SDK exports remain available from `@reigh/editor-sdk` with compatible types.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/sdk/index.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- New `src/sdk/rendering/*` modules
- New `src/sdk/timeline/*` modules
- New `src/sdk/assets/*` modules
- `scripts/quality/check-video-editor-sdk-imports.mjs`

## Anti-scope (not in this milestone)

- Splitting `src/sdk/index.ts` into many scoped modules (M2).
- Defining the family maturity registry (M1).
- Refactoring `extensionSurface.ts` onto adapters (M3).
- Making the packagability smoke strict (M4).
