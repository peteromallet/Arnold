# Extension Platform — Supported V1 & Deferred/Unsupported Behavior

**Status:** Active (M15)
**Last updated:** 2026-07-07
**Scope:** Every V1 extension-platform behavior classified as `supported` or `deferred`, with concrete evidence links to tests, examples, absence checks, blockers, or contract-recheck row IDs.

---

## 1. Purpose

This matrix is the canonical reference for what the Reigh extension platform **supports in V1** and what is **explicitly deferred**. Every row links to concrete implementation evidence discoverable in the repository — tests, compiled examples, absence checks, blocker entries, or contract-recheck row IDs. No row relies on aspirational prose.

This document is the downstream consumer of the [M15 Contract-Recheck Matrix](./extension-platform-contract-recheck.md). The gate semantics are governed by the shared matrix helper (SD1) and the rule that deferred behavior is a valid terminal classification only when backed by absence checks or an explicit release blocker (SD2).

### 1.1 Classification definitions

| Classification | Meaning |
|---|---|
| **supported** | The behavior is implemented, testable, and has concrete evidence in the repository. |
| **deferred** | The behavior is explicitly documented as out-of-scope for V1, backed by an absence check, a blocker entry, or a contract-recheck row. |
| **unsupported** | The behavior is not implemented and no V1 plan exists. |
| **release-blocking** | The gap is serious enough to block a V1 release. |

### 1.2 Evidence link types

| Evidence type | Format | Example |
|---|---|---|
| Contract-recheck row | `CR:<RowID>` | `CR:M1-001` |
| Test file | `TEST:<path>` | `TEST:src/sdk/__tests__/sdk-boundary.test.ts` |
| Example file | `EX:<path>` | `EX:src/examples/toolbar-example.ts` |
| Extension example | `EXT:<path>` | `EXT:src/tools/video-editor/examples/extensions/flagship-local/` |
| Doc reference | `DOC:<path>§<section>` | `DOC:provider-compatibility-matrix.md§3` |
| Absence check | `ABSENCE:<grep pattern>` | `ABSENCE:grep -r 'marketplace' src/sdk/` |
| Blocker entry | `BLOCKER:<ID>` | `BLOCKER:B-001` |
| Deferral entry | `DEFER:<ID>` | `DEFER:D-001` |

---

## 2. Supported V1 Behavior Matrix

### 2.1 SDK Scaffold & Public Boundary

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-001 | `@reigh/editor-sdk` is the only public import path for extensions | **supported** | CR:M0-001, CR:X-001, CR:X-004; TEST:src/sdk/__tests__/sdk-boundary.test.ts (2023 lines) |
| S-002 | Package aliases resolve `@reigh/editor-sdk` → `src/sdk/index.ts` | **supported** | CR:M0-002; vitest.config.ts, tsconfig.json, vite.config.ts |
| S-003 | SDK boundary test runs without importing editor internals | **supported** | CR:M0-003; TEST:src/sdk/__tests__/sdk-boundary.test.ts |
| S-004 | ID validation for extension and contribution IDs | **supported** | CR:M0-001; `validateExtensionId()`, `validateContributionId()` in `src/sdk/index.ts` |
| S-005 | `DisposeHandle` contract (idempotent, must not throw) | **supported** | CR:M5-011; `DisposeHandle` interface in `src/sdk/index.ts` |
| S-006 | Diagnostic system (severity, codes, source ranges, collections) | **supported** | CR:M2-005; `Diagnostic`, `DiagnosticSourceRange`, `DiagnosticCollection` in `src/sdk/index.ts` |

### 2.2 Extension Runtime & Lifecycle

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-010 | Local extension import, registration, toolbar rendering, Fast Refresh, removal without leaks | **supported** | CR:M1-001; EXT:flagship-local/; TEST:VideoEditorProvider.test.tsx |
| S-011 | Extension failure is visible and contained via `ContributionErrorBoundary` | **supported** | CR:M1-002; DOC:frontend-closure-checklist.md§3.2; `ContributionErrorBoundary` in `TimelineEditorShellCore.tsx` |
| S-012 | Provider-scoped extension lifecycle (activate, deactivate, dispose) | **supported** | CR:M1-005; TEST:EditorRuntimeProvider.test.tsx |
| S-013 | Extension removal from provider props unregisters contributions | **supported** | CR:M1-010; TEST:EditorRuntimeProvider.test.tsx |
| S-014 | `ExtensionContext` exposes no raw `DataProvider`, no `applyEdit`, no internal mutation escape hatch | **supported** | CR:M1-014, CR:X-002; `ExtensionContext` shape in `src/tools/video-editor/runtime/` |
| S-015 | HMR-safe re-registration and stale component cleanup | **supported** | CR:M5-003; provider-scoped lifecycle with `DisposeHandle` |
| S-016 | Activation/deactivation wrapped in visible console grouping | **supported** | DOC:extensions-trust-envelope.md§4; `console.groupCollapsed`/`console.groupEnd` in lifecycle host |
| S-017 | Lifecycle teardown failures captured as diagnostics, never thrown | **supported** | DOC:extensions-trust-envelope.md§2 (Dispose row); `lifecycle/teardown-error` diagnostics |
| S-018 | Minimal manifest-only extension compiles and exports through public SDK | **supported** | CR:M0-001; EX:hello-world-extension.ts |
| S-019 | Settings schema-version migration declaration and handler | **supported** | CR:M1-007; EX:settings-migration-example.ts |

