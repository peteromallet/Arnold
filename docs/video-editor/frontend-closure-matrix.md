# Frontend Closure Matrix — M15 Extension Primitives

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Scope:** Every required public frontend primitive in the video editor extension surface layer. Maps each primitive to its host affordance, UI states, accessibility expectation, evidence, status, disposition, and contract-recheck row ID.

> **Supersedes:** This matrix replaces the previous `docs/video-editor/frontend-closure-checklist.md` (§ 2–3) with a structured classification of every public primitive. The old checklist's five-section governance assertion is preserved in `docs/video-editor/frontend-closure-checklist.md` as a transitional bridge satisfying `examples-governance.test.ts`.

---

## 1. Purpose

This matrix classifies every public frontend primitive that is part of the Reigh extension platform contract. Each row documents:

- **Primitive** — The component, surface, or host affordance name.
- **Host affordance** — Which `VideoEditorSlotName` slot or host registration path it occupies.
- **UI states** — How the primitive handles empty, loading, error, and disabled states.
- **Accessibility expectation** — Required ARIA roles, labels, live regions, and keyboard behavior.
- **Evidence** — Concrete test files, component files, or extension examples.
- **Status** — `pass` (evidence confirmed), `gap` (partial/incomplete), `blocked` (no credible evidence).
- **Disposition** — `supported` (V1-supported with evidence), `deferred` (explicitly deferred with absence-check or blocker evidence), `unsupported` (no V1 plan), `release-blocking` (blocks V1 release).
- **Contract-recheck** — Row ID(s) in [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md).

**Status and disposition definitions** are shared with the contract-recheck and supported/deferred matrices (SD1).

---

## 2. Matrix Columns

| Column | Description |
|---|---|
| **Primitive** | Component or surface name as referenced in code, docs, and tests. |
| **Host Affordance** | `VideoEditorSlotName` value (e.g. `'toolbar'`, `'inspectorPanel'`, `'codePanel'`), host registration path, or dialog/overlay descriptor. |
| **UI States** | Empty / Loading / Error / Disabled coverage. `■` = satisfied, `□` = gap, `—` = not applicable. |
| **Accessibility** | ARIA role, label, live region, keyboard expectations. |
| **Evidence** | Test file path(s), component file path, example extension reference. |
| **Status** | `pass` / `gap` / `blocked`. |
| **Disposition** | `supported` / `deferred` / `unsupported` / `release-blocking`. |
| **Contract-Recheck** | Row ID(s) from `extension-platform-contract-recheck.md`. |

---

## 3. Core Shell Primitives

### 3.1 TimelineEditorShellCore

- **Host affordance:** Root shell component wrapping all `VideoEditorSlotName` surfaces. Registered in the host app via `<TimelineEditorShellCore>`.
- **UI states:**
  - **Empty:** ■ Renders all reserved slots as inert placeholders when no extension contributes.
  - **Loading:** — Shell mounts synchronously; loading is per-slot.
  - **Error:** ■ `ContributionErrorBoundary` catches render errors per-slot with extension/contribution ID and "View diagnostics" action.
  - **Disabled:** — Shell itself is never disabled; individual slots use `InertReservedPlaceholder`.
- **Accessibility:** Shell container uses `role="region"` with `aria-label="Video editor"`. Each slot wrapper uses `data-video-editor-slot` attribute for testability.
- **Evidence:** `src/tools/video-editor/components/TimelineEditorShellCore.tsx` (1262 lines); `src/tools/video-editor/components/TimelineEditorShellCore.test.tsx` (679 lines).
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-013, CR:M1-002

### 3.2 ContributionErrorBoundary

- **Host affordance:** Wraps every slot renderer in `TimelineEditorShellCore.tsx`. Not an independent slot — a cross-cutting error containment layer.
- **UI states:**
  - **Empty:** — Not applicable.
  - **Loading:** — Not applicable.
  - **Error:** ■ Catches render throws, displays compact fallback with extension ID, contribution ID, and "View diagnostics" action.
  - **Disabled:** — Not applicable.
