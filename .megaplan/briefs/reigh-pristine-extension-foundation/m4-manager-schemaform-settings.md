# M4: Manager SchemaForm Settings

## Outcome

Make Extension Manager settings the canonical user-facing settings surface: schema defaults render for fresh packages, typed SchemaForm controls validate before save, provider-backed persistence reloads correctly, runtime settings remain coherent, legacy invalid snapshots repair deterministically, and unsupported schemas never become editable string inputs.

## Scope

In scope:

- Introduce a shared host-owned settings editor abstraction usable by Extension Manager and standalone settings surfaces.
- Replace manager raw key/value text inputs with SchemaForm-backed controls for supported schemas.
- Render schema defaults when no saved settings snapshot exists.
- Validate before save and focus/report invalid fields.
- Persist through provider-backed settings storage from M3.
- Reconcile legacy invalid settings with explicit states: repaired, needs review, and blocked/settings-error.
- Preserve repair metadata or diagnostics for dropped/unknown fields.
- Ensure non-object/corrupt snapshots surface `settings-error` without crashing manager.
- Preserve or reject unsupported schema markers at the adapter boundary: `$ref`, `oneOf`, `anyOf`, `allOf`, arrays, nested objects, and conditionals.
- Prove bidirectional coherence: manager writes are runtime-visible; extension writes flow back to manager.
- Add browser/layout coverage for populated, empty, error, and repaired-settings manager states where feasible.

Out of scope:

- Do not change repository-first runtime settings ownership except for integration fixes discovered while consuming M3.
- Do not build new settings-driven contribution families.
- Do not add marketplace/install/update.
- Do not make raw JSON editing the default happy path.

## Locked Decisions

- The shared editor should be the path future settings-driven families reuse.
- Field-level repair is preferred over blanket activation blocking where safe.
- Unsupported schema structures must become diagnostics/read-only blockers, not editable strings.

## Open Questions To Resolve

- Exact UI for repaired vs needs-review vs blocked settings.
- Exact recovery metadata location for dropped unknown fields.
- Whether the standalone settings panel should be replaced by the shared abstraction in the same PR or adapted after manager parity is proven.
- How to keep the manager dense and usable inside the Properties panel while surfacing repair/diagnostic detail.

## Constraints

- Do not silently lose legacy settings values.
- Do not write recovery metadata into settings values if that violates schema contracts.
- Keep trust warning/no-marketplace posture intact.
- Avoid card-in-card or cluttered nested panels in the manager UI.

## Done Criteria

- Fresh schema-backed packages show defaults in manager through SchemaForm.
- Invalid saves are blocked with visible field-level feedback.
- Saves persist through provider storage and reload correctly.
- Runtime `settings.get()` sees manager-saved values after refresh.
- Extension-written settings are visible in the manager after refresh/sync.
- Legacy invalid snapshots are repaired or surfaced deterministically with diagnostics.
- Unsupported schema constructs do not become editable text inputs.
- Browser/component tests cover manager settings happy path, invalid path, repair path, corruption path, and unsupported schema path.

## Touchpoints

- `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx`
- `src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx`
- `src/tools/video-editor/components/ExtensionSettings/SchemaForm.tsx`
- `src/tools/video-editor/runtime/extensionSettings.ts`
- `src/sdk/extensionSettingsService.ts`
- Manager, SchemaForm, settings repair, and browser tests.

## Anti-Scope

- No Phase 4 family implementation.
- No published SDK package.
- No marketplace/install/update.
- No broad visual redesign except what is required for clear settings states.

