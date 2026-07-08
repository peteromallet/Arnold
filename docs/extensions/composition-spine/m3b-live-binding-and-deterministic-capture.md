# M3b: Live Binding and Deterministic Capture

**Status:** Active (M3b)
**Last updated:** 2026-07-04
**Scope:** End-to-end architecture of the M3b live binding → deterministic capture → graph-owned keyframe pipeline. Covers live preview vs planner-owned export readiness, the frozen four-profile V1 scope, graph-owned keyframe op placement, export safety, and sidecar/process exclusions.
**Related:** [Deterministic Capture Profiles](./deterministic-capture-profiles.md) (detailed profile shapes and validation rules).

---

## 1. Architecture overview

M3b extends the composition spine with a deterministic capture pipeline that bridges **live data sources** to **export-safe keyframe operations** without exposing host internals to extensions.

```
┌──────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Live Source     │────▶│  Live Bake Planner   │────▶│  Deterministic       │
│  (webcam, midi,  │     │  (liveBake.ts)       │     │  Capture Validation  │
│   audio, osc…)   │     │                      │     │  (deterministic-     │
└──────────────────┘     └──────────┬───────────┘     │   Capture.ts)        │
                                    │                  └──────────┬──────────┘
                                    ▼                             │
                          ┌──────────────────┐                    │
                          │  Bake Result     │◀───────────────────┘
                          │  (LiveBake-      │
                          │   Deterministic- │
                          │   CaptureMeta)   │
                          └────────┬─────────┘
                                   │
                                   ▼
┌──────────────────┐     ┌──────────────────────┐
│  Event Table     │────▶│  Live Event          │
│  Conversion      │     │  Conversion          │
│                  │     │  (liveEvent-         │
│                  │     │   Conversion.ts)     │
└──────────────────┘     └──────────┬───────────┘
                                    │
                                    ▼
                          ┌──────────────────────┐
                          │  Graph Keyframe Ops  │
                          │  (patchPreview.ts)   │
                          │                      │
                          │  keyframe.add        │
                          │  keyframe.update     │
                          │  keyframe.remove     │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  Composition Graph   │
                          │  Preview / Export    │
                          │  Guard               │
                          └──────────────────────┘
```

**Key invariants:**
- Extensions produce `DeterministicCapture` payloads; the host validates, converts, and owns all graph operations.
- No extension code mutates timeline state, sidecars, or graph input directly.
- Graph keyframe operations are host-owned `GraphPreviewOperation` variants, not public `TimelinePatchOpFamily` members.
- Only the `deterministic-capture` bake-target discriminant is exposed through the public SDK.

---

## 2. Live preview vs planner-owned export readiness

M3b introduces a critical distinction between **live preview** and
**planner-owned export readiness**:

### 2.1 Live preview (non-blocking)

During editing, live bindings feed real-time data into the preview render. Deterministic capture refs may be absent or incomplete — the preview can render with live samples directly, producing a `preview-only` determinism posture. This is intentionally non-blocking because the user is still composing.

Live preview diagnostics (e.g., `composition/material-live-only`) are **warnings**, not errors. They inform the user that the current state cannot be exported but allow the editing workflow to continue uninterrupted.

### 2.2 Export readiness (blocking)

When the user initiates an export, the export guard scanner (`exportGuard.ts`)
performs a structured scan of all live bindings. The scanner classifies
bindings into two export target classes, then `buildExportReadinessPlan()` feeds
that scan payload into `planRender()`. Planner `RenderBlocker` records are the
canonical user-facing readiness vocabulary; scanner diagnostics are planner
input and debug metadata.

| Export target class | Examples | Clearing condition |
|---|---|---|
| **media-like** | Visual/audio bindings, shader material bindings | Must have at least one durable `asset` or `render-material` deterministic ref with a non-empty ref string. |
| **non-media** | Data/control bindings, parameter automation | Must have at least one **structurally valid** `deterministic-capture` ref whose metadata includes `browser-export` in `routeConstraints`. |

