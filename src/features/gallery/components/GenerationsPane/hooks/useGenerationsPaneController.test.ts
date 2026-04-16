import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useGenerationsPaneController } from './useGenerationsPaneController';

const mocks = vi.hoisted(() => ({
  useRenderLogger: vi.fn(),
  useSlidingPane: vi.fn(),
  useQueryClient: vi.fn(),
  useNavigate: vi.fn(),
  useLocation: vi.fn(),
  useContainerWidth: vi.fn(),
  calculateGalleryLayout: vi.fn(),
  usePanes: vi.fn(),
  useGalleryPageState: vi.fn(),
  useIsMobile: vi.fn(),
  useCurrentShot: vi.fn(),
  useShots: vi.fn(),
  useProjectCrudContext: vi.fn(),
  useProjectSelectionContext: vi.fn(),
  useShotCreation: vi.fn(),
  useStableObject: vi.fn(),
  usePaneInteractionLifecycle: vi.fn(),
  isSpecialFilter: vi.fn(),
  useAppEventListener: vi.fn(),
  eventHandlers: {} as Record<string, () => void>,
}));

vi.mock('@/shared/lib/debug/debugRendering', () => ({
  useRenderLogger: (...args: unknown[]) => mocks.useRenderLogger(...args),
}));

vi.mock('@/shared/hooks/useSlidingPane', () => ({
  useSlidingPane: (...args: unknown[]) => mocks.useSlidingPane(...args),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: (...args: unknown[]) => mocks.useQueryClient(...args),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: (...args: unknown[]) => mocks.useNavigate(...args),
  useLocation: (...args: unknown[]) => mocks.useLocation(...args),
}));

vi.mock('@/shared/lib/tooling/toolRoutes', () => ({
  TOOL_ROUTES: {
    IMAGE_GENERATION: '/tools/image-generation',
  },
}));

vi.mock('@/shared/components/MediaGallery/hooks/useContainerWidth', () => ({
  useContainerWidth: (...args: unknown[]) => mocks.useContainerWidth(...args),
}));

vi.mock('@/shared/components/MediaGallery/utils', () => ({
  calculateGalleryLayout: (...args: unknown[]) => mocks.calculateGalleryLayout(...args),
}));

vi.mock('@/shared/contexts/PanesContext', () => ({
  usePanes: (...args: unknown[]) => mocks.usePanes(...args),
}));

vi.mock('@/features/gallery/hooks/useGalleryPageState', () => ({
  useGalleryPageState: (...args: unknown[]) => mocks.useGalleryPageState(...args),
}));

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: (...args: unknown[]) => mocks.useIsMobile(...args),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useCurrentShot: (...args: unknown[]) => mocks.useCurrentShot(...args),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: (...args: unknown[]) => mocks.useShots(...args),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectCrudContext: (...args: unknown[]) => mocks.useProjectCrudContext(...args),
  useProjectSelectionContext: (...args: unknown[]) => mocks.useProjectSelectionContext(...args),
}));

vi.mock('@/shared/hooks/shotCreation/useShotCreation', () => ({
  useShotCreation: (...args: unknown[]) => mocks.useShotCreation(...args),
}));

vi.mock('@/shared/hooks/useStableObject', () => ({
  useStableObject: (...args: unknown[]) => mocks.useStableObject(...args),
}));

vi.mock('@/shared/components/panes/usePaneInteractionLifecycle', () => ({
  usePaneInteractionLifecycle: (...args: unknown[]) => mocks.usePaneInteractionLifecycle(...args),
}));

vi.mock('@/shared/constants/filterConstants', () => ({
  SHOT_FILTER: { ALL: 'all' },
  isSpecialFilter: (...args: unknown[]) => mocks.isSpecialFilter(...args),
}));

vi.mock('@/shared/lib/typedEvents', () => ({
  useAppEventListener: (...args: unknown[]) => mocks.useAppEventListener(...args),
}));

vi.mock('@/shared/lib/queryKeys/shots', () => ({
  shotQueryKeys: {
    all: ['shots'],
  },
}));

