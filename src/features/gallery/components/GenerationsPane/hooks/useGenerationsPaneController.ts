import {
  useEffect,
  useState,
  useRef,
  useCallback,
  useMemo,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from 'react';
import { useRenderLogger } from '@/shared/lib/debug/debugRendering';
import { useSlidingPane } from '@/shared/hooks/useSlidingPane';
import { useQueryClient } from '@tanstack/react-query';
import { shotQueryKeys } from '@/shared/lib/queryKeys/shots';
import { useNavigate, useLocation } from 'react-router-dom';
import { TOOL_ROUTES } from '@/shared/lib/tooling/toolRoutes';
import { type GalleryFilterState } from '@/shared/components/MediaGallery';
import { useContainerWidth } from '@/shared/components/MediaGallery/hooks/useContainerWidth';
import { calculateGalleryLayout } from '@/shared/components/MediaGallery/utils';
import { usePanes } from '@/shared/contexts/PanesContext';
import { useGalleryPageState } from '@/features/gallery/hooks/useGalleryPageState';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useShots } from '@/shared/contexts/ShotsContext';
import {
  useProjectCrudContext,
  useProjectSelectionContext,
} from '@/shared/contexts/ProjectContext';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { useStableObject } from '@/shared/hooks/useStableObject';
import { usePaneInteractionLifecycle } from '@/shared/components/panes/usePaneInteractionLifecycle';
import { SHOT_FILTER, isSpecialFilter } from '@/shared/constants/filterConstants';
import { useAppEventListener } from '@/shared/lib/typedEvents';

// Fallback rows for pane (smaller than full page galleries)
const PANE_ROWS = 2;
const PANE_ROWS_EXPANDED = 3;

type MediaTypeFilter = 'all' | 'image' | 'video';
type BooleanStateSetter = (value: boolean) => void;
type GalleryPageState = ReturnType<typeof useGalleryPageState>;
type SelectedProjectId = ReturnType<typeof useProjectSelectionContext>['selectedProjectId'];
type ProjectAspectRatio = ReturnType<typeof useProjectCrudContext>['projects'][number]['aspectRatio'];

interface GenerationDataParams {
  itemsPerPage: number;
  mediaTypeFilter: MediaTypeFilter;
  shouldEnableDataLoading: boolean;
  selectedProjectId: SelectedProjectId;
}

const useGenerationData = ({
  itemsPerPage,
  mediaTypeFilter,
  shouldEnableDataLoading,
  selectedProjectId,
}: GenerationDataParams) => {
  const queryClient = useQueryClient();
  const { createShot } = useShotCreation();
  const { shots: contextShots } = useShots();

  const galleryPageState = useGalleryPageState({
    itemsPerPage,
    mediaType: mediaTypeFilter,
    enableDataLoading: shouldEnableDataLoading,
  });

  const shotsForFilter = (galleryPageState.shotsData && galleryPageState.shotsData.length > 0)
    ? galleryPageState.shotsData
    : (contextShots || []);

  const handleCreateShot = useCallback(async (shotName: string, files: File[]): Promise<void> => {
    await createShot({
      name: shotName,
      files: files.length > 0 ? files : undefined,
      dispatchSkeletonEvents: files.length > 0,
      onSuccess: () => {
        if (selectedProjectId) {
          void queryClient.invalidateQueries({ queryKey: [...shotQueryKeys.all, selectedProjectId] });
        }
      },
    });
  }, [createShot, queryClient, selectedProjectId]);

  return {
    ...galleryPageState,
    handleCreateShot,
    shotsForFilter,
  };
};

interface GenerationFiltersParams {
  mediaTypeFilter: MediaTypeFilter;
  setMediaTypeFilter: Dispatch<SetStateAction<MediaTypeFilter>>;
  selectedShotFilter: GalleryPageState['selectedShotFilter'];
  excludePositioned: GalleryPageState['excludePositioned'];
  starredOnly: GalleryPageState['starredOnly'];
  searchTerm: GalleryPageState['searchTerm'];
  setSelectedShotFilter: GalleryPageState['setSelectedShotFilter'];
  setExcludePositioned: GalleryPageState['setExcludePositioned'];
  setStarredOnly: GalleryPageState['setStarredOnly'];
  setSearchTerm: GalleryPageState['setSearchTerm'];
}

