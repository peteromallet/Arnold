import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/shared/components/ui/runtime/sonner';
import type { Shot } from '@/domains/generation/types';
import type { ActiveLora } from '@/domains/lora/types/lora';
import { useEnqueueGenerationsInvalidation } from '@/shared/hooks/invalidation/useGenerationInvalidation';
import { DEFAULT_STEERABLE_MOTION_SETTINGS } from '@/shared/types/steerableMotion';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import type { resolveTravelStructureState } from '@/shared/lib/tasks/travelBetweenImages';
import { DEFAULT_PHASE_CONFIG, coerceSelectedModel } from '../../settings';
import { buildBasicModeGenerationRequest as buildBasicModePhaseConfig } from '../ShotEditor/services/generateVideo/modelPhase';
import { generateVideo } from '../ShotEditor/services/generateVideoService';
import { useVideoTravelSettingsMutations } from '../../providers/VideoTravelSettingsProvider';

type StructureState = ReturnType<typeof resolveTravelStructureState>;

// Stub: the batch generate flow no longer clears enhanced prompts here.
// Kept as a no-op so generateVideo's contract remains satisfied.
const clearAllEnhancedPrompts = async () => {};

export interface UseBatchVideoGenerationParams {
  shot: Shot;
  projectId: string | null | undefined;
  onClose: () => void;
  randomSeed: boolean;
  positionedImages: Array<{ metadata?: Record<string, unknown> | null }>;
  effectiveAspectRatio: string;
  selectedLoras: ActiveLora[];
  structureState: StructureState;
}

export interface UseBatchVideoGenerationResult {
  handleGenerate: () => Promise<void>;
  isGenerating: boolean;
  justQueued: boolean;
  isDisabled: boolean;
}

/**
 * Orchestrates the "batch" video generation call for a shot:
 * - Reads authored settings from VideoTravelSettingsProvider (so the hook stays
 *   aligned with the modal's live settings surface).
 * - Consumes already-derived view-state (positionedImages, aspect ratio, loras,
 *   structure state) as parameters — this hook is focused on orchestration, not
 *   data fetching.
 *
 * Behavior mirrors the previous inline handleGenerate in
 * useVideoGenerationModalController (telemetry toasts, invalidation scope, and
 * the 1000 ms justQueued delay are preserved).
 */
export function useBatchVideoGeneration({
  shot,
  projectId,
  onClose,
  randomSeed,
  positionedImages,
  effectiveAspectRatio,
  selectedLoras,
  structureState,
}: UseBatchVideoGenerationParams): UseBatchVideoGenerationResult {
  const queryClient = useQueryClient();
  const invalidateGenerations = useEnqueueGenerationsInvalidation();
  const { settings, updateField } = useVideoTravelSettingsMutations();

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

  const handleGenerate = useCallback(async () => {
    if (!projectId || !shot.id) {
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
        projectId,
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
          random_seed: randomSeed,
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
          projectId: projectId ?? undefined,
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
    projectId,
    shot,
    positionedImages,
    updateField,
    selectedLoras,
    settings,
    structureState,
    queryClient,
    effectiveAspectRatio,
    randomSeed,
    onClose,
    invalidateGenerations,
  ]);

  return {
    handleGenerate,
    isGenerating,
    justQueued,
    isDisabled: isGenerating || positionedImages.length < 1,
  };
}
