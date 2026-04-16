import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({}),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('@/shared/hooks/settings/useAutoSaveSettings', () => ({
  useAutoSaveSettings: vi.fn(),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: vi.fn(),
}));

vi.mock('./useGenerationEditSettings', async () => {
  const actual = await vi.importActual<typeof import('./useGenerationEditSettings')>('./useGenerationEditSettings');
  return {
    ...actual,
    useGenerationEditSettings: vi.fn(),
  };
});

import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import {
  DEFAULT_EDIT_SETTINGS,
  DEFAULT_LAST_USED,
  type EditAdvancedSettings,
  type LastUsedEditSettings,
} from '../model/editSettingsTypes';
import { useEditSettingsPersistence } from './persistence/useEditSettingsPersistence';
import { useGenerationEditSettings, convertToHiresFixApiParams } from './useGenerationEditSettings';
import { useLastUsedEditSettings } from './useLastUsedEditSettings';

const baseSettings: EditAdvancedSettings = {
  enabled: false,
  num_inference_steps: 14,
  resolution_scale: 1.5,
  base_steps: 9,
  hires_scale: 1.2,
  hires_steps: 10,
  hires_denoise: 0.45,
  lightning_lora_strength_phase_1: 0.8,
  lightning_lora_strength_phase_2: 0.6,
};

describe('convertToHiresFixApiParams', () => {
  it('returns undefined when settings are missing', () => {
    expect(convertToHiresFixApiParams(undefined)).toBeUndefined();
  });

  it('returns single-pass params when two-pass mode is disabled', () => {
    expect(convertToHiresFixApiParams(baseSettings)).toEqual({
      num_inference_steps: 14,
    });
  });

  it('returns two-pass hires params when enabled', () => {
    expect(convertToHiresFixApiParams({
      ...baseSettings,
      enabled: true,
    })).toEqual({
      num_inference_steps: 9,
      hires_scale: 1.2,
      hires_steps: 10,
      hires_denoise: 0.45,
      lightning_lora_strength_phase_1: 0.8,
      lightning_lora_strength_phase_2: 0.6,
    });
  });
});

describe('useLastUsedEditSettings', () => {
  const mockUpdate = vi.fn().mockResolvedValue(undefined);
  let toolSettingsState: {
    settings: Partial<LastUsedEditSettings> | null;
    isLoading: boolean;
    update: typeof mockUpdate;
    hasShotSettings: boolean;
  };

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    toolSettingsState = {
      settings: null,
      isLoading: true,
      update: mockUpdate,
      hasShotSettings: false,
    };
    (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockImplementation(() => toolSettingsState);
  });

  it('prefers project local storage, then merges in DB sync, while keeping stable callback references', async () => {
    localStorage.setItem('lightbox-edit-last-used-global', JSON.stringify({
      editMode: 'annotate',
      panelMode: 'edit',
    }));
    localStorage.setItem('lightbox-edit-last-used-project-1', JSON.stringify({
      numGenerations: 3,
      customLoraUrl: 'project-lora',
    }));

    const { result, rerender } = renderHook(() =>
      useLastUsedEditSettings({ projectId: 'project-1', enabled: true }),
    );

    await act(async () => {});

    expect(result.current.lastUsed).toMatchObject({
      ...DEFAULT_LAST_USED,
      numGenerations: 3,
      customLoraUrl: 'project-lora',
    });

    const stableUpdater = result.current.updateLastUsed;
    rerender();
    expect(result.current.updateLastUsed).toBe(stableUpdater);

    toolSettingsState = {
      ...toolSettingsState,
      isLoading: false,
      settings: {
        loraMode: 'custom',
        customLoraUrl: 'db-lora',
      },
    };
    rerender();
    await act(async () => {});

    expect(result.current.lastUsed).toMatchObject({
      numGenerations: 3,
      customLoraUrl: 'db-lora',
      loraMode: 'custom',
    });

    act(() => {
      result.current.updateLastUsed({ panelMode: 'edit' });
    });
    await act(async () => {});

    expect(mockUpdate).toHaveBeenCalledWith('user', expect.objectContaining({
      panelMode: 'edit',
      numGenerations: 3,
      customLoraUrl: 'db-lora',
    }));
  });
});

describe('useEditSettingsPersistence', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    (useToolSettings as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      settings: null,
      isLoading: false,
      update: vi.fn().mockResolvedValue(undefined),
      hasShotSettings: false,
    });
  });

  it('passes last-used bootstrap settings through the generation hook in strict mode without imperative initialization churn', async () => {
    localStorage.setItem('lightbox-edit-last-used-project-strict', JSON.stringify({
      editMode: 'img2img',
      numGenerations: 4,
      customLoraUrl: 'strict-lora',
    }));

    const initializeFromLastUsed = vi.fn();
    const generationHookCalls: Array<Record<string, unknown>> = [];

    (useGenerationEditSettings as unknown as ReturnType<typeof vi.fn>).mockImplementation((input) => {
      generationHookCalls.push(input as Record<string, unknown>);
      return {
        settings: {
          ...DEFAULT_EDIT_SETTINGS,
          prompt: '',
          customLoraUrl: 'strict-lora',
          numGenerations: 4,
        },
        setEditMode: vi.fn(),
        setLoraMode: vi.fn(),
        setCustomLoraUrl: vi.fn(),
        setNumGenerations: vi.fn(),
        setPrompt: vi.fn(),
        setQwenEditModel: vi.fn(),
        setImg2imgPrompt: vi.fn(),
        setImg2imgStrength: vi.fn(),
        setImg2imgEnablePromptExpansion: vi.fn(),
        setAdvancedSettings: vi.fn(),
        setEnhanceSettings: vi.fn(),
        setCreateAsGeneration: vi.fn(),
        updateSettings: vi.fn(),
        flushTextFields: vi.fn().mockResolvedValue(undefined),
        isLoading: false,
        hasPersistedSettings: false,
        initializeFromLastUsed,
      };
    });

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.StrictMode, null, children);

    const { result } = renderHook(
      () => useEditSettingsPersistence({
        generationId: 'gen-1',
        projectId: 'project-strict',
        enabled: true,
      }),
      { wrapper },
    );

    await act(async () => {});

    expect(generationHookCalls.length).toBeGreaterThan(0);
    for (const call of generationHookCalls) {
      expect(call).toMatchObject({
        generationId: 'gen-1',
        enabled: true,
        bootstrapSettings: expect.objectContaining({
          editMode: 'img2img',
          numGenerations: 4,
          customLoraUrl: 'strict-lora',
        }),
      });
    }
    expect(initializeFromLastUsed).not.toHaveBeenCalled();
    expect(result.current.editMode).toBe('img2img');
    expect(result.current.numGenerations).toBe(4);
    expect(result.current.isReady).toBe(true);
  });
});
