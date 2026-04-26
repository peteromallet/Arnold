---
title: Video Editor OSS Extraction Design
status: proposed
doc_mode: true
source_path: docs/design/video-editor-oss-extraction.md
last_updated: 2026-04-19
audiences:
  - OSS contributors
  - reigh-app engineers
---

# Video Editor OSS Extraction Design

This document describes how to extract `reigh-app/src/tools/video-editor/` into a standalone multi-package repository with four public packages: `schema`, `engine`, `editor`, and `cli`. The extracted packages must contain zero reigh-specific product concepts. Reigh-specific concerns remain in `reigh-app` and integrate through explicit ports or app-level extensions.

## Executive Summary

The current video editor is already close to a clean split in two important ways. First, the rendering path is materially separated: `TimelineRenderer.tsx`, `VisualClip.tsx`, `AudioTrack.tsx`, and `EffectLayerSequence.tsx` are Remotion-centric composition code with no direct Supabase, auth, or project selection imports (`reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:1-173`, `reigh-app/src/tools/video-editor/compositions/VisualClip.tsx:1-220`, `reigh-app/src/tools/video-editor/compositions/AudioTrack.tsx:1-68`, `reigh-app/src/tools/video-editor/compositions/EffectLayerSequence.tsx:1-65`). Second, the editor already has a store/provider seam: `useTimelineState()` creates and seeds a Zustand-backed external store, `TimelineStoreProvider` publishes it, and `VideoEditorShell` renders a propless `<TimelineEditor />` that reads selectors from the store (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:413-838`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:34-50`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:302-550`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:67-71`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:686`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:744`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:770`).

The extraction problem is not rendering. It is host coupling. `TimelineEditor.tsx` currently imports project selection, shots context, shot creation/navigation, `VideoGenerationModal`, active task tracking, final-video availability, pinned shot-group hooks, stale-variant handling, and generation duplication utilities directly (`reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:10-50`). `VideoEditorProvider.tsx` also binds the editor to `MediaLightbox`, `ShotsContext`, pending generation-add flows, and the app-level AgentChat bridge (`reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:5-41`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:74-112`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:142-209`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:367-405`). The extraction therefore succeeds only if those concerns are removed from the packages and reintroduced through ports and extension slots.

Why extract:

- OSS audience: a versioned JSON timeline schema, a headless render engine, a reusable React editor shell, and a CLI renderer are independently valuable for teams building lightweight timeline tools.
- Reigh-app: smaller in-tree surface area, cleaner boundaries around Supabase/auth/project state, clearer test ownership, and the ability to consume the editor as a dependency instead of an in-tree subsystem.

Non-goals:

- This is not a general non-linear editor replacement.
- This does not abstract away Remotion in v1.
- This does not move reigh-specific workflow concepts into the OSS packages.
- This does not promise stable host extension APIs before the first schema and port contracts land.

Open placeholders to resolve during implementation:

| Placeholder | Proposed placeholder value | Why it remains open |
| --- | --- | --- |
| npm scope and package names | `@tbd/schema`, `@tbd/engine`, `@tbd/editor`, `@tbd/cli` | The final package scope depends on repo ownership and publishing setup. |
| GitHub org | `TBD` | Needed for README badges, docs URLs, and changesets publish config. |
| Remotion version pin | `Align to current reigh-app pin, then freeze at extraction cut` | Current reigh-app uses `remotion` `^4.0.434`, `@remotion/player` `^4.0.434`, `@remotion/media` `^4.0.438`, `@remotion/web-renderer` `4.0.438` (`reigh-app/package.json:45-72`). |
| OSS docs location | `apps/docs` in extracted repo | This reigh doc lives at `docs/design/video-editor-oss-extraction.md`; the standalone repo docs IA is still TBD. |

## Table of Contents

Part A. OSS repository design, for OSS contributors

