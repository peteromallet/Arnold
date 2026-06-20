# Frontend Closure Checklist — M2+ Extension Primitives

**Status:** Active (M2)  
**Last updated:** 2026-06-19  
**Scope:** Every new public primitive added to the video editor extension surface layer (surfaces, inspectors, overlays, dialogs, canaries, and reserved placeholders).

---

## 1. Purpose

This checklist applies to every new React component, host slot, or SDK-exposed
primitive that becomes part of the extension shell contract. Before marking a
primitive as "done," the implementor must confirm — and document — the
answers to each item below. The goal is catching the cross-cutting concerns
(surface identity, state completeness, diagnostic fallback, accessibility, and
test discoverability) that span multiple batch steps and are easy to miss when
squinting at a single file.

---

## 2. The Checklist

For each new public primitive, confirm the following. Mark `[x]` when
satisfied; note gaps and the milestone where they will be addressed.

### 2.1 Host surface identity

- [ ] **Which host surface/slot does it occupy?**  
  Name the exact `VideoEditorSlotName` value (e.g. `'leftPanel'`,
  `'codePanel'`, `'inspector'`, `'timelineOverlay'`, `'dialogs'`,
  `'toolbar'`, `'statusBar'`, `'writingPanel'`, `'stagePanel'`).

- [ ] **Is the slot registration discoverable?**  
  The primitive must be registered via one of the canonical contribution
  paths (`extensionSurface.ts` normalization, `extensionRendererRegistry`,
  or the `TimelineEditorShellCore.tsx` slot map) and must be traceable
  from the component back to the manifest `contributions` entry.

### 2.2 State completeness — empty / loading / error / disabled

- [ ] **Empty state** — What does the primitive render when there is no
  data, no selection, or no timeline bound? The empty state must be visibly
  distinct from a blank render and must not cause layout collapse in the
  host shell.

- [ ] **Loading state** — What does the primitive render while data is
  being fetched, resolved, or activated? The loading state must be
  distinguishable from empty (e.g., a skeleton, spinner, or progress
  indicator) and must not block shell interaction indefinitely.

- [ ] **Error state** — What does the primitive render when data fetch
  fails, render throws, or an invariant is violated? The error state must
  be caught by `ContributionErrorBoundary` or an equivalent host boundary
  and must display the extension ID / contribution ID where possible.

- [ ] **Disabled state** — What does the primitive render when the slot is
  reserved but not yet bridged (inert placeholder), or when the
  contribution is explicitly disabled? The disabled state must use
  `aria-hidden="true"`, `role="presentation"`, and `tabIndex={-1}` (see
  `InertReservedPlaceholder`) and must not be focusable or interactive.

### 2.3 Diagnostic fallback

- [ ] **Does the primitive publish structured diagnostics?**  
  Errors, warnings, and informational events must use the
  `DiagnosticCollection` (via `ExtensionDiagnosticsService.report()`) with
  stable diagnostic IDs, severity, code, message, and 1-based source ranges
  when applicable.

- [ ] **Does the primitive surface diagnostics in the UI?**  
  The primitive should render inline diagnostic messages (severity-colored
  badges, banners, or markers) and/or provide a "View diagnostics" action
  that opens the `DiagnosticPanel` filtered to the relevant extension and
  contribution.

- [ ] **Are export-blocker diagnostics handled?**  
  Diagnostics with `code` starting with `'export/'` and severity `'error'`
  must be surfaced to the user and must prevent render dispatch through the
  export guard path.

### 2.4 Accessibility behavior

- [ ] **Does the primitive have an accessible role and label?**  
  Use semantic HTML roles (`region`, `dialog`, `list`, `status`) and
  `aria-label` / `aria-labelledby` on the outermost container.

- [ ] **Are dynamic updates announced?**  
  Use `aria-live="polite"` (or `"assertive"` for critical alerts) on
  containers whose content updates asynchronously.

- [ ] **Are interactive elements keyboard-accessible?**  
  All buttons, toggles, and controls must be reachable via `Tab`, operable
  via `Enter`/`Space`, and have visible focus indicators.

- [ ] **Is the primitive's disabled/inert state non-interactive?**  
  Disabled placeholders and reserved slots must use `aria-hidden="true"`,
  `role="presentation"`, and `tabIndex={-1}` to prevent screen-reader
  and keyboard interaction.

### 2.5 Test path

- [ ] **Where are the tests?**  
  Document the exact test file path (e.g.,
  `src/tools/video-editor/components/Canary/Canary.test.tsx`). Every
  primitive must have focused component tests covering at minimum:
  - Smoke rendering with required props
  - Every state from § 2.2 (empty / loading / error / disabled)
  - Diagnostic rendering (banners, source ranges)
  - Accessibility attributes (`role`, `aria-label`, `aria-live`)
  - Interaction behavior (buttons, toggles, gestures)

