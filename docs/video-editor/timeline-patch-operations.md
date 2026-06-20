# TimelinePatch Operation Semantics — M3

**Status:** Active (M3)
**Last updated:** 2026-06-19
**Scope:** Complete reference for every TimelinePatch operation family, its validation rules, merge/replace behavior, ordering semantics, diff shape, previewability, and extension mechanism.

---

## 1. Overview

`TimelinePatch` is the M3 semantic operation vocabulary for timeline mutation. Every mutation flows through a batch of `TimelinePatchOperation` records that are validated atomically, compiled through the existing config/row serialization paths, and applied through the existing `commitData`/history pipeline. This document covers every operation family, its contracts, and the extension mechanism for future contribution kinds.

---

## 2. Patch structure

```typescript
interface TimelinePatch {
  version: number;                              // Monotonic batch version
  operations: readonly TimelinePatchOperation[]; // Ordered, applied atomically
  source?: string;                               // Producer (extension ID, tool name)
  meta?: Record<string, unknown>;                // Opaque producer metadata
}

interface TimelinePatchOperation {
  op: TimelinePatchAnyOpFamily;   // e.g. "clip.add", "track.update"
  target: string;                  // Object identifier scoped to the op family
  payload?: Record<string, unknown>; // Family-dependent
  order?: number;                  // Sortable anchor for ordering-dependent ops
}
```

---

## 3. Active operation families (13)

### 3.1 `clip.add` — Insert a clip

| Property | Value |
|---|---|
| **Target** | Clip ID (unique) |
| **Payload fields** | `track` (string, required), `at` (number, seconds, required), `clipType` (string, optional, defaults to `'video'`) |
| **Merge mode** | N/A — new object |
| **Diff kind** | `added` |
| **Diff granularity** | `clip` |
| **Previewable** | Yes |
| **Validation** | `track` must be a string, `at` must be a number, `clipType` must be a string if present |

### 3.2 `clip.update` — Modify a clip

| Property | Value |
|---|---|
| **Target** | Existing clip ID |
| **Payload fields** | Any mutable clip field (`clipType`, `asset`, `from`, `to`, `speed`, `hold`, `volume`, `x`, `y`, `width`, `height`, `cropTop`, `cropBottom`, `cropLeft`, `cropRight`, `opacity`, `text`, `entrance`, `exit`, `continuous`, `transition`, `effects`, `params`, `pool_id`, `clip_order`, `source_uuid`, `generation`, `app`) plus `mode` |
| **Merge mode** | `merge` (default) or `replace` |
| **Diff kind** | `modified` |
| **Diff granularity** | `clip` |
| **Previewable** | Yes |
| **Validation** | `mode` must be `"merge"` or `"replace"` if present |

#### Merge/replace semantics

- **`merge` (default):** Shallow-merge payload keys into the existing clip object. Keys present in the existing clip but absent from the payload are **preserved**. Nested objects (`app`, `effects`, `params`, `generation`) are deep-merged recursively. Structural fields (`id`, `track`, `at`) are never mutated.
- **`replace`:** Replace all mutable fields with the payload. Structural fields (`id`, `track`, `at`) are preserved. Any mutable field not mentioned in the payload is **removed** (reset to undefined). This is useful for "resetting" a clip to a known state.

### 3.3 `clip.remove` — Delete a clip

| Property | Value |
|---|---|
| **Target** | Existing clip ID |
| **Payload** | None (ignored if present) |
| **Merge mode** | N/A |
| **Diff kind** | `removed` |
| **Diff granularity** | `clip` |
| **Previewable** | Yes |
| **Validation** | None beyond target presence (not-found produces warning, not error) |
| **Cascade** | Removing the last clip on a track does NOT remove the track |

### 3.4 `clip.move` — Reposition or re-track a clip

| Property | Value |
|---|---|
| **Target** | Existing clip ID |
| **Payload fields** | `track` (string, optional), `at` (number, seconds, optional), `before` (string, clip ID, optional), `after` (string, clip ID, optional) |
| **Merge mode** | N/A — positional operation |
| **Diff kind** | `modified` or `reordered` |
| **Diff granularity** | `clip` |
| **Previewable** | Yes |
| **Validation** | At least one of `track`, `at`, `before`, `after` must be present. `before` and `after` must be strings. `before` and `after` cannot reference the same clip. |