- **Accessibility:** Fallback uses `role="alert"` for screen-reader announcement. "View diagnostics" button is keyboard-accessible.
- **Evidence:** `src/tools/video-editor/components/TimelineEditorShellCore.tsx` (error boundary wrapper); `src/tools/video-editor/components/TimelineEditorShellCore.test.tsx`; documented in `docs/video-editor/frontend-closure-checklist.md` § 3.2.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M1-002, CR:M2-008

### 3.3 InertReservedPlaceholder

- **Host affordance:** Rendered for `RESERVED_SLOT_NAMES` (`codePanel`, `writingPanel`, `stagePanel`) when no extension contributes to the slot. Defined in `TimelineEditorShellCore.tsx`.
- **UI states:**
  - **Empty:** ■ Renders slot name + milestone label (e.g. "codePanel — M4").
  - **Loading:** — Not applicable.
  - **Error:** — Not applicable.
  - **Disabled:** ■ Uses `aria-hidden="true"`, `role="presentation"`, `tabIndex={-1}`. Non-interactive, keyboard-inert.
- **Accessibility:** `aria-hidden="true"`, `role="presentation"`, `tabIndex={-1}`. No focusable children. `data-video-editor-slot-inert="true"` attribute.
- **Evidence:** `src/tools/video-editor/components/TimelineEditorShellCore.tsx` (lines 111–128); `src/tools/video-editor/components/TimelineEditorShellCore.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-013

---

## 4. Active Host Surfaces (Supported)

### 4.1 Toolbar Surface

- **Host affordance:** `'toolbar'` slot. Extensions contribute toolbar items via `ExtensionContribution` with `kind: 'toolbar'`.
- **UI states:**
  - **Empty:** ■ Renders empty toolbar area when no toolbar contributions registered.
  - **Loading:** — Toolbar items render synchronously.
  - **Error:** ■ `ContributionErrorBoundary` wraps each toolbar item.
  - **Disabled:** — Toolbar slot itself is never disabled; individual items can be disabled via `when` predicates.
- **Accessibility:** Toolbar uses `role="toolbar"` with `aria-label="Editor toolbar"`. Individual buttons are keyboard-accessible (Tab, Enter/Space).
- **Evidence:** `src/examples/toolbar-example.ts`; `src/examples/toolbar-extension.ts`; `src/examples/hello-world-extension.ts`; registered via `src/tools/video-editor/runtime/extensionSurface.ts` slot map.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001, CR:M1-001, CR:M1-016

### 4.2 Inspector Panel / PropertiesPanel

- **Host affordance:** `'inspectorPanel'` slot. Extensions contribute inspector sections via `VideoEditorInspectorSectionDescriptor` (placement: `'before-default'` / `'after-default'`).
- **UI states:**
  - **Empty:** ■ Renders "No selection" placeholder when no clip/timeline is selected.
  - **Loading:** □ No explicit skeleton/spinner for inspector data loading; inspector mounts synchronously with current selection.
  - **Error:** ■ `ContributionErrorBoundary` wraps inspector sections.
  - **Disabled:** □ Disabled/empty inspector sections render without explicit inert placeholder; layout does not collapse.
- **Accessibility:** Inspector panel uses `role="complementary"` with `aria-label="Inspector"`. Section headers are keyboard-navigable.
- **Evidence:** `src/examples/inspector-example.ts`; `src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx`; `src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx`, `src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx`, `src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001, CR:M2-003, CR:S-021

### 4.3 Overlay Editor / Timeline Overlays

- **Host affordance:** Overlay contributions via `VideoEditorOverlayDescriptor`. Rendered in the preview/timeline area as ordered overlays.
- **UI states:**
  - **Empty:** ■ No overlays rendered when none registered.
  - **Loading:** — Overlays render synchronously with timeline data.
  - **Error:** ■ `ContributionErrorBoundary` wraps each overlay.
  - **Disabled:** — Overlays hidden via `when` predicates.