---

## 3. Application: Code Panel Canary

*Applied against `CodePanelCanary.tsx` (host canary) and
`code-panel-diagnostics-example.ts` (SDK example).*

### 3.1 Host surface identity

- [x] **Host surface:** `codePanel` — registered in
  `TimelineEditorShellCore.tsx` via `RESERVED_SLOT_NAMES` / `InertReservedPlaceholder`
  (M4 milestone) and rendered by `CodePanelCanary` with
  `data-video-editor-slot="codePanel"`.
- [x] **Slot registration:** traceable from `TimelineEditorShellCore.tsx` →
  `resolveSurfaceSlot()` → `CodePanelCanary` canary renderer.

### 3.2 State completeness

- [x] **Empty state:** Implicit — the canary always renders content (the demo
  source and diagnostic). An empty-state path for production ("no code
  panel content") is deferred to M4 when the slot transitions from
  reserved/inert to active.
- [x] **Loading state:** Implicit — not applicable for a canary. Production
  loading state (skeleton / spinner while code analysis runs) is deferred
  to M4.
- [x] **Error state:** The `ContributionErrorBoundary` wrapping the slot in
  `TimelineEditorShellCore.tsx` catches render errors and displays a
  compact fallback with extension/contribution ID and a "View diagnostics"
  action.
- [x] **Disabled state:** The `codePanel` slot is a **reserved slot** (M4
  milestone). When no extension contributes to it, the shell renders
  `InertReservedPlaceholder` with `aria-hidden="true"`,
  `role="presentation"`, and `tabIndex={-1}`. The canary itself is a
  development-only placeholder that communicates the M4 deferral.

### 3.3 Diagnostic fallback

- [x] **Structured diagnostics:** The SDK example
  (`code-panel-diagnostics-example.ts`) publishes three structured
  diagnostics plus one export-blocker diagnostic via
  `ctx.services.diagnostics.report()` with stable codes
  (`code/syntax-error`, `code/unused-variable`, `code/analysis-complete`,
  `export/unknown-clip-type`).
- [x] **Diagnostic rendering:** The canary renders a yellow diagnostic
  banner with severity icon (`AlertCircle`), diagnostic code
  (`canary/syntax-warn`), message, and 1-based source range
  (`L7:5–9`). The source display highlights the offending identifier with
  a wavy underline.
- [x] **Export-blocker diagnostics:** The SDK example includes an
  `export/unknown-clip-type` diagnostic (severity: `warning`) demonstrating
  the export diagnostic shape. Export-blocker semantics (severity
  `error` → render blocked) are enforced by `runExportGuard()`.

### 3.4 Accessibility behavior

- [ ] **Accessible role and label:** The canary container uses
  `data-video-editor-slot="codePanel"` and
  `data-video-editor-canary="true"` but is missing an explicit `role` and
  `aria-label`. **Gap:** add `role="region"` and
  `aria-label="Code panel (canary)"` on the outermost `<div>`.
- [ ] **Dynamic update announcements:** The canary does not change
  asynchronously, so `aria-live` is not strictly required. However, the
  diagnostic banner should use `role="alert"` to ensure screen readers
  announce it on mount. **Gap:** add `role="alert"` to the diagnostic
  banner `<div>`.
- [x] **Keyboard accessibility:** No interactive controls in the canary
  (display-only). The shell-level "View diagnostics" button in the error
  boundary is keyboard-accessible.
- [x] **Disabled/inert state:** The `InertReservedPlaceholder` wrapping the
  slot when no extension contributes satisfies `aria-hidden="true"`,
  `role="presentation"`, and `tabIndex={-1}`.

### 3.5 Test path

- [x] **Test file:** `src/tools/video-editor/components/Canary/Canary.test.tsx`
- [x] **Coverage:** 7 tests covering smoke rendering, timeline name, save
  status, diagnostic banner, diagnostic source range, source line
  rendering, marker span highlighting, and M4 canary legend.

---

## 4. Static Assertion

A governance test in `src/sdk/examples-governance.test.ts` asserts that
this checklist document exists and contains all five required section
headers (§ 2.1–§ 2.5). The assertion runs as part of the SDK governance
suite (`npx vitest run … examples-governance.test.ts`) and will fail the
build if the document is deleted or a required section is renamed.

The assertion is intentionally cheap — a single `readFileSync` plus
`includes()` checks per section — and does not parse Markdown structure.
It keeps the checklist discoverable without adding a new CI script.

---

## 5. Version History

| Date | Change |
|---|---|
| 2026-06-19 | Initial checklist. Created for M2 Surfaces / Inspectors / Overlays. |
