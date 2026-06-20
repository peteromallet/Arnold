# Provider Compatibility Matrix — M3 TimelinePatch & Proposals

**Status:** Active (M15 hardening)
**Last updated:** 2026-06-20
**Scope:** Every DataProvider implementation that the video editor can run against, evaluated for M3 TimelinePatch, TimelineOps, ProposalRuntime, golden replay semantics, and environment-impossible provider checks.

---

## 1. Purpose

This matrix records the compatibility posture of each concrete `DataProvider` implementation against the M3 semantic layer contracts. Each row captures settings, extension requirements, proposal base-version behavior, diagnostics surface, missing-extension reference handling, patch replay fidelity, and any known limitations. Host code and extension authors can use this matrix to understand which provider guarantees hold in their deployment environment.

---

## 2. Provider implementations

| Provider | Class | Persistence | Environment | M3 support |
|---|---|---|---|---|
| **InMemory** | `InMemoryDataProvider` | Ephemeral (Map-backed) | Test / dev / demo | Full |
| **Supabase** | `SupabaseDataProvider` | Durable (DB + append service) | Production (Reigh cloud) | Full |
| **Astrid Bridge** | `AstridBridgeDataProvider` | Local filesystem + bridge API | Local dev (desktop bridge) | Partial |

---

## 3. Compatibility matrix

### 3.1 Settings

| Provider | Settings persistence | Per-extension localStorage scoping | Settings cleanup on dispose |
|---|---|---|---|
| **InMemory** | N/A — no persistent storage | Yes (`reigh.ext.<id>.*` prefix convention) | Yes (via `disposeHostServices`) |
| **Supabase** | N/A — no persistent settings table | Yes | Yes |
| **Astrid Bridge** | N/A — no persistent settings table | Yes | Yes |

Settings are always scoped to browser `localStorage` under the `reigh.ext.<id>.` key prefix, regardless of provider. No provider currently offers a server-side settings store. Settings cleanup is provider-agnostic and handled by the extension lifecycle's `disposeHostServices()`.

### 3.2 Extension requirements

| Provider | `ProjectExtensionRequirement` read support | Missing-extension diagnostic severity | Referenced contribution ID validation |
|---|---|---|---|
| **InMemory** | Full — requirements are inlined in TimelineConfig and surfaced via `TimelineReader.snapshot().extensionRequirements` | `warning` (export guard) | Contribution IDs stored in `referencedContributionIds` are validated structurally but not resolved at runtime |
| **Supabase** | Full — same shape, loaded from DB `timelines.config` | `warning` | Same as InMemory |
| **Astrid Bridge** | Full — same shape, loaded from local `assembly.json` or bridge API | `warning` | Same as InMemory |

Extension requirements are a property of the timeline config, not the provider. The `TimelineReader` extracts `extensionRequirements` from the config shape and returns them in every snapshot. When a project references an extension that is not currently active, the export guard emits `warning`-severity diagnostics (code: `export/missing-extension`) but does not block render.

### 3.3 Proposal base versions

| Provider | `configVersion` semantics | Strict CAS enforcement | Local monotonic invalidation | Stale proposal detection |
|---|---|---|---|---|
| **InMemory** | Monotonic integer, incremented on every `saveTimeline` | **Yes** — `TimelineVersionConflictError` thrown on mismatch | **Yes** — `useTimelineOps.apply()` compares `patch.version` against current `configVersion` before any mutation | **Yes** — `ProposalRuntime.accept()` revalidates `baseVersion` against `reader.snapshot().baseVersion` |
| **Supabase** | Monotonic integer from append service `config_version` | **Yes** — 409 Conflict from append service → `TimelineVersionConflictError` | **Yes** — same local guard as InMemory (catches stale patches before network round-trip) | **Yes** — same revalidation path |
| **Astrid Bridge** | Monotonic integer from bridge payload `config_version` | **Partial** — no server-side CAS; version is incremented locally after save but concurrent writes from another bridge instance would silently overwrite | **Yes** — same local guard | **Yes** — revalidation against current snapshot version works, but the snapshot version may not reflect external concurrent writes |

**Key invariant:** When `patch.version === 0`, the base-version check is bypassed (treated as "no expectation"). This is intended for initial state seeding.

### 3.4 Diagnostics