### 2.3 Contribution Surfaces & Host Slots

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-020 | Public surface classes: toolbar, inspector, overlay, status, code panel, dialogs | **supported** | CR:M2-001; EX:toolbar-example.ts, toolbar-extension.ts, inspector-example.ts, overlay-example.ts, status-surface-example.ts, code-panel-diagnostics-example.ts, surface-coverage.ts |
| S-021 | Inspector and overlay contributions update on host state changes | **supported** | CR:M2-003; EX:inspector-example.ts, overlay-example.ts; TEST:Canary.test.tsx |
| S-022 | `SchemaForm` renders and validates common schema subset; ExtensionManager falls back to raw key-value editing only for schemaless/legacy packages (intentional) | **supported** | CR:M2-006; `SchemaForm` host primitive; `src/sdk/index.ts` parameter schema types; T10 |
| S-023 | Diagnostic fallback links open `DiagnosticPanel` filtered to failing extension | **supported** | CR:M2-008; DOC:frontend-closure-checklist.md§3.2 |
| S-024 | Code panel canary publishes structured diagnostics with source ranges | **supported** | CR:M2-010, CR:M2-011; EX:code-panel-diagnostics-example.ts; TEST:Canary.test.tsx |
| S-025 | Reserved frontend component slots compile as inert placeholders | **supported** | CR:M2-013; `InertReservedPlaceholder` in `TimelineEditorShellCore.tsx` |
| S-026 | Writing/script and canvas/stage canaries demonstrate non-timeline-native workflows | **supported** | CR:M2-014; EX:writing-canary-example.ts, stage-canary-example.ts |
| S-027 | Frontend closure checklist documented and applied to at least one primitive | **supported** | CR:M2-012, CR:X-008; DOC:frontend-closure-checklist.md |

### 2.4 TimelinePatch & Proposal System

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-030 | Safe insert/update/delete/reorder clips and update tracks/assets through `TimelineOps` | **supported** | CR:M3-001; TEST:timeline-patch.test.ts (241 tests); DOC:timeline-patch-operations.md§3 |
| S-031 | Proposal preview without mutating the real timeline | **supported** | CR:M3-002; TEST:proposal-runtime.test.ts (39 tests) |
| S-032 | Accept/reject with stale base version detection | **supported** | CR:M3-003; TEST:proposal-runtime.test.ts; `TimelineVersionConflictError` |
| S-033 | Undo/rollback for patch batches | **supported** | CR:M3-004; TEST:timeline-patch.test.ts |
| S-034 | Relative/fractional ordering for clip positioning | **supported** | CR:M3-005; DOC:timeline-patch-operations.md§3.8 |
| S-035 | Provider version behaviors tested (InMemory, Supabase, Astrid) | **supported** | CR:M3-007; DOC:provider-compatibility-matrix.md§3.3; TEST:AstridBridgeDataProvider.test.ts (22 pass) |
| S-036 | Rapid compiler iteration: atomic proposal replacement from same source | **supported** | CR:M3-008; TEST:proposal-runtime.test.ts |
| S-037 | Golden patch replay across providers | **supported** | CR:M3-009; TEST:timeline-golden-replay.test.ts (81 tests) |
| S-038 | Patch extension mechanism with validation, serialization, previewability | **supported** | CR:M3-011; DOC:timeline-patch-operations.md§7 |
| S-039 | Extension project-data persistence, oversized payload rejection with diagnostics | **supported** | CR:M3-012; DOC:timeline-patch-operations.md§3.11; TEST:source-map-runtime.test.ts |
| S-040 | Source-to-timeline and timeline-to-source navigation metadata | **supported** | CR:M3-014; TEST:source-map-runtime.test.ts (31 tests) |

### 2.5 Commands, Keybindings & Context Menus

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-050 | Command, keybinding, palette entry, and context menu contributions | **supported** | CR:M4-001; EX:command-extension.ts; `CommandContribution`, `KeybindingContribution`, `ContextMenuItemContribution` in SDK |
| S-051 | Deterministic shortcut conflict resolution (first-registered-wins) | **supported** | CR:M4-002; `src/sdk/index.ts` command types |

