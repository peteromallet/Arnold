import React, { useMemo } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import type {
  LightboxFeatureFlags,
} from '../types';
import { EditModePanel } from './EditModePanel';
import { InfoPanel } from './InfoPanel';
import { useLightboxCoreSafe, useLightboxVariantsSafe } from '../contexts/LightboxStateContext';
import type { ImageLightboxEnvironment } from '../hooks/useImageLightboxEnvironment';
import type { ImageLightboxEditModel } from '../hooks/useImageLightboxEditing';

interface ImageLightboxControlsPanelProps {
  media: GenerationRow;
  features?: LightboxFeatureFlags;
  env: ImageLightboxEnvironment;
  editModel: ImageLightboxEditModel;
  showPanel: boolean;
  panelVariant: 'desktop' | 'mobile';
  panelTaskId: string | null;
}

export const ImageLightboxControlsPanel = React.memo(function ImageLightboxControlsPanel({
  media,
  features,
  env,
  editModel,
  showPanel,
  panelVariant,
  panelTaskId,
}: ImageLightboxControlsPanelProps) {
  const coreState = useLightboxCoreSafe();
  const variantsState = useLightboxVariantsSafe();

  if (!showPanel) {
    return null;
  }

  const showImageEditTools = features?.showImageEditTools ?? true;
  const { editOrchestrator, adjustedTaskDetailsData } = editModel;
  const editPanelActions = useMemo(() => ({
    handleUnifiedGenerate: editOrchestrator.handleUnifiedGenerate,
    handleGenerateAnnotatedEdit: editOrchestrator.handleGenerateAnnotatedEdit,
    handleGenerateReposition: editOrchestrator.handleGenerateReposition,
    handleSaveAsVariant: editOrchestrator.handleSaveAsVariant,
    handleGenerateImg2Img: editOrchestrator.handleGenerateImg2Img,
  }), [
    editOrchestrator.handleUnifiedGenerate,
    editOrchestrator.handleGenerateAnnotatedEdit,
    editOrchestrator.handleGenerateReposition,
    editOrchestrator.handleSaveAsVariant,
    editOrchestrator.handleGenerateImg2Img,
  ]);
  const upscaleControls = useMemo(() => ({
    isCloudMode: env.isCloudMode,
    handleUpscale: async () => {
      await env.upscaleHook.handleUpscale({ scaleFactor: 2, noiseScale: 0.1 });
    },
    isUpscaling: env.upscaleHook.isUpscaling,
    upscaleSuccess: env.upscaleHook.upscaleSuccess,
  }), [
    env.isCloudMode,
    env.upscaleHook.handleUpscale,
    env.upscaleHook.isUpscaling,
    env.upscaleHook.upscaleSuccess,
  ]);
  const loraControls = useMemo(() => ({
    img2imgLoraManager: editOrchestrator.img2imgLoraManager,
    editLoraManager: env.editLoraManager,
    availableLoras: env.availableLoras,
  }), [
    editOrchestrator.img2imgLoraManager,
    env.editLoraManager,
    env.availableLoras,
  ]);
  const advancedConfig = useMemo(() => ({
    advancedSettings: env.editSettingsPersistence.advancedSettings,
    setAdvancedSettings: env.editSettingsPersistence.setAdvancedSettings,
  }), [
    env.editSettingsPersistence.advancedSettings,
    env.editSettingsPersistence.setAdvancedSettings,
  ]);
  const panelCoreState = useMemo(() => ({
    onClose: coreState.onClose,
  }), [coreState.onClose]);
  const panelVariantsState = useMemo(() => ({
    variants: variantsState.variants,
    activeVariant: variantsState.activeVariant,
    handleVariantSelect: variantsState.handleVariantSelect,
    handleMakePrimary: variantsState.handleMakePrimary,
    isLoadingVariants: variantsState.isLoadingVariants,
    handlePromoteToGeneration: variantsState.handlePromoteToGeneration,
    isPromoting: variantsState.isPromoting,
    handleDeleteVariant: variantsState.handleDeleteVariant,
    onLoadVariantSettings: variantsState.onLoadVariantSettings,
    pendingTaskCount: variantsState.pendingTaskCount,
    unviewedVariantCount: variantsState.unviewedVariantCount,
    onMarkAllViewed: variantsState.onMarkAllViewed,
    onLoadVariantImages: variantsState.onLoadVariantImages,
    currentSegmentImages: variantsState.currentSegmentImages,
  }), [
    variantsState.variants,
    variantsState.activeVariant,
    variantsState.handleVariantSelect,
    variantsState.handleMakePrimary,
    variantsState.isLoadingVariants,
    variantsState.handlePromoteToGeneration,
    variantsState.isPromoting,
    variantsState.handleDeleteVariant,
    variantsState.onLoadVariantSettings,
    variantsState.pendingTaskCount,
    variantsState.unviewedVariantCount,
    variantsState.onMarkAllViewed,
    variantsState.onLoadVariantImages,
    variantsState.currentSegmentImages,
  ]);

  if (editOrchestrator.isSpecialEditMode) {
    return (
      <EditModePanel
        variant={panelVariant}
        taskId={panelTaskId}
        currentMediaId={media.id}
        actions={editPanelActions}
        upscale={upscaleControls}
        lora={loraControls}
        advanced={advancedConfig}
        isLocalGeneration={env.isLocalGeneration}
        coreState={panelCoreState}
        imageEditState={editOrchestrator.imageEditValue}
        variantsState={panelVariantsState}
      />
    );
  }

  return (
    <InfoPanel
      variant={panelVariant}
      showImageEditTools={showImageEditTools}
      taskPanel={{
        taskDetailsData: adjustedTaskDetailsData,
        replaceImages: env.replaceImages,
        onReplaceImagesChange: env.setReplaceImages,
      }}
      taskId={panelTaskId}
    />
  );
});
