# Video Editor Sprint 2 Ports, Adapters, and Command Facade Checklist

## Sprint 1 start point

Sprint 2 starts from the canonical boundary established in [docs/video_editor_canonical_timeline_sprint1.md](./video_editor_canonical_timeline_sprint1.md).

Hard rule:

- `src/tools/video-editor/lib/timeline-domain.ts` stays authoritative for validation, repair, canonicalization, duration math, and serialization.
- Sprint 2 command and planner work must call the Sprint 1 helpers instead of introducing parallel timeline interpretation logic.

## Scope locks for Sprint 2

### Public surface

Sprint 2 exposes an early public command facade for non-gesture entrypoints only.

Required facade surface:

- `addClip`
- `updateClip`
- `moveClip`
- `trimClip`
- `splitClip`
- `deleteClip`
- `addTrack`
- `moveTrack`
- `registerAsset`
- `setClipParams`

Out of scope for the recommended public API in Sprint 2:

- raw `rows` / `meta` / `clipOrder` mutation
- raw `applyEdit`
- gesture-heavy internals such as `useExternalDrop` and pinned-group drag flows

### Mounted editor compatibility boundary

This boundary is load-bearing and must not change in Sprint 2:

- Outside a mounted editor, the safe command hook must stay nullable: `useTimelineCommandsSafe() === null`.
- Inside a mounted editor, the seeded store bootstrap in `src/tools/video-editor/hooks/useTimelineState.ts` remains synchronous.
- `src/tools/video-editor/contexts/VideoEditorProvider.tsx` must keep the later `syncOpsSlice` augmentation ordering intact.
- `src/domains/media-lightbox/hooks/useAddToVideoEditor.ts` remains the canary consumer for mounted-vs-staged behavior; Sprint 2 must preserve its current fallback choice boundary.

### Command-facade caller set

Sprint 2 migrates these non-gesture callers onto the shared command/planner surface:

- `src/domains/media-lightbox/hooks/useAddToVideoEditor.ts`
- `src/tools/video-editor/contexts/VideoEditorProvider.tsx`
- `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx`
- `src/tools/video-editor/hooks/useAddVariantAsGeneration.ts`
- `src/tools/video-editor/hooks/useSwitchToFinalVideo.ts`

These flows stay internal in Sprint 2, but must reuse the shared planners and explicit duration contract:

- `src/tools/video-editor/hooks/useExternalDrop.ts`
- `src/tools/video-editor/hooks/usePinnedShotGroups.ts`

## Runtime governance rules

Planned stable host/adapter names for Sprint 2:

- `DataProvider`
- `AssetResolver`
- `ProjectHost`
- `ShotsHost`
- `MediaLightboxHost`
- `AgentChatHost`
- `ToastHost`
- `TelemetryHost`
- `AuthHost`

These names are the runtime source of truth and must stay aligned with `VIDEO_EDITOR_HOST_PORT_NAMES` in `src/tools/video-editor/runtime/ports.ts`.

Sprint 2 host-governance work should treat these imports as the watched Reigh-coupling surface under `src/tools/video-editor/`:

```text
@/integrations/supabase
@/shared/contexts/AuthContext
@/shared/contexts/ProjectContext
@/shared/contexts/ShotsContext
@/shared/contexts/AgentChatContext
@/domains/media-lightbox
@/shared/components/ui/runtime/sonner
@/shared/components/ui/toast
@/shared/realtime/RealtimeEventProcessor
@/shared/state/selectionStore
@/shared/state/currentAttachmentSet
@/shared/state/panesStore
@/shared/hooks/settings/useToolSettings
@/shared/hooks/shots/useShotNavigation
@/shared/hooks/shotCreation/useShotCreation
@/tools/travel-between-images/hooks/video/useShotFinalVideos
@/integrations/supabase/functions/invokeSupabaseEdgeFunction
```

Governance policy:

- New direct imports from the watched surface are not allowed unless they land behind a named port/adapter or are added to the explicit allowlist below.
- Existing direct imports listed in the allowlist are tolerated only for the reason stated here; the allowlist must shrink or stay flat during Sprint 2.
- `src/tools/video-editor/hooks/useAddVariantAsGeneration.ts` is explicitly not allowlisted. It is a required migration target for the shared command/planner surface.
- Mounted command consumers must stay on the documented non-gesture facade (`useTimelineCommands()` / `useTimelineCommandsSafe()`); gesture-heavy flows remain internal even when they reuse the same duration helpers.

