import { useCallback } from 'react';
import type { RefObject } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import type { Resource, StructureVideoMetadata } from '@/features/resources/hooks/useResources';
import type { PrimaryStructureVideo, StructureVideoConfigWithMetadata } from '@/shared/lib/tasks/travelBetweenImages';
import type { OnPrimaryStructureVideoInputChange } from '@/tools/travel-between-images/types/mediaHandlers';
import {
  calculateNewVideoPlacement,
} from '../../utils/timeline-utils';
import { useTapToMove } from '../drag/useTapToMove';

interface ImageDropInterceptorArgs {
  files: File[];
  targetFrame?: number;
  handles?: Array<FileSystemFileHandle | null>;
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  setPendingDropFrame: (frame: number | null) => void;
}

interface GenerationDropInterceptorArgs {
  generationId: string;
  imageUrl: string;
  thumbUrl: string | undefined;
  targetFrame?: number;
  onGenerationDrop?: (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number,
  ) => Promise<void>;
  setPendingDropFrame: (frame: number | null) => void;
  setIsInternalDropProcessing: (value: boolean) => void;
}

interface DuplicateInterceptorArgs {
  imageId: string;
  timelineFrame: number;
  images: GenerationRow[];
  onImageDuplicate: (imageId: string, timelineFrame: number, nextTimelineFrame?: number) => void;
  setPendingDuplicateFrame: (frame: number | null) => void;
}

interface StructureVideoSelectionArgs {
  resource: Resource;
  structureVideos?: StructureVideoConfigWithMetadata[];
  primaryStructureVideo?: PrimaryStructureVideo;
  onAddStructureVideo?: (video: StructureVideoConfigWithMetadata) => void;
  onUpdateStructureVideo?: (index: number, updates: Partial<StructureVideoConfigWithMetadata>) => void;
  onPrimaryStructureVideoInputChange?: OnPrimaryStructureVideoInputChange;
  fullMax: number;
  setShowVideoBrowser: (value: boolean) => void;
}

interface UseTimelineOrchestratorActionsInput {
  enableTapToMove: boolean;
  framePositions: Map<string, number>;
  setFramePositions: (positions: Map<string, number>) => Promise<void>;
  fullMin: number;
  fullMax: number;
  fullRange: number;
  containerWidth: number;
  selectedIds: string[];
  clearSelection: () => void;
  containerRef: RefObject<HTMLDivElement>;
  images: GenerationRow[];
  onImageDuplicate: (imageId: string, timelineFrame: number, nextTimelineFrame?: number) => void;
  setPendingDuplicateFrame: (frame: number | null) => void;
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  setPendingDropFrame: (frame: number | null) => void;
  onGenerationDrop?: (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number,
  ) => Promise<void>;
  setIsInternalDropProcessing: (value: boolean) => void;
  structureVideos?: StructureVideoConfigWithMetadata[];
  primaryStructureVideo?: PrimaryStructureVideo;
  onAddStructureVideo?: (video: StructureVideoConfigWithMetadata) => void;
  onUpdateStructureVideo?: (index: number, updates: Partial<StructureVideoConfigWithMetadata>) => void;
  onPrimaryStructureVideoInputChange?: StructureVideoSelectionArgs['onPrimaryStructureVideoInputChange'];
  setShowVideoBrowser: (value: boolean) => void;
  maxFrameLimit?: number;
}

interface TimelineOrchestratorActionsResult {
  handleImageDropInterceptor: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  handleGenerationDropInterceptor: (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number,
  ) => Promise<void>;
  handleDuplicateInterceptor: (imageId: string, timelineFrame: number) => void;
  handleTapToMoveAction: (imageId: string, targetFrame: number) => Promise<void>;
  handleTapToMoveMultiAction: (imageIds: string[], targetFrame: number) => Promise<void>;
  handleTimelineTapToMove: (clientX: number) => void;
  handleVideoBrowserSelect: (resource: Resource) => void;
}

export async function runImageDropInterceptor({
  files,
  targetFrame,
  handles,
  onFileDrop,
  setPendingDropFrame,
}: ImageDropInterceptorArgs): Promise<void> {
  if (targetFrame !== undefined) {
    setPendingDropFrame(targetFrame);
  }
  if (onFileDrop) {
    await onFileDrop(files, targetFrame, handles);
  }
}

export async function runGenerationDropInterceptor({
  generationId,
  imageUrl,
  thumbUrl,
  targetFrame,
  onGenerationDrop,
  setPendingDropFrame,
  setIsInternalDropProcessing,
}: GenerationDropInterceptorArgs): Promise<void> {
  if (targetFrame !== undefined) {
    setPendingDropFrame(targetFrame);
    setIsInternalDropProcessing(true);
  }
  try {
    if (onGenerationDrop) {
      await onGenerationDrop(generationId, imageUrl, thumbUrl, targetFrame);
    }
  } finally {
    setIsInternalDropProcessing(false);
    setPendingDropFrame(null);
  }
}

