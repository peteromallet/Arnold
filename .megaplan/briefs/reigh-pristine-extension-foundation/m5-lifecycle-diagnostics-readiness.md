# M5: Lifecycle, Diagnostics, Inventory, And Readiness

## Outcome

Close the remaining foundation promises and promote readiness from narrative blocker list to objective gate: lifecycle re-enable resets crashed contribution boundaries, diagnostics provenance is host-owned, manager inventory semantics are truthful, non-active packages remain inspectable, trust/security and foundation contracts are documented, and readiness rows point at executable evidence.

## Scope

In scope:

- Add lifecycle-owned extension recovery keys and pass them into all production contribution error boundaries.
- Increment recovery keys on enable/re-enable and explicit retry-after-failure without infinite retry loops or excessive remounts.
- Align lifecycle-local diagnostics reporter with SDK contract: extensions cannot provide host-owned `extensionId` or `source`; host pins both.
- Keep collection sync source override as defense in depth and test cleanup on disable/unload.
- Reconcile diagnostics readiness across compatibility matrix, registry/docs, SDK contract, implementation, and readiness gate.
- Decide and implement direct-extension manager inventory semantics: either truthful exclusion copy or synthesized package-state inventory.
- Derive contribution summaries from package/manifest metadata where possible so disabled/invalid/settings-error/runtime-error packages remain inspectable.
- Add `docs/extensions/trust-and-security.md`.
- Add `docs/extensions/foundation-contracts.md` mapping canonical paths for proposals, settings, diagnostics, lifecycle recovery, manager inventory, render planning, and trust.
- Convert `docs/extensions/phase4-readiness.md` into structured gate rows with ID, category, owner, status, test anchor, code anchor, and objective pass condition.
- Add or document a repeatable readiness verification entrypoint; rows marked cleared must point at passing checks.
- Add browser/layout acceptance coverage for the extension activity region and manager in populated, empty, error, and repaired-settings states across default desktop, condensed, and mobile-sized layouts.

Out of scope:

- Do not build marketplace/install/update flows.
- Do not build sandbox/permission broker.
- Do not implement full Phase 4 contribution families.
- Do not publish `@reigh/editor-sdk`.
- Do not chase purely aesthetic polish unless it affects comprehension, layout, or confidence.

## Locked Decisions

- Current trusted/unsandboxed posture is acceptable only if explicit and documented.
- Declarative permissions remain documentation/UX only until a sandbox/permission broker exists.
- Readiness cannot be cleared by prose alone.
- Direct-extension inventory must be truthful even if it stays out of managed package scope.

## Open Questions To Resolve

- Exact recovery key ownership location: lifecycle host, runtime provider, or a small dedicated recovery registry.
- Exact diagnostic action/remediation vocabulary, e.g. retry, open settings, disable extension, view affected contribution.
- Exact manager empty-state copy if direct extensions remain unmanaged.
- Exact readiness verification command or test suite index.

## Constraints

- Do not allow extension-authored diagnostics to spoof host-owned source/provenance.
- Do not break existing lifecycle cleanup/disposal semantics.
- Do not imply sandbox enforcement that does not exist.
- Keep docs aligned with code and tests; no readiness row should clear without evidence.

## Done Criteria

- Disable/re-enable after a throwing contribution resets the boundary and attempts fresh render.
- All production contribution boundaries receive lifecycle-owned recovery keys.
- Diagnostics reporter cannot spoof host sources; cleanup removes diagnostics on disable/unload.
- Manager inventory behavior is tested for chosen direct-extension semantics.
- Non-active packages retain useful contribution summaries when metadata permits.
- `docs/extensions/trust-and-security.md` exists and is referenced by readiness.
- `docs/extensions/foundation-contracts.md` exists and names canonical contracts.
- `docs/extensions/phase4-readiness.md` is structured and says whether Phase 4 remains blocked or is cleared, with test/code anchors.
- A repeatable verification command/test index backs readiness rows.
- Browser/layout checks cover key activity-region and manager states.

## Touchpoints

- `src/tools/video-editor/runtime/ContributionErrorBoundary.tsx`
- Production contribution boundary call sites in editor shell/runtime provider.
- `src/tools/video-editor/runtime/extensionLifecycle.ts`
- `src/tools/video-editor/runtime/diagnosticCollectionSync.ts`
- `src/sdk/index.ts`
- `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts`
- `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx`
- `docs/extensions/phase4-readiness.md`
- `docs/extensions/trust-and-security.md`
- `docs/extensions/foundation-contracts.md`
- Lifecycle, diagnostics, manager inventory, readiness, and browser/layout tests.

## Anti-Scope

- No marketplace/discovery/install/update.
- No sandbox/permission broker.
- No full extensibility family build.
- No broad docs rewrite unrelated to readiness/trust/contracts.
