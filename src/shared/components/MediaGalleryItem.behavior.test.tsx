import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MediaGalleryItem } from './MediaGalleryItem';

const mocks = vi.hoisted(() => ({
  prefetchTaskData: vi.fn(),
  navigateToShot: vi.fn(),
  setLastAffectedShotId: vi.fn(),
  handleQuickCreateAndAdd: vi.fn(),
  handleVisitCreatedShot: vi.fn(),
  handleShare: vi.fn(),
  markAllViewed: vi.fn(),
  hasLoadedImage: vi.fn(() => false),
  setImageLoadStatus: vi.fn(),
  getGenerationId: vi.fn((image: { id?: string }) => image.id ?? null),
  setGenerationDragData: vi.fn(),
  setMultiGenerationDragData: vi.fn(),
  createDragPreview: vi.fn(),
}));

vi.mock('@/shared/components/DraggableImage', () => ({
  DraggableImage: ({ children }: { children: React.ReactNode }) => <div data-testid="draggable">{children}</div>,
}));

vi.mock('@/shared/components/selectors/ShotSelector', () => ({
  ShotSelector: ({ value }: { value: string }) => <div data-testid="shot-selector">{value}</div>,
}));

vi.mock('@/shared/hooks/ui-image/useProgressiveImage', () => ({
  useProgressiveImage: () => ({
    src: null,
    isThumbShowing: false,
    isFullLoaded: true,
    ref: { current: null },
  }),
}));

vi.mock('@/shared/settings/progressiveLoading', () => ({
  isProgressiveLoadingEnabled: () => false,
}));

vi.mock('@/shared/hooks/tasks/useTaskPrefetch', () => ({
  usePrefetchTaskData: () => mocks.prefetchTaskData,
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1' }),
  useProject: () => ({ updateProject: vi.fn() }),
  useProjectCrudContext: () => ({ updateProject: vi.fn() }),
}));

vi.mock('@/shared/hooks/shots/useShotNavigation', () => ({
  useShotNavigation: () => ({ navigateToShot: mocks.navigateToShot }),
}));

vi.mock('@/shared/hooks/shots/useLastAffectedShot', () => ({
  useLastAffectedShot: () => ({ setLastAffectedShotId: mocks.setLastAffectedShotId }),
}));

vi.mock('@/shared/hooks/useQuickShotCreate', () => ({
  useQuickShotCreate: () => ({
    quickCreateSuccess: false,
    handleQuickCreateAndAdd: mocks.handleQuickCreateAndAdd,
    handleVisitCreatedShot: mocks.handleVisitCreatedShot,
  }),
}));

vi.mock('@/domains/generation/hooks/tasks/useGenerationTaskMapping', () => ({
  useGenerationTaskMapping: () => ({ data: null }),
}));

vi.mock('@/shared/hooks/tasks/useTasks', () => ({
  useGetTask: () => ({ data: null }),
}));

vi.mock('@/shared/hooks/tasks/useTaskType', () => ({
  useTaskType: () => ({ data: null }),
}));

vi.mock('@/shared/hooks/useShareGeneration', () => ({
  useShareGeneration: () => ({
    handleShare: mocks.handleShare,
    isCreatingShare: false,
    shareCopied: false,
    shareSlug: null,
  }),
}));

vi.mock('@/shared/hooks/variants/useMarkVariantViewed', () => ({
  useMarkVariantViewed: () => ({ markAllViewed: mocks.markAllViewed }),
}));

vi.mock('@/shared/lib/preloading', () => ({
  hasLoadedImage: (...args: unknown[]) => mocks.hasLoadedImage(...args),
  setImageLoadStatus: (...args: unknown[]) => mocks.setImageLoadStatus(...args),
}));

vi.mock('@/shared/lib/media/mediaTypeHelpers', () => ({
  getGenerationId: (...args: unknown[]) => mocks.getGenerationId(...args),
  getMediaUrl: (image: { url?: string }) => image.url ?? null,
  getThumbnailUrl: (image: { thumbUrl?: string; url?: string }) => image.thumbUrl ?? image.url ?? null,
}));

vi.mock('@/shared/lib/dnd/dragDrop', () => ({
  setGenerationDragData: (...args: unknown[]) => mocks.setGenerationDragData(...args),
  setMultiGenerationDragData: (...args: unknown[]) => mocks.setMultiGenerationDragData(...args),
  createDragPreview: (...args: unknown[]) => mocks.createDragPreview(...args),
}));

vi.mock('@/domains/generation/components/GenerationDetails', () => ({
  GenerationDetails: () => <div>generation-details</div>,
}));

