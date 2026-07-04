# Deterministic Capture Profiles — V1 (M3b)

**Status:** Active (M3b)
**Last updated:** 2026-07-04
**Scope:** Frozen V1 deterministic capture profiles, table shapes, validation rules, and graph-owned keyframe operation placement.
**Extension boundary:** Concrete table bodies are **host/editor-owned**. Only the `deterministic-capture` bake-target discriminant is exposed through the public SDK (`LiveBakeTargetKind` in `@reigh/editor-sdk`).

---

## 1. Overview

Deterministic captures are host-validated data payloads produced by extensions that describe reproducible state: seeds, timed event tables, scalar mappings, and structured motion curves. They bridge live data sources to export-safe keyframe operations through a strict validation pipeline.

Every capture carries:

- A **frozen V1 profile discriminant** — exactly one of four supported profiles.
- **Provenance metadata** (producer extension, capture timestamp, session id, tags).
- A **SHA-256 content hash** of the serialized body for integrity verification.
- **Route constraints** that declare which render routes this capture is valid for.
- A **determinism posture** (`deterministic`, `preview-only`, or `process-dependent`).

Captures that fail validation (missing provenance, bad hash, unsupported profile, deferred/anti-scope profile, unknown interpolation, malformed body) are **rejected** and produce structured `DeterministicCaptureRejection` records with rule, message, and detail.

---

## 2. The four frozen V1 profiles

### 2.1 `seed` — Capture seed table

A single seed value for deterministic generation workflows.

```typescript
type CaptureSeedTableV1 = {
  profile: 'seed';
  seed: string | number;   // The seed value
  label?: string;           // Optional purpose label
};
```

**Validation rules:**
- `seed` must be present (not `null` or `undefined`).
- `seed` must be `string` or `number` — objects, booleans, and arrays are rejected.

---

### 2.2 `event` — Capture event table

Timed events with target paths, values, and collision policy.

```typescript
type CaptureEventTableV1 = {
  profile: 'event';
  events: CaptureEventV1[];
  defaultCollisionPolicy: CaptureCollisionPolicy;
};

type CaptureEventV1 = {
  eventId: string;                           // Stable event identifier
  time: number;                              // Time in seconds
  targetPath: string;                        // e.g. "params.opacity"
  value: number | string | boolean;          // The value at this event
  interpolation: KeyframeInterpolation;      // 'linear' | 'hold'
  collisionPolicy?: CaptureCollisionPolicy;  // Per-event override
  metadata?: Record<string, unknown>;
};
```

**Validation rules:**
- `events` array must be non-empty.
- Every event must have a non-empty `eventId` and `targetPath`.
- `time` must be a finite number.
- `interpolation` must be `'linear'` or `'hold'` — unknown interpolation modes are rejected.
- `collisionPolicy` (if present) must be one of the locked collision policy vocabulary.
- `defaultCollisionPolicy` must be a valid collision policy.

**Collision policies** (locked vocabulary):
| Policy | Behavior |
|---|---|
| `replace` | Incoming event replaces any existing candidate at the same `(targetPath, mappedTime)`. |
| `merge-first-wins` | First event to occupy a `(targetPath, mappedTime)` slot wins; later events are dropped. |
| `merge-last-wins` | Last event to target a `(targetPath, mappedTime)` slot wins; earlier events are replaced. |
| `reject` | Colliding events are both dropped with a blocking diagnostic. |

---

### 2.3 `scalar` — Capture scalar table

Static parameter-path → scalar-value mappings.

```typescript
type CaptureScalarTableV1 = {
  profile: 'scalar';
  entries: CaptureScalarEntryV1[];
};

type CaptureScalarEntryV1 = {
  targetPath: string;          // Target parameter path
  value: number | string | boolean;  // The scalar value
  label?: string;
};
```

**Validation rules:**
- `entries` must be non-empty.
- Every entry must have a non-empty `targetPath`.
- Duplicate `targetPath` values within the same table are rejected.
- `value` must be `number`, `string`, or `boolean` — `null`, `undefined`, and objects are rejected.

---

### 2.4 `structured-motion-curve` — Capture motion curve table

Keyframe-based motion curves on a single parameter.

```typescript
type CaptureStructuredMotionCurveV1 = {
  profile: 'structured-motion-curve';
  targetPath: string;                       // Target parameter path
  keyframes: CaptureCurveKeyframeV1[];      // Ordered keyframes
  defaultInterpolation: KeyframeInterpolation; // 'linear' | 'hold'
};

type CaptureCurveKeyframeV1 = {
  time: number;                             // Time in seconds
  value: number;                            // Numeric value only
  interpolation?: KeyframeInterpolation;    // Per-keyframe override
};
```

