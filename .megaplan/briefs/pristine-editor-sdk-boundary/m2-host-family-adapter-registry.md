# M2 — Host Family Adapter Registry

## Outcome

`src/tools/video-editor/runtime/extensionSurface.ts` no longer owns all family knowledge in one switch. A host-side family adapter registry under `src/tools/video-editor/runtime/families/*` normalizes, disposes, projects planner capabilities, and produces conformance reports per family. Each active or declarative family has a host adapter. Adding a new family means adding one SDK family module, one host adapter, and one conformance report.

## Background

M1 split the SDK into family modules and removed SDK imports from video-editor internals. M2 inverts the host side: instead of `extensionSurface.ts` special-casing every family, it orchestrates adapters that implement a common `HostFamilyAdapter` interface. This is the architectural change that makes the next wave of family implementations repeatable.

## Scope (in scope)

1. **Define the host family adapter interface.**
   - Create `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts` with:
     ```ts
     interface HostFamilyAdapter<C, D> {
       readonly kind: ContributionKind;
       normalize(input: NormalizeFamilyInput<C>): FamilyNormalizeResult<D>;
       disposeOwner?(extensionId: string): void;
       projectPlannerCapabilities?(input: FamilyPlannerInput<D>): readonly CapabilityRequirement[];
       getConformanceReport(): FamilyConformanceReport;
     }
     ```
   - Types for `NormalizeFamilyInput`, `FamilyNormalizeResult`, `FamilyPlannerInput` live in SDK-owned `src/sdk/families/familyAdapter.ts`.

2. **Create the host adapter registry.**
   - Add `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts`.
   - It maps `ContributionKind` to `HostFamilyAdapter` instances.
   - It provides `normalizeAll`, `disposeExtension`, `projectCapabilities`, and `auditConformance` operations.

3. **Implement adapters for existing families.**
   - Start with families that currently have runtime host behavior:
     - surfaces
     - commands
     - parser
     - metadataFacet
     - assetDetailSection
     - outputFormat
     - process
     - effect
     - transition
     - clipType
     - shader
     - agentTool
   - Each adapter owns its normalization, disposal, planner projection, and conformance report.

4. **Refactor `extensionSurface.ts`.**
   - Replace family-specific switch cases with adapter registry calls.
   - `extensionSurface.ts` should orchestrate: collect contributions, sort, normalize, aggregate diagnostics, and freeze output.
   - Keep host-only types like `VideoEditorRuntimeSlices` in the host; do not promote them to the SDK.

5. **Add adapter registry tests.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.test.ts`
   - `src/tools/video-editor/runtime/families/familyConformance.test.ts`
   - Tests assert every family with `supportLevel` >= `runtime-bridged` has a registered host adapter.
   - Tests assert `extensionSurface.ts` does not add new family switch cases.

6. **Tighten family conformance check.**
   - Update `scripts/quality/check-extension-family-conformance.mjs` so release mode fails if:
     - A `ContributionKind` lacks a `FamilyDefinition`.
     - A family marked `runtime-bridged` lacks a host adapter.
     - A family marked `planner-integrated` lacks planner projection tests.
     - `extensionSurface.ts` adds a new family switch case instead of using an adapter.
   - Keep `--audit` mode reporting for lower support levels.

## Locked decisions

- Host adapters own runtime normalization, lifecycle cleanup, and planner projection for their family.
- The SDK owns the family contract, descriptor types, and conformance report shape.
- `extensionSurface.ts` is an orchestrator, not a family implementation.

## Open questions

- Which families currently lack enough runtime behavior to justify an adapter vs. staying declarative?
- Will adapter registry overhead affect extension loading performance?

## Constraints

- Preserve runtime behavior for extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `HostFamilyAdapter` interface exists and is implemented for every `runtime-bridged` or higher family.
- [ ] `extensionSurface.ts` uses the adapter registry instead of family switch cases.
- [ ] `familyAdapterRegistry.test.ts` and `familyConformance.test.ts` pass.
- [ ] Family conformance check fails release mode when an adapter is missing.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts` (new)
- `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts` (new)
- `src/tools/video-editor/runtime/families/*Adapter.ts` (new)
- `src/sdk/families/familyAdapter.ts` (new SDK contract)
- `scripts/quality/check-extension-family-conformance.mjs`

## Anti-scope (not in this milestone)

- Splitting the SDK barrel further (M1).
- Making the packagability smoke strict (M3).
- Updating docs/readiness language (M3).
- Deciding proposal-runtime ownership (M3).
