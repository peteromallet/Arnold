import React from 'react';
import { useLocation } from 'react-router-dom';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useVideoTravelData } from '../hooks/workflow/useVideoTravelData';
import { useHashDeepLink } from '../hooks/navigation/useHashDeepLink';
import { useUrlSync } from '../hooks/navigation/useUrlSync';
import { useSelectedShotResolution } from '../hooks/settings/useSelectedShotResolution';
import { useStableSkeletonVisibility } from '../hooks/video/useStableSkeletonVisibility';
import { useProjectVideoCountsCache } from '@/shared/hooks/projects/useProjectVideoCountsCache';
import {
  VideoTravelContent,
  useProjectErrorTimer,
  useResetShotOnMount,
  useScrollToTopOnHashChange,
  useShotSortModeState,
  useSyncCurrentShotId,
  type ShotEditorViewProps,
  type ShotListViewProps,
} from './videoTravelPageModel';

/**
 * VideoTravelToolPage - Main page for the travel-between-images tool.
 *
 * This is a thin router that:
 * 1. Handles project/shot resolution from URL hash
 * 2. Decides whether to show list view or editor view
 * 3. Delegates all logic to child components
 */
const VideoTravelToolPage: React.FC = () => {
  const location = useLocation();
  const viaShotClick = location.state?.fromShotClick === true;
  const shotFromState = location.state?.shotData;
  const isNewlyCreatedShot = location.state?.isNewlyCreated === true;

  const { selectedProjectId, setSelectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const { currentShotId, setCurrentShotId } = useCurrentShot();

  // Warm the project video counts cache (includes structure video presence)
  // so it's ready by the time the user clicks into a shot editor
  useProjectVideoCountsCache(selectedProjectId);

  // Get current project's aspect ratio
  const currentProject = projects.find(project => project.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio;

  useScrollToTopOnHashChange(location.hash);

  // Fetch shots and related data
  const {
    shots,
    shotsLoading,
    shotsError,
    refetchShots,
    availableLoras,
    projectUISettings,
    updateProjectUISettings,
    uploadSettings,
  } = useVideoTravelData(currentShotId, selectedProjectId);

  const { shotSortMode, setShotSortMode } = useShotSortModeState(
    projectUISettings?.shotSortMode,
    updateProjectUISettings,
  );

  // Hash-based deep linking (extracts hash, resolves project, manages grace period)
  const { hashShotId, hashLoadingGrace, initializingFromHash } = useHashDeepLink({
    currentShotId,
    setCurrentShotId,
    selectedProjectId,
    setSelectedProjectId,
    shots,
    shotsLoading,
    shotFromState,
    isNewlyCreatedShot,
  });

  // Shot resolution (selectedShot, shotToEdit, shouldShowEditor)
  const { selectedShot, shotToEdit, shouldShowEditor } = useSelectedShotResolution({
    currentShotId,
    shots,
    shotFromState,
    isNewlyCreatedShot,
    hashShotId,
    hashLoadingGrace,
    viaShotClick,
  });

  // URL sync (keeps hash in sync with selection - called after we have selectedShot)
  useUrlSync({
    selectedShot,
    shotsLoading,
    shots,
    shotFromState,
    viaShotClick,
    setCurrentShotId,
  });

  // Loading state (include projectUISettings to avoid sort-mode flash)
  const isLoading = shotsLoading || initializingFromHash || (!!selectedProjectId && projectUISettings === undefined);
  const showStableSkeleton = useStableSkeletonVisibility(isLoading);

  const showProjectError = useProjectErrorTimer(selectedProjectId);
  useSyncCurrentShotId(shotToEdit ?? undefined, currentShotId, setCurrentShotId);
  useResetShotOnMount(location.hash, viaShotClick, currentShotId, setCurrentShotId);

  const selectedProjectIdForProps = selectedProjectId ?? '';

  const shotEditorProps: Omit<ShotEditorViewProps, 'shotToEdit'> = {
    selectedProjectId: selectedProjectIdForProps,
    isNewlyCreatedShot,
    shotFromState,
    shots,
    availableLoras,
    shotSortMode,
  };

  const shotListProps: ShotListViewProps = {
    shots,
    selectedProjectId: selectedProjectIdForProps,
    projectAspectRatio,
    refetchShots,
    projectUISettings,
    updateProjectUISettings,
    uploadSettings,
    shotSortMode,
    setShotSortMode,
  };

  return (
    <VideoTravelContent
      selectedProjectId={selectedProjectId}
      showProjectError={showProjectError}
      hashShotId={hashShotId || null}
      shotsError={shotsError}
      showStableSkeleton={showStableSkeleton}
      shouldShowEditor={shouldShowEditor}
      shotToEdit={shotToEdit ?? undefined}
      isNewlyCreatedShot={isNewlyCreatedShot}
      hashLoadingGrace={hashLoadingGrace}
      locationPathname={location.pathname}
      setCurrentShotId={setCurrentShotId}
      shotEditorProps={shotEditorProps}
      shotListProps={shotListProps}
    />
  );
};

export default VideoTravelToolPage;
