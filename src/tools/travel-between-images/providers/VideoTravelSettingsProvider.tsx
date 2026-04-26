/**
 * VideoTravelSettingsProvider - Centralized settings context for Video Travel tool
 *
 * This provider owns all shot-specific settings state, making it accessible to
 * any child component without prop drilling. Settings are persisted via useShotSettings.
 *
 * Architecture:
 * - Wraps useShotSettings (state + persistence)
 * - Wraps useVideoTravelSettingsHandlers (all update handlers)
 * - Exposes focused hooks for each settings domain
 *
 * Usage:
 * ```tsx
 * // In VideoTravelToolPage
 * <VideoTravelSettingsProvider projectId={projectId} shotId={shotId}>
 *   <ShotSettingsEditor />
 * </VideoTravelSettingsProvider>
 *
 * // In any child component
 * const { prompt, setPrompt } = usePromptSettings();
 * const { motionMode, setMotionMode } = useMotionSettings();
 * ```
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Shot } from '@/domains/generation/types';
import { useShotSettings, UseShotSettingsReturn } from '../hooks/settings/useShotSettings';
import {
  useVideoTravelSettingsHandlers as useVideoTravelSettingsHandlersCore,
  VideoTravelSettingsHandlers,
} from '../hooks/settings/useVideoTravelSettingsHandlers';
import {
  VideoTravelSettings,
  PhaseConfig,
  MODEL_DEFAULTS,
  clampFrameCountToPolicy,
  coerceSelectedModel,
  getModelSpec,
  normalizeVideoTravelSettings,
  resolveGenerationPolicy,
  type SelectedModel,
} from '../settings';
import type { ActiveLora, LoraModel } from '@/domains/lora/types/lora';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { queryKeys } from '@/shared/lib/queryKeys';

// =============================================================================
// CONTEXT TYPES
// =============================================================================

interface VideoTravelSettingsContextValue {
  // Core state
  settings: VideoTravelSettings;
  status: 'idle' | 'loading' | 'ready' | 'saving' | 'error';
  isDirty: boolean;
  isLoading: boolean;

  // Shot info
  shotId: string | null;
  projectId: string | null;

  // All handlers from useVideoTravelSettingsHandlers
  handlers: VideoTravelSettingsHandlers;

  // Direct access to updateField/updateFields for custom updates
  updateField: UseShotSettingsReturn['updateField'];
  updateFields: UseShotSettingsReturn['updateFields'];

  // Save operations
  save: () => Promise<void>;
  saveImmediate: () => Promise<void>;

  // LoRAs (passed through from parent)
  availableLoras: LoraModel[];
}

interface VideoTravelSettingsStatusValue {
  status: VideoTravelSettingsContextValue['status'];
  isDirty: boolean;
  isLoading: boolean;
  shotId: string | null;
  projectId: string | null;
  save: () => Promise<void>;
  saveImmediate: () => Promise<void>;
  updateField: UseShotSettingsReturn['updateField'];
  updateFields: UseShotSettingsReturn['updateFields'];
}

const VideoTravelSettingsDataContext = createContext<VideoTravelSettings | null>(null);
const VideoTravelSettingsHandlersContext = createContext<VideoTravelSettingsHandlers | null>(null);
const VideoTravelSettingsStatusContext = createContext<VideoTravelSettingsStatusValue | null>(null);
const VideoTravelSettingsLorasContext = createContext<LoraModel[] | null>(null);

function requireVideoTravelSettingsContext<T>(value: T | null, hookName: string): T {
  if (!value) {
    throw new Error(`${hookName} must be used within VideoTravelSettingsProvider`);
  }
  return value;
}

// =============================================================================
// PROVIDER COMPONENT
// =============================================================================

/**
 * Seed the useToolSettings cache from shot data already in memory (from useListShots).
 * Must be called before useShotSettings so the cache is populated when useQuery runs.
 */
function useSeedSettingsCache(
  shotId: string | null | undefined,
  projectId: string | null | undefined,
  selectedShot: Shot | null,
) {
  const queryClient = useQueryClient();
  const seededRef = useRef<string | null>(null);

  if (shotId && shotId !== seededRef.current && selectedShot?.settings) {
    const raw = (selectedShot.settings as Record<string, unknown>)?.[TOOL_IDS.TRAVEL_BETWEEN_IMAGES];
    if (raw && typeof raw === 'object') {
      const cacheKey = queryKeys.settings.tool(TOOL_IDS.TRAVEL_BETWEEN_IMAGES, projectId ?? undefined, shotId);
      // Only seed if the cache is empty — don't overwrite a more complete cascade result
      if (!queryClient.getQueryData(cacheKey)) {
        queryClient.setQueryData(cacheKey, {
          settings: normalizeVideoTravelSettings(raw as Record<string, unknown>),
          hasShotSettings: true,
        });
        console.log('[ModeDebug][CacheSeed] seeded settings cache for shot %s', shotId);
      }
    }
    seededRef.current = shotId;
  }
}

