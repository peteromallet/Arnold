import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/shared/components/ui/runtime/sonner';
import type { Shot } from '@/domains/generation/types';
import type { ActiveLora } from '@/domains/lora/types/lora';
import type { LoraModel } from '@/domains/lora/types/lora';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { usePanesStore } from '@/shared/state/panesStore';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { useShotSettings } from '../../hooks/settings/useShotSettings';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { DEFAULT_STEERABLE_MOTION_SETTINGS } from '@/shared/types/steerableMotion';
import { DEFAULT_PHASE_CONFIG, coerceSelectedModel } from '@/tools/travel-between-images/settings';
import { usePublicLoras } from '@/features/resources/hooks/useResources';
import { useShotImages } from '@/shared/hooks/shots/useShotImages';
import { isPositioned, isVideoGeneration } from '@/shared/lib/typeGuards';
import { findClosestAspectRatio } from '@/shared/lib/media/aspectRatios';
import { useEnqueueGenerationsInvalidation } from '@/shared/hooks/invalidation/useGenerationInvalidation';
import { useProjectGenerationModesCache } from '@/shared/hooks/projects/useProjectGenerationModesCache';
import {
  DEFAULT_STRUCTURE_GUIDANCE_CONTROLS,
  DEFAULT_STRUCTURE_VIDEO,
  resolveTravelStructureState,
} from '@/shared/lib/tasks/travelBetweenImages';
import type { TravelGuidance } from '@/shared/lib/tasks/travelBetweenImages/taskTypes';
import type { TravelGuidanceMode } from '@/shared/lib/tasks/travelGuidance';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { buildBasicModeGenerationRequest as buildBasicModePhaseConfig } from '../ShotEditor/services/generateVideo/modelPhase';
import { generateVideo } from '../ShotEditor/services/generateVideoService';
import {
  BUILTIN_DEFAULT_I2V_ID,
  BUILTIN_DEFAULT_VACE_ID,
  FEATURED_PRESET_IDS,
} from '../MotionControl.constants';

const knownPresetIds = [
  BUILTIN_DEFAULT_I2V_ID,
  BUILTIN_DEFAULT_VACE_ID,
  ...FEATURED_PRESET_IDS,
];

const clearAllEnhancedPrompts = async () => {};

function resolveGuidanceKind(travelGuidance?: TravelGuidance): TravelGuidanceMode | undefined {
  if (!travelGuidance || travelGuidance.kind === 'none') {
    return undefined;
  }

  if (travelGuidance.kind === 'uni3c') {
    return 'uni3c';
  }

  return travelGuidance.mode;
}

function resolveEffectiveAspectRatio(
  projectAspectRatio: string,
  positionedImages: Array<{ metadata?: Record<string, unknown> | null }>,
): string {
  if (positionedImages.length === 0) {
    return projectAspectRatio;
  }

  const firstImage = positionedImages[0];
  const metadata = firstImage.metadata || {};
  const width = typeof metadata.width === 'number' ? metadata.width : null;
  const height = typeof metadata.height === 'number' ? metadata.height : null;
  if (!width || !height) {
    return projectAspectRatio;
  }

  return findClosestAspectRatio(width / height);
}

function mapSelectedLorasToActiveLoras(
  settingsLoras: Array<{
    id: string;
    name: string;
    path: string;
    strength: number;
    previewImageUrl?: string;
    trigger_word?: string;
  }> | undefined,
): ActiveLora[] {
  return (settingsLoras || []).map((lora) => ({
    id: lora.id,
    name: lora.name,
    path: lora.path,
    strength: lora.strength,
    previewImageUrl: lora.previewImageUrl,
    trigger_word: lora.trigger_word,
  }));
}

// --- Extracted hooks: only where there's a genuine independent boundary ---