function buildGalleryPageState(overrides: Record<string, unknown> = {}) {
  return {
    selectedShotFilter: 'all',
    excludePositioned: false,
    starredOnly: false,
    searchTerm: '',
    setSelectedShotFilter: vi.fn(),
    setExcludePositioned: vi.fn(),
    setStarredOnly: vi.fn(),
    setSearchTerm: vi.fn(),
    shotsData: [],
    confirmDialogProps: { isOpen: false, onClose: vi.fn() },
    error: null,
    expectedItemCount: 8,
    handleAddToShot: vi.fn(),
    handleAddToShotWithoutPosition: vi.fn(),
    handleDeleteGeneration: vi.fn(),
    handleServerPageChange: vi.fn(),
    handleToggleStar: vi.fn(),
    isDeleting: false,
    isLoading: false,
    lastAffectedShotId: null,
    page: 1,
    paginatedData: { items: [{ id: 'gen-1' }] },
    totalCount: 10,
    ...overrides,
  };
}

function buildSlidingPaneState(overrides: Record<string, unknown> = {}) {
  return {
    isLocked: false,
    isOpen: true,
    toggleLock: vi.fn(),
    openPane: vi.fn(),
    paneProps: { role: 'region' },
    transformClass: 'translate-y-0',
    handlePaneEnter: vi.fn(),
    handlePaneLeave: vi.fn(),
    showBackdrop: true,
    closePane: vi.fn(),
    ...overrides,
  };
}

function buildPanesState(overrides: Record<string, unknown> = {}) {
  return {
    isGenerationsPaneLocked: false,
    setIsGenerationsPaneLocked: vi.fn(),
    isGenerationsPaneOpen: true,
    setIsGenerationsPaneOpen: vi.fn(),
    generationsPaneHeight: 280,
    isShotsPaneLocked: true,
    shotsPaneWidth: 100,
    isTasksPaneLocked: false,
    tasksPaneWidth: 0,
    ...overrides,
  };
}

