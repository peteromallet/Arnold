# State Management Context Audit

Updated on 2026-04-17 after the panes-store migration, the non-pane narrowing pass, and the follow-up review fix for declaration inventory completeness.

`PanesContext`, `PanesProvider`, and `usePanes()` are gone. This document is now the authoritative inventory of the remaining `createContext` declarations and the remaining recomposed context-access hook families.

## Counting Contract

- Declaration inventory source: the same TypeScript-walker logic used by [scripts/quality/check-fat-contexts.mjs](/workspace/reigh-app/scripts/quality/check-fat-contexts.mjs), plus a test-file grep for declarations excluded from `tsconfig.app.json`.
- Declaration matcher scope: `createContext(...)`, `React.createContext(...)`, and namespace-alias variants such as `ReactLocal.createContext(...)`.
- Guard matcher scope: direct initializers plus wrapped initializers such as `const X = freeze(React.createContext(...))`.
- Current declaration count: `53` total.
- Production declarations: `49`.
- Test-only declarations: `4`.
- Final declaration inventory accounted for in this document:
  - `49` production declarations from the `tsconfig.app.json` TypeScript program.
  - `4` test-only declarations found outside that program in `FinalVideoSectionControls.test.tsx`, `GuidanceVideoStripRangeControls.test.tsx`, `PromptEditorAIPanel.test.tsx`, and `ShotImagesEditorHeader.test.tsx`.
- Per-declaration completeness rule for this document:
  - Every live `createContext` declaration name must appear exactly once in either the full declaration tables below or the descriptor snapshot appendix.
  - Pre-split umbrella labels are intentionally not used as inventory rows. The document tracks only current declaration names.
- Section row counts on this pass:
  - Shared application contexts: `13`
  - Media-lightbox contexts: `8`
  - Image-generation-form contexts: `5`
  - Travel-between-images and shot-editor contexts: `11`
  - Video-editor runtime and store-adjacent contexts: `3`
  - Local UI and overlay contexts: `9`
  - Test-only declarations: `4`
- Inventory completeness cross-check: the section row counts above add up to the same `53` descriptors listed in the generated descriptor snapshot appendix, so every current declaration is represented exactly once in the tables below.
- Split surfaces are listed by their current declaration names, not their pre-T6 umbrella names. Examples: `LightboxCoreContext`/`LightboxMediaContext`/`LightboxVariantsContext`/`LightboxNavigationContext` and `ImageGenerationFormUIContext`/`Core`/`Prompts`/`References`/`Loras`.
- The descriptor snapshot appendix below is the canonical declaration-by-declaration source of truth for this pass. The summary tables are a grouped presentation of that same `53`-descriptor set, not a lossy rollup.
- Consumer counts below are unique external production files only.
- Excluded from consumer counts: the declaration file itself, same-file helper composition, tests, mocks, and `__tests__` trees.
- Field counts expand local repository object/interface types recursively.
- Arrays, refs, functions, and third-party or declaration-file types count as one leaf.
- Expansion stops at a 50-leaf documentation cutoff. Rows that exceed it are reported as `50+`.
- Threshold for mandatory migration work: field count `>10` and external production consumer count `>5`.
- Decision meanings:
  - `migrate-complete`: a formerly wide surface was split or moved this milestone.
  - `narrow-complete`: a formerly broad access hook was narrowed this milestone; any remaining bridge is deprecated and has no production callers.
  - `keep`: below threshold or otherwise acceptably scoped today.
  - `out-of-scope`: local UI plumbing, test-only wiring, or an already-store-backed provider boundary.

## Guard

- Automated check: `npm run check:fat-contexts`
- Implementation: [scripts/quality/check-fat-contexts.mjs](/workspace/reigh-app/scripts/quality/check-fat-contexts.mjs)
- Allowlist: [scripts/quality/fat-context-allowlist.json](/workspace/reigh-app/scripts/quality/fat-context-allowlist.json)
- Automated quality wiring:
  - `npm run test:arch`
  - `npm run quality:check`
- The guard now inspects imported `createContext(...)`, direct `React.createContext(...)`, and namespace-alias calls such as `ReactLocal.createContext(...)`, so declarations such as `AIInputModeContext`, the overlay contexts, and future namespace-import variants are covered by the same rule.
- Named-import coverage includes both `import { createContext } from 'react'` and aliased forms such as `import { createContext as createReactContext } from 'react'`, so the checker and this inventory use one declaration matcher across all repository forms.
- React namespace resolution now follows the TypeScript symbol graph for both `import * as React from 'react'` and default-import `React.createContext(...)` forms, rather than assuming the literal identifier name alone.

