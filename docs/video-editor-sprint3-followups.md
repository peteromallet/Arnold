# Video Editor Sprint 3 Host Boundary Inventory

Sprint 3 is introducing a headless editor core plus a Reigh adapter shell. This note records the current host-coupled surfaces before extraction so the split work stays honest about what is actually app-owned today.

## Ownership Inventory

| File | Surface | Sprint 3 owner | Notes |
| --- | --- | --- | --- |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | `DataProviderWrapper`, `useTimelineState()`, `TimelineStoreProvider`, editor-op assembly | Core-owned | This is the provider/bootstrap surface that should move behind `CoreProvider` without changing synchronous store seeding or mutable adapter behavior. |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | `useSearchParams()` staged-add drain, `readPendingAdds()` / `writePendingAdds()`, URL query cleanup | Adapter-owned | This is Reigh route behavior tied to staged add-to-editor flow and should stay outside the headless core. |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | `useShots()`, `useVideoEditorLightboxNavigation()`, inline `MediaLightbox`, `VideoEditorLightboxOverlay` | Adapter-owned | Shot-aware lightbox behavior is Reigh-specific in Sprint 3. |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | `useAgentChatRegistry()`, timeline clip attachment registration into app chat state | Adapter-owned | This is the app bridge into the TasksPane-owned chat workflow. |
| `src/tools/video-editor/contexts/VideoEditorProvider.tsx` | Effect bootstrap via `useEffects()`, `useEffectRegistry()`, `useEffectResources()` | Core-owned | Not a Reigh app-context dependency, but still currently colocated in the adapter-heavy provider file. |
| `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | Timeline canvas composition, drag/drop sensors, marquee, clip movement, selection, row/track editing | Core-owned | This is the main extraction target for `TimelineEditorCore`. |
| `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | `useProjectSelectionContext()`, `useShots()`, `useShotCreation()`, `useShotNavigation()` | Adapter-owned | Project identity, shot creation, and shot navigation are Reigh host concerns. |
| `src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx` | `VideoGenerationModal`, `useActiveTaskClips()`, `useFinalVideoAvailable()`, `useStaleVariants()`, `useAddVariantAsGeneration()`, `useSwitchToFinalVideo()` | Adapter-owned | These flows are tied to Reigh task/shot/final-video workflow and should move out of core paths. |
| `src/tools/video-editor/components/TimelineEditorShellCore.tsx` | Realtime conflict handling, diagnostics boot, keyboard shortcuts, preview portals, playback/chrome wiring, keyboard delete mutation assembly | Core-owned | These runtime shell responsibilities now live in the headless shell core. |
| `src/tools/video-editor/components/ReighVideoEditorShell.tsx` | `useLocation()`, `useNavigate()`, `useHomeNavigation()`, `usePanesStore()`, route-aware condensed/locked-pane behavior | Adapter-owned | Router and pane policy stay in the Reigh shell adapter. |
| `src/tools/video-editor/components/VideoEditorShell.tsx` | Compatibility export to the Reigh shell adapter | Adapter-owned | Sprint 3 keeps the existing import surface stable while the live app rewiring lands in T7. |
| `src/tools/video-editor/components/CompactPreview.tsx` | `CompactPreviewCore`, `RemotionPreview`, timeline scrubber, playback refs | Core-owned | The preview widget itself is portable once route actions are injected. |
| `src/tools/video-editor/components/CompactPreview.tsx` | Reigh `useNavigate()` wrapper for open-editor affordances | Adapter-owned | The route CTA stays outside the core preview surface. |
| `src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx` | Asset listing, drag payload registration, upload callback plumbing | Core-owned | This panel logic is portable once source-preview host wiring is removed. |
| `src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx` | Source-generation open action routed through editor ops | Core-owned | T6 removes the inline `MediaLightbox` dependency; the adapter-owned provider lightbox opens through `onDoubleClickAsset()`. |
| `src/tools/video-editor/components/AgentChat/AgentChat.tsx` | Session UI, voice controls, attachment lightbox, panes-store engagement state, `AgentChatContext` action registry | Adapter-owned | Sprint 3 keeps `AgentChat.tsx` out of the headless core. |
| `src/features/tasks/components/TasksPane/TasksPane.tsx` | Action pane layout, project/task/shot controller wiring, centralized `MediaLightbox` | Adapter-owned | This file is part of the Reigh adapter surface, not editor core. |
| `src/features/tasks/components/TasksPane/TasksPane.tsx` | Split-button wiring via `useAgentChatActions()` and `AgentChatPanel` mount | Adapter-owned | This preserves the live app chat affordances and the null-before-mount contract. |
| `src/app/providers/AppProviders.tsx` | `ProjectProvider`, `ShotsProvider`, `IncomingTasksProvider`, `AgentChatProvider`, `PanesStoreBootstrapBoundary` composition | Adapter-owned | These app-level providers define the Reigh host environment around the editor. |
| `src/app/providers/AppProviders.tsx` | `SelectionStoreBoundary` persistence for `lastAffectedShotId` | Adapter-owned | This is project-scoped app persistence and remains outside the core. |

