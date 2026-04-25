import React from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import { isVideoAny } from '@/shared/lib/typeGuards';
import type {
  AdjacentSegmentsData,
  SegmentSlotModeData,
  TaskDetailsData,
  LightboxNavigationProps,
  LightboxShotWorkflowProps,
  LightboxFeatureFlags,
  LightboxActionHandlers,
  VideoLightboxVideoProps,
} from './types';
import { ImageLightbox } from './ImageLightbox';
import { VideoLightbox } from './VideoLightbox';

interface MediaLightboxCoreProps {
  media?: GenerationRow;
  parentGenerationIdOverride?: string;
  onClose: () => void;
  segmentSlotMode?: SegmentSlotModeData;
  readOnly?: boolean;
  toolTypeOverride?: string;
  onNavigateToGeneration?: (generationId: string) => void;
  onOpenExternalGeneration?: (generationId: string, derivedContext?: string[]) => Promise<void>;
  shotId?: string;
  tasksPaneOpen?: boolean;
  tasksPaneWidth?: number;
  initialVariantId?: string;
  adjacentSegments?: AdjacentSegmentsData;
}

interface MediaLightboxBehaviorProps {
  navigation?: LightboxNavigationProps;
  shotWorkflow?: LightboxShotWorkflowProps;
  features?: LightboxFeatureFlags;
  actions?: LightboxActionHandlers;
  videoProps?: VideoLightboxVideoProps;
  customOverlay?: React.ReactNode;
}

interface MediaLightboxTaskDetailsProps {
  taskDetailsData?: TaskDetailsData;
}

interface MediaLightboxTickStateProps {
  showTickForImageId?: string | null;
  showTickForSecondaryImageId?: string | null;
}

export type MediaLightboxProps =
  & MediaLightboxCoreProps
  & MediaLightboxBehaviorProps
  & MediaLightboxTaskDetailsProps
  & MediaLightboxTickStateProps;

export const MediaLightbox: React.FC<MediaLightboxProps> = (props) => {
  const {
    media,
    segmentSlotMode,
    navigation,
    shotWorkflow,
    features,
    actions,
    videoProps,
  } = props;

  const sharedContainerProps = {
    onClose: props.onClose,
    readOnly: props.readOnly,
    shotId: props.shotId,
    initialVariantId: props.initialVariantId,
    taskDetailsData: props.taskDetailsData,
    onOpenExternalGeneration: props.onOpenExternalGeneration,
    showTickForImageId: props.showTickForImageId,
    showTickForSecondaryImageId: props.showTickForSecondaryImageId,
    tasksPaneOpen: props.tasksPaneOpen,
    tasksPaneWidth: props.tasksPaneWidth,
    adjacentSegments: props.adjacentSegments,
    navigation,
    shotWorkflow,
    features,
    actions,
  };

  if (segmentSlotMode) {
    return (
      <VideoLightbox
        {...sharedContainerProps}
        media={media}
        segmentSlotMode={segmentSlotMode}
        parentGenerationIdOverride={props.parentGenerationIdOverride}
        variantFetchGenerationIdOverride={props.variantFetchGenerationIdOverride}
        videoProps={videoProps}
      />
    );
  }

  if (!media) {
    return null;
  }

  if (isVideoAny(media)) {
    return (
      <VideoLightbox
        {...sharedContainerProps}
        media={media}
        segmentSlotMode={segmentSlotMode}
        parentGenerationIdOverride={props.parentGenerationIdOverride}
        variantFetchGenerationIdOverride={props.variantFetchGenerationIdOverride}
        videoProps={videoProps}
      />
    );
  }

  return (
    <ImageLightbox
      {...sharedContainerProps}
      media={media}
      toolTypeOverride={props.toolTypeOverride}
      onNavigateToGeneration={props.onNavigateToGeneration}
    />
  );
};
