# Slot-First M0 Audit 02: Second-Slot Question

Generated: 2026-05-20T09:40:30Z

## Decision

Decision: `shot_slots` replaces `shot_generations` as the one shot-local placement table. M1 must not create a second `shot_generations` successor table and must not add a `kind` discriminator that preserves the old overload. Work/output identity moves to `attempt_id`; media identity can be represented by optional `clip_id`; shot-local ordering, prompt metadata, duplicate placement, and timeline frame ownership live on `slot_id`.

The current audit did not find a distinct second concept hiding behind `shot_generations`. The same table is used as a shot-local entry identity in UI code, as the timeline ordering record in mutation/RPC code, as the pair prompt metadata holder in segment settings, and as a fallback way for Astrid/edge functions to infer shot membership from a generation. Those are all placement concerns. The pieces that look like output lineage are not a reason for a second table; they are attempts and optional clips attached to slots.

## Commands

Caller inventory command:
```bash
rg -l "shot_generations" src supabase/functions supabase/migrations supabase/tests scripts tasks | sort
```

Total caller/reference files in runtime, migration, test, script, and task surfaces: 279

Bucket counts:

| Bucket | Count |
| --- | ---: |
| `src/` | 86 |
| `supabase/functions/` | 11 |
| `supabase/migrations/` | 173 |
| `supabase/tests/` | 1 |
| `scripts/` | 3 |
| `tasks/` | 5 |

Sibling repository command:
```bash
rg -l "shot_generations" /workspace/reigh-worker /workspace/reigh-worker-orchestrator /workspace/Astrid 2>/dev/null | sort || true
```

Sibling output:
```
/workspace/reigh-worker/source/task_handlers/travel/orchestrator.py
```

Standalone Astrid has no direct `shot_generations` table reference in the mounted checkout, but T13 shows it consumes `reigh-data-fetch`; that edge function exports `shot_generations`-derived rows and is therefore an indirect timeline-placement contract for M3.

## Caller Classification Summary

| Surface | Classification | Evidence | Later owner |
| --- | --- | --- | --- |
| Shot image/gallery rows | timeline-placement | UI comments repeatedly treat `id` as `shot_generations.id`, unique per entry, while `generation_id` points to the reusable underlying generation. | M2 |
| Timeline reorder/frame mutations | timeline-placement | `useTimelineCore`, `timelineDropHelpers`, batch persist, realtime invalidation, and RPC migrations update `timeline_frame` or order by shot-local entry id. | M2/M3 |
| Segment settings and prompt overrides | segment-composition | Segment settings store prompt/override metadata on the shot-local pair record, usually named `pairShotGenerationId`. | M2/M3 |
| Final-video and duplicate-shot SQL | segment-composition | Views/tests count video outputs and copy paired shot entries from legacy `shot_generations`. | M1/M4 |
| Astrid clip resolution | timeline-placement | `ai-timeline-agent/tools/clips.ts` resolves selected clips to a shot by generation membership and creates shot membership rows. | M3 |
| Worker prompt enrichment | segment-composition | Worker comments call `update-shot-pair-prompts`, which writes enhanced prompts to shot-local entries. | M3 |

## File Inventory By Bucket

