// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  toastError: vi.fn(),
  normalizeAndPresentError: vi.fn(),
  useQueryClient: vi.fn(),
  useEnqueueGenerationsInvalidation: vi.fn(),
  useVideoTravelSettingsMutations: vi.fn(),
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

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: (...args: unknown[]) => mocks.useQueryClient(...args),
}));

vi.mock('@/shared/hooks/invalidation/useGenerationInvalidation', () => ({
  useEnqueueGenerationsInvalidation: (...args: unknown[]) => mocks.useEnqueueGenerationsInvalidation(...args),
}));

vi.mock('../../providers/VideoTravelSettingsProvider', () => ({
  useVideoTravelSettingsMutations: (...args: unknown[]) => mocks.useVideoTravelSettingsMutations(...args),
}));

vi.mock('../ShotEditor/services/generateVideo/modelPhase', () => ({
  buildBasicModeGenerationRequest: (...args: unknown[]) => mocks.buildBasicModePhaseConfig(...args),
}));

vi.mock('../ShotEditor/services/generateVideoService', () => ({
  generateVideo: (...args: unknown[]) => mocks.generateVideo(...args),
}));

import { useBatchVideoGeneration } from './useBatchVideoGeneration';

const baseSettings = {
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
  selectedPhasePresetId: 'preset-1',
  steerableMotionSettings: { negative_prompt: 'neg', seed: 123 },
  selectedModel: 'wan-2.2',
  batchVideoSteps: 6,
  guidanceScale: 5,
  ltxHdResolution: true,
};

const baseStructureState = {
  travelGuidance: { kind: 'none' },
  structureGuidance: { mode: 'none' },
  structureVideos: [],
};

const positionedImage = {
  id: 'img-1',
  metadata: { width: 1920, height: 1080 },
} as const;

function renderBatchHook(overrides?: Partial<Parameters<typeof useBatchVideoGeneration>[0]>) {
  const onClose = vi.fn();
  const defaults = {
    shot: { id: 'shot-1' } as never,
    projectId: 'project-1',
    onClose,
    randomSeed: true,
    positionedImages: [positionedImage] as never,
    effectiveAspectRatio: '16:9',
    selectedLoras: [
      { id: 'lora-1', name: 'Lora One', path: '/lora-1', strength: 0.8 },
    ] as never,
    structureState: baseStructureState as never,
  };
  const { result } = renderHook(() => useBatchVideoGeneration({ ...defaults, ...overrides }));
  return { result, onClose };
}

describe('useBatchVideoGeneration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mocks.useQueryClient.mockReturnValue({ query: 'client' });
    mocks.useEnqueueGenerationsInvalidation.mockReturnValue(vi.fn());
    mocks.useVideoTravelSettingsMutations.mockReturnValue({
      settings: baseSettings,
      updateField: vi.fn(),
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

  it('queues generation successfully, flips justQueued, and calls onClose after the timeout', async () => {
    const onClose = vi.fn();
    const invalidateGenerations = vi.fn();
    mocks.useEnqueueGenerationsInvalidation.mockReturnValueOnce(invalidateGenerations);
    const updateField = vi.fn();
    mocks.useVideoTravelSettingsMutations.mockReturnValue({
      settings: baseSettings,
      updateField,
    });

    const { result } = renderBatchHook({ onClose });

    await act(async () => {
      await result.current.handleGenerate();
    });

    expect(updateField).toHaveBeenCalledWith('generationMode', 'batch');
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

  it('shows a toast and skips generation when no positioned images are available', async () => {
    const { result } = renderBatchHook({ positionedImages: [] as never });

    await act(async () => {
      await result.current.handleGenerate();
    });

    expect(mocks.toastError).toHaveBeenCalledWith('At least 1 positioned image is required.');
    expect(mocks.generateVideo).not.toHaveBeenCalled();
  });
});