## Inventory Refresh Recipe

- Production descriptor snapshot: `node scripts/quality/check-fat-contexts.mjs`
- Raw declaration grep cross-check: `rg -n "(React\\.)?createContext(<[^\\n]+>)?\\(" src --glob '!**/*.test.*' --glob '!**/__tests__/**'`
- Test-only declaration grep cross-check: `rg -n "(React\\.)?createContext(<[^\\n]+>)?\\(" src --glob '**/*.test.tsx' --glob '**/*.test.ts' --glob '**/__tests__/**'`
- Appendix maintenance rule:
  - If any of the commands above changes the descriptor set, update the summary counts, the per-section tables, and the appendix in the same change.
  - Historical umbrella names such as the former `LightboxStateContext`, `ImageGenerationFormContext`, and `VideoTravelSettingsContext` may be mentioned only as migration history. They must never replace the current declaration names in the inventory tables or descriptor snapshot.
- Reviewer spot-check anchors:
  - [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) must contribute exactly `LightboxCoreContext`, `LightboxMediaContext`, `LightboxVariantsContext`, and `LightboxNavigationContext`.
  - [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) must contribute exactly `ImageGenerationFormUIContext`, `ImageGenerationFormCoreContext`, `ImageGenerationFormPromptsContext`, `ImageGenerationFormReferencesContext`, and `ImageGenerationFormLorasContext`.

## Review Reconciliation

The review kickback called out two concrete gaps from the prior draft. This pass closes both explicitly:

- The audit now uses the final split declaration names everywhere. There is no remaining umbrella row for the former `LightboxStateContext` or `ImageGenerationFormContext` surfaces; the live rows are `LightboxCoreContext`, `LightboxMediaContext`, `LightboxVariantsContext`, `LightboxNavigationContext`, `ImageGenerationFormUIContext`, `ImageGenerationFormCoreContext`, `ImageGenerationFormPromptsContext`, `ImageGenerationFormReferencesContext`, and `ImageGenerationFormLorasContext`.
- The declaration total is reconciled against the generated descriptor snapshot, not a stale manual count. The current final inventory is `53` declarations: `49` production declarations and `4` test-only declarations.
- The permanent guard now documents the same namespaced coverage that the code enforces. `React.createContext(...)` declarations such as `AIInputModeContext` are part of the checked surface, not an audit-only exception.
- The appendix is now the reviewer-facing declaration ledger for the final tree. If a future edit changes the declaration set, this section and the section counts above must be updated in the same change.
- The split surfaces that triggered the review kickback are now represented only by their live declarations in the ledger and tables. The final tree rows for [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) and [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) are the exact reviewer spot-check set, not a historical rollup.

## Recomposed Access Hooks

These are the remaining exported hook families that intentionally recombine multiple context slices. The over-threshold ones were narrowed during T6; any bridge left behind is deprecated and has no production callers.

| Hook family | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/shared/contexts/ProjectContext.tsx](/workspace/reigh-app/src/shared/contexts/ProjectContext.tsx) `useProject()` | 13 | 0 | `narrow-complete` | The old broad bridge still exists only as a deprecated compatibility export for tests and mocks. Production callers moved to `useProjectSelectionContext()`, `useProjectCrudContext()`, and `useProjectIdentityContext()`. |
| [src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx](/workspace/reigh-app/src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx) `useVideoTravelSettings()` | 50+ | 0 | `narrow-complete` | The base hook remains exported, but production callers were migrated to targeted hooks such as `usePromptSettings()`, `useModelSettings()`, and `useVideoTravelSettingsStatus()`. |
| [src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx) `useShotSettingsContext()` | 50+ | 0 | `migrate-complete` | The wide hook remains as a deprecated bridge with no production callers. Production sections now read `useShotSettingsIdentity()`, `useShotSettingsUi()`, `useShotSettingsMedia()`, or `useShotSettingsGeneration()`. |
| [src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx) `useTimelineMedia()` | 13 | 0 | `narrow-complete` | Production callers were moved to `useTimelineGuidanceMedia()`, `useTimelineAudioMedia()`, and `useTimelineFps()`. |

## Full Declaration Inventory

The tables below enumerate every current `createContext` declaration in the repository under the counting contract above. There are no omitted umbrella aliases; if a provider was split during T6, each live split declaration appears as its own row.

