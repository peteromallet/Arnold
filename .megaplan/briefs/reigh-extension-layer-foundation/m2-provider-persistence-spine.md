# M2: Provider Persistence Spine

## Outcome

Make extension enablement and settings durable across supported providers without making the existing extension loader promise-based. Supabase and browser-local providers should only claim extension persistence support after repository factories and conformance tests prove it.

## Scope

In:

- Define provider-owned repository factory contracts for:
  - extension state
  - extension settings
  - command proposal storage hooks needed by M3
- Keep `ExtensionStateRepository` synchronous for the loader by adding a cache repository over async stores.
- Add an async store/cache hydration strategy for Supabase and browser-local persistence.
- Add Supabase schema/RLS design and migrations for extension install state, enabled flags, settings overrides, schema/version metadata, and proposal storage foundation.
- Add browser-local persistence: localStorage can remain for small enabled/settings state; proposal-sized payloads should use IndexedDB or another structured async store.
- Add provider conformance tests for supported and unsupported providers.
- Update provider capability flags so support maps to repository factories, not static aspirations.
- Define migration/version semantics for settings overrides and saved extension state.

Out:

- Agent `proposal_policy` request/response wiring; M3 owns that.
- Manager UI.
- Full extension update/install/uninstall flow.
- Multi-user/project-shared semantics beyond current single-user ownership.
- Automatic offline merge. Fail-closed diagnostics are acceptable for the first version.

## Locked Decisions

- Do not make `ExtensionLoader.load()` promise-based unless the cache/store adapter fails.
- Use provider-owned repository factories rather than many direct extension methods on `DataProvider`.
- Under the current schema, extension state/settings/proposals are per-user by timeline ownership.
- Provider capability flags must be earned by conformance tests.
- Unsupported providers must emit normalized diagnostics instead of silently no-oping.

## Open Questions

- Exact factory shape: separate factories for state/settings/proposals or one extension persistence service factory?
- Exact table split: one extension state table versus separate settings/proposal tables.
- Whether Astrid bridge should support this now or remain explicitly unsupported.
- Whether browser-local enabled/settings stays localStorage-compatible while proposals use IndexedDB.
- How much of proposal storage schema should land now versus in M3.

## Constraints

- RLS must prevent cross-user/timeline access.
- Cleanup/expiry jobs must account for service-role or security-definer behavior.
- Repository hydration failure must degrade with diagnostics, not partial support.
- Existing no-extension behavior must remain unchanged.
- Do not introduce marketplace install/update semantics.

## Done Criteria

- Provider-owned repository factory contracts exist and are documented.
- Cache-backed repository lets the loader remain synchronous while supported providers hydrate from async stores.
- Supabase migration/RLS design and implementation exist for extension state/settings and proposal storage foundation.
- Browser-local persistence survives reload.
- Supabase and browser-local only report `extensionState`/`extensionSettings` support after conformance tests pass.
- Unsupported providers report stable `provider_capability_*_unsupported` diagnostics.
- Settings schema/version changes have a defined migration/fallback behavior.
- Corrupt persisted state fails closed with diagnostics.

## Touchpoints

- `src/tools/video-editor/runtime/extensionStateRepository.ts`
- `src/tools/video-editor/runtime/extensionSettings.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/data/DataProvider.ts`
- `src/tools/video-editor/data/SupabaseDataProvider.ts`
- `src/tools/video-editor/data/AstridBridgeDataProvider.ts`
- `src/tools/video-editor/testing/InMemoryDataProvider.ts`
- `src/tools/video-editor/data/*Provider.test.ts`
- `src/tools/video-editor/runtime/*test.ts`
- `supabase/migrations/*`
- `src/integrations/supabase/databasePublicTypes.ts`
- `docs/extensions/loading.md`
- `docs/extensions/compatibility.md`

## Required Tests

- Shared provider conformance suite for supported providers.
- Unsupported provider diagnostics tests.
- Supabase RLS/repository tests for user/timeline isolation.
- Browser-local reload persistence tests.
- Corrupt state fallback tests.
- Async hydration failure diagnostics tests.
