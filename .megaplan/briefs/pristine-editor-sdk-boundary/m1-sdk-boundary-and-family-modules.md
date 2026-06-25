# M1 — SDK Boundary and Family Modules

## Outcome

`src/sdk/index.ts` is reduced to a small barrel entrypoint that re-exports scoped SDK-owned modules organized around families and domains (core, manifest, runtime, timeline, rendering, families). The SDK no longer imports from `src/tools/video-editor/*`. Family-specific types live under `src/sdk/families/*`. Existing public SDK exports remain available from `@reigh/editor-sdk` with compatible types.

## Background

M0 defined the family contract and maturity model. M1 executes the physical SDK split. The split is organized around the family registry so that future family work has a clear location and adapter contract to target.

## Scope (in scope)

1. **Move renderability/capability/artifact contracts into the SDK.**
   - Create `src/sdk/rendering/renderability.ts`, `src/sdk/rendering/artifacts.ts`, and `src/sdk/rendering/capabilities.ts` for portable data-only types currently sourced from `src/tools/video-editor/runtime/renderability.ts`:
     - `RenderRoute`, `DeterminismStatus`, `RenderBlockerReason`, `CapabilityFinding`
     - `RenderArtifact`, `RenderMaterial`, `RenderMaterialRef`, `RenderStorageLocator`
     - `ShaderMaterializerRequirementScope`, `shaderMissingMaterializerBlockerMessage`
   - Update `src/tools/video-editor/runtime/renderability.ts` to depend on SDK-owned contracts.
   - Replace direct SDK imports from video-editor renderability with SDK-local imports.

2. **Add an SDK no-video-editor-import guard.**
   - Add or tighten a check that fails when any file under `src/sdk/**` imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.

3. **Snapshot the current SDK export surface.**
   - Run `npm run check:sdk-public-exports -- --release` and record the baseline before moving code.

4. **Split core SDK modules out of `src/sdk/index.ts`.**
   - Move clusters into scoped modules, preserving exported names:
     - `src/sdk/ids.ts`
     - `src/sdk/dispose.ts`
     - `src/sdk/diagnostics.ts`
     - `src/sdk/manifest.ts`
     - `src/sdk/manifestValidation.ts`
     - `src/sdk/lifecycle.ts`
     - `src/sdk/context.ts`
     - `src/sdk/chrome.ts`
     - `src/sdk/commands.ts`
     - `src/sdk/settings.ts`
     - `src/sdk/packaging.ts`
   - Use internal relative imports; do not import back through `src/sdk/index.ts`.

5. **Split family-specific modules.**
   - Move into:
     - `src/sdk/families/effects.ts`
     - `src/sdk/families/transitions.ts`
     - `src/sdk/families/clipTypes.ts`
     - `src/sdk/families/shaders.ts`
     - `src/sdk/families/agentTools.ts`
     - `src/sdk/families/liveData.ts`
     - `src/sdk/families/processes.ts`
     - `src/sdk/families/outputFormats.ts`
     - `src/sdk/families/contributionKinds.ts`
   - Keep public future-family types where they exist, but ensure they are classified by the M0 registry.

6. **Split registry and timeline modules.**
   - Move into:
     - `src/sdk/timeline/patch.ts`
     - `src/sdk/timeline/reader.ts`
     - `src/sdk/timeline/proposals.ts`
     - `src/sdk/timeline/sourceMap.ts`
     - `src/sdk/timeline/capabilities.ts`
     - `src/sdk/assets/metadata.ts`
     - `src/sdk/assets/parsers.ts`
     - `src/sdk/assets/search.ts`
     - `src/sdk/exports/outputFormats.ts`

7. **Reduce `src/sdk/index.ts` to a barrel.**
   - File should be a small set of imports/exports plus docs.
   - No inline implementation beyond re-exports.

8. **Update contract registry and allowlist.**
   - Update `config/contracts/registry.json` to reflect new module locations.
   - Ensure `config/governance/video-editor-sdk-import-allowlist.json` no longer contains SDK-internal entries.

## Locked decisions

- SDK modules may not import from `src/tools/video-editor/**` or `@/tools/video-editor/**` after this milestone.
- Public exported names from `@reigh/editor-sdk` must remain compatible unless explicitly approved.
- Internal SDK modules use relative imports, not barrel imports through `src/sdk/index.ts`.
- Family-specific types stay public but are classified by the M0 registry.

## Open questions

- Will the barrel split cause TypeScript identity or inference regressions?
- Will circular SDK imports emerge between family modules and timeline modules?

## Constraints

- Preserve runtime behavior: extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `src/sdk/index.ts` is a small barrel with no inline implementation.
- [ ] All SDK-owned public types/helpers live under scoped `src/sdk/*` modules.
- [ ] `src/sdk/**` has no imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and a deliberate violation is caught.
- [ ] `npm run check:sdk-public-exports -- --release` passes.
- [ ] `npm run quality:check` passes.
- [ ] `npm run test:readiness` passes.

## Touchpoints

- `src/sdk/index.ts`
- New `src/sdk/*` modules listed above.
- `src/tools/video-editor/runtime/renderability.ts`
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `config/contracts/registry.json`
- `config/governance/video-editor-sdk-import-allowlist.json`

## Anti-scope (not in this milestone)

- Refactoring `extensionSurface.ts` onto host adapters (M2).
- Deciding proposal-runtime ownership (M2).
- Making the packagability smoke strict (M2).
- Updating Phase 4 docs/readiness language (M2).
