# Slot-First Legacy Reference Grep Ledger

Generated: 2026-05-20T09:17:23Z UTC

This is the Day-1 whole-repo burn-down ledger for legacy generation-shaped identifiers. It is file-level output from `rg -l`, not a semantic classification. Later M2/M3/M4 work should use the buckets below as the starting work queue and then decide whether each hit is code, generated type surface, test fixture, documentation, migration history, or planning/debt state.

## Search Contract

Working directory: `/workspace/reigh-app`

Pattern:

```text
generation_id|generation_variants|shot_generations|pair_shot_generation_id|parent_generation_id|child_generation_id|primary_variant_id|findExistingGenerationAtPosition|auto_create_variant|create_generation_on_task_complete|duplicate_as_new_generation
```

Hidden-inclusive command used for the ledger:

```bash
rg -l --hidden --no-ignore --glob '!.git/**' --glob '!node_modules/**' --glob '!dist/**' --glob '!build/**' --glob '!coverage/**' --glob '!tmp/**' --glob '!*.log' "generation_id|generation_variants|shot_generations|pair_shot_generation_id|parent_generation_id|child_generation_id|primary_variant_id|findExistingGenerationAtPosition|auto_create_variant|create_generation_on_task_complete|duplicate_as_new_generation" | sort
```

`--no-ignore` is intentional: `.gitignore` ignores `*.md` and parts of `.megaplan/`, but this audit must include hidden and ignored planning/docs surfaces.

Exclusion globs:

- `!.git/**`
- `!node_modules/**`
- `!dist/**`
- `!build/**`
- `!coverage/**`
- `!tmp/**`
- `!*.log`

Total hit-file count: 643

## Bucket Counts

| Bucket | Hit files |
| --- | ---: |
| `generated Supabase types` | 1 |
| `src/` | 301 |
| `supabase/functions/` | 67 |
| `supabase/migrations/` | 220 |
| `supabase/tests/` | 2 |
| `scripts/` | 4 |
| `docs/` | 8 |
| `tasks/` | 10 |
| `.megaplan/` | 28 |
| `root/other` | 2 |

## `.megaplan/` Sanity Search

Command:

```bash
rg -l --hidden --no-ignore --glob '!.git/**' --glob '!node_modules/**' --glob '!dist/**' --glob '!build/**' --glob '!coverage/**' --glob '!tmp/**' --glob '!*.log' "generation_id|generation_variants|shot_generations|pair_shot_generation_id|parent_generation_id|child_generation_id|primary_variant_id|findExistingGenerationAtPosition|auto_create_variant|create_generation_on_task_complete|duplicate_as_new_generation" .megaplan | sort
```

Hit-file count: 28

Output:

```text
.megaplan/debt.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_output.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v1.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v2.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v3.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/faults.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/final.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/finalize.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/finalize_snapshot.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v1.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v2.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v3.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v1.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v1.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v2.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v2.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v3.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v3.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/state.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/step_receipt_plan_v1.json
.megaplan/slot-first-m0-preflight-idea.md
.megaplan/slot-first-m1-schema-idea.md
.megaplan/slot-first-m2-frontend-idea.md
.megaplan/slot-first-m3a-worker-contract-idea.md
.megaplan/slot-first-m3b-edge-functions-idea.md
.megaplan/slot-first-m3c-astrid-share-idea.md
.megaplan/slot-first-m4-cutover-idea.md
```

## Root/Other Bucket

Root/config hits are intentionally not dropped into a default bucket. They must be reviewed explicitly because files such as `chain.yaml` can drive later automation.

```text
.cursorrules
chain.yaml
```

## generated Supabase types

Hit-file count: 1

```text
src/integrations/supabase/types.ts
```

## src/

Hit-file count: 301

