import React from 'react';
import type { Shot } from '@/domains/generation/types';
import type { ActiveLora } from '@/domains/lora/types/lora';
import type { GenerationRow } from '@/domains/generation/types';
import type { Project } from '@/types/project';
import type { TravelGuidanceMode } from '@/shared/lib/tasks/travelGuidance';
import type { resolveTravelStructureState } from '@/shared/lib/tasks/travelBetweenImages';
import { Dialog, DialogContent, DialogHeader } from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { useExtraLargeModal } from '@/shared/hooks/useModal';
import { LoraSelectorModal } from '@/domains/lora/components';
import {
  VideoGenerationModalAccordionContent,
  VideoGenerationModalHeader,
  VideoGenerationModalLoadingContent,
} from './VideoGenerationModalSections';
import { useVideoGenerationModalController } from './hooks/useVideoGenerationModalController';
import { useBatchVideoGeneration } from './hooks/useBatchVideoGeneration';
import { getModelSpec } from '../settings';
import { VideoTravelSettingsProvider } from '../providers';

export interface VideoGenerationModalProps {
  isOpen: boolean;
  onClose: () => void;
  shot: Shot;
  /** Whether the "Shot Images" section starts open. Default: false */
  defaultTopOpen?: boolean;
  /** Whether the "Final Video" section starts open. Default: false */
  defaultFinalVideoOpen?: boolean;
  /** Whether the "Generation Settings" section starts open. Default: true */
  defaultBottomOpen?: boolean;
}

// Inner body renders inside VideoTravelSettingsProvider so it can call the
// provider-scoped hooks (useBatchVideoGeneration reads live settings via the
// provider). Everything outside the provider (the shell below) handles shot
// data fetching, LoRA modal UI state, and navigation.
interface ModalBodyProps {
  shot: Shot;
  projectId: string | null;
  onClose: () => void;
  randomSeed: boolean;
  positionedImages: Array<{ metadata?: Record<string, unknown> | null }>;
  effectiveAspectRatio: string;
  selectedLoras: ActiveLora[];
  structureState: ReturnType<typeof resolveTravelStructureState>;
  isLoading: boolean;
  shotGenerations: GenerationRow[];
  projects: Project[];
  selectedProjectId: string | null;
  accordionDefaults: {
    defaultTopOpen: boolean;
    defaultFinalVideoOpen: boolean;
    defaultBottomOpen: boolean;
  };
  accordionProps: {
    availableLoras: ReturnType<typeof useVideoGenerationModalController>['availableLoras'];
    accelerated: boolean;
    onAcceleratedChange: (v: boolean) => void;
    onRandomSeedChange: (v: boolean) => void;
    hasStructureVideo: boolean;
    guidanceKind: TravelGuidanceMode | undefined;
    validPresetId: string | undefined;
    status: 'idle' | 'loading' | 'ready' | 'saving' | 'error';
    onOpenLoraModal: () => void;
    onRemoveLora: (loraId: string) => void;
    onLoraStrengthChange: (loraId: string, strength: number) => void;
    onAddTriggerWord: (word: string) => void;
    settings: ReturnType<typeof useVideoGenerationModalController>['settings'];
    updateField: ReturnType<typeof useVideoGenerationModalController>['updateField'];
  };
}

const VideoGenerationModalBody: React.FC<ModalBodyProps> = ({
  shot,
  projectId,
  onClose,
  randomSeed,
  positionedImages,
  effectiveAspectRatio,
  selectedLoras,
  structureState,
  isLoading,
  shotGenerations,
  projects,
  selectedProjectId,
  accordionDefaults,
  accordionProps,
}) => {
  const { handleGenerate, isGenerating, justQueued, isDisabled } = useBatchVideoGeneration({
    shot,
    projectId,
    onClose,
    randomSeed,
    positionedImages,
    effectiveAspectRatio,
    selectedLoras,
    structureState,
  });

  const disabledWithLoading = isDisabled || isLoading;

  return (
    <>
      {isLoading ? (
        <VideoGenerationModalLoadingContent />
      ) : (
        <VideoGenerationModalAccordionContent
          defaultTopOpen={accordionDefaults.defaultTopOpen}
          defaultFinalVideoOpen={accordionDefaults.defaultFinalVideoOpen}
          defaultBottomOpen={accordionDefaults.defaultBottomOpen}
          shotId={shot.id}
          projectId={selectedProjectId || ''}
          positionedImages={positionedImages as never}
          shotGenerations={shotGenerations}
          effectiveAspectRatio={effectiveAspectRatio}
          settings={accordionProps.settings}
          updateField={accordionProps.updateField}
          projects={projects}
          selectedProjectId={selectedProjectId}
          selectedLoras={selectedLoras}
          availableLoras={accordionProps.availableLoras}
          accelerated={accordionProps.accelerated}
          onAcceleratedChange={accordionProps.onAcceleratedChange}
          randomSeed={randomSeed}
          onRandomSeedChange={accordionProps.onRandomSeedChange}
          imageCount={positionedImages.length}
          hasStructureVideo={accordionProps.hasStructureVideo}
          guidanceKind={accordionProps.guidanceKind}
          validPresetId={accordionProps.validPresetId}
          status={accordionProps.status}
          onOpenLoraModal={accordionProps.onOpenLoraModal}
          onRemoveLora={accordionProps.onRemoveLora}
          onLoraStrengthChange={accordionProps.onLoraStrengthChange}
          onAddTriggerWord={accordionProps.onAddTriggerWord}
        />
      )}

      <div className="flex-shrink-0 border-t border-zinc-700 bg-background px-6 py-4 -mx-6 -mb-6 flex justify-center">
        {isLoading ? (
          <Skeleton className="h-11 w-full max-w-md rounded-md" />
        ) : (
          <Button
            size="retro-default"
            className="w-full max-w-md"
            variant={justQueued ? 'success' : 'retro'}
            onClick={handleGenerate}
            disabled={disabledWithLoading}
          >
            {justQueued
              ? 'Submitted, closing modal...'
              : isGenerating
                ? 'Creating Tasks...'
                : 'Generate Video'}
          </Button>
        )}
      </div>
    </>
  );
};

