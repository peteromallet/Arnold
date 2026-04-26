import React, { useMemo, useRef } from 'react';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useShotImages } from '@/shared/hooks/shots/useShotImages';
import { Shot, GenerationRow } from '@/domains/generation/types';
import {
  selectTimelineImages,
  selectUnpositionedImages,
  selectVideoOutputs,
} from '@/shared/lib/shotImageSelectors';
import { compareByCreatedAtDesc } from '@/shared/lib/sorting/createdAtSort';
import type { Project } from '@/types/project';

interface UseShotEditorSetupProps {
  selectedShotId: string;
  projectId: string;
  optimisticShotData?: Shot;
  batchVideoFrames: number;
}

interface UseShotEditorSetupReturn {
  // Shot resolution
  selectedShot: Shot | undefined;
  foundShot: Shot | undefined;
  shots: Shot[] | undefined;

  // Project data
  selectedProjectId: string;
  projects: Project[];

  // Aspect ratio
  effectiveAspectRatio: string | undefined;

  // Image data (from queries/selectors)
  allShotImages: GenerationRow[];
  timelineImages: GenerationRow[];
  unpositionedImages: GenerationRow[];
  videoOutputs: GenerationRow[];
  contextImages: GenerationRow[];
  isLoadingFullImages: boolean;

  // Initial parent generations (for fast FinalVideoSection render)
  initialParentGenerations: GenerationRow[];

  // Stability refs for callbacks
  refs: {
    selectedShotRef: React.MutableRefObject<Shot | undefined>;
    projectIdRef: React.MutableRefObject<string>;
    allShotImagesRef: React.MutableRefObject<GenerationRow[]>;
    batchVideoFramesRef: React.MutableRefObject<number>;
  };
}

export function useShotEditorSetup({
  selectedShotId,
  projectId,
  optimisticShotData,
  batchVideoFrames,
}: UseShotEditorSetupProps): UseShotEditorSetupReturn {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const { shots } = useShots();

  const foundShot = useMemo(
    () => shots?.find(shot => shot.id === selectedShotId),
    [shots, selectedShotId]
  );
  const lastValidShotRef = useRef<Shot | undefined>();

  // Update ref if we found the shot
  if (foundShot) {
    lastValidShotRef.current = foundShot;
  }

  // Preserve the last resolved shot while the shots list is transiently reloading.
  const selectedShot = foundShot || optimisticShotData || (shots === undefined ? lastValidShotRef.current : undefined);

  const selectedShotRef = useRef(selectedShot);
  selectedShotRef.current = selectedShot;
  const projectIdRef = useRef(projectId);
  projectIdRef.current = projectId;

  const effectiveAspectRatio = useMemo(() => {
    const projectAspectRatio = projects.find(p => p.id === projectId)?.aspectRatio;
    return selectedShot?.aspect_ratio || projectAspectRatio;
  }, [selectedShot?.aspect_ratio, projects, projectId]);

  const contextImages = useMemo(
    () => selectedShot?.images ?? [],
    [selectedShot?.images]
  );

  const shouldLoadDetailedData = useMemo(
    () => !!selectedShotId,
    [selectedShotId]
  );

  const queryKey = shouldLoadDetailedData ? selectedShotId : null;

  const fullImagesQueryResult = useShotImages(queryKey, {
    disableRefetch: false,
  });

  const fullShotImages = useMemo(
    () => fullImagesQueryResult.data ?? [],
    [fullImagesQueryResult.data]
  );
  const isLoadingFullImages = fullImagesQueryResult.isLoading;

  // Keep using context images until the detailed query catches up.
  const allShotImages = useMemo(() => {
    return fullShotImages.length > 0 ? fullShotImages : contextImages;
  }, [fullShotImages, contextImages]);

  const timelineImages = useMemo(() => {
    return selectTimelineImages(allShotImages);
  }, [allShotImages]);

  const unpositionedImages = useMemo(() => {
    return selectUnpositionedImages(allShotImages);
  }, [allShotImages]);

  const videoOutputs = useMemo(() => {
    return selectVideoOutputs(allShotImages);
  }, [allShotImages]);

  const initialParentGenerations = useMemo(() => {
    return videoOutputs
      .filter(v => {
        const params = v.params as Record<string, unknown> | null;
        return params?.orchestrator_details != null;
      })
      .sort(compareByCreatedAtDesc);
  }, [videoOutputs]);

  const allShotImagesRef = useRef<GenerationRow[]>(allShotImages);
  allShotImagesRef.current = allShotImages;
  const batchVideoFramesRef = useRef(batchVideoFrames);
  batchVideoFramesRef.current = batchVideoFrames;

  return {
    // Shot resolution
    selectedShot,
    foundShot,
    shots,

    // Project data
    selectedProjectId: selectedProjectId ?? projectId,
    projects,

    // Aspect ratio
    effectiveAspectRatio,

    // Image data
    allShotImages,
    timelineImages,
    unpositionedImages,
    videoOutputs,
    contextImages,
    isLoadingFullImages,
    initialParentGenerations,

    // Stability refs
    refs: {
      selectedShotRef,
      projectIdRef,
      allShotImagesRef,
      batchVideoFramesRef,
    },
  };
}