### `src/` (86)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `src/domains/generation/types/generationMetadata.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/generation/types/generationRow.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/generation/types/generationRowDto.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/inpainting/useTaskGeneration.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useGenerationLineage.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useImg2ImgMode.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useLightboxVideoMode.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useMagicEditMode.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useMakeMainVariant.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useShotCreation.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useShotPositioning.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useStarToggle.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/domains/media-lightbox/hooks/useVariantPromotion.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/features/tasks/components/TasksPane/utils/task-utils.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/integrations/supabase/repositories/segmentGenerationPersistenceRepository.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/integrations/supabase/types.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ImageGenerationForm/hooks/referenceUpload/referenceDomainService.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/MediaGallery/types.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/SegmentSettingsForm/segmentSettingsMigration.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/ShotBatchItemDesktop.tsx` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/ShotBatchItemMobile.tsx` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/ShotImageManagerMobile.tsx` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/components/ImageGrid.tsx` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/hooks/useDragAndDrop.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/hooks/useMobileGestures.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/hooks/useOptimisticOrder.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/hooks/useSelection.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/utils/__tests__/external-generation-utils.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/utils/external-generation-utils.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/components/ShotImageManager/utils/reorder-utils.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/__tests__/useShareGeneration.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/__tests__/useShotCreation.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/gallery/useVideoGalleryPreloader.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/segments/__tests__/segmentOutputsQueries.test.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/segments/__tests__/useSegmentMutations.test.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/segments/segmentOutputsQueries.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/segments/usePairMetadata.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/segments/useSegmentMutations.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shotCreation/shotCreationPaths.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shotCreation/shotCreationPaths.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shotCreation/shotCreationTypes.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/__tests__/mappers.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/__tests__/useShotGenerationMutations.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/__tests__/useShotsQueries.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/addImageToShotHelpers.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/mappers.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/useShotGenerationMetadata.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/useShotGenerationMutations.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/useShotImages.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/shots/useShotsQueries.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/sourceImageChanges/__tests__/dataAccess.test.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/sourceImageChanges/dataAccess.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/tasks/usePendingSegmentTasks.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/timelineFrameCalculators.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/timelineMutationService.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineCore.enhancedPromptOperations.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineCore.enhancedPromptOperations.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineCore.pairOperations.test.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineCore.pairOperations.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineCore.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/timeline/useTimelineFrameUpdates.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/usePendingImageOpen.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/useRealtimeInvalidation.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/hooks/useShareGeneration.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/lib/generationTransformers.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/lib/settingsMigration.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/lib/tasks/__tests__/segmentGenerationPersistence.test.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/lib/timelineFrameBatchPersist.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/realtime/RealtimeConnection.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/realtime/RealtimeEventProcessor.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/realtime/__tests__/RealtimeEventProcessor.test.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/realtime/types.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/shared/types/segmentSettings.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/hooks/actions/useDeleteActions.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/hooks/actions/useDropActions.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/hooks/editor-state/timelineDropHelpers.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/hooks/video/useLastVideoGeneration.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/services/applySettings/imageService.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/services/generateVideo/pairPayload.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotEditor/services/generateVideoService.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/ShotImagesEditor/hooks/useFrameCountUpdater.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/Timeline/hooks/segment/timelineTrailingEndpointPersistence.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/components/Timeline/index.tsx` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/hooks/settings/useSegmentPromptMetadata.ts` | segment-composition | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/hooks/timeline/useEnhancedShotImageReorder.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |
| `src/tools/travel-between-images/hooks/workflow/useDemoteOrphanedVariants.ts` | timeline-placement | M2 rewrites frontend state/query/mutation surface to slot-first nouns. |

### `supabase/functions/` (11)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `supabase/functions/_tests/harness/cases.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/_tests/harness/evaluate.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/_tests/harness/fixtures.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/_tests/harness/snapshot.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/ai-timeline-agent/tools/clips.test.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/ai-timeline-agent/tools/clips.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/ai-timeline-agent/tools/duplicate-generation.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/complete_task/generation-child.ts` | segment-composition | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/reigh-data-fetch/index.test.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/reigh-data-fetch/index.ts` | timeline-placement | M3 rewrites edge-function contract and tests to slots/attempts. |
| `supabase/functions/update-shot-pair-prompts/index.ts` | segment-composition | M3 rewrites edge-function contract and tests to slots/attempts. |

