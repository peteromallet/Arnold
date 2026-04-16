import { useState, useEffect, useCallback, useRef } from 'react';
import { GenerationRow } from '@/domains/generation/types';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { createTask } from '@/shared/lib/taskCreation';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useShotGenerationMetadata } from '@/shared/hooks/shots/useShotGenerationMetadata';
import type { EditAdvancedSettings, QwenEditModel } from './useGenerationEditSettings';
import type { LoraMode } from '../model/editSettingsTypes';
import { isKleinModel } from '../model/editSettingsTypes';
import { convertToHiresFixApiParams } from './useGenerationEditSettings';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import type { BrushStroke } from './inpainting/types';
import { useTaskPlaceholder } from '@/shared/hooks/tasks/useTaskPlaceholder';

interface UseMagicEditModeParams {
  media: GenerationRow;
  selectedProjectId: string | null;
  isInpaintMode: boolean;
  setIsInpaintMode: (value: boolean) => void;
  handleEnterInpaintMode: () => void;
  handleGenerateInpaint: () => Promise<void>;
  brushStrokes: BrushStroke[];
  inpaintPrompt: string;
  setInpaintPrompt: (value: string) => void;
  inpaintNumGenerations: number;
  setInpaintNumGenerations: (value: number) => void;
  editModeLoras: Array<{ url: string; strength: number }> | undefined;
  loraMode: LoraMode;
  setLoraMode: (mode: LoraMode) => void;
  sourceUrlForTasks: string;
  imageDimensions: { width: number; height: number } | null;
  toolTypeOverride?: string;
  // Variant tracking - when editing from a non-primary variant
  activeVariantId?: string | null;
  activeVariantLocation?: string | null;
  // Create as new generation instead of variant
  createAsGeneration?: boolean;
  // Advanced settings for hires fix
  advancedSettings?: EditAdvancedSettings;
  // Model selection for cloud mode
  qwenEditModel?: QwenEditModel;
  // Disable DB queries (for form-only mode with placeholder media)
  enabled?: boolean;
  /** Start with isMagicEditMode=true (skips the "select an option" step) */
  initialActive?: boolean;
}

interface UseMagicEditModeReturn {
  isMagicEditMode: boolean;
  setIsMagicEditMode: (value: boolean) => void;
  magicEditPrompt: string;
  setMagicEditPrompt: (value: string) => void;
  magicEditNumImages: number;
  setMagicEditNumImages: (value: number) => void;
  isCreatingMagicEditTasks: boolean;
  magicEditTasksCreated: boolean;
  toolPanelPosition: 'top' | 'bottom';
  setToolPanelPosition: (value: 'top' | 'bottom') => void;
  handleEnterMagicEditMode: () => void;
  handleExitMagicEditMode: () => void;
  handleUnifiedGenerate: () => Promise<void>;
  isSpecialEditMode: boolean;
}

/**
 * Hook to manage Magic Edit mode state and unified generate handler
 * Handles auto-enter, prompt persistence, and routing between inpaint/magic edit
 */
