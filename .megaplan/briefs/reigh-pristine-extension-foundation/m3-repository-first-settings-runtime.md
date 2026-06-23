# M3: Repository-First Settings Runtime

## Outcome

Make provider-backed settings the canonical source of truth for extension runtime code. Manager/provider-saved settings must be what extensions see through `settings.get()` after refresh, and extension writes through `settings.set()` must write through to the provider instead of disappearing into localStorage.

## Scope

In scope:

- Change `createExtensionSettingsService` semantics so repository snapshots outrank localStorage whenever a repository/provider context exists.
- Inject the loaded settings snapshot or repository into `createExtensionContext` during extension activation.
- Make `settings.set()` write through to the provider-backed repository when available.
- Prevent dispose or localStorage fallback from overwriting newer provider-backed manager saves with stale values.
- Define and implement localStorage compatibility: migration, reseeding, clearing, or fallback only when provider context is unavailable.
- Add settings generation/refresh logic so settings changes rebuild extension contexts even if manifest objects are unchanged.
- Add tests for manager save -> provider -> refresh -> extension `settings.get()`, extension `settings.set()` -> provider -> manager visibility, and stale localStorage safety.

Out of scope:

- Do not replace manager raw settings UI yet.
- Do not solve unsupported schema rendering yet except as needed for runtime value handling.
- Do not remove localStorage fallback entirely unless tests prove it is unused and safe to remove.

## Locked Decisions

- Provider-backed `ExtensionStateRepository`/settings snapshot is canonical when available.
- localStorage is compatibility/offline cache only.
- Manager SchemaForm work must not start before this milestone settles runtime settings ownership.

## Open Questions To Resolve

- Exact migration policy for existing localStorage values when provider snapshots are present.
- Whether `settings.set()` needs sync-looking semantics with async provider writes, and how failures surface.
- How settings generation keys interact with existing extension loader refresh flow.

## Constraints

- Preserve standalone/direct-extension compatibility where no repository exists.
- Avoid data loss when both localStorage and provider snapshots contain values.
- Avoid making extension activation promise-based unless the existing runtime architecture already supports it safely.
- Keep changes scoped to settings ownership and runtime visibility.

## Done Criteria

- `settings.get()` sees provider-backed effective values after manager/provider save and refresh.
- `settings.set()` writes through to provider-backed storage when available.
- localStorage no longer outranks provider snapshots in repository-backed contexts.
- Stale localStorage/dispose cannot overwrite newer provider-backed settings.
- Settings generation refresh rebuilds extension contexts when settings change.
- Tests cover repository-backed, localStorage-only compatibility, and conflict/migration cases.

## Touchpoints

- `src/sdk/extensionSettingsService.ts`
- `src/sdk/index.ts`
- `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/data/DataProvider.ts`
- Settings service/runtime tests.

## Anti-Scope

- No manager UI redesign.
- No full schema repair UX.
- No marketplace/install/update.
- No broad SDK cleanup beyond settings contract changes.

