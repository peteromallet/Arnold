import { useCallback, useRef } from 'react';
import { toast } from "@/shared/components/ui/runtime/sonner";
import { normalizeAndPresentError } from "@/shared/lib/errorHandling/runtimeError";
import { GenerationRow, Shot } from "@/domains/generation/types";
import { useProjectCrudContext } from "@/shared/contexts/ProjectContext";
import {
  useAddImageToShot,
  useHandleExternalImageDrop,
  useUpdateShotAspectRatio,
} from "@/shared/hooks/shots";
import { useQueryClient } from '@tanstack/react-query';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import {
  cropImagesToShotAspectRatio,
  fetchNextAvailableFrameForShot,
  persistTimelinePositions
} from '../editor-state/timelineDropHelpers';
import { DEFAULT_FRAME_SPACING } from '@/shared/lib/timelinePositionCalculator';
import { generationQueryKeys } from '@/shared/lib/queryKeys/generations';
import { useDemoteOrphanedVariants } from '../../../../hooks/workflow/useDemoteOrphanedVariants';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { findClosestAspectRatio } from '@/shared/lib/media/aspectRatios';
import { VARIANT_TYPE } from '@/shared/constants/variantTypes';
import { enqueueVariantInvalidation } from '@/shared/hooks/invalidation/useGenerationInvalidation';
import { uploadImageForVariant } from '@/shared/lib/media/createGenerationFromFile';
import type { VariantDropParams } from '@/shared/hooks/dnd/useImageVariantDrop';
import type { ShotEditorActions } from '../../state/useShotEditorState';

interface UseDropActionsProps {
  actions: Pick<ShotEditorActions, 'setUploadingImage' | 'setAutoAdjustedAspectRatio'>;
  selectedShot: Shot;
  projectId: string;
  batchVideoFrames: number;
}

type ProjectWithSettings = {
  id: string;
  aspectRatio?: string;
  settings?: {
    aspectRatio?: string;
  };
};

type AutoAdjustedAspectRatio = NonNullable<
  ShotEditorActions extends { setAutoAdjustedAspectRatio: (value: infer TValue) => void }
    ? TValue
    : never
>;

async function readImageDimensions(file: File): Promise<{ width: number; height: number } | null> {
  try {
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (event) => {
        const img = new Image();

        img.onload = () => {
          resolve({ width: img.width, height: img.height });
        };

        img.onerror = () => {
          reject(new Error('Failed to load dropped image.'));
        };

        if (event.target?.result) {
          img.src = event.target.result as string;
          return;
        }

        reject(new Error('Failed to read dropped image.'));
      };

      reader.onerror = () => {
        reject(new Error('Failed to probe dropped image dimensions.'));
      };

      reader.readAsDataURL(file);
    });
  } catch (error) {
    normalizeAndPresentError(error, {
      context: 'DropAutoAdjustShotAspectRatio:probe',
      showToast: false,
    });
    return null;
  }
}

async function maybeAutoAdjustShotAspectRatio(
  files: File[],
  currentShot: Shot,
  projectsList: ProjectWithSettings[],
  projectId: string,
): Promise<AutoAdjustedAspectRatio | null> {
  try {
    const firstFile = files[0];
    if (!firstFile) {
      return null;
    }

    const dimensions = await readImageDimensions(firstFile);
    if (!dimensions?.width || !dimensions.height) {
      return null;
    }

    const imageRatio = dimensions.width / dimensions.height;
    const closestAspectRatio = findClosestAspectRatio(imageRatio);
    const currentProject = projectsList.find((project) => project.id === projectId);
    const currentAspectRatio =
      currentShot.aspect_ratio ??
      currentProject?.aspectRatio ??
      currentProject?.settings?.aspectRatio ??
      '16:9';

    if (closestAspectRatio === currentAspectRatio) {
      return null;
    }

    return {
      previousAspectRatio: currentShot.aspect_ratio ?? null,
      adjustedTo: closestAspectRatio,
    };
  } catch (error) {
    normalizeAndPresentError(error, {
      context: 'DropAutoAdjustShotAspectRatio',
      showToast: false,
    });
    return null;
  }
}

