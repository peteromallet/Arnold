import type { Shot } from "@/domains/generation/types";
import type { GalleryFilterState } from '@/shared/contracts/galleryFilters';
import type { AddToShotHandler } from '@/shared/types/imageHandlers';
import type { AsyncImageDeleteHandler } from '@/shared/types/imageHandlers';
import type { DisplayableMetadata } from '@/shared/types/displayableMetadata';
import type { MouseEvent } from 'react';

export type { DisplayableMetadata } from '@/shared/types/displayableMetadata';
export type { GalleryFilterState } from '@/shared/contracts/galleryFilters';
export { DEFAULT_GALLERY_FILTERS } from '@/shared/contracts/galleryFilters';

/**
 * Columns per row can be:
 * - 'auto': Calculate dynamically based on aspect ratio
 * - number: Fixed number of columns
 */
type ColumnsPerRow = 'auto' | number;

export interface GeneratedImageWithMetadata {
  id: string;
  /**
   * Canonical generation identity when `id` is a shot-entry ID.
   * Prefer this in cross-shot and task lookup flows.
   */
  generation_id?: string;
  /** Shot entry identity for shot_generations rows. */
  shot_generation_id?: string;
  /** Alias used by some optimistic cache paths; kept for compatibility. */
  shotImageEntryId?: string;
  url: string | null;
  location?: string | null;
  thumbUrl?: string | null;
  /** Stable URL identity (URL without query params) for caching/comparison - tokens change but file doesn't */
  urlIdentity?: string;
  /** Stable thumbnail URL identity for caching/comparison */
  thumbUrlIdentity?: string;
  prompt?: string;
  seed?: number;
  metadata?: DisplayableMetadata;
  temp_local_path?: string;
  error?: string;
  file?: File;
  isVideo?: boolean;
  type?: string;
  contentType?: string; // MIME type for proper download file extensions (e.g., 'video/mp4', 'image/png')
  unsaved?: boolean;
  createdAt?: string;
  updatedAt?: string | null;
  starred?: boolean;
  shot_id?: string;
  position?: number | null;
  timeline_frame?: number | null;
  name?: string; // Variant name for the generation
  primary_variant_id?: string | null;
  storage_mode?: 'remote' | 'local' | 'uploading' | null;
  local_handle_id?: string | null;
  local_file_name?: string | null;
  local_file_size?: number | null;
  local_file_mime?: string | null;
  all_shot_associations?: Array<{ shot_id: string; position: number | null; timeline_frame?: number | null }>;
  based_on?: string | null; // ID of source generation for lineage tracking (magic edits, variations)
  derivedCount?: number; // Number of generations based on this one
  hasUnviewedVariants?: boolean; // Whether any variants have viewed_at === null (for NEW badge)
  unviewedVariantCount?: number; // Count of unviewed variants for tooltip
  // Parent/child relationship fields (for travel-between-images segments)
  is_child?: boolean;
  parent_generation_id?: string;
  child_order?: number;
}

/**
 * Canonical shot option shape used by gallery selectors and shot-jump actions.
 * Keep this surface stable so gallery/item workflows do not drift.
 */
export interface SimplifiedShotOption {
  id: string;
  name: string;
  settings?: unknown;
  created_at?: string | null;
}

/** Minimal shot navigation contract shared by gallery handlers. */
export interface NavigableShot {
  id: string;
  name?: string;
}

/**
 * Boolean config flags for MediaGallery appearance and behavior.
 * Group these into a single `config` prop to reduce top-level prop count.
 * All fields are optional — defaults are applied via `DEFAULT_GALLERY_CONFIG`.
 */
export interface GalleryConfig {
  // Visibility flags — which action buttons to show on gallery items
  showDelete: boolean;
  showDownload: boolean;
  showShare: boolean;
  showEdit: boolean;
  showStar: boolean;
  showAddToShot: boolean;