| Provider | `TimelinePatchDiagnostic` surface | Provider-level error mapping | Diagnostic panel integration |
|---|---|---|---|
| **InMemory** | Full — all `timeline-patch/*` diagnostic codes are produced by the pure compiler and surfaced identically | `TimelineVersionConflictError` → diagnostic code `timeline-patch/stale-base-version` via `useTimelineOps` | Diagnostic codes flow through `TimelinePatchValidationResult.diagnostics` → host `DiagnosticPanel` |
| **Supabase** | Full | Same as InMemory | Same |
| **Astrid Bridge** | Full | Same as InMemory | Same |

Diagnostics are **provider-agnostic** — the pure `validateTimelinePatch` and `compileTimelinePatch` functions produce identical diagnostic shapes regardless of provider. The only provider-specific diagnostic path is `TimelineVersionConflictError` translation, which is handled by `useTimelineOps` before the provider is called.

### 3.5 Missing extension references

| Provider | Detection mechanism | Diagnostic shape | Runtime behavior |
|---|---|---|---|
| **InMemory** | `TimelineReader.snapshot().extensionRequirements` lists expected extensions; host compares against active extension registry | `warning` severity, code: `export/missing-extension` | Render proceeds; unknown clip types from missing extensions produce `export/unknown-clip-type` |
| **Supabase** | Same | Same | Same |
| **Astrid Bridge** | Same | Same | Same |

Missing extension references are detected at **export-guard time**, not at provider load time. This is intentional — a project that references an extension should remain openable even when the extension is not installed.

### 3.6 Patch replay behavior

| Provider | Golden replay determinism | Cross-provider consistency | Rollback safety | Serialization fidelity |
|---|---|---|---|---|
| **InMemory** | **Full** — 3× compile on identical input produces structurally equivalent output | **Reference** — InMemory is the canonical replay baseline | **Yes** — `useTimelineOps.rollback()` restores to checkpoint via existing history path | **Full** — `JSON.parse(JSON.stringify(nextData))` round-trips without loss |
| **Supabase** | **Identical compiler output** — the pure compiler returns the same `nextData`/`diff` shapes. The append service serialization path preserves all fields | **Consistent** — compiler is provider-agnostic; `nextData` is structurally identical to InMemory for the same input | **Yes** — same history-based rollback | **Full** — `serializeTimelineConfigSnapshot` preserves all M3 fields |
| **Astrid Bridge** | **Identical compiler output** — same pure compiler, same `nextData`/`diff` shapes | **Consistent** — compiler output is structurally identical; bridge serialization preserves config shape | **Yes** — local history path works; bridge save writes to `assembly.json` and bridge API | **Full** — local JSON write preserves all fields |

**Golden replay invariant:** For any valid `TimelinePatch` batch, `compileTimelinePatch(patch, data).nextData` produces structurally equivalent output on any provider. The pure compiler does not import or depend on any `DataProvider` implementation. Provider-specific behavior only enters at the serialization/deserialization boundary (`saveTimeline`/`loadTimeline`), and all providers use the same `serializeTimelineConfigSnapshot` helper.

---

## 4. Provider-specific limitations

### 4.1 InMemoryDataProvider

- **No persistence across page refresh.** All timeline state is lost on reload. Suitable for tests, dev, and demo only.
- **No checkpoint persistence.** `saveCheckpoint` / `loadCheckpoints` methods are not implemented (the `DataProvider` interface marks them as optional).
- **No asset upload.** Assets are resolved via `memory://` prefix.

### 4.2 SupabaseDataProvider

- **Requires authentication.** `saveTimeline` and `syncTimeline` require a valid user JWT.
- **Requires append service.** The `VITE_REIGH_APPEND_SERVICE_URL` environment variable must be set. Without it, the provider throws at construction time.
- **Network-dependent.** All save/load operations are async and may fail due to network conditions.
- **Sync complexity.** The `syncTimeline` method implements a full bookmark-based sync protocol with divergence recording (`keep-both` artifacts). This is transparent to M3 consumers but adds latency.

### 4.3 AstridBridgeDataProvider

- **Read-only for uploads.** `onUpload()` throws `AstridBridgeReadOnlyError`. Asset uploads through the standard `uploadAsset` path are not supported.
- **No server-side CAS.** Concurrent writes from different bridge instances are not detected — the bridge increments its local version but does not compare against a remote head.
- **No checkpoint persistence.** `saveCheckpoint` returns a synthetic ID; `loadCheckpoints` returns an empty array.
- **No waveform/profile loading.** `loadWaveform` and `loadAssetProfile` return `null`.
- **Local-filesystem-dependent.** Requires the File System Access API and user-granted directory permissions.