- **Accessibility:** Overlay container uses `role="region"` with `aria-label="Timeline overlay"`. Content within overlays should follow standard ARIA patterns.
- **Evidence:** `src/examples/overlay-example.ts`; `src/tools/video-editor/components/PreviewPanel/OverlayEditor.test.tsx`; `src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.test.tsx`, `src/tools/video-editor/components/TimelineEditor/WaveformOverlay.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001, CR:M2-003

### 4.4 Status Bar

- **Host affordance:** `'statusBar'` slot. Extensions contribute status bar items via `ExtensionContribution` with `kind: 'statusBar'`.
- **UI states:**
  - **Empty:** ■ Renders default status bar with host-owned status text when no extension contributes.
  - **Loading:** — Status text updates are synchronous.
  - **Error:** ■ Error status text renders via diagnostic integration.
  - **Disabled:** — Not applicable.
- **Accessibility:** Status bar uses `role="status"` with `aria-live="polite"` for dynamic updates.
- **Evidence:** `src/examples/status-surface-example.ts`; documented in `src/examples/surface-coverage.ts`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

### 4.5 Left Panel

- **Host affordance:** `'leftPanel'` slot. Reserved for extension-contributed side panels.
- **UI states:**
  - **Empty:** □ Layout handled by host shell; empty left panel collapses or shows minimal border.
  - **Loading:** — Panel content renders synchronously.
  - **Error:** ■ `ContributionErrorBoundary` wraps panel renderer.
  - **Disabled:** — Not applicable.
- **Accessibility:** Panel uses `role="complementary"` with `aria-label="Left panel"`.
- **Evidence:** Slot defined in `VideoEditorSlotName` union; registration via `src/tools/video-editor/runtime/extensionSurface.ts` slot map.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

### 4.6 Right Panel

- **Host affordance:** `'rightPanel'` slot. Reserved for extension-contributed side panels.
- **UI states:**
  - **Empty:** □ Layout handled by host shell; empty right panel collapses or shows minimal border.
  - **Loading:** — Panel content renders synchronously.
  - **Error:** ■ `ContributionErrorBoundary` wraps panel renderer.
  - **Disabled:** — Not applicable.
- **Accessibility:** Panel uses `role="complementary"` with `aria-label="Right panel"`.
- **Evidence:** Slot defined in `VideoEditorSlotName` union; registration via `src/tools/video-editor/runtime/extensionSurface.ts` slot map.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

### 4.7 Header

- **Host affordance:** `'header'` slot. Top bar area for extension-contributed header items.
- **UI states:**
  - **Empty:** □ Renders with minimal host chrome when no extension contributes.
  - **Loading:** — Header items render synchronously.
  - **Error:** ■ `ContributionErrorBoundary` wraps each header item.
  - **Disabled:** — Not applicable.
- **Accessibility:** Header uses `role="banner"` with `aria-label="Editor header"`.
- **Evidence:** Slot defined in `VideoEditorSlotName` union; registration via `src/tools/video-editor/runtime/extensionSurface.ts` slot map.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

### 4.8 Timeline Footer

- **Host affordance:** `'timelineFooter'` slot. Footer area below the timeline for extension-contributed controls.
- **UI states:**
  - **Empty:** ■ Host renders timeline without footer area when no extension contributes.
  - **Loading:** — Footer items render synchronously.
  - **Error:** ■ `ContributionErrorBoundary` wraps footer renderer.
  - **Disabled:** — Not applicable.
- **Accessibility:** Footer uses `role="contentinfo"` with `aria-label="Timeline footer"`.
- **Evidence:** Slot defined in `VideoEditorSlotName` union; registration via `src/tools/video-editor/runtime/extensionSurface.ts` slot map.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

### 4.9 Asset Panel

- **Host affordance:** `'assetPanel'` slot. Asset detail/inspector panel for extension-contributed asset metadata sections.
- **UI states:**
  - **Empty:** ■ Renders "No asset selected" placeholder when no asset is selected.
  - **Loading:** □ No explicit skeleton/spinner for asset data loading.
  - **Error:** ■ `ContributionErrorBoundary` wraps asset panel sections.
  - **Disabled:** — Not applicable.
- **Accessibility:** Asset panel uses `role="complementary"` with `aria-label="Asset details"`.
- **Evidence:** `src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx`; `AssetDetailSectionContribution` in SDK.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M6-001, CR:M6-002, CR:M6-012 (gap for frontend rendering)

### 4.10 Dialogs

- **Host affordance:** `'dialogs'` slot. Extension-contributed dialogs via `VideoEditorDialogDescriptor` (layer: `'modal'` / `'overlay'`).
- **UI states:**
  - **Empty:** ■ No dialogs rendered when none registered.
  - **Loading:** — Dialog content renders synchronously with trigger.
  - **Error:** ■ `ContributionErrorBoundary` wraps each dialog.
  - **Disabled:** — Dialogs hidden via `when` predicates.
- **Accessibility:** Modal dialogs use `role="dialog"` with `aria-modal="true"`, `aria-labelledby`, focus trap. Overlay dialogs use `role="dialog"` with `aria-label`.
- **Evidence:** Slot defined in `VideoEditorSlotName`; dialog host config in `src/tools/video-editor/runtime/extensionSurface.ts`; `ModalContainer` in shared components.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-001

---

## 5. Reserved / Canary Surfaces (Deferred to future milestones)

### 5.1 CodePanelCanary

- **Host affordance:** `'codePanel'` slot (M4 reserved). Rendered via `RESERVED_SLOT_CANARY` → `CodePanelCanary`.
- **UI states:**
  - **Empty:** ■ Canary renders demo source + diagnostic always; production empty state deferred to M4.
  - **Loading:** □ Production loading state (skeleton/spinner) deferred to M4; canary does not load data.
  - **Error:** ■ `ContributionErrorBoundary` wrapping in shell catches render errors.
  - **Disabled:** ■ Slot renders `InertReservedPlaceholder` when no canary is active. `aria-hidden="true"`, `role="presentation"`, `tabIndex={-1}`.
- **Accessibility:** Canary missing explicit `role` and `aria-label` (gap noted in checklist). Diagnostic banner missing `role="alert"`. `InertReservedPlaceholder` satisfies disabled/inert requirements.
- **Evidence:** `src/tools/video-editor/components/Canary/CodePanelCanary.tsx`; `src/tools/video-editor/components/Canary/Canary.test.tsx` (268 lines, 7 tests); `src/examples/code-panel-diagnostics-example.ts`.
- **Status:** `gap`
- **Disposition:** `deferred`
- **Contract-recheck:** CR:M2-004 (a11y gap), CR:M2-010, CR:M2-011, CR:M2-012

### 5.2 WritingPanelCanary

- **Host affordance:** `'writingPanel'` slot (M4 reserved). Rendered via `RESERVED_SLOT_CANARY` → `WritingPanelCanary`.
- **UI states:**
  - **Empty:** ■ Canary renders M4 milestone placeholder content.
  - **Loading:** □ Production loading deferred to M4.
  - **Error:** ■ `ContributionErrorBoundary` wraps slot renderer.
  - **Disabled:** ■ `InertReservedPlaceholder` when no canary active.
- **Accessibility:** Canary uses `data-video-editor-slot="writingPanel"` and `data-video-editor-canary="true"`. Missing explicit `role` and `aria-label` (gap).
- **Evidence:** `src/tools/video-editor/components/Canary/WritingPanelCanary.tsx`; `src/tools/video-editor/components/Canary/Canary.test.tsx`; `src/examples/writing-canary-example.ts`.
- **Status:** `gap`
- **Disposition:** `deferred`
- **Contract-recheck:** CR:M2-004, CR:M2-014

### 5.3 StagePanelCanary

- **Host affordance:** `'stagePanel'` slot (M3 reserved). Rendered via `RESERVED_SLOT_CANARY` → `StagePanelCanary`.
- **UI states:**
  - **Empty:** ■ Canary renders M3 milestone placeholder content.
  - **Loading:** □ Production loading deferred to M3+.
  - **Error:** ■ `ContributionErrorBoundary` wraps slot renderer.
  - **Disabled:** ■ `InertReservedPlaceholder` when no canary active.
- **Accessibility:** Canary uses `data-video-editor-slot="stagePanel"` and `data-video-editor-canary="true"`. Missing explicit `role` and `aria-label` (gap).
- **Evidence:** `src/tools/video-editor/components/Canary/StagePanelCanary.tsx`; `src/tools/video-editor/components/Canary/Canary.test.tsx`; `src/examples/stage-canary-example.ts`.
- **Status:** `gap`
- **Disposition:** `deferred`
- **Contract-recheck:** CR:M2-004, CR:M2-014

---

## 6. Diagnostic System Primitives

### 6.1 DiagnosticPanel

- **Host affordance:** Host-owned panel rendering `DiagnosticCollection` entries. Openable via "View diagnostics" action in `ContributionErrorBoundary` and diagnostic badges.
- **UI states:**
  - **Empty:** ■ Renders "No diagnostics" message when collection is empty.
  - **Loading:** — Diagnostics are synchronously available from the collection snapshot.
  - **Error:** □ Diagnostic panel itself has no error fallback beyond host error boundary.
  - **Disabled:** — Not applicable.
- **Accessibility:** Panel uses `role="region"` with `aria-label="Diagnostics"`. Individual diagnostic items use severity-colored badges with `aria-label`. "View diagnostics" button is keyboard-accessible.
- **Evidence:** `src/tools/video-editor/components/DiagnosticPanel/DiagnosticPanel.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-008, CR:M2-010, CR:M5-007

