import { useEffect, useRef } from 'react';
import type { DragEvent, MouseEvent as ReactMouseEvent, RefObject } from 'react';
import { useGallerySelectionBridge } from '@/shared/hooks/gallery/useGallerySelectionBridge';
import { useIsMobile, useIsTablet } from '@/shared/hooks/mobile';
import { usePrefetchTaskData } from '@/shared/hooks/tasks/useTaskPrefetch';
import {
  getTrailingEffectiveEnd,
  getPairInfo,
  getTimelineDimensions,
} from '../../utils/timeline-utils';
import { useTimelineDrag } from '../drag/useTimelineDrag';
import { useTimelineSelection } from '../useTimelineSelection';
import { usePendingFrames } from '../segment/usePendingFrames';
import { useComputedTimelineData } from './useComputedTimelineData';
import { useTimelineUiState } from './useTimelineUiState';
import { useEndpointDrag } from '../drag/useEndpointDrag';
import {
  useTimelineViewportController,
  type TimelineViewportControllerResult,
} from './useTimelineViewportController';
import { useUnifiedDrop } from '../drag/useUnifiedDrop';
import type { GenerationRow } from '@/domains/generation/types';
import type { PairData } from '../../TimelineContainer/types';
import type { Resource } from '@/features/resources/hooks/useResources';
import type { PrimaryStructureVideo, StructureVideoConfigWithMetadata } from '@/shared/lib/tasks/travelBetweenImages';
import type { DragType } from '@/shared/lib/dnd/dragDrop';
import type { OnPrimaryStructureVideoInputChange } from '@/tools/travel-between-images/types/mediaHandlers';
import {
  handleTimelineStructureVideoSelect,
  runDuplicateInterceptor,
  runGenerationDropInterceptor,
  runImageDropInterceptor,
  useTimelineOrchestratorActions,
} from './useTimelineOrchestratorActions';
import { useModelSettings } from '@/tools/travel-between-images/providers';
import { MODEL_DEFAULTS } from '@/tools/travel-between-images/settings';

interface TimelineOrchestratorCoreProps {
  shotId: string;
  images: GenerationRow[];
  framePositions: Map<string, number>;
  setFramePositions: (positions: Map<string, number>) => Promise<void>;
}

interface TimelineOrchestratorDropHandlers {
  onImageReorder: (orderedIds: string[], draggedItemId?: string) => void;
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  onGenerationDrop?: (
    generationId: string,
    imageUrl: string,
    thumbUrl: string | undefined,
    targetFrame?: number,
  ) => Promise<void>;
}

interface TimelineOrchestratorInteractionProps {
  setIsDragInProgress: (dragging: boolean) => void;
  onImageDuplicate: (imageId: string, timelineFrame: number, nextTimelineFrame?: number) => void;
  readOnly?: boolean;
  isUploadingImage?: boolean;
  maxFrameLimit?: number;
  hasExistingTrailingVideo?: boolean;
}

interface TimelineOrchestratorStructureVideoConfig {
  structureVideos?: StructureVideoConfigWithMetadata[];
  primaryStructureVideo?: PrimaryStructureVideo;
  onAddStructureVideo?: (video: StructureVideoConfigWithMetadata) => void;
  onUpdateStructureVideo?: (index: number, updates: Partial<StructureVideoConfigWithMetadata>) => void;
  onPrimaryStructureVideoInputChange?: OnPrimaryStructureVideoInputChange;
}

interface TimelineOrchestratorStructureVideoProps {
  structureVideo?: TimelineOrchestratorStructureVideoConfig;
}

type UseTimelineOrchestratorProps = TimelineOrchestratorCoreProps &
  TimelineOrchestratorDropHandlers &
  TimelineOrchestratorInteractionProps &
  TimelineOrchestratorStructureVideoProps;