## Authoritative host inventory

The list below is the source of truth for every live runtime Reigh-coupled module currently under `src/tools/video-editor/`. Type-only bridges that still import the watched surface are also listed so the grep-based governance check stays complete.

### Port-backed migration targets

| Module | Current live Reigh coupling | Sprint 2 classification | Notes |
| --- | --- | --- | --- |
| `src/tools/video-editor/data/SupabaseDataProvider.ts` | Direct Supabase timeline and asset persistence | `DataProvider` adapter | Keep the public `DataProvider` shape mechanically compatible. |
| `src/tools/video-editor/runtime/ports.ts` | Type-level dependency on `useShotFinalVideos()` output | Runtime host contract surface | Keep the stable port names centralized here; extract a shared final-video type later if this bridge survives Sprint 2. |
| `src/tools/video-editor/adapters/reigh/useReighTimelinesList.ts` | Direct Supabase timeline list CRUD | Concrete Reigh timeline catalog adapter | The watched imports now live here; exported hook wrappers should remain thin compatibility shims. |
| `src/tools/video-editor/hooks/useTimelinesList.ts` | Compatibility wrapper over the Reigh timeline catalog adapter | Stable import-path wrapper | Keep existing caller imports stable while the direct host coupling stays concentrated in the adapter. |
| `src/tools/video-editor/adapters/reigh/useReighEffectsCatalog.ts` | Direct Supabase custom-effect CRUD | Concrete Reigh effect catalog adapter | Same class of host dependency as timeline list CRUD; not part of the command facade. |
| `src/tools/video-editor/hooks/useEffects.ts` | Compatibility wrapper over the Reigh effect catalog adapter | Stable import-path wrapper | Keep existing caller imports stable while the direct host coupling stays concentrated in the adapter. |
| `src/tools/video-editor/hooks/useAgentSession.ts` | Supabase table reads, auth lookup, realtime channel, edge-function invocation | `AgentChatHost` adapter | Owns session transport; should stop being imported as a raw Reigh hook by editor UI. |
| `src/tools/video-editor/hooks/useActiveTaskClips.ts` | `ProjectContext` plus direct Supabase task reads | `ProjectHost` + Reigh task-status adapter | Keeps active-task badges tied to the selected project without embedding project/supabase reads in timeline UI. |
| `src/tools/video-editor/hooks/useFinalVideoAvailable.ts` | `ProjectContext` plus `useShotFinalVideos()` from travel-between-images | `ProjectHost` + `ShotsHost` adapter | This is the final-video availability boundary for timeline/editor consumers. |
| `src/tools/video-editor/adapters/reigh/useReighShotsHost.ts` | `ShotsContext` plus `useShotFinalVideos()` | Concrete Reigh `ShotsHost` adapter | Owns the actual shots/final-video host assembly that timeline consumers should read through. |
| `src/tools/video-editor/hooks/useSelectedMediaClips.ts` | `ShotsContext` | `ShotsHost` | Selected attachment summaries should resolve shot names/membership through a host, not a raw shared context. |
| `src/tools/video-editor/hooks/useTimelineClipsForAttachments.ts` | `ShotsContext` | `ShotsHost` | Same host concern as `useSelectedMediaClips.ts`; used for timeline attachment export. |
| `src/tools/video-editor/hooks/useAddVariantAsGeneration.ts` | `ProjectContext`, direct Supabase query, toast, variant-promotion hook | `ProjectHost` + `ToastHost` + Reigh generation-promotion adapter | Mandatory Sprint 2 migration target. Must reuse Sprint 1 helpers and move to the shared command/planner path. |
| `src/tools/video-editor/hooks/useStaleVariants.ts` | Direct Supabase reads, realtime processor, toast | `ToastHost` + Reigh variant-status adapter | Toasting and live variant drift checks need explicit host boundaries. |
| `src/tools/video-editor/hooks/useSwitchToFinalVideo.ts` | Toast-backed final-video replacement flow | `ToastHost` command-facade consumer | Mandatory Sprint 2 migration target alongside duplicate-generation and add-variant promotion. |
| `src/tools/video-editor/hooks/useAssetManagement.ts` | Toast plus direct Reigh generation/upload repository calls | `AssetResolver` + Reigh asset-ingest adapter + `ToastHost` | This is the main asset-registration/drop seam that Sprint 2 must split into pure planners plus imperative adapters. |
| `src/tools/video-editor/hooks/useTimelineState.ts` | `ProjectContext` plus editor runtime bootstrap | `ProjectHost` consumer and bootstrap boundary | Preserve seeded store bootstrap behavior while routing project/runtime reads through explicit hosts. |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | `ShotsContext`, `AgentChatContext`, `MediaLightbox`, toast-backed staged add flow | Runtime composition root for `ShotsHost`, `AgentChatHost`, `MediaLightboxHost`, `ToastHost` | This file is a hard compatibility boundary because it owns pending-add draining and post-mount ops augmentation. |
| `src/tools/video-editor/pages/VideoEditorPage.tsx` | `AuthContext`, `ProjectContext`, `useToolSettings`, toast, `SupabaseDataProvider` construction | Runtime composition root for `AuthHost`, `ProjectHost`, `ToastHost`, `DataProvider` adapter | Page wiring stays Reigh-specific, but host construction should be concentrated here instead of leaking through the tree. |
| `src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx` | `MediaLightbox` | `MediaLightboxHost` | Double-click/open behavior should be hosted explicitly. |
| `src/tools/video-editor/components/AgentChat/AgentChat.tsx` | `MediaLightbox`, `AgentChatContext`, app-wide attachment/pane state | `AgentChatHost` + `MediaLightboxHost` with extra allowlist entries below | Main chat surface; host work cannot ignore its lightbox and composer bridges. |
| `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | `ProjectContext`, `ShotsContext`, toast, shot creation/navigation helpers | `ProjectHost`, `ShotsHost`, `ToastHost` with extra allowlist entries below | Command-facade migration target for duplicate-generation, variant-promotion, and final-video actions. |
| `src/tools/video-editor/components/CustomEffectEditor.tsx` | Toast + effect catalog hook | `ToastHost` + Reigh effect catalog adapter | Keep effect save/delete UI from reaching raw toast/effect persistence directly. |
| `src/tools/video-editor/components/EffectCreatorPanel.tsx` | Toast + Supabase edge-function invocation | `ToastHost` + Reigh effect-generation adapter | Effect generation remains Reigh-specific, but the network boundary should be named. |
| `src/tools/video-editor/components/SequenceCreator/sequenceGenerationService.ts` | Supabase edge-function invocation | Reigh sequence-generation adapter | Service boundary should be named even if the sequence UI stays editor-local. |
| `src/tools/video-editor/adapters/reigh/generationLookup.ts` | Direct Supabase generation lookups | Concrete Reigh generation lookup adapter | Used by lightbox and generation-backed UI; watched imports now live here. |
| `src/tools/video-editor/lib/generation-utils.ts` | Compatibility wrapper over the Reigh generation lookup adapter | Stable import-path wrapper | Keep existing caller imports stable while the direct host coupling stays concentrated in the adapter. |
| `src/tools/video-editor/adapters/reigh/variantPromotionLookup.ts` | Direct Supabase variant lookups | Concrete Reigh variant-promotion adapter | Shared promotion queries should stop being embedded directly inside command consumers. |
| `src/tools/video-editor/adapters/reigh/staleVariantRepository.ts` | Direct Supabase stale-variant reads | Concrete Reigh variant-status adapter | Keeps the stale-variant transport in one place even while the UI flow stays editor-local. |

### Explicit direct-import allowlist for Sprint 2

These entries are allowed to remain direct for Sprint 2, but only for the stated reason.

| Module | Direct coupling kept in Sprint 2 | Why it is allowlisted |
| --- | --- | --- |
| `src/tools/video-editor/hooks/useExternalDrop.ts` | `ShotsContext` and final-video availability hook | Gesture-heavy internal drop path. It should reuse shared planners/duration helpers, but it is not part of the recommended public command surface this sprint. |
| `src/tools/video-editor/hooks/useClipDrag.ts` | `selectionStore` | Internal gesture selection bridge. Converting selection ownership is a separate track; do not expand this surface. |
| `src/tools/video-editor/hooks/useClipDrag.helpers.ts` | `selectionStore` | Same reason as `useClipDrag.ts`; internal drag/selection bridge only. |
| `src/tools/video-editor/hooks/useMarqueeSelect.ts` | `selectionStore` | Internal gesture selection bridge only. |
| `src/tools/video-editor/hooks/useTimelineCommit.ts` | `selectionStore` | Undo/history/save pipeline stays in place for Sprint 2; command work must delegate through it instead of replacing it. |
| `src/tools/video-editor/hooks/useTimelineSelection.ts` | `selectionStore` | Multi-select store ownership is out of scope for this sprint; preserve behavior. |
| `src/tools/video-editor/hooks/clip-editing/types.ts` | `selectionStore` type import | Type-only selection bridge | Keep existing clip-editing type contracts stable; no runtime selection-ownership change is implied by this file. |
| `src/tools/video-editor/hooks/useTimelineState.types.ts` | `selectionStore` type import | Type-only selection bridge | Keep the mounted editor context/store type surface stable while runtime ownership stays elsewhere. |
| `src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx` | `selectionStore` and render-budget instrumentation | Internal preview-selection bridge plus deferred `TelemetryHost` work; not a new public host boundary in Sprint 2. |
| `src/tools/video-editor/components/VideoEditorShell.tsx` | `panesStore`, `selectionStore`, typed app events, home navigation | App-shell integration remains local to the mounted Reigh editor shell this sprint; typed app events stay on the deferred `TelemetryHost` allowlist. |
| `src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx` | `currentAttachmentSet`, `selectionStore`, toast | Reuses the app-level attachment composer strip; keep behavior stable while the command facade lands. |
| `src/tools/video-editor/components/AgentChat/AgentChat.tsx` | `panesStore`, `selectionStore`, `currentAttachmentSet` | Keep the existing app-level attachment/pane bridge stable while `AgentChatHost` is introduced. |
| `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | `useShotCreation`, `useShotNavigation`, `VideoGenerationModal` | Shot-creation/navigation UI remains editor-internal this sprint; do not broaden the command facade to cover it. |
| `src/tools/video-editor/hooks/useVideoEditorLightboxNavigation.ts` | `@/domains/media-lightbox` type import | Type-only `MediaLightboxHost` bridge | Navigation props stay typed against the shared lightbox contract even though runtime access is routed through the host. |
| `src/tools/video-editor/lib/video-editor-path.ts` | `useToolSettings` cache shape | URL restore helper is editor-shell glue, not part of the command/runtime host split. |
| `src/tools/video-editor/hooks/useTimelineRealtime.ts` | `RealtimeEventProcessor` | Keep current invalidation behavior while the broader realtime host story stays unchanged. |
| `src/tools/video-editor/hooks/useClientRender.ts` | toast | Browser render feedback is editor-local UI glue; safe to defer behind a host until after the command surface lands. |
| `src/tools/video-editor/hooks/useClipEditing.ts` | toast | Local edit feedback can stay direct while the command facade is introduced above the existing mutation internals. |

## Sprint 2 execution notes

- Do not add any new public API that exposes raw timeline internals as the preferred mutation path.
- Keep `useExternalDrop` and pinned-group drag flows internal even if they are updated to reuse new planners.
- Preserve current visible editor behavior while concentrating host imports behind adapters.
- When in doubt, prefer a small adapter around an existing Reigh implementation over widening `DataProvider`.

## Batch 1 done when

- This checklist remains the source of truth for Sprint 2 scope and host governance.
- `src/tools/video-editor/hooks/useAddVariantAsGeneration.ts` is explicitly named as a migration target and is not hidden in a generic bucket.
- The mounted safe-hook/bootstrap boundary is written down as a compatibility contract.
- Every live runtime Reigh-coupled module under `src/tools/video-editor/` is classified either as a port-backed migration target or as an explicit allowlist entry.
