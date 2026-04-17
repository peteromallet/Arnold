import { useEffect, useRef, useCallback } from "react";
import { useUpdateShotImageOrder, useAddImageToShot, useRemoveImageFromShot } from "@/shared/hooks/shots";
import { useShotCreation } from "@/shared/hooks/shotCreation/useShotCreation";
import { useIsMobile } from "@/shared/hooks/mobile";
import { Shot } from '@/domains/generation/types';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { usePanesStore } from '@/shared/state/panesStore';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { useQueryClient } from '@tanstack/react-query';

import { ShotEditorProps, GenerationsPaneSettings } from './state/types';
import { useShotEditorState } from './state/useShotEditorState';
import { useGenerationActions } from './hooks/actions/useGenerationActions';
import { useLoraSync } from './hooks/editor-state/useLoraSync';
import { useModeReadiness } from './hooks/video/useModeReadiness';
import { useShotActions } from './hooks/actions/useShotActions';
import { useShotEditorSetup } from './hooks/editor-state/useShotEditorSetup';
import { useShotEditorBridge } from './hooks/editor-state/useShotEditorBridge';
import { useLastVideoGeneration } from './hooks/video/useLastVideoGeneration';
import { useAspectAdjustedColumns } from './hooks/editor-state/useAspectAdjustedColumns';
import {
  usePromptSettings,
  useMotionSettings,
  useFrameSettings,
  useModelSettings,
  usePhaseConfigSettings,
  useGenerationModeSettings,
  useSteerableMotionSettings,
  useLoraSettings,
  useVideoTravelSettingsStatus,
} from '@/tools/travel-between-images/providers';
import { ShotEditorLayoutProps } from './ShotEditorLayout';
import { useGenerationController } from './controllers/useGenerationController';
import { useImageManagementController } from './controllers/useImageManagementController';
import { useGenerationControllerInputModel } from './controllers/useGenerationControllerInputModel';
import { useShotEditorMediaAndOutputControllers } from './controllers/useShotEditorMediaAndOutputControllers';
import {
  buildShotEditorScreenModel,
  type BuildShotEditorScreenModelArgs,
  useShotEditorLayoutModel,
} from './controllers/useShotEditorLayoutModel';
import { useApplySettingsHandler } from './hooks/actions/useApplySettingsHandler';
import { useShotSettingsValue } from './hooks/editor-state/useShotSettingsValue';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';

interface ShotEditorControllerResult {
  hasSelectedShot: boolean;
  layoutProps: ShotEditorLayoutProps;
}

type TravelUiSettings = {
  acceleratedMode?: boolean;
  randomSeed?: boolean;
};

interface ShotEditorBootstrapResult {
  promptSettings: ReturnType<typeof usePromptSettings>;
  motionSettings: ReturnType<typeof useMotionSettings>;
  frameSettings: ReturnType<typeof useFrameSettings>;
  modelSettings: ReturnType<typeof useModelSettings>;
  phaseConfigSettings: ReturnType<typeof usePhaseConfigSettings>;
  generationModeSettings: ReturnType<typeof useGenerationModeSettings>;
  steerableMotionSettings: ReturnType<typeof useSteerableMotionSettings>;
  loraSettings: ReturnType<typeof useLoraSettings>;
  settingsLoadingFromContext: boolean;
  selectedShot: ReturnType<typeof useShotEditorSetup>['selectedShot'];
  shots: ReturnType<typeof useShotEditorSetup>['shots'];
  selectedProjectId: ReturnType<typeof useShotEditorSetup>['selectedProjectId'];
  projects: ReturnType<typeof useShotEditorSetup>['projects'];
  effectiveAspectRatio: ReturnType<typeof useShotEditorSetup>['effectiveAspectRatio'];
  allShotImages: ReturnType<typeof useShotEditorSetup>['allShotImages'];
  timelineImages: ReturnType<typeof useShotEditorSetup>['timelineImages'];
  unpositionedImages: ReturnType<typeof useShotEditorSetup>['unpositionedImages'];
  videoOutputs: ReturnType<typeof useShotEditorSetup>['videoOutputs'];
  contextImages: ReturnType<typeof useShotEditorSetup>['contextImages'];
  initialParentGenerations: ReturnType<typeof useShotEditorSetup>['initialParentGenerations'];
  refs: ReturnType<typeof useShotEditorSetup>['refs'];
  queryClient: ReturnType<typeof useQueryClient>;
  setCurrentShotId: ReturnType<typeof useCurrentShot>['setCurrentShotId'];
  navigateToShot: ReturnType<typeof useShotNavigation>['navigateToShot'];
  addImageToShotMutation: ReturnType<typeof useAddImageToShot>;
  removeImageFromShotMutation: ReturnType<typeof useRemoveImageFromShot>;
  updateShotImageOrderMutation: ReturnType<typeof useUpdateShotImageOrder>;
  createShotRef: React.MutableRefObject<ReturnType<typeof useShotCreation>['createShot']>;
  addToShotMutationRef: React.MutableRefObject<ReturnType<typeof useAddImageToShot>['mutateAsync']>;
  addToShotWithoutPositionMutationRef: React.MutableRefObject<ReturnType<typeof useAddImageToShot>['mutateAsyncWithoutPosition']>;
  isMobile: ReturnType<typeof useIsMobile>;
  isPhone: boolean;
  aspectAdjustedColumns: number;
  setIsGenerationsPaneLocked: ReturnType<typeof usePanes>['setIsGenerationsPaneLocked'];
  lastVideoGeneration: ReturnType<typeof useLastVideoGeneration>;
}