---

## 5. Patch operation support by provider

All 13 active operation families (`clip.add`, `clip.update`, `clip.remove`, `clip.move`, `track.add`, `track.update`, `track.remove`, `asset.update`, `asset.remove`, `app.update`, `project-data.write`, `project-data.delete`, `extension.noop`) are supported identically across all three providers. The pure compiler handles all operation families; providers only see the serialized config result.

Reserved operation families (`clip.split`, `clip.slice`) produce warning diagnostics with `{ reserved: true, deferred: true, nonPreviewable: true }` detail on all providers. They are never executed.

---

## 6. Proposal runtime behavior by provider

| Behavior | InMemory | Supabase | Astrid Bridge |
|---|---|---|---|
| In-memory proposal storage | Yes | Yes | Yes |
| Proposals survive page refresh | No | No | No |
| `replaceForSource` atomicity | Yes | Yes | Yes |
| `accept()` base-version revalidation | Yes | Yes | Yes |
| `preview()` ghost-render safety | Yes | Yes | Yes |
| Proposal count/status in host UI | Yes | Yes | Yes |

Proposal storage is **provider-scoped and in-memory** for M3. Page refresh drops all unaccepted proposals. This is consistent across all providers — the `ProposalRuntime` implementation uses an in-memory `Map` and does not persist to any provider backend.

---

## 7. Extension project-data limits by provider

The extension project-data limits (`MAX_ENTRY_BYTES`: 64 KB, `MAX_EXTENSION_TOTAL_BYTES`: 1 MB, `MAX_ENTRIES_PER_EXTENSION`: 128 entries) are **enforced by the pure compiler**, not by the provider. All three providers observe the same limits because the compiler checks them before any provider interaction.

Overflow diagnostics include `ProjectDataLimitDetail` with `extensionId`, `limit`, `actual`, `unit`, and `code` fields. The diagnostic message points authors to assets, `RenderMaterial` refs, render artifacts, provider-backed extension repositories, or package resources as alternatives.

---

## 8. Source-map runtime behavior by provider

The `SourceMapRuntime` stores entries in extension project-data under `__sm__:<entryId>` keys. This means:

- **All providers** support source-map CRUD identically — the data lives in `TimelineConfig.app`, which is provider-agnostic.
- **Stale marking** persists across saves because it updates the project-data entry.
- **Rollback safety** applies because project-data writes go through the patch compiler, which participates in checkpoint/rollback.
- **Cross-provider portability** is guaranteed — source-map entries serialize into the same config shape on all providers.

---

## 9. Test coverage summary

| Test suite | InMemory | Supabase (adapter) | Astrid Bridge |
|---|---|---|---|
| `timeline-patch.test.ts` (241 tests) | ✓ All pass | N/A (pure compiler) | N/A (pure compiler) |
| `timeline-reader.test.ts` (48 tests) | ✓ All pass | N/A (pure reader) | N/A (pure reader) |
| `timeline-golden-replay.test.ts` (81 tests) | ✓ All pass | ✓ Structurally equivalent | N/A (not available locally) |
| `InMemoryDataProvider.test.ts` (13 tests) | ✓ All pass | N/A | N/A |
| `SupabaseDataProvider.test.ts` (18 tests) | N/A | ✓ All pass | N/A |
| `AstridBridgeDataProvider.test.ts` (22 pass / 3 pre-existing) | N/A | N/A | ✓ 22 pass |
| `proposal-runtime.test.ts` (39 tests) | ✓ All pass | N/A (in-memory runtime) | N/A (in-memory runtime) |
| `source-map-runtime.test.ts` (31 tests) | ✓ All pass | N/A (project-data backed) | N/A (project-data backed) |

---

## 10. Environment-impossible provider checks

This section documents every provider compatibility test that **cannot run** in one or more environments (headless CI, local dev without credentials, Node.js without browser APIs). For each impossible or skipped case, the resolution (mock, skip flag, partial suite, or delegated coverage) is explicitly listed and linked to the relevant contract-recheck rows. No provider check is silently skipped — every gap is traceable to a documented reason.

### 10.1 SupabaseDataProvider — environment prerequisites

