# M5: Extension Manager And Phase 4 Readiness

## Outcome

Expose the foundation through a local extension manager and produce the gate that must pass before public contribution-family work begins. Users should be able to inspect already-loaded packages, enable/disable them, edit settings, see scoped diagnostics and trust warnings, and reload without losing persisted state.

## Scope

In:

- Build host-owned extension manager panel/drawer from loader package-state data. UI copy should say "loaded packages" or "package states," not "installed extensions."
- List loaded, disabled, invalid, incompatible, and duplicate packages.
- Add explicit package status/reason data so disabled, invalid, incompatible, duplicate, and settings-resolution failure do not collapse into an ambiguous `loaded: false` UI.
- Add enable/disable controls that persist and trigger runtime re-resolution without page refresh.
- Add settings editor backed by SchemaForm from M4.
- Add per-package diagnostic badges and inline scoped diagnostics.
- Add manager loading, empty, no-settings, save-in-flight, and error states.
- Add manager error boundary with retry.
- Add trust warning for every package: extensions are trusted, unsandboxed code and manifest permissions are not enforced at runtime.
- Produce Phase 4 readiness artifact covering:
  - render planner extension participation contract
  - trust/sandbox decision
  - per-family promotion checklist
  - roadmap/ticket reconciliation

Out:

- Marketplace/discovery/catalog/search/install-from-URL/update/dependency graph.
- Public creative contribution families.
- Process sidecars, shaders, live data, agent tools, effects/transitions/clip types.
- Timeline overlay contributions unless split into a later product/family milestone.
- Full SDK package publishing unless explicitly split out after Phase 2 contract stability.

## Locked Decisions

- Manager manages packages already loaded by the host only.
- Disabled packages remain inspectable.
- Manager must distinguish disabled-by-user from failed-to-load/invalid/incompatible/duplicate where possible.
- Trust warnings are first-class UI, not just docs.
- Phase 4 does not begin until readiness gate is written and accepted.

## Open Questions

- Exact manager placement in editor chrome.
- Whether manager settings editor should include raw JSON escape hatch for unsupported schemas.
- Whether Phase 4 readiness should update roadmap/tickets directly or produce a separate reconciliation doc first.

## Constraints

- Do not make manager a marketplace.
- Do not expose install/update/delete flows.
- Do not imply disabled packages are uninstalled.
- Do not hide invalid/incompatible packages; they must remain inspectable with diagnostics.
- Do not start implementing Phase 4 families in this milestone.

## Done Criteria

- Manager lists all loaded package states with diagnostic counts and explicit status/reason.
- Manager has empty/loading/error/no-settings/save-in-flight states.
- Enable/disable persists and contributions disappear/reappear without refresh.
- Settings edit/save/reload works through SchemaForm and provider persistence.
- Per-package diagnostics are visible and scoped.
- Trust warning is visible and explicit.
- Manager itself does not crash on invalid metadata.
- No marketplace/discovery/install/update affordances exist.
- Phase 4 readiness artifact exists and names blockers before any deeper family starts.

## Touchpoints

- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionStateRepository.ts`
- `src/tools/video-editor/runtime/extensionSettings.ts`
- `src/tools/video-editor/runtime/diagnostics.ts`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/components/*`
- `src/tools/video-editor/components/DiagnosticsPanel.tsx`
- SchemaForm files from M4
- `src/tools/video-editor/runtime/contributionFamilies.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `docs/extensions/reigh-extension-layer-foundation-plan.md`
- `docs/extensions/reigh-extension-layer-roadmap-v2.md`
- `docs/extensions/reigh-extension-layer-tickets.md`
- `docs/extensions/compatibility.md`
- `docs/extensions/authoring.md`
- `tests/e2e/video-editor-*.spec.ts`

## Required Tests

- Manager renders package states: loaded, disabled, invalid, incompatible, duplicate.
- Enable/disable persists and re-resolves runtime without refresh.
- Settings editor saves and reloads.
- No-settings package shows no-settings state.
- Per-package diagnostics badge and details update.
- Manager error boundary catches bad metadata/render problems.
- Trust warning appears.
- Negative: no marketplace/discovery/install/update UI appears.
- Phase 4 readiness doc/checklist exists and references render planner/trust/family promotion gates.
