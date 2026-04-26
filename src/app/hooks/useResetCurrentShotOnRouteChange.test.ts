import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useResetCurrentShotOnRouteChange } from './useResetCurrentShotOnRouteChange';
import { TOOL_ROUTES } from '@/shared/lib/tooling/toolRoutes';

let currentPathname = TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES;
const setCurrentShotIdMock = vi.fn();

vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: currentPathname }),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useCurrentShot: () => ({
    setCurrentShotId: setCurrentShotIdMock,
  }),
}));

describe('useResetCurrentShotOnRouteChange', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentPathname = TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES;
  });

  it('clears current shot when leaving travel-between-images route', () => {
    const { rerender } = renderHook(() => useResetCurrentShotOnRouteChange());

    currentPathname = '/home';
    rerender();

    expect(setCurrentShotIdMock).toHaveBeenCalledTimes(1);
    expect(setCurrentShotIdMock).toHaveBeenCalledWith(null);
  });

  it('does not clear current shot when not leaving travel-between-images route', () => {
    currentPathname = '/home';
    const { rerender } = renderHook(() => useResetCurrentShotOnRouteChange());

    currentPathname = '/pricing';
    rerender();

    expect(setCurrentShotIdMock).not.toHaveBeenCalled();
  });
});
