# M0 — Extract Portable SDK Contracts

## Outcome

Every portable contract that `@reigh/editor-sdk` needs is owned by the SDK and has no import from `src/tools/video-editor/*`. `src/sdk/index.ts` no longer re-exports video-editor internals. An external SDK-consumer package fixture compiles cleanly. Doc/code discrepancies are recorded so later milestones align with canonical truth.

## Background

The SDK currently declares it must not depend on editor internals, yet it imports from `@/tools/video-editor/runtime/renderability.ts` and `@/tools/video-editor` in `src/sdk/index.ts`. This milestone fixes that contradiction before any family architecture or barrel-split work. It is the hard prerequisite the rest of the epic builds on.

## Scope (in scope)

1. **Reconcile docs/code state before churn.**
   - Read `docs/extensions/phase4-readiness.md`, `docs/extensions/reigh-extension-layer-foundation-plan.md`, and `docs/extensions/foundation-closure-assessment.md`.
   - Record every place where docs disagree with current code (e.g. stale references to `runtime/contributionFamilies.ts`, claims about `src/sdk/index.ts` existence, Phase 4 promotion status).
   - Produce `docs/extensions/pristine-sdk-boundary-audit.md` with a table of discrepancies, owner, and proposed resolution.
   - Do not rewrite all docs yet; just establish the canonical truth that later milestones will align with.

2. **Audit every import from `src/tools/video-editor/*` inside `src/sdk/**`.**
   - List files, imported symbols, and whether each symbol is truly portable or host-only.

3. **Move video renderability contracts into SDK-owned video modules.**
   - Create `src/sdk/video/rendering/renderability.ts` with data-only types:
     - `RenderRoute` (video-specific)
     - `DeterminismStatus` (video-specific)
     - `RenderBlockerReason`
     - `CapabilityFinding`
   - Create `src/sdk/video/rendering/artifacts.ts` with:
     - `RenderArtifact` (video-specific)
     - `RenderMaterial` (video-specific)
     - `RenderMaterialRef`
     - `RenderStorageLocator`
   - Create `src/sdk/video/rendering/capabilities.ts` with:
     - `ShaderMaterializerRequirementScope`
     - `shaderMissingMaterializerBlockerMessage` (video-specific)
   - Update `src/tools/video-editor/runtime/renderability.ts` to depend on SDK-owned contracts.

4. **Move video timeline primitives needed by the video SDK surface into SDK-owned video modules.**
   - Identify which timeline patch/diff/ops/reader types the SDK re-exports only because host code needs them.
   - Move truly portable shapes (e.g. `TimelinePatch` (video-specific), `TimelineDiff` (video-specific), `TimelineDiffGranularity`, `TimelineProposalInput`) into `src/sdk/video/timeline/patch.ts` and `src/sdk/video/timeline/reader.ts`.
   - Keep host-only planner execution details in `src/tools/video-editor`.

5. **Move video asset metadata contracts into SDK-owned video modules.**
   - Move `AssetMetadata`, `AssetIntegrityMetadata`, `AssetGPSMetadata`, etc. into `src/sdk/video/assets/metadata.ts` if they are referenced by SDK public types.

6. **Update `src/sdk/index.ts`.**
   - Replace all `@/tools/video-editor/*` imports with SDK-local imports.
   - Keep the file as a barrel; do not do the full module split yet (that is M2).

7. **Strengthen and run the SDK import guard.**
   - Ensure `scripts/quality/check-video-editor-sdk-imports.mjs` fails if any `src/sdk/**` file imports from `src/tools/video-editor/*` or `@/tools/video-editor/*`.
   - Upgrade the guard from import-text matching to TypeScript module resolution: create a program or use `ts.resolveModuleName` for every static import, export-from, and literal dynamic import in `src/sdk/**`, then fail if any resolved absolute path is under `src/tools/video-editor/**`.
   - Keep the textual checks as a fast prefilter, but do not rely on them as the source of truth.
   - Run the check; fix all failures.
   - Add negative tests: a direct SDK import, an SDK export-from, a literal dynamic import, and an alias-resolved import from video-editor internals all fail the guard.

