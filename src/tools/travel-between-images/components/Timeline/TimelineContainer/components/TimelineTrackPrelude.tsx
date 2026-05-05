import React from 'react';
import { GenerationRow } from '@/domains/generation/types';
import { SegmentSlot } from '@/shared/hooks/segments';
import { PairData } from '@/shared/types/pairData';
import {
  useTimelineFps,
  type TimelineMediaContextValue,
} from '../../TimelineMediaContext';
import { AudioStrip } from '../../AudioStrip';
import { GuidanceVideoStrip } from '../../GuidanceVideoStrip';
import { GuidanceVideoUploader } from '../../GuidanceVideoUploader';
import { GuidanceVideosContainer } from '../../GuidanceVideosContainer';
import { SegmentOutputStrip } from '../../SegmentOutputStrip';
import { PENDING_POSITION_KEY, sortPositionEntries } from '../../utils/timeline-utils';

interface TimelinePairInfo {
  index: number;
  startId: string;
  endId: string;
  startFrame: number;
  endFrame: number;
  frames: number;
  generationStart: number;
  contextStart: number;
  contextEnd: number;
}

interface TimelineTrackPreludeProps {
  timeline: {
    shotId: string;
    projectId?: string;
    readOnly: boolean;
    images: GenerationRow[];
    imagePositions: Map<string, number>;
    activePendingFrame: number | null;
    trailingEndFrame: number | undefined;
    hasCallbackTrailingVideo: boolean;
    hasLiveTrailingVideo: boolean;
    projectAspectRatio?: string;
    pairInfoWithPending: TimelinePairInfo[];
    pairDataByIndex: Map<number, PairData>;
    localShotGenPositions: Map<string, number>;
    segmentSlots?: SegmentSlot[];
    isSegmentsLoading?: boolean;
    hasPendingTask?: (pairShotGenerationId: string | null | undefined) => boolean;
    selectedOutputId?: string | null;
    onPairClick?: (pairIndex: number) => void;
    onOpenPairSettings?: (pairIndex: number) => void;
    onSegmentFrameCountChange?: (pairShotGenerationId: string, frameCount: number) => void;
    onTrailingEndFrameChange: (endFrame: number | undefined) => void;
    onTrailingVideoInfo: (videoUrl: string | null) => void;
    onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
    videoOutputs?: GenerationRow[];
  };
  guidance: Pick<
    TimelineMediaContextValue,
    | 'structureVideos'
    | 'isStructureVideoLoading'
    | 'cachedHasStructureVideo'
    | 'onAddStructureVideo'
    | 'onUpdateStructureVideo'
    | 'onRemoveStructureVideo'
    | 'primaryStructureVideo'
    | 'onPrimaryStructureVideoInputChange'
  > & {
    isUploadingStructureVideo: boolean;
    setIsUploadingStructureVideo: (value: boolean) => void;
  };
  audio: {
    audioUrl?: string | null;
    audioMetadata?: { duration: number; name?: string } | null;
    onAudioChange?: (
      audioUrl: string | null,
      metadata: { duration: number; name?: string } | null,
    ) => void;
  };
  layout: {
    fullMin: number;
    fullMax: number;
    fullRange: number;
    containerWidth: number;
    zoomLevel: number;
    hasNoImages: boolean;
  };
  zoom: {
    onZoomIn: () => void;
    onZoomOut: () => void;
    onZoomReset: () => void;
    onZoomToStart: () => void;
  };
}

