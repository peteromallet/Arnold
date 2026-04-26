import { useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import {
  getCurrentAppEnv,
  isHomeToolPathActive,
  resolveHomeToolPath,
} from '@/shared/lib/tooling/homeNavigation';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { usePanesStore } from '@/shared/state/panesStore';
import { videoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults';

const FALLBACK_GENERATION_METHODS = { onComputer: true, inCloud: true };

export function useHomeNavigation() {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedProjectId } = useProjectSelectionContext();
  const setIsShotsPaneLocked = usePanesStore((state) => state.setIsShotsPaneLocked);
  const { value: defaultTool } = useUserUIState('defaultTool', {
    toolId: TOOL_IDS.TRAVEL_BETWEEN_IMAGES,
  });
  const { value: generationMethods, isLoading: isLoadingGenerationMethods } = useUserUIState(
    'generationMethods',
    FALLBACK_GENERATION_METHODS,
  );
  const { settings: videoEditorProjectSettings } = useToolSettings(videoEditorSettings.id, {
    projectId: selectedProjectId ?? undefined,
    enabled: Boolean(selectedProjectId),
  });

  const targetPath = useMemo(
    () =>
      resolveHomeToolPath({
        preferredToolId: defaultTool.toolId,
        currentEnv: getCurrentAppEnv(),
        isCloudGenerationEnabled: generationMethods.inCloud,
        isLoadingGenerationMethods,
        videoEditorTimelineId: videoEditorProjectSettings?.lastTimelineId,
      }),
    [
      defaultTool.toolId,
      generationMethods.inCloud,
      isLoadingGenerationMethods,
      videoEditorProjectSettings?.lastTimelineId,
    ],
  );

  const navigateHome = useCallback(() => {
    // Inside a video travel shot (deep-linked via hash): back out to the
    // shot list view first instead of the usual home behavior.
    if (
      location.pathname === '/tools/travel-between-images' &&
      location.hash
    ) {
      navigate(location.pathname, { replace: true, state: { fromShotClick: false } });
      return;
    }

    if (isHomeToolPathActive(location.pathname, targetPath)) {
      setIsShotsPaneLocked(true);
      return;
    }

    setIsShotsPaneLocked(false);
    navigate(targetPath);
  }, [location.pathname, location.hash, navigate, setIsShotsPaneLocked, targetPath]);

  return {
    targetPath,
    navigateHome,
  };
}
