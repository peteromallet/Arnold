/**
 * HeaderSection - Shot header with navigation and name editing
 *
 * Extracted from ShotSettingsEditor for modularity.
 * Gets most data from ShotSettingsContext, only takes callback props.
 */

import React from 'react';
import { Header } from '../ui/Header';
import { useShotSettingsIdentity, useShotSettingsUi } from '../ShotSettingsContext';
import { useUpdateShotAspectRatio } from '@/shared/hooks/shots';
import type { HeaderSectionCallbacks, HeaderSectionLayout } from './headerSectionTypes';

interface HeaderSectionProps {
  callbacks: HeaderSectionCallbacks;
  layout: HeaderSectionLayout;
}

export const HeaderSection: React.FC<HeaderSectionProps> = ({
  callbacks,
  layout,
}) => {
  // Get shared state from context
  const {
    selectedShot,
    selectedShotId,
    projectId,
    projects,
    effectiveAspectRatio,
  } = useShotSettingsIdentity();
  const { state, actions } = useShotSettingsUi();
  const { updateShotAspectRatio } = useUpdateShotAspectRatio();

  const onRevertAspectRatio = React.useCallback(async () => {
    if (!selectedShot?.id || !projectId) {
      return;
    }

    const project = projects.find((candidate) => candidate.id === projectId) as
      | {
        aspectRatio?: string;
        settings?: { aspectRatio?: string };
      }
      | undefined;
    const projectDefault =
      project?.aspectRatio ??
      project?.settings?.aspectRatio ??
      '16:9';

    await updateShotAspectRatio(selectedShot.id, projectId, projectDefault, { immediate: true });
    actions.setAutoAdjustedAspectRatio(null);
  }, [actions, projectId, projects, selectedShot, updateShotAspectRatio]);

  const onManualAspectRatioChange = React.useCallback(() => {
    actions.setAutoAdjustedAspectRatio(null);
  }, [actions]);

  React.useEffect(() => {
    actions.setAutoAdjustedAspectRatio(null);
  }, [actions, selectedShotId]);

  return (
    <div ref={layout.headerContainerRef}>
      <Header
        selectedShot={selectedShot}
        isEditingName={state.isEditingName}
        editingName={state.editingName}
        isTransitioningFromNameEdit={state.isTransitioningFromNameEdit}
        onBack={callbacks.onBack}
        onUpdateShotName={callbacks.onUpdateShotName}
        onPreviousShot={callbacks.onPreviousShot}
        onNextShot={callbacks.onNextShot}
        hasPrevious={callbacks.hasPrevious}
        hasNext={callbacks.hasNext}
        onNameClick={callbacks.onNameClick}
        onNameSave={callbacks.onNameSave}
        onNameCancel={callbacks.onNameCancel}
        onNameKeyDown={callbacks.onNameKeyDown}
        onEditingNameChange={actions.setEditingNameValue}
        autoAdjustedInfo={state.autoAdjustedAspectRatio}
        onRevertAspectRatio={onRevertAspectRatio}
        onManualAspectRatioChange={onManualAspectRatioChange}
        projectAspectRatio={effectiveAspectRatio}
        projectId={projectId}
        centerSectionRef={layout.centerSectionRef}
        isSticky={layout.isSticky}
      />
    </div>
  );
};