interface PersistedShotEditorSettingsResult {
  shotUISettings: TravelUiSettings | undefined;
  updateShotUISettings: (scope: 'project' | 'shot', settings: Partial<TravelUiSettings>) => Promise<void>;
  isShotUISettingsLoading: boolean;
  updateGenerationsPaneSettings: (settings: Partial<GenerationsPaneSettings>) => void;
}

function useShotEditorBootstrap({
  selectedShotId,
  projectId,
  optimisticShotData,
}: Pick<ShotEditorProps, 'selectedShotId' | 'projectId' | 'optimisticShotData'>): ShotEditorBootstrapResult {
  const promptSettings = usePromptSettings();
  const motionSettings = useMotionSettings();
  const frameSettings = useFrameSettings();
  const modelSettings = useModelSettings();
  const phaseConfigSettings = usePhaseConfigSettings();
  const generationModeSettings = useGenerationModeSettings();
  const steerableMotionSettings = useSteerableMotionSettings();
  const loraSettings = useLoraSettings();
  const { isLoading: settingsLoadingFromContext } = useVideoTravelSettingsStatus();

  const shotSetup = useShotEditorSetup({
    selectedShotId,
    projectId,
    optimisticShotData: optimisticShotData as Shot | undefined,
    batchVideoFrames: frameSettings.batchVideoFrames,
  });

  const queryClient = useQueryClient();
  const { setCurrentShotId } = useCurrentShot();
  const { navigateToShot } = useShotNavigation();
  const { createShot } = useShotCreation();
  const addImageToShotMutation = useAddImageToShot();
  const removeImageFromShotMutation = useRemoveImageFromShot();
  const updateShotImageOrderMutation = useUpdateShotImageOrder();
  const { mutateAsync: addToShotMutation, mutateAsyncWithoutPosition: addToShotWithoutPositionMutation } =
    addImageToShotMutation;

  const createShotRef = useRef(createShot);
  createShotRef.current = createShot;
  const addToShotMutationRef = useRef(addToShotMutation);
  addToShotMutationRef.current = addToShotMutation;
  const addToShotWithoutPositionMutationRef = useRef(addToShotWithoutPositionMutation);
  addToShotWithoutPositionMutationRef.current = addToShotWithoutPositionMutation;

  const isMobile = useIsMobile();
  const { isPhone, aspectAdjustedColumns } = useAspectAdjustedColumns(shotSetup.effectiveAspectRatio);
  const setIsGenerationsPaneLocked = usePanesStore((state) => state.setIsGenerationsPaneLocked);
  const lastVideoGeneration = useLastVideoGeneration(selectedShotId);

  return {
    promptSettings,
    motionSettings,
    frameSettings,
    modelSettings,
    phaseConfigSettings,
    generationModeSettings,
    steerableMotionSettings,
    loraSettings,
    settingsLoadingFromContext,
    selectedShot: shotSetup.selectedShot,
    shots: shotSetup.shots,
    selectedProjectId: shotSetup.selectedProjectId,
    projects: shotSetup.projects,
    effectiveAspectRatio: shotSetup.effectiveAspectRatio,
    allShotImages: shotSetup.allShotImages,
    timelineImages: shotSetup.timelineImages,
    unpositionedImages: shotSetup.unpositionedImages,
    videoOutputs: shotSetup.videoOutputs,
    contextImages: shotSetup.contextImages,
    initialParentGenerations: shotSetup.initialParentGenerations,
    refs: shotSetup.refs,
    queryClient,
    setCurrentShotId,
    navigateToShot,
    addImageToShotMutation,
    removeImageFromShotMutation,
    updateShotImageOrderMutation,
    createShotRef,
    addToShotMutationRef,
    addToShotWithoutPositionMutationRef,
    isMobile,
    isPhone,
    aspectAdjustedColumns,
    setIsGenerationsPaneLocked,
    lastVideoGeneration,
  };
}