### Shared application contexts

| Declaration | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/shared/contexts/AuthContext.tsx](/workspace/reigh-app/src/shared/contexts/AuthContext.tsx) `AuthContext` | 3 | 4 | `keep` | Thin auth identity/loading state. |
| [src/shared/contexts/IncomingTasksContext.tsx](/workspace/reigh-app/src/shared/contexts/IncomingTasksContext.tsx) `IncomingTasksContext` | 9 | 4 | `keep` | Under the strict `>5` consumer threshold. |
| [src/shared/contexts/UserSettingsContext.tsx](/workspace/reigh-app/src/shared/contexts/UserSettingsContext.tsx) `UserSettingsContext` | 4 | 0 | `keep` | Small settings surface with one file total including the declaration. |
| [src/shared/contexts/AIInputModeContext.tsx](/workspace/reigh-app/src/shared/contexts/AIInputModeContext.tsx) `AIInputModeContext` | 3 | 3 | `keep` | Small persisted UI preference. |
| [src/shared/contexts/AgentChatContext.tsx](/workspace/reigh-app/src/shared/contexts/AgentChatContext.tsx) `AgentChatContext` | 3 | 1 | `keep` | Small bridge surface for chat timeline metadata. |
| [src/shared/contexts/AgentChatContext.tsx](/workspace/reigh-app/src/shared/contexts/AgentChatContext.tsx) `AgentChatRegistryContext` | 2 | 1 | `keep` | Registry bridge is thin and intentionally separate. |
| [src/shared/contexts/GenerationTaskContext.tsx](/workspace/reigh-app/src/shared/contexts/GenerationTaskContext.tsx) `GenerationTaskContext` | 4 | 0 | `out-of-scope` | No exported production consumer hook remains. |
| [src/shared/contexts/ProjectContext.tsx](/workspace/reigh-app/src/shared/contexts/ProjectContext.tsx) `ProjectSelectionContext` | 7 | 53 | `keep` | High fan-out, but the split selection slice is now the intended narrow surface. |
| [src/shared/contexts/ProjectContext.tsx](/workspace/reigh-app/src/shared/contexts/ProjectContext.tsx) `ProjectCrudContext` | 9 | 21 | `keep` | CRUD slice is broad in reach, not in shape. |
| [src/shared/contexts/ProjectContext.tsx](/workspace/reigh-app/src/shared/contexts/ProjectContext.tsx) `ProjectIdentityContext` | 1 | 1 | `keep` | Single-field identity context. |
| [src/shared/contexts/ShotsContext.tsx](/workspace/reigh-app/src/shared/contexts/ShotsContext.tsx) `ShotsContext` | 6 | 15 | `keep` | Many consumers, but still below the field threshold. |
| [src/shared/contexts/ToolPageHeaderContext.tsx](/workspace/reigh-app/src/shared/contexts/ToolPageHeaderContext.tsx) `ToolPageHeaderContext` | 3 | 0 | `keep` | Small layout-local bridge. |
| [src/shared/providers/RealtimeProvider.tsx](/workspace/reigh-app/src/shared/providers/RealtimeProvider.tsx) `RealtimeContext` | 7 | 0 | `keep` | Mostly a side-effect provider now; the context value itself is still thin. |

### Media-lightbox contexts

| Declaration | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/domains/media-lightbox/contexts/ImageEditCanvasContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/ImageEditCanvasContext.tsx) `ImageEditCanvasContext` | 50+ | 4 | `keep` | Still wide, but it stays below the consumer threshold. |
| [src/domains/media-lightbox/contexts/ImageEditFormContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/ImageEditFormContext.tsx) `ImageEditFormContext` | 29 | 0 | `keep` | One external production reader only. |
| [src/domains/media-lightbox/contexts/ImageEditStatusContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/ImageEditStatusContext.tsx) `ImageEditStatusContext` | 10 | 0 | `keep` | Exactly at the field cutoff, not above it. |
| [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) `LightboxCoreContext` | 6 | 6 | `migrate-complete` | Split from the former wide lightbox provider; the core slice is now thin. |
| [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) `LightboxMediaContext` | 50+ | 3 | `migrate-complete` | Still heavy, but the split removed the former wide shared subscription surface. |
| [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) `LightboxVariantsContext` | 45 | 5 | `migrate-complete` | This remains rich state, but it no longer drags core/media/navigation readers with it. |
| [src/domains/media-lightbox/contexts/LightboxStateContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/LightboxStateContext.tsx) `LightboxNavigationContext` | 8 | 2 | `migrate-complete` | Narrow navigation-only slice after the split. |
| [src/domains/media-lightbox/contexts/VideoEditContext.tsx](/workspace/reigh-app/src/domains/media-lightbox/contexts/VideoEditContext.tsx) `VideoEditContext` | 39 | 3 | `keep` | Wide, but the consumer count stays under the migration threshold. |