const useGenerationFilters = ({
  mediaTypeFilter,
  setMediaTypeFilter,
  selectedShotFilter,
  excludePositioned,
  starredOnly,
  searchTerm,
  setSelectedShotFilter,
  setExcludePositioned,
  setStarredOnly,
  setSearchTerm,
}: GenerationFiltersParams) => {
  const [shotFilterOpen, setShotFilterOpen] = useState(false);
  const [mediaTypeFilterOpen, setMediaTypeFilterOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const shotFilterContentRef = useRef<HTMLDivElement>(null);
  const mediaTypeContentRef = useRef<HTMLDivElement>(null);

  const generationFilters = useStableObject(() => ({
    mediaType: mediaTypeFilter,
    shotId: selectedShotFilter === SHOT_FILTER.ALL ? undefined : selectedShotFilter,
    excludePositioned: selectedShotFilter !== SHOT_FILTER.ALL ? excludePositioned : undefined,
    starredOnly,
  }), [mediaTypeFilter, selectedShotFilter, excludePositioned, starredOnly]);

  const galleryFilters = useMemo((): GalleryFilterState => ({
    mediaType: mediaTypeFilter,
    shotFilter: selectedShotFilter,
    excludePositioned,
    searchTerm,
    starredOnly,
    toolTypeFilter: false,
  }), [mediaTypeFilter, selectedShotFilter, excludePositioned, searchTerm, starredOnly]);

  const handleGalleryFiltersChange = useCallback((newFilters: GalleryFilterState) => {
    setSelectedShotFilter(newFilters.shotFilter);
    setExcludePositioned(newFilters.excludePositioned);
    setSearchTerm(newFilters.searchTerm);
    setStarredOnly(newFilters.starredOnly);
    setMediaTypeFilter(newFilters.mediaType);
  }, [setSelectedShotFilter, setExcludePositioned, setSearchTerm, setStarredOnly, setMediaTypeFilter]);

  return {
    excludePositioned,
    galleryFilters,
    generationFilters,
    handleGalleryFiltersChange,
    isSearchOpen,
    mediaTypeContentRef,
    mediaTypeFilter,
    mediaTypeFilterOpen,
    searchInputRef,
    searchTerm,
    selectedShotFilter,
    setExcludePositioned,
    setIsSearchOpen,
    setMediaTypeFilter,
    setMediaTypeFilterOpen,
    setSelectedShotFilter,
    setShotFilterOpen,
    setStarredOnly,
    setSearchTerm,
    shotFilterContentRef,
    shotFilterOpen,
    starredOnly,
  };
};

interface PaneLifecycleParams {
  isGenerationsPaneLocked: boolean;
  setIsGenerationsPaneLocked: BooleanStateSetter;
  setIsGenerationsPaneOpen: BooleanStateSetter;
  isOnImageGenerationPage: boolean;
  shotFilterContentRef: RefObject<HTMLDivElement | null>;
  mediaTypeContentRef: RefObject<HTMLDivElement | null>;
  setShotFilterOpen: BooleanStateSetter;
  setMediaTypeFilterOpen: BooleanStateSetter;
}

const usePaneLifecycle = ({
  isGenerationsPaneLocked,
  setIsGenerationsPaneLocked,
  setIsGenerationsPaneOpen,
  isOnImageGenerationPage,
  shotFilterContentRef,
  mediaTypeContentRef,
  setShotFilterOpen,
  setMediaTypeFilterOpen,
}: PaneLifecycleParams) => {
  const {
    isLocked,
    isOpen,
    toggleLock,
    openPane,
    paneProps,
    transformClass,
    handlePaneEnter,
    handlePaneLeave,
    showBackdrop,
    closePane,
  } = useSlidingPane({
    side: 'bottom',
    isLocked: isGenerationsPaneLocked,
    onToggleLock: () => setIsGenerationsPaneLocked(!isGenerationsPaneLocked),
    additionalRefs: [shotFilterContentRef, mediaTypeContentRef],
  });
  const paneIsOpen = Boolean(isOpen);

  const handlePaneOpenStart = useCallback(() => {
    setShotFilterOpen(false);
    setMediaTypeFilterOpen(false);
  }, [setMediaTypeFilterOpen, setShotFilterOpen]);

  const { isPointerEventsEnabled, isInteractionDisabled } = usePaneInteractionLifecycle({
    isOpen: paneIsOpen,
    disableInteractionsDuringOpen: true,
    onOpenStart: handlePaneOpenStart,
  });

  const handleOpenGenerationsPane = useCallback(() => {
    openPane();
  }, [openPane]);
  useAppEventListener('openGenerationsPane', handleOpenGenerationsPane);

  useEffect(() => {
    setIsGenerationsPaneOpen(paneIsOpen);
  }, [paneIsOpen, setIsGenerationsPaneOpen]);

  useEffect(() => {
    if (isOnImageGenerationPage && (paneIsOpen || isLocked)) {
      setIsGenerationsPaneLocked(false);
    }
  }, [isOnImageGenerationPage, paneIsOpen, isLocked, setIsGenerationsPaneLocked]);

  return {
    closePane,
    handlePaneEnter,
    handlePaneLeave,
    isInteractionDisabled,
    isLocked,
    isPointerEventsEnabled,
    openPane,
    paneIsOpen,
    paneProps,
    showBackdrop,
    toggleLock,
    transformClass,
  };
};

const usePaneLayout = (projectAspectRatio: ProjectAspectRatio | undefined, expandedRows = false) => {
  const isMobile = useIsMobile();
  const [galleryContainerRef, containerWidth] = useContainerWidth();

  const paneLayout = useMemo(() => {
    const layout = calculateGalleryLayout(
      projectAspectRatio,
      isMobile,
      containerWidth,
      undefined,
      true,
    );
    const rows = expandedRows ? PANE_ROWS_EXPANDED : PANE_ROWS;
    return {
      ...layout,
      itemsPerPage: layout.columns * rows,
    };
  }, [projectAspectRatio, isMobile, containerWidth, expandedRows]);

  return {
    galleryContainerRef,
    isMobile,
    paneLayout,
  };
};

export const useGenerationsPaneController = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    isGenerationsPaneLocked,
    setIsGenerationsPaneLocked,
    isGenerationsPaneOpen,
    setIsGenerationsPaneOpen,
    generationsPaneHeight,
    isShotsPaneLocked,
    shotsPaneWidth,
    isTasksPaneLocked,
    tasksPaneWidth,
    isEditorPaneLocked,
  } = usePanes();
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const { currentShotId } = useCurrentShot();

  const isOnImageGenerationPage = location.pathname === TOOL_ROUTES.IMAGE_GENERATION;
  const currentProject = projects.find((project) => project.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio;
  const shouldEnableDataLoading = isGenerationsPaneOpen;

  const { galleryContainerRef, isMobile, paneLayout } = usePaneLayout(projectAspectRatio, isEditorPaneLocked);

  const [mediaTypeFilter, setMediaTypeFilter] = useState<MediaTypeFilter>('image');
  const generationData = useGenerationData({
    itemsPerPage: paneLayout.itemsPerPage,
    mediaTypeFilter,
    shouldEnableDataLoading,
    selectedProjectId,
  });

  const filters = useGenerationFilters({
    mediaTypeFilter,
    setMediaTypeFilter,
    selectedShotFilter: generationData.selectedShotFilter,
    excludePositioned: generationData.excludePositioned,
    starredOnly: generationData.starredOnly,
    searchTerm: generationData.searchTerm,
    setSelectedShotFilter: generationData.setSelectedShotFilter,
    setExcludePositioned: generationData.setExcludePositioned,
    setStarredOnly: generationData.setStarredOnly,
    setSearchTerm: generationData.setSearchTerm,
  });

  const pane = usePaneLifecycle({
    isGenerationsPaneLocked,
    setIsGenerationsPaneLocked,
    setIsGenerationsPaneOpen,
    isOnImageGenerationPage,
    shotFilterContentRef: filters.shotFilterContentRef,
    mediaTypeContentRef: filters.mediaTypeContentRef,
    setShotFilterOpen: filters.setShotFilterOpen,
    setMediaTypeFilterOpen: filters.setMediaTypeFilterOpen,
  });

  const [isGenerationModalOpen, setIsGenerationModalOpen] = useState(false);
  const handleOpenModal = useCallback(() => setIsGenerationModalOpen(true), []);
  const handleCloseModal = useCallback(() => setIsGenerationModalOpen(false), []);
  useAppEventListener('openGenerationModal', handleOpenModal);
  useAppEventListener('closeGenerationModal', handleCloseModal);

  const handleNavigateToImageGeneration = useCallback(() => {
    setIsGenerationsPaneLocked(false);
    navigate(TOOL_ROUTES.IMAGE_GENERATION);
  }, [navigate, setIsGenerationsPaneLocked]);

  useRenderLogger('GenerationsPane', {
    page: generationData.page,
    totalItems: generationData.totalCount,
  });

  return {
    pane: {
      ...pane,
      generationsPaneHeight,
      isOnImageGenerationPage,
      isShotsPaneLocked,
      isTasksPaneLocked,
      shotsPaneWidth,
      tasksPaneWidth,
    },
    filters: {
      ...filters,
      currentShotId,
      isSpecialFilterSelected: isSpecialFilter(filters.selectedShotFilter),
      shotsForFilter: generationData.shotsForFilter,
    },
    gallery: {
      confirmDialogProps: generationData.confirmDialogProps,
      error: generationData.error,
      expectedItemCount: generationData.expectedItemCount,
      handleAddToShot: generationData.handleAddToShot,
      handleAddToShotWithoutPosition: generationData.handleAddToShotWithoutPosition,
      handleCreateShot: generationData.handleCreateShot,
      handleDeleteGeneration: generationData.handleDeleteGeneration,
      handleServerPageChange: generationData.handleServerPageChange,
      handleToggleStar: generationData.handleToggleStar,
      isDeleting: generationData.isDeleting,
      isLoading: generationData.isLoading,
      lastAffectedShotId: generationData.lastAffectedShotId,
      page: generationData.page,
      paginatedData: generationData.paginatedData,
      shotsData: generationData.shotsData,
      totalCount: generationData.totalCount,
    },
    layout: {
      galleryContainerRef,
      isMobile,
      paneLayout,
      projectAspectRatio,
    },
    modal: {
      isGenerationModalOpen,
      setIsGenerationModalOpen,
    },
    navigation: {
      handleNavigateToImageGeneration,
    },
  };
};
