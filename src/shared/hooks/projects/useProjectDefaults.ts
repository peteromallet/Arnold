import { useEffect } from 'react';
import { usePrefetchToolSettings } from '@/shared/hooks/settings/usePrefetchToolSettings';
import { useMobileTimeoutFallback } from '@/shared/hooks/useMobileTimeoutFallback';
import { Project } from '@/types/project';

interface UseProjectDefaultsOptions {
  userId: string | null;
  selectedProjectId: string | null;
  isLoadingProjects: boolean;
  projects: Project[];
  fetchProjects: () => Promise<void>;
  applyCrossDeviceSync: (projects: Project[]) => void;
}

/**
 * Orchestrates project-related side effects:
 * - Triggers fetchProjects when userId is available
 * - Cross-device sync when preferences + projects are both loaded
 * - Prefetches tool settings for the selected project
 * - Mobile timeout fallback for stalled fetches
 */
export function useProjectDefaults({
  userId,
  selectedProjectId,
  isLoadingProjects,
  projects,
  fetchProjects,
  applyCrossDeviceSync,
}: UseProjectDefaultsOptions) {
  // Prefetch all tool settings for the currently selected project
  usePrefetchToolSettings(selectedProjectId);

  // Trigger initial project fetch when userId becomes available.
  // Intentionally omits isLoadingPreferences — that caused a triple-fetch
  // (userId ready → prefs start loading → prefs done) on every startup.
  // fetchProjects is also excluded because it rebuilds when selectedProjectId
  // changes after the first fetch, which would trigger a cascade re-fetch.
  // The mobile timeout fallback below handles any stalled initial fetch.
   
  useEffect(() => {
    if (userId) {
      fetchProjects();
    }
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cross-device sync: apply server preferences once projects + prefs are loaded
  useEffect(() => {
    if (projects.length > 0) {
      applyCrossDeviceSync(projects);
    }
  }, [projects, applyCrossDeviceSync]);

  // [MobileStallFix] Fallback recovery: retry fetch if projects loading stalls
  useMobileTimeoutFallback({
    isLoading: isLoadingProjects,
    onTimeout: fetchProjects,
    mobileTimeoutMs: 15000,
    desktopTimeoutMs: 10000,
    enabled: !!userId,
  });
}