interface VideoTravelSettingsProviderProps {
  projectId: string | null | undefined;
  shotId: string | null | undefined;
  selectedShot: Shot | null;
  availableLoras: LoraModel[];
  /** Function to optimistically update generation mode cache (from useProjectGenerationModesCache) */
  updateShotMode: (shotId: string, mode: 'batch' | 'timeline' | 'by-pair') => void;
  children: React.ReactNode;
}

export const VideoTravelSettingsProvider: React.FC<VideoTravelSettingsProviderProps> = ({
  projectId,
  shotId,
  selectedShot,
  availableLoras,
  updateShotMode,
  children,
}) => {
  // Seed the useToolSettings React Query cache from the shot object that's already
  // in memory (from useListShots). This eliminates the loading flash — the settings
  // fetch resolves instantly from cache instead of re-fetching the same DB row.
  useSeedSettingsCache(shotId, projectId, selectedShot);

  // Core settings hook - manages state + persistence
  const shotSettings = useShotSettings(shotId, projectId);

  console.log('[ModeDebug][SettingsProvider] shotId=%s status=%s generationMode=%s', shotId, shotSettings.status, shotSettings.settings?.generationMode ?? 'NOT SET');

  // Create ref for handlers (they need ref to avoid recreation)
  const shotSettingsRef = useRef(shotSettings);
  shotSettingsRef.current = shotSettings;

  // All handlers
  const handlers = useVideoTravelSettingsHandlersCore({
    shotSettingsRef,
    currentShotId: shotId || null,
    selectedShot,
    updateShotMode,
  });

  const setSelectedModel = useCallback((nextModel: SelectedModel) => {
    const currentSettings = shotSettingsRef.current.settings;
    const currentModel = coerceSelectedModel(currentSettings.selectedModel);

    if (currentModel === nextModel) {
      return;
    }

    const currentDefaults = MODEL_DEFAULTS[currentModel];
    const nextDefaults = MODEL_DEFAULTS[nextModel];
    const nextSpec = getModelSpec(nextModel);
    const currentFrames = clampFrameCountToPolicy(
      currentSettings.batchVideoFrames ?? currentDefaults.frames,
      getModelSpec(currentModel),
      {
        smoothContinuations: currentSettings.smoothContinuations ?? false,
        requestedExecutionMode: currentSettings.generationTypeMode ?? 'i2v',
      },
    );
    const modelSettingsByModel = {
      ...(currentSettings.modelSettingsByModel ?? {}),
      [currentModel]: {
        batchVideoFrames: currentFrames,
        batchVideoSteps: currentSettings.batchVideoSteps ?? currentDefaults.steps,
        guidanceScale: currentSettings.guidanceScale ?? currentDefaults.guidanceScale,
      },
    };
    const nextSubstate = modelSettingsByModel[nextModel];
    const nextFrames = clampFrameCountToPolicy(
      nextSubstate?.batchVideoFrames ?? nextDefaults.frames,
      nextSpec,
      {
        smoothContinuations: currentSettings.smoothContinuations ?? false,
        requestedExecutionMode: currentSettings.generationTypeMode ?? 'i2v',
      },
    );

    shotSettingsRef.current.updateFields({
      selectedModel: nextModel,
      batchVideoFrames: nextFrames,
      batchVideoSteps: nextSubstate?.batchVideoSteps ?? nextDefaults.steps,
      guidanceScale: nextSubstate?.guidanceScale ?? nextDefaults.guidanceScale,
      modelSettingsByModel: {
        ...modelSettingsByModel,
        [nextModel]: {
          batchVideoFrames: nextFrames,
          batchVideoSteps: nextSubstate?.batchVideoSteps ?? nextDefaults.steps,
          guidanceScale: nextSubstate?.guidanceScale ?? nextDefaults.guidanceScale,
        },
      },
      ...(!nextSpec.ui.turboMode
        ? {
          turboMode: false,
          motionMode: 'basic',
          advancedMode: false,
        }
        : {}),
    });
  }, []);

  useEffect(() => {
    const currentSettings = shotSettings.settings;
    const currentModel = coerceSelectedModel(currentSettings.selectedModel);
    const spec = getModelSpec(currentModel);
    const requestedExecutionMode = currentSettings.generationTypeMode ?? 'i2v';
    const nextSmoothContinuations = currentSettings.smoothContinuations
      && resolveGenerationPolicy(spec, {
        smoothContinuations: true,
        requestedExecutionMode,
      }).continuation.enabled;
    const normalizedFrames = clampFrameCountToPolicy(
      currentSettings.batchVideoFrames ?? MODEL_DEFAULTS[currentModel].frames,
      spec,
      {
        smoothContinuations: nextSmoothContinuations,
        requestedExecutionMode,
      },
    );
    const currentSubstate = currentSettings.modelSettingsByModel?.[currentModel];
    const needsSmoothReset = (currentSettings.smoothContinuations ?? false) !== nextSmoothContinuations;
    const needsFrameReset = currentSettings.batchVideoFrames !== normalizedFrames
      || currentSubstate?.batchVideoFrames !== normalizedFrames;

    if (!needsSmoothReset && !needsFrameReset) {
      return;
    }

    shotSettings.updateFields({
      ...(needsSmoothReset ? { smoothContinuations: nextSmoothContinuations } : {}),
      ...(needsFrameReset
        ? {
          batchVideoFrames: normalizedFrames,
          modelSettingsByModel: {
            ...(currentSettings.modelSettingsByModel ?? {}),
            [currentModel]: {
              ...currentSubstate,
              batchVideoFrames: normalizedFrames,
            },
          },
        }
        : {}),
    });
  }, [
    shotSettings.settings.batchVideoFrames,
    shotSettings.settings.selectedModel,
    shotSettings.settings.generationTypeMode,
    shotSettings.settings.smoothContinuations,
    shotSettings.settings.modelSettingsByModel,
    shotSettings.updateFields,
  ]);

  const setGuidanceScale = useCallback((guidanceScale: number) => {
    const currentSettings = shotSettingsRef.current.settings;
    const currentModel = coerceSelectedModel(currentSettings.selectedModel);

    shotSettingsRef.current.updateFields({
      guidanceScale,
      modelSettingsByModel: {
        ...(currentSettings.modelSettingsByModel ?? {}),
        [currentModel]: {
          batchVideoFrames: currentSettings.batchVideoFrames ?? MODEL_DEFAULTS[currentModel].frames,
          batchVideoSteps: currentSettings.batchVideoSteps ?? MODEL_DEFAULTS[currentModel].steps,
          guidanceScale,
        },
      },
    });
  }, []);

  const providerHandlers = useMemo<VideoTravelSettingsHandlers>(() => ({
    ...handlers,
    handleSelectedModelChange: setSelectedModel,
    handleGuidanceScaleChange: setGuidanceScale,
  }), [handlers, setGuidanceScale, setSelectedModel]);

  const statusValue = useMemo<VideoTravelSettingsStatusValue>(() => ({
    status: shotSettings.status,
    isDirty: shotSettings.isDirty,
    isLoading: shotSettings.status === 'loading' || shotSettings.status === 'idle',
    shotId: shotSettings.shotId,
    projectId: projectId || null,
    updateField: shotSettings.updateField,
    updateFields: shotSettings.updateFields,
    save: shotSettings.save,
    saveImmediate: shotSettings.saveImmediate,
  }), [
    shotSettings.status,
    shotSettings.isDirty,
    shotSettings.shotId,
    shotSettings.updateField,
    shotSettings.updateFields,
    shotSettings.save,
    shotSettings.saveImmediate,
    projectId,
  ]);

  return (
    <VideoTravelSettingsStatusContext.Provider value={statusValue}>
      <VideoTravelSettingsDataContext.Provider value={shotSettings.settings}>
        <VideoTravelSettingsHandlersContext.Provider value={providerHandlers}>
          <VideoTravelSettingsLorasContext.Provider value={availableLoras}>
            {children}
          </VideoTravelSettingsLorasContext.Provider>
        </VideoTravelSettingsHandlersContext.Provider>
      </VideoTravelSettingsDataContext.Provider>
    </VideoTravelSettingsStatusContext.Provider>
  );
};

