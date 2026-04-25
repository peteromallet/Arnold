import type { ReactNode } from 'react';
import type { GenerationRow, Shot, ShotOption } from '@/domains/generation/types';
import type {
  TaskDetailsData,
} from '@/shared/lib/taskDetails/taskDetailsContract';
import type { StructureVideoConfigWithMetadata } from '@/shared/lib/tasks/travelBetweenImages';
import type { TravelGuidanceMode } from '@/shared/lib/tasks/travelGuidance';
import type { AsyncImageDeleteHandler } from '@/shared/types/imageHandlers';
import type { SelectedModel } from '@/tools/travel-between-images/settings';

export type { ShotOption };
export type { TaskDetailsData };
export type LightboxDeleteHandler = AsyncImageDeleteHandler;

// ============================================================================
// Props Sub-Interfaces (grouped by concern, shared by ImageLightbox & VideoLightbox)
// ============================================================================

/** Shot workflow: shot selection, positioning, and optimistic state */
export interface LightboxShotWorkflowProps {
  allShots?: ShotOption[];
  selectedShotId?: string;
  onShotChange?: (shotId: string) => void;
  onAddToShot?: (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string) => Promise<boolean>;
  onAddToShotWithoutPosition?: (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string) => Promise<boolean>;
  onCreateShot?: (shotName: string, files: File[]) => Promise<{shotId?: string; shotName?: string} | void>;
  onNavigateToShot?: (shot: Shot, options?: { isNewlyCreated?: boolean }) => void;
  onShowTick?: (imageId: string) => void;
  onShowSecondaryTick?: (imageId: string) => void;
  onOptimisticPositioned?: (mediaId: string, shotId: string) => void;
  onOptimisticUnpositioned?: (mediaId: string, shotId: string) => void;
  optimisticPositionedIds?: Set<string>;
  optimisticUnpositionedIds?: Set<string>;
  positionedInSelectedShot?: boolean;
  associatedWithoutPositionInSelectedShot?: boolean;
}

/** Gallery navigation: next/prev and indicators */
export interface LightboxNavigationProps {
  onNext?: () => void;
  onPrevious?: () => void;
  showNavigation?: boolean;
  hasNext?: boolean;
  hasPrevious?: boolean;
}

/** Feature toggles: which UI elements to show */
export interface LightboxFeatureFlags {
  showImageEditTools?: boolean;
  showDownload?: boolean;
  showMagicEdit?: boolean;
  initialEditActive?: boolean;
  showTaskDetails?: boolean;
}

/** Action handlers: delete, star, apply settings */
export interface LightboxActionHandlers {
  onDelete?: LightboxDeleteHandler;
  isDeleting?: string | null;
  onApplySettings?: (metadata: GenerationRow['metadata']) => void;
  onToggleStar?: (id: string, starred: boolean) => void;
  starred?: boolean;
  onAddToVideoEditor?: () => void;
}

/**
 * Information about an adjacent segment (video) for navigation.
 * Used to show "jump to video" buttons when viewing an image in the lightbox.
 */
interface AdjacentSegmentInfo {
  /** Pair index to navigate to */
  pairIndex: number;
  /** Whether this segment has a generated video */
  hasVideo: boolean;
  /** Start image URL (thumbnail preferred) */
  startImageUrl?: string;
  /** End image URL (thumbnail preferred) */
  endImageUrl?: string;
}

/**
 * Adjacent segments data for the current image.
 * - prev: The segment that ENDS with this image (before this image in timeline)
 * - next: The segment that STARTS with this image (after this image in timeline)
 */
export interface AdjacentSegmentsData {
  prev?: AdjacentSegmentInfo;
  next?: AdjacentSegmentInfo;
  /** Callback to navigate to a segment by pair index */
  onNavigateToSegment: (pairIndex: number) => void;
}

export interface QuickCreateSuccess {
  isSuccessful: boolean;
  shotId: string | null;
  shotName: string | null;
  isLoading?: boolean; // True when shot is created but still syncing/loading
}


/**
 * Unified segment slot data for MediaLightbox segment editor mode.
 * Combines pair data (images on timeline) with optional segment video.
 */
export interface SegmentSlotModeData {
  /** Current pair index (0-based) */
  currentIndex: number;
  /** Total number of pairs */
  totalPairs: number;

  /** Pair data from the timeline */
  pairData: {
    index: number;
    frames: number;
    startFrame: number;
    endFrame: number;
    startImage: {
      id: string;           // shot_generation.id
      generationId?: string; // generation_id
      primaryVariantId?: string; // generation_variants.id of primary variant
      url?: string;
      thumbUrl?: string;
      position: number;
    } | null;
    endImage: {
      id: string;
      generationId?: string;
      primaryVariantId?: string;
      url?: string;
      thumbUrl?: string;
      position: number;
    } | null;
  };

  /** The video generation if this slot has one, null otherwise */
  segmentVideo: GenerationRow | null;
  /** Active child generation ID (for creating variants on correct child) */
  activeChildGenerationId?: string;

  /** Navigation callback - called with new pair index */
  onNavigateToPair: (index: number) => void;

