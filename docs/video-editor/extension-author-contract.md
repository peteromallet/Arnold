# Extension Author Contract — Reigh Video Editor V1

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Audience:** Extension authors who need to understand the exact contractual guarantees, obligations, and limitations of the V1 extension platform.
**Prerequisite gate:** [Example readiness](./extension-platform-supported-deferred.md) (M15 pre-doc gate, passed 2026-06-20).

---

## 1. Purpose

This document defines the **developer contract** between extension authors and the Reigh V1 extension platform. It specifies:

1. What the platform **guarantees** to extension authors (invariants, lifecycle, services).
2. What extension authors **must** do (import boundary, dispose contract, diagnostic conventions).
3. What is **explicitly deferred** or **unsupported** in V1.

This contract is backed by the [supported/deferred matrix](./extension-platform-supported-deferred.md) (91 supported rows, 69 deferred rows) and the [trust envelope](./extensions-trust-envelope.md). Every supported claim is traceable to concrete evidence — tests, examples, absence checks, or contract-recheck rows.

---

## 2. Platform guarantees

### 2.1 Public SDK boundary

| Guarantee | Evidence |
|---|---|
| `@reigh/editor-sdk` is the **only** public import path for extensions | S-001, S-154 |
| Package aliases resolve `@reigh/editor-sdk` → `src/sdk/index.ts` | S-002 |
| The SDK boundary test runs without importing editor internals | S-003, S-154 |
| No internal `DataProvider`, `applyEdit`, or mutation escape hatches leak from SDK entrypoints | S-014, S-152 |
| SDK exports are governed by a public-export allowlist (`config/governance/sdk-public-export-allowlist.json`) | S-152 |

**Author obligation:** Import exclusively from `@reigh/editor-sdk`. Internal imports (`src/tools/video-editor/`, `@/tools/`, etc.) are violations. The pre-doc example readiness gate enforces this mechanically.

### 2.2 Extension lifecycle

| Guarantee | Evidence |
|---|---|
| Extensions are imported, registered, and rendered by the host provider | S-010 |
| Provider-scoped lifecycle: activate → deactivate → dispose per provider instance | S-012 |
| Removing an extension from provider props unregisters its contributions | S-013 |
| Activation/deactivation wrapped in visible `console.groupCollapsed`/`console.groupEnd` | S-016 |
| Lifecycle teardown failures captured as diagnostics, never thrown | S-017 |
| HMR-safe re-registration and stale component cleanup | S-015 |
| `DisposeHandle` contract: idempotent, must not throw | S-005 |

**Author obligation:** The `dispose()` function returned from `activate()` must be **idempotent** (safe to call multiple times) and **must not throw**. The platform guarantees disposal failures are captured as diagnostics; the author must not rely on dispose exceptions for error signalling.

### 2.3 Contribution surfaces

| Guarantee | Evidence |
|---|---|
| Host slots: header, toolbar, leftPanel, rightPanel, codePanel, writingPanel, stagePanel, timelineFooter, statusBar, dialogs, assetPanel, inspectorPanel | S-020 |
| Inspector and overlay contributions update on host state changes | S-021 |
| `SchemaForm` renders and validates common schema subset | S-022 |
| `ExtensionManager` settings editing uses `SchemaForm` when a `settingsSchema` is declared in the manifest; falls back to raw key-value editing only for schemaless or legacy packages (intentional, not a missing implementation) | T10 |
| Diagnostic fallback links open `DiagnosticPanel` filtered to failing extension | S-023 |
| Reserved frontend component slots compile as inert placeholders | S-025 |
| Frontend closure checklist documented and applied | S-027 |

**Author obligation:** Contributions declared in the manifest are validated at definition time. Contribution IDs must be unique within the extension. Unknown contribution kinds produce `contribution_kind_not_yet_bridged` diagnostics rather than silent failures.

### 2.4 Timeline patch system

| Guarantee | Evidence |
|---|---|
| Safe insert/update/delete/reorder clips via `TimelineOps` | S-030 |
| Proposal preview without mutating real timeline | S-031 |
| Accept/reject with stale base version detection | S-032 |
| Undo/rollback for patch batches | S-033 |
| Relative/fractional ordering for clip positioning | S-034 |
| Provider version behaviours tested (InMemory, Supabase, Astrid) | S-035 |
| Patch extension mechanism with validation, serialization, previewability | S-038 |
| Extension project-data persistence, oversized payload rejection with diagnostics | S-039 |
| Source-to-timeline and timeline-to-source navigation metadata | S-040 |

**Author obligation:** Patches must include a `source` field identifying the extension, a `version` matching the base snapshot, and valid operations. Oversized project-data payloads are rejected with diagnostics.

