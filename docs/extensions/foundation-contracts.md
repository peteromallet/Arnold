# Foundation Contracts — Reigh Video Editor V1

**Status:** Active (M5)
**Last updated:** 2026-06-24
**Scope:** Canonical contract paths that every extension follows from definition through activation, contribution rendering, diagnostics, and disposal. This document records the *actual code paths* — not aspirational architecture — and is traceable to specific files and functions.

---

## 1. Extension Definition

### 1.1 Entry point

Extensions are defined via `defineExtension()` from `@reigh/editor-sdk`. The function validates and deep-freezes the manifest.

**Canonical path:** `src/sdk/index.ts` → `defineExtension()`

### 1.2 Manifest contract

Every extension manifest (`reigh-extension.json`) must include:

| Field | Type | Validated by |
|---|---|---|
| `id` | `string` | `validateExtensionId()` — dot-separated, lowercase start, ≤128 chars |
| `version` | `string` | Semver |
| `label` | `string` | Non-empty |
| `apiVersion` | `number` | Must be `1` in V1 |

Optional fields: `description`, `contributions`, `settingsDefaults`, `settingsSchema`, `messages`, `permissions`, `processes`, `dependsOn`, `migrations`.

**Manifest format is frozen for V1.** There are 9 consistent example manifests in `src/tools/video-editor/examples/extensions/*/reigh-extension.json`.

### 1.3 Immutability

`defineExtension()` deep-freezes the manifest. Extension IDs, contribution IDs, and all literal values are preserved through the frozen object. Authors must not mutate the manifest after definition.

---

## 2. Lifecycle State Machine

### 2.1 States

Extensions follow a provider-scoped lifecycle managed by `ExtensionLifecycleHost`:

```
inactive → activating → active ──┐
             ↓                   ↓
           failed → deactivating → disposed
```

`disposed` is terminal. All operations on a disposed lifecycle are no-ops.

**Canonical path:** `src/tools/video-editor/runtime/extensionLifecycle.ts` → `createExtensionLifecycleHost()`

### 2.2 State transitions

| Transition | Trigger | Idempotent? |
|---|---|---|
| `inactive → activating` | `activate(ctx)` called | Yes — no-op if not inactive |
| `activating → active` | `activate()` returns successfully | Automatic |
| `activating → failed` | `activate()` throws | Automatic; error captured as diagnostic |
| `active → deactivating` | `deactivate()` called | Yes |
| `deactivating → disposed` | Dispose handles called, host services cleaned | Automatic |
| `failed → deactivating` | `deactivate()` called (resets before re-activation) | Yes |

### 2.3 Dev-console grouping

Every activation and deactivation is wrapped in `console.groupCollapsed` / `console.groupEnd` with the extension ID as the label:

```
[Extension lifecycle] com.reigh.examples.flagship-local
  Activating extension "com.reigh.examples.flagship-local" (v1.0.0)
  Extension "com.reigh.examples.flagship-local" activated successfully
```

---

## 3. Contribution Surfaces

### 3.1 Slot system

Extensions contribute React nodes to named host slots. Each slot is a stable mount point in the editor shell.

**Canonical path:** `src/tools/video-editor/runtime/extensionSurface.ts` → `VideoEditorSlotName`

| Slot | Mount point |
|---|---|
| `header` | Above the toolbar |
| `toolbar` | Main toolbar area |
| `leftPanel` | Left-side panel |
| `rightPanel` | Right-side panel |
| `codePanel` | Code editing panel |
| `writingPanel` | Writing/script panel |
| `stagePanel` | Canvas/stage panel |
| `timelineFooter` | Below the timeline |
| `statusBar` | Status bar area |
| `dialogs` | Modal/overlay dialog host |
| `assetPanel` | Asset management panel |
| `inspectorPanel` | Inspector panel |

**Rendering:** `src/tools/video-editor/components/TimelineEditorShellCore.tsx` — slot contributions resolved via `resolveSurfaceSlot()` and wrapped in `HostContributionErrorBoundary`.

### 3.2 Panel registry

Extensions can register panels for the asset panel and inspector sections:

- `VideoEditorPanelDescriptor` — asset panel panels
- `VideoEditorInspectorSectionDescriptor` — inspector sections (before/after default)
- `VideoEditorOverlayDescriptor` — timeline overlays

**Canonical path:** `src/tools/video-editor/runtime/extensionSurface.ts` → `resolveVideoEditorPanelRegistry()`, `getInspectorContributions()`, `getTimelineOverlayContributions()`

### 3.3 Dialog host