vi.mock('@/domains/generation/components/GenerationDetails/ImageGenerationDetails', () => ({
  ImageGenerationDetails: () => <div>image-generation-details</div>,
}));

vi.mock('lucide-react', async () => {
  const actual = await vi.importActual<typeof import('lucide-react')>('lucide-react');
  return {
    ...actual,
    Share2: () => <svg data-testid="share-icon" />,
    Copy: () => <svg data-testid="copy-icon" />,
    Check: () => <svg data-testid="check-icon" />,
    PlusCircle: () => <svg data-testid="plus-circle-icon" />,
    Eye: () => <svg data-testid="eye-icon" />,
  };
});

function buildProps(overrides: Record<string, unknown> = {}) {
  const image = {
    id: 'img-1',
    url: 'https://cdn/image.png',
    thumbUrl: 'https://cdn/thumb.png',
    prompt: 'Sunset over water',
    metadata: { taskId: 'task-1' },
    createdAt: '2026-01-01T00:00:00.000Z',
    ...((overrides.image as object | undefined) ?? {}),
  };

  return {
    image,
    index: 0,
    shotWorkflow: {
      selectedShotIdLocal: 'shot-1',
      simplifiedShotOptions: [{ id: 'shot-1', name: 'Shot 1' }],
      setSelectedShotIdLocal: vi.fn(),
      setLastAffectedShotId: vi.fn(),
      showTickForImageId: null,
      onShowTick: vi.fn(),
      onShowSecondaryTick: vi.fn(),
      optimisticUnpositionedIds: new Set<string>(),
      optimisticPositionedIds: new Set<string>(),
      onOptimisticUnpositioned: vi.fn(),
      onOptimisticPositioned: vi.fn(),
      addingToShotImageId: null,
      setAddingToShotImageId: vi.fn(),
      addingToShotWithoutPositionImageId: null,
      setAddingToShotWithoutPositionImageId: vi.fn(),
      currentViewingShotId: 'other-shot',
      onCreateShot: vi.fn(),
      onAddToLastShot: vi.fn(async () => true),
      onAddToLastShotWithoutPosition: vi.fn(async () => true),
      ...((overrides.shotWorkflow as object | undefined) ?? {}),
    },
    mobileInteraction: {
      isMobile: false,
      mobileActiveImageId: null,
      mobilePopoverOpenImageId: null,
      onMobileTap: vi.fn(),
      setMobilePopoverOpenImageId: vi.fn(),
      ...((overrides.mobileInteraction as object | undefined) ?? {}),
    },
    features: {
      showShare: true,
      showDelete: true,
      showDownload: true,
      showEdit: true,
      showStar: true,
      showAddToShot: true,
      enableSingleClick: false,
      videosAsThumbnails: false,
      ...((overrides.features as object | undefined) ?? {}),
    },
    actions: {
      onOpenLightbox: vi.fn(),
      onDelete: vi.fn(),
      onDownloadImage: vi.fn(),
      onToggleStar: vi.fn(),
      onImageClick: undefined,
      onImageLoaded: vi.fn(),
      ...((overrides.actions as object | undefined) ?? {}),
    },
    loading: {
      shouldLoad: true,
      isPriority: false,
      isDeleting: false,
      downloadingImageId: null,
      ...((overrides.loading as object | undefined) ?? {}),
    },
    projectAspectRatio: '16:9',
    ...overrides,
  };
}

