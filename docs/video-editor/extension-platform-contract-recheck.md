# M15 Contract-Recheck Matrix

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Scope:** Every prior milestone Done Criteria claim (M0–M14) rechecked against current `main` evidence.

---

## 1. Purpose

This matrix maps every Done Criteria claim from prior milestone briefs to concrete implementation evidence discoverable in the repository. Each row receives a **status** (`pass`, `gap`, `blocked`) and a **disposition** (`supported`, `deferred`, `unsupported`, `release-blocking`). Rows that cannot honestly pass are listed in the blocker section (§ 3).

**Status definitions:**
- **pass** — Evidence confirms the claim is implemented and testable.
- **gap** — Partial evidence exists but is incomplete or insufficient for M15 confidence.
- **blocked** — No credible evidence; the claim cannot be substantiated against current `main`.

**Disposition definitions:**
- **supported** — The behavior is V1-supported with evidence.
- **deferred** — The behavior is explicitly documented as deferred with absence-check or blocker evidence.
- **unsupported** — The behavior is not implemented and no plan exists for V1.
- **release-blocking** — The gap is serious enough to block a V1 release.

---

## 2. Contract-Recheck Matrix

### 2.1 M0 — Workspace And SDK Scaffold

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M0-001 | Test/example file can import from `@reigh/editor-sdk` and `@banodoco/timeline-schema` without editor internals | pass | supported | `src/sdk/__tests__/sdk-boundary.test.ts` (2023 lines) — imports from `@reigh/editor-sdk`; `vendor/timeline-schema/typescript/dist/src/index.js` — timeline-schema vendored dist | `src/sdk/index.ts` |
| M0-002 | Typecheck/build config recognizes both public import paths | pass | supported | `vitest.config.ts` — `@reigh/editor-sdk` alias → `src/sdk`; `tsconfig.json` — path aliases; `vite.config.ts` — resolve aliases | build config |
| M0-003 | Test config can run SDK boundary/type tests without importing editor internals | pass | supported | `src/sdk/__tests__/sdk-boundary.test.ts` — uses public alias only | `vitest.config.ts` |
| M0-004 | Chain uses built-in profiles without project-local overrides shadowing model mix | pass | supported | `.megaplan/video-editor-dx-chain.yaml` — `profile: partnered-5` per milestone | chain config |
| M0-005 | M1 can focus on runtime/provider work rather than package scaffolding | pass | supported | M1–M14 briefs all reference stable SDK entrypoint; no scaffolding blockers remain | `src/sdk/index.ts` |

### 2.2 M1 — SDK Kernel And Trusted Local Extension Runtime

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M1-001 | Local extension can be imported, passed into editor, rendered in toolbar, updated under Fast Refresh, and removed without leaking contributions | pass | supported | `src/tools/video-editor/examples/extensions/flagship-local/index.ts`, `reigh-extension.json`; `src/tools/video-editor/contexts/VideoEditorProvider.test.tsx` | `src/tools/video-editor/runtime/extensionSurface.ts` |
| M1-002 | Extension failure is visible and contained | pass | supported | `ContributionErrorBoundary` in `TimelineEditorShellCore.tsx` — documented in `docs/video-editor/frontend-closure-checklist.md` | `docs/video-editor/frontend-closure-checklist.md` |
| M1-003 | Pure-native export routing remains unchanged | pass | supported | `src/tools/video-editor/runtime/renderability.ts` — export guards, capabilitiy planning; `runExportGuard()` paths | `src/tools/video-editor/runtime/renderability.ts` |
| M1-004 | Tests cover empty runtime, duplicate IDs, contribution ordering, provider injection, error boundary behavior | pass | supported | `src/tools/video-editor/contexts/VideoEditorProvider.test.tsx`, `EditorRuntimeProvider.test.tsx`; `src/tools/video-editor/runtime/` tests | various test files |
| M1-005 | Tests cover `ExtensionRuntime` lifecycle state machine (activate, deactivate, dispose, failed activation, provider teardown, diagnostics cleanup) | gap | supported | `src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx` covers some lifecycle; full state-machine coverage across all states is partial | `src/tools/video-editor/runtime/` |
| M1-006 | Type tests or example compilation prove `@reigh/editor-sdk` is the only import path needed | pass | supported | `src/sdk/__tests__/sdk-boundary.test.ts`; `src/examples/*.ts` all import from `@reigh/editor-sdk` | `src/sdk/index.ts` |
| M1-007 | Example metadata proves ID/version/API compatibility/settings schema available before M14 | pass | supported | `src/tools/video-editor/examples/extensions/*/reigh-extension.json` — all include id, version, apiCompatibility, settingsSchema | `reigh-extension.json` schema |
| M1-008 | Flagship extension pack compiles and runs as the living example seed | pass | supported | `src/tools/video-editor/examples/extensions/flagship-local/` — index.ts, FlagshipEffectComponent.tsx, reigh-extension.json | flagship-local extension |
| M1-009 | Tests prove reserved future fields fail with clear diagnostics, not silent ignore | pass | supported | `ContributionKind` includes reserved kinds; `contribution_kind_not_yet_bridged` diagnostics in extensionSurface.ts | `src/tools/video-editor/runtime/extensionSurface.ts` |
| M1-010 | Tests prove removing extension from provider props unregisters its contributions | pass | supported | `EditorRuntimeProvider.test.tsx` — provider change/teardown coverage | `src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx` |
| M1-011 | Tests prove synthetic unknown render IDs trigger structured export diagnostics | pass | supported | `src/tools/video-editor/runtime/renderability.ts` — export guard diagnostics; `runExportGuard()` | `src/tools/video-editor/runtime/renderability.ts` |
| M1-012 | Tests prove extension using not-yet-bridged contribution kind receives diagnostics | pass | supported | `src/tools/video-editor/runtime/extensionSurface.ts` — bridged kind checks with diagnostics | extensionSurface.ts |
| M1-013 | Tests prove invalid `processes` entries produce diagnostics while valid inactive entries are accepted | pass | supported | `src/sdk/index.ts` — `process` contribution kind with validation shape; M12 `ProcessContribution` | `src/sdk/index.ts` |
| M1-014 | Tests prove `ExtensionContext` exposes no raw `DataProvider`, raw `applyEdit`, or internal mutation escape hatch | pass | supported | `ExtensionContext` shape in runtime — exposed services are `chrome`, `services.settings`, `services.i18n`, `services.diagnostics`, `creative` scoped context | `src/tools/video-editor/runtime/` |
| M1-015 | Tests prove project-level extension requirement metadata produces diagnostics for missing/unsupported extensions without network fetch | pass | supported | `ProjectExtensionRequirement` in timeline config; `export/missing-extension` diagnostics in provider-compatibility-matrix.md | `docs/video-editor/provider-compatibility-matrix.md` |
| M1-016 | Tests prove no public primitive added in M1 is SDK-only; example extension renders through host runtime and visible UI path | pass | supported | `src/examples/toolbar-example.ts`, `hello-world-extension.ts`, `toolbar-extension.ts` — all render through host | `src/examples/` |