/** Per-shot UI toggle persistence (accelerated mode, random seed). Own external hook dep. */
function useVideoUiSettings(isOpen: boolean, shotId: string) {
  const { settings: shotUISettings, update: updateShotUISettings } = useToolSettings<{
    acceleratedMode?: boolean;
    randomSeed?: boolean;
  }>(SETTINGS_IDS.TRAVEL_UI_STATE, {
    shotId: isOpen ? shotId : undefined,
    enabled: isOpen && Boolean(shotId),
  });

  const accelerated = shotUISettings?.acceleratedMode ?? false;
  const randomSeed = shotUISettings?.randomSeed ?? false;

  const setAccelerated = useCallback(
    (value: boolean) => {
      updateShotUISettings('shot', { acceleratedMode: value });
    },
    [updateShotUISettings],
  );

  const setRandomSeed = useCallback(
    (value: boolean) => {
      updateShotUISettings('shot', { randomSeed: value });
    },
    [updateShotUISettings],
  );

  return { accelerated, randomSeed, setAccelerated, setRandomSeed };
}

/** LoRA selection modal + CRUD handlers. Own state (modal open), cohesive unit. */
function useVideoGenerationLoras(
  settings: ReturnType<typeof useShotSettings>['settings'],
  updateField: ReturnType<typeof useShotSettings>['updateField'],
  availableLoras: NonNullable<ReturnType<typeof usePublicLoras>['data']> | undefined,
  selectedLoras: ActiveLora[],
) {
  const [isLoraModalOpen, setIsLoraModalOpen] = useState(false);

  const handleAddLora = useCallback(
    (lora: LoraModel) => {
      const newLora = {
        id: (lora['Model ID'] || '') as string,
        name: (lora.Name || '') as string,
        path: (lora.link || '') as string,
        strength: 1,
        previewImageUrl: lora['Preview Image URL'] as string | undefined,
        trigger_word: lora['Trigger Word'] as string | undefined,
      };

      const currentLoras = settings.loras || [];
      if (!currentLoras.some((existingLora) => existingLora.id === newLora.id)) {
        updateField('loras', [...currentLoras, newLora]);
      }
      setIsLoraModalOpen(false);
    },
    [settings.loras, updateField],
  );

  const handleRemoveLora = useCallback(
    (loraId: string) => {
      updateField(
        'loras',
        (settings.loras || []).filter((lora) => lora.id !== loraId),
      );
    },
    [settings.loras, updateField],
  );

  const handleLoraStrengthChange = useCallback(
    (loraId: string, strength: number) => {
      updateField(
        'loras',
        (settings.loras || []).map((lora) =>
          lora.id === loraId ? { ...lora, strength } : lora,
        ),
      );
    },
    [settings.loras, updateField],
  );

  const handleAddTriggerWord = useCallback(
    (word: string) => {
      const currentPrompt = settings.prompt || '';
      if (!currentPrompt.includes(word)) {
        const newPrompt = currentPrompt ? `${currentPrompt}, ${word}` : word;
        updateField('prompt', newPrompt);
      }
    },
    [settings.prompt, updateField],
  );

  const selectedLorasForModal = useMemo(() => {
    const catalog = availableLoras || [];
    return selectedLoras.flatMap((selectedLora) => {
      const fullLora = catalog.find((model) => model['Model ID'] === selectedLora.id);
      if (!fullLora) {
        return [];
      }
      return [{ ...fullLora, strength: selectedLora.strength }];
    });
  }, [availableLoras, selectedLoras]);

  return {
    isLoraModalOpen,
    openLoraModal: useCallback(() => setIsLoraModalOpen(true), []),
    closeLoraModal: useCallback(() => setIsLoraModalOpen(false), []),
    handleAddLora,
    handleRemoveLora,
    handleLoraStrengthChange,
    handleAddTriggerWord,
    selectedLorasForModal,
  };
}

// --- Main controller ---

