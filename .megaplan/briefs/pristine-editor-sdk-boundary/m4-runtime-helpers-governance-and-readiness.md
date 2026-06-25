# M4 — Runtime Helpers, Governance, and Readiness

## Outcome

Proposal-runtime ownership is decided and implemented. `createExtensionContext()` is split into a pure SDK contract plus host wiring. Remaining author-facing deep imports are replaced. Contract governance recognizes `src/sdk/index.ts` as the extension SDK boundary. Docs and readiness checks reflect the new boundary, family maturity model, and adapter architecture. The SDK passes all release gates and is merged to `main`.

## Background

M0 made the SDK dependency-clean and externally compilable. M1 defined the family maturity model. M2a/M2b split the SDK. M3 built the host adapter registry skeleton and proved it with at least one real family adapter. M4 closes the loop: final runtime helper ownership, governance/docs alignment, and release merge.

## Scope (in scope)

1. **Decide and implement proposal-runtime ownership.**
   - Determine whether `createProposalRuntime` is public SDK functionality or host implementation.
   - Use this decision rule:
     - If it depends on DOM/browser globals, React/provider wiring, DataProvider, timeline contexts, localStorage, console wiring, host diagnostics, editor services, or stateful side effects beyond pure data construction, it is host-only.
     - If public authors only need its shape, expose `ProposalRuntime` and related portable types from the SDK and keep `createProposalRuntime()` behind a host adapter/factory.
     - Move implementation into `src/sdk/runtime/proposalRuntime.ts` only if it is pure, package-evaluable, and passes the external SDK runtime smoke without host shims.
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
   - Add a single `expiration` field to every remaining entry: `"M4"` for temporary entries due in this milestone, a later milestone only if explicitly re-approved in notes, or `"permanent"` for true host boundaries with rationale.
   - Release mode fails if an entry lacks `expiration`, has both old-style deadline/permanent fields, or has expired without re-approval.

4. **Update contract registry and governance mapping.**
   - Update `config/contracts/registry.json` so `src/sdk/index.ts` is the extension SDK contract.
   - Reclassify `src/tools/video-editor/index.ts` as host/video-editor public API.
   - Ensure `npm run check:contracts` and `npm run check:contract-surface-map` pass.

5. **Update compatibility docs and readiness docs.**
   - Update `docs/governance/contracts/compatibility-shims.md` with remaining host-only exceptions.
   - Update `docs/extensions/phase4-readiness.md` and `docs/extensions/foundation-closure-assessment.md` to reflect family maturity and adapter registry.
   - Ensure docs do not overstate Phase 4 runtime support.
   - Generate any family maturity tables or checklist blocks in author-facing docs from `config/extensions/family-maturity.json` where practical.
   - Add a lightweight `docs-maturity-sync` check that compares named family support claims in these docs against generated `config/extensions/family-maturity.json`; fail release mode if docs either overstate or understate the registry for named families.
   - Add `docs/extensions/ADDING_A_FAMILY.md` with the canonical checklist: one SDK family module, one host adapter, one conformance report, examples, tests, and the required maturity registry row.

6. **Maintain and re-run the external SDK import validator.**
   - Ensure the external SDK import validator added in M0 still passes.
   - Add a second smoke that imports representative `src/sdk/families/*` modules directly.
   - Ensure both smoke fixtures also evaluate the imported SDK entrypoints at runtime, not just compile them.
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
- Temporary allowlist entries must expire; keeping one past its target requires explicit re-approval and a new `expiration`.
- Packagability is enforced from M0 onward and maintained through M4.
- Docs may only describe support levels that are backed by the canonical family maturity registry.
- Proposal runtime implementation belongs in the SDK only if it is genuinely pure and package-evaluable.

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
- [ ] Remaining allowlist entries are classified as host-only/internal with owner/rationale/removal condition and `expiration`.
- [ ] Expired temporary allowlist entries are removed or explicitly re-approved with a new `expiration`.
- [ ] Contract registry recognizes `src/sdk/index.ts` as the extension SDK boundary.
- [ ] Docs match the new boundary and do not overstate Phase 4 runtime support.
- [ ] Docs maturity sync check passes against generated `family-maturity.json`.
- [ ] `docs/extensions/ADDING_A_FAMILY.md` documents the canonical family checklist.
- [ ] External SDK-consumer package fixture and family module direct-import smoke compile and evaluate at runtime.
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
- `docs/extensions/ADDING_A_FAMILY.md` (new)

## Anti-scope (not in this milestone)

- Splitting the SDK barrel further (M2a/M2b).
- Adding new extension families or runtime features.
- Fixing pre-existing TypeScript errors in host-only video-editor internals.
- Implementing dynamic extension loading, marketplace, or sandboxing.
