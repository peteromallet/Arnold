import type {
  GeneratedImageWithMetadata,
  DisplayableMetadata,
  SimplifiedShotOption,
} from "../MediaGallery/types";
import type { AddToShotHandler } from '@/shared/types/imageHandlers';
import type { MouseEvent } from 'react';

// ── Shot workflow: selector state, optimistic IDs, adding-to-shot state ──

/** Shot selector state, optimistic position tracking, and add-to-shot loading state */
export interface ItemShotWorkflow {
  selectedShotIdLocal: string;
  simplifiedShotOptions: SimplifiedShotOption[];
  setSelectedShotIdLocal: (id: string) => void;
  setLastAffectedShotId: (id: string) => void;

  /** Tick feedback after adding to shot */
  showTickForImageId: string | null;
  onShowTick: (imageId: string) => void;
  showTickForSecondaryImageId?: string | null;
  onShowSecondaryTick?: (imageId: string) => void;

  /** Optimistic position tracking */
  optimisticUnpositionedIds?: Set<string>;
  optimisticPositionedIds?: Set<string>;
  optimisticDeletedIds?: Set<string>;
  onOptimisticUnpositioned?: (imageId: string, shotId: string) => void;
  onOptimisticPositioned?: (imageId: string, shotId: string) => void;

  /** Which image is currently being added to a shot (loading indicator) */
  addingToShotImageId: string | null;
  setAddingToShotImageId: (id: string | null) => void;
  addingToShotWithoutPositionImageId?: string | null;
  setAddingToShotWithoutPositionImageId?: (id: string | null) => void;

  /** ID of the shot currently being viewed (hides navigation buttons) */
  currentViewingShotId?: string;

  /** Shot creation callback */
  onCreateShot?: (shotName: string, files: File[]) => Promise<void>;

  /** Handlers for adding image to shot */
  onAddToLastShot?: AddToShotHandler;
  onAddToLastShotWithoutPosition?: AddToShotHandler;
}

// ── Mobile interaction state ──

/** Mobile-specific interaction state and handlers */
export interface ItemMobileInteraction {
  isMobile: boolean;
  mobileActiveImageId: string | null;
  mobilePopoverOpenImageId: string | null;
  onMobileTap: (image: GeneratedImageWithMetadata) => void;
  setMobilePopoverOpenImageId: (id: string | null) => void;
}

// ── Feature flags: what buttons/features to show ──

/** Boolean feature flags controlling which UI elements are visible */
export interface ItemFeatures {
  showShare?: boolean;
  showDelete?: boolean;
  showDownload?: boolean;
  showEdit?: boolean;
  showStar?: boolean;
  showAddToShot?: boolean;
  enableSingleClick?: boolean;
  /** When true, videos are rendered as static thumbnail images instead of HoverScrubVideo for better performance */
  videosAsThumbnails?: boolean;
}

// ── Action callbacks ──

/** Core action callbacks for the gallery item */
export interface ItemActions {
  onOpenLightbox: (image: GeneratedImageWithMetadata, autoEnterEditMode?: boolean) => void;
  onDelete?: (id: string) => void;
  onApplySettings?: (metadata: DisplayableMetadata) => void;
  onDownloadImage: (rawUrl: string, filename: string, imageId?: string, isVideo?: boolean, originalContentType?: string) => void;
  onToggleStar?: (id: string, starred: boolean) => void;
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onContextMenu?: (event: MouseEvent, image: GeneratedImageWithMetadata) => void;
  /** Callback when the image has fully loaded and is visible */
  onImageLoaded?: (imageId: string) => void;
}

// ── Loading / progressive state ──

/** Progressive loading and gallery loading state */
export interface ItemLoading {
  shouldLoad?: boolean;
  isPriority?: boolean;
  isGalleryLoading?: boolean;
  isDeleting?: string | boolean | null;
  downloadingImageId: string | null;
}

// ── Top-level props ──

export interface MediaGalleryItemProps {
  /** The media item to render */
  image: GeneratedImageWithMetadata;
  /** Index within the current page */
  index: number;

  /** Shot workflow: selector, optimistic IDs, add-to-shot state */
  shotWorkflow: ItemShotWorkflow;
  /** Mobile interaction state and handlers */
  mobileInteraction: ItemMobileInteraction;
  /** Feature flags controlling visible UI elements */
  features: ItemFeatures;
  /** Core action callbacks */
  actions: ItemActions;
  /** Loading and progress state */
  loading: ItemLoading;
  /** Whether this item is part of the current selection set */
  isSelected?: boolean;
  /** Selected gallery items available for multi-drag gestures */
  selectedItems?: GeneratedImageWithMetadata[];

  /** Project aspect ratio for sizing */
  projectAspectRatio?: string;
  /** Optional data-tour attribute for product tour targeting */
  dataTour?: string;
}

// Re-export types that are used by sub-components
export type { GeneratedImageWithMetadata, DisplayableMetadata } from "../MediaGallery/types";