export function runDuplicateInterceptor({
  imageId,
  timelineFrame,
  images,
  onImageDuplicate,
  setPendingDuplicateFrame,
}: DuplicateInterceptorArgs): void {
  const sortedImages = [...images]
    .filter((img) => img.timeline_frame !== undefined && img.timeline_frame !== null)
    .sort((a, b) => (a.timeline_frame ?? 0) - (b.timeline_frame ?? 0));

  const currentIndex = sortedImages.findIndex((img) => img.timeline_frame === timelineFrame);
  const nextImage = currentIndex >= 0 && currentIndex < sortedImages.length - 1
    ? sortedImages[currentIndex + 1]
    : null;
  const nextFrame = nextImage?.timeline_frame;

  setPendingDuplicateFrame(timelineFrame);
  onImageDuplicate(imageId, timelineFrame, nextFrame ?? undefined);
}

export function handleTimelineStructureVideoSelect({
  resource,
  structureVideos,
  primaryStructureVideo,
  onAddStructureVideo,
  onUpdateStructureVideo,
  onPrimaryStructureVideoInputChange,
  fullMax,
  setShowVideoBrowser,
}: StructureVideoSelectionArgs): void {
  const metadata = resource.metadata as StructureVideoMetadata;
  if (onAddStructureVideo && metadata.videoMetadata) {
    const placement = calculateNewVideoPlacement(
      metadata.videoMetadata.total_frames,
      structureVideos,
      fullMax,
    );

    if (placement.lastVideoUpdate && onUpdateStructureVideo) {
      onUpdateStructureVideo(placement.lastVideoUpdate.index, {
        end_frame: placement.lastVideoUpdate.newEndFrame,
      });
    }

    onAddStructureVideo({
      path: metadata.videoUrl,
      start_frame: placement.start_frame,
      end_frame: placement.end_frame,
      treatment: 'adjust',
      metadata: metadata.videoMetadata,
      resource_id: resource.id,
    });
  } else if (onPrimaryStructureVideoInputChange) {
    onPrimaryStructureVideoInputChange({
      videoPath: metadata.videoUrl,
      metadata: metadata.videoMetadata,
      treatment: primaryStructureVideo?.treatment ?? 'adjust',
      motionStrength: primaryStructureVideo?.motionStrength ?? 1.0,
      structureType: primaryStructureVideo?.structureType ?? 'flow',
    });
  }

  setShowVideoBrowser(false);
}

export function useTimelineOrchestratorActions({
  enableTapToMove,
  framePositions,
  setFramePositions,
  fullMin,
  fullMax,
  fullRange,
  containerWidth,
  selectedIds,
  clearSelection,
  containerRef,
  images,
  onImageDuplicate,
  setPendingDuplicateFrame,
  onFileDrop,
  setPendingDropFrame,
  onGenerationDrop,
  setIsInternalDropProcessing,
  structureVideos,
  primaryStructureVideo,
  onAddStructureVideo,
  onUpdateStructureVideo,
  onPrimaryStructureVideoInputChange,
  setShowVideoBrowser,
  maxFrameLimit,
}: UseTimelineOrchestratorActionsInput): TimelineOrchestratorActionsResult {
  const handleImageDropInterceptor = useCallback(async (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => {
    await runImageDropInterceptor({
      files,
      targetFrame,
      handles,
      onFileDrop,
      setPendingDropFrame,
    });
  }, [onFileDrop, setPendingDropFrame]);

  const handleGenerationDropInterceptor = useCallback(async (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number,
  ) => {
    await runGenerationDropInterceptor({
      generationId,
      imageUrl,
      thumbUrl,
      targetFrame,
      onGenerationDrop,
      setPendingDropFrame,
      setIsInternalDropProcessing,
    });
  }, [onGenerationDrop, setIsInternalDropProcessing, setPendingDropFrame]);

  const {
    handleTapToMoveAction,
    handleTapToMoveMultiAction,
    handleTimelineTapToMove,
  } = useTapToMove({
    enableTapToMove,
    framePositions,
    setFramePositions,
    fullMin,
    fullMax,
    fullRange,
    containerWidth,
    selectedIds,
    clearSelection,
    containerRef,
    maxFrameLimit,
  });

  const handleDuplicateInterceptor = useCallback((imageId: string, timelineFrame: number) => {
    runDuplicateInterceptor({
      imageId,
      timelineFrame,
      images,
      onImageDuplicate,
      setPendingDuplicateFrame,
    });
  }, [images, onImageDuplicate, setPendingDuplicateFrame]);

  const handleVideoBrowserSelect = useCallback((resource: Resource) => {
    handleTimelineStructureVideoSelect({
      resource,
      structureVideos,
      primaryStructureVideo,
      onAddStructureVideo,
      onUpdateStructureVideo,
      onPrimaryStructureVideoInputChange,
      fullMax,
      setShowVideoBrowser,
    });
  }, [
    fullMax,
    onAddStructureVideo,
    onPrimaryStructureVideoInputChange,
    onUpdateStructureVideo,
    primaryStructureVideo,
    setShowVideoBrowser,
    structureVideos,
  ]);

  return {
    handleImageDropInterceptor,
    handleGenerationDropInterceptor,
    handleDuplicateInterceptor,
    handleTapToMoveAction,
    handleTapToMoveMultiAction,
    handleTimelineTapToMove,
    handleVideoBrowserSelect,
  };
}
