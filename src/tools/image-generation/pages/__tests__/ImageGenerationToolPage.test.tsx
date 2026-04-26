import { describe, it, expect, vi } from 'vitest';
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: vi.fn(() => vi.fn()), useParams: vi.fn(() => ({})), useSearchParams: vi.fn(() => [new URLSearchParams(), vi.fn()]), useLocation: vi.fn(() => ({ pathname: '/', search: '', hash: '', state: null })) };
});
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
vi.mock('@/features/resources/hooks/useResources', () => ({ usePublicLoras: vi.fn(() => ({ data: [] })), usePublicStyleReferences: vi.fn(() => ({ data: [] })), useMyStyleReferences: vi.fn(() => ({ data: [] })) }));
import ImageGenerationToolPage from '../ImageGenerationToolPage';

describe('ImageGenerationToolPage', () => {
  it('exports a component', () => {
    expect(ImageGenerationToolPage).toBeDefined();
    expect(typeof ImageGenerationToolPage === 'function' || typeof ImageGenerationToolPage === 'object').toBe(true);
    expect(ImageGenerationToolPage).not.toBeNull();
    expect(String(ImageGenerationToolPage)).toBeDefined();
  });
});
