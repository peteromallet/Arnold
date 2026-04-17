import { useEffect } from 'react';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';

type ProjectContextDebugInfo = {
  timestamp: string;
  isMobile: boolean;
  projectsCount: number;
  selectedProjectId: string;
  isLoadingProjects: boolean;
  userAgent: string;
};

const projectDebugLog: ProjectContextDebugInfo[] = [];

export function getProjectContextDebugLog(): ProjectContextDebugInfo[] {
  return projectDebugLog;
}

/**
 * Debug hook to monitor ProjectContext state changes on mobile.
 * Enable by setting DEBUG_PROJECT_CONTEXT=true in localStorage.
 */
export const useProjectContextDebug = (enabled: boolean = import.meta.env.DEV) => {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects, isLoadingProjects } = useProjectCrudContext();

  useEffect(() => {
    // Never run project debug instrumentation outside an explicitly enabled local dev runtime.
    if (!enabled || !import.meta.env.DEV || typeof window === 'undefined') {
      return;
    }

    const isDebugEnabled = localStorage.getItem('DEBUG_PROJECT_CONTEXT') === 'true';
    if (!isDebugEnabled) {
      return;
    }

    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const debugInfo = {
      timestamp: new Date().toISOString(),
      isMobile,
      projectsCount: projects.length,
      selectedProjectId: selectedProjectId || 'null',
      isLoadingProjects,
      userAgent: navigator.userAgent,
    };

    projectDebugLog.push(debugInfo);

    // Keep only last 50 entries.
    if (projectDebugLog.length > 50) {
      projectDebugLog.splice(0, projectDebugLog.length - 50);
    }
  }, [enabled, projects, selectedProjectId, isLoadingProjects]);
};