#### Reorder anchor semantics

- **`before` takes precedence over `after`:** If both are specified, the clip is placed before the `before` anchor.
- **`order` field fallback:** The `order` field on `TimelinePatchOperation` is used as a fractional positioning anchor when `before`/`after` are absent. Operations with explicit `order` values are applied before those without.
- **Cross-track move:** Specifying a different `track` moves the clip to that track. If the target track does not exist, it is auto-created.
- **Same-track reorder:** Specifying only `before`/`after` on the same track repositions the clip within its current track.
- **Fractional positioning:** The `order` field supports fractional values for precise positioning between existing clips without requiring absolute reorder arrays. This is sync-compatible (no `clipIds[]` array dependency).

### 3.5 `track.add` — Add a track

| Property | Value |
|---|---|
| **Target** | Track ID (unique) |
| **Payload fields** | `kind` (`'visual'` or `'audio'`, required), `label` (string, optional), `muted` (boolean, optional) |
| **Merge mode** | N/A — new object |
| **Diff kind** | `added` |
| **Diff granularity** | `track` |
| **Previewable** | Yes |
| **Validation** | `kind` must be `"visual"` or `"audio"`. Duplicate track ID produces warning (not error). |

### 3.6 `track.update` — Modify a track

| Property | Value |
|---|---|
| **Target** | Existing track ID |
| **Payload fields** | Any mutable track field (`kind`, `label`, `scale`, `fit`, `opacity`, `volume`, `muted`, `blendMode`, `app`) plus `mode` |
| **Merge mode** | `merge` (default) or `replace` |
| **Diff kind** | `modified` |
| **Diff granularity** | `track` |
| **Previewable** | Yes |
| **Validation** | `mode` must be `"merge"` or `"replace"` if present |

#### Merge/replace semantics

Same as `clip.update`: `merge` preserves unmentioned keys, `replace` resets them. Structural `id` is never mutated.

### 3.7 `track.remove` — Remove a track

| Property | Value |
|---|---|
| **Target** | Existing track ID |
| **Payload** | None |
| **Merge mode** | N/A |
| **Diff kind** | `removed` (track) + `removed` (cascaded clips) |
| **Diff granularity** | `track` + `clip` (cascade) |
| **Previewable** | Yes |
| **Cascade** | All clips on the track are removed. Their removal produces individual `removed` diff entries. |

### 3.8 `asset.update` — Document an asset change

| Property | Value |
|---|---|
| **Target** | Asset key (string) |
| **Payload fields** | Arbitrary metadata (`label`, `type`, etc.) plus optional `mode` |
| **Merge mode** | `merge` (default) or `replace` |
| **Diff kind** | `modified` |
| **Diff granularity** | `asset` |
| **Previewable** | Yes (diff entry produced) |
| **Validation** | `mode` must be `"merge"` or `"replace"` if present |
| **⚠️ Deferred execution** | Asset mutations produce diff entries with **warning diagnostics** but are **not applied to the asset registry**. Asset-level mutation is deferred to a future host-owned asset ops path. The diff entry is informational. |

### 3.9 `asset.remove` — Document an asset removal

| Property | Value |
|---|---|
| **Target** | Asset key (string) |
| **Payload** | None |
| **Merge mode** | N/A |
| **Diff kind** | `removed` |
| **Diff granularity** | `asset` |
| **Previewable** | Yes (diff entry produced) |
| **⚠️ Deferred execution** | Same as `asset.update` — produces warning diagnostic, diff entry emitted, not applied to registry. |

### 3.10 `app.update` — Modify extension-owned app data

| Property | Value |
|---|---|
| **Target** | Extension ID (must be a valid extension ID per `validateExtensionId`) |
| **Payload fields** | Arbitrary key-value data for that extension's namespace, plus optional `mode` |
| **Merge mode** | `merge` (default) or `replace` |
| **Diff kind** | `modified` |
| **Diff granularity** | `app` |
| **Previewable** | Yes |
| **Validation** | Target must be a valid extension ID. `mode` must be `"merge"` or `"replace"` if present. |
| **Contribution ID validation** | The target is validated as an extension ID, not a contribution ID. Contribution-level app data is namespaced under the extension. |

### 3.11 `project-data.write` — Write extension-owned project data