## Explicit Sprint 3 Tradeoff

`AgentChatPanel` stays rendered from `src/features/tasks/components/TasksPane/TasksPane.tsx` in Sprint 3.

That means:

- `TasksPane` remains app-owned and becomes part of the Reigh adapter surface rather than the editor core.
- `AppProviders` remains app-owned because it still owns `AgentChatProvider`, `ProjectProvider`, `ShotsProvider`, and the related pane/selection bootstrap.
- The editor core must integrate with chat through adapter bridges only; it should not import `TasksPane`, `AppProviders`, or app chat providers directly.

## Deferred Or Residual Host Dependencies

- `useTimelineState.ts`, `useExternalDrop.ts`, `useActiveTaskClips.ts`, `useFinalVideoAvailable.ts`, `useAddVariantAsGeneration.ts`, `useSelectedMediaClips.ts`, and `useTimelineClipsForAttachments.ts` now read project identity, shots, and final-video availability through `VideoEditorCorePorts` rather than importing `ProjectContext` or `ShotsContext` directly. The current `VideoEditorProvider.tsx` explicitly supplies those adapter values until T5/T7 replace the live composition with dedicated Reigh adapter components.
- `TimelineEditorShellCore.tsx` now owns the runtime shell responsibilities, while `ReighVideoEditorShell.tsx` still owns Reigh route and pane behavior. T7 should switch the live route composition to call the adapter explicitly instead of relying on the compatibility export in `VideoEditorShell.tsx`.
- `VideoEditorProvider.tsx` still owns adapter lightbox, staged-add draining, and AgentChat bridge behavior around `CoreProvider`. That is intentional for Sprint 3 and should stay explicit rather than moving back into core hooks.
- `AgentChat.tsx` remains adapter-owned in Sprint 3. The shell split should not pull its panes-store or lightbox behavior back into the headless core.

## Import Governance

- `scripts/quality/check-video-editor-core-imports.ts` now enforces the Sprint 3 host-import boundary for `src/tools/video-editor/core/**/*`, `src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx`, and `src/tools/video-editor/components/TimelineEditorShellCore.tsx`.
- Those files must not import `ProjectContext`, `ShotsContext`, `AgentChatContext`, `react-router-dom`, or `@/domains/media-lightbox` directly.
- Mixed-ownership files such as `src/tools/video-editor/components/CompactPreview.tsx`, `src/tools/video-editor/components/ReighTimelineEditor.tsx`, `src/tools/video-editor/components/ReighVideoEditorShell.tsx`, and `src/tools/video-editor/contexts/VideoEditorProvider.tsx` are intentionally outside this check because they still contain explicit Reigh adapter behavior in Sprint 3.
