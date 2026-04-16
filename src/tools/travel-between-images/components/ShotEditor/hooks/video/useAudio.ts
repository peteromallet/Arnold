import { useCallback } from 'react';
import { useAutoSaveSettings } from '@/shared/settings/hooks/useAutoSaveSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';

export interface AudioMetadata {
  duration: number;
  name?: string;
}

interface UseAudioParams {
  projectId: string;
  shotId: string | undefined;
}

interface AudioSettings {
  url: string | null;
  metadata: AudioMetadata | null;
}

export interface UseAudioReturn {
  audioUrl: string | null;
  audioMetadata: AudioMetadata | null;
  handleAudioChange: (
    audioUrl: string | null,
    metadata: AudioMetadata | null
  ) => void;
  isLoading: boolean;
}

/**
 * Hook to manage per-shot audio persistence.
 * Standardized on useAutoSaveSettings for load/save behavior.
 */
export function useAudio({
  projectId,
  shotId,
}: UseAudioParams): UseAudioReturn {
  const audioSettings = useAutoSaveSettings<AudioSettings>({
    toolId: SETTINGS_IDS.TRAVEL_AUDIO,
    projectId,
    shotId: shotId ?? null,
    scope: 'shot',
    defaults: {
      url: null,
      metadata: null,
    },
    enabled: !!shotId,
    debounceMs: 100,
  });
  const {
    settings,
    status,
    updateFields,
  } = audioSettings;

  const handleAudioChange = useCallback((
    url: string | null,
    metadata: AudioMetadata | null
  ) => {
    updateFields({
      url,
      metadata: metadata ?? null,
    });
  }, [updateFields]);

  return {
    audioUrl: settings.url ?? null,
    audioMetadata: settings.metadata ?? null,
    handleAudioChange,
    isLoading: !!shotId && status === 'loading',
  };
}
