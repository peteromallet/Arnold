import { useState, useRef, useLayoutEffect, useCallback } from 'react';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useTaskStatusCounts } from '@/shared/hooks/tasks/useTaskStatusCounts';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useEditSettingsPersistence } from '../persistence/useEditSettingsPersistence';
import { extractDimensionsFromMedia } from '../../utils/dimensions';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import type { GenerationRow } from '@/domains/generation/types';
import type { SegmentSlotModeData } from '../../types';
import type { VideoEditSubMode } from '../../model/editSettingsTypes';
import { usePanesStore } from '@/shared/state/panesStore';

import type { LightboxNavigationProps } from '../../types';

interface VideoLightboxModeOptions {
  segmentSlotMode?: SegmentSlotModeData;
  navigation?: LightboxNavigationProps;
}

function resolveInitialVideoEditSubMode(
  selectedProjectId: string | null,
  initialVideoTrimMode?: boolean,
): VideoEditSubMode | null {
  if (initialVideoTrimMode) {
    return 'trim';
  }

  try {
    const projectKey = selectedProjectId ? `lightbox-edit-last-used-${selectedProjectId}` : null;
    const stored = projectKey
      ? localStorage.getItem(projectKey)
      : localStorage.getItem('lightbox-edit-last-used-global');

    if (!stored) {
      return null;
    }

    const parsed = JSON.parse(stored);
    if (parsed.panelMode === 'edit' && parsed.videoEditSubMode) {
      return parsed.videoEditSubMode;
    }
  } catch {
    return null;
  }

  return null;
}

export function useVideoLightboxMode(options: VideoLightboxModeOptions) {
  const {
    segmentSlotMode,
    navigation,
  } = options;
  const hasNextProp = navigation?.hasNext ?? false;
  const hasPreviousProp = navigation?.hasPrevious ?? false;
  const onNext = navigation?.onNext;
  const onPrevious = navigation?.onPrevious;

  const isSegmentSlotMode = !!segmentSlotMode;
  const hasSegmentVideo = isSegmentSlotMode && !!segmentSlotMode.segmentVideo;
  const isFormOnlyMode = isSegmentSlotMode && !hasSegmentVideo;

  const hasNext = isSegmentSlotMode
    ? segmentSlotMode.currentIndex < segmentSlotMode.totalPairs - 1
    : hasNextProp;

  const hasPrevious = isSegmentSlotMode
    ? segmentSlotMode.currentIndex > 0
    : hasPreviousProp;

  const handleSlotNavNext = useCallback(() => {
    if (isSegmentSlotMode) {
      segmentSlotMode.onNavigateToPair(segmentSlotMode.currentIndex + 1);
      return;
    }
    if (onNext) {
      onNext();
    }
  }, [isSegmentSlotMode, onNext, segmentSlotMode]);

  const handleSlotNavPrev = useCallback(() => {
    if (isSegmentSlotMode) {
      segmentSlotMode.onNavigateToPair(segmentSlotMode.currentIndex - 1);
      return;
    }
    if (onPrevious) {
      onPrevious();
    }
  }, [isSegmentSlotMode, onPrevious, segmentSlotMode]);

  return {
    isSegmentSlotMode,
    hasSegmentVideo,
    isFormOnlyMode,
    hasNext,
    hasPrevious,
    handleSlotNavNext,
    handleSlotNavPrev,
  };
}

export type VideoLightboxModeModel = ReturnType<typeof useVideoLightboxMode>;

interface VideoLightboxEnvironmentOptions {
  media?: GenerationRow;
  tasksPaneOpen?: boolean;
  tasksPaneWidth?: number;
  variantFetchGenerationIdOverride?: string;
  videoProps?: {
    fetchVariantsForSelf?: boolean;
    initialVideoTrimMode?: boolean;
  };
}