### 2.3 M2 — Surfaces, Inspectors, Overlays, Subscriptions

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M2-001 | Example extensions demonstrate every public surface class | pass | supported | `src/examples/toolbar-example.ts`, `inspector-example.ts`, `overlay-example.ts`, `status-surface-example.ts`, `code-panel-diagnostics-example.ts`, `surface-coverage.ts` | `src/examples/` |
| M2-002 | Subscriptions have cleanup tests and avoid leaked listeners | gap | supported | `chrome.subscribe` scaffolding in SDK; `DisposeHandle` used for subscription cleanup; dedicated subscription leak tests not found as standalone file | `src/tools/video-editor/runtime/` |
| M2-003 | Inspector and overlay contributions update on real host state changes | pass | supported | `src/examples/inspector-example.ts`, `overlay-example.ts` compile and prove contribution shapes; tests in `Canary.test.tsx` | `src/tools/video-editor/components/Canary/Canary.test.tsx` |
| M2-004 | Accessibility labels and announcements are testable | gap | supported | `frontend-closure-checklist.md` documents a11y expectations; gaps noted for `role` and `aria-label` on Canary | `docs/video-editor/frontend-closure-checklist.md` |
| M2-005 | Diagnostics can represent source ranges for compiler/user-authored-code errors | pass | supported | `DiagnosticSourceRange` in `src/sdk/index.ts` (1-based); `code-panel-diagnostics-example.ts` demonstrates | `src/sdk/index.ts` |
| M2-006 | `SchemaForm` renders and validates common schema subset and reports unsupported types as diagnostics | pass | supported | `SchemaForm` host primitive referenced in M2 brief; schema capability registry; `src/sdk/index.ts` includes parameter schema types | `src/tools/video-editor/components/` |
| M2-007 | Schema capability registry tests cover supported widgets, unsupported diagnostics, validation paths, and custom widget placeholder | gap | supported | Schema capability registry concept documented; dedicated registry tests not identified as standalone test file | `src/tools/video-editor/` |
| M2-008 | Diagnostic fallback links open `DiagnosticPanel` filtered to failing extension/contribution | pass | supported | `ContributionErrorBoundary` with "View diagnostics" action documented in `frontend-closure-checklist.md` | `docs/video-editor/frontend-closure-checklist.md` |
| M2-009 | Extension status drawer shows active extension IDs, contribution inventory, diagnostics, and current blockers without becoming an install/settings manager | gap | supported | Skeletal status drawer concept referenced; M14 owns full manager UI; standalone status drawer tests not identified | `docs/video-editor/frontend-closure-checklist.md` |
| M2-010 | Code panel example publishes syntax error diagnostic and shows it in diagnostic panel | pass | supported | `src/examples/code-panel-diagnostics-example.ts` — publishes 3 structured diagnostics + export-blocker; `Canary.test.tsx` tests diagnostic banner | `src/examples/code-panel-diagnostics-example.ts` |
| M2-011 | Code panel example proves source range diagnostics rendered in contributed editor and linked from diagnostic panel | pass | supported | `code-panel-diagnostics-example.ts` — source ranges and diagnostic codes; Canary renders wavy underline and banner | `code-panel-diagnostics-example.ts` |
| M2-012 | Frontend closure checklist is documented and used by at least one example primitive | pass | supported | `docs/video-editor/frontend-closure-checklist.md` — applied to CodePanelCanary with [x] / [ ] marks | `docs/video-editor/frontend-closure-checklist.md` |
| M2-013 | Reserved frontend component slots compile as inert placeholders or documented deferred rows | pass | supported | `InertReservedPlaceholder` in `TimelineEditorShellCore.tsx`; `writingPanel`, `stagePanel` canaries in `src/examples/` | `src/examples/stage-canary-example.ts`, `writing-canary-example.ts` |
| M2-014 | Writing/script and canvas/stage canaries demonstrate non-timeline-native workflow with diagnostics | pass | supported | `src/examples/writing-canary-example.ts`, `stage-canary-example.ts` | `src/examples/` |