**Validation rules:**
- `targetPath` must be non-empty.
- `keyframes` must be non-empty.
- Every keyframe must have a finite `time` and finite numeric `value`.
- `defaultInterpolation` must be `'linear'` or `'hold'`.
- Per-keyframe `interpolation` (if present) must be `'linear'` or `'hold'`.

---

## 3. Deterministic capture validation pipeline

The full validation pipeline (`validateDeterministicCapture`) runs five checks in order:

1. **Profile discriminant** — Must be a known frozen V1 profile (`seed`, `event`, `scalar`, `structured-motion-curve`). Deferred/unknown profiles are rejected with both `unsupported-profile` and `deferred-profile` rules.
2. **Provenance** — Must include at least `capturedAt` (ISO 8601 timestamp).
3. **Route constraints** — Must be non-empty and contain only known constraint values (`preview`, `browser-export`, `worker-export`, `sidecar-export`).
4. **Content hash** — Must be a valid 64-character SHA-256 hex digest matching the serialized body.
5. **Body schema** — Routed to the per-profile validator (see §2).

On success, a `BakedValueRef` is produced with `captureId`, `profile`, `contentHash`, `provenanceHash` (SHA-256 of provenance metadata), `routeConstraints`, `valuePath`, and `determinism`. On failure, all rejections are collected and returned.

**Rejection rules** (locked vocabulary):
| Rule | Trigger |
|---|---|
| `missing-provenance` | Capture is missing `capturedAt` timestamp. |
| `bad-content-hash` | Content hash is missing, not valid SHA-256 hex, or mismatched. |
| `unsupported-profile` | Profile is not one of the four frozen V1 profiles. |
| `unsupported-event-type` | Event/scalar entry is malformed, missing required fields, or has duplicate target paths. |
| `unsupported-interpolation` | Interpolation mode is not `linear` or `hold`. |
| `bad-route-constraint` | Route constraint is unknown or the constraint list is empty. |
| `deferred-profile` | Profile is a deferred/anti-scope candidate (emitted alongside `unsupported-profile`). |
| `malformed-value-ref` | A baked value ref is structurally invalid. |

---

## 4. Graph-owned keyframe operations

Keyframe operations produced by deterministic capture conversion are **host-owned `GraphPreviewOperation` variants** — they are **not** members of `TimelinePatchOpFamily` and **not** reserved `graph.*` families.

| Operation | Kind | Description |
|---|---|---|
| `GraphKeyframeAddOp` | `keyframe.add` | Add a keyframe to a clip parameter. |
| `GraphKeyframeUpdateOp` | `keyframe.update` | Update an existing keyframe on a clip parameter. |
| `GraphKeyframeRemoveOp` | `keyframe.remove` | Remove a keyframe from a clip parameter. |

These operations carry optional `GraphKeyframeEventMetadata` for diagnostics and preview detail:

```typescript
interface GraphKeyframeEventMetadata {
  readonly captureRef?: string;       // Capture identifier
  readonly eventId?: string;          // Source event identifier
  readonly provenanceHash?: string;   // SHA-256 provenance hash
  readonly collisionPolicy?: CaptureCollisionPolicy;  // Policy that selected this keyframe
  readonly targetPath?: string;       // Canonical target path
}
```

**Invariant:** Graph-owned keyframe operations mutate only **cloned** graph input data, re-project through `projectCompositionGraph`, update `animates` edge detail, and **never** mutate the source timeline, graph input, sidecars, or timeline state.

---

## 5. Event-table conversion flow

Accepted deterministic event-table captures are converted to graph-owned keyframe operations through a pure pipeline:

1. **Timing resolution** — An injected `TimingMapResolver` maps event times to graph-space mapped times. Failures produce `composition/deterministic-capture-timing-failed` diagnostics.
2. **Value normalization** — An injected `ValueSchemaNormalizer` resolves target paths to `(clipId, paramName)` pairs and normalizes values to the `ClipKeyframe` value type. Failures produce `composition/deterministic-capture-value-normalization-failed` diagnostics.
3. **Collision resolution** — Events sharing a `(targetPath, mappedTime)` pair are resolved according to the collision policy (table default or per-event override) **before** any graph operations are emitted.
4. **Operation emission** — Surviving keyframe candidates are emitted as `GraphKeyframeAddOp` operations with full event-conversion metadata.

Each event produces a `LiveEventKeyframeDetail` with: `eventId`, `targetPath`, `mappedTime`, `normalizedValue`, `interpolation`, `collisionPolicy`, `captureRef`, `provenanceHash`, `operationKind` (`'keyframe.add'` or `'blocked'`), and blocking `diagnostics`.