**Blocking rules:**
- Arbitrary deterministic refs **never** clear blockers by count alone.
- Sidecar-only refs leave the export blocked regardless of how many exist.
- Malformed capture metadata (missing `captureId`, invalid `provenanceHash`, unknown `profile`, empty `routeConstraints`) is surfaced as a `malformed` resolution status and blocks export.
- Capture refs missing `browser-export` in `routeConstraints` do not clear the blocker for non-media bindings.
- All five deterministic capture conversion diagnostic codes are exported as
  `export/`-prefixed diagnostic metadata. The planner maps those codes to
  `live-unbaked` blockers for readiness messaging.

### 2.3 Bake status propagation

Each live binding carries a bake status that informs the guard scan:

| Status | Behavior |
|---|---|
| `unbaked` | No deterministic refs exist; export blocked. |
| `partial` | Some ranges baked, unresolved ranges remain; export blocked. |
| `complete` | All ranges baked with valid deterministic refs; export unblocked if refs satisfy planner-owned readiness rules (§2.2). |

---

## 3. Frozen four-profile V1 scope

M3b defines exactly **four** deterministic capture profiles:

| Profile | Shape | Use case |
|---|---|---|
| `seed` | `CaptureSeedTableV1` | Single seed value for deterministic generation |
| `event` | `CaptureEventTableV1` | Timed events with target paths, values, and collision policy |
| `scalar` | `CaptureScalarTableV1` | Static parameter-path → scalar-value mappings |
| `structured-motion-curve` | `CaptureStructuredMotionCurveV1` | Keyframe-based motion curves on a single parameter |

**Any profile outside these four is rejected.** There is no fallback, no deferred profile acceptance, and no anti-scope widening. Unknown profile discriminants produce both `unsupported-profile` and `deferred-profile` rejection rules and terminate validation immediately.

For detailed table shapes and per-profile validation rules, see [Deterministic Capture Profiles](./deterministic-capture-profiles.md).

### 3.1 Profile-agnostic capture fields

Every `DeterministicCapture` carries these fields regardless of profile:

| Field | Type | Description |
|---|---|---|
| `captureId` | `string` | Unique capture identifier |
| `profile` | `DeterministicCaptureProfileV1` | Frozen V1 profile discriminant |
| `provenance` | `DeterministicCaptureProvenance` | Producer extension, version, timestamp, session, tags |
| `contentHash` | `string` | SHA-256 hex digest of the serialized body |
| `routeConstraints` | `DeterministicCaptureRouteConstraint[]` | Valid render routes (`preview`, `browser-export`, `worker-export`, `sidecar-export`) |
| `determinism` | `'deterministic' \| 'preview-only' \| 'process-dependent'` | Determinism posture |
| `body` | `DeterministicCaptureTableV1` | Exactly one of the four V1 table shapes |

---

## 4. Graph-owned keyframe operation placement

### 4.1 Operation vocabulary

Keyframe operations produced by deterministic capture conversion are **host-owned `GraphPreviewOperation` variants**:

```typescript
type GraphPreviewOperation =
  | GraphShaderAssignOp     // kind: 'shader.assign'
  | GraphShaderRemoveOp     // kind: 'shader.remove'
  | GraphKeyframeAddOp      // kind: 'keyframe.add'
  | GraphKeyframeUpdateOp   // kind: 'keyframe.update'
  | GraphKeyframeRemoveOp;  // kind: 'keyframe.remove'
```

These are **not** members of `TimelinePatchOpFamily` and **not** reserved `graph.edge.*` / `graph.node.*` families. They exist solely within the composition spine's preview path.

### 4.2 Operation lifecycle

