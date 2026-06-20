# Extensions Trust Envelope (V1 — Trusted-Local)

## Status

**Milestone:** M1 (SDK Kernel & Trusted Local Extension Runtime)
**Last updated:** 2026-06-19
**Posture:** Honest trusted-local. Extensions execute with **full browser-renderer privileges** in the same JavaScript context as the Reigh editor. No sandboxing, no process isolation, no capability-based enforcement exists in M1.

---

## 1. Trust posture for V1

In M1, every extension is a **trusted-local extension**. This means:

- The extension source is **vetted by the project owner / developer** before it is added.
- At runtime the extension runs **in the same browser JavaScript context** as the Reigh video editor (same thread, same origin, same DOM).
- There is **no sandbox, no iframe isolation, no CSP subdivision, and no process boundary** between the extension and the host.
- The `permissions` field in the manifest is **purely descriptive** — it documents the extension author's intent but has no runtime enforcement. See [§ 3](#3-permission-metadata-descriptive-until-sandboxing-exists).

> ⚠️ **Warning** (emitted at activation by the flagship local extension):
> *"Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project."*

---

## 2. Capability visibility table

The table below lists each capability surface, its V1 posture, how the host surfaces it (logs, diagnostics, console grouping), and the earliest milestone where enforcement or isolation is expected.

| Capability | V1 posture | Host visibility | Earliest enforcement milestone |
|---|---|---|---|
| **Parser code** (contribution kind `parser`) | Manifest-declared only. No custom parser loading or execution. The kind is reserved (M4). | Info diagnostic: `runtime/contribution-kind-not-yet-bridged`. No runtime dispatch. | M4 |
| **Package loading** (`npm` / CDN / dynamic import) | Extensions are statically bundled with the host app. No dynamic package loading, no CDN fetches, no `import()` for extension code. The extension module graph is part of the host Vite/TypeScript build. | Not surfaced — there is no package-loading API. | M4+ (if ever) |
| **Edge-tool declarations** (contribution kind `agentTool`) | Manifest-declared only. No agent tool loading or execution. The kind is reserved (M5). | Info diagnostic: `runtime/contribution-kind-not-yet-bridged`. No runtime dispatch. | M5 |
| **Browser permission helpers** (`navigator.permissions`, clipboard, notifications, etc.) | Extensions have **unrestricted access** to all browser APIs available to the host origin — same as any script on the page. No permission gating, no user-prompt mediation. | Not mediated by the extension runtime. Standard browser permission prompts (e.g. clipboard) fire as usual — the host does not intercept them. | M4+ (if a permission model is introduced) |
| **Local processes** (`ProcessManifestEntry`) | Manifest-declared only. The `processes` field is validated and frozen but **no subprocess is spawned**. The `ProcessSpawnConfig` shape (command, args, env, cwd) exists in the SDK types but is not wired to any launcher. | Not surfaced — processes are not spawned. | M5+ (if local process support is introduced) |
| **Filesystem** | Extensions have **same-origin access** to `localStorage` (scoped per-extension via the `reigh.ext.<id>.` key prefix), `sessionStorage`, and IndexedDB. No direct filesystem API (`showOpenFilePicker`, File System Access API) is mediated or restricted by the extension runtime. | Settings reads/writes/deletes are scoped to `reigh.ext.<id>.*` localStorage keys. All keys written during an activation are cleaned up on dispose by `disposeHostServices()`. Not logged to diagnostics by default (internal to the settings service). | M4+ |
| **Environment variables** | No access to server-side environment variables. The browser has no `process.env`. Build-time env vars (`VITE_*`) are inlined by Vite and available to all code equally — no per-extension gating. | Not surfaced. | N/A (browser constraint) |
| **Network** | Extensions can use `fetch`, `XMLHttpRequest`, `WebSocket`, and `EventSource` with the same origin/CORS rules as the host page. The runtime does **not** intercept, throttle, or log network requests. | Not surfaced by the extension runtime. Standard browser dev-tools network tab applies. | M4+ |
| **Dev-console grouping** | Activation and deactivation are wrapped in `console.groupCollapsed` / `console.groupEnd` with the extension ID as the label. This makes extension lifecycle boundaries visible in the browser console. | Console groups: `[Extension lifecycle] com.reigh.examples.flagship-local` at activation time. Activation start, success, and failure are logged with `console.log`/`console.error`. | N/A (already visible) |
| **Diagnostics (structured)** | Extension code can emit structured `ExtensionDiagnostic` records (severity + code + message) via `ctx.services.diagnostics.report()`. The host collects and surfaces these in the `ExtensionRuntime.diagnostics` array. Export guard diagnostics use the same shape but with export-prefixed codes. | Diagnostics are frozen, collected per-extension, and readable via `ctx.services.diagnostics.diagnostics`. Lifecycle errors (activation/teardown throws) are captured as diagnostics automatically. | N/A (already visible) |
| **Chrome toasts / progress** | `ctx.chrome.toast()` and `ctx.chrome.progress()` call into the host chrome service. In dev, toasts are echoed to `console.log`/`console.warn`/`console.error`. Progress updates are dispatched to chrome subscribers. | Console echo of toast messages. Subscribers receive typed payloads (`ChromeToastPayload`, `ChromeProgressPayload`). | N/A (already visible) |
| **Shutdown / dispose** | The lifecycle host calls `dispose()` on every `DisposeHandle` returned by `activate()`. Host-owned services (settings localStorage keys, chrome event subscribers) are cleaned up via `disposeHostServices()` attached to the context via `CONTEXT_DISPOSE_SYMBOL`. Provider unmount calls `disposeAll()` idempotently. | Disposal success is silent. Disposal failures are captured as `error`-severity diagnostics (code: `lifecycle/teardown-error`) — the lifecycle never throws from dispose. | N/A (already visible via diagnostics) |
| **Export guard diagnostics** | Before render, `runExportGuard()` scans the timeline config for unknown clip types, effects, and transitions. Extension-declared IDs (from inactive contributions) are checked as metadata but do **not** gate render dispatch — they produce `warning`-severity diagnostics instead of `error`. Truly unknown IDs produce `error`-severity diagnostics. | Diagnostics are emitted into `ExportGuardResult.diagnostics` and surfaced via the render log/status. The empty-extension-runtime fast path skips the guard entirely. | M3 (when effect/transition/clipType contributions become active) |

