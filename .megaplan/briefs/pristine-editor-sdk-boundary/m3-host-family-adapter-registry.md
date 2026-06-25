# M3 — Host Family Adapter Registry

## Outcome

`src/tools/video-editor/runtime/extensionSurface.ts` becomes an orchestrator, not the owner of every family projection. A host-side family adapter registry under `src/tools/video-editor/runtime/families/*` normalizes, disposes, projects planner capabilities, and produces conformance reports per family. Families marked `runtime-bridged` have real adapters. Families not yet ready are classified `legacy-delegated`: their projection logic is extracted into per-family helpers and wrapped in placeholder adapters that report conformance gaps.

## Background

M2 split the SDK into family modules. M3 inverts the host side so that adding a family means adding one SDK module, one host adapter, and one conformance report. To avoid preserving the monolithic switch inside placeholder adapters, we first extract per-family projector helpers, then wrap them.

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

3. **Add the `legacy-delegated` execution maturity.**
   - Update the M1 family registry so any family whose projection logic still lives in `extensionSurface.ts` is classified as `legacy-delegated` rather than `runtime-bridged`.
   - `runtime-bridged` means a real, independent adapter exists.
   - `legacy-delegated` means the logic is extracted into a per-family helper and wrapped in a placeholder adapter that reports a conformance gap.
   - Families below `legacy-delegated` stay at `not-implemented` or `declarative`.

4. **Prove the pattern with one low-risk family first.**
   - Pick the lowest-risk runtime family with clean normalization (e.g. `metadataFacet` or `assetDetailSection`).
   - Implement a real `HostFamilyAdapter` that owns normalization, disposal, planner projection, and conformance report.
   - Remove the corresponding switch cases from `extensionSurface.ts`.
   - Add regression tests.
   - Do not proceed to other families until this single adapter is demonstrably independent and conformance-tested.

5. **Expand to representative families (stretch within this milestone).**
   - After the first family is proven, if capacity allows, add real adapters for:
     - **Render-relevant family:** `shader` or `effect`.
     - **Execution/process-like family:** `process` or `agentTool`.
   - For each, follow the same pattern.
   - If capacity does not allow, register these as `legacy-delegated` with extracted helpers and documented conformance gaps.

6. **Extract per-family projector helpers for remaining `legacy-delegated` families.**
   - For each family still using `extensionSurface.ts` switch cases, extract a pure helper module under `src/tools/video-editor/runtime/families/projectors/<family>Projector.ts`.
   - The helper takes raw contributions + extension context and returns descriptors/diagnostics.
   - It must not depend on React, DataProvider, or timeline contexts except through explicitly passed values.
   - Wrap each helper in a placeholder `HostFamilyAdapter`.

7. **Refactor `extensionSurface.ts` into an orchestrator.**
   - Replace family switch cases with adapter registry calls.
   - `extensionSurface.ts` owns: collect contributions, sort, dispatch to adapters, aggregate diagnostics, freeze output.
   - Keep host-only types like `VideoEditorRuntimeSlices` in the host.
   - No family projection logic remains inline.

8. **Add adapter registry tests.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.test.ts`
   - `src/tools/video-editor/runtime/families/familyConformance.test.ts`
   - Assert every family with execution maturity `runtime-bridged` has a real, non-placeholder host adapter.
   - Assert every `legacy-delegated` family has a placeholder adapter and a linked conformance gap.
   - Assert `extensionSurface.ts` has no inline projection logic for families.

9. **Tighten family conformance check.**
   - Update `scripts/quality/check-extension-family-conformance.mjs` so release mode fails if:
     - A `ContributionKind` lacks a `FamilyDefinition`.
     - A family marked `runtime-bridged` lacks a real host adapter.
     - A family marked `planner-integrated` or higher lacks planner projection tests.
     - `extensionSurface.ts` contains inline projection logic for a `runtime-bridged` family.
   - Audit mode reports `legacy-delegated` gaps without failing.

## Locked decisions

- Host adapters own runtime normalization, lifecycle cleanup, and planner projection.
- The SDK owns the family contract, descriptor types, and conformance report shape.
- `extensionSurface.ts` is an orchestrator, not a family implementation.
- Placeholder adapters must not delegate back to the monolithic switch; they wrap extracted per-family helpers.
- `runtime-bridged` requires a real adapter; `legacy-delegated` is explicitly temporary and tracked.

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

- [ ] `HostFamilyAdapter` interface exists and the registry can dispatch adapters by `ContributionKind`.
- [ ] `legacy-delegated` execution maturity is defined and applied to families not yet migrated.
- [ ] One low-risk family has a real adapter that replaces its `extensionSurface.ts` switch cases.
- [ ] Remaining families are either `runtime-bridged` with real adapters or `legacy-delegated` with extracted projector helpers and placeholder adapters.
- [ ] `extensionSurface.ts` has no inline projection logic.
- [ ] Adapter registry tests pass.
- [ ] Family conformance check reports `legacy-delegated` gaps in audit mode and fails release mode for missing real adapters.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts` (new)
- `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts` (new)
- `src/tools/video-editor/runtime/families/*Adapter.ts` (new)
- `src/tools/video-editor/runtime/families/projectors/*.ts` (new)
- `src/sdk/families/familyAdapter.ts` (new SDK contract)
- `src/sdk/families/familyDefinitions.ts` (update maturity levels)
- `scripts/quality/check-extension-family-conformance.mjs`

## Anti-scope (not in this milestone)

- Splitting the SDK barrel further (M2).
- Making the packagability smoke strict (M0).
- Updating docs/readiness language (M4).
- Deciding proposal-runtime ownership (M4).