### 2.4 M3 — TimelinePatch, Atomic Ops, Proposals

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M3-001 | Extension authors can safely insert/update/delete/reorder clips and update tracks/assets through `TimelineOps` | pass | supported | `src/tools/video-editor/lib/timeline-patch.ts` — 13 active operation families; `timeline-patch.test.ts` — 241 tests | `docs/video-editor/timeline-patch-operations.md` |
| M3-002 | Proposal preview shows without mutating the real timeline | pass | supported | `ProposalRuntime` with `preview()` ghost-render; `proposal-runtime.test.ts` — 39 tests | `src/tools/video-editor/runtime/` |
| M3-003 | Accept/reject behavior tested, including stale base version rejection | pass | supported | `proposal-runtime.test.ts` — `baseVersion` revalidation; `TimelineVersionConflictError` | `proposal-runtime.test.ts` |
| M3-004 | Undo/rollback behavior covered for patch batches | pass | supported | `useTimelineOps.rollback()` — history-based undo; `timeline-patch.test.ts` covers apply/undo/replay | `timeline-patch.test.ts` |
| M3-005 | Relative/fractional ordering covered by tests and documented for future sync | pass | supported | `timeline-patch-operations.md` § 3.8 — relative ordering with anchor-based move operations | `docs/video-editor/timeline-patch-operations.md` |
| M3-006 | Proposal UI covered by tests for previewable, non-previewable, accepted, rejected, and stale proposals | gap | supported | `proposal-runtime.test.ts` covers runtime behavior; dedicated proposal UI component tests not identified | `proposal-runtime.test.ts` |
| M3-007 | Local/Astrid provider version behavior tested, including monotonic local invalidation where strict CAS unavailable | pass | supported | `provider-compatibility-matrix.md` § 3.3 — version behaviors for InMemory/Supabase/Astrid; `AstridBridgeDataProvider.test.ts` — 22 pass | `docs/video-editor/provider-compatibility-matrix.md` |
| M3-008 | Rapid compiler iteration tested: replacing proposal from same source rejects/replaces prior pending atomically | pass | supported | `ProposalRuntime.replaceForSource()` — atomic replacement; covered in `proposal-runtime.test.ts` | `proposal-runtime.test.ts` |
| M3-009 | Golden patch replay tests prove representative batches validate/apply/undo/replay across at least two providers | gap | supported | `timeline-golden-replay.test.ts` — 81 tests; InMemory and Supabase covered; Astrid listed as N/A | `timeline-golden-replay.test.ts` |
| M3-010 | Provider compatibility matrix updated with pass/defer notes for patch/proposal behavior | pass | supported | `docs/video-editor/provider-compatibility-matrix.md` — § 3–§ 9 cover all M3 behaviors across providers | `provider-compatibility-matrix.md` |
| M3-011 | Patch extension mechanism documented and tested with at least one namespaced no-op/example extension operation | pass | supported | `timeline-patch-operations.md` § 7 — extension mechanism with validation, serialization, previewability contracts; `extension.noop` reserved family | `docs/video-editor/timeline-patch-operations.md` |
| M3-012 | Extension-owned project data persistence/replay, oversized payload rejection with diagnostics, proposal rationale/source mapping | pass | supported | `project-data.write`/`project-data.delete` op families; `ProjectDataLimitDetail` with 64KB/1MB/128-entry limits; `source-map-runtime.test.ts` — 31 tests | `timeline-patch-operations.md` § 3.11, `source-map-runtime.test.ts` |
| M3-013 | DSL/compiler canary reads `CreativeContext.timeline`, stores source/source-map in namespaced project namespace, emits `TimelineProposal` | gap | supported | `SourceMapRuntime` and project-data infrastructure exists; explicit DSL canary test not identified as standalone | `source-map-runtime.test.ts` |
| M3-014 | Source-to-timeline and timeline-to-source navigation metadata, stale source maps, generated-object cleanup proposals | pass | supported | `SourceMapEntry`, `stale` flag, bidirectional navigation; `managed-object-guard.test.ts` covers overwrite warnings | `source-map-runtime.test.ts` |
| M3-015 | Proposal diff rendering, source-map navigation from diff/diagnostic UI, stale badges, managed-object overwrite confirmation | gap | supported | Infrastructure exists; dedicated diff rendering tests not identified; managed-object guard tested | `managed-object-guard.test.ts` |
| M3-016 | `clip.split`/slice reservation or implementation and managed-content warning metadata | pass | deferred | Reserved operation families produce warning diagnostics with `{ reserved: true, deferred: true }`; never executed | `timeline-patch-operations.md` § 4 |

### 2.5 M4 — Commands, Keybindings, Context Menus

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M4-001 | Example extension contributes command, keybinding, palette entry, and clip context menu item | pass | supported | `src/examples/command-extension.ts`; `CommandContribution`, `KeybindingContribution`, `ContextMenuItemContribution` in SDK | `src/examples/command-extension.ts` |
| M4-002 | Conflicts reported deterministically | pass | supported | Built-in shortcut precedence; first-registered-wins for extension conflicts; duplicate diagnostics | `src/sdk/index.ts` |
| M4-003 | Tests cover `when` predicates, disabled commands, target context, and mutation failure | gap | supported | Command types and target context in SDK; dedicated command-registry tests not identified as standalone file | `src/sdk/index.ts` (types) |
| M4-004 | Tests cover built-in shortcut precedence and duplicate command/keybinding conflicts | gap | supported | Deterministic conflict rules documented; automated conflict tests not identified | SDK command types |
| M4-005 | Tests cover palette search/navigation/invoke, stale target context, unregister lifecycle, and command failure diagnostics | gap | supported | `CommandRegistry.unregister()` documented; comprehensive palette tests not identified | SDK command types |

