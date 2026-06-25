# M4 — Runtime Helpers, Governance, and Readiness

## Outcome

Proposal-runtime ownership is decided and implemented. `createExtensionContext()` is split into a pure SDK contract plus host wiring. Remaining author-facing deep imports are replaced. Contract governance recognizes `src/sdk/index.ts` as the extension SDK boundary. Docs and readiness checks reflect the new boundary, family maturity model, and adapter architecture. The SDK passes all release gates and is merged to `main`.

## Background

M0 made the SDK dependency-clean and externally compilable. M1 defined the family maturity model. M2 split the SDK. M3 built the host adapter registry skeleton and proved it with representative families. M4 closes the loop: final runtime helper ownership, governance/docs alignment, and release merge.

## Scope (in scope)

1. **Decide and implement proposal-runtime ownership.**
   - Determine whether `createProposalRuntime` is public SDK functionality or host implementation.
   - If public: move to `src/sdk/runtime/proposalRuntime.ts` and update consumers.
   - If host-only: expose only `ProposalRuntime` types from SDK and keep `createProposalRuntime` behind a host adapter.

2. **Split `createExtensionContext()` into pure SDK contract plus host wiring.**
   - SDK owns a pure context contract.
   - Host wiring (DOM, localStorage-backed settings, console behavior, default services, lifecycle cleanup) lives in a host factory.

3. **Classify and replace remaining video-editor deep imports.**
   - Audit `config/governance/video-editor-sdk-import-allowlist.json`.
   - Label each as `author-facing`, `host-facing`, or `internal`.
   - Replace author-facing imports with `@reigh/editor-sdk` or scoped SDK modules.
   - Document host-only/internal entries with owner, rationale, and removal condition.

4. **Update contract registry and governance mapping.**
   - Update `config/contracts/registry.json` so `src/sdk/index.ts` is the extension SDK contract.
   - Reclassify `src/tools/video-editor/index.ts` as host/video-editor public API.
   - Ensure `npm run check:contracts` and `npm run check:contract-surface-map` pass.

5. **Update compatibility docs and readiness docs.**
   - Update `docs/governance/contracts/compatibility-shims.md` with remaining host-only exceptions.
   - Update `docs/extensions/phase4-readiness.md` and `docs/extensions/foundation-closure-assessment.md` to reflect family maturity and adapter registry.
   - Ensure docs do not overstate Phase 4 runtime support.

6. **Maintain and re-run the packagability smoke.**
   - Ensure the external SDK-consumer package fixture added in M0 still passes.
   - Add a second smoke that imports representative `src/sdk/families/*` modules directly.
   - Ensure `npm run quality:check` includes the smoke.

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
- Remaining allowlist entries must be explicitly host-only and documented.
- Packagability is enforced from M0 onward and maintained through M4.

## Open questions

- How many existing author-facing deep imports require real replacements versus allowlist documentation?
- Will moving `proposal-runtime.ts` implementation into the SDK pull in additional video-editor internals?

## Constraints

- Preserve runtime behavior for extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check`, `npm run test:readiness`, `npm run test:extensions`, and family conformance checks must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] Proposal runtime ownership is decided and implemented.
- [ ] `createExtensionContext()` is split into SDK contract and host factory.
- [ ] All author-facing deep imports from `src/tools/video-editor/**` are replaced.
- [ ] Remaining allowlist entries are classified as host-only/internal with owner/rationale/removal condition.
- [ ] Contract registry recognizes `src/sdk/index.ts` as the extension SDK boundary.
- [ ] Docs match the new boundary and do not overstate Phase 4 runtime support.
- [ ] External SDK-consumer package fixture and family module direct-import smoke pass.
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

- Splitting the SDK barrel further (M2).
- Adding new extension families or runtime features.
- Fixing pre-existing TypeScript errors in host-only video-editor internals.
- Implementing dynamic extension loading, marketplace, or sandboxing.