export const useMagicEditMode = ({
  media,
  selectedProjectId,
  isInpaintMode,
  setIsInpaintMode,
  handleEnterInpaintMode,
  handleGenerateInpaint,
  brushStrokes,
  inpaintPrompt,
  setInpaintPrompt,
  inpaintNumGenerations,
  setInpaintNumGenerations,
  editModeLoras,
  loraMode,
  setLoraMode,
  sourceUrlForTasks,
  imageDimensions,
  toolTypeOverride,
  activeVariantId,
  activeVariantLocation,
  createAsGeneration,
  advancedSettings,
  qwenEditModel,
  enabled = true,
  initialActive = false,
}: UseMagicEditModeParams): UseMagicEditModeReturn => {
  // Magic Edit mode state
  const [isMagicEditMode, setIsMagicEditMode] = useState(initialActive);
  const [magicEditPrompt, setMagicEditPrompt] = useState('');
  const [magicEditNumImages, setMagicEditNumImages] = useState(4);
  const [isCreatingMagicEditTasks, setIsCreatingMagicEditTasks] = useState(false);
  const [magicEditTasksCreated, setMagicEditTasksCreated] = useState(false);
  const [toolPanelPosition, setToolPanelPosition] = useState<'top' | 'bottom'>('bottom');

  const { currentShotId } = useCurrentShot();
  const run = useTaskPlaceholder();

  // Prompt persistence for magic edit mode
  const {
    addMagicEditPrompt,
    getLastMagicEditPrompt,
    getLastSettings,
    isLoading: isLoadingMetadata
  } = useShotGenerationMetadata({
    shotId: currentShotId || '',
    shotGenerationId: media.id,
    enabled: !!(currentShotId && media.id) && enabled !== false
  });

  // Guard against double-entry during async state updates
  const isEnteringEditModeRef = useRef(false);
  // Track if we've already restored the prompt for this mode entry (prevents re-restore on clear)
  const hasRestoredPromptRef = useRef(false);
  const isInSceneLoraMode = loraMode === 'in-scene';

  // Reset flags when media changes
  useEffect(() => {
    isEnteringEditModeRef.current = false;
    hasRestoredPromptRef.current = false;
  }, [media.id]);

  const handleEnterMagicEditMode = useCallback(() => {
    // Prevent double-entry while state is updating
    if (isEnteringEditModeRef.current) {
      return;
    }
    isEnteringEditModeRef.current = true;

    setIsMagicEditMode(true);
    handleEnterInpaintMode();
  }, [handleEnterInpaintMode]);

  const handleExitMagicEditMode = useCallback(() => {
    hasRestoredPromptRef.current = false; // Reset so re-entering can restore again
    setIsMagicEditMode(false);
    setIsInpaintMode(false);
  }, [setIsInpaintMode]);

  // Load saved prompt and settings when entering magic edit mode (without brush strokes)
  // Only restore once per mode entry to prevent re-restoring when user clears the prompt
  useEffect(() => {
    if (isMagicEditMode && !isLoadingMetadata && currentShotId && brushStrokes.length === 0 && !hasRestoredPromptRef.current) {
      // Mark as initialized FIRST - we only get one chance to restore per mode entry
      // This prevents clearing the prompt from triggering restoration
      hasRestoredPromptRef.current = true;

      const lastPrompt = getLastMagicEditPrompt();
      const lastSettings = getLastSettings();

      if (lastPrompt && !inpaintPrompt) {
        setInpaintPrompt(lastPrompt);
        setInpaintNumGenerations(lastSettings.numImages);
        setLoraMode(lastSettings.isInSceneBoostEnabled ? 'in-scene' : 'none');
      }
    }
  }, [isMagicEditMode, isLoadingMetadata, currentShotId, brushStrokes.length, getLastMagicEditPrompt, getLastSettings, inpaintPrompt, setInpaintPrompt, setInpaintNumGenerations, setLoraMode]);

  // Unified edit mode - merging inpaint and magic edit
  const isSpecialEditMode = isInpaintMode || isMagicEditMode;

  // Unified generate handler - routes based on brush strokes
  const handleUnifiedGenerate = useCallback(async () => {
    if (!selectedProjectId) {
      toast.error('No project selected');
      return;
    }
    
    const prompt = inpaintPrompt.trim();
    if (!prompt) {
      toast.error('Please enter a prompt');
      return;
    }
    
    // Route based on whether there are brush strokes
    // Klein models don't support masks/inpainting — always use prompt-based edit
    const useKleinPath = qwenEditModel && isKleinModel(qwenEditModel);
    if (brushStrokes.length > 0 && !useKleinPath) {
      // Has brush strokes -> inpaint (Qwen models only)
      await handleGenerateInpaint();
    } else {
      // No brush strokes -> magic edit
      setIsCreatingMagicEditTasks(true);
      setMagicEditTasksCreated(false);

      try {
        const useKlein = qwenEditModel && isKleinModel(qwenEditModel);
        await run({
          taskType: useKlein ? 'flux_klein_edit' : 'qwen_image_edit',
          label: prompt || 'Magic edit...',
          context: 'useMagicEditMode',
          toastTitle: 'Failed to create magic edit tasks',
          create: () => {
            // Use active variant's location if viewing a non-primary variant
            const effectiveImageUrl = activeVariantLocation || sourceUrlForTasks;

            // IMPORTANT: Use generation_id (actual generations.id) when available, falling back to id
            // For ShotImageManager/Timeline images, id is shot_generations.id but generation_id is the actual generation ID
            const actualGenerationId = getGenerationId(media);

            if (useKlein) {
              return createTask({
                project_id: selectedProjectId,
                family: 'klein_edit',
                input: {
                  prompt,
                  image_url: effectiveImageUrl,
                  klein_model: qwenEditModel,
                  numImages: inpaintNumGenerations,
                  seed: 11111,
                  shot_id: currentShotId || undefined,
                  tool_type: toolTypeOverride,
                  based_on: actualGenerationId ?? undefined,
                  source_variant_id: activeVariantId || undefined,
                  create_as_generation: createAsGeneration,
                },
              });
            }

            return createTask({
              project_id: selectedProjectId,
              family: 'magic_edit',
              input: {
                prompt,
                image_url: effectiveImageUrl,
                numImages: inpaintNumGenerations,
                negative_prompt: "",
                resolution: imageDimensions ? `${imageDimensions.width}x${imageDimensions.height}` : undefined,
                seed: 11111,
                shot_id: currentShotId || undefined,
                tool_type: toolTypeOverride,
                loras: editModeLoras,
                based_on: actualGenerationId ?? undefined,
                source_variant_id: activeVariantId || undefined,
                create_as_generation: createAsGeneration,
                hires_fix: convertToHiresFixApiParams(advancedSettings),
                qwen_edit_model: qwenEditModel,
              },
            });
          },
          onSuccess: async () => {
            // Save the prompt to shot generation metadata
            if (currentShotId && media.id) {
              try {
                await addMagicEditPrompt(
                  prompt,
                  inpaintNumGenerations,
                  false, // Legacy parameter
                  isInSceneLoraMode
                );
              } catch (error) {
                normalizeAndPresentError(error, { context: 'useMagicEditMode', showToast: false });
                // Don't fail the entire operation if metadata save fails
              }
            }

            setMagicEditTasksCreated(true);
            setTimeout(() => setMagicEditTasksCreated(false), 1500);
          },
        });
      } finally {
        setIsCreatingMagicEditTasks(false);
      }
    }
  }, [
    selectedProjectId,
    inpaintPrompt,
    brushStrokes.length,
    handleGenerateInpaint,
    isInSceneLoraMode,
    sourceUrlForTasks,
    inpaintNumGenerations,
    imageDimensions,
    currentShotId,
    toolTypeOverride,
    media,
    addMagicEditPrompt,
    createAsGeneration,
    advancedSettings,
    qwenEditModel,
    activeVariantId,
    activeVariantLocation,
    editModeLoras,
    run,
  ]);

  return {
    isMagicEditMode,
    setIsMagicEditMode,
    magicEditPrompt,
    setMagicEditPrompt,
    magicEditNumImages,
    setMagicEditNumImages,
    isCreatingMagicEditTasks,
    magicEditTasksCreated,
    toolPanelPosition,
    setToolPanelPosition,
    handleEnterMagicEditMode,
    handleExitMagicEditMode,
    handleUnifiedGenerate,
    isSpecialEditMode
  };
};
