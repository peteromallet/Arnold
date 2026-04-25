import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GenerationsPane } from './GenerationsPane';

const paneControlTabMock = vi.fn();
const useIsDraggingFilesMock = vi.fn();
const setDraggingMock = vi.fn();
const dropToGenerationMock = vi.fn();
const panesState = vi.hoisted(() => ({
  effectiveGenerationsPaneHeight: 180,
}));
const useGenerationsPaneControllerMock = vi.fn();

vi.mock('@/shared/components/PaneControlTab', () => ({
  PaneControlTab: (props: unknown) => {
    paneControlTabMock(props);
    return <div data-testid="pane-control-tab" />;
  },
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: typeof panesState) => unknown) => selector(panesState),
}));

vi.mock('@/shared/state/dragOverlayStore', () => ({
  useIsDraggingFiles: () => useIsDraggingFilesMock(),
  setDragging: (value: boolean) => setDraggingMock(value),
}));

vi.mock('@/features/gallery/hooks/useDropToGeneration', () => ({
  useDropToGeneration: () => dropToGenerationMock,
}));

vi.mock('./hooks/useGenerationsPaneController', () => ({
  useGenerationsPaneController: () => useGenerationsPaneControllerMock(),
}));

vi.mock('./components/GenerationsPaneControls', () => ({
  GenerationsPaneControls: () => <div data-testid="generations-controls" />,
}));

vi.mock('./components/GenerationsPaneGallery', () => ({
  GenerationsPaneGallery: () => <div data-testid="generations-gallery" />,
}));

vi.mock('@/shared/components/modals/ImageGenerationModal', () => ({
  ImageGenerationModal: () => null,
}));

vi.mock('@/shared/components/dialogs/DeleteGenerationConfirmDialog', () => ({
  DeleteGenerationConfirmDialog: () => null,
}));

function buildController() {
  return {
    pane: {
      isOnImageGenerationPage: false,
      generationsPaneHeight: 350,
      isShotsPaneLocked: false,
      shotsPaneWidth: 280,
      isTasksPaneLocked: false,
      tasksPaneWidth: 280,
      isLocked: true,
      paneIsOpen: true,
      paneProps: {},
      transformClass: 'translate-y-0',
      toggleLock: vi.fn(),
      openPane: vi.fn(),
      handlePaneEnter: vi.fn(),
      handlePaneLeave: vi.fn(),
      showBackdrop: false,
      closePane: vi.fn(),
      isPointerEventsEnabled: true,
      isInteractionDisabled: false,
    },
    navigation: {
      handleNavigateToImageGeneration: vi.fn(),
    },
    modal: {
      isGenerationModalOpen: false,
      setIsGenerationModalOpen: vi.fn(),
    },
    filters: {
      shotsForFilter: [],
      selectedShotFilter: 'all',
      setSelectedShotFilter: vi.fn(),
      excludePositioned: false,
      setExcludePositioned: vi.fn(),
      shotFilterContentRef: { current: null },
      mediaTypeContentRef: { current: null },
      shotFilterOpen: false,
      setShotFilterOpen: vi.fn(),
      mediaTypeFilter: 'all',
      setMediaTypeFilter: vi.fn(),
      mediaTypeFilterOpen: false,
      setMediaTypeFilterOpen: vi.fn(),
      searchTerm: '',
      setSearchTerm: vi.fn(),
      isSearchOpen: false,
      setIsSearchOpen: vi.fn(),
      searchInputRef: { current: null },
      starredOnly: false,
      setStarredOnly: vi.fn(),
      currentShotId: null,
      isSpecialFilterSelected: false,
      galleryFilters: {
        status: 'all',
      },
      handleGalleryFiltersChange: vi.fn(),
      generationFilters: undefined,
    },
    gallery: {
      totalCount: 0,
      page: 1,
      handleServerPageChange: vi.fn(),
      isLoading: false,
      expectedItemCount: 0,
      error: null,
      paginatedData: {
        items: [],
      },
      handleDeleteGeneration: vi.fn(),
      handleToggleStar: vi.fn(),
      isDeleting: false,
      shotsData: [],
      lastAffectedShotId: null,
      handleAddToShot: vi.fn(),
      handleAddToShotWithoutPosition: vi.fn(),
      handleCreateShot: vi.fn(),
      confirmDialogProps: {},
    },
    layout: {
      isMobile: false,
      paneLayout: {
        columns: 4,
        itemsPerPage: 20,
      },
      galleryContainerRef: { current: null },
      projectAspectRatio: '1:1',
    },
  };
}

describe('GenerationsPane', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    panesState.effectiveGenerationsPaneHeight = 180;
    useIsDraggingFilesMock.mockReturnValue(false);
    dropToGenerationMock.mockResolvedValue(undefined);
    useGenerationsPaneControllerMock.mockReturnValue(buildController());
  });

  it('uses the effective generations height for the tab position and pane surface', () => {
    render(<GenerationsPane />);

    expect(paneControlTabMock.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        position: expect.objectContaining({
          paneDimension: 180,
        }),
      }),
    );
    expect(screen.getByTestId('generations-pane')).toHaveStyle({ height: '180px' });
  });

  it('keeps the inner flex wrapper shrinkable for gallery scrolling', () => {
    render(<GenerationsPane />);

    expect(screen.getByTestId('generations-pane').firstElementChild).toHaveClass('min-h-0');
  });

  it('renders the drop chip above the pane tab with the same horizontal offset math while dragging files', () => {
    useIsDraggingFilesMock.mockReturnValue(true);
    useGenerationsPaneControllerMock.mockReturnValue(buildController());

    render(<GenerationsPane />);

    const chip = screen.getByTestId('generations-drop-chip');
    expect(chip).toHaveStyle({
      zIndex: `${100014}`,
      transform: 'translateX(-50%) translateX(0px) translateY(-136px) translateY(-56px)',
    });
  });

  it('suppresses the drop chip on the image generation page', () => {
    useIsDraggingFilesMock.mockReturnValue(true);
    const controller = buildController();
    controller.pane.isOnImageGenerationPage = true;
    useGenerationsPaneControllerMock.mockReturnValue(controller);

    render(<GenerationsPane />);

    expect(screen.queryByTestId('generations-drop-chip')).not.toBeInTheDocument();
  });

  it('routes dropped files through the generation drop hook and clears the drag overlay', async () => {
    useIsDraggingFilesMock.mockReturnValue(true);
    render(<GenerationsPane />);

    const chip = screen.getByTestId('generations-drop-chip');
    const file = new File(['image'], 'example.png', { type: 'image/png' });
    fireEvent.drop(chip, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(setDraggingMock).toHaveBeenCalledWith(false);
    expect(dropToGenerationMock).toHaveBeenCalledWith([file]);
  });
});
