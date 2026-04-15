import React, { Suspense, useRef } from 'react';
import { mapSelectedLorasForModal } from '@/shared/components/lora/mapSelectedLorasForModal';
import { LoraSelectorModal } from '@/domains/lora/components';
import { EditPanelLayout } from './EditPanelLayout';
import { ModeSelector } from './ModeSelector';
import { AnnotatePanel } from './editModes/AnnotatePanel';
import { Img2ImgPanel } from './editModes/Img2ImgPanel';
import { InpaintPanel } from './editModes/InpaintPanel';
import { RepositionPanel } from './editModes/RepositionPanel';
import { TextEditPanel } from './editModes/TextEditPanel';
import { UpscalePanel } from './editModes/UpscalePanel';
import type { EditModePanelProps } from './types';
import { useEditModePanelState } from '../hooks/useEditModePanelState';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';

export const EditModePanel: React.FC<EditModePanelProps> = ({
  variant,
  hideInfoEditToggle = false,
  simplifiedHeader = false,
  taskId,
  currentMediaId,
  actions,
  upscale,
  lora,
  advanced,
  isLocalGeneration = false,
  coreState,
  imageEditState,
  variantsState,
}) => {
  useRenderBudget('EditModePanel', 3);
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;
  const instanceRef = useRef<string>();
  if (!instanceRef.current) {
    instanceRef.current = Math.random().toString(36).slice(2, 6);
  }
  console.log('[EditModePanel] render', {
    instance: instanceRef.current,
    renderCount: renderCountRef.current,
    currentMediaId,
  });

  const state = useEditModePanelState({
    variant,
    currentMediaId,
    isCloudMode: upscale?.isCloudMode,
    handleUpscale: upscale?.handleUpscale,
    coreState,
    imageEditState,
    variantsState,
  });

  const modeSelector = (
    <ModeSelector
      items={state.modeSelectorItems}
      activeId={state.editMode ?? 'text'}
    />
  );

  const sharedPanelProps = {
    state,
    isCloudMode: upscale?.isCloudMode,
    editLoraManager: lora?.editLoraManager,
    availableLoras: lora?.availableLoras ?? [],
    advancedSettings: advanced?.advancedSettings,
    setAdvancedSettings: advanced?.setAdvancedSettings,
    isLocalGeneration,
  };

  const renderPanel = () => {
    switch (state.editMode) {
      case 'annotate':
        return <AnnotatePanel {...sharedPanelProps} handleUnifiedGenerate={actions.handleUnifiedGenerate} handleGenerateAnnotatedEdit={actions.handleGenerateAnnotatedEdit} />;
      case 'inpaint':
        return <InpaintPanel {...sharedPanelProps} handleUnifiedGenerate={actions.handleUnifiedGenerate} handleGenerateAnnotatedEdit={actions.handleGenerateAnnotatedEdit} />;
      case 'reposition':
        return <RepositionPanel {...sharedPanelProps} handleSaveAsVariant={actions.handleSaveAsVariant!} handleGenerateReposition={actions.handleGenerateReposition!} />;
      case 'img2img':
        return <Img2ImgPanel state={state} handleGenerateImg2Img={actions.handleGenerateImg2Img!} img2imgLoraManager={lora?.img2imgLoraManager} availableLoras={lora?.availableLoras ?? []} />;
      case 'upscale':
        return upscale?.handleUpscale ? (
          <UpscalePanel
            variant={variant}
            onUpscale={upscale.handleUpscale}
            isUpscaling={upscale.isUpscaling ?? false}
            upscaleSuccess={upscale.upscaleSuccess ?? false}
          />
        ) : null;
      case 'text':
      default:
        return <TextEditPanel {...sharedPanelProps} handleUnifiedGenerate={actions.handleUnifiedGenerate} handleGenerateAnnotatedEdit={actions.handleGenerateAnnotatedEdit} />;
    }
  };

  return (
    <>
      <EditPanelLayout
        variant={variant}
        onClose={state.onClose}
        onExitEditMode={state.handleExitMagicEditMode}
        hideInfoEditToggle={hideInfoEditToggle}
        simplifiedHeader={simplifiedHeader}
        modeSelector={modeSelector}
        taskId={taskId}
        variants={state.variants}
        activeVariantId={state.activeVariantId}
        onVariantSelect={state.onVariantSelect}
        onMakePrimary={state.onMakePrimary}
        isLoadingVariants={state.isLoadingVariants}
        onPromoteToGeneration={state.onPromoteToGeneration}
        isPromoting={state.isPromoting}
        pendingTaskCount={state.pendingTaskCount}
        unviewedVariantCount={state.unviewedVariantCount}
        onMarkAllViewed={state.onMarkAllViewed}
        onDeleteVariant={state.onDeleteVariant}
        onLoadVariantSettings={state.onLoadVariantSettings}
        onLoadVariantImages={state.onLoadVariantImages}
        currentSegmentImages={state.currentSegmentImages}
      >
        {renderPanel()}
      </EditPanelLayout>

      {lora?.editLoraManager && (
        <Suspense fallback={null}>
          <LoraSelectorModal
            isOpen={lora.editLoraManager.isLoraModalOpen}
            onClose={() => lora.editLoraManager.setIsLoraModalOpen(false)}
            loras={lora.availableLoras ?? []}
            onAddLora={lora.editLoraManager.handleAddLora}
            onRemoveLora={lora.editLoraManager.handleRemoveLora}
            onUpdateLoraStrength={lora.editLoraManager.handleLoraStrengthChange}
            selectedLoras={mapSelectedLorasForModal(lora.editLoraManager.selectedLoras, lora.availableLoras ?? [])}
            loraType="Qwen Edit"
          />
        </Suspense>
      )}
    </>
  );
};