export function useVideoTravelSettingsStatus(): VideoTravelSettingsStatusValue {
  return requireVideoTravelSettingsContext(
    useContext(VideoTravelSettingsStatusContext),
    'useVideoTravelSettingsStatus',
  );
}

export function useVideoTravelSettingsMutations() {
  const settings = requireVideoTravelSettingsContext(
    useContext(VideoTravelSettingsDataContext),
    'useVideoTravelSettingsMutations',
  );
  const status = useVideoTravelSettingsStatus();

  return {
    settings,
    status: status.status,
    shotId: status.shotId,
    updateField: status.updateField,
    updateFields: status.updateFields,
  };
}

export function useVideoTravelSettingsHandlers() {
  return requireVideoTravelSettingsContext(
    useContext(VideoTravelSettingsHandlersContext),
    'useVideoTravelSettingsHandlers',
  );
}

function useVideoTravelSettingsData() {
  return requireVideoTravelSettingsContext(
    useContext(VideoTravelSettingsDataContext),
    'useVideoTravelSettingsData',
  );
}

function useVideoTravelSettingsLoras() {
  return requireVideoTravelSettingsContext(
    useContext(VideoTravelSettingsLorasContext),
    'useVideoTravelSettingsLoras',
  );
}

/** @deprecated Migrate production code to the narrower video-travel settings hooks. */
export function useVideoTravelSettings(): VideoTravelSettingsContextValue {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  const {
    status,
    isDirty,
    isLoading,
    shotId,
    projectId,
    save,
    saveImmediate,
    updateField,
    updateFields,
  } = useVideoTravelSettingsStatus();
  const availableLoras = useVideoTravelSettingsLoras();

  return {
    settings,
    status,
    isDirty,
    isLoading,
    shotId,
    projectId,
    handlers,
    updateField,
    updateFields,
    save,
    saveImmediate,
    availableLoras,
  };
}

