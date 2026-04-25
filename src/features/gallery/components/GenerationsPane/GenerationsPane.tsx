import React from 'react';
import { Sparkles, Images } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { ImageGenerationModal } from '@/shared/components/modals/ImageGenerationModal';
import { DeleteGenerationConfirmDialog } from '@/shared/components/dialogs/DeleteGenerationConfirmDialog';
import { PaneControlTab } from '@/shared/components/PaneControlTab';
import { GenerationsPaneControls } from './components/GenerationsPaneControls';
import { GenerationsPaneGallery } from './components/GenerationsPaneGallery';
import { GenerationsDropChip } from './components/GenerationsDropChip';
import { useGenerationsPaneController } from './hooks/useGenerationsPaneController';
import { UI_Z_LAYERS } from '@/shared/lib/uiLayers';
import { usePanesStore } from '@/shared/state/panesStore';

type GenerationsPaneController = ReturnType<typeof useGenerationsPaneController>;

function GenerationsPaneBackdrop({ controller }: { controller: GenerationsPaneController }) {
  const { pane } = controller;

  if (!pane.showBackdrop) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 touch-none"
      style={{ zIndex: UI_Z_LAYERS.GENERATIONS_PANE_BACKDROP }}
      onTouchStart={(event) => {
        event.preventDefault();
        event.stopPropagation();
        pane.closePane();
      }}
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
        pane.closePane();
      }}
      aria-hidden="true"
    />
  );
}

function GenerationsPaneTab({ controller }: { controller: GenerationsPaneController }) {
  const { pane, navigation, modal } = controller;
  const effectiveGenerationsPaneHeight = usePanesStore((state) => state.effectiveGenerationsPaneHeight);

  if (pane.isOnImageGenerationPage) {
    return null;
  }

  return (
    <PaneControlTab
      position={{
        side: "bottom",
        paneDimension: effectiveGenerationsPaneHeight,
        horizontalOffset:
          (pane.isShotsPaneLocked ? pane.shotsPaneWidth : 0) -
          (pane.isTasksPaneLocked ? pane.tasksPaneWidth : 0),
      }}
      state={{ isLocked: pane.isLocked, isOpen: pane.paneIsOpen }}
      handlers={{
        toggleLock: pane.toggleLock,
        openPane: pane.openPane,
        handlePaneEnter: pane.handlePaneEnter,
        handlePaneLeave: pane.handlePaneLeave,
        customOpenAction: () => modal.setIsGenerationModalOpen(true),
      }}
      display={{
        customIcon: <Sparkles className="h-4 w-4" />,
        paneTooltip: "Generate new image",
        allowMobileLock: true,
        shortcutHint: '⌥S',
      }}
      actions={{
        thirdButton: {
          onClick: navigation.handleNavigateToImageGeneration,
          ariaLabel: 'Go to Image Generation tool',
          tooltip: 'Go to Image Generation tool (⌥⇧S)',
          content: <Images className="h-4 w-4" />,
        },
        fourthButton: {
          onClick: () => modal.setIsGenerationModalOpen(true),
          ariaLabel: 'Generate new image',
          tooltip: 'Generate new image',
          content: <Sparkles className="h-4 w-4" />,
        },
      }}
      dataTour="generations-pane-tab"
      dataTourLock="generations-lock"
      dataTourFourthButton="generations-sparkles"
    />
  );
}

