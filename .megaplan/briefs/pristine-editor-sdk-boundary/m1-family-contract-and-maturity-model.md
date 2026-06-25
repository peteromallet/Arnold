# M1 — Family Contract and Maturity Model

## Outcome

A canonical, machine-readable family maturity registry exists in `src/sdk/families/familyDefinitions.ts`. Every `ContributionKind` maps to a `FamilyDefinition` with a two-axis maturity model (declaration + execution) and a compact requirement checklist. `config/extensions/family-maturity.json` is generated from the TypeScript registry and used by gates, but it is not hand-edited. Immediate schema/API drift between SDK constants and `config/contracts/reigh-extension.schema.json` is fixed.

## Background

M0 removed video-editor imports from the SDK and made it externally compilable. M1 defines the family architecture that the SDK split and host adapter registry will be organized around. The maturity model is data, not prose, so gates can enforce it.

## Scope (in scope)

1. **Design the two-axis maturity model.**
   - Axis 1 — **Declaration maturity**:
     - `typed`: TypeScript types exist.
     - `schema-backed`: Manifest schema and descriptor shape are stable.
     - `documented`: Author docs and examples exist.
   - Axis 2 — **Execution maturity**:
     - `absent`: No host runtime behavior.
     - `delegated`: Runtime behavior exists, but it delegates through an extracted host projector wrapped by a placeholder adapter that reports a conformance gap.
     - `runtime-bridged`: A real, independent host adapter owns normalization, lifecycle, and diagnostics.
     - `planner-integrated`: Export/render planner participation is real and tested.
     - `public-supported`: Lifecycle, UI, diagnostics, persistence, examples, and conformance tests are complete.
   - `FamilyDefinition` includes:
     - `kind: ContributionKind`
     - `declarationMaturity: DeclarationMaturity`
     - `executionMaturity: ExecutionMaturity`
     - `requiresTrustedCode: boolean`
     - `manifestSchemaDefinition: string`
     - `sdkModules: readonly string[]`
     - `hostAdapter?: string`
     - `requirements: FamilyRequirementChecklist`
   - `FamilyRequirementChecklist`:
     - manifest schema
     - normalized descriptor
     - registration API
     - lifecycle cleanup
     - diagnostics
     - planner projection
     - UI integration
     - persistence posture
     - examples
     - tests
   - `FamilyConformanceReport` reports the current declaration/execution coordinates plus requirement coverage and any gaps.
   - Requirement paths should follow a predictable convention:
     - conformance tests live next to the family module as `<family>.conformance.test.ts` or under a clearly named adjacent `__tests__` file,
     - examples live under `src/sdk/families/examples/` or `docs/extensions/examples/` and are required only for `public-supported` families,
     - intermediate maturity states may have conformance tests without public examples.

2. **Create the canonical family registry.**
   - Add `src/sdk/families/familyDefinitions.ts`.
   - Map every `ContributionKind` to a `FamilyDefinition` with honest maturity levels.
   - Replace `contributionKindNotYetBridged()` as the source of truth where appropriate.
   - Populate definitions for: surfaces, commands, parser, metadataFacet, assetDetailSection, outputFormat, process, effect, transition, clipType, shader, agentTool, liveSource, searchProvider, etc.

3. **Make the maturity model machine-readable and authoritative.**
   - The TypeScript registry in `src/sdk/families/familyDefinitions.ts` is the canonical source of truth.
   - `config/extensions/family-maturity.json` is a generated release artifact; gates may read it, but it must never be edited by hand.
   - Generate it from a single exported const registry in `src/sdk/families/familyDefinitions.ts` via `scripts/quality/generate-extension-family-matrix.mjs`.
   - The registry must use `as const satisfies Record<ContributionKind, FamilyDefinition>` or an equivalent type-safe factory so the JSON artifact is derived from the TypeScript source rather than re-described by the generator.
   - The JSON row per family must include:
     - family id
     - SDK module path
     - host adapter path (or null)
     - declaration maturity
     - execution maturity
     - schema coverage flag
     - lifecycle coverage flag
     - planner coverage flag
     - docs/examples coverage flag
     - conformance report path
   - Add a test that fails if `config/extensions/family-maturity.json` is out of sync with the registry.
   - Add a generator completeness test that fails if a field exists in `FamilyDefinition` but is missing or null in any generated JSON row, unless that field is explicitly optional.
   - Add a round-trip test that deserializes `config/extensions/family-maturity.json`, compares every row back to the TypeScript registry, and proves every `ContributionKind` is represented.