### 2.5 Commands, keybindings, and context menus

| Guarantee | Evidence |
|---|---|
| Command, keybinding, palette, and context menu contributions supported | S-050 |
| Deterministic shortcut conflict resolution (first-registered-wins) | S-051 |

**Author obligation:** Command IDs should be namespaced under the extension ID (e.g. `com.example.myExt.myCommand`). Shortcut conflicts are resolved at registration time — later registrations for the same key sequence produce diagnostics.

### 2.6 Services available during activation

| Service | Path | Guarantee |
|---|---|---|
| Chrome (toast, progress, focus, announce, subscribe) | `ctx.chrome` | S-010, S-016 |
| Settings (localStorage-backed, scoped, defaults) | `ctx.services.settings` | S-001 |
| Internationalisation (message bundle, placeholder substitution) | `ctx.services.i18n` | S-010 |
| Diagnostics (structured severity+code+message reporting) | `ctx.services.diagnostics` | S-006, S-024 |
| Commands (imperative handler registration) | `ctx.commands` | S-050 |
| Effects (trusted component registration) | `ctx.effects` | S-080, S-081 |
| Transitions (renderer registration) | `ctx.transitions` | S-090 |
| Clip types (renderer + inspector registration) | `ctx.clipTypes` | S-100–S-105 |
| Shaders (WebGL source + uniform registration) | `ctx.shaders` | S-130–S-135 |
| Agent tools (tool handler + process stubs) | `ctx.agentTools` | S-110–S-112 |
| Creative context (timeline reader/patch, source map, proposal runtime) | `ctx.creative` | S-030–S-040 |

---

## 3. Diagnostic contract

### 3.1 Diagnostic shape

Every diagnostic published by an extension must conform to:

```typescript
interface ExtensionDiagnostic {
  severity: 'error' | 'warning' | 'info';
  code: string;          // Dot-separated, extension-scoped (e.g. 'myExt/validation-failed')
  message: string;       // Human-readable, no newlines
  extensionId?: string;  // Populated automatically by the diagnostics service
  contributionId?: string;
  milestone?: string;    // Earliest milestone that activates this feature
  detail?: Record<string, unknown>; // Structured data (clip references, effect IDs, etc.)
}
```

### 3.2 Export diagnostics

Export-scoped diagnostics use `export/`-prefixed codes and carry timeline-specific detail:

```typescript
interface ExportDiagnostic extends ExtensionDiagnostic {
  code: `export/${string}`;
  detail?: Record<string, unknown> & {
    clipId?: string;
    clipType?: string;
    effectType?: string;
    transitionType?: string;
    shaderId?: string;
  };
}
```

### 3.3 Diagnostic conventions

- **Error** severity: the extension cannot proceed in its current state (e.g. required data missing, incompatible API version).
- **Warning** severity: something is unexpected but the extension can continue (e.g. unknown clip type from an inactive contribution).
- **Info** severity: lifecycle events, configuration summaries, analysis results.

**Author obligation:** Use diagnostic codes that are namespaced under the extension (e.g. `myExtension/validation-failed`). Avoid generic codes like `error` or `failed`.

---

## 4. Manifest contract

### 4.1 Required fields

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique extension ID (validated by `validateExtensionId()`) |
| `version` | `string` | Semver (e.g. `1.0.0`) |
| `label` | `string` | Human-readable display name |
| `apiVersion` | `number` | Must be `1` in V1 |

### 4.2 Optional fields

| Field | Type | Description |
|---|---|---|
| `description` | `string` | Human-readable description |
| `contributions` | `ExtensionContribution[]` | One or more contribution declarations |
| `settingsDefaults` | `Record<string, unknown>` | Default values for extension settings |
| `settingsSchema` | `SettingsSchema` | Schema definition for settings validation (deferred, M14) |
| `messages` | `Record<string, string>` | I18n message bundle with `{{placeholder}}` syntax |
| `permissions` | `ExtensionPermissionDeclaration[]` | **Descriptive only** in V1 (no enforcement) |
| `processes` | `ProcessManifestEntry[]` | Reserved — validated and frozen, but no subprocess spawning |
| `dependsOn` | `ExtensionDependency[]` | Reserved — validated and frozen, no runtime resolution |
| `migrations` | `SettingsMigration[]` | Reserved — validates shape, migration execution deferred (M14) |

### 4.3 Manifest immutability

`defineExtension()` deep-freezes the manifest. Extension IDs, contribution IDs, and all literal values are preserved through the frozen object. Authors must not mutate the manifest after definition.

### 4.4 Source-pack contract

Extension packages share a common manifest format (`reigh-extension.json`) with 8 consistent examples in the repository. The format is frozen for V1 (S-153). See any extension directory (e.g. `flagship-local/reigh-extension.json`) for the canonical shape.