Extensions register dialogs via `VideoEditorDialogDescriptor` with modal/overlay layering and visibility predicates.

---

## 4. Runtime Normalization

### 4.1 Normalization pipeline

When extensions are provided to the host, they pass through a normalization pipeline that converts manifest declarations into immutable, provider-scoped runtime descriptors:

```
ReighExtension[] → normalizeExtensionRuntime() → ExtensionRuntime
```

**Canonical path:** `src/tools/video-editor/runtime/extensionSurface.ts` → `normalizeExtensionRuntime()`

### 4.2 What normalization produces

`normalizeExtensionRuntime()` produces:

| Output | Description |
|---|---|
| `ExtensionRuntime` | Provider-scoped runtime with slots, dialogs, panels, overlays, parsers, effects, transitions, shaders, agent tools, output formats, processes, search providers, metadata facets, asset detail sections |
| `extensionRuntime.extensions` | Map of extension ID → `ReighExtension` manifest |
| `extensionRuntime.contributionOwnerMap` | Map of contribution ID → extension ID (for error boundary owner resolution) |
| `extensionRuntime.diagnostics` | Normalization diagnostics (unknown kinds, reserved kinds, validation failures) |
| `extensionRuntime.packageStateInventory` | Package inventory entries for the Extension Manager |

### 4.3 Contribution ordering

Contributions within each surface are deterministically ordered by:
1. Extension order (as provided in the `extensions` array)
2. Contribution order within each extension's manifest
3. Reserved contributions appear after active ones with disabled diagnostics

### 4.4 Disabled contributions

Disabled contributions produce `InactiveReservedContribution` descriptors with:
- Structured diagnostic (code: `runtime/contribution-disabled`)
- Preserved contribution metadata (ID, kind, order)
- No renderer or execution handle

---

## 5. Diagnostic Contract

### 5.1 Shape

Every diagnostic follows the `ExtensionDiagnostic` interface:

```typescript
interface ExtensionDiagnostic {
  severity: 'error' | 'warning' | 'info';
  code: string;        // Dot-separated, extension-scoped
  message: string;     // Human-readable
  extensionId?: string; // Pinned by lifecycle host
  contributionId?: string;
  source?: DiagnosticSource; // Pinned to 'extension' by lifecycle host
  milestone?: string;
  detail?: Record<string, unknown>;
}
```

**Canonical path:** `src/sdk/index.ts` → `ExtensionDiagnostic`, `DiagnosticSource`

### 5.2 Source pinning

The lifecycle host pins `source: DIAGNOSTIC_SOURCE_EXTENSION` and overwrites any caller-supplied `extensionId`. Extensions cannot spoof diagnostic provenance.

**Canonical path:** `src/tools/video-editor/runtime/extensionLifecycle.ts` → `createExtensionDiagnosticsService().report()`

### 5.3 Collection

Host-owned `DiagnosticCollection` aggregates per-extension diagnostics with:
- Per-extension capacity (default 100, oldest-first eviction)
- `publish()`, `remove()`, `removeByExtensionId()`, `clear()`
- `subscribe()` for reactive UI updates
- Frozen snapshots for safe iteration

**Canonical path:** `src/sdk/index.ts` → `createDiagnosticCollection()`

### 5.4 Disposal cleanup

When an extension is disposed, `disposeAll()` in the lifecycle host calls `removeByExtensionId()` on the collection. Extension diagnostics do not survive lifecycle disposal.

---

## 6. Error Boundary Contract

### 6.1 ContributionErrorBoundary

The base class component (`src/tools/video-editor/runtime/ContributionErrorBoundary.tsx`) provides:

- **Error catching**: catches React render errors within the boundary subtree
- **Fallback UI**: preserved existing fallback appearance with error message and "View diagnostics" action
- **Recovery key**: when provided, resets error state only on key change (not children change)
- **Legacy fallback**: when no recovery key, resets on children identity change

### 6.2 HostContributionErrorBoundary

The function component wrapper (`src/tools/video-editor/runtime/ContributionErrorBoundary.tsx` → `HostContributionErrorBoundary()`) adds:

- **Owner resolution**: reads `extensionId` prop, looks up host-owned recovery key via `runtime.getRecoveryKey(extensionId)`
- **Bounded auto-retry**: max 3 retries with 5-second debounce when recovery key changes
- **Null safety**: returns `"0"` when runtime is unavailable, extensionId is missing, or extension is unknown/disposed
- **Fallback**: when no extensionId, falls back to legacy children-change reset

### 6.3 Retry lifecycle

