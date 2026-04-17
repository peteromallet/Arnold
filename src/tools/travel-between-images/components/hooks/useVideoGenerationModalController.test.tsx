// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BUILTIN_DEFAULT_I2V_ID } from '../MotionControl.constants';

const mocks = vi.hoisted(() => ({
  toastError: vi.fn(),
  normalizeAndPresentError: vi.fn(),
  useProject: vi.fn(),
  useProjectCrudContext: vi.fn(),
  useQueryClient: vi.fn(),
  useEnqueueGenerationsInvalidation: vi.fn(),
  useShotNavigation: vi.fn(),
  usePanesStore: vi.fn(),
  useShotSettings: vi.fn(),
  useToolSettings: vi.fn(),
  useProjectGenerationModesCache: vi.fn(),
  usePublicLoras: vi.fn(),
  useShotImages: vi.fn(),
  isPositioned: vi.fn(),
  isVideoGeneration: vi.fn(),
  findClosestAspectRatio: vi.fn(),
  resolveTravelStructureState: vi.fn(),
  buildBasicModePhaseConfig: vi.fn(),
  generateVideo: vi.fn(),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: (...args: unknown[]) => mocks.toastError(...args),
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: (...args: unknown[]) => mocks.normalizeAndPresentError(...args),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: (...args: unknown[]) => mocks.useProject(...args),
  useProjectSelectionContext: (...args: unknown[]) => mocks.useProject(...args),
  useProjectCrudContext: (...args: unknown[]) => mocks.useProjectCrudContext(...args),
  useProjectIdentityContext: () => ({ userId: null }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: (...args: unknown[]) => mocks.useQueryClient(...args),
}));

vi.mock('@/shared/hooks/invalidation/useGenerationInvalidation', () => ({
  useEnqueueGenerationsInvalidation: (...args: unknown[]) => mocks.useEnqueueGenerationsInvalidation(...args),
}));

vi.mock('@/shared/hooks/shots/useShotNavigation', () => ({
  useShotNavigation: (...args: unknown[]) => mocks.useShotNavigation(...args),
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: unknown) => unknown) => selector(mocks.usePanesStore()),
}));

vi.mock('../../hooks/settings/useShotSettings', () => ({
  useShotSettings: (...args: unknown[]) => mocks.useShotSettings(...args),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: (...args: unknown[]) => mocks.useToolSettings(...args),
}));

vi.mock('@/shared/hooks/projects/useProjectGenerationModesCache', () => ({
  useProjectGenerationModesCache: (...args: unknown[]) => mocks.useProjectGenerationModesCache(...args),
}));

vi.mock('@/features/resources/hooks/useResources', () => ({
  usePublicLoras: (...args: unknown[]) => mocks.usePublicLoras(...args),
}));

vi.mock('@/shared/hooks/shots/useShotImages', () => ({
  useShotImages: (...args: unknown[]) => mocks.useShotImages(...args),
}));

vi.mock('@/shared/lib/typeGuards', () => ({
  isPositioned: (...args: unknown[]) => mocks.isPositioned(...args),
  isVideoGeneration: (...args: unknown[]) => mocks.isVideoGeneration(...args),
}));

vi.mock('@/shared/lib/media/aspectRatios', () => ({
  findClosestAspectRatio: (...args: unknown[]) => mocks.findClosestAspectRatio(...args),
}));

vi.mock('@/shared/lib/tasks/travelBetweenImages', () => ({
  DEFAULT_STRUCTURE_VIDEO: {
    treatment: 'adjust',
    motion_strength: 1,
    structure_type: 'flow',
    uni3c_end_percent: 0.1,
  },
  DEFAULT_STRUCTURE_GUIDANCE_CONTROLS: {
    motionStrength: 1,
    structureType: 'flow',
    uni3cEndPercent: 0.1,
  },
  resolveTravelStructureState: (...args: unknown[]) => mocks.resolveTravelStructureState(...args),
}));

vi.mock('../ShotEditor/services/generateVideo/modelPhase', () => ({
  buildBasicModeGenerationRequest: (...args: unknown[]) => mocks.buildBasicModePhaseConfig(...args),
}));