| Property | Value |
|---|---|
| **Target** | Extension ID (must be valid) |
| **Payload fields** | `key` (string, required), `value` (unknown, required), `mode` (`merge` or `replace`, optional) |
| **Merge mode** | `merge` (default) or `replace` |
| **Diff kind** | `modified` |
| **Diff granularity** | `project-data` |
| **Previewable** | Yes |
| **Validation** | `key` and `value` are required. `mode` must be `"merge"` or `"replace"` if present. |
| **Limits** | `value` JSON-serialized size ≤ 64 KB (`MAX_ENTRY_BYTES`); per-extension total ≤ 1 MB (`MAX_EXTENSION_TOTAL_BYTES`); per-extension entries ≤ 128 (`MAX_ENTRIES_PER_EXTENSION`). Exceeding any limit produces an error-level diagnostic. |
| **Rollback safety** | Project-data writes participate in checkpoint/rollback because they go through the patch compiler. |

### 3.12 `project-data.delete` — Delete extension-owned project data

| Property | Value |
|---|---|
| **Target** | Extension ID (must be valid) |
| **Payload fields** | `key` (string, required) |
| **Merge mode** | N/A |
| **Diff kind** | `removed` |
| **Diff granularity** | `project-data` |
| **Previewable** | Yes |
| **Validation** | `key` is required. |

### 3.13 `extension.noop` — Namespaced extension operation placeholder

| Property | Value |
|---|---|
| **Target** | Extension ID (must be valid) |
| **Payload** | Arbitrary (validated for shape, not semantics) |
| **Merge mode** | N/A |
| **Diff kind** | `modified` |
| **Diff granularity** | `app` |
| **Previewable** | Yes |
| **Validation** | Target must be a valid extension ID. |
| **Purpose** | This is the **extension operation mechanism** — a namespaced no-op that validates, serializes, produces diff entries, and declares previewability. Extension authors can use this family as a template for future contribution-specific operations. The payload is round-tripped through the patch but does not mutate timeline state. |

---

## 4. Reserved operation families (deferred)

### 4.1 `clip.split` — Split a clip at a time point

| Property | Value |
|---|---|
| **Target** | Clip ID |
| **Status** | **Deferred** — validated but not executed in M3 |
| **Diagnostics** | Warning: `{ reserved: true, deferred: true, nonPreviewable: true }` |
| **Previewable** | No |

### 4.2 `clip.slice` — Extract a sub-clip range

| Property | Value |
|---|---|
| **Target** | Clip ID |
| **Status** | **Deferred** — validated but not executed in M3 |
| **Diagnostics** | Warning: `{ reserved: true, deferred: true, nonPreviewable: true }` |
| **Previewable** | No |

Reserved operations pass validation (they are known families) but produce non-blocking warning diagnostics. The compiler skips them during materialization — they produce no diff entries and do not mutate timeline state.

---

## 5. Operation validation and compilation

### 5.1 Validation (`validateTimelinePatch`)

- Every operation in the batch is validated independently.
- Unknown operation families → `error` diagnostic (code: `timeline-patch/unknown-op`).
- Reserved families → `warning` diagnostic (code: `timeline-patch/reserved-op`).
- Invalid payloads → `error` diagnostic (code: `timeline-patch/invalid-payload`).
- Invalid targets → `error` diagnostic (code: `timeline-patch/invalid-target`).
- Project-data limit violations → `error` diagnostic (code: `timeline-patch/project-data-limit`).
- Stale base version → `warning` diagnostic (code: `timeline-patch/stale-base-version`) — emitted by `TimelineOps.preview()`, not the pure validator.

### 5.2 Compilation (`compileTimelinePatch`)

- Validates first; refuses to compile if errors exist.
- Deep-clones `TimelineData` before applying operations.
- Applies operations in **order** (sorted by `order` field ascending, `undefined` last, stable by original index).
- Materializes through existing `configToRows` / `rowsToConfig` / `buildDataFromCurrentRegistry` serialization paths.
- Returns `nextData`, `mutation` (for `applyEdit`), `diff`, and `diagnostics`.
- Does **not commit** — caller feeds `mutation` into `applyEdit` or `nextData` into `commitData`.

### 5.3 Atomicity

If any operation in a batch produces an `error`-severity diagnostic, the entire batch is rejected. The canonical timeline is **never partially mutated**. This is enforced at the `TimelineOps.apply()` level: validation runs first, and if it fails, `apply()` throws before any mutation occurs.

