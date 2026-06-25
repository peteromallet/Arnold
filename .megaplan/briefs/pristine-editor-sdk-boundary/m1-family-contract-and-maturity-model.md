# M1 — Family Contract and Maturity Model

## Outcome

A canonical family registry exists in the SDK. Every `ContributionKind` maps to a `FamilyDefinition` with a two-axis maturity model: **declaration maturity** (schema/types/examples) and **execution maturity** (normalized, lifecycle-cleaned, UI-integrated, planner-integrated, production-supported). Future family types stay public but their real status is explicit. Immediate schema/API drift between SDK constants and `config/contracts/reigh-extension.schema.json` is fixed.

## Background

M0 removed video-editor imports from the SDK. M1 defines the family architecture that the SDK split and host adapter registry will be organized around. The maturity model has two axes so that we do not imply runtime support just because a type exists.

## Scope (in scope)

1. **Design the two-axis maturity model.**
   - Axis 1 — **Declaration maturity**:
     - `typed`: TypeScript types exist.
     - `declarative`: Manifest schema and descriptor shape are stable.
     - `documented`: Author docs and examples exist.
   - Axis 2 — **Execution maturity**:
     - `not-implemented`: No host runtime behavior.
     - `runtime-bridged`: Host normalizes/descriptors exist but full integration may be partial.
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

3. **Move contribution-kind constants into the family module.**
   - Consolidate `ContributionKind`, `CONTRIBUTION_KIND_MILESTONE`, and related helpers under `src/sdk/families/`.

4. **Fix immediate schema/API drift.**
   - Compare SDK `RenderRoute`, `DeterminismStatus`, and shader pass/source/uniform types against `config/contracts/reigh-extension.schema.json`.
   - Resolve mismatches; add tests that fail on future drift.

5. **Add family conformance infrastructure.**
   - `src/sdk/families/familyDefinitions.test.ts`
   - `scripts/quality/check-extension-family-conformance.mjs` with `--audit` mode.
   - Wire `check:extension-family-conformance` into `package.json`.

6. **Make the family matrix machine-readable and generative.**
   - Expose a function `getFamilyMatrix(): FamilyDefinition[]` from the registry.
   - Add a script `scripts/quality/generate-extension-family-matrix.mjs` that:
     - emits a JSON matrix,
     - asserts every family in the matrix has a non-empty `manifestSchemaDefinition`, `sdkModules`, and obligation checklist,
     - fails if declaration maturity and execution maturity are not both set.
   - Commit the generated matrix to `docs/extensions/extension-family-matrix.json` so docs/schema/examples can consume it.
   - Add a test that fails if `docs/extensions/extension-family-matrix.json` is out of sync with the registry.

## Locked decisions

- A `ContributionKind` without a `FamilyDefinition` is a bug.
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
- [ ] `contributionKindNotYetBridged()` is no longer the sole source of truth.
- [ ] SDK/schema drift for `RenderRoute`, `DeterminismStatus`, and shader types is fixed and guarded.
- [ ] `npm run check:extension-family-conformance -- --audit` produces a report.
- [ ] `docs/extensions/extension-family-matrix.json` is generated and in sync with the registry.
- [ ] All existing tests pass.

## Touchpoints

- `src/sdk/families/familyDefinitions.ts` (new)
- `src/sdk/families/conformance.ts` (new)
- `src/sdk/families/supportLevels.ts` (new)
- `config/contracts/reigh-extension.schema.json`
- `config/contracts/registry.json`
- `scripts/quality/check-extension-family-conformance.mjs` (new)
- `package.json`

## Anti-scope (not in this milestone)

- Moving runtime contracts into the SDK (M0).
- Splitting the SDK barrel (M2).
- Refactoring `extensionSurface.ts` onto host adapters (M3).
- Making the packagability smoke strict (M4).
