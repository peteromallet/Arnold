import {
  useState,
  useEffect,
  useRef,
  useCallback,
  Suspense,
  type MutableRefObject
} from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shot } from '@/domains/generation/types';
import { Button } from '@/shared/components/ui/button';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useShotNavigation } from '@/shared/hooks/shots/useShotNavigation';
import { useUpdateShotName } from '@/shared/hooks/shots';
import { usePrimeShotImagesCache } from '@/shared/hooks/shots/useShotImages';
import { useEnqueueGenerationsInvalidation } from '@/shared/hooks/invalidation/useGenerationInvalidation';
import { useProjectVideoCountsCache } from '@/shared/hooks/projects/useProjectVideoCountsCache';
import { useProjectGenerationModesCache } from '@/shared/hooks/projects/useProjectGenerationModesCache';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useVideoGalleryPreloader } from '@/shared/hooks/gallery/useVideoGalleryPreloader';
import type { LoraModel } from '@/domains/lora/types/lora';
import { ShotSettingsEditor } from '../components/ShotEditor';
import {
  VideoTravelSettingsProvider,
  useVideoTravelSettingsMutations,
} from '../providers';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { VideoTravelFloatingOverlay } from '../components/VideoTravelFloatingOverlay';
import { useStickyHeader } from '../hooks/useStickyHeader';
import { useNavigationState } from '../hooks/navigation/useNavigationState';
import { useOperationTracking } from '../hooks/useOperationTracking';
import { usePanesStore } from '@/shared/state/panesStore';

interface ShotEditorViewProps {
  /** The shot to edit */
  shotToEdit: Shot;
  /** Selected project ID */
  selectedProjectId: string;
  /** Whether this is a newly created shot */
  isNewlyCreatedShot: boolean;
  /** Shot data from navigation state (for optimistic updates) */
  shotFromState: Shot | undefined;
  /** Array of all shots (for navigation) */
  shots: Shot[] | undefined;
  /** Available LoRAs */
  availableLoras: LoraModel[];
  /** Sort mode for shot navigation */
  shotSortMode?: 'ordered' | 'newest' | 'oldest';
}

/**
 * Shot editor view - wraps ShotSettingsEditor with all necessary setup.
 * Handles settings, navigation, and state coordination.
 */
