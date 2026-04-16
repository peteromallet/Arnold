import { useEffect, useMemo } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import type { LightboxFeatureFlags, TaskDetailsData } from '../types';
import type { ImageLightboxEnvironment } from './useImageLightboxEnvironment';
import type { ImageLightboxSharedModel } from './useImageLightboxSharedState';
import { useImageEditOrchestrator } from './useImageEditOrchestrator';
import { useAdjustedTaskDetails } from './useAdjustedTaskDetails';
import { usePanelModeRestore } from './usePanelModeRestore';
import { useLightboxVariantBadges } from './useLightboxVariantBadges';

interface UseImageLightboxEditingProps {
  media: GenerationRow;
  taskDetailsData?: TaskDetailsData;
  initialVariantId?: string;
  toolTypeOverride?: string;
  shotId?: string;
  features?: LightboxFeatureFlags;
}

export function useImageLightboxEditing(
  props: UseImageLightboxEditingProps,
  env: ImageLightboxEnvironment,
  sharedModel: ImageLightboxSharedModel,
) {
  const {
    media,
    taskDetailsData,
    initialVariantId,
    toolTypeOverride,
    shotId,
  } = props;
  const initialActive = props.features?.initialEditActive ?? false;

  const {
    selectedProjectId,
    actualGenerationId,
    imageDimensions,
    imageContainerRef,
    editSettingsPersistence,
    effectiveEditModeLoras,
    availableLoras,
    variantFetchGenerationId,
  } = env;

  const {
    sharedState,
    setModeSnapshot,
  } = sharedModel;

  const editOrchestrator = useImageEditOrchestrator({
    mediaContext: {
      media,
      selectedProjectId,
      actualGenerationId,
      shotId,
      toolTypeOverride,
      initialActive,
      thumbnailUrl: sharedState.variants.activeVariant?.thumbnail_url || media.thumbUrl,
    },
    displayContext: {
      imageDimensions,
      imageContainerRef,
      effectiveImageUrl: env.upscaleHook.effectiveImageUrl,
    },
    variantContext: {
      activeVariant: sharedState.variants.activeVariant,
      setActiveVariantId: sharedState.variants.setActiveVariantId,
      refetchVariants: sharedState.variants.refetch,
    },
    settingsContext: editSettingsPersistence,
    loraContext: {
      effectiveEditModeLoras,
      availableLoras,
    },
  });

  useEffect(() => {
    setModeSnapshot((current) => {
      if (
        current.isInpaintMode === editOrchestrator.isInpaintMode
        && current.isMagicEditMode === editOrchestrator.isMagicEditMode
      ) {
        return current;
      }
      return {
        isInpaintMode: editOrchestrator.isInpaintMode,
        isMagicEditMode: editOrchestrator.isMagicEditMode,
      };
    });
  }, [
    editOrchestrator.isInpaintMode,
    editOrchestrator.isMagicEditMode,
    setModeSnapshot,
  ]);

  const { adjustedTaskDetailsData } = useAdjustedTaskDetails({
    projectId: selectedProjectId ?? null,
    activeVariant: sharedState.variants.activeVariant,
    taskDetailsData,
    isLoadingVariants: sharedState.variants.isLoading,
    initialVariantId,
  });

  usePanelModeRestore({
    mediaId: media.id,
    persistedPanelMode: editSettingsPersistence.panelMode,
    isVideo: false,
    isSpecialEditMode: editOrchestrator.isSpecialEditMode,
    isInVideoEditMode: false,
    initialVideoTrimMode: false,
    initialEditActive: initialActive,
    handleEnterMagicEditMode: editOrchestrator.handleEnterMagicEditMode,
  });

  const variantBadges = useLightboxVariantBadges({
    pendingTaskGenerationId: env.actualGenerationId,
    selectedProjectId,
    variants: sharedState.variants.list,
    variantFetchGenerationId,
  });

  return useMemo(
    () => ({
      editOrchestrator,
      adjustedTaskDetailsData,
      variantBadges,
    }),
    [adjustedTaskDetailsData, editOrchestrator, variantBadges],
  );
}

export type ImageLightboxEditModel = ReturnType<typeof useImageLightboxEditing>;
