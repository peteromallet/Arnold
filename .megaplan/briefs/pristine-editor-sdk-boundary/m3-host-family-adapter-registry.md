# M3 — Host Family Adapter Registry

## Outcome

`src/tools/video-editor/runtime/extensionSurface.ts` becomes a thin coordinator, not the owner of every family projection. A host-side family adapter registry under `src/tools/video-editor/runtime/families/*` maps contribution kinds to adapters; a separate coordinator normalizes, disposes, projects planner capabilities, and asks conformance helpers for reports. Families marked `runtime-bridged` have real adapters. Families not yet ready are classified `delegated`: their projection logic is extracted into per-family helpers and wrapped in placeholder adapters that report conformance gaps.

## Background

M2a/M2b split the SDK into core and family modules. M3 inverts the host side so that adding a family means adding one SDK module, one host adapter, and one conformance report. To avoid preserving the monolithic switch inside placeholder adapters, we first extract per-family projector helpers, then wrap them.

## Scope (in scope)

1. **Define the host family adapter interface.**
   - Create `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts`:
     ```ts
     interface HostFamilyAdapter<C, D> {
       readonly kind: ContributionKind;
       normalize(input: NormalizeFamilyInput<C>): FamilyNormalizeResult<D>;
       disposeExtension?(extensionId: string): void;
       projectPlannerCapabilities?(input: FamilyPlannerInput<D>): readonly CapabilityRequirement[];
       conformanceReport(): FamilyConformanceReport;
     }
     ```
   - SDK-owned contract types live in `src/sdk/families/familyAdapter.ts`.
   - Add optional capability-specific interfaces instead of forcing all runtime behavior through `normalize()`:
     - `RenderPhaseHooks` for render-relevant families that need compile/materialize/teardown hooks.
     - `ExecutionPhaseHooks` for process-like families that need execute/cancel/progress hooks.
   - Families implement these optional interfaces only when their M1 requirements require them.

