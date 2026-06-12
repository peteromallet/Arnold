/**
 * useProjectImageSettings - Project-level settings, reference loading, and reference selection.
 *
 * Groups all project context, user preferences, tool settings, and reference
 * management into a single hook, extracted from useImageGenForm.
 */

import { useMemo } from 'react';
import {
  useProjectCrudContext,
  useProjectSelectionContext,
} from '@/shared/contexts/ProjectContext';
import { useToolSettings, extractSettingsFromCache } from '@/shared/hooks/settings/useToolSettings';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useQueryClient } from '@tanstack/react-query';
import { settingsQueryKeys } from '@/shared/lib/queryKeys/settings';
import { ASPECT_RATIO_TO_RESOLUTION } from '@/shared/lib/media/aspectRatios';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { useReferenceSelection } from './useReferenceSelection';
import { useLegacyMigrations } from './useLegacyMigrations';
import { useHydratedReferences } from './useHydratedReferences';
import { stripLegacyProjectImageSettings } from './legacyMigrations/legacyProjectImageSettings';

import type { ProjectImageSettings } from '../types';
import type { ProjectImageSettingsInput } from './legacyMigrations/legacyProjectImageSettings';

export function useProjectImageSettings(associatedShotId: string | null) {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const queryClient = useQueryClient();

  // Derive project aspect ratio and resolution for GenerationSettingsSection
  const { projectAspectRatio, projectResolution } = useMemo(() => {
    const currentProject = projects.find(project => project.id === selectedProjectId);
    const aspectRatio = currentProject?.aspectRatio ?? '16:9';
    const resolution = ASPECT_RATIO_TO_RESOLUTION[aspectRatio] ?? '902x508';
    return { projectAspectRatio: aspectRatio, projectResolution: resolution };
  }, [projects, selectedProjectId]);

  // Access user's generation settings to detect local generation
  const { value: generationMethods } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });

  // Privacy defaults for new resources
  const { value: privacyDefaults } = useUserUIState('privacyDefaults', { resourcesPublic: true, generationsPublic: false });

  const isLocalGenerationEnabled = generationMethods.onComputer && !generationMethods.inCloud;

  // Project-level settings for model and style reference (shared across tools)
  const {
    settings: projectImageSettings,
    update: updateProjectImageSettings,
    isLoading: isLoadingProjectSettings
  } = useToolSettings<ProjectImageSettingsInput>(SETTINGS_IDS.PROJECT_IMAGE_SETTINGS, {
    projectId: selectedProjectId ?? undefined,
    enabled: !!selectedProjectId
  });

  // Get the effective shot ID for storage (use 'none' for null)
  const effectiveShotId = associatedShotId || 'none';

  // Get reference pointers array and selected reference for current shot
  const cachedProjectSettings = selectedProjectId
    ? extractSettingsFromCache<ProjectImageSettingsInput>(
        queryClient.getQueryData(settingsQueryKeys.tool(SETTINGS_IDS.PROJECT_IMAGE_SETTINGS, selectedProjectId, undefined))
      )
    : undefined;

  const rawProjectImageSettings = projectImageSettings ?? cachedProjectSettings;
  const effectiveProjectImageSettings = useMemo(
    () => stripLegacyProjectImageSettings(rawProjectImageSettings),
    [rawProjectImageSettings]
  );
  const referencePointers = effectiveProjectImageSettings?.references ?? [];
  const referenceCount = referencePointers.length;
  const selectedReferenceIdByShot = effectiveProjectImageSettings?.selectedReferenceIdByShot ?? {};
  const selectedReferenceId = selectedReferenceIdByShot[effectiveShotId] ?? null;

  // Hydrate references with data from resources table
  const { hydratedReferences, isLoading: isLoadingReferences, hasLegacyReferences } = useHydratedReferences(referencePointers);

  // Reference selection (auto-select, display ID)
  const {
    displayedReferenceId,
    selectedReference,
    isReferenceDataLoading,
  } = useReferenceSelection({
    effectiveShotId,
    referenceCount,
    selectedReferenceId,
    hydratedReferences,
    isLoadingProjectSettings,
    isLoadingReferences,
  });

  // For backward compatibility with single reference - used in legacy migration
  const rawStyleReferenceImage = selectedReference?.styleReferenceImage || rawProjectImageSettings?.styleReferenceImage || null;

  // Legacy migrations (runs effects to migrate old reference formats)
  useLegacyMigrations({
    selectedProjectId,
    effectiveShotId,
    referencePointers,
    hydratedReferences,
    hasLegacyReferences,
    rawStyleReferenceImage,
    isLoadingReferences,
    selectedReferenceIdByShot,
    projectImageSettings: projectImageSettings ?? null,
    updateProjectImageSettings,
    privacyDefaults,
  });

  return {
    selectedProjectId,
    projectAspectRatio,
    projectResolution,
    privacyDefaults,
    isLocalGenerationEnabled,
    projectImageSettings: (projectImageSettings as ProjectImageSettings | null),
    updateProjectImageSettings,
    isLoadingProjectSettings,
    effectiveShotId,
    referencePointers,
    referenceCount,
    selectedReferenceIdByShot,
    selectedReferenceId,
    hydratedReferences,
    displayedReferenceId,
    selectedReference,
    isReferenceDataLoading,
  };
}