---

## 6. Merge/replace behavior summary

| Operation family | Merge mode support | Default | Structural fields preserved |
|---|---|---|---|
| `clip.update` | `merge` / `replace` | `merge` | `id`, `track`, `at` |
| `track.update` | `merge` / `replace` | `merge` | `id` |
| `asset.update` | `merge` / `replace` | `merge` | Asset key (target) |
| `app.update` | `merge` / `replace` | `merge` | Extension ID (target) |
| `project-data.write` | `merge` / `replace` | `merge` | `key` |

**Merge rules:**
1. Payload keys present in the existing object are overwritten.
2. Payload keys absent from the existing object are added.
3. Existing keys absent from the payload are preserved.
4. Nested plain objects are deep-merged recursively (one level).
5. Arrays and primitives are replaced wholesale.

**Replace rules:**
1. All mutable fields are set from the payload.
2. Structural fields (`id`, `track`, `at` for clips; `id` for tracks) are preserved.
3. Any mutable field not mentioned in the payload is removed (set to `undefined`).

---

## 7. Reorder and ordering semantics

### 7.1 Operation ordering within a batch

Operations are applied in this order:
1. Operations with an explicit `order` field, sorted ascending.
2. Operations without an `order` field, in their original array position (stable).

This means a `clip.move` with `order: 0` is applied before a `clip.update` with no `order`, regardless of array position.

### 7.2 Clip positioning (clip.move)

- **`before` anchor:** Place the clip immediately before the specified clip in the track's clip order.
- **`after` anchor:** Place the clip immediately after the specified clip.
- **`before` + `after` conflict:** `before` wins.
- **`before` === `after`:** Warning diagnostic, operation skipped.
- **`at` (absolute time):** Place the clip at the specified time position in seconds.
- **`track` change:** Move to the specified track, preserving `at` or anchor position.
- **No position specified:** Clip stays at its current position (track-only move).

The ordering system is **sync-compatible** — it uses relative anchors (`before`/`after`) and fractional `order` values rather than absolute `clipIds[]` arrays, so concurrent edits from different sources can be merged without array-index conflicts.

---

## 8. Contribution ID validation

- `app.update` and `extension.noop` targets are validated as **extension IDs** using `validateExtensionId()` (non-empty, valid characters, dot-separated reverse-domain convention).
- Contribution IDs are **not directly validated** by the patch compiler — they are validated by `defineExtension()` at registration time and stored in `referencedContributionIds` on `ProjectExtensionRequirement`.
- The `extension.noop` family validates the extension ID but does not validate any contribution-specific payload semantics — that is the responsibility of the extension operation author.

---

## 9. Tombstone/envelope compatibility

Although CRDT sync is deferred (M4+), the patch shapes are designed for future tombstone compatibility:

- **`clip.remove` / `track.remove`:** The diff entry includes a `before` snapshot so undo/replay can reconstruct the removed object. The `affectedObjectIds` list preserves the identity of removed objects.
- **`asset.remove`:** Same pattern — `before` snapshot in the diff.
- **`project-data.delete`:** The key is preserved in the diff entry's `target` and `before` snapshot.
- **Envelope shape:** Every `TimelineDiffEntry` carries `granularity`, `kind`, `target`, `op`, and optional `before`/`after` — this is sufficient for a future CRDT to determine causal ordering and apply tombstones without re-deriving state from config snapshots.
- **`version` field:** Every `TimelinePatch` and `TimelineDiff` carries a monotonic `version` that can serve as a Lamport-clock anchor for future sync.

---

## 10. Deferred operation diagnostics

Deferred operations produce structured diagnostics with the following shape:

```typescript
{
  severity: 'warning',
  code: 'timeline-patch/reserved-op',
  message: 'clip.split is reserved and not yet implemented',
  op: 'clip.split',
  target: '<clip-id>',
  detail: { reserved: true, deferred: true, nonPreviewable: true }
}
```

The `nonPreviewable: true` flag signals to the proposal UI that this operation cannot be ghost-rendered. The proposal panel shows a `non-previewable` badge and omits the diff section for proposals containing only reserved operations.

---

## 11. Extension operation mechanism

### 11.1 `extension.noop` as the extension template