export function useVideoLightboxEnvironment(
  options: VideoLightboxEnvironmentOptions,
  modeModel: VideoLightboxModeModel,
) {
  const { media, tasksPaneOpen, tasksPaneWidth, variantFetchGenerationIdOverride } = options;
  const fetchVariantsForSelf = options.videoProps?.fetchVariantsForSelf;
  const initialVideoTrimMode = options.videoProps?.initialVideoTrimMode;

  const isMobile = useIsMobile();
  const { project, selectedProjectId } = useProjectSelectionContext();
  const projectAspectRatio = project?.aspectRatio;
  const { value: generationMethods } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });
  const isCloudMode = generationMethods.inCloud;

  const tasksPaneOpenContext = usePanesStore((state) => state.isTasksPaneOpen);
  const tasksPaneWidthContext = usePanesStore((state) => state.tasksPaneWidth);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);

  const effectiveTasksPaneOpen = tasksPaneOpen ?? tasksPaneOpenContext;
  const effectiveTasksPaneWidth = tasksPaneWidth ?? tasksPaneWidthContext;

  useTaskStatusCounts(selectedProjectId);

  const contentRef = useRef<HTMLDivElement>(null);
  const variantsSectionRef = useRef<HTMLDivElement>(null);

  const [isDownloading, setIsDownloading] = useState(false);
  const [replaceImages, setReplaceImages] = useState(true);
  const [variantParamsToLoad, setVariantParamsToLoad] = useState<Record<string, unknown> | null>(null);

  const actualGenerationId = getGenerationId(media) || null;
  const variantFetchGenerationId = variantFetchGenerationIdOverride
    || (fetchVariantsForSelf
      ? actualGenerationId
      : (media?.parent_generation_id || actualGenerationId));

  const [videoEditSubMode, setVideoEditSubModeLocal] = useState<VideoEditSubMode | null>(() => {
    return resolveInitialVideoEditSubMode(selectedProjectId, initialVideoTrimMode);
  });

  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(() => {
    return media ? extractDimensionsFromMedia(media) : null;
  });

  useLayoutEffect(() => {
    if (!media) {
      return;
    }

    const dims = extractDimensionsFromMedia(media);
    if (dims) {
      setImageDimensions(dims);
    }
  }, [media]);

  const effectiveImageUrl = media?.imageUrl || media?.location || '';

  const editSettingsPersistence = useEditSettingsPersistence({
    generationId: actualGenerationId,
    projectId: selectedProjectId,
    enabled: !modeModel.isFormOnlyMode,
  });

  const {
    enhanceSettings,
    setEnhanceSettings,
    videoEditSubMode: persistedVideoEditSubMode,
    panelMode: persistedPanelMode,
    setVideoEditSubMode: setPersistedVideoEditSubMode,
    setPanelMode: setPersistedPanelMode,
  } = editSettingsPersistence;

  const setVideoEditSubMode = useCallback((value: VideoEditSubMode | null) => {
    setVideoEditSubModeLocal(value);
    if (value) {
      setPersistedVideoEditSubMode(value);
    }
  }, [setPersistedVideoEditSubMode]);

  return {
    isMobile,
    selectedProjectId,
    projectAspectRatio,
    isCloudMode,
    isTasksPaneLocked,
    effectiveTasksPaneOpen,
    effectiveTasksPaneWidth,
    contentRef,
    variantsSectionRef,
    isDownloading,
    setIsDownloading,
    replaceImages,
    setReplaceImages,
    variantParamsToLoad,
    setVariantParamsToLoad,
    actualGenerationId,
    variantFetchGenerationId,
    videoEditSubMode,
    setVideoEditSubMode,
    imageDimensions,
    setImageDimensions,
    effectiveImageUrl,
    editSettingsPersistence,
    enhanceSettings,
    setEnhanceSettings,
    persistedVideoEditSubMode,
    persistedPanelMode,
    setPersistedPanelMode,
  };
}

export type VideoLightboxEnvironment = ReturnType<typeof useVideoLightboxEnvironment>;