---

## 5. Trust envelope obligations

### 5.1 Trusted-local warning

Extensions that execute with full browser privileges must emit the trusted-local warning. The flagship-local extension demonstrates this pattern (docs-safe, EXT). The warning text is standardised in the trust envelope:

> ⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.

### 5.2 Permission posture

The `permissions` field in the manifest is **descriptive only** in V1. An extension that declares `network: false` can still call `fetch()`. Authors must:

1. Declare permissions honestly — they document intent for future enforcement milestones (M4–M5).
2. Not rely on permission gating for security — there is no runtime enforcement.

### 5.3 Error boundaries

The platform provides `ContributionErrorBoundary` for React-rendered slots, dialogs, panels, and inspector sections. Authors must:

1. Handle errors in non-React paths (event handlers, timers, async callbacks) themselves — these are not caught by error boundaries.
2. Use `ctx.services.diagnostics.report()` to publish structured error information.
3. Not throw from `dispose()` — the platform captures teardown failures as diagnostics.

### 5.4 Service cleanup

The platform cleans up host-owned services (settings localStorage keys, chrome event subscribers) on dispose via `CONTEXT_DISPOSE_SYMBOL`. Authors must:

1. Return a `DisposeHandle` from `activate()` that cleans up extension-owned resources.
2. Call `.dispose()` on any handles received from service registrations (`ctx.commands.registerCommand()`, `ctx.clipTypes.registerClipType()`, etc.).
3. Not rely on host service cleanup order — dispose handles are called before host services.

---

## 6. Renderability contract

### 6.1 Render capability metadata

The platform exports renderability metadata available to export guards:

```typescript
interface RenderCapability {
  // ... (see src/sdk/index.ts for full shape)
}

interface ContributionRenderability {
  // ... 
}

interface RenderBlocker {
  // ...
}
```

### 6.2 Export guard integration

Before render, `runExportGuard()` (S-062) scans the timeline for unknown clip types, effects, and transitions:

- Extension-declared IDs from **inactive** contributions → `warning` diagnostics
- **Unknown** IDs (no declaring extension) → `error` diagnostics → export blocked

### 6.3 Author obligations

1. Declare all clip type, effect, and transition IDs in the manifest contributions.
2. Set `allowBrowserExport` and `allowWorkerExport` honestly for effects and transitions.
3. Check renderability metadata before attempting export workflows.
4. Do not rely on the render planner (deferred, M12) — V1 export uses the ad hoc guard.

---

## 7. Packaging and distribution

### 7.1 V1: Source-local only

In V1, extensions are **statically bundled** with the host application. There is no dynamic package loading, no CDN fetching, no `import()` for extension code, and no marketplace.

### 7.2 What is deferred

The entire extension packaging and manager system (M14) is deferred:

| Deferred capability | Deferral ref |
|---|---|
| User-facing extension manager UI | D-001 |
| Persisted enablement, settings, failed load handling | D-002 |
| Integrity verification prevents installation | D-003 |
| Extension state persistence, workspace pack load | D-004 |
| Migration diagnostics for older metadata shapes | D-005 |
| Local-source-to-installed-pack migration | D-006 |
| Manager trust warnings and requirements/lock metadata | D-007 |
| Provider-backed extension state repository | D-008 |
| Extension dependency diagnostics | D-009 |
| Conflict override UI, dependency tree badges | D-010 |

### 7.3 What is unsupported

- Marketplace / extension registry (unsupported, D-123)
- Cloud extension loading
- Dynamic package loading from npm/CDN/`import()`
- Third-party extension hosting

---

## 8. Compatibility promises

### 8.1 SDK stability

The `@reigh/editor-sdk` entrypoint is the stable public boundary. Types and functions exported from `src/sdk/index.ts` follow semantic versioning:

- **Patch**: bug fixes, no breaking changes
- **Minor**: new types/functions, backward-compatible
- **Major**: breaking changes to public types or functions

### 8.2 Manifest format stability

The `reigh-extension.json` format is frozen for V1 (S-153). New optional fields may be added in minor versions; required fields will not change without a major version bump.

### 8.3 Provider compatibility

Three data providers are supported (S-140–S-143):

| Provider | Support level | Evidence |
|---|---|---|
| InMemory | Full M3 support, ephemeral Map-backed | S-140 |
| Supabase | Full M3 support, durable DB + append service | S-141 |
| Astrid Bridge | Partial M3 support, local filesystem + bridge API | S-142 |

Extension authors must not assume a specific provider. Use the public `TimelineReader.snapshot()` and `TimelineOps.apply()` interfaces — they abstract over provider differences.

---

