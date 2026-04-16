import { useCallback } from 'react';
import { useAutoSaveSettings } from '@/shared/settings/hooks/useAutoSaveSettings';
import type { GenerationControlValues } from '@/shared/components/PromptGenerationControls';
import type { BulkEditControlValues } from '@/shared/components/PromptEditorModal/BulkEditControls';

type EditorMode = 'generate' | 'remix' | 'bulk-edit';

interface PersistedEditorControlsSettings {
  generationSettings: GenerationControlValues;
  bulkEditSettings: BulkEditControlValues;
  activeTab: EditorMode;
}

interface UsePersistentPromptSettingsParams {
  selectedProjectId: string | null;
}

const DEFAULT_GENERATION_SETTINGS: GenerationControlValues = {
  overallPromptText: '',
  remixPromptText: 'More like this',
  rulesToRememberText: '',
  numberToGenerate: 16,
  includeExistingContext: true,
  addSummary: true,
  replaceCurrentPrompts: false,
  temperature: 0.8,
  showAdvanced: false,
};

const DEFAULT_BULK_EDIT_SETTINGS: BulkEditControlValues = {
  editInstructions: '',
  modelType: 'smart',
};

export function usePersistentPromptSettings({ selectedProjectId }: UsePersistentPromptSettingsParams) {
  const persisted = useAutoSaveSettings<PersistedEditorControlsSettings>({
    toolId: 'prompt-editor-controls',
    projectId: selectedProjectId,
    scope: 'project',
    defaults: {
      generationSettings: DEFAULT_GENERATION_SETTINGS,
      bulkEditSettings: DEFAULT_BULK_EDIT_SETTINGS,
      activeTab: 'generate',
    },
    enabled: !!selectedProjectId,
    debounceMs: 150,
  });
  const { settings, updateField } = persisted;

  const handleGenerationValuesChange = useCallback((values: GenerationControlValues) => {
    if (JSON.stringify(settings.generationSettings) === JSON.stringify(values)) {
      return;
    }
    updateField('generationSettings', values);
  }, [settings.generationSettings, updateField]);

  const handleBulkEditValuesChange = useCallback((values: BulkEditControlValues) => {
    if (JSON.stringify(settings.bulkEditSettings) === JSON.stringify(values)) {
      return;
    }
    updateField('bulkEditSettings', values);
  }, [settings.bulkEditSettings, updateField]);

  const handleActiveTabChange = useCallback((mode: EditorMode) => {
    updateField('activeTab', mode);
  }, [updateField]);

  return {
    activeTab: settings.activeTab,
    generationControlValues: settings.generationSettings,
    bulkEditControlValues: settings.bulkEditSettings,
    handleGenerationValuesChange,
    handleBulkEditValuesChange,
    handleActiveTabChange,
  };
}