export function ShotEditorView({
  shotToEdit,
  selectedProjectId,
  isNewlyCreatedShot,
  shotFromState,
  shots,
  availableLoras,
  shotSortMode = 'ordered',
}: ShotEditorViewProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();

  const { setCurrentShotId } = useCurrentShot();
  const { navigateToPreviousShot, navigateToNextShot } = useShotNavigation();
  const updateShotNameMutation = useUpdateShotName();
  const updateShotNameMutateRef = useRef(updateShotNameMutation.mutate);
  updateShotNameMutateRef.current = updateShotNameMutation.mutate;
  const invalidateGenerations = useEnqueueGenerationsInvalidation();

  // Get generation location settings to auto-disable turbo mode when not in cloud
  const { value: generationMethods } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });
  const isCloudGenerationEnabled = generationMethods.inCloud;

  // Project caches
  const { getFinalVideoCount, getHasStructureVideo } = useProjectVideoCountsCache(selectedProjectId);
  const { updateShotMode } = useProjectGenerationModesCache(selectedProjectId);

  // Dimension state (local, not persisted)
  const [dimensionSource, setDimensionSource] = useState<'project' | 'firstImage' | 'custom'>('firstImage');
  const [customWidth, setCustomWidth] = useState<number | undefined>(undefined);
  const [customHeight, setCustomHeight] = useState<number | undefined>(undefined);

  const handleDimensionSourceChange = useCallback((source: 'project' | 'firstImage' | 'custom') => {
    setDimensionSource(source);
  }, []);

  const handleCustomWidthChange = useCallback((width?: number) => {
    setCustomWidth(width);
  }, []);

  const handleCustomHeightChange = useCallback((height?: number) => {
    setCustomHeight(height);
  }, []);

  // Navigation state
  const { sortedShots, hasPrevious, hasNext } = useNavigationState({
    shots,
    shotSortMode,
    selectedShot: shotToEdit,
  });

  // Video gallery thumbnail preloader
  useVideoGalleryPreloader({
    selectedShot: shotToEdit,
    shouldShowShotEditor: true,
  });

  // Operation tracking
  const {
    setIsDraggingInTimeline,
    signalShotOperation,
  } = useOperationTracking();

  // Prime the shot images cache with context data for instant display
  const contextImages = shotToEdit.images || [];
  usePrimeShotImagesCache(shotToEdit.id, contextImages);
  // NOTE: useShotImages query is active in useShotEditorSetup — no need for a
  // duplicate observer here. The duplicate caused ShotEditorView to re-render
  // on every query state change (loading→success), cascading to all children.

  // Sticky header
  const headerContainerRef = useRef<HTMLDivElement>(null) as MutableRefObject<HTMLDivElement | null>;
  const [headerReady, setHeaderReady] = useState(false);
  const headerCallbackRef = useCallback((node: HTMLDivElement | null) => {
    headerContainerRef.current = node;
    setHeaderReady(!!node);
  }, []);

  const nameClickRef = useRef<(() => void) | null>(null);

  const stickyHeader = useStickyHeader({
    headerRef: headerContainerRef,
    isMobile,
    enabled: headerReady
  });

  // Pane widths for floating overlay
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const shotsPaneWidth = usePanesStore((state) => state.shotsPaneWidth);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);

  // Navigation handlers
  const handleBackToShotList = useCallback(() => {
    setCurrentShotId(null);
    navigate(location.pathname, { replace: true, state: { fromShotClick: false } });
  }, [setCurrentShotId, navigate, location.pathname]);

  const handlePreviousShot = useCallback(() => {
    if (sortedShots && shotToEdit) {
      navigateToPreviousShot(sortedShots, shotToEdit, { scrollToTop: true });
    }
  }, [sortedShots, shotToEdit, navigateToPreviousShot]);

  const handleNextShot = useCallback(() => {
    if (sortedShots && shotToEdit) {
      navigateToNextShot(sortedShots, shotToEdit, { scrollToTop: true });
    }
  }, [sortedShots, shotToEdit, navigateToNextShot]);

  const handlePreviousShotNoScroll = useCallback(() => {
    if (sortedShots && shotToEdit) {
      navigateToPreviousShot(sortedShots, shotToEdit, { scrollToTop: false });
    }
  }, [sortedShots, shotToEdit, navigateToPreviousShot]);

  const handleNextShotNoScroll = useCallback(() => {
    if (sortedShots && shotToEdit) {
      navigateToNextShot(sortedShots, shotToEdit, { scrollToTop: false });
    }
  }, [sortedShots, shotToEdit, navigateToNextShot]);

  const handleUpdateShotName = useCallback((newName: string) => {
    updateShotNameMutateRef.current({
      shotId: shotToEdit.id,
      newName: newName,
      projectId: selectedProjectId,
    });
  }, [shotToEdit.id, selectedProjectId]);

  const handleShotImagesUpdate = useCallback(async () => {
    invalidateGenerations(shotToEdit.id, {
      reason: 'shot-operation-complete',
      scope: 'all',
      includeShots: true,
      projectId: selectedProjectId
    });
    signalShotOperation();
  }, [selectedProjectId, shotToEdit.id, invalidateGenerations, signalShotOperation]);

  const handleFloatingHeaderNameClick = useCallback(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setTimeout(() => {
      if (nameClickRef.current) {
        nameClickRef.current();
      }
    }, 600);
  }, []);

  return (
    <>
      <div className="px-4 max-w-7xl mx-auto pt-4">
        <Suspense fallback={<LoadingSkeleton type="editor" />}>
          <VideoTravelSettingsProvider
            projectId={selectedProjectId}
            shotId={shotToEdit.id}
            selectedShot={shotToEdit}
            availableLoras={availableLoras}
            updateShotMode={updateShotMode}
          >
            <SettingsAutoDisable shotId={shotToEdit.id} isCloudGenerationEnabled={isCloudGenerationEnabled} />
            <ShotSettingsEditor
              // Core identifiers
              selectedShotId={shotToEdit.id}
              projectId={selectedProjectId}
              optimisticShotData={isNewlyCreatedShot ? shotFromState : undefined}
              // Callbacks
              onShotImagesUpdate={handleShotImagesUpdate}
              onBack={handleBackToShotList}
              // Dimension settings
              dimensionSource={dimensionSource}
              onDimensionSourceChange={handleDimensionSourceChange}
              customWidth={customWidth}
              onCustomWidthChange={handleCustomWidthChange}
              customHeight={customHeight}
              onCustomHeightChange={handleCustomHeightChange}
              // Navigation
              onPreviousShot={handlePreviousShot}
              onNextShot={handleNextShot}
              hasPrevious={hasPrevious}
              hasNext={hasNext}
              onUpdateShotName={handleUpdateShotName}
              // Loading and cache
              getFinalVideoCount={getFinalVideoCount}
              getHasStructureVideo={getHasStructureVideo}
              // UI coordination
              onDragStateChange={setIsDraggingInTimeline}
              headerContainerRef={headerCallbackRef}
              nameClickRef={nameClickRef}
              isSticky={stickyHeader.isSticky}
            />
          </VideoTravelSettingsProvider>
        </Suspense>
      </div>

      {/* Floating sticky header */}
      <VideoTravelFloatingOverlay
        sticky={{
          shouldShowShotEditor: true,
          stickyHeader,
          shotToEdit,
          isMobile,
          isShotsPaneLocked,
          shotsPaneWidth,
          isTasksPaneLocked,
          tasksPaneWidth,
          hasPrevious,
          hasNext,
          onPreviousShot: handlePreviousShotNoScroll,
          onNextShot: handleNextShotNoScroll,
          onBackToShotList: handleBackToShotList,
          onFloatingHeaderNameClick: handleFloatingHeaderNameClick,
        }}
      />
    </>
  );
}