export const TimelineTrackPrelude: React.FC<TimelineTrackPreludeProps> = ({
  timeline,
  guidance,
  audio,
  layout,
  zoom,
}) => {
  const timelineFps = useTimelineFps();
  const {
    shotId,
    projectId,
    readOnly,
    images,
    imagePositions,
    activePendingFrame,
    trailingEndFrame,
    hasCallbackTrailingVideo,
    hasLiveTrailingVideo,
    projectAspectRatio,
    pairInfoWithPending,
    pairDataByIndex,
    localShotGenPositions,
    segmentSlots,
    isSegmentsLoading,
    hasPendingTask,
    selectedOutputId,
    onPairClick,
    onOpenPairSettings,
    onSegmentFrameCountChange,
    onTrailingEndFrameChange,
    onTrailingVideoInfo,
    videoOutputs,
  } = timeline;

  return (
    <>
      {shotId && (projectId || (readOnly && videoOutputs)) && (() => {
        const sortedEntries = imagePositions.size > 0
          ? sortPositionEntries(imagePositions)
          : [];
        const lastEntry = sortedEntries[sortedEntries.length - 1];
        const isMultiImage = images.length > 1;
        const realLastFrame = lastEntry ? lastEntry[1] : undefined;
        const pendingIsLast = activePendingFrame !== null
          && realLastFrame !== undefined
          && activePendingFrame > realLastFrame;
        const effectiveLastFrame = pendingIsLast ? activePendingFrame : realLastFrame;
        const resolvedSegmentSlots = segmentSlots ?? [];
        const hasTrailingSegment =
          Boolean(lastEntry)
          && (trailingEndFrame !== undefined || hasCallbackTrailingVideo || hasLiveTrailingVideo);
        // Hide the segment output strip when the shot has ≤2 timeline images.
        // In that mode, the segment video IS the final video — showing
        // the strip is redundant. When the user adds a 3rd image, images.length
        // updates reactively and the strip reappears.
        const shouldHideSegmentOutputStrip = images.length <= 2;

        return (
          shouldHideSegmentOutputStrip
            ? <div className="h-8" />
            : <SegmentOutputStrip
              shotId={shotId}
              projectId={projectId}
              readOnly={readOnly}
              projectAspectRatio={projectAspectRatio}
              pairInfo={pairInfoWithPending}
              fullMin={layout.fullMin}
              fullMax={layout.fullMax}
              fullRange={layout.fullRange}
              containerWidth={layout.containerWidth}
              zoomLevel={layout.zoomLevel}
              segmentSlots={resolvedSegmentSlots}
              isLoading={isSegmentsLoading}
              localShotGenPositions={localShotGenPositions}
              hasPendingTask={hasPendingTask}
              pairDataByIndex={pairDataByIndex}
              onOpenPairSettings={onPairClick ? onOpenPairSettings : undefined}
              selectedParentId={selectedOutputId}
              onSegmentFrameCountChange={onSegmentFrameCountChange}
              trailingSegmentMode={hasTrailingSegment && lastEntry
                ? (() => {
                  const [imageId, imageFrame] = lastEntry;
                  const resolvedEndFrame = trailingEndFrame ?? (imageFrame + (isMultiImage ? 17 : 49));
                  const trailingDuration = resolvedEndFrame - imageFrame;
                  const effectiveImageId = pendingIsLast ? PENDING_POSITION_KEY : imageId;
                  const effectiveImageFrame = pendingIsLast ? activePendingFrame : imageFrame;
                  const effectiveEndFrame = pendingIsLast
                    ? (activePendingFrame ?? imageFrame) + trailingDuration
                    : resolvedEndFrame;
                  return {
                    imageId: effectiveImageId,
                    imageFrame: effectiveImageFrame,
                    endFrame: effectiveEndFrame,
                  };
                })()
                : undefined}
              isMultiImage={isMultiImage}
              lastImageFrame={effectiveLastFrame}
              onAddTrailingSegment={realLastFrame !== undefined && lastEntry
                ? () => {
                  onTrailingEndFrameChange(realLastFrame + 17);
                }
                : undefined}
              onRemoveTrailingSegment={isMultiImage && trailingEndFrame !== undefined
                ? () => {
                  onTrailingEndFrameChange(undefined);
                }
                : undefined}
              onTrailingVideoInfo={onTrailingVideoInfo}
            />
        );
      })()}

      {shotId && (projectId || readOnly) && (
        guidance.structureVideos && guidance.onUpdateStructureVideo && guidance.onRemoveStructureVideo ? (
          <GuidanceVideosContainer
            structureVideos={guidance.structureVideos}
            isLoading={guidance.isStructureVideoLoading}
            cachedHasStructureVideo={guidance.cachedHasStructureVideo}
            shotId={shotId}
            onUpdateVideo={guidance.onUpdateStructureVideo}
            onRemoveVideo={guidance.onRemoveStructureVideo}
            fullMin={layout.fullMin}
            fullMax={layout.fullMax}
            fullRange={layout.fullRange}
            containerWidth={layout.containerWidth}
            zoomLevel={layout.zoomLevel}
            timelineFrameCount={images.length}
            readOnly={readOnly}
          />
        ) : guidance.onPrimaryStructureVideoInputChange && (
          guidance.primaryStructureVideo.path ? (
            <GuidanceVideoStrip
              videoUrl={guidance.primaryStructureVideo.path}
              videoMetadata={guidance.primaryStructureVideo.metadata || null}
              treatment={guidance.primaryStructureVideo.treatment}
              onTreatmentChange={(treatment) => guidance.onPrimaryStructureVideoInputChange?.({
                videoPath: guidance.primaryStructureVideo.path,
                metadata: guidance.primaryStructureVideo.metadata ?? null,
                treatment,
                motionStrength: guidance.primaryStructureVideo.motionStrength,
                structureType: guidance.primaryStructureVideo.structureType,
              })}
              onRemove={() => guidance.onPrimaryStructureVideoInputChange?.({
                videoPath: null,
                metadata: null,
                treatment: 'adjust',
                motionStrength: 1.0,
                structureType: 'flow',
              })}
              onMetadataExtracted={(metadata) => guidance.onPrimaryStructureVideoInputChange?.({
                videoPath: guidance.primaryStructureVideo.path,
                metadata,
                treatment: guidance.primaryStructureVideo.treatment,
                motionStrength: guidance.primaryStructureVideo.motionStrength,
                structureType: guidance.primaryStructureVideo.structureType,
              })}
              fullMin={layout.fullMin}
              fullMax={layout.fullMax}
              fullRange={layout.fullRange}
              containerWidth={layout.containerWidth}
              zoomLevel={layout.zoomLevel}
              timelineFrameCount={images.length}
              readOnly={readOnly}
            />
          ) : guidance.isUploadingStructureVideo ? (
            <div
              className="relative h-28 -mt-1 mb-3"
              style={{
                width: layout.zoomLevel > 1 ? `${layout.zoomLevel * 100}%` : '100%',
                minWidth: '100%',
              }}
            >
              <div className="absolute left-4 right-4 top-6 bottom-2 flex items-center justify-center bg-muted/50 dark:bg-muted-foreground/15 border border-border/30 rounded-sm">
                <span className="text-xs text-muted-foreground font-medium">Uploading video...</span>
              </div>
            </div>
          ) : !readOnly ? (
            <GuidanceVideoUploader
              shotId={shotId}
              projectId={projectId ?? ''}
              onVideoUploaded={(videoUrl, metadata) => {
                if (videoUrl && metadata) {
                  guidance.onPrimaryStructureVideoInputChange?.({
                    videoPath: videoUrl,
                    metadata,
                    treatment: guidance.primaryStructureVideo.treatment,
                    motionStrength: guidance.primaryStructureVideo.motionStrength,
                    structureType: guidance.primaryStructureVideo.structureType,
                  });
                }
              }}
              currentVideoUrl={guidance.primaryStructureVideo.path ?? null}
              compact={false}
              zoomLevel={layout.zoomLevel}
              onZoomIn={zoom.onZoomIn}
              onZoomOut={zoom.onZoomOut}
              onZoomReset={zoom.onZoomReset}
              onZoomToStart={zoom.onZoomToStart}
              hasNoImages={layout.hasNoImages}
            />
          ) : null
        )
      )}

      {audio.onAudioChange && audio.audioUrl && (
        <div className="mt-1 mb-2">
          <AudioStrip
            audioUrl={audio.audioUrl}
            audioMetadata={audio.audioMetadata || null}
            onRemove={() => audio.onAudioChange?.(null, null)}
            fullMin={layout.fullMin}
            fullMax={layout.fullMax}
            fullRange={layout.fullRange}
            containerWidth={layout.containerWidth}
            zoomLevel={layout.zoomLevel}
            readOnly={readOnly}
            compact={!!guidance.primaryStructureVideo.path}
            timelineFps={timelineFps}
          />
        </div>
      )}
    </>
  );
};
