/**
 * useOutputSelection - Selected output persistence for the current shot.
 *
 * Uses the shared auto-save settings pattern instead of manual load/save orchestration.
 */

import { useCallback } from 'react';
import { useAutoSaveSettings } from '@/shared/settings/hooks/useAutoSaveSettings';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';

interface UseOutputSelectionProps {
  projectId?: string;
  shotId?: string;
}

interface OutputSelectionSettings {
  selectedParentGenerationId: string | null;
}

interface UseOutputSelectionReturn {
  selectedOutputId: string | null;
  setSelectedOutputId: (id: string | null) => void;
  isLoading: boolean;
  isReady: boolean;
}

export function useOutputSelection({
  projectId,
  shotId,
}: UseOutputSelectionProps): UseOutputSelectionReturn {
  const outputSelection = useAutoSaveSettings<OutputSelectionSettings>({
    toolId: SETTINGS_IDS.TRAVEL_SELECTED_OUTPUT,
    projectId: projectId ?? null,
    shotId: shotId ?? null,
    scope: 'shot',
    defaults: { selectedParentGenerationId: null },
    enabled: !!shotId,
    debounceMs: 100,
  });
  const {
    settings,
    status,
    updateField,
  } = outputSelection;

  const setSelectedOutputId = useCallback((id: string | null) => {
    updateField('selectedParentGenerationId', id);
  }, [updateField]);

  return {
    selectedOutputId: settings.selectedParentGenerationId ?? null,
    setSelectedOutputId,
    isLoading: !!shotId && status === 'loading',
    isReady: !shotId || status === 'ready' || status === 'saving',
  };
}