### 2.6 Provider-Scoped Registry & Trusted Loader

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-060 | Provider contract tests across InMemory instances | **supported** | CR:M5-002; TEST:InMemoryDataProvider.test.ts (13 tests) |
| S-061 | Legacy effects still render and remain editable | **supported** | CR:M5-004; TEST:effect-catalog.test.ts |
| S-062 | Missing effect/transition/clip-type IDs produce clear diagnostics and export blockers | **supported** | CR:M5-005; `runExportGuard()` in `src/tools/video-editor/runtime/renderability.ts` |
| S-063 | Renderability metadata available to export guards | **supported** | CR:M5-006; `RenderCapability`, `ContributionRenderability`, `RenderBlocker` in `src/sdk/index.ts` |
| S-064 | Registry diagnostics visible in diagnostic panel/status surface | **supported** | CR:M5-007; `DiagnosticCollection` and `DiagnosticPanel` integration |
| S-065 | Shared vocabulary: `RenderMaterialRef`, locator, media kind, determinism, replacement policy | **supported** | CR:M5-010; `src/sdk/index.ts`; DOC:shader-execution-model.md |

### 2.7 Asset Metadata & Parser Contributions

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-070 | Asset parser enriches uploaded assets | **supported** | CR:M6-001; EX:integrity-hash-parser-example.ts |
| S-071 | Metadata persisted per extension, namespaced by extension ID | **supported** | CR:M6-002; `AssetRegistryEntry.metadata` in `src/tools/video-editor/` |
| S-072 | Asset search/filter via contributed metadata facets | **supported** | CR:M6-003; `MetadataFacetContribution`, `SearchProviderContribution` in SDK |
| S-073 | Astrid local-first demo: extension mutation and persistence | **supported** | CR:M6-004; TEST:AstridBridgeDataProvider.test.ts (22 pass) |
| S-074 | Compile-only export in export UI/command surface | **supported** | CR:M6-005; EX:metadata-json-output-example.ts |
| S-075 | Render-dependent output formats declared early appear disabled with diagnostics | **supported** | CR:M6-006; `requiresRender: true` → disabled/reserved |
| S-076 | Parser rejection for unsupported MIME/type, oversized input | **supported** | CR:M6-008; `ParserContribution` with `acceptMimeTypes`, `acceptExtensions`, `maxBytes` |

### 2.8 Component Effect Contributions

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-080 | Extension contributes component effect visible in picker and applicable to clips | **supported** | CR:M7-001; EXT:flagship-local/FlagshipEffectComponent.tsx |
| S-081 | Effect renders in preview and responds to Fast Refresh | **supported** | CR:M7-002; HMR-safe provider-scoped registry |
| S-082 | Params editable through parameter-schema UI | **supported** | CR:M7-003; effect parameter schema reuse |
| S-083 | Export guard blocks unsupported worker export with clear reason | **supported** | CR:M7-004; `allowBrowserExport`/`allowWorkerExport` in SDK |
| S-084 | Applied contributed effects removable, resettable, survive undo/redo | **supported** | CR:M7-005; remove/reset controls via history system |
| S-085 | Effect contribution manifest and registration example | **supported** | CR:M7-001; EX:effect-example.ts |

### 2.9 Transition Contributions

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-090 | Extension transition selectable, configurable, persisted, rendered, repairable | **supported** | CR:M8-001; EXT:__tests__/flagship-local-transition.test.ts |
| S-091 | Missing transition IDs produce diagnostics and export blockers | **supported** | CR:M8-003; export guard integration |
| S-092 | Transition contribution manifest and registration example | **supported** | CR:M8-001; EX:transition-example.ts |

### 2.10 Clip-Type Dispatch & Keyframes

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-100 | Extension clip type inserted, inspected, persisted, rendered, export-guarded | **supported** | CR:M9-001; EX:clip-type-keyframed-example.ts; TEST:ClipTypeRegistry.test.ts, clip-types/registry.test.ts, clip-types/runtime.test.ts |
| S-101 | Keyframed params persist and interpolate | **supported** | CR:M9-002; `Keyframe<T>` schema; EX:clip-type-keyframed-example.ts |
| S-102 | Missing IDs, defaults, renderer dispatch, keyframe interpolation tests | **supported** | CR:M9-003; TEST:ClipTypeRegistry.test.ts, clip-types/defineClipType.test.ts, clip-types/manifest.test.ts |
| S-103 | Procedural clip example proves keyframe schema and inspector loop | **supported** | CR:M9-005; EX:clip-type-keyframed-example.ts |
| S-104 | Automation recording canary converts sampled values into deterministic keyframes | **supported** | CR:M9-006; EX:automation-recording-canary.ts |
| S-105 | Stepped/hold interpolation for control-style automation | **supported** | CR:M9-007; keyframe interpolation modes in SDK |

### 2.11 Agent Tool Contributions

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-110 | Agent tool produces proposal; user can preview/accept/reject | **supported** | CR:M10-001; EXT:agent-tools-canary/, agent-tools-copilot/, agent-tools-export/ |
| S-111 | Tool registry is provider-scoped and HMR-safe | **supported** | CR:M10-003; provider-scoped registry pattern |
| S-112 | `invokeProcess` stub returns structured not-available diagnostic | **supported** | CR:M10-007; `src/sdk/index.ts` |
| S-113 | Agent tool contribution manifest and handler registration example | **supported** | CR:M10-001; EX:agent-tool-example.ts |
| S-114 | Process manifest declaration example (execution deferred) | **supported** | CR:M10-007; EX:process-example.ts |