function usePersistedShotEditorSettings({
  selectedProjectId,
  selectedShotId,
  selectedShot,
}: {
  selectedProjectId: string | undefined;
  selectedShotId: string;
  selectedShot: Shot | undefined | null;
}): PersistedShotEditorSettingsResult {
  const {
    settings: shotUISettings,
    update: updateShotUISettings,
    isLoading: isShotUISettingsLoading,
  } = useToolSettings<TravelUiSettings>(SETTINGS_IDS.TRAVEL_UI_STATE, {
    projectId: selectedProjectId,
    shotId: selectedShot?.id,
    enabled: !!selectedShot?.id,
  });

  const { update: updateShotGenerationsPaneSettings } = useToolSettings<GenerationsPaneSettings>(
    SETTINGS_IDS.GENERATIONS_PANE,
    {
      shotId: selectedShotId,
      enabled: !!selectedShotId,
    },
  );

  const selectedShotIdRef = useRef(selectedShotId);
  selectedShotIdRef.current = selectedShotId;
  const updateShotGenerationsPaneSettingsRef = useRef(updateShotGenerationsPaneSettings);
  updateShotGenerationsPaneSettingsRef.current = updateShotGenerationsPaneSettings;

  const updateGenerationsPaneSettings = useCallback((settings: Partial<GenerationsPaneSettings>) => {
    const shotId = selectedShotIdRef.current;
    if (!shotId) {
      return;
    }

    const updatedSettings: GenerationsPaneSettings = {
      selectedShotFilter: settings.selectedShotFilter || shotId,
      excludePositioned: settings.excludePositioned ?? true,
      userHasCustomized: true,
    };
    updateShotGenerationsPaneSettingsRef.current('shot', updatedSettings);
  }, []);

  return {
    shotUISettings,
    updateShotUISettings,
    isShotUISettingsLoading,
    updateGenerationsPaneSettings,
  };
}

function useShotEditorScreenAssembly(
  screenModelArgs: BuildShotEditorScreenModelArgs,
): Pick<ShotEditorControllerResult, 'layoutProps'> {
  const screenModel = buildShotEditorScreenModel(screenModelArgs);
  const contextValue = useShotSettingsValue(screenModel.contextInput);

  return {
    layoutProps: useShotEditorLayoutModel({
      ...screenModel.layoutParams,
      contextValue,
    }),
  };
}

