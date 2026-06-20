# Provider Compatibility Matrix — M3 TimelinePatch & Proposals

**Status:** Active (M3)
**Last updated:** 2026-06-19
**Scope:** Every DataProvider implementation that the video editor can run against, evaluated for M3 TimelinePatch, TimelineOps, ProposalRuntime, and golden replay semantics.

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
