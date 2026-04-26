import { createContext, useContext, ReactNode, useMemo } from 'react';
import { Project } from '@/types/project';
import { useRenderLogger } from '@/shared/lib/debug/debugRendering';
import { useProjectSessionCoordinator } from './useProjectSessionCoordinator';
import { requireContextValue } from './contextGuard';

// Type for updating projects (re-exported for consumers that may need it)
interface ProjectUpdate {
  name?: string;
  aspectRatio?: string;
}

interface ProjectSelectionContextType {
  selectedProjectId: string | null;
  project: Project | null;
  setSelectedProjectId: (projectId: string | null) => void;
}

interface ProjectCrudContextType {
  projects: Project[];
  isLoadingProjects: boolean;
  fetchProjects: () => Promise<void>;
  addNewProject: (projectData: { name: string; aspectRatio: string }) => Promise<Project | null>;
  isCreatingProject: boolean;
  updateProject: (projectId: string, updates: ProjectUpdate) => Promise<boolean>;
  isUpdatingProject: boolean;
  deleteProject: (projectId: string) => Promise<boolean>;
  isDeletingProject: boolean;
}

interface ProjectIdentityContextType {
  /** Current authenticated user ID, null if not logged in */
  userId: string | null;
}

interface ProjectContextType
  extends ProjectSelectionContextType,
    ProjectCrudContextType,
    ProjectIdentityContextType {}

const ProjectSelectionContext = createContext<ProjectSelectionContextType | undefined>(undefined);
const ProjectCrudContext = createContext<ProjectCrudContextType | undefined>(undefined);
const ProjectIdentityContext = createContext<ProjectIdentityContextType | undefined>(undefined);

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const { userId, selection, crud } = useProjectSessionCoordinator();
  useRenderLogger('ProjectProvider', { userId });

  const projects = crud.projects || [];
  const selectedProjectId = selection.selectedProjectId;
  const project = projects.find((item) => item.id === selectedProjectId) ?? null;

  const selectionValue = useMemo(
    (): ProjectSelectionContextType => ({
      selectedProjectId,
      project,
      setSelectedProjectId: selection.setSelectedProjectId,
    }),
    [selectedProjectId, project, selection.setSelectedProjectId],
  );

  const crudValue = useMemo(
    (): ProjectCrudContextType => ({
      projects: crud.projects || [],
      isLoadingProjects: crud.isLoadingProjects,
      fetchProjects: crud.fetchProjects,
      addNewProject: crud.addNewProject,
      isCreatingProject: crud.isCreatingProject,
      updateProject: crud.updateProject,
      isUpdatingProject: crud.isUpdatingProject,
      deleteProject: crud.deleteProject,
      isDeletingProject: crud.isDeletingProject,
    }),
    [
      crud.projects,
      crud.isLoadingProjects,
      crud.fetchProjects,
      crud.addNewProject,
      crud.isCreatingProject,
      crud.updateProject,
      crud.isUpdatingProject,
      crud.deleteProject,
      crud.isDeletingProject,
    ],
  );

  const identityValue = useMemo(
    (): ProjectIdentityContextType => ({
      userId: userId ?? null,
    }),
    [userId],
  );

  return (
    <ProjectIdentityContext.Provider value={identityValue}>
      <ProjectCrudContext.Provider value={crudValue}>
        <ProjectSelectionContext.Provider value={selectionValue}>
          {children}
        </ProjectSelectionContext.Provider>
      </ProjectCrudContext.Provider>
    </ProjectIdentityContext.Provider>
  );
};

export const useProjectSelectionContext = () => {
  return requireContextValue(
    useContext(ProjectSelectionContext),
    'useProjectSelectionContext',
    'ProjectProvider',
  );
};

export const useProjectCrudContext = () => {
  return requireContextValue(
    useContext(ProjectCrudContext),
    'useProjectCrudContext',
    'ProjectProvider',
  );
};

export const useProjectIdentityContext = () => {
  return requireContextValue(
    useContext(ProjectIdentityContext),
    'useProjectIdentityContext',
    'ProjectProvider',
  );
};

/** @deprecated Migrate production code to the split project hooks. */
export const useProject = () => {
  const selection = useProjectSelectionContext();
  const crud = useProjectCrudContext();
  const identity = useProjectIdentityContext();

  return useMemo<ProjectContextType>(() => ({
    ...crud,
    ...selection,
    ...identity,
  }), [crud, selection, identity]);
};
