// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GenerationsPaneGallery } from './GenerationsPaneGallery';

const mocks = vi.hoisted(() => ({
  MediaGallery: vi.fn(() => <div data-testid="media-gallery" />),
  SkeletonGallery: vi.fn(() => <div data-testid="skeleton-gallery" />),
  SelectionContextMenu: vi.fn(({
    position,
    onCreateShot,
    onGenerateVideo,
  }: {
    position: { x: number; y: number } | null;
    onCreateShot: () => void;
    onGenerateVideo: () => void;
  }) => (
    position ? (
      <div data-testid="selection-context-menu">
        <button type="button" onClick={onCreateShot}>Create Shot</button>
        <button type="button" onClick={onGenerateVideo}>Generate Video</button>
      </div>
    ) : null
  )),
  VideoGenerationModal: vi.fn(({ shot }: { shot: { name: string } }) => (
    <div data-testid="video-generation-modal">{shot.name}</div>
  )),
  useGallerySelection: vi.fn(),
  userSelectGalleryItem: vi.fn(),
  userSelectGalleryItems: vi.fn(),
  useShots: vi.fn(),
  useShotCreation: vi.fn(),
  useShotNavigation: vi.fn(),
  useLassoSelection: vi.fn(),
}));

vi.mock('@/shared/components/MediaGallery', () => ({
  MediaGallery: (props: unknown) => mocks.MediaGallery(props),
}));

vi.mock('@/shared/components/SelectionContextMenu', () => ({
  SelectionContextMenu: (props: unknown) => mocks.SelectionContextMenu(props),
}));

vi.mock('@/shared/components/ui/composed/skeleton-gallery', () => ({
  SkeletonGallery: (props: unknown) => mocks.SkeletonGallery(props),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useGallerySelection: () => mocks.useGallerySelection(),
  userSelectGalleryItem: (...args: unknown[]) => mocks.userSelectGalleryItem(...args),
  userSelectGalleryItems: (...args: unknown[]) => mocks.userSelectGalleryItems(...args),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => mocks.useShots(),
}));

vi.mock('@/shared/hooks/shotCreation/useShotCreation', () => ({
  useShotCreation: () => mocks.useShotCreation(),
}));

vi.mock('@/shared/hooks/shots/useShotNavigation', () => ({
  useShotNavigation: () => mocks.useShotNavigation(),
}));

vi.mock('@/tools/travel-between-images/components/VideoGenerationModal', () => ({
  VideoGenerationModal: (props: unknown) => mocks.VideoGenerationModal(props),
}));

vi.mock('../hooks/useLassoSelection', () => ({
  useLassoSelection: (props: unknown) => mocks.useLassoSelection(props),
}));

function buildProps(overrides: Partial<ComponentProps<typeof GenerationsPaneGallery>> = {}) {
  return {
    containerRef: { current: null },
    projectAspectRatio: '16:9',
    layout: { columns: 3, itemsPerPage: 12 },
    loading: { isLoading: false, expectedItemCount: 12 },
    pagination: { page: 2, totalCount: 25 },
    error: null,
    gallery: {
      items: [],
      onDelete: vi.fn(),
      onToggleStar: vi.fn(),
      isDeleting: false,
      allShots: [],
      lastShotId: undefined,
      filters: { sortBy: 'newest' } as never,
      onFiltersChange: vi.fn(),
      onAddToShot: vi.fn(async () => false),
      onAddToShotWithoutPosition: vi.fn(async () => false),
      onServerPageChange: vi.fn(),
      generationFilters: undefined,
      currentViewingShotId: undefined,
      onCreateShot: vi.fn(async () => undefined),
    },
    ...overrides,
  };
}