/**
 * Renderless component that auto-disables conflicting settings.
 * Lives inside VideoTravelSettingsProvider to access settings context.
 */
function SettingsAutoDisable({ shotId, isCloudGenerationEnabled }: {
  shotId: string;
  isCloudGenerationEnabled: boolean;
}) {
  const { settings, status, shotId: loadedShotId, updateField, updateFields } =
    useVideoTravelSettingsMutations();
  const { turboMode = false, advancedMode = false } = settings;

  // Auto-disable turbo mode when cloud generation is disabled
  useEffect(() => {
    if (status !== 'ready' || loadedShotId !== shotId) return;
    if (!isCloudGenerationEnabled && turboMode) updateField('turboMode', false);
  }, [isCloudGenerationEnabled, turboMode, status, loadedShotId, shotId, updateField]);

  // Auto-disable advanced mode when turbo mode is on
  useEffect(() => {
    if (status !== 'ready' || loadedShotId !== shotId) return;
    if (turboMode && advancedMode) updateFields({ advancedMode: false, motionMode: 'basic' });
  }, [turboMode, advancedMode, status, loadedShotId, shotId, updateFields]);

  return null;
}

/**
 * Loading state shown while waiting for shot data.
 */
export function ShotEditorLoading() {
  return (
    <div className="px-4 max-w-7xl mx-auto pt-4">
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading shot...</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Error state shown when shot is not found.
 */
export function ShotEditorNotFound({ onBack }: { onBack: () => void }) {
  return (
    <div className="px-4 max-w-7xl mx-auto pt-4">
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">Shot not found</p>
          <Button onClick={onBack} variant="outline" size="sm">
            Back to Shots
          </Button>
        </div>
      </div>
    </div>
  );
}
