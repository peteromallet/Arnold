# M4: Diagnostics Reporter, SchemaForm, And Lifecycle

## Outcome

Add the host-owned primitives needed before manager UI and future contribution families: scoped extension-authored diagnostics, a safe V1 SchemaForm, and deterministic lifecycle cleanup for disable/unload/re-enable.

## Scope

In:

- Add a dedicated extension-authored diagnostics source.
- Add scoped reporter factory that pins `source` and `extensionId` so extensions cannot impersonate host diagnostics.
- Add diagnostic bounds, per-extension capacity, contribution scoping, and cleanup by extension ID.
- Add `SchemaForm` V1 for settings and future parameterized families.
- Support primitive schema fields: string, number/integer, boolean, enum/select, color, defaults, required, and common constraints such as min/max/pattern where practical.
- Add per-field Ajv validation mapping and accessible error behavior.
- Define lifecycle cleanup contract:
  - forced React unmount
  - command/keybinding rebuild or unregister
  - diagnostics cleanup
  - reporter release
  - error-boundary reset
- Add tests for disable/unload/re-enable cleanup.

Out:

- Manager UI.
- Custom SchemaForm widget marketplace.
- Arrays, `oneOf`/`anyOf`/`allOf`, `$ref`, conditional visibility, file upload, rich text, and custom layouts unless a minimal fallback is needed.
- Public effects/transitions/clip types/keyframes/agent/live families.

## Locked Decisions

- Extensions never receive a raw host diagnostic reporter.
- Extension-authored diagnostics always use the dedicated extension-authored source.
- SchemaForm blocks saving invalid overrides rather than letting one invalid field corrupt all settings.
- Unsupported schema shapes render explicit diagnostics/fallbacks, not silent omissions.
- Lifecycle cleanup is a contract, not just an after-the-fact test list.

## Open Questions

- Exact diagnostic capacity limits and eviction behavior.
- Whether diagnostic source range should be first-class in V1.
- Whether arrays get read-only JSON fallback or unsupported placeholder in V1.
- Exact color input implementation.
- Whether command/keybinding cleanup should rebuild whole registries or add per-command unregister APIs.

## Constraints

- Do not let extension diagnostics spoof `render`, `provider`, or other host-owned sources.
- Do not allow unbounded diagnostics growth.
- Do not let settings edits save partially invalid override objects.
- Do not add custom SchemaForm widget extension points yet.
- Do not build manager UI in this milestone.

## Done Criteria

- Scoped reporter factory pins source and extension ID.
- Store can remove all diagnostics for an extension ID.
- Store enforces deterministic capacity bounds.
- Extension-authored diagnostics include stable code, severity, extension ID, optional contribution ID, and optional source range.
- SchemaForm maps labels/descriptions/errors to accessible attributes, including `aria-invalid`, `aria-required`, and `aria-describedby`.
- Save-with-errors focuses first invalid field or an error summary.
- Disable/unload removes surfaces, commands, keybindings, diagnostics, and settings-derived UI state without stale entries.
- Re-enable restores contributions deterministically.
- Re-enabling a crashed extension resets the render boundary and attempts fresh render.

## Touchpoints

- `src/tools/video-editor/runtime/diagnostics.ts`
- `src/tools/video-editor/hooks/useVideoEditorDiagnostics.ts`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/ExtensionRenderBoundary.tsx`
- `src/tools/video-editor/runtime/extensionSettings.ts`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/components/DiagnosticsPanel.tsx`
- shared UI primitives under `src/shared/components/ui/*`
- command/keybinding hooks and tests
- `src/tools/video-editor/extension.ts`
- `docs/extensions/authoring.md`
- `docs/extensions/compatibility.md`

## Required Tests

- Diagnostics: extension reporter cannot spoof host sources.
- Diagnostics: capacity bounds and oldest-first eviction/rejection.
- Diagnostics: remove by extension ID on disable/unload.
- SchemaForm: primitive fields render and validate.
- SchemaForm: invalid field blocks save without corrupting other overrides.
- SchemaForm accessibility: labels, descriptions, required fields, errors, focus behavior.
- Lifecycle: disable/unload/re-enable removes and restores surfaces, commands, keybindings, diagnostics.
- Error boundary: re-enable after crash resets failed extension UI.