```
Error caught → fallback rendered → diagnostic published
  ↓
recoveryKey changes (manifest change, re-add, explicit retry)
  ↓
boundary resets → children re-render
  ↓ (if crashes again)
retry counter incremented → debounce timer starts
  ↓ (after debounce)
boundary resets again → up to maxRetries (3)
  ↓ (exhausted)
fallback stays rendered until next recoveryKey change
```

---

## 7. Recovery Key System

### 7.1 Ownership

Recovery keys are **lifecycle-host-owned**. The `ExtensionLifecycleHost` (`src/tools/video-editor/runtime/extensionLifecycle.ts`) maintains a `Map<string, number>` per extension ID.

### 7.2 Key lifecycle

| Event | Key behavior |
|---|---|
| First activation | Key initialized to `"1"` |
| Manifest change (different manifest reference) | Key incremented |
| Re-add (same ID, previously removed) | Key incremented |
| Unchanged synchronize | Key **stable** (no increment) |
| Explicit retry (`incrementRecoveryKey()`) | Key incremented; returns `"0"` for unknown/disposed/removed extensions |
| Extension removed | Key entry deleted |

### 7.3 Facade

`VideoEditorRuntimeContextValue` (`src/tools/video-editor/contexts/DataProviderContext.tsx`) exposes `getRecoveryKey` and `incrementRecoveryKey` as optional methods, backed by the lifecycle host via thin delegation with null-safety.

---

## 8. Package Inventory Contract

### 8.1 Entry shape

Every package visible in the Extension Manager is represented as a `PackageStateInventoryEntry`:

```typescript
interface PackageStateInventoryEntry {
  extensionId: string;
  packageState: PackageState;      // 'loaded' | 'disabled-by-user' | 'error' | ...
  stateReason: string;
  packageMetadata: PackageMetadata;
  manifestContributions?: ExtensionContribution[];
  contributionSummary?: PackageContributionSummary;
}
```

**Canonical path:** `src/tools/video-editor/runtime/extensionSurface.ts` → `PackageStateInventoryEntry`

### 8.2 Contribution summary

`computePackageContributionSummary()` derives a frozen summary from manifest contributions:

```typescript
interface PackageContributionSummary {
  declaredCount: number;
  activeCount: number;
  inactiveCount: number;
  kindLabels: string[];     // Sorted alphabetically
  contributionIdsByKind: Record<string, string[]>;
}
```

This summary survives without active runtime descriptors — disabled/error packages still show their declared contribution shape.

**Canonical path:** `src/tools/video-editor/runtime/extensionSurface.ts` → `computePackageContributionSummary()`

### 8.3 Direct vs managed entries

- **Direct (host-supplied) entries**: synthesized in `useExtensionLoaderWiring.ts` when no repository is provided. `stateReason: 'Direct host-supplied extension'`, read-only in the manager, no install/update/toggle affordances.
- **Managed (repository-backed) entries**: produced by `ExtensionLoader.load()`. Full enable/disable and state tracking.

**Canonical path:** `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts`

---

## 9. Settings Contract

### 9.1 Storage backend

Extension settings are backed by the provider (`SupabaseProviderStore` in production, `LocalStorageProviderStore` for local/direct extensions) with localStorage as the fallback.

### 9.2 Key scoping

All extension settings keys are scoped to `reigh.ext.<extensionId>.*` in localStorage, preventing cross-extension key collisions.

### 9.3 Cleanup

On dispose, `disposeHostServices()` (attached via `CONTEXT_DISPOSE_SYMBOL`) removes all localStorage keys written during activation. Settings from disposed extensions do not persist.

**Canonical path:** `src/tools/video-editor/runtime/extensionLifecycle.ts` → `disposeHostServices()`

---

## 10. Export Guard Contract

### 10.1 Pre-render scan

`runExportGuard()` (`src/tools/video-editor/runtime/renderability.ts`) scans the timeline before render/export for:

- Unknown clip types, effects, and transitions → **error** diagnostics → export blocked
- Extension-declared IDs from inactive contributions → **warning** diagnostics
- Missing transition IDs → **error** diagnostics
- Active live sources → **error** diagnostics (must bake before export)

### 10.2 Extension-declared ID recognition

Active extension-declared clip types, effects, and transitions are recognized by the export guard. Unknown IDs (no declaring extension) block export.

---

## 11. Provider Compatibility

Three data providers share the same extension lifecycle and contribution contracts:

| Provider | Support | Source |
|---|---|---|
| InMemory | Full | `src/tools/video-editor/data/InMemoryDataProvider.ts` |
| Supabase | Full | `src/tools/video-editor/data/SupabaseDataProvider.ts` |
| Astrid Bridge | Partial | `src/tools/video-editor/data/AstridBridgeDataProvider.ts` |

