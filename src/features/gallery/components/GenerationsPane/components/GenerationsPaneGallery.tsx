import React from 'react';
import type { Shot } from '@/domains/generation/types';
import { MediaGallery, type GalleryFilterState } from '@/shared/components/MediaGallery';
import { useShots } from '@/shared/contexts/ShotsContext';
import { SelectionContextMenu } from '@/shared/components/SelectionContextMenu';
import { SkeletonGallery } from '@/shared/components/ui/composed/skeleton-gallery';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { VideoGenerationModal } from '@/tools/travel-between-images/components/VideoGenerationModal';
import { useLassoSelection } from '../hooks/useLassoSelection';
import { useModifierKeys } from '../hooks/useModifierKeys';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import { useGallerySelection } from '@/shared/state/selectionStore';

type MediaGalleryProps = React.ComponentProps<typeof MediaGallery>;

interface GenerationsPaneLayoutModel {
  columns: number;
  itemsPerPage: number;
}

interface GenerationsPaneLoadingModel {
  isLoading: boolean;
  expectedItemCount?: number;
}

interface GenerationsPanePageModel {
  page: number;
  totalCount: number;
}

interface GenerationsPaneGalleryModel {
  items: MediaGalleryProps['images'];
  onDelete: NonNullable<MediaGalleryProps['onDelete']>;
  onToggleStar: NonNullable<MediaGalleryProps['onToggleStar']>;
  isDeleting: boolean;
  allShots: NonNullable<MediaGalleryProps['allShots']>;
  lastShotId?: string;
  filters: GalleryFilterState;
  onFiltersChange: (newFilters: GalleryFilterState) => void;
  onAddToShot: NonNullable<MediaGalleryProps['onAddToLastShot']>;
  onAddToShotWithoutPosition: NonNullable<MediaGalleryProps['onAddToLastShotWithoutPosition']>;
  onServerPageChange: NonNullable<
    NonNullable<MediaGalleryProps['pagination']>['onServerPageChange']
  >;
  generationFilters: MediaGalleryProps['generationFilters'];
  currentViewingShotId?: string;
  onCreateShot: NonNullable<MediaGalleryProps['onCreateShot']>;
}

interface GenerationsPaneGalleryProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  projectAspectRatio?: string;
  layout: GenerationsPaneLayoutModel;
  loading: GenerationsPaneLoadingModel;
  pagination: GenerationsPanePageModel;
  error: Error | null;
  gallery: GenerationsPaneGalleryModel;
}