export function useVideoGenerationModalController({ isOpen, onClose, shot }: {
  isOpen: boolean;
  onClose: () => void;
  shot: Shot;
}) {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const queryClient = useQueryClient();
  const invalidateGenerations = useEnqueueGenerationsInvalidation();
  const { navigateToShot } = useShotNavigation();
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const setIsShotsPaneLocked = usePanesStore((state) => state.setIsShotsPaneLocked);
  const { updateShotMode } = useProjectGenerationModesCache(selectedProjectId ?? '');

  // UI state
  const [isGenerating, setIsGenerating] = useState(false);
  const [justQueued, setJustQueued] = useState(false);
  const justQueuedTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (justQueuedTimeoutRef.current) {
        clearTimeout(justQueuedTimeoutRef.current);
      }
    };
  }, []);

  // Data
  const uiSettings = useVideoUiSettings(isOpen, shot.id);

  const { settings, status, updateField } = useShotSettings(
    isOpen ? shot.id : null,
    selectedProjectId,
  );

  const { data: availableLoras } = usePublicLoras();
  const { data: shotGenerations, isLoading: generationsLoading } = useShotImages(
    isOpen ? shot.id : null,
    { disableRefetch: false },
  );

  const positionedImages = useMemo(() => {
    if (!shotGenerations) return [];
    return shotGenerations
      .filter((gen) => !isVideoGeneration(gen) && isPositioned(gen))
      .sort((a, b) => (a.timeline_frame ?? 0) - (b.timeline_frame ?? 0));
  }, [shotGenerations]);

  const currentProject = projects.find((p) => p.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio || '16:9';

  const effectiveAspectRatio = useMemo(
    () => resolveEffectiveAspectRatio(projectAspectRatio, positionedImages),
    [positionedImages, projectAspectRatio],
  );

  const selectedLoras = useMemo(
    () => mapSelectedLorasToActiveLoras(settings.loras),
    [settings.loras],
  );
  const structureState = useMemo(
    () => resolveTravelStructureState(settings, {
      defaultEndFrame: settings.batchVideoFrames || 61,
      defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
      defaultMotionStrength: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.motionStrength,
      defaultStructureType: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.structureType,
      defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
    }),
    [settings],
  );
  const hasStructureVideo = structureState.structureVideos.length > 0;
  const guidanceKind = useMemo(
    () => resolveGuidanceKind(structureState.travelGuidance),
    [structureState.travelGuidance],
  );

  const validPresetId = useMemo(() => {
    const presetId = settings.selectedPhasePresetId;
    if (!presetId) return undefined;
    return knownPresetIds.includes(presetId) ? presetId : undefined;
  }, [settings.selectedPhasePresetId]);

  const isLoading =
    (status !== 'ready' && status !== 'saving' && status !== 'error') || generationsLoading;

  // LoRA management (extracted — has own modal state)
  const loras = useVideoGenerationLoras(settings, updateField, availableLoras, selectedLoras);

  // Navigation callbacks
  const handleNavigateToShot = useCallback(() => {
    if (isShotsPaneLocked) {
      setIsShotsPaneLocked(false);
    }
    onClose();
    navigateToShot(shot);
  }, [isShotsPaneLocked, setIsShotsPaneLocked, navigateToShot, onClose, shot]);

  const handleDialogOpenChange = useCallback(
    (open: boolean) => {
      if (!open && !loras.isLoraModalOpen) {
        onClose();
      }
    },
    [loras.isLoraModalOpen, onClose],
  );

  // Generate
  const handleGenerate = useCallback(async () => {
    if (!selectedProjectId || !shot.id) {
      toast.error('No project or shot selected.');
      return;
    }

    if (positionedImages.length < 1) {
      toast.error('At least 1 positioned image is required.');
      return;
    }

    setIsGenerating(true);
    try {
      updateField('generationMode', 'batch');

      const userLoras = selectedLoras.map((lora) => ({
        path: lora.path,
        strength: lora.strength,
      }));
      const { phaseConfig: basicPhaseConfig } = buildBasicModePhaseConfig(
        settings.amountOfMotion || 50,
        userLoras,
      );

      const motionMode = settings.motionMode || 'basic';
      const advancedMode = motionMode === 'advanced';
      const finalPhaseConfig = advancedMode
        ? settings.phaseConfig || DEFAULT_PHASE_CONFIG
        : basicPhaseConfig;

      const mergedSteerableSettings = {
        ...DEFAULT_STEERABLE_MOTION_SETTINGS,
        ...(settings.steerableMotionSettings || {}),
      };

      const result = await generateVideo({
        projectId: selectedProjectId,
        selectedShotId: shot.id,
        selectedShot: shot,
        queryClient,
        effectiveAspectRatio,
        generationMode: 'batch',
        promptConfig: {
          base_prompt: settings.prompt || '',
          enhance_prompt: settings.enhancePrompt,
          text_before_prompts: settings.textBeforePrompts,
          text_after_prompts: settings.textAfterPrompts,
          default_negative_prompt: settings.negativePrompt || mergedSteerableSettings.negative_prompt,
        },
        motionConfig: {
          amount_of_motion: settings.amountOfMotion || 50,
          motion_mode: motionMode,
          advanced_mode: advancedMode,
          phase_config: finalPhaseConfig,
          selected_phase_preset_id: settings.selectedPhasePresetId ?? undefined,
        },
        modelConfig: {
          selectedModel: coerceSelectedModel(settings.selectedModel),
          num_inference_steps: settings.batchVideoSteps || 6,
          guidance_scale: settings.guidanceScale,
          seed: mergedSteerableSettings.seed,
          random_seed: uiSettings.randomSeed,
          turbo_mode: settings.turboMode || false,
          debug: mergedSteerableSettings.debug || false,
          generation_type_mode: settings.generationTypeMode || 'i2v',
          ltxHdResolution: settings.ltxHdResolution ?? true,
        },
        travelGuidance: structureState.travelGuidance,
        structureGuidance: structureState.structureGuidance,
        structureVideos: structureState.structureVideos,
        batchVideoFrames: settings.batchVideoFrames || 61,
        selectedLoras: selectedLoras.map((lora) => ({
          id: lora.id,
          path: lora.path,
          strength: lora.strength,
          name: lora.name,
        })),
        variantNameParam: '',
        clearAllEnhancedPrompts,
      });

      if (result.ok) {
        setJustQueued(true);
        if (justQueuedTimeoutRef.current) {
          clearTimeout(justQueuedTimeoutRef.current);
        }
        justQueuedTimeoutRef.current = window.setTimeout(() => {
          setJustQueued(false);
          justQueuedTimeoutRef.current = null;
          onClose();
        }, 1000);

        invalidateGenerations(shot.id, {
          reason: 'video-generation-modal-success',
          scope: 'all',
          includeProjectUnified: true,
          projectId: selectedProjectId ?? undefined,
        });
      } else {
        toast.error(result.message || 'Failed to generate video');
      }
    } catch (error) {
      normalizeAndPresentError(error, {
        context: 'VideoGenerationModal',
        toastTitle: 'Failed to generate video',
      });
    } finally {
      setIsGenerating(false);
    }
  }, [
    selectedProjectId,
    shot,
    positionedImages,
    updateField,
    selectedLoras,
    settings,
    structureState,
    queryClient,
    effectiveAspectRatio,
    uiSettings.randomSeed,
    onClose,
    invalidateGenerations,
  ]);

  return {
    projects,
    selectedProjectId,
    settings,
    status,
    updateField,
    availableLoras,
    positionedImages,
    isLoading,
    isGenerating,
    justQueued,
    isDisabled: isGenerating || isLoading || positionedImages.length < 1,
    hasStructureVideo,
    guidanceKind,
    ...uiSettings,
    validPresetId,
    selectedLoras,
    ...loras,
    effectiveAspectRatio,
    shotGenerations: shotGenerations || [],
    handleGenerate,
    handleNavigateToShot,
    handleDialogOpenChange,
    updateShotMode,
  };
}