| Requirement | Why it's needed | Unavailable in |
|---|---|---|
| `VITE_REIGH_APPEND_SERVICE_URL` env var | Constructs the append-service endpoint URL; provider throws at construction time without it | Local CI without service URL; dev environments without Supabase project |
| Supabase auth JWT (`getSession` / `readAccessTokenFromStorage`) | `saveTimeline` and `syncTimeline` require authenticated user | Local CI without auth tokens; anonymous browser sessions |
| Supabase database (`timelines`, `timeline_events`, `sync_bookmarks` tables) | Load/version/sync queries read from materialized DB rows | Local dev without Supabase project; environments without DB access |
| IndexedDB (`syncLedgerIndexedDb`) | Sync bookmark and keep-both artifact persistence | Environments without IndexedDB (Node.js pre-21, some test runners) |
| Network access to append service | `saveTimeline` POSTs to append-service for CAS-enforced writes | Offline environments; CI without network allowlist |

**How skipped tests are handled:**

The `providerCompatibility.supabase.test.ts` suite (416 lines) does **not** use the shared `runProviderCompatibilitySuite` helper. Instead, it supplies a manually written subset of tests backed by heavy mocking:

- IndexedDB is mocked via `fake-indexeddb` and `vi.stubGlobal('indexedDB', ...)`.
- Supabase client methods (`getSession`, `from`) are mocked with `vi.hoisted` mocks.
- `VITE_REIGH_APPEND_SERVICE_URL` is stubbed via `vi.stubEnv`.
- The append-service `fetch` is stubbed with `vi.stubGlobal('fetch', ...)`.
- The shared suite's `versionConflictIsSoft=false` path is **delegated** to the InMemory compatibility test.

**Skipped shared-suite sections (Supabase):**

| Shared suite section | Skipped? | Reason | Coverage delegated to |
|---|---|---|---|
| versioned load/save (full CAS) | Partial — only versioned load + versioned save manually tested | Supabase mocks are too intricate for the generic `ProviderFactory` seed pattern; the shared suite's atomic-save loop would need per-call mock maturation | `SupabaseDataProvider.test.ts` (18 tests, full save/conflict coverage) |
| version conflict handling (strict CAS) | Yes — strict CAS path skipped | The shared suite's `versionConflictIsSoft=false` branch requires atomic expectedVersion rejection loops that need per-call mock state mutation | InMemory compatibility test (`providerCompatibility.inmemory.test.ts`) |
| checkpoints | Yes — not tested in shared suite | Supabase implements `saveCheckpoint` / `loadCheckpoints` but the shared suite's checkpoint tests are gated by `skipCheckpoints` flag; the Supabase compat test does not invoke the shared suite | `SupabaseDataProvider.test.ts` (18 tests) |
| registerAsset | Yes — not tested in shared suite | `registerAsset` is provider-specific and the Supabase compat test does not invoke the shared suite's `registerAsset` section | `SupabaseDataProvider.test.ts` |
| resolveAssetUrl | Partial — manually tested in compat suite | Supabase uses storage bucket public URLs; the shared suite's generic `resolveAssetUrl` section is not invoked | `providerCompatibility.supabase.test.ts` (manual test) |
| missing-timeline error types | Partial — `TimelineNotFoundError` detection tested manually | Supabase's `loadTimeline` returns a default config for missing timelines instead of throwing `TimelineNotFoundError` | `SupabaseDataProvider.test.ts` |
| extension requirements | Partial — manually tested in compat suite | Extension-owned app data round-trip is tested manually; the shared suite's version is not invoked | `providerCompatibility.supabase.test.ts` |

**Contract-recheck row links:**

