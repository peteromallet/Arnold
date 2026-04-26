import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDarkMode } from '@/shared/hooks/core/useDarkMode';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';

interface UseGlobalHeaderProjectOptions {
  onOpenCreateProject: (initialName?: string) => void;
}

export function useGlobalHeaderProject({ onOpenCreateProject }: UseGlobalHeaderProjectOptions) {
  const navigate = useNavigate();
  const { darkMode } = useDarkMode();
  const { selectedProjectId, setSelectedProjectId } = useProjectSelectionContext();
  const { projects, isLoadingProjects } = useProjectCrudContext();

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  const handleProjectChange = useCallback((projectId: string) => {
    if (projectId === 'create-new') {
      onOpenCreateProject(undefined);
      return;
    }
    if (projectId !== selectedProjectId) {
      setSelectedProjectId(projectId);
      navigate('/tools');
    }
  }, [onOpenCreateProject, selectedProjectId, setSelectedProjectId, navigate]);

  return {
    darkMode,
    projects,
    selectedProject,
    isLoadingProjects,
    handleProjectChange,
  };
}
