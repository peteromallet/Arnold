import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GenerationRow } from '@/domains/generation/types';
import { useImageLightboxEnvironment } from '../useImageLightboxEnvironment';

const mocks = vi.hoisted(() => ({
  useProject: vi.fn(),
  panesState: {
    isTasksPaneOpen: false,
    tasksPaneWidth: 320,
    isTasksPaneLocked: true,
  },
  useUserUIState: vi.fn(),
  usePublicLoras: vi.fn(),
  useLoraManager: vi.fn(),
  useIsMobile: vi.fn(),
  getGenerationId: vi.fn(),
  useUpscale: vi.fn(),
  useEditSettingsPersistence: vi.fn(),
  extractDimensionsFromMedia: vi.fn(),
  useChangedDepsLogger: vi.fn(),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: (...args: unknown[]) => mocks.useProject(...args),
  useProjectSelectionContext: (...args: unknown[]) => mocks.useProject(...args),
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: typeof mocks.panesState) => unknown) => selector(mocks.panesState),
}));

vi.mock('@/shared/hooks/useUserUIState', () => ({
  useUserUIState: (...args: unknown[]) => mocks.useUserUIState(...args),
}));

vi.mock('@/features/resources/hooks/useResources', () => ({
  usePublicLoras: (...args: unknown[]) => mocks.usePublicLoras(...args),
}));

vi.mock('@/domains/lora/hooks/useLoraManager', () => ({
  useLoraManager: (...args: unknown[]) => mocks.useLoraManager(...args),
}));

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: (...args: unknown[]) => mocks.useIsMobile(...args),
}));

vi.mock('@/shared/lib/media/mediaTypeHelpers', () => ({
  getGenerationId: (...args: unknown[]) => mocks.getGenerationId(...args),
}));

vi.mock('../useUpscale', () => ({
  useUpscale: (...args: unknown[]) => mocks.useUpscale(...args),
}));

vi.mock('../persistence/useEditSettingsPersistence', () => ({
  useEditSettingsPersistence: (...args: unknown[]) => mocks.useEditSettingsPersistence(...args),
}));

vi.mock('../../utils/dimensions', () => ({
  extractDimensionsFromMedia: (...args: unknown[]) => mocks.extractDimensionsFromMedia(...args),
}));

vi.mock('@/shared/lib/debug/debugRendering', () => ({
  useChangedDepsLogger: (...args: unknown[]) => mocks.useChangedDepsLogger(...args),
}));

function createMedia(overrides: Partial<GenerationRow> = {}): GenerationRow {
  return {
    id: 'media-1',
    parent_generation_id: 'parent-1',
    ...overrides,
  } as unknown as GenerationRow;
}