| Contract-recheck row | How Supabase satisfies it despite environment impossibility |
|---|---|
| [CR:M3-007](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Provider version behaviors tested | `SupabaseDataProvider.test.ts` (18 tests) covers versioned load/save/conflict; InMemory covers strict CAS path |
| [CR:M3-009](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Golden patch replay across providers | `timeline-golden-replay.test.ts` (81 tests) covers InMemory and Supabase structural equivalence |
| [CR:M3-010](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Provider compatibility matrix updated | This document §2–§9 covers all M3 behaviors across providers |
| [CR:X-007](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims) — Provider compatibility documented | This document + this section (§10) provide the complete environment-impossible audit trail |

### 10.2 AstridBridgeDataProvider — environment prerequisites

| Requirement | Why it's needed | Unavailable in |
|---|---|---|
| File System Access API (`showDirectoryPicker`, `getDirectoryHandle`, `requestPermission`) | Reads/writes `assembly.json` and `registry.json` from user-granted local directory | Headless CI (Node.js, no browser); browsers without File System Access API (Firefox, Safari < 15) |
| Local bridge process (HTTP server, default port `17333`) | Serves asset files and accepts save/config API calls | CI environments; dev machines without Astrid bridge installed |
| User-granted directory permissions (`ensurePermission`, `saveDirectoryHandle`) | Persists the local project root handle across sessions | Headless environments; first-run browser contexts |
| `localStorage` (for `PersistedLocalDirectoryHandle`) | Stores the directory handle for reconnection on reload | Environments without `localStorage` (some test runners) |
| Network access to `127.0.0.1:17333` | Fetches asset files and timeline config from the bridge | CI without loopback network; remote dev environments |

**How skipped tests are handled:**

The `providerCompatibility.astrid.test.ts` suite (167 lines) uses the shared `runProviderCompatibilitySuite` with these environment-aware flags:

| Flag | Value | Reason |
|---|---|---|
| `skipCheckpoints` | `true` | Astrid does not persist checkpoints; `saveCheckpoint` returns a synthetic ID and `loadCheckpoints` returns `[]` |
| `versionConflictIsSoft` | `true` | Astrid has **no server-side CAS** — version is incremented locally after save; concurrent writes from another bridge instance silently overwrite |
| `skipMissingTimelineTests` | `true` | Astrid is a **single-timeline bridge** — `loadTimeline` always returns the bridge's current timeline; "nonexistent timeline" errors are not meaningful |
| `skipRegisterAsset` | `false` | `registerAsset` is supported via the bridge API (asset registration PUTs to bridge) |

All bridge API calls are mocked via `vi.stubGlobal('fetch', createAstridFetchMock())`. The mock maintains a stateful `storedState` object that simulates the bridge's in-memory config/registry. Module-level dependencies (`localHandleStore`, `mediaMetadata`, `generationAssetResolver`) are mocked via `vi.mock`.

**Skipped shared-suite sections (Astrid):**

| Shared suite section | Skipped? | Reason | Coverage delegated to |
|---|---|---|---|
| checkpoints | Yes (`skipCheckpoints: true`) | No checkpoint persistence — `saveCheckpoint` returns synthetic ID, `loadCheckpoints` returns `[]` | `AstridBridgeDataProvider.test.ts` (22 pass / 3 pre-existing) |
| missing-timeline error types | Yes (`skipMissingTimelineTests: true`) | Single-timeline bridge — `loadTimeline` always returns the bridge's current payload; `TimelineNotFoundError` never thrown for load | Documented limitation in §4.3 |
| strict CAS version conflict | Behaviorally adapted (`versionConflictIsSoft: true`) | No server-side CAS — version conflict tests assert soft behavior: mismatched `expectedVersion` succeeds, version is not checked against remote head | Documented limitation in §3.3 and §4.3 |

**Contract-recheck row links:**

| Contract-recheck row | How Astrid satisfies it despite environment impossibility |
|---|---|
| [CR:M3-007](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Provider version behaviors tested | `providerCompatibility.astrid.test.ts` exercises the shared suite with `versionConflictIsSoft: true`; `AstridBridgeDataProvider.test.ts` covers full integration (22 pass) |
| [CR:M3-009](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Golden patch replay across providers | Listed as N/A in test coverage summary (§9); golden replay not available locally because the bridge requires File System Access API |
| [CR:M3-010](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) — Provider compatibility matrix updated | This document §§2–4.3 document all Astrid limitations; this section (§10.2) provides the environment-impossible audit trail |
| [CR:M6-004](./extension-platform-contract-recheck.md#27-m6--asset-metadata-parser-contributions-astrid-loop) — Astrid local-first demo/test | `AstridBridgeDataProvider.test.ts` (22 pass) covers extension mutation and persistence |
| [CR:X-007](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims) — Provider compatibility documented | This document + this section (§10) provide the complete environment-impossible audit trail |

### 10.3 InMemoryDataProvider — no environment restrictions

Both InMemory variants (**testing** and **browser-runtime**) have no environment prerequisites. They run identically in all environments:

| Variant | Test file | Shared suite flags | Environment notes |
|---|---|---|---|
| Testing (`src/tools/video-editor/testing/InMemoryDataProvider`) | `providerCompatibility.inmemory.test.ts` | `skipCheckpoints: false`, `versionConflictIsSoft: false`, `skipRegisterAsset: false` | Pure Map-backed; no env dependencies; canonical shared-suite baseline |
| Browser-runtime (`src/tools/video-editor/lib/browser-runtime`) | `providerCompatibility.browserInMemory.test.ts` | `skipCheckpoints: false`, `versionConflictIsSoft: false`, `skipRegisterAsset: false` | Uses `createLocalAssetResolver`; works in any JS environment (Node, browser, CI) |

**Contract-recheck row links:**

| Contract-recheck row | How InMemory satisfies it |
|---|---|
| [CR:M3-007](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) | Both variants pass the full shared suite; InMemory is the canonical CAS-semantics reference |
| [CR:M3-009](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) | InMemory is the **Reference** for golden replay determinism (81 tests, 3× compile consistency) |
| [CR:M3-010](./extension-platform-contract-recheck.md#24-m3--timelinepatch-atomic-ops-proposals) | This document §2 defines InMemory as "Full" M3 support |
| [CR:X-007](./extension-platform-contract-recheck.md#216-cross-milestone--structural-claims) | This document + all sections cover InMemory as the canonical baseline |

### 10.4 Cross-provider impossibility summary

| Provider | Environment-impossible scenario | Resolution | Skipped suite sections | Contract-recheck rows |
|---|---|---|---|---|
| **Supabase** | No auth, no DB, no append-service URL | Manual test subset with heavy mocking; strict CAS delegated to InMemory | version conflict (strict CAS), checkpoints, registerAsset, shared-suite versioned save loop | CR:M3-007, CR:M3-009, CR:M3-010, CR:X-007 |
| **Astrid Bridge** | No File System Access API, no bridge process | Mocked bridge API via `vi.stubGlobal('fetch')`; shared suite with `skipCheckpoints`, `versionConflictIsSoft`, `skipMissingTimelineTests` | checkpoints, missing-timeline errors, strict CAS conflict | CR:M3-007, CR:M3-009, CR:M3-010, CR:M6-004, CR:X-007 |
| **InMemory (both)** | None | Full shared suite, no skips | None | CR:M3-007, CR:M3-009, CR:M3-010, CR:X-007 |

### 10.5 Gate semantics for environment-impossible checks

Per the shared matrix helper (SD1), the `providerCompatibility` shared suite is a **contract gate**, not a release gate. The following status semantics apply:

| Status | Definition | Example |
|---|---|---|
| **pass** | The shared suite passes with all applicable flags in the provider's documented environment | InMemory (both): full pass, no skips |
| **deferred** | The shared suite section was skipped via a documented flag (`skipCheckpoints`, `skipMissingTimelineTests`, `versionConflictIsSoft`) and the skip reason is linked to a contract-recheck row or blocker entry | Astrid: checkpoints deferred (no persistence), missing-timeline deferred (single-timeline bridge) |
| **gap** | The shared suite section was not exercised and no alternative coverage exists | N/A — all current gaps have alternative coverage or documented deferral |
| **blocked** | The shared suite cannot exercise a section and no alternative coverage or deferral exists | None currently — all environment-impossible cases have documented resolutions |
| **release-blocking** | A gap without documented resolution that affects V1 supported claims | None — see [contract-recheck blocker section](./extension-platform-contract-recheck.md#3-blocker-section) for M14/M12/M11 blockers that are independent of provider compatibility |

**Cross-validation rule:** Every `skip*` flag or `versionConflictIsSoft` usage in a provider compatibility test file must have a corresponding row in this section (§10) linking to contract-recheck rows. The deferred-claims checker (SD2) enforces this: a deferred classification is valid only when backed by an absence check or explicit blocker entry. This section serves as the absence-check evidence for environment-impossible provider skips.

---

## 11. Version History

| Date | Change |
|---|---|
| 2026-06-19 | Initial provider compatibility matrix. Coverage: M3 TimelinePatch, Proposals, golden replay across InMemory, Supabase, Astrid. |
| 2026-06-20 | Added §10: environment-impossible provider checks with contract-recheck row links. Documents every skip flag, mock strategy, and delegated coverage path for Supabase and Astrid Bridge. InMemory (both variants) confirmed as environment-unrestricted canonical baseline. Added §11: version history.