describe('GenerationsPaneGallery', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(['g2']),
      gallerySelectionMap: new Map([
        ['g2', { url: 'https://example.com/2.mp4', mediaType: 'video', generationId: 'gen-2' }],
      ]),
    });
    mocks.useShots.mockReturnValue({ shots: [{ id: 'shot-9', name: 'Shot 9' }] });
    mocks.useShotCreation.mockReturnValue({
      createShot: vi.fn(),
      isCreating: false,
    });
    mocks.useShotNavigation.mockReturnValue({
      navigateToShot: vi.fn(),
    });
    mocks.useLassoSelection.mockReturnValue({
      selectionRect: null,
      handleMouseDown: vi.fn(),
    });
  });

  it('renders loading skeleton when loading and no items exist', () => {
    render(
      <GenerationsPaneGallery
        {...buildProps({
          loading: { isLoading: true, expectedItemCount: 9 },
        })}
      />,
    );

    expect(screen.getByTestId('skeleton-gallery')).toBeInTheDocument();
    expect(mocks.SkeletonGallery).toHaveBeenCalledWith(
      expect.objectContaining({
        count: 9,
        fixedColumns: 3,
        projectAspectRatio: '16:9',
      }),
    );
  });

  it('renders media gallery with mapped pagination props when items are present', () => {
    const gallery = buildProps().gallery;
    const items = [
      { id: 'g1', url: 'https://example.com/1.png', type: 'image/png' },
      { id: 'g2', url: 'https://example.com/2.mp4', isVideo: true, generation_id: 'gen-2' },
    ];

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...gallery, items } as never,
        })}
      />,
    );

    expect(screen.getByTestId('media-gallery')).toBeInTheDocument();
    expect(mocks.MediaGallery).toHaveBeenCalledWith(
      expect.objectContaining({
        images: items,
        selectedIds: new Set(['g2']),
        config: expect.objectContaining({
          enableSingleClick: true,
        }),
        pagination: expect.objectContaining({
          offset: 12,
          totalCount: 25,
          itemsPerPage: 12,
        }),
      }),
    );
  });

  it('selects a single gallery item on single click', () => {
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(),
      gallerySelectionMap: new Map(),
    });

    const image = {
      id: 'g1',
      url: 'https://example.com/1.png',
      type: 'image/png',
      generation_id: 'gen-1',
    };

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...buildProps().gallery, items: [image] } as never,
        })}
      />,
    );

    const mediaGalleryProps = mocks.MediaGallery.mock.calls[0]?.[0];
    mediaGalleryProps.onImageClick(image);

    expect(mocks.userSelectGalleryItem).toHaveBeenCalledWith(
      {
        id: 'g1',
        url: 'https://example.com/1.png',
        type: 'image/png',
        generationId: 'gen-1',
      },
      { additive: false },
    );
  });

  it('toggles selection on modifier-assisted click and renders lasso overlay', () => {
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(['g1']),
      gallerySelectionMap: new Map([
        ['g1', { url: 'https://example.com/1.png', mediaType: 'video', generationId: 'g1' }],
      ]),
    });
    mocks.useLassoSelection.mockReturnValue({
      selectionRect: {
        left: 10,
        top: 20,
        width: 30,
        height: 40,
      },
      handleMouseDown: vi.fn(),
    });

    const image = {
      id: 'g1',
      url: 'https://example.com/1.png',
      isVideo: true,
    };

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...buildProps().gallery, items: [image] } as never,
        })}
      />,
    );

    expect(document.querySelector('.border-sky-400.bg-sky-400\\/10')).toBeInTheDocument();

    const mediaGalleryProps = mocks.MediaGallery.mock.calls[0]?.[0];
    mediaGalleryProps.onImageClick(image, { multiSelect: true });

    expect(mocks.userSelectGalleryItem).toHaveBeenCalledWith(
      {
        id: 'g1',
        url: 'https://example.com/1.png',
        type: 'video/mp4',
        generationId: 'g1',
      },
      { additive: true },
    );
  });

  it('selects an unselected item before opening the context menu', () => {
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(),
      gallerySelectionMap: new Map(),
    });

    const image = {
      id: 'g1',
      url: 'https://example.com/1.png',
      type: 'image/png',
      generation_id: 'gen-1',
    };

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...buildProps().gallery, items: [image] } as never,
        })}
      />,
    );

    const mediaGalleryProps = mocks.MediaGallery.mock.calls[0]?.[0];
    act(() => {
      mediaGalleryProps.onContextMenu({
        preventDefault: vi.fn(),
        clientX: 20,
        clientY: 30,
      }, image);
    });

    expect(mocks.userSelectGalleryItem).toHaveBeenCalledWith({
      id: 'g1',
      url: 'https://example.com/1.png',
      type: 'image/png',
      generationId: 'gen-1',
    }, { additive: false });
    expect(screen.getByTestId('selection-context-menu')).toBeInTheDocument();
  });

  it('creates a shot from gallery selection order without clearing the selection', async () => {
    const createShot = vi.fn().mockResolvedValue({
      shotId: 'shot-9',
      shot: { id: 'shot-9', name: 'Shot 9' },
    });
    mocks.useShotCreation.mockReturnValue({ createShot, isCreating: false });
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(['g2', 'g1']),
      gallerySelectionMap: new Map([
        ['g2', { url: 'https://example.com/2.mp4', mediaType: 'video', generationId: 'gen-2' }],
        ['g1', { url: 'https://example.com/1.png', mediaType: 'image', generationId: 'gen-1' }],
      ]),
    });

    const image = {
      id: 'g2',
      url: 'https://example.com/2.mp4',
      type: 'video/mp4',
      generation_id: 'gen-2',
    };

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...buildProps().gallery, items: [image] } as never,
        })}
      />,
    );

    const mediaGalleryProps = mocks.MediaGallery.mock.calls[0]?.[0];
    act(() => {
      mediaGalleryProps.onContextMenu({
        preventDefault: vi.fn(),
        clientX: 20,
        clientY: 30,
      }, image);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Shot' }));

    await waitFor(() => {
      expect(createShot).toHaveBeenCalledWith({ generationIds: ['gen-2', 'gen-1'] });
    });
  });

  it('opens the video generation modal with the newly created shot', async () => {
    const createShot = vi.fn().mockResolvedValue({
      shotId: 'shot-9',
      shot: { id: 'shot-9', name: 'Shot 9' },
    });
    mocks.useShotCreation.mockReturnValue({ createShot, isCreating: false });
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(['g1']),
      gallerySelectionMap: new Map([
        ['g1', { url: 'https://example.com/1.png', mediaType: 'image', generationId: 'gen-1' }],
      ]),
    });

    const image = {
      id: 'g1',
      url: 'https://example.com/1.png',
      type: 'image/png',
      generation_id: 'gen-1',
    };

    render(
      <GenerationsPaneGallery
        {...buildProps({
          gallery: { ...buildProps().gallery, items: [image] } as never,
        })}
      />,
    );

    const mediaGalleryProps = mocks.MediaGallery.mock.calls[0]?.[0];
    act(() => {
      mediaGalleryProps.onContextMenu({
        preventDefault: vi.fn(),
        clientX: 20,
        clientY: 30,
      }, image);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate Video' }));

    await waitFor(() => {
      expect(screen.getByTestId('video-generation-modal')).toHaveTextContent('Shot 9');
    });
  });

  it('renders error and empty states when applicable', () => {
    render(
      <GenerationsPaneGallery
        {...buildProps({
          error: new Error('failed'),
          loading: { isLoading: false },
        })}
      />,
    );

    expect(screen.getByText('Error: failed')).toBeInTheDocument();
    expect(screen.getByText('No generations found for this project.')).toBeInTheDocument();
  });

  it('passes only full-match existing shots to the selection context menu using gallery selection generation ids', () => {
    mocks.useGallerySelection.mockReturnValue({
      selectedGalleryIds: new Set(['gallery-item-1', 'gallery-item-2']),
      gallerySelectionMap: new Map([
        ['gallery-item-1', { url: 'https://example.com/1.png', mediaType: 'image', generationId: 'gen-1' }],
        ['gallery-item-2', { url: 'https://example.com/2.png', mediaType: 'image', generationId: 'gen-2' }],
      ]),
    });
    mocks.useShots.mockReturnValue({
      shots: [
        {
          id: 'shot-full',
          name: 'Full Match',
          images: [
            { id: 'sg-1', generation_id: 'gen-1' },
            { id: 'sg-2', generation_id: 'gen-2' },
          ],
        },
        {
          id: 'shot-partial',
          name: 'Partial Match',
          images: [{ id: 'sg-3', generation_id: 'gen-1' }],
        },
        {
          id: 'shot-wrong-source',
          name: 'Wrong Source',
          images: [
            { id: 'sg-4', generation_id: 'gallery-item-1' },
            { id: 'sg-5', generation_id: 'gallery-item-2' },
          ],
        },
      ],
    });

    render(<GenerationsPaneGallery {...buildProps()} />);

    expect(mocks.SelectionContextMenu).toHaveBeenCalledWith(
      expect.objectContaining({
        existingShots: [
          expect.objectContaining({ id: 'shot-full', name: 'Full Match' }),
        ],
      }),
    );
  });
});
