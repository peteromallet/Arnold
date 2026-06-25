# M2b — Family Modules and Public Surface

## Outcome

Video family-specific SDK types live under `src/sdk/video/families/*`, video timeline and video asset contracts live under scoped SDK modules, and `src/sdk/index.ts` becomes a true public barrel with no remaining family implementation. Existing public SDK exports remain available from `@reigh/editor-sdk` with compatible types.

## Background

M2a split the core SDK modules and established the structural barrel gate. M2b finishes the physical SDK split by moving video family, video timeline, video asset, and video export contracts into their canonical modules using the M1 family registry as the map.

## Scope (in scope)

1. **Start with a low-risk family vertical, then one representative richer family.**
   - First extract a low-risk declaration-heavy family such as `metadataFacet` or `assetDetailSection`.
   - Then extract one richer but still bounded family that exercises cross-module imports, such as `outputFormat`, `shader`, or `process`.
   - Do not use a host UI surface family as the primary template unless the code proves its SDK contract is portable and not React/provider-owned.
   - For each template family:
     - create `src/sdk/video/families/<family>.ts`,
     - move descriptor types, manifest types, constants, and helper contracts from `src/sdk/index.ts`,
     - update `src/sdk/index.ts` to re-export from the new module,
     - ensure the family module imports only from other SDK modules,
     - add conformance tests, examples where the family is `public-supported`, and representative barrel vs. direct-module compatibility coverage.

2. **Split remaining family-specific modules using the template.**
   - Move into:
     - `src/sdk/video/families/effects.ts`
     - `src/sdk/video/families/transitions.ts`
     - `src/sdk/video/families/clipTypes.ts`
     - `src/sdk/video/families/shaders.ts`
     - `src/sdk/video/families/agentTools.ts`
     - `src/sdk/video/families/liveData.ts`
     - `src/sdk/video/families/processes.ts`
     - `src/sdk/video/families/outputFormats.ts`
     - `src/sdk/video/families/searchProviders.ts`
     - `src/sdk/video/families/contributionKinds.ts`
   - Keep public future-family types, but ensure they are classified by the M1 registry.

3. **Split timeline, asset, and export modules.**
   - Move into:
     - `src/sdk/video/timeline/patch.ts`
     - `src/sdk/video/timeline/reader.ts`
     - `src/sdk/video/timeline/proposals.ts`
     - `src/sdk/video/timeline/sourceMap.ts`
     - `src/sdk/video/timeline/capabilities.ts`
     - `src/sdk/video/assets/metadata.ts`
     - `src/sdk/video/assets/parsers.ts`
     - `src/sdk/video/assets/search.ts`
     - `src/sdk/video/exports/outputFormats.ts`
   - Keep host-only planner execution details in `src/tools/video-editor`.

4. **Reduce `src/sdk/index.ts` to a public barrel.**
   - File should be a small set of exports plus docs.
   - No inline implementation beyond re-exports.
   - No namespace exports or default exports.
   - No barrel import cycles: internal SDK modules use relative imports to canonical modules.

5. **Broaden barrel and public API checks.**
   - Extend the M2a structural barrel-identity gate to the final public barrel and any scoped SDK barrels introduced in M2b.
   - Add representative direct-import compatibility coverage for each moved module category: video family, video timeline, video asset, and video export.
   - Compare public API manifest output after the split against the M2a baseline and require explicit notes for any public shape change.
   - Any approved public shape change must name the affected export/type, the compatibility impact, and the approving owner in milestone notes.

6. **Update contract registry and allowlist.**
   - Update `config/contracts/registry.json` to reflect new module locations.
   - Remove clean SDK re-export entries from `config/governance/sdk-public-export-allowlist.json`.
   - Any remaining allowlist entry must have owner, rationale, and `expiration` (`"M3"`, `"M4"`, or `"permanent"`).

## Locked decisions

- SDK modules may not import from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- Public exported names from `@reigh/editor-sdk` must remain compatible unless explicitly approved.
- Public API approvals must name the affected export/type, compatibility impact, and the owner accepting the compatibility change in milestone notes.
- Family-specific types stay public but are classified by the M1 registry.
- The family module path declared in `FamilyDefinition.sdkModules` is the canonical direct-import path.
- Allowlists are migration budgets, not permanent escape hatches.

## Open questions

- Will circular SDK imports emerge between family modules and timeline modules?
- Which richer family should be the representative second template after the low-risk vertical?

## Constraints

- Preserve runtime behavior: extension loading, manifest validation, settings, diagnostics, proposal runtime, host integration metadata (e.g. video planner metadata), and video editor public entrypoints.
- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] One low-risk family and one richer representative family are extracted and tested before the rest are moved.
- [ ] All family-specific SDK contracts live under `src/sdk/video/families/*`.
- [ ] Timeline, asset, and export contracts live under scoped video SDK modules.
- [ ] `src/sdk/index.ts` is a small barrel with no inline implementation.
- [ ] `src/sdk/**` has no imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and a deliberate violation is caught.
- [ ] `npm run check:sdk-public-exports -- --release` passes.
- [ ] Structural barrel-identity gates pass and representative direct-import compatibility coverage exists for each moved module category.
- [ ] Public API manifest output has no unapproved public shape changes.
- [ ] `npm run quality:check` passes.
- [ ] `npm run test:readiness` passes.

## Touchpoints

- `src/sdk/index.ts`
- `src/sdk/video/families/*`
- `src/sdk/video/timeline/*`
- `src/sdk/video/assets/*`
- `src/sdk/video/exports/*`
- `config/contracts/registry.json`
- `config/governance/sdk-public-export-allowlist.json`

## Anti-scope (not in this milestone)

- Refactoring `extensionSurface.ts` onto host adapters (M3).
- Deciding proposal-runtime ownership (M4).
- Governance/docs closure and final release merge (M4).