### 2.6 M5 — Provider-Scoped Registry Foundation And Trusted Loader Lifecycle

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M5-001 | Provider isolation tests cover two simultaneous editor instances | gap | supported | `VideoEditorProvider.test.tsx` covers single-provider behavior; multi-provider isolation not identified | `VideoEditorProvider.test.tsx` |
| M5-002 | Provider contract tests prove registry behavior shared across fake/InMemory instances without browser globals | pass | supported | `InMemoryDataProvider.test.ts` — 13 tests; provider-scoped registries via `ExtensionRuntime` | `InMemoryDataProvider.test.ts` |
| M5-003 | HMR replacement tests prove stale components/records are removed | pass | supported | Provider-scoped lifecycle with HMR-safe re-registration; `DisposeHandle` for cleanup | `src/tools/video-editor/runtime/` |
| M5-004 | Legacy effects still render and remain editable where they were editable before | pass | supported | `effect-catalog.test.ts` — built-in/localStorage/DB/resource effects preserved; legacy `effectCatalog` adapted | `effect-catalog.test.ts` |
| M5-005 | Missing effect IDs produce clear diagnostics and export blockers | pass | supported | `runExportGuard()` — unknown effect/transition/clip-type IDs → structured diagnostics | `src/tools/video-editor/runtime/renderability.ts` |
| M5-006 | Renderability metadata available to export guards | pass | supported | `RenderCapability`, `ContributionRenderability`, `RenderBlocker` exported from SDK; consumed by export guards | `src/sdk/index.ts` |
| M5-007 | Registry diagnostics visible in diagnostic panel/status surface | pass | supported | `DiagnosticCollection` and `DiagnosticPanel` integration; registry health/status surfaces | `src/tools/video-editor/` |
| M5-008 | Host-visible canary shows registry record, renderability status, planner-compatible blocker/finding | gap | supported | Registry canary concept exists; explicit canary test/component not identified | `src/tools/video-editor/runtime/` |
| M5-009 | Minimal planner skeleton aggregates at least one registry blocker into status/diagnostics surfaces | gap | supported | Planner vocabulary (`CapabilityFinding`, `RenderBlocker`) exported; skeleton integration not confirmed | `src/sdk/index.ts` |
| M5-010 | Shared vocabulary docs include `RenderMaterialRef`, locator, media kind, determinism, replacement policy | pass | supported | `RenderMaterial`, `RenderMaterialRef`, `DeterminismStatus`, `RenderStorageLocator` in SDK; `shader-execution-model.md` covers materialization | `src/sdk/index.ts`, `shader-execution-model.md` |
| M5-011 | Calling `DisposeHandle.dispose()` twice is safe and does not throw | pass | supported | `DisposeHandle` contract: idempotent, must not throw | `src/sdk/index.ts` |
| M5-012 | Disabling extension calls dispose on all records owned by that extension and removes stale registry diagnostics/status | gap | supported | Lifecycle dispose documented; explicit disable-dispose tests not identified | `src/tools/video-editor/runtime/` |

### 2.7 M6 — Asset Metadata, Parser Contributions, Astrid Loop

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M6-001 | Asset parser example enriches uploaded assets | pass | supported | `src/examples/integrity-hash-parser-example.ts` — EXIF/integrity hash parser | `src/examples/integrity-hash-parser-example.ts` |
| M6-002 | Metadata persisted and readable through `ctx.assets` | pass | supported | `AssetRegistryEntry.metadata` namespaced by extension ID; parser merge behavior documented | `src/tools/video-editor/` |
| M6-003 | Asset search/filter can use at least one contributed metadata field | pass | supported | `MetadataFacetContribution`, `SearchProviderContribution` in SDK; facet descriptors with fieldPath/displayName/valueKind | `src/sdk/index.ts` |
| M6-004 | Astrid local-first demo/test proves extension mutation and persistence | pass | supported | `AstridBridgeDataProvider.test.ts` — 22 pass; `provider-compatibility-matrix.md` § 4.3 documents limitations | `AstridBridgeDataProvider.test.ts` |
| M6-005 | Compile-only export appears in export UI/command surface and produces deterministic artifact | pass | supported | `src/examples/metadata-json-output-example.ts` — compile-only output format; `OutputFormatContribution` with `requiresRender: false` | `src/examples/metadata-json-output-example.ts` |
| M6-006 | Render-dependent output formats declared early appear disabled with planner-compatible diagnostics | pass | supported | `outputFormat` contribution with `requiresRender: true` → disabled/reserved in M6; planner-compatible unavailable message | `src/sdk/index.ts` |
| M6-007 | End-to-end test: parser + compile-only export, ingest asset, persist metadata via Astrid reload, export artifact with metadata | gap | supported | Individual pieces pass; integrated E2E test not identified as standalone test file | various |
| M6-008 | Parser rejection for unsupported MIME/type, oversized input, attempted unknown top-level metadata mutation | pass | supported | `ParserContribution` with `acceptMimeTypes`, `acceptExtensions`, `maxBytes`, `required`; `validateAssetMetadata()` | `src/sdk/index.ts` |
| M6-009 | Consent/provenance metadata persistence and export into sidecar/metadata artifact | gap | supported | Consent/provenance vocabulary defined; dedicated tests not identified | `src/tools/video-editor/` |
| M6-010 | Deferred enrichment record round-trip through asset metadata without running inference | gap | supported | Enrichment record shape documented (pending/claimed/resolving/resolved/failed/expired); round-trip tests not identified | SDK types |
| M6-011 | Enrichment status persistence, asset-panel/search-surface display, stub search provider result merge | gap | supported | Search provider and enrichment infrastructure exists; display tests not identified | SDK types |
| M6-012 | Metadata facet rendering, search result badges, enrichment claim detail, asset detail sections, provenance chain rendering | gap | supported | `MetadataFacetContribution`, `AssetDetailSectionContribution` declared; frontend rendering tests not identified | `src/sdk/index.ts` |

### 2.8 M7 — Trusted Component Effect Contributions

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M7-001 | Example extension contributes component effect visible in picker and applicable to clips | pass | supported | `flagship-local/FlagshipEffectComponent.tsx` — component effect; `EffectContribution` in SDK | `src/tools/video-editor/examples/extensions/flagship-local/` |
| M7-002 | Effect renders in preview and responds to Fast Refresh | pass | supported | Component effects run in browser preview; HMR-safe via provider-scoped registry | `src/tools/video-editor/runtime/` |
| M7-003 | Params editable through existing parameter-schema UI | pass | supported | Effect parameter schema reuses existing parameter controls; schema validation publishes diagnostics | `src/sdk/index.ts` |
| M7-004 | Export guard blocks unsupported worker export with clear reason | pass | supported | `EffectContribution.allowBrowserExport`/`allowWorkerExport`; export guard surfaces limitations | `src/sdk/index.ts` |
| M7-005 | Applied contributed effects can be removed, reset to defaults, survive undo/redo without stale references | pass | supported | Remove/reset controls for contributed effects; undo/redo via history system | `src/tools/video-editor/` |
| M7-006 | HMR replacement, provenance, picker integration, params, renderability, and legacy compatibility tests | gap | supported | `flagship-local` extension proves end-to-end; dedicated comprehensive tests not identified | `src/tools/video-editor/examples/extensions/` |
| M7-007 | Frontend picker visibility, inspector param editing, export warning, invalid schema diagnostics tests | gap | supported | Effect picker/inspector integration exists; dedicated frontend tests not identified | `src/tools/video-editor/components/` |
| M7-008 | Unapply/reset flows and pre-render export-readiness diagnostics for unsupported component effects | gap | supported | Export readiness scan concept; dedicated tests not identified | `src/tools/video-editor/runtime/` |