### 2.12 Live Data Bridge

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-120 | Live data example updates preview from ring buffer | **supported** | CR:M11-001; EXT:live-webcam-canary/, live-generated-frame-canary/; TEST:__tests__/live-data-bridge.integration.test.tsx |
| S-121 | Timeline mutation/history does not grow per sample | **supported** | CR:M11-002; ring-buffer sample delivery outside history |
| S-122 | Bake creates deterministic data: assets, keyframes, automation clips, sidecars, RenderMaterial refs | **supported** | CR:M11-003; bake semantics in runtime |
| S-123 | Export blocked before bake, follows normal route after bake | **supported** | CR:M11-004; export guard detects active live sources |
| S-124 | Live source declaration and registration example | **supported** | CR:M11-001; EX:live-preview-example.ts |

### 2.13 Shader & WebGL Bridge

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-130 | Shader example renders in browser preview with configurable uniforms | **supported** | CR:M13-001; EXT:clip-local-shader-canary/, postprocess-shader-canary/; TEST:__tests__/clip-local-shader-canary.integration.test.tsx, postprocess-shader-canary.integration.test.tsx |
| S-131 | Shader execution model RFC checked in with implementation | **supported** | CR:M13-002; DOC:shader-execution-model.md |
| S-132 | Invalid shader source produces structured diagnostics without crashing preview | **supported** | CR:M13-003; shader compilation at registration time |
| S-133 | Shader registration, compile diagnostics, picker selection, uniform editing tests | **supported** | CR:M13-004; TEST:clip-local-shader-canary.integration.test.tsx, postprocess-shader-canary.integration.test.tsx |
| S-134 | V1 composition limits documented (one shader per clip/postprocess, no multi-shader stacks) | **supported** | CR:M13-006; DOC:shader-execution-model.md |
| S-135 | Supported uniform types with diagnostics for unsupported types | **supported** | CR:M13-008; float, int, bool, vec2-4, color, enum, texture, frame/time bindings in SDK |

### 2.14 Provider Compatibility

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-140 | InMemory provider: full M3 support, ephemeral Map-backed | **supported** | CR:M3-007; DOC:provider-compatibility-matrix.md§2; TEST:InMemoryDataProvider.test.ts (13 tests) |
| S-141 | Supabase provider: full M3 support, durable DB + append service | **supported** | CR:M3-007; DOC:provider-compatibility-matrix.md§2; TEST:SupabaseDataProvider.test.ts (18 tests) |
| S-142 | Astrid Bridge provider: partial M3 support, local filesystem + bridge API | **supported** | CR:M3-007; DOC:provider-compatibility-matrix.md§§2,4.3; TEST:AstridBridgeDataProvider.test.ts (22 pass) |
| S-143 | Provider compatibility matrix fully documented | **supported** | CR:M3-010, CR:X-007; DOC:provider-compatibility-matrix.md |

### 2.15 Cross-Cutting Platform Guarantees

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-150 | V1 trust envelope documented and honest (trusted-local execution) | **supported** | CR:X-003; DOC:extensions-trust-envelope.md |
| S-151 | No new platform primitives added beyond explicitly bridged kinds | **supported** | CR:X-005; `contribution_kind_not_yet_bridged` diagnostics |
| S-152 | Public SDK boundary guard: no internal provider/mutation leaks from SDK entrypoints | **supported** | CR:X-002; `@publicContract` annotation in `src/sdk/index.ts` |
| S-153 | Source-pack/package contract freeze for manifest format | **supported** | CR:X-009; 8 `reigh-extension.json` files with consistent format |
| S-154 | `npm run test:sdk-boundary` passes | **supported** | CR:M0-003; `src/sdk/__tests__/sdk-boundary.test.ts` |
| S-155 | `npm run build` passes with docs-linked examples | **supported** | CR:X-001; sdk-boundary.test.ts verifies public alias |

### 2.16 Extension Manager, Persistence & Cleanup

*Delivered as proof points across T5 (cleanup), T9 (enable/disable cycle with persistence), and T10 (SchemaForm settings editing). The manager UI, persisted enablement, persisted settings, and lifecycle cleanup are supported; installation, update, and deletion remain deferred (see D-001).*

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| S-160 | Extension manager UI: enable/disable toggle with immediate contribution visibility change | **supported** | CR:M14-001 (partial); TEST:ExtensionManager.test.tsx (T10 — settings editing); TEST:ExtensionHarnessPage.tsx manager-cycle scenario (T9); `ExtensionManager.tsx` enable/disable controls |
| S-161 | Settings editing via `SchemaForm` for schema-backed packages with intentional key-value fallback for schemaless/legacy packages | **supported** | CR:M14-001 (partial); TEST:ExtensionManager.test.tsx (T10 — 7 tests for SchemaForm vs fallback split); `ExtensionManager.tsx` lines 828–853 |
| S-162 | Persisted extension enablement state via repository-backed persistence (`DataProvider.createExtensionPersistenceService`) | **supported** | CR:M14-003 (partial); TEST:extensionStateRepository.test.ts; TEST:ExtensionHarnessPage.tsx manager-cycle scenario (T9 — `extension-manager-cycle-persisted-enablement` probe); `EditorRuntimeProvider.tsx` persistence wiring |
| S-163 | Persisted extension settings via `InMemoryDataProvider` and `SupabaseDataProvider` persistence services | **supported** | CR:M14-003 (partial); TEST:InMemoryDataProvider.extensionPersistence.test.ts; TEST:SupabaseDataProvider.test.ts (persistence); `DataProvider.createExtensionPersistenceService` |
| S-164 | Activation lifecycle cleanup disposes renderer registrations and never mutates stale state | **supported** | CR:M5-011, M5-012 (partial); TEST:extensionSmoke.test.ts (T5 — disposal on deactivation); TEST:extensionRenderSurface.test.ts (T5 — renderer unregistration); `internalExtensionRenderSurface.ts` |

