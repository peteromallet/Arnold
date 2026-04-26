import React from 'react';
import { ArrowLeftRight, Settings, ChevronDown } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/components/ui/collapsible';
import { Label } from '@/shared/components/ui/primitives/label';
import { Switch } from '@/shared/components/ui/switch';

import {
  usePromptSettings,
  useMotionSettings,
  useFrameSettings,
  useModelSettings,
  usePhaseConfigSettings,
  useGenerationModeSettings,
  useLoraSettings,
  useSettingsSave,
  useVideoTravelSettingsStatus,
} from '@/tools/travel-between-images/providers';
import { getModelSpec, type SelectedModel } from '@/tools/travel-between-images/settings';
import { TravelGuidanceEditor } from '@/shared/components/travel/TravelGuidanceEditor';

import {
  useShotSettingsGeneration,
  useShotSettingsIdentity,
  useShotSettingsMedia,
  useShotSettingsUi,
} from '../../ShotSettingsContext';

import { BatchSettingsForm } from '../../../BatchSettingsForm';
import { MotionControl } from '../../../MotionControl';
import { GenerateVideoCTA } from '../../../GenerateVideoCTA';
import { PanelSectionHeader } from '@/tools/travel-between-images/components/shared/PanelSectionHeader';
import {
  JoinClipsSettingsForm,
} from '@/shared/components/JoinClipsSettingsForm/JoinClipsSettingsForm';
import { buildJoinClipsFormProps } from './joinClipsFormProps';

interface BatchModeContentProps {
  ctaContainerRef?: (node: HTMLDivElement | null) => void;
  swapButtonRef: React.RefObject<HTMLButtonElement>;
  parentVariantName?: string;
  parentOnVariantNameChange?: (name: string) => void;
  parentIsGeneratingVideo?: boolean;
  parentVideoJustQueued?: boolean;
}