```text
src/app/hooks/useAppExternalDrop.ts
src/domains/generation/hooks/__tests__/useGenerationMutations.test.ts
src/domains/generation/hooks/useGenerationMutations.ts
src/domains/generation/mappers/generationRowMapper.ts
src/domains/generation/types/generationMetadata.ts
src/domains/generation/types/generationRow.ts
src/domains/generation/types/generationRowDto.ts
src/domains/media-lightbox/VideoLightbox.tsx
src/domains/media-lightbox/components/SegmentRegenerateForm.tsx
src/domains/media-lightbox/hooks/__tests__/useImageLightboxEnvironment.test.ts
src/domains/media-lightbox/hooks/__tests__/useLightboxVariantBadges.test.ts
src/domains/media-lightbox/hooks/__tests__/useVariantSelection.test.ts
src/domains/media-lightbox/hooks/inpainting/createInpaintingTaskWorkflow.ts
src/domains/media-lightbox/hooks/inpainting/useTaskGeneration.ts
src/domains/media-lightbox/hooks/modes/useVideoEditing.ts
src/domains/media-lightbox/hooks/modes/videoEditingTaskPayload.test.ts
src/domains/media-lightbox/hooks/modes/videoEditingTaskPayload.ts
src/domains/media-lightbox/hooks/reposition/useRepositionVariantSave.ts
src/domains/media-lightbox/hooks/useGenerationLineage.ts
src/domains/media-lightbox/hooks/useImageLightboxEnvironment.ts
src/domains/media-lightbox/hooks/useImg2ImgMode.ts
src/domains/media-lightbox/hooks/useLightboxVideoMode.ts
src/domains/media-lightbox/hooks/useMagicEditMode.ts
src/domains/media-lightbox/hooks/useMakeMainVariant.ts
src/domains/media-lightbox/hooks/useReferences.test.ts
src/domains/media-lightbox/hooks/useReferences.ts
src/domains/media-lightbox/hooks/useShotCreation.test.ts
src/domains/media-lightbox/hooks/useShotCreation.ts
src/domains/media-lightbox/hooks/useShotPositioning.ts
src/domains/media-lightbox/hooks/useSourceGeneration.ts
src/domains/media-lightbox/hooks/useStarToggle.ts
src/domains/media-lightbox/hooks/useUpscale.ts
src/domains/media-lightbox/hooks/useVariantPromotion.ts
src/domains/media-lightbox/hooks/useVariantSelection.ts
src/domains/media-lightbox/hooks/useVideoRegenerateMode.ts
src/domains/media-lightbox/hooks/videoLightbox/useVideoLightboxEnvironment.ts
src/domains/media-lightbox/types.ts
src/domains/media-lightbox/utils/__tests__/lightboxDownload.test.ts
src/features/editor/components/ShotsPanelContent.tsx
src/features/gallery/components/GenerationsPane/components/GenerationsPaneGallery.test.tsx
src/features/gallery/components/GenerationsPane/components/GenerationsPaneGallery.tsx
src/features/gallery/components/GenerationsPane/hooks/useLassoSelection.ts
src/features/gallery/hooks/useGalleryPageState.ts
src/features/resources/hooks/useResources.ts
src/features/tasks/components/TasksPane/hooks/useImageGeneration.ts
src/features/tasks/components/TasksPane/hooks/useShotActions.ts
src/features/tasks/components/TasksPane/hooks/useTaskContentType.ts
src/features/tasks/components/TasksPane/hooks/useTaskNavigation.ts
src/features/tasks/components/TasksPane/hooks/useVideoGenerations.ts
src/features/tasks/components/TasksPane/utils/__tests__/task-utils.test.ts
src/features/tasks/components/TasksPane/utils/findGenerationByVariantLocation.ts
src/features/tasks/components/TasksPane/utils/task-utils.ts
src/integrations/supabase/repositories/derivedItemsRepository.test.ts
src/integrations/supabase/repositories/derivedItemsRepository.ts
src/integrations/supabase/repositories/generationMutationsRepository.test.ts
src/integrations/supabase/repositories/generationMutationsRepository.ts
src/integrations/supabase/repositories/segmentGenerationPersistenceRepository.ts
src/pages/shots/hooks/useShotImageMutations.ts
src/shared/components/ImageGenerationForm/hooks/__tests__/useHydratedReferences.test.ts
src/shared/components/ImageGenerationForm/hooks/legacyMigrations/useGenerationBackfillMigration.ts
src/shared/components/ImageGenerationForm/hooks/referenceUpload/referenceDomainService.test.ts
src/shared/components/ImageGenerationForm/hooks/referenceUpload/referenceDomainService.ts
src/shared/components/ImageGenerationForm/hooks/referenceUpload/useResourceSelectHandler.ts
src/shared/components/ImageGenerationForm/hooks/referenceUpload/useStyleReferenceUploadHandler.test.ts
src/shared/components/ImageGenerationForm/hooks/referenceUpload/useStyleReferenceUploadHandler.ts
src/shared/components/ImageGenerationForm/hooks/useHydratedReferences.ts
src/shared/components/ImageGenerationForm/hooks/useReferenceUpload.test.ts
src/shared/components/ImageGenerationForm/hooks/useReferenceUpload.ts
src/shared/components/MediaGallery/hooks/useMediaGalleryActions.ts
src/shared/components/MediaGallery/hooks/useMediaGalleryLightboxSession.test.ts
src/shared/components/MediaGallery/types.ts
src/shared/components/MediaGallery/utils/__tests__/lightboxMedia.test.ts
src/shared/components/MediaGallery/utils/lightboxMedia.ts
src/shared/components/MediaGalleryItem.behavior.test.tsx
src/shared/components/MediaGalleryItem.tsx
src/shared/components/SegmentSettingsForm/segmentSettingsMigration.ts
src/shared/components/SegmentSettingsForm/segmentSettingsUtils.ts
src/shared/components/ShotImageManager/ShotBatchItemDesktop.tsx
src/shared/components/ShotImageManager/ShotBatchItemMobile.tsx
src/shared/components/ShotImageManager/ShotImageManagerContainer.test.tsx
src/shared/components/ShotImageManager/ShotImageManagerDesktop.test.tsx
src/shared/components/ShotImageManager/ShotImageManagerMobile.tsx
src/shared/components/ShotImageManager/components/ImageGrid.tsx
src/shared/components/ShotImageManager/components/MobileImageGrid.tsx
src/shared/components/ShotImageManager/hooks/useDragAndDrop.ts
src/shared/components/ShotImageManager/hooks/useExternalGenerations.ts
src/shared/components/ShotImageManager/hooks/useMobileGestures.ts
src/shared/components/ShotImageManager/hooks/useOptimisticOrder.ts
src/shared/components/ShotImageManager/hooks/useSelection.ts
src/shared/components/ShotImageManager/types.ts
src/shared/components/ShotImageManager/utils/__tests__/external-generation-utils.test.ts
src/shared/components/ShotImageManager/utils/external-generation-utils.ts
src/shared/components/ShotImageManager/utils/reorder-utils.ts
src/shared/components/VariantSelector/__tests__/utils.test.ts
src/shared/components/VariantSelector/__tests__/variantSourceImages.test.ts
src/shared/components/VariantSelector/hooks/useVariantActions.ts
src/shared/components/VariantSelector/variantSourceImages.ts
src/shared/components/VideoTrimEditor/hooks/useTrimSave.ts
src/shared/components/modals/ProjectSettingsModal.tsx
src/shared/hooks/__tests__/useLineageChain.test.ts
src/shared/hooks/__tests__/useLoadVariantImages.test.ts
src/shared/hooks/__tests__/useMarkVariantViewed.test.ts
src/shared/hooks/__tests__/usePendingGenerationTasks.test.ts
src/shared/hooks/__tests__/usePendingImageOpen.test.ts
src/shared/hooks/__tests__/usePromoteVariantToGeneration.test.ts
src/shared/hooks/__tests__/useShareGeneration.test.ts
src/shared/hooks/__tests__/useShotCreation.test.ts
src/shared/hooks/__tests__/useShotImages.test.ts
src/shared/hooks/__tests__/useTimelineCore.test.ts
src/shared/hooks/__tests__/useVariants.test.ts
src/shared/hooks/gallery/useGallerySelectionBridge.ts
src/shared/hooks/gallery/useVideoGalleryPreloader.ts
src/shared/hooks/projects/useProjectGenerations.ts
src/shared/hooks/segments/__tests__/segmentDataTransforms.test.ts
src/shared/hooks/segments/__tests__/segmentOutputsQueries.test.ts
src/shared/hooks/segments/__tests__/useSegmentMutations.test.ts
src/shared/hooks/segments/__tests__/useSegmentOutputsForShot.test.ts
src/shared/hooks/segments/segmentDataTransforms.ts
src/shared/hooks/segments/segmentOutputTypes.test.ts
src/shared/hooks/segments/segmentOutputTypes.ts
src/shared/hooks/segments/segmentOutputsQueries.ts
src/shared/hooks/segments/segmentSlotAssignment.test.ts
src/shared/hooks/segments/segmentSlotAssignment.ts
src/shared/hooks/segments/usePairMetadata.ts
src/shared/hooks/segments/useSegmentMutations.ts
src/shared/hooks/segments/useSegmentOutputsForShot.ts
src/shared/hooks/shotCreation/shotCreationPaths.test.ts
src/shared/hooks/shotCreation/shotCreationPaths.ts
src/shared/hooks/shotCreation/shotCreationTypes.ts
src/shared/hooks/shots/__tests__/addImageToShotHelpers.test.ts
src/shared/hooks/shots/__tests__/cacheUtils.test.ts
src/shared/hooks/shots/__tests__/mappers.test.ts
src/shared/hooks/shots/__tests__/shotMutationHelpers.test.ts
src/shared/hooks/shots/__tests__/useDuplicateAsNewGeneration.test.ts
src/shared/hooks/shots/__tests__/useDuplicateShotWithVideos.test.ts
src/shared/hooks/shots/__tests__/useShotGenerationMutations.test.ts
src/shared/hooks/shots/__tests__/useShotsQueries.test.ts
src/shared/hooks/shots/addImageToShotHelpers.ts
src/shared/hooks/shots/externalImageDrop.test.ts
src/shared/hooks/shots/externalImageDrop.ts
src/shared/hooks/shots/mappers.ts
src/shared/hooks/shots/shotMutationHelpers.ts
src/shared/hooks/shots/useDuplicateAsNewGeneration.ts
src/shared/hooks/shots/useShotCreation.ts
src/shared/hooks/shots/useShotGenerationMetadata.ts
src/shared/hooks/shots/useShotGenerationMutations.ts
src/shared/hooks/shots/useShotImages.ts
src/shared/hooks/shots/useShotsQueries.ts
src/shared/hooks/sourceImageChanges/__tests__/dataAccess.test.ts
src/shared/hooks/sourceImageChanges/dataAccess.ts
src/shared/hooks/tasks/usePendingGenerationTasks.ts
src/shared/hooks/tasks/usePendingSegmentTasks.ts
src/shared/hooks/timeline/__tests__/timelineFrameCalculators.test.ts
src/shared/hooks/timeline/__tests__/useTimelineFrameUpdates.test.ts
src/shared/hooks/timeline/timelineFrameCalculators.ts
src/shared/hooks/timeline/timelineMutationService.ts
src/shared/hooks/timeline/useTimelineCore.enhancedPromptOperations.test.ts
src/shared/hooks/timeline/useTimelineCore.enhancedPromptOperations.ts
src/shared/hooks/timeline/useTimelineCore.pairOperations.test.ts
src/shared/hooks/timeline/useTimelineCore.pairOperations.ts
src/shared/hooks/timeline/useTimelineCore.ts
src/shared/hooks/timeline/useTimelineCore.types.ts
src/shared/hooks/timeline/useTimelineFrameUpdates.ts
src/shared/hooks/usePendingImageOpen.ts
src/shared/hooks/useRealtimeInvalidation.ts
src/shared/hooks/useShareGeneration.ts
src/shared/hooks/useSpecificResources.ts
src/shared/hooks/variants/useLineageChain.ts
src/shared/hooks/variants/useLoadVariantImages.ts
src/shared/hooks/variants/useMarkVariantViewed.ts
src/shared/hooks/variants/usePromoteVariantToGeneration.ts
src/shared/hooks/variants/useToggleVariantStar.ts
src/shared/hooks/variants/useVariants.ts
src/shared/lib/__tests__/generationTaskCache.test.ts
src/shared/lib/__tests__/generationTaskRepository.test.ts
src/shared/lib/__tests__/generationTransformers.test.ts
src/shared/lib/generationTransformers.ts
src/shared/lib/localWorker/ingest.ts
src/shared/lib/media/__tests__/mediaTypeHelpers.test.ts
src/shared/lib/media/__tests__/resolveTaskInputMedia.test.ts
src/shared/lib/media/materializeLocalGeneration.test.ts
src/shared/lib/media/materializeLocalGeneration.ts
src/shared/lib/media/mediaTypeHelpers.ts
src/shared/lib/media/resolveTaskInputMedia.ts
src/shared/lib/reorderUtils.ts
src/shared/lib/settingsMigration.ts
src/shared/lib/taskCreation/createTask.test.ts
src/shared/lib/taskCreation/createTask.ts
src/shared/lib/taskCreation/localWorkerSession.ts
src/shared/lib/tasks/__tests__/segmentGenerationPersistence.test.ts
src/shared/lib/tasks/__tests__/travelPayloadReader.test.ts
src/shared/lib/tasks/generationTaskRepository.ts
src/shared/lib/tasks/imageEditing/__tests__/imageInpaint.test.ts
src/shared/lib/tasks/imageEditing/buildMaskedEditTaskParams.test.ts
src/shared/lib/tasks/imageEditing/buildMaskedEditTaskParams.ts
src/shared/lib/tasks/imageEditing/imageInpaint.ts
src/shared/lib/tasks/orchestrationContract.test.ts
src/shared/lib/tasks/orchestrationContract.ts
src/shared/lib/tasks/shotParentGeneration.ts
src/shared/lib/tasks/travelBetweenImages/__tests__/segmentImages.test.ts
src/shared/lib/tasks/travelBetweenImages/segmentImages.ts
src/shared/lib/tasks/travelBetweenImages/taskTypes.ts
src/shared/lib/tasks/travelPayloadReader.ts
src/shared/lib/timelineFrameBatchPersist.ts
src/shared/lib/timelinePositionCalculator.ts
src/shared/providers/__tests__/RealtimeProvider.test.tsx
src/shared/realtime/RealtimeConnection.ts
src/shared/realtime/RealtimeEventProcessor.ts
src/shared/realtime/__tests__/RealtimeEventProcessor.test.ts
src/shared/realtime/types.ts
src/shared/state/realtimeStore.test.ts
src/shared/state/realtimeStore.ts
src/shared/types/displayableMetadata.ts
src/shared/types/individualTravelSegment.ts
src/shared/types/joinClips.ts
src/shared/types/pairData.ts
src/shared/types/segmentSettings.ts
src/tools/edit-images/components/InlineEditView.test.tsx
src/tools/edit-images/hooks/__tests__/useInlineEditState.test.ts
src/tools/edit-images/hooks/useInlineEditState.ts
src/tools/edit-images/pages/EditImagesPage.tsx
src/tools/edit-video/hooks/useReplaceMode.ts
src/tools/edit-video/pages/EditVideoPage.tsx
src/tools/image-generation/hooks/useImageGenActions.ts
src/tools/image-generation/pages/ImageGenerationToolPage.tsx
src/tools/travel-between-images/components/FinalVideoSection.tsx
src/tools/travel-between-images/components/ShotEditor/hooks/actions/__tests__/useDropActions.test.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useBoundarySummary.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useDeleteActions.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useDropActions.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useDuplicateAction.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useJoinSegmentsHandler.ts
src/tools/travel-between-images/components/ShotEditor/hooks/actions/useShotActions.ts
src/tools/travel-between-images/components/ShotEditor/hooks/editor-state/timelineDropHelpers.test.ts
src/tools/travel-between-images/components/ShotEditor/hooks/editor-state/timelineDropHelpers.ts
src/tools/travel-between-images/components/ShotEditor/hooks/editor-state/useImageManagement.ts
src/tools/travel-between-images/components/ShotEditor/hooks/video/useLastVideoGeneration.ts
src/tools/travel-between-images/components/ShotEditor/services/__tests__/generateVideoService.test.ts
src/tools/travel-between-images/components/ShotEditor/services/applySettings/imageService.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideo/pairPayload.test.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideo/pairPayload.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideo/requestBody.test.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideo/requestBody.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideo/types.ts
src/tools/travel-between-images/components/ShotEditor/services/generateVideoService.ts
src/tools/travel-between-images/components/ShotImagesEditor/hooks/useFrameCountUpdater.ts
src/tools/travel-between-images/components/ShotImagesEditor/hooks/usePairData.ts
src/tools/travel-between-images/components/ShotImagesEditor/hooks/useSegmentSlotPresentationAdapter.test.ts
src/tools/travel-between-images/components/ShotImagesEditor/hooks/useSegmentSlotPresentationAdapter.ts
src/tools/travel-between-images/components/ShotImagesEditor/services/segmentDeletionService.test.ts
src/tools/travel-between-images/components/ShotImagesEditor/services/segmentDeletionService.ts
src/tools/travel-between-images/components/Timeline/TimelineContainer/TimelineContainer.tsx
src/tools/travel-between-images/components/Timeline/TimelineContainer/components/PairRegionsLayer.test.tsx
src/tools/travel-between-images/components/Timeline/TimelineContainer/components/TimelineItemsLayer.test.tsx
src/tools/travel-between-images/components/Timeline/TimelineContainer/components/TimelineItemsLayer.tsx
src/tools/travel-between-images/components/Timeline/TimelineContainer/components/TrailingEndpointLayer.test.tsx
src/tools/travel-between-images/components/Timeline/TimelineItem.tsx
src/tools/travel-between-images/components/Timeline/hooks/segment/timelineTrailingEndpointPersistence.ts
src/tools/travel-between-images/components/Timeline/hooks/segment/useSegmentDeletion.ts
src/tools/travel-between-images/components/Timeline/hooks/segment/useSegmentLightbox.ts
src/tools/travel-between-images/components/Timeline/hooks/segment/useSegmentOutputStrip.ts
src/tools/travel-between-images/components/Timeline/hooks/timeline-core/timelinePositionOperations.ts
src/tools/travel-between-images/components/Timeline/hooks/timeline-core/useComputedTimelineData.ts
src/tools/travel-between-images/components/Timeline/hooks/useTimelineLightboxOrchestrator.test.ts
src/tools/travel-between-images/components/Timeline/hooks/useTimelineLightboxOrchestrator.ts
src/tools/travel-between-images/components/Timeline/index.tsx
src/tools/travel-between-images/components/Timeline/utils/__tests__/timeline-utils.test.ts
src/tools/travel-between-images/components/Timeline/utils/timeline-video-utils.test.ts
src/tools/travel-between-images/components/Timeline/utils/timeline-video-utils.ts
src/tools/travel-between-images/components/VideoGallery/hooks/useVideoItemJoinClips.ts
src/tools/travel-between-images/components/hooks/useFinalVideoSectionController.test.tsx
src/tools/travel-between-images/components/hooks/useFinalVideoSectionController.ts
src/tools/travel-between-images/components/hooks/useModalImageHandlers.ts
src/tools/travel-between-images/hooks/settings/useSegmentPromptMetadata.ts
src/tools/travel-between-images/hooks/timeline/useEnhancedShotImageReorder.ts
src/tools/travel-between-images/hooks/timeline/useTimelinePositionUtils.test.ts
src/tools/travel-between-images/hooks/timeline/useTimelinePositionUtils.ts
src/tools/travel-between-images/hooks/video/useShotFinalVideos.ts
src/tools/travel-between-images/hooks/workflow/useDemoteOrphanedVariants.ts
src/tools/travel-between-images/hooks/workflow/useVideoTravelAddToShot.ts
src/tools/travel-between-images/hooks/workflow/useVideoTravelDropHandlers.ts
src/tools/travel-between-images/utils/__tests__/shareDataTransformers.test.ts
src/tools/travel-between-images/utils/shareDataTransformers.ts
src/tools/video-editor/adapters/reigh/generationLookup.ts
src/tools/video-editor/adapters/reigh/staleVariantRepository.ts
src/tools/video-editor/adapters/reigh/variantPromotionLookup.ts
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx
src/tools/video-editor/components/AgentChat/AgentChat.tsx
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx
src/tools/video-editor/components/ReighTimelineEditor.tsx
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx
src/tools/video-editor/contexts/VideoEditorProvider.tsx
src/tools/video-editor/hooks/useAddVariantAsGeneration.ts
src/tools/video-editor/hooks/useAgentSession.test.tsx
src/tools/video-editor/hooks/useAgentSession.ts
src/tools/video-editor/hooks/useClipEditing.test.ts
src/tools/video-editor/hooks/useExternalDrop.test.tsx
src/tools/video-editor/hooks/useExternalDrop.ts
src/tools/video-editor/hooks/usePinnedShotGroups.ts
src/tools/video-editor/hooks/useStaleVariants.ts
src/types/database.ts
```