### `supabase/migrations/` (173)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `supabase/migrations/20250100000000_create_base_schema.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250107_add_shot_denormalization.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250114000000_add_shot_generation_rpc.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250114000001_fix_shot_generation_rpc_ambiguous_column.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250114000002_fix_shot_generation_rpc_columns.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250124000000_update_shot_statistics_for_tool_type.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250127000001_fix_task_processing_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250127000002_fix_trigger_for_existing_tasks.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250127000003_fix_tasks_array_to_jsonb.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250127100000_optimize_shot_generations_performance.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250128000000_demote_orphaned_video_variants.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250128000001_fix_demote_orphaned_jsonb_extraction.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250128000003_demote_rpc_clears_generation.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250129000000_make_shot_generations_position_nullable.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000000_fix_add_generation_to_shot_duplicates.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000001_fix_add_generation_syntax.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000003_revert_to_original_rpc.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000004_fix_rpc_handle_existing_nulls.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000005_revert_rpc_to_simple.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000006_restore_original_rpc_with_position.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000007_update_add_generation_to_shot_check_existing.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000008_add_debug_to_add_generation_to_shot.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000009_clean_add_generation_to_shot.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250130000010_restore_original_simple_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250202000003_create_position_existing_generation_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250220000000_add_generation_id_index.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250221000000_add_create_shot_with_image_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250713000003_remove_duplicate_generations.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250713000004_update_add_generation_to_shot_to_check_existing_null.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250713000005_always_check_existing_shot_generation.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250713000006_fix_ambiguous_column_reference.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250713000007_revert_to_original_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250830000000_add_video_gallery_performance_indexes.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000003_fix_add_generation_to_shot_properly.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000004_fix_rpc_variable_declaration.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000005_fix_ambiguous_column_reference.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000006_optimize_add_generation_performance.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000007_add_shot_generations_indexes.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000008_fix_ambiguous_columns_in_optimized_rpc.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000009_use_found_flag_instead_of_null_check.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910000010_handle_concurrent_updates_gracefully.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910140000_fix_generation_trigger_tool_type_mapping.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220001_fix_missing_shot_associations_simple.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220003_remove_excessive_security_definer.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220004_remove_more_security_definer.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220005_fix_ambiguous_column_references.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220010_remove_remaining_security_definers.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250910220012_fix_add_generation_to_shot_ambiguity.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250919000000_add_timeline_positions_to_shot_generations.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250919211044_fix_exchange_shot_positions_remove_updated_at.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250919221451_recreate_exchange_shot_positions_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250919221638_fix_exchange_positions_constraint_violation.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250919221720_fix_exchange_positions_use_large_temp_value.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922000000_add_apply_timeline_frames_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922134600_fix_apply_timeline_frames_ambiguous_column_v2.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922134700_force_recreate_apply_timeline_frames.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922134800_fix_initialize_timeline_frames_race_condition.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922135000_force_drop_all_apply_timeline_frames_versions.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922135100_create_apply_timeline_frames_v2.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922135200_debug_function_state.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922135400_create_atomic_timeline_update_fixed.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922135800_create_atomic_timeline_update_final.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922140000_create_timeline_position_sync_clean.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922140100_create_timeline_sync_bulletproof.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922150000_fix_initialize_timeline_frames_positioning.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922222558_fix_timeline_frames_start_at_zero.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922223317_add_computed_position_column.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922223648_simplify_use_timeline_frame_only.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922225738_migrate_position_to_timeline_frame_simple.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922225918_fix_shot_statistics_view.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922230000_fix_add_generation_to_shot_timeline_frame.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922230843_fix_timeline_sync_bulletproof.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922231500_fix_all_position_references.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922235000_fix_create_shot_with_image_timeline_frame.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922235100_fix_ensure_shot_association_timeline_frame.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922240000_fix_all_database_functions_timeline_frame.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922241000_fix_remaining_position_references.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922251000_fix_timeline_frame_spacing.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922260000_cleanup_video_timeline_frames.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922262000_rerun_video_timeline_cleanup.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922264000_rerun_timeline_reordering.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250922270000_disable_timeline_standardization.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923004000_create_update_single_timeline_frame_fn.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923005000_fix_timeline_position_reset.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923006000_disable_timeline_position_reset.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923007000_simple_timeline_fix.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923008000_purge_timeline_standardization.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923009000_final_timeline_fix.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923010000_fix_timeline_sync_bulletproof_user_positions.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923011000_fix_apply_timeline_frames_user_positions.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250923012000_fix_exchange_timeline_frames_user_positions.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924002000_remove_user_positioned_constraint_from_exchange.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924003000_remove_timeline_protection_triggers.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924004000_force_remove_all_timeline_protections.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924005000_restore_essential_constraints.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924006000_debug_remaining_blocks.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924008000_add_timeline_update_logging.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924010000_create_debug_timeline_update_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924011000_check_live_triggers.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924020000_create_batch_timeline_update_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924021000_create_fix_timeline_spacing_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924022000_fix_timeline_spacing_function_ambiguous_id.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924023000_fix_timeline_optimal_positioning.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250924024000_fix_compact_spacing_formula.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250925002000_comprehensive_timeline_drag_protection.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250925006000_diagnose_duplicates.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250926001000_add_drag_session_logging.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20250926003000_fix_exchange_timeline_frames_use_shot_generation_ids.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251010000000_fix_add_generation_position_logic.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251010000001_fix_ambiguous_id_in_add_generation.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251023000000_add_shot_generations_to_realtime.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251114000000_fix_video_count_to_match_display.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251118000001_fix_shot_data_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251118000006_bulletproof_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251126000000_add_batch_update_timeline_frames.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251209000000_add_duplicate_shot_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251209000001_fix_shot_data_sync.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251209110000_allow_duplicate_generations_in_shot.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251212000000_enable_rls_on_projects_and_shots.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251218100000_dynamic_timeline_spacing.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251218110000_update_default_spacing_to_81.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20251221000002_migrate_shot_data_to_array_format.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260104000002_copy_onboarding_template_function.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260104000003_add_admin_template_copy.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260105000001_update_copy_onboarding_extract_settings.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260113000000_fix_duplicate_shot_exclude_videos.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260116110000_fix_final_video_count_require_location.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260118000001_update_onboarding_copy_create_variants.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260123000000_fix_final_video_count_include_join_clips.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260123000001_shot_final_videos_view.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260123100000_fix_final_video_count_match_display_logic.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260123200000_add_pair_shot_generation_id_column.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260125_migrate_settings_field_names.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260126000000_fix_shot_data_to_array_format.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000000_add_live_share_data.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000002_fix_share_data_normalized.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000003_simplify_share_data.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000004_add_raw_settings_debug.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000005_fix_settings_key_name.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000006_include_all_generations.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000007_raw_settings_passthrough.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000008_add_parent_generation_id.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000009_include_segment_children.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000010_include_structure_video.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260128000011_structure_videos_array.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260129100000_fix_add_generation_to_shot_security.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260130000000_add_timeline_normalization_rpcs.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260130200000_security_audit_fixes.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260130230000_critical_fix_view_security.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260213300000_schedule_shot_sync_check.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218143000_ensure_shot_parent_generation.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218163000_optimize_timeline_batch_updates.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218175000_batch_trigger_for_timeline_updates.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218180000_fix_broken_shot_generation_triggers.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218185000_per_statement_update_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218190000_index_shot_generations_generation_id.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218200000_nonblocking_shot_data_update_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260218210000_drop_blocking_before_update_triggers.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260223200000_demote_rpc_handles_null_timeline_frame.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260224000000_auto_demote_trigger.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260224000001_fix_demote_preserves_primary_variant.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260330000001_diagnose_pair_shot_generation_backfill_mismatches.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260330000002_null_misbackfilled_pair_shot_generation_id.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260406_create_shot_with_generations.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260407000000_duplicate_as_new_generation.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260407010000_remove_target_timeline_frame_from_duplicate_as_new_generation.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260414093000_expose_variant_fetch_generation_id_on_shot_final_videos.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260414103000_add_duration_seconds_to_shot_final_videos.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260414120000_expand_shot_final_video_duration_parsing.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/20260508160000_add_duplicate_shot_with_videos.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/_applied_20260225000000_backfill_pair_shot_generation_id.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/_hold_20251218000000_dynamic_timeline_spacing.sql` | timeline-placement | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |
| `supabase/migrations/_hold_20260414_shot_final_videos_single_segment_identity.sql` | segment-composition | M1/M4 migration cutover consumes or drops this legacy SQL; see 01-migration-ledger for object survival. |