  // UI mode flags
  /** When true, single click selects (instead of opening lightbox) */
  enableSingleClick: boolean;
  /** When true, videos render as static thumbnails instead of hover-scrub */
  videosAsThumbnails: boolean;
  /** Dark surface mode - use when component is on a permanently dark surface (e.g., GenerationsPane) */
  darkSurface: boolean;
  /** Reduced spacing between gallery elements */
  reducedSpacing: boolean;
  /** Show shot filter dropdown in header */
  showShotFilter: boolean;
  /** Show search input in header */
  showSearch: boolean;

  // Hide flags — which sections to suppress
  hidePagination: boolean;
  hideTopFilters: boolean;
  hideMediaTypeFilter: boolean;
  hideBottomPagination: boolean;
  hideShotNotifier: boolean;
}

export const DEFAULT_GALLERY_CONFIG: GalleryConfig = {
  showDelete: true,
  showDownload: true,
  showShare: true,
  showEdit: false,
  showStar: true,
  showAddToShot: true,
  enableSingleClick: false,
  videosAsThumbnails: false,
  darkSurface: false,
  reducedSpacing: false,
  showShotFilter: false,
  showSearch: false,
  hidePagination: false,
  hideTopFilters: false,
  hideMediaTypeFilter: false,
  hideBottomPagination: false,
  hideShotNotifier: false,
};

interface MediaGalleryDataProps {
  images: GeneratedImageWithMetadata[];
  allShots: Shot[];
  currentToolType?: string;
  currentToolTypeName?: string;
  currentViewingShotId?: string;
  lastShotId?: string;
  lastShotNameForTooltip?: string;
  isDeleting?: string | boolean | null;
}

interface MediaGalleryActionsProps {
  onDelete?: AsyncImageDeleteHandler;
  onApplySettings?: (metadata: DisplayableMetadata | undefined) => void;
  onAddToLastShot?: AddToShotHandler;
  onAddToLastShotWithoutPosition?: AddToShotHandler;
  onToggleStar?: (id: string, starred: boolean) => void;
  onCreateShot?: (shotName: string, files: File[]) => Promise<void>;
  /** Called after delete to trigger data refetch. Should invalidate queries and refetch current page. */
  onBackfillRequest?: () => Promise<void>;
  onImageClick?: (image: GeneratedImageWithMetadata, modifiers?: { multiSelect: boolean }) => void;
  onContextMenu?: (event: MouseEvent, image: GeneratedImageWithMetadata) => void;
  formAssociatedShotId?: string | null;
  onSwitchToAssociatedShot?: (shotId: string) => void;
}

interface MediaGalleryPagingProps {
  offset?: number;
  totalCount?: number;
  itemsPerPage?: number;
  onServerPageChange?: (page: number, fromBottom?: boolean) => void;
  serverPage?: number;
  enableAdjacentPagePreloading?: boolean;
}

interface MediaGalleryPaginationConfigProps {
  pagination?: MediaGalleryPagingProps;
}

interface MediaGalleryFilterProps {
  initialFilterState?: boolean;
  /** Controlled filter state — parent owns the values */
  filters?: GalleryFilterState;
  /** Callback when any filter changes (controlled mode) */
  onFiltersChange?: (filters: GalleryFilterState) => void;
  /** Default filter overrides for uncontrolled mode */
  defaultFilters?: Partial<GalleryFilterState>;
  /** Filters for generation queries - enables automatic preloading */
  generationFilters?: Record<string, unknown>;
}

interface MediaGalleryDisplayProps {
  /**
   * Number of columns per row.
   * - 'auto': Calculate dynamically based on project aspect ratio (default)
   * - number: Fixed number of columns
   */
  columnsPerRow?: ColumnsPerRow;
  /** Additional className to apply to the gallery wrapper (can override default spacing) */
  className?: string;
  /** Selection state owned by a parent wrapper such as the editor generations pane. */
  selectedIds?: ReadonlySet<string>;
  /**
   * Boolean config flags controlling gallery appearance and behavior.
   * All fields optional — unset fields use defaults from DEFAULT_GALLERY_CONFIG.
   */
  config?: Partial<GalleryConfig>;
}

export type MediaGalleryProps = MediaGalleryDataProps &
  MediaGalleryActionsProps &
  MediaGalleryPaginationConfigProps &
  MediaGalleryFilterProps &
  MediaGalleryDisplayProps;