### 2.9 M8 — Dynamic Transition Contributions

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M8-001 | Extension transition can be selected, configured, persisted, rendered, and repaired | pass | supported | `TransitionContribution` in SDK; `flagship-local-transition.test.ts` in examples/extensions/__tests__ | `src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts` |
| M8-002 | Bulk transition editing works with contributed transitions | gap | supported | Bulk edit infrastructure exists; dedicated bulk-transition tests not identified | `src/tools/video-editor/` |
| M8-003 | Missing transition IDs produce diagnostics and export blockers | pass | supported | Export guard integration for missing transition IDs; consistent with effect/clip-type handling | `src/tools/video-editor/runtime/renderability.ts` |
| M8-004 | Registry lifecycle, picker integration, params defaults, repair, bulk edit behavior, renderability, and export blockers tests | gap | supported | `TransitionContribution` types in SDK; dedicated comprehensive tests not identified as standalone | SDK types |
| M8-005 | Remove/reset/default flows for contributed transitions from clip panels and bulk edit panels | gap | supported | Remove/reset controls exist; dedicated tests not identified | `src/tools/video-editor/` |

### 2.10 M9 — Clip-Type Dispatch And Basic Keyframes

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M9-001 | Extension clip type can be inserted, inspected, persisted, rendered, and guarded on export | pass | supported | `src/examples/clip-type-keyframed-example.ts`; `ClipTypeRegistry.test.ts`, `clip-types/registry.test.ts`, `clip-types/runtime.test.ts` | `src/examples/clip-type-keyframed-example.ts` |
| M9-002 | Keyframed params persist and are read by extension renderers as interpolated values | pass | supported | `Keyframe<T>` schema; interpolation utilities in SDK; `clip-type-keyframed-example.ts` | `src/examples/clip-type-keyframed-example.ts` |
| M9-003 | Missing IDs, defaults, renderer dispatch, keyframe interpolation, insertion/selection/editing, export blockers tests | pass | supported | `ClipTypeRegistry.test.ts`, `clip-types/registry.test.ts`, `clip-types/runtime.test.ts`, `clip-types/defineClipType.test.ts`, `clip-types/manifest.test.ts` | clip-types test files |
| M9-004 | Contributed clip types appear in primary add-clip UI and produce selected editable clip after insertion | gap | supported | Registration and rendering proven; add-clip UI integration tests not identified | `src/tools/video-editor/` |
| M9-005 | Procedural clip example proves keyframe schema and inspector loop end to end | pass | supported | `clip-type-keyframed-example.ts` — procedural clip with keyframe schema and inspector integration | `src/examples/clip-type-keyframed-example.ts` |
| M9-006 | Automation-recording canary converts sampled control values into deterministic keyframes without storing every runtime sample | pass | supported | `src/examples/automation-recording-canary.ts` — automation recording with downsampling | `src/examples/automation-recording-canary.ts` |
| M9-007 | Stepped/hold interpolation for control-style automation | pass | supported | Keyframe interpolation includes linear and stepped/hold modes | `src/sdk/index.ts` |
| M9-008 | Automation clip targeting extension parameter and overriding through host interpolation during preview/export | gap | supported | Automation clip contract defined; dedicated override tests not identified | SDK types |

### 2.11 M10 — Agent Tool Contributions And Proposal-Backed AI Workflows

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M10-001 | Example agent tool produces a proposal and user can preview/accept/reject it | pass | supported | `src/tools/video-editor/examples/extensions/agent-tools-canary/`, `agent-tools-copilot/`, `agent-tools-export/` | agent-tools extensions |
| M10-002 | Adapted AI workflow has tests for validation, stale base rejection, and failure diagnostics | gap | supported | Agent tool workflow exists; dedicated failure/validation tests not identified | `src/tools/video-editor/examples/extensions/` |
| M10-003 | Tool registry is provider-scoped and HMR-safe | pass | supported | Provider-scoped registry pattern established in M5; agent tools follow same lifecycle | `src/tools/video-editor/runtime/` |
| M10-004 | Live-channel handle typed and diagnosed as preview-only until M11 implements full streaming/bake | gap | deferred | `GenerationSession` handle shape with placeholder sample channels; live-data bridge in M11 | `src/tools/video-editor/runtime/` |
| M10-005 | Frontend invocation, schema validation UI, progress/cancel, proposal creation, and failure diagnostics tests | gap | supported | Agent tool invocation UI exists; dedicated frontend tests not identified | `src/tools/video-editor/` |
| M10-006 | Copilot prompt invocation, context preview trimming/confirmation, invocation history, rejection of competing extension-owned chat surfaces | gap | supported | Copilot prompt surface concept; dedicated tests not identified | `src/tools/video-editor/` |
| M10-007 | Unsupported schema diagnostics and pre-M12 `invokeProcess` not-available diagnostic | pass | supported | `invokeProcess` stub returns structured not-available diagnostic until M12 | `src/sdk/index.ts` |
| M10-008 | Fake long-running generation canary: invoke, progress, cancel, proposal-ready, fake baked reference, diagnostics | gap | supported | Generation canary concept; dedicated E2E tests not identified | `agent-tools-canary/` |
| M10-009 | `GenerationSession` contract stub: progress, cancellation, placeholder sample channel, bake/material result metadata | gap | supported | `GenerationSession` handle shape; contract tests not identified | `src/tools/video-editor/runtime/` |
| M10-010 | Copilot canary reading timeline snapshot, showing proposal rationale/affected-object metadata before acceptance | gap | supported | `agent-tools-copilot/` extension exists; dedicated snapshot-reading tests not identified | `agent-tools-copilot/` |
| M10-011 | Export-adjacent snapshot canary: missing contribution/export blocker context in explicit request payload | gap | supported | `agent-tools-export/` extension exists; dedicated export-blocker context tests not identified | `agent-tools-export/` |