### `supabase/tests/` (1)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `supabase/tests/duplicate_shot_with_videos.test.sql` | segment-composition | M4 rewrites or deletes DB fixture after cutover. |

### `scripts/` (3)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `scripts/debug/client.py` | timeline-placement | M4 rewrites, disables, or deletes active debug/quality client surface. |
| `scripts/debug/commands/context.py` | timeline-placement | M4 rewrites, disables, or deletes active debug/quality client surface. |
| `scripts/quality/check-supabase-rls.mjs` | timeline-placement | M4 rewrites, disables, or deletes active debug/quality client surface. |

### `tasks/` (5)

| File | Classification | M0 disposition |
| --- | --- | --- |
| `tasks/2026-02-02-handler-types-consolidation.md` | timeline-placement | Reference-only planning note; no runtime code path. |
| `tasks/2026-02-02-useSegmentSettings-refactor.md` | segment-composition | Reference-only planning note; no runtime code path. |
| `tasks/2026-02-03-any-type-cleanup.md` | timeline-placement | Reference-only planning note; no runtime code path. |
| `tasks/2026-03-10-agent-task-creation-architecture.md` | timeline-placement | Reference-only planning note; no runtime code path. |
| `tasks/2026-03-18-unify-travel-guidance.md` | timeline-placement | Reference-only planning note; no runtime code path. |