The `extension.noop` family is the **canonical extension operation mechanism**. It demonstrates every requirement for a new contribution-specific operation family:

1. **Namespaced:** The target is an extension ID, scoping the operation to a specific extension.
2. **Validates:** The target is validated as a valid extension ID. Invalid targets produce `timeline-patch/invalid-target` diagnostics.
3. **Serializes:** The payload round-trips through the patch compiler and appears in diff entries.
4. **Produces diffs:** `extension.noop` produces `modified` diff entries at `app` granularity.
5. **Previewable:** Declares `previewable: true` — the proposal UI will show it.
6. **Rejects invalid payloads:** While the no-op does not inspect payload semantics, future extension families can add per-payload validation following the same pattern as `clip.add` / `track.add`.

### 11.2 Adding a new operation family (future)

To add a new contribution-specific operation family in a future milestone:

1. Add the family string to `TimelinePatchOpFamily` in `src/sdk/index.ts`.
2. Add the family to `ACTIVE_OPS` in `src/tools/video-editor/lib/timeline-patch.ts`.
3. Add a `validate<Family>` function following the `validateClipAdd` / `validateTrackAdd` pattern.
4. Add a compile case in the `switch` statement in `compileTimelinePatch`.
5. Define the diff entry shape (`granularity`, `kind`, `before`/`after` snapshots).
6. Declare `previewable` status.
7. Add golden replay tests in `timeline-golden-replay.test.ts`.
8. Update this document.

### 11.3 Non-timeline primitives

New contribution-specific mutations for non-timeline primitives (e.g., keyframes, annotations) should use the same extension mechanism pattern but with their own host-owned ops/proposal contracts. They must **not** bypass the patch compiler or raw provider access.

---

## 12. Diagnostics reference

| Code | Severity | Trigger | Detail shape |
|---|---|---|---|
| `timeline-patch/unknown-op` | `error` | Operation family not in `ALL_KNOWN_OPS` | `{ op: string }` |
| `timeline-patch/reserved-op` | `warning` | Reserved family (clip.split, clip.slice) | `{ reserved: true, deferred: true, nonPreviewable: true }` |
| `timeline-patch/invalid-payload` | `error` | Payload field type mismatch or missing required field | `{ key: string, expected: string, actual: string }` |
| `timeline-patch/invalid-target` | `error` | Target fails type or format validation | `{ expected: string, actual: string }` |
| `timeline-patch/project-data-limit` | `error` | Extension project-data limit exceeded | `ProjectDataLimitDetail` |
| `timeline-patch/stale-base-version` | `warning` | Patch version differs from current configVersion | `{ patchVersion: number, currentVersion: number }` |
| `timeline-patch/unknown-target` | `warning` | Target ID not found (remove/update) | `{ targetKind: string }` |

All diagnostic codes use the `timeline-patch/` prefix. The `operationIndex` field (when applicable) points to the zero-based index of the offending operation in the batch.

---

## 13. Diff entry reference

Every compiled operation produces one or more `TimelineDiffEntry` records:

```typescript
interface TimelineDiffEntry {
  granularity: 'clip' | 'track' | 'asset' | 'app' | 'project-data';
  kind: 'added' | 'removed' | 'modified' | 'reordered';
  target: string;       // Object identifier
  op: TimelinePatchAnyOpFamily;
  before?: Record<string, unknown>;  // Pre-mutation snapshot (omitted for 'added')
  after?: Record<string, unknown>;   // Post-mutation snapshot (omitted for 'removed')
}
```

- **`before`/`after` are summaries, never raw internals.** They contain human-visible fields (`id`, `track`, `at`, `clipType`, `duration`) but never expose `rowData`, `meta`, `effects`, `registry`, `resolvedConfig`, or any provider-specific metadata.
- **Cascade removal** (e.g., `track.remove`) produces one diff entry per removed clip, plus the track entry.
- **`reordered` kind** is used for `clip.move` operations that only change position without modifying clip content.

---

## 14. Unsupported mutations

The following mutations are explicitly **not supported** in M3 and produce `timeline-patch/unknown-op` diagnostics:

- `asset.add`, `asset.create`, `asset.rename`
- `project.update`, `project.remove`, `project.create`
- `clip.rename`
- `track.move`

These operations are rejected at validation time with descriptive error messages. They may be added as active families in future milestones through the extension operation mechanism.