### 6.2 Diagnostic Badges / Banners

- **Host affordance:** Inline diagnostic rendering within inspector, code panel, and asset panel. Uses severity-colored badges and banners.
- **UI states:**
  - **Empty:** — No diagnostic banner when no diagnostics exist for the context.
  - **Loading:** — Not applicable.
  - **Error:** ■ Error diagnostics render as red banners with code and message.
  - **Disabled:** — Not applicable.
- **Accessibility:** Error/warning banners use `role="alert"` or `role="status"` (gap: CodePanelCanary diagnostic banner missing `role="alert"`). Source ranges should be announced.
- **Evidence:** `src/tools/video-editor/components/Canary/Canary.test.tsx` (diagnostic banner tests); diagnostic rendering patterns in `src/examples/code-panel-diagnostics-example.ts`.
- **Status:** `gap` (a11y role gap on CodePanelCanary banner)
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-004, CR:M2-005, CR:M2-010

---

## 7. Form & Parameter Primitives

### 7.1 SchemaForm

- **Host affordance:** Host-owned form renderer for extension parameter schemas. Used in inspector, effect config, clip config, and transition config.
- **UI states:**
  - **Empty:** ■ Renders form with all fields at their default values when no data is bound.
  - **Loading:** □ No explicit loading state for schema-form async validation.
  - **Error:** ■ Validation errors render inline per field with diagnostic messages. Unsupported schema types produce structured diagnostics.
  - **Disabled:** ■ Individual fields can be disabled via schema `readOnly` or host-managed disabled state.