vi.mock('../ShotEditor/services/generateVideoService', () => ({
  generateVideo: (...args: unknown[]) => mocks.generateVideo(...args),
}));

import { useVideoGenerationModalController } from './useVideoGenerationModalController';

describe('useVideoGenerationModalController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mocks.useProject.mockReturnValue({
      selectedProjectId: 'project-1',
    });
    mocks.useProjectCrudContext.mockReturnValue({
      projects: [{ id: 'project-1', aspectRatio: '16:9' }],
      isLoadingProjects: false,
      fetchProjects: vi.fn(),
      addNewProject: vi.fn(),
      isCreatingProject: false,
      updateProject: vi.fn(),
      isUpdatingProject: false,
      deleteProject: vi.fn(),
      isDeletingProject: false,
    });
    mocks.useQueryClient.mockReturnValue({ query: 'client' });
    mocks.useEnqueueGenerationsInvalidation.mockReturnValue(vi.fn());
    mocks.useShotNavigation.mockReturnValue({ navigateToShot: vi.fn() });
    mocks.usePanesStore.mockReturnValue({ isShotsPaneLocked: false, setIsShotsPaneLocked: vi.fn() });
    mocks.useToolSettings.mockReturnValue({
      settings: { acceleratedMode: false, randomSeed: true },
      update: vi.fn(),
    });
    mocks.useProjectGenerationModesCache.mockReturnValue({
      updateShotMode: vi.fn(),
    });
    mocks.useShotSettings.mockReturnValue({
      settings: {
        prompt: 'Base prompt',
        enhancePrompt: true,
        textBeforePrompts: 'before',
        textAfterPrompts: 'after',
        amountOfMotion: 70,
        turboMode: true,
        generationTypeMode: 'i2v',
        batchVideoFrames: 61,
        motionMode: 'advanced',
        phaseConfig: { advanced: true },
        selectedPhasePresetId: BUILTIN_DEFAULT_I2V_ID,
        steerableMotionSettings: { negative_prompt: 'neg', seed: 123 },
        loras: [
          { id: 'lora-1', name: 'Lora One', path: '/lora-1', strength: 0.8 },
        ],
      },
      status: 'ready',
      updateField: vi.fn(),
    });
    mocks.usePublicLoras.mockReturnValue({
      data: [{ 'Model ID': 'lora-1', Name: 'Lora One', link: '/lora-1' }],
    });
    mocks.useShotImages.mockReturnValue({
      data: [
        {
          id: 'img-1',
          type: 'image',
          timeline_frame: 0,
          metadata: { width: 1920, height: 1080 },
        },
        {
          id: 'vid-1',
          type: 'video',
          timeline_frame: 5,
        },
      ],
      isLoading: false,
    });
    mocks.isPositioned.mockImplementation((generation: { timeline_frame?: number | null }) => generation.timeline_frame != null);
    mocks.isVideoGeneration.mockImplementation((generation: { type?: string | null }) => generation.type === 'video');
    mocks.findClosestAspectRatio.mockReturnValue('16:9');
    mocks.resolveTravelStructureState.mockReturnValue({
      travelGuidance: { kind: 'none' },
      structureGuidance: { mode: 'none' },
      structureVideos: [],
    });
    mocks.buildBasicModePhaseConfig.mockReturnValue({
      phaseConfig: { basic: true },
    });
    mocks.generateVideo.mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('derives positioned-image state and forwards navigation/dialog actions', () => {
    const onClose = vi.fn();
    const { result } = renderHook(() => useVideoGenerationModalController({
      isOpen: true,
      onClose,
      shot: { id: 'shot-1' } as never,
    }));

    expect(result.current.positionedImages).toEqual([
      expect.objectContaining({ id: 'img-1' }),
    ]);
    expect(result.current.projects).toEqual([{ id: 'project-1', aspectRatio: '16:9' }]);
    expect(result.current.selectedProjectId).toBe('project-1');
    expect(result.current.settings.prompt).toBe('Base prompt');
    expect(result.current.status).toBe('ready');
    expect(result.current.isDisabled).toBe(false);
    expect(result.current.hasStructureVideo).toBe(false);
    expect(result.current.guidanceKind).toBeUndefined();
    expect(result.current.accelerated).toBe(false);
    expect(result.current.randomSeed).toBe(true);
    expect(result.current.validPresetId).toBe(BUILTIN_DEFAULT_I2V_ID);
    expect(result.current.selectedLoras).toEqual([
      expect.objectContaining({ id: 'lora-1', strength: 0.8 }),
    ]);
    expect(result.current.selectedLorasForModal).toEqual([
      expect.objectContaining({ 'Model ID': 'lora-1', strength: 0.8 }),
    ]);

    act(() => {
      result.current.openLoraModal();
    });
    expect(result.current.isLoraModalOpen).toBe(true);

    act(() => {
      result.current.handleDialogOpenChange(false);
    });
    expect(onClose).toHaveBeenCalledTimes(0);

    act(() => {
      result.current.closeLoraModal();
    });
    expect(result.current.isLoraModalOpen).toBe(false);

    act(() => {
      result.current.handleNavigateToShot();
      result.current.handleDialogOpenChange(false);
    });

    expect(mocks.useShotNavigation.mock.results[0]?.value.navigateToShot).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'shot-1' }),
    );
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('derives guidanceKind from canonical travel guidance state', () => {
    mocks.resolveTravelStructureState.mockReturnValueOnce({
      travelGuidance: {
        kind: 'vace',
        mode: 'depth',
        videos: [{ path: '/guide.mp4' }],
      },
      structureGuidance: { mode: 'none' },
      structureVideos: [{ path: '/guide.mp4' }],
    });

    const { result } = renderHook(() => useVideoGenerationModalController({
      isOpen: true,
      onClose: vi.fn(),
      shot: { id: 'shot-1' } as never,
    }));

    expect(result.current.hasStructureVideo).toBe(true);
    expect(result.current.guidanceKind).toBe('depth');
  });

  it('queues generation successfully and closes after the success timeout', async () => {
    const onClose = vi.fn();
    const invalidateGenerations = vi.fn();
    mocks.useEnqueueGenerationsInvalidation.mockReturnValueOnce(invalidateGenerations);

    const { result } = renderHook(() => useVideoGenerationModalController({
      isOpen: true,
      onClose,
      shot: { id: 'shot-1' } as never,
    }));

    await act(async () => {
      await result.current.handleGenerate();
    });

    expect(mocks.useShotSettings.mock.results[0]?.value.updateField).toHaveBeenCalledWith(
      'generationMode',
      'batch',
    );
    expect(mocks.buildBasicModePhaseConfig).toHaveBeenCalledWith(70, [
      { path: '/lora-1', strength: 0.8 },
    ]);
    expect(mocks.generateVideo).toHaveBeenCalledWith(expect.objectContaining({
      projectId: 'project-1',
      selectedShotId: 'shot-1',
      effectiveAspectRatio: '16:9',
      generationMode: 'batch',
    }));
    expect(mocks.generateVideo).toHaveBeenCalledWith(expect.objectContaining({
      structureGuidance: { mode: 'none' },
      structureVideos: [],
      selectedLoras: [
        expect.objectContaining({
          id: 'lora-1',
          name: 'Lora One',
          path: '/lora-1',
          strength: 0.8,
        }),
      ],
    }));
    expect(result.current.justQueued).toBe(true);
    expect(result.current.isGenerating).toBe(false);
    expect(invalidateGenerations).toHaveBeenCalledWith('shot-1', {
      reason: 'video-generation-modal-success',
      scope: 'all',
      includeProjectUnified: true,
      projectId: 'project-1',
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(result.current.justQueued).toBe(false);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows a toast instead of generating when no positioned images are available', async () => {
    mocks.useShotImages.mockReturnValue({
      data: [
        {
          id: 'vid-1',
          type: 'video',
          timeline_frame: 5,
        },
      ],
      isLoading: false,
    });

    const { result } = renderHook(() => useVideoGenerationModalController({
      isOpen: true,
      onClose: vi.fn(),
      shot: { id: 'shot-1' } as never,
    }));

    await act(async () => {
      await result.current.handleGenerate();
    });

    expect(mocks.toastError).toHaveBeenCalledWith('At least 1 positioned image is required.');
    expect(mocks.generateVideo).not.toHaveBeenCalled();
  });
});