## 9. Deferred and unsupported classification (author-facing)

### 9.1 Deferred (planned, not yet implemented)

These behaviours are documented as deferred in the supported/deferred matrix. Authors must not document them as available, and the pre-doc example readiness gate flags examples that demonstrate deferred behaviour as unsupported docs candidates.

| Area | Deferral IDs | Blocked by | Earliest |
|---|---|---|---|
| Extension manager & packaging | D-001–D-010 | B-001 | M14 |
| Render planner & export infrastructure | D-020–D-027 | B-002 | M12 |
| Live data bridge frontend | D-030–D-037 | B-003 | M11 |
| Agent tool frontend & edge cases | D-040–D-047 | — | M10 |
| Command test coverage | D-050–D-052 | — | M4 |
| Asset metadata frontend | D-060–D-064 | — | M6 |
| Provider registry edge cases | D-070–D-073 | — | M5 |
| Effect/transition test coverage | D-080–D-085 | — | M7–M8 |
| Clip-type UI integration | D-090–D-091 | — | M9 |
| Shader frontend & materializer | D-100–D-102 | — | M13 |
| TimelinePatch reserved ops | D-110–D-111 | — | Future |
| Permissions & sandboxing | D-120–D-122 | — | M4–M5 |
| Structural deferrals | D-130–D-135 | — | Various |

### 9.2 Unsupported (out of scope)

These behaviours are unsupported across all milestones:

| Behaviour | Classification | Evidence |
|---|---|---|
| Marketplace / extension registry | Unsupported | D-123, CR:X-006 |
| Cloud extension loading | Unsupported | Absence check |
| Sandboxed execution | Unsupported | Trust envelope §5 |
| Theme contributions | Unsupported | Absence check |
| Public CRDT collaboration primitives | Unsupported | Absence check |

---

## 10. Pre-doc example readiness gate

Before referencing examples in documentation, the following gate must pass:

```bash
node scripts/quality/check-extension-example-readiness.mjs --audit
```

This gate enforces:

1. Every `EX:` and `EXT:` evidence reference in a **supported** matrix row resolves to an existing file.
2. Example files demonstrating deferred/unsupported behaviour are flagged as unsupported docs candidates.
3. Every example file under `src/examples/` imports exclusively from `@reigh/editor-sdk`.
4. On-disk examples without a corresponding supported matrix row are reported as unclassified.

The gate outputs a JSON record of docs-safe example IDs. At the time of this document's writing, the gate passed with **22 docs-safe examples**, **0 failures**, and **8 unclassified warnings** (examples on disk not yet classified in the matrix).

### 10.1 Docs-safe examples (M15 gate pass)

| Category | Docs-safe IDs |
|---|---|
| SDK examples (`src/examples/`) | `toolbar-example`, `inspector-example`, `overlay-example`, `status-surface-example`, `code-panel-diagnostics-example`, `surface-coverage`, `command-extension`, `integrity-hash-parser-example`, `metadata-json-output-example`, `clip-type-keyframed-example`, `automation-recording-canary`, `writing-canary-example`, `stage-canary-example` |
| Extension examples (`src/tools/video-editor/examples/extensions/`) | `flagship-local`, `flagship-local-transition`, `agent-tools-canary`, `agent-tools-copilot`, `agent-tools-export`, `live-webcam-canary`, `live-generated-frame-canary`, `clip-local-shader-canary`, `postprocess-shader-canary` |

---

## 11. Cross-reference

| Document | Purpose |
|---|---|
| [extensions-quickstart.md](./extensions-quickstart.md) | Getting-started guide for new extension authors |
| [extension-platform-supported-deferred.md](./extension-platform-supported-deferred.md) | Canonical supported/deferred matrix (91 supported, 69 deferred) |
| [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md) | Complete M0–M14 Done Criteria evidence matrix |
| [extensions-trust-envelope.md](./extensions-trust-envelope.md) | V1 trusted-local execution model and permission posture |
| [provider-compatibility-matrix.md](./provider-compatibility-matrix.md) | DataProvider compatibility across InMemory/Supabase/Astrid |
| [timeline-patch-operations.md](./timeline-patch-operations.md) | Complete TimelinePatch operation reference |
| [shader-execution-model.md](./shader-execution-model.md) | M13 shader/WebGL bridge model |
| [frontend-closure-checklist.md](./frontend-closure-checklist.md) | Frontend state completeness for public primitives |

---

## 12. Version history

| Date | Change |
|---|---|
| 2026-06-20 | Initial author contract for M15. Written after pre-doc example readiness gate passed. All referenced examples are docs-safe. Deferred and unsupported classifications match the supported/deferred matrix. Trust envelope obligations included. Renderability, packaging, and compatibility promises codified. |
