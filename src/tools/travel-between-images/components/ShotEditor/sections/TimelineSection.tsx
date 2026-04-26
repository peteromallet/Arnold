import React from 'react';
import { ShotImagesEditor } from '../../ShotImagesEditor';
import { ImageManagerSkeleton } from '../ui/Skeleton';
import {
  useShotSettingsIdentity,
  useShotSettingsMedia,
  useShotSettingsUi,
} from '../ShotSettingsContext';
import { useModelSettings } from '@/tools/travel-between-images/providers';
import { MODEL_DEFAULTS } from '@/tools/travel-between-images/settings';
import { usePanesStore } from '@/shared/state/panesStore';

interface TimelineSectionProps {
  timelineSectionRef?: (node: HTMLDivElement | null) => void;
  isModeReady: boolean;
  settingsError: string | null;
  isMobile: boolean;
  generationMode?: 'batch' | 'timeline' | 'by-pair';
  onGenerationModeChange?: (mode: 'batch' | 'timeline' | 'by-pair') => void;
  batchVideoFrames: number;
  onBatchVideoFramesChange: (frames: number) => void;
  columns: 2 | 3 | 4 | 6;
  pendingPositions: Map<string, number>;
  onPendingPositionApplied: (generationId: string) => void;
  onSelectionChange?: (hasSelection: boolean) => void;
  defaultPrompt?: string;
  onDefaultPromptChange?: (prompt: string) => void;
  defaultNegativePrompt?: string;
  onDefaultNegativePromptChange?: (prompt: string) => void;
  maxFrameLimit?: number;
  smoothContinuations?: boolean;
  selectedOutputId?: string | null;
  onSelectedOutputChange?: (id: string | null) => void;
  onDragStateChange?: (isDragging: boolean) => void;
  cachedHasStructureVideo?: boolean;
}

export const TimelineSection: React.FC<TimelineSectionProps> = ({
  timelineSectionRef,
  isModeReady,
  settingsError,
  isMobile,
  generationMode,
  onGenerationModeChange,
  batchVideoFrames,
  onBatchVideoFramesChange,
  columns,
  pendingPositions,
  onPendingPositionApplied,
  onSelectionChange,
  defaultPrompt,
  onDefaultPromptChange,
  defaultNegativePrompt,
  onDefaultNegativePromptChange,
  maxFrameLimit,
  smoothContinuations,
  selectedOutputId,
  onSelectedOutputChange,
  onDragStateChange,
  cachedHasStructureVideo,
}) => {
  const { selectedShot, projectId, effectiveAspectRatio } = useShotSettingsIdentity();
  const { state } = useShotSettingsUi();
  const {
    allShotImages,
    unpositionedImages,
    contextImages,
    structureVideo,
    structureVideoHandlers,
    audio,
    imageHandlers,
    shotManagement,
  } = useShotSettingsMedia();
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const { selectedModel } = useModelSettings();
  const timelineFps = MODEL_DEFAULTS[selectedModel]?.fps ?? 16;

  return (
    <div ref={timelineSectionRef} className="flex flex-col w-full gap-4">
      <ShotImagesEditor
        displayOptions={{
          isModeReady,
          settingsError,
          isMobile,
          generationMode: generationMode ?? 'timeline',
          onGenerationModeChange: onGenerationModeChange ?? (() => {}),
          columns,
          skeleton: (
            <ImageManagerSkeleton
              isMobile={isMobile}
              columns={columns}
              shotImages={contextImages}
              projectAspectRatio={effectiveAspectRatio}
            />
          ),
          readOnly: false,
          projectAspectRatio: effectiveAspectRatio,
          cachedHasStructureVideo,
          maxFrameLimit,
          smoothContinuations,
          selectedOutputId,
          onSelectedOutputChange,
        }}
        imageState={{
          selectedShotId: selectedShot.id,
          preloadedImages: allShotImages,
          projectId,
          shotName: selectedShot.name,
          batchVideoFrames,
          pendingPositions,
          unpositionedGenerationsCount: isGenerationsPaneLocked ? 0 : unpositionedImages.length,
          fileInputKey: state.fileInputKey,
          isUploadingImage: state.isUploadingImage,
          uploadProgress: state.uploadProgress,
          duplicatingImageId: state.duplicatingImageId,
          duplicateSuccessImageId: state.duplicateSuccessImageId,
          defaultPrompt,
          onDefaultPromptChange,
          defaultNegativePrompt,
          onDefaultNegativePromptChange,
          structureGuidance: structureVideo.structureGuidance,
          travelGuidanceByModel: structureVideo.travelGuidanceByModel,
          structureVideos: structureVideo.structureVideos,
          structureVideoDefaultsByModel: structureVideo.structureVideoDefaultsByModel,
          isStructureVideoLoading: structureVideo.isLoading,
          audioUrl: audio.audioUrl,
          audioMetadata: audio.audioMetadata,
          timelineFps,
        }}
        editActions={{
          onImageReorder: imageHandlers.onReorder,
          onFramePositionsChange: () => {},
          onFileDrop: imageHandlers.onFileDrop,
          onGenerationDrop: imageHandlers.onGenerationDrop,
          onBatchFileDrop: imageHandlers.onBatchFileDrop,
          onBatchGenerationDrop: imageHandlers.onBatchGenerationDrop,
          onVariantDrop: imageHandlers.onVariantDrop,
          onPendingPositionApplied,
          onImageDelete: imageHandlers.onDelete,
          onBatchImageDelete: imageHandlers.onBatchDelete,
          onImageDuplicate: imageHandlers.onDuplicate,
          onOpenUnpositionedPane: shotManagement.openUnpositionedGenerationsPane,
          onImageUpload: async (files) => {
            if (imageHandlers.onBatchFileDrop) {
              await imageHandlers.onBatchFileDrop(files);
            }
          },
          onPrimaryStructureVideoInputChange: structureVideoHandlers.handleStructureVideoInputChange,
          onUni3cEndPercentChange: structureVideoHandlers.handleUni3cEndPercentChange,
          onAddStructureVideo: structureVideo.addStructureVideo,
          onUpdateStructureVideo: structureVideo.updateStructureVideo,
          onRemoveStructureVideo: structureVideo.removeStructureVideo,
          onSetStructureVideos: structureVideo.setStructureVideos,
          onAudioChange: audio.handleAudioChange,
          onSelectionChange,
          onDragStateChange,
          onTrailingDurationChange: (durationFrames) => {
            if (typeof durationFrames === 'number') {
              onBatchVideoFramesChange(durationFrames);
            }
          },
        }}
        shotWorkflow={{
          allShots: shotManagement.allShots,
          onShotChange: shotManagement.onShotChange,
          onAddToShot: shotManagement.onAddToShot,
          onAddToShotWithoutPosition: shotManagement.onAddToShotWithoutPosition,
          onCreateShot: shotManagement.onCreateShot,
          onNewShotFromSelection: shotManagement.onNewShotFromSelection,
        }}
      />
    </div>
  );
};