2. **Create the host adapter registry and coordinator.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts` is a passive lookup table: `get(kind)`, `require(kind)`, and `kinds()`.
   - `src/tools/video-editor/runtime/families/familyAdapterCoordinator.ts` owns bulk operations: normalize all contributions, dispose an extension, and project planner capabilities.
   - `src/tools/video-editor/runtime/families/familyConformance.ts` owns conformance aggregation; do not put `auditConformance` on the registry.

3. **Extract focused orchestration primitives before extracting adapters.**
   - Create narrow host-owned helpers/types for:
     - `FamilyContributionSequence`: deterministic contribution ordering and duplicate contribution ID behavior,
     - family diagnostics: reserved/declaration-only diagnostics and adapter diagnostics,
     - `FamilyRuntimeAssembly`: aggregation of per-family normalized descriptors,
     - output freezing/immutability of runtime output.
   - Preserve the existing `extensionSurface.ts` sort, duplicate, reserved-family diagnostic, and freeze semantics before moving family logic.
   - Add tests that compare old and new orchestration results for representative mixed contribution sets.

4. **Add the `delegated` execution maturity.**
   - Update the M1 family registry so any family whose projection logic still lives in `extensionSurface.ts` is classified as `delegated` rather than `runtime-bridged`.
   - `runtime-bridged` means a real, independent adapter exists.
   - `delegated` means the logic is extracted into a per-family helper and wrapped in a placeholder adapter that reports a conformance gap.
   - Every `delegated` conformance gap must include owner, reason, and `expiration` (`"M4"` or `"permanent"` only with explicit rationale).
   - Families with no host runtime behavior stay at execution maturity `absent`; their declaration maturity may still be `typed`, `schema-backed`, or `documented` if the portable contract exists.

5. **Prove the pattern with one low-risk family first.**
   - Pick the lowest-risk runtime family with clean normalization (e.g. `metadataFacet` or `assetDetailSection`).
   - Implement a real `HostFamilyAdapter` that owns normalization, disposal, planner projection, and conformance report.
   - Remove the corresponding switch cases from `extensionSurface.ts`.
   - Add regression tests.
   - Do not proceed to other families until this single adapter is demonstrably independent and conformance-tested.

6. **Expand to representative families only as a capped stretch.**
   - After the first family is proven, the maximum stretch is two additional real adapters:
     - one render-relevant family (`shader` or `effect`),
     - one execution/process-like family (`process` or `agentTool`).
   - For each, follow the same pattern and implement the optional lifecycle interface if needed.
   - If either stretch adapter does not complete inside the milestone, it lands as `delegated` with an extracted helper and documented conformance gap. Do not add a fourth real adapter in M3.

7. **Extract per-family projector helpers for remaining `delegated` families.**
   - For each family still using `extensionSurface.ts` switch cases, extract a pure helper module under `src/tools/video-editor/runtime/families/projectors/<family>Projector.ts`.
   - The helper takes raw contributions plus an explicit projector environment containing only the narrow values that family needs, and returns descriptors/diagnostics.
   - Projector helper input types must be plain-data interfaces defined outside `extensionSurface.ts`; SDK-owned contracts are preferred, and host-only data must be represented by narrow host adapter input interfaces.
   - It must not accept full `ExtensionContext`, `VideoEditorRuntimeSlices`, React/provider objects, DataProvider, or timeline contexts; pass only stable IDs, descriptors, and narrow callbacks needed by that projector.
   - Add a conformance check that fails if `runtime/families/projectors/*.ts` imports from `extensionSurface.ts`, `useTimelineState.types.ts`, or broad host runtime slice modules.
   - Wrap each helper in a placeholder `HostFamilyAdapter`.

8. **Refactor `extensionSurface.ts` into an orchestrator.**
   - Replace family switch cases with adapter registry calls.
   - `extensionSurface.ts` owns: collect contributions, sort, dispatch to adapters, aggregate diagnostics, freeze output.
   - Keep host-only types like `VideoEditorRuntimeSlices` in the host.
   - No family projection logic remains inline.

9. **Add adapter registry tests.**
   - `src/tools/video-editor/runtime/families/familyAdapterRegistry.test.ts`
   - `src/tools/video-editor/runtime/families/familyAdapterCoordinator.test.ts`
   - `src/tools/video-editor/runtime/families/familyConformance.test.ts`
   - Assert every family with execution maturity `runtime-bridged` has a real, non-placeholder host adapter.
   - Assert every `delegated` family has a placeholder adapter and a linked conformance gap.
   - Assert `extensionSurface.ts` has no inline projection logic for families.
   - Assert sorting, duplicate handling, reserved-family diagnostics, and freezing match pre-refactor behavior.

10. **Tighten family conformance check.**
   - Update `scripts/quality/check-extension-family-conformance.mjs` so release mode fails if:
     - A `ContributionKind` lacks a `FamilyDefinition`.
     - A family marked `runtime-bridged` lacks a real host adapter.
     - A family marked `planner-integrated` or higher lacks planner projection tests.
     - `extensionSurface.ts` contains inline projection logic for a `runtime-bridged` family.
     - A delegated projector imports forbidden broad host modules.
   - Audit mode reports `delegated` gaps without failing.

11. **Record an adapter performance baseline.**
   - Add a lightweight benchmark or test fixture for loading a representative batch of 20+ contributions through the adapter registry.
   - Record the pre-refactor baseline and fail only on obvious regressions agreed in the milestone notes; do not turn this into a broad performance project.

## Locked decisions

- Host adapters own runtime normalization, lifecycle cleanup, and planner projection.
- The SDK owns the family contract, descriptor types, and conformance report shape.
- `extensionSurface.ts` is a thin coordinator, not a family implementation.
- Placeholder adapters must not delegate back to the monolithic switch; they wrap extracted per-family helpers.
- `runtime-bridged` requires a real adapter; `delegated` is explicitly temporary unless marked permanent with rationale, and is tracked with owner and expiration.
- Cross-cutting ordering, duplicate, diagnostics, and freezing semantics belong to the orchestration layer, not individual adapters.
- M3 proves the architecture with one required real adapter and at most two additional real adapters.

## Open questions

- Which families currently lack enough runtime behavior to stay at execution maturity `absent`?
- Will adapter registry overhead affect extension loading performance?

## Constraints

- Preserve runtime behavior for extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `HostFamilyAdapter` interface exists and the registry can dispatch adapters by `ContributionKind`.
- [ ] Optional render and execution phase hook interfaces exist for families that need more than normalization.
- [ ] Focused orchestration primitives and tests preserve sort, duplicate, diagnostics, aggregation, and freeze behavior.
- [ ] `delegated` execution maturity is defined and applied to families not yet migrated.
- [ ] One low-risk family has a real adapter that replaces its `extensionSurface.ts` switch cases.
- [ ] Remaining families are either `runtime-bridged` with real adapters or `delegated` with extracted projector helpers and placeholder adapters.
- [ ] Delegated projector helpers use narrow data inputs, do not accept full host context objects, and do not import from forbidden broad host modules.
- [ ] `extensionSurface.ts` has no inline projection logic.
- [ ] Adapter registry tests pass.
- [ ] Family conformance check reports `delegated` gaps in audit mode and fails release mode for invalid maturity claims, missing required real adapters, or delegated gaps without owner/expiration.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/families/hostFamilyAdapter.ts` (new)
- `src/tools/video-editor/runtime/families/familyAdapterRegistry.ts` (new)
- `src/tools/video-editor/runtime/families/familyAdapterCoordinator.ts` (new)
- `src/tools/video-editor/runtime/families/familyConformance.ts` (new)
- `src/tools/video-editor/runtime/families/*Adapter.ts` (new)
- `src/tools/video-editor/runtime/families/projectors/*.ts` (new)
- `src/sdk/families/familyAdapter.ts` (new SDK contract)
- `src/sdk/families/familyDefinitions.ts` (update maturity levels)
- `scripts/quality/check-extension-family-conformance.mjs`

## Anti-scope (not in this milestone)

- Splitting the SDK barrel further (M2a/M2b).
- Making the external SDK import validator strict (M0).
- Updating docs/readiness language (M4).
- Deciding proposal-runtime ownership (M4).