  /** Project/shot context */
  projectId: string | null;
  shotId: string;
  /** Parent generation ID (for regeneration task linking) */
  parentGenerationId?: string;

  /** Prompts for this pair */
  pairPrompt?: string;
  pairNegativePrompt?: string;
  defaultPrompt?: string;
  defaultNegativePrompt?: string;
  enhancedPrompt?: string;

  /** Project resolution for output */
  projectResolution?: string;

  /** Structure video config for this segment (if applicable) */
  structureVideoType?: TravelGuidanceMode | null;
  structureVideoDefaults?: {
    mode?: TravelGuidanceMode;
    motionStrength: number;
    treatment: 'adjust' | 'clip';
    uni3cEndPercent: number;
    cannyIntensity?: number;
    depthContrast?: number;
  };
  structureVideoDefaultsByModel?: Partial<Record<SelectedModel, {
    mode?: TravelGuidanceMode;
    motionStrength: number;
    treatment: 'adjust' | 'clip';
    uni3cEndPercent: number;
    cannyIntensity?: number;
    depthContrast?: number;
  }>>;
  structureVideoUrl?: string;
  structureVideoFrameRange?: {
    segmentStart: number;
    segmentEnd: number;
    videoTotalFrames: number;
    videoFps: number;
    /** Video's output start position on timeline (for "fit to range" calculation) */
    videoOutputStart?: number;
    /** Video's output end position on timeline (for "fit to range" calculation) */
    videoOutputEnd?: number;
  };

  /** Callback when frame count changes - for instant timeline updates */
  onFrameCountChange?: (pairShotGenerationId: string, frameCount: number) => void;
  /** Callback when generate is initiated (for optimistic UI updates) */
  onGenerateStarted?: (pairShotGenerationId: string | null | undefined) => void;
  /** Maximum frames allowed (77 with smooth continuations, 81 otherwise) */
  maxFrameLimit?: number;

  // Per-segment structure video management (Timeline Mode only)
  /** Whether in timeline mode (shows structure video upload) vs batch mode (preview only) */
  isTimelineMode?: boolean;
  /** All existing structure videos (for overlap detection) */
  existingStructureVideos?: StructureVideoConfigWithMetadata[];
  /** Callback to add a structure video for this segment (handles overlap resolution) */
  onAddSegmentStructureVideo?: (video: StructureVideoConfigWithMetadata) => void;
  /** Callback to update this segment's structure video */
  onUpdateSegmentStructureVideo?: (updates: Partial<StructureVideoConfigWithMetadata>) => void;
  /** Callback to remove this segment's structure video */
  onRemoveSegmentStructureVideo?: () => void;

  /** Callback to navigate to a constituent image by shot_generation.id */
  onNavigateToImage?: (shotGenerationId: string) => void;

  /** Adjacent video thumbnails for preview sequence pill (video lightbox only) */
  adjacentVideoThumbnails?: {
    prev?: { thumbUrl: string; pairIndex: number };
    current?: { thumbUrl: string; pairIndex: number };
    next?: { thumbUrl: string; pairIndex: number };
  };
  /** Callback to open the preview-together dialog starting at a given pair index */
  onOpenPreviewDialog?: (startAtPairIndex: number) => void;
}

/** Video-specific props that don't fit into shared groups */
export interface VideoLightboxVideoProps {
  initialVideoTrimMode?: boolean;
  fetchVariantsForSelf?: boolean;
  currentSegmentImages?: {
    startUrl?: string;
    endUrl?: string;
    startGenerationId?: string;
    endGenerationId?: string;
    startShotGenerationId?: string;
    endShotGenerationId?: string;
    activeChildGenerationId?: string;
    startVariantId?: string;
    endVariantId?: string;
  };
  onSegmentFrameCountChange?: (pairShotGenerationId: string, frameCount: number) => void;
  currentFrameCount?: number;
  onTrimModeChange?: (isTrimMode: boolean) => void;
  onShowTaskDetails?: () => void;
}

export interface VideoLightboxProps {
  media?: GenerationRow;
  parentGenerationIdOverride?: string;
  variantFetchGenerationIdOverride?: string;
  onClose: () => void;
  segmentSlotMode?: SegmentSlotModeData;
  readOnly?: boolean;
  shotId?: string;
  initialVariantId?: string;
  taskDetailsData?: TaskDetailsData;
  onOpenExternalGeneration?: (generationId: string, derivedContext?: string[]) => Promise<void>;
  showTickForImageId?: string | null;
  showTickForSecondaryImageId?: string | null;
  tasksPaneOpen?: boolean;
  tasksPaneWidth?: number;
  adjacentSegments?: AdjacentSegmentsData;
  navigation?: LightboxNavigationProps;
  shotWorkflow?: LightboxShotWorkflowProps;
  features?: LightboxFeatureFlags;
  actions?: LightboxActionHandlers;
  videoProps?: VideoLightboxVideoProps;
  customOverlay?: ReactNode;
}

export type VideoLightboxPropsWithMedia = VideoLightboxProps & {
  media: GenerationRow;
};