export const useDropActions = ({
  actions,
  selectedShot,
  projectId,
  batchVideoFrames,
}: UseDropActionsProps) => {
  const { projects } = useProjectCrudContext();
  const queryClient = useQueryClient();
  const addImageToShotMutation = useAddImageToShot();
  const handleExternalImageDropMutation = useHandleExternalImageDrop();
  const { updateShotAspectRatio } = useUpdateShotAspectRatio();
  const { demoteOrphanedVariants } = useDemoteOrphanedVariants();
  const { settings: uploadSettings } = useToolSettings<{ cropToProjectSize?: boolean }>(SETTINGS_IDS.UPLOAD, { projectId });

  // Stability refs - prevent callback recreation when data/mutation state changes
  const selectedShotRef = useRef(selectedShot);
  selectedShotRef.current = selectedShot;

  const projectIdRef = useRef(projectId);
  projectIdRef.current = projectId;

  const batchVideoFramesRef = useRef(batchVideoFrames);
  batchVideoFramesRef.current = batchVideoFrames;

  const projectsRef = useRef(projects);
  projectsRef.current = projects;

  const uploadSettingsRef = useRef(uploadSettings);
  uploadSettingsRef.current = uploadSettings;

  const actionsRef = useRef(actions);
  actionsRef.current = actions;

  const setAutoAdjustedAspectRatioRef = useRef(actions.setAutoAdjustedAspectRatio);
  setAutoAdjustedAspectRatioRef.current = actions.setAutoAdjustedAspectRatio;

  const addImageToShotMutationRef = useRef(addImageToShotMutation);
  addImageToShotMutationRef.current = addImageToShotMutation;

  const handleExternalImageDropMutationRef = useRef(handleExternalImageDropMutation);
  handleExternalImageDropMutationRef.current = handleExternalImageDropMutation;

  const updateShotAspectRatioRef = useRef(updateShotAspectRatio);
  updateShotAspectRatioRef.current = updateShotAspectRatio;

  const queryClientRef = useRef(queryClient);
  queryClientRef.current = queryClient;

  const demoteOrphanedVariantsRef = useRef(demoteOrphanedVariants);
  demoteOrphanedVariantsRef.current = demoteOrphanedVariants;

  /**
   * Handle dropping external image files onto the timeline
   */
  const handleTimelineImageDrop = useCallback(async (files: File[], targetFrame?: number) => {
    const currentShot = selectedShotRef.current;
    const currentProjectId = projectIdRef.current;
    const currentBatchVideoFrames = batchVideoFramesRef.current;
    let adjustedShot: Shot | undefined;

    if (!currentShot?.id || !currentProjectId) {
      toast.error("Cannot add images: No shot or project selected.");
      return;
    }

    try {
      try {
        const autoAdjustedAspectRatio = await maybeAutoAdjustShotAspectRatio(
          files,
          currentShot,
          projectsRef.current as ProjectWithSettings[],
          currentProjectId
        );

        if (autoAdjustedAspectRatio) {
          const ok = await updateShotAspectRatioRef.current(
            currentShot.id,
            currentProjectId,
            autoAdjustedAspectRatio.adjustedTo,
            { immediate: true }
          );

          if (ok) {
            setAutoAdjustedAspectRatioRef.current(autoAdjustedAspectRatio);
            adjustedShot = {
              ...currentShot,
              aspect_ratio: autoAdjustedAspectRatio.adjustedTo,
            };
          } else {
            normalizeAndPresentError(
              new Error('Failed to auto-adjust shot aspect ratio for the dropped image.'),
              {
                context: 'DropAutoAdjustShotAspectRatio:update',
                showToast: false,
                logData: {
                  shotId: currentShot.id,
                  adjustedTo: autoAdjustedAspectRatio.adjustedTo,
                },
              }
            );
          }
        }
      } catch (error) {
        normalizeAndPresentError(error, {
          context: 'DropAutoAdjustShotAspectRatio:update',
          showToast: false,
          logData: { shotId: currentShot.id },
        });
      }

      actionsRef.current.setUploadingImage(true);

      // 1. Calculate target positions BEFORE upload
      const calculatedTargetFrame = await fetchNextAvailableFrameForShot(
        currentShot.id,
        targetFrame
      );

      // 2. Crop images to shot aspect ratio
      const processedFiles = await cropImagesToShotAspectRatio(
        files,
        adjustedShot ?? currentShot,
        currentProjectId,
        projectsRef.current,
        uploadSettingsRef.current
      );

      // 3. Calculate positions for each file
      const positions = processedFiles.map((_, index) =>
        calculatedTargetFrame + (index * currentBatchVideoFrames)
      );

      // 4. Upload with positions (single round trip to database)
      const result = await handleExternalImageDropMutationRef.current.mutateAsync({
        imageFiles: processedFiles,
        targetShotId: currentShot.id,
        currentProjectQueryKey: currentProjectId,
        currentShotCount: 0,
        skipAutoPosition: false,
        positions: positions,
      });

      if (!result?.generationIds?.length) {
        return;
      }

      // 5. If positions weren't set by the upload mutation, set them now
      if (result.generationIds.length > 0) {
        const needsPositionUpdate = await (async () => {
          const { data } = await supabase().from('shot_generations')
            .select('id, timeline_frame')
            .eq('shot_id', currentShot.id)
            .in('generation_id', result.generationIds)
            .limit(1);

          return data?.[0]?.timeline_frame === null;
        })();

        if (needsPositionUpdate) {
          await persistTimelinePositions(
            currentShot.id,
            result.generationIds,
            calculatedTargetFrame,
            currentBatchVideoFrames
          );
        }
      }

      // Demote orphaned video variants now that new images are in place
      await demoteOrphanedVariantsRef.current(currentShot.id, 'image-add');

    } catch (error) {
      normalizeAndPresentError(error, { context: 'TimelineDrop', toastTitle: 'Failed to add images' });
      throw error;
    } finally {
      actionsRef.current.setUploadingImage(false);
    }
  }, []);

  /**
   * Handle dropping a generation from GenerationsPane onto the timeline
   */
  const handleTimelineGenerationDrop = useCallback(async (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number
  ) => {
    const currentShot = selectedShotRef.current;
    const currentProjectId = projectIdRef.current;

    if (!currentShot?.id || !currentProjectId) {
      toast.error("Cannot add generation: No shot or project selected.");
      return;
    }

    if (!generationId) {
      toast.error("Invalid generation: Missing generation ID.");
      return;
    }

    try {
      await addImageToShotMutationRef.current.mutateAsync({
        generation_id: generationId,
        shot_id: currentShot.id,
        imageUrl: imageUrl,
        thumbUrl: thumbUrl,
        timelineFrame: targetFrame,
        project_id: currentProjectId
      });

      // Demote orphaned video variants now that the new image is in place
      await demoteOrphanedVariantsRef.current(currentShot.id, 'image-add');
    } catch (error) {
      normalizeAndPresentError(error, { context: 'GenerationDrop', toastTitle: 'Failed to add generation' });
      throw error;
    }
  }, []);

  /**
   * Handle dropping external images onto batch mode grid
   */
  const handleBatchImageDrop = useCallback(async (
    files: File[],
    targetFrame?: number
  ) => {
    const currentShot = selectedShotRef.current;
    const currentProjectId = projectIdRef.current;
    let adjustedShot: Shot | undefined;

    if (!currentShot?.id || !currentProjectId) {
      toast.error("Cannot add images: No shot or project selected.");
      return;
    }

    // Track optimistic items for cleanup
    const optimisticIds: string[] = [];
    const localUrls: string[] = [];

    try {
      try {
        const autoAdjustedAspectRatio = await maybeAutoAdjustShotAspectRatio(
          files,
          currentShot,
          projectsRef.current as ProjectWithSettings[],
          currentProjectId
        );

        if (autoAdjustedAspectRatio) {
          const ok = await updateShotAspectRatioRef.current(
            currentShot.id,
            currentProjectId,
            autoAdjustedAspectRatio.adjustedTo,
            { immediate: true }
          );

          if (ok) {
            setAutoAdjustedAspectRatioRef.current(autoAdjustedAspectRatio);
            adjustedShot = {
              ...currentShot,
              aspect_ratio: autoAdjustedAspectRatio.adjustedTo,
            };
          } else {
            normalizeAndPresentError(
              new Error('Failed to auto-adjust shot aspect ratio for the dropped image.'),
              {
                context: 'DropAutoAdjustShotAspectRatio:update',
                showToast: false,
                logData: {
                  shotId: currentShot.id,
                  adjustedTo: autoAdjustedAspectRatio.adjustedTo,
                },
              }
            );
          }
        }
      } catch (error) {
        normalizeAndPresentError(error, {
          context: 'DropAutoAdjustShotAspectRatio:update',
          showToast: false,
          logData: { shotId: currentShot.id },
        });
      }

      actionsRef.current.setUploadingImage(true);

      // 1. Calculate target frame positions with collision detection
      const startFrame = targetFrame ?? await fetchNextAvailableFrameForShot(currentShot.id, undefined);

      // For multiple files, ensure each position is unique
      const existingGens = queryClientRef.current.getQueryData<GenerationRow[]>(generationQueryKeys.byShot(currentShot.id)) || [];
      const existingFrames = existingGens
        .filter(g => g.timeline_frame != null && g.timeline_frame !== -1)
        .map(g => g.timeline_frame as number);

      const positions: number[] = [];
      const allUsedFrames = [...existingFrames];
      for (let i = 0; i < files.length; i++) {
        let targetFrame = startFrame + (i * DEFAULT_FRAME_SPACING);
        while (allUsedFrames.includes(targetFrame)) {
          targetFrame += 1;
        }
        positions.push(targetFrame);
        allUsedFrames.push(targetFrame);
      }

      // 2. Create optimistic entries immediately using local file URLs
      const previousFastGens = queryClientRef.current.getQueryData<GenerationRow[]>(generationQueryKeys.byShot(currentShot.id)) || [];

      const optimisticItems = files.map((file, index) => {
        const localUrl = URL.createObjectURL(file);
        localUrls.push(localUrl);
        const tempId = `temp-upload-${Date.now()}-${index}-${Math.random()}`;
        optimisticIds.push(tempId);

        return {
          id: tempId,
          generation_id: tempId,
          shotImageEntryId: tempId,
          shot_generation_id: tempId,
          location: localUrl,
          thumbnail_url: localUrl,
          imageUrl: localUrl,
          thumbUrl: localUrl,
          timeline_frame: positions[index],
          type: 'image' as const,
          created_at: new Date().toISOString(),
          starred: false,
          name: file.name,
          based_on: null,
          params: {},
          shot_data: { [currentShot.id]: [positions[index]] },
          _optimistic: true,
          _uploading: true
        };
      });

      // Add optimistic items to cache
      queryClientRef.current.setQueryData(
        generationQueryKeys.byShot(currentShot.id),
        [...previousFastGens, ...optimisticItems]
      );

      // 3. Crop images
      const processedFiles = await cropImagesToShotAspectRatio(
        files,
        adjustedShot ?? currentShot,
        currentProjectId,
        projectsRef.current,
        uploadSettingsRef.current
      );

      // 4. Upload with positions
      const result = await handleExternalImageDropMutationRef.current.mutateAsync({
        imageFiles: processedFiles,
        targetShotId: currentShot.id,
        currentProjectQueryKey: currentProjectId,
        currentShotCount: 0,
        skipAutoPosition: false,
        positions: positions,
      });

      if (!result?.generationIds?.length) {
        return;
      }

      // 5. If positions weren't set by the upload, set them now (fallback)
      const { data: checkData } = await supabase().from('shot_generations')
        .select('id, timeline_frame')
        .eq('shot_id', currentShot.id)
        .in('generation_id', result.generationIds)
        .limit(1);

      if (checkData?.[0]?.timeline_frame === null) {
        await persistTimelinePositions(
          currentShot.id,
          result.generationIds,
          startFrame,
          1 // Use 1 frame spacing for batch mode
        );
      }

      // Demote orphaned video variants now that new images are in place
      await demoteOrphanedVariantsRef.current(currentShot.id, 'image-add');

    } catch (error) {
      normalizeAndPresentError(error, { context: 'BatchDrop', toastTitle: 'Failed to add images' });

      // Remove optimistic items on error
      const currentCache = queryClientRef.current.getQueryData<GenerationRow[]>(generationQueryKeys.byShot(currentShot.id)) || [];
      queryClientRef.current.setQueryData(
        generationQueryKeys.byShot(currentShot.id),
        currentCache.filter(item => !optimisticIds.includes(item.id))
      );

      throw error;
    } finally {
      actionsRef.current.setUploadingImage(false);

      // Clean up local URLs to prevent memory leaks
      localUrls.forEach(url => URL.revokeObjectURL(url));
    }
  }, []);

  /**
   * Handle dropping a generation from GenerationsPane onto batch mode grid
   */
  const handleBatchGenerationDrop = useCallback(async (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number
  ) => {
    const currentShot = selectedShotRef.current;
    const currentProjectId = projectIdRef.current;

    if (!currentShot?.id || !currentProjectId) {
      toast.error("Cannot add generation: No shot or project selected.");
      return;
    }

    if (!generationId) {
      toast.error("Invalid generation: Missing generation ID.");
      return;
    }

    try {
      await addImageToShotMutationRef.current.mutateAsync({
        generation_id: generationId,
        shot_id: currentShot.id,
        imageUrl: imageUrl,
        thumbUrl: thumbUrl,
        project_id: currentProjectId,
        timelineFrame: targetFrame,
      });

      // Demote orphaned video variants now that the new image is in place
      await demoteOrphanedVariantsRef.current(currentShot.id, 'image-add');
    } catch (error) {
      normalizeAndPresentError(error, { context: 'BatchDrop', toastTitle: 'Failed to add generation' });
      throw error;
    }
  }, []);

  const handleVariantDrop = useCallback(async (params: VariantDropParams) => {
    const currentShot = selectedShotRef.current;
    const currentProjectId = projectIdRef.current;

    if (!currentShot?.id || !currentProjectId) {
      toast.error("Cannot add variant: No shot or project selected.");
      return;
    }

    try {
      if (params.sourceGenerationId) {
        if (!params.imageUrl) {
          toast.error("Cannot add variant: Missing source image.");
          return;
        }

        const { error } = await supabase().from('generation_variants').insert({
          generation_id: params.targetGenerationId,
          project_id: currentProjectId,
          location: params.imageUrl,
          thumbnail_url: params.thumbUrl || params.imageUrl,
          is_primary: params.mode === 'main',
          variant_type: VARIANT_TYPE.DROPPED,
          params: {
            source: 'generation-drop',
            source_generation_id: params.sourceGenerationId,
            source_variant_id: params.sourceVariantId || null,
          },
        });

        if (error) {
          throw error;
        }
      } else if (params.files?.length) {
        const [file] = params.files;
        if (!file) {
          return;
        }

        const { imageUrl, thumbnailUrl } = await uploadImageForVariant(file, currentProjectId);
        const { error } = await supabase().from('generation_variants').insert({
          generation_id: params.targetGenerationId,
          project_id: currentProjectId,
          location: imageUrl,
          thumbnail_url: thumbnailUrl || imageUrl,
          is_primary: params.mode === 'main',
          variant_type: VARIANT_TYPE.DROPPED,
          params: {
            source: 'file-drop',
            original_filename: file.name,
          },
        });

        if (error) {
          throw error;
        }
      } else {
        return;
      }

      await enqueueVariantInvalidation(queryClientRef.current, {
        generationId: params.targetGenerationId,
        shotId: currentShot.id,
        reason: 'variant-drop',
      });

      if (params.mode === 'main') {
        await queryClientRef.current.invalidateQueries({
          queryKey: generationQueryKeys.byShot(currentShot.id),
        });
      }
    } catch (error) {
      normalizeAndPresentError(error, { context: 'VariantDrop', toastTitle: 'Failed to add variant' });
      throw error;
    }
  }, []);

  return {
    handleTimelineImageDrop,
    handleTimelineGenerationDrop,
    handleBatchImageDrop,
    handleBatchGenerationDrop,
    handleVariantDrop,
  };
};