describe('MediaGalleryItem behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hasLoadedImage.mockReturnValue(false);
    mocks.createDragPreview.mockReturnValue(undefined);
  });

  it('renders the placeholder fallback when the item has no persisted id and only a placeholder url', () => {
    const props = buildProps({
      image: {
        id: '',
        url: '/placeholder.svg',
        thumbUrl: '/placeholder.svg',
        metadata: undefined,
      },
    });

    const { container } = render(<MediaGalleryItem {...props} />);

    const image = screen.getByAltText('Generated image 1');
    expect(image).toHaveAttribute('src', expect.stringContaining('/placeholder.svg'));
    expect(image).not.toBeVisible();
    expect(container.querySelector('.animate-pulse')).not.toBeNull();
  });

  it('opens the lightbox when the rendered image is double-clicked', async () => {
    mocks.hasLoadedImage.mockReturnValue(true);
    const props = buildProps();

    render(<MediaGalleryItem {...props} />);

    const image = await screen.findByAltText('Sunset over water');
    fireEvent.doubleClick(image);

    expect(props.actions.onOpenLightbox).toHaveBeenCalledWith(props.image);
  });

  it('forwards context menu events to the item action handler', () => {
    const onContextMenu = vi.fn();
    const props = buildProps({
      actions: {
        onContextMenu,
      },
    });

    const { container } = render(<MediaGalleryItem {...props} />);
    const root = container.querySelector('[data-gallery-item-id="img-1"]');

    fireEvent.contextMenu(root as HTMLElement);

    expect(onContextMenu).toHaveBeenCalledWith(expect.any(Object), props.image);
  });

  it('applies the selection ring only when the item is selected', () => {
    const selected = buildProps({ isSelected: true });
    const unselected = buildProps();

    const { container: selectedContainer } = render(<MediaGalleryItem {...selected} />);
    const { container: unselectedContainer } = render(<MediaGalleryItem {...unselected} />);

    const selectedRoot = selectedContainer.querySelector('[data-gallery-item-id="img-1"]');
    const unselectedRoot = unselectedContainer.querySelector('[data-gallery-item-id="img-1"]');

    expect(selectedRoot).toHaveClass('outline', 'outline-2', 'outline-sky-400', 'rounded-lg', 'transition-[opacity,transform]');
    expect(selectedRoot).not.toHaveClass('transition-all');
    expect(unselectedRoot).not.toHaveClass('outline');
    expect(unselectedRoot).not.toHaveClass('outline-sky-400');
  });

  it('shows add-to-shot affordances and executes the add action for the selected shot', async () => {
    mocks.hasLoadedImage.mockReturnValue(true);
    const props = buildProps();

    const { container } = render(<MediaGalleryItem {...props} />);

    const addButton = screen.getByLabelText("Add to 'Shot 1' at final position");
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(props.shotWorkflow.onAddToLastShot).toHaveBeenCalledWith(
        'shot-1',
        'img-1',
        'https://cdn/image.png',
        'https://cdn/thumb.png',
      );
    });

    const shotActions = container.querySelector('.absolute.top-1\\.5.left-1\\.5.right-1\\.5');
    expect(shotActions).not.toBeNull();
    expect(within(shotActions as HTMLElement).getByTestId('shot-selector')).toHaveTextContent('shot-1');
  });

  it('uses multi-generation drag data when dragging a selected item from a multi-selection', () => {
    const props = buildProps({
      isSelected: true,
      selectedItems: [
        {
          id: 'img-1',
          generation_id: 'gen-1',
          url: 'https://cdn/image.png',
          thumbUrl: 'https://cdn/thumb.png',
          metadata: { taskId: 'task-1' },
        },
        {
          id: 'img-2',
          generation_id: 'gen-2',
          url: 'https://cdn/image-2.png',
          thumbUrl: 'https://cdn/thumb-2.png',
          isVideo: true,
          type: 'video/mp4',
        },
      ],
    });

    const { container } = render(<MediaGalleryItem {...props} />);
    const dragTarget = container.querySelector('[data-gallery-item-id="img-1"]');

    fireEvent.dragStart(dragTarget as HTMLElement, {
      dataTransfer: {
        setData: vi.fn(),
        setDragImage: vi.fn(),
      },
    });

    expect(mocks.setMultiGenerationDragData).toHaveBeenCalledWith(
      expect.anything(),
      [
        expect.objectContaining({
          generationId: 'img-1',
          imageUrl: 'https://cdn/image.png',
          variantType: 'image',
        }),
        expect.objectContaining({
          generationId: 'img-2',
          imageUrl: 'https://cdn/image-2.png',
          variantType: 'video',
        }),
      ],
    );
    expect(mocks.setGenerationDragData).not.toHaveBeenCalled();
    expect(mocks.createDragPreview).toHaveBeenCalledWith(
      expect.anything(),
      { badgeText: '2' },
    );
  });

  it('falls back to the existing single-item drag payload when the drag is not a multi-selection drag', () => {
    const props = buildProps({
      isSelected: true,
      selectedItems: [
        {
          id: 'img-2',
          generation_id: 'gen-2',
          url: 'https://cdn/image-2.png',
        },
      ],
    });

    const { container } = render(<MediaGalleryItem {...props} />);
    const dragTarget = container.querySelector('[data-gallery-item-id="img-1"]');

    fireEvent.dragStart(dragTarget as HTMLElement, {
      dataTransfer: {
        setData: vi.fn(),
        setDragImage: vi.fn(),
      },
    });

    expect(mocks.setGenerationDragData).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        generationId: 'img-1',
        imageUrl: 'https://cdn/image.png',
        variantType: 'image',
      }),
    );
    expect(mocks.setMultiGenerationDragData).not.toHaveBeenCalled();
    expect(mocks.createDragPreview).toHaveBeenCalledWith(expect.anything(), undefined);
  });
});
