# Extension Quickstart — Reigh Video Editor V1

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Audience:** Extension authors beginning their first Reigh extension.
**Prerequisite gate:** [Example readiness](./extension-platform-supported-deferred.md) (M15 pre-doc gate, passed 2026-06-20).

---

## 1. What is a Reigh extension?

A Reigh extension is a TypeScript module that uses **only** the public `@reigh/editor-sdk` entrypoint. Extensions declare their identity, contributions, and lifecycle in a single frozen manifest, then register behaviour imperatively during `activate()`.

In V1, every extension is a **trusted-local extension**: it runs in the same browser JavaScript context as the Reigh editor with full renderer privileges. There is no sandbox, no process isolation, and no capability enforcement. **Review extension source before enabling it in a shared project.** See the [Trust Envelope](./extensions-trust-envelope.md) for full details.

---

## 2. Your first extension

Every extension starts with `defineExtension()` from `@reigh/editor-sdk`. The minimal valid extension is a manifest-only declaration:

```typescript
import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension } from '@reigh/editor-sdk';

export const myExtension: ReighExtension = defineExtension({
  manifest: {
    id: 'com.example.my-extension',
    version: '1.0.0',
    label: 'My Extension',
    description: 'What my extension does.',
    apiVersion: 1,
  },
});
```

### 2.1 Extension ID rules

Extension IDs must match `/^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*$/i` — lowercase start, dot-separated segments of letters, digits, hyphens, and underscores. Contribution IDs follow the same rules and must be unique within the extension.

`defineExtension()` validates IDs at definition time and throws on invalid or duplicate IDs.

### 2.2 Adding an activate function

Extensions that need to do work at activation supply an `activate(ctx)` function:

```typescript
import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension, ExtensionContext, DisposeHandle } from '@reigh/editor-sdk';

export const myExtension: ReighExtension = defineExtension({
  manifest: {
    id: 'com.example.my-extension',
    version: '1.0.0',
    label: 'My Extension',
    description: 'Does work on activation.',
    apiVersion: 1,
  },
  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.chrome.toast('My extension activated!', 'info');

    return {
      dispose(): void {
        ctx.chrome.toast('My extension disposed.', 'info');
      },
    };
  },
});
```

The `activate()` function receives an `ExtensionContext` and must return a `DisposeHandle` (or `void`). The dispose function is called when the extension is deactivated — it must be **idempotent** and **must not throw**.

---

## 3. Declaring contributions

Contributions tell the host what UI surfaces and behaviour your extension provides. They are declared in the `manifest.contributions` array.

### 3.1 Slot contributions (toolbar, statusBar, codePanel, etc.)

Slot contributions place your extension's UI in named host slots:

```typescript
contributions: [
  {
    id: 'my-toolbar-button',
    kind: 'slot',
    slot: 'toolbar',
    order: 200,
    label: 'My Toolbar Button',
  },
  {
    id: 'my-status',
    kind: 'slot',
    slot: 'statusBar',
    order: 100,
    label: 'My Status Widget',
  },
]
```

Available slots: `header`, `toolbar`, `leftPanel`, `rightPanel`, `codePanel`, `writingPanel`, `stagePanel`, `timelineFooter`, `statusBar`, `dialogs`, `assetPanel`, `inspectorPanel`.

Example reference: [toolbar-example.ts](../../src/examples/toolbar-example.ts) (docs-safe), [status-surface-example.ts](../../src/examples/status-surface-example.ts) (docs-safe).

### 3.2 Inspector and overlay contributions

For the properties panel and timeline canvas:

```typescript
{
  id: 'my-inspector-section',
  kind: 'inspectorSection',
  placement: 'before-default', // or 'after-default'
  label: 'My Section',
  order: 50,
},
{
  id: 'my-overlay',
  kind: 'timelineOverlay',
  label: 'My Overlay',
  order: 100,
}
```

Example references: [inspector-example.ts](../../src/examples/inspector-example.ts) (docs-safe), [overlay-example.ts](../../src/examples/overlay-example.ts) (docs-safe).

### 3.3 Commands, keybindings, and context menus (M4)

Declare a command, a keyboard shortcut, and a context-menu entry in one extension:

```typescript
import type {
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
} from '@reigh/editor-sdk';

const contributions: readonly [
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
] = [
  {
    id: 'my-command',
    kind: 'command',
    command: 'com.example.my-extension.doSomething',
    label: 'Do Something',
    category: 'Examples',
    order: 10,
  },
  {
    id: 'my-keybinding',
    kind: 'keybinding',
    command: 'com.example.my-extension.doSomething',
    key: 'CtrlOrCmd+Alt+D',
    order: 10,
  },
  {
    id: 'my-menu-item',
    kind: 'contextMenuItem',
    command: 'com.example.my-extension.doSomething',
    label: 'Do Something',
    target: 'clip',
    when: 'target.clipId != null',
    order: 10,
  },
];
```