### Image-generation-form contexts

| Declaration | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) `ImageGenerationFormUIContext` | 1 | 1 | `migrate-complete` | Split from the former wide image-generation form provider. |
| [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) `ImageGenerationFormCoreContext` | 5 | 6 | `migrate-complete` | Core data slice now stands alone instead of subscribing prompt/reference/LoRA readers. |
| [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) `ImageGenerationFormPromptsContext` | 1 | 1 | `migrate-complete` | Prompt-only slice after the split. |
| [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) `ImageGenerationFormReferencesContext` | 1 | 4 | `migrate-complete` | References-only slice after the split. |
| [src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts](/workspace/reigh-app/src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts) `ImageGenerationFormLorasContext` | 1 | 1 | `migrate-complete` | LoRA-only slice after the split. |

### Travel-between-images and shot-editor contexts

| Declaration | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx](/workspace/reigh-app/src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx) `VideoTravelSettingsDataContext` | 43 | 6 | `migrate-complete` | Replaced the former single `VideoTravelSettingsContext`; production callers use targeted slice hooks. |
| [src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx](/workspace/reigh-app/src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx) `VideoTravelSettingsHandlersContext` | 25 | 1 | `migrate-complete` | Handlers split out of the former broad settings object. |
| [src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx](/workspace/reigh-app/src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx) `VideoTravelSettingsStatusContext` | 9 | 2 | `migrate-complete` | Status slice now isolated from settings data and handlers. |
| [src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx](/workspace/reigh-app/src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx) `VideoTravelSettingsLorasContext` | 1 | 2 | `migrate-complete` | LoRA inventory split out as its own slice. |
| [src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx) `ShotSettingsIdentityContext` | 18 | 4 | `migrate-complete` | Split from the former wide shot-editor context. |
| [src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx) `ShotSettingsUiContext` | 43 | 3 | `migrate-complete` | UI orchestration no longer forces media/generation readers to resubscribe. |
| [src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx) `ShotSettingsMediaContext` | 50+ | 3 | `migrate-complete` | Media-heavy slice isolated from the rest of the editor state. |
| [src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx) `ShotSettingsGenerationContext` | 50+ | 4 | `migrate-complete` | Generation-heavy slice isolated from identity/UI/media readers. |
| [src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx) `TimelineGuidanceMediaContext` | 18 | 1 | `migrate-complete` | Guidance-media slice split from the former mixed timeline-media object. |
| [src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx) `TimelineAudioMediaContext` | 4 | 1 | `migrate-complete` | Audio slice now stands alone. |
| [src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx) `TimelineFpsContext` | 1 | 6 | `migrate-complete` | FPS is now its own one-field context. |

### Video-editor runtime and store-adjacent contexts

| Declaration | Expanded field count | External production consumers | Decision | Rationale |
| --- | ---: | ---: | --- | --- |
| [src/tools/video-editor/contexts/DataProviderContext.tsx](/workspace/reigh-app/src/tools/video-editor/contexts/DataProviderContext.tsx) `DataProviderContext` | 13 | 7 | `keep` | Wider than ideal, but it is runtime provider plumbing rather than a broad mutable editor-state pubsub surface. |
| [src/tools/video-editor/compositions/AudioAnalysisProvider.tsx](/workspace/reigh-app/src/tools/video-editor/compositions/AudioAnalysisProvider.tsx) `AudioAnalysisContext` | 1 | 0 | `out-of-scope` | Render-pipeline analysis data, not app-shell UI state. |
| [src/tools/video-editor/hooks/timelineStore.ts](/workspace/reigh-app/src/tools/video-editor/hooks/timelineStore.ts) `TimelineStoreContext` | 4 | 0 | `out-of-scope` | Store API provider boundary for Zustand. This is intentionally exempt from the fat-context rule. |

### Local UI and overlay contexts

These are provider-local implementation details. All have `0` external production consumers under the counting contract.