- **Accessibility:** Form uses `<form>` element with `aria-label`. Each field uses `<label>` with `htmlFor`. Validation errors use `aria-describedby` linking to error messages.
- **Evidence:** `src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M2-006, CR:M2-007 (gap: schema capability registry tests)

---

## 8. Command & Palette Primitives

### 8.1 CommandPalette

- **Host affordance:** Host-owned command palette rendering registered commands with search, navigation, and invocation. Powered by `CommandRegistry`.
- **UI states:**
  - **Empty:** ■ Renders "No commands" when palette is empty or search filters match nothing.
  - **Loading:** — Commands are synchronously registered; palette renders instantly.
  - **Error:** □ Command invocation failure diagnostics displayed in palette but dedicated error UI tests not identified.
  - **Disabled:** □ Commands with unsatisfied `when` predicates are hidden/filtered; disabled command rendering tests not identified.
- **Accessibility:** Palette uses `role="listbox"` with `aria-label="Command palette"`. Search input uses `role="combobox"`. Keyboard navigation (Arrow keys, Enter, Escape).
- **Evidence:** `src/tools/video-editor/components/CommandPalette/CommandPalette.test.tsx`.
- **Status:** `gap`
- **Disposition:** `supported` (infrastructure); `deferred` (full palette test coverage: D-052)
- **Contract-recheck:** CR:M4-001, CR:M4-003, CR:M4-004, CR:M4-005

---

## 9. Proposal System Primitives

### 9.1 ProposalPanel

- **Host affordance:** Host-owned panel for previewing, accepting, and rejecting `TimelineProposal` objects. Renders proposal diff, rationale metadata, and accept/reject actions.
- **UI states:**
  - **Empty:** ■ Renders "No active proposals" when proposal queue is empty.
  - **Loading:** □ Proposal diff computation is synchronous; loading indicator for diff rendering not identified.
  - **Error:** ■ Stale base version rejection shows clear error with version conflict detail.
  - **Disabled:** □ Accept/reject buttons disabled during apply but explicit disabled-state tests not identified.
- **Accessibility:** Panel uses `role="region"` with `aria-label="Proposal review"`. Accept/reject buttons are keyboard-accessible.
- **Evidence:** `src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx`; `src/tools/video-editor/lib/proposal-runtime.test.ts` (39 tests).
- **Status:** `gap` (UI component tests: CR:M3-006 = deferred D-130)
- **Disposition:** `supported` (runtime); `deferred` (UI test coverage: D-130)
- **Contract-recheck:** CR:M3-002, CR:M3-003, CR:M3-006, CR:M3-008

---

## 10. Inspector & Properties Primitives

### 10.1 ClipPanel

- **Host affordance:** Host-owned panel within `inspectorPanel` for editing selected clip properties. Supports sequence clips, transition clips, and shader clips.
- **UI states:**
  - **Empty:** ■ "No clip selected" when no clip is active.
  - **Loading:** — Clip data is synchronously available from timeline store.
  - **Error:** ■ Missing clip-type IDs produce diagnostics; export guard blocks unsupported clips.
  - **Disabled:** ■ Panel disabled when no clip is selected.
- **Accessibility:** Panel uses `role="region"` with `aria-label="Clip properties"`. Parameter fields use SchemaForm accessibility patterns.
- **Evidence:** `src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx`, `src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx`, `src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx`; `src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M9-001, CR:M9-003, CR:M8-001