8. **Add an external SDK import validator.**
   - Replace the current repo-alias smoke with a temp external consumer that:
     - has its own `tsconfig.json` and minimal `package.json`,
     - resolves `@reigh/editor-sdk` through a package-like temp entrypoint generated from the SDK, not through the repo's `@/*` path alias,
     - has no `@/` alias, no `src/*` path mapping, and no Vite app context,
     - imports the full public SDK surface and representative family/contribution symbols available from the public barrel.
   - Run `tsc --noEmit` in that temp consumer and fail if it emits any diagnostic from SDK files.
   - Do not filter SDK diagnostics; `skipLibCheck` should remain true only for third-party `.d.ts`.
   - Add a static import-graph assertion over the temp consumer and SDK entrypoint that no resolved module path falls under `src/tools/video-editor`.
   - Add a runtime evaluation smoke for value exports: build or transpile the temp consumer enough to import the SDK package entrypoint in Node, enumerate the exported namespace, touch each value export, and report the specific binding that requires browser globals, Vite aliases, lazy host imports, or video-editor internals.
   - Wire the validator into `npm run check:video-editor-sdk-imports` or `npm run test:extensions`.

9. **Add a representative family contract sanity check.**
   - Pick three families of different risk types: one video metadata family (e.g. `metadataFacet`), one video render-relevant family (e.g. `shader`), and one video execution/process-like family (e.g. `process`).
   - For each, document in code comments:
     - what is portable vs. host-only today,
     - which SDK types are declaration-only,
     - which host behavior must remain in `src/tools/video-editor`.
   - This sanity check is documentation-only; it validates the contract extraction boundaries before M2/M3 broaden the work.

## Locked decisions

- After M0, no file under `src/sdk/**` may import from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- Host code may still import from the SDK; the dependency direction is one-way.
- Portable contracts are data-only shapes, not host behavior or React components.
- The external SDK import validator must compile with no diagnostics from SDK files and must not rely on repo path aliases.
- The SDK must evaluate in a package-like Node consumer without importing host/editor internals. Runtime behavior that needs DOM, React providers, DataProvider, timeline contexts, localStorage, or editor services is host-owned.

## Open questions

- Which timeline/planner types are genuinely portable vs. execution details?
- Are there value-level exports (functions, constants) in the SDK that secretly depend on host modules?

## Constraints

- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] `docs/extensions/pristine-sdk-boundary-audit.md` records doc/code discrepancies.
- [ ] `src/sdk/**` has zero imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and catches deliberate direct, re-export, dynamic, and alias-resolved violations.
- [ ] The external SDK import validator compiles with `tsc --noEmit`, emits no diagnostics from `src/sdk/**`, has no repo aliases, and evaluates/touches SDK value exports at runtime.
- [ ] Representative family sanity check documents portable vs. host-only boundaries for one metadata, one render-relevant, and one execution/process-like family.
- [ ] All existing public SDK exports remain available from `@reigh/editor-sdk` with compatible types.
- [ ] `npm run quality:check` and `npm run test:readiness` pass.

## Touchpoints

- `src/sdk/index.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- New `src/sdk/video/rendering/*` modules
- New `src/sdk/video/timeline/*` modules
- New `src/sdk/video/assets/*` modules
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- External SDK import validator under `scripts/quality/` or `scripts/quality/fixtures/sdk-consumer-package/`
- `docs/extensions/pristine-sdk-boundary-audit.md` (new)

## Anti-scope (not in this milestone)

- Splitting `src/sdk/index.ts` into scoped core and family modules (M2a/M2b).
- Defining the family maturity registry (M1).
- Refactoring `extensionSurface.ts` onto adapters (M3).
- Governance/docs closure and final release merge (M4).