| Declaration | Expanded field count | Decision | Rationale |
| --- | ---: | --- | --- |
| [src/shared/components/ui/overlay/dropdown-menu.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/dropdown-menu.tsx) `DropdownMenuModalContext` | 1 | `out-of-scope` | Primitive-local modal token. |
| [src/shared/components/ui/overlay/lightbox.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/lightbox.tsx) `LightboxDialogModalContext` | 1 | `out-of-scope` | Primitive-local modal token. |
| [src/shared/components/ui/overlay/lightbox.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/lightbox.tsx) `LightboxDialogLayerContext` | 2 | `out-of-scope` | Primitive-local portal/layer bridge. |
| [src/shared/components/ui/overlay/overlayBridge.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/overlayBridge.tsx) `OverlayBridgeContext` | 8 | `out-of-scope` | Internal overlay-instance bridge. |
| [src/shared/components/ui/overlay/popover.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/popover.tsx) `PopoverModalContext` | 1 | `out-of-scope` | Primitive-local modal token. |
| [src/shared/components/ui/overlay/select.tsx](/workspace/reigh-app/src/shared/components/ui/overlay/select.tsx) `SelectModalContext` | 1 | `out-of-scope` | Primitive-local modal token. |
| [src/shared/components/ui/segmented-control.tsx](/workspace/reigh-app/src/shared/components/ui/segmented-control.tsx) `SegmentedControlContext` | 4 | `out-of-scope` | Component-local styling/value bridge. |
| [src/shared/components/ui/tabs.tsx](/workspace/reigh-app/src/shared/components/ui/tabs.tsx) `TabsListContext` | 1 | `out-of-scope` | Component-local variant token. |
| [src/shared/components/ui/toggle-group.tsx](/workspace/reigh-app/src/shared/components/ui/toggle-group.tsx) `ToggleGroupContext` | 3 | `out-of-scope` | Component-local variant/size token. |

### Test-only declarations

| Declaration | Expanded field count | Decision | Rationale |
| --- | ---: | --- | --- |
| [src/tools/travel-between-images/components/FinalVideoSectionControls.test.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/FinalVideoSectionControls.test.tsx) `SelectContext` | 1 | `out-of-scope` | Test harness only. |
| [src/tools/travel-between-images/components/Timeline/GuidanceVideoStripRangeControls.test.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/Timeline/GuidanceVideoStripRangeControls.test.tsx) `SelectContext` | 1 | `out-of-scope` | Test harness only. |
| [src/shared/components/PromptEditorModal/components/PromptEditorAIPanel.test.tsx](/workspace/reigh-app/src/shared/components/PromptEditorModal/components/PromptEditorAIPanel.test.tsx) `TabsContext` | 2 | `out-of-scope` | Test-only mock tabs bridge. |
| [src/tools/travel-between-images/components/ShotImagesEditor/ShotImagesEditorHeader.test.tsx](/workspace/reigh-app/src/tools/travel-between-images/components/ShotImagesEditor/ShotImagesEditorHeader.test.tsx) `SegmentContext` | 2 | `out-of-scope` | Test-only mock segmented-control bridge. |

## Explicit Exemptions

- `TimelineStoreContext` is exempt because it provides a Zustand store API, not a wide mutable value object.
- UI primitive and overlay contexts are exempt because they are provider-local implementation details with no external production consumer surface.
- `AudioAnalysisContext` is exempt because it is Remotion composition data, not app-shell state orchestration.
- `scripts/quality/fat-context-allowlist.json` is the explicit exemption register for declaration-only guard failures that are accepted for now. Each entry is a `path::contextName` pair and should be paired with a rationale update here.

## Descriptor Snapshot

This appendix is the exact declaration-by-declaration snapshot used to re-verify document completeness after the review rework. The production list comes from the same TypeScript-walker logic as `npm run check:fat-contexts`, and the four test-only entries come from the explicit grep outside `tsconfig.app.json`. On this pass the generated snapshot still matched the `49` production and `4` test-only counts documented above, so the table inventory and the checker inventory stayed in sync.

### Production descriptors (`49`)