### 10.2 KeyframeInspector

- **Host affordance:** Host-owned panel for editing keyframe parameters on extension clip types. Displays keyframe timeline with interpolation controls.
- **UI states:**
  - **Empty:** ■ "No keyframes" when clip has no keyframe data.
  - **Loading:** — Keyframe data is synchronously available.
  - **Error:** ■ Invalid keyframe interpolation produces diagnostics.
  - **Disabled:** — Not applicable.
- **Accessibility:** Inspector uses `role="region"` with `aria-label="Keyframe inspector"`. Keyframe handles are keyboard-operable.
- **Evidence:** `src/tools/video-editor/components/KeyframeInspector/KeyframeInspector.test.tsx`; `src/examples/clip-type-keyframed-example.ts`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M9-001, CR:M9-002, CR:M9-005

### 10.3 EffectCreatorPanel

- **Host affordance:** Host-owned panel for browsing and applying extension-contributed component effects to clips.
- **UI states:**
  - **Empty:** ■ "No effects available" when no effect contributions registered.
  - **Loading:** — Effect list is synchronously available from registry.
  - **Error:** ■ Invalid effect schema produces diagnostics.
  - **Disabled:** □ Effect picker disabled when no clip selected; explicit disabled-state tests not identified.
- **Accessibility:** Panel uses `role="region"` with `aria-label="Effect creator"`. Effect list items are keyboard-navigable.
- **Evidence:** `src/tools/video-editor/components/EffectCreatorPanel.test.tsx`; `src/examples/effect-example.ts`; `src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M7-001, CR:M7-003, CR:M7-006 (gap for comprehensive tests)

---

## 11. Confirmation & Managed Object Primitives

### 11.1 ManagedObjectConfirmationDialog

- **Host affordance:** Dialog rendered when an extension operation would overwrite a managed (host-tracked) object. Uses `ManagedObjectGuard` for detection.
- **UI states:**
  - **Empty:** — Not applicable (only rendered on trigger).
  - **Loading:** — Not applicable.
  - **Error:** ■ Dialog renders warning with overwrite detail.
  - **Disabled:** — Not applicable.
- **Accessibility:** Dialog uses `role="alertdialog"` with `aria-modal="true"`, `aria-labelledby`. Confirm/cancel buttons are keyboard-accessible.
- **Evidence:** `src/tools/video-editor/components/ManagedObjectConfirmationDialog/ManagedObjectConfirmationDialog.test.tsx`; `src/tools/video-editor/lib/managed-object-guard.test.ts`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M3-014, CR:M3-015 (gap for diff rendering)

---

## 12. Preview & Export Primitives

### 12.1 PreviewPanel / RemotionPreview

- **Host affordance:** Host-owned video preview rendering timeline state through Remotion. Extensions contribute overlay renderers on top of the preview surface.
- **UI states:**
  - **Empty:** ■ Renders blank preview canvas when no timeline is loaded.
  - **Loading:** □ Preview renders progressively; no explicit loading skeleton.
  - **Error:** ■ Render errors caught by preview error boundaries; export guard blocks unsupported render paths.
  - **Disabled:** — Preview always renders when timeline is loaded.
- **Accessibility:** Preview canvas uses `role="img"` with `aria-label="Video preview"`. Playback controls are keyboard-accessible.
- **Evidence:** `src/tools/video-editor/components/PreviewPanel/RemotionPreview.test.tsx`; `src/tools/video-editor/components/PreviewPanel/OverlayEditor.test.tsx`.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M7-002, CR:M1-003

### 12.2 Export Guard / Renderability Surface

- **Host affordance:** Not a visible component — a cross-cutting guard invoked before render dispatch. Surfaces export and fast-path render blockers through planner-compatible diagnostics and `RenderBlocker.message` logs.
- **UI states:**
  - **Empty:** — Not applicable.
  - **Loading:** — Not applicable.
  - **Error:** ■ Export blockers render as `Diagnostic` entries with `code` starting `'export/'`; planner blockers render as `render-planner` diagnostics and provide blocked render/export log messages.
  - **Disabled:** — Not applicable.
- **Accessibility:** Export blocker diagnostics use severity-colored badges in the diagnostic panel. "View diagnostics" action links to filtered diagnostic panel.
- **Evidence:** `src/tools/video-editor/runtime/renderability.ts`; `src/tools/video-editor/runtime/renderPlanner.ts`; `src/tools/video-editor/hooks/useRenderState.ts`; `DiagnosticCollection` integration.
- **Status:** `pass`
- **Disposition:** `supported`
- **Contract-recheck:** CR:M1-003, CR:M1-011, CR:M5-005, CR:M11-004, CR:M7-004

---

## 13. Deferred Frontend Primitives

These primitives have SDK vocabulary defined but frontend implementation, test coverage, or both are explicitly deferred per the contract-recheck and supported/deferred matrices. Each row links to its deferral evidence.

| Primitive | Host Affordance | UI States | Accessibility | Evidence | Status | Disposition | Contract-Recheck |
|---|---|---|---|---|---|---|---|
| **AgentToolsPanel / AgentChat** | Host-owned panel for agent tool invocation and chat | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-041; `src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts`, `src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts` | `gap` | `deferred` | CR:M10-001, CR:M10-005 (D-041) |
| **CopilotPrompt** | Host-owned copilot prompt surface for timeline-aware generation | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-042; `src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts` | `gap` | `deferred` | CR:M10-006 (D-042) |
| **GenerationSessionPanel** | Host-owned panel for long-running generation with progress/cancel/proposal-ready | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-043, D-044; `src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts` | `gap` | `deferred` | CR:M10-008 (D-043), CR:M10-009 (D-044) |
| **LiveSourcesPanel** | Host-owned panel for live data source management, bake, and export readiness | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-030, D-031; `src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts`, `src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts` | `gap` | `deferred` | CR:M11-006 (D-030), CR:M11-007 (D-031) |
| **ShaderInspector** | Host-owned panel for shader uniform editing, texture binding, and compilation diagnostics | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-101, D-102; `src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts`, `src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts` | `gap` | `deferred` | CR:M13-004, CR:M13-007 (D-101), CR:M13-009 (D-102) |
| **MaterialBrowser** | Host-owned browser for `RenderMaterial` entries with filtering and detail views | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-023; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-011 (part of D-023) |
| **ProcessSettingsForm** | Host-owned form for process configuration, environment widgets, and operation discovery | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-023; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-004, CR:M12-010 (D-023) |
| **RoundtripResultsPanel** | Host-owned panel for process roundtrip results, sidecar previews, and download actions | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-025; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-005, CR:M12-006 (D-025) |
| **SidecarPreview** | Host-owned preview for sidecar/manifest artifacts | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-025; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-006 (D-025) |
| **SidecarEditingWidgets** | Host-owned widgets for editing sidecar metadata (captions, labels, cue lists) | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-023; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-011 (part of D-023) |
| **SequenceCreatorPanel** | Host-owned panel for sequence creation with controls manifest layout | □ States not tested in standalone frontend tests | □ Role/label expectations documented but not verified | DEFER:D-023; `src/examples/process-example.ts` | `gap` | `deferred` | CR:M12-011 (part of D-023) |
| **Extension Manager UI** | Host-owned extension manager (install, enable/disable, settings edit) | □ Full UI not confirmed as complete in current `main` | □ Role/label expectations documented but not verified | BLOCKER:B-001; `src/examples/hello-world-extension.ts` | `gap` | `deferred` | CR:M14-001, BLOCKER:B-001 (D-001–D-010) |

---

## 14. Cross-Cutting Accessibility Gaps

The following accessibility gaps span multiple primitives and are documented for tracking:

| Gap ID | Description | Affected Primitives | Resolution |
|---|---|---|---|
| A11Y-001 | Missing explicit `role` and `aria-label` on canary containers | CodePanelCanary, WritingPanelCanary, StagePanelCanary | Add `role="region"` and descriptive `aria-label` (deferred to M4) |
| A11Y-002 | Diagnostic banner missing `role="alert"` | CodePanelCanary, DiagnosticBadges | Add `role="alert"` to diagnostic banners |
| A11Y-003 | Sparse loading-state skeletons/spinners across panels | Inspector, Asset Panel, ProposalPanel | Add loading skeletons deferred per panel milestone |
| A11Y-004 | Deferred primitives not verified for ARIA compliance | All § 13 deferred primitives | Verify on activation milestone |

---

## 15. Matrix Statistics

### 15.1 Supported primitives

| Category | Count | Status |
|---|---|---|
| Core Shell | 3 | 3 pass |
| Active Host Surfaces | 10 | 10 pass |
| Diagnostic System | 2 | 1 pass, 1 gap |
| Form & Parameter | 1 | 1 pass |
| Command & Palette | 1 | 1 gap |
| Proposal System | 1 | 1 gap |
| Inspector & Properties | 3 | 3 pass |
| Confirmation | 1 | 1 pass |
| Preview & Export | 2 | 2 pass |
| **Total supported** | **24** | **21 pass, 3 gap** |

### 15.2 Deferred primitives

| Category | Count | Status |
|---|---|---|
| Reserved / Canary | 3 | 3 gap (deferred to M3–M4) |
| Deferred Frontend | 12 | 12 gap (deferred per contract-recheck) |
| **Total deferred** | **15** | **15 gap** |

### 15.3 Disposition summary

| Disposition | Count |
|---|---|
| `supported` | 21 |
| `deferred` | 18 |
| `unsupported` | 0 |
| `release-blocking` | 0 |

---

## 16. Cross-Reference Index

### 16.1 Contract-recheck rows by primitive

Each primitive row's `Contract-Recheck` column links to the canonical evidence in [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md).

### 16.2 Supported/deferred matrix mapping

Supported primitives map to rows S-020–S-027, S-050–S-051, S-060–S-065 in [extension-platform-supported-deferred.md](./extension-platform-supported-deferred.md). Deferred primitives map to rows D-030–D-046, D-050–D-052, D-060–D-064, D-070–D-073, D-080–D-085, D-090–D-091, D-100–D-102, D-120–D-135.

### 16.3 External documentation references

| Document | Purpose |
|---|---|
| [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md) | Complete M0–M14 Done Criteria evidence matrix |
| [extension-platform-supported-deferred.md](./extension-platform-supported-deferred.md) | Canonical supported/deferred V1 behavior classification |
| [extensions-trust-envelope.md](./extensions-trust-envelope.md) | V1 trusted-local execution model |
| [provider-compatibility-matrix.md](./provider-compatibility-matrix.md) | DataProvider compatibility matrix |
| [docs/video-editor/frontend-closure-checklist.md](./frontend-closure-checklist.md) | Transitional checklist (superseded by this matrix) |

---

## 17. Version History

| Date | Change |
|---|---|
| 2026-06-20 | Initial frontend closure matrix for M15. Replaces the checklist format (§ 2–3 of `docs/video-editor/frontend-closure-checklist.md`) with a comprehensive matrix covering 39 public primitives across core shell, active surfaces, canary surfaces, diagnostic system, forms, commands, proposals, inspectors, confirmation, preview/export, and deferred primitives. |