4. **Replace milestone constants with registry-derived family status.**
   - Consolidate `ContributionKind` and family helpers under `src/sdk/families/`.
   - Do not create a new public `CONTRIBUTION_KIND_MILESTONE` authority. Milestone/status information must be derived from `FamilyDefinition`.
   - Keep existing helper names such as `contributionKindNotYetBridged()` only as temporary compatibility shims that read the registry, and schedule their removal once host callers move to explicit family status helpers.

5. **Fix immediate schema/API drift and establish schema coverage rules.**
   - Compare SDK `RenderRoute`, `DeterminismStatus`, and shader pass/source/uniform types against `config/contracts/reigh-extension.schema.json`.
   - Resolve mismatches; add tests that fail on future drift.
   - For every `FamilyDefinition.manifestSchemaDefinition`, assert the named schema definition exists in `config/contracts/reigh-extension.schema.json`.
   - Audit schema definitions that appear to describe contribution families and require each to map to a `FamilyDefinition` or to an explicit host-only/internal note.
   - Add a release-mode check that fails when a `schema-backed` or `documented` family lacks schema coverage.
   - Do not attempt a full TypeScript-to-JSON-schema structural diff in this milestone; keep the gate focused on declared family/schema coverage plus the known drift-prone render/shader vocabularies.

6. **Add family conformance infrastructure.**
   - `src/sdk/families/familyDefinitions.test.ts`
   - `scripts/quality/check-extension-family-conformance.mjs` with `--audit` and `--release` modes.
   - In `--release` mode, fail if:
     - a `ContributionKind` lacks a `FamilyDefinition`,
     - `config/extensions/family-maturity.json` is out of sync,
     - declaration maturity and execution maturity are both not set,
     - execution maturity is `runtime-bridged` or higher while declaration maturity is below `schema-backed`,
     - execution maturity is `planner-integrated` or higher while declaration maturity is below `documented`,
     - a family with declaration maturity `schema-backed` or `documented` lacks manifest schema coverage.
   - Wire `check:extension-family-conformance` into `package.json`.

## Locked decisions

- A `ContributionKind` without a `FamilyDefinition` is a bug.
- `src/sdk/families/familyDefinitions.ts` is the canonical source of truth for family maturity.
- `config/extensions/family-maturity.json` is a generated release artifact; gates may read it, but it must not be hand-edited.
- Support levels describe current reality, not aspiration.
- Public future-family types stay in the SDK but are honestly labeled `typed`/`schema-backed` until runtime semantics are proven.
- `config/contracts/reigh-extension.schema.json` is authoritative for manifest schema.
- Cross-axis maturity combinations must be coherent. Runtime support cannot outrun the declaration and documentation needed for authors to use it safely.

## Open questions

- Which families currently have runtime implementations vs. only descriptor types?
- Does the schema JSON contain contribution definitions that lack SDK counterparts?
- Which families should be marked `requiresTrustedCode: true`?
- Are any currently bridged families only `typed` because their manifest schema is incomplete?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `FamilyDefinition`, `FamilyRequirementChecklist`, declaration/execution maturity, and `FamilyConformanceReport` exist.
- [ ] Every `ContributionKind` has a `FamilyDefinition`.
- [ ] `config/extensions/family-maturity.json` exists and is generated from the registry.
- [ ] Generator completeness and round-trip tests prove the generated JSON has every required registry field and every `ContributionKind`.
- [ ] Existing milestone/not-yet-bridged helpers read the registry and are no longer a source of truth.
- [ ] SDK/schema drift for `RenderRoute`, `DeterminismStatus`, shader types, and declared family schema coverage is fixed and guarded.
- [ ] Schema contribution definitions are either mapped to a `FamilyDefinition` or explicitly classified as host-only/internal.
- [ ] Release-mode conformance rejects incoherent cross-axis maturity combinations.
- [ ] Family requirement paths use the agreed conformance-test/example convention and public-supported families have examples.
- [ ] `npm run check:extension-family-conformance -- --release` passes.
- [ ] All existing tests pass.

## Touchpoints

- `src/sdk/families/familyDefinitions.ts` (new)
- `src/sdk/families/conformance.ts` (new)
- `src/sdk/families/maturity.ts` (new)
- `config/extensions/family-maturity.json` (new)
- `scripts/quality/generate-extension-family-matrix.mjs` (new)
- `config/contracts/reigh-extension.schema.json`
- `config/contracts/registry.json`
- `scripts/quality/check-extension-family-conformance.mjs` (new)
- `package.json`

## Anti-scope (not in this milestone)

- Moving runtime contracts into the SDK (M0).
- Splitting the SDK barrel (M2a/M2b).
- Refactoring `extensionSurface.ts` onto host adapters (M3).
- Governance/docs closure and final release merge (M4).