---

## 3. Deferred / Unsupported V1 Behavior Matrix

### 3.1 Extension Packaging & Manager (M14)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-001 | Extension installation, update, and deletion from manager UI | **deferred** | CR:M14-001; BLOCKER:B-001; ABSENCE:grep -rE 'installExtension|uninstallExtension|deleteExtension|removeExtension' src/tools/video-editor/components/ExtensionManager/ |
| D-002 | Failed extension load recovery and automated diagnostic triage | **deferred** | CR:M14-003; BLOCKER:B-001 |
| D-003 | Integrity mismatch prevents installation/activation | **deferred** | CR:M14-004; BLOCKER:B-001; DOC:extensions-trust-envelope.md§6 (planned M4–M5) |
| D-004 | Extension state persistence, workspace pack load, bundle pack validation | **deferred** | CR:M14-005; BLOCKER:B-001 |
| D-005 | Migration diagnostics for older metadata shapes | **deferred** | CR:M14-006; BLOCKER:B-001 |
| D-006 | Local-source-to-installed-pack migration (settings/data preservation) | **deferred** | CR:M14-007; BLOCKER:B-001 |
| D-007 | Manager trust warnings and extension requirements/lock metadata for installed packs | **deferred** | CR:M14-008; BLOCKER:B-001; DOC:extensions-trust-envelope.md |
| D-008 | Provider-backed extension state repository | **deferred** | CR:M14-009; BLOCKER:B-001 |
| D-009 | Extension dependency diagnostics, optional dependency degradation | **deferred** | CR:M14-010; BLOCKER:B-001 |
| D-010 | Conflict override UI, dependency tree badges, uninstall reference report | **deferred** | CR:M14-011; BLOCKER:B-001 |