**Sidecar/process exclusion:** The converter accepts opaque `timelineState` and `sidecars` parameters for future callers but **never mutates them**. It is intentionally pure and only produces graph operations.

---

## 6. Export safety

### 6.1 Live binding resolution (authoritative export)

The export guard classifies live bindings into two classes:

| Export target class | Clearing condition |
|---|---|
| **media-like** (visual/audio bindings) | Must have at least one durable `asset` or `render-material` deterministic ref with a non-empty ref string. |
| **non-media** (data/control bindings) | Must have at least one **structurally valid** `deterministic-capture` ref whose metadata includes `browser-export` in `routeConstraints`. |

Arbitrary deterministic refs **never** clear blockers by count alone. Sidecar-only refs, malformed capture metadata, and capture refs missing `browser-export` in route constraints all leave the export blocked.

### 6.2 Composition graph diagnostics during export

All five deterministic capture conversion diagnostic codes are **blocking** during export scans:

- `composition/deterministic-capture-conversion-failed`
- `composition/deterministic-capture-target-path-unresolvable`
- `composition/deterministic-capture-value-normalization-failed`
- `composition/deterministic-capture-timing-failed`
- `composition/deterministic-capture-provenance-mismatch`

These are surfaced as `export/`-prefixed diagnostic codes with `live-unbaked` blocker reason and are annotated with `captureRef` and `provenanceHash` detail fields. Material live-only diagnostics (`composition/material-live-only`, etc.) remain **separate** — they are not in the blocking target set and never reach the capture-conversion diagnostic path.

### 6.3 Malformed ref detection

A `deterministic-capture` ref is considered **malformed** (and export-blocking) if:
- `ref.kind` is not `'deterministic-capture'` or `ref.ref` is empty.
- `ref.metadata` is not a record.
- `ref.metadata.liveBake` is missing or `liveBake.targetKind !== 'deterministic-capture'`.
- `ref.metadata.deterministicCapture` is missing required fields (`captureId`, `profile`, `provenanceHash`, `routeConstraints`, `determinism`) or they fail structural validation.

Malformed refs are surfaced through `liveBindingHasMalformedAuthoritativeRef` and block export with a `malformed` resolution status.

---

## 7. Public SDK boundary

The public SDK (`@reigh/editor-sdk`) exposes **only** the `deterministic-capture` discriminant on `LiveBakeTargetKind`:

```typescript
export type LiveBakeTargetKind =
  | 'asset'
  | 'keyframe'
  | 'automation'
  | 'clip'
  | 'sidecar'
  | 'render-material'
  | 'deterministic-capture';
```

**Not exported through the public SDK:**
- `DeterministicCapture`, `BakedValueRef`, or any concrete table body types.
- `DeterministicCaptureProfileV1`, `CaptureSeedTableV1`, `CaptureEventTableV1`, `CaptureScalarTableV1`, `CaptureStructuredMotionCurveV1`.
- Validation functions (`validateDeterministicCapture`, `hashCaptureBody`, etc.).
- Collision policy engine or conversion interfaces.
- Graph keyframe operation types (`GraphKeyframeAddOp`, `GraphKeyframeUpdateOp`, `GraphKeyframeRemoveOp`).

All of these remain **host/editor-owned** and are imported from `@/tools/video-editor/types` and `@/tools/video-editor/runtime/deterministicCapture`.

---

## 8. What is explicitly excluded from V1

The following are **not** part of the frozen V1 deterministic capture scope and must not be added to this milestone:

- **Deferred/anti-scope profiles** — Any profile discriminant outside `seed`, `event`, `scalar`, `structured-motion-curve` is rejected. No deferred profile candidates are accepted or even type-narrowed.
- **Capture persistence on stored keyframes** — Existing stored keyframe shapes remain backward compatible. Provenance, event, and collision metadata stay on conversion preview and graph operation metadata.
- **Sidecar mutation** — The converter passes through opaque sidecar/timelineState references but never reads or mutates them.
- **TimelinePatch operations for keyframes** — Keyframe operations are strictly `GraphPreviewOperation` variants, not public `TimelinePatchOpFamily` members.
- **Capture body storage strategy** — Where capture bodies live long term (timeline metadata, provider storage, editor-side registry) is a deferred decision; this milestone only defines the validation and conversion pipeline.
- **Expanded route constraint vocabulary** — Only `preview`, `browser-export`, `worker-export`, and `sidecar-export` are recognized. Unknown constraints are rejected.