export function useShotEditorController({
  selectedShotId,
  projectId,
  optimisticShotData,
  onShotImagesUpdate,
  onBack,
  dimensionSource,
  onDimensionSourceChange,
  customWidth,
  onCustomWidthChange,
  customHeight,
  onCustomHeightChange,
  onPreviousShot,
  onNextShot,
  hasPrevious,
  hasNext,
  onUpdateShotName,
  getFinalVideoCount,
  getHasStructureVideo,
  headerContainerRef: parentHeaderRef,
  timelineSectionRef: parentTimelineRef,
  ctaContainerRef: parentCtaRef,
  onSelectionChange: parentOnSelectionChange,
  getGenerationDataRef: parentGetGenerationDataRef,
  generateVideoRef: parentGenerateVideoRef,
  nameClickRef: parentNameClickRef,
  isSticky,
  variantName: parentVariantName,
  onVariantNameChange: parentOnVariantNameChange,
  isGeneratingVideo: parentIsGeneratingVideo,
  videoJustQueued: parentVideoJustQueued,
  onDragStateChange,
}: ShotEditorProps): ShotEditorControllerResult {
  const {
    promptSettings,
    motionSettings,
    frameSettings,
    phaseConfigSettings,
    modelSettings,
    generationModeSettings,
    steerableMotionSettings,
    loraSettings,
    settingsLoadingFromContext,
    selectedShot,
    shots,
    selectedProjectId,
    projects,
    effectiveAspectRatio,
    allShotImages,
    timelineImages,
    unpositionedImages,
    videoOutputs,
    contextImages,
    initialParentGenerations,
    refs: { selectedShotRef, projectIdRef, allShotImagesRef, batchVideoFramesRef },
    queryClient,
    setCurrentShotId,
    navigateToShot,
    addImageToShotMutation,
    removeImageFromShotMutation,
    updateShotImageOrderMutation,
    createShotRef,
    addToShotMutationRef,
    addToShotWithoutPositionMutationRef,
    isMobile,
    isPhone,
    aspectAdjustedColumns,
    setIsGenerationsPaneLocked,
    lastVideoGeneration,
  } = useShotEditorBootstrap({
    selectedShotId,
    projectId,
    optimisticShotData,
  });
  const {
    shotUISettings,
    updateShotUISettings,
    isShotUISettingsLoading,
    updateGenerationsPaneSettings,
  } = usePersistedShotEditorSettings({
    selectedProjectId,
    selectedShotId,
    selectedShot,
  });

  const handleDragStateChange = useCallback((isDragging: boolean) => {
    onDragStateChange?.(isDragging);
  }, [onDragStateChange]);

  const { state, actions } = useShotEditorState();
  const setIsGenerationsPaneLockedRef = useRef(setIsGenerationsPaneLocked);
  setIsGenerationsPaneLockedRef.current = setIsGenerationsPaneLocked;
  const actionsRef = useRef(actions);
  actionsRef.current = actions;

  const centerSectionRef = useRef<HTMLDivElement>(null);
  const videoGalleryRef = useRef<HTMLDivElement>(null);
  const generateVideosCardRef = useRef<HTMLDivElement>(null);
  const joinSegmentsSectionRef = useRef<HTMLDivElement>(null);
  const swapButtonRef = useRef<HTMLButtonElement>(null);

  const { loraManager } = useLoraSync({
    selectedLoras: loraSettings.selectedLoras,
    onSelectedLorasChange: loraSettings.setSelectedLoras,
    projectId: selectedProjectId,
    availableLoras: loraSettings.availableLoras,
    batchVideoPrompt: promptSettings.prompt,
    onBatchVideoPromptChange: promptSettings.setPrompt,
    selectedModel: modelSettings.selectedModel,
  });
  const isShotLoraSettingsLoading = false;

  const { output, editing } = useShotEditorMediaAndOutputControllers({
    selectedProjectId,
    selectedShotId,
    selectedShot: selectedShot ?? null,
    projectId,
    timelineImages,
    effectiveAspectRatio,
    swapButtonRef,
    onUpdateShotName,
    state: { isEditingName: state.isEditingName, editingName: state.editingName },
    actions,
    generationTypeMode: phaseConfigSettings.generationTypeMode,
    setGenerationTypeMode: phaseConfigSettings.setGenerationTypeMode,
    selectedModel: modelSettings.selectedModel,
  });
  const { mediaEditing, joinWorkflow } = editing;
  const selectedOutputId = output.selectedOutputId;
  const demoteOrphanedVariants = output.demoteOrphanedVariants;

  const generationActions = useGenerationActions({
    state,
    actions,
    selectedShot: selectedShot || {} as Shot,
    projectId,
    batchVideoFrames: frameSettings.batchVideoFrames,
    orderedShotImages: allShotImages,
  });

  const shotActions = useShotActions({
    projectIdRef,
    selectedShotRef,
    allShotImagesRef,
    addToShotMutationRef,
    addToShotWithoutPositionMutationRef,
    createShotRef,
    setIsGenerationsPaneLockedRef,
    shots,
    navigateToShot,
    setCurrentShotId,
    updateGenerationsPaneSettings,
    isMobile,
    selectedShot,
  });

  useModeReadiness({
    selectedShot,
    contextImages,
    settingsLoading: settingsLoadingFromContext || false,
    isShotUISettingsLoading,
    isShotLoraSettingsLoading,
    isPhone,
    isMobile,
    generationMode: (() => {
      const mode = generationModeSettings.generationMode || 'batch';
      console.log('[ModeDebug][EditorController] final generationMode=%s (from settings: %s, fallback: batch)', mode, generationModeSettings.generationMode);
      return mode;
    })(),
    state,
    actions,
    onGenerationModeChange: generationModeSettings.setGenerationMode,
  });

  const accelerated = shotUISettings?.acceleratedMode ?? false;
  const randomSeed = shotUISettings?.randomSeed ?? false;
  const simpleFilteredImages = timelineImages;
  const turboMode = motionSettings.turboMode;

  useEffect(() => {
    if (simpleFilteredImages.length > 2 && turboMode) {
      motionSettings.setTurboMode(false);
    }
  }, [motionSettings, simpleFilteredImages.length, turboMode]);

  const generationControllerInput = useGenerationControllerInputModel({
    core: {
      projectId,
      selectedProjectId,
      selectedShotId,
      selectedShot: selectedShot ?? null,
      queryClient,
      onShotImagesUpdate,
      effectiveAspectRatio,
    },
    promptSettings,
    motionSettings,
    frameSettings,
    modelSettings,
    phaseConfigSettings,
    generationModeSettings,
    steerableMotionSettings,
    loraManager,
    mediaEditing,
    selectedOutputId,
    joinWorkflow,
    runtime: {
      accelerated,
      randomSeed,
      isShotUISettingsLoading,
      settingsLoadingFromContext,
      updateShotUISettings,
      setShowStepsNotification: actions.setShowStepsNotification,
    },
  });

  const {
    clearAllEnhancedPrompts,
    updatePairPromptsByIndex,
    loadPositions,
    handleBatchVideoPromptChangeWithClear,
    handleRandomSeedChange,
    handleAcceleratedChange,
    handleStepsChange,
    handleGenerateBatch,
    isSteerableMotionEnqueuing,
    steerableMotionJustQueued,
    isGenerationDisabled,
  } = useGenerationController(generationControllerInput);

  const applySettingsFromTask = useApplySettingsHandler({
    core: {
      projectId,
      selectedShot: selectedShot ?? undefined,
      simpleFilteredImages,
    },
    contexts: {
      model: {
        steerableMotionSettings: steerableMotionSettings.steerableMotionSettings,
        onSteerableMotionSettingsChange: steerableMotionSettings.setSteerableMotionSettings,
        onSelectedModelChange: modelSettings.setSelectedModel,
      },
      prompts: {
        onBatchVideoPromptChange: promptSettings.setPrompt,
        onSteerableMotionSettingsChange: steerableMotionSettings.setSteerableMotionSettings,
        updatePairPromptsByIndex,
      },
      generation: {
        onBatchVideoFramesChange: frameSettings.setFrames,
        onBatchVideoStepsChange: frameSettings.setSteps,
        onGuidanceScaleChange: modelSettings.setGuidanceScale,
      },
      modes: {
        onGenerationModeChange: generationModeSettings.setGenerationMode,
        onAdvancedModeChange: (advanced: boolean) => motionSettings.setMotionMode(advanced ? 'advanced' : 'basic'),
        onMotionModeChange: motionSettings.setMotionMode,
        onGenerationTypeModeChange: phaseConfigSettings.setGenerationTypeMode,
        onSmoothContinuationsChange: motionSettings.setSmoothContinuations,
      },
      advanced: {
        onPhaseConfigChange: phaseConfigSettings.setPhaseConfig,
        onPhasePresetSelect: phaseConfigSettings.selectPreset,
        onPhasePresetRemove: phaseConfigSettings.removePreset,
        onTurboModeChange: motionSettings.setTurboMode,
        onEnhancePromptChange: promptSettings.setEnhancePrompt,
      },
      textAddons: {
        onTextBeforePromptsChange: promptSettings.setTextBeforePrompts,
        onTextAfterPromptsChange: promptSettings.setTextAfterPrompts,
      },
      motion: {
        onAmountOfMotionChange: motionSettings.setAmountOfMotion,
      },
      loras: {
        availableLoras: loraSettings.availableLoras,
        loraManager,
      },
      structureVideo: {
        onStructureVideoInputChange: mediaEditing.handleStructureVideoInputChange,
      },
    },
    mutations: {
      addImageToShotMutation,
      removeImageFromShotMutation,
      loadPositions,
    },
  });

  const {
    isClearingFinalVideo,
    handleDeleteFinalVideo,
    handleReorderImagesInShot,
    handlePendingPositionApplied,
    handleImageUpload,
  } = useImageManagementController({
    queryClient,
    selectedShotRef,
    projectIdRef,
    allShotImagesRef,
    batchVideoFramesRef,
    updateShotImageOrderMutation,
    demoteOrphanedVariants,
    actionsRef,
    pendingFramePositions: state.pendingFramePositions,
    generationActions,
  });

  const { handleSelectionChangeLocal, currentMotionSettings } = useShotEditorBridge({
    parentGetGenerationDataRef,
    parentGenerateVideoRef,
    parentNameClickRef,
    parentOnSelectionChange,
    structureVideoPath: mediaEditing.structureVideoPath,
    structureVideoType: mediaEditing.structureVideoType,
    structureVideoTreatment: mediaEditing.structureVideoTreatment,
    structureVideoMotionStrength: mediaEditing.structureVideoMotionStrength,
    effectiveAspectRatio,
    selectedLoras: loraManager.selectedLoras,
    clearAllEnhancedPrompts,
    handleGenerateBatch,
    handleNameClick: mediaEditing.handleNameClick,
    textBeforePrompts: promptSettings.textBeforePrompts,
    textAfterPrompts: promptSettings.textAfterPrompts,
    prompt: promptSettings.prompt,
    negativePrompt: promptSettings.negativePrompt,
    enhancePrompt: promptSettings.enhancePrompt,
    batchVideoFrames: frameSettings.batchVideoFrames,
    lastVideoGeneration,
  });

  const { layoutProps } = useShotEditorScreenAssembly({
    core: {
      selectedShot,
      selectedShotId,
      projectId,
      selectedProjectId,
      effectiveAspectRatio,
      projects,
      state,
      actions,
      queryClient,
    },
    controllers: {
      mediaEditing,
      joinWorkflow,
      output: {
        selectedOutputId: output.selectedOutputId,
        setSelectedOutputId: output.setSelectedOutputId,
        parentGenerations: output.parentGenerations,
        segmentProgress: output.segmentProgress,
        isSegmentOutputsLoading: output.isSegmentOutputsLoading,
        joinSegmentSlots: output.joinSegmentSlots,
      },
      generationActions,
      shotActions,
      generationController: {
        isGenerationDisabled,
        isSteerableMotionEnqueuing,
        steerableMotionJustQueued,
        currentMotionSettings,
        handleAcceleratedChange,
        handleRandomSeedChange,
        handleGenerateBatch,
        handleBatchVideoPromptChangeWithClear,
        handleStepsChange,
        clearAllEnhancedPrompts,
      },
      imageManagement: {
        handleReorderImagesInShot,
        handleImageUpload,
        handlePendingPositionApplied,
        handleDeleteFinalVideo,
        isClearingFinalVideo,
      },
      bridge: {
        handleSelectionChangeLocal,
      },
      loraManager,
      availableLoras: loraSettings.availableLoras,
      shots,
    },
    settings: {
      promptSettings,
      motionSettings,
      frameSettings,
      modelSettings,
      phaseConfigSettings,
      generationModeSettings,
      isPhone,
      aspectAdjustedColumns,
      accelerated,
      randomSeed,
    },
    images: {
      allShotImages,
      timelineImages,
      unpositionedImages,
      contextImages,
      videoOutputs,
      simpleFilteredImages,
    },
    dimensions: {
      dimensionSource,
      onDimensionSourceChange,
      customWidth,
      onCustomWidthChange,
      customHeight,
      onCustomHeightChange,
    },
    sections: {
      onBack,
      onPreviousShot,
      onNextShot,
      hasPrevious,
      hasNext,
      onUpdateShotName,
      headerContainerRef: parentHeaderRef,
      timelineSectionRef: parentTimelineRef,
      ctaContainerRef: parentCtaRef,
      isSticky,
      parentVariantName,
      parentOnVariantNameChange,
      parentIsGeneratingVideo,
      parentVideoJustQueued,
      getFinalVideoCount,
      getHasStructureVideo,
      onDragStateChange: handleDragStateChange,
      refs: {
        centerSectionRef,
        videoGalleryRef,
        generateVideosCardRef,
        joinSegmentsSectionRef,
        swapButtonRef,
      },
      initialParentGenerations,
      applySettingsFromTask,
    },
  });

  return {
    hasSelectedShot: Boolean(selectedShot),
    layoutProps,
  };
}
