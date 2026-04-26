import { describe, it, expect, vi } from 'vitest';
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: vi.fn(() => vi.fn()), useParams: vi.fn(() => ({})), useSearchParams: vi.fn(() => [new URLSearchParams(), vi.fn()]), useLocation: vi.fn(() => ({ pathname: '/', search: '', hash: '', state: null })) };
});
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn(), loading: vi.fn(), dismiss: vi.fn() } }));
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
import { TaskItem } from '../TaskItem';

describe('TaskItem', () => {
  it('exports a component', () => {
    expect(TaskItem).toBeDefined();
    expect(typeof TaskItem === 'function' || typeof TaskItem === 'object').toBe(true);
    expect(TaskItem).not.toBeNull();
    expect(String(TaskItem)).toBeDefined();
  });
});