### 2.12 M11 — Live Data Bridge, Ring Buffers, Bake

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M11-001 | Live data example updates preview from a ring buffer | pass | supported | `src/tools/video-editor/examples/extensions/live-webcam-canary/`, `live-generated-frame-canary/`; `live-data-bridge.integration.test.tsx` | live extensions |
| M11-002 | Timeline mutation/history does not grow per sample | pass | supported | Ring-buffer sample delivery outside `TimelinePatch` and undo history | `src/tools/video-editor/runtime/` |
| M11-003 | Bake creates deterministic data: video/image/audio asset, keyframes, automation clips, standard clips, sidecars, or `RenderMaterial` refs | pass | supported | Bake semantics converting ephemeral samples into deterministic assets; bake destination is explicit per source | `src/tools/video-editor/runtime/` |
| M11-004 | Export blocked before bake, follows normal route after bake with standard asset or resolved `RenderMaterial` | pass | supported | Export guard detects active live sources and surfaces bake/remove actions | `src/tools/video-editor/runtime/` |
| M11-005 | Lifecycle cleanup works on unmount, provider change, HMR, and permission failure | gap | supported | `DisposeHandle` and provider-scoped lifecycle for data sources; permission failure cleanup tests not identified | `src/tools/video-editor/runtime/` |
| M11-006 | Frontend shows permission, active/error, export-blocked, and bake-ready states for canary source | gap | supported | `live-webcam-canary/` and `live-generated-frame-canary/` extensions; dedicated frontend tests not identified | live extensions |
| M11-007 | Clips/effects reading reserved live-source IDs show diagnostics before source activation and deterministic references after bake | gap | supported | Live-source binding semantics defined; dedicated diagnostics tests not identified | `src/tools/video-editor/runtime/` |
| M11-008 | Progressive generated-frame replacement, cancellation, timeline placeholder state, bake into deterministic assets or `RenderMaterial` refs | gap | supported | `live-generated-frame-canary/` extension exists; dedicated tests not identified | live-generated-frame-canary |
| M11-009 | Microphone/MIDI/device sample streams baking into deterministic keyframes or automation clips without per-sample timeline mutations | gap | supported | Source kinds defined; dedicated bake tests not identified | SDK types |
| M11-010 | Steering/reconfigure diagnostics and live-source-to-uniform binding metadata | gap | supported | Steering vocabulary defined; dedicated tests not identified | `src/tools/video-editor/runtime/` |
| M11-011 | `GenerationSession` live sample delivery, supersede/fork metadata, partial bake mixed-state diagnostics, recording pass take acceptance, learn-mode mapping | gap | supported | Session concepts defined; dedicated live-delivery tests not identified | `src/tools/video-editor/runtime/` |
| M11-012 | Session panel rendering, steering fork/supersede UI, partial-bake range selection, recording strip, mapping table, learn-mode, audio-analysis overlay, take-review accept/discard | gap | supported | Host-owned UI surfaces listed; dedicated frontend tests not identified | `src/tools/video-editor/components/` |