interface UseTimelineOrchestratorReturn {
  refs: {
    timelineRef: RefObject<HTMLDivElement>;
    containerRef: RefObject<HTMLDivElement>;
  };
  viewport: Omit<TimelineViewportControllerResult, 'dragStartDimensionsRef'>;
  drag: {
    state: { isDragging: boolean; activeId: string | null };
    dragOffset: { x: number; y: number } | null;
    currentDragFrame: number | null;
    swapTargetId: string | null;
    pushMode: 'right' | 'left' | null;
    handleMouseDown: (e: ReactMouseEvent, id: string, containerRef: RefObject<HTMLDivElement>) => void;
  };
  selection: {
    selectedIds: string[];
    showSelectionBar: boolean;
    isSelected: (id: string) => boolean;
    toggleSelection: (id: string) => void;
    clearSelection: () => void;
  };
  pending: {
    pendingDropFrame: number | null;
    pendingDuplicateFrame: number | null;
    pendingExternalAddFrame: number | null;
    activePendingFrame: number | null;
    isInternalDropProcessing: boolean;
  };
  drop: {
    isFileOver: boolean;
    dropTargetFrame: number | null;
    dragType: DragType;
    handleDragEnter: (e: DragEvent<HTMLDivElement>) => void;
    handleDragOver: (e: DragEvent<HTMLDivElement>, containerRef: RefObject<HTMLDivElement>) => void;
    handleDragLeave: (e: DragEvent<HTMLDivElement>) => void;
    handleDrop: (e: DragEvent<HTMLDivElement>, containerRef: RefObject<HTMLDivElement>) => Promise<void>;
  };
  computed: {
    currentPositions: Map<string, number>;
    pairInfo: ReturnType<typeof getPairInfo>;
    pairDataByIndex: Map<number, PairData>;
    localShotGenPositions: Map<string, number>;
    showPairLabels: boolean;
  };
  actions: {
    handleImageDropInterceptor: (files: File[], targetFrame?: number) => Promise<void>;
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
    handleEndpointMouseDown: (e: ReactMouseEvent, endpointId: string) => void;
  };
  endpoint: {
    endpointDragFrame: number | null;
    isEndpointDragging: boolean;
  };
  uiState: {
    resetGap: number;
    setResetGap: (value: number) => void;
    maxGap: number;
    showVideoBrowser: boolean;
    setShowVideoBrowser: (value: boolean) => void;
    isUploadingStructureVideo: boolean;
    setIsUploadingStructureVideo: (value: boolean) => void;
  };
  device: {
    isMobile: boolean;
    isTablet: boolean;
    enableTapToMove: boolean;
    prefetchTaskData: (generationId: string) => void;
  };
}