Then register the handler in `activate()`:

```typescript
activate(ctx: ExtensionContext): DisposeHandle {
  return ctx.commands.registerCommand(
    'com.example.my-extension.doSomething',
    (run) => {
      ctx.chrome.toast(`Command invoked on ${run.target?.target ?? 'no target'}.`, 'info');
    },
    { label: 'Do Something', category: 'Examples' },
  );
}
```

Shortcut conflict resolution is **first-registered-wins**. If two extensions bind the same key, the first to register keeps it; later registrations produce diagnostics.

Example reference: [command-extension.ts](../../src/examples/command-extension.ts) (docs-safe).

### 3.4 Effect, transition, and clip-type contributions (M7–M9)

These contributions register trusted component renderers:

- **Effect** (`kind: 'effect'`): Component that renders on clips in preview. Export-blocked by default (`allowBrowserExport: false`, `allowWorkerExport: false`).
- **Transition** (`kind: 'transition'`): Renders between clips.
- **Clip type** (`kind: 'clipType'`): A contributed clip type with parameter schema and keyframed interpolation.

In the composition graph (M4), clip-type contributions project as `ContributionRef`
nodes keyed by `contribution:clipType:<extensionId>:<contributionId>`. Each clip
using a contributed clip type emits a `consumes` edge from the clip node to the
clip-type contribution node, with resolved/missing/disabled reference state
diagnostics.

Example references:
- Effect: flagship-local extension's `FlagshipEffectComponent.tsx` (docs-safe, EXT)
- Transition: flagship-local extension's `__tests__/flagship-local-transition.test.ts` (docs-safe, EXT)
- Clip type: [clip-type-keyframed-example.ts](../../src/examples/clip-type-keyframed-example.ts) (docs-safe)

### 3.5 Other supported contribution kinds

|| Kind | Milestone | Example (docs-safe) |
||---|---|---|
|| `parser` | M6 | [integrity-hash-parser-example.ts](../../src/examples/integrity-hash-parser-example.ts) |
|| `outputFormat` | M6 | Typed and declarable; execution reserved (returns M6 from `contributionKindNotYetBridged`). Example: [metadata-json-output-example.ts](../../src/examples/metadata-json-output-example.ts) |
|| `searchProvider` | M6 | Typed and declarable; execution reserved (returns M6 from `contributionKindNotYetBridged`). Frontend rendering deferred (D-063, D-064) |
|| `metadataFacet` | M6 | Supported (bridged); frontend rendering deferred (D-063, D-064) |
|| `assetDetailSection` | M6 | Supported (bridged); frontend rendering deferred |
|| `agentTool` | M10 | [agent-tools-canary/](../../src/tools/video-editor/examples/extensions/agent-tools-canary/) (EXT, docs-safe) |
|| `shader` | M13 | [clip-local-shader-canary/](../../src/tools/video-editor/examples/extensions/clip-local-shader-canary/) (EXT, docs-safe) |
|| `automation` | M9 | [automation-recording-canary.ts](../../src/examples/automation-recording-canary.ts) (docs-safe) |

Shader contributions (M4) are assigned to clips or the timeline postprocess
scope through **graph-owned** `shader.assign` / `shader.remove` preview
operations. These are internal host operations derived from existing timeline
patch payloads (`clip.update` with `app.shader`, `app.update` with
`shaderPostprocess`) — they are not public SDK patch families. Shader-uniform
keyframes use the canonical `uniforms.<name>` target path (e.g.
`uniforms.intensity`) and project `animates` edges in the composition graph.

---

## 4. The ExtensionContext

The `ExtensionContext` (received in `activate()`) provides every service your extension can use:

### 4.1 Chrome services (`ctx.chrome`)

```typescript
ctx.chrome.toast('Hello!', 'info');           // Host-visible toast
ctx.chrome.progress(75, 'Processing...');     // Progress indicator
ctx.chrome.focus('#my-element');              // Move focus within editor shell
ctx.chrome.announce('Clip added.', 'polite');  // Screen-reader announcement

// Event subscriptions
const sub = ctx.chrome.subscribe('toast', (payload) => { /* ... */ });
sub.dispose(); // Clean up in your dispose function
```

### 4.2 Settings (`ctx.services.settings`)

Settings are localStorage-backed, scoped per extension with the `reigh.ext.<id>.` key prefix, and cleaned up on dispose:

```typescript
const enabled = ctx.services.settings.get<boolean>('myFeature.enabled');
ctx.services.settings.set('myFeature.enabled', true);
ctx.services.settings.delete('myFeature.enabled');
```

Declare defaults in `manifest.settingsDefaults`:

```typescript
settingsDefaults: {
  'myFeature.enabled': true,
  'myFeature.threshold': 0.5,
}
```

Settings migration is **deferred** (D-005). The migration infrastructure exists in the SDK (`extensionSettingsMigration`) but the manager UI is part of the deferred M14 packaging work.

### 4.3 Internationalisation (`ctx.services.i18n`)

Simple key-lookup with `{{placeholder}}` replacement:

```typescript
manifest: {
  messages: {
    'greeting': 'Hello, {{name}}!',
  },
  // ...
}
// In activate():
ctx.services.i18n.t('greeting', { name: 'World' }); // "Hello, World!"
```

### 4.4 Diagnostics (`ctx.services.diagnostics`)

Extensions can publish structured diagnostics:

```typescript
ctx.services.diagnostics.report({
  severity: 'warning',
  code: 'my-extension/validation-failed',
  message: 'Clip exceeds recommended duration.',
  contributionId: 'my-inspector-section',
  detail: { clipId: 'clip-0042', duration: 3600 },
});
```

Diagnostics surfaces include: the diagnostic panel (code panel), status surface, and export guard results. The host provides `DiagnosticPanel` with diagnostic fallback links filtered to the failing extension.

Example reference: [code-panel-diagnostics-example.ts](../../src/examples/code-panel-diagnostics-example.ts) (docs-safe).

---

## 5. Timeline mutation (patches and proposals)

Extensions read and write timeline data through the **TimelinePatch** system:

```typescript
// Read the current timeline
const snapshot = ctx.creative.reader.snapshot();

// Build a patch
const patch: TimelinePatch = {
  version: snapshot.baseVersion,
  source: ctx.extension.id as string,
  meta: { kind: 'my-extension-update' },
  operations: [
    {
      op: 'project-data.write',
      target: ctx.extension.id as string,
      payload: {
        key: 'lastAction',
        value: { timestamp: Date.now() },
        mode: 'replace',
      },
    },
  ],
};

// Apply directly (immediate mutation)
ctx.creative.timeline.apply(patch);
```

Supported operations:
- **Safe insert/update/delete/reorder clips** and update tracks/assets through `TimelineOps`
- **Proposal preview** without mutating the real timeline
- **Accept/reject** with stale base version detection
- **Undo/rollback** for patch batches
- **Relative/fractional ordering** for clip positioning
- **Project-data persistence** per extension with oversized payload rejection
- **Source-map** navigation metadata

Example reference: [command-extension.ts](../../src/examples/command-extension.ts) (docs-safe) demonstrates building and applying a patch.

### 5.1 What is deferred

- `clip.split` and `clip.slice` operations are **deferred** (D-110) — reserved with warnings
- Dedicated proposal UI component tests are **deferred** (D-130)
- DSL/compiler canary reading `CreativeContext.timeline` is **deferred** (D-131)
- Proposal diff rendering and source-map navigation UI are **deferred** (D-132)

See the [supported/deferred matrix](./extension-platform-supported-deferred.md) §3.11 and §3.13 for full details.

---

## 6. Trust and safety warnings

### 6.1 Trusted-local execution

In V1, extensions run **same-thread, same-origin** as the Reigh editor. This means:

- No sandbox, no process isolation, no CSP subdivision
- Full access to `fetch`, `localStorage`, DOM, and all browser APIs
- The `permissions` field in the manifest is **descriptive only** — no runtime enforcement

The flagship-local extension emits this warning at activation:

> ⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.

### 6.2 Error containment

- Contribution-level `ContributionErrorBoundary` catches React render errors within extension slots, dialogs, panels, and inspector sections
- Activation-time throws are captured as diagnostics and the extension transitions to `failed` state
- Lifecycle teardown failures are captured as diagnostics, never thrown
- Extensions can still throw in non-React paths (event handlers, timers) — those errors are **not** caught

### 6.3 Export safety

Before render, `runExportGuard()` scans the timeline for unknown clip types, effects, and transitions. Extension-declared IDs from inactive contributions produce `warning`-severity diagnostics. Truly unknown IDs produce `error`-severity diagnostics that block export.

---

## 7. Running the pre-doc example readiness gate

Before writing documentation that references examples, run:

```bash
node scripts/quality/check-extension-example-readiness.mjs --audit
```

