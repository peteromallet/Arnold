# M1 — Family Contract and Maturity Model

## Outcome

A canonical, machine-readable family maturity registry exists. Every `ContributionKind` maps to a `FamilyDefinition` with a two-axis maturity model (declaration + execution) and an obligation checklist. `config/extensions/family-maturity.json` is the source of truth; gates read it. Immediate schema/API drift between SDK constants and `config/contracts/reigh-extension.schema.json` is fixed.

## Background

M0 removed video-editor imports from the SDK and made it externally compilable. M1 defines the family architecture that the SDK split and host adapter registry will be organized around. The maturity model is data, not prose, so gates can enforce it.

## Scope (in scope)

1. **Design the two-axis maturity model.**
   - Axis 1 — **Declaration maturity**:
     - `typed`: TypeScript types exist.
     - `declarative`: Manifest schema and descriptor shape are stable.
     - `documented`: Author docs and examples exist.
   - Axis 2 — **Execution maturity**:
     - `not-implemented`: No host runtime behavior.
     - `legacy-delegated`: Runtime behavior exists but is still owned by a monolithic host helper; a placeholder adapter wraps an extracted projector and reports a conformance gap.
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
     - `obligations: FamilyObligations`
   - `FamilyObligations` checklist:
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
   - `FamilyConformanceReport`.

2. **Create the canonical family registry.**
   - Add `src/sdk/families/familyDefinitions.ts`.
   - Map every `ContributionKind` to a `FamilyDefinition` with honest maturity levels.
   - Replace `contributionKindNotYetBridged()` as the source of truth where appropriate.
   - Populate definitions for: surfaces, commands, parser, metadataFacet, assetDetailSection, outputFormat, process, effect, transition, clipType, shader, agentTool, liveSource, searchProvider, etc.

3. **Make the maturity model machine-readable and authoritative.**
   - The TypeScript registry in `src/sdk/families/familyDefinitions.ts` is the canonical source of truth.
   - `config/extensions/family-maturity.json` is a generated release artifact; gates may read it, but it must never be edited by hand.
   - Generate it from `src/sdk/families/familyDefinitions.ts` via `scripts/quality/generate-extension-family-matrix.mjs`.
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

4. **Move contribution-kind constants into the family module.**
   - Consolidate `ContributionKind`, `CONTRIBUTION_KIND_MILESTONE`, and related helpers under `src/sdk/families/`.

5. **Fix immediate schema/API drift.**
   - Compare SDK `RenderRoute`, `DeterminismStatus`, and shader pass/source/uniform types against `config/contracts/reigh-extension.schema.json`.
   - Resolve mismatches; add tests that fail on future drift.

6. **Add family conformance infrastructure.**
   - `src/sdk/families/familyDefinitions.test.ts`
   - `scripts/quality/check-extension-family-conformance.mjs` with `--audit` and `--release` modes.
   - In `--release` mode, fail if:
     - a `ContributionKind` lacks a `FamilyDefinition`,
     - `config/extensions/family-maturity.json` is out of sync,
     - declaration maturity and execution maturity are both not set.
   - Wire `check:extension-family-conformance` into `package.json`.

## Locked decisions

- A `ContributionKind` without a `FamilyDefinition` is a bug.
- `src/sdk/families/familyDefinitions.ts` is the canonical source of truth for family maturity.
- `config/extensions/family-maturity.json` is a generated release artifact; gates may read it, but it must not be hand-edited.
- Support levels describe current reality, not aspiration.
- Public future-family types stay in the SDK but are honestly labeled `typed`/`declarative` until runtime semantics are proven.
- `config/contracts/reigh-extension.schema.json` is authoritative for manifest schema.

## Open questions

- Which families currently have runtime implementations vs. only descriptor types?
- Does the schema JSON contain contribution definitions that lack SDK counterparts?
- Which families should be marked `requiresTrustedCode: true`?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `FamilyDefinition`, `FamilyObligations`, declaration/execution maturity, and `FamilyConformanceReport` exist.
- [ ] Every `ContributionKind` has a `FamilyDefinition`.
- [ ] `config/extensions/family-maturity.json` exists and is generated from the registry.
- [ ] `contributionKindNotYetBridged()` is no longer the sole source of truth.
- [ ] SDK/schema drift for `RenderRoute`, `DeterminismStatus`, and shader types is fixed and guarded.
- [ ] `npm run check:extension-family-conformance -- --release` passes.
- [ ] All existing tests pass.

## Touchpoints

- `src/sdk/families/familyDefinitions.ts` (new)
- `src/sdk/families/conformance.ts` (new)
- `src/sdk/families/supportLevels.ts` (new)
- `config/extensions/family-maturity.json` (new)
- `scripts/quality/generate-extension-family-matrix.mjs` (new)
- `config/contracts/reigh-extension.schema.json`
- `config/contracts/registry.json`
- `scripts/quality/check-extension-family-conformance.mjs` (new)
- `package.json`

## Anti-scope (not in this milestone)

- Moving runtime contracts into the SDK (M0).
- Splitting the SDK barrel (M2).
- Refactoring `extensionSurface.ts` onto host adapters (M3).
- Governance/docs closure and final release merge (M4).