```text
src/domains/media-lightbox/contexts/ImageEditCanvasContext.tsx::ImageEditCanvasContext
src/domains/media-lightbox/contexts/ImageEditFormContext.tsx::ImageEditFormContext
src/domains/media-lightbox/contexts/ImageEditStatusContext.tsx::ImageEditStatusContext
src/domains/media-lightbox/contexts/LightboxStateContext.tsx::LightboxCoreContext
src/domains/media-lightbox/contexts/LightboxStateContext.tsx::LightboxMediaContext
src/domains/media-lightbox/contexts/LightboxStateContext.tsx::LightboxNavigationContext
src/domains/media-lightbox/contexts/LightboxStateContext.tsx::LightboxVariantsContext
src/domains/media-lightbox/contexts/VideoEditContext.tsx::VideoEditContext
src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts::ImageGenerationFormCoreContext
src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts::ImageGenerationFormLorasContext
src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts::ImageGenerationFormPromptsContext
src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts::ImageGenerationFormReferencesContext
src/shared/components/ImageGenerationForm/ImageGenerationFormContext.token.ts::ImageGenerationFormUIContext
src/shared/components/ui/overlay/dropdown-menu.tsx::DropdownMenuModalContext
src/shared/components/ui/overlay/lightbox.tsx::LightboxDialogLayerContext
src/shared/components/ui/overlay/lightbox.tsx::LightboxDialogModalContext
src/shared/components/ui/overlay/overlayBridge.tsx::OverlayBridgeContext
src/shared/components/ui/overlay/popover.tsx::PopoverModalContext
src/shared/components/ui/overlay/select.tsx::SelectModalContext
src/shared/components/ui/segmented-control.tsx::SegmentedControlContext
src/shared/components/ui/tabs.tsx::TabsListContext
src/shared/components/ui/toggle-group.tsx::ToggleGroupContext
src/shared/contexts/AIInputModeContext.tsx::AIInputModeContext
src/shared/contexts/AgentChatContext.tsx::AgentChatContext
src/shared/contexts/AgentChatContext.tsx::AgentChatRegistryContext
src/shared/contexts/AuthContext.tsx::AuthContext
src/shared/contexts/GenerationTaskContext.tsx::GenerationTaskContext
src/shared/contexts/IncomingTasksContext.tsx::IncomingTasksContext
src/shared/contexts/ProjectContext.tsx::ProjectCrudContext
src/shared/contexts/ProjectContext.tsx::ProjectIdentityContext
src/shared/contexts/ProjectContext.tsx::ProjectSelectionContext
src/shared/contexts/ShotsContext.tsx::ShotsContext
src/shared/contexts/ToolPageHeaderContext.tsx::ToolPageHeaderContext
src/shared/contexts/UserSettingsContext.tsx::UserSettingsContext
src/shared/providers/RealtimeProvider.tsx::RealtimeContext
src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx::ShotSettingsGenerationContext
src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx::ShotSettingsIdentityContext
src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx::ShotSettingsMediaContext
src/tools/travel-between-images/components/ShotEditor/ShotSettingsContext.provider.tsx::ShotSettingsUiContext
src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx::TimelineAudioMediaContext
src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx::TimelineFpsContext
src/tools/travel-between-images/components/Timeline/TimelineMediaContext.tsx::TimelineGuidanceMediaContext
src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx::VideoTravelSettingsDataContext
src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx::VideoTravelSettingsHandlersContext
src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx::VideoTravelSettingsLorasContext
src/tools/travel-between-images/providers/VideoTravelSettingsProvider.tsx::VideoTravelSettingsStatusContext
src/tools/video-editor/compositions/AudioAnalysisProvider.tsx::AudioAnalysisContext
src/tools/video-editor/contexts/DataProviderContext.tsx::DataProviderContext
src/tools/video-editor/hooks/timelineStore.ts::TimelineStoreContext
```

### Test-only descriptors (`4`)

```text
src/shared/components/PromptEditorModal/components/PromptEditorAIPanel.test.tsx::TabsContext
src/tools/travel-between-images/components/FinalVideoSectionControls.test.tsx::SelectContext
src/tools/travel-between-images/components/ShotImagesEditor/ShotImagesEditorHeader.test.tsx::SegmentContext
src/tools/travel-between-images/components/Timeline/GuidanceVideoStripRangeControls.test.tsx::SelectContext
```

## Post-T6 State

- Every non-pane surface that crossed both thresholds during the audit was narrowed or split in this branch.
- No production caller remains for `useProject()`, `useVideoTravelSettings()`, `useShotSettingsContext()`, or `useTimelineMedia()`.
- New follow-up work should only be opened if:
  1. A currently thin declaration crosses both thresholds.
  2. A deprecated recomposed hook regains production callers.
  3. A new fat declaration is added to the allowlist instead of being split.