/**
 * Video Generation Modal - Opens a simplified video generation form for a shot
 * Always operates in Batch mode (not timeline mode)
 * Changes update the actual shot settings
 */
export const VideoGenerationModal: React.FC<VideoGenerationModalProps> = ({
  isOpen,
  onClose,
  shot,
  defaultTopOpen = false,
  defaultFinalVideoOpen = false,
  defaultBottomOpen = true,
}) => {
  const modal = useExtraLargeModal();

  const {
    projects,
    selectedProjectId,
    settings,
    status,
    updateField,
    availableLoras,
    positionedImages,
    isLoading,
    hasStructureVideo,
    guidanceKind,
    structureState,
    accelerated,
    setAccelerated,
    randomSeed,
    setRandomSeed,
    validPresetId,
    selectedLoras,
    isLoraModalOpen,
    openLoraModal,
    closeLoraModal,
    handleAddLora,
    handleRemoveLora,
    handleLoraStrengthChange,
    handleAddTriggerWord,
    selectedLorasForModal,
    effectiveAspectRatio,
    shotGenerations,
    handleNavigateToShot,
    handleDialogOpenChange,
    updateShotMode,
  } = useVideoGenerationModalController({
    isOpen,
    onClose,
    shot,
  });

  return (
    <>
      <VideoTravelSettingsProvider
        projectId={selectedProjectId}
        shotId={shot.id}
        selectedShot={shot}
        availableLoras={availableLoras ?? []}
        updateShotMode={updateShotMode}
      >
        <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
          <DialogContent className={modal.className} style={{ ...modal.style, maxWidth: '1000px' }}>
            <DialogHeader className={modal.headerClass}>
              <VideoGenerationModalHeader
                shotName={shot.name}
                onNavigateToShot={handleNavigateToShot}
              />
            </DialogHeader>

            <div className={`${modal.scrollClass} -mx-6 px-6 flex-1 min-h-0`}>
              <VideoGenerationModalBody
                shot={shot}
                projectId={selectedProjectId}
                onClose={onClose}
                randomSeed={randomSeed}
                positionedImages={positionedImages}
                effectiveAspectRatio={effectiveAspectRatio}
                selectedLoras={selectedLoras}
                structureState={structureState}
                isLoading={isLoading}
                shotGenerations={shotGenerations}
                projects={projects}
                selectedProjectId={selectedProjectId}
                accordionDefaults={{
                  defaultTopOpen,
                  defaultFinalVideoOpen,
                  defaultBottomOpen,
                }}
                accordionProps={{
                  availableLoras,
                  accelerated,
                  onAcceleratedChange: setAccelerated,
                  onRandomSeedChange: setRandomSeed,
                  hasStructureVideo,
                  guidanceKind,
                  validPresetId,
                  status,
                  onOpenLoraModal: openLoraModal,
                  onRemoveLora: handleRemoveLora,
                  onLoraStrengthChange: handleLoraStrengthChange,
                  onAddTriggerWord: handleAddTriggerWord,
                  settings,
                  updateField,
                }}
              />
            </div>
          </DialogContent>
        </Dialog>
      </VideoTravelSettingsProvider>

      <LoraSelectorModal
        isOpen={isLoraModalOpen}
        onClose={closeLoraModal}
        loras={availableLoras}
        onAddLora={handleAddLora}
        onRemoveLora={handleRemoveLora}
        onUpdateLoraStrength={handleLoraStrengthChange}
        selectedLoras={selectedLorasForModal}
        loraType={getModelSpec(settings.selectedModel).loraFamily}
      />
    </>
  );
};