export const BatchModeContent: React.FC<BatchModeContentProps> = ({
  ctaContainerRef,
  swapButtonRef,
  parentVariantName,
  parentOnVariantNameChange,
  parentIsGeneratingVideo,
  parentVideoJustQueued,
}) => {
  const { projectId, selectedProjectId, projects } = useShotSettingsIdentity();
  const { state, dimensions } = useShotSettingsUi();
  const { simpleFilteredImages, structureVideo, structureVideoHandlers } = useShotSettingsMedia();
  const {
    loraManager,
    availableLoras,
    generationMode,
    generationHandlers,
    joinState,
  } = useShotSettingsGeneration();

  const promptSettings = usePromptSettings();
  const motionSettings = useMotionSettings();
  const frameSettings = useFrameSettings();
  const modelSettings = useModelSettings();
  const phaseConfigSettings = usePhaseConfigSettings();
  const generationModeSettings = useGenerationModeSettings();
  const loraSettingsFromContext = useLoraSettings();
  const { isLoading: settingsLoadingFromContext } = useVideoTravelSettingsStatus();
  const { onBlurSave: blurSaveHandler } = useSettingsSave();

  const advancedMode = motionSettings.motionMode === 'advanced';
  const smoothContinuations = motionSettings.smoothContinuations ?? false;
  const stitchAfterGenerate = smoothContinuations || (joinState.joinSettings.settings.stitchAfterGenerate ?? false);
  const effectiveGenerationMode = generationModeSettings.generationMode;
  const modelSpec = getModelSpec(modelSettings.selectedModel);
  const ltxSelected = modelSpec.modelFamily === 'ltx';
  const fullLtxSelected = modelSpec.id === 'ltx-2.3';
  const handlePrimaryModelChange = (family: 'wan' | 'ltx') => {
    if (family === 'wan') {
      modelSettings.setSelectedModel('wan-2.2');
      return;
    }

    const nextLtxModel: SelectedModel = ltxSelected
      ? modelSettings.selectedModel
      : 'ltx-2.3-fast';
    modelSettings.setSelectedModel(nextLtxModel);
  };
  const joinStitchFormProps = buildJoinClipsFormProps({
    joinState,
    availableLoras,
    projectId,
    loraPersistenceKey: 'join-clips-shot-editor-stitch',
  });

  return (
    <>
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left Column: Main Settings */}
        <div className="lg:w-1/2 order-2 lg:order-1">
          <PanelSectionHeader title="Settings" theme="orange" />
          <BatchSettingsForm
            selectedModel={modelSettings.selectedModel}
            onSelectedModelChange={(nextModel) => {
              if (nextModel === 'wan-2.2') {
                handlePrimaryModelChange('wan');
                return;
              }
              if (getModelSpec(nextModel).modelFamily !== 'ltx') {
                return;
              }
              if (!ltxSelected) {
                handlePrimaryModelChange('ltx');
                return;
              }
              modelSettings.setSelectedModel(nextModel);
            }}
            batchVideoPrompt={promptSettings.prompt}
            onBatchVideoPromptChange={generationHandlers.handleBatchVideoPromptChangeWithClear}
            batchVideoFrames={frameSettings.batchVideoFrames}
            onBatchVideoFramesChange={frameSettings.setFrames}
            batchVideoSteps={frameSettings.batchVideoSteps}
            onBatchVideoStepsChange={generationHandlers.handleStepsChange}
            dimensionSource={dimensions.dimensionSource ?? 'project'}
            onDimensionSourceChange={dimensions.onDimensionSourceChange ?? (() => {})}
            customWidth={dimensions.customWidth}
            onCustomWidthChange={dimensions.onCustomWidthChange ?? (() => {})}
            customHeight={dimensions.customHeight}
            onCustomHeightChange={dimensions.onCustomHeightChange ?? (() => {})}
            negativePrompt={promptSettings.negativePrompt}
            onNegativePromptChange={promptSettings.setNegativePrompt}
            projects={projects}
            selectedProjectId={selectedProjectId}
            selectedLoras={loraManager.selectedLoras}
            availableLoras={loraSettingsFromContext.availableLoras}
            isTimelineMode={effectiveGenerationMode === 'timeline'}
            accelerated={generationMode.accelerated}
            onAcceleratedChange={generationMode.onAcceleratedChange}
            showStepsNotification={state.showStepsNotification}
            randomSeed={generationMode.randomSeed}
            onRandomSeedChange={generationMode.onRandomSeedChange}
            turboMode={motionSettings.turboMode}
            onTurboModeChange={motionSettings.setTurboMode}
            smoothContinuations={motionSettings.smoothContinuations}
            onSmoothContinuationsChange={motionSettings.setSmoothContinuations}
            guidanceScale={modelSettings.guidanceScale}
            onGuidanceScaleChange={modelSettings.setGuidanceScale}
            ltxHdResolution={modelSettings.ltxHdResolution}
            onLtxHdResolutionChange={modelSettings.setLtxHdResolution}
            generationTypeMode={phaseConfigSettings.generationTypeMode}
            amountOfMotion={motionSettings.amountOfMotion}
            onAmountOfMotionChange={motionSettings.setAmountOfMotion}
            imageCount={simpleFilteredImages.length}
            enhancePrompt={promptSettings.enhancePrompt}
            onEnhancePromptChange={promptSettings.setEnhancePrompt}
            advancedMode={advancedMode}
            phaseConfig={phaseConfigSettings.phaseConfig}
            onPhaseConfigChange={phaseConfigSettings.setPhaseConfig}
            selectedPhasePresetId={phaseConfigSettings.selectedPhasePresetId}
            onPhasePresetSelect={phaseConfigSettings.selectPreset}
            onPhasePresetRemove={phaseConfigSettings.removePreset}
            onBlurSave={blurSaveHandler}
            onClearEnhancedPrompts={generationHandlers.clearAllEnhancedPrompts}
            videoControlMode={generationModeSettings.videoControlMode}
            textBeforePrompts={promptSettings.textBeforePrompts}
            onTextBeforePromptsChange={promptSettings.setTextBeforePrompts}
            textAfterPrompts={promptSettings.textAfterPrompts}
            onTextAfterPromptsChange={promptSettings.setTextAfterPrompts}
          />
        </div>

        {/* Right Column: Motion Control */}
        <div className="lg:w-1/2 order-1 lg:order-2">
          <PanelSectionHeader title="Motion" theme="purple" />

          {structureVideo.structureVideoPath && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-muted-foreground mb-3">Camera Guidance</h4>
              <TravelGuidanceEditor
                selectedModel={modelSettings.selectedModel}
                hasStructureVideo={!!structureVideo.structureVideoPath}
                guidanceMode={structureVideo.structureVideoType}
                onGuidanceModeChange={structureVideoHandlers.handleStructureTypeChangeFromMotionControl}
                guidanceStrength={structureVideo.structureVideoMotionStrength}
                onGuidanceStrengthChange={structureVideoHandlers.handleStructureVideoMotionStrengthChange}
                guidanceUni3cEndPercent={structureVideo.structureVideoUni3cEndPercent}
                onGuidanceUni3cEndPercentChange={structureVideoHandlers.handleUni3cEndPercentChange}
              />
            </div>
          )}

          {structureVideo.structureVideoPath && !fullLtxSelected && (
            <h4 className="text-sm font-medium text-muted-foreground mb-3">Model Guidance:</h4>
          )}
          <MotionControl
            mode={{
              motionMode: motionSettings.motionMode || 'basic',
              onMotionModeChange: motionSettings.setMotionMode,
              selectedModel: modelSettings.selectedModel,
              generationTypeMode: phaseConfigSettings.generationTypeMode,
              onGenerationTypeModeChange: phaseConfigSettings.setGenerationTypeMode,
              hasStructureVideo: !!structureVideo.structureVideoPath,
              guidanceKind: structureVideo.structureVideoType || undefined,
            }}
            lora={{
              selectedLoras: loraManager.selectedLoras,
              availableLoras: loraSettingsFromContext.availableLoras,
              onAddLoraClick: () => loraManager.setIsLoraModalOpen(true),
              onRemoveLora: loraManager.handleRemoveLora,
              onLoraStrengthChange: loraManager.handleLoraStrengthChange,
              onAddTriggerWord: loraManager.handleAddTriggerWord,
              renderLoraHeaderActions: loraManager.renderHeaderActions,
            }}
            presets={{
              selectedPhasePresetId: phaseConfigSettings.selectedPhasePresetId,
              onPhasePresetSelect: phaseConfigSettings.selectPreset,
              onPhasePresetRemove: phaseConfigSettings.removePreset,
              currentSettings: generationMode.currentMotionSettings,
            }}
            advanced={{
              phaseConfig: phaseConfigSettings.phaseConfig,
              onPhaseConfigChange: phaseConfigSettings.setPhaseConfig,
              onBlurSave: blurSaveHandler,
              randomSeed: generationMode.randomSeed,
              onRandomSeedChange: generationMode.onRandomSeedChange,
              onRestoreDefaults: phaseConfigSettings.restoreDefaults,
            }}
            stateOverrides={{
              turboMode: motionSettings.turboMode,
              settingsLoading: settingsLoadingFromContext,
            }}
          />
        </div>
      </div>

      {/* Generate CTA */}
      <div ref={ctaContainerRef} className="mt-6 pt-6 border-t">
        <GenerateVideoCTA
          variantName={parentVariantName || ''}
          onVariantNameChange={parentOnVariantNameChange || (() => {})}
          onGenerate={() => generationHandlers.handleGenerateBatch(parentVariantName || '')}
          isGenerating={parentIsGeneratingVideo || generationMode.isSteerableMotionEnqueuing}
          justQueued={parentVideoJustQueued || generationMode.steerableMotionJustQueued}
          disabled={generationMode.isGenerationDisabled}
          enhancementProgress={generationMode.enhancementProgress}
          inputId="variant-name"
          videoCount={Math.max(0, simpleFilteredImages.length - 1)}
          stitchEnabled={stitchAfterGenerate}
          middleContent={
            simpleFilteredImages.length > 2 && !smoothContinuations ? (
              stitchAfterGenerate ? (
                <Collapsible className="mb-6 w-full">
                  <div className="flex items-center justify-center gap-4">
                    <div className="flex items-center gap-2">
                      <Switch
                        id="stitch-after-generate"
                        checked={stitchAfterGenerate}
                        onCheckedChange={(checked) => joinState.joinSettings.updateField('stitchAfterGenerate', checked)}
                      />
                      <Label htmlFor="stitch-after-generate" className="text-sm font-normal cursor-pointer">
                        Stitch generated clips
                      </Label>
                    </div>
                    <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors group">
                      <Settings className="w-4 h-4" />
                      <span>Settings</span>
                      <ChevronDown className="w-3 h-3 transition-transform group-data-[panel-open]:rotate-180" />
                    </CollapsibleTrigger>
                  </div>
                  <CollapsibleContent className="mt-4 pt-4 border-t">
                    <JoinClipsSettingsForm
                      clipSettings={joinStitchFormProps.clipSettings}
                      motionConfig={joinStitchFormProps.motionConfig}
                      uiState={{
                        onGenerate: () => {},
                        isGenerating: false,
                        generateSuccess: false,
                        generateButtonText: '',
                        showGenerateButton: false,
                        onRestoreDefaults: joinState.handleRestoreJoinDefaults,
                      }}
                    />
                  </CollapsibleContent>
                </Collapsible>
              ) : (
                <div className="mb-6 flex items-center justify-center gap-2">
                  <Switch
                    id="stitch-after-generate"
                    checked={stitchAfterGenerate}
                    onCheckedChange={(checked) => joinState.joinSettings.updateField('stitchAfterGenerate', checked)}
                  />
                  <Label htmlFor="stitch-after-generate" className="text-sm font-normal cursor-pointer">
                    Stitch generated clips
                  </Label>
                </div>
              )
            ) : undefined
          }
          bottomContent={
            simpleFilteredImages.length > 2 ? (
              <button
                ref={swapButtonRef}
                onClick={() => generationMode.toggleGenerateModePreserveScroll('join')}
                className="mt-4 w-full flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors pt-2"
              >
                <ArrowLeftRight className="w-4 h-4" />
                <span>Swap to Join Segments</span>
              </button>
            ) : undefined
          }
        />
      </div>
    </>
  );
};