export function useTimelineOrchestrator({
  shotId,
  images,
  framePositions,
  setFramePositions,
  onImageReorder,
  onFileDrop,
  onGenerationDrop,
  setIsDragInProgress,
  onImageDuplicate,
  readOnly = false,
  isUploadingImage = false,
  maxFrameLimit = 81,
  structureVideo,
  hasExistingTrailingVideo = false,
}: UseTimelineOrchestratorProps): UseTimelineOrchestratorReturn {
  const { selectedModel } = useModelSettings();
  const defaultFrameGap = MODEL_DEFAULTS[selectedModel]?.frames;
  const {
    structureVideos,
    primaryStructureVideo,
    onAddStructureVideo,
    onUpdateStructureVideo,
    onPrimaryStructureVideoInputChange,
  } = structureVideo ?? {};

  const timelineRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isEndpointDraggingRef = useRef(false);

  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const enableTapToMove = isTablet && !readOnly;
  const prefetchTaskData = usePrefetchTaskData();

  const uiState = useTimelineUiState({ maxFrameLimit, defaultFrameGap });
  const {
    pendingDropFrame,
    setPendingDropFrame,
    pendingDuplicateFrame,
    setPendingDuplicateFrame,
    pendingExternalAddFrame,
    isInternalDropProcessing,
    setIsInternalDropProcessing,
    activePendingFrame,
  } = usePendingFrames({ shotId, images, isUploadingImage });

  const {
    selectedIds,
    showSelectionBar,
    isSelected,
    toggleSelection,
    clearSelection,
    lockSelection,
    unlockSelection,
  } = useTimelineSelection({ isEnabled: !readOnly });

  useGallerySelectionBridge({
    selectedIds,
    images,
    clearLocalSelection: clearSelection,
  });

  const trailingEffectiveEnd = getTrailingEffectiveEnd({
    framePositions,
    imagesCount: images.length,
    hasExistingTrailingVideo,
  });
  const rawDimensions = getTimelineDimensions(
    framePositions,
    [pendingDropFrame, pendingDuplicateFrame, pendingExternalAddFrame, trailingEffectiveEnd],
  );
  const containerRect = containerRef.current?.getBoundingClientRect() || null;

  const {
    dragState,
    dragOffset,
    currentDragFrame,
    swapTargetId,
    pushMode,
    dynamicPositions,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
  } = useTimelineDrag({
    framePositions,
    setFramePositions,
    images,
    onImageReorder,
    fullMin: rawDimensions.fullMin,
    fullMax: rawDimensions.fullMax,
    fullRange: rawDimensions.fullRange,
    containerRect,
    setIsDragInProgress,
    selectedIds,
    onDragStart: lockSelection,
    onDragEnd: unlockSelection,
    maxFrameLimit,
  });

  const viewport = useTimelineViewportController({
    framePositions,
    pendingDropFrame,
    pendingDuplicateFrame,
    pendingExternalAddFrame,
    imagesCount: images.length,
    hasExistingTrailingVideo,
    timelineRef,
    containerRef,
    isEndpointDraggingRef,
    dragState,
    shotId,
    handleMouseMove,
    handleMouseUp,
  });

  useEffect(() => {
    if (uiState.resetGap > uiState.maxGap) {
      uiState.setResetGap(uiState.maxGap);
    }
  }, [uiState]);

  const {
    handleImageDropInterceptor,
    handleGenerationDropInterceptor,
    handleDuplicateInterceptor,
    handleTapToMoveAction,
    handleTapToMoveMultiAction,
    handleTimelineTapToMove,
    handleVideoBrowserSelect,
  } = useTimelineOrchestratorActions({
    enableTapToMove,
    framePositions,
    setFramePositions,
    fullMin: viewport.fullMin,
    fullMax: viewport.fullMax,
    fullRange: viewport.fullRange,
    containerWidth: viewport.containerWidth,
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
    setShowVideoBrowser: uiState.setShowVideoBrowser,
    maxFrameLimit,
  });

  const drop = useUnifiedDrop({
    onFileDrop: handleImageDropInterceptor,
    onGenerationDrop: handleGenerationDropInterceptor,
    fullMin: viewport.fullMin,
    fullRange: viewport.fullRange,
  });

  const {
    endpointDragFrame,
    isEndpointDragging,
    handleEndpointMouseDown,
  } = useEndpointDrag({
    readOnly,
    fullMin: viewport.fullMin,
    fullMax: viewport.fullMax,
    fullRange: viewport.fullRange,
    containerWidth: viewport.containerWidth,
    maxFrameLimit,
    dynamicPositions,
    framePositions,
    setFramePositions,
    containerRef,
    dragStartDimensionsRef: viewport.dragStartDimensionsRef,
    isEndpointDraggingRef,
  });

  const currentPositions = dynamicPositions();
  const {
    pairInfo,
    pairDataByIndex,
    localShotGenPositions,
    showPairLabels,
  } = useComputedTimelineData({
    currentPositions,
    images,
    containerWidth: viewport.containerWidth,
    fullRange: viewport.fullRange,
    zoomLevel: viewport.zoomLevel,
  });

  return {
    refs: {
      timelineRef,
      containerRef,
    },
    viewport: {
      fullMin: viewport.fullMin,
      fullMax: viewport.fullMax,
      fullRange: viewport.fullRange,
      containerWidth: viewport.containerWidth,
      zoomLevel: viewport.zoomLevel,
      handleZoomInToCenter: viewport.handleZoomInToCenter,
      handleZoomOutFromCenter: viewport.handleZoomOutFromCenter,
      handleZoomReset: viewport.handleZoomReset,
      handleZoomToStart: viewport.handleZoomToStart,
      handleTimelineDoubleClick: viewport.handleTimelineDoubleClick,
    },
    drag: {
      state: dragState,
      dragOffset,
      currentDragFrame,
      swapTargetId,
      pushMode,
      handleMouseDown,
    },
    selection: {
      selectedIds,
      showSelectionBar,
      isSelected,
      toggleSelection,
      clearSelection,
    },
    pending: {
      pendingDropFrame,
      pendingDuplicateFrame,
      pendingExternalAddFrame,
      activePendingFrame,
      isInternalDropProcessing,
    },
    drop,
    computed: {
      currentPositions,
      pairInfo,
      pairDataByIndex,
      localShotGenPositions,
      showPairLabels,
    },
    actions: {
      handleImageDropInterceptor,
      handleGenerationDropInterceptor,
      handleDuplicateInterceptor,
      handleTapToMoveAction,
      handleTapToMoveMultiAction,
      handleTimelineTapToMove,
      handleVideoBrowserSelect,
      handleEndpointMouseDown,
    },
    endpoint: {
      endpointDragFrame,
      isEndpointDragging,
    },
    uiState,
    device: {
      isMobile,
      isTablet,
      enableTapToMove,
      prefetchTaskData,
    },
  };
}
