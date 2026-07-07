# Trust And Security Posture — Reigh Video Editor V1

**Status:** Active (M5)
**Last updated:** 2026-07-07
**Scope:** Honest description of the current trusted/unsandboxed execution posture. This document records what *is* — not what is planned or aspirational. The posture described here is the locked V1 posture.

---

## 1. Execution Model

Extensions execute as **trusted, unsandboxed code** in the host browser environment.

| Property | V1 Reality |
|---|---|
| Execution context | Same-thread, same-origin JavaScript as the Reigh editor |
| Process isolation | None — no Worker, no iframe, no ShadowRealm boundary |
| DOM access | Full same-origin DOM access |
| Network access | Full same-origin `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource` |
| Browser APIs | Unrestricted access to all browser APIs available to the host origin |
| Storage | `localStorage` (scoped to `reigh.ext.<id>.*` keys), `sessionStorage`, IndexedDB |
| Package loading | Extensions are statically bundled with the host Vite/TypeScript build; no dynamic `import()`, no CDN fetches |

There is **no sandbox, no iframe isolation, no CSP subdivision, and no process boundary** between extensions and the host.

---

## 2. Access Disclosure Model

### 2.1 Manifest permissions are declarative access disclosures

The `permissions` field in `reigh-extension.json` remains named for manifest compatibility, but each entry is a **non-enforced declarative access disclosure**. The field is validated and frozen by `defineExtension()`, but it is descriptive metadata only. An extension that declares `network: false` can still call `fetch()`. The field exists so extension authors can document their intent today, and so the schema is stable if a future isolation or brokered-host-API epic introduces real capability enforcement.

**There is no runtime permission enforcement, no permission broker, and no capability-based gating in V1.**

```typescript
// From src/sdk/index.ts — ExtensionPermissionDeclaration
interface ExtensionPermissionDeclaration {
  reason: string;
  posture?: {
    network?: boolean;
    filesystem?: boolean;
    env?: boolean;
    processes?: boolean;
  };
}
```

### 2.2 What access disclosures are NOT

- They are **not enforced at runtime**.
- They are **not** presented to users as a permission prompt.
- They are **not** used to gate browser API access.
- They are **not** a sandbox declaration.
- They are **not** a substitute for code review.

---

## 3. Trust Warning

The Extension Manager displays a persistent trust warning during loading, empty, populated, selected-package, and error states:

> ⚠️ Trusted-local extension: this extension executes with full browser-renderer privileges. Review the extension source before enabling it in a shared project.

This warning is a **product requirement**, not just documentation. It must remain visible in all manager states.

**Implementation:** `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx` — trust warning rendered in the PackageCard component.

---

## 4. Error Containment

### 4.1 Contribution-level error boundaries

React-rendered extension contributions (slots, panels, inspector sections, dialogs, overlays) are wrapped in `HostContributionErrorBoundary` (`src/tools/video-editor/runtime/ContributionErrorBoundary.tsx`). When an extension-owned contribution crashes during render:

1. The boundary catches the error and renders a fallback UI (preserved from the original `ContributionErrorBoundary`).
2. A structured diagnostic is published with the extension ID and contribution ID.
3. A "View diagnostics" action links to the `DiagnosticPanel` filtered to the failing extension.
4. The boundary supports **bounded auto-retry** (max 3 retries, 5-second debounce) when recovery keys change.

### 4.2 What is NOT contained

- Errors thrown in `activate()` are captured as lifecycle diagnostics; the extension transitions to `failed` state.
- Errors thrown in event handlers, timers, or async callbacks are **not** caught by error boundaries.
- Errors thrown from `dispose()` are captured as diagnostics but never propagated — the `DisposeHandle` contract requires idempotent, non-throwing disposal.
- Non-React paths (e.g., direct DOM manipulation, canvas operations) are not wrapped.

**Authors must handle their own errors** in non-React execution paths and use `ctx.services.diagnostics.report()` to publish structured error information.

---

## 5. Diagnostic Provenance

Every diagnostic carries a `source` field that identifies its provenance:

| Source | Meaning | Set by |
|---|---|---|
| `extension` | Authored by a trusted local extension | `createExtensionDiagnosticsService.report()` (lifecycle host pins this) |
| `render` | Emitted by the host render pipeline | Host renderability checks (`runExportGuard()`, planner) |
| `provider` | Emitted by a host provider | Editor runtime, lifecycle host |

**Extensions cannot spoof diagnostic provenance.** In `src/tools/video-editor/runtime/extensionLifecycle.ts`, `createExtensionDiagnosticsService.report()` always pins `source: DIAGNOSTIC_SOURCE_EXTENSION` and overwrites any `extensionId` passed by the caller with the lifecycle-owned extension ID. The SDK contract (`src/sdk/index.ts`) declares that extensions MUST NOT set host-owned sources.

**Capacity:** Per-extension diagnostic capacity is bounded (default 100) with oldest-first eviction. Diagnostics from disposed extensions are cleaned up automatically during lifecycle disposal.

---

## 6. Recovery Key System

The `ExtensionLifecycleHost` (`src/tools/video-editor/runtime/extensionLifecycle.ts`) owns a monotonic recovery-key registry per extension. Recovery keys are:

- **Monotonic**: initialized to `"1"` on first activation, incremented on manifest change, re-add, or explicit retry.
- **Stable**: unchanged across no-op synchronize calls.
- **Lifecycle-owned**: the lifecycle host, not the extension or the UI, controls key increments.
- **Not user-controlled**: there is no public API for extensions to reset their own recovery key.

When `HostContributionErrorBoundary` detects a recovery key change for the owning extension, it resets the error state and re-renders the children — exactly once per key change. The bounded retry loop (max 3 retries with 5-second debounce) prevents infinite crash loops from persistent render errors.

---

## 7. Surface Audit: What Uses Recovery-Aware Boundaries

All production contribution boundaries that have a known owning extension are migrated to `HostContributionErrorBoundary`:

| Surface | File | Owner Resolution |
|---|---|---|
| Timeline slots (14 boundaries) | `TimelineEditorShellCore.tsx` | `slotOwnerMap` memo — resolves slot name → extensionId from manifest contributions |
| Inspector sections | `PropertiesPanel.tsx` | `extensionRuntime.contributionOwnerMap` via `useOptionalVideoEditorRuntime()` |
| Asset panel surface | `VideoEditorAssetPanelSurface.tsx` | `extensionRuntime.contributionOwnerMap` |
| Clip panel | `ClipPanel.tsx` | `clipTypeRegistryRecord.ownerExtensionId` |

When no extensionId is available or the runtime context is unavailable, the boundary falls back to legacy behavior (children-change reset, no recovery key).

---

## 8. Extension Manager Inventory Truthfulness

The Extension Manager (`src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx`) uses `PackageStateInventoryEntry[]` as the card source of truth:

- **Direct host-supplied extensions** appear as read-only entries with `stateReason: 'Direct host-supplied extension'`, a "Direct" badge, and no install/update/toggle affordances.
- **Managed (repository-backed) extensions** show load/enable/disable state from the loader.
- **Disabled/error packages** surface manifest-derived `PackageContributionSummary` (computed by `computePackageContributionSummary()` in `extensionSurface.ts`) so contribution counts and kind labels survive without active runtime descriptors.
- The inventory is **not** a marketplace, install surface, or update manager. Direct entries cannot be installed, updated, or toggled.

---

## 9. What V1 Does NOT Provide

V1 explicitly does **not** provide:

| Feature | Status |
|---|---|
| Sandbox / iframe isolation | **Not present.** Extensions run in the same JS context as the host. |
| Permission enforcement / broker | **Not present.** Manifest permissions are non-enforced declarative access disclosures only. |
| Code signing / integrity verification at load time | **Not present.** Source vetting is human review only. |
| Marketplace / extension registry | **Not present.** Extensions are statically bundled or loaded from local source. |
| Remote extension installation or update | **Not present.** No remote fetch, no CDN, no dynamic `import()`. |
| CSP subdivision | **Not present.** |
| Process isolation (Worker, ShadowRealm) | **Not present.** |
| Capability-based security proxy | **Not present.** |
| User-facing permission prompts for extension capabilities | **Not present.** |
| Automated provenance chain / audit log for extension actions | **Not present.** |

---

## 10. Future Isolation Or Brokered Enforcement Epic

Sandboxing, brokered host APIs, permission enforcement, integrity verification, and user-facing permission prompts are deferred to a future isolation or brokered-host-API epic beyond M5. Before extensions can be safely loaded from untrusted sources, all four must exist:

1. Capability enforcement (manifest access disclosures gate host-mediated browser API access).
2. Process isolation (separate JavaScript realm with capability-based host proxy).
3. Integrity verification (content hashing and signature verification for remote sources).
4. User-facing permission prompts (host presents permission dialog before granting capabilities).

Until then, the posture is explicit: **every extension is trusted code with the same privileges as the Reigh editor itself.**

---

## 11. Cross-Reference

| Document | Relevance |
|---|---|
| `docs/video-editor/extensions-trust-envelope.md` | Original M1 trust envelope (parent document for §1–§6) |
| `docs/video-editor/extension-author-contract.md` | Author-facing contract including trust obligations |
| `docs/video-editor/extension-platform-contract-recheck.md` | M0–M14 Done Criteria evidence matrix |
| `src/sdk/index.ts` | Public SDK types including `ExtensionPermissionDeclaration`, `DiagnosticSource`, `DisposeHandle` |
| `src/tools/video-editor/runtime/extensionLifecycle.ts` | Lifecycle host with recovery-key registry and diagnostic provenance pinning |
| `src/tools/video-editor/runtime/ContributionErrorBoundary.tsx` | `HostContributionErrorBoundary` and `ContributionErrorBoundary` |
| `src/tools/video-editor/runtime/extensionSurface.ts` | Runtime normalization, `PackageContributionSummary`, `PackageStateInventoryEntry` |
| `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx` | Extension manager UI with trust warning and direct-entry read-only rendering |

---

## 12. Version History

| Date | Change |
|---|---|
| 2026-07-07 | Reframed manifest `permissions` entries as non-enforced declarative access disclosures and explicitly deferred true isolation or brokered enforcement to a future epic. |
| 2026-06-24 | Initial trust and security posture document for M5. Covers execution model, permission posture, error containment, diagnostic provenance, recovery keys, boundary audit, inventory truthfulness, and explicit non-provision of sandbox/marketplace/install/update. |