This gate verifies that:
1. Every `EX:` and `EXT:` evidence reference in a **supported** row resolves to an existing file
2. Example files that demonstrate deferred/unsupported behaviour are flagged
3. Every example file imports exclusively from `@reigh/editor-sdk`
4. On-disk examples have a corresponding supported matrix row

The gate outputs a JSON record of docs-safe example IDs as its final line. The documents in this directory were written after the gate passed (22 docs-safe examples, 0 failures, 8 unclassified warnings).

---

## 8. Docs-safe example index

The following examples passed the M15 pre-doc readiness gate and are safe to reference:

### Core SDK examples (`src/examples/`)

| Example file | Demonstrates |
|---|---|
| `toolbar-example.ts` | Slot contribution (toolbar) |
| `inspector-example.ts` | Inspector section contribution |
| `overlay-example.ts` | Timeline overlay contribution |
| `status-surface-example.ts` | Status bar slot + settings + chrome events |
| `code-panel-diagnostics-example.ts` | Structured diagnostic reporting with source ranges |
| `surface-coverage.ts` | Surface coverage across host slots |
| `command-extension.ts` | Command, keybinding, context menu, timeline patch |
| `integrity-hash-parser-example.ts` | Parser contribution with MIME/extension limits |
| `metadata-json-output-example.ts` | Compile-only output format contribution |
| `clip-type-keyframed-example.ts` | Contributed clip type with keyframed params |
| `automation-recording-canary.ts` | Automation recording with deterministic keyframes |
| `writing-canary-example.ts` | Non-timeline-native workflow (writing panel) |
| `stage-canary-example.ts` | Non-timeline-native workflow (canvas/stage panel) |

### Extension directory examples (`src/tools/video-editor/examples/extensions/`)

| Extension directory | Demonstrates |
|---|---|
| `flagship-local/` | Full extension: toolbar, status, commands, effects, transitions |
| `agent-tools-canary/` | Agent tool extension |
| `agent-tools-copilot/` | Copilot-style agent tool |
| `agent-tools-export/` | Export-adjacent agent tool |
| `live-webcam-canary/` | Live data bridge (webcam) |
| `live-generated-frame-canary/` | Live data bridge (generated frames) |
| `clip-local-shader-canary/` | Shader clip type |
| `postprocess-shader-canary/` | Post-process shader |

---

## 9. What is NOT available in V1

These capabilities are explicitly deferred or unsupported. **Do not document them as available in quickstart guides.**

### Deferred (planned for future milestones)

| Area | Deferral ref | Earliest milestone |
|---|---|---|
| Extension manager UI (install, enable/disable) | D-001–D-010 | M14 |
| Render planner & export UI | D-020–D-027 | M12 |
| Live data bridge frontend state coverage | D-030–D-037 | M11 |
| Agent tool workflow validation & frontend | D-040–D-047 | M10 |
| Command registry tests | D-050–D-052 | M4 |
| Asset metadata frontend rendering | D-060–D-064 | M6 |
| Provider isolation tests | D-070–D-073 | M5 |
| Effect/transition comprehensive tests | D-080–D-085 | M7–M8 |
| Clip-type UI integration tests | D-090–D-091 | M9 |
| Shader frontend & materializer | D-100–D-102 | M13 |
| Timeline patch reserved ops (split/slice) | D-110–D-111 | Future |
| Permission enforcement & sandboxing | D-120–D-122 | M4–M5 |

### Unsupported (out of scope for all milestones)

- Marketplace / extension registry (unsupported, D-123)
- Cloud extension loading
- Sandboxed execution (iframe/Worker/ShadowRealm)
- Theme contributions
- Public CRDT collaboration primitives

See the [supported/deferred matrix](./extension-platform-supported-deferred.md) §3–4 for the complete classification.

---

## 10. Next steps

1. Read the [Extension Author Contract](./extension-author-contract.md) for the complete developer obligations.
2. Study the [supported/deferred matrix](./extension-platform-supported-deferred.md) to understand what is available now vs. planned.
3. Review the [trust envelope](./extensions-trust-envelope.md) for the V1 security posture.
4. Browse the docs-safe examples in `src/examples/` and `src/tools/video-editor/examples/extensions/`.
5. Check the [TimelinePatch operations reference](./timeline-patch-operations.md) for the complete patch vocabulary.

---

## 11. Version history

| Date | Change |
|---|---|
| 2026-06-20 | Initial quickstart for M15. Written after pre-doc example readiness gate passed (22 docs-safe examples, 0 failures). All referenced examples are docs-safe. Missing workflows classified as deferred or unsupported per the supported/deferred matrix. |