describe('useImageLightboxEnvironment', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.useProject.mockReturnValue({
      project: { aspectRatio: '16:9' },
      selectedProjectId: 'project-1',
    });
    mocks.panesState = {
      isTasksPaneOpen: false,
      tasksPaneWidth: 320,
      isTasksPaneLocked: true,
    };
    mocks.useUserUIState.mockReturnValue({
      value: { onComputer: true, inCloud: false },
    });
    mocks.usePublicLoras.mockReturnValue({
      data: [{ id: 'pub-1' }],
    });
    mocks.useLoraManager.mockReturnValue({
      selectedLoras: [{ path: 'lora://selected', strength: 0.8 }],
    });
    mocks.useIsMobile.mockReturnValue(true);
    mocks.getGenerationId.mockReturnValue('gen-1');
    mocks.useUpscale.mockReturnValue({
      isUpscaling: false,
      effectiveImageUrl: 'https://img.example/current.png',
      handleUpscale: vi.fn(),
    });
    mocks.useEditSettingsPersistence.mockReturnValue({
      editModeLoras: [{ url: 'lora://fallback', strength: 0.4 }],
    });
    mocks.extractDimensionsFromMedia.mockReturnValue({ width: 640, height: 360 });
  });

  it('builds environment with explicit task pane overrides and selected LoRA precedence', () => {
    const media = createMedia();
    const { result } = renderHook(() =>
      useImageLightboxEnvironment({
        media,
        shotId: 'shot-1',
        tasksPaneOpen: true,
        tasksPaneWidth: 900,
      }),
    );

    expect(result.current.selectedProjectId).toBe('project-1');
    expect(result.current.projectAspectRatio).toBe('16:9');
    expect(result.current.isMobile).toBe(true);
    expect(result.current.isCloudMode).toBe(false);
    expect(result.current.isLocalGeneration).toBe(true);
    expect(result.current.isTasksPaneLocked).toBe(true);
    expect(result.current.effectiveTasksPaneOpen).toBe(true);
    expect(result.current.effectiveTasksPaneWidth).toBe(900);
    expect(result.current.actualGenerationId).toBe('gen-1');
    expect(result.current.variantFetchGenerationId).toBe('parent-1');
    expect(result.current.imageDimensions).toEqual({ width: 640, height: 360 });

    expect(result.current.effectiveEditModeLoras).toEqual([
      { url: 'lora://selected', strength: 0.8 },
    ]);

    expect(mocks.useUpscale).toHaveBeenCalledWith({
      media,
      selectedProjectId: 'project-1',
      isVideo: false,
      shotId: 'shot-1',
    });
    expect(mocks.useEditSettingsPersistence).toHaveBeenCalledWith({
      generationId: 'gen-1',
      projectId: 'project-1',
      enabled: true,
    });
  });

  it('falls back to context pane values, fallback LoRAs, and updates dimensions on media change', () => {
    mocks.useLoraManager.mockReturnValue({
      selectedLoras: [],
    });
    mocks.extractDimensionsFromMedia.mockImplementation((media: GenerationRow) => {
      if ((media as { id?: string }).id === 'media-2') {
        return { width: 1024, height: 512 };
      }
      return { width: 640, height: 360 };
    });

    const { result, rerender } = renderHook(
      (props: { media: GenerationRow }) =>
        useImageLightboxEnvironment({
          media: props.media,
        }),
      {
        initialProps: { media: createMedia({ parent_generation_id: undefined }) },
      },
    );

    expect(result.current.effectiveTasksPaneOpen).toBe(false);
    expect(result.current.effectiveTasksPaneWidth).toBe(320);
    expect(result.current.variantFetchGenerationId).toBe('gen-1');
    expect(result.current.effectiveEditModeLoras).toEqual([
      { url: 'lora://fallback', strength: 0.4 },
    ]);
    expect(result.current.imageDimensions).toEqual({ width: 640, height: 360 });

    rerender({ media: createMedia({ id: 'media-2', parent_generation_id: undefined }) });
    expect(result.current.imageDimensions).toEqual({ width: 1024, height: 512 });
  });

  it('derives isCloudMode and isLocalGeneration from generationMethods UI state', () => {
    mocks.useUserUIState.mockReturnValue({
      value: { onComputer: false, inCloud: true },
    });

    const { result } = renderHook(() =>
      useImageLightboxEnvironment({ media: createMedia() }),
    );

    expect(result.current.isCloudMode).toBe(true);
    expect(result.current.isLocalGeneration).toBe(false);
  });

  it('returns a stable environment reference when upstream inputs are unchanged', () => {
    const stableProjectState = {
      project: { aspectRatio: '16:9' },
      selectedProjectId: 'project-1',
    };
    const stablePanesState = {
      isTasksPaneOpen: false,
      tasksPaneWidth: 320,
      isTasksPaneLocked: true,
    };
    const stableGenerationMethodsState = {
      value: { onComputer: true, inCloud: false },
    };
    const stableAvailableLoras = [{ id: 'pub-1' }];
    const stableLoraManager = {
      selectedLoras: [{ path: 'lora://selected', strength: 0.8 }],
    };
    const stableUpscaleHook = {
      isUpscaling: false,
      effectiveImageUrl: 'https://img.example/current.png',
      handleUpscale: vi.fn(),
    };
    const stableEditSettingsPersistence = {
      editModeLoras: [{ url: 'lora://fallback', strength: 0.4 }],
    };
    const media = createMedia();

    mocks.useProject.mockReturnValue(stableProjectState);
    mocks.panesState = stablePanesState;
    mocks.useUserUIState.mockReturnValue(stableGenerationMethodsState);
    mocks.usePublicLoras.mockReturnValue({ data: stableAvailableLoras });
    mocks.useLoraManager.mockReturnValue(stableLoraManager);
    mocks.useUpscale.mockReturnValue(stableUpscaleHook);
    mocks.useEditSettingsPersistence.mockReturnValue(stableEditSettingsPersistence);

    const { result, rerender } = renderHook(() =>
      useImageLightboxEnvironment({
        media,
        shotId: 'shot-1',
      }),
    );

    const firstEnv = result.current;
    rerender();

    expect(result.current).toBe(firstEnv);
    expect(result.current.upscaleHook).toBe(stableUpscaleHook);
    expect(result.current.editSettingsPersistence).toBe(stableEditSettingsPersistence);
    expect(result.current.editLoraManager).toBe(stableLoraManager);
    expect(result.current.availableLoras).toBe(stableAvailableLoras);
    expect(result.current.effectiveEditModeLoras).toBe(firstEnv.effectiveEditModeLoras);
  });

  it('audits the actual upstream hook references and final env reference in dev mode', () => {
    renderHook(() =>
      useImageLightboxEnvironment({ media: createMedia(), shotId: 'shot-1' }),
    );

    expect(mocks.useChangedDepsLogger).toHaveBeenCalledWith(
      'useImageLightboxEnvironment.inputs',
      expect.objectContaining({
        useIsMobile: true,
        useProjectSelectionContext: expect.objectContaining({ selectedProjectId: 'project-1' }),
        useUserUIState_generationMethods: expect.objectContaining({
          value: expect.objectContaining({ onComputer: true, inCloud: false }),
        }),
        usePanes: expect.objectContaining({
          isTasksPaneLocked: true,
          isTasksPaneOpen: false,
          tasksPaneWidth: 320,
        }),
        usePublicLoras_data: [{ id: 'pub-1' }],
        useLoraManager: expect.objectContaining({
          selectedLoras: [{ path: 'lora://selected', strength: 0.8 }],
        }),
        useUpscale: expect.objectContaining({
          effectiveImageUrl: 'https://img.example/current.png',
        }),
        useEditSettingsPersistence: expect.objectContaining({
          editModeLoras: [{ url: 'lora://fallback', strength: 0.4 }],
        }),
        effectiveEditModeLoras: [{ url: 'lora://selected', strength: 0.8 }],
      }),
    );
    expect(mocks.useChangedDepsLogger).toHaveBeenCalledWith(
      'useImageLightboxEnvironment.env',
      expect.objectContaining({
        env: expect.objectContaining({
          actualGenerationId: 'gen-1',
          variantFetchGenerationId: 'parent-1',
        }),
      }),
    );
  });
});
