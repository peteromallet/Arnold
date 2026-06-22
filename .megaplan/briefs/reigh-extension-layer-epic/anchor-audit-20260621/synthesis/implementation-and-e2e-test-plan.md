# Reigh Extension Layer Implementation And E2E Test Plan

Date: 2026-06-21
Epic: `reigh-extension-layer-epic`
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

## Purpose

This document turns the anchor audit into an implementation plan that also proves the result end to end. The goal is not just to add extension-looking APIs. The goal is to prove that a developer can author, package, load, use, disable, and diagnose a real extension through public surfaces without deep imports or source-tree edits.

The completion bar is: an extension package created outside the video editor core can contribute UI, commands, timeline proposals, diagnostics, effects/transitions/clip types where supported, render capability metadata, and settings; then automated tests exercise those contributions through the same public browser/provider APIs that an embedder would use.

## Non-Negotiable Acceptance Criteria

- No feature counts as implemented until it is exercised from a public SDK entrypoint.
- No contribution family counts as extensible until a test extension can register it without importing from internal paths.
- No runtime behavior counts as safe until there is a negative test for invalid, disabled, stale, or conflicting extension state.
- No UI surface counts as available until a browser-level test proves a user can see or interact with it.
- No render/export behavior counts as supported until the render planner can explain support, blockers, and required artifacts for extension-provided content.
- No public contract counts as stable until `config/contracts/registry.json` and import-boundary checks include it.

## Implementation Slices

### Slice 1: Public Extension Runtime Injection

Goal: make the existing slot/dialog/panel surface reachable.

Implement:

- Add a public extension entrypoint, for example `src/tools/video-editor/extension.ts`.
- Export `VideoEditorExtensionConfig`, `VideoEditorExtensionRuntimeConfig`, slot/dialog/panel/inspector descriptor types, and a `defineExtension()` helper.
- Add `extensions?: VideoEditorExtensionConfig | VideoEditorExtensionConfig[]` to:
  - `VideoEditorProvider`
  - `EditorRuntimeProvider`
  - `BrowserVideoEditorProvider`
  - public mount helpers if they bypass those providers
- Resolve all supplied extensions into one runtime config with deterministic ordering.
- Preserve the empty default for callers that do not pass extensions.
- Update `config/contracts/registry.json` and import allowlists so extension consumers use only public entrypoints.

Required tests:

- Unit: resolving multiple extensions merges slots, dialogs, panels, and inspector sections deterministically.
- Unit: duplicate contribution IDs produce diagnostics instead of silent overwrite.
- Public contract: new extension exports are frozen.
- Import-boundary: test extension cannot import `runtime/extensionSurface.ts` directly.
- Browser acceptance: mount `BrowserVideoEditorProvider` with a test extension and assert the contributed toolbar/status/inspector UI renders.
- Negative browser acceptance: disabled extension contributes nothing.

### Slice 2: Package Manifest, Loader, State, And Settings

Goal: move from in-process config to packageable extensions.

Implement:

- Add `config/contracts/reigh-extension.schema.json`.
- Define `ExtensionManifest` with at least:
  - `id`
  - `name`
  - `version`
  - `apiVersion`
  - `description`
  - `contributes`
  - `permissions`
  - `settingsSchema`
  - `migrations`
- Add `ExtensionPackage` for bundled/test packages.
- Add `ExtensionLoader` that validates manifests and produces normalized extension configs.
- Add `ExtensionStateRepository` for enabled/disabled state, install state, version, and per-extension settings.
- Wire settings into the existing settings/provider layer where appropriate.

Required tests:

- Schema: valid manifest passes, missing `id`, bad semver, bad `apiVersion`, duplicate contribution IDs fail.
- Loader: bundled extension package loads into runtime config.
- Loader negative: incompatible `apiVersion` reports a diagnostic and does not mount.
- State: disabled package stays installed but does not contribute UI/commands/effects.
- Settings: extension default settings load, user overrides persist, invalid setting values are rejected with diagnostics.
- E2E: install fixture package, reload editor, assert extension remains enabled and settings persist.

### Slice 3: Diagnostics As A First-Class Contract

Goal: every extension failure is visible and testable.

Implement:

- Add public diagnostic types:
  - `Diagnostic`
  - `DiagnosticSeverity`
  - `DiagnosticSource`
  - `DiagnosticCode`
  - `DiagnosticReporter`
  - `DiagnosticCollection`
- Route these sources into the same diagnostics stream:
  - manifest validation
  - duplicate contribution IDs
  - command/keybinding conflicts
  - failed asset materialization
  - render blockers
  - extension runtime exceptions
  - incompatible API versions
- Add a diagnostics/status drawer or panel.
- Add extension APIs for reporting diagnostics from extension code.

Required tests:

- Unit: each diagnostic source reports a stable `code`, `severity`, `source`, and optional `extensionId`.
- Browser: failing extension renders a visible diagnostics entry.
- Browser: diagnostics panel can filter by extension.
- Negative: extension render exception does not blank the editor; fallback UI and diagnostic appear.
- Regression: existing generation asset/materialization diagnostics are surfaced through the same stream.

### Slice 4: Versioned Timeline Proposals

Goal: let agents and extensions mutate timelines safely.

Implement:

- Add public types:
  - `TimelinePatch`
  - `TimelineProposal`
  - `TimelineProposalResult`
  - `TimelineProposalPreview`
  - `TimelineProposalApplyResult`
- Include `baseVersion`/`expectedVersion` in proposal envelopes.
- Support validate, preview, apply, and reject.
- Wrap existing command/mutation code rather than creating a second mutation engine.
- Make AI agent destructive tools return proposals by default.
- Add review/apply UX for proposals.

Required tests:

- Unit: proposal preview does not mutate timeline.
- Unit: proposal apply writes with expected version.
- Unit: stale proposal rejects before mutation.
- Integration: extension command returns a proposal; user applies it; timeline changes.
- Integration: AI agent tool returns a proposal; user rejects it; timeline remains unchanged.
- Browser: proposal review UI shows before/after summary and apply/reject controls.

### Slice 5: Extension Commands, Keybindings, Menus, And Palette

Goal: make commands discoverable and conflict-safe.

Implement:

- Add `CommandContribution` with:
  - namespaced `id`
  - title/description
  - contexts
  - optional keybinding
  - optional menu placements
  - execute/validate/propose hooks
- Register extension commands into existing command runner.
- Add conflict diagnostics for duplicate IDs and keybindings.
- Wire command contributions into:
  - command palette
  - clip context menu
  - timeline context menu
  - inspector actions where relevant

Required tests:

- Unit: duplicate command IDs rejected.
- Unit: duplicate keybinding reports diagnostic and disables lower-priority binding.
- Unit: command execute can return a timeline proposal.
- Browser: contributed command appears in palette.
- Browser: contributed clip command appears only for matching clip context.
- Browser: pressing contributed keybinding triggers command or proposal review.

### Slice 6: Contribution Families

Goal: make each supported extension type explicit and tested.

Implement supported families deliberately. Do not imply support for families that are not wired.

Minimum recommended families:

- `surface`: slots, panels, dialogs, inspector sections.
- `command`: commands, keybindings, menus.
- `diagnostic`: diagnostic producers and panels.
- `clipType`: only if third-party clip types are intended now.
- `effect`: trusted component effects with parameter schema and render capability metadata.
- `transition`: dynamic transition registry if transitions stay in epic scope.
- `agentTool`: only after proposal review exists.
- `dataSource`: live-data bridges only if M11 stays in scope.

For each family:

- Add public contribution type.
- Add loader validation.
- Add runtime registration and unregister/dispose path.
- Add diagnostics for invalid registration.
- Add one positive and one negative E2E test.

Required tests:

- Surface E2E: extension adds toolbar button, status item, dialog, asset panel, inspector section.
- Command E2E: extension command appears, validates context, returns proposal, applies safely.
- Effect E2E: extension effect appears in UI, parameter schema renders, preview uses it, render planner accepts or blocks it with explanation.
- Transition E2E: extension transition appears in selector and renders in preview/export path, or the transition family is explicitly removed from epic scope.
- Clip type E2E: extension clip type can be inserted, inspected, rendered, serialized, and reloaded, or clip types are documented as trusted-only.
- Agent tool E2E: extension-provided tool appears in agent capabilities and returns a proposal, not direct mutation.

### Slice 7: Render Capability Planner

Goal: make export readiness explainable for extension content.

Implement:

- Add public render vocabulary:
  - `RenderCapability`
  - `CapabilityFinding`
  - `RenderBlocker`
  - `RenderMaterial`
  - `RenderArtifactManifest`
- Convert `renderRouter.ts` into a planner input rather than the sole source of truth.
- Require extension clip/effect/transition contributions to declare preview/export capabilities.
- Add pre-export readiness UI.
- If sidecars/local processes remain in scope, define `ProcessContribution` and a trusted local process runtime. If not, remove sidecar claims from acceptance criteria.

Required tests:

- Unit: planner accepts built-in media-only timeline.
- Unit: planner accepts extension content with declared export capability.
- Unit: planner blocks extension content with preview-only capability.
- Browser: export button shows actionable blocker for unsupported extension content.
- Integration: render pipeline receives `RenderArtifactManifest` for extension-provided render materials.

### Slice 8: Provider Parity And Persistence

Goal: ensure extensions behave the same across providers.

Implement:

- Add provider capability detection.
- Add conformance tests for:
  - Supabase provider
  - Astrid bridge provider
  - browser/in-memory provider
  - test provider
- Persist extension state/settings where the provider supports it.
- Separate missing event-log infrastructure from empty event-log state in diagnostics.

Required tests:

- Provider conformance: load/save timeline still works with extension metadata present.
- Provider conformance: extension settings persist or report unsupported capability explicitly.
- Provider conformance: timeline proposals use version conflict semantics consistently.
- Supabase negative: missing `timeline_events` reports degraded sync diagnostic, not silent empty history.
- Astrid bridge: asset materialization failure appears in diagnostics panel.

## Canonical Test Extension Fixtures

Create fixture packages under a stable location such as:

- `src/tools/video-editor/testing/extensions/basic-extension/`
- `src/tools/video-editor/testing/extensions/conflicting-extension/`
- `src/tools/video-editor/testing/extensions/incompatible-extension/`
- `src/tools/video-editor/testing/extensions/render-blocked-extension/`

`basic-extension` should contribute:

- a toolbar button
- a status item
- a dialog
- an inspector section
- a command palette command
- a clip context-menu command
- a diagnostic producer
- a timeline proposal command
- one settings field
- one render-capable contribution if effect/clip/transition support is in scope

`conflicting-extension` should intentionally duplicate:

- command ID
- keybinding
- contribution ID

`incompatible-extension` should use an unsupported `apiVersion`.

`render-blocked-extension` should declare preview-only render capability.

## E2E Test Matrix

| Area | User-level proof | Suggested test type |
| --- | --- | --- |
| Runtime injection | Public browser provider mounts extension UI | Playwright or browser acceptance |
| Package loading | Manifest package loads without internal imports | Unit + integration |
| State | Disable extension removes all contributions | Browser acceptance |
| Settings | User setting persists across reload | Browser acceptance |
| Diagnostics | Bad extension shows visible diagnostic | Browser acceptance |
| Commands | Palette and context-menu commands appear | Browser acceptance |
| Proposals | Extension command previews then applies timeline change | Integration + browser acceptance |
| Conflicts | Duplicate command/keybinding rejected with diagnostic | Unit + browser acceptance |
| Effects | Extension effect renders controls and preview | Browser acceptance |
| Transitions | Extension transition selectable and renderable | Browser acceptance |
| Clip types | Extension clip type inserts, inspects, serializes, reloads | Integration + browser acceptance |
| Render planner | Unsupported content blocks export with explanation | Unit + browser acceptance |
| Provider parity | Same fixture works across providers or reports unsupported capability | Integration |
| Public contracts | Exports are frozen and deep imports fail | Contract test |

## Required CI Gates

Add or update package scripts so CI has a single unambiguous extension gate. Example names:

- `npm run test -- src/tools/video-editor/extension`
- `npm run test -- src/tools/video-editor/testing/extensions`
- `npm run test -- src/tools/video-editor/__tests__/public-extension.acceptance.test.tsx`
- `npm run test -- src/tools/video-editor/__tests__/extension-provider-parity.test.ts`
- `npm run test -- src/tools/video-editor/__tests__/extension-render-planner.test.ts`
- `npm run check:video-editor-sdk-contracts`
- `npm run check:video-editor-sdk-imports`

The final epic gate should run:

1. Typecheck.
2. Unit tests for loader/runtime/contributions.
3. Provider parity tests.
4. Public browser/provider extension acceptance tests.
5. Render planner tests.
6. Contract export freeze.
7. Import-boundary checks.
8. Build.

## Definition Of Done

The epic can be called complete only when all of the following are true:

- A developer can author an extension from docs without touching `src/tools/video-editor` internals.
- A valid extension package can be loaded through public provider/browser APIs.
- The same package can be disabled and re-enabled without reload-time source edits.
- Invalid packages produce visible diagnostics and do not break the editor.
- Extension commands are discoverable and conflict-safe.
- Timeline mutations from extensions and agents go through proposal review or explicit apply semantics.
- Extension settings persist.
- Export readiness is explainable for extension-provided content.
- Public exports are frozen.
- Deep imports are rejected.
- At least one browser-level acceptance test proves the whole path: load package, render extension UI, run command, review proposal, apply timeline change, persist/reload, and see diagnostics.

## Recommended First Milestone

Start with a narrow vertical slice:

1. Public extension entrypoint.
2. `extensions` prop through public provider.
3. Basic extension fixture with one toolbar slot, one inspector section, one command, one diagnostic.
4. Browser acceptance test proving those contributions render from the public provider.
5. Contract/import checks updated.

Do not start package manager UI, shader work, sidecars, or marketplace behavior until this vertical slice is green. That slice proves the architectural spine; everything else can hang from it.
