import React, { createContext, useContext } from 'react';
import type { ShotSettingsContextValue } from './ShotSettingsContext.types';

type ShotSettingsIdentityValue = Pick<
  ShotSettingsContextValue,
  'selectedShot' | 'selectedShotId' | 'projectId' | 'selectedProjectId' | 'effectiveAspectRatio' | 'projects'
>;

type ShotSettingsUiValue = Pick<
  ShotSettingsContextValue,
  'state' | 'actions' | 'dimensions'
>;

type ShotSettingsMediaValue = Pick<
  ShotSettingsContextValue,
  | 'allShotImages'
  | 'timelineImages'
  | 'unpositionedImages'
  | 'contextImages'
  | 'videoOutputs'
  | 'simpleFilteredImages'
  | 'structureVideo'
  | 'structureVideoHandlers'
  | 'audio'
  | 'imageHandlers'
  | 'shotManagement'
>;

type ShotSettingsGenerationValue = Pick<
  ShotSettingsContextValue,
  'loraManager' | 'availableLoras' | 'generationMode' | 'generationHandlers' | 'joinState' | 'queryClient'
>;

const ShotSettingsIdentityContext = createContext<ShotSettingsIdentityValue | null>(null);
const ShotSettingsUiContext = createContext<ShotSettingsUiValue | null>(null);
const ShotSettingsMediaContext = createContext<ShotSettingsMediaValue | null>(null);
const ShotSettingsGenerationContext = createContext<ShotSettingsGenerationValue | null>(null);

function requireShotSettingsContext<T>(ctx: T | null, hookName: string): T {
  if (!ctx) {
    throw new Error(`${hookName} must be used within ShotSettingsProvider`);
  }
  return ctx;
}

export function useShotSettingsIdentity() {
  return requireShotSettingsContext(
    useContext(ShotSettingsIdentityContext),
    'useShotSettingsIdentity',
  );
}

export function useShotSettingsUi() {
  return requireShotSettingsContext(
    useContext(ShotSettingsUiContext),
    'useShotSettingsUi',
  );
}

export function useShotSettingsMedia() {
  return requireShotSettingsContext(
    useContext(ShotSettingsMediaContext),
    'useShotSettingsMedia',
  );
}

export function useShotSettingsGeneration() {
  return requireShotSettingsContext(
    useContext(ShotSettingsGenerationContext),
    'useShotSettingsGeneration',
  );
}

/** @deprecated Migrate production code to the split shot-editor hooks. */
export function useShotSettingsContext(): ShotSettingsContextValue {
  return {
    ...useShotSettingsIdentity(),
    ...useShotSettingsUi(),
    ...useShotSettingsMedia(),
    ...useShotSettingsGeneration(),
  };
}

export const ShotSettingsProvider: React.FC<{
  value: ShotSettingsContextValue;
  children: React.ReactNode;
}> = ({ value, children }) => {
  const identityValue: ShotSettingsIdentityValue = {
    selectedShot: value.selectedShot,
    selectedShotId: value.selectedShotId,
    projectId: value.projectId,
    selectedProjectId: value.selectedProjectId,
    effectiveAspectRatio: value.effectiveAspectRatio,
    projects: value.projects,
  };
  const uiValue: ShotSettingsUiValue = {
    state: value.state,
    actions: value.actions,
    dimensions: value.dimensions,
  };
  const mediaValue: ShotSettingsMediaValue = {
    allShotImages: value.allShotImages,
    timelineImages: value.timelineImages,
    unpositionedImages: value.unpositionedImages,
    contextImages: value.contextImages,
    videoOutputs: value.videoOutputs,
    simpleFilteredImages: value.simpleFilteredImages,
    structureVideo: value.structureVideo,
    structureVideoHandlers: value.structureVideoHandlers,
    audio: value.audio,
    imageHandlers: value.imageHandlers,
    shotManagement: value.shotManagement,
  };
  const generationValue: ShotSettingsGenerationValue = {
    loraManager: value.loraManager,
    availableLoras: value.availableLoras,
    generationMode: value.generationMode,
    generationHandlers: value.generationHandlers,
    joinState: value.joinState,
    queryClient: value.queryClient,
  };

  return (
    <ShotSettingsIdentityContext.Provider value={identityValue}>
      <ShotSettingsUiContext.Provider value={uiValue}>
        <ShotSettingsMediaContext.Provider value={mediaValue}>
          <ShotSettingsGenerationContext.Provider value={generationValue}>
            {children}
          </ShotSettingsGenerationContext.Provider>
        </ShotSettingsMediaContext.Provider>
      </ShotSettingsUiContext.Provider>
    </ShotSettingsIdentityContext.Provider>
  );
};
