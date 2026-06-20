# Extension Migration: Local Source → Installed Pack — Reigh Video Editor V1

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Audience:** Extension authors migrating from a statically-bundled local extension to an installed-pack workflow, and developers planning for the deferred M14 packaging milestone.
**Prerequisite:** [Extension Author Contract](./extension-author-contract.md), [Supported/Deferred Matrix](./extension-platform-supported-deferred.md).

---

## 1. Purpose

This document describes the migration path from V1's current **source-local** extension model to the planned **installed-pack** model (M14). It covers settings preservation, manifest format continuity, reference continuity (clip types, effects, transitions), provider-backed state repository contracts, and the explicit boundaries between what is available now and what is deferred.

**Critical honesty:** In V1 (M1–M13), extensions are **statically bundled** with the host application. There is no dynamic package loading, no CDN fetching, no `import()` for extension code, and no marketplace. The entire installed-pack workflow is **deferred** to M14. This document explains what you can do **today** to prepare, and what the migration will look like when M14 lands.

---

## 2. V1 posture: source-local only

### 2.1 Current reality

In the current V1, extensions are:

- **Statically bundled** with the host Vite/TypeScript build.
- **Imported directly** by the host application and passed into the editor provider via props.
- **Loaded synchronously** at application startup — no async extension resolution, no network lookups.
- **Vetted by human review** — there is no automated integrity verification in V1.

```typescript
// Current V1 pattern: direct import, provider-scoped injection
import { flagshipLocalExtension } from '@/tools/video-editor/examples/extensions/flagship-local';

// In the host component:
<VideoEditorProvider extensions={[flagshipLocalExtension]}>
  {/* editor shell */}
</VideoEditorProvider>
```