## supabase/functions/

Hit-file count: 67

```text
supabase/functions/_shared/taskPayloadSnapshot.test.ts
supabase/functions/_shared/taskPayloadSnapshot.ts
supabase/functions/_tests/harness/agentic-runner.ts
supabase/functions/_tests/harness/cases.ts
supabase/functions/_tests/harness/diverse-gen-test.ts
supabase/functions/_tests/harness/evaluate.ts
supabase/functions/_tests/harness/fixtures.ts
supabase/functions/_tests/harness/routing-stress-test.ts
supabase/functions/_tests/harness/snapshot.ts
supabase/functions/_tests/harness/waiter.ts
supabase/functions/ai-timeline-agent/command-parser.ts
supabase/functions/ai-timeline-agent/loop.test.ts
supabase/functions/ai-timeline-agent/loop.ts
supabase/functions/ai-timeline-agent/prompts.ts
supabase/functions/ai-timeline-agent/selectedClips.test.ts
supabase/functions/ai-timeline-agent/selectedClips.ts
supabase/functions/ai-timeline-agent/tool-schemas.ts
supabase/functions/ai-timeline-agent/tools/clips.test.ts
supabase/functions/ai-timeline-agent/tools/clips.ts
supabase/functions/ai-timeline-agent/tools/create-task.test.ts
supabase/functions/ai-timeline-agent/tools/create-task.ts
supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts
supabase/functions/ai-timeline-agent/tools/generation.ts
supabase/functions/ai-timeline-agent/tools/transform-image.test.ts
supabase/functions/ai-timeline-agent/tools/transform-image.ts
supabase/functions/ai-timeline-agent/types.ts
supabase/functions/apply-image-transform/index.ts
supabase/functions/complete_task/cleanupMaterializedInputs.test.ts
supabase/functions/complete_task/cleanupMaterializedInputs.ts
supabase/functions/complete_task/completionHelpers.ts
supabase/functions/complete_task/generation-child-diagnostics.test.ts
supabase/functions/complete_task/generation-child-diagnostics.ts
supabase/functions/complete_task/generation-child.test.ts
supabase/functions/complete_task/generation-child.ts
supabase/functions/complete_task/generation-core.test.ts
supabase/functions/complete_task/generation-core.ts
supabase/functions/complete_task/generation-handlers.test.ts
supabase/functions/complete_task/generation-handlers.ts
supabase/functions/complete_task/generation-parent.ts
supabase/functions/complete_task/generation.ts
supabase/functions/complete_task/handler.test.ts
supabase/functions/complete_task/handler.ts
supabase/functions/complete_task/placement.test.ts
supabase/functions/complete_task/placement.ts
supabase/functions/complete_task/taskParamNormalizer.test.ts
supabase/functions/complete_task/taskParamNormalizer.ts
supabase/functions/create-task/index.ts
supabase/functions/create-task/resolvers/__tests__/placement.test.ts
supabase/functions/create-task/resolvers/crossfadeJoin.ts
supabase/functions/create-task/resolvers/editVideoOrchestrator.ts
supabase/functions/create-task/resolvers/imageUpscale.ts
supabase/functions/create-task/resolvers/individualTravelSegment.ts
supabase/functions/create-task/resolvers/joinClips.ts
supabase/functions/create-task/resolvers/maskedEdit.ts
supabase/functions/create-task/resolvers/shared/lineage.ts
supabase/functions/create-task/resolvers/shared/taskContracts.ts
supabase/functions/create-task/resolvers/travelBetweenImages.ts
supabase/functions/create-task/resolvers/types.ts
supabase/functions/create-task/resolvers/videoEnhance.ts
supabase/functions/generate-thumbnail/index.test.ts
supabase/functions/generate-thumbnail/index.ts
supabase/functions/get-predecessor-output/index.ts
supabase/functions/reigh-data-fetch/index.test.ts
supabase/functions/reigh-data-fetch/index.ts
supabase/functions/trim-video/index.test.ts
supabase/functions/trim-video/index.ts
supabase/functions/update-shot-pair-prompts/index.ts
```