describe('useGenerationsPaneController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.eventHandlers = {};

    mocks.useStableObject.mockImplementation((factory: () => unknown) => factory());
    mocks.useAppEventListener.mockImplementation((event: string, handler: () => void) => {
      mocks.eventHandlers[event] = handler;
    });
    mocks.useRenderLogger.mockReturnValue(undefined);
    mocks.useIsMobile.mockReturnValue(false);
    mocks.useContainerWidth.mockReturnValue([{ current: null }, 640]);
    mocks.calculateGalleryLayout.mockReturnValue({ columns: 3 });
    mocks.useLocation.mockReturnValue({ pathname: '/home' });
    mocks.useNavigate.mockReturnValue(vi.fn());
    mocks.isSpecialFilter.mockReturnValue(false);
    mocks.usePaneInteractionLifecycle.mockReturnValue({
      isPointerEventsEnabled: true,
      isInteractionDisabled: false,
    });
    mocks.useSlidingPane.mockReturnValue(buildSlidingPaneState());
    mocks.usePanes.mockReturnValue(buildPanesState());
    mocks.useProjectSelectionContext.mockReturnValue({ selectedProjectId: 'project-1' });
    mocks.useProjectCrudContext.mockReturnValue({
      projects: [{ id: 'project-1', aspectRatio: 1.6 }],
    });
    mocks.useCurrentShot.mockReturnValue({ currentShotId: 'shot-abc' });
    mocks.useShots.mockReturnValue({ shots: [{ id: 'fallback-shot' }] });
    mocks.useShotCreation.mockReturnValue({ createShot: vi.fn() });
    mocks.useGalleryPageState.mockReturnValue(buildGalleryPageState());
    mocks.useQueryClient.mockReturnValue({ invalidateQueries: vi.fn() });
  });

  it('composes pane/filter/gallery state and wires event handlers plus navigation', async () => {
    const createShot = vi.fn(async ({ onSuccess }: { onSuccess?: () => void }) => {
      onSuccess?.();
    });
    const navigate = vi.fn();
    const openPane = vi.fn();
    const setIsGenerationsPaneLocked = vi.fn();
    const setIsGenerationsPaneOpen = vi.fn();
    const invalidateQueries = vi.fn();
    const galleryPageState = buildGalleryPageState({
      shotsData: [],
      selectedShotFilter: 'all',
    });

    mocks.useShotCreation.mockReturnValue({ createShot });
    mocks.useNavigate.mockReturnValue(navigate);
    mocks.useSlidingPane.mockReturnValue(buildSlidingPaneState({
      openPane,
      isOpen: true,
      isLocked: false,
    }));
    mocks.usePanes.mockReturnValue(buildPanesState({
      isGenerationsPaneOpen: true,
      setIsGenerationsPaneOpen,
      setIsGenerationsPaneLocked,
    }));
    mocks.useGalleryPageState.mockReturnValue(galleryPageState);
    mocks.useQueryClient.mockReturnValue({ invalidateQueries });

    const { result } = renderHook(() => useGenerationsPaneController());

    expect(mocks.useGalleryPageState).toHaveBeenCalledWith({
      itemsPerPage: 6,
      mediaType: 'image',
      enableDataLoading: true,
    });
    expect(result.current.layout.paneLayout.itemsPerPage).toBe(6);
    expect(result.current.layout.projectAspectRatio).toBe(1.6);
    expect(result.current.filters.shotsForFilter).toEqual([{ id: 'fallback-shot' }]);
    expect(result.current.filters.generationFilters).toEqual({
      mediaType: 'image',
      shotId: undefined,
      excludePositioned: undefined,
      starredOnly: false,
    });
    expect(result.current.filters.isSpecialFilterSelected).toBe(false);
    expect(result.current.pane.generationsPaneHeight).toBe(280);
    expect(result.current.pane.isShotsPaneLocked).toBe(true);
    expect(result.current.modal.isGenerationModalOpen).toBe(false);

    act(() => {
      mocks.eventHandlers.openGenerationModal();
    });
    expect(result.current.modal.isGenerationModalOpen).toBe(true);

    act(() => {
      mocks.eventHandlers.closeGenerationModal();
    });
    expect(result.current.modal.isGenerationModalOpen).toBe(false);

    act(() => {
      mocks.eventHandlers.openGenerationsPane();
    });
    expect(openPane).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.navigation.handleNavigateToImageGeneration();
    });
    expect(setIsGenerationsPaneLocked).toHaveBeenCalledWith(false);
    expect(navigate).toHaveBeenCalledWith('/tools/image-generation');
    expect(setIsGenerationsPaneOpen).toHaveBeenCalledWith(true);

    await act(async () => {
      await result.current.gallery.handleCreateShot('New Shot', [new File(['x'], 'one.png', { type: 'image/png' })]);
    });
    expect(createShot).toHaveBeenCalledWith(expect.objectContaining({
      name: 'New Shot',
      files: expect.any(Array),
      dispatchSkeletonEvents: true,
      onSuccess: expect.any(Function),
    }));
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['shots', 'project-1'],
    });
  });

  it('forces unlock on image-generation route and prefers gallery shot data over fallback context', () => {
    const setIsGenerationsPaneLocked = vi.fn();
    const galleryPageState = buildGalleryPageState({
      shotsData: [{ id: 'from-gallery' }],
      selectedShotFilter: 'special',
      excludePositioned: true,
      starredOnly: true,
    });

    mocks.useLocation.mockReturnValue({ pathname: '/tools/image-generation' });
    mocks.usePanes.mockReturnValue(buildPanesState({
      isGenerationsPaneOpen: false,
      isGenerationsPaneLocked: true,
      setIsGenerationsPaneLocked,
    }));
    mocks.useSlidingPane.mockReturnValue(buildSlidingPaneState({
      isOpen: false,
      isLocked: true,
    }));
    mocks.useGalleryPageState.mockReturnValue(galleryPageState);
    mocks.isSpecialFilter.mockReturnValue(true);

    const { result } = renderHook(() => useGenerationsPaneController());

    expect(result.current.pane.isOnImageGenerationPage).toBe(true);
    expect(result.current.filters.shotsForFilter).toEqual([{ id: 'from-gallery' }]);
    expect(result.current.filters.isSpecialFilterSelected).toBe(true);
    expect(mocks.useGalleryPageState).toHaveBeenCalledWith(expect.objectContaining({
      enableDataLoading: false,
    }));
    expect(setIsGenerationsPaneLocked).toHaveBeenCalledWith(false);
  });
});
