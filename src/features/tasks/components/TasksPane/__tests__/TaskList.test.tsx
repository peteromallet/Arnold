import { describe, it, expect, vi } from 'vitest';
vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: vi.fn(() => ({ selectedProjectId: 'test' })),
  useProjectSelectionContext: vi.fn(() => ({ selectedProjectId: 'test', project: null, setSelectedProjectId: vi.fn() })),
  useProjectCrudContext: vi.fn(() => ({
    projects: [],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  })),
  useProjectIdentityContext: vi.fn(() => ({ userId: null })),
}));
import { TaskList } from '../TaskList';

describe('TaskList', () => {
  it('exports a component', () => {
    expect(TaskList).toBeDefined();
    expect(typeof TaskList === 'function' || typeof TaskList === 'object').toBe(true);
  });
});
