# M0 — Family Contract and Maturity Model

## Outcome

A canonical family registry exists in the SDK that maps every `ContributionKind` to a `FamilyDefinition` carrying a support level (`typed` | `declarative` | `runtime-bridged` | `planner-integrated` | `public-supported`) and an explicit obligation checklist. Future family types are preserved in the SDK, but their maturity is explicit. Immediate schema/API drift between SDK constants and `config/contracts/reigh-extension.schema.json` is fixed.

## Background

The next wave of work will add family-specific SDK types: effects, transitions, shaders, agent tools, live data, render sidecars, etc. The pristine SDK boundary plan originally aimed to make `@reigh/editor-sdk` packageable by pulling it out of video-editor internals. A Codex review pointed out that packageability alone does not create a clean *family architecture* — the next wave would still need bespoke wiring across manifest types, `extensionSurface.ts`, registries, lifecycle cleanup, planner metadata, UI states, diagnostics, examples, and tests.

This milestone is the foundation course correction: we define the family adapter contract *before* the big barrel split, so the split is organized around families rather than generic type clusters.

## Scope (in scope)

1. **Design the family contract.**
   - Define `FamilySupportLevel` union: `typed`, `declarative`, `runtime-bridged`, `planner-integrated`, `public-supported`.
   - Define `FamilyDefinition` with:
     - `kind: ContributionKind`
     - `supportLevel: FamilySupportLevel`
     - `requiresTrustedCode: boolean`
     - `manifestSchemaDefinition: string` (path or identifier)
     - `sdkModules: readonly string[]`
     - `hostAdapter?: string`
     - `obligations: FamilyObligations`
   - Define `FamilyObligations` checklist:
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
   - Define `FamilyConformanceReport`.

2. **Create the canonical family registry.**
   - Add `src/sdk/families/familyDefinitions.ts` that exports a registry mapping each `ContributionKind` to its `FamilyDefinition`.
   - Replace `contributionKindNotYetBridged()` as the source of truth where appropriate; keep it as a compatibility helper if needed.
   - Populate definitions for existing families: surfaces, commands, parser, metadataFacet, assetDetailSection, outputFormat, process, effect, transition, clipType, shader, agentTool, liveSource, etc.
   - Classify each family honestly based on current implementation, not aspiration.

3. **Move contribution-kind constants and helpers into the family module.**
   - Consolidate `ContributionKind`, `CONTRIBUTION_KIND_MILESTONE`, and related unions/constants under `src/sdk/families/`.
   - Ensure video-editor internals can still import these values from the SDK.

4. **Fix immediate schema/API drift.**
   - Compare SDK `RenderRoute`, `DeterminismStatus`, and shader pass/source/uniform types against `config/contracts/reigh-extension.schema.json`.
   - Resolve mismatches by choosing the authoritative source (usually the schema) and updating the SDK types or the schema to match.
   - Add tests that fail if the two drift again.

5. **Add family conformance tests.**
   - `src/sdk/families/familyDefinitions.test.ts` asserts every `ContributionKind` has a `FamilyDefinition`, that no two families share the same kind, and that support levels match a known allowed set.
   - Add a negative test: an unknown contribution kind fails the registry lookup.

6. **Add release wiring for the family conformance check.**
   - Create `scripts/quality/check-extension-family-conformance.mjs` with an `--audit` mode that reports current family maturity.
   - Add `check:extension-family-conformance` to `package.json`.
   - In audit mode it should not fail the build; it should produce a report.

## Locked decisions

- A `ContributionKind` without a `FamilyDefinition` is a bug.
- Support levels are descriptive of current reality, not marketing labels.
- The SDK keeps future-family types public, but their `FamilyDefinition` must honestly mark them as `typed` or `declarative` until runtime semantics are proven.
- `config/contracts/reigh-extension.schema.json` is the authoritative source for manifest schema; SDK types derive from it or are explicitly co-evolved with it.

## Open questions

- Which existing families currently have runtime implementations vs. only descriptor types?
- Does the schema JSON already contain contribution definitions that lack SDK counterparts?
- Which families should be marked `requiresTrustedCode: true`?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `FamilyDefinition`, `FamilyObligations`, `FamilySupportLevel`, and `FamilyConformanceReport` exist in `src/sdk/families/`.
- [ ] Every `ContributionKind` has a `FamilyDefinition` in the registry.
- [ ] `contributionKindNotYetBridged()` is no longer the sole source of truth for family maturity.
- [ ] SDK/schema drift for `RenderRoute`, `DeterminismStatus`, and shader types is fixed and guarded by tests.
- [ ] `npm run check:extension-family-conformance -- --audit` runs and produces a report.
- [ ] All existing tests pass.

## Touchpoints

- `src/sdk/index.ts`
- `src/sdk/families/familyDefinitions.ts` (new)
- `src/sdk/families/conformance.ts` (new)
- `src/sdk/families/supportLevels.ts` (new)
- `config/contracts/reigh-extension.schema.json`
- `config/contracts/registry.json`
- `scripts/quality/check-extension-family-conformance.mjs` (new)
- `package.json`

## Anti-scope (not in this milestone)

- Moving renderability or other runtime contracts into the SDK (M1).
- Refactoring `extensionSurface.ts` onto host adapters (M2).
- Deciding proposal-runtime ownership (M2).
- Removing aspirational public types entirely (they are classified, not deleted).