// =============================================================================
// FOCUSED HOOKS - Domain-specific slices
// =============================================================================

/**
 * Prompt-related settings
 */
export function usePromptSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  return useMemo(() => ({
    prompt: settings.prompt || '',
    negativePrompt: settings.negativePrompt || '',
    textBeforePrompts: settings.textBeforePrompts || '',
    textAfterPrompts: settings.textAfterPrompts || '',
    enhancePrompt: settings.enhancePrompt,
    setPrompt: handlers.handleBatchVideoPromptChange,
    setNegativePrompt: handlers.handleNegativePromptChange,
    setTextBeforePrompts: handlers.handleTextBeforePromptsChange,
    setTextAfterPrompts: handlers.handleTextAfterPromptsChange,
    setEnhancePrompt: handlers.handleEnhancePromptChange,
  }), [settings.prompt, settings.negativePrompt, settings.textBeforePrompts, settings.textAfterPrompts, settings.enhancePrompt, handlers]);
}

/**
 * Motion-related settings
 */
export function useMotionSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  const availableLoras = useVideoTravelSettingsLoras();
  return useMemo(() => ({
    amountOfMotion: settings.amountOfMotion ?? 50,
    motionMode: settings.motionMode || 'basic',
    turboMode: settings.turboMode ?? false,
    smoothContinuations: settings.smoothContinuations ?? false,
    setAmountOfMotion: handlers.handleAmountOfMotionChange,
    setMotionMode: handlers.handleMotionModeChange,
    setTurboMode: handlers.handleTurboModeChange,
    setSmoothContinuations: handlers.handleSmoothContinuationsChange,
    availableLoras,
  }), [settings.amountOfMotion, settings.motionMode, settings.turboMode, settings.smoothContinuations, handlers, availableLoras]);
}

/**
 * Frame/duration settings
 */
export function useFrameSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  return useMemo(() => ({
    batchVideoFrames: settings.batchVideoFrames ?? 61,
    batchVideoSteps: settings.batchVideoSteps ?? 6,
    setFrames: handlers.handleBatchVideoFramesChange,
    setSteps: handlers.handleBatchVideoStepsChange,
  }), [settings.batchVideoFrames, settings.batchVideoSteps, handlers]);
}

export function useModelSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  return useMemo(() => ({
    selectedModel: coerceSelectedModel(settings.selectedModel),
    guidanceScale: settings.guidanceScale,
    ltxHdResolution: settings.ltxHdResolution ?? true,
    setSelectedModel: handlers.handleSelectedModelChange,
    setGuidanceScale: handlers.handleGuidanceScaleChange,
    setLtxHdResolution: (value: boolean) => handlers.updateField('ltxHdResolution', value),
  }), [settings.selectedModel, settings.guidanceScale, settings.ltxHdResolution, handlers]);
}