## supabase/migrations/

Hit-file count: 220

```text
supabase/migrations/20250100000000_create_base_schema.sql
supabase/migrations/20250107_add_shot_denormalization.sql
supabase/migrations/20250114000000_add_shot_generation_rpc.sql
supabase/migrations/20250114000001_fix_shot_generation_rpc_ambiguous_column.sql
supabase/migrations/20250114000002_fix_shot_generation_rpc_columns.sql
supabase/migrations/20250124000000_update_shot_statistics_for_tool_type.sql
supabase/migrations/20250124000001_fix_wan_2_2_i2v_shot_generation_issues.sql
supabase/migrations/20250127000001_fix_task_processing_trigger.sql
supabase/migrations/20250127000002_fix_trigger_for_existing_tasks.sql
supabase/migrations/20250127000003_fix_tasks_array_to_jsonb.sql
supabase/migrations/20250127100000_optimize_shot_generations_performance.sql
supabase/migrations/20250128000000_demote_orphaned_video_variants.sql
supabase/migrations/20250128000001_fix_demote_orphaned_jsonb_extraction.sql
supabase/migrations/20250128000003_demote_rpc_clears_generation.sql
supabase/migrations/20250129000000_make_shot_generations_position_nullable.sql
supabase/migrations/20250130000000_fix_add_generation_to_shot_duplicates.sql
supabase/migrations/20250130000001_fix_add_generation_syntax.sql
supabase/migrations/20250130000003_revert_to_original_rpc.sql
supabase/migrations/20250130000004_fix_rpc_handle_existing_nulls.sql
supabase/migrations/20250130000005_revert_rpc_to_simple.sql
supabase/migrations/20250130000006_restore_original_rpc_with_position.sql
supabase/migrations/20250130000007_update_add_generation_to_shot_check_existing.sql
supabase/migrations/20250130000008_add_debug_to_add_generation_to_shot.sql
supabase/migrations/20250130000009_clean_add_generation_to_shot.sql
supabase/migrations/20250130000010_restore_original_simple_function.sql
supabase/migrations/20250202000003_create_position_existing_generation_function.sql
supabase/migrations/20250202000004_fix_shot_association_position.sql
supabase/migrations/20250203100001_update_generation_trigger_with_thumbnails.sql
supabase/migrations/20250220000000_add_generation_id_index.sql
supabase/migrations/20250221000000_add_create_shot_with_image_function.sql
supabase/migrations/20250713000003_remove_duplicate_generations.sql
supabase/migrations/20250713000004_update_add_generation_to_shot_to_check_existing_null.sql
supabase/migrations/20250713000005_always_check_existing_shot_generation.sql
supabase/migrations/20250713000006_fix_ambiguous_column_reference.sql
supabase/migrations/20250713000007_revert_to_original_function.sql
supabase/migrations/20250724000002_complete_enum_casting_fixes.sql
supabase/migrations/20250822000000_add_safe_jsonb_casting_to_db_trigger.sql
supabase/migrations/20250828000000_add_image_edit_to_generation_trigger.sql
supabase/migrations/20250828000001_update_generation_trigger_for_all_generation_tasks.sql
supabase/migrations/20250829000001_fix_wan_2_2_t2i_tool_type_mapping.sql
supabase/migrations/20250830000000_add_video_gallery_performance_indexes.sql
supabase/migrations/20250902000002_make_generation_trigger_category_based.sql
supabase/migrations/20250902130000_fix_generation_trigger_tool_type_mapping.sql
supabase/migrations/20250902140000_add_tool_type_column_to_task_types.sql
supabase/migrations/20250903000001_add_wan_2_2_i2v_video_task_mapping.sql
supabase/migrations/20250910000001_update_shot_id_extraction_and_positioning.sql
supabase/migrations/20250910000003_fix_add_generation_to_shot_properly.sql
supabase/migrations/20250910000004_fix_rpc_variable_declaration.sql
supabase/migrations/20250910000005_fix_ambiguous_column_reference.sql
supabase/migrations/20250910000006_optimize_add_generation_performance.sql
supabase/migrations/20250910000007_add_shot_generations_indexes.sql
supabase/migrations/20250910000008_fix_ambiguous_columns_in_optimized_rpc.sql
supabase/migrations/20250910000009_use_found_flag_instead_of_null_check.sql
supabase/migrations/20250910000010_handle_concurrent_updates_gracefully.sql
supabase/migrations/20250910000011_fix_trigger_timing_to_prevent_concurrent_updates.sql
supabase/migrations/20250910140000_fix_generation_trigger_tool_type_mapping.sql
supabase/migrations/20250910220001_fix_missing_shot_associations_simple.sql
supabase/migrations/20250910220002_fix_shot_id_extraction_root_cause.sql
supabase/migrations/20250910220003_remove_excessive_security_definer.sql
supabase/migrations/20250910220004_remove_more_security_definer.sql
supabase/migrations/20250910220005_fix_ambiguous_column_references.sql
supabase/migrations/20250910220008_fix_shot_id_variable_ambiguity.sql
supabase/migrations/20250910220010_remove_remaining_security_definers.sql
supabase/migrations/20250910220012_fix_add_generation_to_shot_ambiguity.sql
supabase/migrations/20250911000001_fix_add_in_position_extraction.sql
supabase/migrations/20250915000001_make_new_items_unpositioned_by_default.sql
supabase/migrations/20250915000002_add_automatic_thumbnail_generation.sql
supabase/migrations/20250915000003_add_urls_json_to_generations.sql
supabase/migrations/20250915000005_fix_thumbnail_trigger_without_http.sql
supabase/migrations/20250915000006_extract_thumbnail_from_task_params.sql
supabase/migrations/20250915000008_update_trigger_remove_thumbnail_status.sql
supabase/migrations/20250915191336_fix_result_field_trigger_final.sql
supabase/migrations/20250915200000_fix_generation_trigger_complete.sql
supabase/migrations/20250916000000_fix_thumbnail_extraction_orchestrator_details.sql
supabase/migrations/20250917000000_migrate_generation_creation_to_edge_function.sql
supabase/migrations/20250919000000_add_timeline_positions_to_shot_generations.sql
supabase/migrations/20250919211044_fix_exchange_shot_positions_remove_updated_at.sql
supabase/migrations/20250919221451_recreate_exchange_shot_positions_function.sql
supabase/migrations/20250919221638_fix_exchange_positions_constraint_violation.sql
supabase/migrations/20250919221720_fix_exchange_positions_use_large_temp_value.sql
supabase/migrations/20250922000000_add_apply_timeline_frames_function.sql
supabase/migrations/20250922134600_fix_apply_timeline_frames_ambiguous_column_v2.sql
supabase/migrations/20250922134700_force_recreate_apply_timeline_frames.sql
supabase/migrations/20250922134800_fix_initialize_timeline_frames_race_condition.sql
supabase/migrations/20250922135000_force_drop_all_apply_timeline_frames_versions.sql
supabase/migrations/20250922135100_create_apply_timeline_frames_v2.sql
supabase/migrations/20250922135200_debug_function_state.sql
supabase/migrations/20250922135400_create_atomic_timeline_update_fixed.sql
supabase/migrations/20250922135800_create_atomic_timeline_update_final.sql
supabase/migrations/20250922140000_create_timeline_position_sync_clean.sql
supabase/migrations/20250922140100_create_timeline_sync_bulletproof.sql
supabase/migrations/20250922150000_fix_initialize_timeline_frames_positioning.sql
supabase/migrations/20250922222558_fix_timeline_frames_start_at_zero.sql
supabase/migrations/20250922223317_add_computed_position_column.sql
supabase/migrations/20250922223648_simplify_use_timeline_frame_only.sql
supabase/migrations/20250922225738_migrate_position_to_timeline_frame_simple.sql
supabase/migrations/20250922225918_fix_shot_statistics_view.sql
supabase/migrations/20250922230000_fix_add_generation_to_shot_timeline_frame.sql
supabase/migrations/20250922230843_fix_timeline_sync_bulletproof.sql
supabase/migrations/20250922231500_fix_all_position_references.sql
supabase/migrations/20250922235000_fix_create_shot_with_image_timeline_frame.sql
supabase/migrations/20250922235100_fix_ensure_shot_association_timeline_frame.sql
supabase/migrations/20250922240000_fix_all_database_functions_timeline_frame.sql
supabase/migrations/20250922241000_fix_remaining_position_references.sql
supabase/migrations/20250922251000_fix_timeline_frame_spacing.sql
supabase/migrations/20250922260000_cleanup_video_timeline_frames.sql
supabase/migrations/20250922262000_rerun_video_timeline_cleanup.sql
supabase/migrations/20250922264000_rerun_timeline_reordering.sql
supabase/migrations/20250922270000_disable_timeline_standardization.sql
supabase/migrations/20250923004000_create_update_single_timeline_frame_fn.sql
supabase/migrations/20250923005000_fix_timeline_position_reset.sql
supabase/migrations/20250923006000_disable_timeline_position_reset.sql
supabase/migrations/20250923007000_simple_timeline_fix.sql
supabase/migrations/20250923008000_purge_timeline_standardization.sql
supabase/migrations/20250923009000_final_timeline_fix.sql
supabase/migrations/20250923010000_fix_timeline_sync_bulletproof_user_positions.sql
supabase/migrations/20250923011000_fix_apply_timeline_frames_user_positions.sql
supabase/migrations/20250923012000_fix_exchange_timeline_frames_user_positions.sql
supabase/migrations/20250924002000_remove_user_positioned_constraint_from_exchange.sql
supabase/migrations/20250924003000_remove_timeline_protection_triggers.sql
supabase/migrations/20250924004000_force_remove_all_timeline_protections.sql
supabase/migrations/20250924005000_restore_essential_constraints.sql
supabase/migrations/20250924006000_debug_remaining_blocks.sql
supabase/migrations/20250924008000_add_timeline_update_logging.sql
supabase/migrations/20250924010000_create_debug_timeline_update_function.sql
supabase/migrations/20250924011000_check_live_triggers.sql
supabase/migrations/20250924020000_create_batch_timeline_update_function.sql
supabase/migrations/20250924021000_create_fix_timeline_spacing_function.sql
supabase/migrations/20250924022000_fix_timeline_spacing_function_ambiguous_id.sql
supabase/migrations/20250924023000_fix_timeline_optimal_positioning.sql
supabase/migrations/20250924024000_fix_compact_spacing_formula.sql
supabase/migrations/20250925001000_disable_apply_timeline_frames_drag_overwrite.sql
supabase/migrations/20250925002000_comprehensive_timeline_drag_protection.sql
supabase/migrations/20250925006000_diagnose_duplicates.sql
supabase/migrations/20250926001000_add_drag_session_logging.sql
supabase/migrations/20250926003000_fix_exchange_timeline_frames_use_shot_generation_ids.sql
supabase/migrations/20251010000000_fix_add_generation_position_logic.sql
supabase/migrations/20251010000001_fix_ambiguous_id_in_add_generation.sql
supabase/migrations/20251016000000_create_shared_generations.sql
supabase/migrations/20251016000001_add_missing_rls_policies.sql
supabase/migrations/20251023000000_add_shot_generations_to_realtime.sql
supabase/migrations/20251114000000_fix_video_count_to_match_display.sql
supabase/migrations/20251118000001_fix_shot_data_trigger.sql
supabase/migrations/20251118000006_bulletproof_trigger.sql
supabase/migrations/20251120134059_add_child_generation_support_v2.sql
supabase/migrations/20251126000000_add_batch_update_timeline_frames.sql
supabase/migrations/20251201000000_create_generation_variants_table.sql
supabase/migrations/20251201000001_migrate_existing_generations_to_variants.sql
supabase/migrations/20251201000002_create_variant_sync_triggers.sql
supabase/migrations/20251201000003_remove_upscaled_url.sql
supabase/migrations/20251204000000_add_project_id_to_generation_variants.sql
supabase/migrations/20251209000000_add_duplicate_shot_function.sql
supabase/migrations/20251209000001_fix_shot_data_sync.sql
supabase/migrations/20251209110000_allow_duplicate_generations_in_shot.sql
supabase/migrations/20251211000000_fix_variant_deletion_trigger.sql
supabase/migrations/20251211000001_fix_variant_deletion_fk.sql
supabase/migrations/20251212000000_enable_rls_on_projects_and_shots.sql
supabase/migrations/20251218100000_dynamic_timeline_spacing.sql
supabase/migrations/20251218110000_update_default_spacing_to_81.sql
supabase/migrations/20251221000002_migrate_shot_data_to_array_format.sql
supabase/migrations/20251228000000_add_viewed_at_to_variants.sql
supabase/migrations/20251228000001_auto_view_manual_uploads.sql
supabase/migrations/20260104000002_copy_onboarding_template_function.sql
supabase/migrations/20260104000003_add_admin_template_copy.sql
supabase/migrations/20260105000001_update_copy_onboarding_extract_settings.sql
supabase/migrations/20260113000000_fix_duplicate_shot_exclude_videos.sql
supabase/migrations/20260116110000_fix_final_video_count_require_location.sql
supabase/migrations/20260118000000_disable_auto_variant_trigger.sql
supabase/migrations/20260118000001_update_onboarding_copy_create_variants.sql
supabase/migrations/20260123000000_fix_final_video_count_include_join_clips.sql
supabase/migrations/20260123000001_shot_final_videos_view.sql
supabase/migrations/20260123100000_fix_final_video_count_match_display_logic.sql
supabase/migrations/20260123200000_add_pair_shot_generation_id_column.sql
supabase/migrations/20260125_migrate_settings_field_names.sql
supabase/migrations/20260126000000_fix_shot_data_to_array_format.sql
supabase/migrations/20260128000000_add_live_share_data.sql
supabase/migrations/20260128000002_fix_share_data_normalized.sql
supabase/migrations/20260128000003_simplify_share_data.sql
supabase/migrations/20260128000004_add_raw_settings_debug.sql
supabase/migrations/20260128000005_fix_settings_key_name.sql
supabase/migrations/20260128000006_include_all_generations.sql
supabase/migrations/20260128000007_raw_settings_passthrough.sql
supabase/migrations/20260128000008_add_parent_generation_id.sql
supabase/migrations/20260128000009_include_segment_children.sql
supabase/migrations/20260128000010_include_structure_video.sql
supabase/migrations/20260128000011_structure_videos_array.sql
supabase/migrations/20260129100000_fix_add_generation_to_shot_security.sql
supabase/migrations/20260130000000_add_timeline_normalization_rpcs.sql
supabase/migrations/20260130200000_security_audit_fixes.sql
supabase/migrations/20260130230000_critical_fix_view_security.sql
supabase/migrations/20260209000000_add_starred_to_generation_variants.sql
supabase/migrations/20260213300000_schedule_shot_sync_check.sql
supabase/migrations/20260218143000_ensure_shot_parent_generation.sql
supabase/migrations/20260218163000_optimize_timeline_batch_updates.sql
supabase/migrations/20260218175000_batch_trigger_for_timeline_updates.sql
supabase/migrations/20260218180000_fix_broken_shot_generation_triggers.sql
supabase/migrations/20260218185000_per_statement_update_trigger.sql
supabase/migrations/20260218190000_index_shot_generations_generation_id.sql
supabase/migrations/20260218200000_nonblocking_shot_data_update_trigger.sql
supabase/migrations/20260218210000_drop_blocking_before_update_triggers.sql
supabase/migrations/20260223200000_demote_rpc_handles_null_timeline_frame.sql
supabase/migrations/20260224000000_auto_demote_trigger.sql
supabase/migrations/20260224000001_fix_demote_preserves_primary_variant.sql
supabase/migrations/20260224000002_backfill_orphaned_primary_variants.sql
supabase/migrations/20260330000000_protect_original_variant_deletion.sql
supabase/migrations/20260330000001_diagnose_pair_shot_generation_backfill_mismatches.sql
supabase/migrations/20260330000002_null_misbackfilled_pair_shot_generation_id.sql
supabase/migrations/20260406_create_shot_with_generations.sql
supabase/migrations/20260407000000_duplicate_as_new_generation.sql
supabase/migrations/20260407010000_remove_target_timeline_frame_from_duplicate_as_new_generation.sql
supabase/migrations/20260411000000_fix_original_variant_deletion_cascade.sql
supabase/migrations/20260413110000_add_generation_id_to_resources.sql
supabase/migrations/20260414093000_expose_variant_fetch_generation_id_on_shot_final_videos.sql
supabase/migrations/20260414103000_add_duration_seconds_to_shot_final_videos.sql
supabase/migrations/20260414120000_expand_shot_final_video_duration_parsing.sql
supabase/migrations/20260505012055_add_materialized_inputs_to_tasks.sql
supabase/migrations/20260508160000_add_duplicate_shot_with_videos.sql
supabase/migrations/_applied_20260225000000_backfill_pair_shot_generation_id.sql
supabase/migrations/_hold_20251218000000_dynamic_timeline_spacing.sql
supabase/migrations/_hold_20260414_shot_final_videos_single_segment_identity.sql
```