## What The Callers Mean

The overloaded legacy table currently carries four separate meanings:

1. Shot-local placement identity: `shot_generations.id` is the stable row identity used for selection, deletion, drag/drop, realtime invalidation, and timeline frame updates.
2. Underlying generated media identity: `shot_generations.generation_id` points to a reusable `generations.id`; several comments already warn that these are not the same id.
3. Segment pair metadata: `shot_generations.metadata.segmentOverrides` and `enhanced_prompt` store prompt choices for the transition starting at a positioned image.
4. Legacy output lookup: final-video views and duplicate helpers infer video output/state by joining through the shot-local placement table.

Only the first and third meanings need to remain on a shot-local table. The second and fourth become attempt/clip relationships, not a new placement table.

## Adversarial Fixtures

| Fixture | Legacy ambiguity | Slot-first behavior |
| --- | --- | --- |
| Same generation in multiple positions | Existing duplicate handling has repeatedly changed because `generation_id` could be treated as unique per shot even when UI needs multiple entries. | Create two `shot_slots` rows with different `slot_id`/position values. They may point to the same source attempt or clip. Uniqueness applies to slot position, not generation output. |
| Share-copy | Shared media and copied shots can carry old `generation_id` and `shot_generations.id` assumptions into a new project/shot. | Copy creates new slots in the target shot and either references copied attempts/clips or creates explicit derived attempts. No legacy id is preserved as an alias. |
| Drag-drop reorder | Timeline code updates `timeline_frame` on `shot_generations.id`; code comments emphasize the entry id must be unique per row. | Reorder updates `shot_slots.position`/`timeline_frame` on `slot_id`. Attempt and clip identity are untouched. |
| Astrid duplicate | Astrid looks up `shot_generations` by `generation_id`, then calls `duplicate_as_new_generation` and returns `new_generation_id`. | Astrid resolves a selected `slot_id`, duplicates or creates a new `attempt_id`, and optionally places it in a new `shot_slots` row. No `new_generation_id` contract survives. |

## M1 Schema Statement

M1 schema statement: `public.shot_slots` is the sole successor for `public.shot_generations`. The public identity exposed to application and service contracts is `slot_id` (the table primary key). The table owns `project_id`, `shot_id`, ordering/frame columns, and slot-local metadata. Generated work is linked by `attempt_id` and rendered media by optional `clip_id`; neither is an alias for `generation_id`.

Required constraints for M1 to encode from this decision:

- `shot_slots.id` is `slot_id`; `shot_id` and `project_id` are required and must agree with shot ownership.
- A positioned shot slot must be unique in its shot by the new ordering coordinate. M1 should use a database constraint or trigger, not a comment.
- A slot can point at zero or one current `attempt_id` depending on lifecycle state; attempts can be replaced without changing slot identity.
- Segment prompt metadata belongs to the originating `slot_id` or to an explicit transition/attempt child object if M1 introduces one. It must not recreate `pair_shot_generation_id`.
- Final video state is derived from attempts/clips attached to slots, not from a second `shot_generations` table.
- No compatibility aliases are created for `generation_id`, `shot_generation_id`, `pair_shot_generation_id`, `parent_generation_id`, `child_generation_id`, `variant_id`, or `primary_variant_id`.

Illustrative shape, not a migration in M0:

```sql
-- M1 owns exact SQL. This is the contract-level shape M0 decides.
public.shot_slots (
  id uuid primary key,              -- slot_id in service contracts
  project_id uuid not null,
  shot_id uuid not null,
  position integer null,
  timeline_frame integer null,
  current_attempt_id uuid null,
  clip_id uuid null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null
)
```

## Consequence For M1-M4

M1 builds `shot_slots` and attempt lifecycle tables around this decision. M2 rewrites frontend callers that currently distinguish `shot_generations.id` from `generation_id`. M3 rewrites edge, Astrid, worker, and orchestrator contracts around `slot_id`/`attempt_id`. M4 drops `shot_generations` and verifies there are no compatibility aliases or sibling-worktree references left.
