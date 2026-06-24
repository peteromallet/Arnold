# M3 - Settings Runtime Write-Through

## Outcome

Finish the repository-first settings runtime contract: extension runtime `settings.set()` must write through to provider-backed storage on set, preserve compatibility where needed, surface persistence failures, and stay coherent with manager-visible settings snapshots.

## Context

The previous M3 settings milestone failed to publish its product-code implementation. Later manager work made settings look healthier, but the runtime contract remains incomplete: manager saves are provider-backed, while extension runtime `settings.set()` is still local-first and provider persistence happens late.

## Scope

- Update `createExtensionSettingsService` so `settings.set()` writes provider-backed snapshots on set.
- Preserve synchronous local runtime semantics for extension callers while making persistence explicit and testable.
- Add diagnostics or error reporting for provider write failures without breaking editor continuity.
- Retain localStorage compatibility/migration behavior where still needed, but repository snapshots must be canonical when a repository is available.
- Add tests for provider write-through, localStorage fallback, failure diagnostics, dispose safety, and manager/runtime coherence.
- Update the contract ledger with settings runtime evidence.

## Done Criteria

- A test fails if `settings.set()` only writes localStorage and waits for dispose to persist provider state.
- Runtime changes are visible through the provider-backed repository/manager snapshot path.
- Provider write failure creates a visible diagnostic or documented failure signal.
- No stale dispose writes can overwrite newer repository state.
- Contract ledger marks repository-first settings runtime satisfied with exact tests and paths.

## Touchpoints

- `src/sdk/extensionSettingsService.ts`
- `src/sdk/extensionSettingsService.test.ts`
- `src/tools/video-editor/runtime/extensionSettings.ts`
- `src/tools/video-editor/runtime/extensionSettings.test.ts`
- `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx`
- `docs/extensions/foundation-contract-ledger.md`

## Anti-Scope

- Do not redesign the Extension Manager UI.
- Do not remove localStorage compatibility unless tests prove it is no longer needed.
- Do not add marketplace/sandbox/security work.

