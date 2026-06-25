# M2a — Core SDK Boundary Modules

## Outcome

`src/sdk/index.ts` is no longer a 6,000-line implementation file for core SDK concepts. Core SDK-owned contracts and helpers are split into scoped modules (ids, diagnostics, manifest, lifecycle, context, settings, packaging), and the public barrel re-exports them with compatible names. Family-specific extraction is deliberately deferred to M2b so this milestone stays realistically sized.

## Background

M0 removed video-editor imports and made the SDK externally compilable. M1 defined the canonical family maturity model. M2a creates the stable core module structure that family modules can depend on without creating circular imports or public type identity surprises.

## Scope (in scope)

1. **Snapshot the current SDK export and declaration surface.**
   - Run `npm run check:sdk-public-exports -- --release` and record the baseline.
   - Generate a declaration baseline with the repo's existing TypeScript toolchain (`tsc --emitDeclarationOnly` or an existing declaration build path). Do not add new dependencies.
   - Any approved public shape change must be recorded in the milestone notes with the exact export/type affected, the compatibility impact, and the approving owner.

2. **Split core SDK modules out of `src/sdk/index.ts`.**
   - Move clusters into scoped modules, preserving exported names:
     - `src/sdk/ids.ts`
     - `src/sdk/dispose.ts`
     - `src/sdk/diagnostics.ts`
     - `src/sdk/manifest.ts`
     - `src/sdk/manifestValidation.ts`
     - `src/sdk/lifecycle.ts`
     - `src/sdk/context.ts`
     - `src/sdk/chrome.ts`
     - `src/sdk/commands.ts`
     - `src/sdk/settings.ts`
     - `src/sdk/packaging.ts`
   - Use internal relative imports; do not import back through `src/sdk/index.ts`.

3. **Define the pure SDK extension context contract.**
   - Move the `ExtensionContext` interface and portable context-related types into `src/sdk/context.ts`.
   - Keep `createExtensionContext()` implementation in place until M4 unless it can move without pulling host wiring forward.
   - Any field that represents host wiring, DOM, provider services, storage, console behavior, timeline contexts, or React lifecycle must be an explicit host-provided capability or opaque type in the SDK contract.

4. **Reduce `src/sdk/index.ts` to a core barrel plus family-registry re-exports.**
   - Re-export the new core modules and the M1 family registry.
   - Keep family descriptor implementations in `src/sdk/index.ts` only as a temporary migration budget for M2b.
   - No new inline implementation should be added to `src/sdk/index.ts`.

5. **Add TypeScript identity assertions for core exports.**
   - Add a compile-time test that imports each moved public core type/value through `@reigh/editor-sdk` and through its canonical direct module path.
   - Assert mutual assignability for types and equivalent value importability for constants/helpers.
   - Wire the test into the same gate as the SDK public export check.

6. **Update contract registry and allowlist for core moves.**
   - Update `config/contracts/registry.json` for moved core module locations.
   - Ensure `config/governance/video-editor-sdk-import-allowlist.json` no longer contains SDK-internal entries.
   - Treat `config/governance/sdk-public-export-allowlist.json` as a shrinking migration budget: remove entries fixed by M0/M2a and document remaining entries with owner/removal condition.

## Locked decisions

- SDK modules may not import from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- Public exported names from `@reigh/editor-sdk` must remain compatible unless explicitly approved in the milestone notes.
- Public API approvals must name the affected export/type and the owner accepting the compatibility change.
- Internal SDK modules use relative imports, not barrel imports through `src/sdk/index.ts`.
- `ExtensionContext` is an SDK-owned contract; constructing a host-wired context remains host-owned.
- Allowlists are migration budgets, not permanent escape hatches.

## Open questions

- Will the core split cause TypeScript identity or inference regressions?
- Which context fields are truly portable contracts vs. host-provided capabilities?

## Constraints

- Preserve runtime behavior: extension loading, manifest validation, settings, diagnostics, proposal runtime, planner metadata, and video editor public entrypoints.
- `npm run quality:check` and `npm run test:readiness` must stay green.
- Do not install new dependencies.
- Do not alter profile/model selections in megaplan configs.
- Pre-push hooks require Docker; use the existing manual pristine-worktree merge workflow with `git push --no-verify` if needed.

## Done criteria

- [ ] Core SDK modules listed above exist and are imported by relative paths.
- [ ] `src/sdk/index.ts` is a small core barrel plus explicitly temporary family migration exports.
- [ ] The SDK-owned `ExtensionContext` contract exists in `src/sdk/context.ts` without host wiring.
- [ ] `src/sdk/**` has no imports from `src/tools/video-editor/**` or `@/tools/video-editor/**`.
- [ ] `npm run check:video-editor-sdk-imports` passes and a deliberate violation is caught.
- [ ] `npm run check:sdk-public-exports -- --release` passes.
- [ ] Core type-identity assertions pass for barrel and direct-module imports.
- [ ] Declaration output for moved core exports has no unapproved public shape changes.
- [ ] `npm run quality:check` passes.
- [ ] `npm run test:readiness` passes.

## Touchpoints

- `src/sdk/index.ts`
- New core `src/sdk/*` modules listed above
- `src/sdk/context.ts`
- `config/contracts/registry.json`
- `config/governance/video-editor-sdk-import-allowlist.json`
- `config/governance/sdk-public-export-allowlist.json`

## Anti-scope (not in this milestone)

- Extracting all family-specific modules (M2b).
- Refactoring `extensionSurface.ts` onto host adapters (M3).
- Deciding proposal-runtime ownership (M4).
- Governance/docs closure and final release merge (M4).