Extensions do not interact with providers directly. The public `TimelineReader.snapshot()` and `TimelineOps.apply()` interfaces abstract over provider differences.

---

## 12. Contract Boundaries: What Extensions Can and Cannot Do

### 12.1 Allowed

| Capability | Access path |
|---|---|
| Render contributions to host slots | `defineExtension()` → manifest contributions |
| Publish structured diagnostics | `ctx.services.diagnostics.report()` |
| Read/write scoped settings | `ctx.services.settings` |
| Display toasts/progress | `ctx.chrome.toast()`, `ctx.chrome.progress()` |
| Register commands and keybindings | `ctx.commands` |
| Register effects, transitions, clip types | `ctx.effects`, `ctx.transitions`, `ctx.clipTypes` |
| Register shaders | `ctx.shaders` |
| Register agent tools | `ctx.agentTools` |
| Read/manipulate timeline | `ctx.creative` (TimelineReader, TimelineOps, proposals) |
| Read i18n messages | `ctx.services.i18n` |
| Access browser APIs | Unrestricted (same origin) |

### 12.2 Not available (deferred or unsupported)

| Capability | Posture |
|---|---|
| Spawn local processes | `ctx.services.invokeProcess()` returns structured not-available diagnostic |
| Dynamic package loading | No `import()` for extension code; statically bundled only |
| Marketplace installation | Not present |
| Remote extension updates | Not present |
| Sandboxed execution | Not present |
| Permission enforcement | Not present (manifest permissions are descriptive only) |
| Direct `DataProvider` access | Not exposed through `ExtensionContext` |
| Internal `applyEdit` or mutation escape hatches | Not exposed |

---

## 13. Code Path Index

| Contract | Primary file(s) |
|---|---|
| Extension definition | `src/sdk/index.ts` (`defineExtension`, `validateExtensionId`) |
| Lifecycle state machine | `src/tools/video-editor/runtime/extensionLifecycle.ts` (`createExtensionLifecycleHost`) |
| Runtime normalization | `src/tools/video-editor/runtime/extensionSurface.ts` (`normalizeExtensionRuntime`) |
| Contribution surfaces (slots) | `src/tools/video-editor/components/TimelineEditorShellCore.tsx` |
| Contribution surfaces (inspector) | `src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx` |
| Contribution surfaces (asset panel) | `src/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface.tsx` |
| Contribution surfaces (clip panel) | `src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx` |
| Error boundary (base) | `src/tools/video-editor/runtime/ContributionErrorBoundary.tsx` (`ContributionErrorBoundary`) |
| Error boundary (host wrapper) | `src/tools/video-editor/runtime/ContributionErrorBoundary.tsx` (`HostContributionErrorBoundary`) |
| Diagnostic collection | `src/sdk/index.ts` (`createDiagnosticCollection`) |
| Diagnostic provenance | `src/tools/video-editor/runtime/extensionLifecycle.ts` (`createExtensionDiagnosticsService`) |
| Recovery key registry | `src/tools/video-editor/runtime/extensionLifecycle.ts` (`getRecoveryKey`, `incrementRecoveryKey`) |
| Recovery key facade | `src/tools/video-editor/contexts/DataProviderContext.tsx` (`VideoEditorRuntimeContextValue`) |
| Package inventory | `src/tools/video-editor/runtime/extensionSurface.ts` (`PackageStateInventoryEntry`, `computePackageContributionSummary`) |
| Extension loader | `src/tools/video-editor/runtime/extensionLoader.ts` (`createExtensionLoader`) |
| Loader wiring | `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts` |
| Settings service | `src/sdk/extensionSettingsService.ts` (`createExtensionSettingsService`) |
| Settings storage | `src/tools/video-editor/runtime/extensionStateRepositoryProvider.ts` |
| Extension Manager UI | `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx` |
| Export guard | `src/tools/video-editor/runtime/renderability.ts` (`runExportGuard`) |
| Provider compatibility | `src/tools/video-editor/data/InMemoryDataProvider.ts`, `SupabaseDataProvider.ts`, `AstridBridgeDataProvider.ts` |
| Public SDK boundary (governance) | `config/governance/sdk-public-export-allowlist.json` |

---

## 14. Version History

| Date | Change |
|---|---|
| 2026-06-24 | Initial foundation contracts document for M5. Covers extension definition, lifecycle, contribution surfaces, runtime normalization, diagnostics, error boundaries, recovery keys, package inventory, settings, export guard, provider compatibility, allowed/restricted capabilities, and a complete code path index. |
