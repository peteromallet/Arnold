import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useOnboardingFlow } from './useOnboardingFlow';

const {
  navigateMock,
  closeOnboardingModalMock,
  startTourMock,
  handleErrorMock,
  maybeSingleMock,
  eqMock,
  selectMock,
  fromMock,
  getSupabaseClientResultMock,
  useUserUIStateMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  closeOnboardingModalMock: vi.fn(),
  startTourMock: vi.fn(),
  handleErrorMock: vi.fn(),
  maybeSingleMock: vi.fn(),
  eqMock: vi.fn(),
  selectMock: vi.fn(),
  fromMock: vi.fn(),
  getSupabaseClientResultMock: vi.fn(),
  useUserUIStateMock: vi.fn(),
}));

const queryBuilder = {
  select: selectMock,
  eq: eqMock,
  maybeSingle: maybeSingleMock,
};

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClientResult: () => getSupabaseClientResultMock(),
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: handleErrorMock,
}));

vi.mock('@/shared/hooks/useOnboarding', () => ({
  useOnboarding: () => ({
    showOnboardingModal: false,
    closeOnboardingModal: closeOnboardingModalMock,
  }),
}));

vi.mock('@/shared/hooks/useUserUIState', () => ({
  useUserUIState: useUserUIStateMock,
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: () => ({
    selectedProjectId: 'project-1',
  }),
  useProjectSelectionContext: () => ({
    selectedProjectId: 'project-1',
    project: null,
    setSelectedProjectId: vi.fn(),
  }),
  useProjectCrudContext: () => ({
    projects: [],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  }),
  useProjectIdentityContext: () => ({ userId: null }),
}));

vi.mock('@/shared/hooks/useProductTour', () => ({
  useProductTour: () => ({
    startTour: startTourMock,
  }),
}));

describe('useOnboardingFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    selectMock.mockReturnValue(queryBuilder);
    eqMock.mockReturnValue(queryBuilder);
    fromMock.mockReturnValue(queryBuilder);
    getSupabaseClientResultMock.mockReturnValue({
      ok: true,
      client: {
        from: fromMock,
      },
    });
  });

  it('closes modal, navigates to getting started shot, and starts product tour', async () => {
    maybeSingleMock.mockResolvedValue({
      data: { id: 'shot-getting-started' },
    });

    const { result, unmount } = renderHook(() => useOnboardingFlow());

    await act(async () => {
      await result.current.handleOnboardingClose();
    });

    expect(closeOnboardingModalMock).toHaveBeenCalledTimes(1);
    expect(fromMock).toHaveBeenCalledWith('shots');
    expect(navigateMock).toHaveBeenCalledWith('/tools/travel-between-images?shot=shot-getting-started');

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(startTourMock).toHaveBeenCalledTimes(1);

    unmount();
    vi.useRealTimers();
  });

  it('reports errors from shot lookup without throwing', async () => {
    maybeSingleMock.mockRejectedValue(new Error('lookup failed'));

    const { result, unmount } = renderHook(() => useOnboardingFlow());

    await act(async () => {
      await result.current.handleOnboardingClose();
    });

    expect(closeOnboardingModalMock).toHaveBeenCalledTimes(1);
    expect(handleErrorMock).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        context: 'useOnboardingFlow.handleOnboardingClose',
        showToast: false,
      })
    );
    expect(startTourMock).not.toHaveBeenCalled();

    unmount();
    vi.useRealTimers();
  });

  it('reports runtime access errors when supabase client is unavailable', async () => {
    getSupabaseClientResultMock.mockReturnValue({
      ok: false,
      error: new Error('runtime unavailable'),
    });

    const { result, unmount } = renderHook(() => useOnboardingFlow());

    await act(async () => {
      await result.current.handleOnboardingClose();
    });

    expect(handleErrorMock).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        context: 'useOnboardingFlow.supabaseUnavailable',
        showToast: false,
      }),
    );
    expect(fromMock).not.toHaveBeenCalled();
    expect(startTourMock).not.toHaveBeenCalled();

    unmount();
    vi.useRealTimers();
  });
});