1. [Package Layout](#1-package-layout)
2. [Split Rationale](#2-split-rationale)
3. [Port Interfaces](#3-port-interfaces)
4. [Timeline JSON Format Specification](#4-timeline-json-format-specification)
5. [OSS Repository Structure](#5-oss-repository-structure)
6. [OSS Polish Checklist](#6-oss-polish-checklist)
7. [CLI Renderer Specification](#7-cli-renderer-specification)
8. [Test Strategy](#8-test-strategy)

Part B. Reigh-app integration, for reigh engineers

9. [Forbidden in Core](#9-forbidden-in-core)
10. [File and Folder Migration Table](#10-file-and-folder-migration-table)
11. [Host Touchpoint Mapping](#11-host-touchpoint-mapping)
12. [Reference Supabase Adapter and Host Extensions](#12-reference-supabase-adapter-and-host-extensions)
13. [Migration Sequence and Sync Strategy](#13-migration-sequence-and-sync-strategy)

Part C. Open questions and risks, for both audiences

14. [Open Questions and Risks](#14-open-questions-and-risks)

Appendices

- [Appendix A. Glossary](#appendix-a-glossary)
- [Appendix B. Reigh-App File References](#appendix-b-reigh-app-file-references)

## Part A. OSS Repository Design

## 1. Package Layout

Dependency direction is explicit and one-way:

```text
@tbd/cli    -> @tbd/engine -> @tbd/schema
@tbd/editor -> @tbd/engine -> @tbd/schema
```

| Package | Responsibility | Public exports | Peer dependencies | Out of scope |
| --- | --- | --- | --- | --- |
| `@tbd/schema` | Versioned, hand-editable `TimelineConfig` contract; zod parsing; JSON Schema export; migrations; stable serializer. The baseline comes from today's `TimelineConfig`, `TimelineClip`, `TrackDefinition`, and defaults (`reigh-app/src/tools/video-editor/types/index.ts:51-186`, `reigh-app/src/tools/video-editor/lib/defaults.ts:3-35`, `reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`). | `TimelineConfigSchema`, `TimelineTrackSchema`, `TimelineClipSchema`, `migrateTimeline()`, `serializeTimeline()`, `createDefaultTimelineConfig()`, JSON Schema files. | None. `zod` is a direct dependency, not a peer. | Rendering, React UI, persistence, auth, project routing, reigh extensions. |
| `@tbd/engine` | Pure Remotion render engine: given `TimelineConfig`, frame/time context, effect registry, and `AssetResolver`, produce preview or final-frame output. Candidate source files are already in `compositions/` and render-time utilities (`reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:1-173`, `reigh-app/src/tools/video-editor/compositions/VisualClip.tsx:1-220`, `reigh-app/src/tools/video-editor/compositions/AudioTrack.tsx:1-68`, `reigh-app/src/tools/video-editor/compositions/EffectLayerSequence.tsx:1-65`). | `TimelineRenderer`, clip renderers, `DynamicEffectRegistry`, render helpers, engine typings, `createEngineAssetResolver()`. | `react`, `remotion`, `@remotion/media`. | Timeline picker UI, inspector state, Supabase, list/create/delete workflows, app overlays. |
| `@tbd/editor` | React editor shell and store, wired through ports and extension slots. The current store/provider seam is the anchor: `TimelineStoreProvider`, selector hooks, and `useTimelineState()` (`reigh-app/src/tools/video-editor/hooks/timelineStore.ts:34-50`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:302-550`, `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:413-838`). | `EditorProvider`, `TimelineEditorShell`, `TimelineCanvas`, preview components, editor hooks, default in-memory ports, slot contracts, test helpers. | `react`, `react-dom`, `remotion`, `@remotion/player`. `zustand` can be a direct dependency to keep the store internal. | Supabase adapter, auth, project selection, MediaLightbox, AgentChat, task-based export, shots context. |
| `@tbd/cli` | Headless render entrypoint for `timeline.json -> video file`. Uses `@tbd/schema` for validation and `@tbd/engine` for rendering. | `render` command, programmatic `renderTimeline()` helper. | None. Runtime deps are direct. | React editor UI, app shell, timeline creation/listing UI. |

Effect registry placement decision:

- Put `DynamicEffectRegistry` in `@tbd/engine`.
- Rationale: render-time effect resolution must work in browser preview, SSR, and CLI/headless rendering. The current registry is runtime-agnostic and already models registration, async registration, lookup, schemas, and subscriptions without host app imports (`reigh-app/src/tools/video-editor/effects/DynamicEffectRegistry.ts:12-120`).
- Editor packages may re-export a convenience registration hook, but the canonical ABI lives in the engine so the CLI and future headless use cases do not fork effect registration semantics.

## 2. Split Rationale

### 2.1 Why `schema` is a standalone package

Current save/load logic is already treated as a contract boundary. `DataProvider.loadTimeline()` returns a config plus version, `saveTimeline()` enforces optimistic concurrency, and `serialize.ts` explicitly validates top-level, clip, and track keys (`reigh-app/src/tools/video-editor/data/DataProvider.ts:53-71`, `reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`). That contract should be publishable and testable without React or Remotion.

### 2.2 Why `engine` stays pure

The current composition layer has no direct Supabase, project, auth, or lightbox coupling. The rendering path is already centered around Remotion components plus config resolution (`reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:1-173`, `reigh-app/src/tools/video-editor/compositions/VisualClip.tsx:1-220`, `reigh-app/src/tools/video-editor/compositions/AudioTrack.tsx:1-68`). Keeping the engine pure gives one render truth for editor preview, CLI render, and headless/server render.

### 2.3 Why `editor` is ports-and-adapters

Today the editor shell is mixed: the store shape is generic, but the runtime bootstrap pulls in provider state, asset ops, project selection, and specialized host workflows (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:413-838`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:15-29`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:114-405`). A ports-and-adapters editor preserves the generic store and shell while moving backend and app concerns to injected adapters.

### 2.4 Why the editor should keep a provider-plus-shell pair

Recommendation: export a provider-plus-shell pair in v1, not a full prop-driven rewrite.

- Current architecture is already store-first. `useTimelineState()` creates a store, derives `data`, `ops`, `chrome`, and `playback` slices, and synchronizes them into `TimelineStoreProvider` before descendants render (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:423-426`, `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:641-838`).
- `VideoEditorShell` renders a propless `<TimelineEditor />` and sibling components consume store selectors, not a giant prop object (`reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:15-29`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:686`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:744`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:770`).
- `timelineStore.ts` already formalizes the public slices as `data`, `ops`, `chrome`, and `playback` (`reigh-app/src/tools/video-editor/hooks/timelineStore.ts:34-50`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:302-550`).

The extracted surface should therefore be:

```ts
<EditorProvider ports={ports} hostContext={hostContext} initialDocument={...}>
  <TimelineEditorShell />
</EditorProvider>
```

A convenience `<Editor />` wrapper may exist for demos, but the primary API should preserve the current provider/store composition instead of flattening the entire editor state into props.

### 2.5 Why the CLI is separate

The CLI must be usable without React routing, browser-only preview code, or app wiring. A dedicated package also isolates Node-only dependencies such as `@remotion/web-renderer` from the browser editor surface. Reigh already keeps render UI separate from the pure Remotion preview component (`reigh-app/src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:11-143`, `reigh-app/src/tools/video-editor/hooks/useRenderState.ts`, `reigh-app/src/tools/video-editor/hooks/useClientRender.ts`).

## 3. Port Interfaces

The extracted editor exposes five ports: `DataProvider`, `AssetResolver`, `MediaPicker`, `Exporter`, and `HostContext`. Each ships with an in-memory or local default so the editor can run standalone.

### 3.1 DataProvider

Canonical compatibility anchor: `reigh-app/src/tools/video-editor/data/DataProvider.ts:53-71`.

Proposed OSS contract:

```ts
export interface LoadedTimeline {
  config: TimelineConfig;
  configVersion: number;
}

export interface TimelineSummary {
  id: string;
  name: string;
  updatedAt: string;
}

export interface TimelineCheckpointInput {
  timelineId: string;
  config: TimelineConfig;
  createdAt: string;
  triggerType: 'session_boundary' | 'edit_distance' | 'semantic' | 'manual';
  label: string;
  editsSinceLastCheckpoint: number;
}

export interface TimelineCheckpoint extends TimelineCheckpointInput {
  id: string;
}

export interface TimelineSubscriptionEvent {
  type: 'timeline-updated' | 'asset-registry-updated' | 'timeline-deleted';
  timelineId: string;
}

export interface DataProvider {
  loadTimeline(timelineId: string): Promise<LoadedTimeline>;
  saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number>;
  listTimelines?(scope?: { projectId?: string | null }): Promise<TimelineSummary[]>;
  deleteTimeline?(timelineId: string): Promise<void>;
  saveCheckpoint?(timelineId: string, checkpoint: TimelineCheckpointInput): Promise<string>;
  loadCheckpoints?(timelineId: string): Promise<TimelineCheckpoint[]>;
  loadAssetRegistry(timelineId: string): Promise<AssetRegistry>;
  resolveAssetUrl(file: string): string;
  registerAsset?(timelineId: string, assetId: string, entry: AssetRegistryEntry): Promise<void>;
  uploadAsset?(
    file: File | Blob | Uint8Array,
    context: { timelineId: string; userId?: string | null; filename?: string },
  ): Promise<AssetRegistryEntry>;
  loadWaveform?(assetKey: string): Promise<WaveformData | null>;
  loadAssetProfile?(assetKey: string): Promise<AssetProfile | null>;
  subscribe?(
    timelineId: string,
    listener: (event: TimelineSubscriptionEvent) => void,
  ): Promise<() => void> | (() => void);
}
```

Error semantics:

- `saveTimeline()` must throw a version-conflict error equivalent to today's `TimelineVersionConflictError` when `expectedVersion` is stale (`reigh-app/src/tools/video-editor/data/DataProvider.ts:25-37`).
- `loadTimeline()` should throw a not-found error equivalent to today's `TimelineNotFoundError` for missing documents (`reigh-app/src/tools/video-editor/data/DataProvider.ts:39-51`).
- Optional methods must fail closed. If a method is absent, editor UI should hide the feature rather than crash.

In-memory default:

- `InMemoryDataProvider` stores timelines, registries, and checkpoints in a `Map`.
- Supported: `loadTimeline`, `saveTimeline`, `listTimelines`, `deleteTimeline`, `loadAssetRegistry`, `saveCheckpoint`, `loadCheckpoints`, `resolveAssetUrl`, `subscribe`.
- Unsupported by default: `uploadAsset`, `registerAsset`, `loadWaveform`, `loadAssetProfile`.
- Limitation: all data is lost on reload.

Method-by-method gap table:

| Capability | Current surface | Proposed OSS surface | Status | Notes |
| --- | --- | --- | --- | --- |
| Load timeline | `loadTimeline(timelineId)` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:54`) | Same | `UNCHANGED` | Keep optimistic-versioned load result. |
| Save timeline | `saveTimeline(timelineId, config, expectedVersion, registry?)` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:55-60`) | Same | `UNCHANGED` | Needed by `useTimelinePersistence()` (`reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts:104-199`). |
| Save checkpoint | `saveCheckpoint?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:61`) | Same | `UNCHANGED` | Used by `useTimelineHistory()` (`reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:137-166`). |
| Load checkpoints | `loadCheckpoints?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:62`) | Same | `UNCHANGED` | Used by `useTimelineHistory()` (`reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:319-343`). |
| Load asset registry | `loadAssetRegistry(timelineId)` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:63`) | Same | `UNCHANGED` | Needed during initial timeline hydration (`reigh-app/src/tools/video-editor/lib/timeline-data.ts:388-403`). |
| Resolve asset URL | `resolveAssetUrl(file)` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:64`) | Same in v1 | `UNCHANGED` | Preserved because current callers bind it directly into asset management and external drop flows (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:579-593`, `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:611-624`). |
| Register asset | `registerAsset?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:65`) | Same | `UNCHANGED` | Required by `useAssetOperations()` and stale-variant repair (`reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts:27-39`, `reigh-app/src/tools/video-editor/hooks/useStaleVariants.ts:169-219`). |
| Upload asset | `uploadAsset?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:66-69`) | Same | `UNCHANGED` | Current helper wraps it and invalidates queries (`reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts:14-25`, `reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts:41-58`). |
| Load waveform | `loadWaveform?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:70`) | Same | `UNCHANGED` | Keep optional; standalone default can return `null`. |
| Load asset profile | `loadAssetProfile?` (`reigh-app/src/tools/video-editor/data/DataProvider.ts:71`) | Same | `UNCHANGED` | Needed for transcript/profile lookups (`reigh-app/src/tools/video-editor/lib/timeline-data.ts:405-410`). |
| List timelines | No method on `DataProvider`; current list/create/delete lives in `useTimelinesList()` (`reigh-app/src/tools/video-editor/hooks/useTimelinesList.ts:8-98`) | `listTimelines?()` | `ADDED` | Needed for OSS examples and standalone picker screens. |
| Delete timeline | No method on `DataProvider`; current delete also lives in `useTimelinesList()` (`reigh-app/src/tools/video-editor/hooks/useTimelinesList.ts:75-98`) | `deleteTimeline?()` | `ADDED` | Keeps lifecycle operations behind one persistence port. |
| Subscribe | No method on `DataProvider`; current realtime is app-level `realtimeEventProcessor` plus React Query invalidation (`reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts:29-43`) | `subscribe?()` | `ADDED` | This is a new design addition, not an extraction of current behavior. |

### 3.2 AssetResolver

Purpose: decouple the engine from app-specific URL, filesystem, CDN, or auth token logic.

```ts
export interface AssetResolver {
  resolveAssetUrl(input: {
    assetKey?: string;
    file: string;
    entry?: AssetRegistryEntry;
    mode: 'preview' | 'render';
  }): Promise<string> | string;
  loadWaveform?(assetKey: string): Promise<WaveformData | null>;
  loadProfile?(assetKey: string): Promise<AssetProfile | null>;
}
```

Error semantics:

- `resolveAssetUrl()` should throw only for unrecoverable resolution failure.
- Missing waveform/profile data is not an error; return `null`.

In-memory default:

- `LocalAssetResolver` resolves absolute URLs unchanged and resolves relative paths against an `assetRoot`.
- Browser demos default `assetRoot` to `window.location.origin`.
- CLI defaults `assetRoot` to `process.cwd()` or `--asset-root`.

Why a separate port exists even though `DataProvider` still carries URL/profile methods in v1:

- The editor must remain source-compatible with the current `DataProvider` surface.
- The engine should not know anything about timeline listing, saves, checkpoints, or uploads.
- `EditorProvider` can synthesize a resolver from `DataProvider` when a dedicated resolver is not supplied.

### 3.3 MediaPicker

Purpose: abstract MediaLightbox, file pickers, generation libraries, or custom DAM integrations.

```ts
export interface MediaPickerSelection {
  assetId?: string;
  file?: File;
  fileUrl?: string;
  generationId?: string;
  title?: string;
  mimeType?: string;
  metadata?: Record<string, unknown>;
}

export interface MediaPicker {
  open(options: {
    accept: Array<'image' | 'video' | 'audio'>;
    multiple?: boolean;
    initialQuery?: string;
  }): Promise<MediaPickerSelection[]>;
}
```

Error semantics:

- `open()` resolves to an empty array `[]` when the user cancels. Cancellation is NOT an error; hosts must not throw for user-initiated cancellation.
- `open()` rejects with `PickerUnavailableError` when the picker cannot render (no browser, no route, etc.). Callers should catch and fall back to drag-and-drop.
- `open()` rejects with `PickerPermissionError` for denied OS-level file access. The editor treats this as non-fatal and surfaces a toast; timeline state is never mutated on picker failure.
- All rejections must be `Error` subclasses with a `code` string. Hosts MUST NOT reject with raw strings or non-Error values.

Current host coupling that motivates the port:

- `VideoEditorProvider` opens `MediaLightbox` and overlays a custom navigation indicator (`reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:5-8`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:246-253`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:367-381`).
- `VideoEditorLightboxOverlay.tsx` is app-only chrome around that lightbox (`reigh-app/src/tools/video-editor/components/VideoEditorLightboxOverlay.tsx:1-39`).

In-memory default:

- Browser only: hidden `<input type="file">` picker.
- No project library, no generation history, no lightbox navigation.

### 3.4 Exporter

Purpose: abstract browser preview export, local render, queued background render, or external task systems.

```ts
export interface ExportRequest {
  timeline: TimelineConfig;
  registry?: AssetRegistry;
  output: {
    file: string;
    codec?: 'h264' | 'h265' | 'vp8' | 'vp9' | 'prores';
    width?: number;
    height?: number;
    fps?: number;
  };
}

export interface ExportProgress {
  phase: 'validating' | 'rendering' | 'encoding' | 'uploading' | 'complete' | 'failed';
  progress?: number;
  log?: string;
  resultUrl?: string | null;
}

export interface ExportJobHandle {
  id: string;
  subscribe(listener: (progress: ExportProgress) => void): () => void;
  cancel?(): Promise<void>;
}

export interface Exporter {
  render(request: ExportRequest): Promise<ExportJobHandle>;
}
```

Error semantics:

- `render()` MAY reject synchronously (via returned promise rejection) for invalid `ExportRequest` (zod validation failure, missing assets that cannot be resolved). In that case the caller MUST NOT receive an `ExportJobHandle`.
- Once `render()` resolves with a handle, subsequent failures MUST flow through `ExportProgress` events with `phase: 'failed'` and a populated `log` string. The returned `subscribe(listener)` never throws; it returns an unsubscribe function.
- `cancel()` is optional; when present, it MUST be idempotent and MUST be safe to call after the job has already reached `complete` or `failed`.
- Progress listener errors (thrown synchronously by the listener) MUST be caught by the exporter and logged, not propagated to other listeners or surfaced as job failures.

Current seam:

- Render state is already isolated in `useRenderState()` and published into the chrome slice by `useTimelineState()` (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:446-487`, `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:773-807`).
- Preview UI lives in `VideoEditorShell` and `RemotionPreview`, not the engine (`reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:15-29`, `reigh-app/src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:11-143`).

In-memory default:

- `LocalExporter` renders in-process using the engine and local filesystem or browser download primitives.
- No durable job queue, no resumable tasks, no remote workers.

### 3.5 HostContext

Purpose: small, non-persistent UI/config values that are not document data.

```ts
export interface HostContext {
  userId?: string | null;
  locale?: string;
  timeZone?: string;
  brand?: {
    appName?: string;
    accentColor?: string;
  };
  featureFlags?: Record<string, boolean>;
  routes?: {
    openTimeline?: (timelineId: string) => void;
    openAsset?: (assetId: string) => void;
  };
}
```

Error semantics:

- `HostContext` is a plain data record, not an async interface. It has no methods that return promises, so there is no rejection path to define.
- Invalid route callbacks (throwing synchronously when invoked) MUST NOT bubble to the editor. The editor wraps each invocation in a try/catch and logs via the injected logger; a failing callback MUST NOT corrupt timeline state or abort the current user action.
- Missing fields are treated as absent defaults, NEVER as errors. Consumers MUST tolerate an empty `{}` as a valid host context (the in-memory default).
- Feature-flag lookups for unknown keys return `undefined` (falsy). The editor MUST NOT throw or warn for unknown flag keys.

Current evidence:

- `DataProviderContext` currently carries `provider`, `timelineId`, `userId`, and `timelineName` in a runtime wrapper rather than a pure port contract (`reigh-app/src/tools/video-editor/contexts/DataProviderContext.tsx:4-33`).
- `videoEditorDefaults` and `useEditorSettings()` show that some current configuration is editor chrome, not document state (`reigh-app/src/tools/video-editor/settings/videoEditorDefaults.ts:3-12`, `reigh-app/src/tools/video-editor/settings/useEditorSettings.ts:5-31`).

In-memory default:

- Empty object.
- No routing callbacks, no persistence, neutral branding.

## 4. Timeline JSON Format Specification

### 4.1 Normative v1 shape

`@tbd/schema` defines `version: 1` as the first OSS contract:

```ts
const TimelineConfigV1 = z.object({
  version: z.literal(1),
  output: TimelineOutputV1,
  tracks: z.array(TimelineTrackV1),
  clips: z.array(TimelineClipV1),
  app: z.record(z.string(), z.unknown()).optional(),
});

const TimelineTrackV1 = z.object({
  id: z.string().min(1),
  kind: z.enum(['visual', 'audio']),
  label: z.string().min(1),
  scale: z.number().optional(),
  fit: z.enum(['cover', 'contain', 'manual']).optional(),
  opacity: z.number().optional(),
  blendMode: z.string().optional(),
  app: z.record(z.string(), z.unknown()).optional(),
});

const TimelineClipV1 = z.object({
  id: z.string().min(1),
  at: z.number().min(0),
  track: z.string().min(1),
  clipType: z.string().min(1),
  asset: z.string().optional(),
  from: z.number().optional(),
  to: z.number().optional(),
  speed: z.number().positive().optional(),
  hold: z.number().optional(),
  volume: z.number().optional(),
  x: z.number().optional(),
  y: z.number().optional(),
  width: z.number().optional(),
  height: z.number().optional(),
  cropTop: z.number().optional(),
  cropBottom: z.number().optional(),
  cropLeft: z.number().optional(),
  cropRight: z.number().optional(),
  opacity: z.number().optional(),
  text: z.record(z.string(), z.unknown()).optional(),
  entrance: z.record(z.string(), z.unknown()).optional(),
  exit: z.record(z.string(), z.unknown()).optional(),
  continuous: z.record(z.string(), z.unknown()).optional(),
  transition: z.record(z.string(), z.unknown()).optional(),
  effects: z.array(z.record(z.string(), z.unknown())).optional(),
  app: z.record(z.string(), z.unknown()).optional(),
});
```

This shape is derived from the current `TimelineConfig`, `TrackDefinition`, and `TimelineClip` types, but excludes reigh-only `pinnedShotGroups` from the core contract (`reigh-app/src/tools/video-editor/types/index.ts:51-186`).

### 4.2 Migration and JSON Schema export

Contract:

```ts
export function migrate(prev: unknown, fromVersion: number): TimelineConfig;
export function toJsonSchema(): JsonSchema7;
```

Rules:

- `migrate()` either returns a valid `TimelineConfig` for the current schema version or throws a validation error that includes the source version and the failing path.
- Every published schema version emits a JSON Schema artifact for docs, examples, and CLI validation.
- Migrations are pure and side-effect free.

### 4.3 Core fields vs app extension namespace

Locked decision:

- Whitelist exactly one extension key named `app` at the top level, clip level, and track level.
- `app` is `Record<string, unknown>`.
- Unknown keys outside `app` remain rejected.

This is intentionally narrow because the current serializer rejects unexpected keys at the top level, clip level, and track level (`reigh-app/src/tools/video-editor/lib/serialize.ts:98-122`). The OSS schema should extend that validator with a single escape hatch, not a fully permissive serializer.

Chosen rule, stated normatively:

```ts
Top-level allowed keys = core keys + optional "app"
Track allowed keys = core track keys + optional "app"
Clip allowed keys = core clip keys + optional "app"
All unknown non-app keys are invalid.
```

Rejected alternative:

- Do not loosen the serializer to preserve arbitrary unknown keys everywhere.
- Reason: it breaks contract clarity, weakens validation, and makes migrations impossible to reason about.

### 4.4 Forward-compatibility rule

- Unknown data must be preserved only inside `app`.
- Serializer round-trips must preserve the `app` subtree byte-for-byte where possible, or structurally equivalent if key ordering changes.
- Readers must ignore unknown namespaces inside `app`.
- Writers owned by a host may write `app['x-host']`, but core packages must never inspect host namespaces except for migration passthrough.

### 4.5 `pinnedShotGroups` migration

Current state:

- `TimelineConfig` currently includes `pinnedShotGroups?: PinnedShotGroup[]` as a top-level field (`reigh-app/src/tools/video-editor/types/index.ts:171-186`).
- `serializeForDisk()` validates and writes `pinnedShotGroups` as a top-level key (`reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`).

OSS v1 rule:

- `pinnedShotGroups` is removed from the core schema.
- Reigh-specific pinned shot-group data moves to `app['x-reigh'].pinnedShotGroups`.
- `x-reigh` is a namespace inside `app`, not a top-level `reigh` key.

Migration rule:

```ts
if (legacy.pinnedShotGroups) {
  next.app ??= {};
  const reighApp = typeof next.app['x-reigh'] === 'object' && next.app['x-reigh'] !== null
    ? next.app['x-reigh'] as Record<string, unknown>
    : {};
  reighApp.pinnedShotGroups = legacy.pinnedShotGroups;
  next.app['x-reigh'] = reighApp;
  delete legacy.pinnedShotGroups;
}
```

Round-trip invariant for legacy documents:

- Legacy documents that still contain top-level `pinnedShotGroups` must load successfully during the migration window.
- After load, the canonical in-memory representation becomes `app['x-reigh'].pinnedShotGroups`.
- Serializer writes only the new namespaced location once writers flip.

## 5. OSS Repository Structure

Proposed repo tree:

```text
video-editor-oss/
├─ package.json
├─ pnpm-workspace.yaml
├─ turbo.json
├─ tsconfig.base.json
├─ .changeset/
├─ packages/
│  ├─ schema/
│  ├─ engine/
│  ├─ editor/
│  └─ cli/
├─ examples/
│  ├─ local-json/
│  ├─ custom-backend/
│  └─ headless-render/
└─ apps/
   ├─ playground/
   └─ docs/
```

Rationale by entry:

| Path | Rationale |
| --- | --- |
| `packages/schema` | Publishable contract package with no React/Remotion runtime. |
| `packages/engine` | Shared rendering core for preview and CLI. |
| `packages/editor` | Editor shell, store, default ports, and extension slots. |
| `packages/cli` | Node-only render interface isolated from browser editor code. |
| `examples/local-json` | Lowest-friction demo: open/edit/save local JSON with in-memory defaults. |
| `examples/custom-backend` | Reference adapter example for implementers building their own `DataProvider`. |
| `examples/headless-render` | Minimal programmatic render example for Node services. |
| `apps/playground` | Vercel-deployable OSS demo that shows editor + preview + JSON import/export. |
| `apps/docs` | Documentation site for schema, ports, migration guide, and recipes. |
| `.changeset` | Versioning and release notes for multi-package publishing. |

CI pipeline:

1. `lint`
2. `typecheck`
3. `test`
4. `build`
5. preview docs/playground deployment
6. changesets release on main

### 5.1 Examples and playground

Examples to ship on day one:

- `examples/local-json`: standalone editor with in-memory defaults and file import/export; this is the lowest-friction adoption path.
- `examples/custom-backend`: demonstrates a custom `DataProvider` plus `AssetResolver` without any reigh code.
- `examples/headless-render`: validates that `@tbd/schema` plus `@tbd/engine` plus `@tbd/cli` can render without the React editor.

Playground brief:

- `apps/playground` should be Vercel-deployable.
- It should demonstrate JSON import/export, in-memory editing, preview rendering, and custom effect registration.
- Sample timelines should come from checked-in fixtures generated from `@tbd/schema` defaults plus a small set of hand-authored example timelines.

## 6. OSS Polish Checklist

### 6.1 License

Recommendation:

- Project license: `MIT`
- Add `REMOTION_LICENSE.md` and README notice for downstream obligations tied to Remotion's licensing model.

### 6.2 Remotion Licensing

This must be a dedicated subsection in the extracted repo, not a footnote.

As of 2026-04-19, the official Remotion site states:

- Free license for individuals and companies up to 3 people.
- Company license for collaborations and companies of 4+ people.
- Commercial use is allowed under both, but paid licensing applies when the team/usage crosses their thresholds.
- Enterprise terms exist for advanced needs.

Source: official Remotion pricing page on `remotion.dev`, lines describing free vs company tiers and enterprise upsell (`https://www.remotion.dev/`, captured at `turn1view0:99-178`).

What downstream adopters must verify before using the OSS repo:

- Their team size under Remotion's current terms.
- Whether they render in local-only, self-hosted, or cloud/serverless environments that change pricing tier obligations.
- Whether their use case is internal tooling, customer-facing automation, or a commercial video app.

README warning template:

```md
## Remotion licensing notice

This project depends on Remotion. The code in this repository is MIT-licensed, but your use of Remotion may require a separate Remotion commercial license depending on your team size and rendering setup. Verify the current terms at https://www.remotion.dev/ before production use.
```

### 6.3 README structure

Recommended README outline:

1. What this repo is
2. Who it is for
3. Package map
4. Quick start
5. Minimal JSON example
6. Ports and adapter overview
7. CLI render example
8. Remotion licensing notice
9. Status and roadmap

### 6.4 Docs site outline

Docs navigation:

- Getting started
- Timeline JSON schema
- Ports and adapters
- Engine and effects
- Reigh adapter walkthrough
- CLI guide
- Migration guide from in-tree editor
- FAQ and licensing

### 6.5 Release hygiene

- `changesets` for all package releases
- generated changelog per package
- canary tags for pre-release extraction milestones
- `strict: true`, `noImplicitAny: true`, zero exported `any`
- sourcemaps enabled for all packages
- ESM-first output with CJS fallback for packages that need it
- narrow `exports` maps only

Example `exports` map:

```json
{
  "name": "@tbd/editor",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js",
      "require": "./dist/index.cjs"
    },
    "./testing": {
      "types": "./dist/testing.d.ts",
      "import": "./dist/testing.js",
      "require": "./dist/testing.cjs"
    }
  }
}
```

## 7. CLI Renderer Specification

Command:

```bash
npx @tbd/cli render timeline.json out.mp4
```

Flags:

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--fps` | number | from JSON | Override output FPS. |
| `--width` | number | from JSON resolution | Override output width. |
| `--height` | number | from JSON resolution | Override output height. |
| `--codec` | enum | `h264` | Encoding target. |
| `--concurrency` | number | auto | Worker/render concurrency. |
| `--asset-root` | path | current working directory | Root for resolving relative asset paths. |
| `--quality` | number | encoder default | Quality/CRF preset surface. |
| `--log-level` | enum | `info` | Render logging verbosity. |

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Schema validation failed |
| `2` | Asset resolution failed |
| `3` | Render or encode failed |

CLI asset resolution:

- Default behavior resolves `http(s)` URLs unchanged.
- Relative asset paths resolve against `--asset-root`, defaulting to `process.cwd()`.
- If the caller provides a custom resolver module, the CLI uses it instead of the default `LocalAssetResolver`.

Programmatic API:

```ts
await renderTimeline({
  timelinePath: 'timeline.json',
  outputPath: 'out.mp4',
  assetRoot: process.cwd(),
  codec: 'h264',
});
```

## 8. Test Strategy

### 8.1 Package-level test ownership

| Existing test or logic source | Destination | Why |
| --- | --- | --- |
| `lib/render-bounds.test.ts` (`reigh-app/src/tools/video-editor/lib/render-bounds.test.ts:1-66`) | `@tbd/engine` | Render-space math belongs with the render engine. |
| `lib/timeline-scale.test.ts` (`reigh-app/src/tools/video-editor/lib/timeline-scale.test.ts:1-18`) | `@tbd/editor` | Zoom and timeline coordinate conversion are interaction concerns. |
| `lib/duplicate-clip.test.ts` (`reigh-app/src/tools/video-editor/lib/duplicate-clip.test.ts:1-69`) | `@tbd/editor` | Duplicate-clip behavior is editor mutation logic. |
| `lib/config-utils.test.ts` | split across `@tbd/schema` and `@tbd/engine` | Schema normalization assertions move to `schema`; resolution/time helpers move to `engine`. |
| `lib/mediaMetadata.test.ts` (`reigh-app/src/tools/video-editor/lib/mediaMetadata.test.ts:1-75`) | `@tbd/editor` | Upload/import metadata extraction remains editor-side. |
| `lib/interaction-state.test.ts` (`reigh-app/src/tools/video-editor/lib/interaction-state.test.ts:1-80`) | `@tbd/editor` | Drag/resize interaction state is editor runtime logic. |
| `lib/__tests__/editor-utils.test.ts` (`reigh-app/src/tools/video-editor/lib/__tests__/editor-utils.test.ts:1-80`) | `@tbd/editor` | Track mute, detach audio, and related editor helpers stay with editor mutations. |
| `hooks/__tests__/resolve-overlaps.test.ts` (`reigh-app/src/tools/video-editor/hooks/__tests__/resolve-overlaps.test.ts:1-80`) | `@tbd/editor` | Overlap resolution is timeline editing behavior. |
| `lib/snap-edges.ts` (`reigh-app/src/tools/video-editor/lib/snap-edges.ts:1-80`) | `@tbd/editor` with new direct tests | Snapping is timeline interaction math; add a dedicated unit test during move. |

### 8.2 Integration tests that stay in reigh-app

These tests validate host glue and should not move:

- `contexts/VideoEditorProvider.test.tsx`
- `hooks/useTimelinePersistence.test.tsx`
- `hooks/useTimelineCommit.test.tsx`
- `hooks/useTimelineHistory.test.ts`
- `components/PreviewPanel/RemotionPreview.test.tsx`
- `components/TimelineEditor/TimelineCanvas.test.tsx`

Reason: they exercise the adapter/bootstrap layer, runtime wiring, or app-only extension surfaces rather than pure OSS package behavior (`reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:114-405`, `reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts:22-220`, `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:68-170`).

### 8.3 New tests to add in the extracted repo

- Port contract tests for each in-memory default implementation
- Schema migration round-trip tests
- JSON Schema snapshot tests
- Effect registry registration ABI tests
- CLI validation and exit-code tests
- Example smoke tests for `examples/local-json` and `examples/headless-render`

### 8.4 Named verification gate for the pre-extraction `pinnedShotGroups` move

This is the required high-risk verification cluster before any package extraction begins:

- `lib/serialize.test.ts`
- `lib/migrate.test.ts`
- `lib/timeline-save-utils.test.ts`
- `lib/pinned-group-projection.test.ts`
- `hooks/useTimelineCommit.test.tsx`
- `hooks/useClipEditing.test.ts`
- `hooks/useClipDrag.test.tsx`
- `hooks/useTimelineTrackManagement.test.ts`

These tests gate the legacy-config round-trip, the dual-read shim, and the eventual writer flip because direct `config.pinnedShotGroups` reads still exist across runtime and tests (`reigh-app/src/tools/video-editor/lib/serialize.test.ts:56-195`, `reigh-app/src/tools/video-editor/lib/migrate.test.ts:6-133`, `reigh-app/src/tools/video-editor/lib/pinned-group-projection.ts:91-138`, `reigh-app/src/tools/video-editor/hooks/useTimelineCommit.ts:133-160`, `reigh-app/src/tools/video-editor/hooks/useTimelineTrackManagement.ts:107-170`, `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:434-438`, `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:625-631`).

## Part B. Reigh-App Integration

## 9. Forbidden in Core

The extracted packages must contain none of the following concepts:

| Forbidden concept | Why it is forbidden in OSS core | New home |
| --- | --- | --- |
| Shot groups | Product-specific grouping workflow | Reigh extension layer |
| `pinnedShotGroups` | Reigh-only persistence shape | `app['x-reigh'].pinnedShotGroups` plus reigh extension layer |
| Generation assets | Tied to reigh generation pipeline | Reigh `MediaPicker`/asset adapter |
| AgentChat | App-level assistant workflow | Reigh extension layer |
| Task-based export | Reigh task system concern | Reigh `Exporter` adapter |
| Supabase | Backend implementation detail | Reigh `DataProvider` adapter |
| Auth | Host identity concern | `HostContext` and host bootstrap |
| `projectId` | Host document scoping concern | Reigh `DataProvider` adapter |
| MediaLightbox | Host media UI | Reigh `MediaPicker` adapter and overlay slot |
| Project selection | Route/application state | Reigh page shell |
| Shots context | Reigh image/video workflow model | Reigh extension layer |
| `VideoGenerationModal` | Reigh generation UI | Reigh extension layer |
| Generation duplication | Reigh generation semantics | Reigh extension layer |
| Final-video availability | Reigh production state | Reigh extension layer |
| Stale-variant handling | Reigh-specific generation variant workflow | Reigh extension layer |
| Active-task tracking | Reigh task queue semantics | Reigh extension layer |

## 10. File and Folder Migration Table

### 10.1 Top-level folders

| Path | Decision | Destination | Notes |
| --- | --- | --- | --- |
| `compositions/` | `MOVE` | `@tbd/engine/src/compositions/` | Pure Remotion render layer (`reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:1-173`). |
| `components/` | `SPLIT` | `@tbd/editor/src/components/` and `reigh-app/src/tools/video-editor-host/` | Generic preview/editor UI moves; lightbox, AgentChat, shot-group, and route-aware shells stay host. |
| `contexts/` | `SPLIT` | `@tbd/editor/src/contexts/` and `reigh-app/src/tools/video-editor-host/contexts/` | Generic runtime/provider context moves; host bootstrap stays reigh. |
| `data/` | `SPLIT` | `@tbd/editor/src/data/` and `reigh-app/src/tools/video-editor-host/data/` | Interface moves; Supabase adapter stays host. |
| `effects/` | `SPLIT` | `@tbd/engine/src/effects/` and `@tbd/editor/src/effects/` | Registry and render-time ABI move to engine; editor gets convenience bindings only. |
| `hooks/` | `SPLIT` | `@tbd/editor/src/hooks/` and `reigh-app/src/tools/video-editor-host/hooks/` | Generic store, persistence, render, and mutation hooks move; app-specific hooks stay. |
| `lib/` | `SPLIT` | `@tbd/schema/src/`, `@tbd/engine/src/`, `@tbd/editor/src/`, and host | Serializer/defaults to schema; render helpers to engine; editor mutations to editor; host-only generation utilities stay. |
| `pages/` | `STAY` | `reigh-app/src/tools/video-editor-host/pages/` | Route and project-scoped shell stay in reigh. |
| `settings/` | `SPLIT` | `@tbd/editor/src/settings/` and host | OSS editor gets generic preferences; tool-registration defaults stay host. |
| `types/` | `SPLIT` | `@tbd/schema/src/types/`, `@tbd/editor/src/types/`, host | Core schema types move out; app-only types stay. |

### 10.2 Required explicit file classifications

| Path | Decision | Destination | Notes |
| --- | --- | --- | --- |
| `data/DataProvider.ts` | `SPLIT` | `@tbd/editor/src/data/DataProvider.ts` | Canonical interface anchor moves into editor package (`reigh-app/src/tools/video-editor/data/DataProvider.ts:53-71`). |
| `data/SupabaseDataProvider.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/data/SupabaseDataProvider.ts` | This is the reference reigh adapter and keeps `projectId`/`userId`/Supabase coupling (`reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts:43-279`). |
| `contexts/DataProviderContext.tsx` | `SPLIT` | generic runtime context to `@tbd/editor/src/contexts/EditorRuntimeContext.tsx`; host-only wrapper removed | Current wrapper carries `provider`, `timelineId`, `timelineName`, and `userId` (`reigh-app/src/tools/video-editor/contexts/DataProviderContext.tsx:4-33`). |
| `contexts/VideoEditorProvider.tsx` | `STAY` | `reigh-app/src/tools/video-editor-host/contexts/VideoEditorProvider.tsx` | This is the host bootstrap example; it wires MediaLightbox and AgentChat (`reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:74-112`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:367-405`). |
| `components/VideoEditorShell.tsx` | `SPLIT` | generic shell to `@tbd/editor/src/components/VideoEditorShell.tsx`; route/pane integration to host shell | Current shell mixes generic editor UI with routing, pane locks, and realtime dialog state (`reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:13-29`, `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx:67-120`). |
| `components/TimelineEditor/TimelineEditor.tsx` | `SPLIT` | generic orchestration to `@tbd/editor`; reigh overlays and dialogs to host extensions | Current file imports shots, project selection, active tasks, stale variants, final video hooks, and generation modal directly (`reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:10-50`). |
| `components/TimelineEditor/TimelineCanvas.tsx` | `MOVE` | `@tbd/editor/src/components/TimelineCanvas.tsx` | Core interaction surface moves; host-specific overlay/context-menu props become formal extension slots (`reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:68-122`). |
| `components/TimelineEditor/ShotGroupContextMenu.tsx` | `STAY` | `reigh-app/src/tools/video-editor-host/components/ShotGroupContextMenu.tsx` | Entirely shot-group workflow UI (`reigh-app/src/tools/video-editor/components/TimelineEditor/ShotGroupContextMenu.tsx:20-220`). |
| `components/TimelineEditor/ShotGroupOverlay.tsx` | `STAY` | `reigh-app/src/tools/video-editor-host/components/ShotGroupOverlay.tsx` | Encodes final-video, stale-variant, and active-task badges (`reigh-app/src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.tsx:18-25`, `reigh-app/src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.tsx:120-156`). |
| `components/PreviewPanel/RemotionPreview.tsx` | `MOVE` | `@tbd/editor/src/components/PreviewPanel/RemotionPreview.tsx` | Preview wrapper belongs with editor, not engine (`reigh-app/src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:11-143`). |
| `components/PropertiesPanel/PropertiesPanel.tsx` | `SPLIT` | generic inspector frame to `@tbd/editor`; stale-variant banner and host asset panel composition stay host | Current panel imports `useStaleVariants` directly (`reigh-app/src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:4-13`, `reigh-app/src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:55-59`). |
| `components/PropertiesPanel/ClipPanel.tsx` | `SPLIT` | clip inspector core to `@tbd/editor`; effect-resource acquisition to host adapter or editor plugin API | Current panel reads `userId` from runtime and loads effect resources with it (`reigh-app/src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:14-19`, `reigh-app/src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:170-172`). |
| `components/PropertiesPanel/BulkClipPanel.tsx` | `SPLIT` | bulk editor core to `@tbd/editor`; effect-resource loading abstracted | Same reason as `ClipPanel.tsx`; host identity currently leaks through effect-resource fetch (`reigh-app/src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:1-40`). |
| `components/PropertiesPanel/AssetPanel.tsx` | `SPLIT` | generic asset browser to `@tbd/editor`; generation-lightbox and generation-drop affordances stay host | Current panel imports `MediaLightbox` helpers and generation lookup (`reigh-app/src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:1-13`, `reigh-app/src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:89-124`, `reigh-app/src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:145-154`). |
| `components/CompactPreview.tsx` | `SPLIT` | generic compact preview to `@tbd/editor`; route buttons stay host | Current component uses `useNavigate()` and hardcoded editor routes (`reigh-app/src/tools/video-editor/components/CompactPreview.tsx:1-18`, `reigh-app/src/tools/video-editor/components/CompactPreview.tsx:20-26`, `reigh-app/src/tools/video-editor/components/CompactPreview.tsx:35-49`, `reigh-app/src/tools/video-editor/components/CompactPreview.tsx:62-65`). |
| `components/AgentChat/**` | `STAY` | `reigh-app/src/tools/video-editor-host/components/AgentChat/` | App-specific assistant UI (`reigh-app/src/tools/video-editor/components/AgentChat/AgentChat.tsx:7-18`, `reigh-app/src/tools/video-editor/components/AgentChat/AgentChat.tsx:145-220`). |
| `components/VideoEditorLightboxOverlay.tsx` | `STAY` | `reigh-app/src/tools/video-editor-host/components/VideoEditorLightboxOverlay.tsx` | Reigh MediaLightbox overlay only (`reigh-app/src/tools/video-editor/components/VideoEditorLightboxOverlay.tsx:1-39`). |
| `pages/VideoEditorPage.tsx` | `STAY` | `reigh-app/src/tools/video-editor-host/pages/VideoEditorPage.tsx` | Route-level project/auth shell and adapter assembly (`reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx:9-18`, `reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx:182-194`). |
| `hooks/useClientRender.ts` | `MOVE` | `@tbd/editor/src/hooks/useClientRender.ts` | Browser-side exporter implementation belongs with editor export UI (`reigh-app/src/tools/video-editor/hooks/useClientRender.ts:1-60`). |
| `hooks/useRenderState.ts` | `MOVE` | `@tbd/editor/src/hooks/useRenderState.ts` | Render state is editor chrome state, not host app state (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:446-487`). |
| `hooks/useTimelineState.ts` | `SPLIT` | generic bootstrap to `@tbd/editor`; host project/generation bindings moved out | Current bootstrap binds provider, project selection, asset ops, and external drop workflows (`reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:413-838`). |
| `hooks/timelineStore.ts` | `MOVE` | `@tbd/editor/src/hooks/timelineStore.ts` | This is the core editor store contract (`reigh-app/src/tools/video-editor/hooks/timelineStore.ts:34-50`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:302-550`). |
| `hooks/useTimelineHistory.ts` | `MOVE` | `@tbd/editor/src/hooks/useTimelineHistory.ts` | Generic checkpoint/undo behavior over optional provider methods (`reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:137-166`, `reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:319-343`). |
| `hooks/useAssetOperations.ts` | `MOVE` | `@tbd/editor/src/hooks/useAssetOperations.ts` | Generic wrapper over optional `uploadAsset` and `registerAsset` methods (`reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts:7-59`). |
| `hooks/useTimelinePersistence.ts` | `MOVE` | `@tbd/editor/src/hooks/useTimelinePersistence.ts` | Generic optimistic save/conflict logic over `DataProvider` (`reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts:22-220`). |
| `hooks/useTimelineRealtime.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useTimelineRealtime.ts` | Current implementation is app-level `realtimeEventProcessor` glue, not a provider contract (`reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts:29-43`). |
| `hooks/useTimelineQueries.ts` | `MOVE` | `@tbd/editor/src/hooks/useTimelineQueries.ts` | Generic provider-backed query helper (`reigh-app/src/tools/video-editor/hooks/useTimelineQueries.ts:1-25`). |
| `hooks/useTimelinesList.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useTimelinesList.ts` | Supabase list/create/rename/delete helper until `listTimelines()` and `deleteTimeline()` ports are adopted (`reigh-app/src/tools/video-editor/hooks/useTimelinesList.ts:8-98`). |
| `hooks/useActiveTaskClips.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useActiveTaskClips.ts` | Project-scoped task queue integration (`reigh-app/src/tools/video-editor/hooks/useActiveTaskClips.ts:125-261`). |
| `hooks/useFinalVideoAvailable.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useFinalVideoAvailable.ts` | Reigh final-video state (`reigh-app/src/tools/video-editor/hooks/useFinalVideoAvailable.ts:13-30`). |
| `hooks/useAgentSession.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useAgentSession.ts` | Agent session persistence and chat bridge are app-only. |
| `hooks/useVideoEditorLightboxNavigation.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/hooks/useVideoEditorLightboxNavigation.ts` | MediaLightbox navigation remains host-owned. |
| `hooks/useTimelineSync.ts` | `MOVE` | `@tbd/editor/src/hooks/useTimelineSync.ts` | Generic preview/timeline synchronization helper (`reigh-app/src/tools/video-editor/hooks/useTimelineSync.ts:1-60`). |
| `hooks/usePollSync.ts` | `MOVE` | `@tbd/editor/src/hooks/usePollSync.ts` | Generic polling-based conflict reconciliation helper (`reigh-app/src/tools/video-editor/hooks/usePollSync.ts:1-60`). |
| `lib/serialize.ts` | `MOVE` | `@tbd/schema/src/serialize.ts` | This is the serializer and validation contract; apply the `app` whitelist here (`reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`). |
| `lib/config-utils.ts` | `SPLIT` | schema migration/normalization to `@tbd/schema`; resolution helpers to `@tbd/engine` | Current file mixes config math and async resolution (`reigh-app/src/tools/video-editor/lib/config-utils.ts:17-233`). |
| `lib/defaults.ts` | `MOVE` | `@tbd/schema/src/defaults.ts` | Default schema seed (`reigh-app/src/tools/video-editor/lib/defaults.ts:3-35`). |
| `lib/render-bounds.ts` | `MOVE` | `@tbd/engine/src/render-bounds.ts` | Render-space math. |
| `lib/timeline-scale.ts` | `MOVE` | `@tbd/editor/src/timeline-scale.ts` | Timeline interaction scale math. |
| `lib/snap-edges.ts` | `MOVE` | `@tbd/editor/src/snap-edges.ts` | Editor drag/resize snapping (`reigh-app/src/tools/video-editor/lib/snap-edges.ts:1-80`). |
| `lib/resolve-overlaps.ts` | `MOVE` | `@tbd/editor/src/resolve-overlaps.ts` | Editor overlap resolution logic. |
| `lib/duplicate-clip.ts` | `MOVE` | `@tbd/editor/src/duplicate-clip.ts` | Editor mutation helper (`reigh-app/src/tools/video-editor/lib/duplicate-clip.test.ts:1-69`). |
| `lib/mediaMetadata.ts` | `MOVE` | `@tbd/editor/src/mediaMetadata.ts` | Upload/import metadata extraction (`reigh-app/src/tools/video-editor/lib/mediaMetadata.test.ts:1-75`). |
| `lib/interaction-state.ts` | `MOVE` | `@tbd/editor/src/interaction-state.ts` | Editor gesture/save coordination (`reigh-app/src/tools/video-editor/lib/interaction-state.test.ts:1-80`). |
| `lib/timeline-data.ts` | `SPLIT` | document hydration/build helpers to `@tbd/editor`; schema-only pieces to `@tbd/schema` | Current file mixes `TimelineData`, `rowsToConfig`, provider loading, and transcript/profile helpers (`reigh-app/src/tools/video-editor/lib/timeline-data.ts:61-75`, `reigh-app/src/tools/video-editor/lib/timeline-data.ts:206-260`, `reigh-app/src/tools/video-editor/lib/timeline-data.ts:388-410`). |
| `lib/external-drop-utils.ts` | `SPLIT` | generic file-drop helpers to `@tbd/editor`; generation-specific adapters to host | Current file blends generic drop handling with generation semantics (`reigh-app/src/tools/video-editor/lib/external-drop-utils.ts:1-60`). |
| `lib/pinned-group-projection.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/lib/pinned-group-projection.ts` | Entirely reigh shot-group projection logic (`reigh-app/src/tools/video-editor/lib/pinned-group-projection.ts:91-138`). |
| `settings/videoEditorDefaults.ts` | `SPLIT` | generic editor defaults to `@tbd/editor`; tool registration defaults remain host | Current file is tool-settings specific (`reigh-app/src/tools/video-editor/settings/videoEditorDefaults.ts:3-12`). |
| `settings/useEditorSettings.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/settings/useEditorSettings.ts` | Current implementation is localStorage/UI settings glue (`reigh-app/src/tools/video-editor/settings/useEditorSettings.ts:5-31`). |
| `types/index.ts` | `SPLIT` | core schema types to `@tbd/schema`; resolved/render types to `@tbd/engine`; editor-only view types to `@tbd/editor`; `pinnedShotGroups` removed from core | Current file mixes all three concerns (`reigh-app/src/tools/video-editor/types/index.ts:51-216`). |
| `types/timeline-canvas.ts` | `MOVE` | `@tbd/editor/src/types/timeline-canvas.ts` | Timeline UI types (`reigh-app/src/tools/video-editor/types/timeline-canvas.ts:1-60`). |
| `types/agent-session.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/types/agent-session.ts` | Agent session types are app-only (`reigh-app/src/tools/video-editor/types/agent-session.ts:3-50`). |
| `registration.test.ts` | `STAY` | `reigh-app/src/tools/video-editor-host/registration.test.ts` | Reigh tool registration seam remains in app (`reigh-app/src/tools/video-editor/registration.test.ts:10-18`). |

## 11. Host Touchpoint Mapping

| Touchpoint | Current location | New home | What the extracted package exposes |
| --- | --- | --- | --- |
| Supabase persistence | `reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts:43-279` | Reigh host adapter | `DataProvider` port |
| Auth | `reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx:183-194` | Reigh bootstrap | `HostContext.userId` and adapter construction |
| `projectId` | `reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx:183-194`; `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:512`, `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts:579-593` | Reigh bootstrap and adapter | `DataProvider` scope and `listTimelines({ projectId })` |
| MediaLightbox | `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:5-8`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:367-381` | Reigh `MediaPicker` adapter | `MediaPicker` port and overlay slot |
| AgentChat | `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:74-112`; `reigh-app/src/tools/video-editor/components/AgentChat/AgentChat.tsx:145-220` | Reigh extension layer | Store selectors and editor commands |
| Task-based export | `reigh-app/src/tools/video-editor/hooks/useActiveTaskClips.ts:125-261`; `reigh-app/src/tools/video-editor/hooks/useFinalVideoAvailable.ts:13-30` | Reigh `Exporter` adapter | `Exporter` port plus render-status store slice |
| Shot groups | `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:434-438`, `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:500-546` | Reigh extension layer | `renderOverlay`, `contextMenuItems`, store selectors |
| `pinnedShotGroups` | `reigh-app/src/tools/video-editor/types/index.ts:171-186`; `reigh-app/src/tools/video-editor/lib/serialize.ts:98-139` | `app['x-reigh'].pinnedShotGroups` in reigh namespace | `app` namespace passthrough in schema |
| Generation assets | `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:142-209`; `reigh-app/src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:89-124` | Reigh `MediaPicker` and asset adapter | Asset insert commands and media slot |
| Project selection | `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:15`; `reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx:20-26` | Reigh route/page layer | No core coupling; host chooses timeline scope |
| Shots context | `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:16`; `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:6`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:132` | Reigh extension layer | Extension selectors and `app` namespace |
| `VideoGenerationModal` | `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:18` | Reigh extension layer | Command hooks and panel/overlay slots |
| Generation duplication | `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:41-42` | Reigh extension layer | Clip duplicate command interception hook |
| Final-video availability | `reigh-app/src/tools/video-editor/hooks/useFinalVideoAvailable.ts:13-30` | Reigh extension layer | Overlay slot and store subscription |
| Stale-variant handling | `reigh-app/src/tools/video-editor/hooks/useStaleVariants.ts:24-29`, `reigh-app/src/tools/video-editor/hooks/useStaleVariants.ts:117-142`, `reigh-app/src/tools/video-editor/hooks/useStaleVariants.ts:169-219` | Reigh extension layer | Inspector slot and asset-update commands |
| Active-task tracking | `reigh-app/src/tools/video-editor/hooks/useActiveTaskClips.ts:145-261` | Reigh extension layer | Overlay slot and clip-to-asset mapping selectors |
| Checkpoints | `reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:137-166`, `reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts:319-343` | Core editor + provider optional methods | Optional `saveCheckpoint` / `loadCheckpoints` |
| Asset upload/register | `reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts:14-39` | Core editor, optional provider methods | `uploadAsset?` and `registerAsset?` |
| `resolveAssetUrl` | `reigh-app/src/tools/video-editor/data/DataProvider.ts:64`; `reigh-app/src/tools/video-editor/lib/timeline-data.ts:388-410` | `AssetResolver` plus compatibility on `DataProvider` | `AssetResolver.resolveAssetUrl()` |
| Waveform | `reigh-app/src/tools/video-editor/data/DataProvider.ts:70` | Optional asset metadata adapter | `loadWaveform?` on `DataProvider` or `AssetResolver` |
| Profile | `reigh-app/src/tools/video-editor/data/DataProvider.ts:71`; `reigh-app/src/tools/video-editor/lib/timeline-data.ts:405-410` | Optional asset metadata adapter | `loadAssetProfile?` / `loadProfile?` |
| Realtime subscription | `reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts:29-43` | Optional provider capability | `DataProvider.subscribe?()`; explicitly a new design addition |

## 12. Reference Supabase Adapter and Host Extensions

### 12.1 Reference adapter placement

Locked naming and placement:

- Canonical port interface: `data/DataProvider.ts`
- Reference reigh adapter: `data/SupabaseDataProvider.ts`
- Bootstrap example: `contexts/VideoEditorProvider.tsx`

Evidence:

- `SupabaseDataProvider` encapsulates timeline load/save, checkpoint persistence, registry loading, asset upload/register, and URL resolution (`reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts:43-279`).
- `VideoEditorProvider` wraps runtime context, creates store wiring, and mounts app-only extensions such as AgentChatBridge and MediaLightbox (`reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:74-112`, `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx:367-405`).

### 12.2 Hooks are layered helpers, not the adapter

These hooks remain helpers around the port; they are not the backend contract:

- `useTimelineQueries()` is a React Query wrapper over `DataProvider` (`reigh-app/src/tools/video-editor/hooks/useTimelineQueries.ts:6-25`).
- `useTimelineRealtime()` is app-level invalidation glue over `realtimeEventProcessor` (`reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts:29-43`).
- `useTimelinePersistence()` is optimistic save/conflict logic over `DataProvider` (`reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts:22-220`).

### 12.3 Recommended host layout after extraction

```text
reigh-app/src/tools/video-editor-host/
├─ data/
│  └─ SupabaseDataProvider.ts
├─ contexts/
│  └─ VideoEditorProvider.tsx
├─ hooks/
│  ├─ useTimelinesList.ts
│  ├─ useTimelineRealtime.ts
│  ├─ useActiveTaskClips.ts
│  ├─ useFinalVideoAvailable.ts
│  ├─ useAgentSession.ts
│  └─ useVideoEditorLightboxNavigation.ts
├─ components/
│  ├─ AgentChat/
│  ├─ ShotGroupOverlay.tsx
│  ├─ ShotGroupContextMenu.tsx
│  └─ VideoEditorLightboxOverlay.tsx
└─ pages/
   └─ VideoEditorPage.tsx
```

### 12.4 Host extension pattern

The extracted editor should expose extension slots rather than direct reigh imports:

- `renderOverlay?: (ctx) => ReactNode`
- `panels?: Array<EditorPanelExtension>`
- `contextMenuItems?: (ctx) => EditorContextMenuItem[]`
- `onDocumentEvent?: (event) => void`

This matches what `TimelineCanvas` already approximates via shot-group and action callbacks (`reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:83-122`) and what the store already exposes via `data`, `ops`, `chrome`, and `playback` slices (`reigh-app/src/tools/video-editor/hooks/timelineStore.ts:34-50`, `reigh-app/src/tools/video-editor/hooks/timelineStore.ts:523-550`).

## 13. Migration Sequence and Sync Strategy

### 13.1 Before/after import shapes

Example 1, route page:

```ts
// Before
import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider';
import { VideoEditorProvider } from '@/tools/video-editor/contexts/VideoEditorProvider';
import { VideoEditorShell } from '@/tools/video-editor/components/VideoEditorShell';

// After
import { EditorProvider, TimelineEditorShell } from '@tbd/editor';
import { SupabaseDataProvider } from '@/tools/video-editor-host/data/SupabaseDataProvider';
import { VideoEditorProvider } from '@/tools/video-editor-host/contexts/VideoEditorProvider';
```

Example 2, host adapter:

```ts
// Before
import { useTimelineQueries } from '@/tools/video-editor/hooks/useTimelineQueries';
import { useTimelineRealtime } from '@/tools/video-editor/hooks/useTimelineRealtime';

// After
import type { DataProvider } from '@tbd/editor';
import { useTimelineRealtime } from '@/tools/video-editor-host/hooks/useTimelineRealtime';
```

Example 3, reigh extension component:

```ts
// Before
import { useTimelineEditorData, useTimelineEditorOps } from '@/tools/video-editor/hooks/timelineStore';

// After
import { useTimelineEditorData, useTimelineEditorOps } from '@tbd/editor';
```

Example 4, pure logic test:

```ts
// Before
import { buildDuplicateClipEdit } from '@/tools/video-editor/lib/duplicate-clip';

// After
import { buildDuplicateClipEdit } from '@tbd/editor/testing';
```

### 13.2 Numbered order of operations

Execution scope for this plan: steps 1 through 5 execute atomically in a single code-mode megaplan run on branch `megaplan/m1b-m1c-stores`. The resulting commits leave the editor extracted into workspace packages under `@tbd/*`, with reigh-app consuming them via `workspace:*`. Steps 6 and 7 (publishing to a standalone OSS repository and flipping reigh to an npm dependency) are post-plan manual follow-ups that require external actions (repo creation, npm credentials, history split) outside a sandboxed run. They remain documented here as the intended end state.

1. Land the pre-extraction serializer and `pinnedShotGroups` compatibility step in reigh first.
   Rollback: keep the dual-read helpers and continue reading the legacy top-level field.

   Required five-stage recipe:

   - Add `getPinnedShotGroups(config)` and `setPinnedShotGroups(config, value)` helpers that dual-read from both `config.pinnedShotGroups` and `config.app?.['x-reigh']?.pinnedShotGroups`, preferring the new location when both exist.
   - Update all callers to use those helpers. Minimum required caller set:
     - `reigh-app/src/tools/video-editor/hooks/useTimelineCommit.ts`
     - `reigh-app/src/tools/video-editor/lib/pinned-group-projection.ts`
     - `reigh-app/src/tools/video-editor/hooks/useShotGroups.ts`
     - `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx`
     - `reigh-app/src/tools/video-editor/hooks/useTimelineTrackManagement.ts`
     - `reigh-app/src/tools/video-editor/lib/serialize.ts`
   - Flip writers so serializer and runtime updates emit only `app['x-reigh'].pinnedShotGroups`.
   - Add a one-shot load migration in `lib/serialize.ts` / `lib/config-utils.ts` that rewrites legacy inputs on read.
   - Update tests. Minimum required test set:
     - `reigh-app/src/tools/video-editor/lib/serialize.test.ts`
     - `reigh-app/src/tools/video-editor/lib/migrate.test.ts`
     - `reigh-app/src/tools/video-editor/lib/timeline-save-utils.test.ts`
     - `reigh-app/src/tools/video-editor/hooks/useTimelineCommit.test.tsx`
     - `reigh-app/src/tools/video-editor/hooks/useClipEditing.test.ts`
     - `reigh-app/src/tools/video-editor/hooks/useClipDrag.test.tsx`
     - `reigh-app/src/tools/video-editor/hooks/useTimelineTrackManagement.test.ts`
   - Remove the legacy top-level field from `TimelineConfig` and the serializer validator once the dual-read helpers and one-shot load migration are wired and the test set above is green; no deferral period in a single-run execution.

   Evidence that this compatibility phase is mandatory:

   - direct reads in `TimelineEditor.tsx` (`reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:434-438`, `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx:625-631`)
   - projection logic in `lib/pinned-group-projection.ts` (`reigh-app/src/tools/video-editor/lib/pinned-group-projection.ts:91-138`)
   - commit and serialization flow in `useTimelineCommit.ts` and `serialize.ts` (`reigh-app/src/tools/video-editor/hooks/useTimelineCommit.ts:133-160`, `reigh-app/src/tools/video-editor/hooks/useTimelineCommit.ts:226-245`, `reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`)

2. Extract `@tbd/schema` in place first.
   Rollback: revert path aliases and keep using the in-tree schema copy.

   - Move `defaults.ts`, schema types, serializer, migration helpers.
   - Keep reigh importing the package through workspace alias before publishing.

3. Extract `@tbd/engine`.
   Rollback: restore in-tree composition imports if packaging causes preview regressions.

   - Move Remotion compositions and engine effect registry.
   - Make editor preview import the engine package immediately to establish one render path.

4. Extract `@tbd/editor` while reigh still consumes local workspace packages.
   Rollback: keep the old in-tree shell and store behind a feature flag or import alias.

   - Move generic store, shell, canvas, preview, persistence, and editor mutation helpers.
   - Replace direct host imports with extension slots and ports.

5. Flip reigh to `workspace:*` or local `file:` consumption and validate in app.
   Rollback: revert package resolution to the in-tree copy.

   - Validate route page, bootstrap provider, MediaLightbox, AgentChat, and Supabase adapter behavior.

6. Post-plan (manual): publish `v0.1.0` of the OSS repo.
   Out of scope for the single megaplan run; requires external repo creation, history subtree split, and npm/GitHub credentials.
   Rollback: keep reigh pinned to `workspace:*` until package issues are fixed.

7. Post-plan (manual): flip reigh from local link to npm dependency.
   Out of scope for the single megaplan run; runs after step 6 once `v0.1.0` is published.
   Rollback: pin back to local `file:` or workspace dependency while iterating.

### 13.3 Sync strategy options during transition

| Option | Pros | Cons | Recommendation |
| --- | --- | --- | --- |
| Monorepo then subtree split | Lowest drift, fastest validation, keeps refactors atomic | Requires later history extraction | `Recommended` |
| Git submodule from day one | Clear repo boundary early | Friction for local iteration, brittle DX | Not recommended for first extraction phase |
| `file:` link to sibling repo | Good for local package validation | Easy drift between repos before tests mature | Good only after in-place package extraction |
| Dual-commit to both repos | No history rewrite later | High operator cost, easy to desync | Avoid |

Recommendation:

- This megaplan run executes the first two bullets: extract into workspace packages, and stabilize contracts with reigh consuming local packages via `workspace:*`.
- The third and fourth bullets (subtree split into a standalone repo, then reigh switching from `workspace:*` to an npm dependency) are post-plan manual follow-ups once the in-repo extraction is validated.

## Part C. Open Questions and Risks

## 14. Open Questions and Risks

### 14.1 Remotion company-license implications

Recommendation:

- Treat Remotion licensing as a first-class adoption risk in the README and docs.
- Do not imply that the OSS package license alone is sufficient for commercial adopters.
- Re-verify Remotion pricing at every major release because the pricing and team-size threshold are not stable facts.

### 14.2 Pre-1.0 schema stability commitment

Recommendation:

- Even before `1.0`, treat schema versions as strict compatibility boundaries.
- Within a schema version, allow additive fields only.
- Any breaking schema change requires:
  - a new schema version
  - a migration function
  - changelog entry
  - legacy round-trip tests

Deprecation policy:

- Keep readers for the previous schema version through at least one minor release after introducing a new version.
- Allow writers to emit only the newest schema version once migration tests pass.

### 14.3 Repo-sync strategy during transition

Open question:

- Is there any organizational reason to skip the recommended monorepo-first phase and start in a separate repo immediately?

Current recommendation:

- No. Start monorepo-first, then split after contracts stabilize.

### 14.4 Engine renderer abstraction

Recommendation:

- Keep the v1 engine explicitly Remotion-specific.
- Revisit only if a second renderer becomes a concrete requirement.

Why:

- The current engine candidates are already Remotion-native.
- A renderer-agnostic interface now would force abstraction around composition structure, timeline effects, and media semantics before there is a real second backend.

Trigger for revisit:

- A second real rendering backend is required by an adopter and can demonstrate a stable common denominator.

### 14.5 Other risks

- Dependency drift: reigh and the OSS repo must stay aligned on Remotion, React, and Query versions during the transition (`reigh-app/package.json:45-72`).
- Effect registry ABI stability: once host-defined effects are supported publicly, registration shape changes become a compatibility risk (`reigh-app/src/tools/video-editor/effects/DynamicEffectRegistry.ts:12-120`).
- Post-move coverage gaps: reigh-specific adapters can lose test coverage if integration tests are moved out prematurely.
- Serializer regressions: the `app` whitelist must not regress to arbitrary unknown-key preservation or accidental key dropping (`reigh-app/src/tools/video-editor/lib/serialize.ts:98-139`).
- Optional-method compatibility: downstream adopters need clear feature detection and graceful UI degradation when methods like `uploadAsset` or `loadWaveform` are absent.
- Example drift: examples and playgrounds tend to rot unless CI runs them.

## Appendix A. Glossary

| Term | Definition |
| --- | --- |
| `TimelineConfig` | The persisted, versioned JSON document that describes tracks, clips, output settings, and namespaced app extensions. |
| Port | A narrow interface exposed by the OSS packages for host-specific behavior, such as persistence or media picking. |
| Adapter | Host-owned code that implements a port, such as `SupabaseDataProvider`. |
| Extension | Host-owned UI or behavior layered onto the editor through slots, store subscriptions, or app namespaces. |
| `HostContext` | Non-document UI/runtime configuration provided by the embedding app, such as `userId`, locale, routes, or branding. |

## Appendix B. Reigh-App File References

| File | Why it informs this design |
| --- | --- |
| `reigh-app/src/tools/video-editor/data/DataProvider.ts` | Canonical current persistence contract and error semantics. |
| `reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts` | Reference host adapter for persistence, registry, uploads, and URL resolution. |
| `reigh-app/src/tools/video-editor/contexts/DataProviderContext.tsx` | Current runtime wrapper carrying provider, timeline id, user id, and name. |
| `reigh-app/src/tools/video-editor/contexts/VideoEditorProvider.tsx` | Bootstrap example and host-only MediaLightbox/AgentChat integration. |
| `reigh-app/src/tools/video-editor/types/index.ts` | Current core types and `pinnedShotGroups` leakage point. |
| `reigh-app/src/tools/video-editor/types/timeline-canvas.ts` | Editor-only timeline canvas types. |
| `reigh-app/src/tools/video-editor/types/agent-session.ts` | Host-only types that must not move. |
| `reigh-app/src/tools/video-editor/lib/serialize.ts` | Current serializer validation and writer behavior. |
| `reigh-app/src/tools/video-editor/lib/defaults.ts` | Default config seed. |
| `reigh-app/src/tools/video-editor/lib/config-utils.ts` | Mixed schema/runtime utility file to split. |
| `reigh-app/src/tools/video-editor/lib/timeline-data.ts` | Hydration, row conversion, and profile-loading helpers. |
| `reigh-app/src/tools/video-editor/lib/pinned-group-projection.ts` | Current direct `pinnedShotGroups` caller that requires the dual-read shim. |
| `reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx` | Core render root candidate for `@tbd/engine`. |
| `reigh-app/src/tools/video-editor/compositions/VisualClip.tsx` | Clip rendering candidate for `@tbd/engine`. |
| `reigh-app/src/tools/video-editor/compositions/AudioTrack.tsx` | Audio rendering candidate for `@tbd/engine`. |
| `reigh-app/src/tools/video-editor/compositions/EffectLayerSequence.tsx` | Render-time effect integration point. |
| `reigh-app/src/tools/video-editor/effects/DynamicEffectRegistry.ts` | Current effect registry ABI. |
| `reigh-app/src/tools/video-editor/hooks/timelineStore.ts` | Current provider/store pattern that the extracted editor should preserve. |
| `reigh-app/src/tools/video-editor/hooks/useTimelineState.ts` | Current bootstrap that mixes generic editor logic and host coupling. |
| `reigh-app/src/tools/video-editor/hooks/useTimelineQueries.ts` | Layered provider query helper, not the adapter. |
| `reigh-app/src/tools/video-editor/hooks/useTimelinePersistence.ts` | Generic save/conflict helper over `DataProvider`. |
| `reigh-app/src/tools/video-editor/hooks/useTimelineRealtime.ts` | Current app-level realtime invalidation path and evidence that `subscribe()` is new design. |
| `reigh-app/src/tools/video-editor/hooks/useTimelineHistory.ts` | Checkpoint integration over optional provider methods. |
| `reigh-app/src/tools/video-editor/hooks/useAssetOperations.ts` | Upload/register helper over optional provider methods. |
| `reigh-app/src/tools/video-editor/hooks/useTimelinesList.ts` | Current list/create/delete flow outside `DataProvider`. |
| `reigh-app/src/tools/video-editor/hooks/useActiveTaskClips.ts` | Reigh task coupling. |
| `reigh-app/src/tools/video-editor/hooks/useFinalVideoAvailable.ts` | Reigh final-video workflow coupling. |
| `reigh-app/src/tools/video-editor/hooks/useStaleVariants.ts` | Reigh stale-variant workflow coupling. |
| `reigh-app/src/tools/video-editor/components/VideoEditorShell.tsx` | Current shell composition and propless editor usage. |
| `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | Primary host-coupling hotspot. |
| `reigh-app/src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx` | Existing slot-like extension seam. |
| `reigh-app/src/tools/video-editor/components/TimelineEditor/ShotGroupContextMenu.tsx` | Reigh-only shot-group UI. |
| `reigh-app/src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.tsx` | Reigh-only shot-group overlays and task badges. |
| `reigh-app/src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx` | Generic inspector mixed with host stale-variant integration. |
| `reigh-app/src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx` | Generic clip inspector currently leaking host identity. |
| `reigh-app/src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx` | Asset panel mixed with generation-lightbox behavior. |
| `reigh-app/src/tools/video-editor/components/CompactPreview.tsx` | Compact preview mixed with route navigation. |
| `reigh-app/src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx` | Editor preview wrapper around engine render. |
| `reigh-app/src/tools/video-editor/pages/VideoEditorPage.tsx` | Route-level auth/project shell and adapter construction. |
| `reigh-app/src/tools/video-editor/registration.test.ts` | Reigh registration seam that stays in app. |
| `reigh-app/package.json` | Current dependency versions to align during extraction. |