function GenerationsPaneSurface({ controller }: { controller: GenerationsPaneController }) {
  const { pane, filters, gallery, layout } = controller;
  const effectiveGenerationsPaneHeight = usePanesStore((state) => state.effectiveGenerationsPaneHeight);

  return (
    <div
      {...pane.paneProps}
      data-testid="generations-pane"
      style={{
        height: `${effectiveGenerationsPaneHeight}px`,
        left: pane.isShotsPaneLocked ? `${pane.shotsPaneWidth}px` : 0,
        right: pane.isTasksPaneLocked ? `${pane.tasksPaneWidth}px` : 0,
        zIndex: UI_Z_LAYERS.GENERATIONS_PANE,
      }}
      className={cn(
        'fixed bottom-0 bg-zinc-900/95 border-t border-zinc-700 shadow-xl transform transition-all duration-300 ease-smooth flex flex-col pointer-events-auto',
        pane.transformClass,
      )}
    >
      <div
        className={cn(
          'flex flex-col h-full min-h-0',
          pane.isPointerEventsEnabled ? 'pointer-events-auto' : 'pointer-events-none',
        )}
      >
        <GenerationsPaneControls
          filters={{
            shots: filters.shotsForFilter,
            selectedShotFilter: filters.selectedShotFilter,
            onSelectedShotFilterChange: filters.setSelectedShotFilter,
            excludePositioned: filters.excludePositioned,
            onExcludePositionedChange: filters.setExcludePositioned,
            isMobile: layout.isMobile,
            shotFilterContentRef: filters.shotFilterContentRef,
            mediaTypeFilterContentRef: filters.mediaTypeContentRef,
            shotFilterOpen: filters.shotFilterOpen,
            onShotFilterOpenChange: filters.setShotFilterOpen,
            mediaTypeFilter: filters.mediaTypeFilter,
            onMediaTypeFilterChange: filters.setMediaTypeFilter,
            mediaTypeFilterOpen: filters.mediaTypeFilterOpen,
            onMediaTypeFilterOpenChange: filters.setMediaTypeFilterOpen,
            searchTerm: filters.searchTerm,
            onSearchTermChange: filters.setSearchTerm,
            isSearchOpen: filters.isSearchOpen,
            onSearchOpenChange: filters.setIsSearchOpen,
            searchInputRef: filters.searchInputRef,
            starredOnly: filters.starredOnly,
            onStarredOnlyChange: filters.setStarredOnly,
            currentShotId: filters.currentShotId,
            isSpecialFilterSelected: filters.isSpecialFilterSelected,
          }}
          pagination={{
            totalCount: gallery.totalCount,
            perPage: layout.paneLayout.itemsPerPage,
            page: gallery.page,
            onPageChange: gallery.handleServerPageChange,
          }}
          interaction={{ isInteractionDisabled: pane.isInteractionDisabled }}
        />

        <GenerationsPaneGallery
          containerRef={layout.galleryContainerRef}
          projectAspectRatio={layout.projectAspectRatio}
          layout={{
            columns: layout.paneLayout.columns,
            itemsPerPage: layout.paneLayout.itemsPerPage,
          }}
          loading={{
            isLoading: gallery.isLoading,
            expectedItemCount: gallery.expectedItemCount,
          }}
          pagination={{ page: gallery.page, totalCount: gallery.totalCount }}
          error={gallery.error}
          gallery={{
            items: gallery.paginatedData.items,
            onDelete: gallery.handleDeleteGeneration,
            onToggleStar: gallery.handleToggleStar,
            isDeleting: gallery.isDeleting,
            allShots: gallery.shotsData || [],
            lastShotId: gallery.lastAffectedShotId || undefined,
            filters: filters.galleryFilters,
            onFiltersChange: filters.handleGalleryFiltersChange,
            onAddToShot: gallery.handleAddToShot,
            onAddToShotWithoutPosition: gallery.handleAddToShotWithoutPosition,
            onServerPageChange: gallery.handleServerPageChange,
            generationFilters: filters.generationFilters,
            currentViewingShotId: filters.currentShotId || undefined,
            onCreateShot: gallery.handleCreateShot,
          }}
        />
      </div>
    </div>
  );
}

const GenerationsPaneComponent: React.FC = () => {
  const controller = useGenerationsPaneController();

  return (
    <>
      <GenerationsPaneBackdrop controller={controller} />
      <GenerationsDropChip controller={controller} />
      <GenerationsPaneTab controller={controller} />
      <GenerationsPaneSurface controller={controller} />

      <ImageGenerationModal
        isOpen={controller.modal.isGenerationModalOpen}
        onClose={() => controller.modal.setIsGenerationModalOpen(false)}
        initialShotId={controller.filters.currentShotId}
      />

      <DeleteGenerationConfirmDialog {...controller.gallery.confirmDialogProps} />
    </>
  );
};

export const GenerationsPane = React.memo(GenerationsPaneComponent);
