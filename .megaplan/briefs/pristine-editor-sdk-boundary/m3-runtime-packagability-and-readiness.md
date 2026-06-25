# M3 — Runtime Helpers, Strict Packagability, and Readiness

## Outcome

The SDK packagability smoke fails on SDK-internal TypeScript diagnostics. Proposal-runtime ownership is decided and implemented. Author-facing deep imports are replaced. Contract governance recognizes `src/sdk/index.ts` as the extension SDK boundary. Docs and readiness checks reflect the new boundary and family maturity model. The SDK is releasable as a pristine developer surface.

## Background

M0 defined family maturity. M1 split the SDK into family modules. M2 refactored the host side onto family adapters. M3 closes the loop: it makes the package boundary strict, cleans up remaining couplings, and aligns governance/docs/readiness.

## Scope (in scope)

1. **Make the SDK packagability smoke strict.**
   - Replace the temporary fixture with a package-style fixture that includes SDK source files in the TypeScript program.
   - Consumer imports only `@reigh/editor-sdk`.
   - Do not filter diagnostics from `src/sdk/**`; `skipLibCheck` stays true only for third-party `.d.ts`.
   - Add negative assertions: fail on resolved paths under `src/tools/video-editor` or `@/tools/video-editor`, and fail if `tsc` emits any diagnostic from SDK files.
   - Ensure `npm run quality:check` includes the stricter smoke.
   - Add a second smoke that imports representative `src/sdk/families/*` modules directly.

2. **Decide and implement proposal-runtime ownership.**
   - Determine whether `createProposalRuntime` is public SDK functionality or host implementation.
   - If public: move to `src/sdk/runtime/proposalRuntime.ts` and update consumers.
   - If host-only: expose only `ProposalRuntime` types from SDK and keep `createProposalRuntime` behind a host adapter.
   - Ensure external consumers do not need `src/tools/video-editor/lib/proposal-runtime.ts` for SDK concepts.

3. **Split `createExtensionContext()` into pure SDK contract plus host wiring.**
   - The SDK owns a pure context contract.
   - Host wiring (DOM, localStorage-backed settings, console behavior, default services, lifecycle cleanup) lives in a host factory, not in the base SDK abstraction.

4. **Classify and replace remaining video-editor deep imports.**
   - Audit every entry in `config/governance/video-editor-sdk-import-allowlist.json`.
   - Label each as `author-facing`, `host-facing`, or `internal`.
   - Replace author-facing imports with `@reigh/editor-sdk` or scoped SDK modules.
   - Document host-only/internal entries with owner, rationale, and removal condition.

5. **Update contract registry and governance mapping.**
   - Update `config/contracts/registry.json` so `src/sdk/index.ts` is the extension SDK contract.
   - Reclassify `src/tools/video-editor/index.ts` as host/video-editor public API.
   - Ensure `npm run check:contracts` and `npm run check:contract-surface-map` pass.

6. **Update compatibility docs and readiness docs.**
   - Update `docs/governance/contracts/compatibility-shims.md` with remaining host-only exceptions.
   - Update `docs/extensions/phase4-readiness.md` and `docs/extensions/foundation-closure-assessment.md` to reflect the family maturity model and the adapter registry.
   - Ensure docs do not overstate Phase 4 runtime support.

7. **Final validation and manual merge prep.**
   - Run all release gates locally:
     ```bash
     npm run quality:check
     npm run test:readiness
     npm run test:extensions
     npm run check:sdk-public-exports -- --release
     npm run check:extension-drift -- --release
     npm run check:example-readiness -- --release
     npm run check:extension-family-conformance -- --release
     ```
   - Fix regressions.
   - Prepare merge using the existing manual pristine-worktree workflow.

## Locked decisions

- The SDK owns portable contracts and author-facing descriptor types.
- The video editor owns host implementations, React/provider wiring, runtime normalization, and editor internals.
- Remaining allowlist entries after this milestone must be explicitly host-only and documented.
- Packagability smoke must fail on SDK-internal type diagnostics.

## Open questions

- How many existing author-facing deep imports require real replacements versus allowlist documentation?
- Will moving `proposal-runtime.ts` implementation into the SDK pull in additional video-editor internals?
- Are there docs/examples that claim Phase 4 runtime support that need explicit corrections?

## Constraints

- Preserve runtime behavior for extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check`, `npm run test:readiness`, `npm run test:extensions`, and family conformance checks must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] SDK packagability smoke fails on a deliberately introduced SDK type error.
- [ ] Proposal runtime ownership is decided and implemented.
- [ ] All author-facing deep imports from `src/tools/video-editor/**` are replaced.
- [ ] Remaining allowlist entries are classified as host-only/internal with owner, rationale, and removal condition.
- [ ] Contract registry recognizes `src/sdk/index.ts` as the extension SDK boundary.
- [ ] Docs match the new boundary and do not overstate Phase 4 runtime support.
- [ ] All release gates pass locally.
- [ ] Changes are merged to `main` (manually if hooks are unavailable).

## Touchpoints

- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `scripts/quality/check-extension-family-conformance.mjs`
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `src/sdk/runtime/proposalRuntime.ts` (if created)
- `src/sdk/context.ts`
- `config/governance/video-editor-sdk-import-allowlist.json`
- `config/contracts/registry.json`
- `docs/governance/contracts/compatibility-shims.md`
- `docs/extensions/phase4-readiness.md`
- `docs/extensions/foundation-closure-assessment.md`

## Anti-scope (not in this milestone)

- Further splitting the SDK barrel (M1).
- Adding new extension families or runtime features.
- Fixing pre-existing TypeScript errors in host-only video-editor internals.
- Implementing dynamic extension loading, marketplace, or sandboxing.