1. **Conversion** — `convertEventTableToGraphOperations` (in `liveEventConversion.ts`) resolves timing, normalizes values, applies collision policy, and emits `GraphKeyframeAddOp` operations.
2. **Preview attachment** — Accepted event-table bake results are converted to `GraphPreviewOperation[]` and attached to `CompositionGraph.preview()` via `createGraphPreviewWithOps` (in `liveBake.ts`).
3. **Clone and apply** — `applyGraphPreviewOperations` (in `patchPreview.ts`) deep-clones clip automation/keyframe state from the graph input, applies operations only to the clone, and re-projects through `projectCompositionGraph`.
4. **Re-projection** — The projected graph updates `animates` edge detail (including `keyframeCount`) based on the cloned keyframe state.

### 4.3 Immutability invariant

Graph-owned keyframe operations **never** mutate:
- The source timeline config or graph input.
- Opaque `timelineState` or `sidecars` references passed through the converter.
- Existing clip keyframe data on the original graph input.

All mutations happen on a deep-cloned copy, and the original input remains unchanged across every operation application.

---

## 5. Export safety

### 5.1 Export guard scanner behavior

The export guard (`exportGuard.ts`) performs a three-phase scan that feeds
planner readiness:

1. **Live binding scan** — `scanTimelineLiveBindings` (in `timeline-domain.ts`) collects all `TimelineLiveBinding` records from the timeline config.
2. **Resolution classification** — Each binding is classified as `media-like` or `non-media` based on its source kind and channel type.
3. **Scanner evaluation** — Bindings are checked against the clearing inputs in
   §2.2 and emitted as guard-compatible findings/diagnostics.

The planner can clear a binding only when:
- It has a `complete` bake status (no partial ranges).
- For media-like bindings: at least one deterministic ref is a durable `asset` or `render-material` with a non-empty ref.
- For non-media bindings: at least one deterministic ref is a structurally valid `deterministic-capture` ref with `browser-export` in its route constraints.

### 5.2 Composition graph diagnostics

During export, the composition graph's `diagnostics` array is scanned for target
codes. All five deterministic capture conversion codes are carried as
`export/*` diagnostic metadata and mapped by the planner adapter to
`live-unbaked` readiness blockers:

| Composition diagnostic | Export diagnostic | Blocker reason |
|---|---|---|
| `composition/deterministic-capture-conversion-failed` | `export/deterministic-capture-conversion-failed` | `live-unbaked` |
| `composition/deterministic-capture-target-path-unresolvable` | `export/deterministic-capture-target-path-unresolvable` | `live-unbaked` |
| `composition/deterministic-capture-value-normalization-failed` | `export/deterministic-capture-value-normalization-failed` | `live-unbaked` |
| `composition/deterministic-capture-timing-failed` | `export/deterministic-capture-timing-failed` | `live-unbaked` |
| `composition/deterministic-capture-provenance-mismatch` | `export/deterministic-capture-provenance-mismatch` | `live-unbaked` |

Each conversion diagnostic carries `captureRef` and `provenanceHash` detail fields when available, surfaced through `CompositionDiagnosticDetail`.

### 5.3 Material vs capture diagnostic separation

Material live-only diagnostics (`composition/material-live-only`,
`composition/material-stale`, etc.) are **not** in
`BLOCKING_TARGET_COMPOSITION_DIAGNOSTIC_CODES`. They are handled separately
through the material diagnostic path and never reach the capture-conversion scan
path. This keeps the two diagnostic categories distinct so that the planner can
map material and capture issues to the correct readiness blockers.

---

## 6. Sidecar and process exclusions

### 6.1 Converter purity

The live event converter (`liveEventConversion.ts`) is intentionally **pure**:

- It accepts opaque `timelineState` and `sidecars` parameters in `ConvertEventTableRequest` for future callers.
- It **never reads, inspects, or mutates** these opaque values.
- It produces only `GraphKeyframeAddOp[]` operations and `LiveEventKeyframeDetail[]` metadata.
- All side effects are owned by the caller (bake planner, graph preview path).

### 6.2 Sidecar-only refs

A deterministic ref with `kind: 'sidecar'` is recognized as a valid
`TimelineLiveDeterministicRefKind` but **does not clear the planner export
blocker**. Sidecar refs are metadata sidecars (JSON, CSV, etc.) that accompany
the export, not durable artifacts that prove the live data has been baked. The
guard scan requires `asset`, `render-material`, or validated
`deterministic-capture` refs before the planner can clear blockers.