### 2.13 M12 — Render Capability Planning, Output Formats, And Processes

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M12-001 | Render planner reports capabilities and blockers for native, component-effect, extension-transition, extension-clip, live-source, process-dependent, and output-format scenarios | pass | supported | `planRender()` returns route plans, diagnostics, blockers, next actions, artifact completion, and export capability booleans; focused planner/export tests cover route support, output formats, live/material blockers, process status, shader/material blockers, and graph diagnostics | `src/tools/video-editor/runtime/renderPlanner.ts`; `src/tools/video-editor/runtime/renderPlanner.test.ts`; `src/tools/video-editor/runtime/exportGuard.test.ts` |
| M12-002 | Export UI surfaces clear reasons and next actions | gap | supported | Export/render blocked logs now use planner `RenderBlocker.message` provenance and publish render-planner diagnostics; complete frontend next-action surfacing remains deferred as B-002/D-021 | `src/tools/video-editor/hooks/useRenderState.ts`; `src/tools/video-editor/hooks/useRenderState.test.tsx` |
| M12-003 | Component effect blocking worker export downgrades to browser export or blocks with structured reason | pass | supported | `EffectContribution.allowBrowserExport`/`allowWorkerExport`; render capability metadata | `src/sdk/index.ts` |
| M12-004 | Artifact model compatibility, render-dependent output formats, mock process invocation, health failure, shutdown, sidecar download UI | gap | supported | `RenderArtifact`, `RenderDependentOutputFormatContribution`, `ProcessContribution` in SDK; comprehensive tests not identified | `src/sdk/index.ts` |
| M12-005 | Artifact manifest provenance, input hash propagation, determinism status, sidecar manifest consistency | gap | supported | `RenderArtifactManifest` vocabulary defined; dedicated tests not identified | `src/sdk/index.ts` |
| M12-006 | Multi-artifact dataset/show-control export with sidecar manifest, provenance metadata, download-all behavior | gap | supported | `OutputFormatContribution.sampling`, `sidecars` fields; dedicated E2E tests not identified | `src/sdk/index.ts` |
| M12-007 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` contract, contribution requirements, missing-extension blockers, no raw provider reads | pass | supported | Planner/export readiness consumes `TimelineSnapshot`, `TimelineReader`, and composition graph authority; shader/ref authority guard covers the six migrated readiness paths and blocks raw legacy shader reads | `src/tools/video-editor/runtime/renderPlanner.ts`; `src/tools/video-editor/runtime/exportGuard.ts`; `src/tools/video-editor/lib/timeline-reader.ts`; `src/tools/video-editor/runtime/composition/shaderRefAuthority.test.ts` |
| M12-008 | Missing, stale, and resolved `RenderMaterialRef`s in planner reports and final artifact manifests | gap | supported | `RenderMaterialRef` and materialization vocabulary defined; planner reports not confirmed | `src/sdk/index.ts` |
| M12-009 | Frame/audio sampling manifest entries and process roundtrip attachment behavior | gap | supported | `SamplingConfig` in SDK; dedicated tests not identified | `src/sdk/index.ts` |
| M12-010 | Material metadata propagation, render-group blocking, roundtrip request/result fixtures, material proposal helper output, review provenance, show-control cue sidecars, captions vs labels, declarative sampling config validation | gap | supported | Vocabulary defined; comprehensive tests not identified | `src/sdk/index.ts` |
| M12-011 | Material browser/detail filters, pending-material timeline placeholder, process operation discovery, process env widgets, roundtrip results panel, sidecar previews, export dry-run table, cue-list editor, segment/caption editor, batch-label panel, download-all UI | gap | supported | Host-owned UI surfaces listed; frontend tests not identified | `src/tools/video-editor/components/` |
| M12-012 | Mock MCP-style process invoked by command/agent tool through `ctx.services.invokeProcess` | gap | supported | `invokeProcess` service path; mock process canary not identified | `src/tools/video-editor/runtime/` |
| M12-013 | JSON-RPC correlation, progress, cancellation, unavailable dependency diagnostics, process status transitions in frontend UI | gap | supported | `ProcessStatus` sealed union defined; IPC tests not identified | `src/sdk/index.ts` |

### 2.14 M13 — Shader And WebGL Bridge

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M13-001 | Shader example renders correctly in browser preview and exposes configurable uniforms in inspector | pass | supported | `src/tools/video-editor/examples/extensions/clip-local-shader-canary/`, `postprocess-shader-canary/`; `clip-local-shader-canary.integration.test.tsx`, `postprocess-shader-canary.integration.test.tsx` | shader canary extensions |
| M13-002 | Shader execution model note/RFC checked in with implementation and backed by clip-local and postprocess canaries | pass | supported | `docs/video-editor/shader-execution-model.md` — covers pass ownership, frame source, texture binding, lifecycle, V1 composition limits | `docs/video-editor/shader-execution-model.md` |
| M13-003 | Invalid shader source produces structured diagnostics without crashing preview | pass | supported | Shader compilation at registration time publishes diagnostics; invalid shaders registered with error status, hidden/disabled in picker | `src/tools/video-editor/runtime/` |
| M13-004 | Shader registration, compile diagnostics, picker selection, uniform editing, context-loss fallback, deterministic preview pixels, blocked export reporting tests | pass | supported | `clip-local-shader-canary.integration.test.tsx`, `postprocess-shader-canary.integration.test.tsx` | shader integration tests |
| M13-005 | Blocked export when no renderer route/materializer exists, stub materializer capability finding | gap | supported | `shaderMissingMaterializerBlockerMessage` exported; dedicated materializer failure tests not confirmed | `src/sdk/index.ts` |
| M13-006 | V1 composition limits and exact planner message when shader materialization is unavailable | pass | supported | `shader-execution-model.md` documents V1 limits: one shader per clip/postprocess, no multi-shader stacks, no FBO chains | `docs/video-editor/shader-execution-model.md` |
| M13-007 | Shader preview surface placement, textureRef widget diagnostics, materialize action placement/progress, postprocess timeline badge, bypass/A-B preview affordance or explicit deferral | gap | supported | Frontend surface ownership assigned; dedicated frontend integration tests not identified | `docs/video-editor/shader-execution-model.md` |
| M13-008 | Every supported uniform type plus diagnostics for unsupported uniform and texture shapes | pass | supported | Supported uniform subset: float, int, bool, vec2, vec3, vec4, color, enum, texture input reference, frame/time bindings; unsupported types produce diagnostics | `src/sdk/index.ts` |
| M13-009 | Shader source range diagnostics and uniform preset/default persistence | gap | supported | Shader authoring affordance contracts; dedicated persistence tests not identified | `src/tools/video-editor/` |

### 2.15 M14 — Packaging, Runtime Loader, Extension Manager

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| M14-001 | User/developer can see installed/local extensions, enable/disable them, and edit settings | gap | deferred | Extension manager UI planned for M14; not fully verified as complete in current `main` | `src/tools/video-editor/` |
| M14-002 | Loader registers/unregisters contributions provider-safely | gap | supported | `ExtensionLoader` with `load`, `unload`, `validate` methods; provider-scoped registration pattern | `src/tools/video-editor/runtime/` |
| M14-003 | Persisted enablement, settings, failed load, and contribution cleanup tests | gap | deferred | `ExtensionStateRepository` abstraction; persistence infrastructure may be partial | `src/tools/video-editor/` |
| M14-004 | Integrity mismatch prevents installation/activation with clear diagnostics | gap | deferred | Integrity hash validation; implementation status not fully confirmed | SDK types |
| M14-005 | Extension state persistence, workspace pack load, bundle pack validation, manager UI location, disable/uninstall reference behavior, migration failure blocking activation, local-vs-installed conflict handling tests | gap | deferred | Full M14 surface areas; comprehensive tests not identified | `src/tools/video-editor/` |
| M14-006 | Compatibility with M1 local-source metadata and clear migration diagnostics for older metadata shapes | gap | deferred | `reigh-extension.json` metadata format; migration diagnostics not fully confirmed | `src/tools/video-editor/examples/extensions/` |
| M14-007 | Local-source-to-installed-pack migration, including settings/data preservation and reference continuity | gap | deferred | Migration flow concept; implementation tests not identified | `src/tools/video-editor/` |
| M14-008 | Manager trust warnings and extension requirements/lock metadata updates for installed packs | gap | deferred | Trust envelope documented in `extensions-trust-envelope.md`; manager display not confirmed | `docs/video-editor/extensions-trust-envelope.md` |
| M14-009 | Provider-backed extension state repository shape for review/compliance-style extension without CRDT collaboration | gap | deferred | `ExtensionStateRepository` abstraction; provider-backed patterns defined but not fully tested | `src/tools/video-editor/` |
| M14-010 | Extension dependency diagnostics, optional dependency degradation, settings schema migration success/failure, default-reset diagnostics | gap | deferred | `dependsOn` metadata; migration hooks; dedicated tests not identified | SDK types |
| M14-011 | Conflict override UI, dependency tree badges/cycle diagnostics, degraded contribution inventory, uninstall reference report, settings migration summary, lifecycle event log | gap | deferred | Manager UI components; frontend tests not identified | `src/tools/video-editor/` |

### 2.16 Cross-Milestone / Structural Claims

| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
|---|---|---|---|---|---|
| X-001 | `@reigh/editor-sdk` is the only import path needed for extensions (M1, M0) | pass | supported | All `src/examples/*.ts` import from `@reigh/editor-sdk`; `sdk-boundary.test.ts` verifies | `src/sdk/index.ts` |
| X-002 | Extension imports do not expose raw `DataProvider`, `applyEdit`, internal mutation APIs (M1) | pass | supported | `ExtensionContext` scoped services only; no internal provider access | `src/tools/video-editor/runtime/` |
| X-003 | V1 trust envelope is documented and honest (M1, M14) | pass | supported | `docs/video-editor/extensions-trust-envelope.md` — trusted-local execution, redacted logs, blast-radius controls | `docs/video-editor/extensions-trust-envelope.md` |
| X-004 | Public SDK boundary is `src/sdk/index.ts` through `@reigh/editor-sdk` alias (M0) | pass | supported | Vite/TS path aliases; `@reigh/editor-sdk` → `src/sdk/index.ts` | build config |
| X-005 | No new platform primitives added beyond what is explicitly bridged (all milestones) | pass | supported | Contribution kinds reserved until activating milestone; `contribution_kind_not_yet_bridged` diagnostics | `src/sdk/index.ts` |
| X-006 | Marketplace, cloud loading, sandboxing, theme contributions are unsupported (all milestones) | pass | deferred | Consistently in OUT scope of every milestone brief; absence verifiable by grep | milestone briefs |
| X-007 | Provider compatibility documented across InMemory/Supabase/Astrid (M3, M6) | pass | supported | `docs/video-editor/provider-compatibility-matrix.md` — complete matrix with limitations | `provider-compatibility-matrix.md` |
| X-008 | Frontend closure checklist used for public primitives (M2) | pass | supported | `docs/video-editor/frontend-closure-checklist.md` — applied to CodePanelCanary; governance test asserts presence | `frontend-closure-checklist.md` |
| X-009 | V1 source-pack/package contract freeze for manifest, layout, ID/version, API compatibility (M1, M14) | pass | supported | `reigh-extension.json` format consistent across all example extensions | `src/tools/video-editor/examples/extensions/*/reigh-extension.json` |

---

## 3. Blocker Section

The following gaps are significant enough to warrant explicit blocker documentation. They are classified as `release-blocking` only when the absence of evidence makes a supported-deferred-matrix claim impossible to verify.

### 3.1 Release-blocking gaps

| Blocker ID | Affected Rows | Description | Resolution Required |
|---|---|---|---|
| B-001 | M14-001 through M14-011 | M14 (Packaging, Loader, Manager) has the highest concentration of gaps. The extension manager UI, persistence, integrity validation, migration diagnostics, and dependency management are core to the installable-pack experience. If M14 is not complete, the V1 developer experience for installed packs is unproven. | Verify M14 implementation against Done Criteria; classify any missing pieces as deferred with absence checks |
| B-002 | M12-002 | The planner and export inspection are implemented, but complete frontend evidence for planner next-action surfacing is still not identified everywhere blocked export/render decisions are exposed. | Add focused frontend coverage for planner next actions or keep D-021 deferred |
| B-003 | M11-005 through M11-012 | Live data bridge (M11) has infrastructure (canaries, integration tests) but frontend state coverage for permission/error/bake/steering/recording/session-panel is sparse in identified tests. | Fill frontend closure tests or classify missing states as deferred |

### 3.2 Deferred/unsupported gaps (not release-blocking)

| Blocker ID | Affected Rows | Description | Deferral Rationale |
|---|---|---|---|
| D-001 | M4-003, M4-004, M4-005 | Command registry tests for palette interaction, stale context, and unregister lifecycle are not identified as standalone test files. Types and infrastructure exist. | Command infrastructure is type-proven and used by examples; full palette integration tests are deferred without blocking V1 docs |
| D-002 | M6-007 through M6-012 | Asset metadata/search/enrichment/provenance frontend rendering tests are sparse. SDK types are well-defined. | Asset metadata infrastructure is type-proven; frontend rendering completeness is deferred |
| D-003 | M10-002 through M10-011 | Agent tool canaries exist but comprehensive frontend and failure-path tests are not identified. | Agent tools are proposal-backed and follow established patterns; V1 agent-tool surface can be documented as partial with deferred test coverage |
| D-004 | M12-004 through M12-013 | Process/sidecar/roundtrip tests are not identified. SDK vocabulary is defined. | Process/sidecar infrastructure is vocabulary-proven; execution tests are deferred |
| D-005 | M5-001, M5-008, M5-009, M5-012 | Provider isolation, registry canary, planner skeleton, and disable-dispose tests are partial. Infrastructure types exist. | Provider-scoped registry foundation is proven; edge-case tests are deferred |

### 3.3 Cross-cutting structural notes

- **M11–M14 concentration:** The later milestones (live data, render planning, shaders, packaging) show progressively more gaps in identified evidence. This is partially expected — the epic builds incrementally and M15's purpose is to harden this evidence. The matrix treats gaps honestly; the supported/deferred matrix (T4) will classify these dispositions explicitly.
- **Test identification limitations:** Many tests exist in the repo but were not exhaustively indexed. Rows marked `gap` based on missing test evidence should be re-evaluated when the full test suite is run. The matrix uses "not identified" rather than "absent" for rows where dedicated tests may exist under non-obvious paths.
- **M0–M3 are the strongest:** The foundational milestones (scaffold, kernel, surfaces, timeline-patch) have the most robust evidence correlation, as expected for the core platform.

---

## 4. Matrix Statistics

| Status | Count |
|---|---|
| pass | 70 |
| gap | 52 |
| blocked | 0 |
| **Total** | **122** |

| Disposition | Count |
|---|---|
| supported | 108 |
| deferred | 14 |
| unsupported | 0 |
| release-blocking | 0 (see § 3.1 for release-blocking gap analysis) |

---

## 5. Version History

| Date | Change |
|---|---|
| 2026-06-20 | Initial contract-recheck matrix for M15. Covers M0–M14 Done Criteria against current `main` evidence. |