---

## 3. Permission metadata (descriptive until sandboxing exists)

The `ExtensionPermissionDeclaration` type in `@reigh/editor-sdk` has two fields:

```typescript
interface ExtensionPermissionDeclaration {
  /** Human-readable reason the permission is requested. */
  reason: string;
  /** Declared posture: what the extension states it accesses. */
  posture?: {
    network?: boolean;
    filesystem?: boolean;
    env?: boolean;
    processes?: boolean;
  };
}
```

In M1:

- The `permissions` array in an extension manifest is **validated and frozen** by `defineExtension()`.
- It is carried through runtime normalization as part of the frozen manifest.
- **No runtime enforcement** is performed — an extension that declares `network: false` can still call `fetch()`.
- The field exists so extension authors can **document their intent** today, and so the schema is stable when sandboxing / capability enforcement is introduced in a later milestone.

**Expected enforcement milestone:** M4 or later, when a sandboxing layer (iframe isolation, CSP subdivision, or a capability-based proxy) is introduced.

---

## 4. Activation lifecycle (visible boundaries)

Every extension activation is wrapped in visible console grouping:

```
console.groupCollapsed('[Extension lifecycle] com.reigh.examples.flagship-local')
  console.log('Activating extension "com.reigh.examples.flagship-local" (v1.0.0)')
  // ... extension activate() runs ...
  console.log('Extension "com.reigh.examples.flagship-local" activated successfully')
console.groupEnd()
```

If activation throws:
```
console.error('Extension "com.reigh.examples.flagship-local" failed during activation')
// Error details are included in the console group and captured as a lifecycle diagnostic.
```

Deactivation/disposal is similarly grouped. All lifecycle state transitions (inactive → activating → active → deactivating → disposed) emit structured diagnostics via the per-extension diagnostics service.

---

## 5. What "trusted-local" does NOT mean

| Assertion | Reality in V1 |
|---|---|
| "The extension is sandboxed." | **False.** No sandbox exists. |
| "The extension can only access declared permissions." | **False.** Permissions are descriptive metadata only. |
| "The extension's network access is limited." | **False.** Full same-origin `fetch` access; no runtime mediation. |
| "The extension runs in a Web Worker." | **False.** Extensions run on the main thread, same as the host. |
| "The extension can't access the DOM." | **False.** Extensions have full DOM access (same origin). |
| "The extension's errors can't break the editor." | **Mostly false.** Contribution-level error boundaries (`ContributionErrorBoundary`) catch React render errors within extension-contributed slots/dialogs/panels/inspector sections, but an extension can still throw in `activate()` or in non-React paths (event handlers, timers) and those errors are **not** caught by an error boundary. Activation-time throws are captured as diagnostics and the extension transitions to `failed` state. |

---

## 6. When will sandboxing arrive?

Sandboxing is tracked as future work beyond M1. The current trust model is appropriate for:

- **Personal projects** where the developer authors or vets all extensions.
- **Internal team workflows** where extensions are shared as source code and reviewed.
- **Open-source extensions** where the source is publicly auditable.

Before extensions can be safely loaded from untrusted sources (e.g. a marketplace, a URL, or a third-party package registry), the following must exist:

1. **Capability enforcement:** The `permissions` field must gate actual browser API access (network, filesystem, etc.).
2. **Process isolation:** Extensions must run in a separate JavaScript realm (iframe, Worker, or ShadowRealm) with a capability-based proxy to the host.
3. **Integrity verification:** Extensions loaded from remote sources need content hashing and signature verification.
4. **User-facing permission prompts:** The host must present a permission dialog before granting capabilities.

These are planned for M4–M5. Until then, treat every extension as trusted code that has the same privileges as the Reigh editor itself.

---

## 7. Summary

| Concern | V1 answer |
|---|---|
| Execution context | Same-thread, same-origin JavaScript in the browser |
| Isolation | None |
| Permission enforcement | Descriptive only (no runtime gating) |
| Lifecycle visibility | Console groups + structured diagnostics + export guard |
| Service cleanup | Idempotent dispose (settings localStorage, chrome subscribers, DisposeHandle) |
| Error containment | Contribution-level error boundaries for React slots; activation-time throws → `failed` state + diagnostics |
| Export safety | Pre-render scan warns/errors on unknown clip types, effects, and transitions; inactive extension-declared IDs are surfaced as metadata |
| Source vetting | Human review required; no automated integrity checks in M1 |