/**
 * Phase config (advanced mode) settings
 */
export function usePhaseConfigSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  return useMemo(() => ({
    phaseConfig: settings.phaseConfig,
    selectedPhasePresetId: settings.selectedPhasePresetId,
    generationTypeMode: settings.generationTypeMode || 'i2v',
    advancedMode: settings.advancedMode ?? false,
    setPhaseConfig: handlers.handlePhaseConfigChange,
    selectPreset: handlers.handlePhasePresetSelect,
    removePreset: handlers.handlePhasePresetRemove,
    setGenerationTypeMode: handlers.handleGenerationTypeModeChange,
    restoreDefaults: handlers.handleRestoreDefaults,
  }), [settings.phaseConfig, settings.selectedPhasePresetId, settings.generationTypeMode, settings.advancedMode, handlers]);
}

/**
 * Steerable motion settings (seed, model, etc.)
 */
export function useSteerableMotionSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  return useMemo(() => ({
    steerableMotionSettings: settings.steerableMotionSettings,
    setSteerableMotionSettings: handlers.handleSteerableMotionSettingsChange,
  }), [settings.steerableMotionSettings, handlers]);
}

/**
 * LoRA settings
 */
export function useLoraSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  const availableLoras = useVideoTravelSettingsLoras();
  return useMemo(() => {
    const handleAddLora = (lora: LoraModel) => {
      const newLora: ActiveLora = {
        id: (lora['Model ID'] || '') as string,
        name: (lora.Name || '') as string,
        path: (lora.link || '') as string,
        strength: 1,
        previewImageUrl: lora['Preview Image URL'] as string | undefined,
        trigger_word: lora['Trigger Word'] as string | undefined,
      };

      const currentLoras = settings.loras || [];
      if (!currentLoras.some((existingLora) => existingLora.id === newLora.id)) {
        handlers.updateField('loras', [...currentLoras, newLora]);
      }
    };

    const handleRemoveLora = (loraId: string) => {
      handlers.updateField(
        'loras',
        (settings.loras || []).filter((lora) => lora.id !== loraId),
      );
    };

    const handleLoraStrengthChange = (loraId: string, strength: number) => {
      handlers.updateField(
        'loras',
        (settings.loras || []).map((lora) =>
          lora.id === loraId ? { ...lora, strength } : lora,
        ),
      );
    };

    const handleAddTriggerWord = (word: string) => {
      const currentPrompt = settings.prompt || '';
      if (!currentPrompt.includes(word)) {
        const newPrompt = currentPrompt ? `${currentPrompt}, ${word}` : word;
        handlers.updateField('prompt', newPrompt);
      }
    };

    return {
      selectedLoras: settings.loras || [],
      availableLoras,
      setSelectedLoras: handlers.handleSelectedLorasChange,
      handleAddLora,
      handleRemoveLora,
      handleLoraStrengthChange,
      handleAddTriggerWord,
    };
  }, [settings.loras, settings.prompt, availableLoras, handlers]);
}

/**
 * Generation mode (batch vs timeline)
 */
export function useGenerationModeSettings() {
  const settings = useVideoTravelSettingsData();
  const handlers = useVideoTravelSettingsHandlers();
  const { shotId } = useVideoTravelSettingsStatus();
  console.log('[ModeDebug][GenModeSettings] shotId=%s raw generationMode=%s resolved=%s', shotId, settings.generationMode, settings.generationMode || 'timeline');
  return useMemo(() => ({
    generationMode: settings.generationMode || 'timeline',
    videoControlMode: settings.videoControlMode || 'batch',
    setGenerationMode: handlers.handleGenerationModeChange,
    setVideoControlMode: handlers.handleVideoControlModeChange,
  }), [settings.generationMode, settings.videoControlMode, handlers]);
}

/**
 * Save operations
 */
export function useSettingsSave() {
  const handlers = useVideoTravelSettingsHandlers();
  const { save, saveImmediate, isDirty, status } = useVideoTravelSettingsStatus();
  return useMemo(() => ({
    save,
    saveImmediate,
    onBlurSave: handlers.handleBlurSave,
    isDirty,
    isSaving: status === 'saving',
  }), [save, saveImmediate, handlers, isDirty, status]);
}

// =============================================================================
// RE-EXPORT TYPES
// =============================================================================

export type { VideoTravelSettings, PhaseConfig };