## supabase/tests/

Hit-file count: 2

```text
supabase/tests/duplicate_shot_with_videos.test.sql
supabase/tests/original_variant_deletion.test.sql
```

## scripts/

Hit-file count: 4

```text
scripts/debug/client.py
scripts/debug/commands/context.py
scripts/debug/formatters.py
scripts/quality/check-supabase-rls.mjs
```

## docs/

Hit-file count: 8

```text
docs/slot-first-audits/01-grep-ledger.md
docs/structure_detail/data_fetching.md
docs/structure_detail/db_and_storage.md
docs/structure_detail/edge_functions.md
docs/structure_detail/per_pair_data_persistence.md
docs/structure_detail/realtime_system.md
docs/structure_detail/task_worker_lifecycle.md
docs/structure_detail/tool_video_travel.md
```

## tasks/

Hit-file count: 10

```text
tasks/2025-02-13-code-review-remediation.md
tasks/2026-02-01-cache-invalidation-refactor.md
tasks/2026-02-01-useShots-refactor.md
tasks/2026-02-02-handler-types-consolidation.md
tasks/2026-02-02-useSegmentSettings-refactor.md
tasks/2026-02-03-any-type-cleanup.md
tasks/2026-02-10-cruft-deep.md
tasks/2026-03-07-desloppify-to-95.md
tasks/2026-03-10-agent-task-creation-architecture.md
tasks/2026-03-18-unify-travel-guidance.md
```

## .megaplan/

Hit-file count: 28

```text
.megaplan/debt.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_output.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v1.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v2.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/critique_v3.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/faults.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/final.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/finalize.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/finalize_snapshot.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v1.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v2.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/gate_signals_v3.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v1.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v1.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v2.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v2.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v3.md
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/plan_v3.meta.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/state.json
.megaplan/plans/slot-first-redesign-milestone-20260519-2026/step_receipt_plan_v1.json
.megaplan/slot-first-m0-preflight-idea.md
.megaplan/slot-first-m1-schema-idea.md
.megaplan/slot-first-m2-frontend-idea.md
.megaplan/slot-first-m3a-worker-contract-idea.md
.megaplan/slot-first-m3b-edge-functions-idea.md
.megaplan/slot-first-m3c-astrid-share-idea.md
.megaplan/slot-first-m4-cutover-idea.md
```

## root/other

Hit-file count: 2

```text
.cursorrules
chain.yaml
```