### 3.2 Render Planner & Export Infrastructure (M12)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-020 | Full render planner implementation with capability/blocker reports | **supported** | CR:M12-001; TEST:src/tools/video-editor/runtime/renderPlanner.test.ts; TEST:src/tools/video-editor/runtime/exportGuard.test.ts; `src/tools/video-editor/runtime/renderPlanner.ts`; `src/tools/video-editor/runtime/exportGuard.ts` |
| D-021 | Export UI surfaces for clear reasons and next actions | **deferred** | CR:M12-002; BLOCKER:B-002 |
| D-022 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` | **supported** | CR:M12-007; TEST:src/tools/video-editor/runtime/composition/shaderRefAuthority.test.ts; `src/tools/video-editor/runtime/renderPlanner.ts`; `src/tools/video-editor/runtime/exportGuard.ts`; `src/tools/video-editor/lib/timeline-reader.ts` |
| D-023 | Process/sidecar/roundtrip execution tests | **deferred** | CR:M12-004 through M12-013; DEFER:D-004 |
| D-024 | Artifact manifest provenance, input hash propagation | **deferred** | CR:M12-005; DEFER:D-004 |
| D-025 | Multi-artifact dataset/show-control export with sidecar manifest | **deferred** | CR:M12-006; DEFER:D-004 |
| D-026 | Mock MCP-style process invocation via `ctx.services.invokeProcess` | **deferred** | CR:M12-012; DEFER:D-004 |
| D-027 | JSON-RPC correlation, progress, cancellation for processes | **deferred** | CR:M12-013; DEFER:D-004 |

### 3.3 Live Data Bridge — Frontend Coverage (M11)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-030 | Live data frontend state coverage (permission, error, bake-ready) for canary sources | **deferred** | CR:M11-006; BLOCKER:B-003 |
| D-031 | Clips/effects reading reserved live-source IDs: diagnostics before activation, references after bake | **deferred** | CR:M11-007; BLOCKER:B-003 |
| D-032 | Progressive generated-frame replacement, cancellation, bake into deterministic assets | **deferred** | CR:M11-008; BLOCKER:B-003 |
| D-033 | Microphone/MIDI/device sample streams baking into deterministic keyframes | **deferred** | CR:M11-009; BLOCKER:B-003 |
| D-034 | Steering/reconfigure diagnostics and live-source-to-uniform binding metadata | **deferred** | CR:M11-010; BLOCKER:B-003 |
| D-035 | `GenerationSession` live sample delivery, supersede/fork, partial bake, learn-mode mapping | **deferred** | CR:M11-011; BLOCKER:B-003 |
| D-036 | Session panel rendering, steering fork/supersede UI, partial-bake range selection, recording strip | **deferred** | CR:M11-012; BLOCKER:B-003 |
| D-037 | Lifecycle cleanup on permission failure | **deferred** | CR:M11-005; BLOCKER:B-003 |

### 3.4 Agent Tool — Frontend & Edge Cases (M10)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-040 | Agent tool workflow validation, stale base rejection, failure diagnostics (tests) | **deferred** | CR:M10-002; DEFER:D-003 |
| D-041 | Frontend invocation, schema validation UI, progress/cancel, proposal creation tests | **deferred** | CR:M10-005; DEFER:D-003 |
| D-042 | Copilot prompt invocation, context preview trimming, invocation history | **deferred** | CR:M10-006; DEFER:D-003 |
| D-043 | Fake long-running generation canary E2E (invoke, progress, cancel, proposal-ready) | **deferred** | CR:M10-008; DEFER:D-003 |
| D-044 | `GenerationSession` contract tests (progress, cancellation, sample channel, bake metadata) | **deferred** | CR:M10-009; DEFER:D-003 |
| D-045 | Copilot canary: timeline snapshot reading, proposal rationale before acceptance | **deferred** | CR:M10-010; DEFER:D-003 |
| D-046 | Export-adjacent snapshot canary: export-blocker context in request payload | **deferred** | CR:M10-011; DEFER:D-003 |
| D-047 | Live-channel handle typed and diagnosed as preview-only (pre-M11) | **deferred** | CR:M10-004; `GenerationSession` handle shape with placeholder channels |

### 3.5 Commands — Full Test Coverage (M4)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-050 | Command registry tests: `when` predicates, disabled commands, target context, mutation failure | **deferred** | CR:M4-003; DEFER:D-001 |
| D-051 | Automated tests for shortcut precedence and duplicate command/keybinding conflicts | **deferred** | CR:M4-004; DEFER:D-001 |
| D-052 | Palette search/navigation/invoke, stale target context, unregister lifecycle, command failure diagnostics tests | **deferred** | CR:M4-005; DEFER:D-001 |

### 3.6 Asset Metadata — Frontend Rendering (M6)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-060 | End-to-end test: parser + compile-only export, ingest, persist, export | **deferred** | CR:M6-007; DEFER:D-002 |
| D-061 | Consent/provenance metadata persistence and export into sidecar | **deferred** | CR:M6-009; DEFER:D-002 |
| D-062 | Deferred enrichment record round-trip through asset metadata | **deferred** | CR:M6-010; DEFER:D-002 |
| D-063 | Enrichment status persistence, asset-panel/search-surface display, stub search provider result merge | **deferred** | CR:M6-011; DEFER:D-002 |
| D-064 | Metadata facet rendering, search result badges, enrichment claim detail, provenance chain rendering | **deferred** | CR:M6-012; DEFER:D-002 |

### 3.7 Provider Registry — Edge Cases (M5)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-070 | Provider isolation tests: two simultaneous editor instances | **deferred** | CR:M5-001; DEFER:D-005 |
| D-071 | Host-visible canary: registry record, renderability status, planner-compatible blocker/finding | **deferred** | CR:M5-008; DEFER:D-005 |
| D-072 | Minimal planner skeleton aggregating registry blockers into status/diagnostics surfaces | **deferred** | CR:M5-009; DEFER:D-005 |
| D-073 | Disabling extension calls dispose on all records and removes stale diagnostics/status | **deferred** | CR:M5-012; DEFER:D-005 |

### 3.8 Component Effects & Transitions — Test Coverage (M7–M8)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-080 | HMR replacement, provenance, picker integration, params, renderability, legacy compatibility comprehensive tests | **deferred** | CR:M7-006; gap in identified dedicated tests |
| D-081 | Frontend picker visibility, inspector param editing, export warning, invalid schema diagnostics tests | **deferred** | CR:M7-007; gap in identified dedicated tests |
| D-082 | Unapply/reset flows and pre-render export-readiness diagnostics tests | **deferred** | CR:M7-008; gap in identified dedicated tests |
| D-083 | Bulk transition editing with contributed transitions (tests) | **deferred** | CR:M8-002; gap in identified dedicated tests |
| D-084 | Registry lifecycle, picker integration, params defaults, repair, bulk edit, renderability, export blockers tests | **deferred** | CR:M8-004; gap in identified dedicated tests |
| D-085 | Remove/reset/default flows for contributed transitions from clip/bulk edit panels (tests) | **deferred** | CR:M8-005; gap in identified dedicated tests |

### 3.9 Clip-Type — UI Integration (M9)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-090 | Contributed clip types in primary add-clip UI with selected editable clip after insertion (tests) | **deferred** | CR:M9-004; gap in identified dedicated tests |
| D-091 | Automation clip targeting extension parameter and overriding through host interpolation (tests) | **deferred** | CR:M9-008; gap in identified dedicated tests |

### 3.10 Shader — Frontend & Materializer (M13)

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-100 | Stub materializer capability finding for blocked export when no renderer route exists | **deferred** | CR:M13-005; `shaderMissingMaterializerBlockerMessage` exported but materializer not implemented |
| D-101 | Shader preview surface placement, textureRef widget diagnostics, materialize action, postprocess timeline badge, bypass/A-B preview | **deferred** | CR:M13-007; frontend surface ownership assigned but not tested |
| D-102 | Shader source range diagnostics and uniform preset/default persistence (tests) | **deferred** | CR:M13-009; gap in identified dedicated tests |

### 3.11 TimelinePatch — Reserved Operations

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-110 | `clip.split` and `clip.slice` operation families | **deferred** | CR:M3-016; reserved with `{ reserved: true, deferred: true }` warnings; DOC:timeline-patch-operations.md§4 |
| D-111 | Overlay shader composition surface (V1 has vocabulary only) | **deferred** | CR:M13-002; DOC:shader-execution-model.md (overlay vocabulary reserved, no V1 surface) |

### 3.12 Permissions & Sandboxing

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-120 | Runtime permission enforcement (network, filesystem, env, processes gating) | **deferred** | DOC:extensions-trust-envelope.md§3; ABSENCE:grep -r 'permission enforcement' src/tools/video-editor/runtime/ |
| D-121 | Sandboxed extension execution (iframe, Worker, ShadowRealm isolation) | **deferred** | DOC:extensions-trust-envelope.md§§5-6; ABSENCE:grep -r 'sandbox' src/tools/video-editor/runtime/; planned M4–M5 |
| D-122 | Dynamic package loading (npm / CDN / `import()` for extension code) | **deferred** | DOC:extensions-trust-envelope.md§2; ABSENCE:grep -r 'CDN.*extension' src/tools/video-editor/runtime/; extensions statically bundled with host |
| D-123 | Marketplace, cloud loading, or third-party extension registry | **unsupported** | CR:X-006; consistently OUT of scope for all milestones; ABSENCE:grep -r 'marketplace' src/sdk/ |

### 3.13 Structural Deferrals

| Row ID | Behavior | Classification | Evidence |
|---|---|---|---|
| D-130 | Proposal UI component tests (previewable, non-previewable, accepted, rejected, stale) | **deferred** | CR:M3-006; proposal-runtime.test.ts covers runtime; dedicated UI tests not identified |
| D-131 | DSL/compiler canary reading `CreativeContext.timeline`, storing source/source-map, emitting `TimelineProposal` | **deferred** | CR:M3-013; `SourceMapRuntime` exists; explicit DSL canary test not identified |
| D-132 | Proposal diff rendering, source-map navigation from diff/diagnostic UI, stale badges | **deferred** | CR:M3-015; infrastructure exists; dedicated rendering tests not identified |
| D-133 | Schema capability registry tests (supported widgets, unsupported diagnostics, validation, custom widget placeholder) | **deferred** | CR:M2-007; concept documented; dedicated registry tests not identified |
| D-134 | Extension status drawer: active extension IDs, contribution inventory, diagnostics, current blockers, and composition-spine expansion | **deferred** | CR:M2-009; skeletal concept; the manager UI basics (enable/disable, settings editing, persistence) are now supported and credited to M5/M14 cross-delivery (see S-160–S-164); composition-spine and status-drawer expansion remain staged |
| D-135 | Subscription cleanup dedicated tests (leaked listener prevention) | **deferred** | CR:M2-002; `DisposeHandle` infrastructure exists; dedicated leak tests not identified |
| D-136 | Standalone `@reigh/editor-sdk` npm package publishing (independent npm registry publication with its own `package.json`, versioning, and distribution outside the monorepo) | **deferred** | ABSENCE:grep -r 'standalone-publish' src/sdk/; `@reigh/editor-sdk` is a monorepo path alias resolving to `src/sdk/index.ts` — it does not have its own `package.json`, publishConfig, or independent build pipeline (no standalone-publish markers exist). The SDK is monorepo-extractable (verified by `scripts/quality/check-video-editor-sdk-imports.mjs` external-consumption smoke). Standalone npm publishing has not been implemented. |

---

## 4. V1 Scope Boundaries

### 4.1 Explicitly out-of-scope for V1

These behaviors are documented as unsupported across all milestones and have no active implementation path:

| Behavior | Evidence |
|---|---|
| Marketplace / extension registry | ABSENCE:grep -r 'marketplace' src/sdk/; CR:X-006 |
| Standalone `@reigh/editor-sdk` npm publishing | Deferred — see D-136 above. The SDK is monorepo-extractable but has not been published as an independent npm package. |
| Cloud extension loading | ABSENCE:grep -r 'cloud.*extension' src/tools/video-editor/runtime/ |
| Sandboxed execution (iframe/Worker/ShadowRealm) | DOC:extensions-trust-envelope.md§5 |
| Theme contributions | ABSENCE:grep -r 'theme.*contribution' src/sdk/index.ts |
| Public CRDT collaboration primitives | ABSENCE:grep -r 'CRDT' src/sdk/index.ts |

### 4.2 Active V1 trust model

| Concern | V1 Answer | Evidence |
|---|---|---|
| Execution context | Same-thread, same-origin JavaScript in the browser | DOC:extensions-trust-envelope.md§7 |
| Isolation | None | DOC:extensions-trust-envelope.md§1 |
| Permission enforcement | Descriptive only (no runtime gating) | DOC:extensions-trust-envelope.md§3 |
| Lifecycle visibility | Console groups + structured diagnostics + export guard | DOC:extensions-trust-envelope.md§7 |
| Error containment | Contribution-level error boundaries; activation throws → `failed` state + diagnostics | DOC:extensions-trust-envelope.md§5 |
| Source vetting | Human review required; no automated integrity checks in V1 | DOC:extensions-trust-envelope.md§7 |

---

## 5. Matrix Statistics

### 5.1 Supported V1 behaviors

| Category | Count |
|---|---|
| SDK Scaffold & Public Boundary | 6 |
| Extension Runtime & Lifecycle | 10 |
| Contribution Surfaces & Host Slots | 8 |
| TimelinePatch & Proposal System | 11 |
| Commands, Keybindings & Context Menus | 2 |
| Provider-Scoped Registry | 6 |
| Asset Metadata & Parsers | 7 |
| Component Effects | 6 |
| Transition Contributions | 3 |
| Clip-Type Dispatch & Keyframes | 6 |
| Agent Tool Contributions | 5 |
| Live Data Bridge | 5 |
| Shader & WebGL Bridge | 6 |
| Provider Compatibility | 4 |
| Cross-Cutting Guarantees | 6 |
| Extension Manager, Persistence & Cleanup | 5 |
| **Total supported** | **96** |

### 5.2 Deferred V1 behaviors

| Category | Count |
|---|---|
| Extension Packaging & Manager (M14) | 10 |
| Render Planner & Export (M12) | 6 |
| Live Data Bridge Frontend (M11) | 8 |
| Agent Tool Frontend (M10) | 8 |
| Commands Tests (M4) | 3 |
| Asset Metadata Frontend (M6) | 5 |
| Provider Registry Edge Cases (M5) | 4 |
| Effects & Transitions Tests (M7–M8) | 6 |
| Clip-Type UI (M9) | 2 |
| Shader Frontend (M13) | 3 |
| TimelinePatch Reserved Ops | 2 |
| Permissions & Sandboxing | 4 |
| Structural Deferrals | 7 |
| **Total deferred** | **68** |

---

## 6. Release Blocker Reference

The following blocker entries (from the contract-recheck matrix § 3.1) track gaps that are significant enough to be documented as release-blocking until resolved or deferred:

| Blocker ID | Affected Areas | Description |
|---|---|---|
| B-001 | D-001 through D-010 (M14) | Extension manager UI, persistence, integrity, migration, dependency management are core to installed-pack experience |
| B-002 | D-021 (M12) | Remaining gap is complete frontend evidence that planner next actions are surfaced everywhere blocked export/render decisions are exposed |
| B-003 | D-030 through D-037 (M11) | Live data bridge frontend state coverage is sparse in identified tests |

---

## 7. Cross-Reference Index

### 7.1 Contract-recheck row → Supported row (S-*)

Each supported row in this document maps to one or more contract-recheck rows in `extension-platform-contract-recheck.md`. The primary mapping is embedded in each row's Evidence column as `CR:<RowID>`. The contract-recheck matrix contains the full Done Criteria evidence paths.

### 7.2 Contract-recheck row → Deferred row (D-*)

Each deferred row maps to the contract-recheck row(s) where the gap was identified, plus any relevant blocker (B-*) or deferral (D-*) entry.

### 7.3 External documentation references

| Document | Purpose |
|---|---|
| [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md) | Complete M0–M14 Done Criteria evidence matrix |
| [extensions-trust-envelope.md](./extensions-trust-envelope.md) | V1 trusted-local execution model and permission posture |
| [provider-compatibility-matrix.md](./provider-compatibility-matrix.md) | DataProvider compatibility across InMemory/Supabase/Astrid |
| [timeline-patch-operations.md](./timeline-patch-operations.md) | Complete TimelinePatch operation reference |
| [shader-execution-model.md](./shader-execution-model.md) | M13 shader/WebGL bridge model |
| [frontend-closure-checklist.md](./frontend-closure-checklist.md) | Frontend state completeness for public primitives |

---

## 8. Version History

| Date | Change |
|---|---|
| 2026-07-07 | Reconciled matrix with final foundation state (T11): narrowed D-001 to install/update/delete only, narrowed D-002 to failed-load recovery; added S-160–S-164 for delivered manager UI, persisted enablement/settings, and lifecycle cleanup; updated D-134 to credit M5/M14 cross-delivery while keeping composition-spine expansion staged; D-136 standalone npm publishing deferral confirmed. |