### 6.3 Process-dependent posture

Captures with `determinism: 'process-dependent'` are accepted through
validation (they carry valid provenance, content hash, and body schema) but
their determinism posture signals that the captured values depend on
host-process state (e.g., system time, random seed from host entropy). The guard
scan does **not** currently emit a blocker for this posture alone; it is
metadata for downstream consumers to interpret.

---

## 7. Public SDK boundary

The public SDK (`@reigh/editor-sdk`) exposes only the minimal surface needed for extensions to target deterministic capture during live bake:

```typescript
// src/sdk/video/liveData.ts — public export
export type LiveBakeTargetKind =
  | 'asset'
  | 'keyframe'
  | 'automation'
  | 'clip'
  | 'sidecar'
  | 'render-material'
  | 'deterministic-capture';  // ← M3b addition
```

**Not exported through the public SDK:**
- All concrete deterministic capture types (`DeterministicCapture`, `BakedValueRef`, `CaptureEventTableV1`, etc.)
- Validation functions (`validateDeterministicCapture`, `hashCaptureBody`, etc.)
- Conversion interfaces (`TimingMapResolver`, `ValueSchemaNormalizer`, `KeyframeCollisionPolicyEngine`)
- Graph keyframe operation types (`GraphKeyframeAddOp`, `GraphKeyframeUpdateOp`, `GraphKeyframeRemoveOp`)
- Collision policy vocabulary or rejection rule enums

This keeps the SDK surface minimal and portable while allowing the host to evolve capture profiles without breaking extension contracts. Extensions produce captures as opaque JSON; the host owns validation and conversion.

---

## 8. What is explicitly excluded from M3b

| Exclusion | Rationale |
|---|---|
| **Deferred/anti-scope profiles** | Only the four frozen V1 profiles are accepted. Unknown profiles are rejected immediately. |
| **Capture persistence on stored keyframes** | Existing keyframe shapes remain backward compatible. Provenance/event/collision metadata stays on preview/op metadata. |
| **Sidecar mutation** | The converter passes through opaque sidecar refs but never reads or writes them. |
| **TimelinePatch operations for keyframes** | Keyframe ops are `GraphPreviewOperation` variants, not public patch families. |
| **Capture body storage strategy** | Where capture bodies are persisted is a deferred decision. |
| **Expanded route constraint vocabulary** | Only `preview`, `browser-export`, `worker-export`, `sidecar-export` are recognized. Unknown constraints are rejected. |
| **Capture profile expansion beyond V1** | No new profiles, no deferred candidates, no anti-scope widening. |

---

## 9. Key files

| File | Role |
|---|---|
| `src/tools/video-editor/types/index.ts` | Host-owned type definitions (lines 580–778) |
| `src/tools/video-editor/runtime/deterministicCapture.ts` | Validation pipeline, vocabularies, SHA-256 hashing |
| `src/tools/video-editor/runtime/liveEventConversion.ts` | Pure event-table → graph keyframe op converter |
| `src/tools/video-editor/runtime/liveBake.ts` | Live bake planner with deterministic capture metadata threading |
| `src/tools/video-editor/runtime/composition/patchPreview.ts` | Graph preview operations, clone-and-apply, event metadata |
| `src/tools/video-editor/runtime/composition/diagnostics.ts` | Composition diagnostic codes (M3b conversion codes at lines 107–123) |
| `src/tools/video-editor/runtime/exportGuard.ts` | Export guard scanner with capture diagnostic metadata for planner readiness |
| `src/tools/video-editor/lib/timeline-domain.ts` | Live binding resolution, deterministic ref validation, malformed detection |
| `src/sdk/video/liveData.ts` | Public SDK `LiveBakeTargetKind` with `deterministic-capture` discriminant |
| `src/sdk/index.ts` | SDK barrel re-export |