export function GenerationsPaneGallery({
  containerRef,
  projectAspectRatio,
  layout,
  loading,
  pagination,
  error,
  gallery,
}: GenerationsPaneGalleryProps): React.ReactElement {
  useRenderBudget('GenerationsPaneGallery', 5);
  const gallerySurfaceRef = React.useRef<HTMLDivElement | null>(null);
  const [contextMenuPosition, setContextMenuPosition] = React.useState<{ x: number; y: number } | null>(null);
  const [videoModalShot, setVideoModalShot] = React.useState<Shot | null>(null);
  const {
    selectedGalleryIds,
    gallerySelectionMap,
    selectGalleryItem,
    selectGalleryItems,
    clearGallerySelection,
  } = useGallerySelection();
  const { shots } = useShots();
  const { createShot, isCreating } = useShotCreation();
  const { navigateToShot } = useShotNavigation();
  const modifierKeys = useModifierKeys();
  const { selectionRect, handleMouseDown } = useLassoSelection({
    containerRef: gallerySurfaceRef,
    items: gallery.items,
    onSelectItems: selectGalleryItems,
  });

  const buildSelectionMeta = React.useCallback((image: MediaGalleryProps['images'][number]) => ({
    url: image.url,
    type: image.type ?? image.contentType ?? (image.isVideo ? 'video/mp4' : 'image/png'),
    generationId: image.generation_id ?? image.id,
    variantId: image.primary_variant_id,
  }), []);

  const handleImageClick = React.useCallback((image: MediaGalleryProps['images'][number]) => {
    selectGalleryItem(image.id, buildSelectionMeta(image), { toggle: modifierKeys.isMultiSelectModifier });
  }, [buildSelectionMeta, modifierKeys.isMultiSelectModifier, selectGalleryItem]);

  const resolveSelectedGenerationIds = React.useCallback(() => (
    Array.from(gallerySelectionMap.values()).map((entry) => entry.generationId)
  ), [gallerySelectionMap]);

  const selectedGenerationIds = React.useMemo(() => resolveSelectedGenerationIds(), [resolveSelectedGenerationIds]);

  const existingShotsForSelection = React.useMemo(() => {
    if (selectedGenerationIds.length === 0 || !shots?.length) {
      return [] as Shot[];
    }

    return shots.filter((shot) => {
      const shotGenerationIds = new Set(
        (shot.images ?? [])
          .map((image) => image.generation_id)
          .filter((generationId): generationId is string => typeof generationId === 'string' && generationId.length > 0),
      );

      return selectedGenerationIds.every((generationId) => shotGenerationIds.has(generationId));
    });
  }, [selectedGenerationIds, shots]);

  const createShotFromSelection = React.useCallback(async (): Promise<Shot | null> => {
    if (selectedGenerationIds.length === 0) {
      return null;
    }

    const result = await createShot({ generationIds: selectedGenerationIds });
    if (!result?.shotId) {
      return null;
    }

    const createdShot = result.shot ?? shots?.find((shot) => shot.id === result.shotId) ?? null;
    return createdShot;
  }, [createShot, selectedGenerationIds, shots]);

  const handleContextMenu = React.useCallback((
    event: React.MouseEvent,
    image: MediaGalleryProps['images'][number],
  ) => {
    event.preventDefault();
    if (!selectedGalleryIds.has(image.id)) {
      selectGalleryItem(image.id, buildSelectionMeta(image));
    }
    setContextMenuPosition({ x: event.clientX, y: event.clientY });
  }, [buildSelectionMeta, selectGalleryItem, selectedGalleryIds]);

  const handleCreateShotFromMenu = React.useCallback(async (): Promise<Shot | null> => {
    return createShotFromSelection();
  }, [createShotFromSelection]);

  const handleGenerateVideoFromMenu = React.useCallback(async () => {
    const createdShot = await createShotFromSelection();
    if (createdShot) {
      setVideoModalShot(createdShot);
    }
  }, [createShotFromSelection]);

  const handleNavigateToShot = React.useCallback((shot: Shot) => {
    navigateToShot(shot, { isNewlyCreated: true });
  }, [navigateToShot]);

  const handleOpenGenerateVideo = React.useCallback((shot: Shot) => {
    setVideoModalShot(shot);
  }, []);

  return (
    <>
      <div
        ref={containerRef}
        className="flex-grow px-1 sm:px-3 overflow-y-auto overscroll-contain flex flex-col"
        style={{ WebkitOverflowScrolling: 'touch' }}
        data-tour="gallery-section"
      >
        {loading.isLoading && gallery.items.length === 0 && (
          <SkeletonGallery
            count={loading.expectedItemCount ?? layout.itemsPerPage}
            fixedColumns={layout.columns}
            gapClasses="gap-2 sm:gap-4"
            darkSurface
            showControls={false}
            projectAspectRatio={projectAspectRatio}
            className="space-y-0 pb-4 pt-2"
          />
        )}

        {error && <p className="text-red-500 text-center">Error: {error.message}</p>}

        {gallery.items.length > 0 && (
          <div className={loading.isLoading ? 'opacity-60 pointer-events-none transition-opacity duration-200' : ''}>
            <div
              ref={gallerySurfaceRef}
              className="relative"
              onMouseDown={handleMouseDown}
            >
              <MediaGallery
                images={gallery.items}
                onDelete={gallery.onDelete}
                onToggleStar={gallery.onToggleStar}
                isDeleting={gallery.isDeleting}
                allShots={gallery.allShots}
                lastShotId={gallery.lastShotId}
                filters={gallery.filters}
                onFiltersChange={gallery.onFiltersChange}
                columnsPerRow={layout.columns}
                onImageClick={handleImageClick}
                onContextMenu={handleContextMenu}
                onAddToLastShot={gallery.onAddToShot}
                onAddToLastShotWithoutPosition={gallery.onAddToShotWithoutPosition}
                className="space-y-0 pb-8"
                selectedIds={selectedGalleryIds}
                config={{
                  darkSurface: true,
                  reducedSpacing: true,
                  hidePagination: true,
                  hideTopFilters: true,
                  showShare: false,
                  enableSingleClick: true,
                }}
                pagination={{
                  offset: (pagination.page - 1) * layout.itemsPerPage,
                  totalCount: pagination.totalCount,
                  itemsPerPage: layout.itemsPerPage,
                  serverPage: pagination.page,
                  onServerPageChange: gallery.onServerPageChange,
                }}
                generationFilters={gallery.generationFilters}
                currentViewingShotId={gallery.currentViewingShotId}
                onCreateShot={gallery.onCreateShot}
              />
              {selectionRect && (
                <div
                  className="pointer-events-none absolute border border-sky-400 bg-sky-400/10"
                  style={{
                    left: selectionRect.left,
                    top: selectionRect.top,
                    width: selectionRect.width,
                    height: selectionRect.height,
                  }}
                />
              )}
            </div>
          </div>
        )}

        {gallery.items.length === 0 && !loading.isLoading && (
          <div className="flex-1 flex items-center justify-center text-zinc-500">
            No generations found for this project.
          </div>
        )}
      </div>

      <SelectionContextMenu
        position={contextMenuPosition}
        onClose={() => setContextMenuPosition(null)}
        onCreateShot={handleCreateShotFromMenu}
        onGenerateVideo={handleGenerateVideoFromMenu}
        onNavigateToShot={handleNavigateToShot}
        onOpenGenerateVideo={handleOpenGenerateVideo}
        existingShots={existingShotsForSelection}
        isCreating={isCreating}
      />

      {videoModalShot && (
        <>
          {/* VideoGenerationModal only uses app-wide providers, so it can open from gallery selection flow. */}
          <VideoGenerationModal
            isOpen={true}
            onClose={() => setVideoModalShot(null)}
            shot={videoModalShot}
          />
        </>
      )}
    </>
  );
}
