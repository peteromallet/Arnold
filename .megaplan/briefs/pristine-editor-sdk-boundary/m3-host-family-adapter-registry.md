# M3 — Host Family Adapter Registry

## Outcome

`src/tools/video-editor/runtime/extensionSurface.ts` no longer owns all family knowledge in one switch. A host-side family adapter registry under `src/tools/video-editor/runtime/families/*` normalizes, disposes, projects planner capabilities, and produces conformance reports per family. Each family with execution maturity `runtime-bridged` or higher has a host adapter.

## Background

M2 split the SDK into family modules. M3 inverts the host side so that adding a family means adding one SDK module, one host adapter, and one conformance report.

## Scope (in scope)

1. **Define the host family adapter interface.**
   - Create `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts`:
     ```ts
     interface HostFamilyAdapter<C, D> {
       readonly kind: ContributionKind;
       normalize(input: NormalizeFamilyInput<C>): FamilyNormalizeResult<D>;
       disposeOwner?(extensionId: string): void;
       projectPlannerCapabilities?(input: FamilyPlannerInput<D>): readonly CapabilityRequirement[];
       getConformanceReport(): FamilyConformanceReport;
     }
     ```
   - SDK-owned contract types live in `src/sdk/families/familyAdapter.ts`.

2. **Create the host adapter registry.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts` maps `ContributionKind` to adapters and provides `normalizeAll`, `disposeExtension`, `projectCapabilities`, `auditConformance`.

3. **Implement adapters for existing runtime families.**
   - Start with families currently normalized in `extensionSurface.ts`:
     - surfaces, commands, parser, metadataFacet, assetDetailSection, outputFormat, process, effect, transition, clipType, shader, agentTool, searchProvider.
   - Each adapter owns normalization, disposal, planner projection, and conformance report.

4. **Refactor `extensionSurface.ts`.**
   - Replace family switch cases with adapter registry calls.
   - `extensionSurface.ts` orchestrates: collect contributions, sort, normalize, aggregate diagnostics, freeze output.
   - Keep host-only types like `VideoEditorRuntimeSlices` in the host.

5. **Add adapter registry tests.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.test.ts`
   - `src/tools/video-editor/runtime/families/familyConformance.test.ts`
   - Assert every family with execution maturity >= `runtime-bridged` has a registered host adapter.
   - Assert `extensionSurface.ts` does not add new family switch cases.

6. **Tighten family conformance check.**
   - Update `scripts/quality/check-extension-family-conformance.mjs` so release mode fails if:
     - A `ContributionKind` lacks a `FamilyDefinition`.
     - A family with execution maturity `runtime-bridged` or higher lacks a host adapter.
     - A family with execution maturity `planner-integrated` or higher lacks planner projection tests.
     - `extensionSurface.ts` adds a new family switch case instead of using an adapter.

## Locked decisions

- Host adapters own runtime normalization, lifecycle cleanup, and planner projection.
- The SDK owns the family contract, descriptor types, and conformance report shape.
- `extensionSurface.ts` is an orchestrator, not a family implementation.

## Open questions

- Which families currently lack enough runtime behavior to stay at `not-implemented` or `declarative`?
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
- [ ] Adapter registry tests pass.
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

- Splitting the SDK barrel further (M2).
- Making the packagability smoke strict (M4).
- Updating docs/readiness language (M4).
- Deciding proposal-runtime ownership (M4).