**Evidence:** [Author Contract §7.1](./extension-author-contract.md#71-v1-source-local-only); [Trust Envelope §2](./extensions-trust-envelope.md#2-capability-visibility-table) (Package loading row); [Contract-Recheck CR:X-006](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims).

### 2.2 What you cannot do today

| Action | Status | Reference |
|---|---|---|
| Install an extension from a URL or marketplace | Unsupported | D-123, CR:X-006 |
| Load an extension dynamically via `import()` | Deferred | Trust Envelope §2 |
| Verify extension integrity with a content hash | Deferred | D-003, B-001 |
| Manage installed extensions through a UI | Deferred | D-001, B-001 |
| Persist extension enablement/disablement across sessions | Deferred | D-002, B-001 |
| Resolve extension dependencies at runtime | Deferred | D-009, B-001 |

---

## 3. What "migration" means

### 3.1 The two extension models

| Aspect | Source-local (V1 current) | Installed pack (M14 planned) |
|---|---|---|
| **Loading** | Statically imported, bundled with host | Loaded from a workspace pack or bundle at runtime |
| **Storage** | In repo (`src/tools/video-editor/examples/extensions/`) | Provider-backed extension state repository |
| **Persistence** | localStorage (`reigh.ext.<id>.*` keys), cleaned up on dispose | Provider-backed state repository with enablement, settings, and lifecycle event persistence |
| **Integrity** | Human review of source | Content hash + signature verification (deferred) |
| **Updates** | Git pull + rebuild | Pack version comparison + migration handlers |
| **Discovery** | Known only to the developer | Extension manager UI (deferred) |

### 3.2 Settings preservation across migration

The most critical piece of the migration is preserving user settings when an extension transitions from source-local to installed-pack. The SDK provides infrastructure for this today:

**Evidence:** [settings-migration-example.ts](../../src/examples/settings-migration-example.ts) (docs-safe, EX) — complete example of settings schema-version migration with `StateRepository`, `SettingsSnapshot`, and lifecycle events.

**Infrastructure:** `src/sdk/extensionSettingsMigration.ts` (T10) — `runSettingsMigration()`, `getManifestSettingsSchemaVersion()`, `findSettingsMigrationDeclarations()`.

---

## 4. Settings migration infrastructure (available today)

### 4.1 The `SettingsSnapshot` contract

Settings are captured as versioned snapshots:

```typescript
interface SettingsSnapshot {
  readonly extensionId: string;
  readonly schemaVersion: number;   // The version when this snapshot was written
  readonly values: Record<string, unknown>;
  readonly lastWrittenAt: string;
}
```

**Evidence:** `src/sdk/contracts.ts` (S-039); [Author Contract §2.4](./extension-author-contract.md#24-timeline-patch-system).

### 4.2 The `StateRepository` contract

The repository persists settings snapshots and lifecycle events:

```typescript
interface StateRepository {
  readonly isDisposed: boolean;
  putSettingsSnapshot(snapshot: SettingsSnapshot): Promise<void>;
  appendLifecycleEvent(event: LifecycleEvent): Promise<void>;
}
```

This is a **minimal SDK-owned subset** of the full internal `ExtensionStateRepository`. In V1, the repository is **not provider-backed** — settings live in localStorage. When M14 lands, the same contract will be backed by the provider (Supabase, Astrid, or InMemory).

**Evidence:** `src/sdk/contracts.ts`; [Author Contract §7.2](./extension-author-contract.md#72-what-is-deferred) (D-008).

### 4.3 Running a settings migration

The `runSettingsMigration()` function (available today from `@reigh/editor-sdk`) handles:

1. **Schema version detection:** Compares the snapshot's `schemaVersion` against the manifest's declared version.
2. **Handler lookup:** Finds `kind: 'settings'` migration declarations in the manifest.
3. **Handler invocation:** Calls the migration handler with current values and manifest defaults.
4. **Fallback:** On failure or missing handler, resets to manifest defaults.
5. **Lifecycle events:** Emits `migration_start`, `migration_success`, `migration_failure`, and `migration_reset` events through the repository.

```typescript
import { runSettingsMigration } from '@reigh/editor-sdk';

const result = await runSettingsMigration(extensionId, {
  manifest,
  snapshot,              // The persisted snapshot (may have older schema version)
  migrationHandlers: {   // Handler implementations keyed by name
    migrateV1ToV2,
  },
  repository,            // Optional StateRepository for event persistence
});

// result.values        — final settings (migrated or reset to defaults)
// result.schemaVersion — new version to persist
// result.migrated      — true if a handler was invoked and succeeded
// result.failure       — Error if migration failed
// result.resetToDefaults — true if reset to manifest defaults
// result.lifecycleEvents — all events emitted during migration
```

**Evidence:** `src/sdk/extensionSettingsMigration.ts` (368 lines, T10); TEST:`settings-migration-example.ts` (docs-safe).

### 4.4 Manifest migration declarations

Declare migrations in your manifest:

```typescript
manifest: {
  // ...
  settingsSchema: { version: 2 },
  settingsDefaults: {
    'audio.volume': 0.8,
    'audio.muted': false,
  },
  migrations: [
    {
      kind: 'settings',
      fromVersion: '1',
      toVersion: '2',
      handler: 'migrateV1ToV2',
      description: 'Migrates flat volume → nested audio.volume.',
    },
  ],
}
```

**Example reference:** [settings-migration-example.ts](../../src/examples/settings-migration-example.ts) (docs-safe, EX) — complete manifest with `settingsSchema`, `settingsDefaults`, and `migrations` array.

---

## 5. Manifest format continuity

### 5.1 Frozen for V1

The `reigh-extension.json` manifest format is **frozen for V1** (S-153). All 8 example extensions in the repository use the same format. New optional fields may be added in minor SDK versions; required fields will not change without a major version bump.

**Evidence:** [Author Contract §8.2](./extension-author-contract.md#82-manifest-format-stability); 8 consistent `reigh-extension.json` files in `src/tools/video-editor/examples/extensions/*/`.

### 5.2 Fields that survive migration

| Manifest field | Survives migration? | Notes |
|---|---|---|
| `id`, `version`, `label`, `description`, `apiVersion` | Yes — immutable identity | `defineExtension()` deep-freezes these |
| `contributions` | Yes — validated and frozen | Contribution IDs must remain stable for reference continuity |
| `settingsDefaults` | Yes | Used as fallback during migration |
| `settingsSchema` | Yes — version field drives migration | `getManifestSettingsSchemaVersion()` reads this |
| `messages` (i18n bundle) | Yes | No format change expected |
| `permissions` | Yes — descriptive only in V1 | Enforcement deferred to M4–M5 |
| `migrations` | Yes — validated and frozen | Handler names must match provided implementations |
| `dependsOn` | Reserved — validated, no runtime resolution | Deferred (D-009) |
| `processes` | Reserved — validated, no subprocess spawning | Deferred (D-023–D-027) |

### 5.3 Reference continuity

When an extension migrates from source-local to installed-pack, the following references must remain valid:

| Reference type | Continuity requirement | Evidence |
|---|---|---|
| **Clip type IDs** | Must be declared in the installed pack's `contributions` with the same `clipTypeId` | CR:M9-001, S-100 |
| **Effect IDs** | Must be declared with the same `effectId` | CR:M7-001, S-080 |
| **Transition IDs** | Must be declared with the same `transitionId` | CR:M8-001, S-090 |
| **Shader IDs** | Must be declared with the same shader registration | CR:M13-001, S-130 |
| **Project-data keys** | Extension-scoped project data is keyed by extension ID — must remain stable | S-039 |
| **Source-map entries** | Stored under `__sm__:<entryId>` in project-data — extension ID must be stable | S-040 |

**Important:** If an extension changes its `id` during migration, all project-data and source-map entries are orphaned. The migration path must preserve the extension ID.

**Evidence:** [Provider Compatibility Matrix §7–8](./provider-compatibility-matrix.md#7-extension-project-data-limits-by-provider); [Supported/Deferred Matrix §2.14](./extension-platform-supported-deferred.md#214-provider-compatibility); [Contract-Recheck CR:M14-007](./extension-platform-contract-recheck.md#215-m14--packaging-runtime-loader-extension-manager).

---

## 6. What is deferred (M14)

The following pieces of the migration workflow are **deferred** to M14. Do not attempt to implement them in V1:

### 6.1 Extension manager UI (D-001)

No user-facing UI exists for installing, enabling, disabling, or removing extensions. Extension management is done through code (provider props).

**Evidence:** [Supported/Deferred Matrix D-001–D-011](./extension-platform-supported-deferred.md#31-extension-packaging--manager-m14); Blocker B-001.

### 6.2 Persisted enablement and state (D-002, D-004)

Extension enablement/disablement is not persisted across sessions. When the page reloads, all extensions start in their initial state (as defined by provider props).

**Evidence:** [Contract-Recheck CR:M14-003, CR:M14-005](./extension-platform-contract-recheck.md#215-m14--packaging-runtime-loader-extension-manager).

### 6.3 Integrity verification (D-003)

No content hashing or signature verification exists in V1. The `permissions` field is descriptive only. When M14 introduces installed packs, integrity verification will prevent installation of tampered packs.

**Evidence:** [Trust Envelope §6](./extensions-trust-envelope.md#6-when-will-sandboxing-arrive); [Supported/Deferred Matrix D-003](./extension-platform-supported-deferred.md#31-extension-packaging--manager-m14).

### 6.4 Provider-backed state repository (D-008)

The full `ExtensionStateRepository` interface (internal to `src/tools/video-editor/runtime/`) has many methods beyond the SDK's minimal `StateRepository` contract. Provider-backed persistence for pack records, enablement state, dev overrides, and project locks is deferred.

**Evidence:** [Supported/Deferred Matrix D-008](./extension-platform-supported-deferred.md#31-extension-packaging--manager-m14); `src/sdk/contracts.ts` (minimal SDK contract).

### 6.5 Conflict resolution (D-010)

When an installed pack and a local source extension share the same ID, no conflict resolution UI exists. The current behaviour is first-registered-wins (same as command shortcuts).

**Evidence:** [Supported/Deferred Matrix D-010](./extension-platform-supported-deferred.md#31-extension-packaging--manager-m14); [Contract-Recheck CR:M14-011](./extension-platform-contract-recheck.md#215-m14--packaging-runtime-loader-extension-manager).

### 6.6 Dependency resolution (D-009)

The `dependsOn` field in the manifest is validated and frozen but not resolved at runtime. Optional dependency degradation and cycle diagnostics are deferred.

**Evidence:** [Supported/Deferred Matrix D-009](./extension-platform-supported-deferred.md#31-extension-packaging--manager-m14); [Contract-Recheck CR:M14-010](./extension-platform-contract-recheck.md#215-m14--packaging-runtime-loader-extension-manager).

---

## 7. Unsupported paths (cloud, export, marketplace)

### 7.1 Cloud extension loading

Loading extensions from a URL, CDN, or remote package registry is **unsupported** across all milestones (CR:X-006, D-123). The `import()` function is not used for extension code. There is no extension registry server.

**Evidence:** [Trust Envelope §2](./extensions-trust-envelope.md#2-capability-visibility-table) (Package loading row); [Author Contract §7.3](./extension-author-contract.md#73-what-is-unsupported).

### 7.2 Marketplace

A public or private extension marketplace is **unsupported** across all milestones (D-123). Grep confirms no marketplace infrastructure:

```bash
grep -r 'marketplace' src/sdk/   # no results
grep -r 'marketplace' src/tools/video-editor/runtime/   # no results
```

**Evidence:** [Supported/Deferred Matrix D-123](./extension-platform-supported-deferred.md#312-permissions--sandboxing); [Contract-Recheck CR:X-006](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims); ABSENCE:`grep -r 'marketplace' src/sdk/`.

### 7.3 Export paths for installed packs

When M14 lands, installed packs will follow the same export guard path as source-local extensions. The export guard (`runExportGuard()`) is provider-agnostic and contribution-kind-agnostic — it scans for unknown IDs regardless of how the extension was loaded.

There is **no specialised export path** for installed packs, and no plan for one in V1. Pack provenance does not affect export behaviour.

**Evidence:** [Author Contract §6.2](./extension-author-contract.md#62-export-guard-integration); `runExportGuard()` in `src/tools/video-editor/runtime/renderability.ts`.

### 7.4 Sandboxed execution

Sandboxing (iframe, Worker, or ShadowRealm isolation) is **deferred** to M4–M5 (D-121). When installed packs land in M14, they will initially run under the same trusted-local model as source-local extensions. Sandboxing is a separate concern from packaging.

**Evidence:** [Trust Envelope §5–6](./extensions-trust-envelope.md#5-what-trusted-local-does-not-mean); [Supported/Deferred Matrix D-121](./extension-platform-supported-deferred.md#312-permissions--sandboxing).

---

## 8. Migration checklist (pre-M14 preparation)

What you can do **today** to prepare for the M14 installed-pack migration:

### 8.1 Manifest readiness

- [x] Ensure your `reigh-extension.json` uses the frozen V1 format (S-153).
- [x] Declare `settingsSchema.version` in your manifest.
- [x] Define `settingsDefaults` for every setting your extension reads.
- [x] Add `kind: 'settings'` migration declarations for any planned schema changes.
- [x] Verify contribution IDs are stable — they will be the reference keys after migration.

**Evidence:** 8 consistent `reigh-extension.json` files in `src/tools/video-editor/examples/extensions/*/`.

### 8.2 Settings migration readiness

- [x] Implement migration handlers as pure functions exported from your extension module.
- [x] Test migration handlers with `runSettingsMigration()` using a stub `StateRepository`.
- [x] Handle the `resetToDefaults` case gracefully — assume settings may be lost during migration.
- [x] Namespace all settings keys uniquely (they are scoped to `reigh.ext.<id>.` prefix automatically).

**Example reference:** [settings-migration-example.ts](../../src/examples/settings-migration-example.ts) (docs-safe, EX).

### 8.3 Reference continuity readiness

- [x] Keep extension ID stable across versions.
- [x] Keep contribution IDs stable across versions.
- [x] Keep effect/transition/clip-type/shader IDs stable across versions.
- [x] Do not change the format of project-data keys.

### 8.4 What not to do

- [ ] Do not implement a custom extension loader — the M14 `ExtensionLoader` will handle this.
- [ ] Do not build an extension manager UI — this is deferred (D-001).
- [ ] Do not implement integrity hashing — `defineExtension()` does not yet accept hashes (D-003).
- [ ] Do not depend on `dependsOn` resolution — it's validated but not executed (D-009).
- [ ] Do not assume cloud loading or a marketplace will be available — they are unsupported (D-123).

---

## 9. Provider compatibility for migration

### 9.1 Settings storage by provider

| Provider | Settings persistence today | Post-M14 settings persistence |
|---|---|---|
| **InMemory** | `localStorage` (`reigh.ext.<id>.*` keys) | Provider-backed repository (InMemory → ephemeral; settings lost on reload) |
| **Supabase** | `localStorage` (`reigh.ext.<id>.*` keys) | Provider-backed repository (Supabase → durable; settings survive reload) |
| **Astrid Bridge** | `localStorage` (`reigh.ext.<id>.*` keys) | Provider-backed repository (Astrid → local filesystem-backed) |

Settings are always scoped to browser `localStorage` under the `reigh.ext.<id>.` key prefix today, regardless of provider. No provider currently offers a server-side settings store. When M14 introduces the provider-backed `StateRepository`, settings will follow the same persistence model as the provider.

**Evidence:** [Provider Compatibility Matrix §3.1](./provider-compatibility-matrix.md#31-settings).

### 9.2 Migration across providers

The `runSettingsMigration()` function is **provider-agnostic** — it operates on in-memory `SettingsSnapshot` and `Record<string, unknown>` values. The provider only enters the picture through the optional `StateRepository` for lifecycle event persistence.

When migrating from source-local (InMemory) to installed-pack (Supabase), the settings migration runs identically — the handler receives the same input shapes.

**Evidence:** `src/sdk/extensionSettingsMigration.ts` (no provider imports); [Provider Compatibility Matrix §3.1](./provider-compatibility-matrix.md#31-settings).

---

## 10. Automated quality checks

### 10.1 Example readiness gate

```bash
node scripts/quality/check-extension-example-readiness.mjs --audit
```

Verifies that the `settings-migration-example.ts` imports exclusively from `@reigh/editor-sdk` and has a corresponding supported matrix row.

**Evidence:** [Quickstart §7](./extensions-quickstart.md#7-running-the-pre-doc-example-readiness-gate).

### 10.2 Deferred claims check

```bash
node scripts/quality/check-extension-deferred-claims.mjs --audit
```

Verifies that every deferred classification (D-001–D-010 for M14 packaging) is backed by an absence check or blocker entry (B-001).

**Evidence:** [Supported/Deferred Matrix §1.1](./extension-platform-supported-deferred.md#11-classification-definitions); SD2.

### 10.3 Contract recheck

```bash
node scripts/quality/check-extension-contract-recheck.mjs --audit
```

Checks that migration-related contract-recheck rows (CR:M14-001 through CR:M14-011) have valid evidence references.

**Evidence:** [Contract-Recheck Matrix §2.15](./extension-platform-contract-recheck.md#215-m14--packaging-runtime-loader-extension-manager).

---

## 11. Cross-reference

| Document | Relevance |
|---|---|
| [extensions-quickstart.md](./extensions-quickstart.md) | Getting-started guide; V1 extension patterns |
| [extension-author-contract.md](./extension-author-contract.md) | Complete developer obligations and platform guarantees |
| [extension-platform-supported-deferred.md](./extension-platform-supported-deferred.md) | Full supported/deferred classification (84 supported, 69 deferred) |
| [extension-platform-contract-recheck.md](./extension-platform-contract-recheck.md) | Complete M0–M14 Done Criteria evidence |
| [extensions-trust-envelope.md](./extensions-trust-envelope.md) | V1 trusted-local execution model; sandboxing deferral |
| [provider-compatibility-matrix.md](./provider-compatibility-matrix.md) | Settings persistence across providers; migration compatibility |
| [extensions-debugging.md](./extensions-debugging.md) | Debugging activation, disposal, and export guard failures |

**Source references:**
- `src/sdk/extensionSettingsMigration.ts` — `runSettingsMigration()`, schema version detection, handler chaining
- `src/sdk/contracts.ts` — `StateRepository`, `SettingsSnapshot`, `LifecycleEvent` contracts
- `src/sdk/extensionSettingsService.ts` — localStorage-backed settings service (`createExtensionSettingsService`)
- `src/examples/settings-migration-example.ts` — Complete migration example with stub repository
- `src/tools/video-editor/examples/extensions/*/reigh-extension.json` — 8 frozen manifest examples

---

## 12. Version history

| Date | Change |
|---|---|
| 2026-06-20 | Initial migration guide for M15. Covers V1 source-local posture, settings migration infrastructure (T10), manifest format continuity, reference continuity, deferred M14 packaging pieces (D-001–D-010, B-001), unsupported cloud/export/marketplace paths, provider compatibility for migration, pre-M14 preparation checklist, and automated quality checks. All workflows linked to tests, examples, matrix rows, absence checks, and blockers. |
